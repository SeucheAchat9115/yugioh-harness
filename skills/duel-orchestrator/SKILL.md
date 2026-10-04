---
name: duel-orchestrator
description: Run all duel modes through one conversational moderator and sequential private player subagents, without user terminal steps.
---

# Single-conversation duels

Apply when the user asks to start, play, watch, pause, or resume a duel. The user
speaks only to the orchestrator. Read `agents/orchestrator/AGENT.md`, shared
moderator instructions, and the relevant open/blind/agent-duel policy.

## Setup

1. Verify the host can run repository tools and spawn context-isolated children.
   Use a configured conversational MCP service if available. Otherwise the
   orchestrator can launch that service through its own execution tools and use
   the local stdio MCP protocol. Keep one process/writer alive for the session.
   This is internal automation; do not give the user commands to execute.
2. Discover complete bundles with `duel_decks`. Ask conversationally for missing
   mode, deck selection, rules/banlist, starting player, and settings. Reuse prior
   agreements. Populate `templates/duel-config.json` internally. Do not assume
   current or historical rules. In blind mode take human counts, never their YDK
   or hidden card identities. A user can select by deck name or linked YDK.
3. Start with `duel_start(config, rules_text)`. The runtime assigns an ID if absent,
   creates private storage outside the checkout, snapshots rules/decks, and deals
   managed hands. Discover saved sessions with `duel_games` when needed and resume with
   `duel_resume(game_id)` instead of restarting. Resolve IDs internally; the user
   can simply ask to continue the previous duel.
   Keep the game ID for conversational resumption. Do not launch competing writers.

## Repeat until a human question, pause, or finish

Call `duel_next` after setup, presentation, input, or an applied action:

- `kind: moderator`, `stage: next_step`: adjudicate the next window from supplied
  moderator context. Use `duel_step` to open a window, then `duel_present` to save
  its reviewed options. For compulsory steps require a complete no-choice review.
- `kind: human`: show the returned fixed state display in this conversation.
  Give two distinct legal recommendations when available; free text is valid.
  Submit their answer with `duel_human_reply(decision_id, request_id, response)`.
  Keep stable IDs and identical payloads for retries; the user never types IDs.
- `kind: subagent`: follow `docs/player-isolation.md`. Verify the actual host
  boundary: no parent history, tools, or filesystem access, or use the context-only
  model adapter. Reserve with `duel_player_start` and a stable request ID. Spawn
  only when `dispatch_authorized: true`; duplicate reservations never authorize
  another child. Give only the permitted context/policy, correlate by attempt ID,
  and immediately save the native handle through `duel_player_bind`.
  Await a terminal response and call `duel_agent_result(task_id, attempt_id,
  response)`. Review it before applying anything. A retry uses a new attempt ID.
- `kind: subagent_wait`: keep the same host child; poll with bounded waits and
  fresh status. Do not spawn again or advance the decision while it is running.
- `kind: subagent_failure`: show the safe fixed state and report the failure.
  Interrupt the host child and confirm it stopped with `duel_player_fail` and
  `terminated: true`. Only then can a new bounded attempt start. Never mark a
  child terminated merely because a deadline elapsed. After three attempts, stop
  and pause; no auto-pass or substituted moderator move.
- `kind: moderator`, `stage: review_intent`: check exact card text, costs, timing,
  materials, restrictions, and responses. Apply reviewed operations through
  `duel_step`, using the intention's request ID as `submission_id`. If clarification
  is needed, present a new decision ID; never alter a persisted menu in place.
- `kind: paused` or `finished`: show permitted state and reviewed events. Save
  locally; never commit automatically.

Every outward gameplay message must include the fixed state display; private
subagent work stays internal. In agent-versus-agent mode report public spectator
state using the decision renderer, without private menus. Accumulate reviewed
intervening events and explain them when reporting the next choice. Stop at every
actual human option; unknown blind responses cannot be auto-passed.

## Safety and resumption

Only the moderator gets conversational MCP tools. Player children get permitted
context and return intentions. The service schedules work but does not itself
call model APIs or spawn vendor agents: the host orchestrator does that. Native
Codex/Claude/Gemini facilities differ; use the actual installed tools, never
invent a subagent command. Plain chat apps without runtime/subagent access cannot
run this workflow merely by reading the repository.

Private checkpoints include managed hands/orders, pending menus, submissions,
player task bindings, and execution receipts. On reconnect, resume the game and
call `duel_next`; outstanding tasks, attempt IDs, deadlines, and child handles
remain saved. Reconcile any existing child before retrying. Identical result/action
retries are safe. Recover storage errors before continuing; never repeat a
recorded effect. Do not publish game files without explicit authorization.

Legacy saved games created before the lobby have no `session.json` locator. The
orchestrator may use their existing private state/game paths with the direct
runner or arena, preserving the checkpoint and journal. Never initialize a new
duel to replace them. Python entry points and role credentials are backend
interfaces operated by the orchestrator, not steps the human performs.
