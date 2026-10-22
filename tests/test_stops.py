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
        self.assertEqual(stops.more_time(900), 1800)
        self.assertEqual(stops.lasted(5400), '1 hour 30 minutes')
        self.assertEqual(stops.lasted(45), '45 seconds')

    def test_a_stop_for_money_says_how_to_carry_on_and_that_settings_is_the_other_way(self):
        what, kept = stops.spent('training', 20.4, 20)
        self.assertEqual(what, 'This training has spent $20.40. It stops and asks each time it '
                               'has spent another $20.00.')
        self.assertEqual(kept, 'Everything made so far is kept. Carry on lets it spend up to '
                               'another $20.00. To let it spend more before it asks, raise the '
                               'limit in Settings, under Limits, then carry on.')
        what, _ = stops.spent('deck', 19.7, 20, left=0.3)
        self.assertEqual(what, 'This deck has spent $19.70, and the $0.30 it may still spend is '
                               'too little to start another step. It stops and asks each time '
                               'it has spent another $20.00.')
        what, kept = stops.spent('training', 20.0, 20, label='Write the learner guide')
        self.assertEqual(what, 'Write the learner guide was stopped when this training reached '
                               'what it may spend: it has spent $20.00. It stops and asks each '
                               'time it has spent another $20.00.')
        self.assertTrue(kept.startswith('Everything finished before this step is kept, and the '
                                        'step starts again when you carry on. Carry on'))
        # Each studio names the action as its page does.
        self.assertTrue(stops.spent('deck', 1, 1, go='Resume')[1].endswith('then resume.'))

    def test_no_job_starts_with_less_than_the_floor_left(self):
        self.assertEqual((stops.floor(20), stops.floor(1), stops.floor(0)), (0.5, 0.25, 0.0))

    def test_an_agent_that_cannot_be_used_points_at_the_status_screen(self):
        self.assertEqual(stops.unusable('Claude Code', 'It is not signed in.'), (
            'Claude Code could not be used. It is not signed in. Check this computer, on the '
            'Status screen, says what it needs.'))
        limited = SimpleNamespace(reason='limit', budget=False, detail="You've hit your usage limit.")
        self.assertTrue(stops.account_limit(limited))
        # Where the agent reports it, the account's refusal is known without its words.
        self.assertTrue(stops.account_limit(SimpleNamespace(
            reason='limit', budget=False, account=True, detail='It stopped without finishing.')))
        for other in (SimpleNamespace(reason='limit', budget=True, detail='usage limit'),
                      SimpleNamespace(reason='limit', budget=False, detail='Too many turns.'),
                      SimpleNamespace(reason='failed', budget=False, detail='usage limit')):
            self.assertFalse(stops.account_limit(other))

    def test_an_account_at_its_limit_is_waited_out_not_checked(self):
        # Check this computer cannot show a usage limit, so the stop does not send anyone there.
        limited = SimpleNamespace(reason='limit', budget=False, account=True, detail='429')
        self.assertEqual(stops.agent_stopped('Claude Code', limited, '429'), (
            "Claude Code's account reached a usage or rate limit. Wait until it resets, then "
            'Try again.'))
        gone = SimpleNamespace(reason='unavailable', budget=False, detail='Not signed in.')
        self.assertEqual(stops.agent_stopped('Codex', gone, 'Not signed in.'),
                         stops.unusable('Codex', 'Not signed in.'))
        self.assertIsNone(stops.agent_stopped('Codex', SimpleNamespace(
            reason='timeout', budget=False, detail='slow'), 'slow'))


if __name__ == '__main__':
    unittest.main()
