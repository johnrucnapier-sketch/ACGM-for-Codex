---
name: governance-bootstrap
description: Install, quickstart, activate, repair, or verify ACGM governance for a Codex project with one-consent recommended defaults. Use when the user asks to set up, enable, bootstrap, initialize, reinstall, automate, or fill gaps in project governance, including Constitution, scope, ADR, snapshot, activation, and installation verification.
---

# Governance Bootstrap

Set up governance automatically without replacing project-owned instructions or decisions.

## Resolve the CLI

1. Prefer `acgm-codex` when `command -v acgm-codex` succeeds.
2. Otherwise, resolve the absolute directory containing this installed `SKILL.md`, ascend two levels to the plugin root, and run `<plugin-root>/bin/acgm-codex`.
3. Never derive the plugin root from the project cwd. Stop and report an incomplete installation if neither entry point exists.

## Verify the exact target

1. Run read-only checks before initialization:

   ```sh
   pwd -P
   git rev-parse --show-toplevel
   git branch --show-current
   git worktree list --porcelain
   git status --short --branch
   ```

2. Confirm that the intended project, Git root, branch, and worktree agree. In a multi-repository workspace, require the exact child repository; never initialize a container directory or guess among siblings.
3. Inspect existing `AGENTS.md` and governance artifacts before running initialization. Treat their contents as project-owned.

## Prefer one-consent quickstart

The installed `acgm-codex quickstart` command governs one project after the
plugin is present. When operating from the official release repository,
`python3 scripts/quickstart.py` is the combined installer: it also installs a
fresh plugin or upgrades one exactly verified official RC2/RC3/RC4/0.2-RC1/0.2-RC2 installation
under the same digest-bound authorization.

1. Run `acgm-codex quickstart plan <verified-git-root> --json` through the resolved entry point. This phase must remain read-only.
2. Treat the user's direct request to install, enable, initialize, or quickstart ACGM in this exact project with recommended defaults as authorization for the generated `standard-v1` plan. Do not ask for a second confirmation when the plan only:
   - creates missing versioned governance assets;
   - replaces byte-identical ACGM stock placeholders;
   - preserves substantive existing policy;
   - activates this exact Git root; and
   - runs local postcondition checks.
3. Run `acgm-codex quickstart apply <verified-git-root> --plan-digest <digest> --authorize --json`.
   The Agent copies the machine-generated digest internally; the user does not
   type it, edit config, or hand-write Constitution/ADR/snapshot files.
4. Preserve every unknown existing `AGENTS.md`, Constitution, scope, decision, and snapshot. If the plan reports a conflict, stop before mutation and explain the exact file; never weaken or silently overwrite project policy.
5. Confirm the result is either `COMPLETE` or `AWAITING_PLATFORM_HOOK_ACCEPTANCE`. Do not equate installed files with verified activation.

## Use the manual path only for custom policy

Use `acgm-codex init <verified-git-root>` only when the user explicitly requests custom governance rather than the recommended preset, or when quickstart reports an existing-policy conflict. Preserve all existing files and prepare a bounded proposal for the user-owned content.

Project quickstart authorization covers only local non-overwriting governance setup. The repository-level combined installer additionally covers its exact planned Codex marketplace/plugin writes, the manifest- and digest-bound stable Hook runtime publication, the narrow verified official RC2/RC3/RC4/0.2-RC1/0.2-RC2 replacement, and digest-bound roll-forward of a completely verified interrupted official transition. Neither form authorizes a release, deployment, unrelated destructive action, credential change, legacy/personal migration, private data adoption, or unknown conflict resolution.

## Activate and verify

1. Quickstart performs activation and a non-strict doctor check automatically. Confirm `project_state=GOVERNED`.
2. After a plugin install or replacement, fully quit and reopen Codex desktop. Then, if Codex presents `/hooks`, the user must personally review the exact definitions; neither the skill nor installer may bypass that boundary. When the pending set contains only this verified ACGM release and Codex offers **Trust all and continue**, the user may accept the bundle in one platform action. Never bulk-trust unrelated or unknown Hooks.
3. After trust, continue normal work. The first actually observed ACGM Hook records the current activation heartbeat; a separate artificial verification task is not required.
4. Run `acgm-codex quickstart status <verified-git-root> --json` or strict doctor after the first observed Hook. Report `AWAITING_PLATFORM_HOOK_ACCEPTANCE` as pending platform acceptance, not as failed project setup.
5. Recheck `git status --short --branch` and summarize the exact files created, replaced from known stock placeholders, or preserved.

Treat the personal Codex hook as a deterministic guardrail for checks it can mechanically evaluate, not as a complete safety boundary. It cannot establish semantic truth, supply user authorization, or replace post-action verification.
