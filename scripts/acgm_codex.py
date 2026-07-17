#!/usr/bin/env python3
"""ACGM for Codex local governance runtime.

This module intentionally uses only the Python standard library.  Hook input is
treated as ephemeral: the activity ledger stores only controlled enums and
HMAC-derived opaque identifiers, never paths, commands, prompts, providers, or
credentials.
"""

from __future__ import annotations

import argparse
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
from typing import Any, Iterable, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - the supported platforms provide it.
    fcntl = None  # type: ignore[assignment]


def _read_version() -> str:
    try:
        value = (Path(__file__).resolve().parent.parent / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return "unknown"
    return value or "unknown"


VERSION = _read_version()
STATE_SCHEMA = "acgm-codex-state-v1"
LEDGER_SCHEMA = "acgm-codex-event-v1"
CASE_SCHEMA = "acgm-codex-case-v1"
DATA_LOCATION_SCHEMA = "acgm-codex-data-location-v1"
GATE_TTL_SECONDS = 180

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


class RuntimeProblem(Exception):
    """A user-actionable runtime or project-state problem."""


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


def _project_root(start: Optional[str] = None) -> Path:
    candidate = Path(start or os.getcwd()).expanduser()
    if not candidate.exists():
        raise RuntimeProblem("project directory does not exist")
    candidate = candidate.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    chain = (candidate,) + tuple(candidate.parents)
    for parent in chain:
        if (parent / ".acgm" / "codex.json").exists() or (parent / ".git").exists():
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


def _write_new_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, mode)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


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
    if not re.search(
        r"(?:^|[^A-Za-z0-9_.-])CONSTITUTION\.md(?:$|[^A-Za-z0-9_.-])",
        command,
        re.IGNORECASE,
    ):
        return False
    return bool(
        re.search(
            r"(?:>>?|\b(?:rm|mv|cp|tee|truncate|touch|chmod|chown)\b|"
            r"\bsed\s+[^\n]*-[A-Za-z]*i|\bperl\s+[^\n]*-[A-Za-z]*i|"
            r"\bgit\s+(?:restore\b|checkout\s+--)|\bdd\b[^\n]*\bof=|"
            r"\binstall\b|\bexport-case\b[^\n]*(?:\s-o\s|--output(?:=|\s)))",
            command,
            re.IGNORECASE,
        )
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
    root = _project_root(project)
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be an object")
    except (json.JSONDecodeError, ValueError):
        try:
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
        if project is None and isinstance(payload_cwd, str) and payload_cwd:
            root = _project_root(payload_cwd)
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
        if dispatch in {"session-start", "subagent-start", "pre-compact"}:
            _append_event(
                "hook-heartbeat",
                root,
                payload.get("session_id"),
                payload.get("turn_id"),
                category=dispatch,
                outcome="observed",
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
    state_path = _state_path(root)
    if state_path.exists():
        try:
            existing = _safe_read_json(state_path)
        except RuntimeProblem as exc:
            print(f"activation refused: {exc}", file=sys.stderr)
            return 2
        if existing.get("schema") != STATE_SCHEMA:
            print("activation refused: adapter state schema is not recognized", file=sys.stderr)
            return 2
    missing, placeholders = _asset_issues(root)
    if missing or placeholders:
        print("activation refused: governance assets are incomplete", file=sys.stderr)
        if missing:
            print("missing: " + ", ".join(missing), file=sys.stderr)
        if placeholders:
            print("placeholder or too short: " + ", ".join(placeholders), file=sys.stderr)
        return 2
    _atomic_json(
        state_path,
        {
            "schema": STATE_SCHEMA,
            "version": VERSION,
            "active": True,
            "platform": "codex",
            "activated_at": int(time.time()),
            "activation_id": secrets.token_hex(12),
            "baseline": _component_baseline(root),
        },
    )
    print("ACGM Codex project governance is active.")
    print("Start a new Codex task, trust the plugin hooks, then run doctor --strict.")
    return 0


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
