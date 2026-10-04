# Playing through the agentic harness

Codex acts as the opponent, moderator, and (in open mode) coach. The harness keeps
state and supplies persistent tools; it does not call a model to decide rules.
These roles follow the existing blind/open agent definitions and response protocol.

## Connect Codex once

1. Prepare a duel configuration and initialize a session using the commands in
   [harness setup](harness.md#start-and-resume). Keep private state outside the repo.
2. Merge the [MCP configuration example](../examples/codex-mcp.toml) into your Codex
   configuration, replacing all example paths. Start a Codex session with that
   server enabled. The server loads the duel once and stays alive across tool calls.
3. Ask Codex to read the appropriate `agents/*/AGENT.md` and shared moderator policy,
   then resume using the MCP tools. Do not launch a second runner or legacy writer.

The server is `python -m harness.integration.mcp --state ... --game-dir ...`. It
implements MCP initialization, tool discovery, and tool calls over local stdio
without external Python dependencies. Adding files to the repo does not register
tools in an already-running Codex conversation; enable the server in a new session.
No model API key or model provider SDK is required by the harness.

The six tools are trusted **moderator** tools. Codex must request the appropriate
player perspective when choosing opponent actions. A separate player client must
receive only its permitted context, never unrestricted moderator tool access.

| Tool | Purpose |
| --- | --- |
| `duel_context` | State, visible card text, snapshot rules, bounded guide excerpts, recent events |
| `duel_present` | Persist the reviewed prompt, numbered choices, and decision ID |
| `duel_submit` | Store a numbered/free-text intention bound to that decision |
| `duel_step` | Execute reviewed bookkeeping operations with durable retry receipts |
| `duel_status` | Inspect decision, submission, and execution statuses |
| `duel_recover` | Repair projections after save failure without repeating effects |

## Decision workflow

1. Get moderator context to adjudicate the current window. For an opponent choice,
   get agent context and apply the opponent policy. Do not inspect future draw order.
2. Use a reviewed step to open the next human/agent decision window when needed.
   Compulsory steps need `automatic: true` and the complete no-choice review.
3. Present a packet with the current `expected_revision`, two distinct legal
   recommendations when available, reasons, events, and a question. The tool
   returns a `decision_id`; human packets also return the fixed state display.
   Opponent packets stay private and never return opponent recommendations to the human.
4. Bind the reply to that ID using `duel_submit`. Numbers select the persisted menu;
   other text remains an intention for the LLM to interpret. Submission does not
   move cards or authorize an effect by itself.
5. Review legality, costs, materials, timing, and responses. Execute a step with the
   `submission_id` and a new stable `request_id`. Preserve every response window.
6. Continue verified no-choice steps, then present the next actual choice. Include
   the intervening events. If a ruling is uncertain, pause rather than invent one.

If clarification is needed, present a new decision ID and revised question before
accepting a corrected response. Never reuse an ID for a different menu. Human
choices are never replaced with the coach recommendation automatically.

Every retry must use the same request ID and identical payload. A submitted reply
can be safely retried after reconnecting. A recorded execution returns its receipt
and current permitted state without applying it again, even after restart. Reusing
an ID with different content is rejected. On `recovery_required`, recover first,
then retry the original request; prepared shuffles retain their sampled order.

## Bookkeeping tools

`duel_step` accepts an `operations` list instead of hand-built before/after patches:

```json
{
  "request_id": "resolve-example-001",
  "submission_id": "human-choice-001",
  "request": {
    "kind": "choice",
    "actor": "moderator",
    "expected_revision": 12,
    "moderator_approved": true,
    "public_summary_reviewed": true,
    "public_summary": "The reviewed choice is recorded.",
    "operations": [
      {"op": "move", "card": "H1", "to": ["players", "human", "graveyard"]},
      {"op": "lp", "player": "human", "delta": -500},
      {"op": "decision", "value": null}
    ]
  }
}
```

This is a structural example, not a legal card-effect recipe. `H1`/`A1` refer to
persisted human/agent hand mappings; physical instance IDs also work. Destination
paths address zone lists (append or specify `index`) or empty slots. `move` can
attach a card to a located monster's `materials` list. `attributes` set position,
original owner, controller, or other tracked card state. Conservation checks reject
ordinary-card creation/deletion and physical-ID changes.

Supported operations: `move`, `card` attributes, `lp`, `usage`, `restrictions`,
`normal_summon`, `decision`, `chain`, `pending_effects`, `phase`, `turn`, `status`,
`draw`, and `shuffle`. `place`/`remove` handle explicit tokens and blind human
reveals/returns; conservation still rejects managed-card creation/deletion.
`counts` updates blind human unknown-zone counts. `set` assigns an existing custom
mutable path without requiring a before/after patch. Combine related operations
into one guarded action.
No operation independently certifies Yu-Gi-Oh legality.

Moderator context includes a sorted, unordered managed Deck inventory to select
searches/materials by physical ID. It never exposes shuffled order. Blind human
Deck identities and guides are absent. Guide excerpts are bounded to about 5,000
characters per authorized deck; rule text is capped at 8,000 characters with a
truncation flag. `card_ids` optionally focuses the card-text portion on visible
identities; it cannot reveal a hidden opponent card.

## Host-driven loop

Applications can use `harness.runner.loop.DuelLoop` instead of orchestrating each
MCP call manually. Supply a moderator callback and player adapters:

```python
from harness.runner.duel import DuelRunner
from harness.runner.loop import DuelLoop
from harness.players.adapters import CallbackPlayer

with DuelRunner(state_path, game_dir) as runner:
    loop = DuelLoop(runner, moderator_callback, {
        "agent": CallbackPlayer(opponent_callback)
    })
    result = loop.run()  # stops at human input, pause, finish, or clarification
    # Show result["text"] when awaiting human input.
    runner.workflow.submit(result["decision_id"], "human-input-001", human_text)
    result = loop.run()
```

The moderator callback receives `stage: next_step` or `review_intent`, permitted
moderator context, and the submitted intention. Return `{"packet": ...}` to ask a
choice, `{"action": ...}` for reviewed operations, or `{"rejected": true}` to stop
for clarification. For agent decisions, the player adapter returns
`{"response": "1", "request_id": "agent-input-001"}` or free text. Callbacks supply
actual LLM reasoning; the temporary tests use scripted callbacks, not a model.
The loop stops at every available human option and accepts durable queued input
after restart. Automatic plans require a verified no-choice review and a step limit
prevents runaway progression. Completed/paused results include a fixed state display.

Loop metrics measure callback/player latency; MCP replies measure harness tool
latency. Benchmark engine time separately. Neither local timings nor scripted
scenario tests promise a particular Codex response time. No game commits occur
through these tools, at a pause, or at game end.
