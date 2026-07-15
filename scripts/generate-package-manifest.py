#!/usr/bin/env python3
"""Generate or check the deterministic ACGM release byte manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "PACKAGE_MANIFEST.json"
EXCLUDED_PARTS = {
    ".git",
    ".acgm",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
EXCLUDED_NAMES = {MANIFEST_NAME, ".DS_Store"}


def safe_relative(value: str) -> PurePosixPath | None:
    if not value or "\\" in value or "\0" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path if path.as_posix() == value else None


def included(value: str) -> bool:
    path = safe_relative(value)
    return bool(
        path
        and not any(part in EXCLUDED_PARTS for part in path.parts)
        and path.name not in EXCLUDED_NAMES
        and path.suffix != ".pyc"
    )


def git_names(root: Path) -> list[str] | None:
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return [
        item
        for item in completed.stdout.decode("utf-8", "surrogateescape").split("\0")
        if item and included(item)
    ]


def filesystem_names(root: Path) -> list[str]:
    names: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if included(relative) and path.is_file() and not path.is_symlink():
            names.append(relative)
    return names


def discover(root: Path, source: str) -> list[str]:
    if source == "git":
        names = git_names(root)
        if names is None:
            raise RuntimeError("git inventory unavailable")
    elif source == "filesystem":
        names = filesystem_names(root)
    else:
        names = git_names(root) or filesystem_names(root)
    return sorted(set(names))


def read_regular(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"release path is not a regular file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise ValueError(f"release path is not a regular file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read()
        after = os.fstat(descriptor)
        if (
            current.st_size != after.st_size
            or current.st_mtime_ns != after.st_mtime_ns
            or current.st_ctime_ns != after.st_ctime_ns
        ):
            raise ValueError(f"release path changed while reading: {path}")
        return content
    finally:
        os.close(descriptor)


def build(root: Path, source: str) -> dict[str, object]:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    files = {
        name: hashlib.sha256(read_regular(root / name)).hexdigest()
        for name in discover(root, source)
    }
    return {"schema_version": 1, "version": version, "files": files}


def serialize(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source", choices=("auto", "git", "filesystem"), default="auto")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    output = root / MANIFEST_NAME
    content = serialize(build(root, args.source))
    if args.stdout:
        sys.stdout.write(content)
        return 0
    if args.check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError:
            print(f"missing package manifest: {output}", file=sys.stderr)
            return 1
        if current != content:
            print(f"stale package manifest: {output}", file=sys.stderr)
            return 1
        print(f"package manifest is current: {output}")
        return 0
    atomic_write(output, content)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
