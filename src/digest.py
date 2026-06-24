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

import yaml
from anthropic import Anthropic
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from curate import curate_items
from dedupe import fetch_canonicals, normalize_title, normalize_url, url_id
from gather_feeds import gather_feed_items
from gather_search import broad_search, watchlist_search
from render import write_outputs

# Curation needs editorial judgment (categorizing, paraphrasing, flagging) —
# keep it on Sonnet per the locked decision. Search calls are pure discovery
# (find candidate URLs, no judgment), so they run on Haiku — much cheaper per
# token, and the cost is dominated by ingested page content either way.
CURATE_MODEL = "claude-sonnet-4-6"
SEARCH_MODEL = "claude-haiku-4-5-20251001"
LOOKBACK_DAYS = 7
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


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

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set (put it in aicn/.env or export it).")
    client = Anthropic(api_key=api_key)

    t0 = time.time()
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

    today_weekday = datetime.datetime.now(ZoneInfo("America/Los_Angeles")).weekday()
    all_entities = watchlist.get("entities", [])
    due_entities = [
        e for e in all_entities
        if e.get("cadence", "daily") == "daily" or e.get("weekday") == today_weekday
    ]
    skipped = len(all_entities) - len(due_entities)
    print(
        f"Running watchlist search ({len(due_entities)} due today, {skipped} weekly entries skipped)...",
        file=sys.stderr,
    )
    for entity in due_entities:
        items, note = watchlist_search(client, SEARCH_MODEL, entity)
        candidates.extend(items)
        if note:
            notes.append(note)
        print(f"  {entity['id']}: {len(items)} items", file=sys.stderr)

    print(f"Total raw candidates: {len(candidates)}", file=sys.stderr)

    # Best-effort canonical-URL lookup before normalizing/hashing.
    print("Resolving canonical URLs...", file=sys.stderr)
    canonical_map = fetch_canonicals([c["url"] for c in candidates])

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
        effective_url = canonical_map.get(c["url"]) or c["url"]
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
        deduped.append(c)

    print(f"After within-run + state dedupe: {len(deduped)} candidates", file=sys.stderr)

    print("Curating (one Anthropic API call)...", file=sys.stderr)
    curated, curate_note = curate_items(client, CURATE_MODEL, deduped)
    if curate_note:
        notes.append(curate_note)
    if curated is None:
        sys.exit("Curation call did not return parseable JSON. Aborting without writing output.")

    candidates_by_url = {c["url"]: c for c in deduped}
    run_date = datetime.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    run_id = run_date.isoformat()

    new_run, digests_path, meta_path, feed_path = write_outputs(
        ROOT, run_id, run_date, candidates_by_url, curated, dry_run=args.dry_run
    )

    elapsed = time.time() - t0
    print("\n--- Run summary ---", file=sys.stderr)
    print(f"run_id: {run_id}  is_light_run: {new_run['is_light_run']}  items: {new_run['item_count']}", file=sys.stderr)
    print(f"feed errors: {feed_errors}", file=sys.stderr)
    print(f"elapsed: {elapsed:.1f}s", file=sys.stderr)
    print(f"wrote: {digests_path}, {meta_path}, {feed_path}", file=sys.stderr)
    if args.dry_run:
        print("DRY RUN: state/seen.json was NOT written.", file=sys.stderr)
    for note in notes:
        print(f"note: {note}", file=sys.stderr)


if __name__ == "__main__":
    main()
