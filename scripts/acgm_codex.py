#!/usr/bin/env python3
"""ACGM for Codex local governance runtime.

This module intentionally uses only the Python standard library.  Hook input is
treated as ephemeral: the activity ledger stores only controlled enums and
HMAC-derived opaque identifiers, never paths, commands, prompts, providers, or
credentials.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - the supported platforms provide it.
    fcntl = None  # type: ignore[assignment]


VERSION = "0.2.0-rc.4"
STATE_SCHEMA = "acgm-codex-state-v1"
LEDGER_SCHEMA = "acgm-codex-event-v1"
CASE_SCHEMA = "acgm-codex-case-v1"
DATA_LOCATION_SCHEMA = "acgm-codex-data-location-v1"
QUICKSTART_SCHEMA = "acgm-codex-quickstart-plan-v1"
QUICKSTART_RECEIPT_SCHEMA = "acgm-codex-quickstart-receipt-v1"
QUICKSTART_PRESET = "standard-v1"
QUICKSTART_COMPATIBLE_STATE_VERSIONS = (
    "0.1.0-rc.2",
    "0.1.0-rc.3",
    "0.1.0-rc.4",
    "0.2.0-rc.1",
    "0.2.0-rc.2",
    "0.2.0-rc.3",
)
QUICKSTART_MANAGED_DIRECTORIES = (
    ".acgm",
    ".governance",
    ".governance/decisions",
    ".governance/snapshots",
)
GATE_TTL_SECONDS = 180
MAX_WORKSPACE_ENTRIES = 128
MAX_DIRECT_REPOSITORIES = 16

INSTALLED_NOT_BOOTSTRAPPED = "INSTALLED_NOT_BOOTSTRAPPED"
PARTIALLY_GOVERNED = "PARTIALLY_GOVERNED"
GOVERNED = "GOVERNED"
DRIFTED = "DRIFTED"
BROKEN = "BROKEN"

REQUIRED_FILES = (
    "CONSTITUTION.md",
    "AGENTS.md",
    ".governance/scope.yml",
)
REQUIRED_DIRS = (
    ".governance/decisions",
    ".governance/snapshots",
)
GATE_CATEGORIES = (
    "git-reset-hard",
    "git-clean-force",
    "git-branch-delete",
    "git-force-push",
    "recursive-delete",
)
RESOLUTION_STATUSES = (
    "resolved",
    "verified",
    "human_override",
    "false_positive",
    "unresolved",
)

HOOK_NAMES = {
    "session-start": "SessionStart",
    "subagent-start": "SubagentStart",
    "pre-tool": "PreToolUse",
    "permission-request": "PermissionRequest",
    "post-tool": "PostToolUse",
    "pre-compact": "PreCompact",
    "stop": "Stop",
}

_PENDING_TOKEN = "TO" + "DO"
PLACEHOLDER_RE = re.compile(
    r"(?:\[\s*(?:" + _PENDING_TOKEN + r"|TBD|PLACEHOLDER)\s*\]|"
    r"<(?:" + _PENDING_TOKEN + r"|TBD|PLACEHOLDER)>|"
    r"\bACGM[-_]PLACEHOLDER\b|"
    r"\b(?:REPLACE_ME|FILL_ME_IN|YOUR_PROJECT)\b)",
    re.IGNORECASE,
)

CONSTITUTION_TEMPLATE = """# Project Constitution

<!-- [PLACEHOLDER] Human review is required before ACGM activation. -->

## Authority

This file contains the stable governance constraints for this project. Changes
to it require explicit human review; automated editing is blocked by ACGM.

## Truth hierarchy

1. Current code, configuration, and Git state are current facts.
2. Version-control history is evidence of recorded change.
3. Historical discussions explain decisions but do not override current facts.
4. Claims about completion require proportionate verification.

## Change discipline

- Inspect current state before a consequential or destructive action.
- Preserve unrelated work and avoid broad destructive cleanup.
- Keep implementation, documentation, and validation evidence aligned.
- Record durable architectural decisions under `.governance/decisions/`.

## Completion

A task is complete only when requested behavior is implemented, relevant checks
pass, and remaining limitations are stated plainly.
"""

AGENTS_TEMPLATE = """# ACGM instructions for Codex

Read `CONSTITUTION.md` and `.governance/scope.yml` before making consequential
changes. Treat current files and Git state as current truth; use history and old
transcripts only as evidence.

Before destructive Git or filesystem actions, inspect current state. If ACGM
denies the action, run the exact `acgm-codex gate arm --event ... --category
...` command described by the hook. That command performs a fixed read-only
check inside the ACGM runtime before arming one retry. A gate arm never
constitutes user authorization and never bypasses Codex's own permission
system.

After an allowed high-risk action, run the exact `acgm-codex gate verify
--event ... --category ...` command described by the hook before ending the
turn. Do not edit `CONSTITUTION.md` through an automated tool; prepare a
proposal for human review instead.

Use `acgm-codex doctor --strict` to verify project activation and observed hook
execution. Use `acgm-codex report` for the privacy-minimized activity ledger.
"""

SCOPE_TEMPLATE = """# [PLACEHOLDER] Replace the example scope after human review.
version: 1
project: local
governed:
  - source
  - tests
  - documentation
excluded:
  - generated_artifacts
  - third_party_dependencies
require_current_state_check: true
require_post_action_verification: true
privacy:
  persist_raw_paths: false
  persist_commands_or_prompts: false
"""

STANDARD_CONSTITUTION = """# Project Constitution

This project adopts the ACGM `standard-v1` governance preset. The project owner
approved these versioned defaults through the one-consent quickstart flow.

## Authority

Project-specific instructions and explicit user decisions remain authoritative.
This Constitution supplies durable defaults where the project has not stated a
more specific rule. Later changes require explicit project-owner authorization.

## Truth hierarchy

1. Current code, configuration, and Git state are current facts.
2. Version-control history is evidence of recorded change.
3. Historical discussions explain decisions but do not override current facts.
4. Claims about completion require proportionate verification.

## Change discipline

- Verify the active project root, branch, worktree, and dirty state before a
  consequential change.
- Preserve unrelated work; do not use destructive cleanup to simplify a task.
- Require explicit authorization for destructive, external, credential, release,
  deployment, permission, or irreversible actions.
- Keep implementation, documentation, and validation evidence aligned.
- Never expose credentials, tokens, cookies, private transcript content, or other
  sensitive local evidence.

## Completion

A task is complete only when requested behavior is implemented, relevant checks
pass, and remaining limitations or pending platform acceptance are stated plainly.
"""

STANDARD_SCOPE = """version: 1
preset: standard-v1
project_root: .
governed:
  - .
excluded:
  - .git
  - .acgm
  - third_party_dependencies
  - generated_artifacts
require_current_state_check: true
require_post_action_verification: true
require_explicit_authorization_for:
  - destructive_changes
  - external_state_mutation
  - credential_or_permission_changes
  - releases_and_deployments
privacy:
  persist_raw_paths: false
  persist_commands_or_prompts: false
  persist_credentials_or_transcripts: false
"""

STANDARD_DECISION = """# Adopt ACGM standard-v1

Status: accepted

