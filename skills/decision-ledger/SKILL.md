---
name: decision-ledger
description: Preserve material project decisions and unresolved questions across tasks and compaction. Use during architectural or product discussions in an authorized project, when a decision thread closes, or when resuming its existing ledger. Skip routine edits and tool logs.
---

# Decision Ledger

Record the reason a path was chosen while the evidence is available. Adapted from
ACGM for Claude Code 0.9.2; this is an advisory workflow, not a Hook-enforced claim
that the user approved a decision.

## Keep the record small

Use the verified project root and its existing governance conventions. Within
authorized project work, create these files only when there is something material
to preserve. Read-only requests remain read-only. Do not initialize unrelated
projects or overwrite existing policy.

- `.governance/OPEN_THREADS.md`: current unresolved questions, rewritten as state.
- `.governance/claims/`: one unconfirmed draft per closed decision thread.
- `.governance/decisions/`: human-confirmed ADRs, following the project's workflow.

Record alternatives, constraints, reasons, evidence, and remaining uncertainty.
Do not duplicate command logs, file-change lists, transcripts, or trivial choices.
Keep credentials, private conversation details, and unnecessary personal data out
of these Git-trackable records. A working-tree file is saved locally, not committed
or backed up remotely. Commit and publication follow the user's existing authority.

## Draft when a thread closes

A human ruling, movement to another topic, entry into implementation, or a resolved
objection can close a thread. Only the first establishes human approval; silence,
implementation, and lack of further objection never do. Preserve uncertainty in
the draft. If the question is still unresolved, keep it in OPEN_THREADS.

Use [the claim template](assets/CLAIM.md). Check existing IDs before choosing a
new filename; a date alone does not prevent worktree collisions. Write the draft
before removing its open-thread entry so an interruption does not lose both.
Capture one thread once, not once per message. Mark reconstructed history explicitly.

## Confirmation never interrupts work

Drafting does not wait for confirmation. Mention relevant pending drafts in a
report or question already needed for the task; bundle them and do not repeat an
unanswered request. Never block a turn or invent a confirmation task for the ledger.

Promote only on an actual human ruling. The agent may write the ADR implementing
that ruling, using [the ADR template](assets/ADR.md), linking the source claim and
the actual confirmation. Never fabricate a quote or treat a Hook result as consent.
Preserve the source claim. Supersede decisions explicitly rather than rewriting
their history. Follow the repository's branch and review policy; do not force a
switch to trunk or merge a worktree just to record a decision.

## Resume and finish

Read OPEN_THREADS and relevant claims/ADRs on resume. Recheck technical claims
against current code and Git. Before the ordinary final report, save material open
questions and identify any unconfirmed draft or uncommitted ledger work relevant
to continuation. Do not promise an automatic SessionEnd report: this Codex adapter
does not implement that Claude mechanism.

Claims and OPEN_THREADS are outside the activation baseline. Markdown ADR and
snapshot changes produce an advisory reminder, not a reactivation requirement.
Review relevant changes on resume; changed text does not establish approval.
Actual policy changes still require the authorized activation workflow. Never
auto-reactivate to hide policy drift.

中文：只记录影响决策与路径的信息。开放问题保留在线程表，闭合后立即保存未确认草案；
沉默、开始实施或换话题都不等于批准。确认只随正常汇报提出，不阻塞、不催问。
遵守项目已有分支、提交及隐私约定；落盘、提交、远端备份是三个不同状态。
