# Headless play and chat hosts

`yugioh-harness duel` exposes `duel-v1`, a versioned JSON-lines protocol over the
same `DuelService`, `Orchestrator`, and `DuelRunner` used by MCP. There is one state
writer and no second rules engine. The host agent interprets rules, adjudicates
transitions, and dispatches player agents. The CLI does not call an LLM by itself.

## Start a host transport

Install once from the monorepo root (`python -m pip install -e .`). The host can
keep a process open:

```sh
yugioh-harness duel --repo /path/to/yugioh-harness --private-root /private/duels
```

Send one complete JSON object per line; stdout returns one JSON object per line,
with no prompts or progress text mixed into the stream:

```json
{"protocol":"duel-v1","id":"discover","request":{"op":"describe"}}
{"protocol":"duel-v1","id":"decks","request":{"op":"decks"}}
```

Every envelope has exactly `protocol`, `id` (string or integer), and `request`.
Responses contain `protocol`, the same `id`, `ok`, and either `result` or `error`.
Malformed JSON/invalid identities return `id: null`. `describe` returns operation
properties, required fields, supported task kinds, and the authority boundary.
Invalid requests do not terminate a stream or echo private input.

Saved-session `game_id` values returned by `games` identify the private session
folder used by `resume`. For fixed scenarios this can differ from the original
`state_game_id` inside a reviewed checkpoint; the original state is preserved.

The ordinary workflow is:

1. `preflight` with honestly observed `host_capabilities`.
2. `start` with the agreed `config` and full pinned `rules_text`, or `resume` with
   `game_id`. `templates/edison-managed.json` is an explicit Edison example:
   human Blackwing, opponent Lightsworn, human starts. Confirm those choices for
   a real game; shared APIs remain format-neutral.
3. `next` to obtain a host task. `moderator` means the host must review/propose
   the next transition or submitted intention. `human` means ask the user in
   the same conversation. `subagent` means reserve, dispatch, bind, and collect
   an independent pilot using only its filtered packet.
4. `human_reply` accepts free text or a numbered suggestion. `agent_result`
   accepts the bound pilot's intention. Neither executes card effects.
5. The referee checks legality, costs, targets, and response windows. `step`
   commits its approved operations, bound to the submission ID. `present`
   persists the next question. Continue with `next`.

Use the same operation arguments documented in [orchestration](orchestration.md)
and returned by `describe`; the headless protocol validates required fields,
primitive types, enum choices and unexpected arguments before dispatch. Nested
config/action validation remains owned by the existing runtime. Open intention
means a player is never restricted to the displayed recommendations. Structured
`intent-v1` is optional and retains its documented limited initiation coverage.

The CLI will not invent card effects, enumerate a complete legal move set, skip a
response, auto-pass a failed pilot, or substitute the moderator for the opponent.
Pause on uncertain rulings. Host tasks are the explicit boundary for all LLM work.

## One request per execution tool call

Hosts with an execution tool but no registered MCP server can save an envelope
in a private file and execute:

```sh
python -m harness.cli duel --repo /path/to/yugioh-harness \
  --private-root /private/duels --game-id saved-duel-id \
  --request-file /private/request.json
```

`--game-id` resumes before the request. `--request-file` handles one envelope,
closes the writer, and exits 0 on success or 1 on failure. Omit `--game-id` for
lobby operations or the initial start. `--host-file` loads an observed capability
declaration before processing requests; this is useful when the initial
`preflight` and `start` occur in separate invocations. Do not use both a persistent
writer and one-shot calls for the same game at the same time.

Decision IDs, submissions, child handles, attempt deadlines, journals, and shuffled
orders survive process restarts. Reuse identical execution request IDs and payloads
after ambiguous transport failures. An envelope's `id` correlates a response;
mutation-level `request_id` supplies durable idempotency. They are different.

## ChatGPT Work / execution-capable chat

A repository link alone does not install tools. A chat host that actually has
execution and fresh native subagents can clone/install the monorepo, read
`agents/orchestrator/AGENT.md` and `skills/duel-orchestrator/SKILL.md`, then run the
headless command internally. No registered MCP server, provider API key, terminal
commands from the human, or GUI is required for this native-host path.

Example user request:

> Start a managed Edison duel through the headless CLI. I play Blackwing against
> Lightsworn and go first. Use open intentions and keep the game in this chat.

The orchestrator reads `rules/common.md`, `rules/edison.md`, and the exact dated
banlist; includes their complete contents and historical overrides in
`rules_text`; verifies the real host capabilities; and starts internally. It
performs the compulsory first-turn draw through reviewed operations and preserves
Draw/Standby response opportunities before Main Phase. It shows only the human
state and asks for a move in the conversation. It never forwards its own hidden
state/history to the opponent child. Cooperative privacy relies on the child's
context-only/no-tools instructions; it is not a filesystem sandbox.

Across chat sessions, a durable save location is required. A Git PR does not
back up ignored game files. If private saves are unavailable, report that rather
than recreating or reshuffling the game.

## Future GUI boundary

A GUI's trusted host/backend uses the same API. Poll `interaction` for structured
human/spectator data: `perspective`, filtered `context` (board/cards/recent events),
a human-only `decision`, and `awaiting_input`. The decision includes its ID,
window, optional recommendations, and `action_mode: open-intention`. Submit text
through the host's `human_reply`. State is data; the existing Markdown renderer
is not required by a GUI.

Do not forward raw `next` responses to a GUI: moderator tasks can contain both
hands, and player tasks contain private opponent choices. `interaction` hides
opponent menus and uses a public spectator view for agent-vs-agent sessions.
This local CLI/Python API is a **trusted moderator channel**, not an authenticated
HTTP service. A future network backend must bind users to sessions and expose
only filtered reads and their own decision submissions. Existing role-bound arena
credentials remain the separate option for independent player clients.
