# Claim maturity register

This file prevents implementation activity from silently becoming a product
claim. Promotion requires evidence at the level stated below.

**Current candidate status:** RC3's exact-tag local upgrade, full desktop
restart, user trust review, genuine new-task SessionStart heartbeat, and strict
doctor pass are now observed on macOS with Codex CLI 0.145.0-alpha.18. That
trial also exposed two read-only Constitution false positives: RC3 combined a
global target match with an unrelated greedy writer match elsewhere in a
compound command. The `0.2.0-rc.4` candidate binds a supported writer and its
literal Constitution target within the same tokenized shell segment and adds
direction-aware read/write fixtures. RC4 has automated coverage, but its own
exact-tag install, restart, platform trust review, and genuine new-task
acceptance remain pending. Broader automatic-installation and automatic-Hook
claims therefore remain unpromoted.

| Claim | Current maturity | Required next evidence |
|---|---|---|
| The candidate package has a valid Codex manifest and installable skill inventory | Candidate automated release contract; installed-platform discovery still pending | Confirm candidate skill discovery in a completely new task |
| One direct install request can drive exact install, `standard-v1` provisioning, activation, and local verification | Designed / automated fixture | Run exact-tag quickstart against a disposable project with real Codex plugin state |
| Quickstart authorization is digest-bound and preserves unknown policy | Automated fixture | Exercise stale-plan and existing-policy cases against the installed candidate and inspect every write |
| Ambiguous multi-repository containers are not initialized or given a project heartbeat | Automated fixture | Observe fail-closed behavior in a real Codex task opened at a disposable multi-repo parent |
| Project state does not equate installation with governance | Automated contract | Runtime lifecycle tests and disposable-repo E2E |
| The first trusted ACGM Hook can establish the current activation heartbeat without a second artificial task | Designed / automated fixture | Review the installed candidate definitions, use bulk trust only for an ACGM-only pending set, run one real tool event, and obtain strict completion |
| Session startup injects current grounding | RC3 installed-platform heartbeat and strict pass on one macOS/Codex build | Repeat against RC4 and additional supported environments |
| Constitution writes are intercepted | RC4 automated target-bound fixture; RC3 real read-only false positives | Obtain a real write denial and read-only non-denial in a disposable RC4-governed repo |
| Narrow destructive operations require a target-bound fixed current-state gate | Designed / automated fixture | Real Bash path: deny, fixed check, atomic arm consumption, retry, verify |
| Post-action obligations prevent a quiet first stop | Designed / automated fixture | Real `PostToolUse` and bounded `Stop` continuation |
| The Event Ledger is source-minimized | Automated contract | Search the real plugin data directory after E2E |
| Native Windows runtime is supported | Blocked | Replace POSIX `fcntl` and pass native Windows install/runtime E2E |
| ACGM reduces long-horizon drift in general | Predictive | Repeated external project trials with reviewed controls |

## 0.2.0-rc.4 candidate evidence

- A fully restarted, user-trusted RC3 installation recorded a genuine
  SessionStart heartbeat and passed strict doctor with a healthy ledger. This
  proves the stable runtime lifecycle for that local build, not general product
  effectiveness.
- The same live audit produced a read-only denial, and an independent compound
  read command reproduced it without changing the protected file. RC3's Bash
  matcher first searched the entire command for `CONSTITUTION.md`, then applied
  a second entire-command writer regex. Its greedy `sed` in-place expression
  crossed shell segments and matched letters inside a hyphenated path.
- RC4 tokenizes control-separated shell segments and requires the protected
  operand to be a target of a supported writer in that same segment. Fixtures
  distinguish copy/stream/read directions from overwrite/move/in-place/write
  directions and cover common shell, environment, command, and sudo wrappers.
- The RC3 predecessor is pinned by immutable revision, package-manifest digest,
  and stable-runtime digest. Upgrade planning still binds the exact source,
  installed cache, stable-runtime preimage, plan digest, and postflight bytes;
  unknown or changed predecessors remain non-executable.
- RC4 exact-tag release checks and installed-platform acceptance remain gates.

