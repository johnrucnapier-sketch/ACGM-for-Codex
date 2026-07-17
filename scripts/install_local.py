#!/usr/bin/env python3
"""DEVELOPMENT ONLY: install the checkout as a personal ACGM Codex plugin.

The workspace checkout remains the canonical development source.  This command
copies a clean snapshot to ``~/plugins/acgm-codex``, updates the personal
marketplace, installs a stable CLI wrapper, and asks Codex to refresh its cache.
Public users should use ``scripts/quickstart.py`` and the tagged Git marketplace;
this helper is not a legacy migration mechanism.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import Any


PLUGIN_NAME = "acgm-codex"
DEFAULT_MARKETPLACE_NAME = "personal"
SOURCE_ROOT = Path(__file__).resolve().parent.parent

# Keep the personal-plugin snapshot deterministic.  In particular, do not turn
# this into a directory-wide copy: a development checkout can contain local
# ledgers, virtual environments, build output, credentials, or unrelated
# untracked work that must never enter the installed plugin.
PUBLISHED_FILES = (
    ".agents/plugins/marketplace.json",
    ".codex-plugin/plugin.json",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "EVIDENCE.md",
    "INSTALL.md",
    "LICENSE-CODE",
    "LICENSE-DOCS",
    "LICENSING.md",
    "PACKAGE_MANIFEST.json",
    "README.en.md",
    "README.md",
    "RELEASING.md",
    "SECURITY.md",
    "VERSION",
    "bin/acgm-codex",
    "hooks/hooks.json",
    "pyproject.toml",
    "scripts/acgm_codex.py",
    "scripts/bootstrap.py",
    "scripts/generate-package-manifest.py",
    "scripts/install_local.py",
    "scripts/preflight.py",
    "scripts/release_check.py",
    "skills/activity-report/SKILL.md",
    "skills/activity-report/agents/openai.yaml",
    "skills/governance-bootstrap/SKILL.md",
    "skills/governance-bootstrap/agents/openai.yaml",
    "skills/session-grounding/SKILL.md",
    "skills/session-grounding/agents/openai.yaml",
    "skills/truth-first/SKILL.md",
    "skills/truth-first/agents/openai.yaml",
    "tests/manual/CODEX_E2E.md",
    "tests/test_bootstrap.py",
    "tests/test_install_local.py",
    "tests/test_package_contract.py",
    "tests/test_release_tools.py",
    "tests/test_runtime.py",
)


class InstallTransactionError(RuntimeError):
    """Raised when installation fails after local-state mutation begins."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _pyproject_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    section = re.search(
        r"^\[project\]\s*$\n(.*?)(?=^\[|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not section:
        raise ValueError(f"missing [project] section: {path}")
    match = re.search(
        r'''^version\s*=\s*(["'])([^"']+)\1\s*(?:#.*)?$''',
        section.group(1),
        flags=re.MULTILINE,
    )
    if not match or not match.group(2).strip():
        raise ValueError(f"missing non-empty [project].version: {path}")
    return match.group(2).strip()


def validate_source(source: Path) -> str:
    manifest_path = source / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing plugin manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("name") != PLUGIN_NAME:
        raise ValueError(f"plugin manifest name must be {PLUGIN_NAME!r}")
    version = manifest.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("plugin manifest must contain a non-empty version")
    manifest_version = version.strip()

    version_path = source / "VERSION"
    file_version = version_path.read_text(encoding="utf-8").strip()
    if not file_version:
        raise ValueError(f"{version_path} must contain a non-empty version")
    project_version = _pyproject_version(source / "pyproject.toml")
    if len({manifest_version, file_version, project_version}) != 1:
        raise ValueError(
            "source version mismatch: "
            f"manifest={manifest_version!r}, VERSION={file_version!r}, "
            f"pyproject={project_version!r}"
        )
    return manifest_version


