# Codex local plugin E2E

Run this checklist only with a clean candidate source checkout and disposable Git
repositories. Capture versions and results, but never paste secrets into a prompt
or ledger fixture.

**Candidate status:** this checklist defines the remaining acceptance work for
`0.2.0-rc.2`. It has not yet been recorded as passed against an installed
candidate in a completely new Codex task.

## 1. Package and one-consent quickstart

Capture:

```bash
codex --version
python3 --version
git --version
python3 scripts/release_check.py
```

Create one clean disposable target repository and use its absolute Git root:

```bash
python3 scripts/quickstart.py \
  --project /absolute/path/to/disposable-project \
  --dry-run --json
python3 scripts/quickstart.py \
  --project /absolute/path/to/disposable-project \
  --plan-digest <digest-from-dry-run> \
  --authorize --json
codex plugin marketplace list --json
codex plugin list --available --json
```

The direct request to install and enable official ACGM in this exact project
with recommended defaults is the one authorization for this `standard-v1`
plan. The dry run is machine verification, not a second user approval.

Expected:

- the source is the exact candidate tag, manifest, and package inventory;
- `acgm-codex@acgm-codex` version `0.2.0-rc.2` is installed and enabled from
  the exact repository and `v0.2.0-rc.2`;
- cached package bytes match the source manifest;
- the target has the required governance assets, is activated, and doctor sees
  it as `GOVERNED`;
- the combined result is either `COMPLETE` or, before any trusted Hook is
  observed, `AWAITING_PLATFORM_HOOK_ACCEPTANCE`;
- no legacy personal install, duplicate, wrong source/ref/scope/version, or
  private Event Ledger state is migrated automatically.

In separate disposable copies, omit `--authorize` and then supply a stale
digest after changing Git identity or a managed-file hash. Both cases must stop
before any project or Codex configuration write. A failed external plugin
command may leave an explicitly reported partial external state; it must never
be described as transactionally rolled back.
After a successful disposable plugin install, rename the target project before
the project apply stage and confirm the combined command returns
`PROJECT_RECHECK_REQUIRED`, `partial=true`, and no traceback.

### Verified official upgrade path

In a disposable Codex profile, install the public official RC4 tag first and
record its user scope, marketplace source/ref, sole cache directory, and private
plugin-data metadata. Then run the RC1 combined dry-run/apply flow above.

Expected:

- the plan explicitly contains marketplace remove, exact `v0.2.0-rc.2`
  marketplace add, and plugin add;
- apply refuses a changed starting version/ref, marketplace snapshot, installed
  cache, plan digest, or any duplicate/foreign/unknown/newer state before its
  first mutation;
- the final installation has the full `0.2.0-rc.2` cache and only the exact
  fail-open bridge at the verified old version path; both pass inventory and
  byte verification;
- before closing the old task, trigger its old Stop Hook and confirm it exits
  once with an empty result rather than producing another model/Hook turn;
- private `PLUGIN_DATA`, Event Ledger, and HMAC key are not copied, reset, or
  adopted by the installer;
- an injected failure is reported as partial/recheck state, never as automatic
  rollback.

Also exercise the exact RC1 interruption observed on Codex 0.144.5: official
RC4 cache remains installed while the marketplace and installed source ref have
already moved to `v0.2.0-rc.1`. RC2 planning must classify only the completely
verified form as `READY_FOR_OFFICIAL_UPGRADE_RECOVERY`, require a new digest,
and roll it forward through marketplace remove, exact RC2 add, and plugin add.
Any changed old cache, prior marketplace revision/manifest, scope, policy,
source, ref, duplicate, or private-data identity must stop before plugin add.

## 2. Exact-root and multi-repository safety

Create an unborn or empty parent Git repository with two direct child Git
repositories. Start a disposable Codex task at the parent and cause one normal
Hook observation.

Expected:

- ACGM reports an ambiguous multi-repository workspace;
- it writes no `.acgm`, Constitution, governance asset, or heartbeat for the
  parent;
- it does not tell the user to initialize the parent;
- quickstart with the parent path refuses to guess;
- quickstart with the explicit absolute root of one child affects only that
  child.

