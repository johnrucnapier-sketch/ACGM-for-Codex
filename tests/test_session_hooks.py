"""Test the confirmed lifecycle policy, independently from the user's live state."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import io
from test_session_guardian import G

ROOT = Path(__file__).resolve().parents[1]
N = dict(vars(G))
exec(compile((ROOT / "scripts/session_hooks.py").read_text(), "session_hooks.py", "exec"), N)
POLICY = {"schema": "acgm-session-policy-v1", "enabled": True,
          "raw_window": 500000, "compact_limit": 450000,
          "handoff_reserve": 40000, "reaction_margin": 20000}


class LifecycleTests(unittest.TestCase):
    def evaluate(self, event, used, state=None, **extra):
        payload = {"hook_event_name": event, "turn_id": "turn-one", **extra}
        return N["evaluate_hook"](payload, POLICY,
            {"context_used": used, "context_window": 475000}, state if state is not None else {})

    def test_35_and_20_are_footer_advice_not_blocks(self):
        for used in [310000, 381000]:
            result = self.evaluate("UserPromptSubmit", used, prompt="continue implementing")
            self.assertNotIn("decision", result)
            self.assertIn("最终回复末尾", result["hookSpecificOutput"]["additionalContext"])

    def test_buffer_gate_precedes_ten_percent(self):
        result = self.evaluate("UserPromptSubmit", 391000, prompt="new feature")
        self.assertEqual(result["decision"], "block")
        self.assertGreater((1 - 391000 / 475000) * 100, 10)

    def test_only_user_prompt_grants_one_turn(self):
        state = {}
        self.evaluate("UserPromptSubmit", 391000, state, prompt="ACGM 继续一次\nfinish one small change")
        self.assertEqual(state["allowed_turn"], "turn-one")
        self.assertEqual(self.evaluate("PreToolUse", 391000, state, tool_name="Bash"), {})
        denied = self.evaluate("PreToolUse", 411000, state, tool_name="Bash")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        # Grant cannot carry over to a later user request.
        self.assertEqual(self.evaluate("UserPromptSubmit", 391000, state, prompt="another task")["decision"], "block")
        self.assertNotIn("allowed_turn", state)

    def test_handoff_grant_does_not_depend_on_keywords_in_tool_input(self):
        state = {}
        denied = self.evaluate("PreToolUse", 400000, state, tool_name="Bash",
                               tool_input={"command": "echo 'ACGM 交接'"})
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.evaluate("UserPromptSubmit", 400000, state, prompt="ACGM 交接")
        self.assertEqual(self.evaluate("PreToolUse", 425000, state, tool_name="apply_patch"), {})

    def test_auto_compaction_stops_even_without_metrics(self):
        result = self.evaluate("PreCompact", None, trigger="auto")
        self.assertIs(result["continue"], False)
        self.assertEqual(self.evaluate("PreCompact", 450000, trigger="manual"), {})

    def test_recovery_allows_exactly_one_compaction_in_same_session(self):
        state = {}
        self.evaluate('UserPromptSubmit', None, state, prompt='ACGM 恢复会话')
        self.assertFalse(self.evaluate('PreCompact', None, {}, trigger='auto', turn_id='other')['continue'])
        allowed = self.evaluate('PreCompact', None, state, trigger='auto', turn_id='next')
        self.assertNotIn('continue', allowed)
        self.assertFalse(self.evaluate('PreCompact', None, state, trigger='auto')['continue'])
        self.assertEqual(self.evaluate('PreToolUse', 460000, state, tool_name='Bash', turn_id='next'), {})
        self.evaluate('UserPromptSubmit', 410000, state, prompt='new task', turn_id='next')
        self.assertNotIn('handoff_turn', state)
        self.assertFalse(self.evaluate('PreCompact', None, state, trigger='auto', turn_id='next')['continue'])

    def test_recovery_expires_and_never_arms_from_assistant_text(self):
        state = {}
        self.evaluate('UserPromptSubmit', None, state, prompt='ACGM 恢复会话')
        with patch.object(N['time'], 'time', return_value=state['recovery_until'] + 1):
            self.assertFalse(self.evaluate('PreCompact', None, state, trigger='auto')['continue'])
        fresh = {}
        self.evaluate('PreToolUse', 400000, fresh, tool_name='Bash',tool_input={'command':"echo 'ACGM 恢复会话'"})
        self.assertNotIn('recovery_turn', fresh)

    def test_recovery_is_not_granted_by_embedded_or_tool_text(self):
        for prompt in ['说明 ACGM 恢复会话', 'ACGM 恢复会话\n执行删除']:
            state = {}
            self.evaluate('UserPromptSubmit', 410000, state, prompt=prompt)
            self.assertNotIn('recovery_turn', state)
        self.assertIn('核对', N['evaluate_hook']({'hook_event_name':'SessionStart','source':'compact'}, POLICY, {}, {})['hookSpecificOutput']['additionalContext'])

    def test_unflushed_or_reverted_rollout_does_not_reject_user_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript = root / 'rollout.jsonl'
            for content in [None, '', '{"unfinished":', json.dumps({'type':'session_meta','payload':{'id':'other','cwd':tmp,'cli_version':'0.159.2'}})+'\n']:
                if content is not None:
                    transcript.write_text(content)
                payload = {'hook_event_name':'UserPromptSubmit','cwd':tmp,'session_id':'fixture',
                           'turn_id':'first','transcript_path':str(transcript),'prompt':'Read README'}
                output = io.StringIO()
                with patch.dict(N, policy_for=lambda _: POLICY), patch.dict(os.environ, PLUGIN_DATA=tmp), patch('sys.stdin', io.StringIO(json.dumps(payload))), patch('sys.stdout', output):
                    N['hook_main']()
                result = json.loads(output.getvalue())
                self.assertNotIn('decision', result)
                self.assertIn('UNKNOWN', result['hookSpecificOutput']['additionalContext'])

    def test_unknown_measurement_tools_warn_once_but_do_not_disable_safety_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {'hook_event_name':'PreToolUse','cwd':tmp,'session_id':'fixture','turn_id':'one','tool_name':'Bash'}
            def run():
                output = io.StringIO()
                with patch.dict(N, policy_for=lambda _: POLICY), patch.dict(os.environ, PLUGIN_DATA=tmp), patch('sys.stdin', io.StringIO(json.dumps(payload))), patch('sys.stdout', output): N['hook_main']()
                return json.loads(output.getvalue())
            self.assertIn('UNKNOWN',run()['hookSpecificOutput']['additionalContext'])
            self.assertEqual(run(), {})

    def test_recovery_hook_survives_missing_rollout_but_not_bad_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {'hook_event_name':'UserPromptSubmit','cwd':tmp,'session_id':'fixture',
                       'turn_id':'recovery','prompt':'ACGM 恢复会话'}
            def run(policy):
                output = io.StringIO()
                with patch.dict(N, policy_for=policy), patch.dict(os.environ, PLUGIN_DATA=tmp), patch('sys.stdin', io.StringIO(json.dumps(payload))), patch('sys.stdout', output):
                    N['hook_main']()
                return json.loads(output.getvalue())
            self.assertNotIn('decision', run(lambda _: POLICY))
            payload.update(hook_event_name='PreCompact', trigger='auto')
            self.assertNotIn('continue', run(lambda _: POLICY))
            self.assertFalse(run(lambda _: POLICY)['continue'])
            payload.update(hook_event_name='UserPromptSubmit')
            def broken(_): raise ValueError('bad policy')
            self.assertEqual(run(broken)['decision'], 'block')

    def test_stop_never_forces_more_generation(self):
        state = {}
        first = self.evaluate("Stop", 381000, state)
        self.assertIn("systemMessage", first)
        self.assertNotIn("decision", first)
        self.assertEqual(self.evaluate("Stop", 381000, state), {})

    def test_continue_refused_when_handoff_reserve_exhausted(self):
        result = self.evaluate("UserPromptSubmit", 411000, prompt="ACGM 继续一次")
        self.assertEqual(result["decision"], "block")

    def test_pending_prompt_counts_against_reserve(self):
        result = self.evaluate("UserPromptSubmit", 380000, prompt="字" * 11000)
        self.assertEqual(result["decision"], "block")

    def test_smaller_actual_window_never_bypasses_gate(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "new task", "turn_id": "t"}
        metrics = {"context_used": 210000, "context_window": 258400}
        state = {}
        first = N["evaluate_hook"](payload, POLICY, metrics, state)
        self.assertIn("窗口迁移核验轮", first["hookSpecificOutput"]["additionalContext"])
        denied = N["evaluate_hook"]({"hook_event_name":"PreToolUse", "turn_id":"t", "tool_name":"Bash"}, POLICY, metrics, state)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        payload['turn_id'] = 'next'
        result = N["evaluate_hook"](payload, POLICY, metrics, state)
        self.assertEqual(result["decision"], "block")
        self.assertIn("实际窗口", result["reason"])

    def test_handoff_does_not_repeat_begin_handoff_notices(self):
        state = {}
        self.evaluate('UserPromptSubmit', 410000, state, prompt='ACGM 交接')
        self.assertEqual(self.evaluate('PostToolUse', 420000, state), {})
        self.assertEqual(self.evaluate('Stop', 420000, state), {})

    def test_blocked_authorization_reaches_handoff_as_unexecuted_request(self):
        state = {}
        self.evaluate('UserPromptSubmit', 410000, state, prompt='确认安装指定的新版本')
        reply = self.evaluate('UserPromptSubmit', 410000, state, prompt='ACGM 交接')
        text = reply['hookSpecificOutput']['additionalContext']
        self.assertIn('确认安装指定的新版本',text)
        self.assertIn('不得把未执行写成未授权',text)
        self.assertNotIn('allowed_turn', state)

    def test_request_buffer_is_bounded_and_overflow_is_explicit(self):
        state = {}
        for i in range(12):
            self.evaluate('UserPromptSubmit', 420000, state, prompt='字'*5000, turn_id=str(i))
        self.assertEqual(len(state['pending_requests']),4)
        self.assertTrue(state['pending_overflow'])
        self.assertTrue(all(x['truncated'] and len(x['text'])==2000 for x in state['pending_requests']))

    def test_built_hook_runs_opted_in_and_leaves_unrelated_projects_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
            package = root / "package"
            subprocess.run(["python3", str(ROOT / "scripts/build_session_trial.py"), str(package)], check=True, capture_output=True)
            hooks = json.loads((package / "hooks/hooks.json").read_text())["hooks"]
            command = hooks["PreCompact"][0]["hooks"][0]["command"]
            payload = {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(root)}
            def run():
                result = subprocess.run(command, shell=True, input=json.dumps(payload), text=True,
                    capture_output=True, env={**os.environ, "PLUGIN_ROOT": str(package)})
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            self.assertEqual(run(), {})
            (root / ".acgm").mkdir()
            (root / ".acgm/session-guardian.json").write_text(json.dumps(POLICY))
            self.assertFalse(run()["continue"])
            # Integrity binding refuses a changed runtime rather than executing it.
            with (package / "scripts/session_runtime.py").open("a") as f:
                f.write("\nraise RuntimeError('should not execute')\n")
            result = subprocess.run(command, shell=True, input=json.dumps(payload), text=True,
                capture_output=True, env={**os.environ, "PLUGIN_ROOT": str(package)})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("integrity mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
