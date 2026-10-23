"""Remove published items from the digest.

Usage (from the repo root; quote each URL):
    .venv/bin/python src/takedown.py "https://..." "https://..."            # remove
    .venv/bin/python src/takedown.py --dry-run "https://..."               # show what would change

Finds each item by URL in data/digests.json or data/archive.json and removes it.
Items stay in state/seen.json, so the pipeline never gathers and republishes
them. A day that loses items gets a fresh top summary written from what remains,
because the old one usually described the removed story; a day left with no
items gets an empty summary and is marked light. meta.json totals and feed.xml
are rebuilt the same way the pipeline does.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
from dedupe import normalize_url, url_id

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATE_MODEL = "claude-sonnet-4-6"

_env = os.path.join(ROOT, ".env")
if not os.environ.get("ANTHROPIC_API_KEY") and os.path.exists(_env):
    for _line in open(_env):
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.strip().split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

_SUMMARY_SYSTEM = """You write the top summary for one day of AICN (AI Campaign News),
a neutral, non-partisan digest of how political campaigns use AI.

Given that day's items, write 2-3 plain, neutral sentences on the most important
development(s) across them. Name the specific people, organizations and products
involved. Describe only the items given — never mention items that were left
out, how many candidates were reviewed, or anything else about how the digest
was put together. Return only the summary text."""


def remove_items(runs: list, target_ids: set) -> dict:
    """Remove items whose id is in target_ids. Mutates runs; returns {run_id: [removed titles]}."""
    touched = {}
    for run in runs:
        keep = [it for it in run.get("items", []) if it["id"] not in target_ids]
        removed = [it["title"] for it in run.get("items", []) if it["id"] in target_ids]
        if removed:
            run["items"] = keep
            run["item_count"] = len(keep)
            run["is_light_run"] = not keep
            if not keep:
                run["top_summary"] = ""
            touched[run["run_id"]] = removed
    return touched


def rewrite_summary(client, run: dict) -> str:
    items = [{"title": it["title"], "summary": it["summary"]} for it in run["items"]]
    resp = client.messages.create(
        model=CURATE_MODEL,
        max_tokens=600,
        system=_SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(items, indent=1)}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def main():
    ap = argparse.ArgumentParser(description="Remove published items from AICN.")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    target_ids = {url_id(normalize_url(u)) for u in args.urls}
    digests_path = os.path.join(ROOT, "data", "digests.json")
    archive_path = os.path.join(ROOT, "data", "archive.json")
    digests = render._load_existing_digests(digests_path)
    archive = render._load_existing_digests(archive_path) if os.path.exists(archive_path) else {"runs": []}

    touched = remove_items(digests["runs"], target_ids)
    touched_archive = remove_items(archive["runs"], target_ids)
    found = sum(len(v) for v in touched.values()) + sum(len(v) for v in touched_archive.values())
    if found < len(target_ids):
        print(f"warning: matched {found} of {len(target_ids)} URL(s); the rest were not found", file=sys.stderr)
    if not found:
        sys.exit("nothing to remove")

    client = None
    for runs, label in ((digests["runs"], "digest"), (archive["runs"], "archive")):
        for run in runs:
            removed = (touched if label == "digest" else touched_archive).get(run["run_id"])
            if not removed:
                continue
            print(f"\n{run['run_id']} ({label}): removed {len(removed)}, {run['item_count']} left")
            for t in removed:
                print(f"  - {t}")
            if run["items"] and not args.dry_run:
                if client is None:
                    from anthropic import Anthropic
                    client = Anthropic(timeout=120.0)
                run["top_summary"] = rewrite_summary(client, run)
                print(f"  new summary: {run['top_summary']}")

    if args.dry_run:
        print("\nDRY RUN: nothing written.", file=sys.stderr)
        return

    with open(digests_path, "w") as f:
        json.dump(digests, f, indent=2)
    if touched_archive:
        with open(archive_path, "w") as f:
            json.dump(archive, f, indent=2)
    meta_path = os.path.join(ROOT, "data", "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    archived_runs, archived_items = render.archive_totals(ROOT)
    meta["total_runs"] = len(digests["runs"]) + archived_runs
    meta["total_items"] = sum(r["item_count"] for r in digests["runs"]) + archived_items
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    with open(os.path.join(ROOT, "feed.xml"), "w") as f:
        f.write(render._render_feed_xml(digests["runs"]))
    print(f"\nRemoved {found} item(s). Commit and push to make it live.", file=sys.stderr)


if __name__ == "__main__":
    main()
