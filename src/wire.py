"""Wire accepted proposals into the gathering config.

Accepting a proposal used to only flip a status string in proposals.json —
nothing added the domain to sources.yaml, site_targets.yaml, or watchlist.yaml,
so approved sources were never actually gathered from. This module closes that
gap, and `find_unwired` detects it if it ever reopens.

The config files carry substantial provenance comments (sources.yaml's
`unavailable` block and its per-outlet reasons, watchlist.yaml's cadence
history). PyYAML drops comments on dump, so these writers never round-trip
through yaml.safe_dump — they insert formatted text at the end of the target
list and leave every other byte of the file alone.
"""

import os
import re
import urllib.parse

import yaml

# Controlled vocabularies, read from the config itself rather than hardcoded so
# they can't drift out of sync with what the files actually use.
TIER_FALLBACK = [
    "tech_accountability",
    "left_movement_tech",
    "trade_industry",
    "regulation_tracker",
    "elections_coverage",
]
KIND_FALLBACK = ["vendor", "regulator", "legislation", "org_no_feed", "person"]
CADENCES = ["daily", "weekly"]


def slugify(value: str) -> str:
    """Domain or name -> an id in the style the config files already use."""
    value = value.strip().lower()
    value = value.removeprefix("www.")
    # Drop a TLD so nypost.com -> nypost, matching ids like `axios`, `semafor`.
    value = re.sub(r"\.(com|org|net|news|io|gov|us|ai|co|dev)$", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _uniq_id(base: str, taken: set) -> str:
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


# ---------------------------------------------------------------------------
# Comment-preserving insertion
# ---------------------------------------------------------------------------

def insert_into_block(text: str, list_key: str, block: str) -> str:
    """Insert `block` at the end of the top-level `list_key:` list in `text`.

    Finds the last indented, non-blank line belonging to the list and inserts
    after it. Trailing blank lines and any column-0 comments that introduce the
    *next* top-level key (sources.yaml's `unavailable:` header, for example) are
    left below the insertion, where they belong.
    """
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(list_key)}:\s*(#.*)?$", line):
            start = i
            break
    if start is None:
        raise ValueError(f"top-level key '{list_key}:' not found")

    last_content = None
    for i in range(start + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            continue
        if line[0].isspace():
            last_content = i
            continue
        if stripped.startswith("#"):
            # Could introduce the next key; keep scanning without claiming it.
            continue
        break  # a new top-level key — the list is over

    if last_content is None:
        raise ValueError(f"'{list_key}:' has no entries to append after")

    if not lines[last_content].endswith("\n"):
        lines[last_content] += "\n"
    if not block.endswith("\n"):
        block += "\n"
    lines.insert(last_content + 1, block)
    return "".join(lines)


# ---------------------------------------------------------------------------
# Config readers
# ---------------------------------------------------------------------------

def _load(root: str, name: str) -> dict:
    with open(os.path.join(root, name)) as f:
        return yaml.safe_load(f) or {}


def known_feed_domains(sources: dict) -> set:
    out = set()
    for feed in sources.get("feeds", []) or []:
        host = urllib.parse.urlsplit(feed.get("url", "")).netloc.removeprefix("www.")
        if host:
            out.add(host)
    return out


def known_target_domains(targets: dict) -> set:
    return {
        t.get("domain", "").removeprefix("www.")
        for t in (targets.get("targets", []) or [])
        if t.get("domain")
    }


def known_entity_names(watchlist: dict) -> set:
    return {e["name"] for e in (watchlist.get("entities", []) or []) if e.get("name")}


def vocab(root: str) -> dict:
    """Controlled vocabularies offered at accept time.

    Union of what the config already uses and the known vocabulary, so a value
    that is valid but not yet used stays selectable — `person` is the case that
    matters, since the curator emits it for figures like a senator but no
    watchlist entity carries that kind yet.
    """
    sources = _load(root, "sources.yaml")
    watchlist = _load(root, "watchlist.yaml")
    tiers = {f.get("tier") for f in (sources.get("feeds") or []) if f.get("tier")}
    kinds = {e.get("kind") for e in (watchlist.get("entities") or []) if e.get("kind")}
    return {
        "tiers": sorted(tiers | set(TIER_FALLBACK)),
        "kinds": sorted(kinds | set(KIND_FALLBACK)),
        "cadences": CADENCES,
    }


def existing_ids(root: str) -> dict:
    sources = _load(root, "sources.yaml")
    targets = _load(root, "site_targets.yaml")
    watchlist = _load(root, "watchlist.yaml")
    return {
        "sources.yaml": {f.get("id") for f in (sources.get("feeds") or [])},
        "site_targets.yaml": {t.get("id") for t in (targets.get("targets") or [])},
        "watchlist.yaml": {e.get("id") for e in (watchlist.get("entities") or [])},
    }


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _write(root: str, filename: str, list_key: str, block: str) -> str:
    path = os.path.join(root, filename)
    with open(path) as f:
        text = f.read()
    updated = insert_into_block(text, list_key, block)
    # Parse before committing to disk: a malformed block should fail loudly
    # rather than silently break the next pipeline run.
    yaml.safe_load(updated)
    with open(path, "w") as f:
        f.write(updated)
    return path


def wire_feed(root: str, entry_id: str, name: str, url: str, tier: str, description: str) -> str:
    block = (
        f"\n  # Added from an accepted proposal.\n"
        f"  - id: {entry_id}\n"
        f"    name: {yaml_scalar(name)}\n"
        f"    description: {yaml_scalar(description)}\n"
        f"    url: {url}\n"
        f"    tier: {tier}\n"
    )
    return _write(root, "sources.yaml", "feeds", block)


def wire_target(root: str, entry_id: str, name: str, domain: str, cadence: str, description: str) -> str:
    block = (
        f"  # Added from an accepted proposal.\n"
        f"  - id: {entry_id}\n"
        f"    name: {yaml_scalar(name)}\n"
        f"    description: {yaml_scalar(description)}\n"
        f"    domain: {domain}\n"
        f"    cadence: {cadence}\n"
    )
    return _write(root, "site_targets.yaml", "targets", block)


def wire_entity(root: str, entry_id: str, name: str, kind: str, cadence: str) -> str:
    block = (
        f"  # Added from an accepted proposal.\n"
        f"  - id: {entry_id}\n"
        f"    name: {yaml_scalar(name)}\n"
        f"    kind: {kind}\n"
        f"    cadence: {cadence}\n"
    )
    return _write(root, "watchlist.yaml", "entities", block)


def yaml_scalar(value: str) -> str:
    """Quote a name only when YAML would otherwise misread it.

    Rather than guess at the special characters, round-trip the bare value and
    quote whenever YAML hands back anything other than the identical string.
    That catches the non-obvious cases too: YAML 1.1 reads `Yes`/`No`/`On` as
    booleans and `2026` as an int, so an outlet named "Yes" would otherwise be
    written as a boolean and break the config.
    """
    needs_quotes = value != value.strip() or not value
    if not needs_quotes:
        try:
            parsed = yaml.safe_load(value)
        except yaml.YAMLError:
            needs_quotes = True
        else:
            needs_quotes = not isinstance(parsed, str) or parsed != value
    if needs_quotes:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def next_id(root: str, filename: str, base: str) -> str:
    return _uniq_id(slugify(base), existing_ids(root)[filename] - {None})


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def find_unwired(root: str, proposals: list) -> list:
    """Accepted proposals that never made it into the gathering config."""
    sources = _load(root, "sources.yaml")
    targets = _load(root, "site_targets.yaml")
    watchlist = _load(root, "watchlist.yaml")
    feeds = known_feed_domains(sources)
    sites = known_target_domains(targets)
    entities = {n.lower() for n in known_entity_names(watchlist)}

    unwired = []
    for p in proposals:
        if p.get("status") != "accepted":
            continue
        value = p.get("value", "")
        if p.get("kind") == "source":
            domain = value.removeprefix("www.")
            if domain not in feeds and domain not in sites:
                unwired.append(p)
        else:
            if value.lower() not in entities:
                unwired.append(p)
    return unwired
