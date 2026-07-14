---
name: session-grounding
description: Re-ground a Codex task in verified project state and preserve evidence boundaries. Use at the start of a new task, after context compaction, during recovery or handoff, when resuming a long-running project, or whenever the cwd, repository, branch, worktree, transcript, or remembered state may be wrong or stale.
---

# Session Grounding

Reconstruct the working baseline before drawing conclusions or changing files.

## Resolve the CLI

Prefer `acgm-codex`. If unavailable, resolve the absolute directory containing this installed `SKILL.md`, ascend two levels to the plugin root, and run `<plugin-root>/bin/acgm-codex`. Never assume the project cwd is the plugin directory.

## Verify current state

1. Run:

   ```sh
   pwd -P
   git rev-parse --show-toplevel
   git branch --show-current
   git rev-parse HEAD
   git worktree list --porcelain
   git status --short --branch
   ```

2. Confirm the intended project, Git root, branch, and worktree before reading or writing project files. Stop if the cwd is wrong.
3. Run `acgm-codex doctor <verified-git-root>` through the resolved entry point.
4. Follow the governance paths reported by project configuration or `doctor`; inspect the latest snapshot and the ADRs relevant to the task. Do not guess paths or assume that the newest timestamp contains the governing decision.
5. Reconcile claims with current files and Git history. Treat a missing artifact as missing evidence, not permission to invent it.

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

State concisely:

1. verified project path, branch, worktree, HEAD, and cleanliness;
2. latest relevant snapshot and ADR;
3. confirmed objective and constraints;
4. discrepancies between current state and historical material;
5. unresolved evidence gaps;
6. next safe action.

After compaction or handoff, restate this grounding note before continuing. Re-run the checks when repository state may have changed.

Treat the personal Codex hook as a deterministic guardrail, not a complete safety boundary. It does not make stale memory current or prove that the intended project was selected.
