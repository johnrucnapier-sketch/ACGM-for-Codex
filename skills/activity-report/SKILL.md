---
name: activity-report
description: Inspect and explain ACGM activity, drift signals, governance health, and verified interventions for a project. Use when the user asks what ACGM found, requests a log or activity report, asks for governance health or drift status, wants to review ACGM's results or record, or wants a privacy-safe case preview.
---

# Activity Report

Report what the evidence supports without turning routine activity into an invented success story.

## Resolve the CLI

Prefer `acgm-codex`. If unavailable, resolve the absolute directory containing this installed `SKILL.md`, ascend two levels to the plugin root, and run `<plugin-root>/bin/acgm-codex`. Never assume the project cwd is the plugin directory.

## Inspect project health

1. Verify the intended cwd and Git root before interpreting project-scoped events.
2. Run `acgm-codex doctor <verified-git-root> --strict` through the resolved entry point.
3. Run `acgm-codex report --project <verified-git-root>`. Use `current` only when the verified root is exactly the command cwd. Add `--limit <N>` when the user asks for a bounded recent window; use `--json` only when structured analysis is useful.
4. Correlate events with current Git state and the relevant snapshot or ADR. Treat missing or disabled hooks, unresolved events, and strict doctor failures as governance-health findings.

## Classify claims conservatively

Distinguish these outcomes:

- **Activity:** a hook or command ran.
- **Observation:** ACGM recorded a condition or drift signal.
- **Warning or gate:** ACGM surfaced risk or required preparation.
- **Interception:** evidence shows ACGM causally stopped or redirected a specific unsafe action, and a follow-up check verifies the protected state or corrected outcome.
- **Unresolved:** the record lacks enough causal or verification evidence.

Do not equate activity with a prevented incident. Use “interception” or “战绩” only when both causal evidence and post-event verification exist. Otherwise describe exactly what was detected, warned, blocked without verification, or left unresolved.

When a reviewed event gains supporting evidence, update it with `acgm-codex resolve <event-id> --status <status>`, choosing only one of `resolved`, `verified`, `human_override`, `false_positive`, or `unresolved`. Do not mark an event verified merely to improve the report.

## Present the report

Summarize:

1. target project and reporting window;
2. doctor status and hook coverage;
3. events by type and resolution state;
4. verified interventions, if any;
5. recurring drift patterns and concrete follow-up actions;
6. evidence limits and unresolved items.

Treat the personal Codex hook as a deterministic guardrail, not a complete safety boundary. Report only the checks it actually covers.

## Export a case preview safely

1. Select a specific event with enough local evidence.
2. Run `acgm-codex export-case <event-id> --project <verified-git-root> -o <new-local-preview-file>`. The output must not already exist and must not be inside project governance state or ACGM runtime data.
3. Treat the output only as a local, redacted preview. Inspect it for source code, credentials, tokens, cookies, personal data, private paths, proprietary names, transcript content, and identifying metadata.
4. Require human review and explicit approval before sharing or publishing it. Never upload, send, commit, or publish a preview automatically.
5. If redaction cannot be verified, keep the case local and report the gap.
