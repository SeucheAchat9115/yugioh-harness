"""Real JSON-lines/one-shot processes and filtered GUI projection, no model scores."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from harness.environment import DuelEnvironment, PROTOCOL
from harness.environment.positions import create_position
from harness.integration.headless import respond
from harness.runner.duel import DuelRunner
from harness.runner.state_tools import build
import test_session as fixtures
from test_workflow import open_window, packet, plan
from smoke_install import HOST


class HeadlessTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown

    def prepare(self):
        for name in ('AGENTS.md', 'agents/orchestrator/AGENT.md', 'skills/duel-orchestrator/SKILL.md'):
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixtures.REPO / name, target)
        for deck in ('blackwing', 'lightsworn'):
            shutil.copytree(fixtures.REPO / 'decks/edison' / deck, self.repo / 'decks/edison' / deck)
        self.edison = json.loads((fixtures.REPO / 'templates/edison-managed.json').read_text())
        self.edison['id'] = 'edison-headless'
        self.rules = '\n\n'.join((fixtures.REPO / path).read_text(encoding='utf-8')
                                 for path in ('rules/common.md', 'rules/edison.md', 'rules/banlists/tcg-2010-03-01.json'))

    def envelope(self, operation, **arguments):
        return {'protocol': PROTOCOL, 'id': 'request', 'request': {'op': operation, **arguments}}

    def call(self, env, operation, **arguments):
        result = env.request(self.envelope(operation, **arguments))
        self.assertTrue(result['ok'], result)
        return result['result']

    def start(self, env):
        self.call(env, 'preflight', host_capabilities=HOST)
        return self.call(env, 'start', config=self.edison, rules_text=self.rules)

    def test_protocol_gate_and_no_hidden_data_in_error(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            description = self.call(env, 'describe')
            self.assertEqual(description['action_mode'], 'open-intention')
            self.assertIn('agent_result', description['operations'])
            self.assertFalse(env.request(self.envelope('start', config=self.edison, rules_text=self.rules))['ok'])
            for value in (None, [], {'protocol': 'wrong', 'id': 'x', 'request': {'op': 'games'}},
                          self.envelope('view', player='other'), self.envelope('start', config=[], rules_text='SECRET'),
                          self.envelope('player_start', task_id='x', request_id='x', isolation={}, timeout_seconds=True),
                          self.envelope('games', unrecognized='SECRET')):
                result = env.request(value)
                self.assertFalse(result['ok'])
                self.assertNotIn('SECRET', json.dumps(result))
            self.assertFalse(respond(env, '{"private":"SECRET"')['ok'])
            self.start(env)  # Bad requests did not poison the stream.

    def test_open_intention_retry_response_window_and_gui_filter(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            runner = env.service.runner
            self.assertEqual(len(runner.state['players']['human']['hand']), 5)
            self.assertEqual(runner.configuration['settings']['field_layout']['extra_monster_zones'], 0)
            # A transport fixture opens a choice; this is not a full-game legality claim.
            open_window(runner)
            prompt = packet(runner)
            prompt['recommendations'][0]['operations'] = 'PRIVATE_EXECUTION_DETAILS'
            runner.workflow.present(prompt)
            before = self.call(env, 'interaction')
            self.assertTrue(before['awaiting_input'])
            self.assertEqual(before['decision']['action_mode'], 'open-intention')
            board = self.call(env, 'board_snapshot')
            self.assertEqual(board['options']['recommendations'], before['decision']['recommendations'])
            self.assertEqual(board['options']['question'], before['decision']['question'])
            self.assertNotIn('decision_id', board['options'])
            self.assertNotIn('PRIVATE_EXECUTION_DETAILS', json.dumps(board))
            self.assertNotIn('hand', before['context']['state']['players']['agent'])
            self.assertNotIn('remaining_deck_order', json.dumps(before))
            self.assertNotIn('PRIVATE_EXECUTION_DETAILS', json.dumps(before))
            decision_id = before['decision']['decision_id']
            intention = 'I set a monster face down; please check the selected card.'
            args = dict(decision_id=decision_id, request_id='human-free-text', response=intention)
            first = self.call(env, 'human_reply', **args)
            self.assertEqual(first, self.call(env, 'human_reply', **args))
            self.assertEqual(first['intention']['text'], intention)
            self.assertFalse(self.call(env, 'interaction')['awaiting_input'])
            self.assertNotIn('options', self.call(env, 'board_snapshot'))
            self.assertEqual(self.call(env, 'next')['stage'], 'review_intent')
            request = plan(runner, [{'op': 'decision', 'value': {'actor': 'agent', 'window': 'response'}}])
            self.call(env, 'step', request_id='review', request=request, submission_id='human-free-text')
            duplicate = self.call(env, 'step', request_id='review', request=request, submission_id='human-free-text')
            self.assertTrue(duplicate['duplicate'])
            menu = packet(runner)
            menu['question'] = 'PRIVATE_OPPONENT_MENU'
            runner.workflow.present(menu)
            task = self.call(env, 'next')
            self.assertEqual(task['kind'], 'subagent')
            self.assertNotIn('hand', task['context']['state']['players']['human'])
            display = self.call(env, 'interaction')
            self.assertIsNone(display['decision'])
            self.assertFalse(display['awaiting_input'])
            self.assertNotIn('PRIVATE_OPPONENT_MENU', json.dumps(display))
            self.assertNotIn('task_id', display)

    def test_optional_board_snapshot_filters_visible_chat_data(self):
        self.prepare()
        self.edison['presentation']['show_agent_hand'] = True
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            interaction = self.call(env, 'interaction')
            agent = interaction['context']['state']['players']['agent']
            self.assertIn('hand', agent)
            board = self.call(env, 'board_snapshot')
            self.assertEqual(board['schema'], 'duel-board-v1')
            self.assertEqual(board['revision'], 0)
            self.assertEqual(len(board['players']['human']['hand']), 5)
            self.assertTrue(all(card['text'] for card in board['players']['human']['hand']))
            self.assertNotIn('hand', board['players']['agent'])
            self.assertEqual(len(board['players']['human']['extra_deck']), 15)
            self.assertTrue(all(card['text'] for card in board['players']['human']['extra_deck']))
            self.assertNotIn('extra_deck', board['players']['agent'])
            for player in board['players'].values():
                self.assertNotIn('deck', player)
                self.assertEqual(player['graveyard'], [])
                self.assertEqual(player['banished'], [])
            self.assertNotIn('side_deck', board['players']['human'])
            for forbidden in ('instance_id', 'remaining_deck_order'):
                self.assertNotIn(forbidden, json.dumps(board))
            self.assertNotIn('options', board)
            self.assertNotIn('decision', board)
            self.assertTrue(all(card['image_id'] in self.call(env, 'board_artwork')
                                for card in board['players']['human']['hand']))
            open_window(env.service.runner)
            self.assertGreater(self.call(env, 'board_snapshot')['revision'], board['revision'])

    def test_board_snapshot_shows_public_piles_and_hides_face_down_opponent_cards(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            runner = env.service.runner
            grave, hidden, visible = runner.state['players']['agent']['hand'][:3]
            moves = [
                {'op': 'move', 'card': grave['instance_id'], 'to': ['players', 'agent', 'graveyard']},
                {'op': 'move', 'card': hidden['instance_id'], 'to': ['players', 'agent', 'banished'],
                 'attributes': {'hidden': True, 'position': 'face-down'}},
                {'op': 'move', 'card': visible['instance_id'], 'to': ['players', 'agent', 'banished'],
                 'attributes': {'hidden': False, 'position': 'face-up'}},
            ]
            self.call(env, 'step', request_id='board-zone-fixture', request=plan(runner, moves))
            opponent = self.call(env, 'board_snapshot')['players']['agent']
            self.assertEqual(opponent['graveyard'][0]['image_id'], grave['card_id'])
            self.assertTrue(opponent['graveyard'][0]['text'])
            self.assertEqual(opponent['banished'][0], {'hidden': True, 'position': 'face-down'})
            self.assertEqual(opponent['banished'][1]['image_id'], visible['card_id'])

    def test_board_chain_details_use_only_public_source_identity(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            runner = env.service.runner
            player = runner.state['players']['agent']
            revealed, hidden = player['hand'][:2]
            known = player['cards'][str(revealed['card_id'])]
            chain = [{'id': 'one', 'actor': 'agent', 'name': known['name'], 'effect': 'Public effect.',
                      'costs': [{'kind': 'discard', 'instance_id': hidden['instance_id']},
                                {'kind': 'unrecognized-cost'}]},
                     {'id': 'two', 'actor': 'agent', 'card': hidden['instance_id'],
                      'effect': 'Unknown source.', 'resolution_started': True}]
            self.call(env, 'step', request_id='board-chain-fixture', request=plan(runner, [
                {'op': 'chain', 'value': chain},
            ]))
            first, second = self.call(env, 'board_snapshot')['chain']
            self.assertEqual(first['card']['name'], known['name'])
            self.assertEqual(first['card']['image_id'], revealed['card_id'])
            self.assertEqual(first['card']['text'], known['desc'])
            self.assertEqual(first['effect'], 'Public effect.')
            self.assertEqual(first['action'], 'activate')
            self.assertEqual(first['costs'], ['discard'])
            self.assertNotIn(hidden['instance_id'], json.dumps(first))
            self.assertEqual(second['card']['name'], 'Card effect')
            self.assertEqual(second['action'], 'resolve')
            self.assertEqual(second['costs'], [])
            self.assertNotIn('image_id', second['card'])
            self.assertNotIn('movement', second)
            self.assertNotIn(hidden['instance_id'], json.dumps(second))
            self.assertIsNone(second['card']['text'])

    def test_board_chain_movement_tracks_each_link_at_activation(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            runner = env.service.runner

            def record(operations, kind='choice'):
                runner.record(build(runner.state, plan(runner, operations, kind=kind)))

            opponent = runner.state['players']['agent']
            source = opponent['hand'][0]
            name = opponent['cards'][str(source['card_id'])]['name']
            first = {'id': 'first', 'actor': 'agent', 'name': name, 'costs': [{'kind': 'banish'}]}
            source_ref = source['instance_id']
            human_card, cost = runner.state['players']['human']['hand'][:2]
            second = {'id': 'second', 'actor': 'human', 'card': human_card['instance_id'],
                      'costs': [{'kind': 'discard', 'instance_id': cost['instance_id']}]}
            record([
                {'op': 'move', 'card': human_card['instance_id'], 'to': ['players', 'human', 'graveyard']},
            ])
            record([
                {'op': 'move', 'card': source_ref, 'to': ['players', 'agent', 'banished']},
                {'op': 'chain', 'value': [first]},
                {'op': 'decision', 'value': {'actor': 'human', 'window': 'chain_response'}},
            ], kind='activate')
            record([
                {'op': 'move', 'card': cost['instance_id'], 'to': ['players', 'human', 'graveyard']},
                {'op': 'chain', 'value': [first, second]},
                {'op': 'decision', 'value': {'actor': 'agent', 'window': 'chain_response'}},
            ], kind='respond')
            record([
                {'op': 'move', 'card': source_ref, 'to': ['players', 'agent', 'graveyard']},
            ])
            first_display, second_display = self.call(env, 'board_snapshot')['chain']
            self.assertEqual(first_display['movement'], {'from': 'hand', 'to': 'banished'})
            self.assertEqual(second_display['movement'], {'from': 'graveyard', 'to': 'graveyard'})
            self.assertEqual(second_display['costs'], ['discard'])
            self.assertNotIn(cost['instance_id'], json.dumps(second_display))

    def test_spectator_projection_and_recovery_failure(self):
        self.prepare()
        self.edison['mode'] = 'agent-vs-agent'
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            runner = env.service.runner
            open_window(runner, 'human')
            prompt = packet(runner)
            prompt['question'] = 'PRIVATE_PLAYER_ONE_CHOICE'
            runner.workflow.present(prompt)
            display = self.call(env, 'interaction')
            self.assertEqual(display['perspective'], 'public')
            self.assertIsNone(display['decision'])
            self.assertFalse(display['awaiting_input'])
            self.assertNotIn('PRIVATE_PLAYER_ONE_CHOICE', json.dumps(display))
            for player in display['context']['state']['players'].values():
                self.assertNotIn('hand', player)
            board = self.call(env, 'board_snapshot')
            self.assertTrue(all('hand' not in player and 'extra_deck' not in player
                                for player in board['players'].values()))
            self.assertNotIn('PRIVATE_PLAYER_ONE_CHOICE', json.dumps(board))
            self.assertNotIn('options', board)
            runner._recovery_required = True
            result = env.request(self.envelope('interaction'))
            self.assertFalse(result['ok'])
            self.assertEqual(result['error']['code'], 'recovery_required')

    def test_source_checkout_cli_does_not_require_installed_metadata(self):
        source = self.private.parent / 'source-without-metadata'
        shutil.copytree(fixtures.REPO / 'harness', source / 'harness',
                        ignore=shutil.ignore_patterns('__pycache__'))
        completed = subprocess.run([sys.executable, '-S', '-m', 'harness.cli', 'duel', '--repo', str(self.repo)],
                                   cwd=source, input=json.dumps(self.envelope('describe')) + '\n',
                                   text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['result']['protocol'], PROTOCOL)

    def test_real_cli_stream_and_single_request_resume(self):
        self.prepare()
        command = [sys.executable, '-m', 'harness.cli', 'duel', '--repo', str(self.repo),
                   '--private-root', str(self.private)]
        messages = [self.envelope('preflight', host_capabilities=HOST),
                    self.envelope('start', config=self.edison, rules_text=self.rules), self.envelope('interaction')]
        completed = subprocess.run(command, input='not json\n' + '\n'.join(map(json.dumps, messages)) + '\n',
                                   text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(rows), 4)
        self.assertFalse(rows[0]['ok'])
        self.assertTrue(all(row['ok'] for row in rows[1:]), rows)
        initial = rows[-1]['result']['context']['state']
        request = self.private / 'request.json'
        request.write_text(json.dumps(self.envelope('interaction')), encoding='utf-8')
        completed = subprocess.run([*command, '--game-id', 'edison-headless', '--request-file', str(request)],
                                   text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['result']['context']['state'], initial)
        request.write_text(json.dumps(self.envelope('unknown')), encoding='utf-8')
        rejected = subprocess.run([*command, '--request-file', str(request)], capture_output=True, timeout=15)
        self.assertEqual(rejected.returncode, 1)

    def test_fixed_position_used_by_benchmark_is_resumable_through_same_api(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            state = deepcopy(env.service.runner.state)
            config = deepcopy(env.service.runner.configuration)
        output = self.private.parent / 'scenario'
        path, game = create_position(output, position_id='scenario-one', configuration=config,
                                     state=state, rules_text=self.rules)
        with DuelEnvironment(output / 'archive', output / 'private') as env:
            self.assertEqual(self.call(env, 'games')[0]['game_id'], 'scenario-one')
            self.call(env, 'resume', game_id='scenario-one')
            projection = self.call(env, 'interaction')
            self.assertEqual(len(projection['context']['state']['players']['human']['hand']), 5)
            self.assertEqual(env.service.runner.state, state)
        with self.assertRaises(ValueError):
            create_position(output, position_id='scenario-one', configuration=config, state=state, rules_text=self.rules)
        with self.assertRaises(ValueError):
            create_position(output, position_id='../escape', configuration=config, state=state, rules_text=self.rules)
        with DuelRunner(path, game) as runner:
            self.assertEqual(runner.state, state)