The project adopts the versioned ACGM `standard-v1` preset through the
one-consent quickstart flow. Existing project-owned instructions are preserved
and take precedence when they are more specific. ACGM may generate missing
governance assets, but it must not overwrite unknown existing policy.
"""


class RuntimeProblem(Exception):
    """A user-actionable runtime or project-state problem."""


class AmbiguousWorkspace(RuntimeProblem):
    """A container workspace has no single safe implicit project root."""

    def __init__(
        self,
        container: Path,
        candidates: Iterable[Path] = (),
        *,
        reason: Optional[str] = None,
    ) -> None:
        self.container = container
        self.candidates = tuple(candidates)
        names = ", ".join(path.name for path in self.candidates)
        detail = f" Candidates: {names}." if names else ""
        super().__init__(
            (reason or "multiple repositories were found in an empty container workspace")
            + "; open the intended repository directly or pass its exact path."
            + detail
        )


def _supported_platform() -> bool:
    return os.name == "posix" and platform.system() in {"Darwin", "Linux"}


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _cli_launcher() -> str:
    installed = Path.home() / ".local" / "bin" / "acgm-codex"
    candidate = installed if installed.is_file() else _plugin_root() / "bin" / "acgm-codex"
    return shlex.quote(str(candidate)) if candidate.is_file() else "acgm-codex"


def _installed() -> bool:
    return (_plugin_root() / ".codex-plugin" / "plugin.json").is_file()


def _git_probe(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        environment.pop(name, None)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            env=environment,
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return subprocess.CompletedProcess([], 127, "", "git probe failed")


def _verified_git_root(candidate: Path) -> Optional[Path]:
    result = _git_probe(candidate, "rev-parse", "--show-toplevel")
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return Path(result.stdout.strip()).resolve()
    except OSError:
        return None


def _adapter_declares_active(root: Path) -> bool:
    path = _state_path(root)
    if path.is_symlink() or not path.is_file():
        return False
    try:
        state = _safe_read_json(path)
    except RuntimeProblem:
        return False
    return state.get("schema") == STATE_SCHEMA and state.get("active") is True


def _container_workspace_root(root: Path) -> Path:
    # An active adapter is an intentional project marker.  An inactive or
    # malformed residual marker is not: letting it win here would make an empty
    # container repository silently swallow one of several child repositories.
    if _adapter_declares_active(root):
        return root
    if _git_probe(root, "rev-parse", "--verify", "HEAD").returncode == 0:
        return root
    index = _git_probe(root, "ls-files", "-z")
    if index.returncode != 0 or index.stdout:
        return root
    try:
        entries = list(root.iterdir())
    except OSError:
        return root
    if len(entries) > MAX_WORKSPACE_ENTRIES:
        raise AmbiguousWorkspace(
            root,
            reason="the unborn workspace contains too many entries to resolve safely",
        )
    repositories: list[Path] = []
    non_container_entries: list[Path] = []
    for entry in entries:
        if entry.name == ".git":
            continue
        if entry.is_symlink() or not entry.is_dir() or not (entry / ".git").exists():
            non_container_entries.append(entry)
            continue
        verified = _verified_git_root(entry)
        if verified is None or verified != entry.resolve():
            non_container_entries.append(entry)
            continue
        repositories.append(verified)
        if len(repositories) > MAX_DIRECT_REPOSITORIES:
            raise AmbiguousWorkspace(root, repositories)
    repositories.sort(key=lambda path: path.name.casefold())
    if len(repositories) > 1:
        raise AmbiguousWorkspace(root, repositories)
    if len(repositories) == 1 and non_container_entries:
        raise AmbiguousWorkspace(
            root,
            repositories,
            reason=(
                "the unborn workspace contains both a child repository and "
                "non-container files"
            ),
        )
    if len(repositories) == 1:
        return repositories[0]
    return root


def _project_root(start: Optional[str] = None) -> Path:
    candidate = Path(start or os.getcwd()).expanduser()
    if not candidate.exists():
        raise RuntimeProblem("project directory does not exist")
    candidate = candidate.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    chain = (candidate,) + tuple(candidate.parents)
    for parent in chain:
        if (parent / ".git").exists() and _verified_git_root(parent) == parent:
            return _container_workspace_root(parent)
        if _adapter_declares_active(parent):
            return parent
    return candidate


def _state_path(root: Path) -> Path:
    return root / ".acgm" / "codex.json"


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeProblem("adapter state is unreadable or invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeProblem("adapter state must be a JSON object")
    return value


def _atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_new_bytes(path: Path, payload: bytes, mode: int) -> str:
    """Publish one complete new file without exposing a writable partial target.

    ``O_EXCL`` on the final path only protects the creation syscall.  Writing
    through that descriptor afterwards exposes a zero-length or partial file
    that another writer can edit before our write completes.  Prepare the full
    payload under a private name, fsync it, then use link(2) as the
    no-overwrite publication point instead.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(12)
    prepared = path.with_name(f".{path.name}.acgm-create-{token}")
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    descriptor = os.open(prepared, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(prepared, mode)
    except Exception:
        try:
            prepared.unlink()
        except OSError:
            pass
        raise

    try:
        # link(2) never replaces a target created by a concurrent writer.
        os.link(prepared, path, follow_symlinks=False)
        prepared_stat = prepared.lstat()
        current_stat = path.lstat()
        if (
            not stat.S_ISREG(current_stat.st_mode)
            or current_stat.st_dev != prepared_stat.st_dev
            or current_stat.st_ino != prepared_stat.st_ino
            or not hmac.compare_digest(_sha256(path), payload_sha256)
        ):
            raise RuntimeProblem("quickstart target changed during creation")
        return payload_sha256
    finally:
        try:
            prepared.unlink()
        except FileNotFoundError:
            pass


def _write_new_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> str:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return _write_new_bytes(path, payload, mode)


def _entry_exists_at(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _regular_bytes_at(directory_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeProblem("quickstart target is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read()
        after = os.fstat(descriptor)
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            raise RuntimeProblem("quickstart target changed while reading")
        return content
    finally:
        os.close(descriptor)


def _sha256_at(directory_fd: int, name: str) -> str:
    return hashlib.sha256(_regular_bytes_at(directory_fd, name)).hexdigest()


def _safe_read_json_at(directory_fd: int, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_regular_bytes_at(directory_fd, name).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeProblem("adapter state is unreadable or invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeProblem("adapter state must be a JSON object")
    return value


def _regular_digest_at(directory_fd: int, name: str) -> str:
    """Hash one stable regular directory entry without following symlinks."""

    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise RuntimeProblem("quickstart managed file is unavailable") from exc
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeProblem("quickstart managed file is not a regular file")
    digest = _sha256_at(directory_fd, name)
    try:
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise RuntimeProblem("quickstart managed file changed while hashing") from exc
    if (
        not stat.S_ISREG(after.st_mode)
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
    ):
        raise RuntimeProblem("quickstart managed file changed while hashing")
    return digest


def _directory_baseline_at(directory_fd: int, prefix: str = "") -> dict[str, str]:
    """Recursively fingerprint non-hidden regular files from an anchored dirfd."""

    try:
        names = sorted(os.listdir(directory_fd))
    except OSError as exc:
        raise RuntimeProblem("quickstart managed directory is unreadable") from exc
    baseline: dict[str, str] = {}
    for name in names:
        if not name or name in {".", ".."} or name.startswith("."):
            continue
        relative = f"{prefix}/{name}" if prefix else name
        try:
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as exc:
            raise RuntimeProblem(
                "quickstart managed directory changed while scanning"
            ) from exc
        if stat.S_ISREG(metadata.st_mode):
            baseline[relative] = _regular_digest_at(directory_fd, name)
            continue
        if stat.S_ISDIR(metadata.st_mode):
            expected = {"device": metadata.st_dev, "inode": metadata.st_ino}
            child_fd = _open_quickstart_managed_directory(
                directory_fd, name, expected
            )
            try:
                baseline.update(_directory_baseline_at(child_fd, relative))
                _verify_quickstart_directory_entry(directory_fd, name, child_fd)
            finally:
                os.close(child_fd)
            continue
        raise RuntimeProblem(
            "quickstart managed directory contains a symlink or special entry"
        )
    return baseline


def _quickstart_component_baseline_at(
    root_fd: int,
    governance_fd: int,
    decisions_fd: int,
    snapshots_fd: int,
) -> dict[str, Any]:
    """Compute the governance baseline only through already-anchored directories."""

    return {
        "files": {
            "CONSTITUTION.md": _regular_digest_at(root_fd, "CONSTITUTION.md"),
            "AGENTS.md": _regular_digest_at(root_fd, "AGENTS.md"),
            ".governance/scope.yml": _regular_digest_at(
                governance_fd, "scope.yml"
            ),
        },
        "directories": {
            ".governance/decisions": _directory_baseline_at(decisions_fd),
            ".governance/snapshots": _directory_baseline_at(snapshots_fd),
        },
    }


def _verify_quickstart_asset_postimages_at(
    assets: Iterable[dict[str, Any]],
    locations: dict[str, tuple[int, str]],
) -> None:
    """Revalidate every managed asset entry and digest without path traversal."""

    for asset in assets:
        path = str(asset.get("path"))
        location = locations.get(path)
        expected = asset.get("after_sha256")
        if location is None or not isinstance(expected, str):
            raise RuntimeProblem("quickstart plan contains an invalid managed asset")
        directory_fd, name = location
        if not hmac.compare_digest(_regular_digest_at(directory_fd, name), expected):
            raise RuntimeProblem(f"quickstart managed asset changed: {path}")


def _write_new_bytes_at(
    directory_fd: int, name: str, payload: bytes, mode: int
) -> str:
    """Publish a complete file relative to one already-open parent directory."""

    if not name or "/" in name or name in {".", ".."}:
        raise RuntimeProblem("quickstart received an unsafe managed file name")
    token = secrets.token_hex(12)
    prepared = f".{name}.acgm-create-{token}"
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    descriptor = os.open(
        prepared,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        mode,
        dir_fd=directory_fd,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
    except Exception:
        try:
            os.unlink(prepared, dir_fd=directory_fd)
        except OSError:
            pass
        raise

    try:
        os.link(
            prepared,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        prepared_stat = os.stat(
            prepared, dir_fd=directory_fd, follow_symlinks=False
        )
        current_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(current_stat.st_mode)
            or current_stat.st_dev != prepared_stat.st_dev
            or current_stat.st_ino != prepared_stat.st_ino
            or not hmac.compare_digest(
                _sha256_at(directory_fd, name), payload_sha256
            )
        ):
            raise RuntimeProblem("quickstart target changed during creation")
        return payload_sha256
    finally:
        try:
            os.unlink(prepared, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _write_new_json_at(
    directory_fd: int,
    name: str,
    value: dict[str, Any],
    mode: int = 0o600,
) -> str:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return _write_new_bytes_at(directory_fd, name, payload, mode)


def _path_entry_exists(path: Path) -> bool:
    """Return whether a directory entry exists, including a broken symlink."""

    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _quickstart_cas_bytes(
    path: Path,
    payload: bytes,
    expected_sha256: str,
    *,
    mode: int,
) -> str:
    """Replace one known regular file without overwriting a concurrent edit.

    POSIX rename has no compare-and-swap primitive: a final hash check followed
    by ``os.replace`` still has a lost-update window.  Quickstart therefore
    detaches the current directory entry first, verifies that detached
    preimage, and publishes the prepared postimage with a no-overwrite hard
    link.  A concurrent writer either becomes the detached preimage (and fails
    the hash check) or wins the now-empty target name (and makes the link fail).
    In both cases its bytes are preserved and quickstart reports partial state.
    """

    if not isinstance(expected_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_sha256
    ):
        raise RuntimeProblem("quickstart CAS requires an exact preimage digest")
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(12)
    prepared = path.with_name(f".{path.name}.acgm-prepared-{token}")
    displaced = path.with_name(f".{path.name}.acgm-preimage-{token}")
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    descriptor = os.open(prepared, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(prepared, mode)
    except Exception:
        try:
            prepared.unlink()
        except OSError:
            pass
        raise

    detached = False
    try:
        # The random destination is private to this operation.  Whatever entry
        # occupies `path` at this exact syscall boundary is what gets verified.
        os.rename(path, displaced)
        detached = True
        metadata = displaced.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeProblem("quickstart target changed before final CAS")
        if not hmac.compare_digest(_sha256(displaced), expected_sha256):
            raise RuntimeProblem("quickstart target changed before final CAS")

        # link(2) is the commit point and never replaces an entry created by a
        # concurrent writer while the verified preimage is detached.
        os.link(prepared, path, follow_symlinks=False)
        prepared_stat = prepared.lstat()
        current_stat = path.lstat()
        if (
            not stat.S_ISREG(current_stat.st_mode)
            or current_stat.st_dev != prepared_stat.st_dev
            or current_stat.st_ino != prepared_stat.st_ino
            or not hmac.compare_digest(_sha256(path), payload_sha256)
            or not hmac.compare_digest(_sha256(displaced), expected_sha256)
        ):
            raise RuntimeProblem("quickstart target changed during final CAS")

        displaced.unlink()
        detached = False
        return payload_sha256
    except (OSError, RuntimeProblem) as exc:
        # Never restore with rename/replace: either operation could overwrite a
        # concurrent writer.  A no-overwrite link restores the detached entry
        # only when the original name is still free.  Otherwise the detached
        # entry remains beside it as explicit recovery evidence.
        if detached and _path_entry_exists(displaced) and not _path_entry_exists(path):
            try:
                os.link(displaced, path, follow_symlinks=False)
                displaced.unlink()
                detached = False
            except OSError:
                pass
        raise RuntimeProblem(
            "quickstart final compare-and-swap detected a concurrent change"
        ) from exc
    finally:
        try:
            prepared.unlink()
        except FileNotFoundError:
            pass
        # If publication succeeded and a later verification failed, keep both
        # the visible entry and detached preimage.  Removing either could erase
        # a concurrent writer's bytes; the partial receipt directs a recheck.


def _quickstart_cas_json(
    path: Path,
    value: dict[str, Any],
    expected_sha256: str,
    *,
    mode: int = 0o600,
) -> str:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    return _quickstart_cas_bytes(
        path, payload, expected_sha256, mode=mode
    )


def _quickstart_cas_bytes_at(
    directory_fd: int,
    name: str,
    payload: bytes,
    expected_sha256: str,
    *,
    mode: int,
) -> str:
    """Replace one known entry without ever resolving its parent by pathname."""

    if not name or "/" in name or name in {".", ".."}:
        raise RuntimeProblem("quickstart received an unsafe managed file name")
    if not isinstance(expected_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_sha256
    ):
        raise RuntimeProblem("quickstart CAS requires an exact preimage digest")
    token = secrets.token_hex(12)
    prepared = f".{name}.acgm-prepared-{token}"
    displaced = f".{name}.acgm-preimage-{token}"
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    descriptor = os.open(
        prepared,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        mode,
        dir_fd=directory_fd,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
    except Exception:
        try:
            os.unlink(prepared, dir_fd=directory_fd)
        except OSError:
            pass
        raise

    detached = False
    try:
        os.rename(
            name,
            displaced,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        detached = True
        metadata = os.stat(
            displaced, dir_fd=directory_fd, follow_symlinks=False
        )
        if not stat.S_ISREG(metadata.st_mode) or not hmac.compare_digest(
            _sha256_at(directory_fd, displaced), expected_sha256
        ):
            raise RuntimeProblem("quickstart target changed before final CAS")

        os.link(
            prepared,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        prepared_stat = os.stat(
            prepared, dir_fd=directory_fd, follow_symlinks=False
        )
        current_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(current_stat.st_mode)
            or current_stat.st_dev != prepared_stat.st_dev
            or current_stat.st_ino != prepared_stat.st_ino
            or not hmac.compare_digest(
                _sha256_at(directory_fd, name), payload_sha256
            )
            or not hmac.compare_digest(
                _sha256_at(directory_fd, displaced), expected_sha256
            )
        ):
            raise RuntimeProblem("quickstart target changed during final CAS")

        os.unlink(displaced, dir_fd=directory_fd)
        detached = False
        return payload_sha256
    except (OSError, RuntimeProblem) as exc:
        if (
            detached
            and _entry_exists_at(directory_fd, displaced)
            and not _entry_exists_at(directory_fd, name)
        ):
            try:
                os.link(
                    displaced,
                    name,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                os.unlink(displaced, dir_fd=directory_fd)
                detached = False
            except OSError:
                pass
        raise RuntimeProblem(
            "quickstart final compare-and-swap detected a concurrent change"
        ) from exc
    finally:
        try:
            os.unlink(prepared, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _quickstart_cas_json_at(
    directory_fd: int,
    name: str,
    value: dict[str, Any],
    expected_sha256: str,
    *,
    mode: int = 0o600,
) -> str:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return _quickstart_cas_bytes_at(
        directory_fd, name, payload, expected_sha256, mode=mode
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _governance_directory_files(root: Path, name: str) -> list[Path]:
    directory = root / name
    if not directory.is_dir():
        return []
    try:
        return sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(directory).parts)
        )
    except OSError:
        return []


def _directory_baseline(root: Path, name: str) -> dict[str, str]:
    directory = root / name
    return {
        path.relative_to(directory).as_posix(): _sha256(path)
        for path in _governance_directory_files(root, name)
    }


def _component_baseline(root: Path) -> dict[str, Any]:
    return {
        "files": {name: _sha256(root / name) for name in REQUIRED_FILES},
        "directories": {
            name: _directory_baseline(root, name) for name in REQUIRED_DIRS
        },
    }


def _asset_issues(root: Path) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    placeholders: list[str] = []
    for name in REQUIRED_FILES:
        path = root / name
        if not path.is_file():
            missing.append(name)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            placeholders.append(name)
            continue
        if len(text.strip()) < 20 or PLACEHOLDER_RE.search(text):
            placeholders.append(name)
    for name in REQUIRED_DIRS:
        directory = root / name
        if not directory.is_dir():
            missing.append(name + "/")
            continue
        substantive = False
        for path in _governance_directory_files(root, name):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if len(text.strip()) >= 20 and not PLACEHOLDER_RE.search(text):
                substantive = True
                break
        if not substantive:
            placeholders.append(name + "/")
    return missing, placeholders


def _project_status(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    missing, placeholders = _asset_issues(root)
    result: dict[str, Any] = {
        "state": INSTALLED_NOT_BOOTSTRAPPED,
        "active": False,
        "missing": missing,
        "placeholders": placeholders,
        "drift": [],
    }
    if not path.exists():
        return result
    try:
        state = _safe_read_json(path)
    except RuntimeProblem:
        result["state"] = BROKEN
        result["drift"] = ["adapter-state-invalid"]
        return result
    if state.get("schema") != STATE_SCHEMA or not isinstance(state.get("active"), bool):
        result["state"] = BROKEN
        result["drift"] = ["adapter-state-schema"]
        return result
    result["active"] = bool(state["active"])
    if not state["active"]:
        result["state"] = PARTIALLY_GOVERNED
        return result
    if not isinstance(state.get("activation_id"), str) or not state["activation_id"]:
        result["state"] = BROKEN
        result["drift"] = ["adapter-activation-id"]
        return result
    baseline = state.get("baseline")
    if (
        not isinstance(baseline, dict)
        or not isinstance(baseline.get("files"), dict)
        or not isinstance(baseline.get("directories"), dict)
    ):
        result["state"] = BROKEN
        result["drift"] = ["adapter-baseline-invalid"]
        return result
    drift: list[str] = []
    if state.get("version") != VERSION:
        drift.append("adapter-version:changed")
    expected_files = baseline["files"]
    for name in REQUIRED_FILES:
        path_item = root / name
        expected = expected_files.get(name)
        if not path_item.is_file():
            drift.append(name + ":missing")
        elif not isinstance(expected, str):
            drift.append(name + ":unbaselined")
        else:
            try:
                if not hmac.compare_digest(_sha256(path_item), expected):
                    drift.append(name + ":changed")
            except OSError:
                drift.append(name + ":unreadable")
    expected_directories = baseline["directories"]
    for name in REQUIRED_DIRS:
        if not (root / name).is_dir():
            drift.append(name + ":missing")
        elif not isinstance(expected_directories.get(name), dict):
            drift.append(name + ":unbaselined")
        else:
            try:
                current_directory = _directory_baseline(root, name)
                if current_directory != expected_directories[name]:
                    drift.append(name + ":changed")
            except OSError:
                drift.append(name + ":unreadable")
    if missing or placeholders:
        for name in placeholders:
            marker = name + ":placeholder"
            if marker not in drift:
                drift.append(marker)
    result["drift"] = drift
    result["state"] = DRIFTED if drift else GOVERNED
    return result


def _data_dir(*, prepare: bool = True) -> Path:
    # The explicit override is useful for tests. Installed hooks receive the
    # authoritative PLUGIN_DATA path, which is recorded locally so the standalone
    # CLI can inspect the same ledger outside a hook process. Read-only consumers
    # disable preparation so inspection never repairs permissions or creates state.
    override = os.environ.get("ACGM_CODEX_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    plugin_data = os.environ.get("PLUGIN_DATA")
    locator = Path.home() / ".codex" / "acgm-codex" / "data-location.json"
    if plugin_data:
        path = Path(plugin_data).expanduser().resolve()
        if prepare:
            try:
                locator.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                os.chmod(locator.parent, 0o700)
                expected = {"schema": DATA_LOCATION_SCHEMA, "path": str(path)}
                current: dict[str, Any] = {}
                locator_is_symlink = locator.is_symlink()
                if locator.exists() and not locator_is_symlink:
                    try:
                        current = _safe_read_json(locator)
                    except RuntimeProblem:
                        current = {}
                if current != expected or locator_is_symlink:
                    _atomic_json(locator, expected, mode=0o600)
                else:
                    os.chmod(locator, 0o600)
            except OSError:
                # The Hook can still use its official data path. A later standalone
                # doctor will remain unhealthy until the locator can be written.
                pass
        return path
    if locator.exists() or locator.is_symlink():
        if locator.is_symlink():
            raise RuntimeProblem("the plugin data locator must not be a symlink")
        value = _safe_read_json(locator)
        raw = value.get("path")
        if value.get("schema") != DATA_LOCATION_SCHEMA or not isinstance(raw, str):
            raise RuntimeProblem("the plugin data locator is invalid")
        if prepare:
            os.chmod(locator.parent, 0o700)
            os.chmod(locator, 0o600)
        return Path(raw).expanduser().resolve()
    return Path.home() / ".codex" / "plugins" / "data" / "acgm-codex"


def _ensure_data_dir() -> Path:
    if not _supported_platform() or fcntl is None:
        raise RuntimeProblem("the activity ledger is supported only on macOS and Linux")
    path = _data_dir()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def _read_key_file(path: Path) -> bytes:
    try:
        key = path.read_bytes()
    except OSError as exc:
        raise RuntimeProblem("the activity ledger key is unreadable") from exc
    if len(key) < 32:
        raise RuntimeProblem("the activity ledger key is invalid")
    return key


def _secret_key() -> bytes:
    directory = _ensure_data_dir()
    path = directory / "hmac.key"
    ledger = directory / "events.jsonl"
    lock_path = directory / "hmac.key.lock"
    lock_descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        if not path.exists() and ledger.exists() and ledger.stat().st_size > 0:
            raise RuntimeProblem(
                "the activity ledger key is missing; preserve the ledger and key "
                "together or move both aside before starting a new audit epoch"
            )
        if not path.exists():
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(secrets.token_bytes(32))
                handle.flush()
                os.fsync(handle.fileno())
        os.chmod(path, 0o600)
        return _read_key_file(path)
    finally:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)


def _opaque(label: str, raw: Any) -> str:
    message = f"{label}\0{raw if raw not in (None, '') else 'none'}".encode(
        "utf-8", "surrogatepass"
    )
    return hmac.new(_secret_key(), message, hashlib.sha256).hexdigest()[:24]


def _read_secret_key() -> bytes:
    directory = _data_dir(prepare=False)
    path = directory / "hmac.key"
    ledger = directory / "events.jsonl"
    if not path.exists():
        if ledger.exists() and ledger.stat().st_size > 0:
            raise RuntimeProblem(
                "the activity ledger key is missing; preserve the ledger and key "
                "together or move both aside before starting a new audit epoch"
            )
        raise RuntimeProblem("the activity ledger key is missing")
    return _read_key_file(path)


def _opaque_readonly(label: str, raw: Any) -> str:
    message = f"{label}\0{raw if raw not in (None, '') else 'none'}".encode(
        "utf-8", "surrogatepass"
    )
    return hmac.new(_read_secret_key(), message, hashlib.sha256).hexdigest()[:24]


def _ledger_path() -> Path:
    return _ensure_data_dir() / "events.jsonl"


def _read_ledger_path() -> Path:
    if not _supported_platform() or fcntl is None:
        raise RuntimeProblem("the activity ledger is supported only on macOS and Linux")
    return _data_dir(prepare=False) / "events.jsonl"


def _event_value(
    kind: str,
    root: Path,
    session: Any = None,
    turn: Any = None,
    *,
    category: str = "none",
    outcome: str = "observed",
    state: Optional[str] = None,
    ref_id: Optional[str] = None,
    target_id: Optional[str] = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema": LEDGER_SCHEMA,
        "version": VERSION,
        "event_id": secrets.token_hex(12),
        "ts": int(time.time()),
        "kind": kind,
        "project_id": _opaque("project", str(root.resolve())),
        "session_id": _opaque("session", session),
        "turn_id": _opaque("turn", turn),
        "category": category,
        "outcome": outcome,
        "state": state or _project_status(root)["state"],
    }
    if ref_id:
        event["ref_id"] = ref_id
    if target_id:
        event["target_id"] = target_id
    try:
        adapter = _safe_read_json(_state_path(root))
        activation_id = adapter.get("activation_id")
        if adapter.get("active") is True and isinstance(activation_id, str):
            event["activation_id"] = activation_id
    except RuntimeProblem:
        pass
    return event


def _read_event_stream(handle: Any) -> list[dict[str, Any]]:
    handle.seek(0)
    events: list[dict[str, Any]] = []
    for line in handle:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeProblem("the activity ledger contains invalid JSON") from exc
        if not isinstance(value, dict) or value.get("schema") != LEDGER_SCHEMA:
            raise RuntimeProblem("the activity ledger contains an unknown record")
        events.append(value)
    return events


def _append_locked(handle: Any, event: dict[str, Any]) -> None:
    handle.seek(0, os.SEEK_END)
    handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _append_event(
    kind: str,
    root: Path,
    session: Any = None,
    turn: Any = None,
    *,
    category: str = "none",
    outcome: str = "observed",
    state: Optional[str] = None,
    ref_id: Optional[str] = None,
    target_id: Optional[str] = None,
) -> dict[str, Any]:
    event = _event_value(
        kind,
        root,
        session,
        turn,
        category=category,
        outcome=outcome,
        state=state,
        ref_id=ref_id,
        target_id=target_id,
    )
    path = _ledger_path()
    descriptor = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.chmod(path, 0o600)
        with os.fdopen(descriptor, "r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            _append_locked(handle, event)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        # fdopen owns the descriptor; do not attempt a second close here.
        raise
    return event


def _append_first_activation_heartbeat(
    root: Path,
    session: Any,
    turn: Any,
    *,
    category: str,
    state: str,
) -> Optional[dict[str, Any]]:
    event = _event_value(
        "hook-heartbeat",
        root,
        session,
        turn,
        category=category,
        outcome="observed",
        state=state,
    )
    activation_id = event.get("activation_id")
    if not isinstance(activation_id, str):
        return None
    path = _ledger_path()
    descriptor = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.chmod(path, 0o600)
        with os.fdopen(descriptor, "r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            events = _read_event_stream(handle)
            exists = any(
                item.get("kind") == "hook-heartbeat"
                and item.get("project_id") == event.get("project_id")
                and item.get("version") == VERSION
                and item.get("activation_id") == activation_id
                for item in events
            )
            if not exists:
                _append_locked(handle, event)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return None if exists else event
    except Exception:
        raise


def _read_events() -> list[dict[str, Any]]:
    path = _read_ledger_path()
    if not path.exists():
        return []
    descriptor = os.open(path, os.O_RDONLY)
    with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        events = _read_event_stream(handle)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return events


def _event_scope(root: Path, payload: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _opaque("project", str(root.resolve())),
        _opaque("session", payload.get("session_id")),
        _opaque("turn", payload.get("turn_id")),
    )


def _scoped_events(root: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    project_id, session_id, turn_id = _event_scope(root, payload)
    return [
        event
        for event in _read_events()
        if event.get("project_id") == project_id
        and event.get("session_id") == session_id
        and event.get("turn_id") == turn_id
    ]


def _session_events(root: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    project_id, session_id, _ = _event_scope(root, payload)
    return [
        event
        for event in _read_events()
        if event.get("project_id") == project_id and event.get("session_id") == session_id
    ]


def _command_from(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    return command if isinstance(command, str) else ""


def _risk_category(command: str) -> Optional[str]:
    tokens = _tokens_if_independent(command)
    if tokens:
        executable = Path(tokens[0]).name
        if executable == "rm":
            options = tokens[1:]
            recursive = "--recursive" in options or any(
                token.startswith("-")
                and not token.startswith("--")
                and "r" in token[1:].lower()
                for token in options
            )
            force = "--force" in options or any(
                token.startswith("-")
                and not token.startswith("--")
                and "f" in token[1:].lower()
                for token in options
            )
            if recursive and force:
                return "recursive-delete"
        if executable == "git":
            index = 1
            while index < len(tokens) and tokens[index] == "-C" and index + 1 < len(tokens):
                index += 2
            if index < len(tokens):
                verb = tokens[index]
                options = tokens[index + 1 :]
                if verb == "reset" and "--hard" in options:
                    return "git-reset-hard"
                if verb == "clean":
                    force = "--force" in options or any(
                        token.startswith("-")
                        and not token.startswith("--")
                        and "f" in token[1:].lower()
                        for token in options
                    )
                    directories = "--directories" in options or any(
                        token.startswith("-")
                        and not token.startswith("--")
                        and "d" in token[1:].lower()
                        for token in options
                    )
                    if force and directories:
                        return "git-clean-force"
                if verb == "branch" and (
                    "-D" in options
                    or ("--delete" in options and "--force" in options)
                ):
                    return "git-branch-delete"
                if verb == "push" and (
                    "-f" in options
                    or "--force" in options
                    or any(token.startswith("--force-with-lease=") for token in options)
                    or "--force-with-lease" in options
                ):
                    return "git-force-push"
    patterns = (
        (r"(?:^|[;&|]\s*|\s)(?:\S*/)?git(?:\s+-C\s+\S+)?\s+reset\s+--hard(?:\s|$)", "git-reset-hard"),
        (
            r"(?:^|[;&|]\s*|\s)(?:\S*/)?git(?:\s+-C\s+\S+)?\s+clean\s+"
            r"(?=[^\n]*(?:-[A-Za-z]*f|--force\b))"
            r"(?=[^\n]*(?:-[A-Za-z]*d|--directories\b))",
            "git-clean-force",
        ),
        (
            r"(?:^|[;&|]\s*|\s)(?:\S*/)?git(?:\s+-C\s+\S+)?\s+branch\s+"
            r"(?:-D\b|(?=[^\n]*--delete\b)(?=[^\n]*--force\b))",
            "git-branch-delete",
        ),
        (
            r"(?:^|[;&|]\s*|\s)(?:\S*/)?git(?:\s+-C\s+\S+)?\s+push\b[^\n]*"
            r"(?:--force(?:-with-lease(?:=\S+)?)?(?=\s|$)|(?:^|\s)-f(?:\s|$))",
            "git-force-push",
        ),
        (r"(?:^|[;&|]\s*|\s)(?:\S*/)?rm\s+(?:-[A-Za-z]*r[A-Za-z]*f|-[A-Za-z]*f[A-Za-z]*r)(?:\s|$)", "recursive-delete"),
        (r"(?:^|[;&|]\s*|\s)(?:\S*/)?rm\s+(?=[^\n]*--recursive\b)(?=[^\n]*--force\b)", "recursive-delete"),
        (r"(?:^|[;&|]\s*|\s)(?:\S*/)?rm\s+-r\s+-f(?:\s|$)", "recursive-delete"),
        (r"(?:^|[;&|]\s*|\s)(?:\S*/)?rm\s+-f\s+-r(?:\s|$)", "recursive-delete"),
    )
    for pattern_text, category in patterns:
        if re.search(pattern_text, command, re.IGNORECASE):
            return category
    return None


def _shell_segments(command: str) -> Optional[list[list[str]]]:
    """Tokenize shell words and keep control-separated commands independent."""

    try:
        lexer = shlex.shlex(
            command.replace("\n", " ; "),
            posix=True,
            punctuation_chars=";&|<>",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in {";", "&", "&&", "|", "||"}:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _constitution_operand(value: str) -> bool:
    """Return whether one literal shell operand names the protected file."""

    return Path(value).name.lower() == "constitution.md"


def _short_option_has(option: str, flag: str) -> bool:
    return bool(
        option.startswith("-")
        and not option.startswith("--")
        and flag in option[1:]
    )


def _in_place_option(executable: str, option: str) -> bool:
    if option == "--in-place" or option.startswith("--in-place="):
        return True
    if executable == "sed":
        return bool(re.match(r"^-[Enru]*i", option))
    return bool(re.match(r"^-[0-9pnlwa]*i", option))


def _in_place_targets(executable: str, arguments: list[str]) -> list[str]:
    """Separate sed/perl program operands from files changed in place."""

    targets: list[str] = []
    program_supplied = False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            remainder = arguments[index + 1 :]
            if not program_supplied and remainder:
                remainder = remainder[1:]
            targets.extend(remainder)
            break
        if executable == "sed":
            if argument in {"-e", "--expression", "-f", "--file"}:
                program_supplied = True
                index += 2
                continue
            if (
                argument.startswith("--expression=")
                or argument.startswith("--file=")
                or (len(argument) > 2 and argument[:2] in {"-e", "-f"})
            ):
                program_supplied = True
                index += 1
                continue
        else:
            if argument in {"-e", "-E"}:
                program_supplied = True
                index += 2
                continue
            if len(argument) > 2 and argument[:2] in {"-e", "-E"}:
                program_supplied = True
                index += 1
                continue
            if argument in {"-I", "-M", "-m"}:
                index += 2
                continue
        if argument.startswith("-"):
            index += 1
            continue
        if not program_supplied:
            program_supplied = True
        else:
            targets.append(argument)
        index += 1
    return targets


def _segment_writes_constitution(tokens: list[str], *, depth: int = 0) -> bool:
    """Bind one supported writer and its literal target within one shell segment."""

    if depth > 4:
        return False
    for index, token in enumerate(tokens[:-1]):
        if token in {">", ">>", ">|", "<>", "&>", "&>>"} and _constitution_operand(
            tokens[index + 1]
        ):
            return True

    index = 0
    while index < len(tokens) and re.match(
        r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[index]
    ):
        index += 1
    if index >= len(tokens):
        return False
    executable = Path(tokens[index]).name.lower()
    arguments = tokens[index + 1 :]

    if executable in {"sh", "bash", "dash", "ksh", "zsh"}:
        for option_index, argument in enumerate(arguments[:-1]):
            if argument == "-c" or _short_option_has(argument, "c"):
                nested = _shell_segments(arguments[option_index + 1])
                return bool(
                    nested
                    and any(
                        _segment_writes_constitution(segment, depth=depth + 1)
                        for segment in nested
                    )
                )
        return False

    if executable in {"command", "builtin", "exec", "sudo"}:
        nested_index = 0
        while nested_index < len(arguments) and arguments[nested_index].startswith("-"):
            if arguments[nested_index] == "--":
                nested_index += 1
                break
            if arguments[nested_index] in {"-a", "-C", "-g", "-h", "-p", "-u"}:
                nested_index += 2
            else:
                nested_index += 1
        return bool(
            nested_index < len(arguments)
            and _segment_writes_constitution(
                arguments[nested_index:], depth=depth + 1
            )
        )

    if executable == "env":
        nested_index = 0
        while nested_index < len(arguments):
            argument = arguments[nested_index]
            if argument == "--":
                nested_index += 1
                break
            if argument in {"-u", "--unset", "-C", "--chdir"}:
                nested_index += 2
                continue
            if argument.startswith("-") or re.match(
                r"^[A-Za-z_][A-Za-z0-9_]*=", argument
            ):
                nested_index += 1
                continue
            break
        return bool(
            nested_index < len(arguments)
            and _segment_writes_constitution(
                arguments[nested_index:], depth=depth + 1
            )
        )

    if executable in {"rm", "mv", "tee", "truncate", "touch", "chmod", "chown"}:
        return any(_constitution_operand(argument) for argument in arguments)

    if executable in {"cp", "install"}:
        if any(
            argument.startswith("--target-directory=")
            and _constitution_operand(argument.split("=", 1)[1])
            for argument in arguments
        ):
            return True
        for option_index, argument in enumerate(arguments[:-1]):
            if argument in {"-t", "--target-directory"} and _constitution_operand(
                arguments[option_index + 1]
            ):
                return True
        if executable == "install" and any(
            argument in {"-d", "--directory"} for argument in arguments
        ):
            return any(_constitution_operand(argument) for argument in arguments)
        literal_arguments = [
            argument
            for argument in arguments
            if argument == "-" or not argument.startswith("-")
        ]
        return bool(
            len(literal_arguments) >= 2
            and _constitution_operand(literal_arguments[-1])
        )

    if executable in {"sed", "perl"}:
        in_place = any(
            _in_place_option(executable, argument)
            for argument in arguments
        )
        return bool(
            in_place
            and any(
                _constitution_operand(argument)
                for argument in _in_place_targets(executable, arguments)
            )
        )

    if executable == "git":
        verb_index = 0
        while verb_index < len(arguments):
            argument = arguments[verb_index]
            if argument == "-C" and verb_index + 1 < len(arguments):
                verb_index += 2
                continue
            if argument.startswith("-"):
                verb_index += 1
                continue
            break
        if verb_index < len(arguments):
            verb = arguments[verb_index]
            operands = arguments[verb_index + 1 :]
            if verb in {"restore", "checkout"}:
                return any(_constitution_operand(argument) for argument in operands)

    if executable == "dd":
        return any(
            argument.startswith("of=")
            and _constitution_operand(argument.split("=", 1)[1])
            for argument in arguments
        )

    if "export-case" in arguments:
        for option_index, argument in enumerate(arguments):
            if argument.startswith("--output=") and _constitution_operand(
                argument.split("=", 1)[1]
            ):
                return True
            if (
                argument in {"-o", "--output"}
                and option_index + 1 < len(arguments)
                and _constitution_operand(arguments[option_index + 1])
            ):
                return True
    return False


def _constitution_write(
    tool_name: str, command: str, payload: Optional[dict[str, Any]] = None
) -> bool:
    if tool_name in {"Edit", "Write"}:
        tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
        if not isinstance(tool_input, dict):
            return False
        for key in ("file_path", "path", "filename"):
            value = tool_input.get(key)
            if isinstance(value, str) and Path(value).name.lower() == "constitution.md":
                return True
        return False
    if tool_name == "apply_patch":
        for line in command.splitlines():
            match = re.match(
                r"^\*\*\*\s+(?:Add|Update|Delete)\s+File:\s*(.+?)\s*$", line
            )
            if match and Path(match.group(1)).name.lower() == "constitution.md":
                return True
            move = re.match(r"^\*\*\*\s+Move\s+to:\s*(.+?)\s*$", line, re.IGNORECASE)
            if move and Path(move.group(1)).name.lower() == "constitution.md":
                return True
        return False
    if tool_name != "Bash":
        return False
    segments = _shell_segments(command)
    return bool(
        segments
        and any(_segment_writes_constitution(segment) for segment in segments)
    )


def _tokens_if_independent(command: str) -> Optional[list[str]]:
    # Gate target binding accepts only one literal shell command. Reject shell
    # expansion, globbing, comments, grouping, and control operators rather
    # than pretending their runtime target can be reconstructed statically.
    if not command.strip() or re.search(
        r"(?:\n|[;&|<>`$~*?\[\]{}()#!])", command
    ):
        return None
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    return tokens or None


def _payload_cwd(root: Path, payload: dict[str, Any]) -> Path:
    raw = payload.get("cwd")
    candidate = Path(raw).expanduser() if isinstance(raw, str) and raw else root
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve()
    except OSError:
        return root.resolve()


def _command_target_id(
    root: Path, payload: dict[str, Any], command: str
) -> Optional[str]:
    """Return a privacy-preserving target binding for simple standalone commands.

    Compound shell commands are deliberately unarmable because their effective
    working directory cannot be reconstructed reliably without executing a shell.
    """

    tokens = _tokens_if_independent(command)
    if not tokens:
        return None
    executable = Path(tokens[0]).name
    cwd = _payload_cwd(root, payload)
    target = cwd
    if executable == "git":
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if token == "-C" and index + 1 < len(tokens):
                path = Path(tokens[index + 1]).expanduser()
                target = (target / path).resolve() if not path.is_absolute() else path.resolve()
                index += 2
                continue
            if token.startswith("--work-tree=") or token.startswith("--git-dir="):
                path = Path(token.split("=", 1)[1]).expanduser()
                target = (target / path).resolve() if not path.is_absolute() else path.resolve()
                index += 1
                continue
            break
    elif executable == "rm":
        operands = [token for token in tokens[1:] if not token.startswith("-")]
        if not operands:
            return None
        parents = {
            str(
                ((cwd / Path(operand)).resolve() if not Path(operand).is_absolute() else Path(operand).resolve()).parent
            )
            for operand in operands
        }
        if len(parents) != 1:
            return None
        target = Path(next(iter(parents)))
    elif executable in {"ls", "tree"}:
        # Reject option forms whose following value is ambiguous; simple flag
        # clusters such as `ls -la /path` remain supported.
        value_options = {"-L", "--max-depth", "--filelimit", "--block-size"}
        if any(token in value_options for token in tokens[1:]):
            return None
        operands = [token for token in tokens[1:] if not token.startswith("-")]
        if len(operands) > 1:
            return None
        if operands:
            path = Path(operands[0]).expanduser()
            target = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
    elif executable == "find":
        operands: list[str] = []
        for token in tokens[1:]:
            if token.startswith("-") or token in {"!", "("}:
                break
            operands.append(token)
        if len(operands) > 1:
            return None
        if operands:
            path = Path(operands[0]).expanduser()
            target = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
    elif executable != "pwd":
        return None
    return _opaque("target", str(target))


def _gate_request(command: str, operation: str) -> Optional[dict[str, str]]:
    tokens = _tokens_if_independent(command)
    if not tokens:
        return None
    try:
        gate_index = tokens.index("gate")
    except ValueError:
        return None
    if gate_index + 1 >= len(tokens) or tokens[gate_index + 1] != operation:
        return None
    prefix = tokens[:gate_index]
    if not prefix:
        return None
    names = {Path(token).name for token in prefix}
    if "acgm-codex" not in names and "acgm_codex.py" not in names:
        return None
    values: dict[str, str] = {}
    arguments = tokens[gate_index + 2 :]
    index = 0
    allowed = {"--category", "--event", "--target"}
    while index < len(arguments):
        flag = arguments[index]
        if flag not in allowed or flag in values or index + 1 >= len(arguments):
            return None
        values[flag] = arguments[index + 1]
        index += 2
    if values.get("--category") not in GATE_CATEGORIES or not values.get("--event"):
        return None
    return {
        "category": values["--category"],
        "event": values["--event"],
        "target": values.get("--target", ""),
    }


def _requested_target_id(root: Path, payload: dict[str, Any], raw: str) -> str:
    base = _payload_cwd(root, payload)
    path = Path(raw) if raw else base
    target = (base / path).resolve() if not path.is_absolute() else path.resolve()
    return _opaque("target", str(target))


def _consume_active_arm(
    root: Path,
    payload: dict[str, Any],
    category: str,
    target_id: Optional[str],
) -> Optional[dict[str, Any]]:
    """Atomically consume one current-session arm for a matching denial."""

    if target_id is None:
        return None
    adapter = _safe_read_json(_state_path(root))
    activation_id = adapter.get("activation_id")
    if not isinstance(activation_id, str):
        return None
    project_id, session_id, turn_id = _event_scope(root, payload)
    consumed = _event_value(
        "gate-consumed",
        root,
        payload.get("session_id"),
        payload.get("turn_id"),
        category=category,
        outcome="allowed-retry",
        state=GOVERNED,
        target_id=target_id,
    )
    path = _ledger_path()
    descriptor = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        events = _read_event_stream(handle)
        denials = [
            event
            for event in events
            if event.get("project_id") == project_id
            and event.get("session_id") == session_id
            and event.get("turn_id") == turn_id
            and event.get("kind") == "gate-denied"
            and event.get("category") == category
            and event.get("target_id") == target_id
        ]
        now = int(time.time())
        selected: Optional[dict[str, Any]] = None
        for denial in reversed(denials):
            denial_id = denial.get("event_id")
            arms = [
                event
                for event in events
                if event.get("project_id") == project_id
                and event.get("kind") == "gate-armed"
                and event.get("ref_id") == denial_id
                and event.get("category") == category
                and event.get("target_id") == target_id
                and event.get("version") == VERSION
                and event.get("activation_id") == activation_id
                and now - int(event.get("ts", 0)) <= GATE_TTL_SECONDS
            ]
            for arm in reversed(arms):
                if not any(
                    event.get("kind") == "gate-consumed"
                    and event.get("ref_id") == arm.get("event_id")
                    for event in events
                ):
                    selected = arm
                    break
            if selected:
                break
        if selected is None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return None
        consumed["ref_id"] = str(selected["event_id"])
        _append_locked(handle, consumed)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return consumed


def _open_obligations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    opened = [event for event in events if event.get("kind") == "obligation-opened"]
    closed_refs = {
        event.get("ref_id")
        for event in events
        if event.get("kind")
        in {"obligation-check-observed", "obligation-unresolved", "event-resolution"}
    }
    return [event for event in opened if event.get("event_id") not in closed_refs]


def _open_session_obligations(
    root: Path, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    _, session_id, _ = _event_scope(root, payload)
    return [
        event
        for event in _open_obligations(_project_events(root))
        if event.get("session_id") == session_id
    ]


def _json_output(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _hook_context(event_name: str, text: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    }


def _deny_pretool(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _hook_session_like(
    dispatch: str, root: Path, payload: dict[str, Any], status: dict[str, Any]
) -> dict[str, Any]:
    official = HOOK_NAMES[dispatch]
    root_note = f" ACGM resolved the actual project root as `{root}`."
    unresolved = _open_obligations(_project_events(root))
    obligation_note = (
        f" {len(unresolved)} earlier verification obligation(s) remain unresolved; "
        "run `acgm-codex report`."
        if unresolved
        else ""
    )
    if status["state"] == GOVERNED:
        return _hook_context(
            official,
            "ACGM Codex is active. Read CONSTITUTION.md, AGENTS.md, and "
            ".governance/scope.yml before consequential changes."
            + root_note
            + obligation_note,
        )
    if status["state"] in {DRIFTED, BROKEN}:
        result = _hook_context(
            official,
            "ACGM Codex detected governance drift. Run `acgm-codex doctor --strict` "
            "and repair or reactivate before relying on enforcement."
            + root_note
            + obligation_note,
        )
        result["systemMessage"] = "ACGM Codex governance is drifted or broken."
        return result
    return _hook_context(
        official,
        "ACGM Codex is installed but not active for this project. Run "
        "`acgm-codex init`, review the assets, then run `acgm-codex activate`."
        + root_note
        + obligation_note,
    )


def _hook_pretool(root: Path, payload: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str):
        tool_name = ""
    command = _command_from(payload)
    session = payload.get("session_id")
    turn = payload.get("turn_id")

    if _state_path(root).exists() and _constitution_write(tool_name, command, payload):
        _append_event(
            "constitution-write-denied",
            root,
            session,
            turn,
            category="constitution-write",
            outcome="denied",
            state=status["state"],
        )
        return _deny_pretool(
            "ACGM blocks automated changes to CONSTITUTION.md. Prepare a proposal "
            "for explicit human review instead."
        )

    if status["state"] != GOVERNED:
        return {}

    if tool_name != "Bash":
        return {}

    arm_request = _gate_request(command, "arm")
    if arm_request:
        events = _scoped_events(root, payload)
        target_id = _requested_target_id(root, payload, arm_request["target"])
        source = next(
            (
                event
                for event in events
                if event.get("event_id") == arm_request["event"]
                and event.get("kind") == "gate-denied"
                and event.get("category") == arm_request["category"]
                and event.get("target_id") == target_id
            ),
            None,
        )
        if source is not None:
            _append_event(
                "gate-arm-requested",
                root,
                session,
                turn,
                category=arm_request["category"],
                outcome="fixed-check-required",
                state=GOVERNED,
                ref_id=str(source["event_id"]),
                target_id=target_id,
            )
            return {
                "systemMessage": "ACGM accepted the gate-arm request. The CLI will "
                "now run a fixed, non-shell read-only check; only its zero exit status "
                "can arm one retry."
            }
        _append_event(
            "gate-arm-rejected",
            root,
            session,
            turn,
            category=arm_request["category"],
            outcome="rejected",
            state=GOVERNED,
        )
        return {
            "systemMessage": "ACGM rejected the gate-arm request: its event, category, "
            "target, or current-turn scope did not match the denial."
        }

    verify_request = _gate_request(command, "verify")
    if verify_request:
        target_id = _requested_target_id(root, payload, verify_request["target"])
        source = next(
            (
                event
                for event in _open_session_obligations(root, payload)
                if event.get("event_id") == verify_request["event"]
                and event.get("category") == verify_request["category"]
                and event.get("target_id") == target_id
            ),
            None,
        )
        if source is not None:
            _append_event(
                "gate-verify-requested",
                root,
                session,
                turn,
                category=verify_request["category"],
                outcome="fixed-check-required",
                state=GOVERNED,
                ref_id=str(source["event_id"]),
                target_id=target_id,
            )
            return {
                "systemMessage": "ACGM accepted the verification request. The CLI "
                "will now run a fixed, non-shell read-only check."
            }
        _append_event(
            "gate-verify-rejected",
            root,
            session,
            turn,
            category=verify_request["category"],
            outcome="rejected",
            state=GOVERNED,
        )
        return {
            "systemMessage": "ACGM rejected the verification request: its event, "
            "category, target, or session scope did not match an open obligation."
        }

    category = _risk_category(command)
    if not category:
        return {}
    target_id = _command_target_id(root, payload, command)
    if _consume_active_arm(root, payload, category, target_id):
        return {
            "systemMessage": "ACGM consumed the one-time gate for "
            f"{category}. This does not constitute user authorization and Codex's "
            "normal permission checks still apply. Verify the result afterward."
        }
    denial = _append_event(
        "gate-denied",
        root,
        session,
        turn,
        category=category,
        outcome="denied",
        state=GOVERNED,
        target_id=target_id,
    )
    if target_id is None:
        return _deny_pretool(
            f"ACGM denied high-risk category {category}. This command uses a compound, "
            "expanded, or ambiguous target form and cannot be armed. Use a literal "
            "standalone command or a safer non-destructive alternative."
        )
    return _deny_pretool(
        f"ACGM denied high-risk category {category}. Run `{_cli_launcher()} gate arm "
        f"--event {denial['event_id']} --category {category}` before one retry. "
        "If the action targets a directory other than the current one, append "
        "`--target <that-directory>`. The CLI performs its own fixed read-only check; "
        "an arm is not user authorization."
    )


def _hook_posttool(root: Path, payload: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    if status["state"] != GOVERNED or payload.get("tool_name") != "Bash":
        return {}
    command = _command_from(payload)
    session = payload.get("session_id")
    turn = payload.get("turn_id")
    events = _scoped_events(root, payload)
    category = _risk_category(command)
    if category:
        target_id = _command_target_id(root, payload, command)
        consume_index = -1
        for index, event in enumerate(events):
            if (
                event.get("kind") == "gate-consumed"
                and event.get("category") == category
                and event.get("target_id") == target_id
            ):
                consume_index = index
        already_opened = any(
            event.get("kind") == "obligation-opened"
            and event.get("category") == category
            and event.get("target_id") == target_id
            for event in events[consume_index + 1 :]
        ) if consume_index >= 0 else True
        if consume_index >= 0 and not already_opened:
            obligation = _append_event(
                "obligation-opened",
                root,
                session,
                turn,
                category=category,
                outcome="verification-required",
                state=GOVERNED,
                target_id=target_id,
            )
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "ACGM opened a verification obligation for "
                    f"{category}. Run `{_cli_launcher()} gate verify --event "
                    f"{obligation['event_id']} --category {category}` before stopping. "
                    "Append `--target <that-directory>` when the action targeted a "
                    "directory other than the current one.",
                }
            }
    return {}


def _hook_permission(
    root: Path, payload: dict[str, Any], status: dict[str, Any]
) -> dict[str, Any]:
    command = _command_from(payload)
    _append_event(
        "permission-boundary-observed",
        root,
        payload.get("session_id"),
        payload.get("turn_id"),
        category=_risk_category(command) or "codex-permission",
        outcome="left-to-codex",
        state=status["state"],
        target_id=_command_target_id(root, payload, command) if command else None,
    )
    return {}


def _hook_stop(root: Path, payload: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    if status["state"] != GOVERNED:
        return {}
    session = payload.get("session_id")
    turn = payload.get("turn_id")
    events = _session_events(root, payload)
    obligations = _open_session_obligations(root, payload)
    if not obligations:
        return {}
    stop_active = payload.get("stop_hook_active") is True
    blocked_refs = {
        event.get("ref_id") for event in events if event.get("kind") == "stop-blocked"
    }
    already_blocked = any(event.get("event_id") in blocked_refs for event in obligations)
    if not stop_active and not already_blocked:
        for obligation in obligations:
            _append_event(
                "stop-blocked",
                root,
                session,
                turn,
                category=str(obligation.get("category")),
                outcome="continued-once",
                state=GOVERNED,
                ref_id=str(obligation.get("event_id")),
            )
        categories = ", ".join(sorted({str(item.get("category")) for item in obligations}))
        return {
            "decision": "block",
            "reason": "ACGM verification is still required for: "
            f"{categories}. Run a matching independent read-only check, then finish."
        }
    for obligation in obligations:
        _append_event(
            "obligation-unresolved",
            root,
            session,
            turn,
            category=str(obligation.get("category")),
            outcome="released-to-avoid-loop",
            state=GOVERNED,
            ref_id=str(obligation.get("event_id")),
        )
    return {
        "systemMessage": "ACGM released an unresolved verification obligation to "
        "avoid a Stop-hook loop; review the activity report."
    }


def _run_hook(dispatch: str, project: Optional[str]) -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be an object")
    except (json.JSONDecodeError, ValueError):
        try:
            root = _project_root(project)
            _append_event(
                "runtime-error",
                root,
                category=dispatch,
                outcome="fail-open",
            )
        except Exception:
            pass
        _json_output(
            {
                "systemMessage": "ACGM Codex received invalid hook input and failed "
                "open; enforcement was not applied."
            }
        )
        return 0
    try:
        payload_cwd = payload.get("cwd")
        target = (
            payload_cwd
            if project is None and isinstance(payload_cwd, str) and payload_cwd
            else project
        )
        try:
            root = _project_root(target)
        except AmbiguousWorkspace:
            official = HOOK_NAMES[dispatch]
            text = (
                "ACGM detected a multi-repository workspace and did not choose or "
                "modify a project. Open the intended repository directly or pass its "
                "exact path to `acgm-codex`."
            )
            result = _hook_context(official, text)
            if dispatch not in {"session-start", "subagent-start"}:
                result["systemMessage"] = text
            _json_output(result)
            return 0
        if not _supported_platform():
            raise RuntimeProblem("unsupported platform")
        status = _project_status(root)
        if dispatch in {"session-start", "subagent-start"}:
            result = _hook_session_like(dispatch, root, payload, status)
        elif dispatch == "pre-tool":
            result = _hook_pretool(root, payload, status)
        elif dispatch == "post-tool":
            result = _hook_posttool(root, payload, status)
        elif dispatch == "permission-request":
            result = _hook_permission(root, payload, status)
        elif dispatch == "pre-compact":
            result = {
                "systemMessage": "ACGM recorded the pre-compaction heartbeat. Re-ground "
                "from current project files after compaction."
            } if status["state"] == GOVERNED else {}
        elif dispatch == "stop":
            result = _hook_stop(root, payload, status)
        else:
            result = {}
        lifecycle_heartbeat = dispatch in {
            "session-start",
            "subagent-start",
            "pre-compact",
        }
        if lifecycle_heartbeat:
            _append_event(
                "hook-heartbeat",
                root,
                payload.get("session_id"),
                payload.get("turn_id"),
                category=dispatch,
                outcome="observed",
                state=status["state"],
            )
        elif status["state"] == GOVERNED:
            _append_first_activation_heartbeat(
                root,
                payload.get("session_id"),
                payload.get("turn_id"),
                category=dispatch,
                state=status["state"],
            )
        _json_output(result)
        return 0
    except Exception:
        try:
            _append_event(
                "runtime-error",
                root,
                payload.get("session_id"),
                payload.get("turn_id"),
                category=dispatch,
                outcome="fail-open",
            )
        except Exception:
            pass
        _json_output(
            {
                "systemMessage": "ACGM Codex encountered an internal error and failed "
                "open; enforcement was not applied. Run `acgm-codex doctor`."
            }
        )
        return 0


def _quickstart_worktree_digest(root: Path, status_output: str) -> str:
    digest = hashlib.sha256()
    digest.update(b"status\0")
    digest.update(status_output.encode("utf-8", "surrogatepass"))
    for label, arguments in (
        (b"index\0", ("diff", "--cached", "--binary", "--full-index", "--no-ext-diff")),
        (b"worktree\0", ("diff", "--binary", "--full-index", "--no-ext-diff")),
    ):
        result = _git_probe(root, *arguments)
        if result.returncode != 0:
            raise RuntimeProblem("quickstart could not fingerprint the target Git state")
        digest.update(label)
        digest.update(result.stdout.encode("utf-8", "surrogatepass"))
    untracked = _git_probe(root, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        raise RuntimeProblem("quickstart could not fingerprint untracked project files")
    for raw_name in sorted(name for name in untracked.stdout.split("\0") if name):
        relative = Path(raw_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeProblem("quickstart received an unsafe untracked Git path")
        path = root / relative
        digest.update(b"untracked\0")
        digest.update(raw_name.encode("utf-8", "surrogatepass"))
        digest.update(b"\0")
        try:
            if path.is_symlink():
                digest.update(b"symlink\0")
                digest.update(os.readlink(path).encode("utf-8", "surrogatepass"))
            elif path.is_file():
                digest.update(b"file\0")
                digest.update(_sha256(path).encode("ascii"))
            else:
                digest.update(b"nonregular\0")
        except OSError as exc:
            raise RuntimeProblem(
                "quickstart could not fingerprint an untracked project file"
            ) from exc
    return digest.hexdigest()


def _quickstart_managed_git_path(raw_name: str) -> bool:
    name = raw_name
    if name == ".acgm" or name.startswith(".acgm/"):
        return True
    return name in {
        "CONSTITUTION.md",
        "AGENTS.md",
        ".governance/scope.yml",
        ".governance/decisions/0001-adopt-acgm-standard-v1.md",
        ".governance/snapshots/bootstrap.md",
    }


def _quickstart_git_guard(root: Path) -> dict[str, str]:
    """Fingerprint Git identity and every non-quickstart project path.

    The normal plan identity includes the files quickstart is authorized to
    create.  Those files necessarily change during apply, so the final CAS uses
    this companion guard, which excludes only the exact managed postimage and
    local `.acgm` runtime records.
    """

    head_result = _git_probe(root, "rev-parse", "--verify", "HEAD")
    head = head_result.stdout.strip() if head_result.returncode == 0 else "UNBORN"
    branch_result = _git_probe(root, "branch", "--show-current")
    if branch_result.returncode != 0:
        raise RuntimeProblem("quickstart could not inspect the target Git branch")
    common_result = _git_probe(root, "rev-parse", "--git-common-dir")
    if common_result.returncode != 0 or not common_result.stdout.strip():
        raise RuntimeProblem("quickstart could not inspect the target Git common dir")

    index = _git_probe(root, "ls-files", "--stage", "-z")
    cached = _git_probe(root, "ls-files", "--cached", "-z")
    untracked = _git_probe(
        root, "ls-files", "--others", "--exclude-standard", "-z"
    )
    status = _git_probe(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    if any(item.returncode != 0 for item in (index, cached, untracked, status)):
        raise RuntimeProblem("quickstart could not fingerprint the final Git state")

    digest = hashlib.sha256()
    worktree_names: set[str] = set()
    for record in sorted(item for item in index.stdout.split("\0") if item):
        _, separator, name = record.partition("\t")
        if not separator:
            raise RuntimeProblem("quickstart received an invalid Git index record")
        # Quickstart never changes the Git index.  Keep every staged/index
        # record in the guard, including managed paths; only their worktree
        # postimages are excluded below.
        digest.update(b"index\0")
        digest.update(record.encode("utf-8", "surrogatepass"))
        digest.update(b"\0")

    for name in cached.stdout.split("\0") + untracked.stdout.split("\0"):
        if name and not _quickstart_managed_git_path(name):
            worktree_names.add(name)
    for name in sorted(worktree_names):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeProblem("quickstart received an unsafe Git path")
        path = root / relative
        digest.update(b"worktree\0")
        digest.update(name.encode("utf-8", "surrogatepass"))
        digest.update(b"\0")
        try:
            if path.is_symlink():
                digest.update(b"symlink\0")
                digest.update(os.readlink(path).encode("utf-8", "surrogatepass"))
            elif path.is_file():
                digest.update(b"file\0")
                digest.update(_sha256(path).encode("ascii"))
            elif path.is_dir():
                digest.update(b"directory\0")
            elif path.exists():
                digest.update(b"nonregular\0")
            else:
                digest.update(b"missing\0")
        except OSError as exc:
            raise RuntimeProblem("quickstart could not fingerprint a Git path") from exc

    status_records = [item for item in status.stdout.split("\0") if item]
    index_position = 0
    while index_position < len(status_records):
        record = status_records[index_position]
        if len(record) < 3:
            raise RuntimeProblem("quickstart received an invalid Git status record")
        names = [record[3:]]
        if "R" in record[:2] or "C" in record[:2]:
            index_position += 1
            if index_position >= len(status_records):
                raise RuntimeProblem("quickstart received an invalid Git rename record")
            names.append(status_records[index_position])
        if any(not _quickstart_managed_git_path(name) for name in names):
            digest.update(b"status\0")
            digest.update(record.encode("utf-8", "surrogatepass"))
            for extra in names[1:]:
                digest.update(b"\0")
                digest.update(extra.encode("utf-8", "surrogatepass"))
            digest.update(b"\0")
        index_position += 1

    return {
        "head": head,
        "branch": branch_result.stdout.strip() or "DETACHED_OR_UNBORN",
        "git_common_dir": common_result.stdout.strip(),
        "nonmanaged_sha256": digest.hexdigest(),
    }


def _release_key(value: Any) -> Optional[tuple[int, int, int, int, int]]:
    if not isinstance(value, str) or len(value) > 64:
        return None
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?", value)
    if match is None:
        return None
    major, minor, patch, release_candidate = match.groups()
    try:
        return (
            int(major),
            int(minor),
            int(patch),
            0 if release_candidate is not None else 1,
            int(release_candidate or 0),
        )
    except ValueError:
        return None


def _compatible_state_upgrade(source_version: Any) -> bool:
    source_key = _release_key(source_version)
    current_key = _release_key(VERSION)
    return bool(
        source_version in QUICKSTART_COMPATIBLE_STATE_VERSIONS
        and source_key is not None
        and current_key is not None
        and source_key < current_key
    )


def _quickstart_git_identity(root: Path) -> dict[str, Any]:
    verified = _verified_git_root(root)
    if verified != root:
        raise RuntimeProblem("quickstart requires an explicit Git repository root")
    try:
        root_metadata = root.lstat()
    except OSError as exc:
        raise RuntimeProblem("quickstart could not inspect the target root") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeProblem("quickstart target root is not a real directory")
    head_result = _git_probe(root, "rev-parse", "--verify", "HEAD")
    head = head_result.stdout.strip() if head_result.returncode == 0 else "UNBORN"
    branch_result = _git_probe(root, "branch", "--show-current")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
    status_result = _git_probe(root, "status", "--porcelain")
    if status_result.returncode != 0:
        raise RuntimeProblem("quickstart could not inspect the target Git status")
    common_result = _git_probe(root, "rev-parse", "--git-common-dir")
    common = common_result.stdout.strip() if common_result.returncode == 0 else "unknown"
    return {
        "root": str(root),
        "root_device": root_metadata.st_dev,
        "root_inode": root_metadata.st_ino,
        "head": head,
        "branch": branch or "DETACHED_OR_UNBORN",
        "dirty": bool(status_result.stdout),
        "worktree_sha256": _quickstart_worktree_digest(root, status_result.stdout),
        "git_common_dir": common,
    }


def _quickstart_directory_entry_identity(
    root: Path, name: str
) -> Optional[dict[str, int]]:
    path = root / name
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeProblem("quickstart could not inspect a managed directory") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        return None
    return {"device": metadata.st_dev, "inode": metadata.st_ino}


def _quickstart_directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _open_quickstart_root(root: Path, identity: dict[str, Any]) -> int:
    descriptor = os.open(root, _quickstart_directory_flags())
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_dev != identity.get("root_device")
            or metadata.st_ino != identity.get("root_inode")
        ):
            raise RuntimeProblem("quickstart target root changed during apply")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _rename_quickstart_directory_noreplace(
    parent_fd: int, source: str, destination: str
) -> None:
    """Publish a prepared directory without replacing a concurrent entry.

    POSIX ``rename`` may replace an empty directory and therefore cannot uphold
    quickstart's no-overwrite contract.  The supported platforms expose an
    atomic no-replace variant; if the primitive is unavailable, quickstart
    fails closed instead of falling back to a racy check-then-rename sequence.
    """

    library = ctypes.CDLL(None, use_errno=True)
    encoded_source = os.fsencode(source)
    encoded_destination = os.fsencode(destination)
    if sys.platform == "darwin":
        function = getattr(library, "renameatx_np", None)
        flag = 0x00000004  # RENAME_EXCL from <sys/stdio.h>.
    elif sys.platform.startswith("linux"):
        function = getattr(library, "renameat2", None)
        flag = 0x00000001  # RENAME_NOREPLACE from <linux/fs.h>.
    else:
        function = None
        flag = 0
    if function is None:
        raise RuntimeProblem(
            "quickstart requires atomic no-replace directory publication"
        )
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if (
        function(
            parent_fd,
            encoded_source,
            parent_fd,
            encoded_destination,
            flag,
        )
        == 0
    ):
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(
            error_number, os.strerror(error_number), destination
        )
    raise OSError(error_number, os.strerror(error_number), destination)


def _remove_private_quickstart_directory(
    parent_fd: int,
    name: str,
    expected_device: int,
    expected_inode: int,
) -> None:
    """Remove only the still-empty private directory created by this process."""

    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return
    if (
        stat.S_ISDIR(metadata.st_mode)
        and metadata.st_dev == expected_device
        and metadata.st_ino == expected_inode
    ):
        try:
            os.rmdir(name, dir_fd=parent_fd)
        except OSError:
            pass


def _open_quickstart_managed_directory(
    parent_fd: int,
    name: str,
    expected: Optional[dict[str, int]],
) -> int:
    if not name or "/" in name or name in {".", ".."}:
        raise RuntimeProblem("quickstart received an unsafe managed directory name")
    if expected is None:
        private_name = f".{name}.acgm-directory-{secrets.token_hex(12)}"
        try:
            os.mkdir(private_name, 0o700, dir_fd=parent_fd)
            created_entry = os.stat(
                private_name, dir_fd=parent_fd, follow_symlinks=False
            )
        except OSError as exc:
            raise RuntimeProblem(
                "quickstart could not prepare a managed directory"
            ) from exc
        descriptor: Optional[int] = None
        try:
            descriptor = os.open(
                private_name,
                _quickstart_directory_flags(),
                dir_fd=parent_fd,
            )
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(created_entry.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_dev != created_entry.st_dev
                or metadata.st_ino != created_entry.st_ino
            ):
                raise RuntimeProblem(
                    "quickstart prepared directory changed during apply"
                )
            os.fchmod(descriptor, 0o755)
            _rename_quickstart_directory_noreplace(
                parent_fd, private_name, name
            )
            _verify_quickstart_directory_entry(parent_fd, name, descriptor)
            return descriptor
        except Exception:
            if descriptor is not None:
                os.close(descriptor)
            _remove_private_quickstart_directory(
                parent_fd,
                private_name,
                created_entry.st_dev,
                created_entry.st_ino,
            )
            raise

    try:
        descriptor = os.open(name, _quickstart_directory_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise RuntimeProblem(
            "quickstart managed directory changed during apply"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or not isinstance(expected, dict)
            or metadata.st_dev != expected.get("device")
            or metadata.st_ino != expected.get("inode")
        ):
            raise RuntimeProblem(
                "quickstart managed directory changed during apply"
            )
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _verify_quickstart_directory_entry(
    parent_fd: int, name: str, descriptor: int
) -> None:
    try:
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        opened = os.fstat(descriptor)
    except OSError as exc:
        raise RuntimeProblem(
            "quickstart managed directory changed during apply"
        ) from exc
    if (
        not stat.S_ISDIR(entry.st_mode)
        or entry.st_dev != opened.st_dev
        or entry.st_ino != opened.st_ino
    ):
        raise RuntimeProblem("quickstart managed directory changed during apply")


def _verify_quickstart_root(root: Path, descriptor: int) -> None:
    try:
        entry = root.lstat()
        opened = os.fstat(descriptor)
    except OSError as exc:
        raise RuntimeProblem("quickstart target root changed during apply") from exc
    if (
        not stat.S_ISDIR(entry.st_mode)
        or entry.st_dev != opened.st_dev
        or entry.st_ino != opened.st_ino
    ):
        raise RuntimeProblem("quickstart target root changed during apply")


def _standard_snapshot(identity: dict[str, Any]) -> str:
    cleanliness = "dirty" if identity["dirty"] else "clean"
    return (
        "# ACGM quickstart snapshot\n\n"
        "Current verified facts at plan time:\n\n"
        f"- Preset: `{QUICKSTART_PRESET}`\n"
        f"- Git HEAD: `{identity['head']}`\n"
        f"- Branch state: `{identity['branch']}`\n"
        f"- Working tree: `{cleanliness}`\n\n"
        "The next safe action is automatic local activation followed by the one-time "
        "Codex Hook trust boundary when the platform presents it.\n"
    )


def _quickstart_asset_plan(
    root: Path,
    name: str,
    content: str,
    *,
    replace_known: Optional[str] = None,
    preserve_known: Optional[str] = None,
    exact_existing_or_conflict: bool = False,
) -> dict[str, Any]:
    path = root / name
    parent = root
    for part in Path(name).parts[:-1]:
        parent = parent / part
        if parent.is_symlink():
            return {
                "path": name,
                "action": "conflict",
                "reason": "parent-is-symlink",
            }
        if parent.exists() and not parent.is_dir():
            return {
                "path": name,
                "action": "conflict",
                "reason": "parent-is-not-a-directory",
            }
    if path.is_symlink():
        return {"path": name, "action": "conflict", "reason": "symlink"}
    if path.exists() and not path.is_file():
        return {"path": name, "action": "conflict", "reason": "not-a-regular-file"}
    if path.is_file():
        try:
            current = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return {"path": name, "action": "conflict", "reason": "unreadable"}
        if replace_known is not None and current == replace_known:
            return {
                "path": name,
                "action": "replace-known-placeholder",
                "before_sha256": _sha256(path),
                "after_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "content": content,
            }
        if preserve_known is not None and current == preserve_known:
            digest = _sha256(path)
            return {
                "path": name,
                "action": "preserve",
                "before_sha256": digest,
                "after_sha256": digest,
            }
        if exact_existing_or_conflict:
            if current == content:
                digest = _sha256(path)
                return {
                    "path": name,
                    "action": "preserve",
                    "before_sha256": digest,
                    "after_sha256": digest,
                }
            return {
                "path": name,
                "action": "conflict",
                "reason": "reserved-path-content-conflict",
                "before_sha256": _sha256(path),
            }
        if len(current.strip()) < 20 or PLACEHOLDER_RE.search(current):
            return {
                "path": name,
                "action": "conflict",
                "reason": "existing-content-is-incomplete",
                "before_sha256": _sha256(path),
            }
        digest = _sha256(path)
        return {
            "path": name,
            "action": "preserve",
            "before_sha256": digest,
            "after_sha256": digest,
        }
    encoded = content.encode("utf-8")
    return {
        "path": name,
        "action": "create",
        "before_sha256": None,
        "after_sha256": hashlib.sha256(encoded).hexdigest(),
        "content": content,
    }


def _quickstart_directory_preimage(
    root: Path, name: str
) -> tuple[dict[str, str], Optional[str]]:
    directory = root / name
    if directory.is_symlink():
        return {}, "managed-directory-is-symlink"
    if directory.exists() and not directory.is_dir():
        return {}, "managed-directory-is-not-a-directory"
    if not directory.exists():
        return {}, None
    baseline: dict[str, str] = {}
    try:
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory)
            if any(part.startswith(".") for part in relative.parts):
                continue
            if path.is_symlink():
                return {}, "managed-directory-contains-symlink"
            if path.is_dir():
                continue
            if not path.is_file():
                return {}, "managed-directory-contains-nonregular-entry"
            baseline[relative.as_posix()] = _sha256(path)
    except OSError:
        return {}, "managed-directory-is-unreadable"
    return baseline, None


def _quickstart_receipt_preimage(
    path: Path,
) -> tuple[Optional[str], Optional[str]]:
    if path.is_symlink():
        return None, "quickstart-receipt-is-symlink"
    if path.exists() and not path.is_file():
        return None, "quickstart-receipt-is-not-a-regular-file"
    if not path.exists():
        return None, None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "quickstart-receipt-is-unknown"
    if not isinstance(receipt, dict) or receipt.get("schema") != QUICKSTART_RECEIPT_SCHEMA:
        return None, "quickstart-receipt-is-unknown"
    try:
        return _sha256(path), None
    except OSError:
        return None, "quickstart-receipt-is-unreadable"


def _quickstart_plan(project: str, preset: str = QUICKSTART_PRESET) -> dict[str, Any]:
    if not project:
        raise RuntimeProblem("quickstart requires an explicit project path")
    if preset != QUICKSTART_PRESET:
        raise RuntimeProblem(f"unknown quickstart preset: {preset}")
    explicit = Path(project).expanduser()
    if not explicit.exists() or not explicit.is_dir():
        raise RuntimeProblem("quickstart requires an existing project directory")
    explicit = explicit.resolve()
    root = _project_root(str(explicit))
    if root != explicit:
        raise RuntimeProblem(
            "quickstart requires the exact Git repository root, not a parent workspace "
            "or repository subdirectory"
        )
    identity = _quickstart_git_identity(root)
    git_guard = _quickstart_git_guard(root)
    managed_directory_entries = {
        name: _quickstart_directory_entry_identity(root, name)
        for name in QUICKSTART_MANAGED_DIRECTORIES
    }
    conflicts: list[dict[str, str]] = []
    local_state = root / ".acgm"
    if local_state.is_symlink() or (local_state.exists() and not local_state.is_dir()):
        conflicts.append({"path": ".acgm", "reason": "unsafe-local-state-path"})
    state_path = _state_path(root)
    unsafe_state = state_path.is_symlink() or (
        state_path.exists() and not state_path.is_file()
    )
    if unsafe_state:
        conflicts.append(
            {"path": ".acgm/codex.json", "reason": "unsafe-adapter-state-path"}
        )
        status: dict[str, Any] = {"state": BROKEN}
        state: dict[str, Any] = {}
        state_sha256: Optional[str] = None
    else:
        state_sha256 = _sha256(state_path) if state_path.is_file() else None
        try:
            state = _safe_read_json(state_path) if state_path.is_file() else {}
        except RuntimeProblem:
            state = {}
        status = _project_status(root)
    state_drift = list(status.get("drift", []))
    source_state_version = state.get("version")
    version_only_upgrade = (
        status["state"] == DRIFTED
        and state_drift == ["adapter-version:changed"]
        and _compatible_state_upgrade(source_state_version)
    )
    if status["state"] in {DRIFTED, BROKEN} and not version_only_upgrade:
        conflicts.append(
            {
                "path": ".acgm/codex.json",
                "reason": (
                    "adapter-version-not-compatible"
                    if state_drift == ["adapter-version:changed"]
                    else "active-governance-needs-repair"
                ),
            }
        )
    assets = [
        _quickstart_asset_plan(
            root,
            ".acgm/.gitignore",
            "*\n!.gitignore\n",
            preserve_known="*\n!.gitignore\n",
        ),
        _quickstart_asset_plan(
            root,
            "CONSTITUTION.md",
            STANDARD_CONSTITUTION,
            replace_known=CONSTITUTION_TEMPLATE,
        ),
        _quickstart_asset_plan(root, "AGENTS.md", AGENTS_TEMPLATE),
        _quickstart_asset_plan(
            root,
            ".governance/scope.yml",
            STANDARD_SCOPE,
            replace_known=SCOPE_TEMPLATE,
        ),
        _quickstart_asset_plan(
            root,
            ".governance/decisions/0001-adopt-acgm-standard-v1.md",
            STANDARD_DECISION,
            exact_existing_or_conflict=True,
        ),
        _quickstart_asset_plan(
            root,
            ".governance/snapshots/bootstrap.md",
            _standard_snapshot(identity),
        ),
    ]
    directory_preimages: dict[str, dict[str, str]] = {}
    for name in REQUIRED_DIRS:
        baseline, reason = _quickstart_directory_preimage(root, name)
        directory_preimages[name] = baseline
        if reason:
            conflicts.append({"path": name, "reason": reason})
    conflicts.extend(
        {"path": str(asset["path"]), "reason": str(asset["reason"])}
        for asset in assets
        if asset["action"] == "conflict"
    )
    directory_postimages = {
        name: dict(baseline) for name, baseline in directory_preimages.items()
    }
    for asset in assets:
        asset_name = str(asset["path"])
        for directory_name, baseline in directory_postimages.items():
            prefix = directory_name + "/"
            if asset_name.startswith(prefix) and asset.get("after_sha256"):
                baseline[asset_name[len(prefix) :]] = str(asset["after_sha256"])
    receipt_path = _quickstart_receipt_path(root)
    if local_state.is_symlink() or (local_state.exists() and not local_state.is_dir()):
        receipt_sha256, receipt_reason = None, "unsafe-local-state-path"
    else:
        receipt_sha256, receipt_reason = _quickstart_receipt_preimage(receipt_path)
    if receipt_reason:
        conflicts.append({"path": ".acgm/quickstart.json", "reason": receipt_reason})
    asset_by_path = {str(asset["path"]): asset for asset in assets}
    expected_baseline = {
        "files": {
            name: asset_by_path[name].get("after_sha256") for name in REQUIRED_FILES
        },
        "directories": directory_postimages,
    }
    baseline_mutation = any(
        asset.get("action") in {"create", "replace-known-placeholder"}
        and (
            str(asset.get("path")) in REQUIRED_FILES
            or any(
                str(asset.get("path")).startswith(directory + "/")
                for directory in REQUIRED_DIRS
            )
        )
        for asset in assets
    )
    planned_active_rebaseline = status["state"] == GOVERNED and baseline_mutation
    planned_preset_adoption = status["state"] == GOVERNED and (
        state.get("preset") != preset or state.get("provisioned_by") != "quickstart"
    )
    if not unsafe_state:
        if state_sha256 is None:
            if state_path.exists() or state_path.is_symlink():
                raise RuntimeProblem("quickstart adapter state changed while planning")
        elif (
            state_path.is_symlink()
            or not state_path.is_file()
            or not hmac.compare_digest(_sha256(state_path), state_sha256)
        ):
            raise RuntimeProblem("quickstart adapter state changed while planning")
    if receipt_reason is None:
        current_receipt_sha256, current_receipt_reason = _quickstart_receipt_preimage(
            receipt_path
        )
        if (
            current_receipt_reason is not None
            or current_receipt_sha256 != receipt_sha256
        ):
            raise RuntimeProblem("quickstart receipt changed while planning")
    if _quickstart_git_guard(root) != git_guard:
        raise RuntimeProblem("quickstart Git state changed while planning")
    if {
        name: _quickstart_directory_entry_identity(root, name)
        for name in QUICKSTART_MANAGED_DIRECTORIES
    } != managed_directory_entries:
        raise RuntimeProblem("quickstart managed directories changed while planning")
    unsigned = {
        "schema": QUICKSTART_SCHEMA,
        "version": VERSION,
        "preset": preset,
        "project": identity,
        "project_state": status["state"],
        "state_drift": state_drift,
        "source_state_version": source_state_version,
        "version_only_upgrade": version_only_upgrade,
        "planned_active_rebaseline": planned_active_rebaseline,
        "planned_preset_adoption": planned_preset_adoption,
        "state_sha256": state_sha256,
        "receipt_sha256": receipt_sha256,
        "git_guard": git_guard,
        "managed_directory_entries": managed_directory_entries,
        "assets": assets,
        "directory_preimages": directory_preimages,
        "directory_postimages": directory_postimages,
        "expected_baseline": expected_baseline,
        "conflicts": conflicts,
        "capabilities": [
            "create_missing_versioned_governance_assets",
            "preserve_existing_project_policy",
            "activate_exact_project",
            "run_local_postcondition_checks",
        ],
        "platform_boundary": "codex_hook_trust_may_require_one_user_confirmation",
    }
    canonical = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    plan = dict(unsigned)
    plan["plan_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    plan["ok"] = not conflicts
    plan["status"] = "PLAN_READY" if not conflicts else "PROJECT_ASSET_CONFLICT"
    return plan


def _quickstart_receipt_path(root: Path) -> Path:
    return root / ".acgm" / "quickstart.json"


def _write_new_text(root: Path, name: str, content: str) -> None:
    path = root / name
    parent = root
    for part in Path(name).parts[:-1]:
        parent = parent / part
        if parent.is_symlink():
            raise RuntimeProblem(f"quickstart parent became a symlink: {name}")
        parent.mkdir(exist_ok=True)
    try:
        _write_new_bytes(path, content.encode("utf-8"), 0o644)
    except FileExistsError as exc:
        raise RuntimeProblem(f"quickstart plan became stale before creating {name}") from exc


def _replace_known_text(
    root: Path, name: str, content: str, expected_sha256: str
) -> None:
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise RuntimeProblem(f"quickstart plan became stale for {name}")
    _quickstart_cas_bytes(
        path,
        content.encode("utf-8"),
        expected_sha256,
        mode=0o644,
    )


def _write_new_text_at(directory_fd: int, name: str, content: str) -> None:
    try:
        _write_new_bytes_at(directory_fd, name, content.encode("utf-8"), 0o644)
    except FileExistsError as exc:
        raise RuntimeProblem(
            f"quickstart plan became stale before creating {name}"
        ) from exc


def _replace_known_text_at(
    directory_fd: int,
    name: str,
    content: str,
    expected_sha256: str,
) -> None:
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise RuntimeProblem(f"quickstart plan became stale for {name}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeProblem(f"quickstart plan became stale for {name}")
    _quickstart_cas_bytes_at(
        directory_fd,
        name,
        content.encode("utf-8"),
        expected_sha256,
        mode=0o644,
    )


_QUICKSTART_CAS_UNSET = object()


def _assert_quickstart_state_preimage(
    path: Path, expected_sha256: Optional[str]
) -> None:
    if expected_sha256 is None:
        if path.exists() or path.is_symlink():
            raise RuntimeProblem("quickstart adapter state changed during apply")
        return
    if (
        path.is_symlink()
        or not path.is_file()
        or not hmac.compare_digest(_sha256(path), expected_sha256)
    ):
        raise RuntimeProblem("quickstart adapter state changed during apply")


def _assert_quickstart_state_preimage_at(
    directory_fd: int, expected_sha256: Optional[str]
) -> None:
    name = "codex.json"
    if expected_sha256 is None:
        if _entry_exists_at(directory_fd, name):
            raise RuntimeProblem("quickstart adapter state changed during apply")
        return
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise RuntimeProblem("quickstart adapter state changed during apply") from exc
    if not stat.S_ISREG(metadata.st_mode) or not hmac.compare_digest(
        _sha256_at(directory_fd, name), expected_sha256
    ):
        raise RuntimeProblem("quickstart adapter state changed during apply")


def _write_quickstart_receipt_cas(
    path: Path, value: dict[str, Any], expected_sha256: Optional[str]
) -> str:
    if expected_sha256 is None:
        if path.exists() or path.is_symlink():
            raise RuntimeProblem("quickstart receipt changed during apply")
        try:
            published_sha256 = _write_new_json(path, value)
        except FileExistsError as exc:
            raise RuntimeProblem("quickstart receipt changed during apply") from exc
    else:
        if (
            path.is_symlink()
            or not path.is_file()
            or not hmac.compare_digest(_sha256(path), expected_sha256)
        ):
            raise RuntimeProblem("quickstart receipt changed during apply")
        published_sha256 = _quickstart_cas_json(path, value, expected_sha256)
    if (
        path.is_symlink()
        or not path.is_file()
        or not hmac.compare_digest(_sha256(path), published_sha256)
    ):
        raise RuntimeProblem("quickstart could not verify its receipt")
    return published_sha256


def _write_quickstart_receipt_cas_at(
    directory_fd: int,
    value: dict[str, Any],
    expected_sha256: Optional[str],
) -> str:
    name = "quickstart.json"
    if expected_sha256 is None:
        if _entry_exists_at(directory_fd, name):
            raise RuntimeProblem("quickstart receipt changed during apply")
        try:
            published_sha256 = _write_new_json_at(directory_fd, name, value)
        except FileExistsError as exc:
            raise RuntimeProblem("quickstart receipt changed during apply") from exc
    else:
        try:
            metadata = os.stat(
                name, dir_fd=directory_fd, follow_symlinks=False
            )
        except OSError as exc:
            raise RuntimeProblem("quickstart receipt changed during apply") from exc
        if not stat.S_ISREG(metadata.st_mode) or not hmac.compare_digest(
            _sha256_at(directory_fd, name), expected_sha256
        ):
            raise RuntimeProblem("quickstart receipt changed during apply")
        published_sha256 = _quickstart_cas_json_at(
            directory_fd, name, value, expected_sha256
        )
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise RuntimeProblem("quickstart could not verify its receipt") from exc
    if not stat.S_ISREG(metadata.st_mode) or not hmac.compare_digest(
        _sha256_at(directory_fd, name), published_sha256
    ):
        raise RuntimeProblem("quickstart could not verify its receipt")
    return published_sha256


def _quickstart_health_result(
    doctor: dict[str, Any],
) -> tuple[str, bool, list[str]]:
    if doctor["healthy"]:
        return "COMPLETE", True, []
    if doctor["project_state"] != GOVERNED:
        return (
            "NOT_READY",
            False,
            ["Repair project governance, then rerun quickstart status."],
        )
    if doctor["hook"]["runtime_error_after_last_heartbeat"]:
        return (
            "HOOK_RUNTIME_REPAIR_REQUIRED",
            False,
            ["Run `acgm-codex doctor --strict` and repair the reported Hook runtime error."],
        )
    if not doctor["installed"] or not doctor["platform_supported"]:
        return (
            "LOCAL_RUNTIME_REPAIR_REQUIRED",
            False,
            ["Repair the local ACGM installation or use a supported platform."],
        )
    if not doctor["ledger"]["available"] or not doctor["ledger"]["mode_0600"]:
        return (
            "LOCAL_RUNTIME_REPAIR_REQUIRED",
            False,
            ["Run `acgm-codex doctor --strict` and repair the local activity ledger."],
        )
    return (
        "AWAITING_PLATFORM_HOOK_ACCEPTANCE",
        True,
        [
            "Trust the current ACGM definition once if Codex presents /hooks, then "
            "continue normal work; the next observed Hook can complete verification."
        ],
    )


def _activate_project(
    root: Path,
    *,
    preset: Optional[str] = None,
    reuse_active: bool = False,
    allow_version_only_upgrade: bool = False,
    allow_planned_rebaseline: bool = False,
    adopt_preset: bool = False,
    expected_state_sha256: Any = _QUICKSTART_CAS_UNSET,
    expected_baseline: Optional[dict[str, Any]] = None,
    verified_baseline: Optional[dict[str, Any]] = None,
    activation_guard: Optional[Callable[[], dict[str, Any]]] = None,
    state_directory_fd: Optional[int] = None,
) -> tuple[dict[str, Any], bool]:
    state_path = _state_path(root)
    if expected_state_sha256 is not _QUICKSTART_CAS_UNSET:
        if state_directory_fd is None:
            _assert_quickstart_state_preimage(state_path, expected_state_sha256)
        else:
            _assert_quickstart_state_preimage_at(
                state_directory_fd, expected_state_sha256
            )
    baseline = (
        verified_baseline
        if verified_baseline is not None
        else _component_baseline(root)
    )
    if expected_baseline is not None and baseline != expected_baseline:
        raise RuntimeProblem("quickstart governance postimage changed before activation")
    target_baseline = expected_baseline if expected_baseline is not None else baseline
    state_exists = (
        state_path.exists()
        if state_directory_fd is None
        else _entry_exists_at(state_directory_fd, "codex.json")
    )
    if state_exists:
        existing = (
            _safe_read_json(state_path)
            if state_directory_fd is None
            else _safe_read_json_at(state_directory_fd, "codex.json")
        )
        if existing.get("schema") != STATE_SCHEMA:
            raise RuntimeProblem("adapter state schema is not recognized")
        if reuse_active and existing.get("active") is True:
            activation_id = existing.get("activation_id")
            if not isinstance(activation_id, str) or not activation_id:
                raise RuntimeProblem("active governance has no reusable activation id")
            version_upgrade = allow_version_only_upgrade and _compatible_state_upgrade(
                existing.get("version")
            )
            already_current = (
                existing.get("version") == VERSION
                and existing.get("baseline") == target_baseline
            )
            if already_current and not adopt_preset:
                return existing, False
            if version_upgrade or allow_planned_rebaseline or (
                already_current and adopt_preset
            ):
                state = dict(existing)
                state.update(
                    {
                        "version": VERSION,
                        "baseline": target_baseline,
                    }
                )
                if version_upgrade:
                    state["upgraded_at"] = int(time.time())
                if allow_planned_rebaseline:
                    state["quickstart_rebaselined_at"] = int(time.time())
                if preset:
                    state["preset"] = preset
                    state["provisioned_by"] = "quickstart"
                    if adopt_preset:
                        state["quickstart_adopted_at"] = int(time.time())
                if activation_guard is not None:
                    guarded_baseline = activation_guard()
                    if (
                        expected_baseline is not None
                        and guarded_baseline != expected_baseline
                    ):
                        raise RuntimeProblem(
                            "quickstart governance postimage changed before activation"
                        )
                if expected_state_sha256 is not _QUICKSTART_CAS_UNSET:
                    if state_directory_fd is None:
                        _assert_quickstart_state_preimage(
                            state_path, expected_state_sha256
                        )
                    else:
                        _assert_quickstart_state_preimage_at(
                            state_directory_fd, expected_state_sha256
                        )
                    if not isinstance(expected_state_sha256, str):
                        raise RuntimeProblem(
                            "quickstart adapter state has no replaceable preimage"
                        )
                    if state_directory_fd is None:
                        _quickstart_cas_json(
                            state_path, state, expected_state_sha256
                        )
                    else:
                        _quickstart_cas_json_at(
                            state_directory_fd,
                            "codex.json",
                            state,
                            expected_state_sha256,
                        )
                else:
                    _atomic_json(state_path, state)
                current_state = (
                    _safe_read_json(state_path)
                    if state_directory_fd is None
                    else _safe_read_json_at(state_directory_fd, "codex.json")
                )
                if current_state != state:
                    raise RuntimeProblem("quickstart could not verify adapter state")
                return state, True
            raise RuntimeProblem("active governance is drifted or broken and was not rebaselined")
    if expected_baseline is not None and verified_baseline is not None:
        missing, placeholders = [], []
    else:
        missing, placeholders = _asset_issues(root)
    if missing or placeholders:
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if placeholders:
            detail.append("placeholder or too short: " + ", ".join(placeholders))
        raise RuntimeProblem("governance assets are incomplete; " + "; ".join(detail))
    state: dict[str, Any] = {
        "schema": STATE_SCHEMA,
        "version": VERSION,
        "active": True,
        "platform": "codex",
        "activated_at": int(time.time()),
        "activation_id": secrets.token_hex(12),
        "baseline": target_baseline,
    }
    if preset:
        state["preset"] = preset
        state["provisioned_by"] = "quickstart"
    if activation_guard is not None:
        guarded_baseline = activation_guard()
        if expected_baseline is not None and guarded_baseline != expected_baseline:
            raise RuntimeProblem(
                "quickstart governance postimage changed before activation"
            )
    if expected_state_sha256 is not _QUICKSTART_CAS_UNSET:
        if state_directory_fd is None:
            _assert_quickstart_state_preimage(state_path, expected_state_sha256)
        else:
            _assert_quickstart_state_preimage_at(
                state_directory_fd, expected_state_sha256
            )
        if expected_state_sha256 is None:
            try:
                if state_directory_fd is None:
                    _write_new_json(state_path, state)
                else:
                    _write_new_json_at(
                        state_directory_fd, "codex.json", state
                    )
            except FileExistsError as exc:
                raise RuntimeProblem(
                    "quickstart adapter state changed during apply"
                ) from exc
        elif isinstance(expected_state_sha256, str):
            if state_directory_fd is None:
                _quickstart_cas_json(state_path, state, expected_state_sha256)
            else:
                _quickstart_cas_json_at(
                    state_directory_fd,
                    "codex.json",
                    state,
                    expected_state_sha256,
                )
        else:
            raise RuntimeProblem(
                "quickstart adapter state has no replaceable preimage"
            )
    else:
        _atomic_json(state_path, state)
    current_state = (
        _safe_read_json(state_path)
        if state_directory_fd is None
        else _safe_read_json_at(state_directory_fd, "codex.json")
    )
    if current_state != state:
        raise RuntimeProblem("quickstart could not verify adapter state")
    return state, True


def _apply_quickstart(
    project: str,
    *,
    preset: str = QUICKSTART_PRESET,
    authorized: bool,
    expected_digest: Optional[str] = None,
) -> dict[str, Any]:
    plan = _quickstart_plan(project, preset)
    result: dict[str, Any] = {
        "schema": QUICKSTART_RECEIPT_SCHEMA,
        "ok": False,
        "complete": False,
        "partial": False,
        "authorized": authorized,
        "status": plan["status"],
        "plan_digest": plan["plan_digest"],
        "preset": preset,
        "project": plan["project"],
        "completed_steps": [],
        "claims": {
            "project_assets_verified": False,
            "project_activated": False,
            "automatic_hook_observed": False,
        },
    }
    if not plan["ok"]:
        result["conflicts"] = plan["conflicts"]
        return result
    if not authorized:
        result["status"] = "AUTHORIZATION_REQUIRED"
        return result
    if not expected_digest:
        result["status"] = "PLAN_DIGEST_REQUIRED"
        return result
    if expected_digest != plan["plan_digest"]:
        result["status"] = "PLAN_STALE"
        return result
    root = Path(str(plan["project"]["root"]))
    receipt = dict(result)
    receipt["status"] = "APPLYING"
    receipt_sha256 = plan["receipt_sha256"]
    root_fd: Optional[int] = None
    acgm_fd: Optional[int] = None
    governance_fd: Optional[int] = None
    decisions_fd: Optional[int] = None
    snapshots_fd: Optional[int] = None
    try:
        root_fd = _open_quickstart_root(root, plan["project"])
        directory_entries = plan["managed_directory_entries"]
        acgm_fd = _open_quickstart_managed_directory(
            root_fd, ".acgm", directory_entries[".acgm"]
        )
        receipt_sha256 = _write_quickstart_receipt_cas_at(
            acgm_fd, receipt, receipt_sha256
        )
        governance_fd = _open_quickstart_managed_directory(
            root_fd, ".governance", directory_entries[".governance"]
        )
        decisions_fd = _open_quickstart_managed_directory(
            governance_fd,
            "decisions",
            directory_entries[".governance/decisions"],
        )
        snapshots_fd = _open_quickstart_managed_directory(
            governance_fd,
            "snapshots",
            directory_entries[".governance/snapshots"],
        )

        asset_locations = {
            ".acgm/.gitignore": (acgm_fd, ".gitignore"),
            "CONSTITUTION.md": (root_fd, "CONSTITUTION.md"),
            "AGENTS.md": (root_fd, "AGENTS.md"),
            ".governance/scope.yml": (governance_fd, "scope.yml"),
            ".governance/decisions/0001-adopt-acgm-standard-v1.md": (
                decisions_fd,
                "0001-adopt-acgm-standard-v1.md",
            ),
            ".governance/snapshots/bootstrap.md": (
                snapshots_fd,
                "bootstrap.md",
            ),
        }

        def activation_guard() -> dict[str, Any]:
            """Revalidate every cross-file activation precondition by dirfd."""

            _verify_quickstart_asset_postimages_at(
                plan["assets"], asset_locations
            )
            _verify_quickstart_root(root, root_fd)
            _verify_quickstart_directory_entry(root_fd, ".acgm", acgm_fd)
            _verify_quickstart_directory_entry(
                root_fd, ".governance", governance_fd
            )
            _verify_quickstart_directory_entry(
                governance_fd, "decisions", decisions_fd
            )
            _verify_quickstart_directory_entry(
                governance_fd, "snapshots", snapshots_fd
            )
            current_baseline = _quickstart_component_baseline_at(
                root_fd,
                governance_fd,
                decisions_fd,
                snapshots_fd,
            )
            if current_baseline != plan["expected_baseline"]:
                raise RuntimeProblem(
                    "quickstart governance postimage changed before activation"
                )
            if _quickstart_git_guard(root) != plan["git_guard"]:
                raise RuntimeProblem(
                    "quickstart target Git identity or state changed during apply"
                )
            return current_baseline

        for asset in plan["assets"]:
            name = str(asset["path"])
            location = asset_locations.get(name)
            if location is None:
                raise RuntimeProblem("quickstart plan contains an unknown managed path")
            directory_fd, entry_name = location
            if asset["action"] == "create":
                _write_new_text_at(
                    directory_fd, entry_name, str(asset["content"])
                )
            elif asset["action"] == "replace-known-placeholder":
                _replace_known_text_at(
                    directory_fd,
                    entry_name,
                    str(asset["content"]),
                    str(asset["before_sha256"]),
                )
            elif asset["action"] == "preserve":
                try:
                    metadata = os.stat(
                        entry_name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    raise RuntimeProblem(
                        f"quickstart plan became stale for {name}"
                    ) from exc
                if not stat.S_ISREG(metadata.st_mode) or not hmac.compare_digest(
                    _sha256_at(directory_fd, entry_name),
                    str(asset["before_sha256"]),
                ):
                    raise RuntimeProblem(f"quickstart plan became stale for {name}")
            try:
                metadata = os.stat(
                    entry_name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise RuntimeProblem(f"quickstart could not verify {name}") from exc
            if not stat.S_ISREG(metadata.st_mode) or not hmac.compare_digest(
                _sha256_at(directory_fd, entry_name), str(asset["after_sha256"])
            ):
                raise RuntimeProblem(f"quickstart could not verify {name}")
            receipt["completed_steps"].append("asset:" + name)
            receipt_sha256 = _write_quickstart_receipt_cas_at(
                acgm_fd, receipt, receipt_sha256
            )
        anchored_baseline = activation_guard()
        receipt["claims"]["project_assets_verified"] = True
        state, activation_changed = _activate_project(
            root,
            preset=preset,
            reuse_active=True,
            allow_version_only_upgrade=bool(plan["version_only_upgrade"]),
            allow_planned_rebaseline=bool(plan["planned_active_rebaseline"]),
            adopt_preset=bool(plan["planned_preset_adoption"]),
            expected_state_sha256=plan["state_sha256"],
            expected_baseline=plan["expected_baseline"],
            verified_baseline=anchored_baseline,
            activation_guard=activation_guard,
            state_directory_fd=acgm_fd,
        )
        if plan["state_sha256"] is None:
            activation_step = "activation:created"
        elif activation_changed:
            activation_step = "activation:updated"
        else:
            activation_step = "activation:preserved"
        receipt["completed_steps"].append(activation_step)
        receipt["activation_id"] = state["activation_id"]
        receipt["claims"]["project_activated"] = True
        _verify_quickstart_asset_postimages_at(plan["assets"], asset_locations)
        if _quickstart_component_baseline_at(
            root_fd,
            governance_fd,
            decisions_fd,
            snapshots_fd,
        ) != plan["expected_baseline"]:
            raise RuntimeProblem("quickstart governance postimage changed after activation")
        if _quickstart_git_guard(root) != plan["git_guard"]:
            raise RuntimeProblem("quickstart final Git identity or state changed")
        if _safe_read_json_at(acgm_fd, "codex.json") != state:
            raise RuntimeProblem("quickstart final adapter state changed")
        _verify_quickstart_root(root, root_fd)
        _verify_quickstart_directory_entry(root_fd, ".acgm", acgm_fd)
        _verify_quickstart_directory_entry(
            root_fd, ".governance", governance_fd
        )
        _verify_quickstart_directory_entry(
            governance_fd, "decisions", decisions_fd
        )
        _verify_quickstart_directory_entry(
            governance_fd, "snapshots", snapshots_fd
        )
        doctor = _doctor_payload(root)
        if doctor["project_state"] != GOVERNED:
            raise RuntimeProblem("post-activation doctor did not report GOVERNED")
        if _safe_read_json_at(acgm_fd, "codex.json") != state:
            raise RuntimeProblem("quickstart adapter state changed during verification")
        _verify_quickstart_asset_postimages_at(plan["assets"], asset_locations)
        if _quickstart_component_baseline_at(
            root_fd,
            governance_fd,
            decisions_fd,
            snapshots_fd,
        ) != plan["expected_baseline"]:
            raise RuntimeProblem(
                "quickstart governance postimage changed during verification"
            )
        receipt["doctor"] = doctor
        receipt["claims"]["automatic_hook_observed"] = bool(
            doctor["hook"]["observed_for_current_version_and_activation"]
        )
        health_status, health_ok, pending_actions = _quickstart_health_result(doctor)
        receipt["ok"] = health_ok
        receipt["complete"] = health_status == "COMPLETE"
        receipt["status"] = health_status
        receipt["pending_actions"] = pending_actions
        _write_quickstart_receipt_cas_at(acgm_fd, receipt, receipt_sha256)
        _verify_quickstart_root(root, root_fd)
        _verify_quickstart_directory_entry(root_fd, ".acgm", acgm_fd)
        _verify_quickstart_directory_entry(
            root_fd, ".governance", governance_fd
        )
        _verify_quickstart_directory_entry(
            governance_fd, "decisions", decisions_fd
        )
        _verify_quickstart_directory_entry(
            governance_fd, "snapshots", snapshots_fd
        )
        _verify_quickstart_asset_postimages_at(plan["assets"], asset_locations)
        if _quickstart_component_baseline_at(
            root_fd,
            governance_fd,
            decisions_fd,
            snapshots_fd,
        ) != plan["expected_baseline"]:
            raise RuntimeProblem("quickstart final governance postimage changed")
        return receipt
    except (OSError, RuntimeProblem) as exc:
        receipt["ok"] = False
        receipt["complete"] = False
        receipt["status"] = "PARTIAL_RECHECK_REQUIRED"
        receipt["partial"] = True
        receipt["error"] = str(exc)
        try:
            if acgm_fd is not None:
                _write_quickstart_receipt_cas_at(
                    acgm_fd, receipt, receipt_sha256
                )
        except (OSError, RuntimeProblem):
            pass
        return receipt
    finally:
        for descriptor in (
            snapshots_fd,
            decisions_fd,
            governance_fd,
            acgm_fd,
            root_fd,
        ):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _quickstart_status(project: str) -> dict[str, Any]:
    root = _project_root(project)
    receipt_path = _quickstart_receipt_path(root)
    receipt: dict[str, Any] = {}
    if receipt_path.is_file() and not receipt_path.is_symlink():
        receipt = _safe_read_json(receipt_path)
    doctor = _doctor_payload(root)
    health_status, health_ok, pending_actions = _quickstart_health_result(doctor)
    return {
        "schema": QUICKSTART_RECEIPT_SCHEMA,
        "ok": health_ok,
        "complete": health_status == "COMPLETE",
        "status": health_status,
        "project": str(root),
        "plan_digest": receipt.get("plan_digest"),
        "pending_actions": pending_actions,
        "doctor": doctor,
    }


def _cmd_init(args: argparse.Namespace) -> int:
    root = _project_root(_project_argument(args))
    created: list[str] = []
    skipped: list[str] = []
    assets = {
        "CONSTITUTION.md": CONSTITUTION_TEMPLATE,
        "AGENTS.md": AGENTS_TEMPLATE,
        ".governance/scope.yml": SCOPE_TEMPLATE,
    }
    for name, content in assets.items():
        path = root / name
        if path.exists():
            skipped.append(name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(name)
    for name in REQUIRED_DIRS:
        path = root / name
        if path.exists():
            skipped.append(name + "/")
        else:
            path.mkdir(parents=True)
            created.append(name + "/")
    state_path = _state_path(root)
    local_ignore = state_path.parent / ".gitignore"
    if local_ignore.exists():
        skipped.append(".acgm/.gitignore")
    else:
        local_ignore.parent.mkdir(parents=True, exist_ok=True)
        local_ignore.write_text("*\n!.gitignore\n", encoding="utf-8")
        created.append(".acgm/.gitignore")
    if state_path.exists():
        skipped.append(".acgm/codex.json")
    else:
        _atomic_json(
            state_path,
            {
                "schema": STATE_SCHEMA,
                "version": VERSION,
                "active": False,
                "platform": "codex",
            },
        )
        created.append(".acgm/codex.json")
    print("ACGM Codex initialized without overwriting existing files.")
    print("created: " + (", ".join(created) if created else "none"))
    print("preserved: " + (", ".join(skipped) if skipped else "none"))
    print("Review the governance assets, then run `acgm-codex activate`.")
    return 0


def _cmd_activate(args: argparse.Namespace) -> int:
    root = _project_root(_project_argument(args))
    try:
        _activate_project(root)
    except RuntimeProblem as exc:
        print(f"activation refused: {exc}", file=sys.stderr)
        return 2
    print("ACGM Codex project governance is active.")
    print("Start a new Codex task, trust the plugin hooks, then run doctor --strict.")
    return 0


def _cmd_quickstart(args: argparse.Namespace) -> int:
    if args.quickstart_command == "plan":
        payload = _quickstart_plan(args.project, args.preset)
    elif args.quickstart_command == "apply":
        payload = _apply_quickstart(
            args.project,
            preset=args.preset,
            authorized=args.authorize,
            expected_digest=args.plan_digest,
        )
    elif args.quickstart_command == "status":
        payload = _quickstart_status(args.project)
    else:
        raise RuntimeProblem("unknown quickstart command")
    if args.json:
        _json_output(payload)
    else:
        print(f"ACGM Codex quickstart: {payload['status']}")
        if payload.get("pending_actions"):
            for action in payload["pending_actions"]:
                print("next: " + str(action))
    if payload.get("status") == "PARTIAL_RECHECK_REQUIRED":
        return 3
    return 0 if payload.get("ok") else 2


def _doctor_payload(root: Path) -> dict[str, Any]:
    status = _project_status(root)
    platform_supported = _supported_platform()
    installed = _installed()
    relevant_events: list[dict[str, Any]] = []
    ledger_available = False
    ledger_secure = False
    activated_at = 0
    activation_id: Optional[str] = None
    try:
        adapter = _safe_read_json(_state_path(root))
        if adapter.get("active") is True:
            activated_at = int(adapter.get("activated_at", 0))
            value = adapter.get("activation_id")
            activation_id = value if isinstance(value, str) else None
    except (RuntimeProblem, TypeError, ValueError):
        activated_at = 0
    try:
        events = _read_events()
        project_id = (
            _opaque_readonly("project", str(root.resolve())) if events else None
        )
        relevant_events = [
            event
            for event in events
            if project_id is not None
            and event.get("project_id") == project_id
            and event.get("version") == VERSION
            and activation_id is not None
            and event.get("activation_id") == activation_id
            and int(event.get("ts", 0)) >= activated_at
        ]
        ledger_available = True
        ledger = _read_ledger_path()
        if ledger.exists():
            ledger_secure = stat.S_IMODE(ledger.stat().st_mode) == 0o600
        else:
            ledger_secure = True
    except Exception:
        ledger_available = False
    heartbeat_indexes = [
        index
        for index, event in enumerate(relevant_events)
        if event.get("kind") == "hook-heartbeat"
    ]
    latest_index = heartbeat_indexes[-1] if heartbeat_indexes else -1
    latest = relevant_events[latest_index] if latest_index >= 0 else None
    later_errors = (
        [
            event
            for event in relevant_events[latest_index + 1 :]
            if event.get("kind") == "runtime-error"
        ]
        if latest_index >= 0
        else [event for event in relevant_events if event.get("kind") == "runtime-error"]
    )
    latest_error = later_errors[-1] if later_errors else None
    hook_observed = latest is not None and latest_error is None
    healthy = bool(
        installed
        and platform_supported
        and status["state"] == GOVERNED
        and hook_observed
        and ledger_available
        and ledger_secure
    )
    return {
        "schema": "acgm-codex-doctor-v1",
        "version": VERSION,
        "installed": installed,
        "platform": platform.system().lower(),
        "platform_supported": platform_supported,
        "project_state": status["state"],
        "active": status["active"],
        "missing": status["missing"],
        "placeholders": status["placeholders"],
        "drift": status["drift"],
        "hook": {
            "observed": hook_observed,
            "observed_for_current_version_and_activation": hook_observed,
            "last_event": latest.get("category") if latest else None,
            "last_observed_at": latest.get("ts") if latest else None,
            "last_error_at": latest_error.get("ts") if latest_error else None,
            "runtime_error_after_last_heartbeat": latest_error is not None,
        },
        "ledger": {
            "available": ledger_available,
            "mode_0600": ledger_secure,
        },
        "healthy": healthy,
    }


def _cmd_doctor(args: argparse.Namespace) -> int:
    root = _project_root(_project_argument(args))
    value = _doctor_payload(root)
    if args.json:
        _json_output(value)
    else:
        print(f"ACGM Codex {value['version']}")
        print(f"installed: {'yes' if value['installed'] else 'no'}")
        print(f"platform supported: {'yes' if value['platform_supported'] else 'no'}")
        print(f"project state: {value['project_state']}")
        print(f"hook observed: {'yes' if value['hook']['observed'] else 'no'}")
        print(f"ledger healthy: {'yes' if value['ledger']['available'] and value['ledger']['mode_0600'] else 'no'}")
        print(f"overall healthy: {'yes' if value['healthy'] else 'no'}")
        if value["missing"]:
            print("missing: " + ", ".join(value["missing"]))
        if value["placeholders"]:
            print("placeholder: " + ", ".join(value["placeholders"]))
        if value["drift"]:
            print("drift: " + ", ".join(value["drift"]))
    return 0 if value["healthy"] or not args.strict else 2


def _project_events(root: Path) -> list[dict[str, Any]]:
    events = _read_events()
    if not events:
        return []
    project_id = _opaque_readonly("project", str(root.resolve()))
    return [event for event in events if event.get("project_id") == project_id]


def _cmd_report(args: argparse.Namespace) -> int:
    root = _project_root(_project_argument(args))
    events = _project_events(root)[-args.limit :]
    value = {
        "schema": "acgm-codex-report-v1",
        "version": VERSION,
        "project_state": _project_status(root)["state"],
        "count": len(events),
        "events": events,
    }
    if args.json:
        _json_output(value)
    elif not events:
        print("No ACGM Codex events recorded for this project.")
    else:
        for event in events:
            print(
                f"{event['ts']} {event['event_id']} {event['kind']} "
                f"{event['category']} {event['outcome']}"
            )
    return 0


def _find_project_event(root: Path, event_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events = _project_events(root)
    for event in events:
        if hmac.compare_digest(str(event.get("event_id", "")), event_id):
            return event, events
    raise RuntimeProblem("event was not found for the current project")


def _cmd_export_case(args: argparse.Namespace) -> int:
    root = _project_root(_project_argument(args))
    source, events = _find_project_event(root, args.event)
    none_session = _opaque("session", None)
    none_turn = _opaque("turn", None)
    related = [source]
    if (
        source.get("session_id") != none_session
        and source.get("turn_id") != none_turn
    ):
        related = [
            event
            for event in events
            if event.get("session_id") == source.get("session_id")
            and event.get("turn_id") == source.get("turn_id")
        ]
    related_ids = {str(event.get("event_id")) for event in related}
    changed = True
    while changed:
        changed = False
        parent_ids = {
            str(event.get("ref_id"))
            for event in related
            if isinstance(event.get("ref_id"), str)
        }
        for event in events:
            if (
                event.get("ref_id") in related_ids
                or event.get("event_id") in parent_ids
            ) and event not in related:
                related.append(event)
                related_ids.add(str(event.get("event_id")))
                changed = True
    related = sorted(related, key=lambda item: int(item.get("ts", 0)))[-50:]
    value = {
        "schema": CASE_SCHEMA,
        "version": VERSION,
        "exported_at": int(time.time()),
        "case_id": _opaque("case", source["event_id"]),
        "source_event_id": source["event_id"],
        "events": related,
        "privacy": {
            "paths": "not-collected",
            "commands": "not-collected",
            "prompts": "not-collected",
            "model_or_provider": "not-collected",
            "credentials": "not-collected",
        },
    }
    if args.output == "-":
        _json_output(value)
        return 0
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = Path.cwd() / output
    output = output.resolve()
    protected_roots = (
        (root / ".acgm").resolve(),
        (root / ".governance").resolve(),
        _data_dir().resolve(),
    )
    protected_files = {
        (root / name).resolve() for name in REQUIRED_FILES
    }
    if output in protected_files or any(
        output == protected or output.is_relative_to(protected)
        for protected in protected_roots
    ):
        raise RuntimeProblem("refusing to export over governance or runtime state")
    if output.exists():
        raise RuntimeProblem("export output already exists; choose a new path")
    _write_new_json(output, value, mode=0o600)
    print("Sanitized ACGM case exported.")
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    root = _project_root(_project_argument(args))
    source, _ = _find_project_event(root, args.event)
    event = _append_event(
        "event-resolution",
        root,
        category=str(source.get("category", "none")),
        outcome=args.status,
        ref_id=source["event_id"],
    )
    print(f"Recorded resolution {args.status} as event {event['event_id']}.")
    return 0


def _gate_target_path(raw: Optional[str]) -> Path:
    base = Path.cwd().resolve()
    path = Path(raw) if raw else base
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def _claim_gate_request(
    root: Path,
    event_id: str,
    category: str,
    target_id: str,
    operation: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    adapter = _safe_read_json(_state_path(root))
    activation_id = adapter.get("activation_id")
    if not isinstance(activation_id, str):
        raise RuntimeProblem("project activation is invalid")
    expected_source = "gate-denied" if operation == "arm" else "obligation-opened"
    expected_request = (
        "gate-arm-requested" if operation == "arm" else "gate-verify-requested"
    )
    claim = _event_value(
        "gate-check-started",
        root,
        category=category,
        outcome=operation,
        state=GOVERNED,
        target_id=target_id,
    )
    path = _ledger_path()
    descriptor = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        events = _read_event_stream(handle)
        source = next(
            (
                event
                for event in events
                if event.get("event_id") == event_id
                and event.get("kind") == expected_source
                and event.get("category") == category
                and event.get("target_id") == target_id
                and event.get("version") == VERSION
                and event.get("activation_id") == activation_id
            ),
            None,
        )
        if source is None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            raise RuntimeProblem("gate source event does not match this project and target")
        now = int(time.time())
        requests = [
            event
            for event in events
            if event.get("kind") == expected_request
            and event.get("ref_id") == event_id
            and event.get("category") == category
            and event.get("target_id") == target_id
            and event.get("version") == VERSION
            and event.get("activation_id") == activation_id
            and now - int(event.get("ts", 0)) <= 30
        ]
        request = next(
            (
                item
                for item in reversed(requests)
                if not any(
                    event.get("kind") == "gate-check-started"
                    and event.get("ref_id") == item.get("event_id")
                    for event in events
                )
            ),
            None,
        )
        if request is None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            raise RuntimeProblem(
                "the matching PreToolUse request was not observed or was already used"
            )
        claim["ref_id"] = str(request["event_id"])
        _append_locked(handle, claim)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return source, request


def _run_fixed_gate_check(category: str, target: Path) -> int:
    if category == "recursive-delete":
        command = ["/bin/ls", "-la", str(target)]
    elif category == "git-branch-delete":
        command = ["git", "--no-optional-locks", "-C", str(target), "branch", "--list"]
    else:
        command = [
            "git",
            "--no-optional-locks",
            "-C",
            str(target),
            "status",
            "--short",
            "--branch",
        ]
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        raise RuntimeProblem("the fixed read-only check could not be started") from exc


def _cmd_gate_operation(args: argparse.Namespace) -> int:
    root = _project_root(_project_argument(args))
    if _project_status(root)["state"] != GOVERNED:
        raise RuntimeProblem("project governance is not active and healthy")
    target = _gate_target_path(args.target)
    target_id = _opaque("target", str(target))
    source, _ = _claim_gate_request(
        root,
        args.event,
        args.category,
        target_id,
        args.gate_command,
    )
    result = _run_fixed_gate_check(args.category, target)
    if result != 0:
        _append_event(
            "state-check-failed"
            if args.gate_command == "arm"
            else "obligation-check-failed",
            root,
            category=args.category,
            outcome=f"exit-{result}",
            state=GOVERNED,
            ref_id=str(source["event_id"]),
            target_id=target_id,
        )
        print("fixed read-only check failed; no gate state changed", file=sys.stderr)
        return 3
    if args.gate_command == "arm":
        _append_event(
            "state-check-observed",
            root,
            category=args.category,
            outcome="fixed-check-passed",
            state=GOVERNED,
            ref_id=str(source["event_id"]),
            target_id=target_id,
        )
        _append_event(
            "gate-armed",
            root,
            category=args.category,
            outcome="armed-after-fixed-check",
            state=GOVERNED,
            ref_id=str(source["event_id"]),
            target_id=target_id,
        )
        print(
            f"one retry is armed for {args.category}; this is not user authorization "
            "and does not bypass Codex permissions"
        )
    else:
        _append_event(
            "obligation-check-observed",
            root,
            category=args.category,
            outcome="fixed-postcondition-check-passed",
            state=GOVERNED,
            ref_id=str(source["event_id"]),
            target_id=target_id,
        )
        print(f"verification obligation {source['event_id']} is closed")
    return 0


def _positive_limit(value: str) -> int:
    number = int(value)
    if number < 1 or number > 1000:
        raise argparse.ArgumentTypeError("limit must be between 1 and 1000")
    return number


def _project_argument(args: argparse.Namespace) -> Optional[str]:
    project = getattr(args, "project", None)
    if project == "current":
        project = None
    return project or getattr(args, "global_project", None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acgm-codex")
    parser.add_argument(
        "--project",
        dest="global_project",
        help="project directory (legacy form; subcommand paths are preferred)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="show runtime version")
    init = subparsers.add_parser("init", help="create governance assets without overwriting")
    init.add_argument("project", nargs="?", help="project directory")
    activate = subparsers.add_parser("activate", help="validate and activate project governance")
    activate.add_argument("project", nargs="?", help="project directory")

    quickstart = subparsers.add_parser(
        "quickstart", help="plan, apply, or verify one-consent project governance"
    )
    quickstart_subparsers = quickstart.add_subparsers(
        dest="quickstart_command", required=True
    )
    quickstart_plan = quickstart_subparsers.add_parser(
        "plan", help="produce a read-only digest-bound quickstart plan"
    )
    quickstart_plan.add_argument("project", help="explicit Git project root")
    quickstart_plan.add_argument("--preset", default=QUICKSTART_PRESET)
    quickstart_plan.add_argument("--json", action="store_true")
    quickstart_apply = quickstart_subparsers.add_parser(
        "apply", help="apply one approved quickstart plan without overwriting policy"
    )
    quickstart_apply.add_argument("project", help="explicit Git project root")
    quickstart_apply.add_argument("--preset", default=QUICKSTART_PRESET)
    quickstart_apply.add_argument(
        "--plan-digest",
        help="required with --authorize; copy it from quickstart plan",
    )
    quickstart_apply.add_argument(
        "--authorize",
        action="store_true",
        help="authorize the exact generated plan for this project and preset",
    )
    quickstart_apply.add_argument("--json", action="store_true")
    quickstart_status = quickstart_subparsers.add_parser(
        "status", help="verify local activation and automatic Hook evidence"
    )
    quickstart_status.add_argument("project", help="explicit Git project root")
    quickstart_status.add_argument("--json", action="store_true")

    doctor = subparsers.add_parser("doctor", help="inspect install, project, hook, and ledger health")
    doctor.add_argument("project", nargs="?", help="project directory")
    doctor.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    doctor.add_argument("--strict", action="store_true", help="exit non-zero unless fully healthy")

    report = subparsers.add_parser("report", help="show the privacy-minimized activity ledger")
    report.add_argument(
        "--project",
        default="current",
        help="project directory or 'current' (default)",
    )
    report.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    report.add_argument("--limit", type=_positive_limit, default=20)

    export_case = subparsers.add_parser("export-case", help="export a sanitized event case")
    export_case.add_argument("event")
    export_case.add_argument("-o", "--output", required=True)
    export_case.add_argument("--project", help="project directory")

    resolve = subparsers.add_parser("resolve", help="append a resolution for an event")
    resolve.add_argument("event")
    resolve.add_argument("--status", required=True, choices=RESOLUTION_STATUSES)
    resolve.add_argument("--project", help="project directory")

    gate = subparsers.add_parser("gate", help="operate the high-risk action gate")
    gate_subparsers = gate.add_subparsers(dest="gate_command", required=True)
    arm = gate_subparsers.add_parser(
        "arm", help="run a fixed check and request a one-time category retry"
    )
    arm.add_argument("--event", required=True, help="gate-denied event id from the hook")
    arm.add_argument("--category", required=True, choices=GATE_CATEGORIES)
    arm.add_argument("--target", help="target directory when it differs from cwd")
    verify = gate_subparsers.add_parser(
        "verify", help="run a fixed post-action check for one obligation"
    )
    verify.add_argument(
        "--event", required=True, help="obligation-opened event id from the hook"
    )
    verify.add_argument("--category", required=True, choices=GATE_CATEGORIES)
    verify.add_argument("--target", help="target directory when it differs from cwd")

    hook = subparsers.add_parser("hook", help="dispatch one Codex lifecycle hook")
    hook.add_argument("event", choices=tuple(HOOK_NAMES))
    hook.add_argument("--project", help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "version":
            print(f"acgm-codex {VERSION}")
            return 0
        if args.command == "init":
            return _cmd_init(args)
        if args.command == "activate":
            return _cmd_activate(args)
        if args.command == "quickstart":
            return _cmd_quickstart(args)
        if args.command == "doctor":
            return _cmd_doctor(args)
        if args.command == "report":
            return _cmd_report(args)
        if args.command == "export-case":
            return _cmd_export_case(args)
        if args.command == "resolve":
            return _cmd_resolve(args)
        if args.command == "gate":
            return _cmd_gate_operation(args)
        if args.command == "hook":
            return _run_hook(args.event, _project_argument(args))
    except RuntimeProblem as exc:
        print(f"acgm-codex: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("acgm-codex: local state or ledger operation failed", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
