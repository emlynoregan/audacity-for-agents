# Audacity for Agents

Fork of Audacity **3.7.8** for headless scripting beside a normal GUI install.

- Exe: `AudacityForAgents.exe` (Release build)
- Pipes: `\\.\pipe\ToAudacityForAgents` / `FromAudacityForAgents`
- Always `--batch`: no windows; dialogs and logs go to stderr
- Own Portable Settings next to the exe; no `.aup3` file association
- `Close:` detaches the saved project (does not vacuum it) and prunes orphan sample blocks so stock Audacity can open the file without “Project Recovered”

Branch: `audacity-for-agents`. Remotes: `origin` → this fork; `upstream` → [audacity/audacity](https://github.com/audacity/audacity) `release-3.7.8`.

Operator notes and Python clients live in the docs project: `docs/projects/20260830 AudacityForAgents/` (especially `howto.md`).

Rebuild (this machine; use 2 jobs — full parallel hit C1060):

```
cmake --build <build-dir> --config Release --parallel 2 --target Audacity
```

Licence: GPL, same as Audacity. Rebase onto 3.7.x only — never onto Audacity 4 (`master`).
