"""Workflow profiles change guidance, never the existing enforcement boundary."""
import json
from unittest import mock
import unittest
import test_runtime as R


class PolicyTests(R.RuntimeTests):
    def configure(self, capability='high-autonomy', profile='auto'):
        self.cli('init', str(self.project), check=True)
        self.complete_assets()
        self.policy_path = self.project / '.governance/decisions/acgm-policy.json'
        self.policy_path.write_text(json.dumps({'schema': 'acgm-workflow-policy-v1',
                                               'capability': capability, 'profile': profile}))
        self.cli('activate', str(self.project), check=True)

    def resolve(self, *args):
        return json.loads(self.cli('policy', '--json', *args, check=True).stdout)

    def test_default_and_explanation_are_read_only(self):
        before = sorted(p.relative_to(self.project) for p in self.project.rglob('*'))
        result = self.resolve('--risk', 'read-only')
        self.assertEqual(result['profile'], 'standard')
        self.assertFalse(result['active'])
        self.assertFalse(self.data.exists())
        self.assertEqual(before, sorted(p.relative_to(self.project) for p in self.project.rglob('*')))

    def test_capability_risk_and_user_floors(self):
        self.configure()
        for risk, expected in [('read-only', 'light'), ('reversible', 'light'),
                               ('unknown', 'standard'), ('service', 'strict'), ('destructive', 'strict')]:
            with self.subTest(risk=risk):
                result = self.resolve('--risk', risk, '--profile', 'light')
                self.assertEqual(result['profile'], expected)
                self.assertEqual(result['hard_core'], 'unchanged')
        self.assertEqual(self.resolve('--risk', 'read-only', '--profile', 'strict')['profile'], 'strict')
        runtime = self.load_runtime_module()
        for capability, expected in [('general', 'standard'), ('limited', 'strict'), ('unknown', 'standard')]:
            with mock.patch.object(runtime, '_workflow_settings', return_value={'capability': capability, 'profile': 'auto'}):
                self.assertEqual(runtime._workflow_policy(self.project, risk='read-only', requested='light', events=[])['profile'], expected)

    def test_project_floor_and_policy_drift_cannot_be_lowered(self):
        self.configure(profile='strict')
        self.assertEqual(self.resolve('--risk', 'read-only', '--profile', 'light')['profile'], 'strict')
        original = self.policy_path.read_bytes()
        self.policy_path.write_text(original.decode().replace('strict', 'light'))
        self.assertEqual(self.cli('policy', '--json').returncode, 2)
        self.assertEqual(self.pre_bash('date')['hookSpecificOutput']['permissionDecision'], 'deny')
        self.policy_path.write_bytes(original)
        self.policy_path.unlink()
        self.assertEqual(self.pre_bash('date')['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_malformed_or_symlinked_policy_is_not_light(self):
        self.configure()
        runtime = self.load_runtime_module()
        for value in ['[]', '{}', 'invalid', json.dumps({'schema': 'acgm-workflow-policy-v1', 'capability': [], 'profile': 'light'})]:
            self.policy_path.write_text(value)
            with self.assertRaises(runtime.RuntimeProblem):
                runtime._workflow_settings(self.project)
        self.policy_path.unlink()
        self.policy_path.symlink_to(self.base / 'missing')
        with self.assertRaises(runtime.RuntimeProblem):
            runtime._workflow_settings(self.project)

    def test_light_does_not_weaken_any_protected_category(self):
        self.configure()
        for command in ['git reset --hard', 'git clean -fd', 'git branch -D old',
                        'git push --force origin main', 'rm -rf cache']:
            with self.subTest(command=command):
                result = self.pre_bash(command)
                self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')
                self.assertIn('operation floor: strict', result['systemMessage'])
        self.pre_bash('rm -rf cache')
        _, arm = self.gate_operation('arm', self.latest_event('gate-denied'))
        self.assertEqual(arm.returncode, 0)
        self.assertIn('consumed', self.pre_bash('rm -rf cache')['systemMessage'])
        self.post_bash('rm -rf cache', response={'exit_code': 0})
        self.assertEqual(self.hook('stop', self.payload('Stop'))[1]['decision'], 'block')

    def test_session_hook_profiles_and_guardian_independence(self):
        self.configure()
        payload = self.payload('SessionStart')
        before = self.hook('session-start', payload)[1]
        self.assertIn('Initial workflow profile: light', before['hookSpecificOutput']['additionalContext'])
        self.assertFalse((self.project / '.acgm/session-guardian.json').exists())
        policy_before = self.resolve('--risk', 'read-only')
        (self.project / '.acgm/session-guardian.json').write_text('{"enabled": true}')
        self.assertEqual(self.resolve('--risk', 'read-only'), policy_before)
        self.assertEqual(self.hook('session-start', payload)[1], before)

    def test_repeated_real_fixed_check_failures_escalate_only_originating_session(self):
        self.configure()
        target = self.base / 'not-a-repository'
        target.mkdir()
        self.pre_bash(f'git -C {target} reset --hard')
        source = self.latest_event('gate-denied')
        for index in range(2):
            _, result = self.gate_operation('arm', source, target=target)
            self.assertEqual(result.returncode, 3, result.stderr)
            profile = self.resolve('--risk', 'read-only', '--session', 'session-sensitive-value')
            self.assertEqual(profile['profile'], 'light' if index == 0 else 'strict')
            command = f"acgm-codex gate arm --event {source['event_id']} --category {source['category']} --target {target}"
            notice = self.post_bash(command, response={})
        self.assertIn('escalated to strict', notice['systemMessage'])
        self.assertNotIn('escalated to strict', self.post_bash(command, response={}).get('systemMessage', ''))
        self.post_bash('date', response={'exit_code': 0})
        self.assertEqual(self.resolve('--risk', 'read-only', '--session', 'session-sensitive-value')['profile'], 'strict')
        self.assertEqual(self.resolve('--risk', 'read-only', '--session', 'different-session')['profile'], 'light')

    def test_unknown_and_ordinary_failures_do_not_escalate(self):
        self.configure()
        for response in [{'exit_code': 1}, {}, {'status': 'approval_denied'}] * 2:
            self.post_bash('test -e missing', response=response)
        self.assertEqual(self.resolve('--risk', 'read-only', '--session', 'session-sensitive-value')['profile'], 'light')

    def test_fixed_check_streak_reset_latch_and_target_scope(self):
        runtime = self.load_runtime_module()
        source = {'event_id': 'source', 'kind': 'gate-denied', 'session_id': 's',
                  'activation_id': 'a', 'target_id': 't', 'category': 'recursive-delete'}
        def result(kind, number, **overrides):
            return dict(source, event_id=str(number), kind=kind, ref_id='source', **overrides)
        failure = result('state-check-failed', 1)
        success = result('state-check-observed', 2)
        self.assertFalse(runtime._workflow_escalated([source, failure, success, result('state-check-failed', 3)], 's'))
        self.assertTrue(runtime._workflow_escalated([source, failure, result('state-check-failed', 3), success], 's'))
        unrelated = dict(failure, event_id='other', target_id='other')
        self.assertFalse(runtime._workflow_escalated([source, failure, unrelated], 's'))
        self.assertFalse(runtime._workflow_escalated([source, failure, result('state-check-failed', 3)], 'another'))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(PolicyTests(name) for name in PolicyTests.__dict__ if name.startswith('test_'))