## 0.2.0-rc.3 candidate evidence

- A real RC2 installation showed exact plugin config/cache state and a healthy
  Event Ledger while strict doctor still reported `hook observed: no`. The
  running Codex app-server predated the install. A genuine new `codex exec`
  process—not a manually invoked Hook—then attempted the retained RC1 absolute
  Hook path after Codex pruned it, reproducing the missing-script failure shown
  across the user's stuck tasks. This is evidence of stale process lifecycle and
  cache-path coupling, not project drift or Hermes runtime failure.
- Hook contract fixtures verify that every RC3 command embeds the exact runtime
  size and SHA-256, reads a regular stable file once with no-follow/nonblocking
  flags, executes only those same verified bytes, and returns `{}` for unset
  `PLUGIN_DATA`, missing/changed/wrong-size/symlink/FIFO targets. Changing
  runtime bytes without changing the trusted command cannot execute them.
- Bootstrap fixtures cover missing, exact/idempotent, permission-drifted,
  digest-pinned known-old, unrecognized, and symlinked stable runtimes; unsafe
  or writable parents; zero-progress writes; injected write/fchmod/fsync/replace
  failure cleanup; and a FIFO race during publisher inspection. Unknown runtime
  bytes and dirty cache entries remain fail-closed.
- The install authorization plan binds the stable runtime logical-path hash,
  expected hash/size, observed state/hash/size, replaceability, and publication
  requirement. A changed known preimage after dry-run makes the old digest
  stale; an unrecognized preimage blocks without replacement; exact state is
  idempotent with a stable digest.
- The Codex platform trust hash is claimed only for the fixed Hook command. The
  embedded hash/size and digest-bound official publisher/postflight are the
  separate evidence binding runtime bytes. RC3 exact-tag installation, full
  desktop restart, user trust review, genuine SessionStart heartbeat, and
  strict doctor pass subsequently succeeded in one local macOS trial. The
  trial's Constitution false positives prevented promotion of the matcher as
  correct and led to RC4.

## 0.2.0-rc.2 candidate evidence

- An isolated disposable Codex CLI `0.144.5` profile verified that exact
  marketplace add and plugin add produce clean tag-pinned Git checkouts without
  `.codex-marketplace-install.json`; final plugin identity, enabled state,
  version, source ref, and cache bytes were otherwise exact. No real user
  profile or private ledger was read or modified by that probe.
- The real RC4-to-RC1 exact-tag run verified source, manifest, old official
  marketplace/cache, and the digest-bound remove/add/add plan. After successful
  marketplace replacement it stopped before plugin add and before project
  writes when RC1 did not recognize Codex's re-associated old-version entry.
  The private data directory, HMAC key, Event Ledger, and locator retained their
  inode and permission identities; ledger growth was append-only Hook activity.
- RC2 fixtures accept metadata absence only with the complete exact Git/config/
  CLI/package/release chain, keep invalid present metadata fail-closed, model
  the observed re-association, bind it to the originally authorized old cache,
  and reject changed ref or cache bytes before plugin add.
- Cross-process recovery fixtures require a new plan digest. A pinned prior
  target is rolled forward through remove/add/add; an exact current target may
  resume plugin add. Unknown, duplicate, foreign, wrong-scope/policy/source,
  unpinned, or tampered transition states remain non-executable.
- Hook command fixtures execute every released definition against a missing
  versioned runtime and verify a zero exit with an empty result. Upgrade
  fixtures execute old-path Stop Hooks after RC2 replacement, verify the exact
  complete known-version bridge inventory (including RC4 when RC1 is currently
  installed), recreate the bridges after an injected plugin-add failure deletes
  the old cache, and reject a modified bridge.
- RC2 exact-tag installed-platform E2E, final full-RC2-plus-verified-bridge cache verification,
  and the next-task Hook trust/heartbeat proof remain promotion gates.

## 0.2.0-rc.1 candidate evidence

