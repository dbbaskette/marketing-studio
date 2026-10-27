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

    def finished(self, title: str) -> str:
        path = self.started(title=title)
        for _ in range(20):
            if self.run_of(path)['gate'] is None:
                break
            self.decided(path)
        return path

    def every_kind(self) -> dict:
        """Decks needing you, working and finished, as the runner lists them."""
        self.started(title='Waiting deck')
        self.finished('Finished deck')
        decks = self.get('decks')
        working = {**decks['needs'][0], 'path': '/elsewhere/working', 'id': 'working',
                   'title': 'Working deck', 'state': 'working', 'needs': False,
                   'sentence': 'Drafting the outline.'}
        decks['working'] = [working]
        return decks

    # --- the toolbar ---------------------------------------------------------------

    def test_the_filled_action_comes_first_and_the_rest_are_quiet(self):
        self.started(title='Waiting deck')
        result = self.run_page(self.answers(), [{'snapshot': 'home'}])
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


    # --- Home, Status, Settings and Set-up ----------------------------------------

    def test_home_puts_what_needs_you_first_and_setup_after_ways_to_start(self):
        decks = self.every_kind()
        result = self.run_page(self.answers(**{'GET /api/decks': [ok(decks)]}),
                               [{'snapshot': 'home'}])
        home = result['snapshots']['home']
        self.assertEqual(home['ledes'], ['What needs you comes first, then decks in progress, '
                                         'then ways to start one.'])
        parts = home['parts']
        self.assertEqual(parts[:2], ['Needs you', 'In progress'])
        self.assertIn('Start a deck', parts)
        self.assertLess(parts.index('Start a deck'), parts.index('Finished'))
        if 'Updates' in parts:
            self.assertLess(parts.index('Start a deck'), parts.index('Updates'))
            self.assertLess(parts.index('Updates'), parts.index('Finished'))
        # The greeting stays above the lede.
        self.assertLess(home['text'].index('Good '), home['text'].index('What needs you'))

    def test_start_a_deck_opens_the_form_at_its_route(self):
        self.started(title='Waiting deck')
        result = self.run_page(self.answers(), [
            {'click': 'Start from a document'}, {'snapshot': 'document'}])
        shot = result['snapshots']['document']
        self.assertTrue('Your document' in shot['parts'] or shot['heading'] == 'Your document',
                        shot['parts'])

    def test_status_shows_the_check_first(self):
        result = self.run_page(self.answers(**{'POST /api/computer': [ok(self.get('computer'))]}),
                               [{'click': 'Status'}, {'click': 'Check this computer'},
                                {'snapshot': 'status'}])
        status = result['snapshots']['status']
        self.assertEqual(status['parts'][0], 'This computer')
        self.assertEqual(status['ledes'], ['What is running, who runs it, and whether this '
                                           'computer has what a deck needs.'])

    def on_settings(self, *steps) -> dict:
        setup = self.setup_with(person={'name': 'Alex Doe'})
        return self.run_page(self.answers(**{'GET /api/setup': [setup]}),
                             [{'click': 'Settings'}, {'snapshot': 'settings'}, *steps])

    def test_settings_has_one_way_to_each_value(self):
        shot = self.on_settings()['snapshots']['settings']
        self.assertEqual(shot['ledes'], ['How Presentation Studio works on this computer; what '
                                         'every studio shares is changed in Shared settings.'])
        self.assertNotIn('What a new deck starts with', shot['parts'])
        self.assertEqual(shot['parts'][:3], ['Shared settings', 'Where new work stops',
                                             'Workspace'])
        shared = shot['text'][shot['text'].index('Shared settings'):
                              shot['text'].index('Where new work stops')]
        self.assertIn('Alex Doe', shared)
        self.assertIn('example', shared)
        self.assertIn('Change shared settings', shot['buttons'])
        self.assertIn('Change the set-up', shot['buttons'])
        self.assertNotIn('Change them', shot['buttons'])
        self.assertEqual(shot['filled'], [])

    def test_set_up_has_a_one_sentence_lede(self):
        shot = self.on_settings({'click': 'Change the set-up'},
                             {'snapshot': 'setup'})['snapshots']['setup']
        self.assertEqual(shot['ledes'], ['Say where your team keeps its decks and what a new '
                                         'deck starts with.'])
        self.assertIn('nothing is changed until you save', shot['text'])

    def test_moved_controls_on_home_status_and_settings_are_reachable(self):
        result = self.on_settings({'click': 'Change the set-up'}, {'snapshot': 'setup'})
        self.assertEqual(result['snapshots']['setup']['heading'], 'Set-up')
        result = self.on_settings({'click': 'Change shared settings'}, {'snapshot': 'away'})
        self.assertEqual(result['snapshots']['away']['href'], '/onboarding/#token=the-test-key')


if __name__ == '__main__':
    unittest.main()
