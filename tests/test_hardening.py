"""Regression cases from real safety failures, using isolated projects only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import test_runtime as R
from test_session_hooks import N, POLICY
from test_session_guardian import G


class HardeningTests(R.RuntimeTests):
    # Reuse fixture helpers, not inherited test methods (see load_tests below).
    def test_broken_and_drifted_policy_never_silently_allow(self):
        self.init_activate()
        state = self.project / '.acgm/codex.json'
        original = state.read_bytes()
        for content in ['', '{}', '[]', 'not-json']:
            state.write_text(content)
            self.assertEqual(self.pre_bash('rm -rf cache')['hookSpecificOutput']['permissionDecision'], 'deny')
        state.write_bytes(original)
        (self.project/'AGENTS.md').write_text('Changed policy')
        self.assertEqual(self.pre_bash('rm -rf cache')['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_root_nested_policy_identity_and_compound_mutations(self):
        self.init_activate()
        nested = self.project/'sub/deep'; nested.mkdir(parents=True)
        for cwd in [self.project, nested.parent, nested]:
            for command in ['date & rm -rf x','date ; rm -r -f x','date && rm --recursive --force x',
                            'date | rm -rf x','echo $(rm -rf x)','(rm -rf x)',
                            'rm -rf x > out','rm -rf x >> out']:
                with self.subTest(cwd=cwd, command=command):
                    self.assertEqual(self.pre_bash(command,cwd=str(cwd))['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertEqual(len({e['project_id'] for e in self.report_json()['events']}),1)

    def test_argv_examples_are_never_gate_evidence(self):
        self.init_activate()
        for command in ['date','date -s now','uniq input','uniq input output',
                        'journalctl query','journalctl --rotate','systemctl show',
                        'systemctl restart service','nvcc --version','nvcc source -o output']:
            self.pre_bash(command)
            self.post_bash(command)
        self.assertNotIn('state-check-observed',self.event_kinds())
        self.assertNotIn('gate-armed',self.event_kinds())

    def test_same_directory_different_operation_cannot_spend_arm(self):
        self.init_activate()
        self.pre_bash('rm -rf cache-one')
        source=self.latest_event('gate-denied')
        _, armed=self.gate_operation('arm',source)
        self.assertEqual(armed.returncode,0,armed.stderr)
        self.assertEqual(self.pre_bash('rm -rf cache-two')['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertIn('consumed',self.pre_bash('rm -rf cache-one')['systemMessage'])

    def test_remote_read_cannot_arm_local_or_other_host_action(self):
        self.init_activate()
        for command in ["ssh nas 'ls -la /remote/path'", "ssh other 'ls -la /remote/path'",'ls /remote/path']:
            self.pre_bash(command); self.post_bash(command)
        self.assertEqual(self.pre_bash('rm -rf local-cache')['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertNotIn('state-check-observed',self.event_kinds())

    def test_execution_results_do_not_conflate_unknown_blocked_and_success(self):
        self.init_activate()
        for response,expected in [({},'unknown'),('Process exited with code 0','unknown'),
                                 ({'exit_code':0},'execution-succeeded'),({'exit_code':7},'execution-failed'),
                                 ({'status':'sandbox_blocked'},'sandbox-blocked'),
                                 ({'status':'approval_denied'},'approval-denied'),
                                 ({'status':'interrupted'},'interrupted'),({'session_id':3},'running')]:
            self.post_bash('date',response=response)
            self.assertEqual(self.latest_event('tool-result-observed')['outcome'],expected)
        self.pre_bash('date')
        self.assertEqual(self.report_json()['events'][-1]['kind'],'tool-requested')

    def test_sandbox_block_is_not_mutation_or_verification(self):
        self.init_activate()
        self.pre_bash('rm -rf cache')
        _,result=self.gate_operation('arm',self.latest_event('gate-denied'))
        self.assertEqual(result.returncode,0)
        self.pre_bash('rm -rf cache')
        self.post_bash('rm -rf cache',response={'status':'sandbox_blocked'})
        self.assertNotIn('obligation-opened',self.event_kinds())

    def test_claimed_verified_or_unresolved_is_not_execution_evidence(self):
        runtime=self.load_runtime_module()
        opened={'event_id':'operation','kind':'obligation-opened'}
        for status in ['verified','resolved','unresolved']:
            self.assertEqual(runtime._open_obligations([opened,{'kind':'event-resolution','ref_id':'operation','outcome':status}]),[opened])


    def test_interruption_is_a_distinct_observation(self):
        self.init_activate()
        self.hook('interrupt',self.payload('Interrupt'))
        self.assertEqual(self.latest_event('session-interrupted')['outcome'],'interrupted')


class GuardianHardeningTests(unittest.TestCase):
    def test_append_to_existing_request_list_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            for turn in ['one','two']:
                with N['session_state'](tmp,'session') as state:
                    N['remember_request'](state,{'turn_id':turn,'prompt':turn})
            with N['session_state'](tmp,'session') as state:
                self.assertEqual(len(state['pending_requests']),2)
            with N['session_state'](tmp,'new-session') as state:
                self.assertEqual(state,{})

    def test_complete_requests_survive_preview_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(6):
                with N['session_state'](tmp,'session') as state:
                    N['preserve_request'](tmp,'session',{'turn_id':str(i),'prompt':str(i)+'字'*12000},state)
            with N['session_state'](tmp,'session') as state:
                entries=[json.loads(p.read_text()) for p in Path(state['pending_archive']).glob('*.json')]
                self.assertEqual(len(entries),6)
                self.assertTrue(all(len(e['text'])==12001 for e in entries))

    def test_malformed_policy_is_not_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);subprocess.run(['git','init','-q',tmp],check=True)
            (root/'.acgm').mkdir();p=root/'.acgm/session-guardian.json'
            for content in ['', '{}','[]','{"schema":"unknown","enabled":true}']:
                p.write_text(content)
                with self.assertRaises((ValueError,TypeError)):N['policy_for'](tmp)

    def test_dashboard_and_hook_budget_are_identical(self):
        import sys
        sys.path.insert(0,str(R.REPO/'scripts'))
        import session_dashboard as D
        for used,expected in [(1000,'NORMAL'),(310000,'CAUTION'),(381000,'CLOSING'),(391000,'CONFIRM'),(411000,'CONFIRM')]:
            reader=G.RolloutReader('fixture',R.REPO)
            reader.used=used;reader.window=475000;reader.observed_at=__import__('time').time()
            self.assertEqual(D.display_metrics(reader,POLICY)['stage'],expected)
            self.assertEqual(G.budget_metrics(used,475000,POLICY)[2],expected)

    def test_integrated_hooks_opt_in_and_hash_failure(self):
        import shlex
        hooks=json.loads((R.REPO/'hooks/hooks.json').read_text())["hooks"]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);subprocess.run(['git','init','-q',tmp],check=True)
            env={**os.environ,'PLUGIN_ROOT':str(R.REPO),'PLUGIN_DATA':tmp}
            command=hooks['PreCompact'][-1]['hooks'][0]['command']
            payload={'cwd':tmp,'hook_event_name':'PreCompact','trigger':'auto'}
            def call(environment):
                p=subprocess.run(shlex.split(command),input=json.dumps(payload),text=True,capture_output=True,env=environment)
                self.assertEqual(p.returncode,0,p.stderr)
                return json.loads(p.stdout)
            self.assertEqual(call(env),{})
            (root/'.acgm').mkdir();(root/'.acgm/session-guardian.json').write_text(json.dumps(POLICY))
            self.assertFalse(call(env)['continue'])
            self.assertFalse(call({**env,'PLUGIN_ROOT':tmp})['continue'])

    def test_native_audit_missing_ledger_returns_unknown_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rollout=root/'fixture.jsonl'
            rollout.write_text(json.dumps({'type':'session_meta','payload':{'id':'s','cwd':tmp,'cli_version':'0.154.0-alpha.6.2'}})+'\n')
            result=subprocess.run(['python3',str(R.REPO/'scripts/session_guardian.py'),'audit','--project',tmp,'--thread','s','--rollout',str(rollout)],env={**os.environ,'ACGM_CODEX_DATA_DIR':str(root/'missing')},capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(json.loads(result.stdout)['state'],'UNKNOWN')
            self.assertFalse((root/'missing').exists())

    def test_native_audit_matches_call_turn_operation_without_writing(self):
        import sys
        sys.path.insert(0,str(R.REPO/'scripts'))
        import acgm_codex as A
        events=[{'session_id':'session:s','kind':'tool-requested','call_id':'call:c','turn_id':'turn:t','operation_id':'operation:exit 7','event_id':'e'}]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rollout=root/'fixture.jsonl'
            records=[{'type':'session_meta','payload':{'id':'s','cwd':tmp,'cli_version':'0.154.0-alpha.6.2'}},
                     {'type':'event_msg','payload':{'type':'item_completed','thread_id':'s','turn_id':'t','item':{'type':'CommandExecution','id':'c','command':['/bin/sh','-c','exit 7'],'cwd':tmp,'status':'failed','exit_code':7}}}]
            rollout.write_text(''.join(json.dumps(x)+'\n' for x in records))
            with mock.patch.object(A,'_project_events',return_value=events), mock.patch.object(A,'_opaque_readonly',side_effect=lambda k,v:k+':'+v):
                result=G.native_audit(root,'s',rollout)
                self.assertEqual(result['results'][0]['outcome'],'execution-failed')
                self.assertEqual(result['requests_without_native_completion'],0)
                events[0]['operation_id']='operation:unrelated'
                self.assertEqual(G.native_audit(root,'s',rollout)['results'],[])
            self.assertEqual(list(root.iterdir()),[rollout])


def load_tests(loader, tests, pattern):
    suite=unittest.TestSuite()
    for name in HardeningTests.__dict__:
        if name.startswith('test_'):suite.addTest(HardeningTests(name))
    suite.addTests(loader.loadTestsFromTestCase(GuardianHardeningTests))
    return suite
