# ACGM for Codex one-consent installation / 一次授权安装

Public candidate: **`0.2.0-rc.1`**, immutable source tag:
**`v0.2.0-rc.1`**.

ACGM uses the official Codex Git marketplace. It never hand-edits Codex
`config.toml`, never copies private Event Ledger data, and never silently
replaces an unknown or legacy installation.

## Give the repository to an Agent / 把仓库交给 Agent

The user-facing instruction can be as short as:

> Install ACGM for Codex from the official GitHub repository in this project
> with recommended defaults. Complete download, installation, project setup,
> activation, and verification automatically.

That direct request is one authorization for the exact `standard-v1` plan. The
Agent must not ask the user to type governance files or approve the same plan a
second time.

The Agent performs:

```bash
ACGM_SOURCE="$(mktemp -d)/ACGM-for-Codex"
git clone --branch v0.2.0-rc.1 --depth 1 \
  https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git "$ACGM_SOURCE"
python3 "$ACGM_SOURCE/scripts/quickstart.py" \
  --project /absolute/path/to/the/exact/project \
  --dry-run --json
python3 "$ACGM_SOURCE/scripts/quickstart.py" \
  --project /absolute/path/to/the/exact/project \
  --plan-digest <digest-from-dry-run> \
  --authorize --json
```

The temporary source directory must stay outside the target project so the
installation does not leave a nested ACGM checkout in the governed repository.

The dry run is machine verification, not another user ceremony. Its digest
binds the official repository/tag/version, fixed Codex plugin commands, the
effective Codex profile target's non-reversible identity, exact Git root and
identity, `standard-v1` preset, pre-existing managed-file hashes, and every
proposed byte. Apply recomputes the plan; any change invalidates the
authorization before mutation.

中文：用户只需明确要求“在这个准确项目里安装并启用官方 ACGM，采用推荐默认值”。Agent
随后自动 clone、校验、安装、生成治理文件、激活并验证，不再要求用户手写 Constitution、
scope、ADR 或 snapshot，也不重复询问同一授权。

## What quickstart does / 自动完成的步骤

1. verifies the clean immutable source tag and `PACKAGE_MANIFEST.json`;
2. verifies the current Codex marketplace/plugin state;
3. for a fresh install, runs only the two fixed official Codex installation
   commands;
4. as the sole plugin-upgrade exception, can replace one enabled user-scope
   official `0.1.0-rc.2`, `0.1.0-rc.3`, or `0.1.0-rc.4` whose repository, ref,
   policy, marketplace snapshot, package bytes, and sole cache entry all verify;
   the fixed sequence is marketplace remove, exact-ref marketplace add, then
   plugin add;
5. verifies source/ref, enabled version, and cached package bytes;
6. requires the explicit quickstart target to be the exact Git project root and
   refuses parent containers rather than guessing a child. Runtime Hooks have a
   separate unique-child resolver for an unborn parent, but only when every
   entry other than `.git` is itself a verified direct child repository; any
   ordinary untracked or ignored parent file stops that runtime-only selection;
7. generates missing `standard-v1` Constitution, scope, adoption decision, and
   snapshot;
8. preserves substantive existing `AGENTS.md` and governance policy;
9. replaces only byte-identical ACGM stock placeholders from the older manual
   `init` flow;
10. safely adopts the preset into a healthy already-active project when only the
    missing preset decision/snapshot must be added, and allows project adapter
    upgrades only from the explicit compatible RC2/RC3/RC4 set—not from unknown
    or newer versions;
11. activates the project without rotating an already-valid activation;
12. runs local doctor postconditions and records a private progress receipt for
    diagnosis and safe replanning. A retry always makes a new read-only plan and
    requires its current digest; the receipt is not an automatic rollback or
    resume grant.

The combined result is either `COMPLETE` or
`AWAITING_PLATFORM_HOOK_ACCEPTANCE`. The latter is a successful local setup with
one remaining Codex-owned trust boundary, not a failed installation.

