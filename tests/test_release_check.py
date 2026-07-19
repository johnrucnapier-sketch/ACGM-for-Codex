from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_check  # noqa: E402


class ReleaseCheckTests(unittest.TestCase):
    def test_run_uses_the_explicit_timeout_budget(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["fixture"], returncode=0, stdout="ok\n", stderr=""
        )
        with mock.patch.object(
            release_check.subprocess, "run", return_value=completed
        ) as runner:
            result = release_check.run(
                "fixture", ["fixture"], timeout_seconds=321
            )

        self.assertTrue(result["ok"])
        self.assertEqual(runner.call_args.kwargs["timeout"], 321)

    def test_full_unittest_budget_exceeds_the_observed_suite_duration(self) -> None:
        self.assertGreaterEqual(release_check.UNITTEST_TIMEOUT_SECONDS, 240)
        self.assertLess(
            release_check.DEFAULT_CHECK_TIMEOUT_SECONDS,
            release_check.UNITTEST_TIMEOUT_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
