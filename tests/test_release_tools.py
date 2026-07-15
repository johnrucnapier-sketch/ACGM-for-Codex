from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "scripts" / "generate-package-manifest.py"
SPEC = importlib.util.spec_from_file_location("generate_package_manifest", GENERATOR_PATH)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class ReleaseToolTests(unittest.TestCase):
    def test_current_package_manifest_matches_release_inventory(self) -> None:
        expected = generator.build(ROOT, "auto")
        actual = json.loads((ROOT / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)
        self.assertEqual(actual["version"], "0.1.0-rc.2")
        for required in (
            ".agents/plugins/marketplace.json",
            "AGENTS.md",
            "INSTALL.md",
            "scripts/preflight.py",
            "scripts/bootstrap.py",
            "tests/test_bootstrap.py",
        ):
            self.assertIn(required, actual["files"])

    def test_manifest_paths_are_safe_and_symlinks_are_not_packaged(self) -> None:
        for unsafe in ("", "../escape", "/absolute", "a\\b", "a/./b"):
            self.assertIsNone(generator.safe_relative(unsafe))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (root / "file.txt").write_text("ok\n", encoding="utf-8")
            (root / "link.txt").symlink_to(root / "file.txt")
            payload = generator.build(root, "filesystem")
            self.assertIn("file.txt", payload["files"])
            self.assertNotIn("link.txt", payload["files"])


if __name__ == "__main__":
    unittest.main()
