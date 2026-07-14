# ACGM for Codex

**Drift control for long-horizon agent coding.**

ACGM for Codex is an independent Codex adapter for Agent Coding Governance
Methodology. It turns implementation, cognitive, structural-placement, and scope
drift into visible project health, narrow deterministic guardrails, and a
source-minimized local Event Ledger.

[中文](README.md)

> **Status: `0.1.0-rc.1`.** This is a public-preview release candidate, not a stable
> release. Automated tests can validate the package and runtime. Automatic Hook
> behavior is not considered verified until the clean-task E2E checklist passes
> on the installed Codex version.

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
- The `acgm-codex` CLI with `init`, `activate`, `doctor`, `report`,
  `export-case`, `resolve`, `gate`, and `version`.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [EVIDENCE.md](EVIDENCE.md) for the
guarantee matrix and known gaps.

The command recognizer covers only recognized spellings of hard reset, forced
clean, forced branch deletion, forced push, and recursive forced delete. A
recognized high-risk command with shell expansion, compound execution, or an
ambiguous target is denied and cannot be armed. Unrecognized aliases, wrappers,
indirect writes, and other tool paths remain outside complete coverage.

## Install the public preview from GitHub

The release candidate is installed from its independent repository and does not
overwrite ACGM for Claude Code:

```bash
git clone https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git
cd ACGM-for-Codex
python3 scripts/install_local.py
codex plugin list
```

If the repository is already cloned, run from its root:

```bash
python3 scripts/install_local.py
codex plugin list
```

The installer copies only an explicit reviewed-file allowlist, updates the
personal marketplace, installs the CLI wrapper, and asks Codex to refresh its
cache. The first three managed paths form a local transaction: a later failure
restores the prior personal source, marketplace, and wrapper. Codex's cache is
external state; if refresh has already started and then fails, rerun the
installer rather than treating that cache as rolled back.

Then start a new Codex task, open `/hooks`, review and trust the current ACGM
Hook definitions, and invoke `$governance-bootstrap` in the target project.
Existing tasks are not guaranteed to reload newly installed components. A Hook
definition change can require a new trust review because Codex records trust by
definition hash.

The CLI wrapper is installed at `~/.local/bin/acgm-codex`. If that directory is
not on `PATH`, use the absolute path; plugin skills fall back to the installed
plugin's own launcher. The installer does not silently edit shell startup files.

## Bootstrap a project

Ask Codex:

```text
Use $governance-bootstrap to initialize ACGM governance in this repository.
```

Or run:

```bash
acgm-codex init .
acgm-codex doctor .
```

Initialization is idempotent and never overwrites an existing Constitution or
`AGENTS.md`. The Constitution is human-owned: Codex may draft a proposal, but
after initialization it must not use an automated tool to write that file for
the user. The user must complete it, along with non-placeholder scope, at least
one decision, and one current snapshot, before activation:

```bash
acgm-codex activate .
acgm-codex doctor .
```

Activation baselines the required files and the non-hidden files under the
decision and snapshot directories; additions, removals, and content changes are
reported as `DRIFTED`. Activation also resets the heartbeat acceptance time.
Start a new Codex task, confirm the current definitions are trusted in `/hooks`,
let `SessionStart` run, and only then run `acgm-codex doctor . --strict`. Before
that new heartbeat, strict failure means automatic Hook operation has not yet
been accepted as verified, not that the governance content itself is invalid.

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

## Validate

```bash
python3 -m unittest discover -s tests -v
python3 scripts/release_check.py
```

Run the platform checklist in
[tests/manual/CODEX_E2E.md](tests/manual/CODEX_E2E.md) before promoting the RC.

Mechanical code is MIT licensed; methodology prose and skill bodies are
CC-BY-4.0. See [LICENSING.md](LICENSING.md).
