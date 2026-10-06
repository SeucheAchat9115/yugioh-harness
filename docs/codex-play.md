# Play through one conversation

Open this repository in a tool-capable Codex, Claude, or Gemini environment and say:

> Read `agents/orchestrator/AGENT.md`. Start a managed duel: I play Branded Despia
> against Dracotail. Ask me for any missing rules, then guide me through the game.

For self mode say you manage your own hidden cards. To watch two agents, request
an agent-versus-agent duel and name both decks. To continue, ask to resume the saved
game ID. You always talk to one orchestrator. You do not run Python, prepare JSON,
open player sessions, manage credentials, or relay agent messages during play.
The orchestrator handles setup, runtime calls, player delegation, and saving.

The app environment needs execution or MCP tools and a native subagent facility
without inherited parent/sibling history. Cooperative is the normal native-host
policy; enforced additionally needs a verified sandbox or tool-free transport. Plain chat apps do not gain those capabilities
from these files. If a required capability is missing, the orchestrator explains
it and pauses rather than pretending to run independent players. The workflow is
provider-neutral; it does not include vendor model SDKs or API credentials.

See [quickstart](quickstart.md) for tested runtime installation and generated host
configuration. Vendor subagent support must be checked in the actual app.

## Host integration (one-time configuration)

The [MCP example](../examples/codex-mcp.toml) connects a repository-level lobby.
An installer or the orchestrator configures it; no per-duel state paths are needed.
Equivalent MCP setup works in hosts that support stdio servers. If no MCP server
is registered, the orchestrator can operate the stdio backend through its own
execution tools. Adding a repository does not automatically register tools in an
already-running app. These are **moderator** tools; never expose them to players.

| Tool | Purpose |
| --- | --- |
| `duel_preflight` | Check readiness and record observed host capabilities before dealing |
| `duel_decks` | Discover prepared deck bundles |
| `duel_games` | Discover saved local games for conversational resume |
| `duel_start` | Create an agreed duel, internal private paths, snapshots, and hands |
| `duel_resume` | Load a saved game by ID, without reshuffling |
| `duel_next` | Return the next human display, private player task, or moderator review |
| `duel_agent_context` | Compact filtered board, relevant card text and bounded guidance; optional card focus |
| `duel_player_start` | Reserve a bounded attempt under the saved isolation policy |
| `duel_player_bind` | Save the native child handle for cancellation/resume |
| `duel_player_fail` | Record failure and acknowledge actual child termination |
| `duel_agent_result` | Bind terminal output to its task and attempt |
| `duel_human_reply` | Bind conversational human input to the displayed decision |
| `duel_context` | Get a permitted perspective, card text, rules, and guides |
| `duel_present` | Save reviewed options and the decision ID |
| `duel_step` | Apply reviewed operations with durable retry protection |
| `duel_submit` | Lower-level decision-bound intention submission |
| `duel_status` | Inspect revisions and durable receipts |
| `duel_recover` | Repair projections after save failure without repeating effects |

## Orchestrator workflow

Follow [the orchestration skill](../skills/duel-orchestrator/SKILL.md). Collect rules
and deck selections conversationally, start internally, then call `duel_next`.
The LLM moderator opens and presents decisions and reviews submitted intentions.
Human tasks are displayed and answered in the same conversation. Player tasks
are dispatched sequentially to native children with only their own context and
no inherited moderator history. Wait for each result, store it, review it, apply
the action, then fetch fresh context for the next actor. The scheduler does not
spawn a model itself; the app's orchestrator invokes its native subagent tools.

In managed mode only the moderator manages human hidden state; the opponent
receives its own cards and legally revealed human information. Self mode never
imports human hidden cards. Agent-versus-agent player views hide the
other hand and guide. Child context envelopes must stay internal. Follow [isolation and failure handling](player-isolation.md)
for policy selection, honest capability declarations, deadlines, cancellation,
and bounded retries. Cooperative children use only their supplied context and
are instructed to avoid tools/files; enforced requires actual restrictions or a
tool-free transport. Shared native tools/files do not block cooperative play.

Every gameplay message includes the fixed state display and reviewed intervening
events. Human windows have two legal suggestions when available and accept free
text. Only verified compulsory/no-choice steps advance automatically. Unknown
self choices cannot be skipped. The user never supplies request IDs or operations.

Retries retain IDs and identical payloads. Recorded actions return receipts rather
than reapplying effects. Outstanding task bindings, prompts, choices, and hidden
managed cards survive checkpoint restore. Legacy sessions without lobby metadata
can still be loaded by the orchestrator through their existing direct runner paths.
No tool commits game records at pause, finish, or save.

## Backend reference for maintainers

`harness.integration.mcp --repo <checkout>` is the repository-level stdio service;
`--private-root` optionally configures durable external storage. Direct `--state`
and `--game-dir` and role-bound `--credential` transports remain compatible.
`DuelService` owns setup and the persistent writer; `Orchestrator.next()` returns
a sequential host task; `DuelLoop` supports synchronous moderator/player callbacks.
See [harness internals](harness.md) and [agent duels](agent-vs-agent.md).

`duel_step` uses moderator-approved `operations`: `move`, `card`, `lp`, `usage`,
`restrictions`, `normal_summon`, `decision`, `chain`, `pending_effects`, `phase`,
`turn`, `status`, `draw`, `shuffle`, `place`, `remove`, `counts`, and `set`.
These provide structural safeguards; the LLM certifies legality against card text
and agreed rules. H/A references are bound to persisted menus. Future draw orders
are excluded from LLM context; moderator Deck inventory is unordered.

Harness benchmarks exclude model latency. Sequential subagents add model calls;
use focused contexts and a persistent runner to minimize overhead, without
claiming a guaranteed response time.
