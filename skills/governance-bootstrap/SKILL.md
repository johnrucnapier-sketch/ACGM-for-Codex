---
name: governance-bootstrap
description: Initialize, install, activate, repair, or complete ACGM governance for a Codex project. Use when the user asks to set up, enable, bootstrap, reinstall, or fill gaps in project governance, including Constitution, scope, ADR, snapshot, activation, and installation verification.
---

# Governance Bootstrap

Set up governance without replacing project-owned instructions or decisions.

## Resolve the CLI

1. Prefer `acgm-codex` when `command -v acgm-codex` succeeds.
2. Otherwise, resolve the absolute directory containing this installed `SKILL.md`, ascend two levels to the plugin root, and run `<plugin-root>/bin/acgm-codex`.
3. Never derive the plugin root from the project cwd. Stop and report an incomplete installation if neither entry point exists.

## Verify the target

1. Run read-only checks before initialization:

   ```sh
   pwd -P
   git rev-parse --show-toplevel
   git branch --show-current
   git worktree list --porcelain
   git status --short --branch
   ```

2. Confirm that the intended project, Git root, branch, and worktree agree. Stop before reading or writing project files if the cwd points at the wrong project.
3. Inspect existing `AGENTS.md` and governance artifacts before running initialization. Treat their contents as project-owned.

## Initialize without overwriting

1. Run `acgm-codex init <verified-git-root>` through the resolved entry point.
2. Preserve every existing `AGENTS.md` and Constitution. Never overwrite, silently merge, or weaken them. If initialization reports a conflict, show it to the user and propose a bounded manual integration.
3. Review the command output and resulting diff. Distinguish newly created scaffolding from pre-existing project policy.

## Establish the governance baseline

Work with the user to complete these artifacts in this order:

1. **Constitution:** Draft principles, invariants, prohibited actions, and decision ownership as a proposal in chat or a separate non-governance draft. Treat the Constitution as human-owned. After `init` creates the adapter marker, ACGM blocks automated writes to `CONSTITUTION.md`; the user must personally put the confirmed text into that file through an editor outside Codex tool automation. Never ask to disable or bypass the Hook for bootstrap.
2. **Scope:** Record the current objective, allowed paths and systems, prohibited areas, and acceptance criteria. Ask for direction when a missing choice would materially change scope.
3. **ADR:** Record consequential design decisions, alternatives, evidence, and unresolved risks. Do not turn tentative discussion into a decided outcome.
4. **Snapshot:** Capture verified repository state and the next safe action. Label historical or reconstructed context separately from current facts.

Keep drafts explicit until the user confirms them. Do not infer authorization for external or irreversible actions from initialization.

## Activate and verify

1. Run `acgm-codex activate <verified-git-root>`.
2. Run `acgm-codex doctor <verified-git-root>` without `--strict` and confirm the project state is `GOVERNED`. Do not claim governance is active merely because files were created.
3. Activation resets the accepted-heartbeat time. Start a new Codex task, review and trust the current definitions in `/hooks`, and let `SessionStart` run before using `acgm-codex doctor <verified-git-root> --strict` as the automatic-Hook acceptance check.
4. If a new trusted task has not yet produced that heartbeat, report strict health as pending platform acceptance rather than as a governance-content failure.
5. Resolve every other strict diagnostic or report the remaining failure precisely.
6. Recheck `git status --short --branch` and summarize the exact files added or left untouched.

Treat the personal Codex hook as a deterministic guardrail for checks it can mechanically evaluate, not as a complete safety boundary. It cannot establish semantic truth, supply user authorization, or replace post-action verification.
