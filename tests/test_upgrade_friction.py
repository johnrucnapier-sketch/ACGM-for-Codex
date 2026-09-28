"""Real upgrade lockout regression: usable old projects, bounded diagnostics."""
import json
import shlex
import unittest
from pathlib import Path
import test_runtime as R


class UpgradeFrictionTests(R.RuntimeTests):
    def test_compatible_version_keeps_baseline_and_enforces_risk(self):
        self.init_activate()
        state_path = self.project / '.acgm/codex.json'
        state = json.loads(state_path.read_text())
        state['version'] = '0.3.0-rc.1'
        state_path.write_text(json.dumps(state))
        before = state_path.read_bytes()
        for command in ['pwd', 'git status --short', 'printf fixture > ordinary.txt']:
            self.assertNotEqual(self.pre_bash(command).get('hookSpecificOutput', {}).get('permissionDecision'), 'deny')
        for command in ['rm -rf build/stale-cache', 'git reset --hard']:
            self.assertEqual(self.pre_bash(command)['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(self.latest_event('gate-denied')['state'], 'GOVERNED')
        self.assertEqual(json.loads(self.cli('doctor', '--json').stdout)['drift'], [])
        self.assertEqual(state_path.read_bytes(), before)
        (self.project/'AGENTS.md').write_text('Unreviewed actual policy change')
        self.assertEqual(self.pre_bash('pwd')['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_exact_diagnostic_survives_broken_state_without_ledger_writes(self):
        self.init_activate()
        plugin = self.base/'plugin'
        plugin.symlink_to(R.REPO, target_is_directory=True)
        self.env['PLUGIN_ROOT'] = str(plugin)
        launcher = shlex.quote(str(plugin/'bin/acgm-codex'))
        state = self.project/'.acgm/codex.json'
        state.write_text('not-json')
        before = {str(p):p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        for args in ['doctor', 'doctor --strict', 'doctor --json --strict', 'doctor '+str(self.project.resolve())+' --strict']:
            self.assertEqual(self.pre_bash(launcher+' '+args), {})
        self.assertEqual({str(p):p.read_bytes() for p in self.data.rglob('*') if p.is_file()}, before)
        rejected = [
            'acgm-codex doctor --strict', '/tmp/acgm-codex doctor',
            launcher+' doctor; touch marker', launcher+' doctor && pwd',
            launcher+' doctor > output', launcher+' doctor $(touch marker)',
            'env '+launcher+' doctor', launcher+' activate '+str(self.project),
            launcher+' doctor --unknown', launcher+' doctor /tmp',
            launcher+' doctor --strict --strict', launcher+' doctor\npwd',
        ]
        for command in rejected:
            with self.subTest(command=command):
                self.assertEqual(self.pre_bash(command)['hookSpecificOutput']['permissionDecision'], 'deny')
        result = self.cli('doctor', '--strict', '--json')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['project_state'], 'BROKEN')
        # An attacker-controlled same-name CLI is never a diagnostic exemption.
        fake = self.base/'fake';(fake/'bin').mkdir(parents=True)
        (fake/'bin/acgm-codex').write_text('#!/bin/sh\ntouch marker\n')
        self.env['PLUGIN_ROOT'] = str(fake)
        self.assertEqual(self.pre_bash(str(fake/'bin/acgm-codex')+' doctor')['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_corrupt_ledger_does_not_block_diagnostic_or_allow_mutation(self):
        self.init_activate()
        self.pre_bash('pwd')
        plugin = self.base/'plugin';plugin.symlink_to(R.REPO, target_is_directory=True)
        self.env['PLUGIN_ROOT'] = str(plugin)
        ledger = self.data/'events.jsonl';ledger.write_text('broken\n')
        command = str(plugin/'bin/acgm-codex')+' doctor --json'
        self.assertEqual(self.pre_bash(command), {})
        self.assertEqual(ledger.read_text(), 'broken\n')
        result = json.loads(self.cli('doctor', '--json').stdout)
        self.assertFalse(result['ledger']['available'])
        self.assertEqual(self.pre_bash('rm -rf cache')['hookSpecificOutput']['permissionDecision'], 'deny')
        # A genuine launcher with substituted runtime bytes is not exempt.
        fake = self.base/'fake';(fake/'bin').mkdir(parents=True);(fake/'scripts').mkdir()
        (fake/'bin/acgm-codex').write_bytes((R.REPO/'bin/acgm-codex').read_bytes())
        (fake/'scripts/acgm_codex.py').write_text('raise SystemExit(0)')
        self.env['PLUGIN_ROOT'] = str(fake)
        self.assertEqual(self.pre_bash(str(fake/'bin/acgm-codex')+' doctor')['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_unknown_versions_and_changed_policy_still_block(self):
        self.init_activate()
        path = self.project/'.acgm/codex.json'
        state = json.loads(path.read_text())
        for version in ['99.0.0', '0.4.0-local', None, []]:
            state['version'] = version;path.write_text(json.dumps(state))
            self.assertEqual(self.pre_bash('pwd')['hookSpecificOutput']['permissionDecision'], 'deny')


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(UpgradeFrictionTests(name) for name in UpgradeFrictionTests.__dict__ if name.startswith('test_'))
