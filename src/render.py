"""Build the run object and write data/digests.json, data/archive.json,
data/meta.json, feed.xml."""

import datetime
import json
import os
import urllib.parse
import xml.sax.saxutils as saxutils

SCHEMA_VERSION = 1
# digests.json holds the most recent runs; anything older moves to
# data/archive.json instead of being dropped. Dropping used to be permanent:
# every candidate is in seen.json, so no later run would gather it again.
MAX_RUNS_KEPT = 40
FEED_ITEM_CAP = 30
SITE_URL = "https://russfagaly.github.io/aicn/"


def build_run(run_id: str, run_date, candidates_by_url: dict, curated: dict):
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    is_light_run = bool(curated.get("is_light_run", False))
    top_summary = curated.get("top_summary", "") or ""

    items = []
    for curated_item in curated.get("items", []):
        url = curated_item.get("url")
        cand = candidates_by_url.get(url)
        if cand is None:
            continue
        source_domain = cand.get("source_domain") or urllib.parse.urlsplit(cand["_normalized_url"]).netloc
        items.append(
            {
                "id": cand["_id"],
                "title": cand["title"],
                "url": cand["_normalized_url"],
                "source": cand["source"],
                "source_domain": source_domain,
                "published": cand.get("published", run_date.isoformat()),
                "first_seen_run": run_id,
                "category": curated_item.get("category", "analysis_oped"),
                "summary": curated_item.get("summary", ""),
                "why_it_matters": curated_item.get("why_it_matters", ""),
                "flags": curated_item.get("flags", []),
                "discovery": cand.get("discovery"),
            }
        )

    if not items:
        is_light_run = True

    return {
        "run_id": run_id,
        "date": run_date.isoformat(),
        "generated_at": now_utc,
        "is_light_run": is_light_run,
        "top_summary": top_summary,
        "item_count": len(items),
        "items": items,
    }


def _load_existing_digests(path: str):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"schema_version": SCHEMA_VERSION, "generated_at": "", "runs": []}


def archive_overflow(root: str, digests: dict, dry_run: bool = False) -> int:
    """Trim digests["runs"] to MAX_RUNS_KEPT, moving the overflow to data/archive.json.

    Returns how many runs were moved. An archived run_id replaces any older copy
    of itself, so re-archiving is idempotent.
    """
    overflow = digests["runs"][MAX_RUNS_KEPT:]
    digests["runs"] = digests["runs"][:MAX_RUNS_KEPT]
    if not overflow or dry_run:
        return len(overflow)
    path = os.path.join(root, "data", "archive.json")
    archive = {"schema_version": SCHEMA_VERSION, "runs": []}
    if os.path.exists(path):
        with open(path) as f:
            archive = json.load(f)
    moved = {r["run_id"] for r in overflow}
    runs = overflow + [r for r in archive.get("runs", []) if r["run_id"] not in moved]
    archive["runs"] = sorted(runs, key=lambda r: r["run_id"], reverse=True)
    with open(path, "w") as f:
        json.dump(archive, f, indent=2)
    return len(overflow)


def archive_totals(root: str) -> tuple:
    """(runs, items) currently in data/archive.json, for meta.json's all-time totals."""
    path = os.path.join(root, "data", "archive.json")
    if not os.path.exists(path):
        return 0, 0
    with open(path) as f:
        runs = json.load(f).get("runs", [])
    return len(runs), sum(r.get("item_count", 0) for r in runs)


def _rss_escape(text: str) -> str:
    return saxutils.escape(text or "")


def _rfc822_date(iso_date: str) -> str:
    """RSS 2.0 requires RFC-822 pubDates; items carry ISO YYYY-MM-DD."""
    try:
        d = datetime.date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return iso_date or ""
    return d.strftime("%a, %d %b %Y 00:00:00 GMT")


def _render_feed_xml(runs: list) -> str:
    items_xml = []
    count = 0
    for run in runs:
        for item in run["items"]:
            if count >= FEED_ITEM_CAP:
                break
            items_xml.append(
                "    <item>\n"
                f"      <title>{_rss_escape(item['title'])}</title>\n"
                f"      <link>{_rss_escape(item['url'])}</link>\n"
                f"      <guid isPermaLink=\"false\">{_rss_escape(item['id'])}</guid>\n"
                f"      <pubDate>{_rss_escape(_rfc822_date(item['published']))}</pubDate>\n"
                f"      <description>{_rss_escape(item['summary'])}</description>\n"
                "    </item>"
            )
            count += 1
        if count >= FEED_ITEM_CAP:
            break

    now_rfc822 = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>AI Campaign News (AICN)</title>\n"
        f"    <link>{SITE_URL}</link>\n"
        f'    <atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>\n'
        "    <description>A tracker of AI use in political campaigns, elections, and advocacy.</description>\n"
        "    <lastBuildDate>" + now_rfc822 + "</lastBuildDate>\n"
        + "\n".join(items_xml)
        + "\n  </channel>\n</rss>\n"
    )


