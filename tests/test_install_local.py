from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts" / "install_local.py"
sys.path.insert(0, str(ROOT))
from scripts import install_local  # noqa: E402


class LocalInstallerTests(unittest.TestCase):
    def make_valid_source(self, root: Path, *, version: str = "1.2.3") -> Path:
        source = root / "source"
        for relative_name in install_local.PUBLISHED_FILES:
            path = source / relative_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"published: {relative_name}\n", encoding="utf-8")
        (source / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "acgm-codex", "version": version}) + "\n",
            encoding="utf-8",
        )
        (source / "VERSION").write_text(version + "\n", encoding="utf-8")
        (source / "pyproject.toml").write_text(
            f'[project]\nname = "acgm-codex"\nversion = "{version}"\n',
            encoding="utf-8",
        )
        return source

    def run_installer(self, home: Path, *extra: str) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                "--home",
                str(home),
                "--no-plugin-add",
                "--json",
                *extra,
            ],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return json.loads(result.stdout)

    def test_installs_snapshot_marketplace_and_cli_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as raw_home:
            home = Path(raw_home)
            first = self.run_installer(home)
            second = self.run_installer(home)

            plugin = home / "plugins" / "acgm-codex"
            self.assertEqual(Path(first["personal_source"]).resolve(), plugin.resolve())
            self.assertEqual(second["marketplace"], "personal")
            self.assertTrue((plugin / ".codex-plugin" / "plugin.json").is_file())
            self.assertFalse((plugin / ".git").exists())

            marketplace = json.loads(
                (home / ".agents" / "plugins" / "marketplace.json").read_text()
            )
            entries = [item for item in marketplace["plugins"] if item["name"] == "acgm-codex"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["source"]["path"], "./plugins/acgm-codex")

            wrapper = home / ".local" / "bin" / "acgm-codex"
            self.assertTrue(wrapper.is_file())
            self.assertTrue(wrapper.stat().st_mode & 0o111)
            self.assertIn(str(plugin / "bin" / "acgm-codex"), wrapper.read_text())

    def test_snapshot_uses_exact_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            source = self.make_valid_source(root)
            destination = root / "installed"

            private_paths = (
                ".env",
                ".git/config",
                ".acgm/events.jsonl",
                ".venv/bin/python",
                "build/package.bin",
                "dist/archive.zip",
                "private-notes.md",
                "scripts/private_untracked.py",
                "skills/activity-report/private_untracked.md",
            )
            for relative_name in private_paths:
                path = source / relative_name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private\n", encoding="utf-8")

            install_local.install_snapshot(source, destination, force=False)

            for relative_name in install_local.PUBLISHED_FILES:
                with self.subTest(published=relative_name):
                    self.assertTrue((destination / relative_name).is_file())
            for relative_name in private_paths:
                with self.subTest(private=relative_name):
                    self.assertFalse((destination / relative_name).exists())

    def test_snapshot_rejects_symlink_in_published_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            source = self.make_valid_source(root)
            destination = root / "installed"
            secret = root / "secret.txt"
            secret.write_text("do not publish\n", encoding="utf-8")
            readme = source / "README.md"
            readme.unlink()
            readme.symlink_to(secret)

            with self.assertRaisesRegex(ValueError, "refusing symlink"):
                install_local.install_snapshot(source, destination, force=False)

            self.assertFalse(destination.exists())

    def test_cli_wrapper_replaces_symlink_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            home = root / "home"
            plugin = root / "plugin"
            target = root / "valuable.txt"
            target.write_text("keep me\n", encoding="utf-8")
            wrapper = home / ".local" / "bin" / "acgm-codex"
            wrapper.parent.mkdir(parents=True)
            wrapper.symlink_to(target)

            result = install_local.install_cli_wrapper(home, plugin)

            self.assertEqual(result, wrapper)
            self.assertFalse(wrapper.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "keep me\n")
            self.assertIn(str(plugin / "bin" / "acgm-codex"), wrapper.read_text())
            self.assertTrue(wrapper.stat().st_mode & 0o111)

    def test_cli_wrapper_refuses_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            home = root / "home"
            wrapper = home / ".local" / "bin" / "acgm-codex"
            wrapper.mkdir(parents=True)

            with self.assertRaisesRegex(IsADirectoryError, "wrapper directory"):
                install_local.install_cli_wrapper(home, root / "plugin")

            self.assertTrue(wrapper.is_dir())

    def test_validate_source_requires_all_versions_to_match(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            source = self.make_valid_source(root)
            self.assertEqual(install_local.validate_source(source), "1.2.3")

            cases = {
                "manifest": (
                    source / ".codex-plugin" / "plugin.json",
                    '{"name":"acgm-codex","version":"9.9.9"}\n',
                ),
                "VERSION": (source / "VERSION", "9.9.9\n"),
                "pyproject": (
                    source / "pyproject.toml",
                    '[project]\nname = "acgm-codex"\nversion = "9.9.9"\n',
                ),
            }
            for name, (path, replacement) in cases.items():
                with self.subTest(name=name):
                    source = self.make_valid_source(root)
                    path = source / path.relative_to(root / "source")
                    path.write_text(replacement, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "version mismatch"):
                        install_local.validate_source(source)

    def test_transaction_restores_existing_state_after_codex_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            source = self.make_valid_source(root)
            home = root / "home"
            destination = home / "plugins" / "acgm-codex"
            manifest = destination / ".codex-plugin" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                '{"name":"acgm-codex","version":"0.0.1"}\n',
                encoding="utf-8",
            )
            marker = destination / "old-state.txt"
            marker.write_text("old plugin\n", encoding="utf-8")

            marketplace = home / ".agents" / "plugins" / "marketplace.json"
            marketplace.parent.mkdir(parents=True)
            old_marketplace = (
                '{"name":"personal","plugins":[{"name":"other-plugin"}]}\n'
            )
            marketplace.write_text(old_marketplace, encoding="utf-8")

            wrapper = home / ".local" / "bin" / "acgm-codex"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("old wrapper\n", encoding="utf-8")
            wrapper.chmod(0o700)

            with mock.patch.object(
                install_local,
                "run_codex_install",
                side_effect=RuntimeError("simulated cache failure"),
            ):
                with self.assertRaisesRegex(
                    install_local.InstallTransactionError,
                    "prior personal source.*was restored",
                ):
                    install_local.perform_install(
                        source,
                        home,
                        force=False,
                        refresh_cache=True,
                    )

            self.assertEqual(marker.read_text(encoding="utf-8"), "old plugin\n")
            self.assertFalse((destination / "README.md").exists())
            self.assertEqual(marketplace.read_text(encoding="utf-8"), old_marketplace)
            self.assertEqual(wrapper.read_text(encoding="utf-8"), "old wrapper\n")
            self.assertEqual(wrapper.stat().st_mode & 0o777, 0o700)

    def test_transaction_removes_new_paths_after_codex_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            source = self.make_valid_source(root)
            home = root / "home"

            with mock.patch.object(
                install_local,
                "run_codex_install",
                side_effect=RuntimeError("simulated cache failure"),
            ):
                with self.assertRaises(install_local.InstallTransactionError):
                    install_local.perform_install(
                        source,
                        home,
                        force=False,
                        refresh_cache=True,
                    )

            self.assertFalse((home / "plugins" / "acgm-codex").exists())
            self.assertFalse(
                (home / ".agents" / "plugins" / "marketplace.json").exists()
            )
            self.assertFalse((home / ".local" / "bin" / "acgm-codex").exists())

    def test_transaction_reports_incomplete_rollback_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            source = self.make_valid_source(root)
            home = root / "home"

            with mock.patch.object(
                install_local,
                "run_codex_install",
                side_effect=RuntimeError("simulated cache failure"),
            ), mock.patch.object(
                install_local,
                "_restore_path",
                side_effect=OSError("simulated restore failure"),
            ):
                with self.assertRaisesRegex(
                    install_local.InstallTransactionError,
                    "rollback was incomplete.*partial install state may remain",
                ):
                    install_local.perform_install(
                        source,
                        home,
                        force=False,
                        refresh_cache=True,
                    )

    def test_refuses_unrelated_destination_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as raw_home:
            home = Path(raw_home)
            destination = home / "plugins" / "acgm-codex"
            (destination / ".codex-plugin").mkdir(parents=True)
            (destination / ".codex-plugin" / "plugin.json").write_text(
                '{"name":"something-else","version":"1.0.0"}\n'
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--home",
                    str(home),
                    "--no-plugin-add",
                ],
                cwd=ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to replace", result.stderr)


if __name__ == "__main__":
    unittest.main()
