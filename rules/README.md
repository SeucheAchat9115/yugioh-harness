# Format profiles

Use these sourced reference summaries and local banlist data:

| Profile | Rules / text policy | Banlist |
| --- | --- | --- |
| [Modern TCG Advanced](tcg.md) | Current TCG rules, official 2021 supplement, current text | 2026-09-21; verified 2026-10-06 |
| [Edison](edison.md) | April 2010 mechanics and historical text/rulings | 2010-03-01 |
| [Goat](goat.md) | Community August 2005 pool and historical mechanics/text | 2005-04-01 TCG |

[Shared basics](common.md) apply with the selected profile's overrides.
[Banlist JSONs and schema](banlists/README.md) contain the copy restrictions,
source authority, check dates, and documented archive discrepancies.
Official rulebooks and supplements are linked at Konami; local summaries are
original reference notes, not replacement editions of those documents.

Konami's [Time Wizard FAQ](https://www.yugioh-card.com/en/play/alternate_format_tournaments/time-wizard/)
provides the official framework for historical rules and pre-errata text.
EdisonFormat.com and GoatFormat.com supply community historical interpretations;
they are not official Konami ruling publications. Time Travel instead applies
current mechanics/text to an older pool, so it is a different agreed profile.

Create `rules/<format>.md` for other formats. Shared templates do not select a
format or load/enforce profiles automatically; the LLM moderator applies them.

Before playing, record:

- Format ID, card pool, region or platform, and banlist date or version.
- Applicable rule version, card texts, and historical rulings where relevant.
- Starting LP, opening hand size, and the starting player's draw and battle rules.
- Main, Extra, and Side Deck limits and any additional construction restrictions.
- Field layout, including Extra Monster Zones and Pendulum Zones when applicable.
- Single-game or match structure, sideboarding rules, and any custom rules.
- Rules sources and how unclear interactions will be resolved.

## Orchestrator setup and resumption

1. Read the selected profile, shared basics, and its dated banlist JSON. For new
   modern games verify the live official list when network access is available;
   otherwise disclose the stored check date and agree on that dated list.
2. Check managed decks against both the list and eligible card pool. Self mode
   keeps the human deck hidden; obtain their format/count confirmation and verify
   revealed cards as play proceeds. Do not claim full hidden-deck validation.
3. Record profile ID/version, exact banlist date, explicit configuration settings,
   and any deviations. Goat's historical unlimited Main/Fusion sizes and 0-or-15
   Side Deck differ from current limits; do not silently apply a platform cap.
4. Assemble `rules_text` internally from shared basics, the complete selected
   profile and banlist JSON, plus agreed historical card-text/ruling overrides,
   variant/match settings, and any supplemental rules needed for that game.
   Supply this text to `duel_start` so its existing immutable rules snapshot
   retains the actual local material, not just mutable links/file paths.
5. On resume use saved rules/deck snapshots, never today's profile/list instead.
   Keep player contexts filtered; research an uncertain interaction before
   adjudication, recording the chosen ruling/source locally.

The runtime does not fetch linked PDFs, parse these banlists, or certify deck
legality. The orchestrator reads the references and reviews legality. It also
operates all setup tools; the user does not need to assemble JSON or run commands.
