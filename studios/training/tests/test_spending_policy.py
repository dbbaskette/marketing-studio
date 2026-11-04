"""Saved project policy, native job caps and explicit local changes over isolated state."""
import helpers  # Sets the isolated native runtime before domain imports.
import home
from runner import settings
from runner_support import StudioCase
from studio_core import activity_log, spending, work_summary
from workspace import WorkspaceError


class SpendingPolicyTests(StudioCase):
    def test_new_work_warns_with_a_five_dollar_job_cap(self):
        root=self.start()
        record=self.engine._load(root)
        self.assertEqual(record['spending_policy'],'warn')
        self.assertTrue(self.workers.jobs)
        self.assertEqual(self.workers.jobs[0][1].limits.dollars,5)

    def test_explicit_local_policy_change_is_stale_safe_and_starts_no_job(self):
        root=self.start();before=len(self.workers.jobs)
        shown=spending.get(self.engine,root,'training')
        self.assertEqual(shown['policy'],'warn')
        result=spending.change(self.engine,root,shown['expected'],'hard-stop','training')
        self.assertEqual(result['spending']['policy'],'hard-stop')
        with self.assertRaises(WorkspaceError):spending.change(self.engine,root,shown['expected'],'warn','training')
        self.assertEqual(len(self.workers.jobs),before)

    def test_legacy_policy_stays_hard_and_warning_is_saved_once_in_activity_and_home(self):
        root=self.start();record=self.engine._load(root)
        record.pop('spending_policy')
        self.engine._store(root,record)
        self.assertEqual(spending.get(self.engine,root,'training')['policy'],'hard-stop')
        record['spending_policy']='warn'
        self.engine._tried(record,'budget-fixture',home.now(),1,'kept',dollars=30)
        self.engine._store(root,record);self.engine._store(root,record)
        log=root/self.engines.ACTIVITY
        self.assertEqual(len([e for e in activity_log.checkpoints(log) if e['checkpoint']=='spending-warning']),1)
        self.assertIn('Work continues',work_summary.read(root)['warning'])
        self.assertIn('spending',self.view(root))