- Targeted automated fixtures in `tests/test_runtime.py` exercise stable
  quickstart planning without ACGM-planned mutation, explicit authorization,
  stale-digest rejection,
  `standard-v1` asset creation, preservation of substantive `AGENTS.md`,
  byte-identical stock-placeholder replacement, idempotent activation,
  ambiguous-root fail-closed behavior even with residual inactive adapter state,
  explicit compatible project-adapter upgrades, healthy manual activation
  adoption, receipt/state/Git/postimage race rejection, runtime-repair status,
  and completion after a simulated Hook dispatch.
- Codex CLI state probes used during planning remain vendor-controlled and may
  perform their own startup housekeeping; the no-mutation claim applies to
  ACGM's planned install and project writes, not undocumented vendor behavior.
- Boundary fixtures inject concurrent edits at the final policy/state/receipt
  path-publication point, confirm prepared-file/no-overwrite CAS preserves those
  path-based bytes, reject concurrent directory publication and late managed
  symlink replacement through anchored no-follow descriptor checks, reject an
  unborn parent with ordinary untracked/ignored content, and turn a post-install
  project disappearance into explicit partial `PROJECT_RECHECK_REQUIRED` state.
- Targeted fixtures in `tests/test_quickstart.py` exercise the combined
  install-plus-project plan, the single authorization boundary, external
  install ordering, and stale-digest rejection before install mutation. They
  also bind the effective Codex profile target and starting official
  version/ref, and reject either change before the first Codex configuration
  mutation.
- Bootstrap fixtures allow only verified official RC2/RC3/RC4 upgrades, require
  the old marketplace tag snapshot and installed cache to match, verify the
  real Codex marketplace-metadata and full-Git-cache shapes, pin each known old
  release's commit/manifest identity, enforce the fixed remove/add/add sequence,
  reject full old-and-new cache coexistence while accepting only the exact
  lifecycle bridge shape, and keep
  unknown, personal, duplicate, foreign-scope/source/ref, tampered, and newer
  installs fail-closed. Injected command/postcondition failures are reported as
  partial state without a rollback claim.
- Runtime fixtures show the first observed governed Hook creates one
  activation heartbeat atomically. They do not prove that Codex displayed,
  accepted, or persisted the candidate's real `/hooks` trust hash.
- A tag and passing fixture suite do not prove that the candidate is installed
  on another machine, that the current Codex platform accepted and ran its
  Hooks, or that native Windows runtime works. The manual checklist remains the
  promotion boundary.

## RC2 public-bootstrap finding

On 2026-07-15, a fresh isolated `HOME`/`CODEX_HOME` cloned public tag
`v0.1.0-rc.2` at commit `4deb6d1` and ran against Codex CLI
`0.144.0-alpha.4`. Source preflight and dry-run passed. The exact marketplace-add
command returned zero, after which bootstrap stopped at
`MARKETPLACE_ADDED_BUT_POSTCONDITION_UNVERIFIED` rather than claiming success.

The real CLI omitted `ref` from `marketplace list --json`, returned an empty
pre-install `available` array, and reported an installed Git plugin with source
kind `git` rather than the fixture's assumed `url`. The exact ref was still
present in read-only `config.toml` evidence and the clean marketplace snapshot;
an explicitly addressed plugin add succeeded in the disposable profile. This was
an RC2 release-tool schema mismatch and false conflict, not a Hook failure or
damaged installation. Hook trust, heartbeat, and project bootstrap were not
reached, and RC2 was not promoted to a GitHub Release.

## RC3 public-bootstrap finding

On 2026-07-15, a second fresh isolated profile cloned public tag
`v0.1.0-rc.3` at commit `244a0e4`. Source preflight and dry-run passed, and the
marketplace-add command returned zero. The new persisted-config plus exact-tag
snapshot evidence chain also passed completely. In this run, however, the real
CLI enumerated the uninstalled plugin with the exact ID, repository, ref, and
policy but `version: null`. RC3 conservatively treated that explicit null placeholder as a
conflict and stopped at `MARKETPLACE_ADDED_BUT_POSTCONDITION_UNVERIFIED` before
plugin add. This was another pre-install CLI-schema compatibility finding, not a
Hook or package-integrity failure. RC4 accepts a null available version only when
the complete independent runtime evidence chain proves the exact candidate.

