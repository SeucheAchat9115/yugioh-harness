# Agentic duel harness

This page documents backend interfaces for maintainers and the orchestrator.
Players use [one conversational agent](codex-play.md) in every mode and never
need to execute these Python commands themselves. The repository-level MCP lobby
handles deck discovery, setup/resume, and sequential private subagent tasks;
`--repo <checkout>` enables it without per-game paths. The host orchestrator
invokes native children and remains the sole moderator writer.


The LLM is the gameplay interpreter and moderator. It reasons about card text,
legality, timing, costs, chains, summons, battles, victory, and strategy under the
agreed rules. The harness keeps the duel loaded, applies the LLM's approved state
updates, manages randomness and permitted views, and saves resumable records.
A full coded Yu-Gi-Oh! simulator is outside the required scope.

The Python runtime uses Python 3.12 and the standard library on Linux/macOS. It
has no model SDK dependency; the host assistant or application supplies the LLM.
The runner is a trusted local moderator service; its JSON-lines transport is not
a public authenticated API.

## Responsibilities

| Module | Responsibility |
| --- | --- |
| `harness/runner/duel.py` | Persistent single writer, incremental updates, decision contexts, and scheduler hook |
| `harness/engine/` | Setup, guarded actions, replay, draw/shuffle commands, and structural validation |
| `harness/effects/` | Optional coded shortcuts; the LLM adjudicates effects without a handler |
| `harness/players/` | Callback/protocol boundary for human and model clients |
| `harness/views/` | Permitted views; runner player contexts exclude future draw order |
| `harness/storage/` | Atomic files and self-contained private checkpoints |
| `harness/rendering/` | Fixed decision-v1 human display |
| `agents/` | LLM policies for rules adjudication, opponent play, and coaching |

Decks remain in `decks/<format>/<name>/`; rules, skills, and historical records keep
their existing locations. Legacy `agents/runtime/*.py` entry points delegate to the
new modules. Existing schema-1 journals and checkpoints load without conversion.

## Gameplay responsibility and action flow

| LLM moderator/player | Harness |
| --- | --- |
| Interpret natural-language declarations and exact card text | Supply deck/card assets and permitted state views |
| Judge legality, costs, targets, materials, timing, and response opportunities | Check revisions, guarded values, chain structure, and physical-card identity |
| Resolve effects, battle, delayed effects, and phase/turn procedures | Apply approved changes, preserve random outcomes, and persist checkpoints |
| Choose tactics, coach human decisions, and consult ruling sources | Render the fixed display and retain exact pending choices |

The normal path is human/agent input → LLM adjudication → approved action record →
harness update and local save → next decision. The runtime's `engine/` directory
names the state-update machinery, not a complete implementation of card rules.
`moderator_approved` records the LLM's review; structural checks do not prove that
its rule judgment is correct. Unclear interactions pause for a ruling.

## Start and resume

For conversational play the orchestrator calls `duel_start` and `duel_resume`
internally through the repository lobby. The commands below are the legacy
maintainer interface, not player instructions.

Prepare a private configuration from `templates/duel-config.json`. Agree on rules
and legality first; start deals opening hands but does not perform a turn draw.
Use a durable private directory outside the repository.

```sh
python -m harness.engine.session start --repo . --config /tmp/duel-config.json --private-dir /workspace/duel-private/example-001
python -m harness --state /workspace/duel-private/example-001/state.json --game-dir games/tcg/example-001
```

Replace example IDs/format with the actual configuration. To resume, use the second
command only. The runner verifies the journal, state cache, and checkpoint once,
then retains state and card data in memory. It preserves pending choices and orders.
Never start again to resume. Inspect `runner.packet` in Python for saved numbered
choices; the transport's `view` returns only a permitted context.

The runner and legacy mutation commands share nonblocking writer locks for both
the private session and repository archive directory. A second runner or competing writer
is rejected, including one using a copy of the private state. Lock files are local
coordination artifacts and are never archived. Out-of-band journal edits are also
detected before updates. This is a local single-writer design.

## Agent-versus-agent mode

[Agent-vs-agent play](agent-vs-agent.md) manages both decks with symmetric private
player views and a moderator view. The conversational orchestrator dispatches
private player children sequentially; a role-bound arena is an optional backend
for host-managed independent clients.
Open coaching visibility never applies in this mode; spectators see neither hand.

## Codex and integrated play

Use [Codex play integration](codex-play.md) for the persistent MCP tools,
numbered/free-text input binding, retry receipts, state operations, and the
host-driven player/moderator loop. Rules and guide excerpts are loaded from saved
assets; Codex continues to adjudicate gameplay.

## Moderator transport

Send one JSON object per stdin line; each stdout line is a JSON response. For example:

```json
{"op":"capabilities"}
{"op":"view","player":"human"}
{"op":"command","request":{"id":"draw-001","command":"draw","actor":"agent","count":1,"expected_revision":0,"moderator_approved":true}}
```

The draw example is legal only after the moderator checks a draw is due and no
chain/decision is pending. Primitive commands reject pending windows. Shuffles
store the resulting order in the journal; replay never samples randomness again.
Self human draws update counts only; self human shuffles remain human-managed.

Other operations:

- `record`: a trusted moderator-approved action using `templates/action.json`.
- `effect`: an optional named coded helper and request. Unknown handler names are
  rejected by this endpoint; the LLM instead adjudicates the effect and submits
  the approved result through `record`. Missing handlers do not block gameplay.
- `display`: a packet using `templates/decision.json`; persists exact hand references
  and choices before returning the fixed display.
- `present`, `submit`, `step`, `status`: durable decision workflow and reviewed state
  operations described in [Codex play integration](codex-play.md).
- `recover`: rebuilds projections/checkpoint from the journal after a write failure,
  without applying another action.

