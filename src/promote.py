"""Phase 2: cross-run domain stats, feed autodiscovery, and proposals.

Source promotion: each run we tally which domains appear in on-topic candidates
but aren't already in sources.yaml or site_targets.yaml. When a domain crosses
the PROMOTION_THRESHOLD it gets a proposals.json entry (kind: source) for review.

Lead-following: the curation call (curate.py) is asked to also extract newly-named
vendors/people/legislation → those arrive here as new_entities and become
proposals.json entries (kind: watchlist_entity) for review.
"""

import concurrent.futures
import re
import urllib.parse
import urllib.request

from dedupe import _is_public_url, _opener

_FEED_TYPES = re.compile(r"application/(rss|atom)\+xml", re.I)
_FEED_LINK = re.compile(r"<link\s[^>]+>", re.I | re.S)
_REL_ALT = re.compile(r"""rel=["']alternate["']""", re.I)
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)

_SNIFF_TIMEOUT = 7.0
_SNIFF_UA = "AICN-feedsniffer/1.0"


# ---------------------------------------------------------------------------
# Domain stats
# ---------------------------------------------------------------------------

def update_domain_stats(stats: dict, candidates: list, known_domains: set, run_id: str) -> dict:
    """Increment per-domain counters for candidates not already in known_domains.

    stats is mutated in place and also returned.
    """
    for c in candidates:
        raw_url = c.get("_normalized_url") or c.get("url", "")
        try:
            host = urllib.parse.urlsplit(raw_url).netloc
        except Exception:
            continue
        host = host.removeprefix("www.")
        if not host or host in known_domains:
            continue
        entry = stats.setdefault(host, {"count": 0, "example_urls": [], "last_seen": ""})
        entry["count"] += 1
        entry["last_seen"] = run_id
        if raw_url and raw_url not in entry["example_urls"] and len(entry["example_urls"]) < 5:
            entry["example_urls"].append(raw_url)
    return stats


# ---------------------------------------------------------------------------
# Feed autodiscovery
# ---------------------------------------------------------------------------

def _sniff_one(domain: str) -> tuple[str, str | None]:
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        # Domains come from third-party candidate URLs — same SSRF guard as
        # page-metadata fetching (public IPs only, redirects re-validated).
        if not _is_public_url(url):
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _SNIFF_UA})
            with _opener.open(req, timeout=_SNIFF_TIMEOUT) as resp:
                if resp.status != 200:
                    continue
                html = resp.read(200_000).decode("utf-8", errors="replace")
            for m in _FEED_LINK.finditer(html):
                tag = m.group(0)
                if not _FEED_TYPES.search(tag):
                    continue
                if not _REL_ALT.search(tag):
                    continue
                href_m = _HREF.search(tag)
                if not href_m:
                    continue
                href = href_m.group(1)
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = f"{scheme}://{domain}{href}"
                return domain, href
            return domain, None  # 200 but no feed link found
        except Exception:
            continue
    return domain, None


def sniff_feed_urls(domains: list, max_workers: int = 8) -> dict:
    """Returns {domain: feed_url_or_None}."""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for domain, feed_url in pool.map(_sniff_one, domains):
            results[domain] = feed_url
    return results


# ---------------------------------------------------------------------------
# Proposal builders
# ---------------------------------------------------------------------------

def build_source_proposals(
    stats: dict,
    threshold: int,
    existing_proposals: list,
    known_domains: set,
    run_id: str,
    feed_urls: dict,
) -> list:
    """New proposal dicts for domains that crossed the threshold and aren't
    already in proposals.json (any status)."""
    existing_values = {p["value"] for p in existing_proposals}
    new_proposals = []
    for domain, entry in sorted(stats.items(), key=lambda kv: -kv[1]["count"]):
        if domain in known_domains:
            continue
        if entry["count"] < threshold:
            continue
        if domain in existing_values:
            continue
        prop_id = f"prop-source-{domain.replace('.', '-')}"
        new_proposals.append(
            {
                "id": prop_id,
                "kind": "source",
                "value": domain,
                "feed_url": feed_urls.get(domain),
                "rationale": (
                    f"Surfaced {entry['count']} on-topic candidate(s) across runs; "
                    "not in feed list or site-scoped targets."
                ),
                "example_urls": entry.get("example_urls", [])[:3],
                "first_proposed": run_id,
                "status": "pending",
            }
        )
    return new_proposals


def build_entity_proposals(
    new_entities: list,
    existing_proposals: list,
    known_entity_names: set,
    run_id: str,
) -> list:
    """Convert curator-extracted entities into proposals, skipping ones already
    in proposals.json or watchlist.yaml."""
    existing_lc = {p["value"].lower() for p in existing_proposals}
    known_lc = {n.lower() for n in known_entity_names}
    new_proposals = []
    seen_this_run: set[str] = set()
    for ent in new_entities or []:
        name = (ent.get("name") or "").strip()
        if not name or name.lower() in existing_lc or name.lower() in known_lc:
            continue
        if name.lower() in seen_this_run:
            continue
        seen_this_run.add(name.lower())
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower())[:40].strip("-")
        prop_id = f"prop-entity-{slug}"
        new_proposals.append(
            {
                "id": prop_id,
                "kind": "watchlist_entity",
                "value": name,
                "feed_url": None,
                "rationale": ent.get("rationale", "Named in a published item this run."),
                "example_urls": ([ent["example_url"]] if ent.get("example_url") else []),
                "first_proposed": run_id,
                "status": "pending",
            }
        )
    return new_proposals
