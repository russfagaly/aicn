"""Gather candidate items via the Anthropic API web_search tool.

Cost-restructured discovery (2026-07): instead of one API call per watchlist
entity and per site target (19 calls/day at peak), discovery is now:

  - broad_search: one wide pass across the whole relevance space (unchanged).
  - ONE consolidated site-scoped call covering every due site target, using
    the web_search tool's allowed_domains parameter. 28 runs of attribution
    data showed 7 of 11 targets produced zero published items, so 11 calls x
    2 searches was massively over-provisioned.
  - Entity watchlist calls GROUPED ~5 entities per call. Grouping cut the
    per-entity cost enough to move every entity to daily cadence.

All discovery requests are submitted together through the Message Batches API
(50% off token costs; the daily cron doesn't care about latency). If batch
submission or polling fails, we fall back to direct per-request calls so a
batch-layer problem can't take out a whole day of discovery.

Each call asks the model to return ONLY a JSON array of items backed by real
search results (never invented URLs); we parse and tag discovery.method.
"""

import json
import re
import time

_RELEVANCE_RULES = """On-topic = AI intersecting with political campaigns, elections, or political/
issue advocacy: vendor & tool moves (launches, features, funding, M&A, shutdowns);
use cases by campaign department (fundraising, outreach/texting/calling, digital ads,
oppo research, field/canvassing, comms/rapid response, data & targeting, compliance);
deepfakes & synthetic media in elections; synthetic respondents / "silicon sampling" as
a polling replacement and the methodological debate; regulation & legal (FEC, FCC,
state deepfake/disclosure laws, NO FAKES Act, TAKE IT DOWN Act, preemption fights,
court rulings); notable deployments/case studies and credible academic studies;
substantive analysis/op-eds. EXCLUDE generic AI-industry news with no campaign/
election/advocacy nexus, and vague hype with no concrete development."""

_OUTPUT_FORMAT = """Return ONLY a JSON array (no markdown fences, no prose before or after) of
candidate items you found via actual web_search results. Each item:
{"title": str, "url": str, "source": str, "published": "YYYY-MM-DD or your best estimate"}
Only include items backed by a real search result URL you retrieved — never invent a
URL or guess one you didn't see in a result. If nothing relevant turned up, return []."""

_OUTPUT_FORMAT_ENTITY = """Return ONLY a JSON array (no markdown fences, no prose before or after) of
candidate items you found via actual web_search results. Each item:
{"title": str, "url": str, "source": str, "published": "YYYY-MM-DD or your best estimate",
 "matched_entity": "<exactly one of the watched entity names this item is about>"}
Only include items backed by a real search result URL you retrieved — never invent a
URL or guess one you didn't see in a result. If nothing relevant turned up, return []."""

# max_uses caps how many searches the model can run per call. Each search's
# page-content excerpt is the dominant cost driver (~10k+ input tokens per
# search), so these caps matter more for cost than for recall.
BROAD_MAX_USES = 2
SITES_MAX_USES = 5
ENTITY_MAX_USES = 3
ENTITY_GROUP_SIZE = 5

_BATCH_POLL_INTERVAL_S = 20
_BATCH_POLL_CAP_S = 30 * 60


