# ACGM for Codex installation bridge

This repository is the public install source for **ACGM for Codex**. A bare
repository name or URL without an install request authorizes read-only inspection
only. A direct request to install, enable, initialize, or quickstart this exact
repository in an exact project authorizes the versioned one-consent flow below.

When the user explicitly asks to install or update ACGM for Codex:

1. Confirm the exact target Git root and read `INSTALL.md` completely. Never
   choose a multi-repository container or guess among sibling repositories.
2. Run `python3 scripts/quickstart.py --project <exact-root> --dry-run --json`.
   Do not mutate Codex configuration or project governance when the plan is
   blocked, ambiguous, stale, or reports `MIGRATION_REQUIRED`.
3. When the user's original request explicitly asks to install, enable,
   initialize, or quickstart ACGM in that exact project with recommended
   defaults, do not ask for another confirmation. Run:

   `python3 scripts/quickstart.py --project <exact-root> --plan-digest <digest-from-dry-run> --authorize --json`

   The generated digest binds the source, fixed plugin commands, effective
   Codex profile target identity, exact project, Git identity, preset, existing
   asset hashes, and proposed bytes. If any bound fact changes, authorization
   expires before mutation.
4. Never remove, replace, merge, or adopt `acgm-codex@personal`, duplicate
   installs, unknown sources, another scope, newer/unknown versions, or private
   `PLUGIN_DATA` / Event Ledger content. The sole plugin-upgrade exception is one
   enabled user-scope official RC2/RC3/RC4 whose exact old source/ref/policy,
   marketplace snapshot, bytes, and sole cache entry all verify. The plan digest
   must explicitly include the fixed marketplace remove, exact-ref add, and
   plugin add sequence. Report the manual migration plan for every other state.
5. Quickstart automatically creates missing `standard-v1` governance assets,
   replaces only byte-identical ACGM stock placeholders, preserves unknown
   existing policy, activates the exact project, and verifies local
   postconditions.
6. In the next normal Codex task, the user must personally review `/hooks`.
   When the pending set contains only the exact verified ACGM definitions and
   Codex offers **Trust all and continue**, that one platform action may trust
   the bundle. Never bulk-trust unrelated or unknown Hooks. The first
   subsequently observed ACGM Hook completes runtime verification; do not
   require a second artificial task. This is the required ACGM-specific trust
   boundary; any separate network, filesystem, or command permission prompts
   remain controlled by Codex or the operating system.

This RC supports macOS and Linux with Python 3.10+. It is blocked on Windows:
the current runtime uses POSIX `fcntl` locking and has not passed a native
Windows runtime E2E. Codex app support for plugins does not change that limit.

中文摘要：仅收到仓库名或 URL 仍然只读；但用户只要明确要求在准确项目里安装、启用或
初始化 ACGM，就视为对 `standard-v1` 精确计划的一次授权，不再重复询问。Agent 自动完成
安装、治理文件生成、激活和本地验证；未知冲突绝不覆盖。Codex 自己的 `/hooks` 信任仍由
用户确认一次，之后第一次真实 Hook 调用自动完成验收。Windows 当前明确不支持。
