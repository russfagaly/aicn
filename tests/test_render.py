import datetime
import json
import os
import xml.dom.minidom

import pytest

import render


def run(run_id, items=(), **extra):
    return {"run_id": run_id, "date": run_id, "item_count": len(items), "items": list(items), **extra}


def item(i, published="2026-10-20"):
    return {"id": f"id{i}", "title": f"T{i} & <b>", "url": f"https://e.com/{i}", "published": published, "summary": "s"}


@pytest.fixture
def root(tmp_path):
    os.makedirs(tmp_path / "data")
    os.makedirs(tmp_path / "state")
    return str(tmp_path)


def read(root, *parts):
    with open(os.path.join(root, *parts)) as f:
        return json.load(f)


# --- archive -------------------------------------------------------------

def test_archive_overflow_moves_runs_past_the_cap(root, monkeypatch):
    monkeypatch.setattr(render, "MAX_RUNS_KEPT", 3)
    digests = {"runs": [run(f"2026-10-{d:02d}") for d in range(10, 0, -1)]}
    assert render.archive_overflow(root, digests) == 7
    assert [r["run_id"] for r in digests["runs"]] == ["2026-10-10", "2026-10-09", "2026-10-08"]
    archived = [r["run_id"] for r in read(root, "data", "archive.json")["runs"]]
    assert archived == [f"2026-10-{d:02d}" for d in range(7, 0, -1)]


def test_archive_overflow_is_idempotent_and_newest_copy_wins(root, monkeypatch):
    monkeypatch.setattr(render, "MAX_RUNS_KEPT", 1)
    render.archive_overflow(root, {"runs": [run("2026-10-03"), run("2026-10-02", top_summary="old")]})
    render.archive_overflow(root, {"runs": [run("2026-10-03"), run("2026-10-02", top_summary="new")]})
    archived = read(root, "data", "archive.json")["runs"]
    assert [r["run_id"] for r in archived] == ["2026-10-02"]
    assert archived[0]["top_summary"] == "new"


def test_archive_overflow_dry_run_writes_nothing(root, monkeypatch):
    monkeypatch.setattr(render, "MAX_RUNS_KEPT", 1)
    digests = {"runs": [run("2026-10-02"), run("2026-10-01")]}
    assert render.archive_overflow(root, digests, dry_run=True) == 1
    assert len(digests["runs"]) == 1
    assert not os.path.exists(os.path.join(root, "data", "archive.json"))


def test_archive_totals(root):
    assert render.archive_totals(root) == (0, 0)
    with open(os.path.join(root, "data", "archive.json"), "w") as f:
        json.dump({"runs": [run("a", [item(1), item(2)]), run("b")]}, f)
    assert render.archive_totals(root) == (2, 2)


# --- same-day merge ------------------------------------------------------

def test_merge_same_day_runs_keeps_both_and_drops_duplicates():
    earlier = run("2026-10-20", [item(1), item(2)], top_summary="Morning.", candidates_reviewed=12)
    later = run("2026-10-20", [item(2), item(3)], top_summary="Afternoon.", candidates_reviewed=5)
    merged = render.merge_same_day_runs(earlier, later)
    assert [i["id"] for i in merged["items"]] == ["id2", "id3", "id1"]
    assert merged["item_count"] == 3 and merged["is_light_run"] is False
    assert merged["top_summary"] == "Morning. Afternoon."
    assert merged["candidates_reviewed"] == 17


def test_merge_same_day_runs_without_counts_has_no_count():
    merged = render.merge_same_day_runs(run("d"), run("d"))
    assert "candidates_reviewed" not in merged and merged["is_light_run"] is True


def test_merge_same_day_runs_with_one_count_keeps_it():
    assert render.merge_same_day_runs(run("d", candidates_reviewed=4), run("d"))["candidates_reviewed"] == 4


# --- feed ----------------------------------------------------------------

def test_feed_is_valid_rss_with_channel_link_and_escaping():
    xml_text = render._render_feed_xml([run("2026-10-20", [item(1)])])
    doc = xml.dom.minidom.parseString(xml_text)
    channel = doc.getElementsByTagName("channel")[0]
    links = [n for n in channel.childNodes if getattr(n, "tagName", None) == "link"]
    assert links and links[0].firstChild.data == render.SITE_URL
    assert doc.getElementsByTagName("title")[1].firstChild.data == "T1 & <b>"
    assert doc.getElementsByTagName("pubDate")[0].firstChild.data == "Tue, 20 Oct 2026 00:00:00 GMT"


def test_feed_caps_item_count():
    runs = [run(f"r{n}", [item(f"{n}-{i}") for i in range(10)]) for n in range(5)]
    doc = xml.dom.minidom.parseString(render._render_feed_xml(runs))
    assert len(doc.getElementsByTagName("item")) == render.FEED_ITEM_CAP


def test_rfc822_date_passes_through_unparseable():
    assert render._rfc822_date("2026-01-05") == "Mon, 05 Jan 2026 00:00:00 GMT"
    assert render._rfc822_date("soon") == "soon"
    assert render._rfc822_date(None) == ""


# --- end to end ----------------------------------------------------------

def candidates(*ids):
    return {
        f"u{i}": {
            "_id": f"c{i}", "title": f"Title {i}", "_normalized_url": f"https://e.com/{i}",
            "_normalized_title": f"title {i}", "source": "E", "published": "2026-10-20",
        }
        for i in ids
    }


def curated(*urls):
    return {
        "is_light_run": not urls, "top_summary": "s" if urls else "",
        "items": [{"url": u, "category": "deepfakes", "summary": "s", "why_it_matters": "w", "flags": []} for u in urls],
    }


def test_write_outputs_records_counts_marks_seen_and_archives(root, monkeypatch):
    monkeypatch.setattr(render, "MAX_RUNS_KEPT", 2)
    day = datetime.date(2026, 10, 21)
    for d in ("2026-10-19", "2026-10-20"):
        render.write_outputs(root, d, day, candidates(), curated(), dry_run=False)

    new_run, *_ = render.write_outputs(root, "2026-10-21", day, candidates(1, 2, 3), curated("u2", "nope"), dry_run=False)

    assert new_run["candidates_reviewed"] == 3
    assert [i["id"] for i in new_run["items"]] == ["c2"]  # a url the curator invented is ignored
    assert [r["run_id"] for r in read(root, "data", "digests.json")["runs"]] == ["2026-10-21", "2026-10-20"]
    assert [r["run_id"] for r in read(root, "data", "archive.json")["runs"]] == ["2026-10-19"]
    meta = read(root, "data", "meta.json")
    assert meta["total_runs"] == 3 and meta["total_items"] == 1
    assert read(root, "state", "seen.json")["ids"] == ["c1", "c2", "c3"]


def test_write_outputs_dry_run_leaves_real_files_alone(root):
    day = datetime.date(2026, 10, 21)
    render.write_outputs(root, "2026-10-21", day, candidates(1), curated("u1"), dry_run=True)
    assert os.path.exists(os.path.join(root, "data", "dryrun_digests.json"))
    for real in (("data", "digests.json"), ("data", "meta.json"), ("state", "seen.json"), ("feed.xml",)):
        assert not os.path.exists(os.path.join(root, *real)), real