def _extract_json_array(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []


def _search_tool(max_uses: int, allowed_domains: list | None = None) -> dict:
    tool = {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}
    if allowed_domains:
        tool["allowed_domains"] = allowed_domains
    return tool


# ---------------------------------------------------------------------------
# Request builders — each returns Messages API params (batch- and direct-safe)
# ---------------------------------------------------------------------------

def _broad_params(model: str) -> dict:
    system = (
        "You are a research assistant gathering candidate news items for AICN, a "
        "neutral tracker of AI use in political campaigns and elections.\n\n"
        + _RELEVANCE_RULES
        + "\n\nSearch broadly for items published within the last 7 days, beyond any "
        "single company or feed. "
        + _OUTPUT_FORMAT
    )
    user_message = (
        "Search the web for recent (last 7 days) news on AI use in political "
        "campaigns, elections, and political/issue advocacy. Cover vendor moves, "
        "deepfakes, synthetic polling, regulation, deployments, and substantive "
        "analysis. Cast a wide net."
    )
    return {
        "model": model,
        "max_tokens": 2000,
        "system": system,
        "tools": [_search_tool(BROAD_MAX_USES)],
        "messages": [{"role": "user", "content": user_message}],
    }


def _sites_params(model: str, targets: list) -> dict:
    """One consolidated call for all due site targets, constrained via
    allowed_domains so every search result comes from a watched outlet."""
    outlet_lines = "\n".join(f"- {t['name']} ({t['domain']})" for t in targets)
    domains = [t["domain"] for t in targets]
    system = (
        "You are a research assistant gathering candidate news items for AICN, a "
        "neutral tracker of AI use in political campaigns and elections.\n\n"
        + _RELEVANCE_RULES
        + "\n\nThis call covers a fixed set of large outlets where this beat is real "
        "but low-density. Your searches are restricted to these domains:\n"
        + outlet_lines
        + "\n\nUse varied queries to cover the beat across these outlets — each search "
        "returns results from any of them, so query by topic, not by outlet. Most of "
        "what these outlets publish won't be relevant, and that's expected. "
        + _OUTPUT_FORMAT
    )
    user_message = (
        "Search these outlets for recent (last 7 days) coverage of AI use in "
        "political campaigns, elections, or political/issue advocacy. Only return "
        "items that are genuinely on-topic."
    )
    return {
        "model": model,
        "max_tokens": 2000,
        "system": system,
        "tools": [_search_tool(SITES_MAX_USES, allowed_domains=domains)],
        "messages": [{"role": "user", "content": user_message}],
    }


def _entity_group_params(model: str, entities: list) -> dict:
    """One call watching a small group of entities (grouping is what made
    all-daily cadence affordable)."""
    entity_lines = "\n".join(f'- "{e["name"]}" ({e["kind"]})' for e in entities)
    system = (
        "You are a research assistant gathering candidate news items for AICN, a "
        "neutral tracker of AI use in political campaigns and elections.\n\n"
        + _RELEVANCE_RULES
        + "\n\nYou are watching this specific group of entities this call:\n"
        + entity_lines
        + "\n\nYou have a limited number of searches — combine related entities into "
        "one query where sensible, and prioritize entities most likely to have news. "
        + _OUTPUT_FORMAT_ENTITY
    )
    user_message = (
        "Search for recent (last 7 days) news about each watched entity in the "
        "context of AI and political campaigns, elections, or advocacy. Only return "
        "items genuinely about a watched entity's campaign-AI-relevant activity — "
        "skip unrelated news about similar names/companies."
    )
    return {
        "model": model,
        "max_tokens": 2000,
        "system": system,
        "tools": [_search_tool(ENTITY_MAX_USES)],
        "messages": [{"role": "user", "content": user_message}],
    }


# ---------------------------------------------------------------------------
# Discovery tagging
# ---------------------------------------------------------------------------

def _tag_broad(items: list) -> list:
    for item in items:
        item["discovery"] = {"method": "search", "source_ref": "broad_web_search", "confidence": "medium"}
    return items


def _tag_sites(items: list, targets: list) -> list:
    """Attribute each item to its target by URL domain (deterministic — no
    reliance on the model labeling its own output)."""
    import urllib.parse

    by_domain = {t["domain"].removeprefix("www."): t["id"] for t in targets}
    for item in items:
        host = urllib.parse.urlsplit(item.get("url", "")).netloc.lower().removeprefix("www.")
        target_id = by_domain.get(host)
        if target_id is None:
            for domain, tid in by_domain.items():
                if host.endswith("." + domain):
                    target_id = tid
                    break
        ref = f"site:{target_id}" if target_id else "sites_consolidated"
        item["discovery"] = {"method": "search", "source_ref": ref, "confidence": "medium"}
    return items


def _tag_entities(items: list, entities: list) -> list:
    by_name = {e["name"].lower(): e["id"] for e in entities}
    for item in items:
        matched = (item.pop("matched_entity", "") or "").lower()
        entity_id = by_name.get(matched)
        ref = f"entity:{entity_id}" if entity_id else "entity_group"
        item["discovery"] = {"method": "watchlist", "source_ref": ref, "confidence": "medium"}
    return items


# ---------------------------------------------------------------------------
# Batch submission with direct-call fallback
# ---------------------------------------------------------------------------

def _build_requests(model: str, due_entities: list, due_targets: list) -> list:
    """Returns [(custom_id, params, tagger)] for every discovery call."""
    requests = [("broad", _broad_params(model), _tag_broad)]
    if due_targets:
        requests.append(
            ("sites", _sites_params(model, due_targets), lambda items: _tag_sites(items, due_targets))
        )
    if due_entities:
        # Split into evenly-sized groups (5,5,4,4,... rather than 5,5,5,...,1)
        # so no call wastes its fixed search overhead on a single entity.
        n_groups = -(-len(due_entities) // ENTITY_GROUP_SIZE)  # ceil
        base, extra = divmod(len(due_entities), n_groups)
        start = 0
        for g in range(n_groups):
            size = base + (1 if g < extra else 0)
            group = due_entities[start : start + size]
            start += size
            requests.append(
                (
                    f"entities-{g}",
                    _entity_group_params(model, group),
                    lambda items, grp=group: _tag_entities(items, grp),
                )
            )
    return requests


def _message_items_and_usage(message):
    text_parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    items = _extract_json_array("\n".join(text_parts))
    usage = getattr(message, "usage", None)
    return items, usage


def _run_batch(client, requests: list):
    """Submit all discovery requests as one message batch and poll to completion.

    Returns {custom_id: (message_or_None, error_note_or_None)}.
    Raises on batch-level failure (caller falls back to direct calls).
    """
    batch = client.messages.batches.create(
        requests=[{"custom_id": cid, "params": params} for cid, params, _ in requests]
    )
    deadline = time.time() + _BATCH_POLL_CAP_S
    while True:
        status = client.messages.batches.retrieve(batch.id)
        if status.processing_status == "ended":
            break
        if time.time() > deadline:
            raise TimeoutError(f"batch {batch.id} not ended after {_BATCH_POLL_CAP_S}s")
        time.sleep(_BATCH_POLL_INTERVAL_S)

    out = {}
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            out[result.custom_id] = (result.result.message, None)
        else:
            detail = ""
            error = getattr(result.result, "error", None)
            inner = getattr(error, "error", None)
            if inner is not None and getattr(inner, "message", None):
                detail = f" — {inner.message}"
            out[result.custom_id] = (
                None,
                f"batch result {result.custom_id}: {result.result.type}{detail}",
            )
    return out


_BLOCKED_DOMAIN_RE = re.compile(r"'([a-z0-9.-]+\.[a-z]{2,})'")


def _retry_sites_without_blocked(client, model: str, due_targets: list, err_text: str, notes: list) -> list:
    """The allowed_domains parameter rejects the whole request if ANY listed
    domain blocks Anthropic's crawler — and outlets change robots policy
    without notice. Strip the domains the error names and retry once directly,
    so one newly-blocked outlet can't zero out site coverage for the day."""
    blocked = set(_BLOCKED_DOMAIN_RE.findall(err_text))
    remaining = [t for t in due_targets if t["domain"] not in blocked]
    if not remaining or len(remaining) == len(due_targets):
        return []
    notes.append(f"sites retry without crawler-blocked domains: {sorted(blocked & {t['domain'] for t in due_targets})}")
    try:
        message = client.messages.create(**_sites_params(model, remaining))
    except Exception as exc:
        notes.append(f"sites retry failed: {exc}")
        return []
    items, usage = _message_items_and_usage(message)
    if usage:
        notes.append(f"sites(retry) usage: input={usage.input_tokens} output={usage.output_tokens}")
    return _tag_sites(items, remaining)


def run_discovery(client, model: str, due_entities: list, due_targets: list):
    """All search-based discovery for one run: broad + consolidated sites +
    grouped entities, batched (with direct-call fallback).

    Returns (candidates, notes).
    """
    requests = _build_requests(model, due_entities, due_targets)
    notes = []
    results = None

    try:
        results = _run_batch(client, requests)
        notes.append(f"discovery batch: {len(requests)} requests")
    except Exception as exc:
        notes.append(f"discovery batch failed ({exc}); falling back to direct calls")

    candidates = []
    for custom_id, params, tagger in requests:
        message, err = (None, None)
        if results is not None:
            message, err = results.get(custom_id, (None, f"{custom_id}: missing from batch results"))
        else:
            try:
                message = client.messages.create(**params)
            except Exception as exc:
                err = f"{custom_id} direct call failed: {exc}"

        if err:
            notes.append(err)
            if custom_id == "sites" and "not accessible" in err:
                candidates.extend(
                    _retry_sites_without_blocked(client, model, due_targets, err, notes)
                )
            continue
        items, usage = _message_items_and_usage(message)
        candidates.extend(tagger(items))
        if usage:
            notes.append(f"{custom_id} usage: input={usage.input_tokens} output={usage.output_tokens}")
    return candidates, notes
