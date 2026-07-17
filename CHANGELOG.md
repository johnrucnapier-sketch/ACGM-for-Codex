# Changelog

## Unreleased

- Make standalone `doctor` and `report` genuinely read-only when consuming an
  existing Hook ledger: they no longer create directories, repair modes, or open
  write-capable lock files merely to resolve the locator, HMAC key, and events.
  This preserves strict health checks inside managed Codex sandboxes where
  plugin data is readable but intentionally not writable.

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

This RC must not be promoted until the current Codex desktop/CLI Hook E2E passes
in a clean task.
