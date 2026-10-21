"""Local Codex host launcher; the host owns the one MCP/UI process."""
import json
from pathlib import Path
import shutil
import subprocess
import sys


PROMPT = """Read agents/orchestrator/AGENT.md, skills/duel-orchestrator/SKILL.md,
and docs/player-ui.md. Act as the sole duel orchestrator using the yugioh MCP
server already configured for this session. Its local browser board shares your
single writer; do not start another server. Verify your actual native subagent,
fresh-history and cancellation capabilities through duel_preflight before dealing.
Use fresh opponent children with only their permitted context, reserve and bind
each attempt, review their intentions, and apply actions through MCP. Never give
opponent children moderator tools or hidden human context. Do not silently act
as the opponent if delegation is unavailable. Explain cooperative isolation.
Ask me whether to resume a saved duel or start one, then agree format, decks,
mode and starting player. Do not create a demo game. Continue opponent decisions
and compulsory steps until my next legal decision or response opportunity; ask
me here and wait. Preserve response windows; do not auto-pass my choices without
an agreed policy. The browser is the visual board and this conversation is the
default input. If I submit in the browser, inspect duel_next when I say continue;
do not submit a second answer. Save each action and pause/resume without reshuffling.
No model API key is required by the harness; use the host's existing sign-in.
"""


def command(repo, private_root=None, port=0, executable=None):
    repo = Path(repo).resolve()
    if not (repo / 'agents/orchestrator/AGENT.md').is_file():
        raise ValueError('Choose the resource checkout containing agents/orchestrator/AGENT.md with --repo.')
    private = Path(private_root or repo.parent / (repo.name + '-private')).resolve()
    if private.is_relative_to(repo):
        raise ValueError('Private root must be outside the repository')
    if not 0 <= port <= 65535:
        raise ValueError('UI port must be between 0 and 65535')
    host = executable or shutil.which('codex')
    if not host:
        raise ValueError('Codex CLI is not on PATH. Install it and sign in, or use host-config for another capable MCP host.')
    server_args = ['-m', 'harness.integration.mcp', '--repo', str(repo),
                   '--private-root', str(private), '--ui-port', str(port), '--open-browser']
    # JSON string/array literals here are also TOML values; pass argv directly,
    # never through a shell or a persistent edit to the user's host settings.
    return [host, '-C', str(repo), '--add-dir', str(private),
            '-c', 'mcp_servers.yugioh.command=' + json.dumps(sys.executable, ensure_ascii=False),
            '-c', 'mcp_servers.yugioh.args=' + json.dumps(server_args, ensure_ascii=False),
            '-c', 'mcp_servers.yugioh.enabled=true', PROMPT]


def launch(repo, private_root=None, port=0):
    argv = command(repo, private_root, port)
    private = Path(private_root or Path(repo).resolve().parent / (Path(repo).resolve().name + '-private')).resolve()
    private.mkdir(parents=True, exist_ok=True)
    print('Opening the local Codex orchestrator. Its MCP server opens the browser board.', flush=True)
    print('Keep the host open while playing. Browser replies need a continue message in the host.', flush=True)
    return subprocess.call(argv)
