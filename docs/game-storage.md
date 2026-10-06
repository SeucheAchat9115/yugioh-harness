# Compact game archives and agent contexts

Games are stored locally for replay and review, including known hidden hands
and face-down identities. Player agents receive filtered runtime contexts instead.
`games/` and `snapshots/` are ignored by Git, and existing records are no longer
tracked. Source commits and pushes do not upload or back up game data. Copies
already present in older Git history are not removed by this policy.

## Local layout and backups

Each `games/<format>/<game-id>/` contains:

- `game.json`: identity, mode, rules/banlist versions, settings, original deck
  identities, logical snapshot names, result and current progress.
- `events.json`: the authoritative archive index and baseline; it contains no event payload array.
- `events/000001.json`, etc.: one immutable recorded event per resulting revision.
  Intermediate states,
  readable action logs and review contexts are generated on demand.

Immutable asset bytes are shared under `snapshots/<first-two-hash-characters>/<sha256>`.
The archive's `assets_sha256` maps readable logical names such as `rules.md` or
`decks/agent/lightsworn/guide.md` to these objects. These names identify resources,
not copied files inside each game. Equal contents reuse the same immutable object
across games. Editing a source deck creates different snapshot hashes; historical
references keep their original contents. Never modify an existing snapshot object.

`catalog_refs` points each managed player's card catalog at the `cards` field of
its shared `deck.json` snapshot. If a custom catalog has no matching deck asset,
it uses its own shared JSON object. The initial state omits embedded catalogs;
replay hydrates them before checking state hashes. No garbage collector deletes
snapshot objects automatically: archives and private checkpoints can still need them.

Do not persist duplicate game-folder `state.json`, `actions.md`, `log.md` or
`resume.md`. YDKs, guide text and provenance are shared deck resources, not second
logs. `harness.storage.snapshots.collect(game_dir)` resolves logical resources for
runtime use and supports legacy games with local snapshot files.

## `events.json` schema 4.0

| Field | Meaning |
| --- | --- |
| `schema_version` | `4.0`; schema-2 and schema-3 archives remain readable, schema-1 summary logs require migration from private history. |
| `visibility` | `omniscient-archive`. Never give this file directly to a player agent. |
| `deck_order` | `unordered-instance-inventory`: deck arrays are sorted by physical instance ID, not draw order. |
| `purpose` | `replay-and-review-not-live-resume`. |
| `hidden_state_coverage` | `complete` for managed/open/agent-vs-agent; `human-unknown` for self/blind. |
| `initial_state` | Known initial hands, zones, physical copies and gameplay bookkeeping; catalogs are referenced separately. |
| `initial_state_sha256` | Hash of the hydrated baseline, including revision-zero games. |
| `operation_encoding` | `physical-moves-and-deltas-v1`. |
| `event_index` | Ordered entries with `file`, `revision`, resulting `turn`/`phase`, `actor`, `kind`, reviewed `public_summary` and `event_sha256`; no operations or state copies. |
| `source_tail_sha256` | Digest connecting the export to its private source journal, without exporting the shuffled queue. |
| `assets_sha256` | Logical names and content hashes of shared immutable resources. |
| `catalog_refs` | Per-player catalog object hash and optional field selector. |
| `configuration_sha256` | Hash of `game.json`. |
| `decision_packets` | Recorded prompts, recommendations, response windows and hand references. |
| `decisions` | Recorded human/AI intentions, selected-option details, actor, revision and IDs. |
| `decision_evidence` | Explicit coverage status, counts, and player-action revisions with no recorded intention/menu. |

Each event file contains `revision`, resulting `turn` and `phase`, `recorded_at`,
`before_sha256`, `after_sha256`, `action`, `deck_outcomes` and `event_sha256`.
A recorded event is one state transition: an activation, response and resolution
can occupy separate records. It is not necessarily a whole human move or turn.
The filename uses the resulting revision, padded to at least six digits; revisions
are contiguous after the baseline. No monolithic event array is also persisted.

For selective review, read `events.json`, filter `event_index` by turn, phase,
actor or kind, then read only the referenced files. `records.read_event(game_dir,
entry)` verifies one record's hash and discovery metadata without loading others.
The index and records contain omniscient information and are moderator/reviewer
resources; active player children continue to receive filtered runtime contexts.

The single writer writes new records first, then atomically replaces the index.
Existing records are immutable. An interrupted append can leave an unindexed
record; readers ignore it, and an identical retry reuses it. A different record
at the same revision is rejected. Do not delete indexed files or reuse revisions.
Changing recorded history requires a separate archive rather than overwriting it.

Schema-4 actions retain ID, kind, actor, expected revision, reviewed narration,
moderator approval, automatic/no-choice review, result and workflow correlation.
They contain `operations`, not whole-zone before/after copies:

