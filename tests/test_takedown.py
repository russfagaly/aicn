from takedown import remove_items


def _run(rid, ids, summary="s"):
    items = [{"id": i, "title": f"t{i}", "summary": "x"} for i in ids]
    return {"run_id": rid, "items": items, "item_count": len(items), "is_light_run": False, "top_summary": summary}


def test_remove_items_updates_counts_and_light_flag():
    runs = [_run("d1", ["a", "b"]), _run("d2", ["c"]), _run("d3", ["d"])]
    touched = remove_items(runs, {"b", "c"})
    assert touched == {"d1": ["tb"], "d2": ["tc"]}
    assert [it["id"] for it in runs[0]["items"]] == ["a"] and runs[0]["item_count"] == 1
    assert runs[0]["is_light_run"] is False
    # a day left empty is light with no summary
    assert runs[1]["item_count"] == 0 and runs[1]["is_light_run"] is True and runs[1]["top_summary"] == ""
    # untouched day unchanged
    assert runs[2]["item_count"] == 1 and runs[2]["top_summary"] == "s"


def test_remove_items_no_match_changes_nothing():
    runs = [_run("d1", ["a"])]
    assert remove_items(runs, {"zzz"}) == {}
    assert runs[0]["item_count"] == 1
