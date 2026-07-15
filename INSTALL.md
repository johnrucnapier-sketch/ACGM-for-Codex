# ACGM for Codex RC2 installation / 安装说明

Public version: **`0.1.0-rc.2`**, immutable source tag:
**`v0.1.0-rc.2`**.

ACGM for Codex uses the official Codex Git marketplace flow. The public
installer never edits `config.toml` or marketplace JSON directly and never
copies private Event Ledger data. The older `scripts/install_local.py` remains
a development-only personal-marketplace path.

## Agent-guided installation / 交给 Agent 安装

Giving an Agent this repository name or URL permits only cloning and read-only
inspection. It is not authorization to change user-level Codex configuration.

After the user explicitly asks to install:

```bash
git clone --branch v0.1.0-rc.2 --depth 1 \
  https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git
cd ACGM-for-Codex
python3 scripts/preflight.py --json
python3 scripts/bootstrap.py --dry-run --json
```

The Agent must present the exact plan and ask for approval. Only after that
approval may it run:

```bash
python3 scripts/bootstrap.py --authorize-install --json
```

For a one-task Agent handoff, the user may explicitly authorize the exact named
repository and the two fixed commands below in the original instruction. The
Agent may then clone, preflight, dry-run, install, and verify continuously, but
must stop at `INSTALLED_ENABLED_PENDING_HOOK_TRUST`. A bare name or URL is never
that authorization.

Bootstrap uses only these Codex mutations:

```bash
codex plugin marketplace add johnrucnapier-sketch/ACGM-for-Codex \
  --ref v0.1.0-rc.2 --json
codex plugin add acgm-codex@acgm-codex --json
```

它会先验证 Python、Git、Codex plugin CLI、干净且位于准确 tag 的 Git checkout、
`PACKAGE_MANIFEST.json`、现有 marketplace/plugin 状态。安装后再次核对 marketplace
source/ref、插件 name/version/enabled 以及 cache 中的 package bytes。任一步失败都会报告
明确的 partial state，不会把“命令返回 0”写成“运行时已激活”。

## Lifecycle states / 生命周期分态

Bootstrap reports these separately:

1. source downloaded and verified;
2. marketplace configured with the exact repository and tag;
3. plugin installed and enabled at the exact version;
4. package/cache bytes verified against `PACKAGE_MANIFEST.json`;
5. Hook trust — requires a discovery task and user review of the exact hash in
   `/hooks`;
6. heartbeat — requires a second new task after trust so `SessionStart` runs
   from task start;
7. project bootstrap — requires an explicit target and `$governance-bootstrap`.

`INSTALLED_ENABLED_PENDING_HOOK_TRUST` is therefore not the same as a verified
runtime. `AGENTS.md`, newly installed skills, and changed Hook definitions are
only guaranteed to be considered when a new run/task starts.

The tag, origin, clean-tree, and manifest checks prove local release consistency;
they are not a cryptographic publisher signature. Clone only the official URL
shown above and review GitHub release provenance before granting install approval.

## Conflicts and legacy personal installs / 冲突与旧 personal 版

The following conditions are fail-closed and never auto-migrated:

- `acgm-codex@personal` from RC1;
- the same plugin name in another marketplace or scope;
- duplicate entries;
- marketplace `acgm-codex` with another source or ref;
- another version or unknown cache/package bytes.

Bootstrap returns a `migration_plan` marked `requires_separate_authorization`.
It does not uninstall, overwrite, merge, adopt, or move plugin data. Before any
future manual migration, close active tasks, inventory the exact installs, and
back up the entire private `PLUGIN_DATA` / Event Ledger with its HMAC key.

## Hook trust and project activation / Hook 信任与项目启用

After installation:

1. start a new Codex discovery task so the installed plugin is loaded;
2. open `/hooks`;
3. compare and review the exact `hooks/hooks.json` SHA-256 reported by bootstrap;
4. explicitly trust it;
5. start a second new verification task;
6. verify the trusted `SessionStart` heartbeat;
7. run `$governance-bootstrap` for one verified project root.

Do not claim that ACGM is active merely because `codex plugin add` succeeded.

Preflight itself does not edit the checkout, marketplace JSON, or Codex plugin
configuration. The read-only Codex CLI probes it invokes can still perform
vendor-controlled startup housekeeping (for example, attempting PATH alias
setup); report such behavior instead of claiming zero filesystem side effects.

## Platform limits / 平台边界

- Supported RC candidates: macOS and Linux, Python 3.10+, Git, and a Codex CLI
  exposing the plugin marketplace commands used above.
- **Windows is blocked in RC2.** The current runtime and wrapper rely on POSIX
  shell behavior and `fcntl` locking. The Windows Codex app may support plugins,
  but that does not make this ACGM runtime portable or tested on Windows.

## Development-only local path / 仅开发使用

Maintainers may use `python3 scripts/install_local.py` with a disposable HOME to
exercise the old local personal-marketplace snapshot. It is not the public
installation path, must not be used to migrate a user's RC1 install, and must
never be run by public bootstrap automatically.
