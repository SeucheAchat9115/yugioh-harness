"""Exercise native Windows lock calls without pretending this is a Windows host."""
import errno
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from harness.storage import locking


class WindowsLockingTests(unittest.TestCase):
    def test_locks_first_byte_and_normalizes_contention(self):
        api = SimpleNamespace(LK_NBLCK=1, locking=Mock())
        with tempfile.TemporaryFile() as handle:
            with patch.object(locking, 'os', SimpleNamespace(name='nt')), patch.object(locking, 'msvcrt', api, create=True):
                locking.lock_handle(handle)
                self.assertEqual(handle.tell(), 0)
                api.locking.assert_called_once_with(handle.fileno(), 1, 1)
                handle.seek(0)
                self.assertEqual(handle.read(), b'\0')
                api.locking.side_effect = OSError(errno.EACCES, 'Locked')
                with self.assertRaises(BlockingIOError):
                    locking.lock_handle(handle)
                api.locking.side_effect = OSError(errno.EBADF, 'Bad file')
                with self.assertRaises(OSError) as failure:
                    locking.lock_handle(handle)
                self.assertEqual(failure.exception.errno, errno.EBADF)
