"""The single curation Anthropic API call: filter to on-topic, dedupe
syndicated stories, categorize, and write summary/why_it_matters/flags.
"""

import json
import re

_SYSTEM = """You are the curator for AICN (AI Campaign News), a neutral, non-partisan
tracker of AI use in political campaigns, elections, and political/issue advocacy.

Given a list of candidate news items (title, url, source, published date, how each
was discovered, and — when available — the real page <title> and meta description),
do the following:

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
3. You will also be given a list of items ALREADY PUBLISHED in the last several
   days (title + summary). Before including a candidate, check whether it's just
   continued coverage of one of those — a different outlet writing up the same
   underlying event or announcement with no real new development. If so, EXCLUDE
   it; the story has already run. Only keep a follow-up article if it reports a
   materially new development (e.g. a vote actually happened after we covered it
   advancing, a new figure/quote, a reversal). When in doubt, exclude — readers
   have already seen the story.
4. For each surviving item, in your own words:
   - category: exactly one of vendor_moves, deepfakes, polling_synthetic,
     regulation, deployments_studies, analysis_oped
   - summary: 1-2 sentence neutral paraphrase (no copied article text beyond a
     short attributed phrase). BE CONCRETE: name the actual people, companies,
     products, or legislation involved whenever the page title or description
     gives you a real name — don't write "a candidate" or "a voter data firm"
     when the source tells you who it actually is. Don't editorialize or frame
     the item as a question/test/cliffhanger ("a test of whether...", "could this
     mean...") — just state what happened.
   - why_it_matters: one line on significance to the field — never "for us" or
     for a party
   - flags: array, may be empty []. Use "vendor_self_reported" for vendor-claimed
     metrics presented as fact, "contested" for disputed claims, "speculative"
     for speculation framed as likely fact, "paywalled" if the source is paywalled.
5. Write top_summary: 2-3 plain, neutral sentences on the run's most important
   development(s) across the surviving items. Empty string only if is_light_run
   is true.
6. Set is_light_run to true if there is little or no real on-topic news this run.
   In that case items may be an empty array — do NOT pad with marginal items just
   to avoid the light-run label.
7. From the surviving published items, extract any vendors, tools, companies,
   people, pieces of legislation, or regulatory bodies that are newly-named
   and not yet widely known in this space — these are candidates for the entity
   watchlist. Exclude household AI names (OpenAI, Google, Anthropic, Meta, etc.),
   major platforms, and legislation already on the watchlist (NO FAKES Act, TAKE
   IT DOWN Act, FEC, FCC). Only flag genuinely niche or emerging names that a
   beat reporter would want to track going forward. Return them as new_entities.

Never invent facts beyond what's implied by the title/url/page metadata given —
if a name or detail genuinely isn't there, keep that part of the summary
high-level rather than guessing. The instruction to "be concrete" means use the
specifics you ARE given, not invent ones you aren't.

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
  ],
  "new_entities": [
    {
      "name": str,
      "kind": "vendor|person|regulator|legislation",
      "rationale": str,
      "example_url": str
    }
  ]
}

new_entities may be an empty array. Each "url" in items MUST exactly match one
of the candidate urls given to you. Do not include a url that wasn't in the
candidate list."""


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


def curate_items(client, model: str, candidates: list, recent_published: list = None):
    """candidates: list of dicts with title/url/source/published/discovery/_id,
    plus optional page_title/page_description from the real page.
    recent_published: list of {title, summary, published} already-published in
    the last several days, used for the continued-coverage check.

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
            "page_title": c.get("page_title"),
            "page_description": c.get("page_description"),
        }
        for c in candidates
    ]
    user_message = (
        "Already published in the last several days (JSON array — check candidates "
        "against this for continued coverage):\n"
        + json.dumps(recent_published or [], indent=2)
        + "\n\nCandidate items (JSON array):\n"
        + json.dumps(payload, indent=2)
        + "\n\nFollow the system instructions and return only the JSON object."
    )

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=8000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as exc:
        return None, f"curate call failed: {exc}"

    text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    full_text = "\n".join(text_parts)
    parsed = _extract_json_object(full_text)

    valid_urls = {c["url"] for c in candidates}
    if parsed and "items" in parsed:
        parsed["items"] = [it for it in parsed["items"] if it.get("url") in valid_urls]

    usage = getattr(resp, "usage", None)
    note = f"curate usage: input={usage.input_tokens} output={usage.output_tokens}" if usage else None
    return parsed, note
