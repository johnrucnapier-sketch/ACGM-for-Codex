# Architecture and guarantee boundaries

ACGM for Codex is an adapter, not a textual port of the Claude Code plugin. It
retains the ACGM governance invariants while using Codex-native plugin, skill,
Hook, tool, trust, and data contracts.

## Runtime flow

1. The public tag-pinned Git marketplace exposes `acgm-codex` to Codex.
2. Codex copies the selected immutable remote source into its plugin cache.
3. A new discovery task discovers four skills and `hooks/hooks.json`.
4. The user reviews the Hook definitions through `/hooks`; untrusted definitions
   are skipped by Codex.
5. A second new verification task starts after trust. Its `SessionStart` resolves
   the actual Git/worktree root, evaluates project state,
   records a heartbeat, and injects a short grounding context.
6. Tool Hooks inspect only the fields required for a narrow rule, write enumerated
   results to `PLUGIN_DATA`, and discard the raw input.
7. `doctor` checks package identity, project state, and whether a real Hook
   heartbeat was observed for the current version and activation without a later
   runtime error.

The workspace checkout and Codex's cache are deliberately different layers.
Public bootstrap verifies a clean exact release tag and `PACKAGE_MANIFEST.json`,
then uses the official Git marketplace CLI. It independently verifies the
resulting marketplace source/ref, plugin identity/version/enabled state, and
cached package bytes. The old personal copy remains development-only; none of
these checks proves that Hooks were trusted or ran.

## Governance layers

### Methodology

The platform-independent invariants remain:

- current code, configuration, and Git state are current facts;
- transcripts, summaries, memory, and handoffs are historical evidence;
- a human owns the Constitution;
- decisions are append-only and explicitly superseded or withdrawn;
- evidence, action, and post-action verification are separate operations;
- authorization is never inferred from a completed evidence template;
- failed or interrupted actions still require current-state verification;
- activity is not automatically a successful interception.

### Skills

Skills make variable, judgment-heavy workflows repeatable. They can be selected
by Codex or explicitly invoked, but they are not an enforcement mechanism.

### Hooks

Hooks handle only mechanically testable subsets:

| Event | ACGM behavior |
|---|---|
| `SessionStart` | Health heartbeat, worktree grounding, state injection |
| `SubagentStart` | Minimal governance context for a subagent |
| `PreToolUse` | Constitution protection and narrow destructive-command gate |
| `PermissionRequest` | Record a sanitized boundary observation, return no allow/deny decision, and leave Codex's approval boundary intact |
| `PostToolUse` | Open a mechanical verification obligation after a consumed high-risk action; never infer check success from Bash response text |
| `PreCompact` | Persist only a source-minimized heartbeat before compaction |
| `Stop` | Continue once when a verification obligation remains open |

`UserPromptSubmit` is intentionally absent: the RC does not need to process raw
prompts. Transcript parsing is also absent because Codex documents transcript
format as unstable.

`PreCompact` does not create a project snapshot, persist compacted context, or
inject a replacement baseline. A later `SessionStart` with the compact reason
re-grounds from current project files. `PermissionRequest` records only the
enumerated `permission-boundary-observed` result and an opaque target when one can
be derived. It neither substitutes for user authorization nor contributes
evidence to the gate.

## Project state machine

- `INSTALLED_NOT_BOOTSTRAPPED`: plugin is visible but the project has no ACGM
  adapter marker.
- `PARTIALLY_GOVERNED`: initialization exists, but one or more human decisions or
  required assets are missing or still placeholders.
- `GOVERNED`: Constitution, Codex root rules, scope, decision, snapshot, and
  activation baseline are present and non-placeholder.
- `DRIFTED`: a previously activated baseline no longer matches required project
  components.
- `BROKEN`: adapter configuration or local state cannot be parsed or trusted.

File existence alone cannot produce `GOVERNED`. `CLAUDE.md` never substitutes for
Codex's `AGENTS.md`. Activation hashes every required file and every non-hidden
file in the decision and snapshot directories. A later addition, removal, or
content change in those directories is baseline drift, and empty or placeholder-
only decision/snapshot directories are never accepted as complete governance.

## High-risk evidence gate

The RC gate is intentionally narrower than the methodology:

