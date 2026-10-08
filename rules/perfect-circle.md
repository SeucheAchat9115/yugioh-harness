# Perfect Circle: September 2007 TCG list, Orlando snapshot

Profile ID `perfect-circle`; version `perfect-circle-2026-10-08`.
Sources checked on **2026-10-08**. This profile adopts the community's
**SJC Orlando, January 26, 2008** reference point, not every date in 2007.
[Community scope and historical rulings](https://perfectcircleformat.altervista.org/perfect-circle-format-important-rulings/)
and [Format Library](https://www.formatlibrary.com/formats/perfect-circle)
define the reference. Record deviations as a custom variant.

Read [shared basics](common.md) with these overrides. These are sourced reference
notes for an LLM moderator, not an effect engine or certification of any replay.

## Setup and eligible cards

| Setting | Value |
| --- | --- |
| Starting LP / opening hand | 8000 / 5 |
| Starting player's first-turn draw / battle | Yes / no |
| Main Deck | At least 40; no historical maximum |
| Fusion Deck | Fusion cards only; no historical size maximum |
| Side Deck | Absent or exactly 15; maintain its size between games |
| Field | 5 Monster Zones, 5 Spell/Trap Zones, Field Zone; no Extra Monster or Pendulum Zones |
| Banlist | [September 1, 2007 restrictions](banlists/perfect-circle-2007-09-01.json) |
| Match | Best of three; loser of the prior game chooses who starts next |

Sources: [archived UDE rulebook v6.02](https://web.archive.org/web/20080913113309if_/http://entertainment.upperdeck.com:80/yugioh/en/gameplay/rulebook/rulebook_v06_EN.pdf)
and [January 2008 basic FAQ](https://web.archive.org/web/20080123101617/http://entertainment.upperdeck.com/yugioh/en/gameplay/faqs/basicgameplay/default.aspx).
The PDF capture is September 2008; it supplies the v6.02 baseline, not proof of
every ruling at Orlando. Date-specific rulings below take precedence.

Check eligibility against the community's [explicit card pool](https://perfectcircleformat.altervista.org/perfect-circle-format-cardpool/).
A release date alone does not establish event eligibility. Synchro, Xyz,
Pendulum and Link mechanics are outside this profile. A runtime's generic
`extra_deck` slot represents the historical Fusion Deck here. Its default
15-card capacity is not a historical rule: record a platform cap as a variant.
Likewise do not apply modern 60-card Main or 0–15 Side limits silently.

The local banlist uses the community TCG pool. A historical list mirror adds
Temple of the Kings, Sixth Sense, Dandylion and Gorz; they are not in this
community's listed pool. Their omission never makes them playable. See JSON
notes for the preserved restriction differences. OCG needs a separate profile.

## Timing and response windows

A successful summon can retain ignition-effect priority, subject to trigger
checks and the available response window. That does not permit chaining an
ignition effect or skipping responses after a resolving chain.
[Community interpretation](https://perfectcircleformat.altervista.org/perfect-circle-format-important-rulings/)
and the [January 17, 2008 UDE judge ruling](https://web.archive.org/web/20080131133124/http://entertainment.upperdeck.com/community/forums/thread/989781.aspx)
are the references. The latter explicitly permits D.D. Crow to banish Malicious
after Destiny Draw resolves, before Malicious's ignition effect activates.

Do not apply Goat's priority procedure wholesale. Offer the actual trigger and
fast-effect windows before continuing. Successful summons, negated summons and
summons inside chain resolution are different situations. A player's "prio"
message is an intention, not authority to execute an illegal effect.

Attack replays reselect a target or stop the attack; they do not start a new
attack or charge attack costs again. The monster has still attacked and cannot
be saved for a later attack that turn. Source: [UDE basic FAQ](https://web.archive.org/web/20080123101617/http://entertainment.upperdeck.com/yugioh/en/gameplay/faqs/basicgameplay/default.aspx),
revised May 2006. For attack-response eligibility at a replay, consult the
[community ruling notes](https://perfectcircleformat.altervista.org/perfect-circle-format-important-rulings/)
and their archival evidence before adjudicating; do not assume modern timing.

Only one Field Spell can be active across both players. Apply historical
replacement/destruction timing rather than modern coexistence. Continuous Trap
activation and its reusable activated effect require separate chains: the Trap
must already be face-up before the chain in which its effect is used. Consult the [January 2008 advanced FAQ](https://web.archive.org/web/20080123120041/http://entertainment.upperdeck.com/yugioh/en/gameplay/faqs/advancedgameplay/default.aspx).
Damage Step eligibility and optional "when" triggers need card-specific checks.

## Historical card text and replay-relevant rulings

Use pre-errata text applicable to this snapshot. Current API descriptions remain
imported reference data; record a sourced override before an affected action.
Do not overwrite a previously played game's deck or rules snapshots.

The [January 26, 2008 UDE D–E card FAQ](https://web.archive.org/web/20080126154656/http://entertainment.upperdeck.com/yugioh/en/gameplay/faqs/cardfaqs/default.aspx?first=D&last=E)
confirms these Dark Magician of Chaos rulings:

- Spell recovery is an optional summon-trigger effect, targeting a GY Spell at
  activation, rather than the modern End Phase recovery. Reasoning can trigger it.
- A summon that is not the last event in a resolving chain can miss timing.
- Returning the face-up monster to hand banishes it instead. A face-down copy
  destroyed on the field is not banished by that replacement.
- Temporary banishment by Interdimensional Matter Transporter permits its return.

The [January 25, 2008 UDE A–C card FAQ](https://web.archive.org/web/20080125033119/http://entertainment.upperdeck.com/yugioh/en/gameplay/faqs/cardfaqs/default.aspx?first=A&last=C)
confirms:

- Breaker's on-summon counter placement starts a chain. Its Spell Speed 1
  counter-removal effect cannot chain to that placement or another activation;
  removing the counter is a cost.
- Brain Control cannot activate with five occupied Monster Zones. Flipping its
  controlled monster face-down does not avoid returning control in the End Phase.

Brain Control's historical target text and Disc Commander's pre-errata effect
need their own agreed text overrides; the selected modern catalog does not
establish them. This profile is not a complete historical catalog for every card.

## Rulings requiring explicit adjudication

The community notes have updated failure-to-find and Plasma/Relinquished
interpretations, including older statements alongside corrections. For these
interactions, resolve the applicable FAQ/archive evidence and store the agreed
interpretation before execution. Do not turn a broad community claim into
permission for every search. See [ruling research process](https://perfectcircleformat.altervista.org/process-behind-which-rulings-to-apply/).

For the supplied replay, additionally review Reasoning/Monster Gate summon
eligibility, Plasma's negation/equip behavior, Scapegoat restrictions, Dimension
Fusion costs/space and return effects. Recorded operations are evidence; they
are not independent proof that a legal response window or resolution occurred.

## Use in the harness and benchmark

1. Agree on this profile, the exact card pool/list and any platform deviations.
2. Review decks and affected historical card text. Preserve unknown information;
   a generic array of runtime deck IDs is not a named decklist.
3. Assemble `rules_text` from shared basics, this complete profile, its dated JSON
   and agreed text/ruling overrides. `duel_start` saves that material immutably.
4. Record profile ID/version and snapshot hashes. Resume from saved material,
   not the current contents of these files or linked websites.
5. Send players only permitted rules and contexts. The moderator reviews legality
   and records journaled actions; an independent benchmark grader assesses them.

The benchmark should pin profile, banlist, resolved card-text and complete rules
snapshot hashes separately. Having these documents does not approve replay
checkpoints, decision boundaries or legality grades.
