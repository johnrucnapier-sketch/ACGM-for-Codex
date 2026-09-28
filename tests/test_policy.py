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

    def test_project_records_resume_without_reactivation_or_losing_obligations(self):
        self.configure()
        # Resolve the actual state path instead of assuming its public filename.
        state = self.load_runtime_module()._state_path(self.project)
        baseline = state.read_bytes()
        self.pre_bash('rm -rf cache')
        _, arm = self.gate_operation('arm', self.latest_event('gate-denied'))
        self.assertEqual(arm.returncode, 0)
        self.pre_bash('rm -rf cache')
        self.post_bash('rm -rf cache', response={'exit_code': 0})
        for folder in ('decisions', 'snapshots'):
            (self.project / '.governance' / folder / 'continuity.md').write_text(
                '# Project continuity\nKeep the agreed API; migration validation remains unfinished.\n')
        (self.project / '.governance/OPEN_THREADS.md').write_text('Unresolved migration verification.\n')
        output = self.hook('session-start', self.payload('SessionStart', session_id='resumed'))[1]
        context = output['hookSpecificOutput']['additionalContext']
        self.assertIn('records changed', context)
        self.assertIn('verification obligation(s) remain unresolved', context)
        self.assertEqual(self.pre_bash('pwd'), {})
        self.assertEqual(self.pre_bash('git status --short'), {})
        self.assertEqual(state.read_bytes(), baseline)
        self.assertEqual(self.pre_bash('git reset --hard')['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(self.hook('stop', self.payload('Stop'))[1]['decision'], 'block')

    def test_record_edit_and_delete_are_advisory_but_policy_changes_are_not(self):
        self.configure()
        record = self.project / '.governance/decisions/note.md'
        for operation in ('add', 'edit', 'delete'):
            if operation == 'delete': record.unlink()
            else: record.write_text('# Reviewed project record\n' + operation)
            self.assertEqual(self.pre_bash('pwd'), {})
        self.policy_path.write_text(self.policy_path.read_text().replace('high-autonomy', 'limited'))
        self.assertEqual(self.pre_bash('pwd')['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_record_symlinks_and_non_markdown_policy_fail_closed(self):
        self.configure()
        record = self.project / '.governance/decisions/link.md'
        record.symlink_to(self.project / 'CONSTITUTION.md')
        self.assertEqual(self.pre_bash('pwd')['hookSpecificOutput']['permissionDecision'], 'deny')
        record.unlink()
        unknown = self.project / '.governance/decisions/permissions.json'
        unknown.write_text('{}')
        self.assertEqual(self.pre_bash('pwd')['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_withdrawn_advisory_fields_cannot_relax_gate(self):
        self.configure()
        runtime = self.load_runtime_module()
        original = json.loads(self.policy_path.read_text())
        for extra in ({'enforcement': 'advisory'}, {'advisory_paths': ['cache']}):
            with self.subTest(extra=extra):
                self.policy_path.write_text(json.dumps(dict(original, **extra)))
                with self.assertRaises(runtime.RuntimeProblem):
                    runtime._workflow_settings(self.project)
                result = self.pre_bash('/bin/rm -rf -- cache')
                self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

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
        self.assertEqual(before, {})
        self.assertFalse((self.project / '.acgm/session-guardian.json').exists())
        policy_before = self.resolve('--risk', 'read-only')
        (self.project / '.acgm/session-guardian.json').write_text('{"enabled": true}')
        self.assertEqual(self.resolve('--risk', 'read-only'), policy_before)
        self.assertEqual(self.hook('session-start', payload)[1], before)

    def test_explicit_assistance_remains_visible(self):
        for capability, profile, expected in [
            ('high-autonomy', 'standard', 'standard'),
            ('high-autonomy', 'strict', 'strict'),
            ('general', 'auto', 'standard'),
            ('limited', 'auto', 'strict'),
        ]:
            with self.subTest(capability=capability, profile=profile):
                self.configure(capability=capability, profile=profile)
                context = self.hook('session-start', self.payload('SessionStart'))[1]['hookSpecificOutput']['additionalContext']
                self.assertIn('Initial workflow profile: ' + expected, context)
                self.assertNotIn('decision-ledger', context)

    def test_quiet_entry_preserves_cross_session_obligations(self):
        self.configure()
        self.pre_bash('rm -rf cache')
        _, arm = self.gate_operation('arm', self.latest_event('gate-denied'))
        self.assertEqual(arm.returncode, 0)
        self.pre_bash('rm -rf cache')
        self.post_bash('rm -rf cache', response={'exit_code': 0})
        start = self.payload('SessionStart', session_id='new-session')
        context = self.hook('session-start', start)[1]['hookSpecificOutput']['additionalContext']
        self.assertIn('verification obligation(s) remain unresolved', context)
        self.assertNotIn('Initial workflow profile', context)
        self.assertEqual(self.hook('stop', self.payload('Stop'))[1]['decision'], 'block')

    def test_quiet_entry_never_hides_drift(self):
        self.configure()
        self.policy_path.write_text('{}')
        context = self.hook('session-start', self.payload('SessionStart'))[1]
        self.assertIn('drifted or broken', context['systemMessage'])
        self.assertEqual(self.pre_bash('pwd')['hookSpecificOutput']['permissionDecision'], 'deny')

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