- `move`: physical instance, source path, destination, optional insertion index and
  only changed/deleted attributes. Source identity and destination capacity are checked.
- `lp` / `delta`: path and numerical adjustment.
- `reveal` / `set`: path and new value.
- `delete`: remove a dictionary field.
- `splice`: replace only a changed list segment, preserving the unaffected prefix/suffix.

Inserted card values can use `$instance` references with attribute changes rather
than repeating an existing card object. References resolve against the event's
starting physical-card registry. Complex changes, materials, tokens, controller
changes and arbitrary adjudicated metadata remain expressible through structural
operations. Operations are applied to a copy; the reconstructed transition then
passes the existing structural guards, physical-card accounting, chain-window
checks and before/after state hashes. The LLM still adjudicates card legality;
this format is not a coded effect engine.

Record LP, cards/zones/controllers, hidden/revealed status, materials, counters,
current stats/types, summon history, attacks, activation limits, restrictions,
chain costs/targets and pending effects/decisions whenever relevant. The archive
cannot recover bookkeeping never recorded. For concession, deck-out or alternate
victory, the finishing `duel_step.request.result` needs `winner` (`human`, `agent`,
`draw`) and a concrete `reason`. Zero-LP results can be derived automatically.

`deck_outcomes` preserves the physical cards actually drawn/milled/searched in
order, and known top/bottom/index placements. Shuffle actions are retained but
permutations and random seeds are omitted. Recorded trajectories are reproducible;
new draws or proving the source queue require the private live checkpoint.
Coin/die/selection outcomes must likewise be explicitly recorded in action/state.

## Revision caches and compatibility

`load_replay(game_dir, revision=None, perspective='moderator', cache_dir=None)`
reads schemas 2, 3 and 4. A cold replay verifies the entire history, even when
requesting an early revision. It then caches every 16th revision, the final state
and requested revisions locally. Warm reads reuse these verified states instead
of replaying the full prefix. Archive contents determine the cache namespace;
archive changes invalidate it. Configuration and immutable resources are still
verified on warm reads. Corrupt/mismatched cached states are discarded and rebuilt.

The default cache is `<repo-parent>/<repo-name>-replay-cache/`, outside Git. Cache
folders are private (0700), files are 0600, and an explicit inside-repository cache
path is rejected. Cache files contain hidden state, are disposable and never the
live session's shuffled queue or authoritative history. Deleting them only makes
the next replay cold. `render_log(game_dir)` generates readable reviewed summaries.

Live session `journal.json`, `state.json`, `checkpoint.json`, `workflow.json` and
locator remain outside the repository. They retain exact queues, pending menus,
subagent handles/deadlines and retry receipts for continuation. Self-contained
checkpoints retain asset bytes for restoration into a fresh checkout; restoration
interns these assets back into the shared store. Never upload raw runtime files.

## Agent context interface

Use MCP `duel_agent_context(player, card_ids?)` or
`runner.context(player, card_ids=None, compact=True)`. The sequential orchestrator
and internal decision loop use compact contexts by default. The compatibility
`duel_context` endpoint still provides the full permitted context.

Compact-v1 includes the current board and resources, private hands only as allowed
by that game's mode, pending chain/effects and decision, exact relevant card text,
format/rules, up to four recent actions and up to 1200 characters of relevant
own-deck guidance. Extra Deck option identities remain available; their effect
text is provided on explicit focus. Side Deck options are omitted during ordinary
play and included during sideboarding. Old attack usage entries and the moderator's
remaining-deck inventory are omitted. Current restrictions and other effect usage
remain intact. Limits/truncation are labelled rather than presented as complete.

Filtering happens before compaction. A focus request can only return card records
already visible to that role, never the opponent's hidden identities or future
queue. The host can request full/focused permitted details before dispatching a
fresh player child. Player children remain context-only and must not read archives
or shared snapshot objects. Legacy open-mode visibility remains unchanged.

## Decision evidence and migration

Coverage is labelled from recorded evidence, not invented reasoning. Player actions
without a saved menu/intention are listed; delegated continuations can intentionally
have no new menu. Stored intentions are decisions, not a transcript of unrecorded
model reasoning. Self/blind archives cannot reconstruct human hidden cards the
moderator never knew. Do not ask for or fabricate them during self play.

The internal `harness.storage.archive` CLI supports `migrate`, `replay` and `log`.
Migration requires an authoritative private journal, checks game identity/newer
history, interns assets, converts transitions and verifies the resulting state.
Historical packet/intention gaps remain explicitly partial. Existing schema-1
private journals/checkpoints and schema-2/schema-3 local archives remain supported.
Humans never need to execute these commands during a duel.

Back up `games/`, `snapshots/`, and the external private save directory together.
The replay archive reconstructs past states; exact continuation also requires its
private checkpoint and shuffled queues. A self-mode human keeps their physical
hidden cards separately. Do not force-add local archives to publish source changes.