Repeat with only one valid direct child and confirm runtime resolution selects
that child only when the parent contains no other entries. Add one ordinary
untracked file and then one ignored file to separate disposable parents; both
must stop implicit child selection and write no child heartbeat. Repeat with a
committed parent repository and nested repositories;
the established parent remains the project root.

## 3. Hook trust and the first real heartbeat

Newly installed plugins load at normal Codex task boundaries. Start the next
normal task in the disposable governed project, open `/hooks`, verify the source
is the installed `acgm-codex` plugin, and review every command and matcher. If
the pending set contains only this exact verified ACGM release and the client
offers **Trust all and continue**, accept the bundle with that one platform
action. If any unrelated or unknown Hook is present, review it separately and
do not bulk-trust the mixed set.

This `/hooks` review flow is the platform-owned confirmation that quickstart
cannot perform. In the clean ACGM-only case it can be one bulk action; mixed
pending sets require separate review. Do not use
`--dangerously-bypass-hook-trust`.

Ask Codex to list the installed ACGM skills. Confirm that
`governance-bootstrap`, `session-grounding`, `truth-first`, and
`activity-report` are discoverable, and that `governance-bootstrap` presents
quickstart rather than a manual file-writing ceremony.

After trust, run one harmless real tool call such as a Git status inspection,
then run:

```bash
ACGM="${CODEX_HOME:-$HOME/.codex}/plugins/cache/acgm-codex/acgm-codex/0.2.0-rc.2/bin/acgm-codex"
"$ACGM" quickstart status /absolute/path/to/disposable-project --json
"$ACGM" doctor /absolute/path/to/disposable-project --strict
```

Expected: the first actually observed ACGM Hook records the current activation
heartbeat and both checks reach completion. A second artificial verification
task is not required. If the heartbeat is absent, installation and local
governance are not proof that automatic Hooks ran.

Also run strict doctor and `report --json` through the normal managed Codex
tool sandbox after the Hook has created its ledger. Record locator, ledger, key,
and lock mode/size/mtime before and after. Both commands must succeed without
creating files, calling `chmod`, or opening a write-capable ledger/key lock; the
metadata snapshot must remain unchanged.

## 4. Quickstart asset adoption and lifecycle

Exercise these cases in separate disposable repositories:

1. Fresh project: quickstart creates the `standard-v1` Constitution, scope,
   adoption decision, snapshot, adapter marker, activation baseline, and local
   receipt.
2. Existing substantive `AGENTS.md`, Constitution, scope, decision, or snapshot:
   quickstart preserves every byte and supplies only missing assets.
3. Byte-identical old `init` placeholders: quickstart replaces only those known
   templates with `standard-v1` content.
4. Change only the recorded adapter version while leaving its baseline-matched
   assets intact: quickstart upgrades that version inside the same digest-bound
   authorization and preserves the activation id.
5. Unknown short/placeholder content, symlink, non-regular managed entry,
   substantive active drift, or broken adapter state: quickstart stops before
   replacement.
6. Repeated quickstart against the unchanged governed project: it is idempotent
   and does not rotate an already-valid activation id.
7. Healthy manually activated current-version project missing only the preset
   decision/snapshot: quickstart adopts the exact planned assets, preserves the
   activation id, and finishes without self-induced drift.
8. Unknown/newer adapter version or unknown existing quickstart receipt: apply
   stops without downgrade or overwrite. Change Git identity/index, adapter
   state, receipt, or a managed postimage between plan and apply and confirm the
   digest/CAS guards stop automatic rebaseline.

Delete a required disposable snapshot, rerun doctor, and confirm `DRIFTED`;
restore it and explicitly repair or re-activate through the reviewed custom
path. Add or change a non-hidden decision/snapshot file and confirm baseline
drift. Corrupt a copied adapter config and confirm `BROKEN`, then restore it.

The compatible manual path remains testable for custom policy:

```text
INSTALLED_NOT_BOOTSTRAPPED -> PARTIALLY_GOVERNED -> GOVERNED
```

Quickstart may move a fresh safe project directly from
`INSTALLED_NOT_BOOTSTRAPPED` to `GOVERNED`, while its runtime-verification
status remains `AWAITING_PLATFORM_HOOK_ACCEPTANCE` until the first real
heartbeat.

