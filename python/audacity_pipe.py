"""Audacity-for-Agents mod-script-pipe client (Windows)."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

TO_PIPE = os.environ.get("AUDACITY_TO_PIPE", r"\\.\pipe\ToAudacityForAgents")
FROM_PIPE = os.environ.get("AUDACITY_FROM_PIPE", r"\\.\pipe\FromAudacityForAgents")
EOL = "\r\n\0"


class AudacityPipe:
    """Send macro/script commands to Audacity for Agents."""

    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout
        self._write = None
        self._read = None
        self._reply = ""
        self._reply_ready = threading.Event()
        self._reader_ready = threading.Event()
        self._reader_broken = threading.Event()
        self._lock = threading.Lock()

    def connect(self, wait: float = 60.0) -> None:
        deadline = time.time() + wait
        last_err: Exception | None = None

        while time.time() < deadline:
            self._reader_ready.clear()
            self._reader_broken.clear()
            self._reply_ready.clear()
            self._reply = ""
            self._write = None
            self._read = None

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
                time.sleep(0.5)
                continue

            try:
                self._write = open(TO_PIPE, "w", newline="")
            except OSError as exc:
                last_err = exc
                self._reader_broken.set()
                time.sleep(0.5)
                continue

            time.sleep(0.75)
            try:
                for _ in range(8):
                    if self._reader_broken.is_set():
                        raise RuntimeError("read pipe broke during handshake")
                    reply = self.do("Message: Text=ping")
                    if "BatchCommand finished: OK" in reply:
                        return
                    time.sleep(0.4)
                last_err = RuntimeError(f"handshake failed: {reply!r}")
            except Exception as exc:  # noqa: BLE001 — retry connect
                last_err = exc
                try:
                    if self._write is not None:
                        self._write.close()
                except OSError:
                    pass
                self._write = None
                self._reader_broken.set()
                time.sleep(0.5)
                continue

        raise RuntimeError(
            "Could not connect to Audacity for Agents script pipes. "
            f"Is AudacityForAgents.exe running? ({TO_PIPE})"
        ) from last_err

    def close(self) -> None:
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
        self._reader_broken.set()

    def alive(self) -> bool:
        return self._write is not None and not self._reader_broken.is_set()

    def __enter__(self) -> "AudacityPipe":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _reader(self) -> None:
        try:
            read_pipe = open(FROM_PIPE, "r", newline="")
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
