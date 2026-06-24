"""The single curation Anthropic API call: filter to on-topic, dedupe
syndicated stories, categorize, and write summary/why_it_matters/flags.
"""

import json
import re

_SYSTEM = """You are the curator for AICN (AI Campaign News), a neutral, non-partisan
tracker of AI use in political campaigns, elections, and political/issue advocacy.

Given a list of candidate news items (title, url, source, published date, and how
each was discovered), do the following:

1. Filter to ON-TOPIC items only: AI intersecting with political campaigns,
   elections, or political/issue advocacy — vendor & tool moves, use cases by
   campaign department, deepfakes/synthetic media in elections, synthetic
   respondents ("silicon sampling") as a polling replacement, regulation & legal
   (FEC, FCC, state laws, NO FAKES Act, TAKE IT DOWN Act), notable deployments/
   case studies, credible academic studies, and substantive analysis/op-eds.
   EXCLUDE generic AI-industry news with no campaign/election/advocacy nexus, and
   vague hype with no concrete development.
2. Among on-topic items, treat near-duplicate coverage of the same underlying
   story (syndication) as one — keep only the most authoritative source.
3. For each surviving item, in your own words:
   - category: exactly one of vendor_moves, deepfakes, polling_synthetic,
     regulation, deployments_studies, analysis_oped
   - summary: 1-2 sentence neutral paraphrase (no copied article text beyond a
     short attributed phrase)
   - why_it_matters: one line on significance to the field — never "for us" or
     for a party
   - flags: array, may be empty []. Use "vendor_self_reported" for vendor-claimed
     metrics presented as fact, "contested" for disputed claims, "speculative"
     for speculation framed as likely fact, "paywalled" if the source is paywalled.
4. Write top_summary: 2-3 plain, neutral sentences on the run's most important
   development(s) across the surviving items. Empty string only if is_light_run
   is true.
5. Set is_light_run to true if there is little or no real on-topic news this run.
   In that case items may be an empty array — do NOT pad with marginal items just
   to avoid the light-run label.

Never invent facts beyond what's implied by the title/source/url given — if
unsure of details, keep the summary high-level rather than guessing specifics.

Return ONLY a JSON object (no markdown fences, no prose) with this exact shape:
{
  "is_light_run": bool,
  "top_summary": str,
  "items": [
    {
      "url": str,
      "category": str,
      "summary": str,
      "why_it_matters": str,
      "flags": [str]
    }
  ]
}

Each "url" in your output MUST exactly match one of the candidate urls given to
you. Do not include a url that wasn't in the candidate list."""


def _extract_json_object(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def curate_items(client, model: str, candidates: list):
    """candidates: list of dicts with title/url/source/published/discovery/_id.

    Returns (curated_dict_or_None, cost_note_or_None).
    curated_dict has shape {"is_light_run": bool, "top_summary": str, "items": [...]}
    where each item only carries the curator-written fields plus "url" to rejoin.
    """
    if not candidates:
        return {"is_light_run": True, "top_summary": "", "items": []}, None

    payload = [
        {
            "title": c["title"],
            "url": c["url"],
            "source": c["source"],
            "published": c.get("published", ""),
            "discovery_method": c.get("discovery", {}).get("method"),
        }
        for c in candidates
    ]
    user_message = (
        "Candidate items (JSON array):\n"
        + json.dumps(payload, indent=2)
        + "\n\nFollow the system instructions and return only the JSON object."
    )

    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )
    text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    full_text = "\n".join(text_parts)
    parsed = _extract_json_object(full_text)

    valid_urls = {c["url"] for c in candidates}
    if parsed and "items" in parsed:
        parsed["items"] = [it for it in parsed["items"] if it.get("url") in valid_urls]

    usage = getattr(resp, "usage", None)
    note = f"curate usage: input={usage.input_tokens} output={usage.output_tokens}" if usage else None
    return parsed, note
