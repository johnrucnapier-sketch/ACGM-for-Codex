from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


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
            "git restore CONSTITUTION.md",
            "git checkout -- CONSTITUTION.md",
            "dd if=/tmp/replacement of=CONSTITUTION.md",
            "acgm-codex export-case abc -o CONSTITUTION.md",
        ):
            with self.subTest(command=command):
                result = self.pre_bash(command)
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.pre_bash("sed -n '1,20p' CONSTITUTION.md"), {})

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

    def test_heartbeat_events_are_limited_to_lifecycle_hooks(self) -> None:
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
            ["session-start", "subagent-start", "pre-compact"],
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
        locator.chmod(0o644)
        report = self.report_json(env=standalone_env)
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["events"][0]["kind"], "hook-heartbeat")
        self.assertEqual(stat.S_IMODE(locator.stat().st_mode), 0o600)

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
            0,
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
