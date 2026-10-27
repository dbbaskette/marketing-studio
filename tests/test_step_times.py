"""How long a step usually takes on this computer, and how much of it is left."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from drafting_fixtures import FolderStore
from studio_core import step_times


class StepTimeCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = FolderStore(folder.name)
        self.path = self.store.root / 'local' / 'step-times.json'


class StepTimeTests(StepTimeCase):
    def test_the_median_of_recent_runs_is_the_estimate(self):
        for seconds in (60, 180, 600):
            step_times.note(self.store, self.path, 'draft:short', seconds)
        self.assertEqual(step_times.expected(self.store, self.path, 'draft:short', 9), 3)
        self.assertEqual(step_times.expected(self.store, self.path, 'outline', 9), 9)
        self.assertEqual(step_times.expected(self.store, self.path, 'outline', lambda: 7), 7)
        step_times.note(self.store, self.path, 'quick', 6)
        self.assertEqual(step_times.expected(self.store, self.path, 'quick', 9), 1)

    def test_twenty_times_are_kept_per_step(self):
        for seconds in range(25):
            step_times.note(self.store, self.path, 'outline', seconds + 0.04)
        kept = self.store.read_json(self.path)['outline']
        self.assertEqual(len(kept), step_times.TIMES)
        self.assertEqual(kept[-1], 24.0)

    def test_a_torn_times_file_falls_back_to_the_guess(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('not json')
        self.assertEqual(step_times.expected(self.store, self.path, 'outline', 4), 4)
        step_times.note(self.store, self.path, 'outline', 30)  # Best effort: never raises.
        self.path.write_text('[1, 2]')
        self.assertEqual(step_times.expected(self.store, self.path, 'outline', 4), 4)

    def test_time_left_counts_what_is_spent_and_says_when_a_step_overruns(self):
        now = datetime.now(timezone.utc)
        job = {'started_at': (now - timedelta(minutes=1)).isoformat(), 'busy': True}
        self.assertEqual(step_times.left([3, 2], job, now), {'minutes_left': 4, 'over': False})
        job = {'started_at': (now - timedelta(minutes=5)).isoformat(), 'busy': True}
        self.assertEqual(step_times.left([3, 2], job, now), {'minutes_left': 2, 'over': True})
        self.assertEqual(step_times.left([3], None, now), {'minutes_left': 3, 'over': False})

    def test_seconds_needs_both_times(self):
        self.assertIsNone(step_times.seconds({'started_at': '2026-01-01T00:00:00+00:00'}))
        self.assertEqual(
            step_times.seconds(
                {'started_at': '2026-01-01T00:00:00+00:00', 'finished_at': '2026-01-01T00:01:30+00:00'}
            ),
            90,
        )


if __name__ == '__main__':
    unittest.main()
