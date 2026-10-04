# Duel harness

The harness keeps a duel loaded and separates deterministic execution from model
reasoning. It uses Python 3.12 and the standard library on Linux/macOS. It has no
network or model dependency. The runner is a trusted local moderator service;
its JSON-lines transport is not a public authenticated API.

## Responsibilities

| Module | Responsibility |
| --- | --- |
| `harness/runner/duel.py` | Persistent single writer, incremental updates, decision contexts, and scheduler hook |
| `harness/engine/` | Setup, guarded actions, replay, draw/shuffle commands, and structural validation |
| `harness/effects/` | Explicit handler registry; unknown effects require moderation |
| `harness/players/` | Callback/protocol boundary for human and model clients |
| `harness/views/` | Permitted views; runner player contexts exclude future draw order |
| `harness/storage/` | Atomic files and self-contained private checkpoints |
| `harness/rendering/` | Fixed decision-v1 human display |
| `agents/` | Opponent, coach, and moderator instructions |

Decks remain in `decks/<format>/<name>/`; rules, skills, and historical records keep
their existing locations. Legacy `agents/runtime/*.py` entry points delegate to the
new modules. Existing schema-1 journals and checkpoints load without conversion.

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
- `effect`: a named registered handler and request; unsupported names are rejected.
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

## Effect and scheduling extension points

Register `name -> handler(state_copy, request_copy)` in an `EffectRegistry` and
pass it to `DuelRunner`. A handler returns one complete moderated action; it cannot
mutate runner state directly. Use separate actions/decisions for activation,
responses, costs, resolution choices, and trigger windows. Never resolve while a
response decision is pending.

`runner.advance(next_step)` repeatedly applies moderator-verified automatic actions
until a pending decision, paused/finished state, or absence of a supported step.
Every automatic action needs the complete no-choice review defined in
`docs/duel-experience.md`. Return the collected narration in the next decision
packet. Unknown blind options cannot justify automatic progression. There is no
built-in complete phase scheduler or exhaustive legal-action generator yet.

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

## Current scope and next work

Implemented: persistent runner, local transport, adapters, views, explicit effect
registry, deterministic primitives, structural checks, fixed displays, local saves,
and verified resume. No card-specific handlers, automated battle/damage engine,
complete legality checker, banlist verifier, model provider, agent-versus-agent
scheduler, or match/sideboard implementation ships yet. Add scenario-tested handlers
for Branded Despia and Dracotail next, or implement an adapter to an established
simulator. The harness boundaries support either approach.
