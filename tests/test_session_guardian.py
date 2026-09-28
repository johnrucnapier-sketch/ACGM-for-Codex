"""Synthetic sessions only; never read the user's transcripts in regression tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess

SPEC = importlib.util.spec_from_file_location("guardian", Path(__file__).resolve().parents[1] / "scripts/session_guardian.py")
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)
STAMP = "2026-09-14T12:00:00Z"
NOW = G.timestamp(STAMP)


class SessionGuardianTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "session.jsonl"
        self.meta = {"type": "session_meta", "payload": {
            "id": "one", "cwd": str(self.root), "cli_version": "0.154.0-alpha.6.2"}}
        self.path.write_text(json.dumps(self.meta) + "\n")
        self.reader = G.RolloutReader("one", self.root)

    def append(self, record):
        with self.path.open("a") as handle:
            handle.write(json.dumps(record) + "\n")

    def metric(self, used=700, window=1000):
        return {"type": "event_msg", "timestamp": STAMP, "payload": {
            "type": "token_count", "info": {"model_context_window": window,
            "last_token_usage": {"total_tokens": used},
            "total_token_usage": {"total_tokens": 99999999}}}}

    def state(self):
        self.reader.poll(self.path)
        return self.reader.status(now=NOW)

    def test_current_cli_captured_metrics_use_last_response(self):
        # Captured from a native 0.158 fixed-Responses session, not hand-invented schema.
        records = json.loads((Path(__file__).parent / 'fixtures/guardian-0.158-metrics.json').read_text())
        records[0]['payload']['cwd'] = str(self.root)
        self.path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        reader = G.RolloutReader('fixture', self.root)
        reader.poll(self.path)
        result = reader.status(now=G.timestamp(records[-1]['timestamp']))
        self.assertEqual(result['state'], 'NORMAL')
        self.assertEqual(result['context_used'], 120)
        self.assertEqual(result['context_window'], 475000)
        self.assertNotEqual(result['context_used'], records[-1]['payload']['info']['total_token_usage']['total_tokens'])

    def test_thresholds_use_last_response_not_cumulative(self):
        for used, expected in [(200, "NORMAL"), (700, "CAUTION"), (820, "CLOSING"), (930, "EMERGENCY")]:
            self.append(self.metric(used))
            self.assertEqual(self.state()["state"], expected)

    def test_no_data_and_invalid_values_are_unknown(self):
        self.assertEqual(self.state()["state"], "UNKNOWN")
        for used in [None, -1, True, "100"]:
            self.append(self.metric(used))
            self.assertEqual(self.state()["state"], "UNKNOWN")

    def test_compaction_budget_can_be_smaller_than_window(self):
        self.append(self.metric(700, 1000))
        self.state()
        result = self.reader.status(now=NOW, compact_limit=800)
        self.assertEqual(result["state"], "CLOSING")
        self.assertEqual(result["remaining_percent"], 12.5)

    def test_stale_and_future_samples_are_unknown(self):
        self.append(self.metric())
        self.state()
        for now in [NOW + 301, NOW - 61]:
            self.assertEqual(self.reader.status(now=now)["state"], "UNKNOWN")

    def test_wrong_thread_project_and_version_refused(self):
        for field, value in [("id", "two"), ("cwd", str(self.root / "other")), ("cli_version", "9.0")]:
            meta = json.loads(json.dumps(self.meta))
            meta["payload"][field] = value
            self.path.write_text(json.dumps(meta) + "\n")
            with self.assertRaises(ValueError):
                G.RolloutReader("one", self.root).poll(self.path)

    def test_wrong_metadata_shape_refused(self):
        for meta in [[], {"payload": []}, {"payload": None}]:
            self.path.write_text(json.dumps(meta) + "\n")
            with self.assertRaises(ValueError):
                G.RolloutReader("one", self.root).poll(self.path)

    def test_handoff_preparation_preserves_dirty_and_untracked_files(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.root), *args], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git("init")
        handoff = self.root / "HANDOFF.md"
        handoff.write_text("A real pending obligation and a user ruling.\n")
        git("add", "HANDOFF.md")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-m", "fixture")
        handoff.write_text(handoff.read_text() + "Uncommitted follow-up.\n")
        before = handoff.read_bytes()
        stamp = handoff.stat().st_mtime_ns
        result = G.prepare(self.root)
        self.assertEqual(result["status"], "DRAFT")
        self.assertIn("HANDOFF.md", result["working_tree"])
        self.assertIn("session.jsonl", result["working_tree"])
        self.assertEqual(handoff.read_bytes(), before)
        self.assertEqual(handoff.stat().st_mtime_ns, stamp)
        self.assertFalse((self.root / "SESSION_HANDOFF.md").exists())

    def test_partial_record_is_retried_without_duplicate_compaction(self):
        self.append(self.metric())
        raw = json.dumps({"type": "compacted", "payload": {}})
        with self.path.open("a") as f:
            f.write(raw[:10])
        self.assertEqual(self.state()["compactions_in_observed_tail"], 0)
        with self.path.open("a") as f:
            f.write(raw[10:] + "\n")
        self.assertEqual(self.state()["state"], "UNKNOWN")
        self.append(self.metric(200))
        self.assertEqual(self.state()["state"], "DEGRADED")
        self.assertEqual(self.state()["compactions_in_observed_tail"], 1)

    def test_latest_usage_record_and_identity(self):
        self.append(self.metric())
        self.append({"type": "token_usage_record", "timestamp": STAMP,
                     "payload": {"thread_id": "one", "usage": {"total_tokens": 850}}})
        self.assertEqual(self.state()["state"], "CLOSING")
        self.append({"type": "token_usage_record", "timestamp": STAMP,
                     "payload": {"thread_id": "other", "usage": {"total_tokens": 950}}})
        self.assertEqual(self.state()["context_used"], 850)

    def test_replacement_resets_metrics(self):
        self.append(self.metric())
        self.state()
        replacement = self.root / "new"
        replacement.write_text(json.dumps(self.meta) + "\n")
        replacement.replace(self.path)
        self.assertEqual(self.state()["state"], "UNKNOWN")

    def test_malformed_record_does_not_claim_health(self):
        self.append(self.metric())
        with self.path.open("a") as f:
            f.write("broken json\n")
        self.assertEqual(self.state()["state"], "UNKNOWN")

    def test_large_history_bootstraps_from_bounded_tail(self):
        with self.path.open("a") as f:
            f.write('x' * (G.READ_BUDGET + G.MAX_LINE) + '\n')
        self.append(self.metric())
        result = self.state()
        self.assertEqual(result["state"], "CAUTION")
        self.assertFalse(result["history_complete"])
        before = self.path.read_bytes()
        offset = self.reader.offset
        self.state()
        self.assertEqual(self.reader.offset, offset)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
