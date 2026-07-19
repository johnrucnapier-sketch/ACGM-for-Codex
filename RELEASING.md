# Release process

## RC gates

1. Confirm the source worktree and review every uncommitted file.
2. Keep `VERSION`, the plugin manifest, changelog, and runtime identity aligned.
3. Regenerate `PACKAGE_MANIFEST.json`, commit every release file, and prove the
   release commit is exactly tagged before public bootstrap testing.
4. Run `python3 scripts/release_check.py` on Python 3.10 and the current Python.
   Confirm the GitHub Actions macOS/Linux matrix and Windows fail-closed job pass.
5. Exercise fresh, dry-run, explicit-authorization, idempotent, legacy,
   duplicate/conflict, command-failure/partial, source/tag/manifest, and cache
   byte-verification paths with an isolated HOME/CODEX_HOME and fake Codex CLI.
   Include Codex-owned marketplace metadata, cache-with-Git/cache-without-Git,
   concurrent directory publication, late managed-file symlink cases, stable
   runtime missing/exact/known-old/unknown/symlink/FIFO states, unsafe parents,
   zero-progress writes, and atomic failure cleanup.
6. Install into a disposable home and verify the exact published-file allowlist,
   symlink-safe CLI replacement, marketplace/personal-source/CLI rollback after
   an injected later failure, and cache behavior. Do not describe Codex cache as
   rolled back if refresh had already begun.
7. Add the exact tag-pinned Git marketplace and plugin in a disposable real
   Codex profile, activate a disposable governed project, and start a new Codex
   task so the accepted heartbeat is later than that activation.
   Record the real `marketplace list --json` and `plugin list --available --json`
   field shapes. When the CLI omits a ref or an available entry, prove the exact
   persisted config plus clean tag/HEAD, origin, manifest, release contract, and
   marketplace snapshot bytes; do not promote a fixture-only interpretation.
   Apply the same rule when a pre-install version key carries an explicit null
   placeholder: accept that null only when independent exact-release evidence
   supplies the version. Continue to reject a missing key or explicit conflict.
   Also exercise the exact latest-official-predecessor-to-candidate upgrade:
   verify the old snapshot and sole installed cache, inspect the
   remove/add/add plan, confirm the full new cache plus only exact transition
   bridges, verify the manifest-bound stable runtime publication, and prove the
   Event Ledger, HMAC key, and all other private plugin data are untouched.
8. Fully quit and reopen Codex desktop after the plugin change; record that the
   app-server process identity changed. Then review and trust the exact Hook
   definitions through `/hooks`. Confirm the command's embedded runtime hash and
   size match the stable private regular file and install postflight. Do not
   simulate a heartbeat by manually invoking a Hook.
9. Complete every item in `tests/manual/CODEX_E2E.md` in a disposable repository.
10. Search real `PLUGIN_DATA` and confirm that raw prompt, path, command, remote,
   model, and secret fixtures were never persisted.
11. Remove the local HMAC key only in a disposable copy and confirm that a
   surviving ledger prevents silent key regeneration; restore key and ledger
   together afterward.
12. Update `EVIDENCE.md` with only the claims actually reproduced.

## Stable promotion

Remove the RC suffix only after all RC gates pass on the declared Codex version.
Do not inherit a Claude Code validation result. Record the tested Codex desktop,
CLI, OS, Python, and Git versions.

Publishing a commit, tag, or release is a separate external-state action. Review
the exact target repository, branch, diff, version, and release status before
each publication; a public repository does not authorize a stable release.
