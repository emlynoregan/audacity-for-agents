"""Audacity-for-Agents mod-script-pipe client (Windows).

Uses Win32 CreateFileW / ReadFile / WriteFile. Do **not** use builtin
open() on these pipes — on CPython 3.13 (and some earlier 3.x) that raises
OSError EINVAL and can leave the single server pipe instance busy so Exit:
cannot attach.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes
from pathlib import Path

TO_PIPE = os.environ.get("AUDACITY_TO_PIPE", r"\\.\pipe\ToAudacityForAgents")
FROM_PIPE = os.environ.get("AUDACITY_FROM_PIPE", r"\\.\pipe\FromAudacityForAgents")
EOL = "\r\n\0"

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_PIPE_BUSY = 231
ERROR_SEM_TIMEOUT = 121
PIPE_READMODE_MESSAGE = 0x00000002

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
_k32.CreateFileW.restype = wintypes.HANDLE
_k32.ReadFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
_k32.ReadFile.restype = wintypes.BOOL
_k32.WriteFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
_k32.WriteFile.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL
_k32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_k32.WaitNamedPipeW.restype = wintypes.BOOL
_k32.SetNamedPipeHandleState.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_k32.SetNamedPipeHandleState.restype = wintypes.BOOL
_k32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
_k32.FlushFileBuffers.restype = wintypes.BOOL


def _err() -> int:
    return ctypes.get_last_error()


def _close_handle(handle) -> None:
    if handle is None or handle == INVALID_HANDLE_VALUE:
        return
    try:
        _k32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        pass


def _create_pipe_file(name: str, access: int, *, wait_ms: int = 2000):
    """CreateFileW on a named pipe; wait briefly if busy."""
    deadline = time.time() + max(wait_ms / 1000.0, 0.05)
    last = 0
    while True:
        handle = _k32.CreateFileW(
            name,
            access,
            0,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle != INVALID_HANDLE_VALUE:
            mode = wintypes.DWORD(PIPE_READMODE_MESSAGE)
            _k32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None)
            return handle
        last = _err()
        if last == ERROR_PIPE_BUSY:
            if not _k32.WaitNamedPipeW(name, min(1000, wait_ms)):
                last = _err()
            if time.time() >= deadline:
                raise OSError(last, f"CreateFileW busy: {name} (winerr={last})")
            continue
        if time.time() >= deadline:
            raise OSError(last, f"CreateFileW failed: {name} (winerr={last})")
        time.sleep(0.05)


class _PipeWriter:
    def __init__(self, handle) -> None:
        self._h = handle

    def write(self, text: str) -> None:
        data = text.encode("utf-8", errors="replace")
        written = wintypes.DWORD(0)
        ok = _k32.WriteFile(self._h, data, len(data), ctypes.byref(written), None)
        if not ok:
            raise OSError(_err(), "WriteFile failed on ToAudacityForAgents")
        _k32.FlushFileBuffers(self._h)

    def flush(self) -> None:
        _k32.FlushFileBuffers(self._h)

    def close(self) -> None:
        _close_handle(self._h)
        self._h = None


class _PipeReader:
    def __init__(self, handle) -> None:
        self._h = handle
        self._buf = ""

    def readline(self) -> str:
        """Return one text line including trailing \\n, or '' on EOF/break."""
        while "\n" not in self._buf:
            chunk = self._read_message()
            if chunk is None:
                if not self._buf:
                    return ""
                # Flush remainder as a final line
                line, self._buf = self._buf, ""
                return line if line.endswith("\n") else line + "\n"
            self._buf += chunk
        line, self._buf = self._buf.split("\n", 1)
        return line + "\n"

    def _read_message(self) -> str | None:
        buf = ctypes.create_string_buffer(8192)
        got = wintypes.DWORD(0)
        ok = _k32.ReadFile(self._h, buf, len(buf), ctypes.byref(got), None)
        if not ok or got.value == 0:
            return None
        return buf.raw[: got.value].decode("utf-8", errors="replace")

    def close(self) -> None:
        _close_handle(self._h)
        self._h = None


class AudacityPipe:
    """Send macro/script commands to Audacity for Agents."""

    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout
        self._write: _PipeWriter | None = None
        self._read: _PipeReader | None = None
        self._reply = ""
        self._reply_ready = threading.Event()
        self._reader_ready = threading.Event()
        self._reader_broken = threading.Event()
        self._lock = threading.Lock()

    def connect(self, wait: float = 60.0) -> None:
        deadline = time.time() + wait
        last_err: Exception | None = None

        while time.time() < deadline:
            self.close()
            self._reader_ready.clear()
            self._reader_broken.clear()
            self._reply_ready.clear()
            self._reply = ""

            reader = threading.Thread(target=self._reader, daemon=True)
            reader.start()

            opened = False
            while time.time() < deadline:
                if self._reader_broken.is_set():
                    break
                if self._reader_ready.wait(0.25):
                    opened = True
                    break
            if not opened:
                last_err = RuntimeError(f"Could not open {FROM_PIPE}")
                time.sleep(0.35)
                continue

            try:
                to_handle = _create_pipe_file(
                    TO_PIPE, GENERIC_WRITE, wait_ms=2000
                )
                self._write = _PipeWriter(to_handle)
            except OSError as exc:
                last_err = exc
                self._reader_broken.set()
                self.close()
                time.sleep(0.35)
                continue

            time.sleep(0.5)
            try:
                reply = ""
                for _ in range(8):
                    if self._reader_broken.is_set():
                        raise RuntimeError("read pipe broke during handshake")
                    reply = self.do("Message: Text=ping")
                    if "BatchCommand finished: OK" in reply:
                        return
                    time.sleep(0.35)
                last_err = RuntimeError(f"handshake failed: {reply!r}")
            except Exception as exc:  # noqa: BLE001 — retry connect
                last_err = exc
                self.close()
                time.sleep(0.35)
                continue

        raise RuntimeError(
            "Could not connect to Audacity for Agents script pipes. "
            f"Is AudacityForAgents.exe running? ({TO_PIPE})"
        ) from last_err

    def close(self) -> None:
        self._reader_broken.set()
        if self._write is not None:
            try:
                self._write.close()
            except OSError:
                pass
            self._write = None
        if self._read is not None:
            try:
                self._read.close()
            except OSError:
                pass
            self._read = None

    def alive(self) -> bool:
        return self._write is not None and not self._reader_broken.is_set()

    def __enter__(self) -> "AudacityPipe":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _reader(self) -> None:
        read_pipe: _PipeReader | None = None
        try:
            handle = _create_pipe_file(FROM_PIPE, GENERIC_READ, wait_ms=3000)
            read_pipe = _PipeReader(handle)
        except OSError:
            self._reader_broken.set()
            return
        self._read = read_pipe
        self._reader_ready.set()
        try:
            while True:
                try:
                    line = read_pipe.readline()
                except OSError:
                    self._reader_broken.set()
                    return
                if line == "":
                    self._reader_broken.set()
                    return
                message = ""
                while line != "\n":
                    message += line
                    try:
                        line = read_pipe.readline()
                    except OSError:
                        self._reader_broken.set()
                        return
                    if line == "":
                        self._reader_broken.set()
                        return
                with self._lock:
                    self._reply = message
                    self._reply_ready.set()
        finally:
            try:
                if read_pipe is not None:
                    read_pipe.close()
            except OSError:
                pass

    def do(self, command: str) -> str:
        if self._write is None:
            raise RuntimeError("Not connected")
        if self._reader_broken.is_set():
            raise RuntimeError("Audacity read pipe is broken")

        with self._lock:
            self._reply = ""
            self._reply_ready.clear()

        self._write.write(command + EOL)
        self._write.flush()

        if not self._reply_ready.wait(self.timeout):
            raise TimeoutError(f"No reply for command: {command}")

        with self._lock:
            return self._reply

    def do_ok(self, command: str) -> str:
        reply = self.do(command)
        if "Failed" in reply and "BatchCommand finished: OK" not in reply:
            raise RuntimeError(f"Audacity command failed:\n  {command}\n  {reply}")
        return reply


def quote_path(path: str | Path) -> str:
    """Path quoting for Audacity command parameters (forward slashes)."""
    return '"' + str(path).replace("\\", "/") + '"'
