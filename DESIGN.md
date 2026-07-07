---
name: AICN — AI Campaign News
description: Daily automated digest tracking AI use in political campaigns, elections, and issue advocacy.
colors:
  accent: "#2b4a8b"
  accent-tint: "#e9eef7"
  accent-tint-border: "#d8e1f1"
  ink: "#1d2330"
  body-text: "#2a2f3a"
  muted-text: "#4b5563"
  quiet-text: "#6b7280"
  faint-text: "#9aa1ab"
  bg: "#eef0f3"
  surface: "#ffffff"
  border: "#e3e6ea"
  border-item: "#e7eaee"
  border-input: "#d4d9e0"
  border-pill: "#cdd7ea"
  selection: "#cdd9f0"
typography:
  display:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.35
  title:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "21px"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "'Public Sans', system-ui, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "'IBM Plex Mono', monospace"
    fontSize: "11px"
    fontWeight: 400
    letterSpacing: "0.04em"
rounded:
  pill: "999px"
  badge: "4px"
  card: "6px"
  input: "7px"
  hero: "10px"
spacing:
  page-max: "880px"
  page-pad: "28px"
  section-gap: "24px"
  item-pad: "20px"
components:
  chip-active:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    padding: "6px 14px"
  chip-inactive:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.quiet-text}"
    rounded: "{rounded.pill}"
    padding: "6px 14px"
  rss-pill:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    rounded: "{rounded.pill}"
    padding: "4px 11px"
  category-badge:
    backgroundColor: "{colors.accent-tint}"
    textColor: "{colors.accent}"
    rounded: "{rounded.badge}"
    padding: "2px 8px"
  filter-btn-active:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    padding: "5px 13px"
  filter-btn-inactive:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted-text}"
    rounded: "{rounded.pill}"
    padding: "5px 13px"
---

# Design System: AICN — AI Campaign News

## 1. Overview

**Creative North Star: "The Analyst's Terminal"**

AICN is built for practitioners who live in data — campaign professionals and tech vendors who don't need AI explained to them. The design serves this reader by getting out of their way. The interface is deliberately not a newspaper. It's closer to a structured intelligence output: precise, legible, flat, and accountable. Every surface signals that something real is happening here — a pipeline is running, sources are logged, methodology is visible.

The three-font system (Source Serif 4 for authority, Public Sans for utility, IBM Plex Mono for machine metadata) is load-bearing. Serif headlines give items the weight they deserve. Mono timestamps and source labels remind the reader that the content was gathered by a process. Sans handles everything in between. The cool blue-gray background (`#eef0f3`) creates a distinct reading plane that's neither editorial-warm nor tech-dark — it reads as infrastructure.

The design explicitly rejects the visual language of AI itself: no gradient accents, no glow, no neural-net aesthetics, no hero-metric panels. It equally rejects campaign-site energy and SaaS product marketing. AICN must be trusted by readers across the political spectrum, which means the palette and layout conventions carry zero partisan or promotional signal.

**Key Characteristics:**
- Flat elevation: no shadows anywhere. Depth through surface contrast and 1px borders only.
- Three-weight typographic system with hard functional roles per family.
- Publication Blue (`#2b4a8b`) reserved for interactive affordances and accent — never used as decoration.
- Information density calibrated to a professional reader who scans, not reads.
- Mono metadata as the "machine voice" — timestamps, source labels, run IDs are always IBM Plex Mono.

## 2. Colors: The Terminal Palette

Cool, institutional, non-partisan. The palette reads as infrastructure, not content.

### Primary
- **Publication Blue** (`#2b4a8b`): The single interactive accent. Used on active nav underlines, links, active filter chips, category badges, the RSS pill border, and the "why it matters" callout marker. Its rarity is the point — when it appears, it signals actionability or categorization, never decoration.
- **Accent Tint** (`#e9eef7`): The diluted blue surface used for the hero summary panel background and category badge fill. Signals "this is a structured output."
- **Accent Tint Border** (`#d8e1f1`): Border for the hero panel.

### Neutral
- **Ink** (`#1d2330`): Headings, item titles, wordmark. Near-black with a cool blue cast.
- **Body Text** (`#2a2f3a`): Primary reading text.
- **Muted Text** (`#4b5563`): Summaries, secondary body copy, rationale text on proposals.
- **Quiet Text** (`#6b7280`): Metadata, inactive nav links, filter button labels, tagline.
- **Faint Text** (`#9aa1ab`): Mono timestamps, section count labels, empty states. The lightest legible gray.
- **Background** (`#eef0f3`): Page canvas. Cool blue-gray — not warm, not dark. The unambiguous "reading plane."
- **Surface** (`#ffffff`): Cards, header, proposals. White contrast against the bg.
- **Border** (`#e3e6ea`): Primary structural borders — header bottom, cards.
- **Border Item** (`#e7eaee`): Feed item dividers. Slightly lighter than structural borders.
- **Border Input** (`#d4d9e0`): Search input, inactive filter buttons.
- **Border Pill** (`#cdd7ea`): RSS pill outline.
- **Selection** (`#cdd9f0`): Text selection highlight. Tinted accent blue.

