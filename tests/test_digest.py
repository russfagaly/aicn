import datetime

from digest import build_avoid_titles, drop_stale_candidates

TODAY = datetime.date(2026, 10, 21)


def test_drop_stale_candidates_applies_age_floor_and_rejects_bad_dates():
    cands = [
        {"title": "fresh", "published": "2026-10-20"},
        {"title": "edge", "published": "2026-10-07"},  # exactly 14 days
        {"title": "old", "published": "2026-10-06"},
        {"title": "undated", "published": ""},
        {"title": "garbage", "published": "last week"},
        {"title": "future", "published": "2026-10-30"},
        {"title": "tomorrow", "published": "2026-10-22T09:00:00Z"},
    ]
    kept, dropped = drop_stale_candidates(cands, TODAY, max_age_days=14)
    assert [c["title"] for c in kept] == ["fresh", "edge", "tomorrow"]
    assert {t for _, t in dropped} == {"old", "undated", "garbage", "future"}


def test_build_avoid_titles_newest_first_deduped_and_capped():
    memory = {"2026-10-19": ["Older"], "2026-10-20": ["Newest", "older  "]}
    published = [{"title": "Published one"}, {"title": "NEWEST"}]
    assert build_avoid_titles(memory, published, limit=10) == ["Newest", "older", "Published one"]
    assert build_avoid_titles(memory, published, limit=2) == ["Newest", "older"]


def test_drop_homepages_removes_front_pages_only():
    from digest import drop_homepages

    cands = [
        {"title": "home", "url": "https://thepoliticalgroup.com/"},
        {"title": "bare", "url": "https://example.com"},
        {"title": "index", "url": "https://example.com/index.html"},
        {"title": "article", "url": "https://example.com/news/ai-launch"},
        {"title": "query", "url": "https://example.com/?p=123"},
    ]
    kept, dropped = drop_homepages(cands)
    assert [c["title"] for c in kept] == ["article", "query"]  # /?p=123 is a WordPress post
    assert set(dropped) == {"home", "bare", "index"}
