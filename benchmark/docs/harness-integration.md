# Agentic evaluation through the harness

The intended benchmark has [three equally weighted KPIs](agentic-kpis.md): state
recreation, human-move agreement and format-specific rule correctness. GPT-6.1
Sol is the configured evaluation target. The combined scorer is implemented;
[18 scoped replay checkpoints](replay-review-stage.md) are prepared; an actual
model run on this expanded suite remains pending. The original four-checkpoint
cooperative pilot has completed; its result does not apply to these 18 positions.

For live evaluation, use the harness's existing orchestrator and sole moderator
writer to collect model attempts, reviewed action records and authoritative
journals. State recreation tests the agent interpreting a player-declared play;
human agreement tests its independent move choice. Independent legality grades
apply to both. Follow the KPI guide for pinned inputs and grading artifacts.
The filtered decision bridge below supplies player intentions only; its text
response is not evidence that the play was executed correctly or was legal.

## Filtered decision bridge

A replay is source evidence. A benchmark case is a reviewed position immediately
before a particular decision. The LLM should receive what that player knew at
that moment, then choose a move. A separate reviewer or grader evaluates legality,
strategic value and reasoning against a rubric. Exact historical-move agreement
alone is not an optimal-play score.

1. Select a source event and reconstruct the position before it. Resolve physical
   card identities, hands, zones, LP, phase, usage limits and public history.
2. Pin historical rules, banlist, card text and deck assets. Verify the position
   and real decision window; mark incomplete positions unsuitable for scoring.
3. Load that reviewed position into a harness runner. Do not start a newly shuffled
   duel to recreate a fixed decision. Checkpoint reconstruction is currently manual.
4. Call `harness_bridge.prepare_case` with the runner, actor, source sequence,
   reviewer approval and a grading rubric. It calls `runner.context(actor,
   compact=True)` and the harness's existing isolated-player validator.
5. Call `harness_bridge.run_case` with the case and a bounded model transport.
   Only the player context goes to the model; source references, grading data and
   future moves stay outside its prompt. Returned text is data, never executed.
6. Assess the response separately. Record correctness, alternatives, rationale,
   model/prompt versions, pinned asset hashes, latency and actual usage/cost
   metadata when available. Runs belong in ignored `runs/`.

The monorepo root installation provides both packages. From the repository root:

```sh
python -m pip install -e .
python -m unittest discover -s benchmark/tests -v
```

No sibling harness checkout or `PYTHONPATH` patch is needed. Current benchmark CI
uses the same commit as live play. Pinned old commits in historical reports remain
provenance for those runs. The metered runner initializes reviewed positions via
`harness.environment.positions.create_position`, using the same journal/checkpoint
format as live sessions. Its saved position locator can be resumed through the
headless API with the output's `archive` directory as `--repo` and `private`
directory as `--private-root`. All original model isolation and grading boundaries
remain required; never send the evaluator suite or expected state to a player.

Bridge cases use `{schema_version, id, source, review, player_context, grading}`;
`source.before_sequence` identifies the source boundary. `review` includes
`status: approved` and `reviewer`; keep pinning/reconstruction evidence there.
`player_context` uses the harness's existing schema, not a second game-state
format. `grading` can contain acceptable lines, illegal options and a rubric;
never pass the case object itself to a player. Store moderator snapshots separately
if needed for adjudication. They must contain all known hidden state, while player
contexts contain only information available to that actor.

`run_case` currently returns a decision, measured latency and `assessment: null`.
Bridge cases/results do not directly satisfy the three-KPI suite
and run contract; prepare the additional reviewed states, semantic moves,
journals and independent grading records described in [agentic KPIs](agentic-kpis.md).
The KPI scorer consumes these trusted artifacts but does not launch the workflow.
Automated strategic rubric grading,
checkpoint reconstruction and model provider transports remain future additions.
The [first scoped replay dataset](replay-review-stage.md) supplies approved inputs
and grading fixtures; broader replay review remains pending. Historical replays cannot evaluate a
counterfactual win rate once the model diverges; that requires actual new duels
in the harness against controlled opponents with repeated seeds and side swaps.

