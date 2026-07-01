"""AICN pipeline entry point.

Each run:
  1. Gathers candidates from curated RSS feeds, a broad web_search pass, and an
     entity watchlist (each entity searched individually).
  2. Dedupes (within-run + against state/seen.json), then makes ONE Anthropic
     API call to filter to on-topic items, categorize, and write
     summary/why_it_matters/flags.
  3. Writes data/digests.json, data/meta.json, feed.xml. In normal (non-dry-run)
     mode it also advances state/seen.json, in the same "commit" as the rest of
     the outputs (the GitHub Actions workflow does the actual git commit).

Use --dry-run to produce real output without touching state/seen.json (and
without anything being committed/pushed — there's no git wiring invoked here
either way; that's handled by the inert workflow).
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.parse

import yaml
from anthropic import Anthropic
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_library import build_library_html
from curate import curate_items
from dedupe import fetch_page_metas, normalize_title, normalize_url, url_id
from gather_feeds import gather_feed_items
from gather_search import broad_search, site_scoped_search, watchlist_search
from promote import (
    build_entity_proposals,
    build_source_proposals,
    sniff_feed_urls,
    update_domain_stats,
)
from render import write_outputs, write_proposals

# Curation needs editorial judgment (categorizing, paraphrasing, flagging) —
# keep it on Sonnet per the locked decision. Search calls are pure discovery
# (find candidate URLs, no judgment), so they run on Haiku — much cheaper per
# token, and the cost is dominated by ingested page content either way.
CURATE_MODEL = "claude-sonnet-4-6"
SEARCH_MODEL = "claude-haiku-4-5-20251001"
LOOKBACK_DAYS = 7
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# How many times a domain must surface in candidates before it's proposed as a
# new source. Set low (3) while run history is short; revisit after a month.
PROMOTION_THRESHOLD = 3


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_recent_published(root: str, lookback_days: int):
    """Title+summary of everything published in the last N days, across runs.

    Used as continued-coverage context for the curator: mechanical dedup
    (URL/title matching) can't tell that a new article is just a different
    outlet rehashing a story we already ran — this gives the model enough to
    make that call itself.
    """
    digests_path = os.path.join(root, "data", "digests.json")
    if not os.path.exists(digests_path):
        return []
    with open(digests_path) as f:
        digests = json.load(f)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=lookback_days)
    recent = []
    for run in digests.get("runs", []):
        try:
            run_date = datetime.datetime.fromisoformat(run["date"]).replace(tzinfo=datetime.timezone.utc)
        except (KeyError, ValueError):
            continue
        if run_date < cutoff:
            continue
        for item in run.get("items", []):
            recent.append(
                {
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "published": item.get("published", ""),
                }
            )
    return recent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Produce real output without writing state/seen.json.",
    )
    args = parser.parse_args()

    sources = load_yaml(os.path.join(ROOT, "sources.yaml"))
    watchlist = load_yaml(os.path.join(ROOT, "watchlist.yaml"))
    site_targets = load_yaml(os.path.join(ROOT, "site_targets.yaml"))

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set (put it in aicn/.env or export it).")
    # The SDK's default read timeout is 600s — a single stalled web_search call
    # (server-side, out of our control) can then block the entire run for up
    # to 10 minutes. 120s is generous for a search or curation call under
    # normal conditions; individual call sites catch the resulting timeout
    # and degrade (empty results / skip) rather than taking the whole run down.
    client = Anthropic(api_key=api_key, timeout=120.0)

    t0 = time.time()
    run_date = datetime.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    run_id = run_date.isoformat()
    candidates = []
    feed_errors = []
    notes = []

    print("Gathering RSS/Atom feeds...", file=sys.stderr)
    for feed in sources.get("feeds", []):
        items, err = gather_feed_items(feed["id"], feed["name"], feed["url"], LOOKBACK_DAYS)
        candidates.extend(items)
        if err:
            feed_errors.append(err)
        print(f"  {feed['id']}: {len(items)} items" + (f" ({err})" if err else ""), file=sys.stderr)

    print("Running broad web_search pass...", file=sys.stderr)
    broad_items, broad_note = broad_search(client, SEARCH_MODEL)
    candidates.extend(broad_items)
    if broad_note:
        notes.append(broad_note)
    print(f"  broad search: {len(broad_items)} items", file=sys.stderr)

    def due_today(entries):
        due = [e for e in entries if e.get("cadence", "daily") == "daily" or e.get("weekday") == run_date.weekday()]
        return due, len(entries) - len(due)

    due_entities, skipped_entities = due_today(watchlist.get("entities", []))
    print(
        f"Running watchlist search ({len(due_entities)} due today, {skipped_entities} weekly entries skipped)...",
        file=sys.stderr,
    )
    for entity in due_entities:
        items, note = watchlist_search(client, SEARCH_MODEL, entity)
        candidates.extend(items)
        if note:
            notes.append(note)
        print(f"  {entity['id']}: {len(items)} items", file=sys.stderr)

    due_targets, skipped_targets = due_today(site_targets.get("targets", []))
    print(
        f"Running site-scoped search ({len(due_targets)} due today, {skipped_targets} weekly entries skipped)...",
        file=sys.stderr,
    )
    for target in due_targets:
        items, note = site_scoped_search(client, SEARCH_MODEL, target)
        candidates.extend(items)
        if note:
            notes.append(note)
        print(f"  {target['id']}: {len(items)} items", file=sys.stderr)

    print(f"Total raw candidates: {len(candidates)}", file=sys.stderr)

    # Best-effort canonical-URL + real page title/description lookup before
    # normalizing/hashing. The page title/description ground the curator in
    # what the article actually says, instead of just the bare title a feed
    # or search result handed us — that's what lets it name specific people/
    # orgs instead of writing around them vaguely.
    print("Resolving canonical URLs + page metadata...", file=sys.stderr)
    page_meta_map = fetch_page_metas([c["url"] for c in candidates])

    seen_path = os.path.join(ROOT, "state", "seen.json")
    seen = {"ids": [], "titles": []}
    if os.path.exists(seen_path):
        with open(seen_path) as f:
            seen = json.load(f)
    seen_ids = set(seen.get("ids", []))
    seen_titles = set(seen.get("titles", []))

    deduped = []
    run_ids_used = set()
    run_titles_used = set()
    for c in candidates:
        page_meta = page_meta_map.get(c["url"], {})
        effective_url = page_meta.get("canonical") or c["url"]
        norm_url = normalize_url(effective_url)
        cid = url_id(norm_url)
        norm_title = normalize_title(c["title"])

        if cid in run_ids_used or norm_title in run_titles_used:
            continue
        if cid in seen_ids or norm_title in seen_titles:
            continue

        run_ids_used.add(cid)
        run_titles_used.add(norm_title)
        c["_id"] = cid
        c["_normalized_url"] = norm_url
        c["_normalized_title"] = norm_title
        c["page_title"] = page_meta.get("page_title")
        c["page_description"] = page_meta.get("page_description")
        deduped.append(c)

    print(f"After within-run + state dedupe: {len(deduped)} candidates", file=sys.stderr)

    # Phase 2: track which domains keep surfacing so we can propose new sources.
    # Known domains = everything already in sources.yaml feeds + site_targets.yaml.
    known_domains: set[str] = set()
    for feed in sources.get("feeds", []):
        host = urllib.parse.urlsplit(feed.get("url", "")).netloc.lstrip("www.")
        if host:
            known_domains.add(host)
    for tgt in site_targets.get("targets", []):
        domain = tgt.get("domain", "").lstrip("www.")
        if domain:
            known_domains.add(domain)

    domain_stats_path = os.path.join(ROOT, "state", "domain_stats.json")
    domain_stats: dict = {}
    if os.path.exists(domain_stats_path):
        with open(domain_stats_path) as f:
            domain_stats = json.load(f)
    update_domain_stats(domain_stats, deduped, known_domains, run_id=run_id)

    recent_published = load_recent_published(ROOT, lookback_days=LOOKBACK_DAYS)
    print(f"Recently published (last {LOOKBACK_DAYS}d, for continued-coverage check): {len(recent_published)} items", file=sys.stderr)

    print("Curating (one Anthropic API call)...", file=sys.stderr)
    curated, curate_note = curate_items(client, CURATE_MODEL, deduped, recent_published)
    if curate_note:
        notes.append(curate_note)
    if curated is None:
        sys.exit("Curation call did not return parseable JSON. Aborting without writing output.")

    # Phase 2: build proposals from domain stats + curator-extracted entities.
    proposals_path_real = os.path.join(ROOT, "data", "proposals.json")
    existing_proposals: list = []
    if os.path.exists(proposals_path_real):
        with open(proposals_path_real) as f:
            existing_proposals = json.load(f).get("proposals", [])

    # Source promotion: domains crossing the threshold get a feed-sniff + proposal.
    promoting = [
        d for d, e in domain_stats.items()
        if e["count"] >= PROMOTION_THRESHOLD
        and d not in known_domains
        and d not in {p["value"] for p in existing_proposals}
    ]
    feed_urls: dict = {}
    if promoting:
        print(f"Sniffing feed URLs for {len(promoting)} promotion candidate(s)...", file=sys.stderr)
        feed_urls = sniff_feed_urls(promoting)

    source_proposals = build_source_proposals(
        domain_stats, PROMOTION_THRESHOLD, existing_proposals, known_domains,
        run_id=run_id,
        feed_urls=feed_urls,
    )

    # Lead-following: entities extracted by the curator.
    new_entities = curated.pop("new_entities", []) if curated else []
    known_entity_names = {e["name"] for e in watchlist.get("entities", [])}
    entity_proposals = build_entity_proposals(
        new_entities, existing_proposals, known_entity_names,
        run_id=run_id,
    )

    all_new_proposals = source_proposals + entity_proposals
    proposals_written = write_proposals(ROOT, all_new_proposals, dry_run=args.dry_run)

    # Persist domain stats (skip on dry run so we don't advance state).
    if not args.dry_run:
        with open(domain_stats_path, "w") as f:
            json.dump(domain_stats, f, indent=2, sort_keys=True)

    candidates_by_url = {c["url"]: c for c in deduped}

    new_run, digests_path, meta_path, feed_path = write_outputs(
        ROOT, run_id, run_date, candidates_by_url, curated, dry_run=args.dry_run
    )

    elapsed = time.time() - t0
    print("\n--- Run summary ---", file=sys.stderr)
    print(f"run_id: {run_id}  is_light_run: {new_run['is_light_run']}  items: {new_run['item_count']}", file=sys.stderr)
    print(f"feed errors: {feed_errors}", file=sys.stderr)
    print(f"elapsed: {elapsed:.1f}s", file=sys.stderr)
    print(f"wrote: {digests_path}, {meta_path}, {feed_path}", file=sys.stderr)
    lib_path = build_library_html(ROOT)
    if lib_path:
        print(f"  library.html rebuilt ({len(open(lib_path).read()):,} bytes)", file=sys.stderr)

    if args.dry_run:
        print("DRY RUN: state/seen.json and domain_stats.json were NOT written.", file=sys.stderr)
    if all_new_proposals:
        print(f"proposals: +{proposals_written} new ({len(source_proposals)} source, {len(entity_proposals)} entity)", file=sys.stderr)
    for note in notes:
        print(f"note: {note}", file=sys.stderr)


if __name__ == "__main__":
    main()
