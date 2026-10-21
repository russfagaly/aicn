from promote import build_entity_proposals, build_source_proposals, update_domain_stats


def test_update_domain_stats_skips_known_domains_and_caps_examples():
    stats = {}
    cands = [{"_normalized_url": f"https://www.new.org/{i}"} for i in range(7)] + [{"url": "https://known.com/x"}]
    update_domain_stats(stats, cands, {"known.com"}, run_id="2026-10-21")
    assert list(stats) == ["new.org"]
    assert stats["new.org"]["count"] == 7 and len(stats["new.org"]["example_urls"]) == 5
    assert stats["new.org"]["last_seen"] == "2026-10-21"


def test_build_source_proposals_respects_threshold_and_existing():
    stats = {
        "a.org": {"count": 3, "example_urls": ["https://a.org/1"]},
        "b.org": {"count": 1, "example_urls": []},
        "c.org": {"count": 5, "example_urls": []},
    }
    existing = [{"value": "c.org"}]
    props = build_source_proposals(stats, 2, existing, set(), run_id="r", feed_urls={"a.org": "https://a.org/feed"})
    assert [p["value"] for p in props] == ["a.org"]
    assert props[0]["id"] == "prop-source-a-org" and props[0]["feed_url"] == "https://a.org/feed"


def test_build_entity_proposals_dedupes_case_insensitively():
    ents = [
        {"name": "Acme Vote", "example_url": "https://x"},
        {"name": "acme vote"},
        {"name": "FEC"},
        {"name": "Old News"},
        {"name": "  "},
    ]
    props = build_entity_proposals(ents, [{"value": "old news"}], {"FEC"}, run_id="r")
    assert [p["value"] for p in props] == ["Acme Vote"]
    assert props[0]["id"] == "prop-entity-acme-vote" and props[0]["example_urls"] == ["https://x"]
