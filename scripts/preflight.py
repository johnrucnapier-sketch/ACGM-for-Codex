#!/usr/bin/env python3
"""Non-mutating-by-design public-install preflight for ACGM for Codex.

The probe never directly edits the checkout or Codex marketplace/plugin
configuration.  The Codex CLI used for state inspection can still perform its
own vendor-controlled startup housekeeping.  The probe reports observable
package, Git, platform, marketplace, plugin, and cache facts without inferring
Hook trust or a backing model/provider/account.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Sequence


PLUGIN_NAME = "acgm-codex"
MARKETPLACE_NAME = "acgm-codex"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
LEGACY_PLUGIN_ID = f"{PLUGIN_NAME}@personal"
VERSION = "0.1.0-rc.2"
TAG = "v0.1.0-rc.2"
REPOSITORY = "johnrucnapier-sketch/ACGM-for-Codex"
REPOSITORY_URL = "https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "PACKAGE_MANIFEST.json"
MINIMUM_PYTHON = (3, 10)
SUPPORTED_PLATFORMS = {"Darwin", "Linux"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXCLUDED_PARTS = {".git", ".acgm", ".venv", "__pycache__", "build", "dist"}
EXCLUDED_NAMES = {MANIFEST_NAME, ".DS_Store"}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


Runner = Callable[[Sequence[str], Path | None, dict[str, str], int], CommandResult]


def run_command(
    argv: Sequence[str], cwd: Path | None, env: dict[str, str], timeout: int
) -> CommandResult:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, timed_out=True)
    except OSError as exc:
        return CommandResult(127, stderr=str(exc))
    return CommandResult(completed.returncode, completed.stdout or "", completed.stderr or "")


def git_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """Prevent inherited Git routing/config variables from changing source identity."""

    environment = {
        key: value
        for key, value in dict(base or os.environ).items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
    )
    return environment


def neutral_cwd_is_safe(path: Path) -> bool:
    """Reject a control cwd nested under any repo or repo-local marketplace."""

    try:
        candidate = path.resolve(strict=True)
    except OSError:
        return False
    for ancestor in (candidate, *candidate.parents):
        if (ancestor / ".git").exists():
            return False
        if (ancestor / ".agents" / "plugins" / "marketplace.json").exists():
            return False
    return True


def run_codex_control(
    argv: Sequence[str], env: dict[str, str], runner: Runner, timeout: int
) -> CommandResult:
    """Run a Codex probe/mutation outside the checkout's auto-discovery scope."""

    try:
        with tempfile.TemporaryDirectory(prefix="acgm-codex-control-") as raw:
            os.chmod(raw, 0o700)
            control = Path(raw)
            if not neutral_cwd_is_safe(control):
                return CommandResult(126, stderr="unsafe neutral control cwd")
            return runner(argv, control, env, timeout)
    except OSError as exc:
        return CommandResult(126, stderr=str(exc))


def _safe_relative(value: str) -> PurePosixPath | None:
    if not value or "\\" in value or "\0" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path if path.as_posix() == value else None


def _included(value: str) -> bool:
    path = _safe_relative(value)
    return bool(
        path
        and not any(part in EXCLUDED_PARTS for part in path.parts)
        and path.name not in EXCLUDED_NAMES
        and path.suffix != ".pyc"
    )


