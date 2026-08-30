"""Save / close / launch helpers for Audacity for Agents.

Never force-kill. Never talk to stock Audacity.exe / ToSrvPipe.

Set AUDACITY_FOR_AGENTS_EXE to the full path of AudacityForAgents.exe,
or put that binary on PATH.
"""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from audacity_pipe import FROM_PIPE, TO_PIPE, AudacityPipe, quote_path

IMAGE = "AudacityForAgents.exe"


def agent_exe() -> Path:
    env = os.environ.get("AUDACITY_FOR_AGENTS_EXE")
    if env:
        return Path(env)
    found = shutil.which("AudacityForAgents.exe") or shutil.which("AudacityForAgents")
    if found:
        return Path(found)
    raise FileNotFoundError(
        "Audacity for Agents not found. Set AUDACITY_FOR_AGENTS_EXE to the "
        "full path of AudacityForAgents.exe, or add that directory to PATH."
    )


def agent_cfg() -> Path:
    return agent_exe().parent / "Portable Settings" / "audacity.cfg"


def agent_session_data() -> Path:
    return agent_exe().parent / "Portable Settings" / "SessionData"


def audacity_running() -> bool:
    """True if Audacity for Agents is running — not stock Audacity.exe."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {IMAGE}", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return IMAGE in out
    except Exception:  # noqa: BLE001
        return False


def wait_file_stable(
    path: Path,
    *,
    min_bytes: int = 1_000_000,
    settle_sec: float = 3.0,
    timeout_sec: float = 600.0,
) -> None:
    """Wait until path exists, is non-tiny, and size stops changing."""
    deadline = time.time() + timeout_sec
    last_size = -1
    stable_since: float | None = None
    while time.time() < deadline:
        if path.is_file():
            size = path.stat().st_size
            if size >= min_bytes:
                if size == last_size:
                    if stable_since is None:
                        stable_since = time.time()
                    elif time.time() - stable_since >= settle_sec:
                        return
                else:
                    stable_since = None
                    last_size = size
        time.sleep(0.5)
    raise TimeoutError(f"Project file did not stabilize: {path}")


def save_project(pipe: AudacityPipe, path: Path, *, timeout_sec: float = 900.0) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"save {path}", flush=True)
    old_timeout = pipe.timeout
    pipe.timeout = max(old_timeout, timeout_sec)
    try:
        pipe.do_ok(
            f"SaveProject2: Filename={quote_path(path)} AddToHistory=False"
        )
    finally:
        pipe.timeout = old_timeout
    print("  waiting for file to settle...", flush=True)
    wait_file_stable(path, timeout_sec=timeout_sec)
    print(f"  saved ok ({path.stat().st_size / (1024 * 1024):.0f} MB)", flush=True)


def snapshot_aup3(src: Path, dest: Path) -> None:
    """Optional SQLite backup of a live .aup3 to another path."""
    import sqlite3

    src = Path(src)
    dest = Path(dest)
    if dest.exists():
        dest.unlink()
    src_db = sqlite3.connect(str(src), timeout=120.0)
    dst_db = sqlite3.connect(str(dest), timeout=120.0)
    try:
        src_db.backup(dst_db)
        dst_db.commit()
        dst_db.execute("DELETE FROM autosave")
        dst_db.commit()
        dst_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        mode = dst_db.execute("PRAGMA journal_mode=DELETE").fetchone()
        print(
            f"  cleared autosave; journal_mode={mode[0] if mode else '?'}",
            flush=True,
        )
        dst_db.execute("VACUUM")
    finally:
        dst_db.close()
        src_db.close()
    mb = dest.stat().st_size / (1024 * 1024)
    print(f"  handoff {dest.name} ({mb:.0f} MB)", flush=True)


def close_project(pipe: AudacityPipe) -> None:
    """Detach the saved .aup3 and leave the hidden frame on a new empty project.

    Call after save_project. The process and pipes stay up.
    """
    print("close project", flush=True)
    pipe.do_ok("Close:")
    time.sleep(1.0)


def save_and_close(pipe: AudacityPipe, path: Path, *, timeout_sec: float = 900.0) -> None:
    save_project(pipe, path, timeout_sec=timeout_sec)
    close_project(pipe)


def new_empty_project(pipe: AudacityPipe) -> None:
    pipe.do_ok("New:")
    time.sleep(0.5)


def exit_audacity_clean(pipe: AudacityPipe) -> None:
    """Ask the agent to quit. Prefer after Close: so Exit: does not prompt."""
    print("exit Audacity for Agents", flush=True)
    try:
        pipe.do("Exit:")
    except Exception as exc:  # noqa: BLE001
        print(f"  Exit: reply/pipe ended ({exc})", flush=True)
    deadline = time.time() + 120
    while time.time() < deadline:
        if not audacity_running():
            print("  Audacity for Agents exited", flush=True)
            return
        time.sleep(0.5)
    raise TimeoutError(
        "AudacityForAgents.exe did not exit after Exit:. Do not force-kill; "
        "end the task from Task Manager only if a window appeared (it should not)."
    )


def launch_agent() -> None:
    exe = agent_exe()
    if not exe.is_file():
        raise FileNotFoundError(f"Audacity for Agents not found: {exe}")
    print(f"launch {exe} --batch", flush=True)
    subprocess.Popen(
        [str(exe), "--batch"],
        cwd=str(exe.parent),
        stdout=None,
        stderr=None,
    )


def ensure_agent_running(wait: float = 90.0) -> None:
    """Start AudacityForAgents.exe --batch if needed, then wait for the pipe."""
    if not audacity_running():
        launch_agent()
        time.sleep(2.5)
    ensure_pipes_ready(wait=wait)


def _wait_named_pipe(name: str, timeout_ms: int = 1000) -> bool:
    return bool(ctypes.windll.kernel32.WaitNamedPipeW(name, timeout_ms))


def ensure_pipes_ready(wait: float = 90.0) -> None:
    """Wait until the agent is listening. Do not open a throwaway client."""
    deadline = time.time() + wait
    last: Exception | None = None
    while time.time() < deadline:
        if not audacity_running():
            try:
                launch_agent()
            except FileNotFoundError:
                raise
            time.sleep(1.0)
            continue
        if _wait_named_pipe(TO_PIPE, 1000) or _wait_named_pipe(FROM_PIPE, 200):
            time.sleep(0.4)
            return
        last = RuntimeError(f"waiting for {TO_PIPE}")
        time.sleep(0.5)
    raise RuntimeError(f"Audacity for Agents pipes not ready: {last}")


def reconnect_pipe(pipe: AudacityPipe | None = None) -> AudacityPipe:
    """Keep using the live pipe after Close:. Relaunch the agent only if it died."""
    if pipe is not None:
        try:
            if pipe.alive():
                reply = pipe.do("Message: Text=reconnect-ping")
                if "BatchCommand finished: OK" in reply:
                    return pipe
        except Exception:  # noqa: BLE001
            pass
        try:
            pipe.close()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    ensure_agent_running()
    fresh = AudacityPipe(timeout=1800.0)
    fresh.connect()
    return fresh


def clear_active_projects(cfg: Path | None = None) -> int:
    """Remove [ActiveProjects] entries. Refuses if the agent is running."""
    cfg = Path(cfg) if cfg is not None else agent_cfg()
    if audacity_running():
        raise RuntimeError(
            "Audacity for Agents is still running — quit it cleanly before "
            "clearing ActiveProjects"
        )
    if not cfg.is_file():
        return 0
    text = cfg.read_text(encoding="utf-8", errors="replace")
    new, n = re.subn(
        r"(?ms)^\[ActiveProjects\]\s*\n(?:^[^=\n]+=[^\n]*\n)*",
        "[ActiveProjects]\n",
        text,
    )
    if n:
        cfg.write_text(new, encoding="utf-8")
    return n


def clear_session_data() -> None:
    if audacity_running():
        raise RuntimeError(
            "Audacity for Agents is still running — quit before clearing SessionData"
        )
    session = agent_session_data()
    if session.is_dir():
        shutil.rmtree(session)
        session.mkdir(parents=True, exist_ok=True)
