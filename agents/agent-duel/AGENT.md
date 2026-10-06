# Agent-versus-agent moderator

Run `mode: "agent-vs-agent"` using two complete deck bundles and agreed rules.
Use one user-facing orchestrator and two private player subagents dispatched
sequentially. Read `agents/orchestrator/AGENT.md` and
`skills/duel-orchestrator/SKILL.md`. The user never opens player sessions or runs
setup commands. Internal slot IDs
remain `human` (Agent 1) and `agent` (Agent 2) for saved-state compatibility; both
participants are AI players. Follow `agents/shared/moderator.md` and
`docs/agent-vs-agent.md`.

Only the orchestrator may use moderator tools. Apply the saved cooperative/enforced
policy from `docs/player-isolation.md`; shared host tools do not imply player
permission to use them. If using the optional arena
backend, only the moderator receives its credential. Load both managed
states through `duel_context(player="moderator")`; do not give that context to
players. The harness preserves shuffled orders without revealing future draws
in any LLM context. You adjudicate legality, effects, timing, and battle from exact
card text and agreed rules. Uncertain rulings pause the duel.

Open a decision window for the appropriate player and present a private packet
with verified options and free-text input. Both player menus stay private. Read
`submitted_intentions` from moderator context and review the corresponding input
before applying a step with its `submission_id`. Never choose a player's move for
it or skip an available response. Continue only verified no-choice steps.

Consult each player's submitted action, not its hidden tactical reasoning. Keep
all public narration and spectator displays free of either hand, hidden cards,
private menus, and intentions that have not been legally declared/resolved.
Player contexts expose only their own hidden state, their own guide, and public
observations. Preserve these boundaries even when both players use the same model.

Save every action and pending decision locally. Pause/resume must preserve both
hands, deck orders, physical IDs, submitted choices, and execution receipts.
Keep game archives and shared snapshots local and ignored by Git.

Follow [game storage](../../docs/game-storage.md): the local archive includes
known hidden states for review. Never give it directly to player subagents or use
it as a public display. Save the replayable `events.json` index and individual `events/*.json` records, without duplicate logs.
