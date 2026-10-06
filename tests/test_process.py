"""Liveness probes must not interrupt the console or terminate the arena."""
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from harness.integration import process


class ProcessTests(unittest.TestCase):
    def test_live_child_survives_repeated_checks(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            for _ in range(10):
                process.check_process(child.pid)
                self.assertIsNone(child.poll())
            child.terminate()
            child.wait(timeout=5)
            with self.assertRaises(ProcessLookupError):
                process.check_process(child.pid)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)

    def test_invalid_pid_never_signals(self):
        for pid in (0, -1, True, '123'):
            with self.assertRaises(ValueError):
                process.check_process(pid)

    def test_windows_wait_and_handle_cleanup(self):
        import ctypes
        api = SimpleNamespace(OpenProcess=Mock(return_value=123),
                              WaitForSingleObject=Mock(return_value=258),
                              CloseHandle=Mock())
        with patch.object(process, 'os', SimpleNamespace(name='nt')), \
             patch.object(ctypes, 'WinDLL', return_value=api, create=True):
            process.check_process(456)
            api.OpenProcess.assert_called_once_with(0x00100000, False, 456)
            api.WaitForSingleObject.assert_called_once_with(123, 0)
            api.CloseHandle.assert_called_once_with(123)
            api.WaitForSingleObject.return_value = 0
            with self.assertRaises(ProcessLookupError):
                process.check_process(456)
            self.assertEqual(api.CloseHandle.call_count, 2)
