"""Readiness gates reject unsafe storage and unsupported host declarations before deal."""
import shutil
import unittest
from unittest.mock import patch

from harness.preflight import inspect
from harness.integration.service import DuelService
import test_session as fixtures
from smoke_install import HOST


class PreflightTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown

    def prepare(self):
        for name in ('AGENTS.md', 'agents/orchestrator/AGENT.md', 'skills/duel-orchestrator/SKILL.md'):
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixtures.REPO / name, target)

    def test_host_evidence_required_and_unsafe_storage_rejected(self):
        self.prepare()
        self.assertIsNone(inspect(self.repo, self.private)['host_ready'])
        self.assertTrue(inspect(self.repo, self.private, HOST)['ready'])
        self.assertFalse(inspect(self.repo, self.repo / 'private', HOST)['runtime_ready'])
        self.assertFalse(inspect(self.repo, self.private, {**HOST, 'fresh_history': False})['ready'])
        self.assertFalse(inspect(self.repo, self.private, {**HOST, 'evidence': ''})['ready'])
        with patch('harness.preflight._writable', side_effect=PermissionError):
            self.assertFalse(inspect(self.repo, self.private, HOST)['runtime_ready'])

    def test_preflight_gate_before_dealing_and_stale_declaration_cleared(self):
        self.prepare()
        service = DuelService(self.repo, self.private, require_host=True)
        self.addCleanup(service.close)
        request = {'op': 'start', 'config': self.config, 'rules_text': 'Test fixture'}
        with patch('harness.integration.service.start') as start:
            self.assertFalse(service.request(request)['ok'])
            start.assert_not_called()
        self.assertTrue(service.request({'op': 'preflight', 'host_capabilities': HOST})['result']['ready'])
        self.assertFalse(service.request({'op': 'preflight', 'host_capabilities': {**HOST, 'execution': False}})['result']['ready'])
        with patch('harness.integration.service.start') as start:
            self.assertFalse(service.request(request)['ok'])
            start.assert_not_called()
        service.preflight(HOST)
        # A damaged selected bundle must still fail after a successful preflight.
        (self.repo / self.config['agent_deck'] / 'guide.md').write_text('Changed guide', encoding="utf-8")
        with patch('harness.integration.service.start') as start:
            self.assertFalse(service.request(request)['ok'])
            start.assert_not_called()
