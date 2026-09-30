# Changelog

## Documentation follow-up — 2026-09-30 (no runtime release)

- Verify the published 0.4.0-rc.2 candidate for team installation; keep its tag,
  runtime, Hooks, skills and installation policy unchanged.
- State the Astra-focused product scope and compare Claude Code 0.9.6-rc.3
  without importing a second logger, remote-tool registry or model classifier.
- Correct stale README publication status, skill count and core integrity-error
  behavior. See [team readiness](docs/TEAM-READINESS-20260930.md).

## 版本概览

以下摘要依据本仓库历史条目、Git 标签和开发交接资料整理。
“候选”不等于已经安装或通过真实用户验收；既有标签内容不会被本轮修改覆盖。

| 版本 / 阶段 | 主要解决的问题 |
|---|---|
| 0.4.0-rc.2（2026-09-28） | 修复旧项目升级后的只读锁死；提供受限诊断入口，保持风险拦截与原有基线 |
| 0.4.0-rc.1（2026-09-28） | 普通任务安静启动；项目记录变化改为按需提醒；保留策略与危险操作边界；验证当前 Codex 的 Guardian 生命周期 |
| 0.3.0-rc.1（2026-09-12） | 用决策记录保留长期项目的重要理由与未决问题；减少多仓库重复提醒 |
| 0.2.0-rc.4（2026-07-20） | 修复 Constitution 保护误伤普通读取和无关写入的问题 |
| 0.2.0-rc.3（2026-07-19） | 固定可信 Hook runtime 的位置与摘要，处理缓存清理和重启后的信任边界 |
| 0.2.0-rc.2（2026-07-19） | 修复真实插件升级、旧任务 Hook 与中断升级恢复路径 |
| 0.2.0-rc.1（2026-07-17） | 一次授权的安装、初始化和激活；用精确计划防止错误升级或覆盖项目资料 |
| 0.1.0-rc.4（2026-07-15） | 兼容平台暂未提供候选版本号的枚举结果，保留独立身份验证 |
| 0.1.0-rc.3（2026-07-15） | 根据真实 Codex 返回修正 marketplace / plugin 的验证协议 |
| 0.1.0-rc.2（2026-07-15） | 建立标签固定的公开安装入口、包校验和保守迁移边界 |
| 0.1.0-rc.1（未发布） | 建立独立 Codex 插件、项目健康状态、evidence gate、验证义务及本机账本 |


## 0.4.0-rc.2 — upgrade lockout hotfix (2026-09-28)

- Fix a real regression after upgrading an active 0.3.0-rc.1 project: version-only
  drift blocked even `pwd`, `git status`, and the recommended `doctor` command.
- Accept only known compatible adapter versions while still validating the
  schema, baseline, project policy and activation. Do not rewrite the project
  version, baseline, activation, records or obligations during normal work.
- Keep explicit quickstart version migration available when requested.
- Permit one literal current-plugin `doctor` invocation even when policy or
  ledger inspection fails. Bind its launcher/runtime bytes to the current
  release and restrict its flags and project target. Reject PATH lookups,
  substituted executables, shell chaining, redirection and extra commands.
- Preserve fail-closed behavior for unknown versions, substantive drift,
  corrupted state and protected operations. Add source and native first-command
  upgrade regressions; existing successful install checks did not cover this path.
- Pin the exact official 0.4.0-rc.1 predecessor for the normal upgrade flow.
  Updated Hook definitions require personal review again in Codex Settings.

Validation: 253 source tests and all package/skill contracts passed; native Codex
Harness passed 28 scenarios / 27 assertions, including the four new upgrade and
diagnostic scenarios. Read-only inspection of the affected project returns
GOVERNED without changing its original adapter or baseline.

## 0.4.0-rc.1 — lean workflow and project continuity (2026-09-28)

### 本阶段的目的与取舍

- 减少 Astra 普通短任务的例行治理负担，不把“每次重复检查”当作安全本身。
- 健康默认/Light 入口不再注入例行说明；恢复和 doctor 按实际不确定性触发。
- 决策/快照目录中的普通 Markdown 记录变化改为启动/恢复时的一条建议提醒；
  不自动批准记录、不改变已接受基线，也不要求只为更新项目笔记重新激活。
- Constitution、AGENTS、scope、实际策略文件、目录结构异常仍保留硬边界。
  未完成验证仍跨任务保留；没有减少现有危险操作 Gate。
