# Architecture and guarantee boundaries

ACGM for Codex is an adapter, not a textual port of the Claude Code plugin. It
retains the ACGM governance invariants while using Codex-native plugin, skill,
Hook, tool, trust, and data contracts.

## Runtime flow

1. A direct request to install and enable official ACGM in one exact project
   with recommended defaults authorizes one `standard-v1` quickstart plan. A
   bare repository URL does not authorize configuration changes.
2. Read-only planning binds the immutable source/tag, fixed plugin commands, a
   non-reversible identity for the normalized effective Codex profile target,
   exact Git root and identity, existing managed-file hashes, and every proposed
   byte into one digest.
3. Apply recomputes that digest, installs the exact Git marketplace package,
   provisions safe missing governance assets, activates the project, and checks
   local postconditions. Any mismatch stops the flow before the affected write.
4. Codex copies the selected immutable remote source into its plugin cache.
   After plugin installation or replacement, the desktop and app-server must be
   fully restarted before a normal task can prove the new plugin loaded.
5. The user reviews the exact Hook definitions through `/hooks`; untrusted
   definitions are skipped by Codex. A current client may offer one bulk trust
   action, which is safe only when the pending set contains exclusively this
   verified ACGM release. This platform-owned boundary cannot be self-approved
   by a plugin.
6. The first real ACGM Hook observed after trust records the current activation
   heartbeat atomically. No second artificial verification task is required.
7. Tool Hooks inspect only the fields required for a narrow rule, write
   enumerated results to `PLUGIN_DATA`, and discard the raw input.
8. `quickstart status` and `doctor` check package identity, project state, and
   whether a real Hook heartbeat was observed for the current version and
   activation without a later runtime error.

The workspace checkout and Codex's cache are deliberately different layers.
Public bootstrap verifies a clean exact release tag and `PACKAGE_MANIFEST.json`,
then uses the official Git marketplace CLI. It independently verifies the
resulting marketplace source/ref, plugin identity/version/enabled state, and
cached package bytes. A fresh install is add/add. The only automatic plugin
replacement is a digest-bound official `0.1.0-rc.2` through `0.1.0-rc.4` or
`0.2.0-rc.1` through `0.2.0-rc.3` upgrade after both the old
marketplace tag snapshot and sole installed cache match the verified old release;
its fixed sequence is marketplace remove, exact-ref marketplace add, and plugin
add. Every step is re-inspected. Because an already-open Codex task retains the
absolute Hook command from the version that started it, bootstrap keeps the
verified installed path executable throughout the transition and publishes a
byte-exact, fail-open two-file bridge for every known official pre-guard version,
including tasks already stale before the upgrade. Current-state
verification accepts one full target cache plus verified bridges from known old
official versions; a retained full old cache or altered bridge is still an
error. RC3 and later additionally publish the manifest-bound runtime to stable
`PLUGIN_DATA/runtime/acgm_codex.py`. Its install authorization digest binds the
hashed logical target, expected hash and size, observed preimage/state/hash, and
whether publication is needed. Only missing, exact, permission-drifted, or
digest-pinned known-official bytes can be atomically replaced under verified
user-owned, non-public-writable parents. Partial failure is reported without a
rollback claim. The old personal copy remains development-only; private Event
Ledger/HMAC data is never adopted, reset, or moved, and none of these checks
proves that Hooks were trusted or ran.

Codex CLI 0.144.5 also omits the `scope` field for a user-installed plugin.
Absence is not treated as user scope by default: it is accepted only when the
exact enabled plugin table exists in the already digest-bound effective
`CODEX_HOME/config.toml`. An explicit null, project/other scope, missing or
duplicate profile table, or non-exact table shape remains fail-closed.

Some Codex builds add one platform-owned
`.codex-marketplace-install.json` file beside the clean marketplace checkout;
Codex 0.144.5 does not. Either shape may retain a full `.git` directory. These
are not release payload bytes. Absence of the metadata is accepted only with an
otherwise empty Git status and the complete exact config, CLI identity,
HEAD/tag/origin, manifest, filesystem inventory, release-contract, and pinned
revision/hash chain. If the metadata exists, its strict JSON identity must match
the expected repository, ref, empty sparse-path set, and exact tag revision,
and it must be the checkout's sole untracked entry. An invalid present file is
always fail-closed. A
cache `.git` directory is accepted only as a real non-symlink directory whose
clean HEAD, exact tag, and origin all verify; a cache without `.git` remains
valid only through exact package bytes and equality with the verified
marketplace manifest. All other unlisted, ignored, generated, symlinked, or
special entries remain fail-closed.

## One-consent quickstart contract

`standard-v1` is a versioned set of exact governance bytes, not permission for
the Agent to invent policy. Quickstart creates a missing Constitution, scope,
adoption decision, and current snapshot, while preserving substantive
`AGENTS.md` and existing governance policy. It may replace only byte-identical
stock placeholders produced by the older `init` flow. Unknown content,
symlinks, non-regular managed paths, substantive active drift, legacy or
duplicate plugin state, and unverified source/scope/ref/version conflicts stop
automatic adoption. The verified official plugin upgrade above is a separate
install-layer exception. Version-only project adapter drift is another narrow
exception: when the recorded
baseline still matches, the approved plan may update the adapter version and
baseline without replacing project-owned policy or rotating its activation ID.
That project-adapter exception accepts only the explicit compatible
`0.1.0-rc.2` through `0.1.0-rc.4` or `0.2.0-rc.1` through
`0.2.0-rc.3` set and a strictly older semantic version; unknown and future states
are not downgraded. A healthy current-version manually activated project can
adopt only its missing preset decision/snapshot, preserve its activation ID, and
rebaseline to the exact authorized postimage.

