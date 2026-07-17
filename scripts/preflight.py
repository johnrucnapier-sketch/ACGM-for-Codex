#!/usr/bin/env python3
"""Non-mutating-by-design public-install preflight for ACGM for Codex.

The probe never directly edits the checkout or Codex marketplace/plugin
configuration.  The Codex CLI used for state inspection can still perform its
own vendor-controlled startup housekeeping.  The probe reports observable
package, Git, platform, marketplace, plugin, and cache facts without inferring
Hook trust or a backing model/provider/account.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Sequence


PLUGIN_NAME = "acgm-codex"
MARKETPLACE_NAME = "acgm-codex"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
LEGACY_PLUGIN_ID = f"{PLUGIN_NAME}@personal"
VERSION = "0.2.0-rc.1"
TAG = "v0.2.0-rc.1"
REPOSITORY = "johnrucnapier-sketch/ACGM-for-Codex"
REPOSITORY_URL = "https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "PACKAGE_MANIFEST.json"
CODEX_MARKETPLACE_METADATA = ".codex-marketplace-install.json"
MAX_CODEX_MARKETPLACE_METADATA_BYTES = 8192
MINIMUM_PYTHON = (3, 10)
SUPPORTED_PLATFORMS = {"Darwin", "Linux"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
RC_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-rc\.(0|[1-9]\d*)$"
)
KNOWN_OFFICIAL_UPGRADE_VERSIONS = frozenset(
    {"0.1.0-rc.2", "0.1.0-rc.3", "0.1.0-rc.4"}
)
KNOWN_OFFICIAL_RELEASES = {
    "0.1.0-rc.2": {
        "revision": "4deb6d1695290bae8a9fdc15e8419fef48cbf808",
        "manifest_sha256": "26385f5ad022dd3b8c3f7beda32b05769dbfd559335ce2a43c14434844ca732a",
    },
    "0.1.0-rc.3": {
        "revision": "244a0e4dab1b082c9ab18cf243a507f420e763b8",
        "manifest_sha256": "3ff678020a75a472c6fc34c9d7dcd39098055ae150604d94d58723202253bb92",
    },
    "0.1.0-rc.4": {
        "revision": "06623a95df96b3ced9759e6434d096ab8c66fb5f",
        "manifest_sha256": "227d52be85d1c6c4104a4018c5a7b4c49f536f54c9365181db3c31edad66cab3",
    },
}
EXCLUDED_PARTS = {".git", ".acgm", ".venv", "__pycache__", "build", "dist"}
EXCLUDED_NAMES = {MANIFEST_NAME, CODEX_MARKETPLACE_METADATA, ".DS_Store"}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


Runner = Callable[[Sequence[str], Path | None, dict[str, str], int], CommandResult]


def run_command(
    argv: Sequence[str], cwd: Path | None, env: dict[str, str], timeout: int
) -> CommandResult:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, timed_out=True)
    except OSError as exc:
        return CommandResult(127, stderr=str(exc))
    return CommandResult(completed.returncode, completed.stdout or "", completed.stderr or "")


def git_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """Prevent inherited Git routing/config variables from changing source identity."""

    environment = {
        key: value
        for key, value in dict(base or os.environ).items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
    )
    return environment


def neutral_cwd_is_safe(path: Path) -> bool:
    """Reject a control cwd nested under any repo or repo-local marketplace."""

    try:
        candidate = path.resolve(strict=True)
    except OSError:
        return False
    for ancestor in (candidate, *candidate.parents):
        if (ancestor / ".git").exists():
            return False
        if (ancestor / ".agents" / "plugins" / "marketplace.json").exists():
            return False
    return True


def run_codex_control(
    argv: Sequence[str], env: dict[str, str], runner: Runner, timeout: int
) -> CommandResult:
    """Run a Codex probe/mutation outside the checkout's auto-discovery scope."""

    try:
        with tempfile.TemporaryDirectory(prefix="acgm-codex-control-") as raw:
            os.chmod(raw, 0o700)
            control = Path(raw)
            if not neutral_cwd_is_safe(control):
                return CommandResult(126, stderr="unsafe neutral control cwd")
            return runner(argv, control, env, timeout)
    except OSError as exc:
        return CommandResult(126, stderr=str(exc))


def _safe_relative(value: str) -> PurePosixPath | None:
    if not value or "\\" in value or "\0" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path if path.as_posix() == value else None


def _included(value: str) -> bool:
    path = _safe_relative(value)
    return bool(
        path
        and not any(part in EXCLUDED_PARTS for part in path.parts)
        and path.name not in EXCLUDED_NAMES
        and path.suffix != ".pyc"
    )