def _copy_published_files(source: Path, destination: Path) -> None:
    """Copy only reviewed release files and reject symlink indirection."""

    for relative_name in PUBLISHED_FILES:
        relative = Path(relative_name)
        source_path = source / relative

        cursor = source
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError(f"refusing symlink in published path: {relative_name}")

        if not source_path.is_file():
            raise FileNotFoundError(f"missing published file: {source_path}")

        destination_path = destination / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)


def install_snapshot(source: Path, destination: Path, *, force: bool) -> None:
    if source.resolve() == destination.resolve():
        return

    if destination.exists():
        existing_manifest = destination / ".codex-plugin" / "plugin.json"
        existing_name = None
        try:
            existing_name = read_json(existing_manifest).get("name")
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        if existing_name != PLUGIN_NAME and not force:
            raise FileExistsError(
                f"refusing to replace non-{PLUGIN_NAME} directory: {destination}; "
                "pass --force only after reviewing it"
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=f".{PLUGIN_NAME}.install-", dir=destination.parent)
    )
    staged = staging_parent / PLUGIN_NAME
    backup = destination.parent / f".{PLUGIN_NAME}.previous-{os.getpid()}"
    try:
        staged.mkdir()
        _copy_published_files(source, staged)
        launcher = staged / "bin" / PLUGIN_NAME
        if launcher.exists():
            launcher.chmod(0o755)

        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            destination.rename(backup)
        try:
            staged.rename(destination)
        except BaseException:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def update_marketplace(home: Path, *, force: bool) -> tuple[Path, str]:
    path = home / ".agents" / "plugins" / "marketplace.json"
    if path.exists():
        payload = read_json(path)
    else:
        payload = {
            "name": DEFAULT_MARKETPLACE_NAME,
            "interface": {"displayName": "Personal"},
            "plugins": [],
        }

    marketplace_name = payload.get("name")
    if not isinstance(marketplace_name, str) or not marketplace_name.strip():
        raise ValueError(f"{path} must contain a non-empty marketplace name")
    plugins = payload.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError(f"{path} field 'plugins' must be an array")

    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }
    for index, current in enumerate(plugins):
        if isinstance(current, dict) and current.get("name") == PLUGIN_NAME:
            if current != entry and not force:
                raise ValueError(
                    f"personal marketplace already has a different {PLUGIN_NAME} entry; "
                    "review it or pass --force"
                )
            plugins[index] = entry
            break
    else:
        plugins.append(entry)

    atomic_write_json(path, payload)
    return path, marketplace_name


def install_cli_wrapper(home: Path, plugin_source: Path) -> Path:
    path = home / ".local" / "bin" / PLUGIN_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        raise IsADirectoryError(f"refusing to replace CLI wrapper directory: {path}")

    target = plugin_source / "bin" / PLUGIN_NAME
    body = "#!/bin/sh\nexec " + shlex.quote(str(target)) + ' "$@"\n'
    fd, temp_name = tempfile.mkstemp(prefix=f".{PLUGIN_NAME}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o755)
        # Replacing the directory entry atomically avoids following an existing
        # symlink and overwriting the symlink target.
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return path


def _capture_path(path: Path, backup_root: Path, label: str) -> dict[str, Any]:
    """Capture a local path without following symlinks."""

    if path.is_symlink():
        return {"path": path, "kind": "symlink", "target": os.readlink(path)}
    if path.is_file():
        stored = backup_root / label
        stored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, stored)
        return {"path": path, "kind": "file", "stored": stored}
    if path.is_dir():
        stored = backup_root / label
        shutil.copytree(path, stored, symlinks=True)
        return {"path": path, "kind": "directory", "stored": stored}
    if os.path.lexists(path):
        raise ValueError(f"unsupported filesystem object at install path: {path}")
    return {"path": path, "kind": "absent"}


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif os.path.lexists(path):
        path.unlink()


def _restore_path(backup: dict[str, Any]) -> None:
    path = backup["path"]
    _remove_path(path)
    kind = backup["kind"]
    if kind == "absent":
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "symlink":
        path.symlink_to(backup["target"])
    elif kind == "file":
        shutil.copy2(backup["stored"], path)
    elif kind == "directory":
        shutil.copytree(backup["stored"], path, symlinks=True)
    else:
        raise ValueError(f"unknown backup kind: {kind!r}")


