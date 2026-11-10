from types import SimpleNamespace
import unittest

import marketing_studio  # noqa: F401  puts the shared core on the import path
from studio_core import stops


class StopWordsTests(unittest.TestCase):
    """What a run says when a step stops for a limit or for its agent."""

    def test_a_step_that_ran_out_of_time_names_the_minutes_and_where_the_limit_is(self):
        self.assertEqual(stops.timed_out('Draft the outline', 900, 3), (
            'Draft the outline ran out of the time a step may take: its last try was stopped '
            'after 15 minutes, and it did not work in 3 tries. That limit, 15 minutes a step, '
            'is in Settings, under Limits.'))
        self.assertEqual(stops.timed_out('Do the research', 600, 1), (
            'Do the research ran out of the time a step may take: it was stopped after 10 '
            'minutes. That limit, 10 minutes a step, is in Settings, under Limits.'))
        # After more time, the limit that ran out is the run's own, not the one in Settings.
        self.assertEqual(stops.timed_out('Draft the outline', 1800, 3, 'deck', own=True), (
            'Draft the outline ran out of the time a step may take: its last try was stopped '
            'after 30 minutes, and it did not work in 3 tries. That limit, now 30 minutes a step '
            'for this deck, was given when you asked for more time; the limit for every deck is '
            'in Settings, under Limits.'))
        self.assertEqual(stops.more_time(900), 1800)
        self.assertEqual(stops.lasted(5400), '1 hour 30 minutes')
        self.assertEqual(stops.lasted(45), '45 seconds')

    def test_took_and_cost_say_dollars_only_when_every_job_reported(self):
        self.assertEqual(stops.took([{'seconds': 300, 'dollars': 0.5},
                                     {'seconds': 420, 'dollars': 0.9}]),
                         {'jobs': 2, 'seconds': 720, 'dollars': 1.4})
        self.assertIsNone(stops.took([{'seconds': 300, 'dollars': 0.5},
                                      {'seconds': 420}])['dollars'])
        self.assertEqual(stops.took([]), {'jobs': 0, 'seconds': 0, 'dollars': None})
        self.assertEqual(stops.cost(720, 1.4), '12 minutes and about $1.40')
        self.assertEqual(stops.cost(720, None), '12 minutes; the assistant reported no cost')

    def test_a_change_says_what_it_draws_again_and_what_that_took_last_time(self):
        self.assertEqual(stops.redone('the outline', 6, 1320, 3.1), (
            'Drawn again: the outline and every step after it, 6 steps. Last time they took '
            '22 minutes and about $3.10.'))
        self.assertEqual(stops.redone('the outline', 6, None, None), (
            'Drawn again: the outline and every step after it, 6 steps; this computer has no '
            'record of what they cost.'))
        self.assertEqual(stops.redone('the handoff', 1, 120, None), (
            'Drawn again: the handoff. Last time it took 2 minutes; the assistant reported no '
            'cost.'))
        self.assertEqual(stops.redone('the handoff', 1, None, None), (
            'Drawn again: the handoff; this computer has no record of what it cost.'))

    def test_no_reported_cost_is_never_said_as_nothing_spent(self):
        # A cost nobody reported, or one that rounds to nothing, is never "$0.00".
        self.assertEqual(stops.cost(60, 0), '1 minute; the assistant reported no cost')
        self.assertEqual(stops.cost(60, 0.003), '1 minute and less than $0.01')
        self.assertEqual(stops.redone('the outline', 3, 600, 0), (
            'Drawn again: the outline and every step after it, 3 steps. Last time they took '
            '10 minutes; the assistant reported no cost.'))
        # What a change writes again may be what is written from a file, not every later step.
        self.assertEqual(stops.redone('the blueprint', 4, None, None,
                                      after='what is written from it'), (
            'Drawn again: the blueprint and what is written from it, 4 steps; this computer '
            'has no record of what they cost.'))

    def test_nothing_stops_a_run_for_what_it_cost(self):
        self.assertFalse(hasattr(stops, 'spent') or hasattr(stops, 'floor') or hasattr(stops, 'FLOOR'))

    def test_an_agent_that_cannot_be_used_is_offered_open_status(self):
        unusable = SimpleNamespace(reason='unavailable', detail='It is not signed in.')
        self.assertEqual(stops.agent_action(unusable), 'status')
        self.assertEqual(stops.ACTION_LABELS['status'], 'Open Status')
        for other in (SimpleNamespace(reason='limit', detail='usage limit'),
                      SimpleNamespace(reason='timeout', detail='')):
            self.assertEqual(stops.agent_action(other), 'retry')

    def test_an_agent_that_cannot_be_used_points_at_the_status_screen(self):
        self.assertEqual(stops.unusable('Claude Code', 'It is not signed in.'), (
            'Claude Code could not be used. It is not signed in. Check this computer, on the '
            'Status screen, says what it needs.'))
        limited = SimpleNamespace(reason='limit', detail="You've hit your usage limit.")
        self.assertTrue(stops.account_limit(limited))
        # Where the agent reports it, the account's refusal is known without its words.
        self.assertTrue(stops.account_limit(SimpleNamespace(
            reason='limit', account=True, detail='It stopped without finishing.')))
        for other in (SimpleNamespace(reason='limit', detail='Too many turns.'),
                      SimpleNamespace(reason='failed', detail='usage limit')):
            self.assertFalse(stops.account_limit(other))

    def test_an_account_at_its_limit_is_waited_out_not_checked(self):
        # Check this computer cannot show a usage limit, so the stop does not send anyone there.
        limited = SimpleNamespace(reason='limit', account=True, detail='429')
        self.assertEqual(stops.agent_stopped('Claude Code', limited, '429'), (
            "Claude Code's account reached a usage or rate limit. Wait until it resets, then "
            'Try again.'))
        gone = SimpleNamespace(reason='unavailable', detail='Not signed in.')
        self.assertEqual(stops.agent_stopped('Codex', gone, 'Not signed in.'),
                         stops.unusable('Codex', 'Not signed in.'))
        self.assertIsNone(stops.agent_stopped('Codex', SimpleNamespace(
            reason='timeout', detail='slow'), 'slow'))


if __name__ == '__main__':
    unittest.main()
