# Modern TCG Advanced

Profile ID `tcg`; version `tcg-2026-10-06`. Checked on **2026-10-06**.
Use [shared basics](common.md), the official references below, and current English
TCG card text. This profile covers the physical TCG Advanced format.

## Setup

| Setting | Value |
| --- | --- |
| Starting LP / opening hand | 8000 / 5 |
| Starting player's first-turn draw / battle | No / no |
| Main / Extra / Side Deck | 40–60 / 0–15 / 0–15 |
| Copy limits | 3 normally; dated list overrides, across all decks combined |
| Field | 5 Main Monster, 5 Spell/Trap, Field Zone, 2 shared Extra Monster Zones |
| Pendulum Zones | Leftmost/rightmost Spell/Trap Zones while used as Pendulum Zones |
| Banlist | [TCG Advanced, 2026-09-21](banlists/tcg-2026-09-21.json) |

The first player normally uses one Extra Monster Zone; occupying both requires
the applicable Extra Link rules. Fusion/Synchro/Xyz Summons from the face-down
Extra Deck can use a Main Monster Zone or an available Extra Monster Zone.
Link Monsters and face-up Pendulum Monsters summoned from the Extra Deck need
an Extra Monster Zone or a Main Monster Zone pointed to by a Link Monster.

## Current clarifications

Source: [Konami 2021 rules update](https://www.yugioh-card.com/en/play/2021_rules_update/).
Apply this supplement when it conflicts with the older printed rulebook:

- A pending monster trigger cannot activate if its location changed before
  its activation opportunity.
- Successfully summoned monsters count for the listed turn-wide summon
  restrictions; negated summons do not count for those restrictions.
- Trap Monsters remaining Traps do not also block a Spell/Trap Zone.
- Returning a monster to either Deck, or making it Xyz Material, does not
  activate its leaves-the-field effect.

Ignition effects have no historical summon-response priority. Use the fast-effect
procedure in the shared reference, including trigger checks before responses.
Read costs, targets, conditions, and conjunctions using
[Konami's PSCT guidance](https://www.yugioh-card.com/en/play/psct/).

The [official Damage Step chart](https://www.yugioh-card.com/eu/play/damage-step-rules/)
uses five timings: start, before calculation, calculation, after calculation, end.
Flip a face-down target before calculation; its Flip trigger waits until after
calculation. Apply battle damage during calculation and send battle-destroyed
monsters to the GY at the end. Check activation eligibility separately from timing.

## Legality and versioning

The linked list was the latest official TCG list verified on the check date.
Mind Master and Elder Entity Norden stayed Forbidden until **2026-09-28**;
the JSON records the September 21–27 exception. Verify later official updates
before a new current-format game; retain the chosen date for resumption.
Card availability is regional and separate from copy restrictions. A card not
listed is not automatically released or tournament legal. Do not apply OCG,
Master Duel, Traditional, Speed Duel, Rush Duel, or Genesys lists to this profile.

Agree single game or match and any timer before setup. Sideboard only between
games; preserve each deck's size. Tournament time/penalty procedures come from
the event's current policy, not an implicit harness timer.

## Official references

- [Rulebook download page](https://www.yugioh-card.com/en/rulebook/) and
  [English v10 PDF](https://www.yugioh-card.com/en/downloads/rulebook/SD_RuleBook_EN_10.pdf).
- [Advanced rules and fast-effect timing](https://www.yugioh-card.com/en/play/advanced-rules/).
- [English TCG card database](https://www.db.yugioh-card.com/yugiohdb/card_search.action?request_locale=en).
- [Live list landing page](https://www.yugioh-card.com/en/limited/) and
  [dated September 21, 2026 list](https://www.yugioh-card.com/en/limited/list_2026-09-21/).
- [Organized-play policy index](https://www.yugioh-card.com/en/events/organizedplay/).
