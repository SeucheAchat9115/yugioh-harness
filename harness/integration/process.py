"""Check a local process without sending Windows console control events."""
import os


def check_process(pid):
    """Raise when the process is gone or inaccessible; never signal it."""
    if type(pid) is not int or pid <= 0:
        raise ValueError('Invalid process ID')
    if os.name != 'nt':
        os.kill(pid, 0)
        return
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    handle = api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: no process with this PID
            raise ProcessLookupError(pid)
        raise ctypes.WinError(error)
    try:
        status = api.WaitForSingleObject(handle, 0)
        if status == 0:  # WAIT_OBJECT_0: process has exited
            raise ProcessLookupError(pid)
        if status != 258:  # WAIT_TIMEOUT: still running
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(handle)
