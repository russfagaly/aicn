"""Supplemental free discovery via the GDELT DOC 2.0 API.

GDELT (gdeltproject.org) is a free, open news index with direct article URLs —
no API key, no token cost. It's used here only as a supplemental wide net on
top of the paid broad web_search pass: coverage of niche/paywalled political
outlets is spotty (e.g. it has no Politico), so it can't replace paid search,
but extra recall at $0 is free money. The curator filters whatever noise it
brings in, same as any other discovery channel.

Etiquette: GDELT hard-limits to ~1 request per 5 seconds per IP and returns a
plain-text scolding instead of JSON when you exceed it — hence the sleep
between queries and the tolerant parsing.
"""

import datetime
import json
import time
import urllib.parse
import urllib.request

_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_TIMEOUT_S = 20.0
_SPACING_S = 10.0
_MAX_RECORDS = 25

# Each query is one free request; keep the list short and broad. sourcelang/
# sourcecountry keep results anglophone-US, matching the site's beat.
_QUERIES = [
    '"artificial intelligence" political campaign sourcelang:english sourcecountry:US',
    'deepfake election sourcelang:english sourcecountry:US',
]


def _fetch_query(query: str) -> list:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "timespan": "2d",
            "maxrecords": _MAX_RECORDS,
        }
    )
    req = urllib.request.Request(
        f"{_API}?{params}", headers={"User-Agent": "AICN-bot/1.0 (aicn digest pipeline)"}
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    # Rate-limit responses are plain text, not JSON — treat as empty.
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data.get("articles", []) or []


def _parse_seendate(seendate: str) -> str:
    """GDELT seendate is e.g. '20260719T110000Z' — crawl time, close enough
    to publish date for a 2-day window."""
    try:
        return datetime.datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").date().isoformat()
    except (TypeError, ValueError):
        return ""


def gather_gdelt_items():
    """Returns (items, error_note_or_None). Best-effort: any failure degrades
    to fewer/zero items, never an exception."""
    items = []
    errors = []
    for i, query in enumerate(_QUERIES):
        if i > 0:
            time.sleep(_SPACING_S)
        try:
            articles = _fetch_query(query)
        except Exception as exc:
            errors.append(f"gdelt query {i} failed: {exc}")
            continue
        for art in articles:
            url = art.get("url")
            title = (art.get("title") or "").strip()
            if not url or not title:
                continue
            if (art.get("language") or "English") != "English":
                continue
            items.append(
                {
                    "title": title,
                    "url": url,
                    "source": art.get("domain", ""),
                    "source_domain": art.get("domain", ""),
                    "published": _parse_seendate(art.get("seendate", "")),
                    "discovery": {"method": "search", "source_ref": "gdelt", "confidence": "low"},
                }
            )
    note = "; ".join(errors) if errors else None
    return items, note
