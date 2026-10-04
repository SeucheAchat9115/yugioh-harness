# Agent-versus-agent play

`agent-vs-agent` is a managed hidden-information mode with two AI players and an
LLM moderator. Both decks are initialized and saved by the harness. Each player
knows its own hand, Extra/Side Deck, and guide plus public observations. Neither
knows the opponent's hidden cards or guide. The moderator can inspect both managed
states; no LLM context contains future draw order.

The legacy internal IDs remain `human` = Agent 1 and `agent` = Agent 2. These are
storage slots, not roles in this mode. Existing open/blind human games retain their
original behavior and require no migration.

## Configure and start

Use [agent duel configuration](../templates/agent-duel.json), choosing format,
banlist, rules version, deck bundles, first player, and settings before starting.
`human_deck` is Agent 1's bundle; `agent_deck` is Agent 2's bundle. Both require
`deck.ydk`, `deck.json`, and `guide.md`. `show_agent_hand: true` is rejected.

```sh
python -m harness.engine.session start --repo . --config /workspace/duel-config.json --private-dir /workspace/duel-private/agents-001
python -m harness.integration.arena --state /workspace/duel-private/agents-001/state.json --game-dir games/tcg/agents-001 --private-dir /workspace/arena-private/agents-001
```

Replace paths and IDs with the actual configuration. The arena owns the only
persistent runner. It prints readiness and credential **paths**, never secret
values. Three private files are created: `player_1.json`, `player_2.json`, and
`moderator.json`. Credentials and local mailboxes have private filesystem modes
and must remain outside the repository.

The arena uses atomic local mailbox files with short polling intervals, so it
works in restricted environments that prohibit socket binding. It serializes
requests against one authoritative writer and uses per-role credentials to
restrict the tool interface. It requires no network listener or model SDK.

## Three independent Codex sessions

Use [arena MCP examples](../examples/agent-duel-mcp.toml) in three separate Codex
configurations/conversations. Each session loads exactly one server block with
its own credential path:

- Agent 1 reads [player instructions](../agents/agent-duel/player.md) and receives
  only the Agent 1 credential.
- Agent 2 reads the same instructions and receives only the Agent 2 credential.
- The moderator reads [moderator instructions](../agents/agent-duel/AGENT.md) and
  receives only the moderator credential.

Start the arena before enabling the MCP gateways. Each gateway connects to that
runner rather than loading a second copy of the game. Player sessions expose only
context, submit, and status tools; the server rejects other perspectives and
moderator operations even if a client forges a request. The moderator retains
all six workflow tools.

Keep player conversation histories separate from the moderator and one another.
Do not grant player sessions direct filesystem access to private state, mailboxes,
or other roles' credentials. Tool restrictions do not sandbox unrelated filesystem
or execution tools; enforce those limits in the host environment, or use API
callbacks that receive only the supplied context. Sharing one unrestricted Codex
conversation across all three roles does not provide hidden-information isolation.

## Play workflow

1. The moderator uses `duel_step` to open Agent 1 or Agent 2's decision window,
   then `duel_present` to persist its private choices and decision ID.
2. The active player gets its own context, chooses an action, and uses `duel_submit`.
   The other player receives no private prompt. Status reports only its own pending
   decision and receipt statuses.
3. Moderator context includes `submitted_intentions`. Review the input, then apply
   a step with its `submission_id`. Preserve the next response/choice window.
4. Repeat for both players, continuing verified no-choice steps automatically.
   Public/spectator contexts and completed-loop output hide both hands and menus.

An observer can request `duel_context(player="public")` through the moderator.
All game updates remain local. Ending an AI duel does not authorize a commit.

For application hosts, `DuelLoop(runner, moderator_callback, players)` runs the same
workflow. Supply both `human` and `agent` adapters; one missing adapter is rejected
in this mode. Use independent LLM clients/histories. Each adapter receives only
its permitted context; the moderator callback receives both managed states.

## Resume and recovery

Stop clients before stopping the arena. Restart the arena using the same private
state and arena directory; role credentials are reused for that game. Shuffled
orders, both hidden states, menus, queued inputs, and retry receipts are preserved.
After a storage failure, only the moderator may recover. Retry the original
submission/execution ID rather than repeating effects. If the runner cannot load
inconsistent projections, stop the arena, replay the journal as documented in
[harness recovery](harness.md), and restart.

Tests exercise two independent adapters, role authorization, multiple MCP clients,
private prompts/set cards, spectator masking, and checkpoint restoration. They
use scripted adjudication to test orchestration; the LLM remains responsible for
actual card legality and tactical decisions.
