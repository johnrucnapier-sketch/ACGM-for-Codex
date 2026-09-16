import time
import unittest
from test_session_hooks import N, POLICY
from test_session_guardian import G
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from session_dashboard import display_metrics

class DashboardTests(unittest.TestCase):
    def reader(self,used,window=475000):
        r=G.RolloutReader('test',Path.cwd());r.used=used;r.window=window;r.observed_at=time.time()
        return r
    def test_colours_match_installed_hook_boundaries(self):
        for used,expected in [(100000,'NORMAL'),(310000,'CAUTION'),(381000,'CLOSING'),(390000,'CONFIRM'),(420000,'CONFIRM')]:
            metrics=display_metrics(self.reader(used),POLICY)
            self.assertEqual(metrics['stage'],expected)
            decision=N['evaluate_hook']({'hook_event_name':'UserPromptSubmit','turn_id':'t','prompt':''},POLICY,{'context_used':used,'context_window':475000},{})
            self.assertEqual(decision.get('decision')=='block',expected=='CONFIRM')
    def test_stale_samples_are_not_green(self):
        r=self.reader(100000);r.observed_at=time.time()-301
        self.assertEqual(display_metrics(r,POLICY)['stage'],'UNKNOWN')
    def test_old_window_uses_its_actual_budget(self):
        m=display_metrics(self.reader(210000,258400),POLICY)
        self.assertEqual(m['stage'],'CONFIRM');self.assertFalse(m['window_matches'])
    def test_compaction_is_not_hidden_by_green(self):
        r=self.reader(100000);r.compactions=1
        self.assertEqual(display_metrics(r,POLICY)['compactions_in_observed_tail'],1)

    def test_native_exec_tasks_are_visible_without_including_subagents(self):
        import json,sqlite3,tempfile
        from session_dashboard import Monitor
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();(root/'.acgm').mkdir()
            (root/'.acgm/session-guardian.json').write_text(json.dumps(POLICY))
            rollout=root/'rollout.jsonl'
            rollout.write_text(json.dumps({'type':'session_meta','payload':{'id':'exec-task','cwd':str(root),'cli_version':'0.154.0-alpha.6.2'}})+'\n')
            with sqlite3.connect(root/'state_5.sqlite') as db:
                db.execute('create table threads (id text,title text,rollout_path text,cwd text,archived int,source text,updated_at int)')
                for source,thread in [('exec','exec-task'),('subagent','child')]:
                    db.execute('insert into threads values (?,?,?,?,?,?,?)',(thread,thread,str(rollout),str(root),0,source,1))
            result=Monitor(root,root).snapshot()
            self.assertEqual([t['id'] for t in result['tasks']],['exec-task'])
            self.assertEqual(result['tasks'][0]['stage'],'UNKNOWN')

if __name__=='__main__':unittest.main()