### Named Rules

**The One Voice Rule.** Publication Blue (`#2b4a8b`) appears only on interactive affordances and structural signifiers (active state, link, badge, callout marker). Never use it as a background fill for large surfaces, decorative accents, or hover effects on non-interactive elements. Its presence must always mean something to the reader.

**The No-Warm Rule.** No warm tones anywhere — no amber, ochre, cream, or parchment. The palette is cool throughout. The single exception is the `is_light_run` warning state (`#f4efe2` / `#8a7330`), which exists precisely because it needs to signal "something different happened today."

## 3. Typography

**Display Font:** Source Serif 4 (Georgia fallback, serif)
**Body Font:** Public Sans (system-ui fallback, sans-serif)
**Mono Font:** IBM Plex Mono (monospace)

**Character:** Source Serif 4 carries weight and credibility for headlines and the wordmark — it signals that each item matters. Public Sans is clean utility: readable, neutral, unserifed, for everything the reader needs to scan fast. IBM Plex Mono is the machine's voice: timestamps, source domains, run metadata, badge labels. The contrast between the three is functional, not decorative.

### Hierarchy

- **Display** (700 weight, 30px, leading 1.1, tracking -0.01em): The "AICN" wordmark only. Single use.
- **Hero Summary** (Source Serif 4, 400 weight, 21px, leading 1.5): The AI-generated run summary in the hero panel. Larger than item titles, lighter weight — reads as editorial voice.
- **Headline** (Source Serif 4, 600 weight, 19px, leading 1.35): Individual item titles and proposal names. The primary reading unit.
- **Page Title** (Source Serif 4, 700 weight, 26px): Interior page h1 (Sources, Library, Proposals).
- **Section Header** (Source Serif 4, 600 weight, 17px): Section sub-headings (e.g. "Curated RSS/Atom feeds").
- **Body** (Public Sans, 400 weight, 14.5px, leading 1.6): Summaries and rationale. Keep line length under 70ch.
- **Meta** (Public Sans, 400–600 weight, 13–13.5px): Secondary body — card rationale, nav labels, filter buttons.
- **Label** (IBM Plex Mono, 400 weight, 11–11.5px, tracking 0.02–0.1em, uppercase): Source name, date, timestamps, section counts, run metadata. Always monospace, always muted.
- **Badge** (IBM Plex Mono, 400 weight, 10–10.5px, tracking 0.06–0.12em, uppercase): Category badges, status pills, kicker labels.

### Named Rules

**The Mono-as-Machine Rule.** IBM Plex Mono appears only on data that was generated by a process: timestamps, source domains, run IDs, counts, badge labels. It must never appear on editorial copy, summaries, or user-facing explanatory text. Its presence signals "a machine produced this value."

**The Serif-for-Signal Rule.** Source Serif 4 appears only on content that carries editorial weight: the wordmark, item headlines, the hero summary, and page titles. Navigation labels, filter chips, search inputs, and metadata stay in Public Sans.

## 4. Elevation

No shadows anywhere. The system is flat by design. Depth is conveyed entirely through surface contrast (the `#eef0f3` background against `#ffffff` cards and header) and 1px borders.

The hierarchy is: `#eef0f3` page canvas → `#ffffff` surface (cards, header) → `#e9eef7` tinted accent panel (hero summary). Three levels, zero shadows. Any shadow added to this system would disrupt the infrastructure register — it would read as "designed," and designed things have opinions.

### Named Rules

**The Flat-by-Default Rule.** No `box-shadow` on any element in any state. Hover and focus states communicate through color shift or border change only. If a component needs to "lift," reconsider the component — lifting is not in the AICN vocabulary.

## 5. Components

### Category Filter Chips
The primary interactive control on the feed page. Pill-shaped throughout.
- **Shape:** Full pill (999px radius)
- **Inactive:** White background, `#d4d9e0` border, `#6b7280` text, 13px Public Sans
- **Active:** `#2b4a8b` background and border, white text
- **Transition:** `all 0.12s` on background, color, border-color
- **Padding:** 6px 14px

### Category Badge (Feed Items)
- **Style:** Mono 10.5px uppercase, `#e9eef7` background, `#2b4a8b` text, `4px` radius, 2px 8px padding
- **Rule:** One badge per feed item, leading the item before the headline.

### Feed Item
The primary content unit. Not a card — items are separated by a 1px `#e7eaee` border-bottom only. No background, no radius, no shadow.
- **Headline:** Source Serif 4, 600, 19px, `#1d2330`, no underline at rest
- **Headline hover:** Underline with `#2b4a8b` underline-color
- **Meta line:** IBM Plex Mono, 11.5px, `#9aa1ab`, uppercase, tracking 0.02em — source and date separated by ` · `
- **Summary:** Public Sans, 14.5px, `#4b5563`, leading 1.6
- **Padding:** 20px top and bottom

