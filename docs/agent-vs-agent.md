# Agent-versus-agent play

Ask the orchestrator in your current conversation to run an agent-versus-agent
duel with two selected decks. It handles rules agreement, setup, runtime calls,
private player subagents, public narration, and saving. You do not open three
sessions, run Python, or relay messages. Follow
[conversational play](codex-play.md) and the
[orchestration skill](../skills/duel-orchestrator/SKILL.md).

## Sequential private player tasks

Both decks are managed. Internal slot `human` is Agent 1 and `agent` is Agent 2;
these legacy storage names do not make either player human. Each child receives
its own hand, Extra/Side Deck, guide, and public observations. Neither receives
the opponent's hidden cards/guide or the moderator's history. The moderator knows
both managed states; no LLM context contains future draw order.

1. The orchestrator internally fills the agent-duel configuration and calls
   `duel_start` with agreed rules. Both bundles need YDK, JSON, and guide;
   `show_agent_hand: true` is rejected.
2. The moderator opens the active actor's decision window and presents its private
   options. `duel_next` returns only that actor's subagent task and permitted context.
3. Follow [isolation and failure handling](player-isolation.md). Reserve an attempt
   with `duel_player_start`, spawn only if authorized with no history/tools/files,
   save its handle with `duel_player_bind`, and bind terminal output using both
   task and attempt IDs with `duel_agent_result`.
   Do not dispatch the other player concurrently or show these menus to observers.
4. `duel_next` requests moderator review. Adjudicate legality and responses, apply
   a guarded step with the submission ID, then repeat with fresh context.
5. Report reviewed public events and the fixed spectator state display. Stop at
   uncertain rulings, pause, finish, or observer requests. Never commit game files
   unless explicitly asked.

The host orchestrator actually invokes native subagents; the Python scheduler
returns tasks without model API calls. A host lacking safe subagent/runtime tools
must explain the limitation and pause. Supplying private prompts alone does not
restrict inherited filesystem or execution tools. Use host restrictions or
context-only callbacks. The moderator must never silently choose both sides.

## Resume

The orchestrator resumes by game ID, then calls `duel_next`. Saved tasks retain
IDs and player bindings; queued intentions return for review. Both hidden states,
shuffled orders, menus, checkpoints, and execution receipts persist. Identical
result/action retries do not repeat effects. Recover storage errors before play.
Legacy sessions can use their existing direct runtime paths internally.

## Optional deployment backend

The role-bound `harness.integration.arena` remains available for hosts that manage
independent player processes internally. One runner owns the game; private role
credentials restrict players to their own context, submission, and status tools.
The orchestrator/host operates these processes and credentials; humans never
have to configure or switch player sessions to play. The
[arena MCP example](../examples/agent-duel-mcp.toml) is an administrator reference,
not the normal user workflow. Private credentials/mailboxes stay outside the repo.
Tool gates require additional host filesystem restrictions for hard isolation.

Tests cover sequential context tasks, durable task IDs, retries, checkpoint
restoration, scripted two-player callbacks, role authorization, multi-client
transport, and spectator masking. They test harness coordination; actual rules
and tactical decisions remain the LLM's responsibility.
