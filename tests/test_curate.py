import json
from types import SimpleNamespace

import curate


class FakeClient:
    """Stands in for anthropic.Anthropic: returns one canned JSON response."""

    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None
        self.messages = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )


CANDS = [{"title": f"T{i}", "url": f"u{i}", "source": "S"} for i in range(4)]


def item(url):
    return {"url": url, "category": "deepfakes", "summary": "s", "why_it_matters": "w", "flags": []}


def test_rejected_is_cleaned_to_real_unpublished_candidates():
    client = FakeClient({
        "is_light_run": False, "top_summary": "s", "new_entities": [],
        "items": [item("u0")],
        "rejected": [
            {"url": "u0", "reason": "no_ai"},           # also published: dropped
            {"url": "u1", "reason": "wrong_actor"},
            {"url": "u1", "reason": "no_ai"},           # repeat: first reason wins
            {"url": "invented", "reason": "no_ai"},     # not a candidate: dropped
            {"url": "u2", "reason": "made_up_reason"},  # unknown reason: dropped
            {"url": "u3", "reason": "duplicate"},
        ],
    })
    parsed, note = curate.curate_items(client, "m", CANDS)
    assert parsed["rejected"] == [{"url": "u1", "reason": "wrong_actor"}, {"url": "u3", "reason": "duplicate"}]
    assert note == "curate usage: input=10 output=5"


def test_request_uses_schema_with_rejected_and_room_to_finish():
    client = FakeClient({"is_light_run": True, "top_summary": "", "items": [], "new_entities": [], "rejected": []})
    curate.curate_items(client, "m", CANDS)
    schema = client.kwargs["output_config"]["format"]["schema"]
    assert "rejected" in schema["required"]
    assert schema["properties"]["rejected"]["items"]["properties"]["reason"]["enum"] == curate.REJECTION_REASONS
    assert client.kwargs["max_tokens"] >= 16000


def test_missing_rejected_does_not_break_parsing():
    client = FakeClient({"is_light_run": False, "top_summary": "s", "items": [item("u0")], "new_entities": []})
    parsed, _ = curate.curate_items(client, "m", CANDS)
    assert parsed["rejected"] == [] and [i["url"] for i in parsed["items"]] == ["u0"]


def test_every_schema_object_is_closed():
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(curate._OUTPUT_SCHEMA)
