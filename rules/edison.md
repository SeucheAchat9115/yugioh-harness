# Edison: March 2010 TCG

Profile ID `edison`; version `edison-2026-10-06`. Checked on **2026-10-06**.
Apply [shared basics](common.md) with the historical changes below.
The [official Time Wizard framework](https://www.yugioh-card.com/en/play/alternate_format_tournaments/time-wizard/)
uses historical pool, list, rules, and pre-errata text. Detailed Edison ruling
references below are community-maintained, not Konami publications.

## Setup

- Edison uses the TCG card pool from SJC Edison in April 2010 and
  the Forbidden & Limited List dated March 1, 2010.
- Both players start with 8000 LP and five cards in hand.
- The starting player also draws a card on their first turn.
- The starting player has no Battle Phase on their first turn.
- Main Deck: 40–60 cards; Extra Deck and Side Deck: up to 15 cards each.
- Historical card text and rules apply, including ignition effect priority.
  Look up unclear interactions before resolving them.
- No sideboarding in a single game; in a match, sideboard between games.
- Field: five Monster Zones, five Spell/Trap Zones, and a Field Zone per player;
  no Extra Monster Zones or Pendulum Zones. Extra Deck uses Fusion/Synchro cards.
- Dated restrictions: [March 1, 2010 JSON](banlists/tcg-2010-03-01.json), transcribed
  from the [Konami archive](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf).

Before playing, assign decks to players and decide who starts. Preserve random
shuffles, draws, and mills in the saved game state; do not reroll an outcome
because it is unfavorable.

## Historical changes

Community source: [Edison rule differences](https://www.edisonformat.com/edison-rule-differences.html).

- First player draws. One active Field Spell; successful opposing activation
  destroys it on resolution. Replacing your own destroys it immediately.
- Original Union limits/protection apply.
- Phase-dependent mandatory triggers retry negated activations, not negated effects.
- Trap Monsters block both Monster and Spell/Trap Zones; negation can revert them.
- Ignition priority applies after a successful summon only if triggers have not
  started a chain. It never chains an ignition effect to a trigger.
- Trigger groups follow turn-player mandatory, opponent mandatory, turn-player
  optional, opponent optional. Within each group, earlier trigger times precede later ones.
- Damage Step has seven timings: start, flip, before calculation, calculation,
  after calculation, resolve effects, end. Flip effects activate in resolve effects;
  battle-destroyed monsters reach the GY at end. Check historical activation eligibility.
- Pending triggers can survive movement; card-specific Deck exceptions exist.
- LP costs must leave positive LP.
- Hand-limit discard is final; optional triggers cannot activate. Mandatory triggers
  allow only historical negation/counter-trap response exceptions.
- Voluntary infinite loops are illegal; involuntary loops use historical correction.

## Card pool and sources

Check the exact format legality of imported decklists during import.
Use the [legal sets](https://www.edisonformat.com/legal-sets.html) and
[card pool](https://www.edisonformat.com/card-pool.html), not every card with a
printing date before April 2010. Duel Terminal-only cards need a tournament-legal
release; [Konami's Hidden Arsenal 2 page](https://www.yugioh-card.com/en/products/past_products/ha02/)
dates that set to July 20, 2010. The full official archive includes out-of-pool
Temple of the Kings, Sixth Sense, and Dewloren; community lists omit them.
Shining Darkness is outside this profile. Consult the
[rules index](https://www.edisonformat.com/rules.html) for advanced/card rulings.

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
