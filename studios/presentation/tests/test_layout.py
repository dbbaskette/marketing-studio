"""The layout pass: each screen in the order a person works, run for real in page_harness.js.

Every journey here is held to the layout rules on every snapshot (`run_page` with
`layout=True`): one lede at most, one heading level in a card, no card inside a card, and a
toolbar whose one filled action comes first with the rest quiet. Nothing starts an agent,
looks at the real computer or touches the network.
"""
import unittest

import test_desk
import test_runner_page
from test_desk import ok


@unittest.skipUnless(test_desk.NODE, 'Node is needed to run the page scripts without a browser')
class LayoutTests(test_desk.ScriptedPage, test_runner_page.PageCase):
    answers = test_desk.ScreenTests.answers
    deck_screen = test_desk.ScreenTests.deck_screen
    setup_with = test_desk.ScreenTests.setup_with

    def run_page(self, answers: dict, steps: list, layout: bool = True, **plan) -> dict:
        return super().run_page(answers, steps, layout=layout, **plan)

    def paused(self, path: str) -> dict:
        """The deck as the runner shows it once it is paused between steps."""
        shown = self.run_of(path)
        shown.update(state='paused', gate=None, question=None, problem=None, undo=True)
        return shown

    # --- the toolbar ---------------------------------------------------------------

    def test_the_filled_action_comes_first_and_the_rest_are_quiet(self):
        self.started(title='Waiting deck')
        # Home's rows are headings inside their card until Home is laid out; then layout=True.
        result = self.run_page(self.answers(), [{'snapshot': 'home'}], layout=False)
        bar = result['snapshots']['home']['toolbar']
        self.assertEqual(bar[0], {'name': 'Review Waiting deck', 'filled': True, 'quiet': False})
        self.assertGreater(len(bar), 1)
        self.assertEqual([control for control in bar[1:] if not control['quiet']], [])

    def test_a_phone_wraps_the_toolbar_and_has_no_more_menu(self):
        path = self.started(title='Paused deck')
        result = self.deck_screen(path, [{'snapshot': 'phone'}], narrow=True,
                                  **{'GET /api/run': [ok(self.paused(path))]})
        phone = result['snapshots']['phone']
        names = [control['name'] for control in phone['toolbar']]
        self.assertIn('Resume', names)
        self.assertIn('Stop', names)
        self.assertNotIn('More', names)
        self.assertNotIn('More', phone['buttons'])
        self.assertEqual(phone['toolbar'][0]['name'], 'Resume')


if __name__ == '__main__':
    unittest.main()
