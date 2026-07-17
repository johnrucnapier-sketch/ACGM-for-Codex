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
import hashlib
import json
import os
from pathlib import Path
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


def _install_authorization_plan(
    source_root: Path, initial: dict[str, Any]
) -> dict[str, Any]:
    """Return the complete stable install state and exact executable plan."""

    actions = [
        action
        for action in initial.get("actions", [])
        if isinstance(action, dict) and isinstance(action.get("argv"), list)
    ]
    return {
        "schema": "acgm-codex-install-authorization-plan-v1",
        "source_root": str(source_root),
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
    environment = dict(env or os.environ)
    initial = preflight.evaluate(source_root, env=environment, runner=runner)
    plan = [
        action
        for action in initial["actions"]
        if isinstance(action, dict) and isinstance(action.get("argv"), list)
    ]
    authorization_plan = _install_authorization_plan(source_root, initial)
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
    if current["status"] == "READY_FOR_OFFICIAL_UPGRADE":
        result = preflight.run_codex_control(
            MARKETPLACE_REMOVE, environment, runner, 180
        )
        payload["commands_run"].append(_command_summary(MARKETPLACE_REMOVE, result))
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
        if current["status"] not in {
            "READY_FOR_PLUGIN_ADD",
            "INSTALLED_ENABLED_PENDING_HOOK_TRUST",
        }:
            payload["status"] = "MARKETPLACE_ADDED_BUT_POSTCONDITION_UNVERIFIED"
            payload["partial"] = True
            payload["lifecycle"] = dict(current["lifecycle"])
            return payload

    if current["status"] == "READY_FOR_PLUGIN_ADD":
        result = preflight.run_codex_control(PLUGIN_ADD, environment, runner, 180)
        payload["commands_run"].append(_command_summary(PLUGIN_ADD, result))
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