## Historical local evidence recorded for RC4

- RC4 automated fixtures cover fresh install, dry-run, explicit authorization,
  idempotence, legacy personal and duplicate conflicts, command failure/partial
  state, exact tag/manifest verification, exact cache inventory/byte
  verification, missing marketplace, invalid available plugin state, the
  observed omitted-ref/empty-available/explicit-null-version/Git-source CLI shapes,
  tampered persisted ref/snapshot evidence, and Windows fail-closed behavior.
- Release validation passed on Python 3.10 and the current Python after the
  final package manifest was regenerated (77 tests on each interpreter).
- RC1 historical personal install: `acgm-codex@personal` version `0.1.0-rc.1`
  was registered and enabled locally. RC4 treats it as a migration conflict.
- A new trusted task recorded an RC4 `session-start` heartbeat for the current
  governed activation. A following `PreToolUse` denial targeted a read-only
  Constitution inspection and was a false positive, not evidence of a correctly
  prevented write.
- Not yet evidenced: complete new-task skill discovery, strict doctor pass in
  the managed sandbox, correct real write interception, bounded `Stop`,
  compaction, or exhaustive real `PLUGIN_DATA` privacy inspection.

## Rejected inferences

- A successful quickstart fixture is not proof that the public candidate was
  downloaded, installed, trusted, or exercised by the current Codex platform.
- `AWAITING_PLATFORM_HOOK_ACCEPTANCE` means local provisioning succeeded; it is
  neither a failed project setup nor proof that automatic Hooks ran.
- A first-observed-Hook unit fixture does not approve Codex's hash-bound
  `/hooks` trust on the user's behalf.
- Path-entry CAS fixtures do not prove coordination with a non-cooperating
  writer that keeps the old inode open and writes its detached descriptor after
  replacement; POSIX provides no portable content CAS for that case.
- A Hook event count is not a prevented incident count.
- A skill invocation is not proof that the workflow was followed.
- A denied operation is not automatically a correct denial.
- A gate arm is not user authorization.
- A fixed check event proves the runtime's non-shell subprocess exited zero, not
  that its human-meaningful postcondition was satisfied.
- A mechanical obligation closure is not semantic verification of the action.
- A `permission-boundary-observed` event is not an ACGM approval, denial, or
  authorization; the `PermissionRequest` callback deliberately returns no
  decision.
- A `PreCompact` heartbeat is not a governance snapshot or preserved context.
- Installing the plugin is not proof that its Hooks were trusted or ran.
- Codex plugin availability on Windows is not evidence that this POSIX-locking
  runtime installs or runs on native Windows.
- A successful Git marketplace add or matching cache is not a trusted Hook,
  fresh-task heartbeat, or bootstrapped project.
- Claude Code V3 test results do not validate the Codex adapter.
- A single incident or arbitrary age threshold cannot create a universal hard
  governance rule.

## 0.3.0-rc.1 source validation — 2026-09-12

- Reference source: Claude product 0.9.2 at `c2ca0a2`; its 68 tests passed.
  These results are not Codex validation.
- Codex baseline passed 178 tests; the candidate passed the release checker,
  including all five skill validators, plugin contract, byte manifest, and
  180 regression tests on macOS / Python 3.14.5. A final targeted run passed
  23 tests, including two new checks for draft/ADR activation boundaries and
  RC4 upgrade preservation, plus package/release-tool checks.
- Ambiguous-root fixtures verify entry warnings, quiet tool/Stop callbacks, and
  no automatic project selection or data/governance creation.
- The decision-ledger skill is advisory. Agent drafting accuracy, actual human
  confirmation, installed skill discovery and real platform E2E remain unverified.
- No new source version has been published or installed. Existing private data
  and user-project governance were not migrated.

## Installation validation — 2026-09-12

- Full source release check: 182 tests plus plugin/skill/manifest contracts pass.
- Real Codex CLI 0.153.4 local installation in a disposable profile succeeded.
  48 installed files matched their source; all five skills were included.