- 撤回没有证明实际收益的删除放行例外；不新增全局 warning-only 开关。
- 从当前 Codex 0.158.0-alpha.2.1 原生临时会话采集用量格式，补充 reader
  回归和原生生命周期验收；未知版本继续拒绝，不更改 Guardian 阈值。
- 不把短任务小样本当作稳定 token/耗时收益或长期语义恢复已验收。

发行前验收：248 项源码测试；当前 CLI 的 24 个原生场景、22 条断言通过。
详见 [阶段验收与安装边界](docs/LEAN-WORKFLOW-ACCEPTANCE.md)。

### 此开发分支前序工作


- Add a thin Light/Standard/Strict workflow resolver, baseline-protected optional
  project choice and session-scoped fixed-check failure escalation. Preserve all
  mechanical Gate requirements and independent Guardian behavior.
- Reduce repeated grounding and routine gate-card guidance for ordinary work.
- Fail closed on broken/drifted policy and pre-tool runtime/integrity errors.
- Bind retry arms to the complete command, and inspect compound shell segments.
- Separate requests/results, preserve unknown outcomes, and reconcile native
  completions with the existing exact-session reader. Claimed verification no
  longer substitutes for the fixed check.
- Integrate the existing optional Guardian without changing thresholds or UX;
  fix nested request-state persistence and preserve full blocked prompt text.
- Share Hook/dashboard budget calculation; add regression and native fixture tests.
- Include Guardian runtime, dashboard and handoff assets in the development
  snapshot allowlist; verify the copied hash-bound Guardian loader.

### Release and upgrade

- Publish a new immutable `v0.4.0-rc.1` candidate; preserve all older tags.
- Verify the exact official `0.3.0-rc.1` predecessor and preserve private data
  during the existing digest-bound upgrade flow.
- Resolve CLI guidance from the current plugin, avoiding stale global wrappers.
- Desktop restart and personal Hook review remain separate from local installation.


## 0.3.0-rc.1 — 2026-09-12 release candidate

- Adapt the decision-ledger workflow from ACGM for Claude Code 0.9.2: preserve
  material open questions and unconfirmed claims, promote only on actual human
  rulings, and carry unfinished reasoning through grounding. This is advisory;
  it adds no transcript reader, automatic approval, database, or Stop loop.
- Add claim/ADR templates and include them in both package distribution paths.
- Report multi-repository ambiguity at session/subagent entry, including resume
  and compaction, instead of repeating the same warning on every tool and Stop.
  Ambiguous roots still select and modify no project.
- State that an observed startup Hook proves only that event, and route inactive
  project setup through the existing authorized bootstrap workflow.
- Pin the verified 0.2.0-rc.4 predecessor for existing installation and adapter
  upgrade paths. Preserve the state schema, preset bytes, Event Ledger, trust
  boundary, and exact runtime hash/size binding.
- Source and isolated installed-cache tests passed. Real desktop Hook trust and
  task activation remain separate acceptance stages; see docs/CLAUDE-092-ALIGNMENT.md.

## 0.2.0-rc.4 — 2026-07-20 candidate; target-bound Constitution protection

- Bind Constitution protection to a supported writer and its literal
  `CONSTITUTION.md` operand inside the same shell segment. RC3's global regular
  expressions could combine a read-only Constitution operand with an unrelated
  writer-looking token elsewhere in a compound command and deny the whole tool
  call.
- Replace the greedy `sed`/`perl` in-place heuristic with token-aware option
  handling. Hyphenated paths such as `session-grounding` and argument-bearing
  options such as Perl `-Ilib` no longer look like in-place edits.
- Preserve narrow write enforcement for shell redirections, read/write `<>`,
  target-directed copy/install, move/remove, `tee`, in-place `sed`/`perl`, Git
  restore/checkout, `dd of=`, export-case output, and common shell/env/command/
  sudo wrappers. Copying or streaming the Constitution to a backup remains
  read-only and is allowed.
- Add regression fixtures for the two real RC3 read-only false-positive shapes
  and for direction-aware read/write variants. A denied Hook event is not
  counted as a successful intervention merely because the Hook ran.
- Add the immutable public RC3 revision, manifest digest, and stable-runtime
  digest to the explicit official-upgrade allowlist, and add RC3 to the
  project-adapter compatibility set. Unknown, modified, or future predecessors
  remain fail-closed.