## The ACGM-specific platform confirmation / ACGM 专属平台确认

Codex records trust against each exact non-managed Hook definition. This is the
only required ACGM-specific post-install trust boundary: a plugin
cannot and must not trust its own executable Hooks. At the next normal task
boundary, current Codex clients may offer **Trust all and continue**. Use that
single platform action only when the review set contains exclusively the
verified ACGM definitions from this exact release. If unrelated or unknown
Hooks are also pending, review them individually rather than bulk-trusting
them. The surrounding environment may still show its own network, filesystem,
or command-permission prompts; quickstart does not bypass Codex or OS security.

No second artificial verification task is required. After trust, the first
actually observed ACGM Hook records the activation heartbeat. The Agent can then
run:

```bash
acgm-codex quickstart status /absolute/path/to/project --json
```

or `acgm-codex doctor /absolute/path/to/project --strict` to obtain `COMPLETE`.
Newly installed plugins still load at Codex task boundaries, so the user starts
the next normal work task rather than following a separate multi-task ceremony.

## Safety and conflict rules / 冲突边界

One-consent quickstart is intentionally narrow. It does not authorize or perform:

- removal, migration, or adoption of `acgm-codex@personal`;
- replacement of duplicate, unknown-source, wrong-scope, newer, unrecognized,
  or otherwise wrong-version installs. The only exception is the exact verified
  official user-level RC2/RC3/RC4 upgrade described above;
- overwriting an unknown Constitution, `AGENTS.md`, scope, decision, or snapshot;
- overwriting an unknown `.acgm/quickstart.json` receipt, absorbing a concurrent
  Git/index/governance change into the activation baseline, or downgrading an
  unknown/newer adapter state;
- copying or resetting private `PLUGIN_DATA`, Event Ledger, or its HMAC key;
- release, deployment, destructive cleanup, credential/permission changes, or
  any unrelated external mutation.

Those states fail before project writes or return an explicit partial-state
receipt. A changed plan, Git identity, asset hash, source, tag, scope, command,
installed version, or verified cache/snapshot evidence invalidates the original
grant. An interrupted official upgrade is re-inspected and reported as partial;
the installer never claims it rolled back private or external state.
If plugin installation succeeds but the project root changes or becomes
unreadable before project apply, the combined result is
`PROJECT_RECHECK_REQUIRED` with `partial=true`, not a traceback or a false
all-complete claim.

If local governance is healthy but a real Hook later records a runtime error,
status reports `HOOK_RUNTIME_REPAIR_REQUIRED`; damaged local installation or
ledger state reports `LOCAL_RUNTIME_REPAIR_REQUIRED`. Neither is mislabeled as
waiting for first-time Hook trust.

## Advanced/manual compatibility path

The earlier staged commands remain available for maintainers and custom-policy
projects:

```bash
python3 scripts/preflight.py --json
python3 scripts/bootstrap.py --dry-run --json
python3 scripts/bootstrap.py --authorize-install \
  --plan-digest <install_plan_digest-from-dry-run> --json
acgm-codex init /absolute/path/to/project
acgm-codex activate /absolute/path/to/project
```

Use this path only when the user explicitly wants custom governance or
quickstart reports an existing-policy conflict. It is no longer the recommended
onboarding experience.

## Platform limits

- Supported candidate runtime: macOS and Linux, Python 3.10+, Git, and a Codex
  CLI exposing the documented plugin marketplace commands.
- Native Windows remains blocked in this candidate because the Event Ledger
  still uses POSIX `fcntl` locking. Do not translate “Codex can install plugins
  on Windows” into an unsupported ACGM runtime claim.

## Development-only local path

Maintainers may use `python3 scripts/install_local.py` with disposable state to
exercise the local personal-marketplace path. It is not the public installation
route and must never migrate a user's legacy install automatically.
