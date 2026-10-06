# Dated copy restrictions

These are local reference data for the LLM moderator, not an automatic runtime
legality validator. A banlist cannot establish release/card-pool legality.

| File | List | Forbidden / Limited / Semi-Limited |
| --- | --- | --- |
| [tcg-2026-09-21.json](tcg-2026-09-21.json) | Konami TCG Advanced; verified 2026-10-06 | 122 / 95 / 8 |
| [tcg-2010-03-01.json](tcg-2010-03-01.json) | Full Konami archive, used with Edison pool | 45 / 70 / 20 |
| [goat-2005-04-01.json](goat-2005-04-01.json) | Community Goat restrictions, cross-checked against Konami archive | 17 / 41 / 15 |

## JSON format, schema 1.0

- `format`, `region`, `effective_date`, `verified_on`: list identity, TCG scope,
  effective date, and last source verification. Verification is not a future guarantee.
- `default_copy_limit`, `copy_limits`, `copy_limit_scope`: normally three copies;
  Forbidden/Limited/Semi-Limited mean zero/one/two, across Main, Extra/Fusion,
  and Side combined. Apply card-name identity rules too.
- `forbidden`, `limited`, `semi_limited`: complete sorted arrays for the stated
  list/pool scope. Names retain uppercase English spelling; compare without case
  sensitivity, preserving punctuation and symbols. Do not title-case acronyms.
- `sources`: URLs and authority labels. Community references are labeled explicitly.
- `notes`: scope, source discrepancies, and restrictions that the arrays cannot convey.
- Optional `date_overrides`: inclusive `from`/`through`, `status`, and `cards`.
  Apply matching overrides before normal/default limits. The 2026 list retains
  Mind Master and Elder Entity Norden as Forbidden until September 28.
- Optional `archive_entries_outside_card_pool`: restrictions printed in the
  official archive but omitted by the selected historical community pool.
  Those cards are **unavailable**, not unlimited.

The Edison archive includes Temple of the Kings, Sixth Sense, and Dewloren; the
community list excludes them from its pool. The Goat archive's March heading
differs from Konami's April TCG FAQ reference and additionally includes four
out-of-pool cards. See the profile/JSON notes rather than silently changing dates
or treating missing entries as permission to play a card.

When updating modern restrictions, add a new dated file after checking the official
TCG landing page, update the profile/check date, and compare every status and count.
Do not overwrite an older list or mutate saved local rules snapshots. Traditional
and other platforms need separately agreed profiles; these arrays describe Advanced.