## 0.2.0-rc.3 — 2026-07-19 candidate; stable Hook runtime and restart-safe trust binding

- Move the installed Hook runtime out of Codex's prunable versioned plugin cache
  and into the plugin's stable `PLUGIN_DATA/runtime/acgm_codex.py` location.
  Bootstrap publishes only exact current bytes or replaces a digest-pinned known
  official old runtime through a private, fsynced, atomic file; unknown bytes,
  symlinks, unsafe parents, wrong ownership, and public-writable paths remain
  fail-closed. Failed writes, permission changes, fsync, and replacement leave no
  temporary executable behind.
- Preserve the Codex Hook trust boundary. Every released Hook definition embeds
  the exact runtime SHA-256 and size, opens the stable file without following
  links and without blocking, verifies that it is a regular file of that exact
  size, reads it once, checks the digest, and executes those same in-memory
  bytes. A runtime-byte change therefore also changes the trusted Hook command
  and requires a new platform review; the fixed command never silently executes
  a future mutable runtime.
- Fail open with `{}` when `PLUGIN_DATA` is unset or the stable runtime is
  missing, changed, symlinked, a FIFO/special file, or otherwise unavailable.
  This removes the missing-cache-path Stop Hook cycle without weakening cache,
  marketplace, package, or private-ledger verification.
- Require a full Codex desktop restart after plugin replacement before judging
  the new Hook set or `SessionStart`. An already-running app-server can retain a
  previous release's exact Hook command even after config and cache show the new
  version; a new task inside that old process is not installation acceptance.
- Add regression coverage for missing, exact, known-old, unrecognized, and
  symlinked runtimes; unsafe parents; atomic failure cleanup and zero-progress
  writes; unset `PLUGIN_DATA`; wrong-sized files; FIFO fail-open behavior; and
  the command-hash/runtime-byte authorization boundary.
- Accept an already-published exact RC3 fail-open bridge while planning a
  verified official predecessor upgrade. This closes the real recovery path in
  which an old task must stay executable while emergency full-cache copies are
  removed before the digest-bound upgrade.
- Pin repository text checkout bytes to LF across platforms so Hook/runtime
  digests and the package manifest do not depend on Git's Windows newline
  conversion. Windows runtime support remains intentionally fail-closed.
- Reject a symlinked stable runtime with `lstat` before opening it even on
  platforms that do not expose `O_NOFOLLOW`; supported POSIX platforms retain
  the additional no-follow open and descriptor-level regular-file checks.

## 0.2.0-rc.2 — 2026-07-19 candidate; installed-platform upgrade and Hook lifecycle repair

- Prevent version upgrades from stranding Hooks already loaded by an open Codex
  task. Bootstrap keeps the verified installed Hook path executable during every
  remove/add/add step and publishes exact two-file fail-open bridges for every
  known official pre-guard version, including older tasks that were already
  stale before this upgrade. The current cache inventory accepts
  only the full target release plus byte-exact bridges from known official old
  versions; retained full releases, extra files, symlinks, and tampered bridges
  remain fail-closed.
- Wrap every newly installed Hook definition with an inline missing-runtime
  guard. If a later plugin upgrade removes its versioned script before an old
  task exits, the Hook returns an empty successful result instead of turning a
  missing `Stop` executable into repeated model/Hook cycles. When the runtime is
  present, the wrapper preserves the original script arguments and behavior.
- Accept the clean marketplace checkout shape produced by Codex CLI `0.144.5`,
  which has no `.codex-marketplace-install.json`. Absence is allowed only when
  the unique config/CLI identity, clean HEAD/tag/origin, exact manifest and
  filesystem inventory, release contract, and pinned revision/hash all verify.
  If the optional platform metadata exists, its full identity remains strict;
  malformed, mismatched, extra, changing, symlinked, or dirty state fails closed.
- Parse marketplace and plugin-enabled evidence from one stable non-symlink
  `CODEX_HOME/config.toml` snapshot and recheck its path identity and hash at the
  end. Codex 0.144.5's omitted scope is accepted only through that exact bound
  user-profile table; explicit null/other scope or split-snapshot evidence is
  rejected. Revalidate marketplace Git, filesystem package, optional metadata,
  and official pins again at the terminal evidence boundary.
- Model Codex's real official-upgrade re-association: after marketplace
  replacement, the installed entry can still report the old version/cache while
  its source ref already points at the new marketplace. The active one-consent
  transaction continues to plugin add only when the old pinned cache identity,
  source, policy, scope, uniqueness, target marketplace, and original authorized
  upgrade origin all match exactly.
