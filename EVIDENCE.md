# Claim maturity register

This file prevents implementation activity from silently becoming a product
claim. Promotion requires evidence at the level stated below.

**Current RC status:** the personal install and Codex cache registration passed
locally on 2026-07-13, but a completely new Codex task has not yet recorded a
passed `/hooks` review/trust plus real-tool E2E for this RC. Claims that depend on
actual Hook discovery therefore remain at “Designed / automated fixture.”

| Claim | Current maturity | Required next evidence |
|---|---|---|
| The package has a valid Codex manifest and installable skill inventory | Automated contract + local install | Confirm skill discovery in a completely new task |
| Project state does not equate installation with governance | Automated contract | Runtime lifecycle tests and disposable-repo E2E |
| Session startup injects current grounding | Designed / automated fixture | New-task `SessionStart` Hook heartbeat and visible context |
| Constitution writes are intercepted | Designed / automated fixture | Real `apply_patch` denial in a disposable governed repo |
| Narrow destructive operations require a target-bound fixed current-state gate | Designed / automated fixture | Real Bash path: deny, fixed check, atomic arm consumption, retry, verify |
| Post-action obligations prevent a quiet first stop | Designed / automated fixture | Real `PostToolUse` and bounded `Stop` continuation |
| The Event Ledger is source-minimized | Automated contract | Search the real plugin data directory after E2E |
| ACGM reduces long-horizon drift in general | Predictive | Repeated external project trials with reviewed controls |

## Local evidence recorded for this RC

- Codex CLI: `0.144.0-alpha.4`.
- Python: `3.14.5` and `3.10.17`.
- Automated suite: 49 tests passed on both Python versions; plugin and all four
  skill validators passed through `scripts/release_check.py`.
- Personal install: `acgm-codex@personal` version `0.1.0-rc.1` registered as
  installed and enabled; the CLI wrapper reported the same version, and the
  cached Hook definition matched the source checkout.
- Not yet evidenced: new-task skill discovery, Hook trust, actual `SessionStart`,
  real tool interception, bounded `Stop`, compaction, or real `PLUGIN_DATA`
  privacy inspection.

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
- Claude Code V3 test results do not validate the Codex adapter.
- A single incident or arbitrary age threshold cannot create a universal hard
  governance rule.
