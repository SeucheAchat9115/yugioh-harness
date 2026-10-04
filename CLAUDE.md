# Yu-Gi-Oh! conversational harness

Read `AGENTS.md` for repository and gameplay policy. For a duel, load
`agents/orchestrator/AGENT.md` and `skills/duel-orchestrator/SKILL.md`, then the
selected mode policy. The user speaks only to you, the orchestrator. Handle
runtime/setup/resume internally; never ask players to run Python or open separate
sessions. Spawn active player children sequentially with only their permitted
contexts and no inherited parent history. Human decisions stay in this chat.
Verify the actual host has execution/MCP and safe native subagent support.
