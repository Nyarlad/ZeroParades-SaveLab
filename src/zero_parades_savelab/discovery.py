"""Local save discovery and a read-only Windows process check."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path

from .errors import SafetyError


def default_save_directory():
    return Path.home() / "AppData/LocalLow/ZAUM Studio/Zero Parades/Saves"


def default_data_directory():
    return (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
        / "ZeroParadesSaveLab"
    )


def is_game_process_name(name):
    # Exact executable identity: the editor's own ZeroParades-SaveLab.exe
    # must never be mistaken for the game.
    return name.casefold() == "zeroparades.exe"


def ensure_game_closed():
    if os.name != "nt":
        raise SafetyError("Applying/restoring originals is supported on Windows only.")

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise SafetyError("Cannot enumerate processes. Close the game and retry.")
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(handle, ctypes.byref(entry)):
            raise SafetyError("Process enumeration failed; refusing to assume the game is closed.")
        while True:
            if is_game_process_name(entry.szExeFile):
                raise SafetyError("Zero Parades is running. Close it before applying or restoring.")
            if not kernel.Process32NextW(handle, ctypes.byref(entry)):
                if ctypes.get_last_error() not in (0, 18):
                    raise SafetyError("Process enumeration was incomplete.")
                break
    finally:
        kernel.CloseHandle(handle)