- Running the runtime suite from that installed cache passed 70 tests.
- These remain isolated installation and runtime-contract checks, not live
  desktop Hook trust, skill behavior acceptance, or a stable-release claim.

## Quiet-entry candidate — 2026-09-26

- Scope: suppress healthy default/Light startup guidance and inactive install
  hints; narrow grounding/truth-first discovery; make stock doctor/report advice
  conditional. Explicit assistance, obligations and unhealthy-state notices stay.
- Legacy Profile configuration/resolver remains compatible. No new workflow mode,
  capability database, state store or risk classifier was introduced.
- No installed project or user configuration was changed. Historical A/B and clean
  baseline results are frozen; the subsequent real-model check is recorded below.
- Skills are still discoverable; reduced implicit invocation is an intended
  behavior that requires fresh-session validation, not a deterministic guarantee.
- Final source release contract passed: plugin, six skill validators, package
  manifest, and 241 regression tests (164.707 seconds).
- Native CLI 0.155.0-alpha.9 with fixed loopback Responses and temporary
  CODEX_HOME passed quiet-entry, explicit escalation/resume, destructive denial,
  fixed-check failure, native approval accept/decline and sandbox checks. This
  harness uses invocation-only trust bypass for vetted fixture Hooks; it does
  not establish desktop installation or user Hook trust acceptance.
- The full native harness FAILED its Guardian lifecycle group: the unchanged
  reader only accepts 0.154.0-alpha.6.2 and reports UNKNOWN on 0.155.0-alpha.9.
  No allowed-version change was made. An incidental zero-request blocked-turn
  assertion is not evidence that the intended Guardian stage worked. Resolve
  version compatibility separately before claiming complete current-CLI E2E.
- Local detailed results: `.acgm/workflow-quiet/release-final.json` and
  `native-final.json`. Preliminary runs are not final acceptance: one observed
  an in-progress manifest change; the final source was frozen for both reruns.

## Quiet-entry real-model check — 2026-09-26

- Four new Astra/max runs on CLI 0.155.0-alpha.9: T1/T2 Quiet and Clean, n=1
  per combination; Guardian Off, unchanged native sandbox/approval, identical
  business prompts and verified business-file hashes. No mid-run source tuning.
- All tasks passed independent scope/test checks. Both bugfix regressions failed
  against original source and passed after the fix. Quiet samples read no ACGM
  skill body and made no doctor/policy/gate call, but still read governance files.
- Quiet/Clean aggregate: 125,173/136,879 tokens, 16/20 primitive requests,
  219.9/184.7 seconds. Fewer tokens but greater latency is not a stable efficiency
  win; batching, cache, platform delays and tiny sample size limit inference.
- Historical 0.154 groups are reference only; no new real-model R2/R3 acceptance.
  Raw Hook UNKNOWN remains 7/9; native reconciliation is not asserted while the
  Guardian reader rejects this CLI version. No installed-runtime upgrade.
- Local report: `.acgm/workflow-quiet/real-model/REPORT.md`. User config and
  candidate hashes unchanged during runs; temporary authentication copies removed.

## Bounded advisory experiment — 2026-09-26 (withdrawn)

Historical results below describe a superseded candidate, not current behavior.
The production exception and its configuration fields were subsequently removed.

- Optional accepted-policy fields `enforcement` and `advisory_paths`; legacy and
  absent configuration remain enforced. No installed policy or native security
  configuration was changed. Guardian and the Claude Code project are unchanged.
- Only exact-listed literal local `/bin/rm -rf -- <path>` targets qualify after
  bounded committed-content inspection. Other categories, dirty/untracked data,
  protected names, symlinks/hardlinks, nonstandard modes/metadata, Strict,
  escalation and pending obligations retain the existing Gate. This is not a
  full metadata backup or atomic protection against concurrent replacement.
- Nine new boundary tests passed, including real deletion of test-owned files,
  independent Git restoration, hidden dirty bytes, metadata rejection, protected
  collateral, preserved obligations and failure/UNKNOWN result handling.
