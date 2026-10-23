# Shared agentic environment: agreed direction

Decision date: 2026-10-23. The canonical repository is `yugioh-harness`.
Play and evaluation share one runtime. The first end-to-end validation scope is
Edison with Blackwing/Lightsworn; other existing profiles and saves remain supported.
Pilots propose open intentions. Headless operation comes first; a GUI comes later.

## Monorepo boundaries

| Location | Responsibility |
| --- | --- |
| `harness/engine`, `runner`, `storage`, `views` | Authoritative state, orchestration, structural validation and journals |
| `harness/environment` | Versioned host contract, filtered display projection and fixed-position initialization |
| `harness/integration` | Headless JSON lines, MCP, optional role-bound arena |
| `agents`, `skills`, `rules`, `decks` | Host/player instructions and pinned gameplay assets |
| `benchmark/src/yugioh_benchmark` | Replay importing, reviewed scenarios, grading and metering |
| `benchmark/benchmarks`, `fixtures`, `replays`, `docs` | Existing reviewed/source datasets and historical results |

One root installation provides `yugioh-harness` and `yugioh-benchmark`. Benchmark
provenance is pinned to source commit `8894fbf6c8afea5c1908113e1317578be15827cf`;
its original Git history remains available in the source repository. The old remote is not deleted or
archived by this migration. The original benchmarks/results remain labeled with
their formats and protocol; Perfect Circle positions have not become Edison data.

## Agent and runtime roles

The orchestrator routes tasks; the referee interprets rules and proposes approved
transitions; pilots choose intentions from permitted observations. A host may
perform orchestration and referee work in one agent session. Pilot sessions must
remain independent. Python owns state, random draws, inventory integrity, revision
checks and durable execution. Code must not become a second card-effects engine.
Player intentions are submitted before adjudication. A referee cannot silently
repair a pilot's move or select targets/materials on the pilot's behalf.

One player decision, including an opponent response or a choice during effect
resolution, is the interaction unit. Turn ownership does not determine whose
choice comes next. Compulsory steps may advance only after an explicit no-choice
review. Unknown legality or missing player information blocks progression.

A full-state checkpoint is private. Player observations are filtered by role.
Scenario grading, expected moves and future replay events stay evaluator-only.
Fixed positions initialize through `harness.environment.positions.create_position`,
which is also used by the metered benchmark runner; they can be resumed through
the headless API without a separate game-state representation.

## Evaluation tracks

| Track | Vary | Hold fixed | Report |
| --- | --- | --- | --- |
| Pilot | Playing model/policy | Scenarios, referee, prompts, budgets and opponent | Legality, objective success, win rate, latency and cost |
| Referee | Adjudicating model | Reviewed intentions, states and rules | Transition accuracy, timing/window correctness and uncertainty |
| Whole system | Complete configuration | Versioned evaluation protocol | Valid completed duels, interventions, failures, cost and outcomes |

Historical human-move agreement remains descriptive; it does not prove optimal
play. Keep legacy three-KPI results intact and label new protocols separately.
A historical continuation cannot adjudicate a counterfactual after model divergence.
For full-duel comparisons use repeated seeds and side swaps, controlled opponents,
confidence intervals, and explicit referee failures distinct from pilot errors.
Do not publish a new score from scripted integration fixtures.

Archive model identities, exact requests/responses, prompts, options, tool access,
engine and asset digests, opponent/referee versions, budgets, timing, usage and
billing metadata. Pinning a seed does not reproduce a live LLM referee. Recorded
journal transitions replay exactly; fresh model calls need repeated trials.

## Implementation sequence and acceptance

| Stage | State | Acceptance |
| --- | --- | --- |
| Monorepo and headless boundary | Implemented | One install; both test suites; JSON-lines and one-shot resume; filtered GUI projection |
| Native chat transport trial | Completed for one authored position | Real fresh pilot sees only its view, returns an intention, receipt persists and resume preserves it |
| Edison full-duel hardening | Next | Complete Blackwing/Lightsworn games cover draws, priority, summons, chains, battles and resolution; every real choice preserved |
| Unified scenario manifests | Next | Versioned pinned manifests for single decisions, continuations, puzzles and duels; grading stored separately; same positions playable by humans and models |
| Separate evaluation tracks | Planned | Pilot/referee/whole-system reports with independent failure attribution; keep old scores comparable only within old protocols |
| Controlled full-duel suite | Planned | Repeated games, opponents, side swaps and uncertainty; no performance-selected retries |
| RL adapters | Planned | PettingZoo AEC for sequential multi-agent choices; Gymnasium wrapper against a configured opponent |
| GUI | Deferred | Render structured `interaction` data and submit intentions through a trusted host backend |

On 2026-10-23, this ChatGPT Work host ran one fresh native Blackwing pilot
(`fork_turns=none`) against an authored Edison Main Phase position via the headless
one-shot CLI. The pilot proposed a Shura Normal Summon in open natural language.
The host independently reviewed it, committed it, preserved the human
summon-negation response window, resumed the session and verified journal replay.
Cooperative tools/files remained available; no child tool calls were observed.
This was one integration trial, not a full duel or a measured benchmark score.

The existing agentic moderator can handle general card interactions, but a complete
uninterrupted Edison duel has not been certified by the transport tests. Current
`intent-v1` still stops at response windows and is not the full action vocabulary.
The native-chat trial validates integration, not competitive strength or general
rules accuracy. Actual trials must report the host and observed isolation honestly.

## RL contract to prepare next

Keep the transport-independent decision boundary. Add explicit observation/action
encoders and versioned spaces in adapters. Open text/structured intentions remain
the primary LLM track; candidate-index policies are a separately labeled track.
Candidate menus generated by a referee cannot be assumed exhaustive legal actions.
Masking must use only actor-visible information to avoid leaking hidden responses.

Start with terminal rewards: win +1, loss -1, draw 0; scenario-specific objectives
are versioned. LP and material advantage are diagnostics until shaping is justified.
Keep rewards separate from benchmark aggregation. Referee outages, time budgets
and uncertain rulings need explicit truncation/failure reasons, not invented losses.
A training run needs a fixed referee configuration and telemetry for environment
errors. LLM adjudication cost/reliability limits high-throughput self-play; begin
with reviewed short scenarios. Seeded RNG for new games/shuffles remains future
work; the current runtime preserves realized shuffle/draw outcomes on resume.
