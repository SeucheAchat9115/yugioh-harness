# Whole-match review and scoped action suite

The Aco77 versus sdesowitz02 Duelingbook match has 554 source entries across two
games. Extraction produced 207 review work items, not 207 certified strategic
choices. A follow-up evaluator disposition pass now covers **all 185 previously
pending items**. No model was run on the expanded suite during this review.

## Review result

| Coverage | Result |
| --- | --- |
| Source entries / review work items | 554 / 207 |
| Previously pending items reviewed | 185 |
| Newly approved scoped checkpoints | 14 |
| Newly excluded bookkeeping/substeps | 77 |
| Reviewed but blocked items | 94 |
| Total approved checkpoints, including original four | 18 |
| Total exclusions, including original 18 | 95 |
| Scoring suite | 36 tasks: 18 state updates and 18 human choices |
| Rule correctness denominator for a complete run | 36 independently graded attempts |
| Stored player packets | 112: 18 runnable, 94 blocked |

The [manifest](../benchmarks/review/db-json-40753-85958923/manifest.json) pins the
source, assets and counts. The [review index](../benchmarks/review/db-json-40753-85958923/review-index.json)
links every work item. The evaluator-only [follow-up dispositions](../benchmarks/review/db-json-40753-85958923/review-decisions.json)
bind each of the 185 findings to its before-observation and recorded-action
hashes. Each has a reason and, where blocked, concrete next steps. The
[timeline](../benchmarks/review/db-json-40753-85958923/timeline.json) preserves all
554 entries, including excluded observations.

The review is a **Codex evaluator preparation review**, not external expert
certification. A completed disposition means an item has been assessed; it does
not mean its state, rules or decision window have been certified for execution.
Blocked packets remain `runnable: false` and the loader rejects them.

## Approved checkpoints

All approvals are in game 2. Game 1's effect bookkeeping and source discrepancies
still prevent certification of complete checkpoint gameplay states.

| Source index, zero-based | Recorded action | Endpoint for state recreation |
| --- | --- | --- |
| 333 | Normal Set D.D. Warrior Lady M3 | Opponent `after_set` |
| 334 | Set Mirror Force S3 | Opponent `after_set` |
| 335 | Set Dark Bribe S4 | Opponent `after_set` |
| 336 | Set Soul Exchange S2 | Opponent `after_set` |
| 337 | Request ending turn | End Phase, opponent response |
| 359 | Attempt Normal Summon Stratos M3 | Opponent summon-negation decision |
| 367 | Set Return from the Different Dimension S3 | Opponent `after_set` |
| 368 | Set Mystical Space Typhoon S4 | Opponent `after_set` |
| 369 | Set Monster Gate S2 | Opponent `after_set` |
| 376 | Request ending turn | End Phase, opponent response |
| 383 | Attempt Normal Summon Breaker M3 | Opponent summon-negation decision |
| 462 | Request ending turn | End Phase, opponent response |
| 467 | Set Solemn Judgment S5 | Opponent `after_set` |
| 468 | Set Dimensional Prison S1 | Opponent `after_set` |
| 469 | Request ending turn | End Phase, opponent response |
| 490 | Request ending turn | End Phase, opponent response |
| 495 | Request ending turn | End Phase, opponent response |
| 501 | Attempt Normal Summon Snipe Hunter M3 | Opponent summon-negation decision |

These are **fixed checkpoints reset independently for each task**. Prior recorded
resolution outcomes establish observed inventory, not proof that every preceding
human operation was legal. For example, later approved game-2 states use recorded
Card Destruction draws rather than guessed deck order. Breaker has already left
the field, so its missing earlier counter bookkeeping does not remain an active
card-state ambiguity at those later boundaries. Brain Control's temporary control
has no surviving target once Breaker leaves the field. Dimensional Fissure stays
face-up and must be preserved; these task endpoints do not resolve a replacement.

Normal Summon cases stop at the **attempt**, consume the Normal Summon allowance
and await `summon_negation`. They do not certify successful summoning, place
Breaker's counter, activate Stratos's optional trigger/search or Snipe Hunter's
ignition effect. Those actions need actual subsequent decisions. End-turn requests
enter End Phase with `end_phase_response`, preserving turn and active player until
opponent input. The endpoints are explicit harness task conventions; unlogged
historical passes are not invented.

## What remains blocked or excluded

The 94 blocked items have case-specific findings. Common issues include:

- Search selections lack the complete remaining own-deck choice list. A later
  observed search result cannot reconstruct the menu available beforehand.
- Game 1 needs Gold Sarcophagus's countdown, Scapegoat token attributes,
  equip/control relationships, Dasher's temporary effects and effect usage.