- Full source release checks passed: plugin, six skill validators, manifest,
  and 250 tests in 156.021 seconds. Subsequent changes were documentation only;
  the manifest was regenerated and checked after recording these results.
- Three native CLI 0.155.0-alpha.9 fixed-response probes: advisory/workspace-write,
  enforced/workspace-write, advisory/read-only. ACGM emitted `gate-advised` for
  both advisory cases; enforced emitted `gate-denied`. Targets stayed intact.
  In advisory cases the actual tool result was native command-policy rejection:
  `rm -f style commands are not permitted. Use a safer approach`. This was not
  Astra choosing to stop, and not evidence that the read-only sandbox itself
  intercepted execution. No approval dialog/auto-review decision was observed.
- Nonblocking notice was present on the next model request; it is not a
  prerequisite that the model reads before mutation. The fixture final message
  is not success evidence. No native delete/post-verification or model cost
  improvement is claimed. Fixed Responses usage is synthetic, not telemetry
  suitable for token comparison; real-model/account calls: zero.
- Native probes used isolated homes and invocation-only trust bypass for vetted
  fixture Hooks; no desktop trust or installation acceptance. The previously
  reported unsupported Guardian CLI version remains unresolved, not weakened.
- Local artifacts: `.acgm/advisory-candidate/{native.py,results.json,release.json,REPORT.md}`.

## Retained quiet-entry candidate — 2026-09-26

- Removed the experimental deletion exception, Git-content/metadata inspection,
  `gate-advised` emission and `enforcement`/`advisory_paths` schema extensions.
  Archived its source and tests locally with the experimental evidence; no
  installed environment had enabled it. Unknown policy fields fail closed.
- Retained quiet healthy entry, targeted recovery and conditional doctor/report.
  Existing verification obligations still require the supplied check; ordinary
  result verification remains required even without a mechanical obligation.
- Direct same-fixture comparison with PR HEAD: healthy Light SessionStart model
  context 762 -> 0 characters; project-event reads 2 -> 1. Counts cover that Hook
  function only, not all hooks, model tokens, or task duration.
- AST comparison confirms pre-tool Gate, post-tool handling, Stop, arm consumption,
  policy schema and profile resolver equal PR HEAD. All 13 targeted policy tests
  passed, including removal of the advisory fields without opening a bypass.
- Prior quiet-entry real-model evidence remains relevant but small and mixed:
  fewer aggregate tokens, no stable speedup. No additional model calls were made
  for this rollback. Guardian's previously documented native-version limitation
  remains open. No installation, user config modification, commit or push.
- Final verification artifacts live in `.acgm/quiet-final/`.

## Project continuity and current Guardian acceptance — 2026-09-28

- Markdown decision/snapshot record changes now produce advisory entry/recovery
  notices; policy files, required root rules and unsafe directory entries remain
  enforced. The baseline is not rewritten. Existing anchored directory scanning
  is reused; no new permission system or persistent acknowledgement state.
- Source release checks passed with 246 tests (144.646 seconds). A captured native
  0.158.0-alpha.2.1 metrics fixture validates latest-response rather than cumulative
  usage. Unknown versions, identity mismatch and malformed/stale data stay refused.
- Final native harness passed all 22 assertions across 24 scenarios, including
  record readback on resume, exact fixed-check failure escalation and Guardian
  continue/handoff/compaction behavior. This supersedes the previously unsupported
  current-version limitation only for the explicitly verified 0.158.0-alpha.2.1.
- Initial native failures were retained: asynchronous fixture commands were not
  awaited; login-shell PATH/global CLI selection and an unsupported metacharacter
  in the explicit source path then prevented correct checks. The final fixture
  preserves its isolated PATH and waits for commands; production gates were not
  weakened. No real-model token or semantic handoff claim follows from this test.
- Detailed public scope and limits: docs/LEAN-WORKFLOW-ACCEPTANCE.md. Local raw
  results: .acgm/phase-next/release-final.json and native-final.json. No installation
  or immutable release-tag replacement occurred in this development stage.
