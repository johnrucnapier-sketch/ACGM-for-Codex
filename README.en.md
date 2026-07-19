# ACGM for Codex

**Drift control for long-horizon agent coding.**

ACGM for Codex is an independent Codex adapter for Agent Coding Governance
Methodology. It turns implementation, cognitive, structural-placement, and scope
drift into visible project health, narrow deterministic guardrails, and a
source-minimized local Event Ledger.

[中文](README.md)

> **Status: `0.2.0-rc.2`.** This is a public-preview release candidate, not a stable
> release. Automated tests can validate the package and runtime. Automatic Hook
> behavior is not considered verified until Hook trust and real tool-call E2E pass
> in a completely new task on the installed Codex version.

This product does not overwrite or replace
[ACGM for Claude Code](https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology).
The two products have separate plugin identities, lifecycle protocols, install
locations, and local data namespaces.

## Why it is a plugin

Rules in prose do not automatically survive a new task, compaction, a subagent,
or a new worktree. ACGM for Codex separates three guarantees:

| Layer | Purpose | Boundary |
|---|---|---|
| Methodology | Constitution, Truth-first, ADRs, snapshots, scope, and verification obligations | Normative guidance |
| Skills | Reusable workflows for bootstrap, recovery, risky changes, and reporting | Explicitly or implicitly selected |
| Hooks and runtime | Health checks, narrow interception, obligation tracking, and a local ledger | Deterministic guardrails, not an absolute security boundary |

Current Codex documentation says `PreToolUse` interception is incomplete for
`unified_exec` and does not cover every tool path. Personal plugins can also be
disabled, and their Hooks must be reviewed and trusted. ACGM therefore never
equates “installed” with “fully enforced.”

## Capabilities

- Five project states: `INSTALLED_NOT_BOOTSTRAPPED`, `PARTIALLY_GOVERNED`,
  `GOVERNED`, `DRIFTED`, and `BROKEN`.
- Startup and subagent grounding through `SessionStart` and `SubagentStart`.
- Constitution protection and a narrow high-risk evidence gate in `PreToolUse`.
- `PermissionRequest` records only a sanitized boundary observation; it neither
  approves nor denies and does not manufacture a governance decision for the user.
- The evidence gate does not treat Codex Bash's text-only
  `PostToolUse.tool_response` as authenticated success. `gate arm` and `gate
  verify` run fixed-argument, non-shell read-only commands inside the runtime and
  change gate or obligation state only on their actual zero exit status. Output
  still requires interpretation before a semantic verification claim.
- One bounded `Stop` continuation while a matching post-action check is absent.
- A source-minimized `PreCompact` heartbeat only—not a project snapshot or a
  copy of compacted context—and renewed grounding from current files afterward.
- A local, append-only, source-minimized Event Ledger.
- Four skills: `governance-bootstrap`, `session-grounding`, `truth-first`, and
  `activity-report`.
- One-consent quickstart that provisions a versioned governance preset,
  activates the exact project, and checks local postconditions.
- The `acgm-codex` CLI with `quickstart`, `init`, `activate`, `doctor`, `report`,
  `export-case`, `resolve`, `gate`, and `version`.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [EVIDENCE.md](EVIDENCE.md) for the
guarantee matrix and known gaps.

The command recognizer covers only recognized spellings of hard reset, forced
clean, forced branch deletion, forced push, and recursive forced delete. A
recognized high-risk command with shell expansion, compound execution, or an
ambiguous target is denied and cannot be armed. Unrecognized aliases, wrappers,
indirect writes, and other tool paths remain outside complete coverage.

## Install the public preview from GitHub

The release candidate uses the official Codex Git marketplace and does not
overwrite ACGM for Claude Code. The user only needs to tell the Agent to install
and enable official ACGM in the exact project with recommended defaults. That
sentence is one authorization for the exact `standard-v1` plan; it does not
require item-by-item approval or hand-written governance files.

The Agent clones the exact tag and runs:

```bash
ACGM_SOURCE="$(mktemp -d)/ACGM-for-Codex"
git clone --branch v0.2.0-rc.2 --depth 1 \
  https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git "$ACGM_SOURCE"
python3 "$ACGM_SOURCE/scripts/quickstart.py" \
  --project /absolute/path/to/the/exact/project --dry-run --json
python3 "$ACGM_SOURCE/scripts/quickstart.py" --project /absolute/path/to/the/exact/project \
  --plan-digest <digest-from-dry-run> --authorize --json
```

