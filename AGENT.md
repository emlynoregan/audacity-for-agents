# Agent guide — Audacity for Agents

**Start here if you are a coding agent** that must build or mix audio through Audacity for Agents.

You drive a **headless** Audacity 3.7 process over named pipes. Humans keep using **stock** Audacity for listening. You do not attach to the GUI copy.

Companion code: [`python/`](./python/). Project overview: [`README.md`](./README.md).

## What you talk to

| | Stock GUI (humans) | Audacity for Agents (you) |
|--|--------------------|---------------------------|
| Process | `Audacity.exe` | `AudacityForAgents.exe` |
| Pipes | Do **not** use | `\\.\pipe\ToAudacityForAgents` → `FromAudacityForAgents` |
| UI | Normal windows | None. Logs to stderr |
| Config | User app data | `Portable Settings\` next to the exe |

Set `AUDACITY_FOR_AGENTS_EXE` to the full path of `AudacityForAgents.exe` before launching from Python. Optional: `AUDACITY_TO_PIPE`, `AUDACITY_FROM_PIPE`.

Typical Windows install path after Setup:  
`%LOCALAPPDATA%\Audacity for Agents\AudacityForAgents.exe`  
(the installer can also set that env var and/or PATH). Download: see [`README.md`](./README.md). Build-from-source layout: next to your CMake `Release\` output.

## Hard rules

1. **Never** open, launch, or script stock `Audacity.exe` / `ToSrvPipe`.
2. **Never force-kill** `AudacityForAgents.exe`. Send `Exit:` and wait. Force-kill risks corrupt projects (SQLite WAL / SessionData).
3. **Never `SaveProject2` a `.aup3` the GUI has open.** Save to a path the human is not currently playing. They open your file after you `Close:` on the agent side.
4. **Never `GetInfo:`.** JSON blank lines desync the line-oriented pipe client.
5. Peak-normalize **every imported clip** (default −6 dB in the helpers), then leave mixer `Volume=0`. Pan is fine. Do not use the fader as a substitute for that peak.
6. `Import2` aliases by **basename**. If two sources share a name (e.g. both `piano.wav`), copy each to a unique filename first.
7. If the exe is missing, **stop** and tell the human. Do not fall back to Program Files Audacity.

## Connect

Put `python/` on `sys.path` (or install/copy those modules into your project):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("path/to/audacity-for-agents/python").resolve()))

from audacity_lifecycle import ensure_agent_running
from audacity_pipe import AudacityPipe

ensure_agent_running()       # starts AudacityForAgents.exe --batch if needed
pipe = AudacityPipe(timeout=1800.0)
pipe.connect()               # handshake: Message: Text=ping
```

`ensure_agent_running()` waits until the named pipes exist. Launch cwd is the directory containing the exe so Portable Settings apply. Argv is `--batch`. `--gui` is ignored.

The Python client talks to the pipes with **Win32 `CreateFileW` / `ReadFile` / `WriteFile`**. Do **not** use builtin `open()` on `\\.\pipe\…` — on CPython 3.13 that raises `OSError: [Errno 22] Invalid argument` and can leave the server pipe instance busy so a later `Exit:` cannot attach.

Keep one `pipe` for the batch. After `Close:`, the process and pipes stay up — call `reconnect_pipe(pipe)` (pings; relaunches **only** if the agent died).

## One-project recipe

1. `ensure_agent_running()` + `AudacityPipe.connect()`.
2. `new_empty_project(pipe)` → `New:`.
3. For each WAV: unique-name copy if needed → `Import2: Filename=<quoted>` → `SetTrack: Name="…"` → `normalize_track(pipe, index)` → pan / mute.
4. Mix / compress if needed (commands below).
5. `save_project(pipe, out_path)` → `SaveProject2` + wait until the `.aup3` size stops changing (often 900–1800 s for large sessions).
6. `close_project(pipe)`. Tell the human the **SaveProject2 path** — that is what they open in stock Audacity.
7. More projects: `reconnect_pipe(pipe)` then repeat from step 2. When finished: `exit_audacity_clean(pipe)`.

### Path quoting

Always quote with forward slashes:

```text
Import2: Filename="D:/mixes/stems/vocals.wav"
```

Use `quote_path()` from `audacity_pipe`.

### Unique import names

```python
import shutil
from pathlib import Path

def unique_import_copy(src: Path, staging: Path, name: str) -> Path:
    staging.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
    dest = staging / f"{safe}.wav"
    shutil.copy2(src, dest)
    return dest
```

### Normalize (every import)

```text
Select: Track=N TrackCount=1 Mode=Set Start=0 End=100000
Normalize: PeakLevel=-6 ApplyGain=True RemoveDcOffset=True
SetTrackAudio: Volume=0
```

`End=100000` is seconds — long enough for typical takes. Prefer `normalize_track(pipe, index)` from `audacity_levels`.

