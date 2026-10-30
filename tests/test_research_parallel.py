"""Synthetic evidence only: parallelism, pinned-helper validation and recovery."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_contract as rc, research_session as parallel, research_timing
from studio_core.research_transport import Reservations
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


class TimingTests(unittest.TestCase):
    def test_union_is_not_the_sum_and_gaps_are_not_called_pauses(self):
        rows = [{'started_at': '2026-01-01T00:00:10Z', 'ended_at': '2026-01-01T00:00:30Z', 'seconds': 20},
                {'started_at': '2026-01-01T00:00:20Z', 'ended_at': '2026-01-01T00:00:40Z', 'seconds': 20}]
        got = research_timing.account('2026-01-01T00:00:00Z', rows,
            [{'started_at': '2026-01-01T00:00:35Z'}], datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
        self.assertEqual([got[k] for k in ('active_seconds', 'assistant_seconds', 'elapsed_seconds', 'not_working_seconds')], [50, 65, 60, 10])

    def test_missing_history_is_explicit(self):
        got = research_timing.account('2026-01-01T00:00:00Z', [{'seconds': 20}],
                                      now=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
        self.assertTrue(got['incomplete'])
        self.assertIsNone(got['not_working_seconds'])
        self.assertEqual(got['assistant_seconds'], 20)


class BudgetAndProtocolTests(unittest.TestCase):
    def test_concurrent_reservations_do_not_duplicate_the_remaining_budget(self):
        budget = Reservations(lambda: 12)
        barrier = threading.Barrier(3)
        held = []
        def reserve():
            token, cap = budget.take('investigate', 3)
            held.append((token, cap))
            barrier.wait(3)
        threads = [threading.Thread(target=reserve) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join(4)
        self.assertEqual(len(held), 3)
        self.assertLessEqual(sum(cap for _, cap in held), 6)
        token, cap = budget.take('review')
        self.assertAlmostEqual(sum(budget.held.values()), 12)
        with self.assertRaisesRegex(ValueError, 'reserved or exhausted'):
            budget.take('review')
        budget.release(token)
        for token, _ in held: budget.release(token)
        self.assertEqual(budget.held, {})

    def test_new_protocol_is_explicit_and_old_runs_stay_serial(self):
        self.assertFalse(parallel.enabled({}))
        held = {'schema': 1, 'protocol': parallel.PROTOCOL, 'workers': 3,
                'capability': {'protocol': parallel.PROTOCOL, 'digest': 'synthetic'}}
        self.assertTrue(parallel.enabled({'research_execution': held}))
        self.assertEqual([len(a['questions']) for a in parallel.streams({'planning_questions': list(range(8))})], [3, 3, 2])
        self.assertFalse(parallel.protocol({'research_execution': {**held, 'workers': 9}}))

    def test_job_identity_and_retry_grouping(self):
        self.assertEqual(rc.job_round('research:investigate-2-area3'), ('investigate', 2))
        self.assertEqual(rc.job_round('research:synthesize-1'), ('synthesize', 1))
        self.assertEqual(rc.job_round('research:review-1'), ('review', 1))
        got = rc.last_rounds({'research:investigate-1-area1': [
            {'research_attempt': 'old', 'started_at': '1', 'seconds': 60},
            {'research_attempt': 'new', 'started_at': '3', 'seconds': 5}],
            'research:investigate-1-area2': [{'research_attempt': 'new', 'started_at': '2', 'seconds': 6}]})
        self.assertEqual((got['jobs'], got['seconds']), (2, 11))
