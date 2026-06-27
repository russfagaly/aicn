"""Build the run object and write data/digests.json, data/meta.json, feed.xml."""

import datetime
import json
import os
import urllib.parse
import xml.sax.saxutils as saxutils

SCHEMA_VERSION = 1
MAX_RUNS_KEPT = 40
FEED_ITEM_CAP = 30


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


def _rss_escape(text: str) -> str:
    return saxutils.escape(text or "")


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
                f"      <pubDate>{item['published']}</pubDate>\n"
                f"      <description>{_rss_escape(item['summary'])}</description>\n"
                "    </item>"
            )
            count += 1
        if count >= FEED_ITEM_CAP:
            break

    now_rfc822 = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        "    <title>AI Campaign News (AICN)</title>\n"
        "    <description>A tracker of AI use in political campaigns, elections, and advocacy.</description>\n"
        "    <lastBuildDate>" + now_rfc822 + "</lastBuildDate>\n"
        + "\n".join(items_xml)
        + "\n  </channel>\n</rss>\n"
    )


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
    # Replace a same-run_id entry if re-run same day; else prepend newest-first.
    digests["runs"] = [r for r in digests.get("runs", []) if r["run_id"] != run_id]
    digests["runs"].insert(0, new_run)
    digests["runs"] = digests["runs"][:MAX_RUNS_KEPT]
    digests["schema_version"] = SCHEMA_VERSION
    digests["generated_at"] = new_run["generated_at"]

    total_items = sum(r["item_count"] for r in digests["runs"])
    meta = {
        "schema_version": SCHEMA_VERSION,
        "last_updated": new_run["generated_at"],
        "latest_run_id": run_id,
        "total_runs": len(digests["runs"]),
        "total_items": total_items,
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
        for item in new_run["items"]:
            seen_ids.add(item["id"])
        for cand in candidates_by_url.values():
            if cand["_id"] in seen_ids:
                seen_titles.add(cand["_normalized_title"])
        with open(seen_path, "w") as f:
            json.dump({"ids": sorted(seen_ids), "titles": sorted(seen_titles)}, f, indent=2)

    return new_run, digests_path, meta_path, feed_path
