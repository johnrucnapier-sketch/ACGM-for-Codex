---
name: session-grounding
description: Re-ground a Codex task in verified project state and preserve evidence boundaries. Use for recovery after compaction or handoff, resuming a long-running project, or a concrete uncertainty about project identity or remembered state. Do not invoke solely because an ordinary short task has started.
---

# Session Grounding

Reconstruct the working baseline before drawing conclusions or changing files.

## Resolve the CLI

Prefer `acgm-codex`. If unavailable, resolve the absolute directory containing this installed `SKILL.md`, ascend two levels to the plugin root, and run `<plugin-root>/bin/acgm-codex`. Never assume the project cwd is the plugin directory.

## Verify current state

Recover only the facts needed for the current work. Absence of a Hook workflow
message is not a request for Standard recovery and does not prove Hooks ran.
Honor explicit project requirements, outstanding obligations and incident notices.
Do not run `policy` or `doctor` merely to choose how much ceremony to perform.

1. Establish the intended root, branch/worktree and relevant changes when these
   are uncertain. Batch relevant Git reads; reuse current evidence rather than
   mechanically running every identity command again.
2. Read applicable project rules and the snapshot, decisions or unfinished work
   relevant to the resumed task. Do not reload every historical record. Open
   questions and draft claims are not accepted decisions.
3. Run `acgm-codex doctor <exact-root>` when activation/integrity is uncertain,
   reported unhealthy, or installation verification is requested. A healthy
   project does not need a doctor call at every task entry.
4. Reconcile material historical claims with current files. Report missing
   evidence rather than inventing it. Restore unresolved verification obligations
   across sessions; a new session does not discharge them.

Before service, deployment or destructive operations, use `truth-first` for the
exact target, authorization, recovery conditions and independent postconditions.
Resolve unknown targets or LOCAL/REMOTE conflicts before the affected mutation.
Existing mechanical Gates and native permissions apply regardless of workflow
advice. Guardian is independent. Never edit policy or reactivate governance to
reduce checks. Explicitly requested workflow assistance remains applicable;
`acgm-codex policy --project <exact-root> --risk <risk> --json` is available to
explain it, not a prerequisite for ordinary work.

## Preserve the evidence hierarchy

Use these labels when reporting material conclusions:

- **Current verified fact:** observed in current code, configuration, filesystem, or Git state.
- **Git-verified fact:** established by commits, tags, diffs, or tracked history.
- **Historical decision:** stated in a main transcript, snapshot, ADR, or memory but not independently current.
- **Reconstructed conclusion:** supported by multiple evidence sources but not directly recorded as one fact.
- **Unconfirmed lead:** supported by only one incomplete or stale source.
- **Missing history:** not established by available evidence.

Treat current code and Git state as current facts. Treat transcripts and memory as historical evidence: they can explain intent, but they do not override current code. Do not treat a discussed plan as implemented. Use subagent transcripts for local execution details, not as a substitute for the main decision line.

## Publish the grounding note

Report material findings and uncertainty concisely; no separate grounding note
is needed when the facts are already established. At recovery or when state is
ambiguous, cover only the relevant items:

1. verified project path, branch, worktree, HEAD, and cleanliness;
2. latest relevant snapshot and ADR;
3. confirmed objective and constraints;
4. discrepancies between current state and historical material;
5. unresolved evidence gaps;
6. next safe action.

After compaction or handoff, restore the relevant facts before continuing and
report changes or gaps. Re-run checks when repository state may have changed.

Continue within the user's existing authorization. Grounding does not require a
new approval ritual; ask only when a material uncertainty changes the authorized
scope or outcome. Match verification to the change and avoid repeating unchanged
checks. For material decisions, use `decision-ledger` to preserve the reason and
remaining questions without turning normal work into a command log.

Distinguish source verified, configuration verified, runtime observed, and project
governed. One observed Hook proves only that event ran; a cached install record or
historical heartbeat does not establish coverage in the current task.

Treat the personal Codex hook as a deterministic guardrail, not a complete safety boundary. It does not make stale memory current or prove that the intended project was selected.
