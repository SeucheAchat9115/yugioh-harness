"""Host launch boundaries and the actual shared MCP/browser process."""
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen

from harness.integration.launcher import command, launch
from harness.integration.mcp import main as mcp_main, rpc


REPO = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_browser_opens_player_link_without_polluting_stdio(self):
        stdout, stderr = StringIO(), StringIO()
        with tempfile.TemporaryDirectory() as directory:
            argv = ['mcp', '--repo', str(REPO), '--private-root', str(Path(directory) / 'private'),
                    '--ui-port', '0', '--open-browser']
            with patch.object(sys, 'argv', argv), patch('webbrowser.open', return_value=True) as browser, \
                    patch('harness.integration.mcp.run_stdio') as stdio, \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                mcp_main()
            service = stdio.call_args.args[0]
            browser.assert_called_once_with(service.ui_url)
            self.assertIn(service.ui_url, stderr.getvalue())
            self.assertEqual(stdout.getvalue(), '')

    def test_player_role_cannot_retrieve_human_browser_credential(self):
        player = SimpleNamespace(role='agent', conversational=True)
        response = rpc(player, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        self.assertNotIn('duel_ui', [tool['name'] for tool in response['result']['tools']])
        denied = rpc(player, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                              'params': {'name': 'duel_ui', 'arguments': {}}})
        self.assertEqual(denied['error']['code'], -32602)

    def test_config_roundtrip_paths_with_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / 'duel café with spaces'
            (repo / 'agents/orchestrator').mkdir(parents=True)
            (repo / 'agents/orchestrator/AGENT.md').touch()
            argv = command(repo, port=0, executable='codex')
            overrides = [argv[i + 1] for i, arg in enumerate(argv) if arg == '-c']
            config = tomllib.loads('\n'.join(overrides))['mcp_servers']['yugioh']
            self.assertEqual(config['command'], sys.executable)
            self.assertEqual(config['args'][:4], ['-m', 'harness.integration.mcp', '--repo', str(repo.resolve())])
            self.assertEqual(config['args'][-3:], ['--ui-port', '0', '--open-browser'])
            self.assertTrue(config['enabled'])
            self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', argv)
            self.assertIn('duel_preflight', argv[-1])

    def test_invalid_setup_does_not_launch_a_host(self):
        with self.assertRaises(ValueError):
            command(REPO, REPO / 'private', executable='codex')
        with self.assertRaises(ValueError):
            command(REPO, port=65536, executable='codex')
        with patch('harness.integration.launcher.shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'not on PATH'):
                command(REPO)

    def test_launch_keeps_host_exit_status_and_creates_external_private_root(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / 'private'
            with patch('harness.integration.launcher.shutil.which', return_value='codex'), \
                    patch('harness.integration.launcher.subprocess.call', return_value=7) as run:
                self.assertEqual(launch(REPO, private), 7)
            self.assertTrue(private.is_dir())
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs, {})  # No shell or detached host.

    def test_stdio_ui_link_reaches_same_idle_service_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.Popen([sys.executable, '-m', 'harness.integration.mcp',
                '--repo', str(REPO), '--private-root', str(Path(directory) / 'private'), '--ui-port', '0'],
                cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8')
            try:
                request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                           'params': {'name': 'duel_ui', 'arguments': {}}}
                process.stdin.write(json.dumps(request) + '\n')
                process.stdin.flush()
                response = json.loads(process.stdout.readline())
                result = json.loads(response['result']['content'][0]['text'])
                self.assertTrue(result['ok'])
                base, token = result['result']['url'].split('/#token=')
                self.assertTrue(base.startswith('http://127.0.0.1:'))
                with urlopen(Request(base + '/api/state', headers={'X-Duel-Token': token}), timeout=5) as reply:
                    self.assertIsNone(json.load(reply)['state'])
                process.stdin.close()
                process.wait(timeout=10)
                self.assertEqual(process.returncode, 0, process.stderr.read())
                self.assertFalse((Path(directory) / 'private').exists())  # Never starts a demo duel.
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()


if __name__ == '__main__':
    unittest.main()
