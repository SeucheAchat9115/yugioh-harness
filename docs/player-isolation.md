# Player isolation and failed subagents

The orchestrator is the only moderator and user contact. Each player receives
only its permitted context and returns an intention. Human card management
(`managed` or `self`) and player isolation are independent settings.

## Select once and preserve on resume

New `managed`, `self`, and `agent-vs-agent` games default to
`player_isolation: "cooperative"`, the normal native-agent workflow. State the
policy during setup; honor an explicit request for `enforced`. Save the choice
in configuration and journaled state. Never ask for an exception at each turn
or silently downgrade an enforced game. Existing saves without this setting
remain enforced. Legacy `open`/`blind` startup defaults also remain enforced.
The policy cannot be changed through an action or metadata edit on resume.

| Policy | Requirements | Privacy limit |
| --- | --- | --- |
| Cooperative | Fresh child, no inherited parent/sibling history, permitted context only, instructions prohibiting all tools, file/network access, and delegation | The host may still expose tools/files; privacy depends on the child obeying instructions. |
| Enforced | Fresh child plus a tool-free model request or verified host restrictions preventing tool and filesystem access | Host-enforced boundary; the harness records a declaration, not independent sandbox attestation. |

Both use the same filtered views, sequential dispatch, sole moderator writer,
legality review, deadlines, bounded retries, and durable receipts. Cooperative
is not permission to include hidden opponent cards, moderator history, private
paths, credentials, or opponent guides in a task. Do not label it hard-isolated.

## Record the actual dispatch boundary

Before spawning, `duel_player_start` requires exactly these declaration keys.
For a cooperative native host with shared tools and files, an honest example is:

```json
{
  "method": "cooperative",
  "parent_history": false,
  "tools": ["functions", "collaboration"],
  "filesystem": true,
  "evidence": "Fresh child with no inherited history; tools and workspace remain available; player instructions prohibit their use"
}
```

`tools` describes capabilities actually available, not the requested tool-use
policy. `filesystem` likewise describes actual access. Use the host's real
capability names and configuration; do not copy evidence without verifying it.
No inherited history is permitted under either policy. A cooperative declaration
is rejected for an enforced game.

For enforced dispatch use `method: "context-only"` or `"host-sandbox"`,
`parent_history: false`, `tools: []`, `filesystem: false`, and nonempty evidence
identifying the verified transport or host restrictions. Even in a cooperative
game these methods must meet the enforced requirements; shared tools/files cannot
be relabeled as a sandbox. A cooperative game may use a stronger enforced boundary.

- `harness.players.isolated.ContextOnlyPlayer` constructs a system policy and
  permitted player context, with `tools: []` and `tool_choice: none`. The trusted
  transport must not append history, tools, or filesystem content. Provider-specific
  API translation is the host's responsibility. Tool-call output is rejected.
- A native host sandbox must actually prevent tool/file access. Instructions alone
  are insufficient. If the saved policy is enforced and neither route exists,
  explain the limitation and pause; do not downgrade it automatically.

Attempts persist the selected policy, actual declaration, evidence, and boundary
label. Task/dispatch/status responses expose the policy and boundary label to the
moderator. Capability details remain in the private workflow/checkpoint. These
receipts are host assertions, not remote attestation. Cooperative children must
not use inherited tools even if a host exposes them.

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
not a vendor sandbox. The declaration must describe the real host before dispatch; no Python commands or credential handling are required from the player.

## Management and information

Human `managed` and `self` modes select who handles the human cards. Both give
the opponent child only legally revealed human information. Managed additionally
gives the moderator the full human state for bookkeeping and coaching. Self
never imports hidden human cards. The same host isolation requirements apply to
both modes; managing the human deck does not authorize sharing moderator history.
Legacy `open` saves retain their explicitly shared human information.
