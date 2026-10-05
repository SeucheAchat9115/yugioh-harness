# Playing against an agent or a human

The goal is to let an agent load a deck and its playbook, make informed decisions,
and play a complete duel with another agent or a human. The LLM moderator
adjudicates effects, timing, legality, and battle under an agreed rules profile;
the harness persists its approved state changes. A full coded simulator is not
required.

## Before the duel

Agree on format, card pool, banlist, rules version, card text overrides, starting
LP/hand size, field layout, first-turn rules, single game or match, and start player.
Load each bundle from `decks/<format>/<deck-name>/`: `deck.ydk`, `deck.json`,
and `guide.md`; use the optional `README.md` for source notes. Validate known
decklists, including Side Deck Extra Deck cards. In self mode record the
human list as self-attested without requesting it. Snapshot each whole bundle into
`games/<format>/<game-id>/decks/<player>/<deck-name>/`, retaining its generic filenames,
and snapshot the rules into the game's records. Check each guide's JSON hash.

Use the harness for authoritative stored state and managed shuffles; assign the
LLM moderator to interpret rules and approve gameplay updates. Agree on a ruling
source or referee for uncertain interactions. Use independently shuffled,
fixed deck orders and preserve them when saving/resuming. Select [self or managed
mode](../agents/README.md) before providing hidden information. Self mode never
receives the human's hidden deck/hand; the human manages those privately. Managed mode loads the selected human bundle
for the orchestrator and coach, while keeping hidden information private from
the opponent child. Human display still hides agent cards unless agreed otherwise.

## Information and decisions

In self mode, a playing agent receives its own hand and permitted information,
plus the public board, public GYs/banishment, LP, deck/hand counts, and log.
Opponent face-down cards, private draws, and deck order remain unknown until
revealed by a rule or effect. Face-down banished cards remain private as applicable.
Separate a hypothesis about an unknown card from an observed fact.
In managed mode the orchestrator knows the human's state and coaches their choices.
The opponent child receives only legally revealed human information. The human
decides their own actions; never alter randomness or rulings to favor a player.

Use the playbook to propose candidate lines; verify their requirements against
the actual state and full card text. Check costs, targets, material locations,
summon history, once-per-turn counters, locks, zone space, and phase/window.
Choose among legal candidates using survival, interaction, damage, resource gain,
and follow-up. Do not continue a canned combo after its assumptions change.

## Action and response protocol

Follow [natural-language action recording](natural-language-actions.md): the human
speaks normally, and the moderator records confirmed decisions as guarded internal
changes. Keep the exact live journal private and export complete known hidden-state
transitions to the repository archive. Display only permitted state/narration.
Replay the private journal for recovery; see [game storage](game-storage.md).

Follow [duel experience](duel-experience.md) for every gameplay message: the fixed
state display, two recommended moves when available, free-text choices, verified
no-choice continuation, and complete private checkpoints. All saves are local.
Commit/publish game records only when explicitly requested; “save”, pause, and
game end do not authorize a commit.

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
Automatically progress through compulsory/pass-only windows after a complete
no-choice review, recording the reason and reporting intervening events. Stop at
the next actual human choice. Silence never passes an available option, and unknown
self hidden cards cannot prove no response. Uncertain rulings also stop progression.

After resolution, update state before choosing another action. Check for summons,
trigger opportunities, delayed effects, and battle/End Phase procedures. Confirm
attack legality, damage calculation, and lethal against the known state.

## State and logs

Track physical cards and zones, original/current names/types/stats, face-up/down
status, materials, counters, attack history, proper summons, Normal Summon usage,
effect/activation counters, turn-wide locks, and lingering restrictions. Some
effects are per card instance; others share a limit across every copy of a name.
Record this information in live state and action history; deck JSON and guides
do not track it automatically.

Use `game.json`, immutable rules/deck snapshots and the schema-4
`events.json` index and `events/*.json` archive described in [game storage](game-storage.md). It includes
known hidden hands/sets and all state transitions. Generate readable summaries
and states when needed instead of maintaining duplicate logs. During play,
player contexts/displays stay filtered; never give a player the archive directly.

Refresh private `checkpoint.json` after changes and save exact numbered decision
packets before asking. Preserve managed-mode hands/sets and both orders, costs, counters,
pending choices, rules, and exact snapshots. Verify on pause/resume. Self human
hidden state remains with the human; do not fabricate it or request it for a save.

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
