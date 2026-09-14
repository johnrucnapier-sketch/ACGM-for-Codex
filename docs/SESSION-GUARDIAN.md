# Optional Session Guardian — development prototype

This branch develops a small ACGM add-on, not a new governance system. It is not
part of the installed or published 0.3.0-rc.1 package. Existing Hooks, private
event ledger and Codex settings are unchanged. No 500K window has been applied.

## Findings and selection (2026-09-14)

Reviewed the owner's existing project handoff entrypoints, dated handoffs,
snapshot index, version archive index, decision index, a reverted ADR and a
decision claim. Their private contents are not copied into this public package.
The important patterns are: explicit workstream ownership; current-state index
separate from dated evidence; corrections that supersede earlier conclusions;
reverted solutions with still-valid reasoning; source/build/runtime separation;
pending obligations carried across topics; and a precise next-session read path.
The older root resume guide is historical, not a current state authority. A file
named resume or latest can itself be stale. Prefer evidence and provenance.

The supplied Session Guardian proposal is design input, not an execution contract.
Accepted: early closing, safe operation boundaries, explicit unknown data quality,
incremental monitoring, no automatic Git mutations, handoff with fresh readback.
Reduced: Codex only initially, one script and one skill, no provider framework,
daemon, database of our own, universal PROJECT_STATE, desktop UI or duplicate ledger.
Changed: no universal test/build/repair ritual at closing; no blanket prohibition
on rechecking old results; compaction is an event, not proof of memory corruption.

## Data-source research and limits

Official [app-server documentation](https://learn.chatgpt.com/docs/app-server)
exposes `thread/tokenUsage/updated` and a `contextCompaction` item lifecycle.
`thread/read` does not subscribe to a thread. Connecting an independent app-server
process is not evidence that it observes the desktop's active thread. A native
event-stream integration is a future path; this prototype does not pretend to
provide that subscription by resuming or taking over a user's thread.

Locally generated 0.154.0-alpha.6.2 app-server schemas distinguish `last` from
`total` token usage and expose `modelContextWindow`. Read-only inspection of the
active local session confirmed `session_meta`, `event_msg/token_count` with
`last_token_usage` and `model_context_window`, and `token_usage_record/usage`.
The latter advances more recently than some token-count events. The prototype
supports only this explicitly verified CLI version. Other versions report UNKNOWN
until their schema is independently checked. No internal schema stability claim.

The implemented fallback resolves only the explicit thread ID (or CODEX_THREAD_ID)
through SQLite in read-only mode, then verifies rollout metadata ID, cwd and CLI
version. An explicit rollout path bypasses the lookup, not identity validation.
There is no latest-file guessing. It tails at most approximately 4 MiB per poll
plus one bounded record, retaining only metrics. It handles partial JSONL writes,
rotation, truncation and large records. Huge or malformed records can invalidate a
sample; unknown is reported rather than inventing precision. It does not parse
compressed or arbitrary paginated history. Missing files/format changes degrade
to UNKNOWN. No transcript, source body, command text or metrics are persisted.

Context usage is the latest response total, never cumulative session spend;
cached input still occupies context. The value is an OFFICIAL_ESTIMATE, not an
exact real-time free-space meter. Stale (>300 s default), missing or future-dated
samples are UNKNOWN. The model's observed effective window is used, never its
advertised maximum. Observed compactions are counted only in the inspected tail;
zero is not proof of no earlier compaction, and manual/automatic causes are not
distinguished. Inode/path change resets the observation. A compaction followed
by fresh usage reports DEGRADED; absent fresh usage remains UNKNOWN with its
compaction count visible.

Official [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
separates model_context_window, model_auto_compact_token_limit and threshold scope.
Without a verified compaction limit, percentages refer to the observed window
only and cannot guarantee warning before automatic compaction. `--compact-limit`
may supply a verified **total-context** threshold; the smaller of that and the
observed window is the boundary. It is inappropriate for body_after_prefix scope.
The prototype never edits settings, promises zero compactions, or increases the
model capacity just by writing a larger number.

## Use from this checkout

```sh
sh bin/acgm-session status --project /exact/session/cwd --thread ACTUAL_THREAD_ID
sh bin/acgm-session watch --project /exact/session/cwd --thread ACTUAL_THREAD_ID
sh bin/acgm-session handoff --project /exact/git/root
sh bin/acgm-session resume --project /exact/git/root
```

`status` prints JSON; UNKNOWN exits 2. `watch` prints on state/reason transitions
only and ends with Ctrl-C. It is a foreground monitor, not a background service
or in-chat notification. It cannot force the assistant to follow closing advice.
Thresholds are remaining 35/20/10 percent, adjustable through flags. A natural
work boundary is preferable to filling every session to the threshold.

`handoff` and `resume` print fresh Git facts and instructions. They do not write a
handoff, run tests, declare an ADR accepted, alter governance, or create/close a
session. The `session-handoff` skill handles semantic drafting and successor
readback in the project's existing conventions. A prepared JSON record is a
DRAFT and a non-atomic observation; it cannot establish runtime or authorization.
Non-Git handoffs can use the skill, but this mechanical CLI requires a Git root.

Prioritization: protected scope/user corrections; in-flight work and obligations;
decisions with status and reasons; verified implementation/runtime state; next
action. Length follows the evidence needed for a safe continuation, not a fixed
token quota. The handoff points to ADRs, snapshots and historical archives instead
of repeatedly compressing their contents. Existing actual user authorization
persists; historical example commands do not create new authorization.

## Acceptance still needed before a release

Synthetic tests establish parsing and boundary behavior, not native delivery.
Live read-only status has been observed on the author's exact active session;
semantic successor readback, real threshold notification UX, broader CLI version
support and installation remain separate gates. Do not call this the full
proposal's MVP: no Claude adapter or automatic session switching is implemented.
Select a new release version and complete the existing manifest-bound release
and installation flow before distributing it as an installed ACGM upgrade.
