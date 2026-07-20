from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "scripts" / "acgm_codex.py"
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(self.project)], check=True, capture_output=True
        )
        self.data = self.base / "data"
        self.env = os.environ.copy()
        self.env.pop("PLUGIN_DATA", None)
        self.env["ACGM_CODEX_DATA_DIR"] = str(self.data)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_repository(self, path: Path, *, commit: bool = True) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "-q", str(path)], check=True, capture_output=True
        )
        if commit:
            (path / "README.md").write_text("# Fixture repository\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(path), "add", "README.md"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(path),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    "fixture",
                ],
                check=True,
                capture_output=True,
            )
        return path

    def make_container_workspace(self, *names: str) -> tuple[Path, list[Path]]:
        workspace = self.base / ("workspace-" + "-".join(names))
        self.make_repository(workspace, commit=False)
        repositories = [self.make_repository(workspace / name) for name in names]
        return workspace, repositories

    def load_runtime_module(self) -> object:
        name = f"acgm_codex_runtime_test_{id(self)}"
        specification = importlib.util.spec_from_file_location(name, RUNTIME)
        self.assertIsNotNone(specification)
        self.assertIsNotNone(specification.loader)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module

    def write_dirfd_file(
        self, directory_fd: int, name: str, content: str, *, mode: int = 0o600
    ) -> None:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            mode,
            dir_fd=directory_fd,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)

    def cli(
        self,
        *args: str,
        check: bool = False,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(RUNTIME), *args],
            cwd=str(cwd or self.project),
            env=env or self.env,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"CLI failed ({result.returncode}): {result.stderr}\n{result.stdout}")
        return result

    def payload(self, event: str, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "session_id": "session-sensitive-value",
            "turn_id": "turn-sensitive-value",
            "cwd": str(self.project),
            "hook_event_name": event,
            "permission_mode": "default",
        }
        value.update(overrides)
        return value

    def hook(
        self,
        dispatch: str,
        payload: dict[str, object],
        *,
        env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(RUNTIME), "hook", dispatch],
            cwd=str(self.project),
            env=env or self.env,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"hook did not emit one JSON object: {result.stdout!r}: {exc}")
        self.assertIsInstance(value, dict)
        return result, value

    def complete_assets(self) -> None:
        constitution = (self.project / "CONSTITUTION.md").read_text(encoding="utf-8")
        constitution = constitution.replace(
            "<!-- [PLACEHOLDER] Human review is required before ACGM activation. -->",
            "<!-- Reviewed and approved by the project owner. -->",
        )
        (self.project / "CONSTITUTION.md").write_text(constitution, encoding="utf-8")
        scope = (self.project / ".governance" / "scope.yml").read_text(encoding="utf-8")
        scope = scope.replace(
            "# [PLACEHOLDER] Replace the example scope after human review.",
            "# Scope reviewed and approved for this project.",
        )
        (self.project / ".governance" / "scope.yml").write_text(scope, encoding="utf-8")
        (self.project / ".governance" / "decisions" / "0001-initial.md").write_text(
            "# Initial decision\n\nUse the checked-in governance contract for this project.\n",
            encoding="utf-8",
        )
        (self.project / ".governance" / "snapshots" / "current.md").write_text(
            "# Current snapshot\n\nThe initial governance baseline has been reviewed.\n",
            encoding="utf-8",
        )

    def init_activate(self) -> None:
        self.cli("init", str(self.project), check=True)
        self.complete_assets()
        self.cli("activate", str(self.project), check=True)

    def pre_bash(self, command: str, **overrides: object) -> dict[str, object]:
        payload = self.payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="tool-1",
            tool_input={"command": command},
            **overrides,
        )
        return self.hook("pre-tool", payload)[1]

    def post_bash(
        self,
        command: str,
        *,
        exit_code: int = 0,
        response: object | None = None,
        **overrides: object,
    ) -> dict[str, object]:
        payload = self.payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="tool-1",
            tool_input={"command": command},
            tool_response=response
            if response is not None
            else {"output": "sensitive output", "exit_code": exit_code},
            **overrides,
        )
        return self.hook("post-tool", payload)[1]

    def latest_event(self, kind: str) -> dict[str, object]:
        return next(
            event
            for event in reversed(self.report_json()["events"])
            if event["kind"] == kind
        )

    def gate_operation(
        self,
        operation: str,
        source: dict[str, object],
        *,
        target: Path | None = None,
        hook_overrides: dict[str, object] | None = None,
    ) -> tuple[dict[str, object], subprocess.CompletedProcess[str]]:
        arguments = [
            "gate",
            operation,
            "--event",
            str(source["event_id"]),
            "--category",
            str(source["category"]),
        ]
        if target is not None:
            arguments.extend(["--target", str(target)])
        command = "acgm-codex " + " ".join(arguments)
        hook = self.pre_bash(command, **(hook_overrides or {}))
        return hook, self.cli(*arguments)

    def report_json(self, *, env: dict[str, str] | None = None) -> dict[str, object]:
        result = self.cli("report", "--json", "--limit", "1000", check=True, env=env)
        return json.loads(result.stdout)

    def event_kinds(self) -> list[str]:
        return [str(event["kind"]) for event in self.report_json()["events"]]

    def test_version_wrapper_and_no_pending_word_literal_contract(self) -> None:
        result = self.cli("version", check=True)
        self.assertEqual(result.stdout.strip(), f"acgm-codex {VERSION}")
        wrapper = (REPO / "bin" / "acgm-codex").read_text(encoding="utf-8")
        self.assertIn("scripts/acgm_codex.py", wrapper)
        pending_word = "TO" + "DO"
        self.assertNotIn(pending_word, RUNTIME.read_text(encoding="utf-8"))
        self.assertNotIn(pending_word, Path(__file__).read_text(encoding="utf-8"))

    def test_init_is_idempotent_and_never_overwrites(self) -> None:
        custom_agents = (
            "# Existing project instructions\n\n"
            "Keep this exact project-specific policy unchanged.\n"
        )
        (self.project / "AGENTS.md").write_text(custom_agents, encoding="utf-8")
        first = self.cli("init", str(self.project), check=True)
        self.assertIn("initialized without overwriting", first.stdout)
        self.assertEqual((self.project / "AGENTS.md").read_text(encoding="utf-8"), custom_agents)
        self.assertTrue((self.project / "CONSTITUTION.md").is_file())
        self.assertTrue((self.project / ".governance" / "scope.yml").is_file())
        self.assertTrue((self.project / ".governance" / "decisions").is_dir())
        self.assertTrue((self.project / ".governance" / "snapshots").is_dir())
        self.assertEqual(
            (self.project / ".acgm" / ".gitignore").read_text(encoding="utf-8"),
            "*\n!.gitignore\n",
        )
        state_before = (self.project / ".acgm" / "codex.json").read_bytes()
        second = self.cli("init", str(self.project), check=True)
        self.assertIn(".acgm/codex.json", second.stdout)
        self.assertEqual((self.project / ".acgm" / "codex.json").read_bytes(), state_before)
        doctor = json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)
        self.assertEqual(doctor["project_state"], "PARTIALLY_GOVERNED")

    def test_activation_rejects_short_files_and_empty_governance_directories(self) -> None:
        self.cli("init", str(self.project), check=True)
        self.complete_assets()
        original_constitution = (self.project / "CONSTITUTION.md").read_text(encoding="utf-8")
        original_scope = (self.project / ".governance" / "scope.yml").read_text(encoding="utf-8")
        decision = self.project / ".governance" / "decisions" / "0001-initial.md"
        snapshot = self.project / ".governance" / "snapshots" / "current.md"
        original_decision = decision.read_text(encoding="utf-8")
        original_snapshot = snapshot.read_text(encoding="utf-8")

        for path, replacement, label in (
            (self.project / "CONSTITUTION.md", "", "CONSTITUTION.md"),
            (self.project / ".governance" / "scope.yml", "x", ".governance/scope.yml"),
            (decision, "x", ".governance/decisions/"),
            (snapshot, "\n", ".governance/snapshots/"),
        ):
            with self.subTest(asset=label):
                path.write_text(replacement, encoding="utf-8")
                refused = self.cli("activate", str(self.project))
                self.assertEqual(refused.returncode, 2)
                self.assertIn(label, refused.stderr)
                (self.project / "CONSTITUTION.md").write_text(
                    original_constitution, encoding="utf-8"
                )
                (self.project / ".governance" / "scope.yml").write_text(
                    original_scope, encoding="utf-8"
                )
                decision.write_text(original_decision, encoding="utf-8")
                snapshot.write_text(original_snapshot, encoding="utf-8")

        self.cli("activate", str(self.project), check=True)

    def test_existing_agents_alone_does_not_imply_bootstrap(self) -> None:
        (self.project / "AGENTS.md").write_text(
            "# Existing instructions\n\nThis project already has ordinary Codex guidance.\n",
            encoding="utf-8",
        )
        doctor = json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)
        self.assertEqual(doctor["project_state"], "INSTALLED_NOT_BOOTSTRAPPED")
        self.assertFalse(doctor["active"])

    def test_quickstart_plan_is_read_only_stable_and_digest_bound(self) -> None:
        first = self.cli(
            "quickstart", "plan", str(self.project), "--json", check=True
        )
        second = self.cli(
            "quickstart", "plan", str(self.project), "--json", check=True
        )
        first_plan = json.loads(first.stdout)
        second_plan = json.loads(second.stdout)

        self.assertEqual(first_plan["status"], "PLAN_READY")
        self.assertEqual(first_plan["plan_digest"], second_plan["plan_digest"])
        self.assertTrue(all(asset["action"] == "create" for asset in first_plan["assets"]))
        self.assertFalse((self.project / "CONSTITUTION.md").exists())
        self.assertFalse((self.project / ".governance").exists())
        self.assertFalse((self.project / ".acgm").exists())

    def test_quickstart_requires_authorization_before_any_write(self) -> None:
        result = self.cli("quickstart", "apply", str(self.project), "--json")
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["status"], "AUTHORIZATION_REQUIRED")
        self.assertFalse((self.project / "CONSTITUTION.md").exists())
        self.assertFalse((self.project / ".governance").exists())
        self.assertFalse((self.project / ".acgm").exists())

        authorized_without_digest = self.cli(
            "quickstart", "apply", str(self.project), "--authorize", "--json"
        )
        self.assertEqual(authorized_without_digest.returncode, 2)
        self.assertEqual(
            json.loads(authorized_without_digest.stdout)["status"],
            "PLAN_DIGEST_REQUIRED",
        )
        self.assertFalse((self.project / ".acgm").exists())

    def test_quickstart_fresh_apply_preserves_agents_and_activates(self) -> None:
        custom_agents = "# Existing instructions\n\nKeep this project policy unchanged.\n"
        (self.project / "AGENTS.md").write_text(custom_agents, encoding="utf-8")
        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )

        applied = self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        payload = json.loads(applied.stdout)

        self.assertEqual(payload["status"], "AWAITING_PLATFORM_HOOK_ACCEPTANCE")
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["claims"]["project_assets_verified"])
        self.assertTrue(payload["claims"]["project_activated"])
        self.assertFalse(payload["complete"])
        self.assertEqual(
            (self.project / "AGENTS.md").read_text(encoding="utf-8"), custom_agents
        )
        state = json.loads(
            (self.project / ".acgm" / "codex.json").read_text(encoding="utf-8")
        )
        self.assertTrue(state["active"])
        self.assertEqual(state["preset"], "standard-v1")
        self.assertTrue(
            (self.project / ".governance" / "decisions" / "0001-adopt-acgm-standard-v1.md").is_file()
        )
        self.assertTrue(
            (self.project / ".governance" / "snapshots" / "bootstrap.md").is_file()
        )

    def test_quickstart_replaces_only_stock_placeholders_and_is_idempotent(self) -> None:
        self.cli("init", str(self.project), check=True)
        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        actions = {asset["path"]: asset["action"] for asset in plan["assets"]}
        self.assertEqual(actions["CONSTITUTION.md"], "replace-known-placeholder")
        self.assertEqual(actions[".governance/scope.yml"], "replace-known-placeholder")

        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        first_state = json.loads(
            (self.project / ".acgm" / "codex.json").read_text(encoding="utf-8")
        )
        second_plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            second_plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        second_state = json.loads(
            (self.project / ".acgm" / "codex.json").read_text(encoding="utf-8")
        )

        self.assertEqual(first_state["activation_id"], second_state["activation_id"])
        self.assertNotIn("[PLACEHOLDER]", (self.project / "CONSTITUTION.md").read_text())
        self.assertNotIn(
            "[PLACEHOLDER]",
            (self.project / ".governance" / "scope.yml").read_text(),
        )

    def test_quickstart_stale_digest_and_unknown_placeholder_fail_before_write(self) -> None:
        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        (self.project / "README.md").write_text("changed after plan\n", encoding="utf-8")
        stale = self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            plan["plan_digest"],
            "--authorize",
            "--json",
        )
        self.assertEqual(json.loads(stale.stdout)["status"], "PLAN_STALE")
        self.assertFalse((self.project / ".acgm").exists())

        (self.project / "CONSTITUTION.md").write_text(
            "# Custom Constitution\n\n[PLACEHOLDER] owner must decide.\n",
            encoding="utf-8",
        )
        conflict_plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json"
            ).stdout
        )
        conflict = self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            conflict_plan["plan_digest"],
            "--authorize",
            "--json",
        )
        conflict_payload = json.loads(conflict.stdout)
        self.assertEqual(conflict.returncode, 2)
        self.assertEqual(conflict_payload["status"], "PROJECT_ASSET_CONFLICT")
        self.assertFalse((self.project / ".acgm").exists())

    def test_quickstart_digest_detects_content_change_while_git_status_stays_dirty(self) -> None:
        readme = self.project / "README.md"
        readme.write_text("first untracked content\n", encoding="utf-8")
        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        readme.write_text("second untracked content\n", encoding="utf-8")

        stale = self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            plan["plan_digest"],
            "--authorize",
            "--json",
        )

        self.assertEqual(json.loads(stale.stdout)["status"], "PLAN_STALE")
        self.assertFalse((self.project / ".acgm").exists())

    def test_quickstart_requires_exact_root_and_rejects_managed_parent_symlink(self) -> None:
        subdirectory = self.project / "nested"
        subdirectory.mkdir()
        wrong_root = self.cli(
            "quickstart", "apply", str(subdirectory), "--authorize", "--json"
        )
        self.assertEqual(wrong_root.returncode, 2)
        self.assertIn("exact Git repository root", wrong_root.stderr)
        self.assertFalse((self.project / ".acgm").exists())

        external = self.base / "external-governance"
        external.mkdir()
        (self.project / ".governance").symlink_to(external, target_is_directory=True)
        conflict = self.cli(
            "quickstart", "apply", str(self.project), "--authorize", "--json"
        )
        payload = json.loads(conflict.stdout)
        self.assertEqual(conflict.returncode, 2)
        self.assertEqual(payload["status"], "PROJECT_ASSET_CONFLICT")
        self.assertFalse(any(external.iterdir()))
        self.assertFalse((self.project / ".acgm").exists())

    def test_quickstart_acgm_directory_swap_never_writes_outside_project(self) -> None:
        for existing in (False, True):
            with self.subTest(existing=existing):
                project = self.make_repository(
                    self.base / f"acgm-parent-swap-{existing}"
                )
                external = self.base / f"acgm-parent-external-{existing}"
                external.mkdir()
                expected_external: set[str] = set()
                if existing:
                    (project / ".acgm").mkdir()
                    (project / ".acgm" / ".gitignore").write_text(
                        "*\n!.gitignore\n", encoding="utf-8"
                    )
                    (external / ".gitignore").write_text(
                        "*\n!.gitignore\n", encoding="utf-8"
                    )
                    expected_external.add(".gitignore")
                backup = self.base / f"acgm-parent-backup-{existing}"
                runtime = self.load_runtime_module()
                injected = False
                real_open = runtime.os.open

                with mock.patch.dict(os.environ, self.env, clear=False):
                    plan = runtime._quickstart_plan(str(project))

                    def swap_after_parent_open(
                        path: object,
                        flags: int,
                        *args: object,
                        **kwargs: object,
                    ) -> int:
                        nonlocal injected
                        if (
                            str(path).startswith(
                                ".quickstart.json.acgm-create-"
                            )
                            and kwargs.get("dir_fd") is not None
                            and not injected
                        ):
                            (project / ".acgm").rename(backup)
                            (project / ".acgm").symlink_to(
                                external, target_is_directory=True
                            )
                            injected = True
                        return real_open(path, flags, *args, **kwargs)

                    with mock.patch.object(
                        runtime.os, "open", side_effect=swap_after_parent_open
                    ):
                        result = runtime._apply_quickstart(
                            str(project),
                            authorized=True,
                            expected_digest=plan["plan_digest"],
                        )

                self.assertTrue(injected)
                self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
                self.assertTrue(result["partial"])
                self.assertEqual(
                    {
                        path.relative_to(external).as_posix()
                        for path in external.rglob("*")
                        if path.is_file()
                    },
                    expected_external,
                )
                self.assertFalse((external / "quickstart.json").exists())
                self.assertFalse((external / "codex.json").exists())

    def test_quickstart_new_directory_publication_never_adopts_concurrent_entry(
        self,
    ) -> None:
        project = self.make_repository(self.base / "directory-publish-race")
        external = self.base / "concurrent-directory"
        external.mkdir()
        (external / "owner-marker.txt").write_text(
            "preserve\n", encoding="utf-8"
        )
        runtime = self.load_runtime_module()
        injected = False
        real_publish = runtime._rename_quickstart_directory_noreplace

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(project))

            def publish_after_concurrent_entry(
                parent_fd: int, source: str, destination: str
            ) -> None:
                nonlocal injected
                if destination == ".acgm" and not injected:
                    external.rename(project / ".acgm")
                    injected = True
                real_publish(parent_fd, source, destination)

            with mock.patch.object(
                runtime,
                "_rename_quickstart_directory_noreplace",
                side_effect=publish_after_concurrent_entry,
            ):
                result = runtime._apply_quickstart(
                    str(project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"])
        self.assertEqual(
            sorted(path.name for path in (project / ".acgm").iterdir()),
            ["owner-marker.txt"],
        )
        self.assertFalse((project / "CONSTITUTION.md").exists())

    def test_quickstart_late_asset_symlink_never_reports_success(self) -> None:
        project = self.make_repository(self.base / "late-asset-symlink")
        external = self.base / "external-constitution.md"
        runtime = self.load_runtime_module()
        external.write_text(runtime.STANDARD_CONSTITUTION, encoding="utf-8")
        backup = self.base / "constitution-backup.md"
        injected = False
        real_baseline = runtime._quickstart_component_baseline_at

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(project))

            def swap_after_anchored_verification(
                root_fd: int,
                governance_fd: int,
                decisions_fd: int,
                snapshots_fd: int,
            ) -> dict[str, object]:
                nonlocal injected
                baseline = real_baseline(
                    root_fd,
                    governance_fd,
                    decisions_fd,
                    snapshots_fd,
                )
                if not injected:
                    (project / "CONSTITUTION.md").rename(backup)
                    (project / "CONSTITUTION.md").symlink_to(external)
                    injected = True
                return baseline

            with mock.patch.object(
                runtime,
                "_quickstart_component_baseline_at",
                side_effect=swap_after_anchored_verification,
            ):
                result = runtime._apply_quickstart(
                    str(project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertFalse(result["ok"])
        self.assertFalse(result["complete"])
        self.assertTrue(result["partial"])
        self.assertTrue((project / "CONSTITUTION.md").is_symlink())
        self.assertEqual(
            external.read_text(encoding="utf-8"), runtime.STANDARD_CONSTITUTION
        )

    def test_quickstart_governance_directory_swaps_never_write_outside_project(
        self,
    ) -> None:
        for relative in (
            ".governance",
            ".governance/decisions",
            ".governance/snapshots",
        ):
            with self.subTest(relative=relative):
                slug = relative.replace("/", "-").replace(".", "dot")
                project = self.make_repository(self.base / f"parent-swap-{slug}")
                (project / ".governance" / "decisions").mkdir(parents=True)
                (project / ".governance" / "snapshots").mkdir(parents=True)
                external = self.base / f"parent-external-{slug}"
                external.mkdir()
                (external / "owner-marker.txt").write_text(
                    "preserve\n", encoding="utf-8"
                )
                backup = self.base / f"parent-backup-{slug}"
                target = project / relative
                trigger = {
                    ".governance": ".scope.yml.acgm-create-",
                    ".governance/decisions": (
                        ".0001-adopt-acgm-standard-v1.md.acgm-create-"
                    ),
                    ".governance/snapshots": ".bootstrap.md.acgm-create-",
                }[relative]
                runtime = self.load_runtime_module()
                injected = False
                real_open = runtime.os.open

                with mock.patch.dict(os.environ, self.env, clear=False):
                    plan = runtime._quickstart_plan(str(project))

                    def swap_after_parent_open(
                        path: object,
                        flags: int,
                        *args: object,
                        **kwargs: object,
                    ) -> int:
                        nonlocal injected
                        if (
                            str(path).startswith(trigger)
                            and kwargs.get("dir_fd") is not None
                            and not injected
                        ):
                            target.rename(backup)
                            target.symlink_to(external, target_is_directory=True)
                            injected = True
                        return real_open(path, flags, *args, **kwargs)

                    with mock.patch.object(
                        runtime.os, "open", side_effect=swap_after_parent_open
                    ):
                        result = runtime._apply_quickstart(
                            str(project),
                            authorized=True,
                            expected_digest=plan["plan_digest"],
                        )

                self.assertTrue(injected)
                self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
                self.assertTrue(result["partial"])
                self.assertEqual(
                    sorted(
                        path.relative_to(external).as_posix()
                        for path in external.rglob("*")
                    ),
                    ["owner-marker.txt"],
                )

    def test_quickstart_does_not_adopt_an_unknown_reserved_decision(self) -> None:
        decision = (
            self.project
            / ".governance"
            / "decisions"
            / "0001-adopt-acgm-standard-v1.md"
        )
        decision.parent.mkdir(parents=True)
        decision.write_text(
            "# Existing unrelated decision\n\nThis reserved path already has project-owned meaning.\n",
            encoding="utf-8",
        )

        plan_result = self.cli(
            "quickstart", "plan", str(self.project), "--json"
        )
        plan = json.loads(plan_result.stdout)

        self.assertEqual(plan_result.returncode, 2)
        self.assertEqual(plan["status"], "PROJECT_ASSET_CONFLICT")
        self.assertEqual(
            decision.read_text(encoding="utf-8"),
            "# Existing unrelated decision\n\nThis reserved path already has project-owned meaning.\n",
        )
        self.assertFalse((self.project / ".acgm").exists())

    def test_quickstart_preserves_unknown_receipt_and_cas_binds_known_receipt(self) -> None:
        receipt = self.project / ".acgm" / "quickstart.json"
        receipt.parent.mkdir()
        unknown = b'{"schema":"someone-elses-record","keep":true}\n'
        receipt.write_bytes(unknown)

        conflict = self.cli("quickstart", "plan", str(self.project), "--json")
        conflict_payload = json.loads(conflict.stdout)

        self.assertEqual(conflict.returncode, 2)
        self.assertEqual(conflict_payload["status"], "PROJECT_ASSET_CONFLICT")
        self.assertIn(
            {"path": ".acgm/quickstart.json", "reason": "quickstart-receipt-is-unknown"},
            conflict_payload["conflicts"],
        )
        self.assertEqual(receipt.read_bytes(), unknown)
        self.assertFalse((self.project / "CONSTITUTION.md").exists())

        known = {
            "schema": "acgm-codex-quickstart-receipt-v1",
            "status": "OLDER_KNOWN_RECEIPT",
        }
        receipt.write_text(json.dumps(known), encoding="utf-8")
        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        concurrently_changed = dict(known, note="changed after authorization plan")
        receipt.write_text(json.dumps(concurrently_changed), encoding="utf-8")

        stale = self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            plan["plan_digest"],
            "--authorize",
            "--json",
        )

        self.assertEqual(json.loads(stale.stdout)["status"], "PLAN_STALE")
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8")), concurrently_changed)
        self.assertFalse((self.project / "CONSTITUTION.md").exists())

    def test_quickstart_policy_final_cas_preserves_edit_at_replace_boundary(self) -> None:
        self.cli("init", str(self.project), check=True)
        state_path = self.project / ".acgm" / "codex.json"
        state_before = state_path.read_bytes()
        runtime = self.load_runtime_module()
        concurrent_policy = (
            "# Concurrent project-owner policy\n\n"
            "This edit arrived at the final replacement boundary and must survive.\n"
        )
        injected = False
        real_link = runtime.os.link

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def edit_immediately_before_publish(
                source: object, destination: object, *args: object, **kwargs: object
            ) -> object:
                nonlocal injected
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    destination_path.name == "CONSTITUTION.md"
                    and ".acgm-prepared-" in source_path.name
                    and not injected
                ):
                    self.write_dirfd_file(
                        int(kwargs["dst_dir_fd"]),
                        destination_path.name,
                        concurrent_policy,
                    )
                    injected = True
                return real_link(source, destination, *args, **kwargs)

            with mock.patch.object(
                runtime.os, "link", side_effect=edit_immediately_before_publish
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertTrue(result["partial"])
        self.assertEqual(
            (self.project / "CONSTITUTION.md").read_text(encoding="utf-8"),
            concurrent_policy,
        )
        self.assertEqual(state_path.read_bytes(), state_before)

    def test_quickstart_policy_creation_never_overwrites_concurrent_writer(self) -> None:
        runtime = self.load_runtime_module()
        concurrent_policy = (
            "# Concurrent project-owner policy\n\n"
            "This file won the no-overwrite creation boundary.\n"
        )
        injected = False
        real_link = runtime.os.link

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def create_immediately_before_publish(
                source: object, destination: object, *args: object, **kwargs: object
            ) -> object:
                nonlocal injected
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    destination_path.name == "CONSTITUTION.md"
                    and ".acgm-create-" in source_path.name
                    and not injected
                ):
                    self.write_dirfd_file(
                        int(kwargs["dst_dir_fd"]),
                        destination_path.name,
                        concurrent_policy,
                    )
                    injected = True
                return real_link(source, destination, *args, **kwargs)

            with mock.patch.object(
                runtime.os, "link", side_effect=create_immediately_before_publish
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertTrue(result["partial"])
        self.assertEqual(
            (self.project / "CONSTITUTION.md").read_text(encoding="utf-8"),
            concurrent_policy,
        )
        self.assertFalse((self.project / ".acgm" / "codex.json").exists())
        self.assertFalse(
            any(".acgm-create-" in path.name for path in self.project.rglob("*"))
        )

    def test_quickstart_receipt_creation_never_overwrites_concurrent_writer(self) -> None:
        runtime = self.load_runtime_module()
        concurrent_receipt = {
            "schema": "concurrent-owner-receipt-v1",
            "concurrent_writer": "preserve-me",
        }
        injected = False
        real_link = runtime.os.link

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def create_immediately_before_publish(
                source: object, destination: object, *args: object, **kwargs: object
            ) -> object:
                nonlocal injected
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    destination_path.name == "quickstart.json"
                    and ".acgm-create-" in source_path.name
                    and not injected
                ):
                    self.write_dirfd_file(
                        int(kwargs["dst_dir_fd"]),
                        destination_path.name,
                        json.dumps(concurrent_receipt),
                    )
                    injected = True
                return real_link(source, destination, *args, **kwargs)

            with mock.patch.object(
                runtime.os, "link", side_effect=create_immediately_before_publish
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        receipt_path = self.project / ".acgm" / "quickstart.json"
        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertTrue(result["partial"])
        self.assertEqual(
            json.loads(receipt_path.read_text(encoding="utf-8")),
            concurrent_receipt,
        )
        self.assertFalse((self.project / "CONSTITUTION.md").exists())
        self.assertFalse(
            any(".acgm-create-" in path.name for path in self.project.rglob("*"))
        )

    def test_quickstart_receipt_creation_never_adopts_post_publish_edit(self) -> None:
        runtime = self.load_runtime_module()
        concurrent_receipt = {
            "schema": "concurrent-owner-receipt-v1",
            "concurrent_writer": "post-publish-preserve-me",
        }
        injected = False
        real_write_new_json = runtime._write_new_json_at

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def edit_after_publish(
                directory_fd: int,
                name: str,
                value: dict[str, object],
                mode: int = 0o600,
            ) -> str:
                nonlocal injected
                digest = real_write_new_json(directory_fd, name, value, mode)
                if name == "quickstart.json" and not injected:
                    self.write_dirfd_file(
                        directory_fd, name, json.dumps(concurrent_receipt)
                    )
                    injected = True
                return digest

            with mock.patch.object(
                runtime, "_write_new_json_at", side_effect=edit_after_publish
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        receipt_path = self.project / ".acgm" / "quickstart.json"
        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertEqual(
            json.loads(receipt_path.read_text(encoding="utf-8")),
            concurrent_receipt,
        )
        self.assertFalse((self.project / "CONSTITUTION.md").exists())

    def test_quickstart_state_creation_never_overwrites_concurrent_writer(self) -> None:
        runtime = self.load_runtime_module()
        concurrent_state = {
            "schema": "concurrent-owner-state-v1",
            "concurrent_writer": "preserve-me",
        }
        injected = False
        real_link = runtime.os.link

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def create_immediately_before_publish(
                source: object, destination: object, *args: object, **kwargs: object
            ) -> object:
                nonlocal injected
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    destination_path.name == "codex.json"
                    and ".acgm-create-" in source_path.name
                    and not injected
                ):
                    self.write_dirfd_file(
                        int(kwargs["dst_dir_fd"]),
                        destination_path.name,
                        json.dumps(concurrent_state),
                    )
                    injected = True
                return real_link(source, destination, *args, **kwargs)

            with mock.patch.object(
                runtime.os, "link", side_effect=create_immediately_before_publish
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        state_path = self.project / ".acgm" / "codex.json"
        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertTrue(result["partial"])
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8")), concurrent_state
        )
        self.assertFalse(
            any(".acgm-create-" in path.name for path in self.project.rglob("*"))
        )

    def test_quickstart_receipt_final_cas_preserves_concurrent_edit(self) -> None:
        initial_plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            initial_plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        receipt_path = self.project / ".acgm" / "quickstart.json"
        receipt_before = json.loads(receipt_path.read_text(encoding="utf-8"))
        runtime = self.load_runtime_module()
        injected = False
        real_link = runtime.os.link

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def edit_immediately_before_publish(
                source: object, destination: object, *args: object, **kwargs: object
            ) -> object:
                nonlocal injected
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    destination_path.name == "quickstart.json"
                    and ".acgm-prepared-" in source_path.name
                    and not injected
                ):
                    concurrent = dict(receipt_before)
                    concurrent["concurrent_writer"] = "preserve-me"
                    self.write_dirfd_file(
                        int(kwargs["dst_dir_fd"]),
                        destination_path.name,
                        json.dumps(concurrent),
                    )
                    injected = True
                return real_link(source, destination, *args, **kwargs)

            with mock.patch.object(
                runtime.os, "link", side_effect=edit_immediately_before_publish
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertTrue(result["partial"])
        self.assertEqual(
            json.loads(receipt_path.read_text(encoding="utf-8"))["concurrent_writer"],
            "preserve-me",
        )

    def test_quickstart_receipt_replacement_never_adopts_post_publish_edit(self) -> None:
        initial_plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            initial_plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        receipt_path = self.project / ".acgm" / "quickstart.json"
        concurrent_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        concurrent_receipt["concurrent_writer"] = "post-publish-preserve-me"
        runtime = self.load_runtime_module()
        injected = False
        real_cas_json_at = runtime._quickstart_cas_json_at

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def edit_after_publish(
                directory_fd: int,
                name: str,
                value: dict[str, object],
                expected_sha256: str,
                *,
                mode: int = 0o600,
            ) -> str:
                nonlocal injected
                digest = real_cas_json_at(
                    directory_fd,
                    name,
                    value,
                    expected_sha256,
                    mode=mode,
                )
                if name == "quickstart.json" and not injected:
                    self.write_dirfd_file(
                        directory_fd,
                        name,
                        json.dumps(concurrent_receipt),
                    )
                    injected = True
                return digest

            with mock.patch.object(
                runtime,
                "_quickstart_cas_json_at",
                side_effect=edit_after_publish,
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertEqual(
            json.loads(receipt_path.read_text(encoding="utf-8")),
            concurrent_receipt,
        )

    def test_quickstart_safely_upgrades_version_only_state_in_one_authorization(self) -> None:
        initial_plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            initial_plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        state_path = self.project / ".acgm" / "codex.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        activation_id = state["activation_id"]
        state["version"] = "0.1.0-rc.4"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.assertTrue(plan["version_only_upgrade"])
        upgraded = json.loads(
            self.cli(
                "quickstart",
                "apply",
                str(self.project),
                "--plan-digest",
                plan["plan_digest"],
                "--authorize",
                "--json",
                check=True,
            ).stdout
        )
        current = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertTrue(upgraded["ok"])
        self.assertEqual(current["version"], VERSION)
        self.assertEqual(current["activation_id"], activation_id)
        self.assertIn("upgraded_at", current)

        for incompatible_version in ("99.0.0", "0.1.0-local-build"):
            with self.subTest(incompatible_version=incompatible_version):
                incompatible = dict(current, version=incompatible_version)
                state_path.write_text(json.dumps(incompatible), encoding="utf-8")
                rejected = self.cli(
                    "quickstart", "plan", str(self.project), "--json"
                )
                rejected_plan = json.loads(rejected.stdout)
                self.assertEqual(rejected.returncode, 2)
                self.assertFalse(rejected_plan["version_only_upgrade"])
                self.assertIn(
                    {
                        "path": ".acgm/codex.json",
                        "reason": "adapter-version-not-compatible",
                    },
                    rejected_plan["conflicts"],
                )
                self.assertEqual(
                    json.loads(state_path.read_text(encoding="utf-8"))["version"],
                    incompatible_version,
                )

    def test_quickstart_state_final_cas_preserves_concurrent_edit(self) -> None:
        initial_plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            initial_plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        state_path = self.project / ".acgm" / "codex.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["version"] = "0.1.0-rc.4"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        runtime = self.load_runtime_module()
        injected = False
        real_link = runtime.os.link

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))

            def edit_immediately_before_publish(
                source: object, destination: object, *args: object, **kwargs: object
            ) -> object:
                nonlocal injected
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    destination_path.name == "codex.json"
                    and ".acgm-prepared-" in source_path.name
                    and not injected
                ):
                    concurrent = dict(state)
                    concurrent["concurrent_writer"] = "preserve-me"
                    self.write_dirfd_file(
                        int(kwargs["dst_dir_fd"]),
                        destination_path.name,
                        json.dumps(concurrent),
                    )
                    injected = True
                return real_link(source, destination, *args, **kwargs)

            with mock.patch.object(
                runtime.os, "link", side_effect=edit_immediately_before_publish
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertTrue(result["partial"])
        current = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(current["version"], "0.1.0-rc.4")
        self.assertEqual(current["concurrent_writer"], "preserve-me")

    def test_quickstart_adopts_standard_preset_into_healthy_manual_activation(self) -> None:
        self.init_activate()
        state_path = self.project / ".acgm" / "codex.json"
        original = json.loads(state_path.read_text(encoding="utf-8"))
        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )

        self.assertEqual(plan["project_state"], "GOVERNED")
        self.assertTrue(plan["planned_active_rebaseline"])
        applied = json.loads(
            self.cli(
                "quickstart",
                "apply",
                str(self.project),
                "--plan-digest",
                plan["plan_digest"],
                "--authorize",
                "--json",
                check=True,
            ).stdout
        )
        current = json.loads(state_path.read_text(encoding="utf-8"))
        doctor = json.loads(
            self.cli("doctor", str(self.project), "--json", check=True).stdout
        )

        self.assertFalse(applied["partial"])
        self.assertEqual(current["activation_id"], original["activation_id"])
        self.assertEqual(current["preset"], "standard-v1")
        self.assertIn("quickstart_rebaselined_at", current)
        self.assertTrue(
            (
                self.project
                / ".governance"
                / "decisions"
                / "0001-adopt-acgm-standard-v1.md"
            ).is_file()
        )
        self.assertTrue(
            (self.project / ".governance" / "snapshots" / "bootstrap.md").is_file()
        )
        self.assertEqual(doctor["project_state"], "GOVERNED")

    def test_quickstart_final_git_guard_blocks_mid_apply_nonmanaged_change(self) -> None:
        runtime = self.load_runtime_module()
        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))
            original = runtime._write_quickstart_receipt_cas_at
            call_count = 0

            def race_after_assets(
                directory_fd: int,
                value: dict[str, object],
                expected: str | None,
            ) -> str:
                nonlocal call_count
                digest = original(directory_fd, value, expected)
                call_count += 1
                if call_count == len(plan["assets"]) + 1:
                    (self.project / "README.md").write_text(
                        "concurrent nonmanaged change\n", encoding="utf-8"
                    )
                return digest

            with mock.patch.object(
                runtime,
                "_write_quickstart_receipt_cas_at",
                side_effect=race_after_assets,
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertIn("Git identity or state changed", result["error"])
        self.assertFalse((self.project / ".acgm" / "codex.json").exists())

    def test_quickstart_final_git_guard_blocks_mid_apply_index_change(self) -> None:
        runtime = self.load_runtime_module()
        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))
            original = runtime._write_quickstart_receipt_cas_at
            call_count = 0

            def stage_after_assets(
                directory_fd: int,
                value: dict[str, object],
                expected: str | None,
            ) -> str:
                nonlocal call_count
                digest = original(directory_fd, value, expected)
                call_count += 1
                if call_count == len(plan["assets"]) + 1:
                    subprocess.run(
                        ["git", "-C", str(self.project), "add", "CONSTITUTION.md"],
                        check=True,
                        capture_output=True,
                    )
                return digest

            with mock.patch.object(
                runtime,
                "_write_quickstart_receipt_cas_at",
                side_effect=stage_after_assets,
            ):
                result = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertEqual(result["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertIn("Git identity or state changed", result["error"])
        self.assertFalse((self.project / ".acgm" / "codex.json").exists())

    def test_quickstart_state_and_postimage_cas_block_version_rebaseline_races(self) -> None:
        initial_plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            initial_plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        state_path = self.project / ".acgm" / "codex.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["version"] = "0.1.0-rc.4"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        runtime = self.load_runtime_module()

        with mock.patch.dict(os.environ, self.env, clear=False):
            plan = runtime._quickstart_plan(str(self.project))
            original_activate = runtime._activate_project

            def race_state(root: Path, **kwargs: object) -> tuple[dict[str, object], bool]:
                concurrent = json.loads(state_path.read_text(encoding="utf-8"))
                concurrent["concurrent_writer"] = "preserve-me"
                state_path.write_text(json.dumps(concurrent), encoding="utf-8")
                return original_activate(root, **kwargs)

            with mock.patch.object(runtime, "_activate_project", side_effect=race_state):
                state_race = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=plan["plan_digest"],
                )

        self.assertEqual(state_race["status"], "PARTIAL_RECHECK_REQUIRED")
        preserved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(preserved["version"], "0.1.0-rc.4")
        self.assertEqual(preserved["concurrent_writer"], "preserve-me")

        preserved.pop("concurrent_writer")
        state_path.write_text(json.dumps(preserved), encoding="utf-8")
        decision = (
            self.project
            / ".governance"
            / "decisions"
            / "0001-adopt-acgm-standard-v1.md"
        )
        with mock.patch.dict(os.environ, self.env, clear=False):
            postimage_plan = runtime._quickstart_plan(str(self.project))

            def race_postimage(
                root: Path, **kwargs: object
            ) -> tuple[dict[str, object], bool]:
                decision.write_text(
                    decision.read_text(encoding="utf-8")
                    + "\nConcurrent governance edit.\n",
                    encoding="utf-8",
                )
                return original_activate(root, **kwargs)

            with mock.patch.object(
                runtime, "_activate_project", side_effect=race_postimage
            ):
                postimage_race = runtime._apply_quickstart(
                    str(self.project),
                    authorized=True,
                    expected_digest=postimage_plan["plan_digest"],
                )

        self.assertEqual(postimage_race["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertIn("managed asset changed", postimage_race["error"])
        self.assertFalse(postimage_race["claims"]["project_activated"])
        self.assertNotIn(
            "activation:updated", postimage_race["completed_steps"]
        )
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8"))["version"],
            "0.1.0-rc.4",
        )

    def test_quickstart_status_completes_after_real_hook_observation(self) -> None:
        plan = json.loads(
            self.cli(
                "quickstart", "plan", str(self.project), "--json", check=True
            ).stdout
        )
        self.cli(
            "quickstart",
            "apply",
            str(self.project),
            "--plan-digest",
            plan["plan_digest"],
            "--authorize",
            "--json",
            check=True,
        )
        before = json.loads(
            self.cli(
                "quickstart", "status", str(self.project), "--json", check=True
            ).stdout
        )
        self.assertEqual(before["status"], "AWAITING_PLATFORM_HOOK_ACCEPTANCE")

        self.pre_bash("git status --short")
        after = json.loads(
            self.cli(
                "quickstart", "status", str(self.project), "--json", check=True
            ).stdout
        )
        self.assertEqual(after["status"], "COMPLETE")
        self.assertTrue(after["complete"])

    def test_unborn_empty_parent_with_multiple_repositories_is_ambiguous(self) -> None:
        workspace, repositories = self.make_container_workspace("alpha", "beta", "gamma")

        result = self.cli("init", cwd=workspace)

        self.assertEqual(result.returncode, 2)
        self.assertIn("multiple repositories", result.stderr)
        for root in [workspace, *repositories]:
            self.assertFalse((root / "CONSTITUTION.md").exists())
            self.assertFalse((root / ".governance").exists())
            self.assertFalse((root / ".acgm").exists())

    def test_inactive_residual_adapter_does_not_hide_ambiguous_container(self) -> None:
        workspace, repositories = self.make_container_workspace("alpha", "beta")
        state_path = workspace / ".acgm" / "codex.json"
        state_path.parent.mkdir()
        residual = {
            "schema": "acgm-codex-state-v1",
            "version": VERSION,
            "active": False,
            "platform": "codex",
        }
        state_path.write_text(json.dumps(residual), encoding="utf-8")
        before = state_path.read_bytes()

        result = self.cli("init", cwd=workspace)

        self.assertEqual(result.returncode, 2)
        self.assertIn("multiple repositories", result.stderr)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertFalse((workspace / "CONSTITUTION.md").exists())
        for repository in repositories:
            self.assertFalse((repository / "CONSTITUTION.md").exists())

        _, hook_output = self.hook(
            "session-start",
            self.payload("SessionStart", cwd=str(workspace), source="startup"),
        )
        context = hook_output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("multi-repository workspace", context)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertFalse(self.data.exists())

    def test_ambiguous_session_start_fails_open_without_ledger_or_init_hint(self) -> None:
        workspace, _ = self.make_container_workspace("alpha", "beta")

        _, output = self.hook(
            "session-start",
            self.payload("SessionStart", cwd=str(workspace), source="startup"),
        )

        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("multi-repository workspace", context)
        self.assertNotIn("acgm-codex init", context)
        self.assertFalse(self.data.exists())

    def test_explicit_child_init_writes_only_selected_repository(self) -> None:
        workspace, repositories = self.make_container_workspace("alpha", "beta")
        selected = repositories[1]

        result = self.cli("init", str(selected), cwd=workspace, check=True)

        self.assertIn("initialized without overwriting", result.stdout)
        self.assertTrue((selected / "CONSTITUTION.md").is_file())
        self.assertFalse((workspace / "CONSTITUTION.md").exists())
        self.assertFalse((repositories[0] / "CONSTITUTION.md").exists())

    def test_unique_direct_repository_is_selected_from_empty_container(self) -> None:
        workspace, repositories = self.make_container_workspace("only-project")

        self.cli("init", cwd=workspace, check=True)

        self.assertTrue((repositories[0] / "CONSTITUTION.md").is_file())
        self.assertFalse((workspace / "CONSTITUTION.md").exists())

    def test_unique_child_is_not_selected_when_unborn_parent_has_other_files(
        self,
    ) -> None:
        for marker_name, ignored in (
            ("PARENT_NOTES.md", False),
            ("ignored-parent-state.log", True),
        ):
            with self.subTest(marker=marker_name, ignored=ignored):
                workspace, repositories = self.make_container_workspace(
                    "only-" + ("ignored" if ignored else "untracked")
                )
                if ignored:
                    exclude = workspace / ".git" / "info" / "exclude"
                    exclude.write_text(marker_name + "\n", encoding="utf-8")
                marker = workspace / marker_name
                marker.write_text("parent-owned work\n", encoding="utf-8")

                result = self.cli("init", cwd=workspace)

                self.assertEqual(result.returncode, 2)
                self.assertIn("non-container files", result.stderr)
                self.assertEqual(marker.read_text(encoding="utf-8"), "parent-owned work\n")
                self.assertFalse((workspace / "CONSTITUTION.md").exists())
                self.assertFalse((repositories[0] / "CONSTITUTION.md").exists())
                _, output = self.hook(
                    "session-start",
                    self.payload(
                        "SessionStart", cwd=str(workspace), source="startup"
                    ),
                )
                context = output["hookSpecificOutput"]["additionalContext"]
                self.assertIn("multi-repository workspace", context)
                self.assertFalse(self.data.exists())

    def test_committed_parent_with_nested_repository_remains_the_project(self) -> None:
        workspace = self.make_repository(self.base / "committed-parent")
        nested = self.make_repository(workspace / "nested")

        self.cli("init", cwd=workspace, check=True)

        self.assertTrue((workspace / "CONSTITUTION.md").is_file())
        self.assertFalse((nested / "CONSTITUTION.md").exists())

    def test_directory_content_change_produces_drift(self) -> None:
        self.init_activate()
        decision = self.project / ".governance" / "decisions" / "0001-initial.md"
        decision.write_text(decision.read_text(encoding="utf-8") + "Changed later.\n", encoding="utf-8")
        doctor = json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)
        self.assertEqual(doctor["project_state"], "DRIFTED")
        self.assertIn(".governance/decisions:changed", doctor["drift"])

    def test_activate_doctor_and_hook_observation(self) -> None:
        self.init_activate()
        before = json.loads(self.cli("doctor", str(self.project), "--json").stdout)
        self.assertEqual(before["project_state"], "GOVERNED")
        self.assertFalse(before["hook"]["observed"])
        self.assertFalse(before["healthy"])
        self.assertEqual(self.cli("doctor", str(self.project), "--strict").returncode, 2)

        _, output = self.hook(
            "session-start",
            self.payload("SessionStart", source="startup", model="private-model-name"),
        )
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
        after = json.loads(
            self.cli("doctor", str(self.project), "--json", "--strict", check=True).stdout
        )
        self.assertTrue(after["hook"]["observed"])
        self.assertTrue(after["healthy"])

    def test_reactivation_invalidates_old_activation_heartbeat(self) -> None:
        self.init_activate()
        state_path = self.project / ".acgm" / "codex.json"
        first_activation = json.loads(state_path.read_text(encoding="utf-8"))["activation_id"]
        self.hook("session-start", self.payload("SessionStart", source="startup"))
        self.assertTrue(
            json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)[
                "healthy"
            ]
        )

        self.cli("activate", str(self.project), check=True)
        second_activation = json.loads(state_path.read_text(encoding="utf-8"))["activation_id"]
        self.assertNotEqual(first_activation, second_activation)
        stale = json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)
        self.assertFalse(stale["hook"]["observed"])
        self.assertFalse(stale["healthy"])

        self.hook("session-start", self.payload("SessionStart", source="startup"))
        recovered = json.loads(
            self.cli("doctor", str(self.project), "--json", "--strict", check=True).stdout
        )
        self.assertTrue(recovered["hook"]["observed"])
        self.assertTrue(recovered["healthy"])

    def test_missing_agents_is_drift_even_if_claude_file_exists(self) -> None:
        self.init_activate()
        (self.project / "AGENTS.md").unlink()
        (self.project / "CLAUDE.md").write_text(
            "# Claude instructions\n\nThis file cannot replace the Codex asset.\n",
            encoding="utf-8",
        )
        doctor = json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)
        self.assertEqual(doctor["project_state"], "DRIFTED")
        self.assertIn("AGENTS.md", doctor["missing"])
        self.assertTrue(any(item.startswith("AGENTS.md:") for item in doctor["drift"]))

    def test_uninitialized_project_is_warn_only_and_not_blocked(self) -> None:
        output = self.pre_bash("git reset --hard HEAD")
        self.assertEqual(output, {})
        _, start = self.hook("session-start", self.payload("SessionStart", source="startup"))
        self.assertIn("not active", start["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("gate-denied", self.event_kinds())

    def test_apply_patch_body_mention_is_allowed_but_target_is_blocked(self) -> None:
        self.init_activate()
        mention = self.payload(
            "PreToolUse",
            tool_name="apply_patch",
            tool_use_id="patch-mention",
            tool_input={
                "command": "*** Update File: README.md\n+Explain that CONSTITUTION.md is human-owned."
            },
        )
        self.assertEqual(self.hook("pre-tool", mention)[1], {})
        target = self.payload(
            "PreToolUse",
            tool_name="apply_patch",
            tool_use_id="patch-target",
            tool_input={"command": "*** Update File: CONSTITUTION.md\n+unsafe"},
        )
        decision = self.hook("pre-tool", target)[1]["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")

        move_target = self.payload(
            "PreToolUse",
            tool_name="apply_patch",
            tool_use_id="patch-move-target",
            tool_input={
                "command": "*** Update File: README.md\n*** Move to: CONSTITUTION.md\n@@\n-old\n+new"
            },
        )
        move_decision = self.hook("pre-tool", move_target)[1]["hookSpecificOutput"]
        self.assertEqual(move_decision["permissionDecision"], "deny")

    def test_constitution_shell_writer_variants_are_blocked(self) -> None:
        self.init_activate()
        for command in (
            "printf bad > CONSTITUTION.md",
            "cat replacement >./CONSTITUTION.md",
            ": <> CONSTITUTION.md",
            "git restore CONSTITUTION.md",
            "git checkout -- CONSTITUTION.md",
            "dd if=/tmp/replacement of=CONSTITUTION.md",
            "acgm-codex export-case abc -o CONSTITUTION.md",
            "cp README.md CONSTITUTION.md",
            "mv CONSTITUTION.md backup.md",
            "cat replacement | tee CONSTITUTION.md",
            "sed -i.bak 's/old/new/' CONSTITUTION.md",
            "perl -pi -e 's/old/new/' CONSTITUTION.md",
            "sh -c 'printf bad > CONSTITUTION.md'",
            "bash -lc 'cp README.md CONSTITUTION.md'",
            "env cp README.md CONSTITUTION.md",
            "command cp README.md CONSTITUTION.md",
            "sudo -- cp README.md CONSTITUTION.md",
        ):
            with self.subTest(command=command):
                result = self.pre_bash(command)
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        for command in (
            "sed -n '1,20p' CONSTITUTION.md",
            "nl -ba CONSTITUTION.md | sed -n '1,20p'",
            "sed -n '1,20p' /tmp/session-grounding/SKILL.md && "
            "sed -n '1,20p' CONSTITUTION.md",
            "cp README.md /tmp/readme-copy && sed -n '1,20p' CONSTITUTION.md",
            "cp CONSTITUTION.md /tmp/constitution-backup.md",
            "cat CONSTITUTION.md | tee /tmp/constitution-backup.md",
            "dd if=CONSTITUTION.md of=/tmp/constitution-backup.md",
            "sh -c 'sed -n 1,20p CONSTITUTION.md'",
            "env sed -n '1,20p' CONSTITUTION.md",
            "command sed -n '1,20p' CONSTITUTION.md",
            "perl -Ilib -ne 'print' CONSTITUTION.md",
            "sed -i -e CONSTITUTION.md README.md",
            "perl -pi -e CONSTITUTION.md README.md",
            "perl -pi CONSTITUTION.md README.md",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.pre_bash(command), {})

    def test_codex_string_tool_response_never_becomes_gate_evidence(self) -> None:
        self.init_activate()
        denied = self.pre_bash("git reset --hard HEAD")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        source = self.latest_event("gate-denied")

        self.post_bash(
            "git status --short",
            response="aggregated stdout without an authenticated exit status",
        )
        self.assertNotIn("state-check-observed", self.event_kinds())

        accepted, armed = self.gate_operation("arm", source)
        self.assertIn("fixed, non-shell read-only check", accepted["systemMessage"])
        self.assertEqual(armed.returncode, 0, armed.stderr)
        self.assertIn("not user authorization", armed.stdout)
        self.assertIn("state-check-observed", self.event_kinds())
        retry = self.pre_bash("git reset --hard HEAD")
        self.assertNotIn("hookSpecificOutput", retry)

    def test_output_capable_commands_never_count_as_direct_check_evidence(self) -> None:
        self.init_activate()
        output = self.base / "diff-output.txt"
        command = f"git diff --output={output}"
        self.assertEqual(self.pre_bash(command), {})
        completed = subprocess.run(
            ["git", "diff", f"--output={output}"],
            cwd=str(self.project),
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(output.is_file())
        self.assertEqual(self.post_bash(command, response=""), {})

        for ambiguous in (
            "find . -fprint evidence.txt",
            "tree -o evidence.txt",
            "git status & touch evidence.txt",
        ):
            self.assertEqual(self.pre_bash(ambiguous), {})
            self.assertEqual(
                self.post_bash(ambiguous, response={"exit_code": 0}), {}
            )
        self.assertNotIn("state-check-observed", self.event_kinds())

    def test_git_target_binding_rejects_cross_repo_arm(self) -> None:
        self.init_activate()
        other = self.base / "other-repo"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        self.pre_bash("git reset --hard HEAD")
        source = self.latest_event("gate-denied")
        rejected, failed_cli = self.gate_operation("arm", source, target=other)
        self.assertIn("rejected", rejected["systemMessage"])
        self.assertEqual(failed_cli.returncode, 2)

        accepted, armed = self.gate_operation("arm", source)
        self.assertIn("accepted", accepted["systemMessage"])
        self.assertEqual(armed.returncode, 0, armed.stderr)
        self.assertNotIn("hookSpecificOutput", self.pre_bash("git reset --hard HEAD"))

    def test_filesystem_target_binding_rejects_cross_directory_arm(self) -> None:
        self.init_activate()
        other = self.base / "other-directory"
        other.mkdir()
        self.pre_bash("rm -rf build-cache")
        source = self.latest_event("gate-denied")
        rejected, failed_cli = self.gate_operation("arm", source, target=other)
        self.assertIn("rejected", rejected["systemMessage"])
        self.assertEqual(failed_cli.returncode, 2)

        accepted, armed = self.gate_operation("arm", source)
        self.assertIn("accepted", accepted["systemMessage"])
        self.assertEqual(armed.returncode, 0, armed.stderr)
        self.assertNotIn("hookSpecificOutput", self.pre_bash("rm -rf build-cache"))

    def test_gate_obligation_crosses_turn_and_failed_fixed_check_does_not_close(self) -> None:
        self.init_activate()
        turn_one = {"turn_id": "first-turn"}
        self.pre_bash("git reset --hard HEAD", **turn_one)
        source = self.latest_event("gate-denied")
        _, armed = self.gate_operation(
            "arm", source, hook_overrides=turn_one
        )
        self.assertEqual(armed.returncode, 0, armed.stderr)
        self.pre_bash("git reset --hard HEAD", **turn_one)
        opened = self.post_bash(
            "git reset --hard HEAD",
            response="real Codex Bash response text",
            **turn_one,
        )
        self.assertIn(
            "verification obligation",
            opened["hookSpecificOutput"]["additionalContext"],
        )
        obligation = self.latest_event("obligation-opened")

        turn_two = {"turn_id": "second-turn"}
        git_directory = self.project / ".git"
        hidden_git_directory = self.project / ".git.temporarily-missing"
        git_directory.rename(hidden_git_directory)
        accepted_failure, failed_cli = self.gate_operation(
            "verify", obligation, hook_overrides=turn_two
        )
        self.assertIn("accepted", accepted_failure["systemMessage"])
        self.assertEqual(failed_cli.returncode, 3)
        hidden_git_directory.rename(git_directory)
        _, blocked = self.hook(
            "stop",
            self.payload(
                "Stop",
                turn_id="second-turn",
                stop_hook_active=False,
                last_assistant_message="private response",
            ),
        )
        self.assertEqual(blocked["decision"], "block")

        accepted, verified = self.gate_operation(
            "verify", obligation, hook_overrides=turn_two
        )
        self.assertIn("accepted", accepted["systemMessage"])
        self.assertEqual(verified.returncode, 0, verified.stderr)
        _, stopped = self.hook(
            "stop",
            self.payload("Stop", turn_id="second-turn", stop_hook_active=True),
        )
        self.assertEqual(stopped, {})

    def test_stop_loop_guard_releases_unresolved_obligation_once(self) -> None:
        self.init_activate()
        self.pre_bash("git reset --hard HEAD")
        source = self.latest_event("gate-denied")
        _, armed = self.gate_operation("arm", source)
        self.assertEqual(armed.returncode, 0, armed.stderr)
        self.pre_bash("git reset --hard HEAD")
        self.post_bash("git reset --hard HEAD", response="real Codex response")
        stop_payload = self.payload(
            "Stop", stop_hook_active=False, last_assistant_message="private response"
        )
        _, first = self.hook("stop", stop_payload)
        self.assertEqual(first["decision"], "block")
        stop_payload["stop_hook_active"] = True
        _, second = self.hook("stop", stop_payload)
        self.assertNotIn("decision", second)
        self.assertIn("avoid a Stop-hook loop", second["systemMessage"])
        self.assertIn("obligation-unresolved", self.event_kinds())

    def test_expanded_or_compound_targets_are_denied_but_unarmable(self) -> None:
        self.init_activate()
        for command in (
            "git status & rm -rf build-cache",
            "rm -rf $HOME/private-cache",
            "rm -rf ~/private-cache",
            "rm -rf *.tmp",
        ):
            with self.subTest(command=command):
                decision = self.pre_bash(command)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn("cannot be armed", decision["permissionDecisionReason"])

    def test_supported_high_risk_matcher_variants_are_denied(self) -> None:
        self.init_activate()
        cases = {
            "/usr/bin/git branch --delete --force feature": "git-branch-delete",
            "git clean --force --directories": "git-clean-force",
            "git push --force-with-lease origin main": "git-force-push",
            "/bin/rm --recursive --force scratch": "recursive-delete",
        }
        for command, category in cases.items():
            with self.subTest(command=command):
                result = self.pre_bash(command)
                reason = result["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertIn(category, reason)

    def test_permission_request_never_bypasses_codex_approval(self) -> None:
        self.init_activate()
        payload = self.payload(
            "PermissionRequest",
            tool_name="Bash",
            tool_input={"command": "git push --force", "description": "private reason"},
        )
        self.assertEqual(self.hook("permission-request", payload)[1], {})

    def test_first_trusted_hook_completes_heartbeat_without_second_task(self) -> None:
        self.init_activate()
        self.pre_bash("git status --short")
        self.post_bash("git status --short")
        self.hook(
            "permission-request",
            self.payload("PermissionRequest", tool_name="Bash", tool_input={"command": "pwd"}),
        )
        self.hook("stop", self.payload("Stop", stop_hook_active=False))
        self.hook("session-start", self.payload("SessionStart", source="startup"))
        self.hook("subagent-start", self.payload("SubagentStart", agent_id="private"))
        self.hook("pre-compact", self.payload("PreCompact", trigger="auto"))
        heartbeats = [
            event for event in self.report_json()["events"] if event["kind"] == "hook-heartbeat"
        ]
        self.assertEqual(
            [event["category"] for event in heartbeats],
            ["pre-tool", "session-start", "subagent-start", "pre-compact"],
        )

    def test_preactivation_heartbeat_is_stale_and_later_runtime_error_is_unhealthy(self) -> None:
        self.cli("init", str(self.project), check=True)
        self.complete_assets()
        self.hook("session-start", self.payload("SessionStart", source="startup"))
        self.cli("activate", str(self.project), check=True)
        stale = json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)
        self.assertFalse(stale["hook"]["observed"])
        self.assertFalse(stale["healthy"])

        self.hook("session-start", self.payload("SessionStart", source="startup"))
        healthy = json.loads(self.cli("doctor", str(self.project), "--json", check=True).stdout)
        self.assertTrue(healthy["healthy"])
        invalid = subprocess.run(
            [sys.executable, str(RUNTIME), "hook", "pre-tool"],
            cwd=str(self.project),
            env=self.env,
            input="not-json",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(invalid.returncode, 0)
        after_error = json.loads(
            self.cli("doctor", str(self.project), "--json", check=True).stdout
        )
        self.assertFalse(after_error["hook"]["observed"])
        self.assertTrue(after_error["hook"]["runtime_error_after_last_heartbeat"])
        self.assertFalse(after_error["healthy"])
        quickstart_status = self.cli(
            "quickstart", "status", str(self.project), "--json"
        )
        status_payload = json.loads(quickstart_status.stdout)
        self.assertEqual(quickstart_status.returncode, 2)
        self.assertEqual(status_payload["status"], "HOOK_RUNTIME_REPAIR_REQUIRED")
        self.assertNotEqual(
            status_payload["status"], "AWAITING_PLATFORM_HOOK_ACCEPTANCE"
        )

    def test_plugin_data_locator_shares_hook_ledger_with_standalone_cli(self) -> None:
        self.init_activate()
        home = self.base / "isolated-home"
        plugin_data = self.base / "official-plugin-data"
        hook_env = os.environ.copy()
        hook_env.pop("ACGM_CODEX_DATA_DIR", None)
        hook_env["PLUGIN_DATA"] = str(plugin_data)
        hook_env["HOME"] = str(home)
        hook_env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.hook(
            "session-start",
            self.payload("SessionStart", source="startup"),
            env=hook_env,
        )
        locator = home / ".codex" / "acgm-codex" / "data-location.json"
        locator_value = json.loads(locator.read_text(encoding="utf-8"))
        self.assertEqual(locator_value["schema"], "acgm-codex-data-location-v1")
        self.assertEqual(Path(locator_value["path"]), plugin_data.resolve())
        self.assertEqual(stat.S_IMODE(locator.stat().st_mode), 0o600)

        standalone_env = hook_env.copy()
        standalone_env.pop("PLUGIN_DATA")
        report = self.report_json(env=standalone_env)
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["events"][0]["kind"], "hook-heartbeat")
        self.assertEqual(stat.S_IMODE(locator.stat().st_mode), 0o600)

    def test_standalone_doctor_and_report_do_not_write_plugin_data(self) -> None:
        self.init_activate()
        home = self.base / "isolated-home"
        plugin_data = self.base / "official-plugin-data"
        hook_env = os.environ.copy()
        hook_env.pop("ACGM_CODEX_DATA_DIR", None)
        hook_env["PLUGIN_DATA"] = str(plugin_data)
        hook_env["HOME"] = str(home)
        hook_env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.hook(
            "session-start",
            self.payload("SessionStart", source="startup"),
            env=hook_env,
        )

        standalone_env = hook_env.copy()
        standalone_env.pop("PLUGIN_DATA")
        guarded_runner = """
import os
import runpy
import sys

runtime = sys.argv[1]
arguments = sys.argv[2:]
original_open = os.open
write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

def guarded_open(path, flags, mode=0o777, *, dir_fd=None):
    if flags & write_flags:
        raise PermissionError(f"write-capable os.open denied: {path}")
    if dir_fd is None:
        return original_open(path, flags, mode)
    return original_open(path, flags, mode, dir_fd=dir_fd)

def deny_mutation(*args, **kwargs):
    raise PermissionError("filesystem mutation denied")

os.open = guarded_open
os.chmod = deny_mutation
os.mkdir = deny_mutation
os.replace = deny_mutation
sys.argv = [runtime, *arguments]
runpy.run_path(runtime, run_name="__main__")
"""

        def guarded_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "-B", "-c", guarded_runner, str(RUNTIME), *arguments],
                cwd=str(self.project),
                env=standalone_env,
                text=True,
                capture_output=True,
                check=False,
            )

        watched = [
            home / ".codex" / "acgm-codex" / "data-location.json",
            plugin_data,
            plugin_data / "events.jsonl",
            plugin_data / "hmac.key",
            plugin_data / "hmac.key.lock",
        ]
        before = {
            path: (
                stat.S_IMODE(path.stat().st_mode),
                path.stat().st_size,
                path.stat().st_mtime_ns,
            )
            for path in watched
        }

        doctor = guarded_cli("doctor", str(self.project), "--json", "--strict")
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertTrue(json.loads(doctor.stdout)["healthy"])

        report = guarded_cli(
            "report", "--project", str(self.project), "--limit", "20", "--json"
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertEqual(json.loads(report.stdout)["count"], 1)

        after = {
            path: (
                stat.S_IMODE(path.stat().st_mode),
                path.stat().st_size,
                path.stat().st_mtime_ns,
            )
            for path in watched
        }
        self.assertEqual(after, before)

    def test_ledger_is_sanitized_append_only_and_mode_0600(self) -> None:
        self.init_activate()
        secret_path = str(self.project / "customer-secret.txt")
        payload = self.payload(
            "SessionStart",
            source="startup",
            model="provider/private-model",
            transcript_path="/private/transcript.jsonl",
            prompt=f"super-secret-token at {secret_path}",
        )
        self.hook("session-start", payload)
        ledger = self.data / "events.jsonl"
        text = ledger.read_text(encoding="utf-8")
        for forbidden in (
            "super-secret-token",
            secret_path,
            "provider/private-model",
            "/private/transcript.jsonl",
            "session-sensitive-value",
            "turn-sensitive-value",
        ):
            self.assertNotIn(forbidden, text)
        self.assertEqual(stat.S_IMODE(ledger.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.data / "hmac.key").stat().st_mode), 0o600)
        for line in text.splitlines():
            event = json.loads(line)
            self.assertEqual(event["schema"], "acgm-codex-event-v1")
            self.assertEqual(event["version"], VERSION)

    def test_missing_hmac_key_is_not_silently_recreated(self) -> None:
        self.init_activate()
        self.hook("session-start", self.payload("SessionStart", source="startup"))
        key = self.data / "hmac.key"
        key.unlink()
        report = self.cli("report", "--json")
        self.assertEqual(report.returncode, 2)
        self.assertIn("ledger key is missing", report.stderr)
        self.assertFalse(key.exists())

    def test_corrupt_ledger_is_reported(self) -> None:
        self.init_activate()
        self.hook("session-start", self.payload("SessionStart", source="startup"))
        with (self.data / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("{not-valid-json}\n")
        report = self.cli("report", "--json")
        self.assertEqual(report.returncode, 2)
        self.assertIn("invalid JSON", report.stderr)

    def test_invalid_hook_json_fails_open_but_records_error(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNTIME), "hook", "pre-tool"],
            cwd=str(self.project),
            env=self.env,
            input="not-json",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertIn("failed open", output["systemMessage"])
        self.assertIn("runtime-error", self.event_kinds())

    def test_export_never_overwrites_existing_or_governance_state(self) -> None:
        self.init_activate()
        self.pre_bash("git clean -fd")
        source = next(
            event for event in self.report_json()["events"] if event["kind"] == "gate-denied"
        )
        existing = self.base / "existing.json"
        existing.write_text("keep-me", encoding="utf-8")
        refused_existing = self.cli(
            "export-case", source["event_id"], "-o", str(existing)
        )
        self.assertEqual(refused_existing.returncode, 2)
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep-me")

        constitution = self.project / "CONSTITUTION.md"
        constitution_before = constitution.read_bytes()
        refused_governance = self.cli(
            "export-case", source["event_id"], "-o", str(constitution)
        )
        self.assertEqual(refused_governance.returncode, 2)
        self.assertEqual(constitution.read_bytes(), constitution_before)
        protected_new = self.project / ".acgm" / "case.json"
        refused_state = self.cli(
            "export-case", source["event_id"], "-o", str(protected_new)
        )
        self.assertEqual(refused_state.returncode, 2)
        self.assertFalse(protected_new.exists())

        output = self.base / "case.json"
        self.cli("export-case", source["event_id"], "-o", str(output), check=True)
        case = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(case["schema"], "acgm-codex-case-v1")
        self.assertEqual(case["privacy"]["commands"], "not-collected")
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_resolution_uses_false_positive_status(self) -> None:
        self.init_activate()
        self.pre_bash("git clean -fd")
        source = next(
            event for event in self.report_json()["events"] if event["kind"] == "gate-denied"
        )
        resolved = self.cli(
            "resolve", source["event_id"], "--status", "false_positive", check=True
        )
        self.assertIn("false_positive", resolved.stdout)
        self.assertTrue(
            any(
                event["kind"] == "event-resolution"
                and event.get("ref_id") == source["event_id"]
                and event["outcome"] == "false_positive"
                for event in self.report_json()["events"]
            )
        )

    def test_human_resolution_closes_session_obligation(self) -> None:
        self.init_activate()
        self.pre_bash("git reset --hard HEAD")
        denial = self.latest_event("gate-denied")
        _, armed = self.gate_operation("arm", denial)
        self.assertEqual(armed.returncode, 0, armed.stderr)
        self.pre_bash("git reset --hard HEAD")
        self.post_bash("git reset --hard HEAD", response="real Codex response")
        obligation = self.latest_event("obligation-opened")
        self.cli(
            "resolve",
            str(obligation["event_id"]),
            "--status",
            "human_override",
            check=True,
        )
        _, stopped = self.hook(
            "stop", self.payload("Stop", stop_hook_active=False)
        )
        self.assertEqual(stopped, {})

    def test_concurrent_hook_writes_produce_valid_complete_lines(self) -> None:
        self.init_activate()

        def invoke(index: int) -> int:
            payload = self.payload(
                "PermissionRequest",
                session_id=f"session-{index}",
                turn_id=f"turn-{index}",
                tool_name="Bash",
                tool_use_id=f"tool-{index}",
                tool_input={"command": "pwd"},
            )
            result = subprocess.run(
                [sys.executable, str(RUNTIME), "hook", "permission-request"],
                cwd=str(self.project),
                env=self.env,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
            )
            json.loads(result.stdout)
            return result.returncode

        with ThreadPoolExecutor(max_workers=8) as executor:
            codes = list(executor.map(invoke, range(24)))
        self.assertEqual(codes, [0] * 24)
        lines = (self.data / "events.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines]
        self.assertEqual(
            len(
                [
                    event
                    for event in events
                    if event["kind"] == "permission-boundary-observed"
                ]
            ),
            24,
        )
        self.assertEqual(
            len([event for event in events if event["kind"] == "hook-heartbeat"]),
            1,
        )

    def test_one_time_gate_consumption_is_atomic_under_concurrency(self) -> None:
        self.init_activate()
        self.pre_bash("git reset --hard HEAD")
        denial = self.latest_event("gate-denied")
        _, armed = self.gate_operation("arm", denial)
        self.assertEqual(armed.returncode, 0, armed.stderr)
        payload = self.payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="concurrent-risk",
            tool_input={"command": "git reset --hard HEAD"},
        )

        def invoke(_: int) -> dict[str, object]:
            result = subprocess.run(
                [sys.executable, str(RUNTIME), "hook", "pre-tool"],
                cwd=str(self.project),
                env=self.env,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(invoke, range(24)))
        allowed = [item for item in results if "hookSpecificOutput" not in item]
        self.assertEqual(len(allowed), 1)
        self.assertEqual(
            len(
                [
                    event
                    for event in self.report_json()["events"]
                    if event["kind"] == "gate-consumed"
                ]
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