- Source 21 and 245 return a Spell directly from the field during DMOC recovery,
  omitting its GY transition. Review the resolution/trigger boundary rather than
  silently fixing it.
- Game 2 Breaker sources 383–386 omit counter placement/removal. Later effect,
  response and attack cases cannot assume those updates from an empty ledger.
- DMOC and Brain Control cases depend on historical card text/rulings. Complete
  overrides remain deferred as requested; no new historical text was invented.
- Source 313 returns absorbed Dekoichi to the logged controller rather than its
  owner. Affected subsequent game-1 states remain blocked.
- Targets of opponent face-down cards must use visible locations, not the card
  names exposed only in evaluator private logs.

The additional 77 exclusions are phase bookkeeping, duplicated declarations and
serialized cost/summon/recovery steps. For example, Destiny Draw activation and
its discard cost form one action; Return from the Different Dimension's five
summon operations belong to one simultaneous resolution. They remain useful
source evidence for future grouped cases, rather than separate easy free choices.
Excluding phase bookkeeping is this suite's scope choice, not a claim that phases
have no decisions or response windows.

Many blockers require evaluator authoring work rather than more information from
the user. Complete own-deck inventories, ambiguous source corrections and any
historical ruling not already sourced may require additional evidence. The
repository does not claim that all remaining items are permanently unscorable.

## Information and scoring boundaries

The [suite](../benchmarks/review/db-json-40753-85958923/suite.json) contains two
three-KPI tasks per approved checkpoint. State recreation compares complete
specified gameplay roots to the declared-action endpoint. Human agreement compares
semantic action/card/position, ignoring interchangeable empty field slots and
wording. Legality is independently reviewed; runtime acceptance earns no legality
credit. Unknown-card or historical-text-dependent alternative moves remain pending
rather than guessed. Agreement does not prove optimal play or human expertise.

The evaluator-only [grading file](../benchmarks/review/db-json-40753-85958923/evaluator.json)
contains initial/reference states and findings. Only `player_context` from an
approved packet goes to an isolated model. Packets are built with the harness's
perspective filtering and validated by its isolated-request validator. Opponent
hands and face-down identities, grading keys, future actions and future draws
are absent. New checkpoints retain all preceding public logs within their game
so set ages and public summon history are not lost to a four-event truncation.
The original four packets are preserved. Publishing grader files does not authorize model repository access.

Unknown Deck/Fusion/Side identities remain anonymous count carriers. No identity,
shuffle lineage or deck order is guessed. The approved operations preserve them.
Stop before resolving operations that require unavailable identities. This is
neither uninterrupted live-duel simulation nor complete deck-legality certification.

Rules are pinned to harness commit `d3f5a4193cdc81dea033742f9c639b63f21427eb`:
Perfect Circle profile, September 2007 community TCG pool, with profile precedence
over shared basics. Current YGOPRODeck metadata is provisional where historical
text matters. Exact assets are pinned in the manifest.

## Run, reproduce and continue

Use the [harness integration](harness-integration.md). The trusted evaluator loads:

```python
from yugioh_benchmark.review_cases import load_reviewed_case
bridge, initial_state = load_reviewed_case(
    "benchmarks/review/db-json-40753-85958923",
    "db-json-40753-85958923-before-000502-choice",
)
```

For player choices use `harness_bridge.run_case(bridge, bounded_transport)` to
send only filtered context. For state tasks, provide the declared action through
the normal sole-moderator workflow, not the expected-state patch. Record actual
journals and independently normalize/review attempts. Keep live saves, model logs
and execution journals outside Git. Follow the [KPI scorer contract](agentic-kpis.md).
A model transport and actual execution are required to collect new v2 attempts.

The earlier cooperative GPT-6.1 Sol pilot ran only the original four opening
checkpoints. Its 70.83% result does not apply to the expanded suite, is not a
full-game score, and used host assistance. Subsequent
[expanded assisted pilots](results/2026-10-08/README.md) report 78.70% for Sol and
54.63% for Luna across all 36 scoped tasks. These are independent checkpoint
evaluations, not continuous games; delivered prompts differed between models.

Reproduce the authored fixtures and verify them offline:

```sh
PYTHONPATH=../yugioh-harness python scripts/prepare_replay_review.py
PYTHONPATH=../yugioh-harness python -m unittest discover -s tests -v
```

The generator applies **explicit, hash-bound review records**. It does not infer
approvals from successful simulator operations. Further approvals require new
source-specific authoring records and checked reference states. The 94 blocked
cases can be revisited using their listed next steps; exclusions must be grouped
into appropriate effect/phase tasks before reconsidering them for scoring.