def _regular_bytes(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("not_regular")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise ValueError("not_regular")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read()
        after = os.fstat(descriptor)
        if (
            current.st_size != after.st_size
            or current.st_mtime_ns != after.st_mtime_ns
            or current.st_ctime_ns != after.st_ctime_ns
        ):
            raise ValueError("changed_while_reading")
        return content
    finally:
        os.close(descriptor)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(_regular_bytes(path).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("not_object")
    return value


def _json_output(result: CommandResult) -> dict[str, Any] | None:
    if result.returncode != 0 or result.timed_out:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _canonical_repo(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    prefix = "https://github.com/"
    if normalized.casefold().startswith(prefix):
        normalized = normalized[len(prefix) :]
    return normalized.casefold()


def _expected_repo(value: object) -> bool:
    return _canonical_repo(value) == REPOSITORY.casefold()


def _rc_version_order(value: object) -> tuple[int, int, int, int] | None:
    """Return a numeric prerelease order; never compare release strings lexically."""

    if not isinstance(value, str):
        return None
    match = RC_VERSION.fullmatch(value)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def _known_official_upgrade(version: object, ref: object) -> bool:
    order = _rc_version_order(version)
    target = _rc_version_order(VERSION)
    return bool(
        isinstance(version, str)
        and version in KNOWN_OFFICIAL_UPGRADE_VERSIONS
        and ref == f"v{version}"
        and order is not None
        and target is not None
        and order < target
    )


def _codex_marketplace_metadata(
    root: Path, *, expected_tag: str, expected_revision: str | None
) -> dict[str, Any]:
    """Verify the sole untracked metadata file created by the Codex CLI.

    This file is platform-owned rather than release-owned, so it is not part of
    ``PACKAGE_MANIFEST.json``.  It is allowed only at the marketplace checkout
    root and only when every identity field binds it to the already verified
    checkout revision.
    """

    errors: list[str] = []
    path = root / CODEX_MARKETPLACE_METADATA
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("not_regular")
        if metadata.st_size > MAX_CODEX_MARKETPLACE_METADATA_BYTES:
            raise ValueError("too_large")
        raw = _regular_bytes(path)
        payload = json.loads(raw.decode("utf-8"))
    except FileNotFoundError:
        return {
            "verified": False,
            "error_codes": ["codex_marketplace_metadata_missing"],
        }
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {
            "verified": False,
            "error_codes": ["codex_marketplace_metadata_invalid"],
        }
    expected_keys = {
        "source_type",
        "source",
        "ref_name",
        "sparse_paths",
        "revision",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        errors.append("codex_marketplace_metadata_shape_invalid")
    else:
        if payload.get("source_type") != "git" or not _expected_repo(
            payload.get("source")
        ):
            errors.append("codex_marketplace_metadata_source_mismatch")
        if payload.get("ref_name") != expected_tag:
            errors.append("codex_marketplace_metadata_ref_mismatch")
        if payload.get("sparse_paths") != []:
            errors.append("codex_marketplace_metadata_sparse_paths_not_empty")
        revision = payload.get("revision")
        if (
            expected_revision is None
            or not isinstance(revision, str)
            or revision != expected_revision
        ):
            errors.append("codex_marketplace_metadata_revision_mismatch")
    return {
        "verified": not errors,
        "error_codes": sorted(set(errors)),
        "revision": payload.get("revision") if isinstance(payload, dict) else None,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _manifest_inventory(
    root: Path,
    *,
    exact_git_inventory: bool,
    exact_filesystem_inventory: bool,
    allow_codex_marketplace_metadata: bool = False,
    expected_version: str = VERSION,
    expected_tag: str = TAG,
) -> tuple[bool, list[str], dict[str, str] | None, bytes | None]:
    errors: list[str] = []
    try:
        manifest_bytes = _regular_bytes(root / MANIFEST_NAME)
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False, ["package_manifest_missing_or_invalid"], None, None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False, ["package_manifest_schema_invalid"], None, manifest_bytes
    if payload.get("version") != expected_version:
        errors.append("package_manifest_version_mismatch")
    raw_files = payload.get("files")
    if not isinstance(raw_files, dict) or not raw_files:
        return False, [*errors, "package_manifest_files_invalid"], None, manifest_bytes
    files: dict[str, str] = {}
    for name, digest in raw_files.items():
        if not isinstance(name, str) or not _included(name):
            errors.append("package_manifest_path_unsafe")
            continue
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append("package_manifest_digest_invalid")
            continue
        files[name] = digest
    if len(files) != len(raw_files):
        errors.append("package_manifest_inventory_invalid")
    for name, digest in files.items():
        try:
            actual = hashlib.sha256(_regular_bytes(root / name)).hexdigest()
        except (OSError, ValueError):
            errors.append("package_file_missing_or_unsafe")
            continue
        if actual != digest:
            errors.append("package_file_digest_mismatch")
    if exact_git_inventory:
        safe_env = git_environment()
        git = run_command(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(root),
                "ls-tree",
                "-r",
                "-z",
                "--name-only",
                f"refs/tags/{expected_tag}^{{commit}}",
            ],
            root,
            safe_env,
            10,
        )
        if git.returncode != 0 or git.timed_out:
            errors.append("git_inventory_unavailable")
        else:
            tracked = {
                name
                for name in git.stdout.split("\0")
                if name and _included(name)
            }
            if tracked != set(files):
                errors.append("package_manifest_git_inventory_mismatch")
        tagged_manifest = run_command(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(root),
                "cat-file",
                "blob",
                f"refs/tags/{expected_tag}^{{commit}}:{MANIFEST_NAME}",
            ],
            root,
            safe_env,
            10,
        )
        if tagged_manifest.returncode != 0 or tagged_manifest.timed_out:
            errors.append("release_tag_manifest_unavailable")
        elif tagged_manifest.stdout.encode("utf-8") != manifest_bytes:
            errors.append("package_manifest_not_exact_release_tag")
    if exact_filesystem_inventory:
        codex_metadata_verified = False
        codex_metadata_sha256: str | None = None
        codex_metadata_revision: str | None = None
        if allow_codex_marketplace_metadata:
            safe_env = git_environment()
            head = run_command(
                [
                    "git",
                    "--no-replace-objects",
                    "-C",
                    str(root),
                    "rev-parse",
                    "HEAD",
                ],
                root,
                safe_env,
                10,
            )
            tag = run_command(
                [
                    "git",
                    "--no-replace-objects",
                    "-C",
                    str(root),
                    "rev-parse",
                    f"refs/tags/{expected_tag}^{{commit}}",
                ],
                root,
                safe_env,
                10,
            )
            revision = head.stdout.strip() if head.returncode == 0 else None
            metadata_check = _codex_marketplace_metadata(
                root,
                expected_tag=expected_tag,
                expected_revision=revision
                if tag.returncode == 0 and revision == tag.stdout.strip()
                else None,
            )
            codex_metadata_verified = bool(metadata_check["verified"])
            codex_metadata_sha256 = metadata_check.get("sha256")
            codex_metadata_revision = revision
            errors.extend(metadata_check["error_codes"])
        actual: set[str] = set()
        expected_directories = {
            PurePosixPath(*PurePosixPath(name).parts[:depth]).as_posix()
            for name in files
            for depth in range(1, len(PurePosixPath(name).parts))
        }

        def inspect_directory(directory: Path, relative_parent: PurePosixPath) -> None:
            try:
                with os.scandir(directory) as iterator:
                    entries = sorted(iterator, key=lambda item: item.name)
            except OSError:
                errors.append("package_filesystem_inventory_unavailable")
                return
            for entry in entries:
                relative_path = relative_parent / entry.name
                relative = relative_path.as_posix()
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError:
                    errors.append("package_filesystem_inventory_unavailable")
                    continue
                if stat.S_ISLNK(metadata.st_mode):
                    errors.append("package_filesystem_symlink_not_allowed")
                    continue

                # A verified marketplace snapshot, and some verified installed
                # caches, are full Git checkouts. Their real .git directory is
                # permitted only when the caller also requires exact Git proof.
                if relative == ".git" and exact_git_inventory:
                    if not stat.S_ISDIR(metadata.st_mode):
                        errors.append("package_filesystem_git_metadata_unsafe")
                    continue

                if relative == CODEX_MARKETPLACE_METADATA:
                    if not allow_codex_marketplace_metadata:
                        errors.append("package_filesystem_excluded_path_not_allowed")
                    elif not stat.S_ISREG(metadata.st_mode):
                        errors.append("codex_marketplace_metadata_invalid")
                    else:
                        current_metadata = _codex_marketplace_metadata(
                            root,
                            expected_tag=expected_tag,
                            expected_revision=codex_metadata_revision,
                        )
                        if (
                            not codex_metadata_verified
                            or not current_metadata["verified"]
                            or current_metadata.get("sha256")
                            != codex_metadata_sha256
                        ):
                            errors.append("codex_marketplace_metadata_invalid")
                    continue

                if relative == MANIFEST_NAME:
                    if not stat.S_ISREG(metadata.st_mode):
                        errors.append("package_file_missing_or_unsafe")
                    continue

                if not _included(relative):
                    errors.append("package_filesystem_excluded_path_not_allowed")
                    continue
                if stat.S_ISREG(metadata.st_mode):
                    actual.add(relative)
                    continue
                if stat.S_ISDIR(metadata.st_mode):
                    if relative not in expected_directories:
                        errors.append("package_filesystem_unlisted_directory_not_allowed")
                        continue
                    inspect_directory(Path(entry.path), relative_path)
                    continue
                errors.append("package_filesystem_special_file_not_allowed")

        try:
            root_metadata = root.lstat()
        except OSError:
            errors.append("package_filesystem_inventory_unavailable")
        else:
            if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(
                root_metadata.st_mode
            ):
                errors.append("package_filesystem_root_unsafe")
            else:
                inspect_directory(root, PurePosixPath())
        if actual != set(files):
            errors.append("package_manifest_filesystem_inventory_mismatch")
        if allow_codex_marketplace_metadata:
            final_metadata = _codex_marketplace_metadata(
                root,
                expected_tag=expected_tag,
                expected_revision=codex_metadata_revision,
            )
            if (
                not final_metadata["verified"]
                or final_metadata.get("sha256") != codex_metadata_sha256
            ):
                errors.append("codex_marketplace_metadata_changed_during_verification")
    return not errors, sorted(set(errors)), files, manifest_bytes


def verify_package(
    root: Path,
    *,
    exact_git_inventory: bool = False,
    exact_filesystem_inventory: bool = False,
    allow_codex_marketplace_metadata: bool = False,
    expected_version: str = VERSION,
    expected_tag: str = TAG,
) -> dict[str, Any]:
    ok, errors, files, manifest_bytes = _manifest_inventory(
        root,
        exact_git_inventory=exact_git_inventory,
        exact_filesystem_inventory=exact_filesystem_inventory,
        allow_codex_marketplace_metadata=allow_codex_marketplace_metadata,
        expected_version=expected_version,
        expected_tag=expected_tag,
    )
    return {
        "verified": ok,
        "error_codes": errors,
        "file_count": len(files or {}),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_bytes is not None
        else None,
    }


def verify_release_contract(
    root: Path, *, expected_version: str = VERSION, expected_tag: str = TAG
) -> dict[str, Any]:
    """Verify identities that a hash-consistent but wrong package could violate."""

    errors: list[str] = []
    try:
        version = _regular_bytes(root / "VERSION").decode("utf-8").strip()
    except (OSError, ValueError, UnicodeDecodeError):
        version = None
    if version != expected_version:
        errors.append("version_file_mismatch")
    try:
        plugin = _read_json(root / ".codex-plugin" / "plugin.json")
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        plugin = {}
        errors.append("plugin_manifest_missing_or_invalid")
    if plugin.get("name") != PLUGIN_NAME or plugin.get("version") != expected_version:
        errors.append("plugin_manifest_identity_or_version_mismatch")
    try:
        marketplace = _read_json(root / ".agents" / "plugins" / "marketplace.json")
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        marketplace = {}
        errors.append("marketplace_manifest_missing_or_invalid")
    entries = marketplace.get("plugins")
    entry = entries[0] if isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict) else {}
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    policy = entry.get("policy") if isinstance(entry.get("policy"), dict) else {}
    if (
        marketplace.get("name") != MARKETPLACE_NAME
        or entry.get("name") != PLUGIN_NAME
        or source.get("source") != "url"
        or not _expected_repo(source.get("url"))
        or source.get("ref") != expected_tag
        or policy.get("installation") != "AVAILABLE"
        or policy.get("authentication") != "ON_INSTALL"
        or not isinstance(entry.get("category"), str)
        or not entry.get("category")
    ):
        errors.append("marketplace_manifest_contract_mismatch")
    return {"verified": not errors, "error_codes": sorted(set(errors))}


def _git_source(
    root: Path,
    env: dict[str, str],
    runner: Runner,
    *,
    expected_tag: str = TAG,
    require_codex_marketplace_metadata: bool = False,
) -> dict[str, Any]:
    facts: dict[str, Any] = {"verified": False, "error_codes": []}
    safe_env = git_environment(env)
    head = runner(
        ["git", "--no-replace-objects", "-C", str(root), "rev-parse", "HEAD"],
        root,
        safe_env,
        10,
    )
    tag = runner(
        [
            "git",
            "--no-replace-objects",
            "-C",
            str(root),
            "rev-parse",
            f"refs/tags/{expected_tag}^{{commit}}",
        ],
        root,
        safe_env,
        10,
    )
    status = runner(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        root,
        safe_env,
        10,
    )
    remote = runner(
        [
            "git",
            "--no-replace-objects",
            "-C",
            str(root),
            "config",
            "--local",
            "--no-includes",
            "--get-all",
            "remote.origin.url",
        ],
        root,
        safe_env,
        10,
    )
    if head.returncode != 0:
        facts["error_codes"].append("git_head_unavailable")
    if tag.returncode != 0:
        facts["error_codes"].append("release_tag_missing")
    if head.returncode == 0 and tag.returncode == 0 and head.stdout.strip() != tag.stdout.strip():
        facts["error_codes"].append("head_not_exact_release_tag")
    head_value = head.stdout.strip() if head.returncode == 0 else None
    tag_value = tag.stdout.strip() if tag.returncode == 0 else None
    metadata_check: dict[str, Any] | None = None
    status_allowed = status.returncode == 0 and not bool(status.stdout.strip())
    if require_codex_marketplace_metadata:
        metadata_check = _codex_marketplace_metadata(
            root,
            expected_tag=expected_tag,
            expected_revision=head_value if head_value == tag_value else None,
        )
        facts["error_codes"].extend(metadata_check["error_codes"])
        status_allowed = bool(
            status.returncode == 0
            and metadata_check["verified"]
            and status.stdout.splitlines()
            == [f"?? {CODEX_MARKETPLACE_METADATA}"]
        )
    if status.returncode != 0:
        facts["error_codes"].append("git_status_unavailable")
    elif not status_allowed:
        facts["error_codes"].append("checkout_not_clean")
    raw_origins = [line.strip() for line in remote.stdout.splitlines() if line.strip()]
    origin_matches = (
        remote.returncode == 0
        and not remote.timed_out
        and len(raw_origins) == 1
        and _expected_repo(raw_origins[0])
    )
    if not origin_matches:
        facts["error_codes"].append("origin_not_expected_repository")
    facts["head"] = head_value
    facts["tag"] = expected_tag
    facts["clean"] = status_allowed
    facts["origin_matches"] = origin_matches
    facts["codex_marketplace_metadata"] = metadata_check
    facts["verified"] = not facts["error_codes"]
    return facts


def _codex_home(env: dict[str, str]) -> Path:
    configured = env.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    home = Path(env.get("HOME", str(Path.home()))).expanduser()
    return home / ".codex"


def normalized_codex_environment(
    env: dict[str, str], *, base: Path | None = None
) -> dict[str, str]:
    """Make the effective Codex profile path independent of probe cwd.

    Codex control commands intentionally run from a fresh neutral directory.
    A relative ``CODEX_HOME`` or ``HOME`` would otherwise make our filesystem
    inspection and the Codex subprocess address different profiles.  Normalize
    the selected input once before either operation and pass the same absolute
    value to every probe and mutation.
    """

    environment = dict(env)
    anchor = (base or Path.cwd()).resolve(strict=False)

    def absolute(value: str, *, tilde_home: str) -> Path:
        if value == "~" or value.startswith("~/"):
            configured_home = Path(tilde_home).expanduser()
            suffix = value[2:] if value.startswith("~/") else ""
            candidate = configured_home / suffix
        else:
            candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = anchor / candidate
        return Path(os.path.abspath(os.path.normpath(str(candidate))))

    configured = environment.get("CODEX_HOME")
    if configured:
        environment["CODEX_HOME"] = str(
            absolute(
                configured,
                tilde_home=environment.get("HOME", str(Path.home())),
            )
        )
    else:
        environment["HOME"] = str(
            absolute(
                environment.get("HOME", str(Path.home())),
                tilde_home=str(Path.home()),
            )
        )
    return environment


def _marketplace_source(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("marketplaceSource")
    if not isinstance(source, dict):
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
    return source


def _marketplace_identity_exact(item: dict[str, Any]) -> bool:
    source = _marketplace_source(item)
    source_type = source.get("sourceType", source.get("source_type"))
    raw_source = source.get("source", source.get("url"))
    return source_type == "git" and _expected_repo(raw_source)


def _marketplace_reported_ref(item: dict[str, Any]) -> object:
    return _marketplace_source(item).get("ref")


def _toml_multiline_after_line(line: str, active: str | None) -> str | None:
    """Track TOML multiline strings so embedded fake headers are never parsed."""

    def closing_index(delimiter: str, start: int) -> int | None:
        position = line.find(delimiter, start)
        while position >= 0:
            if delimiter == "'''":
                return position
            backslashes = 0
            cursor = position - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                return position
            position = line.find(delimiter, position + 1)
        return None

    if active is not None:
        return None if closing_index(active, 0) is not None else active

    simple_quote: str | None = None
    index = 0
    while index < len(line):
        character = line[index]
        if simple_quote is not None:
            if simple_quote == '"' and character == "\\":
                index += 2
                continue
            if character == simple_quote:
                simple_quote = None
            index += 1
            continue
        if character == "#":
            break
        delimiter = None
        if line.startswith('"""', index):
            delimiter = '"""'
        elif line.startswith("'''", index):
            delimiter = "'''"
        if delimiter is not None:
            close = closing_index(delimiter, index + 3)
            if close is None:
                return delimiter
            index = close + 3
            continue
        if character in {'"', "'"}:
            simple_quote = character
        index += 1
    return None


def _marketplace_config_evidence(
    codex_home: Path, *, expected_ref: str = TAG
) -> dict[str, Any]:
    """Read only the simple table shape currently emitted by the Codex CLI.

    Python 3.10 has no stdlib TOML parser.  This deliberately narrow parser
    accepts the exact string assignments emitted for one marketplace and fails
    closed on duplicate sections, duplicate keys, multiline/complex values, or
    an unreadable/symlinked config file.  It never edits the user's config.
    """

    errors: list[str] = []
    try:
        text = _regular_bytes(codex_home / "config.toml").decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        return {
            "verified": False,
            "error_codes": ["marketplace_config_missing_or_unreadable"],
            "source_matches": False,
            "ref_matches": False,
        }
    header_pattern = re.compile(r"^\s*\[\s*([^\]]+?)\s*\]\s*(?:#.*)?$")
    assignment_pattern = re.compile(
        r'^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*"([^"\\]*)"\s*(?:#.*)?$'
    )
    section_count = 0
    in_target = False
    multiline: str | None = None
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        if multiline is not None:
            multiline = _toml_multiline_after_line(raw_line, multiline)
            continue
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        header = header_pattern.fullmatch(raw_line)
        if header:
            in_target = header.group(1).strip() == f"marketplaces.{MARKETPLACE_NAME}"
            if in_target:
                section_count += 1
            continue
        if not in_target:
            multiline = _toml_multiline_after_line(raw_line, None)
            continue
        assignment = assignment_pattern.fullmatch(raw_line)
        if assignment is None:
            errors.append("marketplace_config_target_table_shape_invalid")
            multiline = _toml_multiline_after_line(raw_line, None)
            continue
        key, decoded = assignment.groups()
        if key in values:
            errors.append("marketplace_config_duplicate_key")
            continue
        values[key] = decoded
    if multiline is not None:
        errors.append("marketplace_config_unterminated_multiline_value")
    if section_count != 1:
        errors.append("marketplace_config_section_missing_or_duplicate")
    source_matches = (
        values.get("source_type") == "git" and _expected_repo(values.get("source"))
    )
    ref_matches = values.get("ref") == expected_ref
    if not source_matches or not ref_matches:
        errors.append("marketplace_config_source_or_ref_conflict")
    return {
        "verified": not errors,
        "error_codes": sorted(set(errors)),
        "source_matches": source_matches,
        "ref_matches": ref_matches,
    }


def _marketplace_runtime_evidence(
    item: dict[str, Any],
    *,
    source_root: Path,
    env: dict[str, str],
    runner: Runner,
    expected_version: str = VERSION,
    expected_ref: str = TAG,
    require_source_manifest_match: bool = True,
) -> dict[str, Any]:
    """Verify config plus the exact cached checkout, independent of CLI claims."""

    errors: list[str] = []
    codex_home = _codex_home(env)
    expected_root = codex_home / ".tmp" / "marketplaces" / MARKETPLACE_NAME
    reported_root = item.get("root")
    root_matches = False
    cache_root = expected_root
    if isinstance(reported_root, str) and reported_root:
        try:
            cache_root = Path(reported_root).expanduser().resolve(strict=True)
            root_matches = cache_root == expected_root.resolve(strict=True)
        except OSError:
            root_matches = False
    if not root_matches:
        errors.append("marketplace_snapshot_root_missing_or_unexpected")

    config = _marketplace_config_evidence(codex_home, expected_ref=expected_ref)
    errors.extend(config["error_codes"])
    if root_matches:
        git = _git_source(
            cache_root,
            env,
            runner,
            expected_tag=expected_ref,
            require_codex_marketplace_metadata=True,
        )
        package = verify_package(
            cache_root,
            exact_git_inventory=True,
            exact_filesystem_inventory=True,
            allow_codex_marketplace_metadata=True,
            expected_version=expected_version,
            expected_tag=expected_ref,
        )
        release_contract = verify_release_contract(
            cache_root,
            expected_version=expected_version,
            expected_tag=expected_ref,
        )
        errors.extend(f"snapshot_{code}" for code in git["error_codes"])
        errors.extend(f"snapshot_{code}" for code in package["error_codes"])
        errors.extend(
            f"snapshot_{code}" for code in release_contract["error_codes"]
        )
        known_release = KNOWN_OFFICIAL_RELEASES.get(expected_version)
        if known_release is not None:
            if git.get("head") != known_release["revision"]:
                errors.append("snapshot_known_official_revision_mismatch")
            if package.get("manifest_sha256") != known_release["manifest_sha256"]:
                errors.append("snapshot_known_official_manifest_mismatch")
        try:
            same_manifest = _regular_bytes(source_root / MANIFEST_NAME) == _regular_bytes(
                cache_root / MANIFEST_NAME
            )
        except (OSError, ValueError):
            same_manifest = False
        if require_source_manifest_match and not same_manifest:
            errors.append("marketplace_snapshot_manifest_differs_from_source")
    else:
        git = {"verified": False}
        package = {"verified": False}
        release_contract = {"verified": False}
        same_manifest = False
    return {
        "verified": not errors,
        "error_codes": sorted(set(errors)),
        "config": config,
        "root_matches": root_matches,
        "git_verified": bool(git.get("verified")),
        "codex_marketplace_metadata_sha256": (
            git.get("codex_marketplace_metadata", {}).get("sha256")
            if isinstance(git.get("codex_marketplace_metadata"), dict)
            else None
        ),
        "package_verified": bool(package.get("verified")),
        "release_contract_verified": bool(release_contract.get("verified")),
        "manifest_matches_source": same_manifest
        if require_source_manifest_match
        else None,
        "manifest_sha256": package.get("manifest_sha256"),
        "expected_version": expected_version,
        "expected_ref": expected_ref,
    }


def _marketplace_exact(
    item: dict[str, Any], runtime_verified: bool, *, expected_ref: str = TAG
) -> bool:
    if not _marketplace_identity_exact(item) or not runtime_verified:
        return False
    reported_ref = _marketplace_reported_ref(item)
    return reported_ref is None or reported_ref == expected_ref


def _plugin_source_exact(item: dict[str, Any], *, expected_ref: str = TAG) -> bool:
    source = item.get("source")
    return bool(
        isinstance(source, dict)
        and source.get("source") in {"git", "url"}
        and _expected_repo(source.get("url"))
        and source.get("ref") == expected_ref
    )


def _plugin_cache_inventory(
    codex_home: Path, *, expected_version: str
) -> dict[str, Any]:
    """Verify that the installed plugin has one regular version directory only."""

    root = codex_home / "plugins" / "cache" / MARKETPLACE_NAME / PLUGIN_NAME
    try:
        entries = list(root.iterdir())
    except OSError:
        return {
            "verified": False,
            "versions": [],
            "error_codes": ["installed_cache_inventory_unavailable"],
        }
    versions: list[str] = []
    errors: list[str] = []
    for entry in entries:
        try:
            metadata = entry.lstat()
        except OSError:
            errors.append("installed_cache_inventory_unavailable")
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            errors.append("installed_cache_version_entry_unsafe")
            continue
        versions.append(entry.name)
    if sorted(versions) != [expected_version]:
        errors.append("installed_cache_version_set_mismatch")
    return {
        "verified": not errors,
        "versions": sorted(versions),
        "error_codes": sorted(set(errors)),
    }


def inspect_codex_state(
    *, source_root: Path, env: dict[str, str], runner: Runner
) -> dict[str, Any]:
    marketplace_result = run_codex_control(
        ["codex", "plugin", "marketplace", "list", "--json"], env, runner, 30
    )
    plugin_result = run_codex_control(
        ["codex", "plugin", "list", "--available", "--json"],
        env,
        runner,
        30,
    )
    marketplace_payload = _json_output(marketplace_result)
    plugin_payload = _json_output(plugin_result)
    if marketplace_payload is None or plugin_payload is None:
        return {
            "readable": False,
            "error_codes": ["codex_state_json_unavailable"],
            "marketplace": "UNKNOWN",
            "plugin": "UNKNOWN",
            "cache_verified": False,
        }
    marketplaces = marketplace_payload.get("marketplaces")
    installed = plugin_payload.get("installed")
    available = plugin_payload.get("available")
    if not all(isinstance(value, list) for value in (marketplaces, installed, available)):
        return {
            "readable": False,
            "error_codes": ["codex_state_json_shape_invalid"],
            "marketplace": "UNKNOWN",
            "plugin": "UNKNOWN",
            "cache_verified": False,
        }
    if (
        any(
            not isinstance(item, dict) or not isinstance(item.get("name"), str)
            for item in marketplaces
        )
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str)
            or not isinstance(item.get("pluginId"), str)
            for item in [*installed, *available]
        )
    ):
        return {
            "readable": False,
            "error_codes": ["codex_state_json_entry_shape_invalid"],
            "marketplace": "UNKNOWN",
            "plugin": "UNKNOWN",
            "cache_verified": False,
        }
    plugin_matches = [
        item
        for item in [*installed, *available]
        if item.get("name") == PLUGIN_NAME
        or item.get("pluginId") in {PLUGIN_ID, LEGACY_PLUGIN_ID}
        or item.get("pluginId", "").startswith(f"{PLUGIN_NAME}@")
    ]
    installed_matches = [
        item
        for item in installed
        if item in plugin_matches
    ]
    marketplace_matches = [
        item
        for item in marketplaces
        if isinstance(item, dict) and item.get("name") == MARKETPLACE_NAME
    ]
    exact_installed = [item for item in installed_matches if item.get("pluginId") == PLUGIN_ID]
    exact_available = [
        item for item in available if item.get("pluginId") == PLUGIN_ID
    ]
    installed_item = exact_installed[0] if len(exact_installed) == 1 else None
    available_item = exact_available[0] if len(exact_available) == 1 else None
    installed_version = installed_item.get("version") if installed_item else None
    installed_ref = (
        installed_item.get("source", {}).get("ref")
        if installed_item and isinstance(installed_item.get("source"), dict)
        else None
    )
    old_ref = (
        installed_ref
        if _known_official_upgrade(installed_version, installed_ref)
        else None
    )

    marketplace_evidence: dict[str, Any] | None = None
    target_runtime_verified = False
    old_runtime_verified = False
    marketplace_ref_omitted = bool(
        len(marketplace_matches) == 1
        and _marketplace_reported_ref(marketplace_matches[0]) is None
    )
    if len(marketplace_matches) == 1 and _marketplace_identity_exact(
        marketplace_matches[0]
    ):
        evidence_version = installed_version if old_ref else VERSION
        evidence_ref = old_ref or TAG
        marketplace_evidence = _marketplace_runtime_evidence(
            marketplace_matches[0],
            source_root=source_root,
            env=env,
            runner=runner,
            expected_version=str(evidence_version),
            expected_ref=evidence_ref,
            require_source_manifest_match=old_ref is None,
        )
        if old_ref:
            old_runtime_verified = bool(marketplace_evidence["verified"])
        else:
            target_runtime_verified = bool(marketplace_evidence["verified"])

    errors: list[str] = []
    target_marketplace_exact = bool(
        marketplace_matches
        and all(
            _marketplace_exact(
                item, target_runtime_verified, expected_ref=TAG
            )
            for item in marketplace_matches
        )
    )
    old_marketplace_exact = bool(
        old_ref
        and marketplace_matches
        and all(
            _marketplace_exact(
                item, old_runtime_verified, expected_ref=old_ref
            )
            for item in marketplace_matches
        )
    )
    if target_marketplace_exact:
        marketplace_state = "EXACT"
    elif old_marketplace_exact:
        marketplace_state = "OFFICIAL_OLD"
    elif marketplace_matches:
        marketplace_state = "CONFLICT"
    else:
        marketplace_state = "ABSENT"
    legacy = any(item.get("pluginId") == LEGACY_PLUGIN_ID for item in installed_matches)
    if legacy:
        errors.append("legacy_personal_install_requires_manual_migration")
    if len(marketplace_matches) > 1:
        errors.append("duplicate_marketplace_entries")
    if marketplace_matches and marketplace_state == "CONFLICT":
        errors.append("marketplace_source_or_ref_conflict")
    foreign_plugins = [
        item for item in plugin_matches if item.get("pluginId") != PLUGIN_ID
    ]
    if foreign_plugins:
        errors.append("duplicate_or_foreign_plugin_install")
    if len(exact_installed) > 1:
        errors.append("duplicate_exact_plugin_install")
    if len(exact_available) > 1:
        errors.append("duplicate_exact_available_plugin")
    if installed_item is not None and exact_available:
        errors.append("installed_and_available_plugin_duplicate")

    def installed_contract(expected_version: str, expected_ref: str) -> bool:
        return bool(
            installed_item is not None
            and installed_item.get("name") == PLUGIN_NAME
            and installed_item.get("marketplaceName") == MARKETPLACE_NAME
            and installed_item.get("version") == expected_version
            and installed_item.get("installed") is True
            and installed_item.get("enabled") is True
            and installed_item.get("installPolicy") == "AVAILABLE"
            and installed_item.get("authPolicy") == "ON_INSTALL"
            and installed_item.get("scope") in {None, "user"}
            and _plugin_source_exact(installed_item, expected_ref=expected_ref)
        )

    current_installed_contract = installed_contract(VERSION, TAG)
    old_installed_contract = bool(
        isinstance(installed_version, str)
        and isinstance(old_ref, str)
        and installed_contract(installed_version, old_ref)
    )
    official_upgrade_base = bool(
        old_installed_contract
        and old_marketplace_exact
        and len(exact_installed) == 1
        and not exact_available
        and not foreign_plugins
        and len(marketplace_matches) == 1
    )
    if installed_item is not None and not (
        current_installed_contract or official_upgrade_base
    ):
        errors.append("installed_plugin_identity_version_or_source_conflict")
    if installed_item is not None and not (
        (current_installed_contract and marketplace_state == "EXACT")
        or (official_upgrade_base and marketplace_state == "OFFICIAL_OLD")
    ):
        errors.append("installed_plugin_marketplace_missing_or_not_exact")

    available_item_exact = bool(
        available_item is not None
        and available_item.get("name") == PLUGIN_NAME
        and available_item.get("marketplaceName") == MARKETPLACE_NAME
        and (
            available_item.get("version") == VERSION
            or (
                "version" in available_item
                and available_item["version"] is None
                and target_runtime_verified
                and marketplace_ref_omitted
            )
        )
        and available_item.get("installed") is False
        and available_item.get("enabled") is False
        and available_item.get("installPolicy") == "AVAILABLE"
        and available_item.get("authPolicy") == "ON_INSTALL"
        and _plugin_source_exact(available_item)
    )
    if available_item is not None and not available_item_exact:
        errors.append("available_plugin_identity_version_or_source_conflict")
    if marketplace_state == "EXACT" and installed_item is None:
        if available_item is None and not (
            target_runtime_verified and marketplace_ref_omitted
        ):
            errors.append("marketplace_expected_plugin_missing")
        elif not available_item_exact:
            if available_item is not None:
                errors.append("marketplace_expected_plugin_invalid")

    cache_verified = False
    cache_check: dict[str, Any] | None = None
    official_upgrade_ready = False
    if installed_item is not None and not errors:
        codex_home = _codex_home(env)
        cache_version = str(installed_version)
        cache_ref = old_ref or TAG
        cache = codex_home / "plugins" / "cache" / MARKETPLACE_NAME / PLUGIN_NAME / cache_version
        cache_git_present = False
        cache_git_errors: list[str] = []
        cache_git_check: dict[str, Any] | None = None
        try:
            cache_git_metadata = (cache / ".git").lstat()
        except FileNotFoundError:
            pass
        except OSError:
            cache_git_errors.append("installed_cache_git_metadata_unavailable")
        else:
            cache_git_present = True
            if stat.S_ISLNK(cache_git_metadata.st_mode) or not stat.S_ISDIR(
                cache_git_metadata.st_mode
            ):
                cache_git_errors.append("installed_cache_git_metadata_unsafe")
            else:
                cache_git_check = _git_source(
                    cache,
                    env,
                    runner,
                    expected_tag=cache_ref,
                )
                cache_git_errors.extend(
                    f"installed_cache_{code}"
                    for code in cache_git_check["error_codes"]
                )
        package_check = verify_package(
            cache,
            exact_git_inventory=cache_git_present,
            exact_filesystem_inventory=True,
            expected_version=cache_version,
            expected_tag=cache_ref,
        )
        release_check = verify_release_contract(
            cache,
            expected_version=cache_version,
            expected_tag=cache_ref,
        )
        inventory_check = _plugin_cache_inventory(
            codex_home, expected_version=cache_version
        )
        try:
            cache_manifest = _regular_bytes(cache / MANIFEST_NAME)
            source_manifest = _regular_bytes(source_root / MANIFEST_NAME)
            marketplace_manifest = _regular_bytes(
                codex_home
                / ".tmp"
                / "marketplaces"
                / MARKETPLACE_NAME
                / MANIFEST_NAME
            )
            same_manifest = source_manifest == cache_manifest
            same_marketplace_manifest = marketplace_manifest == cache_manifest
        except (OSError, ValueError):
            same_manifest = False
            same_marketplace_manifest = False
        cache_errors = [
            *cache_git_errors,
            *package_check["error_codes"],
            *release_check["error_codes"],
            *inventory_check["error_codes"],
        ]
        if current_installed_contract and not same_manifest:
            cache_errors.append("installed_cache_manifest_differs_from_source")
        if official_upgrade_base and not same_marketplace_manifest:
            cache_errors.append(
                "installed_cache_manifest_differs_from_marketplace_snapshot"
            )
        cache_check = {
            **package_check,
            "verified": not cache_errors,
            "error_codes": sorted(set(cache_errors)),
            "release_contract": release_check,
            "inventory": inventory_check,
            "git": cache_git_check,
            "git_checkout_present": cache_git_present,
            "manifest_matches_source": same_manifest
            if current_installed_contract
            else None,
            "manifest_matches_marketplace_snapshot": same_marketplace_manifest
            if official_upgrade_base
            else None,
        }
        cache_verified = bool(cache_check["verified"])
        if not cache_verified:
            errors.append(
                "official_upgrade_cache_unverified"
                if official_upgrade_base
                else "installed_cache_bytes_unverified"
            )
        elif official_upgrade_base:
            official_upgrade_ready = True

    if official_upgrade_ready and not errors:
        plugin_state = "INSTALLED_ENABLED_OFFICIAL_OLD"
    elif installed_item is not None and not errors:
        plugin_state = "INSTALLED_ENABLED_EXACT"
    elif installed_item is not None:
        plugin_state = "CONFLICT_OR_PARTIAL"
    elif plugin_matches:
        plugin_state = "AVAILABLE_EXACT" if available_item_exact and not errors else "CONFLICT"
    elif marketplace_state == "EXACT" and target_runtime_verified:
        plugin_state = "AVAILABLE_NOT_ENUMERATED"
    else:
        plugin_state = "ABSENT"
    return {
        "readable": True,
        "error_codes": sorted(set(errors)),
        "marketplace": marketplace_state,
        "plugin": plugin_state,
        "cache_verified": cache_verified,
        "cache_check": cache_check,
        "legacy_personal_present": legacy,
        "marketplace_runtime_evidence": marketplace_evidence,
        "official_upgrade": {
            "eligible": official_upgrade_ready and not errors,
            "from_version": installed_version if official_upgrade_ready else None,
            "from_ref": old_ref if official_upgrade_ready else None,
            "to_version": VERSION,
            "to_ref": TAG,
            "scope": installed_item.get("scope", "user")
            if official_upgrade_ready and installed_item is not None
            else None,
        },
    }


def _actions(status: str, hook_hash: str | None) -> list[dict[str, Any]]:
    if status == "READY_FOR_OFFICIAL_UPGRADE":
        return [
            {
                "id": "remove_known_old_official_marketplace",
                "argv": [
                    "codex",
                    "plugin",
                    "marketplace",
                    "remove",
                    MARKETPLACE_NAME,
                    "--json",
                ],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
            {
                "id": "add_exact_git_marketplace",
                "argv": [
                    "codex",
                    "plugin",
                    "marketplace",
                    "add",
                    REPOSITORY,
                    "--ref",
                    TAG,
                    "--json",
                ],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
            {
                "id": "install_exact_plugin",
                "argv": ["codex", "plugin", "add", PLUGIN_ID, "--json"],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
        ]
    if status == "READY_FOR_INSTALL":
        return [
            {
                "id": "add_exact_git_marketplace",
                "argv": [
                    "codex",
                    "plugin",
                    "marketplace",
                    "add",
                    REPOSITORY,
                    "--ref",
                    TAG,
                    "--json",
                ],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
            {
                "id": "install_exact_plugin",
                "argv": ["codex", "plugin", "add", PLUGIN_ID, "--json"],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
        ]
    if status == "READY_FOR_PLUGIN_ADD":
        return [
            {
                "id": "install_exact_plugin",
                "argv": ["codex", "plugin", "add", PLUGIN_ID, "--json"],
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            }
        ]
    if status == "INSTALLED_ENABLED_PENDING_HOOK_TRUST":
        return [
            {
                "id": "start_discovery_task",
                "instruction": "Start a new Codex discovery task so the installed plugin, skills, and Hook definitions load.",
                "mutates_user_config": False,
                "requires_explicit_authorization": False,
            },
            {
                "id": "review_hook_hash",
                "instruction": f"Open /hooks and review the exact hooks/hooks.json SHA-256: {hook_hash}",
                "mutates_user_config": True,
                "requires_explicit_authorization": True,
            },
        ]
    if status == "MIGRATION_REQUIRED":
        return [
            {
                "id": "manual_migration_review",
                "instruction": "Inventory exact installs and back up complete PLUGIN_DATA/Event Ledger plus its HMAC key. Removal, replacement, data adoption, and migration require separate user authorization.",
                "executable": False,
                "requires_separate_authorization": True,
            }
        ]
    return []


def evaluate(
    source_root: Path = SOURCE_ROOT,
    *,
    env: dict[str, str] | None = None,
    runner: Runner = run_command,
    platform_name: str | None = None,
    python_version: tuple[int, int] | None = None,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    environment = normalized_codex_environment(dict(env or os.environ))
    system = platform_name or platform.system()
    py_version = python_version or (sys.version_info.major, sys.version_info.minor)
    errors: list[str] = []
    if system not in SUPPORTED_PLATFORMS:
        errors.append("unsupported_platform_posix_fcntl_required")
    if py_version < MINIMUM_PYTHON:
        errors.append("python_3_10_or_newer_required")

    git_help = runner(["git", "--version"], source_root, environment, 5)
    if git_help.returncode != 0 or git_help.timed_out:
        errors.append("git_unavailable")
    help_probes = {
        "marketplace_add": run_codex_control(
            ["codex", "plugin", "marketplace", "add", "--help"],
            environment,
            runner,
            10,
        ),
        "plugin_add": run_codex_control(
            ["codex", "plugin", "add", "--help"], environment, runner, 10
        ),
        "plugin_list": run_codex_control(
            ["codex", "plugin", "list", "--help"], environment, runner, 10
        ),
        "marketplace_remove": run_codex_control(
            ["codex", "plugin", "marketplace", "remove", "--help"],
            environment,
            runner,
            10,
        ),
    }
    if any(item.returncode != 0 or item.timed_out for item in help_probes.values()):
        errors.append("codex_plugin_cli_unavailable")
    elif not (
        "--ref" in help_probes["marketplace_add"].stdout
        and "--json" in help_probes["marketplace_add"].stdout
        and "--json" in help_probes["plugin_add"].stdout
        and "--available" in help_probes["plugin_list"].stdout
        and "--json" in help_probes["marketplace_remove"].stdout
    ):
        errors.append("codex_plugin_cli_contract_unsupported")

    git = _git_source(source_root, environment, runner) if "git_unavailable" not in errors else {
        "verified": False,
        "error_codes": ["git_unavailable"],
    }
    package = verify_package(source_root, exact_git_inventory=True)
    release_contract = verify_release_contract(source_root)
    errors.extend(git.get("error_codes", []))
    errors.extend(package["error_codes"])
    errors.extend(release_contract["error_codes"])

    codex_state: dict[str, Any]
    if not any(code.startswith("codex_plugin_cli") for code in errors):
        codex_state = inspect_codex_state(
            source_root=source_root, env=environment, runner=runner
        )
        errors.extend(codex_state["error_codes"])
    else:
        codex_state = {
            "readable": False,
            "error_codes": ["codex_state_not_probed"],
            "marketplace": "UNKNOWN",
            "plugin": "UNKNOWN",
            "cache_verified": False,
        }

    conflict_codes = {
        "legacy_personal_install_requires_manual_migration",
        "duplicate_marketplace_entries",
        "marketplace_source_or_ref_conflict",
        "duplicate_or_foreign_plugin_install",
        "duplicate_exact_plugin_install",
        "installed_plugin_identity_version_or_source_conflict",
        "installed_plugin_marketplace_missing_or_not_exact",
        "official_upgrade_cache_unverified",
    }
    unique_errors = sorted(set(errors))
    hard_errors = [code for code in unique_errors if code not in conflict_codes]
    if hard_errors:
        status = "BLOCKED"
    elif any(code in conflict_codes for code in unique_errors):
        status = "MIGRATION_REQUIRED"
    elif codex_state.get("official_upgrade", {}).get("eligible"):
        status = "READY_FOR_OFFICIAL_UPGRADE"
    elif codex_state["plugin"] == "INSTALLED_ENABLED_EXACT" and codex_state["cache_verified"]:
        status = "INSTALLED_ENABLED_PENDING_HOOK_TRUST"
    elif codex_state["marketplace"] == "EXACT":
        status = "READY_FOR_PLUGIN_ADD"
    else:
        status = "READY_FOR_INSTALL"

    try:
        hook_hash = hashlib.sha256(_regular_bytes(source_root / "hooks" / "hooks.json")).hexdigest()
    except (OSError, ValueError):
        hook_hash = None
        if "package_file_missing_or_unsafe" not in unique_errors:
            unique_errors.append("hook_definition_unavailable")
            status = "BLOCKED"
    lifecycle = {
        "source": "VERIFIED"
        if git.get("verified") and package["verified"] and release_contract["verified"]
        else "UNVERIFIED",
        "marketplace": codex_state["marketplace"],
        "installed_enabled": codex_state["plugin"],
        "package_bytes": "VERIFIED" if codex_state["cache_verified"] else "NOT_VERIFIED",
        "hook_trust": "DISCOVERY_TASK_USER_REVIEW_REQUIRED" if status == "INSTALLED_ENABLED_PENDING_HOOK_TRUST" else "NOT_REACHED",
        "heartbeat": "FIRST_TRUSTED_HOOK_AUTO_COMPLETES" if status == "INSTALLED_ENABLED_PENDING_HOOK_TRUST" else "NOT_REACHED",
        "project_bootstrap": "ONE_CONSENT_QUICKSTART_EXACT_TARGET",
        "official_upgrade": codex_state.get("official_upgrade"),
    }
    actions = _actions(status, hook_hash)
    return {
        "schema": "acgm-codex-preflight-v1",
        "ok": status in {
            "READY_FOR_INSTALL",
            "READY_FOR_PLUGIN_ADD",
            "READY_FOR_OFFICIAL_UPGRADE",
            "INSTALLED_ENABLED_PENDING_HOOK_TRUST",
        },
        "status": status,
        "version": VERSION,
        "tag": TAG,
        "platform": {
            "name": system,
            "supported": system in SUPPORTED_PLATFORMS,
            "windows_runtime_supported": False,
        },
        "python": {"version": ".".join(map(str, py_version)), "supported": py_version >= MINIMUM_PYTHON},
        "source": {"git": git, "package": package, "release_contract": release_contract},
        "codex": codex_state,
        "hook_definition_sha256": hook_hash,
        "lifecycle": lifecycle,
        "error_codes": sorted(set(unique_errors)),
        "actions": actions,
        "requires_user_action": bool(actions) or status in {"BLOCKED", "MIGRATION_REQUIRED"},
        "claims": {
            "hook_trusted": False,
            "heartbeat_verified": False,
            "project_bootstrapped": False,
            "provider_or_model_inferred": False,
            "publisher_signature_verified": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    payload = evaluate(args.source_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ACGM for Codex preflight: {payload['status']}")
        for code in payload["error_codes"]:
            print(f"- {code}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