## Commands that work

Same 3.7 macro language as stock. Success replies contain `BatchCommand finished: OK` (`pipe.do_ok`).

| Command | Use |
|---------|-----|
| `Message: Text=…` | Handshake / progress. Safe anytime. |
| `New:` | Empty project in the hidden frame. |
| `Import2: Filename=…` | Import audio (quoted path). |
| `Select: Track=N TrackCount=1 Mode=Set Start=0 End=100000` | Select one track. |
| `SetTrack: Name="…"` | Track name. |
| `SetTrackAudio: Volume=0` | Unity fader after normalize. |
| `SetTrackAudio: Pan=-1` / `Pan=1` / `Pan=0` | L / R / centre. |
| `SetTrackAudio: Mute=1` or `Mute=0` | Mute after a bounce. |
| `Normalize: PeakLevel=-6 ApplyGain=True RemoveDcOffset=True` | Working peak. |
| `MixAndRenderToNewTrack:` | Bounce selected tracks to a new track. |
| `SaveProject2: Filename=… AddToHistory=False` | Write `.aup3`. |
| `Export2: Filename=…` | Bounce to WAV/MP3 when you need a file, not a project. |
| `Join:` | Join selected clips. |
| `Close:` | Detach the saved `.aup3`; keep the process. |
| `Exit:` | Quit the agent process. |

### Compressor (3.7 factory-style params)

**Modern** (spoken voice):

```text
Compressor:attackMs="0.2" compressionRatio="4" kneeWidthDb="18" lookaheadMs="1" makeupGainDb="0" releaseMs="210" showActual="1" showInput="1" showOutput="1" showTarget="0" thresholdDb="-14"
```

**Gentle** (piano / light dynamics):

```text
Compressor:attackMs="1" compressionRatio="1.5" kneeWidthDb="6" lookaheadMs="1" makeupGainDb="0" releaseMs="100" showActual="1" showInput="1" showOutput="1" showTarget="0" thresholdDb="-18"
```

These are the Compressor effect, not the Limiter also named Modern.

## Smoke test

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("path/to/audacity-for-agents/python").resolve()))

from audacity_lifecycle import (
    ensure_agent_running,
    new_empty_project,
    close_project,
    exit_audacity_clean,
)
from audacity_pipe import AudacityPipe

ensure_agent_running()
pipe = AudacityPipe(timeout=120.0)
pipe.connect()
print(pipe.do_ok("Message: Text=smoke"))
new_empty_project(pipe)
close_project(pipe)
print(pipe.do_ok("Message: Text=still-alive"))
exit_audacity_clean(pipe)
print("ok")
```

Expect: no Audacity window, process exits cleanly, last print is `ok`. Stock Audacity may stay open the whole time.

A minimal mix is the same plus `Import2` / `normalize_track` / `save_project` / `close_project`. After `Close:` the `.aup3` on disk must stay large (not emptied to a ~20 KB stub).

## Do not

- Attach to whichever Audacity is visible on the desktop.
- Use `GetInfo:`.
- Force-kill the agent.
- Save over a project the GUI has open.
- Expect `--gui` to show a window.
- Treat mixer `Volume` as the working peak.

## If something is wrong

| Symptom | What to do |
|---------|------------|
| Exe not found | Set `AUDACITY_FOR_AGENTS_EXE`. Stop. Do not use stock Audacity. |
| Pipes / handshake fail | Confirm Task Manager shows **`AudacityForAgents.exe`**. Retry `ensure_agent_running()`. Use the repo `python/` client (Win32 pipes), not builtin `open()`. |
| `EINVAL` / errno 22 on `open(pipe)` | Expected on Python 3.13 with builtin `open()`. Use `AudacityPipe` from this repo. |
| `ERROR_PIPE_BUSY` (231) / cannot send `Exit:` | Soft-close: `soft_close_agent()` (WM_CLOSE), then relaunch. Never `taskkill`. Fixed server recycles pipe instances after failed connects (need 0.1.2+ binary). |
| Timeout on Import/Save | Raise `pipe.timeout` / `save_project(..., timeout_sec=…)`. Large stems take minutes. |
| `Failed` in reply | Check `quote_path`, unique basenames, track index. |
| Window or dialog appears | Should not. Stop and report. Never force-kill. |
| Clean slate needed and agent is **not** running | `clear_active_projects()` / `clear_session_data()` in `audacity_lifecycle`. Refuse if the process is still up. SessionData is under `Portable Settings\SessionData` next to the exe. |

Logs: dialog text and logger lines go to **stderr**. `Portable Settings/lastlog.txt` may exist beside the exe after quit.

## Rebuild

Only when the human asks, or the Release binary is missing. Follow [`BUILDING.md`](./BUILDING.md) and [`README.md`](./README.md). Prefer `--parallel 2` on Windows if the compiler runs out of heap.