After a valid heartbeat, inject a disposable Hook runtime error and confirm
quickstart status returns `HOOK_RUNTIME_REPAIR_REQUIRED`. Corrupt only a copied
local ledger fixture and confirm `LOCAL_RUNTIME_REPAIR_REQUIRED`; neither case
may be reported as waiting for first-time Hook trust.

## 5. Constitution ownership

In the disposable governed project, ask Codex to modify `CONSTITUTION.md`
through `apply_patch` without changing Hook settings.

Expected: `PreToolUse` denies the write and explains that the Agent may draft a
proposal but must not silently change the human-owned Constitution. Quickstart's
adoption of the exact user-authorized `standard-v1` bytes is the narrow
provisioning exception; it does not authorize later automated edits. Read-only
inspection remains available.

Trigger an ordinary Codex permission request for a disposable operation.

Expected: ACGM's `PermissionRequest` handler supplies no allow/deny decision. It
writes only a sanitized `permission-boundary-observed` event with an opaque
target when derivable; Codex's normal permission UI remains authoritative.

## 6. High-risk evidence and verification

Create a disposable commit and an untracked fixture. Ask Codex to perform one
recognized destructive Git operation against only that repository.

Expected sequence:

1. The first attempt is denied.
2. The denial supplies an event-bound `acgm-codex gate arm --event ...
   --category ...` command. Run it in the same turn and target.
3. The CLI runs its fixed, non-shell current-state inspection and succeeds only
   when that subprocess exits zero.
4. The retry is not described as user-authorized merely because the gate is
   armed; Codex's permission boundary still applies.
5. `PostToolUse` opens a matching verification obligation.
6. `acgm-codex gate verify --event ... --category ...` repeats the fixed check
   and closes only the mechanical obligation on exit zero.
7. Inspect the output before claiming the semantic postcondition is verified.

Ordinary Bash `PostToolUse.tool_response` text must never arm or close anything.
Also test an incorrect event/category, a nonzero fixed check, another disposable
target, concurrent matching retries, shell expansion, globbing, and a compound
command. None may arm or close the wrong operation, and exactly one retry may
consume one arm.

## 7. Bounded Stop behavior

In a fresh disposable fixture, allow a recognized action but omit the
postcondition.

Expected: the first `Stop` asks Codex to continue and verify. If the obligation
is still open when the continued turn stops, ACGM records it as unresolved and
does not create an infinite loop.

Also delete the versioned runtime only in a disposable profile after its Hook
command has been captured. Every released Hook command must exit zero with an
empty result; `Stop` must not trigger a model/Hook cycle. Restore by reinstalling
the exact release, not by editing the real user cache.

## 8. Compaction and subagents

Trigger a manual compact and start one subagent.

Expected: `PreCompact` records only a source-minimized heartbeat—no project
snapshot, compressed context, or replacement baseline. A subsequent
`SessionStart` re-grounds from current project files; the subagent receives
governance context without raw ledger contents.

## 9. Ledger privacy and reporting

Use unique harmless fixtures representing a path, remote URL, fake model name,
fake token, and command text. Exercise Hooks, locate the data directory from
doctor, and search every persistent file.

Expected: none of the raw fixtures appears. Run:

```bash
"$ACGM" report --project current --limit 50 --json
```

Activity is distinguishable from a verified interception. `export-case`
creates only a new local preview, refuses to overwrite existing or governance
state files, and never uploads it.

Confirm the standalone CLI and Hook resolve the same official `PLUGIN_DATA`
ledger through the mode-`0600` locator. The locator may contain the absolute
data-directory path; no Event Ledger record may contain the fixture paths. In a
disposable copy only, remove the HMAC key while retaining a nonempty ledger and
confirm that runtime refuses a silent new audit epoch.

## 10. Upgrade trust, Windows boundary, and clean exit

Change a disposable Hook definition, reinstall, and start a new task.

Expected: Codex marks the changed definition hash for review. Restore the
released definition, reinstall, review it once, and confirm the first real Hook
restores completion without a second artificial task.

Native Windows runtime remains `BLOCKED` for this candidate because Event
Ledger locking still depends on POSIX `fcntl`. CI may verify a fail-closed
contract on Windows, but that is not Windows installation or runtime E2E.

Record only observed results in `EVIDENCE.md`. Do not promote failed, skipped,
fixture-only, or source-checkout results into installed-platform claims.
