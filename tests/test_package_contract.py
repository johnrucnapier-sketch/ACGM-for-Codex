from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = ROOT / ".codex-plugin" / "plugin.json"
HOOK_PATH = ROOT / "hooks" / "hooks.json"
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
                    f'python3 "${{PLUGIN_ROOT}}/scripts/acgm_codex.py" hook {mode}',
                )
                self.assertEqual(handler["timeout"], timeout)
                self.assertGreater(len(handler["statusMessage"].strip()), 10)

    def test_hooks_use_only_codex_contract(self) -> None:
        raw = HOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("${PLUGIN_ROOT}", raw)
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
            "hooks/**",
            "scripts/**",
            "bin/**",
            "tests/**",
            "skills/**/SKILL.md",
            "README.md",
            "docs/**",
        ):
            self.assertIn(path, mapping)


if __name__ == "__main__":
    unittest.main()