- Add digest-bound recovery for an interrupted pinned official transition. If
  the observed marketplace is already the current target, a new plan can resume
  plugin add; if it is a pinned earlier target such as RC1, a new plan rolls it
  forward through marketplace remove, exact RC2 add, and plugin add. Unknown or
  changed transitions remain blocked and private `PLUGIN_DATA`, Event Ledger,
  and HMAC material are never adopted, reset, or moved.
- Add regression fixtures for metadata-present/metadata-absent marketplace
  shapes, real re-association, transition tampering, new-digest recovery, and
  the fixed final cache/version postcondition. RC1 remains an immutable tagged
  candidate and is not retroactively moved.

## 0.2.0-rc.1 — 2026-07-17 tagged test candidate; pending installed-platform validation

- Add a one-consent quickstart that combines exact tag/manifest/plugin
  verification with project provisioning, activation, and local postcondition
  checks. A direct install-and-enable request for one exact project authorizes
  the fixed `standard-v1` plan without repeated ACGM confirmation prompts.
- Bind quickstart plan/apply to one digest covering source/ref, fixed install
  commands, normalized effective Codex profile target identity, exact Git root
  and identity, existing managed-file hashes, preset, and proposed bytes. Stale
  plans fail before configuration or project mutation.
- Allow only a unique, enabled, user-scope official `0.1.0-rc.2`,
  `0.1.0-rc.3`, or `0.1.0-rc.4` to upgrade automatically after its persisted
  source/ref, policy, exact tag snapshot, package bytes, and sole cache entry all
  verify. The digest binds the fixed marketplace-remove, exact-ref-add, and
  plugin-add sequence; unknown, personal, duplicate, foreign, and newer states
  remain fail-closed, and partial failure never claims rollback.
- Recognize Codex's real platform-owned marketplace metadata and full-Git
  plugin-cache shape without weakening package verification. The metadata file
  must bind the expected repository, ref, empty sparse-path set, and exact tag
  revision; a retained cache `.git` directory must independently verify its
  clean HEAD/tag/origin. Known RC2/RC3/RC4 upgrades are additionally pinned to
  their published commit and manifest identities.
- Provision missing Constitution, scope, adoption decision, and snapshot assets
  while preserving substantive project policy. Replace only byte-identical
  stock placeholders from the older `init` flow; unknown content, symlinks,
  non-regular managed paths, substantive active drift, and legacy/duplicate install state
  remain fail-closed.
- Allow a digest-bound version-only adapter upgrade when the recorded governance
  baseline still matches and the source state is an explicit compatible
  RC2/RC3/RC4 version, while preserving the activation identity. Unknown and
  newer adapter versions fail closed instead of being downgraded.
- Let a healthy current-version manually activated project adopt missing preset
  decision/snapshot assets without self-induced drift. Bind known receipt/state
  preimages, the Git identity/index/worktree guard, and the exact authorized
  governance postimage through activation so concurrent changes are not silently
  rebaselined; unknown receipts remain untouched and fail closed.
- Treat an unborn or empty workspace parent containing multiple direct Git
  repositories as ambiguous. Hooks write no project state or heartbeat there
  and no longer suggest initializing the wrong parent; a unique child can be
  selected only when the parent contains no ordinary untracked/ignored entries,
  and an established parent repository remains authoritative.
- Publish new directories from private names through platform atomic
  no-replace rename, publish complete private files with no-overwrite links,
  and replace known policy/adapter/receipt path entries through a final
  no-overwrite compare-and-swap. Keep no-follow directory descriptors open and
  revalidate all managed entries/baselines through them before success, so a
  late symlink or directory replacement yields partial recheck instead of an
  external write or false completion. Arbitrary writes through a descriptor
  opened on an old detached inode remain outside the portable guarantee.
- Return `PROJECT_RECHECK_REQUIRED` with explicit partial state when plugin
  installation succeeds but the target project changes before apply; do not let
  that boundary escape as a traceback.
- Let the first real trusted ACGM Hook record the activation heartbeat
  atomically. Codex's hash-bound `/hooks` review remains platform-owned; current
  clients can reduce a clean ACGM-only review set to one bulk trust action, but
  mixed or unknown Hooks must not be bulk-trusted. No second artificial
  verification task is needed.
