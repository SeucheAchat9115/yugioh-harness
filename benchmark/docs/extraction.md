# Extracting and reviewing replay states

Native JSON importing preserves observations. The separate `extract` command
reconstructs **unreviewed, reviewer-only** before/after snapshots from explicit
logs. It does not interpret card effects, create legal-action lists, run a model
or produce a KPI score. A duel player can ask the orchestrator to perform these
steps; the commands below are maintainer instructions.

## Generate the extraction

Install the repository as described in the README. For the bundled replay:

```sh
yugioh-benchmark extract replays/db-json-40753-85958923 --output inspection/db-json-40753-85958923
```

For a new match, first follow [replay acquisition](acquisition.md) and
[native JSON importing](native-json.md), then pass the new bundle to `extract`.
The command validates the bundle's hashes and derived annotations, runs offline,
creates a new output directory and refuses to overwrite an existing directory.
Use a new directory when repeating an extraction with changed code.

Outputs:

| File | Contents |
| --- | --- |
| `states-and-actions.json` | Every source event, recorded action and before/after observed state |
| `decision-review.json` | Candidate positions selected by native action kind |
| `summary.json` | Source digest, extractor version, counts, limitations and transition gaps |

The full artifacts contain both private hands and outcomes. Keep them under
ignored `inspection/` and never give them to a player agent. Only the small
[selected extraction summary](../benchmarks/extractions/db-json-40753-85958923.json)
is committed for the current replay; regenerate its snapshots locally. The
source replay, selected fixture and attribution remain unchanged.

## What is reconstructed

The extractor tracks hand **name multisets**, field slots and recorded ownership,
graveyard and banished entries, deck counts, explicit counter/stat updates,
turn/phase changes, concessions and LP changes. Opening hands come from the
batched private draw logs. Sets use the private name recorded at that moment;
future reveals are not used to fill earlier unknown cards. Logged hand counts
and shuffle hand sizes are checked against the observed inventory.

LP baselines are derived from the source's signed and absolute LP updates.
This uses later observations for a reviewer audit; the baseline must be checked
against the selected format before becoming player setup. Field runtime
references are retained, including recorded control transfers, but no physical
copy identity is inferred through hand/deck shuffles. Source log indexes are
zero-based; event sequence numbers are one-based.

Unseen deck identities/order and sided-in lists stay unknown. Card text does not
supply unlogged effect outcomes. Token properties, default card stats, attachments,
summon negation and response windows still need review. A snapshot after a native
summon operation is not automatically the resolved state of a successful summon.
The extractor preserves suspicious operations and flags inconsistencies instead
of repairing the source with an assumed ruling. Later records in the same game
carry `unresolved_prior_source_indexes`; a new game resets state independently.

For this replay, there are **554 events across two games and 174 candidates**,
including one candidate after concession. One explicit ownership conflict occurs
at source index **313**, game 1, **14:12**: Dekoichi, originally owned by Aco77,
is recorded as returning to sdesowitz02's hand after a control change. Resolve it
or exclude checkpoints affected by it. Successful mechanical checks do not mean
all other positions are complete or legally certified.

## Prepare a small scored dataset

1. Select clear positions before concession. Read their source events and
   preceding context; do not treat every phase change, draw, or manual operation
   as an independent strategic decision. Chat declarations, effect targets and
   multi-operation plays can require additional boundaries beyond the automated
   candidates. Resolve flagged gaps or exclude affected checkpoints.
2. Verify the state and identities at each boundary. Establish physical-copy
   identities where the harness needs them, token properties, field attachments,
   effect availability and prior-turn facts. Document unresolved deck information
   and narrow the case scope where a complete deck is unavailable. Never guess
   missing cards or assume different runtime namespaces are identical.
3. Create a **player packet** containing only that player's hand, public state,
   permitted history and pinned rules. Hide opponent hands/face-down names,
   unseen deck order, future draws/actions, recorded expected moves and grading
   keys. Review information availability at that exact decision point.
4. Store the grading material separately. For **state recreation**, specify the
   player-declared action and expected resolved state/journal changes. For
   **human-move agreement**, specify the reviewed semantic human choice without
   feeding it to the player. For **rule correctness**, identify the actual legal
   decision/response window, pinned format/banlist and card text used by the
   independent grader. A recorded action is evidence, not proof of legality.
5. Mark cases reviewed only after state, visibility, rules, decision boundaries
   and grading are checked. Follow [harness integration](harness-integration.md)
   and [three-KPI evaluation](agentic-kpis.md) to collect model attempts, journals
   and independent grades. Keep model logs/game saves local.

The selected format is user-declared Perfect Circle 2007. Historical text
completion is deferred for the current pilot; legality results affected by
modern versus historical text must remain provisional. This extraction does
not change that status or claim competitive playing strength.

Run the offline extraction checks with:

```sh
python -m unittest discover -s tests -p test_extraction.py -v
```
