# Player isolation and failed subagents

The orchestrator is the only moderator and user contact. A player receives its own
permitted context and returns one intention. Player code must not receive parent
or sibling histories, moderator MCP servers, execution/read tools, credentials,
or private-state paths. A role-scoped context is not an operating-system sandbox.

## Two supported dispatch boundaries

- **Context-only model request:** `harness.players.isolated.ContextOnlyPlayer`
  builds exactly a system policy and a permitted player context, with `tools: []`
  and `tool_choice: none`. It rejects moderator context, extra parent-message
  fields, opponent hidden zones/guides, future deck orders, and authoritative card
  catalogs. Returned tool-call objects are rejected; output is never executed.
  The trusted host transport sends this request to a model API without appending
  history, tools, or filesystem content. Provider-specific API translation is the
  host's responsibility; it must preserve these restrictions.
- **Native host sandbox:** configure a fresh child with no inherited conversation,
  no tools, and no filesystem access. Verify the host's actual permissions before
  dispatch. An instruction such as “do not read files” does not count as enforcement.
  Native facilities that inherit unrestricted tools/shared private files cannot
  be used as isolated players. Use the context-only route or pause the duel.

Before spawning, `duel_player_start` requires this exact declaration:

```json
{
  "method": "context-only",
  "parent_history": false,
  "tools": [],
  "filesystem": false,
  "evidence": "Reference to the verified host configuration or context-only transport"
}
```

`method` can also be `host-sandbox`. The declaration and evidence are saved
privately. The runtime rejects absent/unsafe declarations. This is a trusted
host assertion, **not remote attestation**: the harness cannot independently
verify a vendor app's sandbox or prevent a dishonest moderator from leaking data.
Role-bound arena tools enforce API access; host filesystem restrictions remain
necessary. Never label shared unrestricted native children as hard-isolated.

## Durable attempt protocol

1. Get the active private task from `duel_next`. Retain its clean player context.
2. Call `duel_player_start(task_id, request_id, isolation, timeout_seconds)` before
   creating a child. The default deadline is 60 seconds, configurable from 1–120.
   One unfinished/unconfirmed child blocks all further dispatches and moderator
   mutations. At most three attempts are allowed for each actor/revision decision
   window; re-presenting its menu does not reset the budget.
3. Spawn **only if `dispatch_authorized: true`**. Identical start retries return
   the same attempt ID with `dispatch_authorized: false`. Do not respawn; inspect
   the existing host task or confirm it never started. Name/correlate the child
   using the attempt ID. Save its native handle immediately with
   `duel_player_bind(task_id, attempt_id, child_id)`.
4. Wait in bounded intervals; poll `duel_next` before the deadline. A running child
   returns `subagent_wait`; an expired/failed child returns `subagent_failure`.
   Both include a safe fixed state display. Deadline checks occur on tool calls;
   the runtime has no vendor process supervisor or background kill thread.
5. Submit a terminal number/free-text response with
   `duel_agent_result(task_id, attempt_id, response)`. Responses must be nonempty
   text up to 8,192 characters or an integer; booleans, objects, invalid menu
   numbers, and tool-call output are rejected. Legality still requires moderator
   review. A late, cancelled, superseded, or wrong-attempt reply is rejected.
6. On timeout/cancellation/transport failure, use `duel_player_fail` with the
   standardized reason. Interrupt/cancel the actual host child. Set `terminated:
   true` **only after confirming it stopped or was never spawned**. Recording
   failure does not kill the process. The host owns cancellation. If the attempt
   already has a failure reason, preserve that reason when acknowledging its
   termination (for example, `timeout` after automatic deadline expiry).
7. Once stopped, retry with a new start request ID. The decision task stays the
   same; each retry gets a fresh attempt ID. Do not change the menu to evade the
   attempt limit. After three failed attempts, keep the game waiting, report the
   issue, and pause; never auto-pass, invent a move, or assume a failed child chose.

Failure reasons are `timeout`, `cancelled`, `malformed`, `transport_error`,
`host_shutdown`, and `isolation_failed`. Raw model errors, stack traces, and private
response content are not echoed in public errors or stored as failure reasons.
Malformed output records failure and requires termination acknowledgement before
retrying. An already committed result can be retried identically without duplicate
submission/actions; different content for that result ID is rejected.

## Resume and shutdown

Checkpoints retain tasks, isolation declarations, deadlines, attempts, native
handles, submissions, and receipts. After reconnecting, an existing running child
is waited for, never spawned again. If the host lost it, verify termination and
record `host_shutdown`, then explicitly start a new bounded attempt. Wall-clock
UTC deadlines survive process restarts. Do not reset them on resume.

Cancel and acknowledge children before switching games or advancing the decision.
Stopping the backend does not stop vendor children. A crash after submission but
before attempt finalization is repaired from the durable submission; the intention
returns for review without dispatching another player. These operations never
move cards or advance state by themselves.

## What the checks prove

Tests cover missing/unsafe declarations, separate permitted views, moderator
context rejection, tool-call rejection, duplicate starts, timeout boundaries,
cancellation, malformed output, late replies, bounded retries, resumed attempts,
and interrupted result finalization. They exercise trusted scripted transports,
not a vendor sandbox. A real host's permissions must be verified before its first
duel; no Python commands or credential handling are required from the player.
