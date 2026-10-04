# Natural-language decisions and internal records

Humans speak normally: “Activate Branded Fusion”, “No response”, or “Set this
card and end my turn”. The duel agent interprets each statement, checks the
current state and agreed rules, and records the confirmed decision internally.
The human never needs to write JSON or use commands.

Use [duel experience](duel-experience.md) for fixed state displays, two recommended
moves/free-text input, automatic verified no-choice progression, local-only saves,
and complete private resume checkpoints. No game commit without explicit request.

## Moderator workflow

1. Inspect the permitted view and revision. Resolve references to physical copies.
   Clarify ambiguous intent before recording. Split compound requests into separate
   decisions, preserving response windows and End Phase procedures.
2. Check legality, timing, costs, and choices. A clear declaration is the human's
   decision; no extra mechanical confirmation is required. Never invent a choice
   or treat silence as passing. Unconfirmed drafts do not change game state.
   Record compulsory/no-choice progression automatically after a complete review;
   stop at the next real human choice and explain everything that happened.
3. Prepare a private action file outside the repository with changes that happen
   now. Activation choices and costs occur at activation; effect results and
   resolution choices are recorded when due.
4. Review narration for hidden information, approve, and record once. Present the
   resulting public situation and whose decision is next.
5. Use the resulting revision for the next action. On a stale-state error, reload
   and reconsider rather than blindly changing the expected revision.

Language interpretation and legality belong to the agent. The Python helper
validates bookkeeping, not Yu-Gi-Oh! rules or optimal play.

## Private action format, version 1.0

See [action.json](../templates/action.json). Required fields:

| Field | Meaning |
| --- | --- |
| `id` | Unique decision ID, retained on retries. Duplicate submission is rejected. |
| `kind` | `activate`, `respond`, `resolve`, `pass`, `summon`, `set`, `move`, `search`, `shuffle`, `draw`, `attack`, `damage`, `phase`, `turn`, `reveal`, `usage`, `choice`, `finish`, or `correction`. |
| `actor` | `human`, `agent`, or `moderator`. |
| `expected_revision` | Current integer revision, starting at zero. |
| `moderator_approved` | Explicit `true` after legality/timing review; an attestation, not rules-engine certification. |
| `public_summary_reviewed` | Explicit `true` after reviewing narration for hidden information. |
| `public_summary` | Public narration without hidden identities, private reasoning, or future draws. |
| `changes` | Array of `{path, before, after}` replacements. Empty for a decision with no state changes. |

Optional `automatic` is an explicit boolean. If true, `option_review` must contain
`complete: true`, integer `meaningful_choices: 0`, a nonempty reason, and basis
`open-state-verified`, `public-rules-verified`, or `human-confirmed-none`. Blind
rejects open-state proof. This records a moderator-reviewed compulsory/pass-only
step, never a guessed strategic action or pass with unknown options.

Paths are arrays of object keys and nonnegative indexes, such as
`["players", "human", "lp"]`. Existing values must match `before` exactly.
Paths must exist. Add custom tracking by replacing existing `effect_usage`,
`restrictions`, or `pending_effects` containers. Overlapping paths are rejected.
`game_id`, `mode`, `presentation`, and `revision` are protected.

Move a card by replacing its source and destination containers in one action,
preserving `instance_id`. Face-down cards use `hidden: true`. Blind human hidden
zones remain `null` with counts only; unknown face-down human cards contain only
anonymous instance/owner/position/hidden fields. Keep legally observed identities
in separate observations without importing unknown human cards.

Chain entries must be public; refer to hidden targets by anonymous instance IDs.
`pending_decision` is `null` or an object with public `actor` and `window` fields.
Further private decision details are omitted from perspective views.

## Activation and resolution example

“Activate Branded Fusion” appends one chain link and sets a pending response.
It does not record the future Fusion Summon or material selection. Those happen
if and when the effect resolves.

`activate` and `respond` append exactly one link. `pass` leaves the chain intact.
The moderator tracks all required responses and updates the pending decision;
clear it only when the applicable responses are complete. `resolve` requires no
pending decision and removes exactly the last link with its actual results.
Record a choice due during resolution first without prematurely removing the link.
Collect resulting triggers for their next window. These checks do not implement
priority, simultaneous triggers, or complete resolution rules.

Generate shuffle orders once using system randomness and record the resulting
private array; replay restores it without shuffling again. For blind human
draws/searches/shuffles, the human performs the private operation; record counts
and legally revealed cards only. Include costs, usage, and restrictions when they
become applicable. Phase/turn updates include applicable resets and delayed effects.

## Recording and recovery

The agent runs these commands on the human's behalf, using the actual game path:

```sh
python -m harness.engine.actions record --state /tmp/duel-private-001/state.json --game-dir games/tcg/example-001 --action /tmp/duel-private-001/action.json
python -m harness.engine.actions replay --state /tmp/duel-private-001/state.json --game-dir games/tcg/example-001
```

State and action drafts must be outside the repository. New sessions initialize
an adjacent private `journal.json`. An older session without one uses its current
state as the baseline; earlier manual actions cannot be recovered retroactively.

The authoritative private journal holds the baseline, action changes, timestamps,
and before/after state hashes. Private `state.json` is a cache. Public `state.json`,
`events.json`, and `actions.md` are regenerated projections. If interrupted after
the journal save, run `replay` to repair projections. Check the action ID before
retrying. `session.py draw` records in the same journal. Do not edit journaled
state directly. Use one moderator writer; concurrent writers are unsupported.
Hashes detect inconsistent replay, not malicious history rewriting.

Every update refreshes a private, self-contained `checkpoint.json` with complete
state/journal, configuration, rules/deck snapshots, and current decision packet.
The decision renderer adds numbered choice/card mappings before input. Restore
with `checkpoint.py` into a fresh private directory; do not restart the duel.
Prefer durable workspace storage outside the repo for long pauses. “Publish” in
the Python helper means writing local public projections; it performs no Git or
GitHub operation. No automatic commit at a save, turn, pause, or game end.

Public events contain only revision, ID, kind, actor, timestamp, and reviewed
summary. Private change payloads are excluded. Free-text narration requires
moderator review because its safety cannot be proven automatically. Archive
private records only by agreement. Record an agreed `correction` with reason and
explicit repair changes rather than deleting events; do not exploit information
gained from an invalid play.

## Scope

This provides consistent decisions and recoverable updates. It is not an automatic
language parser, card-effect engine, complete state schema, or full simulator.
The agent still judges legal moves, response windows, summon procedures, victory,
and relevant counters under the agreed rules.
