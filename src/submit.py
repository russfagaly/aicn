"""Publish editor-chosen articles into today's digest entry.

Usage (from the repo root; quote each URL so the shell leaves ? and & alone):
    .venv/bin/python src/submit.py "https://..." "https://..."            # publish
    .venv/bin/python src/submit.py --dry-run "https://..." "https://..."  # draft only

The pipeline only publishes what it finds on its own, and an article the editor
already knows belongs had no way in. This is that way in. It deliberately skips
the curator's relevance filter and the age floor — the editor has already made
that call — but still has the curator model write the category, summary and
why-it-matters, so a hand-added entry reads like every other one.

Each URL is resolved to its canonical address (which drops email tracking
parameters and turns Substack inbox links into the real post), merged into
today's run with the same merge the pipeline uses for a same-day rerun, and
marked seen so the pipeline never publishes it a second time. Discovery is
recorded as method "manual" so hand-added items stay distinguishable.
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anthropic import Anthropic

import render
from curate import _OUTPUT_SCHEMA
from dedupe import _is_public_url, _opener, normalize_title, normalize_url, url_id

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# This is a local tool, so read the API key from the project's .env when it
# isn't already in the environment (the pipeline gets it from GitHub secrets).
_env = os.path.join(ROOT, ".env")
if not os.environ.get("ANTHROPIC_API_KEY") and os.path.exists(_env):
    for _line in open(_env):
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.strip().split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

CURATE_MODEL = "claude-sonnet-4-6"  # same model as curation, so entries read alike
_UA = "Mozilla/5.0 (compatible; AICN-bot/1.0; +https://russfagaly.github.io/aicn/)"

_SYSTEM = """You write entries for AICN (AI Campaign News), a neutral, non-partisan
digest of how political campaigns and the people who build for them use AI.

The editor has already chosen every article you are given. Do not filter or
judge relevance — write exactly one entry per article.

For each, in your own words:
- category: exactly one of vendor_moves, deepfakes, polling_synthetic,
  regulation, deployments_studies, analysis_oped
- summary: 1-2 sentence neutral paraphrase, no copied text beyond a short
  attributed phrase. Be concrete — name the actual people, organizations,
  products or races the text gives you. Don't editorialize or frame it as a
  question or cliffhanger; state what it says.
- why_it_matters: one line on significance to campaign practitioners — never
  "for us" or for a party.
- flags: may be empty. "vendor_self_reported" for vendor-claimed metrics stated
  as fact, "contested" for disputed claims, "speculative" for speculation
  framed as likely fact, "paywalled" if only a preview was readable.

Never invent facts beyond the text given. If only a short preview is
available, keep the summary to what the preview supports.