The Agent clones the tool source into a temporary directory outside the target
project, so onboarding does not leave a nested checkout in the governed repo.

You can say:

> Install ACGM for Codex from the official GitHub repository in this exact
> project with recommended defaults. Complete download, installation,
> governance-file generation, activation, and verification automatically. Do
> not overwrite existing project policy or migrate a legacy installation.

A bare URL without an install request still permits only download and read-only
inspection. Quickstart dry-run is machine verification, not a second approval
ceremony. Its digest binds the official source/tag, fixed install commands, a
non-reversible identity for the effective Codex profile target, exact Git root
and identity, existing managed-file hashes, and every proposed byte. Any changed
fact invalidates the grant before apply.

For a fresh install, bootstrap invokes `codex plugin marketplace add
johnrucnapier-sketch/ACGM-for-Codex --ref v0.2.0-rc.2 --json` and then `codex
plugin add acgm-codex@acgm-codex --json`. It independently verifies the exact
marketplace source/ref, plugin name/version/enabled state, and cached package
bytes. The sole automatic plugin-upgrade exception is one enabled, user-scope
official `0.1.0-rc.2`, `0.1.0-rc.3`, `0.1.0-rc.4`, or `0.2.0-rc.1` whose source, ref, policy,
marketplace snapshot, package bytes, and sole cache entry all verify. That
digest explicitly binds marketplace remove, exact-ref marketplace add, and
plugin add. A failed external mutation is reported as partial/recheck state; it
is not described as rolled back.
An open task continues to invoke the old versioned Hook path it loaded at task
start. RC2 protects that path during each upgrade step and publishes verified
fail-open bridges for every known official pre-guard version, including tasks
already stale before this upgrade. The stale task
therefore cannot turn a missing Stop Hook into a model loop, while a restarted
task loads the full current ACGM runtime. New Hook commands also carry their
missing-runtime guard inline so a future upgrade cannot recreate this lockout.
This is not Lite mode and does not weaken rules while the full runtime exists.
RC2 also verifies the temporary “old installed cache + new source ref”
re-association that Codex can expose after marketplace replacement. It proceeds
only when the old cache, target checkout, scope, policy, and pinned official
release identities all match. The equivalent RC1-interrupted state receives a
new RC2 digest and is rolled forward automatically without hand-editing config.
If installation succeeds but the project root changes before project apply, the
combined result reports `PROJECT_RECHECK_REQUIRED` with `partial=true` instead
of escaping as a traceback.

Quickstart then creates missing Constitution, scope, adoption-decision, and
snapshot assets, preserves existing `AGENTS.md` and substantive governance
policy, and replaces only byte-identical stock placeholders created by the old
`init` flow. It activates the project and runs doctor automatically. Quickstart
requires the exact Git root; a parent workspace stops before any project write,
does not guess a child, and never receives project governance. Only the runtime
Hook resolver may auto-select a unique child below an unborn parent, and only
when every entry other than `.git` is a verified direct child repository. An
ordinary untracked or ignored parent file stops that runtime-only selection.

Codex Hook trust is the only required ACGM-specific post-install confirmation
the plugin cannot perform for the user. At the next normal task boundary,
current Codex clients may offer **Trust
all and continue**. Use that single platform action only when the pending review
set contains exclusively the verified ACGM definitions from this exact release;
review any mixed or unknown Hooks individually. The first real ACGM Hook
observed afterward records the activation heartbeat automatically; a second
artificial "verification task" is not required. The surrounding environment may
still show its own network, filesystem, or command-permission prompts; ACGM does
not bypass Codex or OS security.

Legacy `acgm-codex@personal`, duplicates, another scope/source/ref, unknown
versions, and newer versions are fail-closed; the exact verified official
four exact official candidate paths above are the only plugin-upgrade exceptions. Bootstrap never
adopts, resets, or moves private `PLUGIN_DATA` / Event Ledger content. See
[INSTALL.md](INSTALL.md).
Unknown policy, symlinks, non-regular managed paths, substantive active drift,
and stale plan digests also stop before automatic replacement. A state whose
only drift is an older adapter version may be upgraded inside the same
digest-bound authorization when its existing baseline still matches.

