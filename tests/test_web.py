"""Browser boundary tests using real persisted duel decisions."""
import json
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import test_orchestrator as fixtures
from test_workflow import open_window, packet
from harness.web.server import snapshot, start_server


class WebTests(unittest.TestCase):
    setUp = fixtures.OrchestratorTests.setUp
    tearDown = fixtures.OrchestratorTests.tearDown
    service = fixtures.OrchestratorTests.service

    def test_player_snapshot_and_opponent_menu_filter(self):
        service = self.service('managed')
        runner = service.runner
        open_window(runner)
        runner.workflow.present(packet(runner))
        data = snapshot(service)
        self.assertTrue(data['can_reply'])
        self.assertIn('hand', data['state']['players']['human'])
        self.assertNotIn('hand', data['state']['players']['agent'])
        self.assertNotIn('remaining_deck_order', json.dumps(data))
        self.assertNotIn('guides', data)
        self.assertNotIn('hand_refs', data['decision'])
        runner.workflow.submit(data['decision']['decision_id'], 'browser', '1')
        self.assertFalse(snapshot(service)['can_reply'])

    def test_http_auth_reply_and_stale_decision(self):
        service = self.service('managed')
        open_window(service.runner)
        service.runner.workflow.present(packet(service.runner))
        server, url = start_server(service, 0)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base, token = url.split('/#token=')
        with self.assertRaises(HTTPError) as error:
            urlopen(base + '/api/state')
        self.assertEqual(error.exception.code, 403)
        with urlopen(Request(base + '/api/state', headers={'X-Duel-Token': token})) as response:
            data = json.load(response)
        body = {'decision_id': data['decision']['decision_id'], 'request_id': 'web', 'response': '1'}
        def reply(body):
            return urlopen(Request(base + '/api/reply', data=json.dumps(body).encode(), headers={'X-Duel-Token': token}))
        with reply(body) as response:
            self.assertTrue(json.load(response)['ok'])
        with reply(body) as response:
            self.assertTrue(json.load(response)['ok'])
        with self.assertRaises(HTTPError) as error:
            reply({**body, 'decision_id': 'stale', 'request_id': 'different'})
        self.assertEqual(error.exception.code, 409)
        with self.assertRaises(HTTPError):
            reply({**body, 'op': 'context', 'player': 'moderator'})
