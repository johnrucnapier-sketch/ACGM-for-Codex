# Workflow guidance: quiet entry, explicit assistance

Status: source candidate, not an installed-runtime upgrade. The user approved the
bounded direction on 2026-09-16: preserve Hard Core, adjust workflow burden, keep
Guardian independent, and avoid a new framework. This document records that
implementation boundary; it does not authorize installation or project activation.

## What changes

One resolver in the existing runtime selects the strongest of these inputs:

| Input | Profile floor |
|---|---|
| Configured high-autonomy capability | Light |
| General or unknown capability | Standard |
| Limited capability | Strict |
| Read-only or ordinary reversible operation | Light |
| Unknown operation risk | Standard; clarify before external mutation |
| Service/deployment or destructive operation | Strict |
| Explicit project or user request | May raise the other floors |
| Repeated fixed-check failure in this session | Strict, latched |

Capability is a reviewed project choice, not a model-name ranking, model probe,
or model self-assessment. No configuration means unknown capability and Standard.
If a model/harness changes, do not carry a high-autonomy rating over without review;
use at least Standard until that review. V1 does not discover the running model.

Profiles change workflow guidance, not native permissions or mechanical Gate
requirements. Light reuses still-valid grounding and avoids a routine gate card
or a repeated six-part report for ordinary work. Standard retains entry/recovery
checks but reuses equivalent current evidence. Strict favors bounded actions,
fresh target evidence and independent postconditions. It does not mean additional
approval for already authorized work or more paperwork for its own sake.

Existing target/command/session binding, policy-integrity denials, evidence
semantics, one-time arms, existing verification obligations and Stop behavior are retained.
A fixed check's zero exit still proves only that the check ran successfully.
Neither profile selection nor successful inspection proves semantic safety.

## Configuration and explanation

The optional accepted project decision lives at
`.governance/decisions/acgm-policy.json`:

```json
{
  "schema": "acgm-workflow-policy-v1",
  "capability": "high-autonomy",
  "profile": "auto"
}
```

The schema accepts only these three fields. Capability is `high-autonomy`,
`general`, `limited` or `unknown`; profile is `auto`, `light`, `standard` or `strict`.
Use `general`/`unknown` unless a higher capability is actually established.
This decision belongs to the existing activation baseline. The agent may prepare
it when project policy configuration is authorized, explain the recommendation,
and use the existing reviewed activation workflow. No installer creates it by
default, no Hook writes it, and no model may edit/reactivate it to evade controls.
Changes, additions or removals of this policy after activation cause hard governance drift.
Malformed or symlinked present policy cannot silently fall back to Light.

The read-only explanation command is:

```sh
acgm-codex policy --project /exact/project --risk reversible --json
acgm-codex policy --project /exact/project --risk service --profile light --json
acgm-codex policy --project /exact/project --risk read-only --session EXACT_SESSION_ID --json
```

The service example still resolves to Strict. `--profile` raises only this
recommendation; it does not save a session preference or rewrite project policy.
Omitting `--session` omits session evidence; it is not proof of no escalation.
On an unactivated project the result is explicitly an inactive recommendation.
The command creates no configuration, ledger or HMAC key.

## When governance appears (2026-09-26 candidate)

The quiet-entry simplification changes visibility, not enforcement or the accepted
configuration schema. Ordinary task entry is no longer a request to recover the
whole project. The legacy resolver and capability mapping above remain available
for compatibility and explicit explanation; they are not a new default ceremony.
Removing that mapping or migrating existing project decisions is deferred.

| Trigger | Required behavior | Context shown |
|---|---|---|
| Healthy default or Light entry, no open obligations | Keep integrity checks and heartbeat | None |
| No project governance installed | Remain inactive; do not suggest bootstrap automatically | None |
| Explicit Standard/Strict or configured general/limited assistance | Honor accepted project assistance | Short profile guidance |
| Earlier verification obligation | Preserve it across tasks and sessions | Count and report command |
| Repeated correlated fixed-check failure | Retain latched incident guidance | Existing escalation notice |
| Broken/drifted policy | Keep existing fail-closed behavior | Repair notice |
| Covered destructive command | Keep denial, exact target binding, fixed check and one retry | Existing Gate output |
| Service/deployment or other semantic risk | Confirm target, authorization, recovery and postcondition | Existing truth-first skill |
| Compaction, handoff or concrete stale-state uncertainty | Recover relevant project facts | Existing session-grounding skill |
| Material project decision | Preserve rationale and unfinished questions | Existing decision-ledger skill |

Skills remain discoverable. Narrowing their descriptions reduces unnecessary
implicit selection; it does not hide their metadata or unload already-read text.
There is no dynamic plugin loader, classifier, new mode or persistent state.
Existing project AGENTS/Constitution requirements still apply. New stock AGENTS
text makes doctor/report conditional; this change does not rewrite installed
project files or reactivate their baselines.

