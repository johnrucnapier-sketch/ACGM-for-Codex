# Workflow profiles: bounded first stage

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
semantics, one-time arms, verification obligations and Stop behavior are unchanged.
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
Changes, additions or removals after activation cause ordinary governance drift.
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

At SessionStart/SubagentStart the Hook supplies an initial profile for grounding.
This is not classification of future work. The agent reapplies the risk floor
when the operation changes, retaining user-raised requirements for their requested
scope. Existing detected destructive categories also get a Strict operation notice.
Other service/remote/MCP actions rely on the skill's semantic guidance and native
permissions: there is no new general command classifier. A caller-provided
`--risk read-only` never bypasses the mechanical Gate. Do not run the explanation
command before every tool; resolve when entering a task or when relevant inputs
change. Clarify only ambiguity that changes the required action or lifecycle policy.

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
