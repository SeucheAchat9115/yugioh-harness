# Agentic duel harness

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

A lifetime file lock rejects a second runner. Do not use legacy writer commands
while it is running. Journal changes made by a legacy writer are detected before
the next mutation. This is a local single-writer design, not a distributed service.

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
Blind human draws update counts only; blind human shuffles remain human-managed.

Other operations:

- `record`: a trusted moderator-approved action using `templates/action.json`.
- `effect`: an optional named coded helper and request. Unknown handler names are
  rejected by this endpoint; the LLM instead adjudicates the effect and submits
  the approved result through `record`. Missing handlers do not block gameplay.
- `display`: a packet using `templates/decision.json`; persists exact hand references
  and choices before returning the fixed display.

Player adapters must never receive `record` access, authoritative state, private
files, or moderator credentials. They receive `runner.context(player)` and return
an intention. The moderator translates natural language and reviews legality,
then executes a supported command/handler or approved action. The model client
and human chat UI are supplied by the host application; no hosted bot ships here.
Open coaching deliberately permits knowledge of the human hand. Future draw order
is excluded from runner player contexts, even in open mode. The legacy moderator
view can still expose it for authorized bookkeeping. Free-form public narration
and chain fields must be reviewed for hidden information before saving.

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
packet. Unknown blind options cannot justify automatic progression. The LLM
moderator identifies available actions and decides when phases or turns advance;
a complete coded scheduler or legal-action generator is not required.

## Persistence and speed

Each action is structurally validated, appended incrementally, and saved locally.
The journal is written before disposable projections and the checkpoint. Recovery
uses full replay after interrupted writes; do not keep playing with mismatched
files. Snapshot assets are cached for the lifetime of the runner and are immutable
during play. Full history verification happens at resume, not on every command.

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