Malformed requests return structured `invalid_request` errors rather than ending
the transport. Rejected actions return `action_rejected`; storage failures can
return `recovery_required` with the action ID and whether it reached the journal
(`recorded: true`, `false`, or `null` when status cannot be determined). No private
payloads or exception details are echoed. Never resubmit an action already recorded.

Player adapters must never receive `record` access, authoritative state, private
files, or moderator credentials. They receive `runner.context(player)` and return
an intention. The moderator translates natural language and reviews legality,
then executes a supported command/handler or approved action. The model client
and human chat UI are supplied by the host application; no hosted bot ships here.
Open coaching deliberately permits knowledge of the human hand. Future draw order
is excluded from runner player contexts, even in managed mode. The legacy moderator
view can still expose it for authorized bookkeeping. Public cards, chains, costs,
counters, restrictions, and delayed effects use explicit allowed fields; private
annotations and resolution-choice payloads are omitted. Mark private delayed effects
with `visibility: "private"` and their `owner`. Free text in public fields and event
narration still needs moderator review.

Player contexts include exact gameplay text for visible card identities, permitted
pending effects, and the ten most recent reviewed events. They do not include the
opponent's hidden card catalog or future Deck order.

## Optional effect helpers and agent-controlled progression

Coded helpers are optional conveniences for repeated operations. Register
`name -> handler(state_copy, request_copy)` in an `EffectRegistry` and
pass it to `DuelRunner`. A handler returns one complete moderated action; it cannot
mutate runner state directly. Use separate actions/decisions for activation,
responses, costs, resolution choices, and trigger windows. Never resolve while a
response decision is pending.

`runner.advance(next_step)` repeatedly applies moderator-verified automatic actions
until a pending decision, paused/finished state, or absence of a supported step.
Every automatic action needs the complete no-choice review defined in
`docs/duel-experience.md`. Return the collected narration in the next decision
packet. Unknown self options cannot justify automatic progression. The LLM
moderator identifies available actions and decides when phases or turns advance;
a complete coded scheduler or legal-action generator is not required.

## Persistence and speed

Each action is structurally validated, appended incrementally, and saved locally.
The journal is written before disposable projections and the checkpoint. Recovery
uses full replay after interrupted writes; do not keep playing with mismatched
files. Snapshot assets are cached for the lifetime of the runner and are immutable
during play. Full history verification happens at resume, not on every command.

Structural checks conserve managed physical card IDs across all zones and attached
materials, reject invalid zone containers/layout changes, and preserve card identity.
On control changes, keep the original `owner` and track `controller` separately.
Tokens use an explicit boolean `token: true` and may be created/removed; this never
allows an ordinary card to disappear. Self human hidden cards remain count-based
and are not assigned invented identities.

After a save failure, the live runner blocks gameplay and context delivery until
`recover` succeeds. The journal remains authoritative. If the process ended before
recovery, stop competing writers, run `python -m harness.engine.actions replay`
with the session's `--state` and `--game-dir`, then resume the runner. Recovery
repairs recorded results; it never repeats an effect or reshuffles a Deck.

No Git, network, model calls, or guide regeneration happen on the execution path.
The engine returns public state; models receive compact permitted contexts and
relevant card text chosen by the moderator. Cards/guides need not be reloaded for
every move. Measure model reasoning and transport latency separately from engine
latency.

```sh
python -m unittest discover -s tests -v
python tests/benchmarks/runner.py
```

The benchmark creates a temporary open session, performs 20 shuffles, and reports
startup, median, and p95 action latency, including saves. It never touches live games.

## Project scope and improvements

The project remains an LLM-driven play harness. Its runtime provides persistent
state, local transport, adapters, permitted views, optional helper hooks,
deterministic primitives, structural checks, fixed displays, and verified resume.
The LLM supplies game-rule adjudication and strategic decisions. Card-specific
handlers, a battle simulator, and a comprehensive coded rules engine are optional
extensions, not milestones required to complete the harness.

Prioritize better agent context, low-latency tool calls, reliable state tracking,
clear human decisions, ruling references, played-scenario evaluations, and
agent-versus-agent coordination. Evaluate the LLM's gameplay separately from
runtime integrity. An external simulator can be an optional integration if useful;
it is not the default architecture or a prerequisite for playing new decks.

## Human mode configuration

For new human games set `mode` to `managed` or `self` in the internal
`templates/duel-config.json` configuration. `managed` requires `human_deck` and
loads its bundle; `self` requires `human_deck: null` and numeric
`human_deck_counts` without card identities. The orchestrator fills these fields
from conversation. Managed human hands, sets, private effects, and guides remain
hidden from the opponent child. Agent-vs-agent still uses `agent-vs-agent`.

Legacy `open` and `blind` are accepted for existing integrations and saved games.
They are not rewritten: `open` retains opponent access to human hidden state,
whereas `blind` behaves as self. The journal mode is immutable. The existing
`open-state-verified` no-choice basis means a moderator review of known state;
it is valid for managed games and never valid for unknown self/blind human state.

## Saved player isolation

The startup configuration and immutable journaled state contain
`player_isolation: "cooperative"` or `"enforced"`. New managed/self/agent-vs-agent
games default to cooperative; legacy open/blind startup and saved documents
without a setting retain enforced requirements. Resume verifies configuration
and state agree. `duel_next` and status report the policy, and dispatch receipts
record the actual boundary separately; an enforced transport may satisfy a
cooperative game. Actual capabilities/evidence are saved privately per attempt.
Neither policy changes hidden-information projection or legality review.

Repository persistence uses the single omniscient schema-2 `events.json` archive
described in [game storage](game-storage.md). It includes hidden identities and
realized outcomes; player contexts stay filtered. Private checkpoints retain
exact shuffled orders for continuation.