Each "url" you return MUST exactly match one of the urls given."""


def _meta(raw: str, pattern: str):
    m = re.search(pattern, raw, re.I | re.S)
    return html.unescape(m.group(1)).strip() if m else None


def fetch_article(url: str) -> dict:
    if not _is_public_url(url):
        raise ValueError(f"refusing non-public URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with _opener.open(req, timeout=20) as resp:
        final = resp.geturl()
        raw = resp.read(600_000).decode("utf-8", errors="replace")
    canonical = _meta(raw, r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)') or final
    # Canonical pages are clean; fall back to stripping the query outright.
    canonical = urllib.parse.urlunsplit(urllib.parse.urlsplit(canonical)._replace(query="", fragment=""))
    title = (_meta(raw, r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)')
             or _meta(raw, r"<title>(.*?)</title>") or canonical)
    desc = _meta(raw, r'<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']+)')
    site = _meta(raw, r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)')
    date = (_meta(raw, r'"datePublished"\s*:\s*"([^"]+)"')
            or _meta(raw, r'article:published_time["\'][^>]+content=["\']([^"\']+)'))
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    body = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
    host = urllib.parse.urlsplit(canonical).netloc.removeprefix("www.")
    return {
        "url": canonical,
        "title": title,
        "description": desc,
        "source": site or host,
        "source_domain": host,
        "published": (date or "")[:10],
        "text": " ".join(body.split()[:1500]),
    }


def write_entries(client, articles: list) -> dict:
    schema = {
        "type": "object",
        "properties": {"items": _OUTPUT_SCHEMA["properties"]["items"]},
        "required": ["items"],
        "additionalProperties": False,
    }
    payload = [{k: a[k] for k in ("url", "title", "description", "source", "published", "text")} for a in articles]
    resp = client.messages.create(
        model=CURATE_MODEL,
        max_tokens=4000,
        system=_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": "Articles (JSON):\n" + json.dumps(payload, indent=1)}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return {it["url"]: it for it in json.loads(text)["items"]}


def main():
    ap = argparse.ArgumentParser(description="Publish editor-chosen articles into today's AICN entry.")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--dry-run", action="store_true", help="Draft the entries without writing anything.")
    args = ap.parse_args()

    run_date = datetime.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    run_id = run_date.isoformat()

    articles = []
    for u in args.urls:
        a = fetch_article(u)
        print(f"resolved: {a['url']}\n   title: {a['title']}\n   published: {a['published'] or '(unknown)'}", file=sys.stderr)
        articles.append(a)

    entries = write_entries(Anthropic(timeout=120.0), articles)

    seen_path = os.path.join(ROOT, "state", "seen.json")
    with open(seen_path) as f:
        seen = json.load(f)
    seen_ids, seen_titles = set(seen.get("ids", [])), set(seen.get("titles", []))

    items = []
    for a in articles:
        e = entries.get(a["url"])
        if not e:
            sys.exit(f"no entry was written for {a['url']}; nothing published")
        norm_url = normalize_url(a["url"])
        cid = url_id(norm_url)
        if cid in seen_ids:
            print(f"note: {a['url']} was already seen by the pipeline — adding it anyway", file=sys.stderr)
        items.append({
            "id": cid,
            "title": a["title"],
            "url": norm_url,
            "source": a["source"],
            "source_domain": a["source_domain"],
            "published": a["published"] or run_id,
            "first_seen_run": run_id,
            "category": e["category"],
            "summary": e["summary"],
            "why_it_matters": e["why_it_matters"],
            "flags": e["flags"],
            "discovery": {"method": "manual", "source_ref": "editor", "confidence": "high"},
        })
        seen_ids.add(cid)
        seen_titles.add(normalize_title(a["title"]))

    for it in items:
        print(f"\n[{it['category']}] {it['title']}\n  {it['url']}\n  published {it['published']}"
              f"\n  summary: {it['summary']}\n  why: {it['why_it_matters']}\n  flags: {it['flags']}")

    if args.dry_run:
        print("\nDRY RUN: nothing written.", file=sys.stderr)
        return

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manual_run = {
        "run_id": run_id, "date": run_id, "generated_at": now,
        "is_light_run": False, "top_summary": "", "item_count": len(items), "items": items,
    }
    digests_path = os.path.join(ROOT, "data", "digests.json")
    digests = render._load_existing_digests(digests_path)
    existing = next((r for r in digests["runs"] if r["run_id"] == run_id), None)
    # Hand-added items go after the pipeline's own items for the day, and the
    # pipeline's summary stays as the day's summary.
    run = render.merge_same_day_runs(manual_run, existing) if existing else manual_run
    digests["runs"] = [r for r in digests["runs"] if r["run_id"] != run_id]
    digests["runs"].insert(0, run)
    digests["runs"] = digests["runs"][: render.MAX_RUNS_KEPT]
    with open(digests_path, "w") as f:
        json.dump(digests, f, indent=2)

    meta_path = os.path.join(ROOT, "data", "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    meta["total_runs"] = len(digests["runs"])
    meta["total_items"] = sum(r["item_count"] for r in digests["runs"])
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    with open(os.path.join(ROOT, "feed.xml"), "w") as f:
        f.write(render._render_feed_xml(digests["runs"]))
    with open(seen_path, "w") as f:
        json.dump({"ids": sorted(seen_ids), "titles": sorted(seen_titles)}, f, indent=2)

    print(f"\nPublished {len(items)} item(s) into {run_id}. Commit and push to make it live.", file=sys.stderr)


if __name__ == "__main__":
    main()