- Keep native Windows runtime support explicitly blocked while Event Ledger
  locking still depends on POSIX `fcntl`.
- Make standalone `doctor` and `report` genuinely read-only when consuming an
  existing Hook ledger: they no longer create directories, repair modes, or open
  write-capable lock files merely to resolve the locator, HMAC key, and events.
  This preserves strict health checks inside managed Codex sandboxes where
  plugin data is readable but intentionally not writable.
- Distinguish post-heartbeat Hook failures as `HOOK_RUNTIME_REPAIR_REQUIRED` and
  local installation/ledger failures as `LOCAL_RUNTIME_REPAIR_REQUIRED` instead
  of misreporting either as first-time Hook acceptance.

## 0.1.0-rc.4 — 2026-07-15 tagged test candidate; pending public validation

- Accept a pre-install available entry whose version is `null` only when the
  complete persisted config, exact tag snapshot, manifest, package bytes, and
  release contract independently prove the candidate version. A wrong explicit
  version or missing runtime evidence remains blocked.

## 0.1.0-rc.3 — 2026-07-15 tagged test candidate; not promoted

- Make marketplace verification compatible with the observed Codex CLI
  `0.144.0-alpha.4` JSON contract without weakening fail-closed checks.
- When `marketplace list` omits the configured Git ref, verify the unique CLI
  identity together with the read-only `config.toml` entry and the exact clean,
  tag-pinned marketplace snapshot, release contract, manifest, and package bytes.
- Treat an empty pre-install `available` list as “not enumerated” only when that
  stronger evidence chain passes; explicit source/ref conflicts and any missing,
  dirty, mistagged, or byte-mismatched evidence remain blocked.
- Accept the installed plugin source kind actually reported by Codex (`git`) while
  retaining exact repository/ref, version, enabled-state, and cache-byte checks.
- Read the stored origin without Git URL rewrites and bind the working manifest
  and inventory directly to the release tag tree, so index flags cannot disguise
  untagged package bytes as a clean release checkout.
- Public exact-tag testing passed the stronger marketplace evidence chain but
  found that the real CLI can enumerate the uninstalled plugin with
  `version: null`. Verification stopped before plugin add, so RC3 was not
  promoted to a GitHub Release or accepted runtime.

## 0.1.0-rc.2 — 2026-07-15 tagged test candidate; not promoted

- Add a root Agent installation bridge and bilingual public install contract.
- Replace the public personal-copy flow with a tag-pinned Git marketplace and a
  read-only preflight plus explicitly authorized bootstrap.
- Verify clean tag/HEAD, release manifest bytes, exact marketplace source/ref,
  plugin identity/version/enabled state, and an exact cache file inventory and
  package bytes.
- Fail closed when the configured marketplace disappears or exposes a missing,
  duplicate, wrong-version, or wrong-source available plugin.
- Add macOS/Linux CI plus a Windows fail-closed contract job.
- Fail closed for legacy `acgm-codex@personal`, duplicates, unknown sources,
  scopes, and versions; emit a non-executable migration plan without touching
  private Event Ledger data.
- Separate download/configuration, install/enablement, Hook trust, fresh-task
  heartbeat, and project bootstrap claims. Windows remains blocked because the
  runtime still requires POSIX `fcntl`.
- Public exact-tag testing found that the bootstrap fixtures assumed fields the
  real CLI did not enumerate. Marketplace add itself succeeded and fail-closed
  verification stopped before plugin add; RC2 was therefore not promoted to a
  GitHub Release or accepted runtime.

## 0.1.0-rc.1 — unreleased

- Create the independent `acgm-codex` plugin identity and personal install flow.
- Add Codex-native lifecycle Hooks, five-state project health, Hook heartbeat,
  Truth-first evidence gate, verification obligations, and Event Ledger.
- Bind gate operations to opaque denial/obligation events and HMAC targets; run
  fixed non-shell checks instead of trusting Bash response text, and consume a
  one-time arm atomically.
- Add governance bootstrap, session grounding, truth-first, and activity report
  skills.
- Add package, runtime, privacy, and installer test coverage plus a manual Codex
  E2E checklist. The real new-task checklist is not yet recorded as passed.

The next candidate must not be promoted until the current Codex desktop/CLI
quickstart and Hook E2E pass in a clean task. Automated fixtures are not a
substitute for the one real `/hooks` trust boundary and subsequent tool event.
