"""Conversational lobby and single-orchestrator transport, with internal setup."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4
from harness.engine.session import start, load_bundle
from harness.runner.duel import DuelRunner, RecoveryRequired
from harness.runner.orchestrator import Orchestrator
from harness.runner.player_tasks import PlayerTaskError
from harness.storage.atomic import save
from harness.storage.checkpoint import write_checkpoint
from harness.__main__ import dispatch


class DuelService:
    conversational = True
    role = 'moderator'

    def __init__(self, repo, private_root=None, require_host=False):
        self.repo = Path(repo).resolve()
        self.private_root = Path(private_root or self.repo.parent / (self.repo.name + '-private')).resolve()
        if self.private_root.is_relative_to(self.repo):
            raise ValueError('Private root must be outside the repository')
        self.runner = None
        self.require_host = require_host
        self.host_capabilities = None

    def preflight(self, host_capabilities=None):
        from harness.preflight import inspect
        self.host_capabilities = None
        report = inspect(self.repo, self.private_root, host_capabilities)
        if report["ready"]:
            self.host_capabilities = deepcopy(host_capabilities)
        return report

    def close(self):
        if self.runner:
            self.runner.close()
            self.runner = None

    def decks(self):
        result = []
        for path in sorted((self.repo / 'decks').glob('*/*/deck.json')):
            folder = path.parent.relative_to(self.repo).as_posix()
            try:
                load_bundle(self.repo, folder)
            except (ValueError, KeyError, OSError):
                continue
            result.append({'deck': folder, 'name': path.parent.name})
        return result

    def games(self):
        result = []
        for locator in sorted(self.private_root.glob('*/session.json')):
            try:
                game = Path(json.loads(locator.read_text())['game_dir']).resolve()
                if not game.is_relative_to(self.repo / 'games'):
                    continue
                metadata = json.loads((game / 'game.json').read_text())
                progress = metadata.get('resume', {})
                result.append({'game_id': metadata['id'], 'mode': metadata['mode'],
                               'status': metadata['status'], 'revision': progress.get('revision', 0)})
            except (ValueError, KeyError, TypeError, OSError):
                continue
        return result

    def start(self, config, rules_text):
        if self.runner:
            raise ValueError('An active session is already loaded; resume or close it first')
        config = deepcopy(config)
        from harness.preflight import inspect
        from harness.modes import managed_cards
        selected = [config['agent_deck']]
        if managed_cards(config['mode']):
            selected.append(config['human_deck'])
        report = inspect(self.repo, self.private_root, self.host_capabilities, selected, require_docs=False)
        if not report['runtime_ready'] or (self.require_host and not report['ready']):
            raise ValueError('Run preflight with verified host capabilities before dealing')
        if self.host_capabilities:
            config['host_capabilities'] = deepcopy(self.host_capabilities)
        config['id'] = config.get('id') or 'duel-' + uuid4().hex
        if not isinstance(rules_text, str) or not rules_text.strip():
            raise ValueError('Agreed rules text required')
        _, game, state = start(self.repo, config, self.private_root / config['id'])
        (game / 'rules.md').write_text(rules_text, encoding='utf-8')
        journal = json.loads(state.with_name('journal.json').read_text())
        from harness.storage.archive import write_archive
        write_archive(journal, json.loads(state.read_text()), game)
        write_checkpoint(state, game, journal)
        save(state.with_name('session.json'), {'game_dir': str(game)})
        self.runner = DuelRunner(state, game)
        return {'game_id': config['id'], 'mode': config['mode'], 'status': self.runner.workflow.status()}

    def resume(self, game_id):
        if not isinstance(game_id, str) or not game_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in game_id):
            raise ValueError('Invalid game ID')
        folder = self.private_root / game_id
        metadata = json.loads((folder / 'session.json').read_text())
        game = Path(metadata['game_dir']).resolve()
        if not game.is_relative_to(self.repo / 'games'):
            raise ValueError('Invalid game directory')
        if self.runner and self.runner.state['game_id'] == game_id:
            return self.runner.workflow.status()
        if self.runner and Orchestrator(self.runner).players.blocking():
            raise PlayerTaskError('child_still_active')
        self.close()
        self.runner = DuelRunner(folder / 'state.json', game)
        return self.runner.workflow.status()

    def request(self, request):
        try:
            op = request.get('op')
            if op == 'preflight':
                result = self.preflight(request.get('host_capabilities'))
            elif op == 'decks':
                result = self.decks()
            elif op == 'games':
                result = self.games()
            elif op == 'start':
                result = self.start(request['config'], request['rules_text'])
            elif op == 'resume':
                result = self.resume(request['game_id'])
            else:
                if self.runner is None:
                    raise ValueError('Start or resume a duel first')
                orchestrator = Orchestrator(self.runner)
                if op == 'next':
                    result = orchestrator.next()
                elif op == 'agent_result':
                    result = orchestrator.agent_result(request['task_id'], request['attempt_id'], request['response'])
                elif op == 'player_start':
                    result = orchestrator.players.begin(request['task_id'], request['request_id'], request['isolation'], request.get('timeout_seconds', 60))
                elif op == 'player_bind':
                    result = orchestrator.players.bind(request['task_id'], request['attempt_id'], request['child_id'])
                elif op == 'player_fail':
                    result = orchestrator.players.fail(request['task_id'], request['attempt_id'], request['reason'], request.get('terminated', False))
                elif op == 'human_reply':
                    result = orchestrator.human_reply(request['decision_id'], request['request_id'], request['response'])
                else:
                    if op == 'submit' and (request.get('player', 'human') == 'agent' or self.runner.state['mode'] == 'agent-vs-agent'):
                        raise PlayerTaskError('player_attempt_required')
                    if op in ('step', 'present', 'command', 'record', 'effect') and orchestrator.players.blocking():
                        raise PlayerTaskError('child_still_active')
                    result = dispatch(self.runner, request)
            return {'ok': True, 'result': result}
        except PlayerTaskError as error:
            return {'ok': False, 'error': {'code': error.code, 'message': 'Player dispatch blocked; inspect duel_next and the host child status.'}}
        except RecoveryRequired as error:
            return {'ok': False, 'error': {'code': 'recovery_required', 'action_status': error.action_status}}
        except (ValueError, KeyError, TypeError, AttributeError, IndexError):
            return {'ok': False, 'error': {'code': 'invalid_request', 'message': 'Request rejected; check session and decision status.'}}
        except OSError:
            return {'ok': False, 'error': {'code': 'storage_error', 'message': 'Local session storage unavailable.'}}
