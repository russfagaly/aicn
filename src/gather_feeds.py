"""Gather candidate items from curated RSS/Atom feeds via feedparser."""

import datetime
import urllib.parse

import feedparser
from dateutil import parser as dtparser


def _parse_published(entry):
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                return dtparser.parse(val)
            except (ValueError, OverflowError):
                continue
    return None


def gather_feed_items(feed_id: str, name: str, url: str, lookback_days: int = 7):
    """Returns (items, error_message_or_None)."""
    try:
        parsed = feedparser.parse(url)
    except Exception as exc:
        return [], f"{feed_id}: failed to parse ({exc})"

    if parsed.bozo and not parsed.entries:
        return [], f"{feed_id}: unparseable feed ({getattr(parsed, 'bozo_exception', 'unknown error')})"

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=lookback_days)
    items = []
    for entry in parsed.entries:
        pub = _parse_published(entry)
        if pub is None:
            continue
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=datetime.timezone.utc)
        if pub < cutoff:
            continue
        link = entry.get("link")
        title = entry.get("title", "").strip()
        if not link or not title:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "source": name,
                "source_domain": urllib.parse.urlsplit(link).netloc.replace("www.", ""),
                "published": pub.date().isoformat(),
                "discovery": {"method": "feed", "source_ref": feed_id, "confidence": "high"},
            }
        )
    return items, None
