"""Interactive CLI for reviewing proposals.json entries.

Usage:
    python3 src/review.py              # review all pending proposals
    python3 src/review.py --all        # review all proposals (including decided ones)
    python3 src/review.py --id <id>    # review a specific proposal by ID
"""

import argparse
import json
import os
import sys

import wire

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPOSALS_PATH = os.path.join(ROOT, "data", "proposals.json")

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
BLUE   = "\033[34m"
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"


def load():
    with open(PROPOSALS_PATH) as f:
        return json.load(f)


def save(data):
    with open(PROPOSALS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def status_color(status):
    return {
        "pending":  YELLOW + "pending"  + RESET,
        "accepted": GREEN  + "accepted" + RESET,
        "rejected": RED    + "rejected" + RESET,
    }.get(status, status)


def print_proposal(p, index=None, total=None):
    counter = f"[{index}/{total}] " if index is not None else ""
    kind = "Source" if p["kind"] == "source" else "Entity"
    print()
    print(f"{BOLD}{counter}{kind}: {p['value']}{RESET}  {DIM}({p['id']}){RESET}")
    print(f"  Status:  {status_color(p['status'])}")
    if p.get("first_proposed"):
        print(f"  Proposed: {DIM}{p['first_proposed']}{RESET}")
    print(f"  {p['rationale']}")
    if p.get("feed_url"):
        print(f"  Feed:    {CYAN}{p['feed_url']}{RESET}")
    for url in p.get("example_urls") or []:
        print(f"  Example: {DIM}{url}{RESET}")


def prompt_decision(p):
    current = p["status"]
    hints = []
    if current != "accepted": hints.append(f"{GREEN}a{RESET}ccept")
    if current != "rejected": hints.append(f"{RED}r{RESET}eject")
    if current != "pending":  hints.append(f"{YELLOW}p{RESET}end")
    hints.append(f"{DIM}s{RESET}kip")
    hints.append(f"{DIM}q{RESET}uit")
    prompt = "  → " + "  ".join(hints) + "  > "

    while True:
        try:
            choice = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "quit"
        if choice in ("a", "accept"):
            return "accepted"
        if choice in ("r", "reject"):
            return "rejected"
        if choice in ("p", "pend", "pending"):
            return "pending"
        if choice in ("s", "skip", ""):
            return "skip"
        if choice in ("q", "quit"):
            return "quit"
        print("  Unrecognized — try a / r / p / s / q")


class Abort(Exception):
    """Reviewer backed out of the wiring prompts."""


def ask_text(label, default=None):
    suffix = f" {DIM}[{default}]{RESET}" if default else ""
    while True:
        try:
            value = input(f"    {label}{suffix}  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise Abort
        if value:
            return value
        if default:
            return default
        print(f"    {DIM}(required){RESET}")


def ask_choice(label, options):
    for i, opt in enumerate(options, 1):
        print(f"    {DIM}[{i}]{RESET} {opt}")
    while True:
        try:
            raw = input(f"    {label}  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise Abort
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print(f"    {DIM}(enter 1-{len(options)}, or the value){RESET}")


def wire_accepted(p):
    """Add an accepted proposal to the gathering config.

    Returns a short description of what was written, or None if it was already
    wired. Raises Abort if the reviewer backs out — the caller then leaves the
    proposal's status alone, so "accepted" never means "approved but ignored".
    """
    if not wire.find_unwired(ROOT, [dict(p, status="accepted")]):
        return None

    v = wire.vocab(ROOT)
    value = p["value"]

    if p["kind"] == "source" and p.get("feed_url"):
        print(f"  {BOLD}Wiring into sources.yaml{RESET} {DIM}(has a feed){RESET}")
        name = ask_text("name", default=value)
        tier = ask_choice("tier", v["tiers"])
        entry_id = wire.next_id(ROOT, "sources.yaml", value)
        wire.wire_feed(ROOT, entry_id, name, p["feed_url"], tier)
        return f"sources.yaml  id: {entry_id}  tier: {tier}"

    if p["kind"] == "source":
        print(f"  {BOLD}Wiring into site_targets.yaml{RESET} {DIM}(no feed — site-scoped search){RESET}")
        name = ask_text("name", default=value)
        cadence = ask_choice("cadence", v["cadences"])
        entry_id = wire.next_id(ROOT, "site_targets.yaml", value)
        wire.wire_target(ROOT, entry_id, name, value.removeprefix("www."), cadence)
        return f"site_targets.yaml  id: {entry_id}  cadence: {cadence}"

    print(f"  {BOLD}Wiring into watchlist.yaml{RESET}")
    name = ask_text("name", default=value)
    kind = ask_choice("kind", v["kinds"])
    cadence = ask_choice("cadence", v["cadences"])
    entry_id = wire.next_id(ROOT, "watchlist.yaml", value)
    wire.wire_entity(ROOT, entry_id, name, kind, cadence)
    return f"watchlist.yaml  id: {entry_id}  kind: {kind}  cadence: {cadence}"


def run_check(proposals):
    """Report accepted proposals that never reached the gathering config."""
    unwired = wire.find_unwired(ROOT, proposals)
    if not unwired:
        print(f"{GREEN}All accepted proposals are wired into the config.{RESET}")
        return 0
    print(f"{RED}{len(unwired)} accepted proposal(s) not in the gathering config:{RESET}")
    for p in unwired:
        dest = "watchlist.yaml"
        if p["kind"] == "source":
            dest = "sources.yaml" if p.get("feed_url") else "site_targets.yaml"
        print(f"  {p['value']}  {DIM}({p['id']} -> {dest}){RESET}")
    print(f"\n{DIM}Re-accept with `review.py --id <id>` to wire one in.{RESET}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Review AICN proposals interactively.")
    parser.add_argument("--all", action="store_true", help="Include already-decided proposals")
    parser.add_argument("--id", dest="proposal_id", help="Review a single proposal by ID")
    parser.add_argument("--check", action="store_true",
                        help="Report accepted proposals missing from the config, then exit")
    args = parser.parse_args()

    data = load()
    proposals = data.get("proposals", [])

    if args.check:
        sys.exit(run_check(proposals))

    if args.proposal_id:
        targets = [p for p in proposals if p["id"] == args.proposal_id]
        if not targets:
            sys.exit(f"No proposal found with id: {args.proposal_id}")
    elif args.all:
        targets = proposals
    else:
        targets = [p for p in proposals if p["status"] == "pending"]

    if not targets:
        print("No proposals to review.")
        return

    changed = 0
    wired_count = 0
    by_id = {p["id"]: p for p in proposals}

    for i, p in enumerate(targets, 1):
        print_proposal(p, index=i, total=len(targets))
        if p["status"] == "accepted" and wire.find_unwired(ROOT, [p]):
            print(f"  {RED}Accepted but not in the config — nothing is gathered from it.{RESET}")
            print(f"  {DIM}Accept again to wire it in.{RESET}")
        decision = prompt_decision(p)

        if decision == "quit":
            break
        if decision == "skip":
            continue

        # Wire before recording the status, so "accepted" can never mean
        # "approved but never gathered from" — the bug this flow exists to fix.
        if decision == "accepted":
            try:
                wired = wire_accepted(p)
            except Abort:
                print(f"  {DIM}Wiring cancelled — status unchanged.{RESET}")
                continue
            except Exception as exc:
                print(f"  {RED}Wiring failed:{RESET} {exc}")
                print(f"  {DIM}Status unchanged; config not modified.{RESET}")
                continue
            if wired:
                print(f"  {GREEN}Wired{RESET} {DIM}{wired}{RESET}")
                wired_count += 1
            elif p["status"] == "accepted":
                print(f"  {DIM}Already wired into the config.{RESET}")

        if decision != p["status"]:
            by_id[p["id"]]["status"] = decision
            changed += 1
            label = {"accepted": GREEN + "Accepted" + RESET,
                     "rejected": RED + "Rejected" + RESET,
                     "pending":  YELLOW + "Reset to pending" + RESET}[decision]
            print(f"  {label}")

    if changed:
        data["proposals"] = list(by_id.values())
        save(data)
        print(f"\n{BOLD}Saved.{RESET} {changed} proposal(s) updated in data/proposals.json")
    if wired_count:
        print(f"{BOLD}Wired.{RESET} {wired_count} entr(y/ies) added to the gathering config")
    if changed or wired_count:
        print(f"{DIM}Don't forget to commit and push when ready.{RESET}")
    else:
        print(f"\n{DIM}No changes made.{RESET}")


if __name__ == "__main__":
    main()
