#!/usr/bin/env python3
"""Run the ACGM for Codex release-contract validation suite."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
PLUGIN_VALIDATOR = (
    CODEX_HOME
    / "skills"
    / ".system"
    / "plugin-creator"
    / "scripts"
    / "validate_plugin.py"
)
SKILL_VALIDATOR = (
    CODEX_HOME
    / "skills"
    / ".system"
    / "skill-creator"
    / "scripts"
    / "quick_validate.py"
)


def run(name: str, command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "name": name,
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "name": name,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args(argv)

    checks: list[dict[str, Any]] = []
    if PLUGIN_VALIDATOR.is_file():
        checks.append(
            run(
                "plugin_contract",
                [sys.executable, str(PLUGIN_VALIDATOR), str(ROOT)],
            )
        )
    else:
        checks.append(
            {
                "name": "plugin_contract",
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": f"official validator not found: {PLUGIN_VALIDATOR}",
            }
        )

    skill_paths = sorted(
        path
        for path in (ROOT / "skills").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )
    if not SKILL_VALIDATOR.is_file():
        checks.append(
            {
                "name": "skill_contract",
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": f"official validator not found: {SKILL_VALIDATOR}",
            }
        )
    elif not skill_paths:
        checks.append(
            {
                "name": "skill_contract",
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": "no skills found",
            }
        )
    else:
        for skill_path in skill_paths:
            checks.append(
                run(
                    f"skill_contract:{skill_path.name}",
                    [sys.executable, str(SKILL_VALIDATOR), str(skill_path)],
                )
            )

    checks.append(
        run(
            "unittest",
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
                "-v",
            ],
        )
    )

    payload = {"ok": all(check["ok"] for check in checks), "checks": checks}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        for check in checks:
            state = "PASS" if check["ok"] else "FAIL"
            print(f"[{state}] {check['name']}")
            if check["stdout"]:
                print(check["stdout"])
            if check["stderr"]:
                print(check["stderr"], file=sys.stderr)
        print("release contract passed" if payload["ok"] else "release contract failed")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
