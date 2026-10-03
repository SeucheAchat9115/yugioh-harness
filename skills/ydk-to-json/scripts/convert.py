#!/usr/bin/env python3
"""Enrich YDK exports with complete YGOPRODeck API card records (stdlib only)."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
SECTIONS = ("main", "extra", "side")


def parse_ydk(path):
    raw = path.read_bytes()
    sections = {key: [] for key in SECTIONS}
    header, seen, current = [], set(), None
    markers = {"#main": "main", "#extra": "extra", "!side": "side"}
    for number, original in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        line = original.strip()
        if not line:
            continue
        if line in markers:
            current = markers[line]
            if current in seen:
                raise ValueError(f"{path}:{number}: duplicate {current} section")
            seen.add(current)
        elif line.startswith("#"):
            header.append(original)
        elif re.fullmatch(r"[0-9]+", line) and int(line) > 0 and current:
            sections[current].append(int(line))
        else:
            raise ValueError(f"{path}:{number}: invalid card ID or section")
    if not sections["main"]:
        raise ValueError(f"{path}: empty or missing Main Deck")
    return raw, sections, header


def request_cards(ids):
    url = API + "?" + urlencode({"id": ",".join(map(str, ids)), "misc": "yes"})
    for attempt in range(4):
        time.sleep(0.5)  # At most two requests per second, including retries.
        try:
            req = Request(url, headers={"User-Agent": "agentic-yugioh-ydk-to-json/1.0"})
            with urlopen(req, timeout=45) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError(f"API returned no card data for IDs {ids}: {payload}")
            return payload["data"]
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def match_records(ids, records):
    matched = {}
    wanted = set(ids)
    for card in records:
        if (not isinstance(card, dict) or not isinstance(card.get("id"), int)
                or not card.get("name") or not isinstance(card.get("desc"), str)
                or not card.get("type")):
            raise ValueError("API returned a malformed card object")
        aliases = {card["id"]}
        aliases.update(img["id"] for img in card.get("card_images", [])
                       if isinstance(img, dict) and isinstance(img.get("id"), int))
        for card_id in aliases & wanted:
            if card_id in matched and matched[card_id] != card:
                raise ValueError(f"Conflicting API records for ID {card_id}")
            matched[card_id] = card
    return matched


def fetch_all(ids):
    cards = {}
    ids = sorted(set(ids))
    for offset in range(0, len(ids), 40):
        batch = ids[offset:offset + 40]
        try:
            cards.update(match_records(batch, request_cards(batch)))
        except HTTPError as exc:
            if exc.code not in (400, 404):
                raise
            # Isolate invalid IDs, or services that reject multi-ID queries.
        for missing in (card_id for card_id in batch if card_id not in cards):
            records = request_cards([missing])
            match = match_records([missing], records)
            if missing not in match:
                raise ValueError(f"API did not resolve YDK ID {missing}")
            cards.update(match)
    return cards


def build_deck(path, parsed, cards, retrieved_at):
    raw, sections, header = parsed
    output = path.with_suffix(".json")
    deck = json.loads(output.read_text()) if output.exists() else {}
    if not isinstance(deck, dict):
        raise ValueError(f"{output}: expected metadata object")
    deck.setdefault("id", path.stem)
    deck.setdefault("name", path.stem)
    deck.setdefault("format", None)
    deck.setdefault("banlist", None)
    deck.setdefault("version", 1)
    deck.setdefault("legality_status", "not_checked")
    source = deck.setdefault("source", {})
    if not isinstance(source, dict):
        raise ValueError(f"{output}: source must be an object")
    for line in header:
        url = re.search(r"https://cardcluster\.com/deck/[A-Za-z0-9]+", line)
        if url:
            source.setdefault("url", url.group())
        author = re.search(r"#created by (.*?) - https://cardcluster\.com/", line)
        if author:
            source.setdefault("author", author.group(1))
    unique = sorted({card_id for values in sections.values() for card_id in values})
    if any(card_id not in cards for card_id in unique):
        raise ValueError(f"{path}: incomplete card coverage")
    deck.update({
        "schema_version": "1.0",
        "ydk_file": path.name,
        "ydk_sha256": hashlib.sha256(raw).hexdigest(),
        "ydk_header": header,
        "counts": {key: len(values) for key, values in sections.items()},
        **sections,
        "cards": {str(card_id): cards[card_id] for card_id in unique},
        "card_data_source": {"api": API, "language": "en", "misc": True,
                             "retrieved_at": retrieved_at},
    })
    return output, json.dumps(deck, ensure_ascii=False, indent=2) + "\n"


def convert(paths):
    parsed = [(path, parse_ydk(path)) for path in paths]
    ids = {card_id for _, (_, sections, _) in parsed
           for values in sections.values() for card_id in values}
    cards = fetch_all(ids)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # Fetch and validate ALL decks before writing any JSON.
    outputs = [build_deck(path, data, cards, retrieved_at) for path, data in parsed]
    for output, content in outputs:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        try:
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
        print(f"Saved {output} ({len(json.loads(content)['cards'])} distinct cards)")
    print(f"Resolved {len(cards)} distinct IDs across {len(outputs)} decks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("paths", type=Path, nargs="*")
    args = parser.parse_args()
    repo = args.repo.resolve()
    paths = sorted(set(path.resolve() for path in args.paths)) if args.paths else sorted((repo / "decks").rglob("*.ydk"))
    if not paths:
        parser.error("No YDK files found")
    for path in paths:
        if path.suffix.lower() != ".ydk" or not path.is_relative_to(repo):
            parser.error(f"Expected a .ydk file inside the repository: {path}")
    convert(paths)


if __name__ == "__main__":
    main()
