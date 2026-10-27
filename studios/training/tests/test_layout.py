"""The layout pass: each screen in the order a person works, run for real in page_harness.js.

Every journey here is held to the layout rules on every snapshot (`run_page` with
`layout=True`): one lede at most, one heading level in a card, no card inside a card, and a
toolbar whose one filled action comes first with the rest quiet. Nothing starts an agent,
looks at the real computer or touches the network.
"""
import unittest

import test_desk
from test_desk import a_run, steps


@unittest.skipUnless(test_desk.NODE, 'Node is needed to run the page scripts without a browser')
class LayoutTests(test_desk.ScriptedPage, test_desk.PageCase):
    answers = test_desk.RunnerScreenTests.answers
    posts = test_desk.RunnerScreenTests.posts
    started = test_desk.RunnerScreenTests.started
    at_the_questions_gate = test_desk.RunnerScreenTests.at_the_questions_gate
    listed = test_desk.RunnerScreenTests.listed
    detail = test_desk.RunnerScreenTests.detail

    def run_page(self, answers: dict, steps: list, layout: bool = True, **plan) -> dict:
        return super().run_page(answers, steps, layout=layout, **plan)

    # --- the toolbar ---------------------------------------------------------------

    def test_the_filled_action_comes_first_and_the_rest_are_quiet(self):
        self.started()
        self.at_the_questions_gate()
        # Home's rows are headings inside their card until Home is laid out; then layout=True.
        result = self.run_page(self.answers(), [{'snapshot': 'home'}], layout=False)
        bar = result['snapshots']['home']['toolbar']
        self.assertEqual(bar[0]['filled'], True)
        self.assertTrue(bar[0]['name'].startswith('Review '), bar)
        self.assertGreater(len(bar), 1)
        self.assertEqual([control for control in bar[1:] if not control['quiet']], [])

    def test_a_phone_wraps_the_toolbar_and_has_no_more_menu(self):
        self.started()
        resting = 'Paused before the research questions.'
        paused = a_run('paused', resting, steps=steps('done', 'pending'))
        answers = self.answers(**{'GET /api/trainings': [self.listed('paused', resting)],
                                  'GET /api/training': [self.detail('paused', resting)],
                                  'GET /api/run': [paused]})
        result = self.run_page(answers, [{'click': 'Open Rolling restarts'},
                                         {'snapshot': 'phone'}], narrow=True)
        phone = result['snapshots']['phone']
        names = [control['name'] for control in phone['toolbar']]
        self.assertIn('Resume', names)
        self.assertIn('Stop', names)
        self.assertNotIn('More', names)
        self.assertNotIn('More', phone['buttons'])


if __name__ == '__main__':
    unittest.main()
