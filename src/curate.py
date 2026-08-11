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

1. Filter to ON-TOPIC items only. AICN covers AI as a CAMPAIGN TOOL, not AI as a
   political SUBJECT. An item is on-topic only if ALL THREE hold:

   (a) AI/ML is named, described, or central to the story — not merely implied by
       the outlet's beat or the vendor's general reputation.
   (b) ACTOR: the one using AI is a campaign, party, committee, PAC, or advocacy
       group running political programs — or a vendor, consultant, or investor
       building for them.
   (c) PRACTICAL USE: the item says something concrete about capability, adoption,
       targeting, cost, technique, or measured effect — something a campaign's
       digital director could act on or learn from. "AI is a factor in politics"
       is not enough.

   THE DECIDING QUESTION when a call is close — WHOSE HANDS IS THE AI IN?
   In a campaign's hands, or a vendor's selling to campaigns: IN.
   In a legislature's, court's, regulator's, journalist's, or researcher's: OUT.
   An outlet, academic, or analytics startup using AI to STUDY a race is not a
   campaign using AI, however good the analysis and however central the AI is to
   how the study was produced. The same goes for an AI-generated attack ad where
   the story is the candidate's response: the AI is in an anonymous ad-maker's
   hands and the article is about the reaction.

   A vendor's launch, demo, or case study is IN even when no campaign has
   publicly adopted the tool yet — a practitioner could go buy it tomorrow. What
   matters is that the thing is built for campaign work, not that adoption has
   already been reported.

   Qualifying content: AI-powered tools campaigns use, AI-generated content a
   campaign actually deployed, AI chatbots in voter contact, synthetic respondents
   ("silicon sampling") replacing real polling, credible studies measuring AI's
   effects on campaign work, and substantive practitioner analysis.

   EXCLUDE — read this carefully, it is where most mistakes happen:
   - Legislation and bill tracking (NO FAKES Act, TAKE IT DOWN Act, state deepfake
     or disclosure statutes), regulators (FEC, FCC), court rulings, and AI policy
     at large (export controls, data-center siting, taxation). These fail test (b):
     the actor is a legislature, agency, or court, not a campaign.
   - AI companies' own political spending, lobbying, or policy campaigns. The actor
     is an AI lab, not a campaign using AI.
   - Government agencies using AI for policy or administration. Not a campaign.
   - Journalists, academics, or analytics firms using AI to analyze an election —
     scraping and classifying ads, videos, or posts to describe a race. The AI is
     the researcher's instrument, not campaign infrastructure. This is an easy one
     to get wrong, because the AI is genuinely central to the story.
   - Platform moderation policy and content-rule changes.
   - A synthetic-media incident where the story IS the reaction — a lawsuit, a
     candidate objecting, a regulator responding. Include such an item only when it
     reports how the thing was made, targeted, funded, or how it performed.
   - Campaign tech or political data deals with no AI/ML component (voter-file
     integrations, programmatic ad buys, CRM/ad-tech partnerships) even if the
     vendor is on the watchlist; generic AI-industry news with no campaign nexus;
     vague hype with no concrete development.

   GEOGRAPHY: any country qualifies. Weight toward western democracies — the United
   States, and with particular interest, Canada and the United Kingdom.

   WATCHLIST NOTE: Discovery method "watchlist" means an entity we track
   appeared in the article — it does NOT mean the article is automatically
   on-topic. Apply the same AI + elections filter; a watchlist-sourced item
   about a data partnership, ad-targeting deal, or company news with no AI
   component must be excluded.
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
   development(s) across the surviving items. Write one whenever there is at
   least one item — a two-item run still needs orientation just as much as a
   six-item one. Use an empty string ONLY when items is empty.
6. Set is_light_run to true ONLY when there is no real on-topic news at all and
   items is an empty array. A run with even one genuine item is a normal run for
   this publication, not a light one — the median run here is a single item, so
   do not treat a small run as a shortfall. Do NOT pad with marginal items just
   to avoid the label, and do NOT apply the label merely because the run is
   small.
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


# Structured-outputs schema: the API guarantees the response text is valid
# JSON matching this shape, which removes the pipeline's only hard-abort path
# (a curation response that fails regex JSON extraction). The system prompt
# still describes the fields — the schema enforces shape, the prompt supplies
# the semantics.
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_light_run": {"type": "boolean"},
        "top_summary": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "vendor_moves",
                            "deepfakes",
                            "polling_synthetic",
                            "regulation",
                            "deployments_studies",
                            "analysis_oped",
                        ],
                    },
                    "summary": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "flags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "vendor_self_reported",
                                "contested",
                                "speculative",
                                "paywalled",
                            ],
                        },
                    },
                },
                "required": ["url", "category", "summary", "why_it_matters", "flags"],
                "additionalProperties": False,
            },
        },
        "new_entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["vendor", "person", "regulator", "legislation"],
                    },
                    "rationale": {"type": "string"},
                    "example_url": {"type": "string"},
                },
                "required": ["name", "kind", "rationale", "example_url"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["is_light_run", "top_summary", "items", "new_entities"],
    "additionalProperties": False,
}


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
            output_config={"format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}},
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as exc:
        return None, f"curate call failed: {exc}"

    text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    full_text = "\n".join(text_parts)
    # Structured outputs guarantees valid JSON; keep the regex extractor as a
    # belt-and-suspenders fallback (e.g. stop_reason=max_tokens truncation).
    try:
        parsed = json.loads(full_text)
    except json.JSONDecodeError:
        parsed = _extract_json_object(full_text)

    valid_urls = {c["url"] for c in candidates}
    if parsed and "items" in parsed:
        parsed["items"] = [it for it in parsed["items"] if it.get("url") in valid_urls]

    usage = getattr(resp, "usage", None)
    note = f"curate usage: input={usage.input_tokens} output={usage.output_tokens}" if usage else None
    return parsed, note
