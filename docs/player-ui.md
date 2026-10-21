# Visual player UI

## Windows: launch the MCP orchestrator and board

Install Python 3.11–3.13 and a current Codex CLI, then sign in to Codex using
your supported ChatGPT subscription. The harness does not request an API key.
Your actual host must support fresh native subagents and cancellation; the
orchestrator checks these capabilities before dealing. Installing MCP alone
does not supply an opponent model or subagent facility.

In PowerShell, from this resource checkout, perform the one-time setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m harness.cli doctor --repo .
```

Double-click `Start-Duel.cmd`, or run:

```powershell
.\.venv\Scripts\python.exe -m harness.cli play --repo .
```

The launcher opens a local Codex conversation with a session-only `yugioh` MCP
configuration. Codex starts the single persistent Python service, which opens
your browser on a free loopback port. There is no separate UI server to launch,
no global MCP configuration edit, and no Vercel deployment or tunnel. Keep the
Codex host running. If the browser does not open, ask the orchestrator for
`duel_ui`; it returns the current private player link. Reopen that link after a
page reload. Do not share it with the opponent subagent.

Use the Codex conversation for setup and moves; the local browser is your live
board. The orchestrator delegates opponent intentions to fresh permitted-context
children, reviews them, applies actions, and continues until your next decision
or response window. It asks you in the same Codex conversation. Cooperative
children follow no-tools instructions; this is not enforced filesystem isolation.
Unavailable native delegation blocks play rather than making the orchestrator
silently play the opponent. No child is launched by the Python service itself.

Browser submissions are optional. If you use one, say “continue” in Codex to
process it; the UI cannot wake an idle model host. Do not answer the same decision
again in chat. Ask to save and pause before quitting. Relaunch and ask to resume
the saved game; closing the browser alone does not end the duel. The default
private save folder is the sibling `<checkout-name>-private/`, outside Git;
archives and shared snapshots remain local ignored repository data.

This ChatGPT web conversation does not gain access to your PC from this launcher.
Gameplay runs in the local MCP-capable host conversation. To use this exact web
chat instead would require a separately supported authenticated remote connector
and verified opponent delegation, neither of which this launcher configures.

For another MCP host, generate and merge its configuration instead:

```powershell
.\.venv\Scripts\python.exe -m harness.cli host-config --host claude --repo . --ui-port 0 --open-browser
```

Replace `claude` with `codex` or `gemini` as appropriate. Use only one orchestrator
connection for the active duel. The launcher was checked with simulated host
execution; a real signed-in Windows host/subagent trial is still required.

## Local transport

The optional browser client runs alongside the repository MCP lobby and shares its
single persistent writer. It renders the human perspective, field slots, LP, hand,
Extra/Side Decks, public piles, shared zones, chain, usage and restrictions. Select
a visible card for its details. Reviewed suggestions and free-text actions submit
intentions to the existing durable decision workflow. The host orchestrator still
reviews legality, applies actions, and delegates opponent choices. The web server
does not call a model or resolve card effects independently.

For host setup, add `--ui-port 8765` to the existing MCP command arguments:

```sh
python -m harness.integration.mcp --repo /path/to/yugioh-harness --ui-port 8765
```

Keep that process running through the tool-capable host. Its stderr prints a
`Player UI: http://127.0.0.1:8765/#token=...` link. Open the complete link, then
ask the same host orchestrator to start or resume a duel normally. Setup remains
conversational; the browser displays the loaded duel and polls for updates.
The moderator must continue checking `duel_next` after browser submissions.
The UI does not wake an idle host or implement an autonomous model transport.

The server binds only to loopback. For a remote workspace, use an authenticated
host port tunnel; do not expose this player link publicly. The fragment token is
removed from the address bar after loading and retained in page memory; reopen
the original link after a page reload. Restarting the service rotates the token.

Only state reads and human intention submissions are exposed over HTTP. Moderator
operations, private task envelopes, opponent choices, guides, archives, and future
draw orders are excluded. The browser uses the existing perspective visibility
rules, including preserved legacy open/blind behavior; agent-vs-agent is read-only.
Requests carry a per-process token. Replies preserve decision and request IDs for
retry safety and reject stale decisions. Sessions, journals, and checkpoints retain
their existing local storage behavior. No game is created for UI previews.

The client uses local text cards and has no external artwork dependency. Assets are
included in the Python package; no frontend build or additional dependencies are
required.

## Hosting handoff

`vercel.json` and `.vercelignore` prepare a static frontend deployment containing
only the three browser assets. This is scaffolding, not a playable Vercel deployment:
`/api/state` and `/api/reply` currently exist only on the local Python HTTP server.
No Vercel project or deployment has been created or verified. Phone access to the
cloud workspace was not established; localhost links do not work on another device.

Next implementation work must provide an authenticated reachable backend or adapt
the runtime to durable hosted storage and a supported execution model. Preserve the
single-writer workflow, player filtering, decision-bound idempotent replies, and
host orchestration; do not expose moderator APIs or private save files. Determine
the current Vercel capabilities using the installed deployment/backend skills rather
than assuming a particular hosting restriction. Wire the frontend API routes and
verify the entire phone-browser → API → saved human intention → moderator review
flow before describing the hosted game as playable. Also visually verify responsive
layouts; automated browser rendering has not yet been checked.
