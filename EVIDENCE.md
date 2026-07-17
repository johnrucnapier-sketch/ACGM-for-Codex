# Claim maturity register

This file prevents implementation activity from silently becoming a product
claim. Promotion requires evidence at the level stated below.

**Current RC status:** RC4's tag-pinned marketplace/preflight/bootstrap lifecycle
is covered by isolated fixtures that include the JSON shapes observed from a real
Codex CLI. On 2026-07-17, a new governed Codex task after Hook trust recorded a
real `SessionStart` heartbeat for the current activation in official
`PLUGIN_DATA`. Formal strict acceptance did not pass: standalone `doctor` tried
to mutate already-correct locator/ledger metadata inside a managed read-only
sandbox and incorrectly reported the ledger unavailable. The read-only runtime
fix and regression test are not a released RC, so broader automatic-Hook claims
remain unpromoted. RC1's personal install is historical evidence, not RC4
acceptance.

| Claim | Current maturity | Required next evidence |
|---|---|---|
| The package has a valid Codex manifest and installable skill inventory | Automated contract + local install | Confirm skill discovery in a completely new task |
| Project state does not equate installation with governance | Automated contract | Runtime lifecycle tests and disposable-repo E2E |
| Session startup injects current grounding | Real Hook heartbeat; strict CLI compatibility finding remains | Release and reinstall the read-only diagnostic fix, then obtain strict pass plus visible context in a fresh task |
| Constitution writes are intercepted | Designed / automated fixture | Real `apply_patch` denial in a disposable governed repo |
| Narrow destructive operations require a target-bound fixed current-state gate | Designed / automated fixture | Real Bash path: deny, fixed check, atomic arm consumption, retry, verify |
| Post-action obligations prevent a quiet first stop | Designed / automated fixture | Real `PostToolUse` and bounded `Stop` continuation |
| The Event Ledger is source-minimized | Automated contract | Search the real plugin data directory after E2E |
| ACGM reduces long-horizon drift in general | Predictive | Repeated external project trials with reviewed controls |

## RC2 public-bootstrap finding

On 2026-07-15, a fresh isolated `HOME`/`CODEX_HOME` cloned public tag
`v0.1.0-rc.2` at commit `4deb6d1` and ran against Codex CLI
`0.144.0-alpha.4`. Source preflight and dry-run passed. The exact marketplace-add
command returned zero, after which bootstrap stopped at
`MARKETPLACE_ADDED_BUT_POSTCONDITION_UNVERIFIED` rather than claiming success.

The real CLI omitted `ref` from `marketplace list --json`, returned an empty
pre-install `available` array, and reported an installed Git plugin with source
kind `git` rather than the fixture's assumed `url`. The exact ref was still
present in read-only `config.toml` evidence and the clean marketplace snapshot;
an explicitly addressed plugin add succeeded in the disposable profile. This was
an RC2 release-tool schema mismatch and false conflict, not a Hook failure or
damaged installation. Hook trust, heartbeat, and project bootstrap were not
reached, and RC2 was not promoted to a GitHub Release.

## RC3 public-bootstrap finding

On 2026-07-15, a second fresh isolated profile cloned public tag
`v0.1.0-rc.3` at commit `244a0e4`. Source preflight and dry-run passed, and the
marketplace-add command returned zero. The new persisted-config plus exact-tag
snapshot evidence chain also passed completely. In this run, however, the real
CLI enumerated the uninstalled plugin with the exact ID, repository, ref, and
policy but `version: null`. RC3 conservatively treated that explicit null placeholder as a
conflict and stopped at `MARKETPLACE_ADDED_BUT_POSTCONDITION_UNVERIFIED` before
plugin add. This was another pre-install CLI-schema compatibility finding, not a
Hook or package-integrity failure. RC4 accepts a null available version only when
the complete independent runtime evidence chain proves the exact candidate.

## Local evidence recorded for the current RC

- RC4 automated fixtures cover fresh install, dry-run, explicit authorization,
  idempotence, legacy personal and duplicate conflicts, command failure/partial
  state, exact tag/manifest verification, exact cache inventory/byte
  verification, missing marketplace, invalid available plugin state, the
  observed omitted-ref/empty-available/explicit-null-version/Git-source CLI shapes,
  tampered persisted ref/snapshot evidence, and Windows fail-closed behavior.
- Release validation passed on Python 3.10 and the current Python after the
  final package manifest was regenerated (77 tests on each interpreter).
- RC1 historical personal install: `acgm-codex@personal` version `0.1.0-rc.1`
  was registered and enabled locally. RC4 treats it as a migration conflict.
- A new trusted task recorded an RC4 `session-start` heartbeat for the current
  governed activation. A following `PreToolUse` denial targeted a read-only
  Constitution inspection and was a false positive, not evidence of a correctly
  prevented write.
- Not yet evidenced: complete new-task skill discovery, strict doctor pass in
  the managed sandbox, correct real write interception, bounded `Stop`,
  compaction, or exhaustive real `PLUGIN_DATA` privacy inspection.

## Rejected inferences

- A Hook event count is not a prevented incident count.
- A skill invocation is not proof that the workflow was followed.
- A denied operation is not automatically a correct denial.
- A gate arm is not user authorization.
- A fixed check event proves the runtime's non-shell subprocess exited zero, not
  that its human-meaningful postcondition was satisfied.
- A mechanical obligation closure is not semantic verification of the action.
- A `permission-boundary-observed` event is not an ACGM approval, denial, or
  authorization; the `PermissionRequest` callback deliberately returns no
  decision.
- A `PreCompact` heartbeat is not a governance snapshot or preserved context.
- Installing the plugin is not proof that its Hooks were trusted or ran.
- A successful Git marketplace add or matching cache is not a trusted Hook,
  fresh-task heartbeat, or bootstrapped project.
- Claude Code V3 test results do not validate the Codex adapter.
- A single incident or arbitrary age threshold cannot create a universal hard
  governance rule.
