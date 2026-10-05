# Duel decisions, local saves, and continuation

Apply these rules in both modes to every gameplay declaration, question,
clarification, correction, and pause/resume update. Repo development discussions
do not require a duel display.

## Local saves and commits

During play, keep the omniscient replay archive under `games/<format>/<id>` and
live runtime/checkpoint files outside the repository. Follow
[game storage](game-storage.md): a schema-4 `events.json` index plus individual `events/*.json` records preserve hidden hands,
set identities and transitions. Shuffled queues stay in the private checkpoint.
Player contexts and outward displays remain filtered.

Do not stage, commit, push, create a PR, or call GitHub write tools automatically.
Only an explicit publication request authorizes uploading the requested archive
and snapshots. “Save”, pause and game end authorize local updates only. Exclude
raw runtime/checkpoint/workflow files and unrelated game/code changes.

## Fixed display: decision-v1

Use `harness/rendering/decision.py` for every gameplay message, preserving this order:

```text
Game: <id> | <mode> | <status> | revision <n>
Role: <Moderator / Opponent / Coach>
Turn / phase: <turn> / <phase> | active: <player>
Decision: <player> / <window>
LP: You <lp> | Opponent <lp>
You counts: Hand <n> | Deck <n> | Extra <n> | Side <n>
Opponent counts: Hand <n> | Deck <n> | Extra <n> | Side <n>
Your hand: <H1, H2, ... in managed mode; private in self mode>
Board: <both numbered fields, Field Zones, GYs, banishment, shared zones>
Chain (activation order): <links, effects, costs, targets>
Usage / restrictions: <Normal Summon use, effect limits, locks>
What happened: <all intervening actions and automatic steps>
Coach — recommended moves:
1. <legal move; benefit, cost, main risk>
2. <different legal move; benefit, cost, main risk>
Your choice: <one clear request; 1/2 or any free-text legal action>
```

Show empty fields/chain explicitly. Open displays include the human's own hand
and set identities; opponent hidden cards and both future draw orders stay hidden.
Blind displays never inspect the human's hidden cards. Give recommendations from
public facts/reveals and accept free-text actions using their unknown hand.

Give two distinct legal recommendations whenever available. They are suggestions,
not an exhaustive menu. Include pass/end phase when legal and useful. If fewer
than two moves can be verified, explain that rather than inventing another move.
Never take over an optional human decision or use a recommendation automatically.

## Continue until the next real choice

Review hand/field/GY/banished effects, costs, targets, timing, restrictions, and
required selections at every window. Managed mode can check full human state. Blind
unknown cards mean unknown options: only public rules excluding action, or a human
confirmation of no response, justify skipping. An empty menu does not prove absence.

If only compulsory execution/bookkeeping or pass-only progression remains, record
the automatic step and continue. Resolve eligible links, mandatory draws, empty
windows, and delayed effects without repeated “continue?” questions. Recheck after
each step and stop at the next real response, optional effect, target/material,
search, trigger-order, attack, phase, or other choice. Choosing among several cards
is meaningful even within a mandatory effect. Unknown legality/rulings also stop
progression. Never advance a paused game without a request to resume.

At the next display report all intervening events in `What happened`, including
costs, negation, draws, damage, and triggers. Silence is never a pass where a human
option exists. For automatic actions add `automatic: true` and `option_review`:

```json
{"complete": true, "meaningful_choices": 0, "basis": "open-state-verified",
 "reason": "No legal human response under the current state and rules."}
```

Other bases: `public-rules-verified`, `human-confirmed-none`. Blind rejects
`open-state-verified`. Zero means no human alternative; compulsory outcomes and
pass-only windows have zero meaningful choices. An optional action plus passing
has two choices. This is a moderator attestation, not automatic rules-engine proof.

## Decision packets

[decision.json](../templates/decision.json) defines the private renderer input:
revision, role, intervening events, recommendations (label/reason), question,
`awaiting_user`, and option review. Complete reviews with at least two choices
require two recommendations. For self/uncertain options use `complete: false`
and `meaningful_choices: null`; this cannot authorize automatic progression.
No-choice active packets require a verified review and `awaiting_user: false`.
Paused/finished displays request no action. Narration and advice must be human-safe.

```sh
python -m harness.rendering.decision --state /workspace/duel-private/example/state.json --game-dir games/casual/example --packet /workspace/duel-private/example/decision.json
```

Use real paths. Packets may name hand cards and remain private. The renderer saves
the exact question, numbered choices, and H-number/physical-instance mapping before
displaying them, preserving the meaning of “1” or “H2” on resume.

## Complete private checkpoints

Initialization and every update refresh private `checkpoint.json`. Rendering adds
the current decision packet/mapping. This self-contained file stores state and
journal, configuration, rules, exact deck/card-text/guide snapshots with hashes,
both hands/sets in managed mode, managed Extra/Side Decks, fixed draw orders, LP/zones,
materials, usage, restrictions, delayed effects, summon history, chain links,
paid costs, targets, resolution choices, and pending windows as recorded by the
moderator. Facts never entered into state/actions cannot be restored.

Blind checkpoints preserve the agent's hidden state and human public counts/reveals
only. The human independently preserves their private cards/order and confirms
the public state on resume. No hidden human data is requested or invented.

```sh
python -m harness.storage.checkpoint save --state /workspace/duel-private/example/state.json --game-dir games/casual/example
python -m harness.storage.checkpoint verify --checkpoint /workspace/duel-private/example/checkpoint.json
python -m harness.storage.checkpoint restore --checkpoint /workspace/duel-private/example/checkpoint.json --state /workspace/duel-private/restored-example/state.json --game-dir games/casual/example
```

Restore into a fresh private directory. Verification checks journal/state, identity,
snapshot hashes, and packet revision. Restore recreates private state/history and
local public views without drawing, shuffling, repaying costs, resolving links,
or committing. It rejects existing private sessions and newer public revisions.
A paused game remains paused; requested resumption is a separate recorded change.

Checkpoints are local private files, not a cloud backup. Keep any requested backup
in authorized durable storage. They do not survive deletion of the entire workspace
unless separately backed up. Do not commit raw runtime files. The separate schema-4 archive intentionally
includes known hidden identities, but never the shuffled queue.
