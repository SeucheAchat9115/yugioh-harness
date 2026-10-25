# Benchmarks from recorded harness duels

`harness-objectives-v1` evaluates a single decision using the same persistent
writer, visibility projection, semantic intentions and reviewed action translator
as headless duels. The first dataset contains six scoped Edison checkpoints from
`max-edison-20261023`. A future GUI can use the same environment boundary; this
change adds no GUI, Gymnasium environment or coded card-effect engine.

## What ships

| Source revision | Objective | Reviewed initiation |
| --- | --- | --- |
| 18 | Preserve LP and cards when MST targets Bottomless | Pass |
| 46 | Stop Ryko's attempted Flip Summon before its FLIP effect | Solemn Judgment, pay 4000 LP |
| 60 | Protect two cards from Celestia's pending destruction | Chain Starlight Road |
| 67 | Avoid an illegal response to Wulf's revival | Pass |
| 88 | Keep Lyla's targeted Spell/Trap on the field | Tribute Stardust Dragon to negate |
| 136 | Prevent lethal Stardust battle damage and preserve Garoth | Banish Necro Gardna as its own cost |

These are deliberately small goal-directed problems, not an assertion that every
reference action is optimal in a full duel. Revision 88 deliberately permits a
reviewed response different from the human's recorded pass. Acceptable semantic
alternatives belong in the private grading list and must be explicitly reviewed.
The present six cases each have one reviewed signature. Card IDs, exact costs,
phase and response timing still have to pass independent legality review and
shared-runtime execution. The reviewer is identified as Codex; this is automated
scoped author review, not expert certification of the source duel.

The importer preserves the archive's **partial** decision-evidence label. It
requires an actual saved decision packet and a matching pending actor. It does
not invent absent menus, fill missing intentions, or turn a queued continuation
into a certified boundary. For example, the later Ryko/Shura continuation and
End Phase ordering are not included. The source's Wulf response coaching wrongly
offered MST targeting itself; that coaching is discarded, and the scoped review
records the problem. Archive import does not approve the remaining duel.

## Maintainer workflow

The orchestrator can run these steps internally when a user requests a benchmark.
With the root distribution installed:

```sh
yugioh-benchmark inspect-harness replays/edison/max-edison-20261023/replay.zip

yugioh-benchmark prepare-harness replays/edison/max-edison-20261023/replay.zip \
  --reviews benchmark/benchmarks/reviews/max-edison-20261023.json \
  --output benchmark/imports/edison-reviewed

yugioh-benchmark evaluate benchmark/imports/edison-reviewed \
  --output benchmark/runs/edison-comparison \
  --models MODEL_A MODEL_B --referee-model REFEREE_MODEL
```

`inspect-harness` returns unreviewed boundaries and information gaps. Both schema-4
directories and self-contained ZIPs are supported. ZIPs are bounded and checked
for traversal, symlinks and duplicate paths. The reader cold-verifies the entire
archive's event, configuration and snapshot hashes. Reviews pin the exact index,
select recorded revisions, state public facts and objectives, and explicitly
approve answers, costs, rationale and evidence. Import alone never creates an
approved case. Output paths must be new; existing cases/runs are not overwritten.

The selected review definitions are versioned under `benchmarks/reviews/`.
Full checkpoint states and filtered player packets are generated locally under
ignored `imports/`; no additional hidden-state fixture, live game save or raw
model-run log is committed. Tests generate their datasets in temporary storage. The exact rules and card catalogs
come from the original archive, including its embedded dated banlist. No current
API card text or today's rules files are substituted. A slot notice distinguishes
original setup labels from the evaluated checkpoint's labels. Historical text
or rulings outside the reviewed scope can still require further review.

## Privacy and execution

Full source archives, checkpoint hidden states, answers and reference costs are
trusted evaluator material. Players and the independent referee receive only the
runtime's permitted player projection, visible card text, complete pinned rules
and reviewed public facts. The player also sees its public objective. Neither
receives source menus, recommendations, guides, future actions, outcomes, reference
answers or shuffled future draw order. Descriptive evaluator case IDs are replaced
with opaque position IDs in player state to avoid tactical hints.

The evaluated source player is mapped to `agent`, preserving physical IDs and
remapping structured ownership, controllers, pending decisions and targets. The
checkpoint starts at revision zero under a fresh stateless, tool-free enforced
transport. The original duel's cooperative isolation remains recorded in the
archive; this stronger benchmark policy is an explicit transformation. On load,
the player packet is recomputed using the live runtime and compared, even if
someone has recomputed its packet digest. Archived chain prose is omitted;
structured public links/costs/targets and reviewed public facts describe the window.

After a player submits exactly one intention, a separate stateless referee judges
that exact candidate against visible state and pinned rules. It does not see the
objective answers or repair missing cost/target selections. A valid reviewed
activation pays explicit costs and opens the next response window through the
shared writer. Chaining, off-turn responses and self-Tribute/self-banish costs
are generic bookkeeping capabilities, not card-specific handlers. Passing never
resolves a chain or pending attack. All six cases stop before resolution.

## Scoring and comparisons

Objective success is 1 only when the normalized semantic choice meets an approved
goal, the referee accepts it, and the exact candidate executes in the harness.
Incorrect choices, invalid actions, missing attempts and timeouts score zero.
Missing or uncertain referee grades keep the final score pending. The score is
100 times mean objective success. Rule correctness is a separate referee-dependent
diagnostic; it is not an extra weight that rewards an unsuccessful goal.

The scorer verifies bound normalization/legality evidence, initial-state hashes,
the replayable one-action journal, the submitted intention and the executed plan.
Reports retain prompts, model IDs, usage, observed call times, costs when known,
referee identity, protocol, suite, harness and evaluator fingerprints. There are
no automatic retries or hidden rerolls. Paid evaluation requires configured model
credentials and explicit model IDs; offline scripted transport tests are **not**
reported as model performance.

The legacy `structured-checkpoints-v1` three-KPI suites and their historical
scores remain available. They are not comparable to this new objective metric.
The legacy three-KPI plotting command rejects objective reports explicitly;
read `comparison.json`, per-model `report.json`, `score.json` and `run.json` for
this track. Six positions from one duel cannot establish competitive strength,
whole-duel referee accuracy, generalization or reinforcement-learning rewards.
The archive's remaining decks are unordered inventories, so these checkpoints
must not be resumed as counterfactual full games with supposed future draws.