A silent entry does not prove that all Hooks ran, classify future work as low
risk, or waive explicit project requirements. Detected destructive categories still get their Strict operation notice. Other service/remote/MCP
actions rely on truth-first semantic guidance and native permissions; this is
not universal mechanical risk detection. Do not run `policy` before ordinary
tools just to compensate for an absent startup message.

Guardian remains independent. Runtime checks and ledger I/O still cost time;
quiet model context is not zero runtime overhead. Cost/quality improvement needs
fresh model runs; deterministic tests alone cannot establish token savings or
prove implicit skill selection on real tasks.

## Advisory experiment withdrawn (2026-09-26)

The candidate deletion exception was tested and withdrawn before installation.
`enforcement` and `advisory_paths` are not supported configuration fields; the
original strict schema rejects them. No installed project needs migration.
The experiment added recovery checks but demonstrated no native execution benefit:
ACGM advice was followed by a Codex command-policy rejection. Evidence is retained
in EVIDENCE.md; passing fixture tests did not justify ongoing production complexity.

The retained change targets a measured source of ceremony: healthy task entry
and automatic full recovery. It does not replace denials with per-command warnings,
change native policy, or create a second permission system. A platform refusal is
an unexecuted request, not a reason to repeat ACGM arming or claim verification.

## Project records and policy integrity (2026-09-28)

Within the required decisions/snapshots directories, ordinary `.md` additions,
edits and removals are `record_changes`. They generate one concise reminder at
entry/recovery; ordinary tools remain quiet. The activation baseline is retained,
so later sessions can still identify changed records. No per-tool reminder or
new acknowledgement state is added. Review only relevant records; a changed ADR
is not approval, authorization or proof that the recorded fact is current.

Constitution, AGENTS, scope, non-Markdown files (including the workflow policy),
missing required directories, symlinks, special files and unreadable entries remain
hard boundaries. Do not put executable policy into Markdown to evade validation.
Cross-session obligations remain in the existing ledger and are not cleared by
editing records, changing sessions or choosing a quieter profile.

## Bounded automatic escalation

Two consecutive failed fixed checks for the same target/category in one session
raise workflow guidance to Strict. A matching successful fixed check between
failures resets that streak. Once the threshold has been reached, later success
does not lower it in that session. Temporary Strict operation floors do not latch.

Use existing `state-check-failed` / `obligation-check-failed` events and their
source references to bind project, session, activation, target and category.
Do not count normal command exits, unknown results, expected initial Gate denials,
permission denials or missing telemetry. A failed fixed inspection is a recovery
signal, not proof that a semantic postcondition failed or that a model is weak.

After a Gate check result the Hook emits a transition notice and records
`policy-escalated` in the existing ledger. Concurrent callbacks may duplicate the
notice but cannot lower the floor. Recovery/explanation can derive the floor from
the source events even if the result Hook was missed. Without a known session,
no session-specific claim is made. There is no automatic downgrade/reset command;
carry unresolved obligations into any handoff rather than using a new session as
a bypass. LOCAL/REMOTE conflicts and unknown authority require resolving the
ambiguity, not simply escalating and continuing.

There is no second state store, model API call, parser, dependency or production
module. Additional escalation scans occur on Gate check results and policy
explanation/recovery, not on every ordinary tool call. Existing governance
integrity checks remain; this phase does not introduce unsafe caching.

## Guardian and acceptance boundaries

Guardian keeps its own `.acgm/session-guardian.json`, thresholds, state and
handoff behavior. A workflow profile neither enables/disables it nor changes its
budget. Long-task requests may warrant a recommendation to enable it; duration is
not a risk classification. Handoff continues to preserve unresolved obligations.

Regression acceptance covers profile floors, all five existing destructive Gate
categories, drift/malformed policy, successful arm and Stop obligation behavior,
real fixed-check failures, session isolation, no downgrade after recovery,
unknown-result handling, read-only explanation and Guardian independence.
Existing package and full runtime release checks remain required.

This phase does not claim measured token savings, improved real-model success,
automated semantic drift detection, or installed Desktop acceptance. Compare task
completion time, model tokens/calls, local Hook time, false blocks and dangerous
misses in a separately scoped real-model trial before promoting stronger claims.
Keep the production increment under 200 physical lines for this phase; revisit
scope before exceeding that budget. Do not add a policy DSL, three Gate copies,
a model capability database or a new event store.

Native follow-up on Codex CLI `0.154.0-alpha.6.2` exercised 23 isolated
scenarios with 21 explicit acceptance assertions. All passed, including Light
destructive denial, two failed fixed checks, Strict on same-session resume, Light
in a new session, and independent Guardian lifecycle behavior. Responses were
local deterministic fixtures, not real-model behavior or token-efficiency trials.
