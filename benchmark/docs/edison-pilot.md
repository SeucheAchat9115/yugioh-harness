# First Edison agentic pilot

On October 8, 2026, six fresh native children were requested with model
`gpt-6.1-sol`, without inherited history. They proposed moderator operations or
player intentions for six authored, controlled positions. This was an assisted
harness workflow pilot, not a full match or replay reproduction.

| KPI | Passed / tested | Score |
| --- | --- | --- |
| State recreation | 3 / 3 | 100% |
| Human-move agreement | 0 reviewed replay positions | Not measured |
| Rule correctness | 6 / 6 | 100% |
| Equal-weight final score | Incomplete KPI set | Not available |

## What actually ran

The harness was pinned to commit `1d54835a8e239160f8e5dc4f01c8589506669ac0`.
Rules came from its shared basics and Edison profile, with the March 1, 2010
banlist. Card data came from its Blackwing deck snapshot. The tested card
conditions and basic rules do not depend on unresolved historical errata;
this is not certification of every description in that catalog.

Three evaluated moderator children proposed operations for declared plays:

- The starting player's compulsory first-turn draw, stopping in Draw Phase.
- Normal Summoning Shura into the requested slot, consuming the turn's summon
  and leaving an opponent summon-response window.
- Setting Mirror Force face-down into the requested slot without activating it
  or revealing its name in public narration.

The host independently reviewed the plans and applied their operation lists
through `DuelRunner.workflow.execute`. Resulting full gameplay states matched
the independently prepared states, and authoritative journals replayed correctly.
The draw child's generic `proposed_operations` envelope was normalized to the
harness's `draw` action kind; its operations were unchanged. Its first prompt
omitted the kind enum. These are assisted orchestration scores, not strict
raw-JSON conformance scores.

Three evaluated player children used the normal orchestrator task protocol:
reserve, spawn, bind the native handle, submit the intention, review and execute.
They chose:

- A legal Normal Summon instead of entering the forbidden first-turn Battle Phase.
- A legal Shura Normal Summon instead of summoning Dark Armed Dragon with only
  two DARK monsters in their own GY.
- Passing priority when Normal Summon/Set was already used and no hand monster
  had an available Special Summon procedure.

The moderator preserved opponent response opportunities. Legality was assessed
by the trusted host evaluator separately from each evaluated child, using pinned
rules/card conditions. It was not assessed by an external human referee or a
fully coded legality engine. All three declared plays also passed legality
review, producing the legality denominator of six.

## Information boundary and limits

Player children received host-condensed permitted contexts, never opponent hand
identities, future draw order or grading keys. Moderator children received only
the context needed for their declared-play task. Native children had shared
tools/files available but were instructed not to use them: this is cooperative
isolation, not a verified sandbox. No child tool use was observed. The native host
accepted the requested model selection; provider usage attestation is unavailable.

Expected states and reviews were held by the evaluator. Rules and operation
documentation were supplied to the tested model. The prompts were curated for
these basic cases; this does not measure the complete default instruction stack
or autonomous full-game orchestration. The host supplied narration/schema
normalization and translated player intentions into reviewed operations.

No replay-derived human decisions were scored. The supplied Unlimited replay
still has unresolved rules and incomplete checkpoint information. Its candidate
index is not a reviewed suite. The scorer correctly returns a null final score
when a KPI has no cases; missing coverage is not silently reweighted away.

This sample is far too small and simple to estimate competitive playing ability.
Actual suite, prompts, responses, independent grades, private checkpoints and
journals remain local, outside source control. This document publishes aggregate
results and scope only. Repeat runs require fresh model calls; rescoring saved
artifacts verifies the same attempts and is not a new model evaluation.
