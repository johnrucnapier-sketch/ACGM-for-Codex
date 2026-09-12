# Claude 0.9.2 alignment review — 2026-09-12

## Verified sources

- Reference: [ACGM-for-Claude-Code](https://github.com/johnrucnapier-sketch/ACGM-for-Claude-Code/tree/c2ca0a2913d376d7eefee98fd6549774a0aa7961),
  `main`, HEAD `c2ca0a2913d376d7eefee98fd6549774a0aa7961`, source version 0.9.2.
- Codex baseline: `3e9c507617e8e1290ca8d56532c623c571675069`, published
  `v0.2.0-rc.4`. Candidate branch: `codex/claude-092-alignment`.
- The old `Agent-Coding-Governance-Methodology` checkout is 0.3.0-rc.4 and is
  not the reference for the newer Claude product.
- Both reference and Codex checkouts were clean before development. Baseline
  suites passed locally: Claude 68 tests; Codex 178 tests.

## Transfer decisions

| Claude mechanism | Codex treatment | Reason |
|---|---|---|
| Open threads, claims, confirmed decisions | Adopt as a concise skill with templates | Preserve reasons without another runtime subsystem |
| Draft immediately; confirmation rides normal work | Adopt | No repeated consent or standalone interruption |
| Resume open threads; distinguish facts from history | Add to grounding | Current code remains authoritative |
| Small, purposeful injection | Remove per-tool ambiguous-root warnings | Reproduced repeatedly in the parent workspace in this task |
| Four distinct evidence stages | Clarify startup wording | One Hook cannot prove all Hooks ran |
| Claude transcript-based evidence gate | Retain Codex fixed checks | Codex transcript format is not a stable interface |
| Claude SSH/read-only whitelist | Do not port | The current Codex gate does not gate all SSH; no corresponding fault justifies it |
| Claude doctor source/cache comparison | Retain existing exact manifest/pinned-source checks | Avoid replacing independent verification with a self-comparison |
| SessionEnd ledger report | Not implemented in this candidate | Skill saves during work; no claim that an end callback guarantees preservation |
| All decisions authored directly on trunk | Use project branch/review policy | Codex worktrees and user scope must be preserved |

The reference skill's advisory grace period began 2026-08-06 and is already past
its stated 30-day window. Its existence is not second independent evidence.
The workflow remains advisory here; no empirical effectiveness claim is inherited.
Its assertion that date-based claim IDs cannot collide is also not inherited.

## Complexity and compatibility

The Claude reference has 2,111 lines across its scripts. The Codex baseline has
9,052 Python script lines, of which 4,617 are the runtime (including project
quickstart) and 3,607 are preflight/bootstrap/quickstart installers. Counts are
scope-specific, not a quality score. Existing installation verification and
privacy protections have regression coverage and cannot simply be deleted as
redundant. This candidate adds no dependency or new runtime subsystem.

The private Event Ledger remains separate from Git-trackable decision files.
No transcript or claim body is copied into the private ledger. No existing
Constitution, preset byte string, activation schema, gate category, or project
file is silently migrated. New accepted ADRs remain subject to the existing
activation-baseline drift check; draft/open-thread files do not change that baseline.

Source-verified predecessor pins permit the normal exact-plan upgrade from RC4.
Unknown/changed predecessor bytes remain blocked. Runtime changes regenerate the
Hook command's embedded hash and size; installing them requires platform trust.

## Verification and delivery boundaries

Validation passed locally: release checker with 180 tests; then 23 targeted
checks including two new draft/ADR and RC4-preservation regressions. No runtime
code changed after the full run.

Run `python3 scripts/release_check.py` for package, skill, byte-manifest, and
regression checks. New fixtures check entry-only ambiguity warnings, zero project
or data writes from ambiguous-root events, and accurate startup context.
The existing suite still covers gates, Constitution protection, bootstrap,
preservation, and restart-safe runtime wrappers.

Manual acceptance additionally checks decision workflow behavior: a meaningful
thread produces one pending draft; silence does not promote it; recovery reads
open questions; draft creation does not block Stop or auto-commit. These are
agent behavior checks, not guarantees established by template existence.

At the initial source review, the candidate was unpublished. No current plugin cache, Codex configuration,
private runtime, or governed user project was changed. The reference repository
is read-only. Do not claim installed behavior until exact-source publication,
installation and real platform acceptance are complete.

Platform boundary checked against [official Codex Hooks documentation](https://learn.chatgpt.com/docs/hooks)
on 2026-09-12: transcript format is unstable; SessionEnd is advisory and distinct
from Stop; concise Hook output is recommended. Current support must still be
tested against the installed target, not inferred from July's coverage notes.

## Installation validation — 2026-09-12

Codex CLI 0.153.4 installed this candidate into an isolated temporary profile.
All 48 installed files matched the corresponding source bytes, and all five
skills were present. The installed cache passed 70 runtime tests; the source
release checker passed all 182 tests plus plugin, skill and manifest contracts.
The first test attempt needed its temporary CODEX_HOME directory created; retry
then succeeded. No production configuration was involved in that attempt.

These checks support publishing the RC and attempting the verified official RC4
upgrade. They do not represent desktop Hook trust or actual task E2E. The old
program was retained outside the repository and private data was fingerprinted
without copying its contents for post-upgrade comparison.
