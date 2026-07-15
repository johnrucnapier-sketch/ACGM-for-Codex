# Changelog

## 0.1.0-rc.2 — unreleased

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
