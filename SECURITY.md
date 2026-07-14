# Security and policy boundary

ACGM for Codex is a governance and drift-control plugin, not a security sandbox.
Codex documents personal `PreToolUse` Hooks as guardrails with incomplete tool
coverage, and users can disable personal plugins or decline Hook trust. Keep
Codex's sandbox, approvals, repository protections, credential controls, backups,
and human review in place.

The destructive-command recognizer covers only narrow spellings of hard reset,
forced clean, forced branch deletion, forced push, and recursive forced delete.
It is not a shell parser and does not claim coverage for aliases, wrappers,
compound commands, indirect writes, ambiguous targets, or every Codex tool path.
`PermissionRequest` stores only a sanitized boundary observation and never
approves or denies on the user's behalf. A gate arm is process evidence, not
authorization, and a matching post-action check closes only a mechanical
obligation until its output is interpreted.

The runtime does not trust aggregated Bash `PostToolUse.tool_response` text as an
exit-status signal. Gate checks use fixed argument vectors without a shell and
change state only after the subprocess returns zero. A gate arm is bound to one
denial and target, then consumed under an exclusive ledger lock at most once.

Event Ledger records omit raw project paths, but the mode-`0600` data locator at
`~/.codex/acgm-codex/data-location.json` necessarily stores the official
`PLUGIN_DATA` directory path so standalone CLI commands can find the Hook ledger.
Protect that locator and the mode-`0600` HMAC key as local metadata. If a ledger
survives without its key, the runtime refuses silent replacement; preserve or
restore them together, or move both aside deliberately to begin a new audit
epoch.

`export-case` is no-clobber and refuses outputs inside project governance state
or runtime data. It remains a local preview and still requires line-by-line human
review before any external sharing.

If a defect lets a supported Hook path bypass an advertised narrow rule, causes
raw source or sensitive input to be persisted, or makes `doctor` report healthy
after a runtime failure, treat it as a security-relevant bug. Preserve a minimal
local reproduction without real credentials and use GitHub's private
"Report a vulnerability" flow for this repository before publishing exploit
details. Do not put security-sensitive details in a public issue.

Never submit tokens, cookies, OAuth material, private transcripts, proprietary
source, or identifying local paths in a report.
