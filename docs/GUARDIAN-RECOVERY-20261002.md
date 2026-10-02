# Guardian startup and recovery — 2026-10-02

## Incident evidence and limits

An earlier session was created with Codex 0.159.2. A fresh session later the
same day reported 0.159.0-alpha.12.1, which RC3 had not verified. The exact-version
reader rejected that session; the old Hook converted unavailable observation
into a blocked prompt/tool. A native isolated replay reproduced that rejection.
This was a compatibility/availability defect, not evidence of a dangerous task.

Separately, the older session's latest response usage was 383,413 tokens while
Codex's internal compaction-scope estimate reached 463,677 against a 450,000 limit.
The automatic PreCompact stop then repeatedly interrupted ordinary retries.
The response counter remains useful for trend estimates but cannot prove exact
remaining space, and the cumulative spend counter is not a substitute.

Native replay confirms that a resumed turn can emit PreCompact **before**
UserPromptSubmit. A recovery prompt restricted to its own turn cannot unblock
that ordering. Real logs also contained TLS handshake failures/model-list
timeouts. This fix does not claim to repair network or platform transport errors.
No private transcripts, project code, credentials or user content are published.

## Narrow changes

- Verify exact 0.159.0-alpha.12.1 metrics using local native fixed-Responses
  fixtures. Keep existing verified versions and reject unknown formats in status.
- On unavailable observation, prompts and tools receive UNKNOWN advice instead
  of a Guardian deny. Tool warnings deduplicate until measurement recovers.
  This does not mark the measurement healthy or exempt independent risk Gates.
- Policy corruption, runtime byte integrity, existing budget confirmation gates
  and default automatic-compaction protection remain.
- Explicit `ACGM 恢复会话` records one recovery-compaction permission in existing
  per-session state, for five minutes. If pre-sampling compaction already stopped
  that turn, send `继续` once. The next matching session's compaction consumes the
  permission; it never transfers to a different session or grants a risky action.
  An ordinary subsequent prompt clears an unused permission. No daemon, new
  database, global disable switch or automatic cross-thread action is added.
- After compaction, prompt for project-record/unfinished-work reconciliation.
  UI/Hook wording and status JSON no longer equate response usage with exact
  native compaction headroom.

## Recovery choices

For continued work, prefer a genuinely empty new task with the exact project and
saved handoff paths. A reverted or forked old history is not an empty context.
To recover an already-paused old session, use the two-step flow above. Do not
assume a response was executed merely because it was requested or preserved.
A recovered task still needs normal project verification; this is not a promise
of lossless compression or user acceptance.

## Validation

Acceptance uses disposable CODEX_HOME/project data and fixed local Responses,
not a real model or user session. It must exercise actual new-task execution,
unflushed prompt records, blocked compaction, explicit recovery, a subsequent
normal turn, preserved destructive-operation denial, native sandbox/approval,
and the existing lifecycle cases. Unit tests also cover grant expiry, isolation,
unknown-format telemetry and corrupt policy. Installation and desktop Hook
review/trust remain separate from source/native fixture checks.

The earlier RC3 compatibility report remains historical; its tests did not
establish long-session headroom equivalence or cover the later alpha executable.

Release validation: **264 source tests**, package/skill/manifest checks, and
**33 native scenarios / 37 assertions** on Codex **0.159.0-alpha.12.1** passed.
Native recovery exercised the actual PreCompact-before-UserPromptSubmit order,
then observed a compaction request, successful tool execution and a subsequent
normal turn. The unknown-metrics fixture permitted a local write while denying
a destructive command through the independent Gate. This is deterministic
execution testing, not real-model task-quality or lossless-handoff acceptance.