### Why-it-Matters Callout
A designated signed exception to the flat system. Appears within feed items when additional context exists.
- **Style:** `border-left: 3px solid #2b4a8b`, `padding: 2px 0 2px 14px`
- **Label:** IBM Plex Mono, 10.5px, uppercase, tracking 0.12em, `#2b4a8b` — "NOTES"
- **Body:** Public Sans, 14px, `#384152`, leading 1.55

### Hero Summary Panel
The run-level context block at the top of the feed.
- **Background:** `#e9eef7` with `1px solid #d8e1f1` border, 10px radius, 26px 30px padding
- **Kicker:** IBM Plex Mono, 10.5px, uppercase, white text on `#2b4a8b` background, 4px radius
- **Summary text:** Source Serif 4, 400, 21px, `#2c3340`, leading 1.5
- **Jump links:** 13.5px, `#2b4a8b`, no underline, `»` leader

### Navigation (Site Header)
- **Layout:** Flex, space-between, max-width 880px, 28px horizontal padding
- **Wordmark:** "AICN" in Source Serif 4 700 30px `#1d2330` + kicker in Public Sans 600 13px uppercase tracking 0.16em `#2b4a8b`
- **Nav links:** Public Sans 13px, inactive `#6b7280`, active `#2b4a8b` with `font-weight: 600` and `border-bottom: 2px solid #2b4a8b; padding-bottom: 1px`
- **RSS pill:** 12.5px `#2b4a8b` text, `1px solid #cdd7ea` border, 999px radius, 4px 11px padding, no background

### Proposal Card
Used on the Proposals page.
- **Shape:** 6px radius, `1px solid #e3e6ea` border, white background, 18px 20px padding
- **Meta:** IBM Plex Mono 11px, `#9aa1ab`, uppercase, tracking 0.04em
- **Title:** Source Serif 4, 600, 19px, `#1d2330`
- **Rationale:** Public Sans, 13.5px, `#4b5563`, leading 1.55
- **Kind badge:** Mono 10px uppercase, `#edf0f4` background, `#6b7280` text, 999px radius
- **Status badge:** Same shape with leading `8px` dot indicator

### Search Input
- **Style:** White background, `1px solid #d4d9e0` border, 7px radius, 9px 14px padding
- **Font:** Public Sans 14px `#2a2f3a`
- **Focus:** `outline: none` — relies on existing browser ring (minimal)
- **Note:** Intentionally understated — in an information-dense feed, the search field shouldn't shout.

### Pagination Buttons
- **Style:** White background, `1px solid #d4d9e0` border, 7px radius, 7px 16px padding
- **Active:** `#4b5563` text
- **Disabled:** `#c3c8d1` text, `cursor: default`

## 6. Do's and Don'ts

### Do:
- **Do** keep Publication Blue (`#2b4a8b`) exclusively on interactive affordances: active states, links, category badges, and the Notes callout marker. One color, one job.
- **Do** use IBM Plex Mono for any value generated by a process — timestamps, source domains, run IDs, counts. Mono is the machine's voice.
- **Do** use Source Serif 4 for content that carries editorial weight: item headlines, the hero summary, page titles. Everything else is Public Sans.
- **Do** keep the page canvas at `#eef0f3` — it's the reading plane that separates the content layer from the page frame.
- **Do** use 1px solid borders for depth. The system is flat; borders are the only structural tool.
- **Do** write category labels, source names, and date metadata in IBM Plex Mono uppercase. These are machine-generated values; they should look like it.
- **Do** keep item summaries under 70ch line length. The reader is scanning, not reading a longform piece.

### Don't:
- **Don't** use any `box-shadow` anywhere. The Flat-by-Default Rule has no exceptions.
- **Don't** use SaaS product marketing aesthetics — hero metrics, gradient accents, feature grids, or anything that reads as a product pitch. AICN is a publication, not a product.
- **Don't** use AI-hype visual language — glowing neural nets, circuit-board patterns, cyan-on-dark, anything that mimics the aesthetic of the industry AICN is covering. The site must feel credible to readers skeptical of AI.
- **Don't** use warm tones (amber, ochre, cream, parchment) as structural colors. The palette is cool throughout.
- **Don't** use Publication Blue as a decorative background fill on any large surface. Its rarity is the point.
- **Don't** use partisan visual conventions — red/blue political energy, candidate-site aesthetics. The design must read as third-party infrastructure across the political spectrum.
- **Don't** put Source Serif 4 on navigation, filter chips, metadata, or body copy. Serif is for signal; everything operational stays in Public Sans.
- **Don't** add cards, borders, or backgrounds to feed items — they are separated by a 1px divider only. Cards make the feed read as a product; dividers make it read as a list.
- **Don't** use IBM Plex Mono for editorial copy, summaries, or explanatory text. Mono is the machine's voice, not the editorial voice.
