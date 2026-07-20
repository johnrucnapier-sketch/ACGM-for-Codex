from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: E402
import preflight  # noqa: E402


_UNSET = object()


def command(argv: list[str], cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def revision_for(root: Path, tag: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"],
        cwd=root,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def write_codex_marketplace_metadata(
    root: Path, tag: str, *, overrides: dict[str, object] | None = None
) -> None:
    payload: dict[str, object] = {
        "source_type": "git",
        "source": preflight.REPOSITORY_URL,
        "ref_name": tag,
        "sparse_paths": [],
        "revision": revision_for(root, tag),
    }
    payload.update(overrides or {})
    (root / preflight.CODEX_MARKETPLACE_METADATA).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def make_release(
    root: Path,
    *,
    version: str = preflight.VERSION,
    tag: str | None = None,
) -> Path:
    tag = tag or f"v{version}"
    source = root / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "scripts").mkdir(parents=True)
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".agents" / "plugins").mkdir(parents=True)
    (source / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.venv/\nbuild/\ndist/\n",
        encoding="utf-8",
    )
    (source / "VERSION").write_text(version + "\n", encoding="utf-8")
    (source / "hooks" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    (source / "scripts" / "acgm_codex.py").write_text(
        f'VERSION = "{version}"\n', encoding="utf-8"
    )
    (source / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": preflight.PLUGIN_NAME, "version": version}) + "\n",
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
                            "ref": tag,
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
            {"schema_version": 1, "version": version, "files": files},
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


def authorized_execute(
    source: Path,
    *,
    env: dict[str, str],
    runner: preflight.Runner,
) -> dict[str, object]:
    """Bind every mutating fixture run to its immediately preceding plan."""

    prepared = bootstrap.execute(
        source,
        dry_run=True,
        authorized=False,
        env=env,
        runner=runner,
    )
    return bootstrap.execute(
        source,
        dry_run=False,
        authorized=True,
        expected_plan_digest=str(prepared["install_plan_digest"]),
        env=env,
        runner=runner,
    )


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
        cache_pyc: bool = False,
        cache_ignored_executable: bool = False,
        marketplace_failure: bool = False,
        plugin_failure: bool = False,
        available_wrong_version: bool = False,
        available_null_version: bool = False,
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
        self.cache_pyc = cache_pyc
        self.cache_ignored_executable = cache_ignored_executable
        self.available_wrong_version = available_wrong_version
        self.available_null_version = available_null_version
        self.available_wrong_source = available_wrong_source
        self.available_missing = available_missing
        self.duplicate_available = duplicate_available
        self.marketplace = bool(
            marketplace_conflict
            or wrong_version
            or available_wrong_version
            or available_null_version
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
        self.codex_homes: list[str | None] = []
        if self.marketplace:
            self.add_marketplace()

    @property
    def codex_home(self) -> Path:
        return Path(self.env["CODEX_HOME"])

    @property
    def marketplace_root(self) -> Path:
        return self.codex_home / ".tmp" / "marketplaces" / preflight.MARKETPLACE_NAME

    def _write_config(self) -> None:
        lines: list[str] = []
        if self.installed:
            lines.extend(
                [
                    f'[plugins."{preflight.PLUGIN_ID}"]',
                    "enabled = true",
                    "",
                ]
            )
        source = (
            "https://github.com/unknown/source.git"
            if self.marketplace_conflict
            else preflight.REPOSITORY_URL
        )
        ref = "main" if self.marketplace_conflict else preflight.TAG
        lines.extend(
            [
                f"[marketplaces.{preflight.MARKETPLACE_NAME}]",
                'source_type = "git"',
                f'source = "{source}"',
                f'ref = "{ref}"',
                "",
            ]
        )
        self.codex_home.mkdir(parents=True, exist_ok=True)
        (self.codex_home / "config.toml").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    def add_marketplace(self) -> None:
        self.marketplace_root.parent.mkdir(parents=True, exist_ok=True)
        if self.marketplace_root.exists():
            shutil.rmtree(self.marketplace_root)
        shutil.copytree(self.source, self.marketplace_root)
        write_codex_marketplace_metadata(self.marketplace_root, preflight.TAG)
        self._write_config()
        self.marketplace = True

    def __call__(
        self, argv: list[str] | tuple[str, ...], cwd: Path | None, env: dict[str, str], timeout: int
    ) -> preflight.CommandResult:
        args = list(argv)
        if args[0] == "git":
            return preflight.run_command(args, cwd, env, timeout)
        self.codex_homes.append(env.get("CODEX_HOME"))
        if cwd is not None:
            self.codex_cwds.append(cwd)
            self.codex_cwds_safe.append(preflight.neutral_cwd_is_safe(cwd))
        if args[-1:] == ["--help"]:
            if args[1:4] == ["plugin", "marketplace", "add"]:
                return preflight.CommandResult(0, "--ref --json")
            if args[1:4] == ["plugin", "marketplace", "remove"]:
                return preflight.CommandResult(0, "--json")
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
                        "root": str(self.marketplace_root),
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
                        "installPolicy": "AVAILABLE",
                        "authPolicy": "ON_INSTALL",
                        "source": source,
                    }
                )
            if self.installed:
                installed.append(
                    {
                        "pluginId": preflight.PLUGIN_ID,
                        "name": preflight.PLUGIN_NAME,
                        "marketplaceName": preflight.MARKETPLACE_NAME,
                        "version": "9.9.9" if self.wrong_version else preflight.VERSION,
                        "installed": True,
                        "enabled": True,
                        "installPolicy": "AVAILABLE",
                        "authPolicy": "ON_INSTALL",
                        "source": source,
                    }
                )
            elif self.marketplace and not self.available_missing:
                available.append(
                    {
                        "pluginId": preflight.PLUGIN_ID,
                        "name": preflight.PLUGIN_NAME,
                        "marketplaceName": preflight.MARKETPLACE_NAME,
                        "version": (
                            None
                            if self.available_null_version
                            else "9.9.9"
                            if self.available_wrong_version
                            else preflight.VERSION
                        ),
                        "installed": False,
                        "enabled": False,
                        "installPolicy": "AVAILABLE",
                        "authPolicy": "ON_INSTALL",
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
            self.add_marketplace()
            return preflight.CommandResult(0, "{}")
        if args == bootstrap.PLUGIN_ADD:
            self.mutations.append(args)
            if self.plugin_failure:
                return preflight.CommandResult(8, stderr="fixture failure")
            self.installed = True
            self._write_config()
            cache = (
                Path(self.env["CODEX_HOME"])
                / "plugins"
                / "cache"
                / preflight.MARKETPLACE_NAME
                / preflight.PLUGIN_NAME
                / preflight.VERSION
            )
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.source, cache)
            if self.cache_tamper:
                (cache / "payload.txt").write_text("tampered cache\n", encoding="utf-8")
            if self.cache_extra:
                (cache / "skills" / "rogue").mkdir(parents=True)
                (cache / "skills" / "rogue" / "SKILL.md").write_text(
                    "unlisted cache file\n", encoding="utf-8"
                )
            if self.cache_pyc:
                (cache / "__pycache__").mkdir(parents=True)
                (cache / "__pycache__" / "rogue.cpython-310.pyc").write_bytes(
                    b"unlisted bytecode\n"
                )
            if self.cache_ignored_executable:
                executable = cache / ".venv" / "bin" / "rogue-runtime"
                executable.parent.mkdir(parents=True)
                executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                executable.chmod(0o755)
            return preflight.CommandResult(0, "{}")
        return preflight.CommandResult(127, stderr="unexpected fake command")


class ObservedCodex0144:
    """Reproduce the marketplace/plugin JSON observed from Codex CLI 0.144.

    The marketplace list omits ``ref`` and the plugin list does not enumerate an
    uninstalled available plugin.  After installation, the source kind is
    reported as ``git``.  Config and cached Git/package evidence carry the
    omitted release-ref proof.
    """

    def __init__(self, source: Path, env: dict[str, str]) -> None:
        self.source = source
        self.env = env
        self.marketplace = False
        self.installed = False
        self.installed_name = preflight.PLUGIN_NAME
        self.enumerate_available = False
        self.enumerated_available_version: object = None
        self.omit_available_version = False
        self.plugin_payload_override: dict[str, object] | None = None
        self.mutations: list[list[str]] = []

    @property
    def codex_home(self) -> Path:
        return Path(self.env["CODEX_HOME"])

    @property
    def marketplace_root(self) -> Path:
        return self.codex_home / ".tmp" / "marketplaces" / preflight.MARKETPLACE_NAME

    def add_marketplace(self) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        self.marketplace_root.parent.mkdir(parents=True, exist_ok=True)
        if self.marketplace_root.exists():
            shutil.rmtree(self.marketplace_root)
        shutil.copytree(self.source, self.marketplace_root)
        write_codex_marketplace_metadata(self.marketplace_root, preflight.TAG)
        (self.codex_home / "config.toml").write_text(
            "\n".join(
                [
                    f"[marketplaces.{preflight.MARKETPLACE_NAME}]",
                    'last_updated = "2026-07-15T00:00:00Z"',
                    'source_type = "git"',
                    f'source = "{preflight.REPOSITORY_URL}"',
                    f'ref = "{preflight.TAG}"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.marketplace = True

    def add_plugin(self) -> None:
        cache = (
            self.codex_home
            / "plugins"
            / "cache"
            / preflight.MARKETPLACE_NAME
            / preflight.PLUGIN_NAME
            / preflight.VERSION
        )
        cache.parent.mkdir(parents=True, exist_ok=True)
        if cache.exists():
            shutil.rmtree(cache)
        shutil.copytree(self.source, cache)
        self.installed = True
        config = self.codex_home / "config.toml"
        config.write_text(
            "\n".join(
                [
                    f'[plugins."{preflight.PLUGIN_ID}"]',
                    "enabled = true",
                    "",
                ]
            )
            + config.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def __call__(
        self, argv: list[str] | tuple[str, ...], cwd: Path | None, env: dict[str, str], timeout: int
    ) -> preflight.CommandResult:
        args = list(argv)
        if args[0] == "git":
            return preflight.run_command(args, cwd, env, timeout)
        if args[-1:] == ["--help"]:
            if args[1:4] == ["plugin", "marketplace", "add"]:
                return preflight.CommandResult(0, "--ref --json")
            if args[1:4] == ["plugin", "marketplace", "remove"]:
                return preflight.CommandResult(0, "--json")
            if args[1:3] == ["plugin", "add"]:
                return preflight.CommandResult(0, "--json")
            if args[1:3] == ["plugin", "list"]:
                return preflight.CommandResult(0, "--available --json")
        if args == ["codex", "plugin", "marketplace", "list", "--json"]:
            marketplaces = []
            if self.marketplace:
                marketplaces.append(
                    {
                        "name": preflight.MARKETPLACE_NAME,
                        "root": str(self.marketplace_root),
                        "marketplaceSource": {
                            "sourceType": "git",
                            "source": preflight.REPOSITORY_URL,
                        },
                    }
                )
            return preflight.CommandResult(0, json.dumps({"marketplaces": marketplaces}))
        if args == ["codex", "plugin", "list", "--available", "--json"]:
            if self.plugin_payload_override is not None:
                return preflight.CommandResult(
                    0, json.dumps(self.plugin_payload_override)
                )
            installed = []
            available = []
            if self.installed:
                installed.append(
                    {
                        "pluginId": preflight.PLUGIN_ID,
                        "name": self.installed_name,
                        "marketplaceName": preflight.MARKETPLACE_NAME,
                        "version": preflight.VERSION,
                        "installed": True,
                        "enabled": True,
                        "installPolicy": "AVAILABLE",
                        "authPolicy": "ON_INSTALL",
                        "source": {
                            "source": "git",
                            "url": preflight.REPOSITORY_URL,
                            "ref": preflight.TAG,
                        },
                    }
                )
            elif self.marketplace and self.enumerate_available:
                available_item: dict[str, object] = {
                    "pluginId": preflight.PLUGIN_ID,
                    "name": preflight.PLUGIN_NAME,
                    "marketplaceName": preflight.MARKETPLACE_NAME,
                    "installed": False,
                    "enabled": False,
                    "installPolicy": "AVAILABLE",
                    "authPolicy": "ON_INSTALL",
                    "source": {
                        "source": "git",
                        "url": preflight.REPOSITORY_URL,
                        "ref": preflight.TAG,
                    },
                }
                if not self.omit_available_version:
                    available_item["version"] = self.enumerated_available_version
                available.append(available_item)
            return preflight.CommandResult(
                0, json.dumps({"installed": installed, "available": available})
            )
        if args == bootstrap.MARKETPLACE_ADD:
            self.mutations.append(args)
            self.add_marketplace()
            return preflight.CommandResult(0, "{}")
        if args == bootstrap.PLUGIN_ADD:
            self.mutations.append(args)
            self.add_plugin()
            return preflight.CommandResult(0, "{}")
        return preflight.CommandResult(127, stderr="unexpected observed command")


class OfficialUpgradeCodex:
    """Model the observed 0.144 official remove/add/add upgrade sequence."""

    def __init__(
        self,
        current_source: Path,
        old_source: Path,
        env: dict[str, str],
        *,
        old_version: str = "0.1.0-rc.4",
        report_marketplace_ref: bool = False,
        remove_failure: bool = False,
        add_failure: bool = False,
        plugin_failure: bool = False,
        remove_no_effect: bool = False,
        retain_old_cache: bool = False,
        reassociate_on_add: bool = False,
        transition_wrong_ref: bool = False,
        transition_cache_tamper: bool = False,
        transition_scope_override: object = _UNSET,
        transition_wrong_policy: bool = False,
        transition_wrong_source: bool = False,
        transition_duplicate: bool = False,
    ) -> None:
        self.current_source = current_source
        self.old_source = old_source
        self.env = env
        self.old_version = old_version
        self.old_ref = f"v{old_version}"
        self.report_marketplace_ref = report_marketplace_ref
        self.remove_failure = remove_failure
        self.add_failure = add_failure
        self.plugin_failure = plugin_failure
        self.remove_no_effect = remove_no_effect
        self.retain_old_cache = retain_old_cache
        self.reassociate_on_add = reassociate_on_add
        self.transition_wrong_ref = transition_wrong_ref
        self.transition_cache_tamper = transition_cache_tamper
        self.transition_scope_override = transition_scope_override
        self.transition_wrong_policy = transition_wrong_policy
        self.transition_wrong_source = transition_wrong_source
        self.transition_duplicate = transition_duplicate
        self.transition_phase_active = False
        self.detached_installed_version: str | None = None
        self.marketplace_phase = "old"
        self.marketplace_ref: str | None = self.old_ref
        self.installed_version: str | None = old_version
        self.installed_ref: str | None = self.old_ref
        self.installed_scope: object = "user"
        self.omit_installed_scope = False
        self.installed_marketplace = preflight.MARKETPLACE_NAME
        self.plugin_source_url = preflight.REPOSITORY_URL
        self.marketplace_source_url = preflight.REPOSITORY_URL
        self.extra_installed: list[dict[str, object]] = []
        self.mutations: list[list[str]] = []
        preflight.KNOWN_OFFICIAL_RELEASES[old_version] = {
            "revision": revision_for(old_source, self.old_ref),
            "manifest_sha256": hashlib.sha256(
                (old_source / preflight.MANIFEST_NAME).read_bytes()
            ).hexdigest(),
        }
        self._install_marketplace_snapshot(old_source, self.old_ref)
        self._install_plugin_cache(old_source, old_version, replace_all=True)

    def set_interrupted_transition(
        self, source: Path, version: str
    ) -> None:
        ref = f"v{version}"
        self.marketplace_phase = "interrupted"
        self.marketplace_ref = ref
        self._install_marketplace_snapshot(source, ref)
        self.installed_ref = ref

    @property
    def codex_home(self) -> Path:
        return Path(self.env["CODEX_HOME"])

    @property
    def marketplace_root(self) -> Path:
        return self.codex_home / ".tmp" / "marketplaces" / preflight.MARKETPLACE_NAME

    @property
    def cache_root(self) -> Path:
        return (
            self.codex_home
            / "plugins"
            / "cache"
            / preflight.MARKETPLACE_NAME
            / preflight.PLUGIN_NAME
        )

    def _write_config(self, ref: str | None) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        lines = [
            f'[plugins."{preflight.PLUGIN_ID}"]',
            "enabled = true",
            "",
        ]
        if ref is not None:
            lines.extend(
                [
                    f"[marketplaces.{preflight.MARKETPLACE_NAME}]",
                    'source_type = "git"',
                    f'source = "{self.marketplace_source_url}"',
                    f'ref = "{ref}"',
                    "",
                ]
            )
        (self.codex_home / "config.toml").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    def _install_marketplace_snapshot(self, source: Path, ref: str) -> None:
        self.marketplace_root.parent.mkdir(parents=True, exist_ok=True)
        if self.marketplace_root.exists():
            shutil.rmtree(self.marketplace_root)
        shutil.copytree(source, self.marketplace_root)
        write_codex_marketplace_metadata(self.marketplace_root, ref)
        self._write_config(ref)

    def _install_plugin_cache(
        self, source: Path, version: str, *, replace_all: bool
    ) -> None:
        if replace_all and self.cache_root.exists():
            shutil.rmtree(self.cache_root)
        cache = self.cache_root / version
        cache.parent.mkdir(parents=True, exist_ok=True)
        if cache.exists():
            shutil.rmtree(cache)
        shutil.copytree(source, cache)

    def __call__(
        self,
        argv: list[str] | tuple[str, ...],
        cwd: Path | None,
        env: dict[str, str],
        timeout: int,
    ) -> preflight.CommandResult:
        args = list(argv)
        if args[0] == "git":
            return preflight.run_command(args, cwd, env, timeout)
        if args[-1:] == ["--help"]:
            if args[1:4] == ["plugin", "marketplace", "add"]:
                return preflight.CommandResult(0, "--ref --json")
            if args[1:4] == ["plugin", "marketplace", "remove"]:
                return preflight.CommandResult(0, "--json")
            if args[1:3] == ["plugin", "add"]:
                return preflight.CommandResult(0, "--json")
            if args[1:3] == ["plugin", "list"]:
                return preflight.CommandResult(0, "--available --json")
        if args == ["codex", "plugin", "marketplace", "list", "--json"]:
            marketplaces = []
            if self.marketplace_phase != "absent":
                ref = self.marketplace_ref
                source: dict[str, object] = {
                    "sourceType": "git",
                    "source": self.marketplace_source_url,
                }
                if self.report_marketplace_ref:
                    source["ref"] = ref
                marketplaces.append(
                    {
                        "name": preflight.MARKETPLACE_NAME,
                        "root": str(self.marketplace_root),
                        "marketplaceSource": source,
                    }
                )
            return preflight.CommandResult(
                0, json.dumps({"marketplaces": marketplaces})
            )
        if args == ["codex", "plugin", "list", "--available", "--json"]:
            installed: list[dict[str, object]] = list(self.extra_installed)
            available: list[dict[str, object]] = []
            if self.installed_version is not None:
                installed_item: dict[str, object] = {
                    "pluginId": preflight.PLUGIN_ID,
                    "name": preflight.PLUGIN_NAME,
                    "marketplaceName": self.installed_marketplace,
                    "version": self.installed_version,
                    "installed": True,
                    "enabled": True,
                    "installPolicy": "AVAILABLE",
                    "authPolicy": "MANUAL"
                    if self.transition_phase_active
                    and self.transition_wrong_policy
                    else "ON_INSTALL",
                    "source": {
                        "source": "git",
                        "url": self.plugin_source_url,
                        "ref": self.installed_ref,
                    },
                }
                if not self.omit_installed_scope:
                    installed_item["scope"] = self.installed_scope
                installed.append(installed_item)
            elif self.marketplace_phase == "current" and self.report_marketplace_ref:
                available.append(
                    {
                        "pluginId": preflight.PLUGIN_ID,
                        "name": preflight.PLUGIN_NAME,
                        "marketplaceName": preflight.MARKETPLACE_NAME,
                        "version": preflight.VERSION,
                        "installed": False,
                        "enabled": False,
                        "installPolicy": "AVAILABLE",
                        "authPolicy": "ON_INSTALL",
                        "source": {
                            "source": "git",
                            "url": preflight.REPOSITORY_URL,
                            "ref": preflight.TAG,
                        },
                    }
                )
            return preflight.CommandResult(
                0, json.dumps({"installed": installed, "available": available})
            )
        if args == bootstrap.MARKETPLACE_REMOVE:
            self.mutations.append(args)
            if self.remove_failure:
                return preflight.CommandResult(9, stderr="remove failed")
            if not self.remove_no_effect:
                self.marketplace_phase = "absent"
                self.marketplace_ref = None
                self.detached_installed_version = self.installed_version
                self.installed_version = None
                self.installed_ref = None
                # Codex 0.144 keeps enabled=true and the old cache at this point.
                self._write_config(None)
            return preflight.CommandResult(0, "{}")
        if args == bootstrap.MARKETPLACE_ADD:
            self.mutations.append(args)
            if self.add_failure:
                return preflight.CommandResult(10, stderr="add failed")
            self.marketplace_phase = "current"
            self.marketplace_ref = preflight.TAG
            self._install_marketplace_snapshot(self.current_source, preflight.TAG)
            if self.reassociate_on_add:
                self.transition_phase_active = True
                self.installed_version = self.detached_installed_version
                self.installed_ref = (
                    "v0.0.0-rc.1"
                    if self.transition_wrong_ref
                    else preflight.TAG
                )
                if self.transition_cache_tamper and self.installed_version:
                    (
                        self.cache_root
                        / self.installed_version
                        / "payload.txt"
                    ).write_text("tampered transition cache\n", encoding="utf-8")
                if self.transition_scope_override is not _UNSET:
                    self.installed_scope = self.transition_scope_override
                if self.transition_wrong_source:
                    self.plugin_source_url = (
                        "https://github.com/unknown/source.git"
                    )
                if self.transition_duplicate:
                    self.extra_installed.append(
                        {
                            "pluginId": "acgm-codex@other",
                            "name": preflight.PLUGIN_NAME,
                            "version": self.installed_version,
                            "installed": True,
                            "enabled": True,
                            "installPolicy": "AVAILABLE",
                            "authPolicy": "ON_INSTALL",
                            "scope": "user",
                            "source": {
                                "source": "git",
                                "url": preflight.REPOSITORY_URL,
                                "ref": preflight.TAG,
                            },
                        }
                    )
            return preflight.CommandResult(0, "{}")
        if args == bootstrap.PLUGIN_ADD:
            self.mutations.append(args)
            if self.plugin_failure:
                return preflight.CommandResult(11, stderr="plugin add failed")
            self._install_plugin_cache(
                self.current_source,
                preflight.VERSION,
                replace_all=not self.retain_old_cache,
            )
            self.installed_version = preflight.VERSION
            self.installed_ref = preflight.TAG
            return preflight.CommandResult(0, "{}")
        return preflight.CommandResult(127, stderr="unexpected upgrade fake command")


class BootstrapTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, str]]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        source = make_release(root)
        env = os.environ.copy()
        env["HOME"] = str(root / "home")
        env["CODEX_HOME"] = str(root / "codex-home")
        return temp, source, env

    def upgrade_fixture(
        self,
        *,
        old_version: str = "0.1.0-rc.4",
        report_marketplace_ref: bool = False,
        **kwargs: object,
    ) -> tuple[
        tempfile.TemporaryDirectory[str], Path, dict[str, str], OfficialUpgradeCodex
    ]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        source = make_release(root / "current")
        old_source = make_release(root / "old", version=old_version)
        env = os.environ.copy()
        env["HOME"] = str(root / "home")
        env["CODEX_HOME"] = str(root / "codex-home")
        previous_release_identities = dict(preflight.KNOWN_OFFICIAL_RELEASES)
        fake = OfficialUpgradeCodex(
            source,
            old_source,
            env,
            old_version=old_version,
            report_marketplace_ref=report_marketplace_ref,
            **kwargs,
        )

        def restore_release_identities() -> None:
            preflight.KNOWN_OFFICIAL_RELEASES.clear()
            preflight.KNOWN_OFFICIAL_RELEASES.update(previous_release_identities)

        self.addCleanup(restore_release_identities)
        return temp, source, env, fake

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

    def test_authorized_mutation_requires_immediately_prepared_plan_digest(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            prepared = bootstrap.execute(
                source, dry_run=True, authorized=False, env=env, runner=fake
            )
            self.assertEqual(prepared["status"], "DRY_RUN_PLAN_READY")
            self.assertRegex(
                str(prepared["install_plan_digest"]), r"\Asha256:[0-9a-f]{64}\Z"
            )
            self.assertEqual(
                prepared["install_plan_digest"],
                bootstrap._install_plan_digest(prepared["authorization_plan"]),
            )

            result = bootstrap.execute(
                source, dry_run=False, authorized=True, env=env, runner=fake
            )

            self.assertEqual(result["status"], "INSTALL_PLAN_DIGEST_REQUIRED")
            self.assertTrue(result["requires_install_plan_digest"])
            self.assertEqual(result["commands_run"], [])
            self.assertEqual(fake.mutations, [])

            # Digest enforcement is status-bound, not dependent on the action
            # renderer remaining bug-free.  An accidentally empty action list
            # must never reopen a mutation path.
            with mock.patch.object(preflight, "_actions", return_value=[]):
                omitted_plan = bootstrap.execute(
                    source, dry_run=False, authorized=True, env=env, runner=fake
                )
            self.assertEqual(
                omitted_plan["status"], "INSTALL_PLAN_DIGEST_REQUIRED"
            )
            self.assertEqual(fake.mutations, [])

    def test_bootstrap_cli_forwards_plan_digest(self) -> None:
        digest = "sha256:" + "a" * 64
        result = {"ok": False, "status": "INSTALL_PLAN_STALE"}
        with mock.patch.object(bootstrap, "execute", return_value=result) as execute:
            with mock.patch("builtins.print"):
                exit_code = bootstrap.main(
                    ["--authorize-install", "--plan-digest", digest, "--json"]
                )
        self.assertEqual(exit_code, 2)
        self.assertEqual(execute.call_args.kwargs["expected_plan_digest"], digest)

    def test_expected_install_plan_digest_rejects_state_drift_before_command(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            prepared = bootstrap.execute(
                source, dry_run=True, authorized=False, env=env, runner=fake
            )
            self.assertEqual(prepared["status"], "DRY_RUN_PLAN_READY")

            # Simulate another actor installing the verified marketplace after
            # authorization but before bootstrap reaches its first mutation.
            fake.add_marketplace()
            result = bootstrap.execute(
                source,
                dry_run=False,
                authorized=True,
                expected_plan_digest=str(prepared["install_plan_digest"]),
                env=env,
                runner=fake,
            )

            self.assertEqual(result["status"], "INSTALL_PLAN_STALE")
            self.assertEqual(result["commands_run"], [])
            self.assertEqual(fake.mutations, [])
            self.assertNotEqual(
                result["install_plan_digest"], prepared["install_plan_digest"]
            )

    def test_install_digest_binds_exact_codex_home_before_mutation(self) -> None:
        temp, source, first_env = self.fixture()
        with temp:
            first_fake = FakeCodex(source, first_env)
            prepared = bootstrap.execute(
                source,
                dry_run=True,
                authorized=False,
                env=first_env,
                runner=first_fake,
            )
            second_env = dict(first_env)
            second_home = Path(temp.name) / "other-empty-codex-home"
            second_env["CODEX_HOME"] = str(second_home)
            second_fake = FakeCodex(source, second_env)

            result = bootstrap.execute(
                source,
                dry_run=False,
                authorized=True,
                expected_plan_digest=str(prepared["install_plan_digest"]),
                env=second_env,
                runner=second_fake,
            )

            self.assertEqual(result["status"], "INSTALL_PLAN_STALE")
            self.assertEqual(result["commands_run"], [])
            self.assertEqual(second_fake.mutations, [])
            self.assertFalse(second_home.exists())
            self.assertNotEqual(
                result["authorization_plan"]["install_target"],
                prepared["authorization_plan"]["install_target"],
            )
            self.assertNotEqual(
                result["install_plan_digest"], prepared["install_plan_digest"]
            )

    def test_relative_codex_home_is_normalized_for_probe_and_mutation(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            relative = "relative-codex-profile"
            env["CODEX_HOME"] = relative
            fake = FakeCodex(source, env)

            prepared = bootstrap.execute(
                source,
                dry_run=True,
                authorized=False,
                env=env,
                runner=fake,
            )

            expected = str((Path.cwd() / relative).resolve(strict=False))
            self.assertTrue(prepared["ok"])
            self.assertEqual(
                prepared["authorization_plan"]["install_target"]["selector"],
                "CODEX_HOME",
            )
            self.assertTrue(fake.codex_cwds)
            self.assertTrue(fake.codex_homes)
            self.assertEqual(set(fake.codex_homes), {expected})

    def test_tilde_home_default_is_normalized_once(self) -> None:
        normalized = preflight.normalized_codex_environment(
            {"HOME": "~/profile-root"}, base=Path("/ignored-anchor")
        )

        self.assertNotIn("CODEX_HOME", normalized)
        self.assertEqual(
            normalized["HOME"], str(Path.home() / "profile-root")
        )

    def test_source_checkout_may_ignore_local_python_runtime_artifacts(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            generated = source / "__pycache__" / "local.cpython-310.pyc"
            generated.parent.mkdir()
            generated.write_bytes(b"local-only bytecode\n")
            fake = FakeCodex(source, env)

            result = preflight.evaluate(source, env=env, runner=fake)

            self.assertEqual(result["status"], "READY_FOR_INSTALL")
            self.assertTrue(result["source"]["git"]["clean"])
            self.assertTrue(result["source"]["package"]["verified"])

    def test_known_official_upgrade_plan_is_numeric_exact_and_read_only(self) -> None:
        self.assertEqual(
            preflight.KNOWN_OFFICIAL_RELEASES["0.1.0-rc.4"],
            {
                "revision": "06623a95df96b3ced9759e6434d096ab8c66fb5f",
                "manifest_sha256": (
                    "227d52be85d1c6c4104a4018c5a7b4c49f536f54c9365181db3c31edad66cab3"
                ),
            },
        )
        self.assertEqual(
            preflight.KNOWN_OFFICIAL_RELEASES["0.2.0-rc.1"],
            {
                "revision": "ef036b7308af295f61902ee392b452347ffd1c81",
                "manifest_sha256": (
                    "34eac875510513d1a13af9a8da3a9486fbdde35c5949349744174648443c07c3"
                ),
            },
        )
        self.assertLess(
            preflight._rc_version_order("0.1.0-rc.10"),
            preflight._rc_version_order(preflight.VERSION),
        )
        self.assertTrue(
            preflight._known_official_upgrade("0.1.0-rc.4", "v0.1.0-rc.4")
        )
        self.assertFalse(
            preflight._known_official_upgrade("0.1.0-rc.10", "v0.1.0-rc.10")
        )
        self.assertTrue(
            preflight._known_official_upgrade("0.2.0-rc.2", "v0.2.0-rc.2")
        )
        self.assertFalse(
            preflight._known_official_upgrade("0.2.0-rc.3", "v0.2.0-rc.3")
        )

        temp, source, env, fake = self.upgrade_fixture()
        with temp:
            evaluated = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(evaluated["status"], "READY_FOR_OFFICIAL_UPGRADE")
            self.assertEqual(
                evaluated["lifecycle"]["official_upgrade"]["from_version"],
                "0.1.0-rc.4",
            )
            planned = bootstrap.execute(
                source, dry_run=True, authorized=False, env=env, runner=fake
            )
            self.assertTrue(planned["ok"])
            self.assertEqual(planned["status"], "DRY_RUN_PLAN_READY")
            self.assertEqual(
                [action["argv"] for action in planned["plan"]],
                [
                    bootstrap.MARKETPLACE_REMOVE,
                    bootstrap.MARKETPLACE_ADD,
                    bootstrap.PLUGIN_ADD,
                ],
            )
            self.assertEqual(fake.mutations, [])
            unauthorized = bootstrap.execute(
                source, dry_run=False, authorized=False, env=env, runner=fake
            )
            self.assertEqual(unauthorized["status"], "AUTHORIZATION_REQUIRED")
            self.assertEqual(fake.mutations, [])

    def test_present_codex_marketplace_metadata_is_identity_bound(self) -> None:
        cases: list[tuple[str, object]] = [
            ("source", {"source": "https://github.com/unknown/repo.git"}),
            ("ref", {"ref_name": "main"}),
            ("revision", {"revision": "0" * 40}),
            ("sparse", {"sparse_paths": ["skills"]}),
            ("extra_key", {"unexpected": True}),
            ("malformed", "{not-json"),
            ("extra_untracked", None),
            ("symlink", "symlink"),
        ]
        for name, change in cases:
            with self.subTest(case=name):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env)
                    fake.add_marketplace()
                    metadata = (
                        fake.marketplace_root
                        / preflight.CODEX_MARKETPLACE_METADATA
                    )
                    if isinstance(change, dict):
                        write_codex_marketplace_metadata(
                            fake.marketplace_root,
                            preflight.TAG,
                            overrides=change,
                        )
                    elif change == "{not-json":
                        metadata.write_text(str(change), encoding="utf-8")
                    elif change == "symlink":
                        metadata.unlink()
                        metadata.symlink_to(source / "VERSION")
                    else:
                        (fake.marketplace_root / "unexpected.txt").write_text(
                            "not platform metadata\n", encoding="utf-8"
                        )

                    evaluated = preflight.evaluate(source, env=env, runner=fake)

                    self.assertIn(
                        evaluated["status"], {"BLOCKED", "MIGRATION_REQUIRED"}
                    )
                    evidence = evaluated["codex"]["marketplace_runtime_evidence"]
                    self.assertIsNotNone(evidence)
                    self.assertFalse(evidence["verified"])
                    self.assertFalse(
                        evaluated["codex"]["official_upgrade"]["eligible"]
                    )

    def test_absent_codex_marketplace_metadata_accepts_exact_clean_checkout(
        self,
    ) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            fake.add_marketplace()
            metadata = fake.marketplace_root / preflight.CODEX_MARKETPLACE_METADATA
            metadata.unlink()

            evaluated = preflight.evaluate(source, env=env, runner=fake)

            self.assertEqual(evaluated["status"], "READY_FOR_PLUGIN_ADD")
            evidence = evaluated["codex"]["marketplace_runtime_evidence"]
            self.assertTrue(evidence["verified"])
            self.assertTrue(evidence["git_verified"])
            self.assertTrue(evidence["package_verified"])

    def test_marketplace_metadata_change_after_package_check_blocks(
        self,
    ) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            fake.add_marketplace()
            original_verify = preflight.verify_package
            changed = False

            def change_after_first_marketplace_check(
                root: Path, **kwargs: object
            ) -> dict[str, object]:
                nonlocal changed
                result = original_verify(root, **kwargs)
                if (
                    root.resolve() == fake.marketplace_root.resolve()
                    and not changed
                ):
                    changed = True
                    (
                        root / preflight.CODEX_MARKETPLACE_METADATA
                    ).write_text("{broken-json", encoding="utf-8")
                return result

            with mock.patch.object(
                preflight,
                "verify_package",
                side_effect=change_after_first_marketplace_check,
            ):
                evaluated = preflight.evaluate(source, env=env, runner=fake)

            self.assertIn(
                evaluated["status"], {"BLOCKED", "MIGRATION_REQUIRED"}
            )
            evidence = evaluated["codex"]["marketplace_runtime_evidence"]
            self.assertFalse(evidence["verified"])
            self.assertIn(
                "snapshot_marketplace_metadata_changed_after_verification",
                evidence["error_codes"],
            )
            self.assertEqual(fake.mutations, [])

    def test_installed_cache_accepts_verified_git_checkout_or_manifest_snapshot(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            result = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(result["ok"])
            cache = (
                Path(env["CODEX_HOME"])
                / "plugins"
                / "cache"
                / preflight.MARKETPLACE_NAME
                / preflight.PLUGIN_NAME
                / preflight.VERSION
            )
            self.assertTrue((cache / ".git").is_dir())
            with_git = preflight.evaluate(source, env=env, runner=fake)
            self.assertTrue(with_git["codex"]["cache_check"]["verified"])
            self.assertTrue(
                with_git["codex"]["cache_check"]["git_checkout_present"]
            )

            shutil.rmtree(cache / ".git")
            without_git = preflight.evaluate(source, env=env, runner=fake)
            self.assertTrue(without_git["codex"]["cache_check"]["verified"])
            self.assertFalse(
                without_git["codex"]["cache_check"]["git_checkout_present"]
            )

    def test_installed_cache_rejects_unsafe_or_wrong_git_metadata(self) -> None:
        cases = ("symlink", "wrong_origin")
        for case in cases:
            with self.subTest(case=case):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env)
                    installed = authorized_execute(source, env=env, runner=fake)
                    self.assertTrue(installed["ok"])
                    cache = (
                        Path(env["CODEX_HOME"])
                        / "plugins"
                        / "cache"
                        / preflight.MARKETPLACE_NAME
                        / preflight.PLUGIN_NAME
                        / preflight.VERSION
                    )
                    if case == "symlink":
                        shutil.rmtree(cache / ".git")
                        (cache / ".git").symlink_to(source / ".git")
                    else:
                        command(
                            [
                                "git",
                                "remote",
                                "set-url",
                                "origin",
                                "https://github.com/unknown/repo.git",
                            ],
                            cache,
                        )

                    evaluated = preflight.evaluate(source, env=env, runner=fake)

                    self.assertIn(
                        evaluated["status"], {"BLOCKED", "MIGRATION_REQUIRED"}
                    )
                    cache_check = evaluated["codex"]["cache_check"]
                    self.assertFalse(cache_check["verified"])
                    self.assertIn(
                        "installed_cache_bytes_unverified",
                        evaluated["error_codes"],
                    )

    def test_known_official_upgrade_executes_fixed_sequence_and_verifies_each_step(self) -> None:
        temp, source, env, fake = self.upgrade_fixture()
        with temp:
            result = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "INSTALLED_ENABLED_PENDING_HOOK_TRUST")
            self.assertEqual(
                fake.mutations,
                [
                    bootstrap.MARKETPLACE_REMOVE,
                    bootstrap.MARKETPLACE_ADD,
                    bootstrap.PLUGIN_ADD,
                ],
            )
            self.assertEqual(
                result["after_marketplace_remove"]["status"], "READY_FOR_INSTALL"
            )
            self.assertEqual(
                result["after_marketplace_add"]["status"], "READY_FOR_PLUGIN_ADD"
            )
            self.assertEqual(
                sorted(path.name for path in fake.cache_root.iterdir()),
                sorted(
                    set(preflight.KNOWN_OFFICIAL_UPGRADE_VERSIONS)
                    | {preflight.VERSION}
                ),
            )
            self.assertEqual(
                result["postflight"]["codex"]["cache_check"]["inventory"][
                    "versions"
                ],
                [preflight.VERSION],
            )
            self.assertEqual(
                result["postflight"]["codex"]["cache_check"]["inventory"][
                    "hook_bridges"
                ],
                sorted(preflight.KNOWN_OFFICIAL_UPGRADE_VERSIONS),
            )
            old_hook = (
                fake.cache_root
                / fake.old_version
                / "scripts"
                / "acgm_codex.py"
            )
            completed = subprocess.run(
                [sys.executable, str(old_hook), "hook", "stop"],
                input="{}\n",
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {})
            self.assertEqual(
                result["old_hook_protection"][-1]["state"],
                "bridge-created",
            )

    def test_known_official_upgrade_accepts_exact_preexisting_target_bridge(self) -> None:
        temp, source, env, fake = self.upgrade_fixture(
            old_version="0.2.0-rc.2"
        )
        with temp:
            bridge = bootstrap._ensure_one_old_hook_path(
                env, from_version="0.2.0-rc.1"
            )
            self.assertTrue(bridge["protected"])
            self.assertEqual(bridge["state"], "bridge-created")

            evaluated = preflight.evaluate(source, env=env, runner=fake)

            self.assertEqual(evaluated["status"], "READY_FOR_OFFICIAL_UPGRADE")
            inventory = evaluated["codex"]["cache_check"]["inventory"]
            self.assertTrue(inventory["verified"])
            self.assertEqual(inventory["versions"], ["0.2.0-rc.2"])
            self.assertEqual(inventory["hook_bridges"], ["0.2.0-rc.1"])

    def test_real_codex_reassociation_continues_only_with_exact_old_cache(
        self,
    ) -> None:
        temp, source, env, fake = self.upgrade_fixture(
            reassociate_on_add=True
        )
        with temp:
            result = authorized_execute(source, env=env, runner=fake)

            self.assertTrue(result["ok"])
            self.assertEqual(
                result["after_marketplace_add"]["status"],
                "READY_FOR_OFFICIAL_UPGRADE_RECOVERY",
            )
            transition = result["after_marketplace_add"]["codex"][
                "official_upgrade_transition"
            ]
            self.assertTrue(transition["recoverable"])
            self.assertEqual(transition["strategy"], "PLUGIN_ADD_ONLY")
            self.assertEqual(transition["from_version"], fake.old_version)
            self.assertEqual(
                fake.mutations,
                [
                    bootstrap.MARKETPLACE_REMOVE,
                    bootstrap.MARKETPLACE_ADD,
                    bootstrap.PLUGIN_ADD,
                ],
            )

        for kwargs in (
            {"reassociate_on_add": True, "transition_wrong_ref": True},
            {"reassociate_on_add": True, "transition_cache_tamper": True},
            {
                "reassociate_on_add": True,
                "transition_scope_override": None,
            },
            {"reassociate_on_add": True, "transition_wrong_policy": True},
            {"reassociate_on_add": True, "transition_wrong_source": True},
            {"reassociate_on_add": True, "transition_duplicate": True},
        ):
            with self.subTest(kwargs=kwargs):
                temp, source, env, fake = self.upgrade_fixture(**kwargs)
                with temp:
                    result = authorized_execute(source, env=env, runner=fake)
                    self.assertFalse(result["ok"])
                    self.assertEqual(
                        result["status"],
                        "OLD_HOOK_PROTECTION_FAILED_STATE_REQUIRES_RECHECK"
                        if kwargs.get("transition_cache_tamper")
                        else "MARKETPLACE_ADDED_BUT_POSTCONDITION_UNVERIFIED",
                    )
                    self.assertEqual(
                        fake.mutations,
                        [bootstrap.MARKETPLACE_REMOVE, bootstrap.MARKETPLACE_ADD],
                    )

    def test_interrupted_prior_candidate_requires_new_digest_and_rolls_forward(
        self,
    ) -> None:
        temp = tempfile.TemporaryDirectory()
        with temp:
            root = Path(temp.name)
            source = make_release(root / "current")
            old_source = make_release(root / "old", version="0.1.0-rc.4")
            interrupted_version = "0.2.0-rc.1"
            interrupted = make_release(
                root / "interrupted", version=interrupted_version
            )
            env = os.environ.copy()
            env["HOME"] = str(root / "home")
            env["CODEX_HOME"] = str(root / "codex-home")
            previous_release_identities = dict(
                preflight.KNOWN_OFFICIAL_RELEASES
            )
            preflight.KNOWN_OFFICIAL_RELEASES[interrupted_version] = {
                "revision": revision_for(
                    interrupted, f"v{interrupted_version}"
                ),
                "manifest_sha256": hashlib.sha256(
                    (interrupted / preflight.MANIFEST_NAME).read_bytes()
                ).hexdigest(),
            }
            self.addCleanup(
                lambda: (
                    preflight.KNOWN_OFFICIAL_RELEASES.clear(),
                    preflight.KNOWN_OFFICIAL_RELEASES.update(
                        previous_release_identities
                    ),
                )
            )
            fake = OfficialUpgradeCodex(
                source, old_source, env, old_version="0.1.0-rc.4"
            )
            fake.set_interrupted_transition(
                interrupted, interrupted_version
            )

            evaluated = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(
                evaluated["status"],
                "READY_FOR_OFFICIAL_UPGRADE_RECOVERY",
            )
            transition = evaluated["codex"][
                "official_upgrade_transition"
            ]
            self.assertTrue(transition["recoverable"])
            self.assertEqual(transition["strategy"], "RESTART_TO_CURRENT")

            with mock.patch.dict(
                preflight.KNOWN_OFFICIAL_RELEASES,
                {
                    interrupted_version: {
                        "revision": "0" * 40,
                        "manifest_sha256": "0" * 64,
                    }
                },
                clear=False,
            ):
                pinned_refusal = authorized_execute(
                    source, env=env, runner=fake
                )
            self.assertIn(
                pinned_refusal["status"],
                {"BLOCKED", "MIGRATION_REQUIRED"},
            )
            self.assertEqual(fake.mutations, [])

            refused = bootstrap.execute(
                source,
                dry_run=False,
                authorized=True,
                env=env,
                runner=fake,
            )
            self.assertEqual(refused["status"], "INSTALL_PLAN_DIGEST_REQUIRED")
            self.assertEqual(fake.mutations, [])

            result = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(result["ok"])
            self.assertEqual(
                fake.mutations,
                [
                    bootstrap.MARKETPLACE_REMOVE,
                    bootstrap.MARKETPLACE_ADD,
                    bootstrap.PLUGIN_ADD,
                ],
            )
            self.assertEqual(
                result["status"],
                "INSTALLED_ENABLED_PENDING_HOOK_TRUST",
            )

    def test_current_target_transition_new_process_resumes_with_plugin_add_only(
        self,
    ) -> None:
        for metadata_absent in (False, True):
            with self.subTest(metadata_absent=metadata_absent):
                temp, source, env, fake = self.upgrade_fixture()
                with temp:
                    fake.set_interrupted_transition(
                        source, preflight.VERSION
                    )
                    if metadata_absent:
                        (
                            fake.marketplace_root
                            / preflight.CODEX_MARKETPLACE_METADATA
                        ).unlink()

                    evaluated = preflight.evaluate(
                        source, env=env, runner=fake
                    )
                    self.assertEqual(
                        evaluated["status"],
                        "READY_FOR_OFFICIAL_UPGRADE_RECOVERY",
                    )
                    self.assertEqual(
                        evaluated["codex"]["official_upgrade_transition"][
                            "strategy"
                        ],
                        "PLUGIN_ADD_ONLY",
                    )
                    self.assertTrue(
                        evaluated["codex"]["marketplace_runtime_evidence"][
                            "verified"
                        ]
                    )

                    prepared = bootstrap.execute(
                        source,
                        dry_run=True,
                        authorized=False,
                        env=env,
                        runner=fake,
                    )
                    self.assertEqual(
                        [action["argv"] for action in prepared["plan"]],
                        [bootstrap.PLUGIN_ADD],
                    )
                    refused = bootstrap.execute(
                        source,
                        dry_run=False,
                        authorized=True,
                        env=env,
                        runner=fake,
                    )
                    self.assertEqual(
                        refused["status"], "INSTALL_PLAN_DIGEST_REQUIRED"
                    )
                    self.assertEqual(fake.mutations, [])

                    result = bootstrap.execute(
                        source,
                        dry_run=False,
                        authorized=True,
                        expected_plan_digest=str(
                            prepared["install_plan_digest"]
                        ),
                        env=env,
                        runner=fake,
                    )
                    self.assertTrue(result["ok"])
                    self.assertEqual(fake.mutations, [bootstrap.PLUGIN_ADD])
                    self.assertEqual(
                        result["status"],
                        "INSTALLED_ENABLED_PENDING_HOOK_TRUST",
                    )

    def test_known_official_upgrade_requires_pinned_release_identity(self) -> None:
        temp, source, env, fake = self.upgrade_fixture()
        with temp:
            wrong = {
                "revision": "0" * 40,
                "manifest_sha256": "0" * 64,
            }
            with mock.patch.dict(
                preflight.KNOWN_OFFICIAL_RELEASES,
                {fake.old_version: wrong},
                clear=False,
            ):
                evaluated = preflight.evaluate(source, env=env, runner=fake)

            self.assertEqual(evaluated["status"], "MIGRATION_REQUIRED")
            evidence = evaluated["codex"]["marketplace_runtime_evidence"]
            self.assertFalse(evidence["verified"])
            self.assertIn(
                "snapshot_known_official_revision_mismatch",
                evidence["error_codes"],
            )
            self.assertFalse(evaluated["codex"]["official_upgrade"]["eligible"])

    def test_cli_omitted_scope_requires_exact_bound_user_profile_config(
        self,
    ) -> None:
        temp, source, env, fake = self.upgrade_fixture()
        with temp:
            fake.omit_installed_scope = True
            accepted = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(accepted["status"], "READY_FOR_OFFICIAL_UPGRADE")
            self.assertTrue(
                accepted["codex"]["plugin_profile_config"]["verified"]
            )
            self.assertEqual(
                accepted["codex"]["official_upgrade"]["scope"], "user"
            )

            config = fake.codex_home / "config.toml"
            config.write_text(
                "\n".join(
                    [
                        f"[marketplaces.{preflight.MARKETPLACE_NAME}]",
                        'source_type = "git"',
                        f'source = "{preflight.REPOSITORY_URL}"',
                        f'ref = "{fake.old_ref}"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            rejected = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(rejected["status"], "MIGRATION_REQUIRED")
            self.assertFalse(
                rejected["codex"]["plugin_profile_config"]["verified"]
            )

    def test_marketplace_and_plugin_evidence_share_one_config_snapshot(
        self,
    ) -> None:
        temp, source, env, fake = self.upgrade_fixture()
        with temp:
            fake.omit_installed_scope = True
            config = fake.codex_home / "config.toml"
            config.write_text(
                "\n".join(
                    [
                        f"[marketplaces.{preflight.MARKETPLACE_NAME}]",
                        'source_type = "git"',
                        f'source = "{preflight.REPOSITORY_URL}"',
                        f'ref = "{fake.old_ref}"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            original_marketplace_parser = (
                preflight._marketplace_config_evidence
            )

            def swap_after_marketplace_parse(
                *args: object, **kwargs: object
            ) -> dict[str, object]:
                result = original_marketplace_parser(*args, **kwargs)
                config.write_text(
                    "\n".join(
                        [
                            f'[plugins."{preflight.PLUGIN_ID}"]',
                            "enabled = true",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                return result

            with mock.patch.object(
                preflight,
                "_marketplace_config_evidence",
                side_effect=swap_after_marketplace_parse,
            ):
                evaluated = preflight.evaluate(source, env=env, runner=fake)

            self.assertIn(
                evaluated["status"], {"BLOCKED", "MIGRATION_REQUIRED"}
            )
            self.assertFalse(
                evaluated["codex"]["plugin_profile_config"]["verified"]
            )
            self.assertFalse(
                evaluated["codex"]["codex_config_snapshot"]["unchanged"]
            )
            self.assertIn(
                "codex_config_changed_during_verification",
                evaluated["error_codes"],
            )
            self.assertEqual(fake.mutations, [])

    def test_official_old_cache_must_match_verified_marketplace_snapshot(self) -> None:
        temp, source, env, fake = self.upgrade_fixture(
            report_marketplace_ref=True
        )
        with temp:
            rogue_cache = Path(temp.name) / "rogue-cache"
            shutil.copytree(
                fake.old_source,
                rogue_cache,
                ignore=shutil.ignore_patterns(".git"),
            )
            (rogue_cache / "payload.txt").write_text(
                "different but internally consistent bytes\n", encoding="utf-8"
            )
            files: dict[str, str] = {}
            for path in sorted(item for item in rogue_cache.rglob("*") if item.is_file()):
                name = path.relative_to(rogue_cache).as_posix()
                if name != preflight.MANIFEST_NAME:
                    files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            (rogue_cache / preflight.MANIFEST_NAME).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "version": fake.old_version,
                        "files": files,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            fake._install_plugin_cache(
                rogue_cache, fake.old_version, replace_all=True
            )

            evaluated = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(evaluated["status"], "MIGRATION_REQUIRED")
            self.assertIn(
                "official_upgrade_cache_unverified", evaluated["error_codes"]
            )
            self.assertIn(
                "installed_cache_manifest_differs_from_marketplace_snapshot",
                evaluated["codex"]["cache_check"]["error_codes"],
            )
            result = authorized_execute(source, env=env, runner=fake)
            self.assertEqual(result["status"], "MIGRATION_REQUIRED")
            self.assertEqual(fake.mutations, [])

    def test_explicit_cli_ref_never_skips_config_or_snapshot_verification(self) -> None:
        cases = ("config", "snapshot")
        for tamper in cases:
            with self.subTest(tamper=tamper):
                temp, source, env, fake = self.upgrade_fixture(
                    report_marketplace_ref=True
                )
                with temp:
                    if tamper == "config":
                        fake._write_config("v0.1.0-rc.3")
                    else:
                        (fake.marketplace_root / "payload.txt").write_text(
                            "tampered snapshot\n", encoding="utf-8"
                        )

                    evaluated = preflight.evaluate(source, env=env, runner=fake)
                    self.assertEqual(evaluated["status"], "MIGRATION_REQUIRED")
                    evidence = evaluated["codex"]["marketplace_runtime_evidence"]
                    self.assertIsNotNone(evidence)
                    self.assertFalse(evidence["verified"])
                    result = authorized_execute(source, env=env, runner=fake)
                    self.assertIn(result["status"], {"MIGRATION_REQUIRED", "BLOCKED"})
                    self.assertEqual(fake.mutations, [])

    def test_official_upgrade_command_and_postcondition_failures_are_partial(self) -> None:
        cases = (
            (
                {"remove_failure": True},
                "MARKETPLACE_REMOVE_FAILED_STATE_REQUIRES_RECHECK",
                [bootstrap.MARKETPLACE_REMOVE],
            ),
            (
                {"remove_no_effect": True},
                "MARKETPLACE_REMOVED_BUT_POSTCONDITION_UNVERIFIED",
                [bootstrap.MARKETPLACE_REMOVE],
            ),
            (
                {"add_failure": True},
                "MARKETPLACE_ADD_FAILED_STATE_REQUIRES_RECHECK",
                [bootstrap.MARKETPLACE_REMOVE, bootstrap.MARKETPLACE_ADD],
            ),
            (
                {"plugin_failure": True},
                "PLUGIN_ADD_FAILED_MARKETPLACE_MAY_REMAIN",
                [
                    bootstrap.MARKETPLACE_REMOVE,
                    bootstrap.MARKETPLACE_ADD,
                    bootstrap.PLUGIN_ADD,
                ],
            ),
            (
                {"retain_old_cache": True},
                "INSTALL_COMMANDS_FINISHED_BUT_VERIFICATION_FAILED",
                [
                    bootstrap.MARKETPLACE_REMOVE,
                    bootstrap.MARKETPLACE_ADD,
                    bootstrap.PLUGIN_ADD,
                ],
            ),
        )
        for kwargs, expected_status, expected_mutations in cases:
            with self.subTest(kwargs=kwargs):
                temp, source, env, fake = self.upgrade_fixture(**kwargs)
                with temp:
                    result = authorized_execute(source, env=env, runner=fake)
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["partial"])
                    self.assertEqual(result["status"], expected_status)
                    self.assertEqual(fake.mutations, expected_mutations)
                    self.assertNotIn("rollback", json.dumps(result).lower())

    def test_failed_plugin_add_recreates_deleted_old_hook_path(self) -> None:
        temp, source, env, fake = self.upgrade_fixture(
            old_version="0.2.0-rc.1",
            plugin_failure=True,
        )
        with temp:
            def runner(
                argv: list[str] | tuple[str, ...],
                cwd: Path | None,
                environment: dict[str, str],
                timeout: int,
            ) -> preflight.CommandResult:
                result = fake(argv, cwd, environment, timeout)
                if list(argv) == bootstrap.PLUGIN_ADD and result.returncode != 0:
                    shutil.rmtree(fake.cache_root)
                return result

            result = authorized_execute(source, env=env, runner=runner)
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["status"], "PLUGIN_ADD_FAILED_MARKETPLACE_MAY_REMAIN"
            )
            bridge = fake.cache_root / fake.old_version
            self.assertTrue(
                preflight._hook_bridge_verified(
                    bridge,
                    from_version=fake.old_version,
                    target_version=preflight.VERSION,
                )
            )
            rc4_bridge = fake.cache_root / "0.1.0-rc.4"
            self.assertTrue(
                preflight._hook_bridge_verified(
                    rc4_bridge,
                    from_version="0.1.0-rc.4",
                    target_version=preflight.VERSION,
                )
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(bridge / "scripts" / "acgm_codex.py"),
                    "hook",
                    "stop",
                ],
                input="{}\n",
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {})

    def test_tampered_old_hook_bridge_invalidates_current_cache_inventory(self) -> None:
        temp, source, env, fake = self.upgrade_fixture(
            old_version="0.2.0-rc.1"
        )
        with temp:
            installed = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(installed["ok"])
            bridge_script = (
                fake.cache_root
                / fake.old_version
                / "scripts"
                / "acgm_codex.py"
            )
            bridge_script.write_text("print('tampered')\n", encoding="utf-8")

            evaluated = preflight.evaluate(source, env=env, runner=fake)

            self.assertEqual(evaluated["status"], "BLOCKED")
            inventory = evaluated["codex"]["cache_check"]["inventory"]
            self.assertFalse(inventory["verified"])
            self.assertIn(
                "installed_cache_version_entry_unrecognized",
                inventory["error_codes"],
            )

    def test_post_plugin_identity_drift_is_partial_not_success(self) -> None:
        cases = ("policy", "source", "duplicate")
        for case in cases:
            with self.subTest(case=case):
                temp, source, env, fake = self.upgrade_fixture()
                with temp:
                    changed = False

                    def runner(
                        argv: list[str] | tuple[str, ...],
                        cwd: Path | None,
                        environment: dict[str, str],
                        timeout: int,
                    ) -> preflight.CommandResult:
                        nonlocal changed
                        result = fake(argv, cwd, environment, timeout)
                        if list(argv) == bootstrap.PLUGIN_ADD and not changed:
                            changed = True
                            if case == "policy":
                                fake.transition_phase_active = True
                                fake.transition_wrong_policy = True
                            elif case == "source":
                                fake.plugin_source_url = (
                                    "https://github.com/unknown/source.git"
                                )
                            else:
                                fake.extra_installed.append(
                                    {
                                        "pluginId": "acgm-codex@other",
                                        "name": preflight.PLUGIN_NAME,
                                        "version": preflight.VERSION,
                                        "installed": True,
                                        "enabled": True,
                                        "installPolicy": "AVAILABLE",
                                        "authPolicy": "ON_INSTALL",
                                        "scope": "user",
                                        "source": {
                                            "source": "git",
                                            "url": preflight.REPOSITORY_URL,
                                            "ref": preflight.TAG,
                                        },
                                    }
                                )
                        return result

                    result = authorized_execute(
                        source, env=env, runner=runner
                    )
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["partial"])
                    self.assertEqual(
                        result["status"],
                        "INSTALL_COMMANDS_FINISHED_BUT_VERIFICATION_FAILED",
                    )
                    self.assertEqual(
                        fake.mutations,
                        [
                            bootstrap.MARKETPLACE_REMOVE,
                            bootstrap.MARKETPLACE_ADD,
                            bootstrap.PLUGIN_ADD,
                        ],
                    )

    def test_unknown_newer_foreign_scope_and_duplicate_installs_never_auto_upgrade(self) -> None:
        cases: list[tuple[str, str, dict[str, object]]] = [
            ("unknown_old_version", "0.1.0-rc.10", {}),
            ("newer_version", "0.2.0-rc.4", {}),
            ("null_scope", "0.1.0-rc.4", {"installed_scope": None}),
            ("wrong_scope", "0.1.0-rc.4", {"installed_scope": "project"}),
            (
                "wrong_marketplace",
                "0.1.0-rc.4",
                {"installed_marketplace": "other"},
            ),
            (
                "wrong_plugin_source",
                "0.1.0-rc.4",
                {"plugin_source_url": "https://github.com/unknown/source.git"},
            ),
            (
                "wrong_marketplace_source",
                "0.1.0-rc.4",
                {"marketplace_source_url": "https://github.com/unknown/source.git"},
            ),
            (
                "duplicate",
                "0.1.0-rc.4",
                {
                    "extra_installed": [
                        {
                            "pluginId": "acgm-codex@other",
                            "name": preflight.PLUGIN_NAME,
                            "version": "0.1.0-rc.4",
                            "installed": True,
                            "enabled": True,
                        }
                    ]
                },
            ),
        ]
        for name, old_version, changes in cases:
            with self.subTest(name=name):
                temp, source, env, fake = self.upgrade_fixture(
                    old_version=old_version,
                    report_marketplace_ref=True,
                )
                with temp:
                    for field, value in changes.items():
                        setattr(fake, field, value)
                    result = authorized_execute(source, env=env, runner=fake)
                    self.assertIn(result["status"], {"BLOCKED", "MIGRATION_REQUIRED"})
                    self.assertEqual(fake.mutations, [])

    def test_fresh_install_verifies_cache_and_is_idempotent(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            result = authorized_execute(source, env=env, runner=fake)
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
                ],
            )
            again = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(again["idempotent"])
            self.assertEqual(fake.mutations, [bootstrap.MARKETPLACE_ADD, bootstrap.PLUGIN_ADD])

    def test_observed_cli_0144_shape_completes_verified_install(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = ObservedCodex0144(source, env)
            result = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "INSTALLED_ENABLED_PENDING_HOOK_TRUST")
            self.assertEqual(fake.mutations, [bootstrap.MARKETPLACE_ADD, bootstrap.PLUGIN_ADD])
            intermediate = result["after_marketplace_add"]
            self.assertEqual(intermediate["status"], "READY_FOR_PLUGIN_ADD")
            self.assertEqual(
                intermediate["codex"]["plugin"], "AVAILABLE_NOT_ENUMERATED"
            )
            self.assertTrue(
                intermediate["codex"]["marketplace_runtime_evidence"]["verified"]
            )
            self.assertEqual(result["lifecycle"]["package_bytes"], "VERIFIED")

    def test_observed_cli_null_available_version_uses_strong_runtime_evidence(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = ObservedCodex0144(source, env)
            fake.enumerate_available = True
            result = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "INSTALLED_ENABLED_PENDING_HOOK_TRUST")
            intermediate = result["after_marketplace_add"]
            self.assertEqual(intermediate["status"], "READY_FOR_PLUGIN_ADD")
            self.assertEqual(intermediate["codex"]["plugin"], "AVAILABLE_EXACT")
            self.assertTrue(
                intermediate["codex"]["marketplace_runtime_evidence"]["verified"]
            )

    def test_explicit_wrong_available_version_overrides_runtime_evidence(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = ObservedCodex0144(source, env)
            fake.enumerate_available = True
            fake.enumerated_available_version = "9.9.9"
            fake.add_marketplace()
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn(
                "available_plugin_identity_version_or_source_conflict",
                result["error_codes"],
            )

    def test_missing_available_version_is_not_treated_as_explicit_null(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = ObservedCodex0144(source, env)
            fake.enumerate_available = True
            fake.omit_available_version = True
            fake.add_marketplace()
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn(
                "available_plugin_identity_version_or_source_conflict",
                result["error_codes"],
            )

    def test_observed_cli_0144_missing_or_tampered_ref_evidence_fails_closed(self) -> None:
        cases = (
            "missing_config",
            "multiline_config_spoof",
            "duplicate_config_section",
            "invalid_toml_escape",
            "wrong_config_ref",
            "wrong_snapshot_origin",
            "wrong_snapshot_head",
            "dirty_snapshot",
            "tampered_snapshot_bytes",
        )
        for case in cases:
            with self.subTest(case=case):
                temp, source, env = self.fixture()
                with temp:
                    fake = ObservedCodex0144(source, env)
                    fake.add_marketplace()
                    if case == "missing_config":
                        (fake.codex_home / "config.toml").unlink()
                    elif case == "multiline_config_spoof":
                        (fake.codex_home / "config.toml").write_text(
                            "\n".join(
                                [
                                    'decoy = """',
                                    f"[marketplaces.{preflight.MARKETPLACE_NAME}]",
                                    'source_type = "git"',
                                    f'source = "{preflight.REPOSITORY_URL}"',
                                    f'ref = "{preflight.TAG}"',
                                    '"""',
                                    "",
                                ]
                            ),
                            encoding="utf-8",
                        )
                    elif case == "duplicate_config_section":
                        config = fake.codex_home / "config.toml"
                        config.write_text(
                            config.read_text(encoding="utf-8")
                            + f"\n[marketplaces.{preflight.MARKETPLACE_NAME}]\n"
                            + f'ref = "{preflight.TAG}"\n',
                            encoding="utf-8",
                        )
                    elif case == "invalid_toml_escape":
                        config = fake.codex_home / "config.toml"
                        config.write_text(
                            config.read_text(encoding="utf-8").replace(
                                "https://", "https:\\/\\/"
                            ),
                            encoding="utf-8",
                        )
                    elif case == "wrong_config_ref":
                        config = fake.codex_home / "config.toml"
                        config.write_text(
                            config.read_text(encoding="utf-8").replace(
                                f'ref = "{preflight.TAG}"', 'ref = "main"'
                            ),
                            encoding="utf-8",
                        )
                    elif case == "wrong_snapshot_origin":
                        command(
                            [
                                "git",
                                "remote",
                                "set-url",
                                "origin",
                                "https://github.com/unknown/source.git",
                            ],
                            fake.marketplace_root,
                        )
                    elif case == "wrong_snapshot_head":
                        (fake.marketplace_root / "payload.txt").write_text(
                            "new untagged commit\n", encoding="utf-8"
                        )
                        command(["git", "add", "payload.txt"], fake.marketplace_root)
                        command(["git", "commit", "-m", "untagged"], fake.marketplace_root)
                    elif case == "dirty_snapshot":
                        (fake.marketplace_root / "untracked.txt").write_text(
                            "unexpected\n", encoding="utf-8"
                        )
                    elif case == "tampered_snapshot_bytes":
                        (fake.marketplace_root / "payload.txt").write_text(
                            "tampered\n", encoding="utf-8"
                        )
                    result = authorized_execute(source, env=env, runner=fake)
                    self.assertFalse(result["ok"])
                    self.assertIn(result["status"], {"BLOCKED", "MIGRATION_REQUIRED"})
                    self.assertEqual(fake.mutations, [])
                    evidence = result["preflight"]["codex"][
                        "marketplace_runtime_evidence"
                    ]
                    self.assertFalse(evidence["verified"])
                    self.assertTrue(evidence["error_codes"])

    def test_marketplace_snapshot_rejects_git_ignored_runtime_artifacts(self) -> None:
        cases = ("python_bytecode", "ignored_executable")
        for case in cases:
            with self.subTest(case=case):
                temp, source, env = self.fixture()
                with temp:
                    fake = ObservedCodex0144(source, env)
                    fake.add_marketplace()
                    if case == "python_bytecode":
                        artifact = (
                            fake.marketplace_root
                            / "__pycache__"
                            / "rogue.cpython-310.pyc"
                        )
                        artifact.parent.mkdir()
                        artifact.write_bytes(b"ignored executable bytecode\n")
                    else:
                        artifact = fake.marketplace_root / ".venv" / "bin" / "rogue"
                        artifact.parent.mkdir(parents=True)
                        artifact.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                        artifact.chmod(0o755)

                    result = preflight.evaluate(source, env=env, runner=fake)

                    self.assertEqual(result["status"], "MIGRATION_REQUIRED")
                    evidence = result["codex"]["marketplace_runtime_evidence"]
                    self.assertTrue(evidence["git_verified"])
                    self.assertFalse(evidence["package_verified"])
                    self.assertIn(
                        "snapshot_package_filesystem_excluded_path_not_allowed",
                        evidence["error_codes"],
                    )
                    self.assertEqual(fake.mutations, [])

    def test_malformed_json_or_hidden_exact_plugin_identity_fails_closed(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = ObservedCodex0144(source, env)
            fake.add_marketplace()
            fake.plugin_payload_override = {}
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("codex_state_json_shape_invalid", result["error_codes"])

        temp, source, env = self.fixture()
        with temp:
            fake = ObservedCodex0144(source, env)
            fake.add_marketplace()
            fake.add_plugin()
            fake.installed_name = "not-acgm-codex"
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertNotEqual(result["status"], "READY_FOR_PLUGIN_ADD")
            self.assertIn(
                "installed_plugin_identity_version_or_source_conflict",
                result["error_codes"],
            )

    def test_unrelated_multiline_toml_cannot_spoof_or_block_real_section(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = ObservedCodex0144(source, env)
            fake.add_marketplace()
            config = fake.codex_home / "config.toml"
            decoy = "\n".join(
                [
                    'unrelated = """',
                    f"[marketplaces.{preflight.MARKETPLACE_NAME}]",
                    'source_type = "git"',
                    'source = "https://github.com/unknown/source.git"',
                    'ref = "main"',
                    '"""',
                    "",
                ]
            )
            config.write_text(decoy + config.read_text(encoding="utf-8"), encoding="utf-8")
            result = preflight.evaluate(source, env=env, runner=fake)
            self.assertEqual(result["status"], "READY_FOR_PLUGIN_ADD")
            self.assertTrue(
                result["codex"]["marketplace_runtime_evidence"]["verified"]
            )

    def test_explicit_ref_and_installed_source_contract_remain_strict(self) -> None:
        marketplace = {
            "marketplaceSource": {
                "sourceType": "git",
                "source": preflight.REPOSITORY_URL,
                "ref": "main",
            }
        }
        self.assertFalse(preflight._marketplace_exact(marketplace, True))
        for source_kind in ("git", "url"):
            with self.subTest(source_kind=source_kind):
                self.assertTrue(
                    preflight._plugin_source_exact(
                        {
                            "source": {
                                "source": source_kind,
                                "url": preflight.REPOSITORY_URL,
                                "ref": preflight.TAG,
                            }
                        }
                    )
                )
        for source in (
            {
                "source": "local",
                "path": "/tmp/untrusted",
            },
            {
                "source": "git",
                "url": preflight.REPOSITORY_URL,
                "ref": "main",
            },
        ):
            with self.subTest(source=source):
                self.assertFalse(preflight._plugin_source_exact({"source": source}))

    def test_legacy_personal_and_duplicate_are_fail_closed(self) -> None:
        for field in ("legacy", "duplicate"):
            with self.subTest(field=field):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env, **{field: True})
                    result = authorized_execute(source, env=env, runner=fake)
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
                    result = authorized_execute(source, env=env, runner=fake)
                    self.assertEqual(result["status"], expected)
                    self.assertEqual(fake.mutations, [])

    def test_tampered_cache_is_partial_not_installed_claim(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env, cache_tamper=True)
            result = authorized_execute(source, env=env, runner=fake)
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
            result = authorized_execute(source, env=env, runner=fake)
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["status"], "INSTALL_COMMANDS_FINISHED_BUT_VERIFICATION_FAILED"
            )
            self.assertIn(
                "package_filesystem_unlisted_directory_not_allowed",
                result["postflight"]["codex"]["cache_check"]["error_codes"],
            )

    def test_installed_cache_rejects_ignored_runtime_artifacts(self) -> None:
        cases = (
            {"cache_pyc": True},
            {"cache_ignored_executable": True},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env, **kwargs)
                    result = authorized_execute(source, env=env, runner=fake)

                    self.assertFalse(result["ok"])
                    self.assertTrue(result["partial"])
                    self.assertEqual(
                        result["status"],
                        "INSTALL_COMMANDS_FINISHED_BUT_VERIFICATION_FAILED",
                    )
                    self.assertIn(
                        "package_filesystem_excluded_path_not_allowed",
                        result["postflight"]["codex"]["cache_check"][
                            "error_codes"
                        ],
                    )

    def test_installed_plugin_without_marketplace_is_not_complete(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env)
            installed = authorized_execute(source, env=env, runner=fake)
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
            {"available_null_version": True},
            {"available_wrong_source": True},
            {"available_missing": True},
            {"duplicate_available": True},
        ):
            with self.subTest(kwargs=kwargs):
                temp, source, env = self.fixture()
                with temp:
                    fake = FakeCodex(source, env, **kwargs)
                    result = authorized_execute(source, env=env, runner=fake)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertEqual(fake.mutations, [])

    def test_cli_failures_report_partial_state_without_rollback_claim(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env, marketplace_failure=True)
            result = authorized_execute(source, env=env, runner=fake)
            self.assertTrue(result["partial"])
            self.assertEqual(result["status"], "MARKETPLACE_ADD_FAILED_STATE_REQUIRES_RECHECK")
        temp, source, env = self.fixture()
        with temp:
            fake = FakeCodex(source, env, plugin_failure=True)
            result = authorized_execute(source, env=env, runner=fake)
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

    def test_raw_origin_cannot_be_hidden_by_instead_of_rewrite(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            command(
                ["git", "config", "remote.origin.url", "evil:ACGM-for-Codex.git"],
                source,
            )
            command(
                [
                    "git",
                    "config",
                    "url.https://github.com/johnrucnapier-sketch/.insteadOf",
                    "evil:",
                ],
                source,
            )
            rewritten = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=source,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            self.assertEqual(rewritten, preflight.REPOSITORY_URL)
            result = preflight.evaluate(source, env=env, runner=FakeCodex(source, env))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("origin_not_expected_repository", result["error_codes"])

    def test_assume_unchanged_cannot_replace_tag_bound_manifest_and_bytes(self) -> None:
        temp, source, env = self.fixture()
        with temp:
            replacement = b"self-consistent but not tagged\n"
            (source / "payload.txt").write_bytes(replacement)
            manifest_path = source / preflight.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["payload.txt"] = hashlib.sha256(replacement).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            command(
                [
                    "git",
                    "update-index",
                    "--assume-unchanged",
                    "payload.txt",
                    preflight.MANIFEST_NAME,
                ],
                source,
            )
            status = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=source,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout
            self.assertEqual(status, "")
            result = preflight.evaluate(source, env=env, runner=FakeCodex(source, env))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn(
                "package_manifest_not_exact_release_tag", result["error_codes"]
            )

class StableRuntimeTests(unittest.TestCase):
    def fixture(
        self, *, runtime_bytes: bytes = b'VERSION = "fixture-current"\n'
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        source = root / "source"
        (source / "scripts").mkdir(parents=True)
        (source / "scripts" / bootstrap.STABLE_RUNTIME_NAME).write_bytes(
            runtime_bytes
        )
        codex_home = root / "codex-home"
        codex_home.mkdir(mode=0o700)
        env = dict(os.environ)
        env["HOME"] = str(root / "home")
        env["CODEX_HOME"] = str(codex_home)
        target = codex_home.joinpath(
            *bootstrap.STABLE_RUNTIME_PARTS, bootstrap.STABLE_RUNTIME_NAME
        )
        return temp, source, env, target

    def installed_fixture(
        self,
    ) -> tuple[
        tempfile.TemporaryDirectory[str],
        Path,
        dict[str, str],
        Path,
        FakeCodex,
    ]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        source = make_release(root)
        env = dict(os.environ)
        env["HOME"] = str(root / "home")
        env["CODEX_HOME"] = str(root / "codex-home")
        fake = FakeCodex(source, env)
        installed = authorized_execute(source, env=env, runner=fake)
        self.assertTrue(installed["ok"])
        target = Path(env["CODEX_HOME"]).joinpath(
            *bootstrap.STABLE_RUNTIME_PARTS, bootstrap.STABLE_RUNTIME_NAME
        )
        return temp, source, env, target, fake

    def test_missing_runtime_is_published_atomically_and_idempotently(self) -> None:
        temp, source, env, target = self.fixture()
        with temp:
            before = bootstrap._stable_runtime_evidence(source, env)
            self.assertEqual(before["state"], "missing")
            self.assertTrue(before["replaceable"])

            published = bootstrap._publish_stable_runtime(source, env)
            self.assertTrue(published["verified"])
            self.assertTrue(published["published"])
            self.assertEqual(published["previous_state"], "missing")
            self.assertEqual(
                target.read_bytes(),
                (source / "scripts" / bootstrap.STABLE_RUNTIME_NAME).read_bytes(),
            )
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

            again = bootstrap._publish_stable_runtime(source, env)
            self.assertTrue(again["verified"])
            self.assertFalse(again["published"])
            self.assertEqual(
                list(target.parent.glob(f".{bootstrap.STABLE_RUNTIME_NAME}.new-*")),
                [],
            )

    def test_install_digest_binds_stable_runtime_preimage_and_publication(self) -> None:
        common: dict[str, object] = {
            "status": "READY_FOR_STABLE_HOOK_RUNTIME",
            "platform": "Darwin",
            "python": "3.14",
            "source": {"verified": True},
            "codex": {"plugin": "INSTALLED_ENABLED_EXACT"},
            "hook_definition_sha256": "1" * 64,
            "lifecycle": {"stable_hook_runtime": "NOT_VERIFIED"},
            "error_codes": [],
            "actions": [],
        }
        missing = {
            **common,
            "stable_hook_runtime": {
                "state": "missing",
                "expected_sha256": "2" * 64,
                "expected_size": 123,
                "logical_path_sha256": "3" * 64,
                "replaceable": True,
                "verified": False,
            },
        }
        known_old = {
            **common,
            "stable_hook_runtime": {
                **missing["stable_hook_runtime"],
                "state": "known-official-old-runtime",
                "observed_sha256": "4" * 64,
            },
        }
        target = {"schema": "fixture-target"}
        missing_plan = bootstrap._install_authorization_plan(ROOT, missing, target)
        old_plan = bootstrap._install_authorization_plan(ROOT, known_old, target)

        self.assertEqual(
            missing_plan["schema"], "acgm-codex-install-authorization-plan-v3"
        )
        self.assertEqual(
            missing_plan["stable_hook_runtime_publication"]["target"],
            "PLUGIN_DATA/runtime/acgm_codex.py",
        )
        self.assertEqual(
            missing_plan["stable_hook_runtime_publication"]["replacement_policy"],
            "missing-or-digest-pinned-known-official-only",
        )
        self.assertNotEqual(
            bootstrap._install_plan_digest(missing_plan),
            bootstrap._install_plan_digest(old_plan),
        )

    def test_runtime_preimage_change_after_dry_run_makes_plan_stale(self) -> None:
        temp, source, env, target, fake = self.installed_fixture()
        with temp:
            target.unlink()
            prepared = bootstrap.execute(
                source,
                dry_run=True,
                authorized=False,
                env=env,
                runner=fake,
            )
            self.assertEqual(prepared["initial_status"], "READY_FOR_STABLE_HOOK_RUNTIME")
            old = b'VERSION = "fixture-known-old"\n'
            target.write_bytes(old)
            if os.name != "nt":
                target.chmod(0o600)
            with mock.patch.dict(
                preflight.KNOWN_OFFICIAL_RELEASES,
                {
                    "fixture-known-old": {
                        "runtime_sha256": hashlib.sha256(old).hexdigest()
                    }
                },
                clear=False,
            ):
                refused = bootstrap.execute(
                    source,
                    dry_run=False,
                    authorized=True,
                    expected_plan_digest=str(prepared["install_plan_digest"]),
                    env=env,
                    runner=fake,
                )

            self.assertEqual(refused["status"], "INSTALL_PLAN_STALE")
            self.assertEqual(target.read_bytes(), old)

    def test_unrecognized_runtime_after_dry_run_blocks_without_replacement(self) -> None:
        temp, source, env, target, fake = self.installed_fixture()
        with temp:
            target.unlink()
            prepared = bootstrap.execute(
                source,
                dry_run=True,
                authorized=False,
                env=env,
                runner=fake,
            )
            unrecognized = b"changed after the authorized plan\n"
            target.write_bytes(unrecognized)
            if os.name != "nt":
                target.chmod(0o600)
            refused = bootstrap.execute(
                source,
                dry_run=False,
                authorized=True,
                expected_plan_digest=str(prepared["install_plan_digest"]),
                env=env,
                runner=fake,
            )

            self.assertEqual(refused["status"], "BLOCKED")
            self.assertEqual(target.read_bytes(), unrecognized)

    def test_exact_runtime_produces_stable_idempotent_plan_digest(self) -> None:
        temp, source, env, target, fake = self.installed_fixture()
        with temp:
            first = bootstrap.execute(
                source,
                dry_run=True,
                authorized=False,
                env=env,
                runner=fake,
            )
            second = bootstrap.execute(
                source,
                dry_run=True,
                authorized=False,
                env=env,
                runner=fake,
            )

            self.assertTrue(first["idempotent"])
            self.assertTrue(second["idempotent"])
            self.assertEqual(first["install_plan_digest"], second["install_plan_digest"])
            self.assertFalse(
                first["authorization_plan"]["stable_hook_runtime_publication"][
                    "required"
                ]
            )
            self.assertEqual(
                target.read_bytes(),
                (source / "scripts" / bootstrap.STABLE_RUNTIME_NAME).read_bytes(),
            )

    def test_known_official_old_runtime_is_replaceable(self) -> None:
        temp, source, env, target = self.fixture()
        with temp:
            old = b'VERSION = "fixture-old"\n'
            target.parent.mkdir(parents=True, mode=0o700)
            target.write_bytes(old)
            if os.name != "nt":
                target.chmod(0o600)
            release = {"runtime_sha256": hashlib.sha256(old).hexdigest()}
            with mock.patch.dict(
                preflight.KNOWN_OFFICIAL_RELEASES,
                {"fixture-old": release},
                clear=False,
            ):
                before = bootstrap._stable_runtime_evidence(source, env)
                self.assertEqual(before["state"], "known-official-old-runtime")
                self.assertTrue(before["replaceable"])
                published = bootstrap._publish_stable_runtime(source, env)

            self.assertTrue(published["verified"])
            self.assertTrue(published["published"])
            self.assertEqual(published["previous_state"], "known-official-old-runtime")

    def test_unrecognized_runtime_is_never_replaced(self) -> None:
        temp, source, env, target = self.fixture()
        with temp:
            unrecognized = b"not an authorized runtime\n"
            target.parent.mkdir(parents=True, mode=0o700)
            target.write_bytes(unrecognized)
            if os.name != "nt":
                target.chmod(0o600)

            before = bootstrap._stable_runtime_evidence(source, env)
            published = bootstrap._publish_stable_runtime(source, env)

            self.assertEqual(before["state"], "unrecognized-runtime")
            self.assertFalse(before["replaceable"])
            self.assertFalse(published["published"])
            self.assertFalse(published["verified"])
            self.assertEqual(target.read_bytes(), unrecognized)

    def test_symlinked_runtime_is_never_replaced(self) -> None:
        temp, source, env, target = self.fixture()
        with temp:
            target.parent.mkdir(parents=True, mode=0o700)
            target.symlink_to(source / "scripts" / bootstrap.STABLE_RUNTIME_NAME)

            observed = bootstrap._stable_runtime_evidence(source, env)
            published = bootstrap._publish_stable_runtime(source, env)

            self.assertEqual(observed["state"], "unsafe-entry")
            self.assertFalse(observed["replaceable"])
            self.assertFalse(published["published"])
            self.assertTrue(target.is_symlink())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO is unavailable")
    def test_publisher_read_rejects_fifo_without_blocking(self) -> None:
        temp, source, env, target = self.fixture()
        with temp:
            target.parent.mkdir(parents=True, mode=0o700)
            os.mkfifo(target, 0o600)
            program = "\n".join(
                [
                    "import os, sys",
                    f"sys.path.insert(0, {str(ROOT / 'scripts')!r})",
                    "import bootstrap",
                    f"directory = {str(target.parent)!r}",
                    "flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)",
                    "descriptor = os.open(directory, flags)",
                    "try:",
                    "    try:",
                    "        bootstrap._read_regular_at(descriptor, 'acgm_codex.py')",
                    "    except OSError:",
                    "        pass",
                    "    else:",
                    "        raise SystemExit(3)",
                    "finally:",
                    "    os.close(descriptor)",
                ]
            )
            completed = subprocess.run(
                [sys.executable, "-B", "-c", program],
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_unsafe_or_symlinked_parent_is_never_used(self) -> None:
        cases = ("group-writable", "symlink")
        for case in cases:
            with self.subTest(case=case):
                temp, source, env, target = self.fixture()
                with temp:
                    codex_home = Path(env["CODEX_HOME"])
                    if case == "group-writable":
                        plugins = codex_home / "plugins"
                        plugins.mkdir(mode=0o700)
                        if os.name == "nt":
                            self.skipTest("POSIX group/other mode is unavailable")
                        plugins.chmod(0o770)
                    else:
                        outside = Path(temp.name) / "outside"
                        outside.mkdir(mode=0o700)
                        (codex_home / "plugins").symlink_to(
                            outside, target_is_directory=True
                        )

                    observed = bootstrap._stable_runtime_evidence(source, env)
                    published = bootstrap._publish_stable_runtime(source, env)

                    self.assertEqual(observed["state"], "unsafe-parent")
                    self.assertFalse(observed["replaceable"])
                    self.assertFalse(published["published"])
                    self.assertFalse(target.exists())

    def test_atomic_failures_leave_no_temporary_runtime(self) -> None:
        failures = ("replace", "fchmod", "fsync", "zero-write")
        for failure in failures:
            with self.subTest(failure=failure):
                temp, source, env, target = self.fixture()
                with temp:
                    if failure == "replace":
                        patcher = mock.patch.object(
                            bootstrap.os,
                            "replace",
                            side_effect=OSError("injected replace failure"),
                        )
                    elif failure == "fchmod":
                        if not hasattr(bootstrap.os, "fchmod"):
                            self.skipTest("fchmod is unavailable")
                        patcher = mock.patch.object(
                            bootstrap.os,
                            "fchmod",
                            side_effect=OSError("injected fchmod failure"),
                        )
                    elif failure == "fsync":
                        patcher = mock.patch.object(
                            bootstrap.os,
                            "fsync",
                            side_effect=OSError("injected fsync failure"),
                        )
                    else:
                        patcher = mock.patch.object(
                            bootstrap.os, "write", return_value=0
                        )
                    with patcher:
                        published = bootstrap._publish_stable_runtime(source, env)

                    self.assertFalse(published["verified"])
                    self.assertFalse(published["published"])
                    self.assertEqual(published["publish_error"], "OSError")
                    runtime_dir = target.parent
                    self.assertTrue(runtime_dir.is_dir())
                    self.assertEqual(
                        list(
                            runtime_dir.glob(
                                f".{bootstrap.STABLE_RUNTIME_NAME}.new-*"
                            )
                        ),
                        [],
                    )
                    self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