def write_proposals(root: str, new_proposals: list, dry_run: bool):
    """Merge new_proposals into data/proposals.json, skipping any id already present."""
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)

    if dry_run:
        proposals_path = os.path.join(data_dir, "dryrun_proposals.json")
        real_proposals_path = os.path.join(data_dir, "proposals.json")
    else:
        proposals_path = os.path.join(data_dir, "proposals.json")
        real_proposals_path = proposals_path

    existing = {"schema_version": 1, "proposals": []}
    if os.path.exists(real_proposals_path):
        with open(real_proposals_path) as f:
            existing = json.load(f)

    existing_ids = {p["id"] for p in existing.get("proposals", [])}
    added = 0
    for prop in new_proposals:
        if prop["id"] not in existing_ids:
            existing["proposals"].append(prop)
            existing_ids.add(prop["id"])
            added += 1

    # ensure_ascii=False to match review.py, the other writer of this file.
    # Curator rationales are full of em-dashes, so a mismatch makes the whole
    # file churn between escaped and literal forms every time the pipeline and
    # a review pass alternate — a one-field edit shows up as a 50-line diff.
    with open(proposals_path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return added


def merge_same_day_runs(earlier: dict, later: dict) -> dict:
    """Combine two runs that share a run_id into one entry.

    Later items come first (newest first, like the rest of the digest), then
    earlier items not already present. Both top summaries are kept, earlier
    first, so the day reads in order. A merged run is light only if it ends up
    with no items at all.
    """
    merged = dict(later)
    ids = {it["id"] for it in later.get("items", [])}
    items = list(later.get("items", [])) + [it for it in earlier.get("items", []) if it["id"] not in ids]
    merged["items"] = items
    merged["item_count"] = len(items)
    merged["is_light_run"] = not items
    summaries = [s for s in (earlier.get("top_summary"), later.get("top_summary")) if s]
    merged["top_summary"] = " ".join(summaries)
    return merged


def write_outputs(root: str, run_id: str, run_date, candidates_by_url: dict, curated: dict, dry_run: bool):
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)

    real_digests_path = os.path.join(data_dir, "digests.json")
    # Dry runs read the real digests.json (so they dedupe/preview against what's
    # actually live) but write to separate dryrun_* files — otherwise a dry run
    # on a day that already has a real published run would silently overwrite
    # it, since both share the same run_id.
    if dry_run:
        digests_path = os.path.join(data_dir, "dryrun_digests.json")
        meta_path = os.path.join(data_dir, "dryrun_meta.json")
        feed_path = os.path.join(root, "dryrun_feed.xml")
    else:
        digests_path = real_digests_path
        meta_path = os.path.join(data_dir, "meta.json")
        feed_path = os.path.join(root, "feed.xml")

    new_run = build_run(run_id, run_date, candidates_by_url, curated)

    digests = _load_existing_digests(real_digests_path)
    # A second run on the same day merges into that day's entry rather than
    # replacing it. Replacing used to delete the earlier run's items for good:
    # they were already in seen.json, so no later run would gather them again.
    # That happened on 2026-10-12, when a manual run's 5 items were erased by
    # the scheduled run that afternoon.
    earlier = next((r for r in digests.get("runs", []) if r["run_id"] == run_id), None)
    if earlier is not None:
        new_run = merge_same_day_runs(earlier, new_run)
    digests["runs"] = [r for r in digests.get("runs", []) if r["run_id"] != run_id]
    digests["runs"].insert(0, new_run)
    archive_overflow(root, digests, dry_run=dry_run)
    digests["schema_version"] = SCHEMA_VERSION
    digests["generated_at"] = new_run["generated_at"]

    archived_runs, archived_items = archive_totals(root)
    meta = {
        "schema_version": SCHEMA_VERSION,
        "last_updated": new_run["generated_at"],
        "latest_run_id": run_id,
        "total_runs": len(digests["runs"]) + archived_runs,
        "total_items": sum(r["item_count"] for r in digests["runs"]) + archived_items,
    }

    feed_xml = _render_feed_xml(digests["runs"])

    with open(digests_path, "w") as f:
        json.dump(digests, f, indent=2)
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    with open(feed_path, "w") as f:
        f.write(feed_xml)

    if not dry_run:
        seen_path = os.path.join(root, "state", "seen.json")
        seen = {"ids": [], "titles": []}
        if os.path.exists(seen_path):
            with open(seen_path) as f:
                seen = json.load(f)
        seen_ids = set(seen.get("ids", []))
        seen_titles = set(seen.get("titles", []))
        # Every candidate that reached the curator is marked seen — published
        # or rejected. Each item gets exactly one judgment; without this,
        # rejected items resurface from feeds/search for up to 7 days, get
        # re-fetched and re-judged daily, and can flip to accepted late and
        # publish as stale news.
        for cand in candidates_by_url.values():
            seen_ids.add(cand["_id"])
            seen_titles.add(cand["_normalized_title"])
        with open(seen_path, "w") as f:
            json.dump({"ids": sorted(seen_ids), "titles": sorted(seen_titles)}, f, indent=2)

    return new_run, digests_path, meta_path, feed_path
