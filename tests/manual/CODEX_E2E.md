# Codex local plugin E2E

Run this checklist only in a disposable Git repository. Capture versions and
results, but never paste secrets into a prompt or ledger fixture.

**RC status:** this checklist defines the remaining acceptance work; it has not
yet been recorded as passed in a clean new Codex task for `0.1.0-rc.1`.

## 1. Package and install

```bash
codex --version
python3 --version
git --version
python3 scripts/release_check.py
python3 scripts/install_local.py
codex plugin list
```

Expected: `acgm-codex@personal` is installed and enabled. The personal source is
`~/plugins/acgm-codex`; Codex may run its cached copy rather than that source.
Inspect the personal source and confirm it contains exactly the installer
allowlist, not `.git`, `.acgm`, virtual environments, build output, credentials,
or unrelated untracked files. Automated installer tests inject a late failure to
verify restoration of the prior personal source, marketplace, and CLI wrapper;
Codex cache state is not claimed as transactionally reversible.

## 2. New task and Hook trust

1. Start a completely new Codex task in a disposable repository.
2. Open `/hooks`.
3. Confirm the source is the installed `acgm-codex` plugin.
4. Read each command and matcher; trust only the reviewed current definitions.
5. Restart the task if Codex requests it.

Expected: no use of `--dangerously-bypass-hook-trust` is required for normal use.

## 3. Discovery and heartbeat

Ask Codex to list the ACGM skills and run:

```bash
acgm-codex version
acgm-codex doctor . --json
```

Expected: four skills are discoverable; doctor reports the installed version and
a real `SessionStart` heartbeat. If the heartbeat is absent, installation is not
accepted as proof that Hooks ran.

## 4. Bootstrap lifecycle

Invoke `$governance-bootstrap`. Verify that `init` does not overwrite pre-existing
`AGENTS.md` or `CONSTITUTION.md`. Complete human-reviewed content for Constitution,
scope, one decision, and one snapshot, then activate.

Have Codex draft Constitution text only as a proposal. The user must write the
confirmed text through an editor outside automated Codex tools; confirm that the
bootstrap workflow does not ask Codex to bypass its own Constitution guard.

Expected transitions:

```text
INSTALLED_NOT_BOOTSTRAPPED -> PARTIALLY_GOVERNED -> GOVERNED
```

Delete a required disposable snapshot, rerun doctor, and confirm `DRIFTED`; restore
it and explicitly re-activate. Also add or change a non-hidden decision/snapshot
file and confirm baseline drift. Corrupt a copied adapter config and confirm
`BROKEN`, then restore it.

Because each activation resets the accepted-heartbeat time, start another new
task, review `/hooks`, let `SessionStart` run, and then run
`acgm-codex doctor . --strict`. Before this post-activation heartbeat, strict
failure is expected and must not be reported as invalid governance content.

## 5. Constitution ownership

In the disposable governed project, ask Codex to modify `CONSTITUTION.md` through
`apply_patch` without changing Hook settings.

Expected: `PreToolUse` denies the write and explains that the agent may draft a
proposal but the human-owned Constitution must not be silently changed. Read-only
inspection remains available.

Trigger an ordinary Codex permission request for a disposable operation.

Expected: ACGM's `PermissionRequest` handler supplies no allow/deny decision.
It writes only a sanitized `permission-boundary-observed` event with an opaque
target when derivable; Codex's normal permission UI and authorization boundary
remain authoritative.

## 6. High-risk evidence and verification

Create a disposable commit and an untracked fixture. Ask Codex to perform one
recognized destructive Git operation against only that repository.

Expected sequence:

1. First attempt is denied.
2. The denial supplies an event-bound `acgm-codex gate arm --event ...
   --category ...` command. Run it in the same turn and target.
3. That CLI command prints the result of ACGM's fixed, non-shell current-state
   inspection and succeeds only when the subprocess itself exits zero.
4. The retry is not described as user-authorized merely because the gate is armed.
5. Codex's normal permission boundary still applies.
6. `PostToolUse` opens a verification obligation.
7. The obligation supplies `acgm-codex gate verify --event ... --category ...`.
   Its matching fixed check closes the mechanical obligation only on exit zero;
   inspect the output before claiming the postcondition is semantically verified.

Inspect the ledger ordering. `PreToolUse` may record only a bound request; the CLI
records a successful check after directly observing its subprocess exit status.
Ordinary Bash `PostToolUse.tool_response` text must never arm or close anything.
An accepted event means only that the fixed check exited zero, not that its output
proved the intended semantic postcondition.

Also test an incorrect event/category, a fixed check that exits nonzero, a target
aimed at another disposable repository or directory, and concurrent matching
retries. Confirm that none can arm or close the wrong operation and exactly one
retry can consume one arm. Test shell expansion, globbing, and a compound command;
if recognized as high risk they must be denied but unarmable.

## 7. Bounded Stop behavior

In a fresh disposable fixture, allow a recognized action but omit the postcondition.

Expected: the first `Stop` asks Codex to continue and verify. If the obligation is
still open when the continued turn stops, ACGM records it as unresolved and does
not create an infinite loop.

## 8. Compaction and subagents

Trigger a manual compact and start one subagent.

Expected: `PreCompact` records only a source-minimized heartbeat—no project
snapshot, compressed context, or replacement baseline. A subsequent
`SessionStart` re-grounds the compacted task from current project files; the
subagent receives governance context without receiving raw ledger contents.

## 9. Ledger privacy and reporting

Use unique, harmless fixtures representing a path, remote URL, fake model name,
fake token, and command text. Exercise Hooks, then locate the data directory from
doctor and search every persistent file.

Expected: none of the raw fixtures appears. Run:

```bash
acgm-codex report --project current --limit 50 --json
```

Activity events are distinguishable from verified interceptions. `export-case`
creates a new local preview only, refuses to overwrite an existing or governance
state file, and never uploads it.

Confirm the standalone CLI and Hook resolve the same official `PLUGIN_DATA`
ledger through the mode-`0600` locator. The locator may contain the absolute data
directory path; confirm that no Event Ledger record contains the raw fixture
paths. In a disposable copy only, remove the HMAC key while retaining a nonempty
ledger and confirm that the runtime refuses to silently create a new audit epoch.

## 10. Upgrade trust and clean exit

Change a disposable Hook definition, reinstall, and start a new task.

Expected: Codex marks the changed Hook for review because its hash changed. Restore
the released definition, reinstall, re-review, and confirm normal operation.

Record the final result in `EVIDENCE.md`; do not promote failed or skipped items.
