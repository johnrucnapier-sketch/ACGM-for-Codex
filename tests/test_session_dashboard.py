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

if __name__=='__main__':unittest.main()
