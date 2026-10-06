# Goat: April 2005 TCG

Profile ID `goat`; version `goat-2026-10-06`. Checked on **2026-10-06**.
Apply [shared basics](common.md) with the historical changes below.
This adopts GoatFormat.com's community standard under Konami's
[Time Wizard framework](https://www.yugioh-card.com/en/play/alternate_format_tournaments/time-wizard/):
historical pool, list, mechanics, and pre-errata text.

## Setup and pool

| Setting | Value |
| --- | --- |
| Starting LP / opening hand | 8000 / 5 |
| Starting player's first-turn draw / battle | Yes / no |
| Main / Fusion Deck | At least 40, no historical maximum / no historical maximum |
| Side Deck | Historically 0 or exactly 15; 0–15 only if agreed as a variant |
| Field | 5 Monster, 5 Spell/Trap, Field Zone; no Extra Monster/Pendulum Zones |
| Banlist | [April 1, 2005 Goat restrictions](banlists/goat-2005-04-01.json) |

Source: [Goat card pool and list](https://www.goatformat.com/cardpool.html).
Use premier-event legality as of **August 17, 2005**, including The Lost Millennium
and the listed legal promos. **Cybernetic Revolution and Exarion Universe are
excluded** ([community explanation](https://www.goatformat.com/home/cybernetic-revolution-crv-in-goat-format)).
Synchro, Xyz, Pendulum, and Link cards are outside the pool.
Reprints are usable with the historical text; the printing date alone is not the
card's legality date. Fusion copies still follow the combined three-copy limit.

## Historical changes

Community source: [Goat basic mechanics](https://www.goatformat.com/basics.html).
These concise reminders require the linked card rulings for exceptions:

- First player draws; Main/Fusion sizes are unlimited.
- One active Field Spell; opposing activation destroys it on resolution.
- Ignition priority follows trigger checks.
- Attack replays redeclare attacks, including attack costs and responses.
- Continuous Trap ignition-like effects require prior face-up activation.
- Historical verification applies; online omission needs agreement.
- Searches permit failure-to-find; Venus is an exception.
- Earlier trigger times precede later groups, unlike Edison's within-group ordering.
- Damage Step has six timings; ATK/DEF changes allow calculation, with one calculation chain.
- Matches require two wins; record overtime policy.
- Pending triggers survive movement, sometimes including Deck triggers.
- Failed Relinquished/Thousand-Eyes equips leave targets with their controller.
- Taking an opposing monster can permit a same-turn manual position change.
- Two zero-ATK Attack monsters destroy each other.
- LP costs leave positive LP; Chain Energy differs. Deck-out effects can activate.
- Voluntary infinite loops are illegal; involuntary loops use historical correction.
- Historical Union limits/protection apply.

Damage timings: start, before calculation, calculation part 1, calculation
part 2, after calculation, end. Flip effects wait until after calculation;
battle-destroyed monsters reach the GY at the end.

## Text, rulings, and archive discrepancy

Use [individual rulings](https://www.goatformat.com/indivrulings.html) and
[ruling notices](https://www.goatformat.com/rulingnotices), both community
references. Modern API descriptions are insufficient for pre-errata cards such as
Sinister Serpent, Sangan, Ring of Destruction, and Dark Magician of Chaos.
Record the applicable historical interpretation before using an affected card.

The official Time Wizard FAQ names the **April 2005 TCG** list but links a
[Konami archive labeled March 1, 2005](https://www.yugioh-card.com/en/downloads/alt_format/2005-03-01.pdf).
Our JSON cross-checks that archive against the community Goat pool. Sixth Sense,
Crush Card Virus, Exchange of the Spirit, and Marshmallon appear in the archive
but are outside this Goat pool. Their omission from playable restrictions does
not legalize them. The JSON preserves this discrepancy explicitly.

Agree single game or match, verification policy, and any deck-size/platform cap
before dealing. Any departure from this profile is a recorded custom variant.
