"""A visible Windows mailbox response is not necessarily readable yet."""
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from harness.integration import arena


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'server.json').write_text(json.dumps({'pid': os.getpid()}), encoding='utf-8')
        credentials = self.root / 'credentials.json'
        credentials.write_text(json.dumps({'role': 'human', 'mailbox': str(self.root), 'token': 'test'}), encoding='utf-8')
        self.client = arena.ArenaClient(credentials)

    def test_windows_waits_for_access_without_resending_request(self):
        read = Path.read_text
        denied = PermissionError(13, 'Sharing violation')
        replies = iter([FileNotFoundError(), denied, '{"ok": true}'])

        def response(path, *args, **kwargs):
            if not path.name.endswith('.response.json'):
                return read(path, *args, **kwargs)
            result = next(replies)
            if isinstance(result, Exception):raise result
            return result

        with patch.object(arena, 'os', SimpleNamespace(name='nt')), \
             patch.object(Path, 'read_text', response), \
             patch.object(arena, 'save', wraps=arena.save) as send, \
             patch.object(arena.time, 'sleep'):
            self.assertEqual(self.client.request({'op': 'view'}), {'ok': True})
            send.assert_called_once()
        self.assertEqual(list(self.root.glob('*.request.json')), [])

    def test_persistent_permission_error_is_preserved_at_deadline(self):
        read = Path.read_text
        denied = PermissionError(13, 'Access denied')

        def response(path, *args, **kwargs):
            if path.name.endswith('.response.json'):raise denied
            return read(path, *args, **kwargs)

        with patch.object(arena, 'os', SimpleNamespace(name='nt')), \
             patch.object(Path, 'read_text', response), \
             patch.object(arena.time, 'monotonic', side_effect=[0, 1, 31]), \
             patch.object(arena.time, 'sleep'):
            with self.assertRaises(PermissionError) as caught:
                self.client.request({'op': 'view'})
            self.assertIs(caught.exception, denied)

    def test_other_platform_permissions_and_bad_json_are_not_retried(self):
        read = Path.read_text
        for reply, exception in [(PermissionError(13, 'Access denied'), PermissionError),
                                 ('broken JSON', json.JSONDecodeError)]:
            def response(path, *args, **kwargs):
                if not path.name.endswith('.response.json'):return read(path, *args, **kwargs)
                if isinstance(reply, Exception):raise reply
                return reply
            with self.subTest(reply=reply), \
                 patch.object(arena, 'os', SimpleNamespace(name='posix')), \
                 patch.object(Path, 'read_text', response), \
                 patch.object(arena.time, 'sleep') as wait:
                with self.assertRaises(exception):self.client.request({'op': 'view'})
                wait.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Requires native Windows sharing semantics')
    def test_native_windows_exclusive_response_handle(self):
        import ctypes
        from ctypes import wintypes
        from harness.storage.atomic import save
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        api.CreateFileW.restype = wintypes.HANDLE
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        denied = threading.Event()
        read = Path.read_text
        releases = []

        def send(path, data):
            response = path.with_name(path.name.replace('.request.json', '.response.json'))
            save(response, {'ok': True})
            handle = api.CreateFileW(str(response), 0x80000000, 0, None, 3, 0, None)
            if handle == ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
            def release():
                try:denied.wait(5)
                finally:api.CloseHandle(handle)
            thread = threading.Thread(target=release)
            thread.start()
            releases.append(thread)

        def response(path, *args, **kwargs):
            try:return read(path, *args, **kwargs)
            except PermissionError:
                denied.set()
                raise

        try:
            with patch.object(arena, 'save', side_effect=send) as sent, \
                 patch.object(Path, 'read_text', response):
                self.assertEqual(self.client.request({'op': 'view'}), {'ok': True})
                sent.assert_called_once()
                self.assertTrue(denied.is_set())
        finally:
            for thread in releases:thread.join(timeout=6)
