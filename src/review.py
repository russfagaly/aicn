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


def main():
    parser = argparse.ArgumentParser(description="Review AICN proposals interactively.")
    parser.add_argument("--all", action="store_true", help="Include already-decided proposals")
    parser.add_argument("--id", dest="proposal_id", help="Review a single proposal by ID")
    args = parser.parse_args()

    data = load()
    proposals = data.get("proposals", [])

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
    by_id = {p["id"]: p for p in proposals}

    for i, p in enumerate(targets, 1):
        print_proposal(p, index=i, total=len(targets))
        decision = prompt_decision(p)

        if decision == "quit":
            break
        if decision == "skip":
            continue

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
        print(f"{DIM}Don't forget to commit and push when ready.{RESET}")
    else:
        print(f"\n{DIM}No changes made.{RESET}")


if __name__ == "__main__":
    main()
