from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: E402
import preflight  # noqa: E402


def command(argv: list[str], cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_release(root: Path, *, tag: str = preflight.TAG) -> Path:
    source = root / "source"
    (source / "hooks").mkdir(parents=True)
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".agents" / "plugins").mkdir(parents=True)
    (source / "VERSION").write_text(preflight.VERSION + "\n", encoding="utf-8")
    (source / "hooks" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    (source / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": preflight.PLUGIN_NAME, "version": preflight.VERSION}) + "\n",
        encoding="utf-8",
    )
    (source / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": preflight.MARKETPLACE_NAME,
                "plugins": [
                    {
                        "name": preflight.PLUGIN_NAME,
                        "source": {
                            "source": "url",
                            "url": preflight.REPOSITORY_URL,
                            "ref": preflight.TAG,
                        },
                        "policy": {
                            "installation": "AVAILABLE",
                            "authentication": "ON_INSTALL",
                        },
                        "category": "Developer Tools",
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (source / "payload.txt").write_text("reviewed bytes\n", encoding="utf-8")
    files = {}
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        name = path.relative_to(source).as_posix()
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (source / preflight.MANIFEST_NAME).write_text(
        json.dumps(
            {"schema_version": 1, "version": preflight.VERSION, "files": files},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    command(["git", "init", "-b", "main"], source)
    command(["git", "config", "user.email", "fixture@example.invalid"], source)
    command(["git", "config", "user.name", "Fixture"], source)
    command(["git", "remote", "add", "origin", preflight.REPOSITORY_URL], source)
    command(["git", "add", "."], source)
    command(["git", "commit", "-m", "fixture"], source)
    command(["git", "tag", tag], source)
    return source


class FakeCodex:
    def __init__(
        self,
        source: Path,
        env: dict[str, str],
        *,
        legacy: bool = False,
        duplicate: bool = False,
        marketplace_conflict: bool = False,
        wrong_version: bool = False,
        state_failure: bool = False,
        cache_tamper: bool = False,
        cache_extra: bool = False,
        marketplace_failure: bool = False,
        plugin_failure: bool = False,
        available_wrong_version: bool = False,
        available_wrong_source: bool = False,
        available_missing: bool = False,
        duplicate_available: bool = False,
    ) -> None:
        self.source = source
        self.env = env
        self.legacy = legacy
        self.duplicate = duplicate
        self.marketplace_conflict = marketplace_conflict
        self.wrong_version = wrong_version
        self.state_failure = state_failure
        self.cache_tamper = cache_tamper
        self.cache_extra = cache_extra
        self.available_wrong_version = available_wrong_version
        self.available_wrong_source = available_wrong_source
        self.available_missing = available_missing
        self.duplicate_available = duplicate_available
        self.marketplace = bool(
            marketplace_conflict
            or wrong_version
            or available_wrong_version
            or available_wrong_source
            or available_missing
            or duplicate_available
        )
        self.installed = False
        if wrong_version:
            self.installed = True
        self.marketplace_failure = marketplace_failure
        self.plugin_failure = plugin_failure
        self.mutations: list[list[str]] = []
        self.codex_cwds: list[Path] = []
        self.codex_cwds_safe: list[bool] = []

    def __call__(
        self, argv: list[str] | tuple[str, ...], cwd: Path | None, env: dict[str, str], timeout: int
    ) -> preflight.CommandResult:
        args = list(argv)
        if args[0] == "git":
            return preflight.run_command(args, cwd, env, timeout)
        if cwd is not None:
            self.codex_cwds.append(cwd)
            self.codex_cwds_safe.append(preflight.neutral_cwd_is_safe(cwd))
        if args[-1:] == ["--help"]:
            if args[1:4] == ["plugin", "marketplace", "add"]:
                return preflight.CommandResult(0, "--ref --json")
            if args[1:3] == ["plugin", "add"]:
                return preflight.CommandResult(0, "--json")
            if args[1:3] == ["plugin", "list"]:
                return preflight.CommandResult(0, "--available --json")
        if args == ["codex", "plugin", "marketplace", "list", "--json"]:
            if self.state_failure:
                return preflight.CommandResult(0, "not-json")
            marketplaces = []
            if self.marketplace:
                marketplaces.append(
                    {
                        "name": preflight.MARKETPLACE_NAME,
                        "marketplaceSource": {
                            "sourceType": "git",
                            "source": "https://github.com/unknown/source.git"
                            if self.marketplace_conflict
                            else preflight.REPOSITORY_URL,
                            "ref": "main" if self.marketplace_conflict else preflight.TAG,
                        },
                    }
                )
            return preflight.CommandResult(0, json.dumps({"marketplaces": marketplaces}))
        if args == ["codex", "plugin", "list", "--available", "--json"]:
            if self.state_failure:
                return preflight.CommandResult(0, "[]")
            installed = []
            available = []
            source = {
                "source": "url",
                "url": preflight.REPOSITORY_URL,
                "ref": preflight.TAG,
            }
            if self.legacy:
                installed.append(
                    {
                        "pluginId": preflight.LEGACY_PLUGIN_ID,
                        "name": preflight.PLUGIN_NAME,
                        "version": "0.1.0-rc.1",
                        "installed": True,
                        "enabled": True,
                        "source": {"source": "local", "path": "/legacy"},
                    }
                )
            if self.duplicate:
                installed.append(
                    {
                        "pluginId": "acgm-codex@other",
                        "name": preflight.PLUGIN_NAME,
                        "version": preflight.VERSION,
                        "installed": True,
                        "enabled": True,
                        "source": source,
                    }
                )
            if self.installed:
                installed.append(
                    {
                        "pluginId": preflight.PLUGIN_ID,
                        "name": preflight.PLUGIN_NAME,
                        "version": "9.9.9" if self.wrong_version else preflight.VERSION,
                        "installed": True,
                        "enabled": True,
                        "source": source,
                    }
                )
            elif self.marketplace and not self.available_missing:
                available.append(
                    {
                        "pluginId": preflight.PLUGIN_ID,
                        "name": preflight.PLUGIN_NAME,
                        "version": "9.9.9" if self.available_wrong_version else preflight.VERSION,
                        "installed": False,
                        "enabled": False,
                        "source": (
                            {
                                "source": "url",
                                "url": "https://github.com/unknown/source.git",
                                "ref": "main",
                            }
                            if self.available_wrong_source
                            else source
                        ),
                    }
                )
                if self.duplicate_available:
                    available.append(dict(available[-1]))
            return preflight.CommandResult(
                0, json.dumps({"installed": installed, "available": available})
            )
        if args == bootstrap.MARKETPLACE_ADD:
            self.mutations.append(args)
            if self.marketplace_failure:
                return preflight.CommandResult(7, stderr="fixture failure")
            self.marketplace = True
            return preflight.CommandResult(0, "{}")
        if args == bootstrap.PLUGIN_ADD:
            self.mutations.append(args)
            if self.plugin_failure:
                return preflight.CommandResult(8, stderr="fixture failure")
            self.installed = True
            cache = (
                Path(self.env["CODEX_HOME"])
                / "plugins"
                / "cache"
                / preflight.MARKETPLACE_NAME
                / preflight.PLUGIN_NAME
                / preflight.VERSION
            )
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.source, cache, ignore=shutil.ignore_patterns(".git"))
            if self.cache_tamper:
                (cache / "payload.txt").write_text("tampered cache\n", encoding="utf-8")
            if self.cache_extra:
                (cache / "skills" / "rogue").mkdir(parents=True)
                (cache / "skills" / "rogue" / "SKILL.md").write_text(
                    "unlisted cache file\n", encoding="utf-8"
                )
            return preflight.CommandResult(0, "{}")
        return preflight.CommandResult(127, stderr="unexpected fake command")


class BootstrapTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, str]]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        source = make_release(root)
        env = os.environ.copy()
        env["HOME"] = str(root / "home")
        env["CODEX_HOME"] = str(root / "codex-home")
        return temp, source, env

    def test_fresh_preflight_and_dry_run_do_not_mutate(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            before = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(before["status"], "READY_FOR_INSTALL")
            result = bootstrap.execute(
                source, dry_run=True, authorized=False, env=env, runner=fake
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "DRY_RUN_PLAN_READY")
            self.assertEqual(fake.mutations, [])
            self.assertEqual(result["plan"][0]["argv"], bootstrap.MARKETPLACE_ADD)
            self.assertTrue(fake.codex_cwds)
            for cwd in fake.codex_cwds:
                self.assertFalse(cwd == source or source in cwd.parents)

    def test_repo_local_marketplace_cannot_appear_as_configured_user_marketplace(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            self.assertTrue((source / ".agents" / "plugins" / "marketplace.json").is_file())
            fake = FakeCodex(source, env)
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(result["codex"]["marketplace"], "ABSENT")
            self.assertEqual(result["status"], "READY_FOR_INSTALL")
            self.assertTrue(fake.codex_cwds)
            self.assertTrue(all(fake.codex_cwds_safe))

    def test_authorization_required_before_any_mutation(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            result = bootstrap.execute(
                source, dry_run=False, authorized=False, env=env, runner=fake
            )
            self.assertEqual(result["status"], "AUTHORIZATION_REQUIRED")
            self.assertEqual(fake.mutations, [])

    def test_fresh_install_verifies_cache_and_is_idempotent(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            result = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "INSTALLED_ENABLED_PENDING_HOOK_TRUST")
            self.assertEqual(fake.mutations, [bootstrap.MARKETPLACE_ADD, bootstrap.PLUGIN_ADD])
            self.assertEqual(result["lifecycle"]["package_bytes"], "VERIFIED")
            self.assertEqual(result["claims"]["hook_trusted"], False)
            self.assertEqual(
                [action["id"] for action in result["next_actions"]],
                [
                    "start_discovery_task",
                    "review_hook_hash",
                    "start_verification_task",
                ],
            )
            again = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )
            self.assertTrue(again["idempotent"])
            self.assertEqual(fake.mutations, [bootstrap.MARKETPLACE_ADD, bootstrap.PLUGIN_ADD])

    def test_legacy_personal_and_duplicate_are_fail_closed(self) -> None:
        for field in ("legacy", "duplicate"):
            with self.subTest(field=field):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env, **{field: True})
                    result = bootstrap.execute(
                        source, dry_run=False, authorized=True, env=env, runner=fake
                    )
                    self.assertEqual(result["status"], "MIGRATION_REQUIRED")
                    self.assertFalse(result["migration_plan"]["executable"])
                    self.assertFalse(result["migration_plan"]["automatic_data_adoption"])
                    self.assertEqual(fake.mutations, [])

    def test_unknown_marketplace_wrong_version_and_state_json_fail_closed(self) -> None:
        for kwargs, expected in (
            ({"marketplace_conflict": True}, "MIGRATION_REQUIRED"),
            ({"wrong_version": True}, "MIGRATION_REQUIRED"),
            ({"state_failure": True}, "BLOCKED"),
        ):
            with self.subTest(kwargs=kwargs):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env, **kwargs)
                    result = bootstrap.execute(
                        source, dry_run=False, authorized=True, env=env, runner=fake
                    )
                    self.assertEqual(result["status"], expected)
                    self.assertEqual(fake.mutations, [])

    def test_tampered_cache_is_partial_not_installed_claim(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env, cache_tamper=True)
            result = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )
            self.assertFalse(result["ok"])
            self.assertTrue(result["partial"])
            self.assertEqual(
                result["status"], "INSTALL_COMMANDS_FINISHED_BUT_VERIFICATION_FAILED"
            )
            self.assertEqual(result["lifecycle"]["package_bytes"], "NOT_VERIFIED")

    def test_extra_cache_file_is_partial_not_installed_claim(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env, cache_extra=True)
            result = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["status"], "INSTALL_COMMANDS_FINISHED_BUT_VERIFICATION_FAILED"
            )
            self.assertIn(
                "package_manifest_filesystem_inventory_mismatch",
                result["postflight"]["codex"]["cache_check"]["error_codes"],
            )

    def test_installed_plugin_without_marketplace_is_not_complete(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            installed = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )
            self.assertTrue(installed["ok"])
            fake.marketplace = False
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertNotEqual(result["status"], "INSTALLED_ENABLED_PENDING_HOOK_TRUST")
            self.assertIn(
                "installed_plugin_marketplace_missing_or_not_exact",
                result["error_codes"],
            )

    def test_invalid_or_missing_available_plugin_blocks_add(self) -> None:
        for kwargs in (
            {"available_wrong_version": True},
            {"available_wrong_source": True},
            {"available_missing": True},
            {"duplicate_available": True},
        ):
            with self.subTest(kwargs=kwargs):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env, **kwargs)
                    result = bootstrap.execute(
                        source, dry_run=False, authorized=True, env=env, runner=fake
                    )
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertEqual(fake.mutations, [])

    def test_cli_failures_report_partial_state_without_rollback_claim(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env, marketplace_failure=True)
            result = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )
            self.assertTrue(result["partial"])
            self.assertEqual(result["status"], "MARKETPLACE_ADD_FAILED_STATE_REQUIRES_RECHECK")
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env, plugin_failure=True)
            result = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )
            self.assertTrue(result["partial"])
            self.assertEqual(result["status"], "PLUGIN_ADD_FAILED_MARKETPLACE_MAY_REMAIN")
            self.assertTrue(fake.marketplace)
            self.assertFalse(fake.installed)

    def test_windows_is_blocked_even_if_codex_plugin_cli_exists(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            result = preflight.evaluate(
                source, env=env, runner=fake, platform_name="Windows"
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["platform"]["windows_runtime_supported"])
            legacy = FakeCodex(source, env, legacy=True)
            result = preflight.evaluate(
                source, env=env, runner=legacy, platform_name="Windows"
            )
            self.assertEqual(result["status"], "BLOCKED")

    def test_source_tag_and_manifest_fail_closed(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            (source / "payload.txt").write_text("tampered\n", encoding="utf-8")
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("package_file_digest_mismatch", result["error_codes"])


if __name__ == "__main__":
    unittest.main()
