# Release process

## RC gates

1. Confirm the source worktree and review every uncommitted file.
2. Keep `VERSION`, the plugin manifest, changelog, and runtime identity aligned.
3. Run `python3 scripts/release_check.py` on Python 3.10 and the current Python.
4. Install into a disposable home and verify the exact published-file allowlist,
   symlink-safe CLI replacement, marketplace/personal-source/CLI rollback after
   an injected later failure, and cache behavior. Do not describe Codex cache as
   rolled back if refresh had already begun.
5. Install into the real personal marketplace, activate a disposable governed
   project, and start a new Codex task so the accepted heartbeat is later than
   that activation.
6. Review and trust the exact Hook definitions through `/hooks`.
7. Complete every item in `tests/manual/CODEX_E2E.md` in a disposable repository.
8. Search real `PLUGIN_DATA` and confirm that raw prompt, path, command, remote,
   model, and secret fixtures were never persisted.
9. Remove the local HMAC key only in a disposable copy and confirm that a
   surviving ledger prevents silent key regeneration; restore key and ledger
   together afterward.
10. Update `EVIDENCE.md` with only the claims actually reproduced.

## Stable promotion

Remove the RC suffix only after all RC gates pass on the declared Codex version.
Do not inherit a Claude Code validation result. Record the tested Codex desktop,
CLI, OS, Python, and Git versions.

Publishing a commit, tag, or release is a separate external-state action. Review
the exact target repository, branch, diff, version, and release status before
each publication; a public repository does not authorize a stable release.
