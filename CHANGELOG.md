# Changelog

## 0.2.0-rc.1 — 2026-07-17 tagged test candidate; pending installed-platform validation

- Add a one-consent quickstart that combines exact tag/manifest/plugin
  verification with project provisioning, activation, and local postcondition
  checks. A direct install-and-enable request for one exact project authorizes
  the fixed `standard-v1` plan without repeated ACGM confirmation prompts.
- Bind quickstart plan/apply to one digest covering source/ref, fixed install
  commands, exact Git root and identity, existing managed-file hashes, preset,
  and proposed bytes. Stale plans fail before project mutation.
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
