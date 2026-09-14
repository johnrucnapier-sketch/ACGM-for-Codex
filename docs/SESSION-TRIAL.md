# ACGM Session Guardian — local trial

This optional module is developed in the ACGM repository and packaged separately
as `acgm-session-guardian@personal`, version `0.1.0-local.1`. It does not replace
installed ACGM 0.3.0-rc.1 or modify its seven trusted Hook definitions. Do not push,
tag or publish this trial until the owner completes the small-project trial.

## Explicit project opt-in

Installation alone changes no model window and enables no project gate. For an
exact Git root selected by the owner, back up the existing project configuration
and policy before merging these top-level `.codex/config.toml` settings:

```toml
model_context_window = 500000
model_auto_compact_token_limit = 450000
model_auto_compact_token_limit_scope = "total"
```

Preserve other settings. Do not overwrite an existing config, change the model,
activate globally or enable the owner's large project. Project trust and an
actual new task must establish effective settings; writing a number does not
increase a model's supported capacity. This trial was checked against local
Codex 0.154.0-alpha.6.2 and its Astra model metadata, not arbitrary models.

Create `.acgm/session-guardian.json` only in the selected project:

```json
{"schema":"acgm-session-policy-v1","enabled":true,"raw_window":500000,"compact_limit":450000,"handoff_reserve":40000,"reaction_margin":20000}
```

500K is the raw configured window. The verified 95% effective-window calculation
produces 475K. The total-context compaction ceiling is 450K. Defaults are
configurable, but the effective setting and actual observed window must agree.
If they differ, the Hook uses the smaller estimated boundary and reports the
mismatch rather than treating 500K as verified.

## Three stages and a last-resort stop

| Stage | Default observed remaining | Action |
| --- | --- | --- |
| Caution | <=35% | Finish normal work, append yellow warning; avoid large new work. |
| Closing | <=20% | Finish normal work, append orange recommendation to hand off. |
| Confirmation | <=10%, OR within 60K of compaction, whichever comes first | Reject new work until user chooses handoff or one short continuation. |

With the defaults, the confirmation gate starts at about 390K used, or 17.9%
remaining effective context. This intentionally precedes 10%: 40K is reserved
for handoff plus 20K for reaction and measurement lag. At 410K used, even an
explicit continuation is refused so the 40K handoff reserve remains.

Six Hook events are used, based on the current official
[Hook contract](https://learn.chatgpt.com/docs/hooks):

- SessionStart: introduce the enabled project policy.
- UserPromptSubmit: inject footer advice or block a new request. Only a real
  user prompt `ACGM 交接` grants a handoff turn; `ACGM 继续一次` plus the request
  grants one short turn while above the handoff reserve. Grants expire on the
  next user prompt and never arise from tool output.
- PreToolUse: deny further ordinary tool calls at the confirmation gate. It
  does not kill an already-running command. Handoff turns permit necessary tools;
  the skill and user scope, not a semantic tool classifier, restrict their use.
- PostToolUse: inject a reminder when the stage changes.
- Stop: show a UI warning at the end, without forcing another model generation.
  Colored emoji are used because Markdown text color is not portable. Model
  compliance determines exact footer placement; the UI warning is a fallback.
- PreCompact: `continue:false` stops automatic compaction before it runs.
  Explicit manual compaction remains available as a recovery choice.

Measurements come from a bounded read of the exact session transcript, not
cumulative account usage. The internal format is version-specific. Latest usage
is only a lower bound after further input/output growth. The CLI status command
marks old samples unknown; Hooks retain the latest count across idle periods
and re-read it at each lifecycle event. Malformed invalidated observations block
new operations. A brand-new session with no usage permits its first request.
Pending prompt characters add an estimate, not exact tokenization; attachments,
large tool output or a long generation can jump a threshold.

The buffer is not a guarantee that every handoff fits. Save the minimum useful
handoff first, then add details. If automatic compaction is stopped too late to
write anything else, retain the old task and recover from saved files and
explicitly selected old records in a new task. Do not retry indefinitely. No
claim of lossless summarization, full Hook coverage or automatic archival.

## Build, trust and acceptance

`python3 scripts/build_session_trial.py <staging>/acgm-session-guardian` creates
one standalone runtime from the reader and policy; Hook commands bind its exact
SHA-256 and length. Use the Plugin Creator scaffold and personal marketplace
helper, then `codex plugin add acgm-session-guardian@personal --json` for local
installation. The official validator must pass before installation. Changed
Hook/runtime bytes require a new cachebuster and the user's fresh Hook trust.

Fully quit and reopen Codex after installation. In a normal new task the user
reviews the six definitions using `/hooks`; the agent must not self-trust them.
Verify installed bytes, enabled state, effective context and real Hook events
separately. Synthetic subprocess tests do not prove native engine delivery.
Small-project acceptance should observe end-of-answer warnings, denied new work,
explicit handoff, persisted files, the copyable successor prompt and successor
readback. Do not inflate a real project's context just to hit the limits; use
isolated fixtures for mechanical boundaries and ordinary trial work for UX.

## Rollback

Set the selected project's policy `enabled` to false to disable all six actions.
Restore only the changed context keys from that project's preimage backup;
preserve unrelated later edits. Remove the companion plugin with
`codex plugin remove acgm-session-guardian@personal --json`, then restart Codex.
Keep handoff files and private plugin state for diagnosis; do not delete user
records. Existing ACGM remains installed. If necessary compare against the
private installation backup, but never blindly restore an old whole global
config over unrelated changes. No automatic Git commit or remote upload occurs.

## Live local panel

Run `python3 scripts/session_dashboard.py --project /exact/project` from this
checkout and open the printed loopback URL in the Codex browser pane. It refreshes
every three seconds without another model request. It displays up to 20 recent
unarchived main tasks for that exact root, excluding subagents/review agents.
It does not infer which task is foreground; each card names its task. New tasks
in the same exact folder appear automatically. Other worktrees are separate.

Green/yellow/orange/red follow the Hook budgets, including the dynamic 60K
buffer. Missing or stale observations are gray, and the last known count is
labeled as such. The browser receives only bounded titles, IDs and metrics; no
transcript body, prompt, commands or credentials. The server binds 127.0.0.1,
requires its random URL path and exact Host, emits no CORS headers or request
logs, and makes no external requests. It performs no project writes.

This is a checkout-hosted preview, not an embedded native desktop status-line
extension, and it does not alter trusted Hook bytes. The process must remain
running; Ctrl-C stops it. There is no login-item/daemon or automatic restart.
A new run prints a new URL. Live Hook coverage and a new-task effective 500K
window remain separate acceptance steps from panel rendering.
