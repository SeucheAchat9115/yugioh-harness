---
name: ydk-to-json
description: Convert Yu-Gi-Oh! YDK exports into same-basename JSON files containing complete card records from the YGOPRODeck API, and save the results in this repository.
---

# YDK to JSON

Use this skill when importing or refreshing a `.ydk` deck with full card data.
Decklists must still come from Cardcluster or user-supplied Cardcluster exports.
YGOPRODeck supplies card metadata, not replacement decklists.

## Procedure

1. Read the repository's `AGENTS.md`. Locate the requested YDK files and preserve
   their bytes. Do not assume a format or infer legality from current API banlists.
2. Run the bundled converter from the repository root:

   ```sh
   python skills/ydk-to-json/scripts/convert.py --repo .
   ```

   This converts all `decks/**/*.ydk`. To select specific files, append their paths:

   ```sh
   python skills/ydk-to-json/scripts/convert.py --repo . decks/unassigned/dracotail.ydk
   ```

3. Fetch every distinct ID across Main, Extra, and Side Decks from
   `https://db.ygoprodeck.com/api/v7/cardinfo.php`, using `id` and `misc=yes`.
   The converter batches IDs, throttles requests, retries transient errors, and
   resolves alternate-art IDs through the response's `card_images` entries.
   Keep the complete returned card object, including unknown/new fields.
4. Require all IDs to resolve before replacing any output. A failed request,
   unknown ID, malformed YDK, or incomplete response must fail the conversion;
   never fabricate card data or publish a partially enriched deck.
5. Write a sibling JSON with exactly the YDK's basename: `dracotail.ydk` becomes
   `dracotail.json`; `branded-despia-v1.ydk` becomes `branded-despia-v1.json`.
   Preserve existing deck metadata. Resolve legacy filenames explicitly before
   conversion rather than creating competing manifests for the same deck.
6. Verify the SHA-256 against the original YDK, section order and copy counts,
   and coverage of every distinct ID in `cards`. Commit the skill, converter,
   and generated JSON files to the requested repository. Report the actual outcome.

If local network access is unavailable, use `.github/workflows/enrich-ydk.yml`.
It runs this same converter on GitHub Actions and commits successful conversions
back to the branch. It runs when YDKs or converter files change on `main`, and can
also be started manually. Inspect its run and resulting files before claiming success.
The workflow requires GitHub Actions to be enabled and `contents: write` permission.

## JSON format (schema version `1.0`)

The output is a UTF-8 JSON object. The same format applies to every game format.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | `"1.0"` for this enriched deck representation. |
| `id` | string | Stable deck/version ID; preserve an existing ID or use the YDK stem. |
| `name` | string | Existing deck name, or the YDK stem if unknown. |
| `format`, `banlist` | string/object/null | Existing format and banlist metadata; null when unknown. |
| `version` | integer | Existing deck version, default 1. Refreshing card data does not change the deck version. |
| `source` | object | Deck provenance, separate from card data provenance. Preserve existing fields and extract a Cardcluster URL/author from the header when available. |
| `ydk_file` | string | Sibling YDK filename, including `.ydk`. |
| `ydk_sha256` | string | Lowercase SHA-256 of the original YDK bytes. |
| `ydk_header` | array of strings | Original comment lines except section markers. |
| `counts` | object | Integer `main`, `extra`, and `side` counts, including duplicate copies. |
| `main`, `extra`, `side` | arrays of integers | Original YDK card IDs in original section order. Repeated IDs represent repeated copies. Leading zeroes in textual IDs are normalized numerically. |
| `cards` | object | One entry per distinct YDK ID, keyed by its decimal string. Each value is the **complete, unmodified card object** returned by the API. |
| `card_data_source` | object | `api`, `language: "en"`, `misc: true`, and UTC ISO-8601 `retrieved_at` for this fetch. |
| `legality_status` | string | Preserved metadata, default `"not_checked"`; card enrichment does not validate format legality. |

Additional existing metadata, including `status` and `changes_from_source`, is
preserved. Section arrays in this format use ordered IDs, rather than the counted
entries in the generic `templates/deck.json` import template.

Every ID in the three section arrays must have a corresponding `cards` entry.
An alternate-art ID can map to an API object with a different canonical `id`;
the requested ID must then occur in that object's `card_images`.

Card objects retain every API field that is returned: for example `id`, `name`,
`type`, `frameType`, `desc`, `race`, `archetype`, `ygoprodeck_url`, monster stats
(`atk`, `def`, `level`, `attribute`), Pendulum/Link details (`scale`, `linkval`,
`linkmarkers`), `banlist_info`, `card_sets`, `card_images`, `card_prices`, and
`misc_info`. Fields vary by card; do not add invented values for absent fields.
Image data is represented by the API's URLs; image binaries are not downloaded.
Prices and current card descriptions reflect the API retrieval time, not a
historical rules snapshot.

To access a card, use `deck["cards"][str(deck["main"][0])]`. To count copies,
count occurrences of an ID in each section array.
