# Rules for our Edison duels

- Edison uses the TCG card pool from SJC Edison in April 2010 and
  the Forbidden & Limited List dated March 1, 2010.
- Both players start with 8000 LP and five cards in hand.
- The starting player also draws a card on their first turn.
- The starting player has no Battle Phase on their first turn.
- Main Deck: 40–60 cards; Extra Deck and Side Deck: up to 15 cards each.
- Historical card text and rules apply, including ignition effect priority.
  Look up unclear interactions before resolving them.
- No sideboarding in a single game; in a match, sideboard between games.

Before playing, assign decks to players and decide who starts. Preserve random
shuffles, draws, and mills in the saved game state; do not reroll an outcome
because it is unfavorable.

## Source status

Check the exact format legality of imported decklists during import.
Format rules reference: https://www.edisonformat.com/

## Imported deck text differences

The Edison bundles retain current API descriptions in `deck.json`. Agree on the
historical interpretation and include it in the game's rules snapshot:

- Goyo Guardian accepts a generic Tuner; the later EARTH requirement does not apply.
- Brionac can return targets from either field and has no once-per-turn limit.
- Brain Control can target face-up monsters without the later summonability restriction.
- Ryko's historical destruction targets; use historical destruction/mill sequencing.

See [functional errata](https://www.edisonformat.com/functional-errata.html).
Celestia's mill is an activation cost; Beckoning Light discards during resolution.
Lumina needs an eligible GY target before paying its discard. Consult the
[individual A–C rulings](https://www.edisonformat.com/rulings/individual-rulings-a-c)
and [L–O rulings](https://www.edisonformat.com/rulings/individual-rulings-l-o).
These notes address important included cards, not every possible historical ruling.