def _regular_bytes(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("not_regular")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise ValueError("not_regular")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read()
        after = os.fstat(descriptor)
        if (
            current.st_size != after.st_size
            or current.st_mtime_ns != after.st_mtime_ns
            or current.st_ctime_ns != after.st_ctime_ns
        ):
            raise ValueError("changed_while_reading")
        return content
    finally:
        os.close(descriptor)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(_regular_bytes(path).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("not_object")
    return value


def _json_output(result: CommandResult) -> dict[str, Any] | None:
    if result.returncode != 0 or result.timed_out:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _canonical_repo(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    prefix = "https://github.com/"
    if normalized.casefold().startswith(prefix):
        normalized = normalized[len(prefix) :]
    return normalized.casefold()


def _expected_repo(value: object) -> bool:
    return _canonical_repo(value) == REPOSITORY.casefold()


def _manifest_inventory(
    root: Path, *, exact_git_inventory: bool, exact_filesystem_inventory: bool
) -> tuple[bool, list[str], dict[str, str] | None, bytes | None]:
    errors: list[str] = []
    try:
        manifest_bytes = _regular_bytes(root / MANIFEST_NAME)
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False, ["package_manifest_missing_or_invalid"], None, None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False, ["package_manifest_schema_invalid"], None, manifest_bytes
    if payload.get("version") != VERSION:
        errors.append("package_manifest_version_mismatch")
    raw_files = payload.get("files")
    if not isinstance(raw_files, dict) or not raw_files:
        return False, [*errors, "package_manifest_files_invalid"], None, manifest_bytes
    files: dict[str, str] = {}
    for name, digest in raw_files.items():
        if not isinstance(name, str) or not _included(name):
            errors.append("package_manifest_path_unsafe")
            continue
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append("package_manifest_digest_invalid")
            continue
        files[name] = digest
    if len(files) != len(raw_files):
        errors.append("package_manifest_inventory_invalid")
    for name, digest in files.items():
        try:
            actual = hashlib.sha256(_regular_bytes(root / name)).hexdigest()
        except (OSError, ValueError):
            errors.append("package_file_missing_or_unsafe")
            continue
        if actual != digest:
            errors.append("package_file_digest_mismatch")
    if exact_git_inventory:
        git = run_command(
            ["git", "--no-replace-objects", "-C", str(root), "ls-files", "-z"],
            root,
            git_environment(),
            10,
        )
        if git.returncode != 0 or git.timed_out:
            errors.append("git_inventory_unavailable")
        else:
            tracked = {
                name
                for name in git.stdout.split("\0")
                if name and _included(name)
            }
            if tracked != set(files):
                errors.append("package_manifest_git_inventory_mismatch")
    if exact_filesystem_inventory:
        actual: set[str] = set()
        try:
            paths = list(root.rglob("*"))
        except OSError:
            errors.append("package_filesystem_inventory_unavailable")
            paths = []
        for path in paths:
            try:
                relative = path.relative_to(root).as_posix()
                if not _included(relative):
                    continue
                metadata = path.lstat()
            except (OSError, ValueError):
                errors.append("package_filesystem_inventory_unavailable")
                continue
            if stat.S_ISLNK(metadata.st_mode):
                errors.append("package_filesystem_symlink_not_allowed")
            elif stat.S_ISREG(metadata.st_mode):
                actual.add(relative)
            elif not stat.S_ISDIR(metadata.st_mode):
                errors.append("package_filesystem_special_file_not_allowed")
        if actual != set(files):
            errors.append("package_manifest_filesystem_inventory_mismatch")
    return not errors, sorted(set(errors)), files, manifest_bytes


def verify_package(
    root: Path,
    *,
    exact_git_inventory: bool = False,
    exact_filesystem_inventory: bool = False,
) -> dict[str, Any]:
    ok, errors, files, manifest_bytes = _manifest_inventory(
        root,
        exact_git_inventory=exact_git_inventory,
        exact_filesystem_inventory=exact_filesystem_inventory,
    )
    return {
        "verified": ok,
        "error_codes": errors,
        "file_count": len(files or {}),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_bytes is not None
        else None,
    }


def verify_release_contract(root: Path) -> dict[str, Any]:
    """Verify identities that a hash-consistent but wrong package could violate."""

    errors: list[str] = []
    try:
        version = _regular_bytes(root / "VERSION").decode("utf-8").strip()
    except (OSError, ValueError, UnicodeDecodeError):
        version = None
    if version != VERSION:
        errors.append("version_file_mismatch")
    try:
        plugin = _read_json(root / ".codex-plugin" / "plugin.json")
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        plugin = {}
        errors.append("plugin_manifest_missing_or_invalid")
    if plugin.get("name") != PLUGIN_NAME or plugin.get("version") != VERSION:
        errors.append("plugin_manifest_identity_or_version_mismatch")
    try:
        marketplace = _read_json(root / ".agents" / "plugins" / "marketplace.json")
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        marketplace = {}
        errors.append("marketplace_manifest_missing_or_invalid")
    entries = marketplace.get("plugins")
    entry = entries[0] if isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict) else {}
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    policy = entry.get("policy") if isinstance(entry.get("policy"), dict) else {}
    if (
        marketplace.get("name") != MARKETPLACE_NAME
        or entry.get("name") != PLUGIN_NAME
        or source.get("source") != "url"
        or not _expected_repo(source.get("url"))
        or source.get("ref") != TAG
        or policy.get("installation") != "AVAILABLE"
        or policy.get("authentication") != "ON_INSTALL"
        or not isinstance(entry.get("category"), str)
        or not entry.get("category")
    ):
        errors.append("marketplace_manifest_contract_mismatch")
    return {"verified": not errors, "error_codes": sorted(set(errors))}


def _git_source(root: Path, env: dict[str, str], runner: Runner) -> dict[str, Any]:
    facts: dict[str, Any] = {"verified": False, "error_codes": []}
    safe_env = git_environment(env)
    head = runner(
        ["git", "--no-replace-objects", "-C", str(root), "rev-parse", "HEAD"],
        root,
        safe_env,
        10,
    )
    tag = runner(
        [
            "git",
            "--no-replace-objects",
            "-C",
            str(root),
            "rev-parse",
            f"refs/tags/{TAG}^{{commit}}",
        ],
        root,
        safe_env,
        10,
    )
    status = runner(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        root,
        safe_env,
        10,
    )
    remote = runner(
        ["git", "--no-replace-objects", "-C", str(root), "remote", "get-url", "origin"],
        root,
        safe_env,
        10,
    )
    if head.returncode != 0:
        facts["error_codes"].append("git_head_unavailable")
    if tag.returncode != 0:
        facts["error_codes"].append("release_tag_missing")
    if head.returncode == 0 and tag.returncode == 0 and head.stdout.strip() != tag.stdout.strip():
        facts["error_codes"].append("head_not_exact_release_tag")
    if status.returncode != 0:
        facts["error_codes"].append("git_status_unavailable")
    elif status.stdout.strip():
        facts["error_codes"].append("checkout_not_clean")
    if remote.returncode != 0 or not _expected_repo(remote.stdout.strip()):
        facts["error_codes"].append("origin_not_expected_repository")
    facts["head"] = head.stdout.strip() if head.returncode == 0 else None
    facts["tag"] = TAG
    facts["clean"] = status.returncode == 0 and not bool(status.stdout.strip())
    facts["origin_matches"] = remote.returncode == 0 and _expected_repo(remote.stdout.strip())
    facts["verified"] = not facts["error_codes"]
    return facts


def _marketplace_exact(item: dict[str, Any]) -> bool:
    source = item.get("marketplaceSource")
    if not isinstance(source, dict):
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
    source_type = source.get("sourceType", source.get("source_type"))
    raw_source = source.get("source", source.get("url"))
    return (
        source_type == "git"
        and _expected_repo(raw_source)
        and source.get("ref") == TAG
    )


def _plugin_source_exact(item: dict[str, Any]) -> bool:
    source = item.get("source")
    return bool(
        isinstance(source, dict)
        and source.get("source") == "url"
        and _expected_repo(source.get("url"))
        and source.get("ref") == TAG
    )


def inspect_codex_state(
    *, source_root: Path, env: dict[str, str], runner: Runner
) -> dict[str, Any]:
    marketplace_result = run_codex_control(
        ["codex", "plugin", "marketplace", "list", "--json"], env, runner, 30
    )
    plugin_result = run_codex_control(
        ["codex", "plugin", "list", "--available", "--json"],
        env,
        runner,
        30,
    )
    marketplace_payload = _json_output(marketplace_result)
    plugin_payload = _json_output(plugin_result)
    if marketplace_payload is None or plugin_payload is None:
        return {
            "readable": False,
            "error_codes": ["codex_state_json_unavailable"],
            "marketplace": "UNKNOWN",
            "plugin": "UNKNOWN",
            "cache_verified": False,
        }
    marketplaces = marketplace_payload.get("marketplaces", [])
    installed = plugin_payload.get("installed", [])
    available = plugin_payload.get("available", [])
    if not all(isinstance(value, list) for value in (marketplaces, installed, available)):
        return {
            "readable": False,
            "error_codes": ["codex_state_json_shape_invalid"],
            "marketplace": "UNKNOWN",
            "plugin": "UNKNOWN",
            "cache_verified": False,
        }
    marketplace_matches = [
        item
        for item in marketplaces
        if isinstance(item, dict) and item.get("name") == MARKETPLACE_NAME
    ]
    plugin_matches = [
        item
        for item in [*installed, *available]
        if isinstance(item, dict) and item.get("name") == PLUGIN_NAME
    ]
    installed_matches = [
        item
        for item in installed
        if isinstance(item, dict) and item.get("name") == PLUGIN_NAME
    ]
    errors: list[str] = []
    if marketplace_matches and all(_marketplace_exact(item) for item in marketplace_matches):
        marketplace_state = "EXACT"
    elif marketplace_matches:
        marketplace_state = "CONFLICT"
    else:
        marketplace_state = "ABSENT"
    legacy = any(item.get("pluginId") == LEGACY_PLUGIN_ID for item in installed_matches)
    if legacy:
        errors.append("legacy_personal_install_requires_manual_migration")
    if len(marketplace_matches) > 1:
        errors.append("duplicate_marketplace_entries")
    if marketplace_matches and not all(_marketplace_exact(item) for item in marketplace_matches):
        errors.append("marketplace_source_or_ref_conflict")
    foreign_plugins = [
        item for item in plugin_matches if item.get("pluginId") != PLUGIN_ID
    ]
    if foreign_plugins:
        errors.append("duplicate_or_foreign_plugin_install")
    exact_installed = [item for item in installed_matches if item.get("pluginId") == PLUGIN_ID]
    exact_available = [
        item
        for item in available
        if isinstance(item, dict) and item.get("pluginId") == PLUGIN_ID
    ]
    if len(exact_installed) > 1:
        errors.append("duplicate_exact_plugin_install")
    if len(exact_available) > 1:
        errors.append("duplicate_exact_available_plugin")
    installed_item = exact_installed[0] if len(exact_installed) == 1 else None
    available_item = exact_available[0] if len(exact_available) == 1 else None
    if installed_item is not None and (
        installed_item.get("version") != VERSION
        or installed_item.get("installed") is not True
        or installed_item.get("enabled") is not True
        or installed_item.get("scope") not in {None, "user"}
        or not _plugin_source_exact(installed_item)
    ):
        errors.append("installed_plugin_identity_version_or_source_conflict")
    if installed_item is not None and marketplace_state != "EXACT":
        errors.append("installed_plugin_marketplace_missing_or_not_exact")
    available_item_exact = bool(
        available_item is not None
        and available_item.get("name") == PLUGIN_NAME
        and available_item.get("version") == VERSION
        and available_item.get("installed") is False
        and available_item.get("enabled") is False
        and _plugin_source_exact(available_item)
    )
    if available_item is not None and not available_item_exact:
        errors.append("available_plugin_identity_version_or_source_conflict")
    if marketplace_state == "EXACT" and installed_item is None:
        if available_item is None:
            errors.append("marketplace_expected_plugin_missing")
        elif not available_item_exact:
            errors.append("marketplace_expected_plugin_invalid")

    cache_verified = False
    cache_check: dict[str, Any] | None = None
    if installed_item is not None and not errors:
        codex_home = Path(env.get("CODEX_HOME", str(Path(env.get("HOME", "~")).expanduser() / ".codex")))
        cache = codex_home / "plugins" / "cache" / MARKETPLACE_NAME / PLUGIN_NAME / VERSION
        cache_check = verify_package(
            cache,
            exact_git_inventory=False,
            exact_filesystem_inventory=True,
        )
        try:
            source_manifest = _regular_bytes(source_root / MANIFEST_NAME)
            cache_manifest = _regular_bytes(cache / MANIFEST_NAME)
            same_manifest = source_manifest == cache_manifest
        except (OSError, ValueError):
            same_manifest = False
        cache_verified = bool(cache_check["verified"] and same_manifest)
        if not cache_verified:
            errors.append("installed_cache_bytes_unverified")

    if installed_item is not None and not errors:
        plugin_state = "INSTALLED_ENABLED_EXACT"
    elif installed_item is not None:
        plugin_state = "CONFLICT_OR_PARTIAL"
    elif plugin_matches:
        plugin_state = "AVAILABLE_EXACT" if available_item_exact and not errors else "CONFLICT"
    else:
        plugin_state = "ABSENT"
    return {
        "readable": True,
        "error_codes": sorted(set(errors)),
        "marketplace": marketplace_state,
        "plugin": plugin_state,
        "cache_verified": cache_verified,
        "cache_check": cache_check,
        "legacy_personal_present": legacy,
    }


def _actions(status: str, hook_hash: str | None) -> list[dict[str, Any]]:
    if status == "READY_FOR_INSTALL":
        return [
            {
                "id": "add_exact_git_marketplace",
                "argv": [
                    "codex",
                    "plugin",
                    "marketplace",
                    "add",
                    REPOSITORY,
                    "--ref",
                    TAG,
                    "--json",
                ],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
            {
                "id": "install_exact_plugin",
                "argv": ["codex", "plugin", "add", PLUGIN_ID, "--json"],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
        ]
    if status == "READY_FOR_PLUGIN_ADD":
        return [
            {
                "id": "install_exact_plugin",
                "argv": ["codex", "plugin", "add", PLUGIN_ID, "--json"],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            }
        ]
    if status == "INSTALLED_ENABLED_PENDING_HOOK_TRUST":
        return [
            {
                "id": "start_discovery_task",
                "instruction": "Start a new Codex discovery task so the installed plugin, skills, and Hook definitions load.",
                "mutates_user_config": False,
                "requires_explicit_authorization": False,
            },
            {
                "id": "review_hook_hash",
                "instruction": f"Open /hooks and review the exact hooks/hooks.json SHA-256: {hook_hash}",
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
            {
                "id": "start_verification_task",
                "instruction": "After trusting the definition, start a second new Codex verification task so trusted SessionStart runs from task start.",
                "mutates_user_config": False,
                "requires_explicit_authorization": False,
            },
        ]
    if status == "MIGRATION_REQUIRED":
        return [
            {
                "id": "manual_migration_review",
                "instruction": "Inventory exact installs and back up complete PLUGIN_DATA/Event Ledger plus its HMAC key. Removal, replacement, data adoption, and migration require separate user authorization.",
                "executable": False,
                "requires_separate_authorization": True,
            }
        ]
    return []


def evaluate(
    source_root: Path = SOURCE_ROOT,
    *,
    env: dict[str, str] | None = None,
    runner: Runner = run_command,
    platform_name: str | None = None,
    python_version: tuple[int, int] | None = None,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    environment = dict(env or os.environ)
    system = platform_name or platform.system()
    py_version = python_version or (sys.version_info.major, sys.version_info.minor)
    errors: list[str] = []
    if system not in SUPPORTED_PLATFORMS:
        errors.append("unsupported_platform_posix_fcntl_required")
    if py_version < MINIMUM_PYTHON:
        errors.append("python_3_10_or_newer_required")

    git_help = runner(["git", "--version"], source_root, environment, 5)
    if git_help.returncode != 0 or git_help.timed_out:
        errors.append("git_unavailable")
    help_probes = {
        "marketplace_add": run_codex_control(
            ["codex", "plugin", "marketplace", "add", "--help"],
            environment,
            runner,
            10,
        ),
        "plugin_add": run_codex_control(
            ["codex", "plugin", "add", "--help"], environment, runner, 10
        ),
        "plugin_list": run_codex_control(
            ["codex", "plugin", "list", "--help"], environment, runner, 10
        ),
    }
    if any(item.returncode != 0 or item.timed_out for item in help_probes.values()):
        errors.append("codex_plugin_cli_unavailable")
    elif not (
        "--ref" in help_probes["marketplace_add"].stdout
        and "--json" in help_probes["marketplace_add"].stdout
        and "--json" in help_probes["plugin_add"].stdout
        and "--available" in help_probes["plugin_list"].stdout
    ):
        errors.append("codex_plugin_cli_contract_unsupported")

    git = _git_source(source_root, environment, runner) if "git_unavailable" not in errors else {
        "verified": False,
        "error_codes": ["git_unavailable"],
    }
    package = verify_package(source_root, exact_git_inventory=True)
    release_contract = verify_release_contract(source_root)
    errors.extend(git.get("error_codes", []))
    errors.extend(package["error_codes"])
    errors.extend(release_contract["error_codes"])

    codex_state: dict[str, Any]
    if not any(code.startswith("codex_plugin_cli") for code in errors):
        codex_state = inspect_codex_state(
            source_root=source_root, env=environment, runner=runner
        )
        errors.extend(codex_state["error_codes"])
    else:
        codex_state = {
            "readable": False,
            "error_codes": ["codex_state_not_probed"],
            "marketplace": "UNKNOWN",
            "plugin": "UNKNOWN",
            "cache_verified": False,
        }

    conflict_codes = {
        "legacy_personal_install_requires_manual_migration",
        "duplicate_marketplace_entries",
        "marketplace_source_or_ref_conflict",
        "duplicate_or_foreign_plugin_install",
        "duplicate_exact_plugin_install",
        "installed_plugin_identity_version_or_source_conflict",
        "installed_plugin_marketplace_missing_or_not_exact",
    }
    unique_errors = sorted(set(errors))
    hard_errors = [code for code in unique_errors if code not in conflict_codes]
    if hard_errors:
        status = "BLOCKED"
    elif any(code in conflict_codes for code in unique_errors):
        status = "MIGRATION_REQUIRED"
    elif codex_state["plugin"] == "INSTALLED_ENABLED_EXACT" and codex_state["cache_verified"]:
        status = "INSTALLED_ENABLED_PENDING_HOOK_TRUST"
    elif codex_state["marketplace"] == "EXACT":
        status = "READY_FOR_PLUGIN_ADD"
    else:
        status = "READY_FOR_INSTALL"

    try:
        hook_hash = hashlib.sha256(_regular_bytes(source_root / "hooks" / "hooks.json")).hexdigest()
    except (OSError, ValueError):
        hook_hash = None
        if "package_file_missing_or_unsafe" not in unique_errors:
            unique_errors.append("hook_definition_unavailable")
            status = "BLOCKED"
    lifecycle = {
        "source": "VERIFIED"
        if git.get("verified") and package["verified"] and release_contract["verified"]
        else "UNVERIFIED",
        "marketplace": codex_state["marketplace"],
        "installed_enabled": codex_state["plugin"],
        "package_bytes": "VERIFIED" if codex_state["cache_verified"] else "NOT_VERIFIED",
        "hook_trust": "DISCOVERY_TASK_USER_REVIEW_REQUIRED" if status == "INSTALLED_ENABLED_PENDING_HOOK_TRUST" else "NOT_REACHED",
        "heartbeat": "SECOND_NEW_TASK_AFTER_TRUST_REQUIRED" if status == "INSTALLED_ENABLED_PENDING_HOOK_TRUST" else "NOT_REACHED",
        "project_bootstrap": "EXPLICIT_TARGET_AND_SKILL_REQUIRED",
    }
    actions = _actions(status, hook_hash)
    return {
        "schema": "acgm-codex-preflight-v1",
        "ok": status in {
            "READY_FOR_INSTALL",
            "READY_FOR_PLUGIN_ADD",
            "INSTALLED_ENABLED_PENDING_HOOK_TRUST",
        },
        "status": status,
        "version": VERSION,
        "tag": TAG,
        "platform": {
            "name": system,
            "supported": system in SUPPORTED_PLATFORMS,
            "windows_runtime_supported": False,
        },
        "python": {"version": ".".join(map(str, py_version)), "supported": py_version >= MINIMUM_PYTHON},
        "source": {"git": git, "package": package, "release_contract": release_contract},
        "codex": codex_state,
        "hook_definition_sha256": hook_hash,
        "lifecycle": lifecycle,
        "error_codes": sorted(set(unique_errors)),
        "actions": actions,
        "requires_user_action": bool(actions) or status in {"BLOCKED", "MIGRATION_REQUIRED"},
        "claims": {
            "hook_trusted": False,
            "heartbeat_verified": False,
            "project_bootstrapped": False,
            "provider_or_model_inferred": False,
            "publisher_signature_verified": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    payload = evaluate(args.source_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ACGM for Codex preflight: {payload['status']}")
        for code in payload["error_codes"]:
            print(f"- {code}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
