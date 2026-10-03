#!/usr/bin/env python3
"""Print deck evidence or audit a playbook's structure and exact-list coverage."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HEADINGS = (
    "Overview", "Card roles and usage", "Search, summon, and recovery map",
    "Synergies", "Combo lines", "Going first and going second",
    "Opponent-turn interaction", "Resource and timing ledger",
    "Sideboarding and matchup notes", "Agent piloting checklist",
    "Uncertainties and validation",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inventory", "check"))
    parser.add_argument("deck", type=Path)
    args = parser.parse_args()
    raw = args.deck.read_bytes()
    deck = json.loads(raw)
    counts = {section: Counter(deck[section]) for section in ("main", "extra", "side")}
    ids = set().union(*(counter.keys() for counter in counts.values()))
    if set(deck["cards"]) != {str(card_id) for card_id in ids}:
        raise SystemExit("Card record coverage differs from deck sections")
    if args.action == "inventory":
        print(f"{deck['name']} ({deck['id']}); counts={deck['counts']}")
        for card_id in sorted(ids):
            card = deck["cards"][str(card_id)]
            copies = "/".join(str(counts[section][card_id]) for section in counts)
            stats = {key: card[key] for key in ("race", "attribute", "level", "atk", "def", "scale", "linkval", "linkmarkers") if key in card}
            print(f"\n{card_id} | {card['name']} | M/E/S {copies} | {card['type']} | {stats}")
            print(card["desc"])
        return
    guide = args.deck.with_suffix(".md")
    text = guide.read_text()
    errors = []
    required = {
        "deck_id": deck["id"], "deck_json": args.deck.name,
        "ydk": args.deck.with_suffix(".ydk").name,
        "deck_json_sha256": hashlib.sha256(raw).hexdigest(),
    }
    for key, value in required.items():
        if not re.search(rf"^{key}: {re.escape(str(value))}$", text, re.M):
            errors.append(f"Missing or stale {key}")
    for key in ("format", "banlist", "review_status"):
        if not re.search(rf"^{key}: .+$", text, re.M):
            errors.append(f"Missing {key}")
    for heading in HEADINGS:
        if f"## {heading}\n" not in text:
            errors.append(f"Missing heading: {heading}")
    for card_id in sorted(ids):
        card = deck["cards"][str(card_id)]
        copies = "/".join(str(counts[section][card_id]) for section in counts)
        row = f"| {card_id} | {card['name']} | {copies} |"
        if row not in text:
            errors.append(f"Missing or incorrect inventory row for {card['name']}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"{guide}: structure, deck hash, and {len(ids)} card inventory rows verified.")
    print("Combo legality requires separate card-text/rulings review; this audit does not simulate play.")


if __name__ == "__main__":
    main()
