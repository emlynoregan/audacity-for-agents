# Python client (Windows)

Helpers for driving **Audacity for Agents** over named pipes.

```text
python/
  audacity_pipe.py       # AudacityPipe, quote_path, pipe names
  audacity_lifecycle.py  # launch, save, close, exit (never force-kill)
  audacity_levels.py     # peak-normalize helper (−6 dB by default)
```

## Setup

1. Build `AudacityForAgents.exe` (see repo [`README.md`](../README.md)).
2. Set the executable path:

```text
set AUDACITY_FOR_AGENTS_EXE=C:\path\to\Release\AudacityForAgents.exe
```

Or export the same variable in your shell / agent environment. If unset, the client looks for `AudacityForAgents.exe` on `PATH`.

3. Add this directory to `sys.path`, or copy the three modules into your project.

Optional pipe overrides: `AUDACITY_TO_PIPE`, `AUDACITY_FROM_PIPE` (defaults are `\\.\pipe\ToAudacityForAgents` and `FromAudacityForAgents`).

Requires **Windows**. Pipe I/O uses Win32 APIs (not builtin `open()`), so Python 3.13 works.

## Minimal usage

```python
from audacity_lifecycle import (
    ensure_agent_running,
    new_empty_project,
    save_project,
    close_project,
    exit_audacity_clean,
)
from audacity_pipe import AudacityPipe, quote_path
from audacity_levels import normalize_track

ensure_agent_running()
pipe = AudacityPipe(timeout=1800.0)
pipe.connect()

new_empty_project(pipe)
pipe.do_ok(f"Import2: Filename={quote_path('D:/audio/track.wav')}")
normalize_track(pipe, 0)
save_project(pipe, "D:/out/mix.aup3")
close_project(pipe)
exit_audacity_clean(pipe)
```

Full agent rules and command list: [`../AGENT.md`](../AGENT.md).
