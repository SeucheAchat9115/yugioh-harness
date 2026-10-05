# Game archives and live checkpoints

Each game uses `games/<format>/<game-id>/`. Its repository archive contains hidden
information for replay and review. It is an omniscient artifact, never a player
context or public live-state display. Publishing requires an explicit user request;
local saving, pausing and finishing never authorize a Git commit.

## Files and their authority

- `game.json`: game identity, mode, format, banlist, historical rules version,
  settings, original deck identities, snapshot locations, status and resume summary.
- `events.json`: schema 2.0, the single authoritative archive log. Contains the
  initial state and ordered guarded transitions, including both managed hands and
  face-down identities. No separate `state.json`, `actions.md`, `log.md` or
  `resume.md` is written in the game folder. Final/intermediate states and readable
  summaries are generated from the log.
- `rules.md` and `decks/<slot>/<deck-name>/`: immutable rules and deck snapshots.
  Gameplay JSON supplies exact card text/stats; guides preserve the advice available
  to the agent, including historical errata notes. Their content hashes are checked
  on replay. YDKs and provenance remain deck artifacts, not additional action logs.

The outside-repository live session still owns its `journal.json`, `state.json`,
`checkpoint.json`, `workflow.json` and session locator. These preserve the exact
shuffled queues, pending menus, subagent deadlines/handles and retry receipts for
safe resumption. Do not upload those runtime files wholesale.

## `events.json` schema 2.0

The top-level fields are:

| Field | Meaning |
| --- | --- |
| `schema_version` | `2.0`; older schema-1 summary logs lack complete replay data. |
| `visibility` | `omniscient-archive`; hidden identities are deliberately included. |
| `deck_order` | `unordered-instance-inventory`. Deck arrays are sorted by physical instance ID, not draw order. |
| `purpose` | `replay-and-review-not-live-resume`. |
| `hidden_state_coverage` | `complete` for managed/open/agent-vs-agent; `human-unknown` for self/blind. |
| `initial_state` | Full known game state at the starting revision, including hidden hands, field cards, card catalogs and unordered deck inventories. |
| `initial_state_sha256` | Integrity hash of the baseline, including revision-zero games. |
| `events` | Ordered transitions: timestamp, state hashes, moderator-approved action and exact before/after changes, deck outcomes and an event integrity hash. |
| `source_tail_sha256` | Digest linking this export to the latest private journal state; does not contain its deck queue. |
| `assets_sha256` | Paths and hashes of immutable rules/deck snapshots. |
| `configuration_sha256` | Hash of this game's `game.json`. |
| `decision_packets` | Persisted menus, recommendations, response question and hand references for assessing guidance, when available. |
| `decisions` | When available, submitted human/AI intentions with decision IDs, actor, revision and selected recommendation details. Host credentials and duplicate execution patches are excluded. |

Each action retains its ID, kind, actor, expected revision, reviewed narration,
legality approval, automatic/no-choice review and workflow correlation when present.
Its changes reconstruct the next state without executing card effects or rerolling
randomness. Physical `instance_id` values distinguish duplicate copies.

Record every relevant state change: LP, zones and controllers, hidden/revealed
status, materials, counters, current stats/types, summon history, attacks, activation
limits, restrictions, chain costs/targets, pending effects and response decisions.
For a concession, deck-out or alternate victory, include `request.result` with
`winner` (`human`, `agent` or `draw`) and a concrete `reason` in the finishing
`duel_step`. Zero-LP results can be derived automatically; other results are never
invented.

The moderator must explicitly record these fields when a ruling uses them; the
archive cannot recover bookkeeping that was never recorded. Card text and format
snapshots make retrospective legality review possible, but replay validates
structure and integrity rather than proving every ruling correct.

`deck_outcomes` records physical cards leaving each deck in their original order
(draws, mills, searches or other moves), and newly returned cards' top/bottom/index
positions. Shuffle events remain recorded, but shuffled permutations are omitted.
Future actions record their realized outcomes, so a finished recorded trajectory
is reproducible without its random seed or queue. Unordered inventories cannot
predict a new draw or prove that a recorded draw came from the original queue;
use the retained private checkpoint/journal for either task. Random coin/die or
selection results must likewise be recorded explicitly in the action/state.

For self/blind games, the human's unknown hidden identities cannot be archived
unless supplied after play. Do not ask for them during a self game, fabricate them,
or label that archive complete. Previously unrecorded menus/rationale remain
unavailable after migration; submitted intentions are preserved when the private
workflow exists. Legacy journals and checkpoints remain supported.

## Replay, review, and migration

The orchestrator operates these helpers internally. Humans never need terminal
commands during a duel.

`harness.storage.archive.load_replay(game_dir, revision=None,
perspective='moderator')` verifies assets, configuration, all event hashes and
structural transitions, then reconstructs the requested revision. The moderator
perspective exposes known hidden identities. Request `human`, `agent` or `public`
for filtered views, preserving each game's original visibility policy. These
views omit deck order; player agents must not read the omniscient file directly.

`render_log(game_dir)` generates readable reviewed summaries on demand. The module's
internal CLI supports `replay`, `log` and `migrate`. Migration requires the
original authoritative private journal, checks game identity and newer-history
conflicts, and verifies the resulting state against the source. Missing private
history means an old summary-only game cannot be upgraded into a full replay.
