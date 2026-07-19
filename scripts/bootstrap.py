#!/usr/bin/env python3
"""Conservative public bootstrap for the tagged ACGM Codex marketplace.

No mutation occurs in dry-run mode or without ``--authorize-install``.  A
unique, verified older release from this same official user marketplace may be
replaced by the exact planned remove/add/add sequence.  Unknown, legacy,
foreign, duplicate, personal, and newer installs remain fail-closed, and
private plugin data is never touched.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import sys
from typing import Any, Sequence

import preflight


SOURCE_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_ADD = [
    "codex",
    "plugin",
    "marketplace",
    "add",
    preflight.REPOSITORY,
    "--ref",
    preflight.TAG,
    "--json",
]
PLUGIN_ADD = ["codex", "plugin", "add", preflight.PLUGIN_ID, "--json"]
MARKETPLACE_REMOVE = [
    "codex",
    "plugin",
    "marketplace",
    "remove",
    preflight.MARKETPLACE_NAME,
    "--json",
]


def _rename_directory_noreplace(parent: Path, source: str, destination: str) -> None:
    """Atomically publish a prepared bridge without replacing cache state."""

    descriptor = os.open(
        parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        library = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            function = getattr(library, "renameatx_np", None)
            flag = 0x00000004
        elif sys.platform.startswith("linux"):
            function = getattr(library, "renameat2", None)
            flag = 0x00000001
        else:
            function = None
            flag = 0
        if function is None:
            raise OSError(errno.ENOSYS, "atomic no-replace rename unavailable")
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
                descriptor,
                os.fsencode(source),
                descriptor,
                os.fsencode(destination),
                flag,
            )
            == 0
        ):
            return
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination)
    finally:
        os.close(descriptor)


def _verified_old_runtime(
    path: Path, *, from_version: str, manifest_sha256: object
) -> bool:
    """Recognize the already-authorized immutable old cache without rewriting it."""

    if not isinstance(manifest_sha256, str):
        return False
    exact_git_inventory = False
    try:
        git_metadata = (path / ".git").lstat()
    except FileNotFoundError:
        pass
    except OSError:
        return False
    else:
        if stat.S_ISLNK(git_metadata.st_mode) or not stat.S_ISDIR(
            git_metadata.st_mode
        ):
            return False
        exact_git_inventory = True
    package = preflight.verify_package(
        path,
        exact_git_inventory=exact_git_inventory,
        exact_filesystem_inventory=True,
        expected_version=from_version,
        expected_tag=f"v{from_version}",
    )
    return bool(
        package.get("verified")
        and package.get("manifest_sha256") == manifest_sha256
    )


def _ensure_one_old_hook_path(
    environment: dict[str, str],
    *,
    from_version: str,
    authorized_manifest_sha256: object = None,
) -> dict[str, Any]:
    """Keep one known old live-task Hook path executable."""

    if (
        from_version not in preflight.KNOWN_OFFICIAL_UPGRADE_VERSIONS
        or from_version == preflight.VERSION
    ):
        return {
            "required": True,
            "protected": False,
            "state": "unauthorized-origin",
            "from_version": from_version,
        }
    cache_root = (
        preflight._codex_home(environment)
        / "plugins"
        / "cache"
        / preflight.MARKETPLACE_NAME
        / preflight.PLUGIN_NAME
    )
    bridge = cache_root / from_version
    if preflight._hook_bridge_verified(
        bridge,
        from_version=from_version,
        target_version=preflight.VERSION,
    ):
        return {
            "required": True,
            "protected": True,
            "state": "bridge-present",
            "from_version": from_version,
        }
    if _verified_old_runtime(
        bridge,
        from_version=from_version,
        manifest_sha256=authorized_manifest_sha256,
    ):
        return {
            "required": True,
            "protected": True,
            "state": "full-runtime-present",
            "from_version": from_version,
        }
    try:
        if bridge.exists() or bridge.is_symlink():
            raise FileExistsError("unrecognized old cache entry")
        cache_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        cache_metadata = cache_root.lstat()
        if stat.S_ISLNK(cache_metadata.st_mode) or not stat.S_ISDIR(
            cache_metadata.st_mode
        ):
            raise OSError("unsafe plugin cache root")
        private_name = f".{from_version}.acgm-hook-bridge-{secrets.token_hex(12)}"
        private = cache_root / private_name
        (private / "scripts").mkdir(mode=0o700, parents=True)
        script = private / "scripts" / "acgm_codex.py"
        marker = private / preflight.HOOK_BRIDGE_MARKER
        script.write_bytes(preflight.HOOK_BRIDGE_SCRIPT)
        marker.write_bytes(
            preflight.hook_bridge_marker_bytes(from_version, preflight.VERSION)
        )
        os.chmod(script, 0o600)
        os.chmod(marker, 0o600)
        try:
            _rename_directory_noreplace(cache_root, private_name, from_version)
        except Exception:
            if private.exists():
                shutil.rmtree(private)
            raise
        if not preflight._hook_bridge_verified(
            bridge,
            from_version=from_version,
            target_version=preflight.VERSION,
        ):
            raise OSError("published Hook bridge did not verify")
    except (OSError, ValueError) as exc:
        return {
            "required": True,
            "protected": False,
            "state": "bridge-unavailable",
            "from_version": from_version,
            "error": type(exc).__name__,
        }
    return {
        "required": True,
        "protected": True,
        "state": "bridge-created",
        "from_version": from_version,
    }


def _ensure_old_hook_bridge(
    environment: dict[str, str], origin: dict[str, Any] | None
) -> dict[str, Any]:
    """Protect every known pre-guard Hook path, including already-stale tasks."""

    origin_version = origin.get("from_version") if isinstance(origin, dict) else None
    if not isinstance(origin_version, str):
        return {"required": False, "protected": True, "state": "not-required"}
    if origin_version not in preflight.KNOWN_OFFICIAL_UPGRADE_VERSIONS:
        return {
            "required": True,
            "protected": False,
            "state": "unauthorized-origin",
            "from_version": origin_version,
            "paths": [],
        }
    paths = [
        _ensure_one_old_hook_path(
            environment,
            from_version=version,
            authorized_manifest_sha256=(
                origin.get("cache_manifest_sha256")
                if version == origin_version
                else None
            ),
        )
        for version in sorted(preflight.KNOWN_OFFICIAL_UPGRADE_VERSIONS)
        if version != preflight.VERSION
    ]
    origin_path = next(
        (item for item in paths if item.get("from_version") == origin_version),
        None,
    )
    protected = bool(paths) and all(item.get("protected") for item in paths)
    return {
        "required": True,
        "protected": protected,
        "state": (
            str(origin_path.get("state"))
            if protected and isinstance(origin_path, dict)
            else "bridge-set-unavailable"
        ),
        "from_version": origin_version,
        "paths": paths,
    }


def _record_old_hook_protection(
    payload: dict[str, Any],
    environment: dict[str, str],
    origin: dict[str, Any] | None,
) -> bool:
    result = _ensure_old_hook_bridge(environment, origin)
    payload.setdefault("old_hook_protection", []).append(result)
    if result["protected"]:
        return True
    payload["status"] = "OLD_HOOK_PROTECTION_FAILED_STATE_REQUIRES_RECHECK"
    payload["partial"] = True
    return False


def _migration_plan() -> dict[str, Any]:
    return {
        "executable": False,
        "requires_separate_authorization": True,
        "automatic_data_adoption": False,
        "steps": [
            "Close active Codex tasks and inventory every acgm-codex marketplace, scope, version, source, cache, and enabled state.",
            "Back up the complete private PLUGIN_DATA/Event Ledger together with its HMAC key; do not copy it into the new package automatically.",
            "Review an exact uninstall/remove plan and obtain separate user authorization before changing any legacy or conflicting entry.",
            "After the conflict is resolved outside bootstrap, rerun read-only preflight from the exact release tag.",
        ],
    }


def _command_summary(argv: Sequence[str], result: preflight.CommandResult) -> dict[str, Any]:
    return {
        "argv": list(argv),
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "succeeded": result.returncode == 0 and not result.timed_out,
    }


def _entry_identity(path: Path) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"kind": "absent"}
    if stat.S_ISDIR(metadata.st_mode):
        kind = "directory"
    elif stat.S_ISREG(metadata.st_mode):
        kind = "regular-file"
    elif stat.S_ISLNK(metadata.st_mode):
        kind = "symlink"
    else:
        kind = "special"
    return {
        "kind": kind,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
    }


def _codex_install_target(environment: dict[str, str]) -> dict[str, Any]:
    """Return a non-reversible identity for the exact Codex profile target."""

    logical = preflight._codex_home(environment)
    if not logical.is_absolute():
        raise ValueError("effective Codex home must be absolute")
    logical = Path(os.path.abspath(os.path.normpath(str(logical))))
    resolved = logical.resolve(strict=False)
    return {
        "schema": "acgm-codex-install-target-v1",
        "selector": "CODEX_HOME"
        if environment.get("CODEX_HOME")
        else "HOME_DEFAULT",
        "logical_path_sha256": hashlib.sha256(os.fsencode(str(logical))).hexdigest(),
        "resolved_path_sha256": hashlib.sha256(os.fsencode(str(resolved))).hexdigest(),
        "logical_entry": _entry_identity(logical),
        "resolved_entry": _entry_identity(resolved),
    }


def _install_authorization_plan(
    source_root: Path,
    initial: dict[str, Any],
    install_target: dict[str, Any],
) -> dict[str, Any]:
    """Return the complete stable install state and exact executable plan."""

    actions = [
        action
        for action in initial.get("actions", [])
        if isinstance(action, dict) and isinstance(action.get("argv"), list)
    ]
    return {
        "schema": "acgm-codex-install-authorization-plan-v2",
        "source_root": str(source_root),
        "install_target": install_target,
        "version": preflight.VERSION,
        "tag": preflight.TAG,
        "status": initial.get("status"),
        "platform": initial.get("platform"),
        "python": initial.get("python"),
        "source": initial.get("source"),
        "codex": initial.get("codex"),
        "hook_definition_sha256": initial.get("hook_definition_sha256"),
        "lifecycle": initial.get("lifecycle"),
        "error_codes": initial.get("error_codes"),
        "actions": actions,
    }


def _install_plan_digest(plan: dict[str, Any]) -> str:
    canonical = json.dumps(
        plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _upgrade_origin(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the old installed release identity bound into authorization."""

    codex = state.get("codex")
    if not isinstance(codex, dict):
        return None
    if state.get("status") == "READY_FOR_OFFICIAL_UPGRADE":
        evidence = codex.get("official_upgrade")
        cache = codex.get("cache_check")
        if not isinstance(evidence, dict) or not isinstance(cache, dict):
            return None
        return {
            "from_version": evidence.get("from_version"),
            "from_ref": evidence.get("from_ref"),
            "scope": evidence.get("scope"),
            "cache_manifest_sha256": cache.get("manifest_sha256"),
        }
    if state.get("status") == "READY_FOR_OFFICIAL_UPGRADE_RECOVERY":
        evidence = codex.get("official_upgrade_transition")
        if not isinstance(evidence, dict) or not evidence.get("recoverable"):
            return None
        return {
            "from_version": evidence.get("from_version"),
            "from_ref": evidence.get("from_ref"),
            "scope": evidence.get("scope"),
            "cache_manifest_sha256": evidence.get("cache_manifest_sha256"),
        }
    return None


