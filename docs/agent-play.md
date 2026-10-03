# Playing against an agent or a human

The goal is to let an agent load a deck and its playbook, make informed decisions,
and play a complete duel with another agent or a human. These assets support
that task; actual effects must still be adjudicated under an agreed rules profile.

## Before the duel

Agree on format, card pool, banlist, rules version, card text overrides, starting
LP/hand size, field layout, first-turn rules, single game or match, and start player.
Load each bundle from `decks/<format>/<deck-name>/`: `deck.ydk`, `deck.json`,
and `guide.md`; use the optional `README.md` for source notes. Validate both
decklists, including Side Deck Extra Deck cards. Snapshot each whole bundle into
`games/<format>/<game-id>/decks/<deck-name>/`, retaining its generic filenames,
and snapshot the rules into the game's records. Check each guide's JSON hash.

Choose who maintains the authoritative state and handles shuffles and rulings:
a game engine, a referee agent, or an agreed human. Use independently shuffled,
fixed deck orders and preserve them when saving/resuming. A player must not inspect
the opponent's private state. Agree on whether decklists are open information.

## Information and decisions

A playing agent receives its own hand and other information it is allowed to
know, plus the public board, public GYs/banishment, LP, deck/hand counts, and log.
Opponent face-down cards, private draws, and deck order remain unknown until
revealed by a rule or effect. Face-down banished cards remain private as applicable.
Separate a hypothesis about an unknown card from an observed fact.

Use the playbook to propose candidate lines; verify their requirements against
the actual state and full card text. Check costs, targets, material locations,
summon history, once-per-turn counters, locks, zone space, and phase/window.
Choose among legal candidates using survival, interaction, damage, resource gain,
and follow-up. Do not continue a canned combo after its assumptions change.

## Action and response protocol

For each action, state the phase/window, card and zone, intended effect, costs,
targets, and any material choices required at activation. Allow the opponent to
respond before advancing. Passing one response window does not waive future ones.
Human opponents can use ordinary card names; clarify an ambiguous action before
changing state. Agents should use exact names plus IDs and physical-copy identifiers.

Example declaration: "Main Phase 1: activate Branded Fusion. No cost or target.
Any response?" Fusion Material is normally chosen when this effect resolves,
not committed as an activation target. Apply the specific card's text each time.

Record each chain link in activation order and resolve in reverse order.
Distinguish costs from effects, activation negation from effect negation,
targeting from non-targeting selection, and destruction from negation.
Do not activate new effects while a chain is resolving. Collect resulting triggers
for the next legal window and order simultaneous effects under the selected rules.
Automatic passing is allowed only within an explicitly agreed response policy.

After resolution, update state before choosing another action. Check for summons,
trigger opportunities, delayed effects, and battle/End Phase procedures. Confirm
attack legality, damage calculation, and lethal against the known state.

## State and logs

Track physical cards and zones, original/current names/types/stats, face-up/down
status, materials, counters, attack history, proper summons, Normal Summon usage,
effect/activation counters, turn-wide locks, and lingering restrictions. Some
effects are per card instance; others share a limit across every copy of a name.
The JSON and Markdown do not themselves store this live state.

Use `templates/game.json`, `templates/game-log.md`, and `templates/state.json`
as starting points and add the counters/lingering effects needed for the game.
The shared templates are not a complete rules-engine state schema. A public log
must not expose hidden information; a shared repository should contain public
records during a live game, with private states held by the authorized referee
or respective player. Full records can be archived afterward by agreement.

## Errors, rulings, and ending the game

If an action is invalid, identify the failed requirement before applying it.
For disputed interactions, pause at the exact chain/window and consult the
agreed referee or ruling source. Avoid retroactively choosing costs/materials
with knowledge gained from an invalid resolution. Any rollback must be agreed
and recorded. Guides flag unresolved interactions instead of deciding them silently.

Record the result, relevant win condition, and post-game analysis. In a match,
sideboard only between games, preserve section sizes and legal copy limits,
and snapshot the next game's exact list. Update guides from observed games
without rewriting historical deck snapshots or claiming unsupported win rates.
