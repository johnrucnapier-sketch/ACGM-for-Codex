---
name: truth-first
description: Prepare, authorize, execute, and verify high-risk or state-sensitive changes with explicit evidence. Use before irreversible or destructive actions, external-state mutations, releases, pushes, deployments, migrations, credential or permission changes, or any action whose safety depends on the current repository or service state.
---

# Truth First

Separate evidence collection, mutation, and verification so that assumptions cannot masquerade as current truth.

## Resolve the CLI

Prefer `acgm-codex`. If unavailable, resolve the absolute directory containing this installed `SKILL.md`, ascend two levels to the plugin root, and run `<plugin-root>/bin/acgm-codex`. Never resolve the plugin from the project cwd.

## Build the gate card

Before mutation, write down all four items:

1. **Target:** identify the exact repository, worktree, branch, file, resource, account, or environment and the intended action.
2. **Current state:** collect fresh, read-only evidence at the source of truth. Include timestamps or revisions when state can drift.
3. **Authorization and rollback:** identify what the user authorized, what remains unauthorized, the blast radius, prerequisites, and a tested or credible rollback path.
4. **Postcondition:** define the observable state that will prove success, plus the checks that would expose partial failure.

Stop when any item is materially unknown. Ask for user direction when the missing fact changes scope, authority, risk, or outcome.

## Arm the mechanical gate

For a command that matches one of ACGM's protected categories, follow the runtime sequence exactly:

1. Complete the gate card and obtain any authorization the action actually requires.
2. Submit the exact, narrowly scoped high-risk command and receive the expected first-attempt Hook denial. Do not bypass that denial or treat it as execution.
3. **After the denial**, run the exact `acgm-codex gate arm --event <event-id> --category <category>` command supplied by the Hook. Append `--target <directory>` only when the denied action targeted a directory other than the current one. Do not invent or reuse an event id.
4. Inspect the fixed read-only check output printed by that command. The runtime arms only after the non-shell subprocess exits zero, but zero does not prove the output is semantically safe. If the observed state is unexpected, do not retry; let the arm expire and reassess.
5. Retry the same scoped command once. A changed target, category, turn, expanded path, or compound command requires a new denial-and-check sequence.

Treat arming as preparation for deterministic Hook checks. It is not user authorization, evidence that the check's output is semantically satisfactory, or permission to expand scope. Do not use a broad category to bypass a rejected or expired gate.

The personal Codex hook is a deterministic guardrail, not a complete safety boundary. It may catch supported command patterns, but it cannot infer intent, verify every external precondition, confer authorization, or guarantee that every execution path passes through it.

## Execute one bounded action

1. Finish the required post-denial read-only evidence collection before mutation.
2. State the exact action about to occur and its expected postcondition.
3. Execute only the authorized, scoped mutation. Avoid combining unrelated mutations.
4. Preserve raw command results needed for verification; do not reinterpret an exit code as proof of the desired outcome.

## Discharge the verification obligation

Every high-risk action creates a verification obligation. Complete it before calling the task done:

1. Run the exact `acgm-codex gate verify --event <obligation-id> --category <category>` command supplied by the Hook, with the same optional `--target` rule.
2. Compare the fixed check output with the stated postcondition. A zero exit closes only the runtime's mechanical obligation.
3. Check for partial success, unexpected collateral changes, and rollback viability with additional authoritative evidence when needed.
4. Record whether the action is verified, failed, ambiguous, or rolled back.
5. If verification cannot be completed, say so explicitly and leave the task incomplete; do not convert absence of evidence into success.

Keep the three phases visible in the final account: evidence acquired, action taken, and postcondition verified.
