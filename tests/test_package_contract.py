from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"
HOOK_PATH = ROOT / "hooks" / "hooks.json"
RUNTIME_PATH = ROOT / "scripts" / "acgm_codex.py"
VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
EXPECTED_SKILLS = {
    "activity-report",
    "governance-bootstrap",
    "session-grounding",
    "truth-first",
}
EXPECTED_HOOKS = {
    "SessionStart": ("startup|resume|clear|compact", "session-start", 10),
    "SubagentStart": (None, "subagent-start", 5),
    "PreToolUse": ("Bash|apply_patch|Edit|Write", "pre-tool", 5),
    "PermissionRequest": (
        "Bash|apply_patch|Edit|Write",
        "permission-request",
        5,
    ),
    "PostToolUse": ("Bash|apply_patch|Edit|Write", "post-tool", 5),
    "PreCompact": ("manual|auto", "pre-compact", 10),
    "Stop": (None, "stop", 10),
}
RUNTIME_SHA256 = hashlib.sha256(RUNTIME_PATH.read_bytes()).hexdigest()
RUNTIME_SIZE = RUNTIME_PATH.stat().st_size


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = text.split("[project]", 1)[-1].split("\n[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', project, re.MULTILINE)
    return match.group(1) if match else ""


def skill_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        return {}
    values: dict[str, str] = {}
    for key in ("name", "description"):
        field = re.search(rf"^{key}:\s*(.+?)\s*$", match.group(1), re.MULTILINE)
        if field:
            values[key] = field.group(1).strip().strip("'\"")
    return values


class PackageContractTests(unittest.TestCase):
    def test_manifest_identity_and_version_contract(self) -> None:
        manifest = read_json(PLUGIN_PATH)
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(manifest.get("id"), "acgm-codex")
        self.assertEqual(manifest.get("name"), "acgm-codex")
        self.assertEqual(manifest.get("version"), version)
        self.assertEqual(project_version(), version)
        self.assertRegex(version, VERSION_PATTERN)
        self.assertEqual(manifest.get("license"), "SEE LICENSING.md")
        self.assertNotIn("hooks", manifest)
        self.assertNotIn("homepage", manifest)
        self.assertNotIn("repository", manifest)

        interface = manifest.get("interface")
        self.assertIsInstance(interface, dict)
        self.assertEqual(interface.get("displayName"), "ACGM for Codex")
        self.assertEqual(interface.get("developerName"), "johnrucnapier-sketch")
        self.assertTrue(interface.get("defaultPrompt"))

    def test_public_marketplace_is_tag_pinned_and_policy_complete(self) -> None:
        marketplace = read_json(MARKETPLACE_PATH)
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(marketplace.get("name"), "acgm-codex")
        self.assertEqual(marketplace.get("interface", {}).get("displayName"), "ACGM for Codex")
        plugins = marketplace.get("plugins")
        self.assertIsInstance(plugins, list)
        self.assertEqual(len(plugins), 1)
        entry = plugins[0]
        self.assertEqual(entry.get("name"), "acgm-codex")
        self.assertEqual(
            entry.get("source"),
            {
                "source": "url",
                "url": "https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git",
                "ref": f"v{version}",
            },
        )
        self.assertEqual(
            entry.get("policy"),
            {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        )
        self.assertEqual(entry.get("category"), "Developer Tools")

    def test_agent_install_bridge_defines_one_consent_quickstart_contract(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        contract = agents + "\n" + install
        for required in (
            "URL",
            "explicit",
            "scripts/quickstart.py",
            "--authorize",
            "--plan-digest",
            "standard-v1",
            "digest",
            "/hooks",
            "subsequently observed",
            "Windows",
        ):
            self.assertIn(required, contract)
        self.assertNotIn("new Codex discovery task", contract)
        self.assertNotIn("second new verification task", contract)
        preflight = (ROOT / "scripts" / "preflight.py").read_text(encoding="utf-8")
        self.assertIn("FIRST_TRUSTED_HOOK_AUTO_COMPLETES", preflight)
        self.assertNotIn("SECOND_NEW_TASK_AFTER_TRUST_REQUIRED", preflight)
        self.assertNotIn('"id": "start_verification_task"', preflight)
        architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8").lower()
        self.assertIn("windows claim requires", architecture)

    def test_official_upgrade_is_narrow_and_uses_fixed_remove_add_add_plan(self) -> None:
        preflight = (ROOT / "scripts" / "preflight.py").read_text(encoding="utf-8")
        bootstrap = (ROOT / "scripts" / "bootstrap.py").read_text(encoding="utf-8")
        for required in (
            "READY_FOR_OFFICIAL_UPGRADE",
            "KNOWN_OFFICIAL_UPGRADE_VERSIONS",
            "official_upgrade_cache_unverified",
            "installed_cache_version_set_mismatch",
            "marketplace",
            "remove",
            "scope",
        ):
            self.assertIn(required, preflight + bootstrap)
        self.assertIn("MARKETPLACE_REMOVE", bootstrap)
        self.assertLess(
            bootstrap.index('if current["status"] == "READY_FOR_OFFICIAL_UPGRADE"'),
            bootstrap.index('if current["status"] == "READY_FOR_INSTALL"'),
        )
        self.assertIn("MARKETPLACE_REMOVED_BUT_POSTCONDITION_UNVERIFIED", bootstrap)
        self.assertIn("INSTALL_PLAN_DIGEST_REQUIRED", bootstrap)
        self.assertIn('"--plan-digest"', bootstrap)
        self.assertIn("expected_plan_digest=args.plan_digest", bootstrap)
        self.assertIn("package_filesystem_excluded_path_not_allowed", preflight)
        self.assertNotIn("rolled back", bootstrap.lower())

    def test_ci_matrix_covers_supported_and_blocked_platform_contracts(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        for required in (
            "ubuntu-latest",
            "macos-latest",
            "windows-latest",
            '"3.10"',
            '"3.11"',
            '"3.12"',
            "scripts/generate-package-manifest.py --check --source git",
            "tests.test_bootstrap",
            "tests.test_quickstart",
        ):
            self.assertIn(required, workflow)

    def test_release_checkout_keeps_platform_neutral_lf_bytes(self) -> None:
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* text=auto eol=lf", attributes.splitlines())

    def test_default_hook_path_and_inventory(self) -> None:
        self.assertTrue(HOOK_PATH.is_file())
        self.assertFalse((ROOT / "hooks.json").exists())
        hooks = read_json(HOOK_PATH).get("hooks")
        self.assertIsInstance(hooks, dict)
        self.assertEqual(set(hooks), set(EXPECTED_HOOKS))

    def test_hook_schema_commands_and_timeouts(self) -> None:
        hooks = read_json(HOOK_PATH)["hooks"]
        for event, (matcher, mode, timeout) in EXPECTED_HOOKS.items():
            with self.subTest(event=event):
                groups = hooks[event]
                self.assertIsInstance(groups, list)
                self.assertEqual(len(groups), 1)
                group = groups[0]
                self.assertEqual(set(group), {"hooks"} | ({"matcher"} if matcher else set()))
                if matcher:
                    self.assertEqual(group["matcher"], matcher)

                handlers = group["hooks"]
                self.assertIsInstance(handlers, list)
                self.assertEqual(len(handlers), 1)
                handler = handlers[0]
                self.assertEqual(
                    set(handler),
                    {"type", "command", "timeout", "statusMessage"},
                )
                self.assertEqual(handler["type"], "command")
                self.assertEqual(
                    handler["command"],
                    handler["command"].rsplit(" hook ", 1)[0] + f" hook {mode}",
                )
                self.assertIn("PLUGIN_DATA", handler["command"])
                self.assertIn(RUNTIME_SHA256, handler["command"])
                self.assertIn(f"e={RUNTIME_SIZE}", handler["command"])
                self.assertIn("O_NONBLOCK", handler["command"])
                self.assertIn("S_ISREG", handler["command"])
                self.assertNotIn("PLUGIN_ROOT", handler["command"])
                self.assertEqual(handler["timeout"], timeout)
                self.assertGreater(len(handler["statusMessage"].strip()), 10)

    def test_hook_wrapper_fails_open_when_stable_runtime_is_missing(self) -> None:
        hooks = read_json(HOOK_PATH)["hooks"]
        with tempfile.TemporaryDirectory(prefix="acgm missing plugin ") as raw:
            plugin_data = Path(raw)
            for event, (_, _, _) in EXPECTED_HOOKS.items():
                with self.subTest(event=event):
                    command = hooks[event][0]["hooks"][0]["command"]
                    argv = shlex.split(command)
                    environment = dict(os.environ)
                    environment["PLUGIN_DATA"] = str(plugin_data)
                    completed = subprocess.run(
                        argv,
                        input="{}\n",
                        check=False,
                        env=environment,
                        text=True,
                        encoding="utf-8",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=5,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(json.loads(completed.stdout), {})

    def test_hook_wrapper_preserves_runtime_arguments_when_present(self) -> None:
        hooks = read_json(HOOK_PATH)["hooks"]
        with tempfile.TemporaryDirectory(prefix="acgm present plugin ") as raw:
            plugin_data = Path(raw)
            script = plugin_data / "runtime" / "acgm_codex.py"
            script.parent.mkdir()
            script.write_text(
                "import json, sys\nprint(json.dumps(sys.argv))\n",
                encoding="utf-8",
            )
            fixture_hash = hashlib.sha256(script.read_bytes()).hexdigest()
            for event, (_, mode, _) in EXPECTED_HOOKS.items():
                with self.subTest(event=event):
                    trusted_command = hooks[event][0]["hooks"][0]["command"]
                    fixture_command = trusted_command.replace(
                        RUNTIME_SHA256, fixture_hash
                    ).replace(
                        f"e={RUNTIME_SIZE}", f"e={script.stat().st_size}"
                    )
                    self.assertNotEqual(fixture_command, trusted_command)
                    argv = shlex.split(fixture_command)
                    environment = dict(os.environ)
                    environment["PLUGIN_DATA"] = str(plugin_data)
                    completed = subprocess.run(
                        argv,
                        input="{}\n",
                        check=False,
                        env=environment,
                        text=True,
                        encoding="utf-8",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=5,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(
                        json.loads(completed.stdout),
                        [str(script), "hook", mode],
                    )

    def test_trusted_hook_hash_rejects_changed_runtime_bytes(self) -> None:
        command = read_json(HOOK_PATH)["hooks"]["SessionStart"][0]["hooks"][0][
            "command"
        ]
        with tempfile.TemporaryDirectory(prefix="acgm changed runtime ") as raw:
            plugin_data = Path(raw)
            script = plugin_data / "runtime" / "acgm_codex.py"
            script.parent.mkdir()
            script.write_bytes(RUNTIME_PATH.read_bytes() + b"\n# changed after trust\n")
            environment = dict(os.environ)
            environment["PLUGIN_DATA"] = str(plugin_data)
            completed = subprocess.run(
                shlex.split(command),
                input="{}\n",
                check=False,
                env=environment,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {})

    def test_hook_wrapper_fails_open_when_plugin_data_is_unset(self) -> None:
        command = read_json(HOOK_PATH)["hooks"]["SessionStart"][0]["hooks"][0][
            "command"
        ]
        environment = dict(os.environ)
        environment.pop("PLUGIN_DATA", None)
        completed = subprocess.run(
            shlex.split(command),
            input="{}\n",
            check=False,
            env=environment,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {})

    def test_hook_wrapper_rejects_wrong_sized_regular_runtime(self) -> None:
        command = read_json(HOOK_PATH)["hooks"]["SessionStart"][0]["hooks"][0][
            "command"
        ]
        with tempfile.TemporaryDirectory(prefix="acgm wrong size runtime ") as raw:
            plugin_data = Path(raw)
            script = plugin_data / "runtime" / "acgm_codex.py"
            script.parent.mkdir()
            script.write_bytes(RUNTIME_PATH.read_bytes() + b"\n")
            environment = dict(os.environ)
            environment["PLUGIN_DATA"] = str(plugin_data)
            completed = subprocess.run(
                shlex.split(command),
                input="{}\n",
                check=False,
                env=environment,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {})

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO is unavailable")
    def test_hook_wrapper_rejects_fifo_without_blocking(self) -> None:
        command = read_json(HOOK_PATH)["hooks"]["SessionStart"][0]["hooks"][0][
            "command"
        ]
        with tempfile.TemporaryDirectory(prefix="acgm fifo runtime ") as raw:
            plugin_data = Path(raw)
            runtime = plugin_data / "runtime"
            runtime.mkdir()
            os.mkfifo(runtime / "acgm_codex.py", 0o600)
            environment = dict(os.environ)
            environment["PLUGIN_DATA"] = str(plugin_data)
            completed = subprocess.run(
                shlex.split(command),
                input="{}\n",
                check=False,
                env=environment,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {})

    def test_hook_wrapper_rejects_symlinked_runtime(self) -> None:
        command = read_json(HOOK_PATH)["hooks"]["SessionStart"][0]["hooks"][0][
            "command"
        ]
        with tempfile.TemporaryDirectory(prefix="acgm symlink runtime ") as raw:
            plugin_data = Path(raw)
            runtime = plugin_data / "runtime"
            runtime.mkdir()
            (runtime / "acgm_codex.py").symlink_to(RUNTIME_PATH)
            environment = dict(os.environ)
            environment["PLUGIN_DATA"] = str(plugin_data)
            completed = subprocess.run(
                shlex.split(command),
                input="{}\n",
                check=False,
                env=environment,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {})

    def test_hooks_use_only_codex_contract(self) -> None:
        raw = HOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("PLUGIN_DATA", raw)
        self.assertNotIn("PLUGIN_ROOT", raw)
        self.assertNotIn("CLAUDE_", raw)
        for unsupported in (
            "UserPromptSubmit",
            "PostCompact",
            "SubagentStop",
            "SessionEnd",
            "PostToolUseFailure",
        ):
            self.assertNotIn(unsupported, raw)
        for unsupported_handler in ('"async"', '"prompt"', '"agent"', '"commandWindows"'):
            self.assertNotIn(unsupported_handler, raw)

    def test_skill_inventory_and_frontmatter(self) -> None:
        skills_root = ROOT / "skills"
        actual = {
            path.name
            for path in skills_root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }
        self.assertEqual(actual, EXPECTED_SKILLS)
        for name in sorted(EXPECTED_SKILLS):
            with self.subTest(skill=name):
                path = skills_root / name / "SKILL.md"
                self.assertTrue(path.is_file())
                frontmatter = skill_frontmatter(path.read_text(encoding="utf-8"))
                self.assertEqual(frontmatter.get("name"), name)
                self.assertTrue(frontmatter.get("description"))

    def test_release_text_has_no_placeholders(self) -> None:
        marker = "TO" + "DO"
        suffixes = {".md", ".json", ".py", ".toml", ".yaml", ".yml"}
        violations: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.suffix not in suffixes and path.name not in {
                "VERSION",
                "LICENSE-CODE",
                "LICENSE-DOCS",
            }:
                continue
            if marker in path.read_text(encoding="utf-8", errors="replace"):
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [])

    def test_dual_track_license_mapping(self) -> None:
        code = (ROOT / "LICENSE-CODE").read_text(encoding="utf-8")
        docs = (ROOT / "LICENSE-DOCS").read_text(encoding="utf-8")
        mapping = (ROOT / "LICENSING.md").read_text(encoding="utf-8")

        self.assertIn("MIT License", code)
        self.assertIn("CC-BY-4.0", docs)
        for path in (
            ".codex-plugin/**",
            ".github/workflows/**",
            "hooks/**",
            "scripts/**",
            "bin/**",
            "tests/**",
            "skills/**/SKILL.md",
            "skills/**/agents/openai.yaml",
            "README.md",
            "docs/**",
        ):
            self.assertIn(path, mapping)


if __name__ == "__main__":
    unittest.main()
