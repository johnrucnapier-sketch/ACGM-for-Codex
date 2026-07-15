# ACGM for Codex installation bridge

This repository is the public install source for **ACGM for Codex**, not proof
that the user authorized an install. A bare repository name, URL, clone, or
download authorizes read-only inspection only.

When the user explicitly asks to install or update ACGM for Codex:

1. Confirm the repository root and read `INSTALL.md` completely.
2. Run `python3 scripts/preflight.py --json`. Do not mutate Codex configuration
   when it reports `BLOCKED` or `MIGRATION_REQUIRED`.
3. Show the exact plan and obtain explicit approval for the Codex user-config
   mutation. Then run `python3 scripts/bootstrap.py --authorize-install --json`.
   The user's original instruction may supply that approval only when it names
   this repository and explicitly authorizes the two fixed Codex plugin
   mutations documented in `INSTALL.md`; a bare URL never qualifies.
4. Never remove, replace, merge, or adopt `acgm-codex@personal`, duplicate
   installs, unknown sources, another scope, or private `PLUGIN_DATA` / Event
   Ledger content. Report the generated manual migration plan instead.
5. Start a **new Codex discovery task** after installation. This file, installed
   skills, and changed Hooks are not guaranteed to load into the task that
   performed the installation.
6. In that discovery task, ask the user to open `/hooks`, review the exact
   SHA-256 shown by bootstrap, and trust that definition.
7. Start a **second new verification task** so the already-trusted
   `SessionStart` Hook can run from task start.
8. Only after that task records the trusted heartbeat should the target project
   be initialized through `$governance-bootstrap`.

This RC supports macOS and Linux with Python 3.10+. It is blocked on Windows:
the current runtime uses POSIX `fcntl` locking and has not passed a native
Windows runtime E2E. Codex app support for plugins does not change that limit.

中文摘要：仅收到仓库名或 URL 不等于获准安装。先只读 preflight，再展示计划并取得明确
授权；不得静默覆盖旧 personal 版或吸收 Event Ledger。安装后先新开 discovery task，在
`/hooks` 审查精确 hash，再新开 verification task 触发已信任的 `SessionStart`；之后才可在
目标项目执行 governance bootstrap。Windows 当前明确不支持。
