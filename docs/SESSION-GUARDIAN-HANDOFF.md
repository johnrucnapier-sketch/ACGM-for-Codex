# Session Guardian development handoff — 2026-09-14

Status: ready for successor readback; not yet accepted by another session.
Branch: codex/session-guardian. Base commit: e2a951956c0d61ae91cfef51712c0b585cee3a8b.

## Goal and authorization

The user chose an optional ACGM module instead of a separate product and authorized
starting development. The supplied proposal requires independent selection, not
literal implementation. Use existing project handoffs, decisions and snapshots
as references; retain the lean governance approach. No production business code,
Codex context settings, installed plugin caches or private event ledger were changed.
No new permission or 500K configuration is inferred from this design discussion.

## Decisions and provenance

Confirmed product direction: optional ACGM module, prioritize reliable long-project
continuity, reuse real handoff practices. Implementation choices below are provisional,
not new human-approved ADRs: Codex-only prototype; read-only version-bounded rollout
fallback; foreground watch; semantic drafting through a skill; no daemon/database,
auto-commit, automatic switching or additional long-term project-state file.

Source study distilled: preserve constraints, corrections, in-flight obligations,
decision status/reasons, source versus actual runtime, and next-action references.
A reverted decision can retain a valid diagnosis. Historical handoff commands do
not renew authorization. Private source examples were not imported into this repo.

## Current implementation

- bin/acgm-session and scripts/session_guardian.py implement read-only status/watch,
  exact thread+project directory matching, bounded incremental rollout reading,
  explicit unknown/stale quality, adjustable thresholds and handoff/resume preparation.
- skills/session-handoff gives the actual semantic preservation/readback workflow,
  reusing decision-ledger and existing project documents. No fixed handoff length.
- docs/SESSION-GUARDIAN.md records research, selection and platform limits.
- Tests use synthetic sessions, including dirty/untracked handoff preservation.

Live observation in this source task: the verified CLI rollout produced current
context samples and CAUTION; a three-second watch printed one unchanged-state
notification. This proves local reading and foreground reporting, not native UI
notification delivery, automatic agent compliance or reliable next-session recovery.

## Outstanding work and next action

Read the research/limits document and test results before extending the prototype.
Run a normal user-authorized project handoff and successor readback to evaluate
whether constraints, corrections and obligations actually survive. Fix concrete
losses before adding more formats or platforms. A native official event subscription
must not resume/take over an active desktop thread just to obtain telemetry.

Before any installed release: choose a new package version, update immutable source
pins and manifest, complete release checks and the existing installation procedure.
The currently installed 0.3.0-rc.1 remains independent. Do not publish the changed
branch as replacement bytes for the existing immutable tag.

## Recovery and verification boundaries

No in-flight deployment or background monitor remains from prototype testing.
The new optional files can be revised on this branch without changing installed
behavior. Preserve all user changes if branch state differs on resume. Baseline
runtime scripts/acgm_codex.py and hooks/hooks.json were not changed. The source
checkout has no activated governance baseline; do not create a Constitution merely
to make its doctor appear healthy. Git state is current truth for this handoff.

## Source checks completed

Release checker passed plugin contract, all six skills, manifest and 192 tests.
After two extra regression cases and metadata validation, the final 12 session
tests and 19 package tests passed. No baseline Hook/runtime changes followed.
These checks do not constitute installed-version or successor-readback acceptance.