ACGM performs no planned installation or project mutation during planning.
Codex CLI state probes are vendor-controlled and may still perform their own
startup housekeeping. Apply requires both the authorization flag and the
immediately preceding plan digest; it recomputes and compares the whole plan
immediately before every first mutation.
A changed root, Git identity, source/tag, install command, managed-file hash, or
proposed byte invalidates the original grant. The local
`.acgm/quickstart.json` receipt records progress for diagnosis and safe
replanning; it does not auto-resume, widen the authorization, or absorb private
Event Ledger data. Unknown receipts fail closed. Known receipt/state preimages,
the Git identity/index/worktree guard, and the exact governance postimage are
rechecked before and after activation so a concurrent change is not silently
absorbed into the baseline.

Quickstart creates managed directories under private random names and publishes
them with the supported platform's atomic no-replace directory rename. Files
are fully written under private names and published with no-overwrite links;
known replacements isolate and verify the current path entry before publishing
their postimage. All managed directories stay bound to no-follow directory file
descriptors, and every managed file/directory baseline is revalidated through
those descriptors before success. A late symlink or directory-entry swap
therefore returns partial recheck rather than a false success or an external
write. This protects path-based creators, replacers, and ordinary
save-by-rename editors. POSIX cannot make a portable content CAS against a
non-cooperating process that opened the old inode before replacement and writes
that detached descriptor afterward; ACGM does not claim that stronger
guarantee. These are point-in-time postcondition checks, not a claim that a
different process cannot mutate the project after the last observation.

An applied project can be locally `GOVERNED` while quickstart reports
`AWAITING_PLATFORM_HOOK_ACCEPTANCE`. That status means project provisioning and
activation succeeded but no trusted Hook heartbeat has yet proved automatic
runtime observation for the current activation. `COMPLETE` requires that
heartbeat.

A heartbeat followed by a runtime error produces
`HOOK_RUNTIME_REPAIR_REQUIRED`; damaged installation or ledger state produces
`LOCAL_RUNTIME_REPAIR_REQUIRED`. Only a healthy governed project that has not
yet observed its first current activation heartbeat reports
`AWAITING_PLATFORM_HOOK_ACCEPTANCE`.

## Project-root resolution

Explicit quickstart commands require the exact Git project root. Runtime Hooks
also validate their resolved Git root instead of trusting an inherited
workspace `cwd` blindly. For runtime Hook resolution only, an empty or unborn
parent repository that merely contains one valid direct child repository can
resolve to that child. If such a
container has multiple direct repositories, ACGM returns an ambiguous-workspace
result, writes no project state or heartbeat, and does not suggest initializing
the parent. Unique-child auto-selection is allowed only when every entry other
than `.git` is a verified direct child repository; any ordinary untracked or
ignored parent file disables implicit child selection. A committed parent
repository remains the project even when it
contains nested repositories.

## Governance layers

### Methodology

The platform-independent invariants remain:

- current code, configuration, and Git state are current facts;
- transcripts, summaries, memory, and handoffs are historical evidence;
- a human owns the Constitution; quickstart may provision only the exact
  versioned preset bytes the user authorized, and later Agent edits remain
  prohibited;
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

Each RC3-and-later Hook command addresses the stable `PLUGIN_DATA` runtime instead of a
versioned cache path. Codex's platform trust hash binds the fixed Hook command;
it does not independently hash future bytes at that path. The command therefore
embeds this release's exact runtime SHA-256 and size, opens the target with
no-follow and nonblocking flags, requires a regular file of that exact size,
reads once, verifies the digest, and executes those same in-memory bytes. A
runtime change changes every Hook definition and requires new platform trust.
Unset `PLUGIN_DATA`, missing or changed bytes, symlinks, FIFOs, and special files
return an empty successful Hook result and cannot turn a Stop failure into a
repeated model/Hook cycle. Pre-RC3 version bridges remain only as transition
recovery. This is lifecycle fail-open behavior, not a Lite governance mode.

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

Installed Hooks own ledger initialization, locator recording, and permission
hardening. Standalone `doctor` and `report` resolve an existing locator and read
the key and ledger without creating directories, calling `chmod`, or opening a
write-capable lock file. This separation is required for managed Codex sandboxes
that permit inspection of plugin data but intentionally deny metadata writes.
Read-only diagnostics report missing or insecure state; they do not silently
repair it.

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
- Hook trust is external Codex state. A package can provide definitions but
  cannot silently trust itself. One-consent quickstart removes redundant ACGM
  prompts, not Codex's `/hooks` review or the required full desktop restart
  after plugin changes. The platform trust hash binds the command definition;
  the embedded hash/size plus digest-bound publication/postflight bind runtime
  bytes. A bulk trust action must not absorb unrelated pending Hooks.
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

Automated fixtures exercise the one-consent plan/apply contract, conservative
asset adoption, ambiguous-root fail-closed behavior, and first-observed-Hook
heartbeat. They do not prove installed-platform behavior. The installed-plugin
E2E for the `0.2.0-rc.4` candidate—including the platform-owned `/hooks` review
flow and real Codex tool events in a completely new task—has not yet been
recorded as passed. No new automatic-Hook claim is promoted to verified platform
behavior until that checklist is completed.
