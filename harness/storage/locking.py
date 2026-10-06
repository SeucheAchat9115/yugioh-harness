"""Shared nonblocking writer lock for runner and all legacy mutation commands."""
from contextlib import contextmanager
import errno
import os

if os.name == "nt":
    import msvcrt
else:
    import fcntl
from pathlib import Path
import threading

_local = threading.local()


class WriterHandles:
    def __init__(self):
        self.handles = []
        self.closed = False

    def close(self):
        for handle in reversed(self.handles):
            handle.close()
        self.closed = True


def lock_handle(handle):
    """Nonblocking process lock, normalized to BlockingIOError on contention."""
    if os.name == 'nt':
        # Windows byte-range locks require a byte to lock and a stable position.
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'\0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise BlockingIOError(errno.EAGAIN, 'Duel writer already locked') from error
            raise
    else:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def acquire_writer(state_path, game_dir=None):
    group = WriterHandles()
    paths = [Path(state_path).resolve().with_name('runner.lock')]
    if game_dir is not None and Path(game_dir).exists():
        paths.append(Path(game_dir).resolve() / '.writer.lock')
    try:
        for path in paths:
            handle = path.open('a+b')
            group.handles.append(handle)
            path.chmod(0o600)
            lock_handle(handle)
    except BaseException:
        group.close()
        raise
    return group


@contextmanager
def writer_lock(state_path, game_dir=None):
    """Nested legacy writes may share a lock; a live runner never joins this pool."""
    key = (str(Path(state_path).resolve()), str(Path(game_dir).resolve()) if game_dir is not None else None)
    held = getattr(_local, 'held', None)
    if held is None:
        held = _local.held = {}
    if key in held:
        yield
        return
    handle = acquire_writer(state_path, game_dir)
    held[key] = handle
    try:
        yield
    finally:
        held.pop(key)
        handle.close()
