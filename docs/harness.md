# Harness internals

This is a maintainer/backend reference. Players use the
[conversational orchestrator](orchestration.md); installation and host setup belong
in the [quickstart](quickstart.md).

The runtime supports Python 3.11–3.13 on Windows, Linux, and macOS using the
standard library. The host supplies models and native player children. The LLM
adjudicates legality, timing, costs, effects, battles, and win conditions;
the runtime validates structural state changes and saves them.

## Modules

| Module | Responsibility |
| --- | --- |
| `harness/cli.py` | Installed commands, readiness checks, generated host configuration |
| `harness/integration/service.py` | Repository lobby, setup/resume, and one persistent writer |
| `harness/integration/mcp.py` | Moderator stdio MCP tools |
| `harness/runner/orchestrator.py` | Next human task, player task, or moderator review |
| `harness/runner/player_tasks.py` | Durable child attempts, bindings, deadlines, and results |
| `harness/runner/duel.py` | Authoritative in-memory state, approved actions, and recovery |
| `harness/runner/workflow.py` | Decision IDs, input binding, reviewed execution, and retry receipts |
| `harness/engine/` | Setup, guarded actions, replay, draw/shuffle, and card conservation |
| `harness/players/isolated.py` | Optional tool-free model transport for permitted player context |
| `harness/views/`, `harness/runner/agent_context.py` | Full/compact permitted views and focused card data |
| `harness/storage/` | Locks, atomic writes, checkpoints, archive records, snapshots, and replay caches |
| `harness/rendering/decision.py` | Fixed decision-v1 display |

The supported player workflow uses `Orchestrator.next()` and durable player tasks.
Only the moderator applies state changes. The LLM records adjudicated effects
through `duel_step`; no coded card-handler registry or alternate callback loop is
needed. Draw/shuffle helpers provide randomness, not card-rule adjudication.

## Direct maintainer transport

Normal hosts use `harness.integration.mcp --repo <checkout>` and the tools in
[orchestration](orchestration.md). For existing direct integrations, the module
CLIs remain available:

```sh
python -m harness.engine.session start --repo . --config <private-config.json> --private-dir <private-directory>
python -m harness --state <private-directory>/state.json --game-dir games/<format>/<game-id>
```

Replace angle-bracket placeholders with actual paths. The private directory must
be durable and outside the checkout. The first command initializes a new game;
resume with the second command only. Never deal a new game to recover an old one.
Old `agents/runtime/*.py` script wrappers were removed; use the module names above,
`harness.engine.actions`, `harness.rendering.decision`, or `harness.storage.checkpoint`.

The direct moderator transport reads one JSON object per stdin line and writes
one UTF-8 JSON response per stdout line. Its operations are:

| Operation | Purpose |
| --- | --- |
| `capabilities` | Supported draw/shuffle primitives and the moderator-reviewed legality boundary |
| `view` | Permitted context for `human`, `agent`, `moderator`, or `public` |
| `command` | Approved draw/shuffle when no decision or chain is pending |
| `record` | Approved guarded action from `templates/action.json` |
| `display`, `present` | Save/render a reviewed packet from `templates/decision.json` |
| `submit` | Bind an intention to a saved decision |
| `step` | Execute reviewed operations with a durable receipt |
| `status` | Revision and workflow status |
| `recover` | Repair projections/checkpoint from the recorded journal |

These are trusted moderator interfaces, not a public authenticated API.
Players receive only permitted context and return intentions. Independent host
processes can use the role-bound [arena backend](agent-vs-agent.md).

## State updates and failures

`moderator_approved` records LLM review, not independent rules-engine certification.
Check revisions, physical-copy identities, locations, zone capacity, public
narration, and response windows before applying a step. See
[natural-language actions](natural-language-actions.md) for the action contract.

A runner locks both its private session and game archive directory. Competing
writers, even with copied private state, are rejected. A cached state must match
the journal and checkpoint at resume; the saved mode and isolation policy remain
immutable. Legacy `open`/`blind` modes and old archive readers are retained for
historical saves, not new mode definitions.

The journal is saved before derived projections/checkpoints. A projection failure
reports `recovery_required`; stop and call recovery before continuing. Keep stable
request IDs and identical payloads on retries. Recovery replays recorded results
without repeating effects or sampling another shuffle. Out-of-band journal edits
are rejected. No Git, model, or network calls run inside state-update execution.

Saved numbered choices, attempts, managed hidden state, and deck order survive
private checkpoint restore. The archive and content-addressed asset contract is
owned by [game storage](game-storage.md); child isolation/failure handling by
[player isolation](player-isolation.md).

## Performance and verification

Keep one runner loaded per game and use compact permitted context for routine
decisions; request focused/full data when needed. Benchmarks use temporary games:

```sh
python -m unittest discover -s tests -v
python tests/benchmarks/runner.py
python tests/benchmarks/workflow.py
python tests/benchmarks/archive.py
```

They measure state-update, workflow, replay/cache, and context costs separately
from model latency. Tests validate storage, privacy, and orchestration rather
than comprehensive card legality. See [release validation](releases.md) for built
wheel smoke tests and [contributing](../CONTRIBUTING.md) for change requirements.
