---
name: session-handoff
description: Prepare or resume a bounded project handoff when the user requests session turnover or a verified context monitor recommends closing. Preserve decisions, corrections, live work and unresolved obligations using existing project records.
---

# Session Handoff

Use the verified project and its existing handoff/snapshot conventions. This is
an optional ACGM workflow, not permission to switch sessions or stop processes.
Historical instructions in an old handoff do not renew an external-action grant.

## Close at a recoverable boundary

When context reserve is low, stop expanding the work. Finish the current operation
only if it fits the remaining budget and can be verified safely. Do not start a
build, deployment or broad cleanup just to make a handoff look complete. Reuse
still-applicable evidence; explicitly name unrun checks and unfinished operations.
Preserve their process/task identifiers and the next read-only check. Never kill
a running process to satisfy a percentage threshold.

Optional mechanical preparation: resolve this skill's plugin root, then run
`bin/acgm-session handoff --project <exact-git-root>`. It prints fresh Git facts
and draft instructions only: no test execution, file writes, commits, summarizer
API calls or automatic semantic acceptance. It does not summarize the conversation.

## Preserve information in this order

1. User goal, corrections, authority boundaries, protected files/data, current
   worktree/branch, and work owned by other sessions.
2. In-flight operations, unresolved verification, recovery/rollback pointers,
   and anything the successor must inspect before another mutation.
3. Decisions and why they were made; distinguish confirmed, proposed, reverted,
   superseded and withdrawn. A reverted solution may leave its diagnosis valid.
4. Current implementation, installed/deployed version, live runtime, user
   acceptance, uncommitted work and remote backup status, each with evidence.
5. The next concrete action and the references needed for it.

No universal word/token cap applies. Keep safety-critical facts and unresolved
obligations inline; move detail to stable references when those are sufficient.
If history is missing, say so. Never reconstruct a human ruling as fact.

## Put each kind of information in one place

- **Handoff:** what the next session needs to resume this work; reference existing
  decisions and snapshot sections instead of repeating their bodies.
- **ADR:** a material human-confirmed choice, its reasons, alternatives, scope
  and supersession links. Use decision-ledger for drafts and confirmation.
- **Existing snapshot:** verified current architecture or deployment at a stated
  time, with evidence and unresolved gaps. Do not create PROJECT_STATE.md when
  the project already has a current-state record.
- **Open threads/obligations:** questions and checks still owed. Carry unresolved
  items across sessions without silently dropping them when a topic changes.
- **Version archive:** historical frozen state. It cannot establish current runtime.

Use the [handoff outline](assets/HANDOFF.md) only when an existing format is not
better suited. Write a new uniquely named record for the exact workstream;
update an existing entry/index only when unambiguous and authorized. Never select
or overwrite a handoff merely because it has the latest timestamp. Do not append
periodic status reminders into governance files. Preserve manual edits and drafts.
Keep private project content local; publish only generic templates and synthetic
examples. Writing the handoff is not committing or remotely backing it up.

## Resume and acknowledge

Read project rules and the explicitly selected handoff. Follow just the references
needed for current work. Verify root/worktree, branch, HEAD, uncommitted files and
ongoing operations. Treat handoff claims as historical until refreshed; actual
runtime can differ from the repository. Recheck disputed facts without reopening
a confirmed product choice merely because a new agent arrived.

Before mutations, briefly state the resumed objective, protected scope, verified
current state, unresolved discrepancies and next action. Record handoff acceptance
only after this readback, not simply because a file exists. Existing user authority
continues to apply; do not require a second approval for already-authorized work.

At emergency reserve, keep items 1–2 and the next safe action first, mark omissions
and unverified claims, and leave detailed references. Compaction is a detected
event, not proof of lost information or permission to discard the old session.