1. A recognized destructive operation is denied on its first attempt.
2. The denial returns an opaque event id. In the same turn, Codex runs the exact
   `acgm-codex gate arm --event <id> --category <category>` command, adding
   `--target` only when the destructive command targeted another directory.
   `PreToolUse` binds this request to the denial, activation, turn, category, and
   HMAC target.
3. The CLI executes a category-specific fixed-argument check directly, without a
   shell: Git status/branch inspection or `/bin/ls`. It records
   `state-check-observed` and a short-lived arm only when the subprocess's actual
   exit code is zero. Codex Bash currently supplies PostTool Hooks with aggregated
   output text rather than an authenticated exit status, so ordinary Bash output
   is never accepted as gate evidence.
4. A matching retry consumes exactly one arm under the ledger's exclusive lock,
   then may proceed to Codex's own permission flow. The arm is evidence of
   process only; it is not user authorization.
5. The action's `PostToolUse` signal opens a matching post-action verification
   obligation even if the action may have failed, because failed or partial work
   still requires current-state verification.
6. `acgm-codex gate verify --event <obligation-id> --category <category>` repeats
   the fixed non-shell check against the same HMAC target. A zero exit closes the
   mechanical obligation. This is bookkeeping, not a semantic success claim:
   the output must still be interpreted before claiming the postcondition is
   verified. Otherwise `Stop` requests one continuation; the second stop records
   `unresolved` and exits to avoid a loop. A human `resolve` record linked to the
   obligation also closes that mechanical item.

This gate does not parse prose or an unstable transcript to manufacture a claim
that the four Truth-first fields were mechanically verified.

## Event Ledger

Storage precedence is:

1. `ACGM_CODEX_DATA_DIR` for controlled tests;
2. `PLUGIN_DATA` supplied to an installed plugin Hook;
3. the last official `PLUGIN_DATA` path recorded with mode `0600` under
   `~/.codex/acgm-codex/data-location.json`, so the standalone CLI shares the
   Hook ledger;
4. `~/.codex/plugins/data/acgm-codex` only before an installed Hook has recorded
   its official path.

The mode-`0600` locator necessarily contains the absolute official data-directory
path. It is local routing metadata, not a ledger event, and must not be confused
with the claim that Event Ledger records omit source and project paths.

Persistent records contain schema/version, opaque local identifiers, timestamps,
enumerated rule/action/status/outcome fields, and optional relationships between
events. A local secret salt creates project/session/turn/target identifiers. Raw paths,
commands, prompts, transcripts, model names, remotes, and credentials are never
written first and sanitized later; they are discarded before persistence.

## Explicit limitations

- Official Codex documentation says `PreToolUse` and `PostToolUse` do not yet
  intercept every `unified_exec` path or every tool.
- Multiple matching Hooks can run concurrently; ACGM cannot prevent another Hook
  from starting.
- A personal Hook can be disabled and is not an enterprise policy boundary.
- Hook trust is external Codex state. A package can provide the definition but
  cannot silently trust itself.
- The command recognizer deliberately covers only recognized spellings of five
  categories: hard Git reset, forced Git clean, forced branch deletion, forced
  push, and recursive forced delete. It is not a shell parser. Recognized risky
  commands with control operators, expansion, globbing, or ambiguous targets are
  denied but unarmable. Unrecognized aliases/wrappers, alternate spellings,
  indirect writes, and other tool paths can remain outside this guardrail.
- If the local HMAC key is lost while a ledger remains, ACGM refuses to create a
  silent replacement key. The old ledger and key must be preserved or moved
  aside together to begin an explicit new audit epoch.
- The RC has no automatic ledger rotation or retention policy. Hook lookups scan
  the project ledger linearly, so very large long-lived ledgers need an explicit,
  human-reviewed archive/epoch procedure before stable release claims.
- The RC supports macOS and Linux. A Windows claim requires a portable locking,
  launcher, command, and E2E implementation.
- Mechanism failure is surfaced as unhealthy; it does not lock every unrelated
  development action and pretend that fail-closed coverage is complete.

## RC acceptance status

The automated fixtures exercise these contracts, but the installed-plugin E2E
in a completely new task—including `/hooks` review/trust and real Codex tool
events—has not yet been recorded as passed. Until that checklist is completed,
this checkout remains `0.1.0-rc.3` and no automatic-Hook claim is promoted to
verified platform behavior.
