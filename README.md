# Audacity for Agents

**Audacity for Agents** is a fork of [Audacity](https://www.audacityteam.org) **3.7.x** made for **headless scripting**. It runs as a separate process beside a normal GUI Audacity install so AI agents and automation can import, mix, and save `.aup3` projects without stealing the window you use for listening.

This is **not** a drop-in replacement for stock Audacity. There is no usable GUI here. Stock Audacity remains the app humans open; this binary is what scripts and coding agents drive over named pipes.

| | Stock Audacity | Audacity for Agents |
|--|----------------|---------------------|
| Who | Humans (listening / editing) | Agents and Python scripts |
| Executable | `Audacity.exe` / `audacity` | `AudacityForAgents.exe` |
| Windows | Normal UI | None (always batch / headless) |
| Script pipes | `ToSrvPipe` / `FromSrvPipe` | `ToAudacityForAgents` / `FromAudacityForAgents` |
| File association | Owns `.aup3` | None |
| Config | User app data | Portable Settings next to the exe |

## Why it exists

Official Audacity scripting uses a single global Windows mutex and one pair of named pipes. While a script holds that process, you cannot usefully use the GUI. Dialogs (crash recovery, save prompts, splash) block the pipe. A second stock install still loses to the first process via DDE/IPC.

This fork changes identity (mutex, IPC name, pipe names, exe name), stays headless, stubs dialogs to stderr, keeps the script pipe alive across `Close:`, and writes `.aup3` files that stock Audacity can open without a false “Project Recovered” dialog.

## Status

First working version on **Windows** (Audacity 3.7.8 base). Build and run next to a normal Audacity 3.x install. Rebase onto 3.7.x only — do **not** merge Audacity 4 (`master` / Qt).

**Installer:** Windows Setup from House of Ur:

https://audacityforagents-bronzearch.house-of-ur.com/

Default install: `%LOCALAPPDATA%\Audacity for Agents\` (optional PATH / `AUDACITY_FOR_AGENTS_EXE`). Or build from source below.

## Quick start for agents

If you are an AI coding agent that needs to build or mix audio through this tool, read **[`AGENT.md`](./AGENT.md)** first. Use the Python helpers under [`python/`](./python/).

Humans: build from source (below), point `AUDACITY_FOR_AGENTS_EXE` at the Release binary, then either run your own macros over the agent pipes or use the Python client.

## Build

Same prerequisites as upstream Audacity — see [`BUILDING.md`](./BUILDING.md) (Visual Studio 2022 + CMake on Windows, out-of-tree build recommended).

```bash
cmake -G "Visual Studio 17 2022" -A x64 -S . -B ../audacity-for-agents-build
cmake --build ../audacity-for-agents-build --config Release --parallel 2 --target Audacity
```

Use a modest `--parallel` value on Windows; unbounded parallelism has hit compiler out-of-heap (C1060) on some machines.

Output binary (name may vary by generator layout):

```text
…/audacity-for-agents-build/Release/AudacityForAgents.exe
```

Create or keep a `Portable Settings` folder next to that exe (the build/runtime expects portable config there). Launch with cwd = the folder that contains the exe:

```text
AudacityForAgents.exe --batch
```

`--gui` is ignored. There is no window.

## Scripting pipes

| Direction | Pipe name |
|-----------|-----------|
| Client → agent | `\\.\pipe\ToAudacityForAgents` |
| Agent → client | `\\.\pipe\FromAudacityForAgents` |

Override with `AUDACITY_TO_PIPE` / `AUDACITY_FROM_PIPE` if needed. **Do not** use stock `ToSrvPipe` / `FromSrvPipe` for this binary.

Protocol is the same Audacity 3.7 macro language as stock (`Import2:`, `Normalize:`, `SaveProject2:`, …). Command lines end with `\r\n\0`. Prefer `Message: Text=ping` for handshake; avoid `GetInfo:` (blank lines in the JSON reply desync simple line clients).

## Python client

See [`python/`](./python/) for a Windows pipe client and lifecycle helpers (`ensure_agent_running`, `save_project`, `close_project`, `exit_audacity_clean`). Set:

```text
AUDACITY_FOR_AGENTS_EXE=C:\path\to\Release\AudacityForAgents.exe
```

## Hard rules

1. Never force-kill the agent process (`taskkill`, End Task unless the process is already wedged with no pipes). Use `Exit:` and wait. Force-kill risks WAL / SessionData corruption.
2. Never `SaveProject2` a `.aup3` that stock Audacity currently has open (SQLite WAL). Isolation is per process, not per file.
3. After `SaveProject2`, call `Close:` before asking a human to open the file in the GUI. `Close:` detaches the save and leaves the agent on a fresh empty project; the pipe stays up.
4. Do not fall back to scripting stock `Audacity.exe` “because it is already open.”

## Upstream

- Base: [audacity/audacity](https://github.com/audacity/audacity) tag/branch **release-3.7.8** (and future 3.7.x).
- This fork’s product notes and agent API live in this repository. Upstream docs describe stock Audacity, not this headless identity.

## License

GPL, same as Audacity. See [`LICENSE.txt`](./LICENSE.txt). If you distribute binaries, distribute corresponding source.