def perform_install(
    source: Path,
    home: Path,
    *,
    force: bool,
    refresh_cache: bool,
) -> dict[str, Any]:
    """Install locally and restore all managed paths if a later step fails."""

    source = source.resolve()
    home = home.expanduser().resolve()
    version = validate_source(source)
    destination = home / "plugins" / PLUGIN_NAME
    marketplace_path = home / ".agents" / "plugins" / "marketplace.json"
    cli_path = home / ".local" / "bin" / PLUGIN_NAME

    home.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{PLUGIN_NAME}.transaction-", dir=home
    ) as raw_backup_root:
        backup_root = Path(raw_backup_root)
        backups = [
            _capture_path(destination, backup_root, "personal-source"),
            _capture_path(marketplace_path, backup_root, "marketplace.json"),
            _capture_path(cli_path, backup_root, "cli-wrapper"),
        ]
        try:
            install_snapshot(source, destination, force=force)
            updated_marketplace_path, marketplace_name = update_marketplace(
                home, force=force
            )
            installed_cli_path = install_cli_wrapper(home, destination)
            codex_result: dict[str, Any] | None = None
            if refresh_cache:
                codex_result = run_codex_install(marketplace_name, home=home)
        except Exception as exc:
            rollback_errors: list[str] = []
            for backup in reversed(backups):
                try:
                    _restore_path(backup)
                except Exception as rollback_exc:
                    rollback_errors.append(f"{backup['path']}: {rollback_exc}")

            if rollback_errors:
                detail = "; ".join(rollback_errors)
                raise InstallTransactionError(
                    "local install failed and rollback was incomplete; "
                    f"partial install state may remain ({detail})"
                ) from exc
            raise InstallTransactionError(
                "local install failed; prior personal source, marketplace, and CLI "
                "wrapper state was restored. If Codex cache refresh had started, "
                "run the installer again before relying on the cached plugin"
            ) from exc

    path_entries = {
        Path(item).expanduser().resolve()
        for item in os.environ.get("PATH", "").split(os.pathsep)
        if item
    }
    cli_on_path = cli_path.parent.resolve() in path_entries
    next_step = "Start a new Codex task, open /hooks, and trust the reviewed ACGM hooks."
    if not cli_on_path:
        next_step += (
            f" The CLI is available at {cli_path}; add {cli_path.parent} to PATH "
            "only if you want to call it directly outside Codex."
        )
    return {
        "plugin": PLUGIN_NAME,
        "version": version,
        "source": str(source),
        "personal_source": str(destination),
        "marketplace": marketplace_name,
        "marketplace_path": str(updated_marketplace_path),
        "cli": str(installed_cli_path),
        "cli_on_path": cli_on_path,
        "cache_refreshed": refresh_cache,
        "codex": codex_result,
        "next": next_step,
    }


def run_codex_install(marketplace_name: str, *, home: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    result = subprocess.run(
        ["codex", "plugin", "add", f"{PLUGIN_NAME}@{marketplace_name}", "--json"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"codex plugin add failed: {message}")
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"stdout": result.stdout.strip()}
    return payload if isinstance(payload, dict) else {"result": payload}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install ACGM as a personal Codex plugin")
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument(
        "--no-plugin-add",
        action="store_true",
        help="prepare the personal source and marketplace without refreshing the Codex cache",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace a conflicting local ACGM destination or marketplace entry",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    home = args.home.expanduser().resolve()
    source = SOURCE_ROOT.resolve()
    result = perform_install(
        source,
        home,
        force=args.force,
        refresh_cache=not args.no_plugin_add,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Installed {PLUGIN_NAME} {result['version']} from {source}")
        print(f"Personal source: {result['personal_source']}")
        print(f"Marketplace: {result['marketplace']} ({result['marketplace_path']})")
        print(f"CLI: {result['cli']}")
        print(result["next"])


if __name__ == "__main__":
    main()
