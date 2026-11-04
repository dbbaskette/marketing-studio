"""Spending totals are advisory only for explicitly saved warning-mode projects."""
import tempfile
import unittest
from pathlib import Path
import marketing_studio
from studio_core import activity_log, preferences, spending
from studio_core.research_transport import Reservations


class SpendingTests(unittest.TestCase):
    def test_shared_defaults_warn_but_missing_saved_policy_preserves_hard_stop(self):
        self.assertEqual(spending.shared({}, 'training'), 'warn')
        self.assertEqual(spending.policy({}), 'hard-stop')
        self.assertEqual(spending.cap({}, 0.4), 0.4)
        self.assertEqual(spending.cap({'spending_policy':'warn'}, -21), 5)
        with self.assertRaises(ValueError):spending.policy({'spending_policy':'invalid'})

    def test_warning_jobs_keep_finite_caps_after_project_total_is_exhausted(self):
        reservations = Reservations(lambda: -30, fixed=spending.JOB_DOLLARS)
        jobs = [reservations.take('investigate', 3) for _ in range(3)]
        self.assertEqual([cap for _,cap in jobs], [5,5,5])
        self.assertEqual(len({ident for ident,_ in jobs}), 3)
        for ident,_ in jobs:reservations.release(ident)
        self.assertEqual(reservations.held, {})
        with self.assertRaises(ValueError):Reservations(lambda: 0).take('investigate')

    def test_crossings_are_durable_once_and_do_not_count_as_assistant_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'activity.jsonl';record={'spending_policy':'warn'}
            activity_log.checkpoint(path,'accepted');activity_log.checkpoint(path,'working')
            for used in (20,21,39,40,41):spending.observe(path,record,used,20)
            warnings=[e for e in activity_log.checkpoints(path) if e['checkpoint']=='spending-warning']
            self.assertEqual(len(warnings),2)
            self.assertEqual(activity_log.view(path)['jobs'],[])
            self.assertEqual(len(activity_log.view(path)['spending_warnings']),2)
            self.assertEqual(activity_log.timing(path)['phase'],'working')
            self.assertEqual(record['spending_warning']['crossing'],2)

    def test_conversation_requests_are_not_claimed_to_have_runner_budget_control(self):
        record={'execution':'conversation','spending_policy':'warn'}
        self.assertFalse(spending.info(record,30,20)['available'])
        self.assertIsNone(spending.notice(record,30,20))

    def test_unknown_usage_never_becomes_zero_or_a_false_warning(self):
        for used in (None, float('nan'), float('inf')):
            self.assertIsNone(spending.notice({'spending_policy':'warn'},used,20))
        self.assertIsNone(spending.notice({},100,20))

    def test_shared_policy_validation_preserves_unrelated_settings(self):
        original={'brand':{'brand':'synthetic'},'spending':{'training':'hard-stop'}}
        merged=preferences.check({'spending':{'presentation':'warn'}}, original)
        self.assertEqual(merged['brand'],original['brand'])
        self.assertEqual(merged['spending'],{'training':'hard-stop','presentation':'warn'})
        with self.assertRaises(ValueError):preferences.check({'spending':{'training':'unlimited'}},original)

    def test_policy_basis_changes_with_limits_and_owner_but_not_activity(self):
        record={'limits':{'dollars':20},'driver':{'id':'synthetic'},'spending_policy':'warn'}
        expected=spending.identity(record)
        self.assertEqual(spending.identity({**record,'activity':'another poll'}),expected)
        self.assertNotEqual(spending.identity({**record,'limits':{'dollars':30}}),expected)
        self.assertNotEqual(spending.identity({**record,'driver':{'id':'another'}}),expected)
