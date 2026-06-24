"""Gather candidate items via the Anthropic API web_search tool.

Two call sites use this:
  - broad_search: one wide pass across the whole relevance space.
  - watchlist_search: one pass per entity in watchlist.yaml.

Both ask the model to return ONLY a JSON array of items backed by real search
results (never invented URLs), then we parse and tag discovery.method.
"""

import json
import re

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

# max_uses caps how many searches the model can run per call. Each search's
# page-content excerpt is the dominant cost driver (tens of thousands of input
# tokens per call), so keeping this low matters more for cost than for recall.
DEFAULT_MAX_USES = 2


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


def _run_search(client, model: str, system: str, user_message: str, max_uses: int = DEFAULT_MAX_USES):
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=system,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
        messages=[{"role": "user", "content": user_message}],
    )
    text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    full_text = "\n".join(text_parts)
    items = _extract_json_array(full_text)
    usage = getattr(resp, "usage", None)
    return items, usage


def broad_search(client, model: str):
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
    try:
        items, usage = _run_search(client, model, system, user_message)
    except Exception as exc:
        return [], f"broad_search failed: {exc}"

    for item in items:
        item["discovery"] = {"method": "search", "source_ref": "broad_web_search", "confidence": "medium"}
    note = None
    if usage:
        note = f"broad_search usage: input={usage.input_tokens} output={usage.output_tokens}"
    return items, note


def watchlist_search(client, model: str, entity: dict):
    name = entity["name"]
    system = (
        "You are a research assistant gathering candidate news items for AICN, a "
        "neutral tracker of AI use in political campaigns and elections.\n\n"
        + _RELEVANCE_RULES
        + "\n\nYou are specifically watching one entity this call. "
        + _OUTPUT_FORMAT
    )
    user_message = (
        f'Search for recent (last 7 days) news specifically about "{name}" in the '
        "context of AI and political campaigns, elections, or advocacy. Only return "
        "items genuinely about this entity's campaign-AI-relevant activity — skip "
        "unrelated news about the same name/company."
    )
    try:
        items, usage = _run_search(client, model, system, user_message)
    except Exception as exc:
        return [], f"watchlist[{entity['id']}] failed: {exc}"

    for item in items:
        item["discovery"] = {"method": "watchlist", "source_ref": f"entity:{entity['id']}", "confidence": "medium"}
    note = None
    if usage:
        note = f"watchlist[{entity['id']}] usage: input={usage.input_tokens} output={usage.output_tokens}"
    return items, note