Public installation does not add a shell wrapper to `PATH`; installed skills
resolve the launcher inside the plugin root. `scripts/install_local.py` is only
for maintainers exercising the old personal path with a disposable HOME.

The current candidate supports macOS and Linux with Python 3.10+. Windows is
explicitly blocked:
the runtime still relies on POSIX `fcntl` locking, so Codex app plugin support
on Windows is not evidence that this runtime is portable or E2E-tested there.

## Bootstrap a project

Ask Codex:

```text
Use $governance-bootstrap to quickstart ACGM in this repository with recommended defaults.
```

Or run:

```bash
acgm-codex quickstart plan /absolute/path/to/project --json
acgm-codex quickstart apply /absolute/path/to/project --plan-digest <digest> --authorize --json
acgm-codex quickstart status /absolute/path/to/project --json
```

`standard-v1` is a versioned safe preset. One quickstart authorization adopts
those exact bytes; the user does not have to type a Constitution. Existing
substantive policy is preserved. Version-only adapter drift with an otherwise
matching baseline is upgraded in the same authorization only from the explicit
compatible RC2/RC3/RC4/0.2-RC1 project-adapter set; an unknown or newer state is never
automatically downgraded. A healthy manually activated project may adopt its
missing standard decision/snapshot while preserving the activation id. Unknown
receipts, concurrent Git/index changes, unknown placeholders, symlinks,
non-regular files, other active drift, and conflicting content stop automatic
absorption. The compatible `init` / `activate` sequence remains available for
projects that explicitly require custom policy.

After apply, the project is `GOVERNED`. Until a real Hook heartbeat exists for
the current activation, quickstart reports
`AWAITING_PLATFORM_HOOK_ACCEPTANCE`: local setup succeeded, but the platform
mechanism still needs its one trust boundary. After the first real Hook runs,
`quickstart status` or strict doctor reports completion. An installed but
uninitialized project remains `INSTALLED_NOT_BOOTSTRAPPED`; missing assets are
never relabeled silently as `GOVERNED`.
If a Hook runtime error occurs after a heartbeat, status reports
`HOOK_RUNTIME_REPAIR_REQUIRED`; damaged local installation or ledger state
reports `LOCAL_RUNTIME_REPAIR_REQUIRED`, never a misleading first-trust wait.

## Inspect activity

```bash
acgm-codex doctor . --json
acgm-codex report --project current --limit 20
```

An activity count proves that a mechanism ran; it does not by itself prove that
an incident was prevented. `export-case` refuses to overwrite an existing file
or project governance/runtime state. Exported cases remain local sanitized
previews until a human reviews every line.

## Privacy

Raw Hook input is processed in memory and discarded. The ledger does not retain
prompts, transcripts, source, full commands, file paths, model/provider names,
remote URLs, credentials, or reconstructable technical fingerprints. It never
uploads automatically. Gate, check, and obligation events correlate only when
their locally HMAC-bound target is the same.

This RC does not rotate the Event Ledger automatically, and event lookup grows
linearly with the local ledger. Archiving a large long-lived ledger or beginning
a new audit epoch remains an explicit human-reviewed operation; its HMAC key
must not be separated accidentally.

On its first installed Hook run, the runtime writes the official `PLUGIN_DATA`
location to a mode-`0600` local locator so the standalone CLI and Hooks share one
ledger. The locator itself contains that data-directory path; it is not an Event
Ledger event. If the ledger remains but its local HMAC key is missing, the
runtime refuses to create a silent replacement. Preserve or restore ledger and
key together, or move both aside explicitly to begin a new audit epoch.
Hooks own ledger initialization and permission hardening. Standalone `doctor`
and `report` only read an existing locator, key, and ledger; they do not create
directories, call `chmod`, or open a write-capable lock merely to inspect state,
so they remain usable in managed Codex sandboxes with read-only plugin data.

## Validate

```bash
python3 -m unittest discover -s tests -v
python3 scripts/release_check.py
```

Run the platform checklist in
[tests/manual/CODEX_E2E.md](tests/manual/CODEX_E2E.md) before promoting the RC.

Mechanical code is MIT licensed; methodology prose and skill bodies are
CC-BY-4.0. See [LICENSING.md](LICENSING.md).
