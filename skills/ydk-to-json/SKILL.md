---
name: ydk-to-json
description: Convert YDK exports into generic `deck.json` gameplay files in named deck folders using YGOPRODeck card data, and save the results in the repository.
---

# YDK to gameplay JSON

Use this skill to import or refresh YDK decks for playing Yu-Gi-Oh!.
Read `AGENTS.md` first. Decklists come from Cardcluster or user-supplied
Cardcluster exports; YGOPRODeck provides card information.

## Procedure

1. Preserve the original YDK bytes and locate all IDs in Main, Extra, and Side.
2. Fetch every distinct ID from `https://db.ygoprodeck.com/api/v7/cardinfo.php`
   using the bundled converter:

   ```sh
   python skills/ydk-to-json/scripts/convert.py --repo .
   ```

   Append paths such as `decks/unassigned/dracotail/deck.ydk` to select specific
   decks. Default discovery reads only `decks/**/deck.ydk`. The converter batches and throttles
   requests, retries transient failures, and resolves alternate artwork IDs via
   the API's `card_images` before discarding artwork metadata.
3. Keep only the gameplay fields listed below. Never truncate card text. Require
   names, full descriptions, card types, races, and applicable monster stats.
   Missing card records or required gameplay fields fail the conversion before
   any outputs are replaced; never invent values.
4. Store each deck under `decks/<format>/<deck-name>/`, with lowercase hyphenated
   folder names. Read `deck.ydk` and write `deck.json` in that same folder.
   Its playbook is `guide.md`; optional provenance notes belong in `README.md`.
   Preserve deck identity, format, banlist, and version.
   Remove all old non-gameplay metadata, including unknown fields.
5. Check exact section order, duplicates, copy counts, and coverage of all IDs.
   Confirm the YDK files remain unchanged. Commit the skill and generated JSONs.

To filter card records already fetched into the same folders' `deck.json` files without another
network request, use:

```sh
python skills/ydk-to-json/scripts/convert.py --repo . --from-existing
```

This reuses the saved data; it does not refresh it. For network access through
GitHub Actions, use `.github/workflows/enrich-ydk.yml`. It runs on changes to
YDKs, this skill, or the workflow on `main`, and supports manual runs. It tests
and runs this same converter, then commits successful outputs back to the branch.
Confirm the run and generated files succeeded before reporting completion.

## JSON format: schema version `2.0`

UTF-8 JSON object containing only the following top-level fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | `"2.0"`, the gameplay-only representation. |
| `id`, `name` | strings | Stable deck/version identifier and readable deck name. |
| `format`, `banlist` | string/object/null | Selected play format and banlist; null if not assigned. |
| `version` | integer | Deck version; a card-data refresh does not change it. |
| `counts` | object | Integer `main`, `extra`, and `side` copy counts. |
| `main`, `extra`, `side` | arrays of integers | Original ordered YDK IDs, with one entry per copy. Repeated IDs are preserved. |
| `cards` | object | A gameplay card record for each distinct YDK ID, keyed by its decimal string. |

`cards` records contain only these allowlisted fields, when provided by the API:

| Field | Meaning |
| --- | --- |
| `id` | Canonical card ID. The lookup key remains the original YDK ID for alternate artwork. |
| `name` | Full English card name. |
| `type`, `frameType` | Card classification, including Effect, Normal, Fusion, Synchro, Xyz, Pendulum, Link, Spell, or Trap. |
| `desc` | Complete card text, including effects, summoning conditions/materials, restrictions, and any combined Pendulum text. |
| `race` | Monster type (e.g. Dragon) or Spell/Trap subtype (e.g. Quick-Play, Continuous). |
| `archetype` | API archetype classification, when available; determine actual name-based membership from card names/text. |
| `atk`, `def` | Printed ATK and DEF. Preserve `-1` for unknown/variable values; do not convert it to zero. Link monsters have no DEF. |
| `level` | Monster Level, or Xyz Rank as represented by the API. Link monsters use `linkval` instead. |
| `attribute` | Monster Attribute. |
| `scale` | Pendulum Scale. |
| `pend_desc`, `monster_desc` | Separate Pendulum and monster texts if the API provides them. Always retain full `desc` as well. |
| `linkval`, `linkmarkers` | Link Rating and Link Arrow directions. |

Do not invent fields for cards to which they do not apply. Monsters require ATK,
Attribute, and either DEF/Level or Link Rating/Arrows. Pendulum monsters require
Scale. All cards require ID, name, type, race, and full text.

Do not include card prices, sets/printings, images or image URLs, release dates,
API URLs, API timestamps, `misc_info`, current `banlist_info`, import headers,
source metadata, file hashes, status notes, or arbitrary API fields in the JSON.
Cardcluster provenance stays in the original YDK header and deck README.
Game rules and saved game states remain separate from deck JSONs.

Every ID in the three section arrays must resolve in `cards`. Access a card with
`deck["cards"][str(deck["main"][0])]`; count occurrences to find copy counts.
The current API card text is not a historical rules snapshot. Historical or
custom formats require their own rules and any card-text overrides for play.