def _transition_matches_authorized_origin(
    state: dict[str, Any], origin: dict[str, Any] | None
) -> bool:
    """Accept only the exact target transition from the authorized old bytes."""

    if origin is None or state.get("status") != "READY_FOR_OFFICIAL_UPGRADE_RECOVERY":
        return False
    codex = state.get("codex")
    transition = (
        codex.get("official_upgrade_transition")
        if isinstance(codex, dict)
        else None
    )
    return bool(
        isinstance(transition, dict)
        and transition.get("recoverable") is True
        and transition.get("strategy") == "PLUGIN_ADD_ONLY"
        and transition.get("observed_version") == preflight.VERSION
        and transition.get("observed_ref") == preflight.TAG
        and all(transition.get(key) == value for key, value in origin.items())
    )


def execute(
    source_root: Path = SOURCE_ROOT,
    *,
    dry_run: bool,
    authorized: bool,
    expected_plan_digest: str | None = None,
    env: dict[str, str] | None = None,
    runner: preflight.Runner = preflight.run_command,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    environment = preflight.normalized_codex_environment(
        dict(env or os.environ)
    )
    initial = preflight.evaluate(source_root, env=environment, runner=runner)
    plan = [
        action
        for action in initial["actions"]
        if isinstance(action, dict) and isinstance(action.get("argv"), list)
    ]
    authorization_plan = _install_authorization_plan(
        source_root, initial, _codex_install_target(environment)
    )
    authorization_plan_digest = _install_plan_digest(authorization_plan)
    payload: dict[str, Any] = {
        "schema": "acgm-codex-bootstrap-v1",
        "ok": False,
        "dry_run": dry_run,
        "authorized": authorized,
        "version": preflight.VERSION,
        "tag": preflight.TAG,
        "initial_status": initial["status"],
        "status": initial["status"],
        "commands_run": [],
        "plan": plan,
        "authorization_plan": authorization_plan,
        "install_plan_digest": authorization_plan_digest,
        "preflight": initial,
        "lifecycle": dict(initial["lifecycle"]),
        "requires_user_action": True,
        "claims": {
            "hook_trusted": False,
            "heartbeat_verified": False,
            "project_bootstrapped": False,
        },
    }
    mutation_statuses = {
        "READY_FOR_INSTALL",
        "READY_FOR_PLUGIN_ADD",
        "READY_FOR_OFFICIAL_UPGRADE",
        "READY_FOR_OFFICIAL_UPGRADE_RECOVERY",
    }
    if not dry_run and authorized and initial["status"] in mutation_statuses:
        if expected_plan_digest is None:
            payload["status"] = "INSTALL_PLAN_DIGEST_REQUIRED"
            payload["requires_install_plan_digest"] = True
            return payload
        if expected_plan_digest != authorization_plan_digest:
            payload["status"] = "INSTALL_PLAN_STALE"
            payload["expected_install_plan_digest"] = expected_plan_digest
            return payload
    if initial["status"] == "MIGRATION_REQUIRED":
        payload["status"] = "MIGRATION_REQUIRED"
        payload["migration_plan"] = _migration_plan()
        return payload
    if initial["status"] == "BLOCKED":
        return payload
    if initial["status"] == "INSTALLED_ENABLED_PENDING_HOOK_TRUST":
        payload["ok"] = True
        payload["idempotent"] = True
        payload["status"] = initial["status"]
        payload["next_actions"] = initial["actions"]
        return payload

    if dry_run:
        payload["ok"] = True
        payload["status"] = "DRY_RUN_PLAN_READY"
        payload["requires_explicit_install_authorization"] = True
        return payload
    if not authorized:
        payload["status"] = "AUTHORIZATION_REQUIRED"
        payload["requires_explicit_install_authorization"] = True
        return payload

    current = initial
    authorized_upgrade_origin = _upgrade_origin(initial)
    transition = initial.get("codex", {}).get(
        "official_upgrade_transition", {}
    )
    restart_recovery = bool(
        initial["status"] == "READY_FOR_OFFICIAL_UPGRADE_RECOVERY"
        and isinstance(transition, dict)
        and transition.get("strategy") == "RESTART_TO_CURRENT"
    )
    if current["status"] == "READY_FOR_OFFICIAL_UPGRADE" or restart_recovery:
        result = preflight.run_codex_control(
            MARKETPLACE_REMOVE, environment, runner, 180
        )
        payload["commands_run"].append(_command_summary(MARKETPLACE_REMOVE, result))
        if not _record_old_hook_protection(
            payload, environment, authorized_upgrade_origin
        ):
            return payload
        if result.returncode != 0 or result.timed_out:
            payload["status"] = "MARKETPLACE_REMOVE_FAILED_STATE_REQUIRES_RECHECK"
            payload["partial"] = True
            payload["postflight"] = preflight.evaluate(
                source_root, env=environment, runner=runner
            )
            payload["lifecycle"] = dict(payload["postflight"]["lifecycle"])
            return payload
        current = preflight.evaluate(source_root, env=environment, runner=runner)
        payload["after_marketplace_remove"] = current
        if current["status"] != "READY_FOR_INSTALL":
            payload["status"] = "MARKETPLACE_REMOVED_BUT_POSTCONDITION_UNVERIFIED"
            payload["partial"] = True
            payload["lifecycle"] = dict(current["lifecycle"])
            return payload

    if current["status"] == "READY_FOR_INSTALL":
        result = preflight.run_codex_control(
            MARKETPLACE_ADD, environment, runner, 180
        )
        payload["commands_run"].append(_command_summary(MARKETPLACE_ADD, result))
        if not _record_old_hook_protection(
            payload, environment, authorized_upgrade_origin
        ):
            return payload
        if result.returncode != 0 or result.timed_out:
            payload["status"] = "MARKETPLACE_ADD_FAILED_STATE_REQUIRES_RECHECK"
            payload["partial"] = True
            payload["postflight"] = preflight.evaluate(
                source_root, env=environment, runner=runner
            )
            payload["lifecycle"] = dict(payload["postflight"]["lifecycle"])
            return payload
        current = preflight.evaluate(source_root, env=environment, runner=runner)
        payload["after_marketplace_add"] = current
        ordinary_postcondition = current["status"] in {
            "READY_FOR_PLUGIN_ADD",
            "INSTALLED_ENABLED_PENDING_HOOK_TRUST",
        }
        authorized_transition = _transition_matches_authorized_origin(
            current, authorized_upgrade_origin
        )
        if not ordinary_postcondition and not authorized_transition:
            payload["status"] = "MARKETPLACE_ADDED_BUT_POSTCONDITION_UNVERIFIED"
            payload["partial"] = True
            payload["lifecycle"] = dict(current["lifecycle"])
            return payload

    if current["status"] == "READY_FOR_OFFICIAL_UPGRADE_RECOVERY" and not (
        _transition_matches_authorized_origin(
            current, authorized_upgrade_origin
        )
    ):
        payload["status"] = "OFFICIAL_UPGRADE_TRANSITION_UNVERIFIED"
        payload["partial"] = True
        payload["lifecycle"] = dict(current["lifecycle"])
        return payload

    if current["status"] in {
        "READY_FOR_PLUGIN_ADD",
        "READY_FOR_OFFICIAL_UPGRADE_RECOVERY",
    }:
        result = preflight.run_codex_control(PLUGIN_ADD, environment, runner, 180)
        payload["commands_run"].append(_command_summary(PLUGIN_ADD, result))
        if not _record_old_hook_protection(
            payload, environment, authorized_upgrade_origin
        ):
            return payload
        if result.returncode != 0 or result.timed_out:
            payload["status"] = "PLUGIN_ADD_FAILED_MARKETPLACE_MAY_REMAIN"
            payload["partial"] = True
            payload["postflight"] = preflight.evaluate(
                source_root, env=environment, runner=runner
            )
            payload["lifecycle"] = dict(payload["postflight"]["lifecycle"])
            return payload

    final = preflight.evaluate(source_root, env=environment, runner=runner)
    payload["postflight"] = final
    payload["lifecycle"] = dict(final["lifecycle"])
    if final["status"] != "INSTALLED_ENABLED_PENDING_HOOK_TRUST":
        payload["status"] = "INSTALL_COMMANDS_FINISHED_BUT_VERIFICATION_FAILED"
        payload["partial"] = True
        return payload

    payload["ok"] = True
    payload["status"] = "INSTALLED_ENABLED_PENDING_HOOK_TRUST"
    payload["next_actions"] = final["actions"]
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show the plan without mutation")
    parser.add_argument(
        "--authorize-install",
        action="store_true",
        help="confirm explicit authorization for the exact marketplace/plugin mutations",
    )
    parser.add_argument(
        "--plan-digest",
        help="required for authorized mutation; copy it from the immediately preceding dry run",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    payload = execute(
        args.source_root,
        dry_run=args.dry_run,
        authorized=args.authorize_install,
        expected_plan_digest=args.plan_digest,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ACGM for Codex bootstrap: {payload['status']}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
