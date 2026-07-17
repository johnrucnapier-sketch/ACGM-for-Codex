#!/usr/bin/env python3
"""One-consent ACGM installer and project activation orchestrator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import acgm_codex
import bootstrap
import preflight


SOURCE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "acgm-codex-one-consent-v1"


def _stable_install_plan(payload: dict[str, Any]) -> dict[str, Any]:
    authorization_plan = payload.get("authorization_plan")
    install_plan_digest = payload.get("install_plan_digest")
    if isinstance(authorization_plan, dict) and isinstance(
        install_plan_digest, str
    ):
        verified = (
            bootstrap._install_plan_digest(authorization_plan) == install_plan_digest
        )
        return {
            "verified": verified,
            "authorization_plan": authorization_plan,
            "install_plan_digest": install_plan_digest,
        }

    # A bootstrap result without a signed stable plan cannot participate in the
    # one-consent flow.  Keep limited diagnostics, but fail the combined plan.
    preflight_payload = payload.get("preflight")
    preflight_payload = preflight_payload if isinstance(preflight_payload, dict) else {}
    source = preflight_payload.get("source")
    source = source if isinstance(source, dict) else {}
    git = source.get("git")
    git = git if isinstance(git, dict) else {}
    package = source.get("package")
    package = package if isinstance(package, dict) else {}
    release_contract = source.get("release_contract")
    release_contract = (
        release_contract if isinstance(release_contract, dict) else {}
    )
    return {
        "verified": False,
        "status": payload.get("status"),
        "version": payload.get("version"),
        "tag": payload.get("tag"),
        "commands": [
            action.get("argv")
            for action in payload.get("plan", [])
            if isinstance(action, dict) and isinstance(action.get("argv"), list)
        ],
        "source_status": payload.get("initial_status"),
        "source_proof": {
            "head": git.get("head"),
            "tag": git.get("tag"),
            "clean": git.get("clean"),
            "origin_matches": git.get("origin_matches"),
            "manifest_sha256": package.get("manifest_sha256"),
            "manifest_file_count": package.get("file_count"),
            "release_contract_verified": release_contract.get("verified"),
            "hook_definition_sha256": preflight_payload.get(
                "hook_definition_sha256"
            ),
        },
        "lifecycle": payload.get("lifecycle"),
    }


def plan(
    source_root: Path,
    project: Path,
    *,
    preset: str = acgm_codex.QUICKSTART_PRESET,
    env: dict[str, str] | None = None,
    runner: preflight.Runner = preflight.run_command,
) -> dict[str, Any]:
    environment = dict(env or os.environ)
    try:
        install = bootstrap.execute(
            source_root,
            dry_run=True,
            authorized=False,
            env=environment,
            runner=runner,
        )
    except (OSError, acgm_codex.RuntimeProblem) as exc:
        install = {
            "ok": False,
            "status": "INSTALL_PLAN_BLOCKED",
            "error": str(exc),
        }
    stable_install = _stable_install_plan(install)
    try:
        project_plan = acgm_codex._quickstart_plan(str(project), preset)
    except (OSError, acgm_codex.RuntimeProblem) as exc:
        project_plan = {
            "ok": False,
            "status": "PROJECT_PLAN_BLOCKED",
            "project": str(project.expanduser()),
            "error": str(exc),
            "writes_planned": [],
        }
    unsigned = {
        "schema": SCHEMA,
        "source_root": str(source_root.expanduser().resolve()),
        "install": stable_install,
        "project": project_plan,
        "authorization_scope": [
            "install_exact_tagged_acgm_plugin",
            "apply_exact_standard_preset_without_overwriting_existing_policy",
            "activate_exact_project_and_verify_local_postconditions",
        ],
    }
    canonical = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload = dict(unsigned)
    payload["plan_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    payload["ok"] = (
        bool(install.get("ok"))
        and bool(stable_install.get("verified"))
        and bool(project_plan.get("ok"))
    )
    payload["status"] = "PLAN_READY" if payload["ok"] else "PLAN_BLOCKED"
    return payload


def execute(
    source_root: Path,
    project: Path,
    *,
    preset: str = acgm_codex.QUICKSTART_PRESET,
    dry_run: bool,
    authorized: bool,
    expected_digest: str | None = None,
    env: dict[str, str] | None = None,
    runner: preflight.Runner = preflight.run_command,
) -> dict[str, Any]:
    environment = dict(env or os.environ)
    current_plan = plan(
        source_root,
        project,
        preset=preset,
        env=environment,
        runner=runner,
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "ok": False,
        "complete": False,
        "partial": False,
        "authorized": authorized,
        "status": current_plan["status"],
        "plan_digest": current_plan["plan_digest"],
        "plan": current_plan,
        "claims": {
            "plugin_install_verified": False,
            "project_assets_verified": False,
            "project_activated": False,
            "automatic_hook_observed": False,
        },
    }
    if dry_run:
        payload["ok"] = bool(current_plan["ok"])
        return payload
    if not current_plan["ok"]:
        return payload
    if not authorized:
        payload["status"] = "AUTHORIZATION_REQUIRED"
        return payload
    if not expected_digest:
        payload["status"] = "PLAN_DIGEST_REQUIRED"
        return payload
    if expected_digest != current_plan["plan_digest"]:
        payload["status"] = "PLAN_STALE"
        return payload

    install = bootstrap.execute(
        source_root,
        dry_run=False,
        authorized=True,
        expected_plan_digest=str(
            current_plan["install"]["install_plan_digest"]
        ),
        env=environment,
        runner=runner,
    )
    payload["install"] = install
    if not install.get("ok"):
        install_status = str(install.get("status", "FAILED"))
        payload["status"] = (
            install_status
            if install_status == "INSTALL_PLAN_STALE"
            else "INSTALL_" + install_status
        )
        payload["partial"] = bool(install.get("partial"))
        return payload
    payload["claims"]["plugin_install_verified"] = True

    try:
        project_result = acgm_codex._apply_quickstart(
            str(project),
            preset=preset,
            authorized=True,
            expected_digest=current_plan["project"]["plan_digest"],
        )
    except (OSError, acgm_codex.RuntimeProblem) as exc:
        # Installation is already a verified user-level mutation.  A target
        # deletion, root change, or unreadable project during the immediately
        # following replan must therefore be returned as explicit partial state
        # rather than escaping as a traceback with an ambiguous install result.
        project_result = {
            "ok": False,
            "complete": False,
            "partial": True,
            "status": "PROJECT_RECHECK_REQUIRED",
            "error": str(exc),
            "claims": {
                "project_assets_verified": False,
                "project_activated": False,
                "automatic_hook_observed": False,
            },
            "pending_actions": [
                "Re-resolve the exact project Git root and run a new read-only quickstart plan."
            ],
        }
    payload["project_result"] = project_result
    payload["claims"].update(project_result.get("claims", {}))
    # The user-level plugin install has already been verified at this point. If
    # project provisioning then fails, this is a real partial mutation even when
    # no project asset was written before the failure.
    payload["partial"] = bool(project_result.get("partial")) or not bool(
        project_result.get("ok")
    )
    payload["ok"] = bool(project_result.get("ok"))
    payload["complete"] = bool(project_result.get("complete"))
    project_status = str(project_result.get("status", "PROJECT_FAILED"))
    project_partial = bool(project_result.get("partial"))
    pending_actions = list(project_result.get("pending_actions", []))
    replan_action = (
        "Re-resolve the exact project Git root and run a new read-only quickstart plan."
    )
    if not payload["ok"] and not project_partial:
        # The verified plugin installation is already a user-level mutation, but
        # this project result occurred before quickstart began its own writes.
        # Keep the precise nested status while making the top-level partial state
        # and required recovery action unambiguous.
        payload["status"] = "PROJECT_RECHECK_REQUIRED"
        if replan_action not in pending_actions:
            pending_actions.append(replan_action)
    else:
        payload["status"] = project_status
    payload["pending_actions"] = pending_actions
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="explicit target Git root")
    parser.add_argument("--preset", default=acgm_codex.QUICKSTART_PRESET)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--authorize",
        action="store_true",
        help="authorize this exact combined install and project plan once",
    )
    parser.add_argument(
        "--plan-digest",
        help="required for authorized apply; copy it from the immediately preceding dry run",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    payload = execute(
        args.source_root,
        args.project,
        preset=args.preset,
        dry_run=args.dry_run,
        authorized=args.authorize,
        expected_digest=args.plan_digest,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ACGM for Codex one-consent quickstart: {payload['status']}")
        for action in payload.get("pending_actions", []):
            print("next: " + str(action))
    if payload.get("status") == "PARTIAL_RECHECK_REQUIRED" or payload.get("partial"):
        return 3
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
