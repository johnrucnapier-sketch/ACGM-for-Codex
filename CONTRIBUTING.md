# Contributing

ACGM for Codex is an evidence-led governance adapter. Keep changes narrow,
testable, and explicit about what Codex can and cannot enforce.

## Before changing behavior

1. Verify the current Codex Hook and plugin contract from official sources.
2. Separate a platform-independent methodology rule from a Codex-specific
   mechanism.
3. Decide whether the change belongs in prose, a skill, a deterministic Hook,
   or an external human review.
4. Do not convert one incident, an activity count, or a fixed age threshold into
   a universal blocking rule without stronger evidence.

## Validation

Run:

```bash
python3 scripts/release_check.py
```

Changes to Hook definitions also require the disposable real-platform checklist
in `tests/manual/CODEX_E2E.md`. Fixture tests cannot prove that the installed
Codex version discovered, trusted, and invoked a Hook.

Preserve event semantics when changing the runtime: `PermissionRequest` records
only a sanitized boundary observation and makes no ACGM decision; `PreCompact` is
heartbeat-only; Codex Bash response text is never authenticated gate evidence;
fixed non-shell checks must exit zero before arming or closing anything; and
closing a mechanical obligation is not a semantic success claim. Gate evidence
and postcondition checks must stay bound to the same locally HMAC-derived target,
and one arm must be consumed atomically at most once.

## Privacy

Do not add prompts, transcripts, source, full commands, paths, remotes, model or
provider identities, credentials, or reconstructable fingerprints to persistent
events. Test with harmless unique fixtures, never real secrets.

## Claims

Update `EVIDENCE.md` when a claim's maturity changes. State skipped or failed
checks plainly. An RC is not stable until its declared manual gates pass.
