# Optional structured intentions

`harness.runner.intents` provides the opt-in `intent-v1` initiation interface for
players and checkpoint evaluations. Players choose semantic actions and physical
card IDs instead of authoring privileged journal operations. The moderator remains
the sole writer and interprets rules, costs, effects and response opportunities.
The existing free-text live workflow remains supported.

A player can return, for example:

```json
{"action":"set","card":"agent-hand-1","zone":"S-3"}
```

`M-3` and `S-3` mean the third configured field slot. The translator converts them
to zero-based storage indexes. It rejects unavailable slots, wrong card locations
and a consumed Normal Summon/Set allowance. The prompt constant `POLICY` describes
the supported action shapes: Set, ATK Normal Summon, activation, pass, phase
request, End Turn request, and an explicit unsupported intention.

Follow the ordinary [orchestration](orchestration.md) and
[player-isolation](player-isolation.md) lifecycle: present a saved decision,
reserve and bind the player attempt, receive its intention, independently review
legality and public narration, then execute through `runner.workflow.execute`.
`parse_intent(response)` accepts one bounded JSON object;
`translate_intent(runner.state, intent, actor=..., reviewed_activation=...)`
returns an **unapproved** action proposal. Only the trusted moderator adds
`moderator_approved` and `public_summary_reviewed` after review. Never accept
these flags or state operations from a player.

For reviewed activations or Tribute Summons, `reviewed_activation` supplies an
effect description and `cost_operations`. Costs are restricted to negative own-LP
operations or consuming precisely the player's selected `cost_cards` into its own
GY/banished zone. This is structural validation; it cannot prove the amount,
required tributes, targeting legality or card timing. The referee must check those
against the pinned rules and card text. The translator does not repair the player's
cost choices.

Each supported action stops at an opponent response window. Normal Summons stop
at summon negation, before confirmation or triggers. End Turn enters End Phase and
opens a response, preserving turn and active player. Activations create a pending
chain initiation; they never resolve it. Battle resolution, chained responses,
special summons, multi-step procedures and uncertain rulings require the existing
moderator workflow. This module is bookkeeping, not a coded effects engine.

The companion benchmark uses a tool-free, bounded provider transport and an
independent stateless referee call. Native subagents remain the default live-play
workflow. Evaluation journals and provider logs belong outside source control.
