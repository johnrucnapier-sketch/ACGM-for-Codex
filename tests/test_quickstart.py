from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import quickstart as one_consent  # noqa: E402


class OneConsentQuickstartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(self.project)], check=True, capture_output=True
        )
        self.source = self.base / "source"
        self.source.mkdir()
        self.environment = os.environ.copy()
        self.environment["ACGM_CODEX_DATA_DIR"] = str(self.base / "plugin-data")
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def install_payload(
        *, dry_run: bool, target: str = "/fixture/codex-home"
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": True,
            "status": "DRY_RUN_PLAN_READY"
            if dry_run
            else "INSTALLED_ENABLED_PENDING_HOOK_TRUST",
            "initial_status": "READY_FOR_INSTALL",
            "version": one_consent.preflight.VERSION,
            "tag": one_consent.preflight.TAG,
            "plan": [
                {"argv": ["codex", "plugin", "marketplace", "add", "fixture"]},
                {"argv": ["codex", "plugin", "add", "acgm-codex@acgm-codex"]},
            ],
            "lifecycle": {"source_verified": True},
            "partial": False,
        }
        authorization_plan = {
            "schema": "acgm-codex-install-authorization-plan-v2",
            "install_target": {
                "schema": "acgm-codex-install-target-v1",
                "logical_path_sha256": hashlib.sha256(
                    target.encode("utf-8")
                ).hexdigest(),
            },
            "status": payload["initial_status"],
            "version": payload["version"],
            "tag": payload["tag"],
            "actions": payload["plan"],
            "lifecycle": payload["lifecycle"],
        }
        payload["authorization_plan"] = authorization_plan
        payload["install_plan_digest"] = (
            one_consent.bootstrap._install_plan_digest(authorization_plan)
        )
        return payload

    def test_combined_dry_run_is_read_only_and_emits_one_digest(self) -> None:
        with mock.patch.object(
            one_consent.bootstrap,
            "execute",
            return_value=self.install_payload(dry_run=True),
        ):
            payload = one_consent.execute(
                self.source,
                self.project,
                dry_run=True,
                authorized=False,
                env=self.environment,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "PLAN_READY")
        self.assertTrue(str(payload["plan_digest"]).startswith("sha256:"))
        self.assertFalse((self.project / "CONSTITUTION.md").exists())
        self.assertFalse((self.project / ".governance").exists())
        self.assertFalse((self.project / ".acgm").exists())

    def test_invalid_explicit_project_returns_blocked_json_without_traceback(self) -> None:
        nested = self.project / "not-the-git-root"
        nested.mkdir()
        output = io.StringIO()
        with mock.patch.object(
            one_consent.bootstrap,
            "execute",
            return_value=self.install_payload(dry_run=True),
        ):
            with contextlib.redirect_stdout(output):
                exit_code = one_consent.main(
                    [
                        "--source-root",
                        str(self.source),
                        "--project",
                        str(nested),
                        "--dry-run",
                        "--json",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "PLAN_BLOCKED")
        self.assertEqual(
            payload["plan"]["project"]["status"], "PROJECT_PLAN_BLOCKED"
        )
        self.assertFalse((self.project / ".acgm").exists())

    def test_one_authorization_installs_then_activates_exact_project(self) -> None:
        calls: list[bool] = []

        def fake_install(*args: object, **kwargs: object) -> dict[str, object]:
            dry_run = bool(kwargs["dry_run"])
            calls.append(dry_run)
            return self.install_payload(dry_run=dry_run)

        with mock.patch.object(one_consent.bootstrap, "execute", side_effect=fake_install):
            with mock.patch.dict(os.environ, self.environment, clear=True):
                prepared = one_consent.plan(
                    self.source, self.project, env=self.environment
                )
                payload = one_consent.execute(
                    self.source,
                    self.project,
                    dry_run=False,
                    authorized=True,
                    expected_digest=str(prepared["plan_digest"]),
                    env=self.environment,
                )

        self.assertEqual(calls, [True, True, False])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "AWAITING_PLATFORM_HOOK_ACCEPTANCE")
        self.assertTrue(payload["claims"]["plugin_install_verified"])
        self.assertTrue(payload["claims"]["project_assets_verified"])
        self.assertTrue(payload["claims"]["project_activated"])
        self.assertTrue((self.project / "CONSTITUTION.md").is_file())
        self.assertTrue((self.project / ".acgm" / "codex.json").is_file())

    def test_combined_apply_passes_exact_install_digest_to_mutating_bootstrap(
        self,
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_install(*args: object, **kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return self.install_payload(dry_run=bool(kwargs["dry_run"]))

        with mock.patch.object(
            one_consent.bootstrap, "execute", side_effect=fake_install
        ):
            with mock.patch.object(
                one_consent.acgm_codex,
                "_apply_quickstart",
                return_value={
                    "ok": True,
                    "complete": False,
                    "partial": False,
                    "status": "AWAITING_PLATFORM_HOOK_ACCEPTANCE",
                    "claims": {},
                    "pending_actions": [],
                },
            ):
                prepared = one_consent.plan(
                    self.source, self.project, env=self.environment
                )
                result = one_consent.execute(
                    self.source,
                    self.project,
                    dry_run=False,
                    authorized=True,
                    expected_digest=str(prepared["plan_digest"]),
                    env=self.environment,
                )

        self.assertTrue(result["ok"])
        mutating = [call for call in calls if not bool(call["dry_run"])]
        self.assertEqual(len(mutating), 1)
        self.assertEqual(
            mutating[0]["expected_plan_digest"],
            prepared["install"]["install_plan_digest"],
        )

    def test_install_state_race_is_reported_stale_before_project_mutation(self) -> None:
        dry_payload = self.install_payload(dry_run=True)
        stale_payload = self.install_payload(dry_run=False)
        stale_payload.update(
            {
                "ok": False,
                "status": "INSTALL_PLAN_STALE",
                "commands_run": [],
            }
        )
        with mock.patch.object(
            one_consent.bootstrap,
            "execute",
            side_effect=[dry_payload, dry_payload, stale_payload],
        ) as installer:
            with mock.patch.object(
                one_consent.acgm_codex, "_apply_quickstart"
            ) as project_apply:
                prepared = one_consent.plan(
                    self.source, self.project, env=self.environment
                )
                result = one_consent.execute(
                    self.source,
                    self.project,
                    dry_run=False,
                    authorized=True,
                    expected_digest=str(prepared["plan_digest"]),
                    env=self.environment,
                )

        self.assertEqual(result["status"], "INSTALL_PLAN_STALE")
        self.assertFalse(result["ok"])
        self.assertEqual(installer.call_count, 3)
        self.assertEqual(
            installer.call_args_list[-1].kwargs["expected_plan_digest"],
            prepared["install"]["install_plan_digest"],
        )
        project_apply.assert_not_called()
        self.assertFalse((self.project / ".acgm").exists())

    def test_changed_project_invalidates_digest_before_install_mutation(self) -> None:
        dry_payload = self.install_payload(dry_run=True)
        with mock.patch.object(
            one_consent.bootstrap, "execute", return_value=dry_payload
        ) as installer:
            prepared = one_consent.plan(
                self.source, self.project, env=self.environment
            )
            (self.project / "README.md").write_text(
                "state changed after authorization\n", encoding="utf-8"
            )
            result = one_consent.execute(
                self.source,
                self.project,
                dry_run=False,
                authorized=True,
                expected_digest=str(prepared["plan_digest"]),
                env=self.environment,
            )

        self.assertEqual(result["status"], "PLAN_STALE")
        self.assertTrue(all(call.kwargs["dry_run"] for call in installer.call_args_list))
        self.assertFalse((self.project / ".acgm").exists())

    def test_changed_codex_home_invalidates_combined_digest_before_mutation(
        self,
    ) -> None:
        first = self.install_payload(
            dry_run=True, target="/fixture/first-codex-home"
        )
        second = self.install_payload(
            dry_run=True, target="/fixture/second-codex-home"
        )
        with mock.patch.object(
            one_consent.bootstrap, "execute", side_effect=[first, second]
        ) as installer:
            prepared = one_consent.plan(
                self.source, self.project, env=self.environment
            )
            result = one_consent.execute(
                self.source,
                self.project,
                dry_run=False,
                authorized=True,
                expected_digest=str(prepared["plan_digest"]),
                env=self.environment,
            )

        self.assertEqual(result["status"], "PLAN_STALE")
        self.assertEqual(installer.call_count, 2)
        self.assertTrue(all(call.kwargs["dry_run"] for call in installer.call_args_list))
        self.assertFalse((self.project / ".acgm").exists())

    def test_changed_official_upgrade_origin_invalidates_combined_digest(self) -> None:
        rc4 = self.install_payload(dry_run=True)
        rc4["initial_status"] = "READY_FOR_OFFICIAL_UPGRADE"
        rc4["lifecycle"] = {
            "official_upgrade": {
                "from_version": "0.1.0-rc.4",
                "from_ref": "v0.1.0-rc.4",
                "to_version": one_consent.preflight.VERSION,
                "to_ref": one_consent.preflight.TAG,
            }
        }
        rc4["authorization_plan"]["lifecycle"] = rc4["lifecycle"]
        rc4["install_plan_digest"] = one_consent.bootstrap._install_plan_digest(
            rc4["authorization_plan"]
        )
        rc3 = self.install_payload(dry_run=True)
        rc3["initial_status"] = "READY_FOR_OFFICIAL_UPGRADE"
        rc3["lifecycle"] = {
            "official_upgrade": {
                "from_version": "0.1.0-rc.3",
                "from_ref": "v0.1.0-rc.3",
                "to_version": one_consent.preflight.VERSION,
                "to_ref": one_consent.preflight.TAG,
            }
        }
        rc3["authorization_plan"]["lifecycle"] = rc3["lifecycle"]
        rc3["install_plan_digest"] = one_consent.bootstrap._install_plan_digest(
            rc3["authorization_plan"]
        )
        with mock.patch.object(
            one_consent.bootstrap, "execute", side_effect=[rc4, rc3]
        ) as installer:
            prepared = one_consent.plan(
                self.source, self.project, env=self.environment
            )
            result = one_consent.execute(
                self.source,
                self.project,
                dry_run=False,
                authorized=True,
                expected_digest=str(prepared["plan_digest"]),
                env=self.environment,
            )

        self.assertEqual(result["status"], "PLAN_STALE")
        self.assertEqual(installer.call_count, 2)
        self.assertTrue(all(call.kwargs["dry_run"] for call in installer.call_args_list))
        self.assertFalse((self.project / ".acgm").exists())

    def test_authorized_apply_without_plan_digest_stops_before_install_mutation(self) -> None:
        with mock.patch.object(
            one_consent.bootstrap,
            "execute",
            return_value=self.install_payload(dry_run=True),
        ) as installer:
            result = one_consent.execute(
                self.source,
                self.project,
                dry_run=False,
                authorized=True,
                env=self.environment,
            )

        self.assertEqual(result["status"], "PLAN_DIGEST_REQUIRED")
        self.assertTrue(all(call.kwargs["dry_run"] for call in installer.call_args_list))
        self.assertFalse((self.project / ".acgm").exists())

    def test_project_failure_after_verified_install_is_reported_as_partial(self) -> None:
        def fake_install(*args: object, **kwargs: object) -> dict[str, object]:
            return self.install_payload(dry_run=bool(kwargs["dry_run"]))

        with mock.patch.object(one_consent.bootstrap, "execute", side_effect=fake_install):
            with mock.patch.object(
                one_consent.acgm_codex,
                "_apply_quickstart",
                return_value={
                    "ok": False,
                    "complete": False,
                    "partial": False,
                    "status": "PROJECT_ASSET_CONFLICT",
                    "claims": {},
                },
            ):
                prepared = one_consent.plan(
                    self.source, self.project, env=self.environment
                )
                payload = one_consent.execute(
                    self.source,
                    self.project,
                    dry_run=False,
                    authorized=True,
                    expected_digest=str(prepared["plan_digest"]),
                    env=self.environment,
                )

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["status"], "PROJECT_RECHECK_REQUIRED")
        self.assertEqual(
            payload["project_result"]["status"], "PROJECT_ASSET_CONFLICT"
        )
        self.assertTrue(payload["pending_actions"])

    def test_any_prewrite_project_failure_after_install_maps_to_recheck(self) -> None:
        def fake_install(*args: object, **kwargs: object) -> dict[str, object]:
            return self.install_payload(dry_run=bool(kwargs["dry_run"]))

        for project_status in (
            "PLAN_STALE",
            "PROJECT_ASSET_CONFLICT",
            "AUTHORIZATION_REQUIRED",
        ):
            with self.subTest(project_status=project_status):
                with mock.patch.object(
                    one_consent.bootstrap, "execute", side_effect=fake_install
                ):
                    with mock.patch.object(
                        one_consent.acgm_codex,
                        "_apply_quickstart",
                        return_value={
                            "ok": False,
                            "complete": False,
                            "partial": False,
                            "status": project_status,
                            "claims": {},
                        },
                    ):
                        prepared = one_consent.plan(
                            self.source, self.project, env=self.environment
                        )
                        payload = one_consent.execute(
                            self.source,
                            self.project,
                            dry_run=False,
                            authorized=True,
                            expected_digest=str(prepared["plan_digest"]),
                            env=self.environment,
                        )

                self.assertFalse(payload["ok"])
                self.assertTrue(payload["partial"])
                self.assertTrue(payload["claims"]["plugin_install_verified"])
                self.assertEqual(payload["status"], "PROJECT_RECHECK_REQUIRED")
                self.assertEqual(payload["project_result"]["status"], project_status)
                self.assertTrue(payload["pending_actions"])

    def test_midapply_project_partial_retains_precise_recheck_status(self) -> None:
        def fake_install(*args: object, **kwargs: object) -> dict[str, object]:
            return self.install_payload(dry_run=bool(kwargs["dry_run"]))

        project_result = {
            "ok": False,
            "complete": False,
            "partial": True,
            "status": "PARTIAL_RECHECK_REQUIRED",
            "claims": {"project_assets_verified": False},
            "pending_actions": ["Inspect the partial project receipt."],
        }
        with mock.patch.object(
            one_consent.bootstrap, "execute", side_effect=fake_install
        ):
            with mock.patch.object(
                one_consent.acgm_codex,
                "_apply_quickstart",
                return_value=project_result,
            ):
                prepared = one_consent.plan(
                    self.source, self.project, env=self.environment
                )
                payload = one_consent.execute(
                    self.source,
                    self.project,
                    dry_run=False,
                    authorized=True,
                    expected_digest=str(prepared["plan_digest"]),
                    env=self.environment,
                )

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["status"], "PARTIAL_RECHECK_REQUIRED")
        self.assertEqual(payload["project_result"], project_result)
        self.assertEqual(
            payload["pending_actions"], ["Inspect the partial project receipt."]
        )

    def test_project_change_during_verified_install_maps_to_recheck(self) -> None:
        def fake_install(*args: object, **kwargs: object) -> dict[str, object]:
            dry_run = bool(kwargs["dry_run"])
            if not dry_run:
                (self.project / "changed-during-install.txt").write_text(
                    "project changed after plugin install\n", encoding="utf-8"
                )
            return self.install_payload(dry_run=dry_run)

        with mock.patch.object(
            one_consent.bootstrap, "execute", side_effect=fake_install
        ):
            prepared = one_consent.plan(
                self.source, self.project, env=self.environment
            )
            payload = one_consent.execute(
                self.source,
                self.project,
                dry_run=False,
                authorized=True,
                expected_digest=str(prepared["plan_digest"]),
                env=self.environment,
            )

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["partial"])
        self.assertTrue(payload["claims"]["plugin_install_verified"])
        self.assertEqual(payload["status"], "PROJECT_RECHECK_REQUIRED")
        self.assertEqual(payload["project_result"]["status"], "PLAN_STALE")
        self.assertTrue(payload["pending_actions"])

    def test_project_replan_exception_after_install_returns_explicit_partial_state(
        self,
    ) -> None:
        def fake_install(*args: object, **kwargs: object) -> dict[str, object]:
            return self.install_payload(dry_run=bool(kwargs["dry_run"]))

        for exception in (
            one_consent.acgm_codex.RuntimeProblem(
                "quickstart requires an explicit Git repository root"
            ),
            OSError("project directory became unreadable"),
        ):
            with self.subTest(exception=type(exception).__name__):
                with mock.patch.object(
                    one_consent.bootstrap, "execute", side_effect=fake_install
                ) as installer:
                    prepared = one_consent.plan(
                        self.source, self.project, env=self.environment
                    )
                    with mock.patch.object(
                        one_consent.acgm_codex,
                        "_apply_quickstart",
                        side_effect=exception,
                    ):
                        payload = one_consent.execute(
                            self.source,
                            self.project,
                            dry_run=False,
                            authorized=True,
                            expected_digest=str(prepared["plan_digest"]),
                            env=self.environment,
                        )

                self.assertEqual(installer.call_count, 3)
                self.assertFalse(payload["ok"])
                self.assertFalse(payload["complete"])
                self.assertTrue(payload["partial"])
                self.assertEqual(payload["status"], "PROJECT_RECHECK_REQUIRED")
                self.assertTrue(payload["claims"]["plugin_install_verified"])
                self.assertEqual(
                    payload["project_result"]["status"],
                    "PROJECT_RECHECK_REQUIRED",
                )
                self.assertTrue(payload["project_result"]["partial"])


if __name__ == "__main__":
    unittest.main()
