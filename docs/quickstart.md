# Install and start a duel

## Supported environment

Python 3.11–3.13 on Windows, Linux or macOS. Windows uses native byte-range
writer locks; POSIX systems use `flock`. CI runs on Windows only. Runtime dependencies are Python's standard library.
Install/build tools are needed only for setup. Deck conversion additionally needs
network access to the YGOPRODeck API; prepared decks play offline with respect to
card data (your model host may still use its own network).

Choose a tool-capable Codex, Claude Code or Gemini CLI environment that actually
provides execution/MCP plus native subagents with fresh history and cancellation.
A plain chat app or an MCP server alone does not provide those subagents. Support
is capability-based: configuration examples are provided for all three hosts;
real vendor/version combinations still need a native-player trial. Automated smoke
tests use simulated host callbacks and do not certify an app's isolation.

## One-time installation

The installer, host administrator or orchestrator performs these steps. Players
never execute terminal commands during a duel.

```sh
git clone https://github.com/SeucheAchat9115/yugioh-harness.git
cd yugioh-harness
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/yugioh-harness --version
.venv/bin/yugioh-harness doctor --repo .
```

On Windows PowerShell, use `python` to create the environment and the `Scripts`
executables instead:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\yugioh-harness.exe doctor --repo .
.\.venv\Scripts\yugioh-harness.exe host-config --host codex --repo .
```

An installed wheel contains the runtime; keep this resource checkout for decklists,
rules, agents and skills. Run from any directory using `--repo` with the actual
checkout path. Default private saves are in the sibling `<checkout-name>-private/`
directory and replay caches in `<checkout-name>-replay-cache/`, outside Git.
Choose `--private-root` when that sibling directory is unsuitable. Store private
saves on durable storage if the host uses an ephemeral workspace.

`doctor` checks Python/locks, writable locations and deck/guide integrity. Without
a host declaration it reports `host_ready: null`; passing local checks alone
never proves an app can dispatch players.

## Configure a host

Generate configuration with the installed environment's Python and actual checkout:

```sh
.venv/bin/yugioh-harness host-config --host codex --repo .
.venv/bin/yugioh-harness host-config --host claude --repo .
.venv/bin/yugioh-harness host-config --host gemini --repo .
```

Install the relevant output in the host's MCP settings: Codex's MCP TOML settings,
Claude Code's project `.mcp.json`, or Gemini CLI's `.gemini/settings.json`, according
to that host/version's configuration documentation. Merge the `yugioh` entry with
existing servers rather than replacing unrelated settings. Restart/reload MCP.
The command uses an absolute Python path; regenerate it if the virtual environment
or checkout moves. It runs locally over stdio, with no public HTTP listener.

Execution-capable orchestrators can launch the same backend themselves when MCP
is not registered. Static files in `examples/` use marked placeholders; the
configuration generator produces usable paths. Models/API credentials belong to
the host; this project does not require vendor SDKs or collect credentials.

## Verify capabilities before dealing

The orchestrator checks that it can execute tools, spawn a fresh player child
without inherited history, provide context-only/no-tools instructions, and stop
a child. It calls `duel_preflight` with those observed capabilities and a short
`evidence` description. Do not declare unavailable features true. The default
repository MCP lobby refuses `duel_start` until this preflight succeeds, then
checks selected bundles and storage again before shuffling/dealing.

For a maintainer check, copy `templates/host-capabilities.json` outside the checkout,
fill it from real observations, then use `doctor --host-file <file> --require-host`.
Declarations record host evidence, not enforced sandboxing. Cooperative privacy
relies on the child obeying instructions; enforced play needs actual restrictions.
The programmatic `DuelService` keeps its legacy non-strict default for existing
integrations; new integrations should construct it with `require_host=True`.

## Start by talking

Managed:

> Read agents/orchestrator/AGENT.md. Start a managed Edison duel: I play Blackwing
> against Lightsworn. Check setup, ask who starts, then guide me through play.

Self:

> Start a self-mode Edison duel. You play Blackwing; I use an unknown physical
> deck, 40/15/15. I go second. Never ask for my hidden hand or decklist.

Agent against agent:

> Start an Edison agent-versus-agent duel, Blackwing versus Lightsworn. Use
> separate fresh player children and show me only the public game.

The orchestrator confirms rules and starting player, operates all runtime tools,
and saves after actions. Say “save and pause” to stop and retain the pending
window, or ask to resume the saved game ID later. A save does not publish to Git.
Self players must preserve their own physical hidden cards/order for continuation.

## Troubleshooting

- Missing Python/module: use the generated absolute virtual-environment executable.
- No subagent facility or no fresh history: use a capable host; do not pretend the
  moderator is an independent opponent or silently downgrade enforced isolation.
- `duel_start` rejected before dealing: run `duel_preflight`, inspect readiness,
  selected deck names and agreed settings.
- Storage failure: retain private files, recover projections from the journal,
  and resume; never initialize a replacement game to bypass a saved shuffle.
- Corrupt guide/bundle: regenerate through the deck skills and review provenance;
  don't modify historical shared snapshots.

See `docs/codex-play.md` for the tool protocol and `CONTRIBUTING.md` for development.

Windows file privacy follows the directory ACLs inherited from the user profile.
POSIX `chmod` modes do not establish equivalent ACL isolation on Windows. Choose
a private save directory accessible only to the intended user; cooperative player
children still rely on their no-tools instructions on either platform.
