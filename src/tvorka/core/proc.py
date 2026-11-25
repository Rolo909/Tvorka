"""Process lifetime helpers shared by the local server and the command runner."""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ Windows: die with the app
def kill_with_parent(process: subprocess.Popen[bytes]) -> Any:
    """Put a process and its descendants in a kill-on-close job object.

    The caller owns the returned handle.
    """
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class _Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _Basic), ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                                 wintypes.DWORD)
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _Extended()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)) and \
        kernel32.AssignProcessToJobObject(job, int(process._handle))  # type: ignore[attr-defined]
    if not ok:
        log.warning("process is not tied to the app (error %s)", ctypes.get_last_error())
        close_handle(job)
        return None
    return job


def close_handle(handle: Any) -> None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        close = ctypes.WinDLL("kernel32").CloseHandle
        close.argtypes = (wintypes.HANDLE,)
        close(handle)
