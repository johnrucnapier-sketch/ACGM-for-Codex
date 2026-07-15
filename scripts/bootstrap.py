#!/usr/bin/env python3
"""Conservative public bootstrap for the tagged ACGM Codex marketplace.

No mutation occurs in dry-run mode or without ``--authorize-install``.  The
bootstrap never removes or migrates another install and never touches private
plugin data.
"""

from __future__ import annotations

import argparse
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


def execute(
    source_root: Path = SOURCE_ROOT,
    *,
    dry_run: bool,
    authorized: bool,
    env: dict[str, str] | None = None,
    runner: preflight.Runner = preflight.run_command,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    environment = dict(env or os.environ)
    initial = preflight.evaluate(source_root, env=environment, runner=runner)
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
        "preflight": initial,
        "lifecycle": dict(initial["lifecycle"]),
        "requires_user_action": True,
        "claims": {
            "hook_trusted": False,
            "heartbeat_verified": False,
            "project_bootstrapped": False,
        },
    }
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

    plan = [
        action
        for action in initial["actions"]
        if isinstance(action, dict) and isinstance(action.get("argv"), list)
    ]
    payload["plan"] = plan
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
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    payload = execute(
        args.source_root,
        dry_run=args.dry_run,
        authorized=args.authorize_install,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ACGM for Codex bootstrap: {payload['status']}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
