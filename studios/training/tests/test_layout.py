"""The layout pass: each screen in the order a person works, run for real in page_harness.js.

Every journey here is held to the layout rules on every snapshot (`run_page` with
`layout=True`): one lede at most, one heading level in a card, no card inside a card, and a
toolbar whose one filled action comes first with the rest quiet. Nothing starts an agent,
looks at the real computer or touches the network.
"""
import unittest
from urllib.parse import urlencode

import test_desk
from test_desk import SET_UP, a_run, ok, steps


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

    def three(self) -> dict:
        """Three trainings: one at a gate, one in progress and one finished."""
        self.started()
        self.at_the_questions_gate()
        going, done = self.another('going'), self.another('done')
        found = self.read('trainings')
        for item in found['body']['trainings']:
            if item['path'] == str(going):
                item.update(state='in-progress', sentence='Drafting the guide.')
            elif item['path'] == str(done):
                item.update(state='finished', sentence='Finished.', ready=True)
        return found

    # --- the toolbar ---------------------------------------------------------------

    def test_the_filled_action_comes_first_and_the_rest_are_quiet(self):
        self.started()
        self.at_the_questions_gate()
        result = self.run_page(self.answers(), [{'snapshot': 'home'}])
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


    # --- Home, the detail, Status, Settings, the index and set-up ---------------------

    def test_home_puts_what_needs_you_first_and_setup_after_ways_to_start(self):
        result = self.run_page(self.answers(**{'GET /api/trainings': [self.three()]}),
                               [{'snapshot': 'home'}])
        home = result['snapshots']['home']
        self.assertEqual(home['ledes'], ['What needs you comes first, then trainings in '
                                         'progress, then ways to start one.'])
        parts = home['parts']
        self.assertEqual(parts[:2], ['Needs you', 'In progress'])
        self.assertIn('Start a training', parts)
        self.assertLess(parts.index('Start a training'), parts.index('Finished'))
        for later in ('Updates', 'Your other studios'):
            if later in parts:
                self.assertLess(parts.index('Start a training'), parts.index(later))
                self.assertLess(parts.index(later), parts.index('Finished'))
        # The greeting stays above the lede.
        self.assertLess(home['text'].index('Good '), home['text'].index('What needs you'))
        self.assertIn('New training', home['buttons'])

    def test_the_detail_leads_with_what_is_in_the_way_and_hides_empty_cards(self):
        self.started()
        found = self.read('trainings')
        for item in found['body']['trainings']:
            item['run'] = None
        detail = self.read('training', path=str(self.root))
        detail['body']['view'].update(blocking=['The guide is not approved yet.'],
                                      warnings=[], limitations=[])
        result = self.run_page(self.answers(**{'GET /api/trainings': [found],
                                               'GET /api/training': [detail]}), [
            {'click': 'Trainings'}, {'click': 'Open Rolling restarts'},
            {'snapshot': 'detail'}])
        shot = result['snapshots']['detail']
        self.assertEqual(shot['heading'], 'Rolling restarts')
        self.assertLess(shot['parts'].index('In the way'), shot['parts'].index('Files'))
        for absent in ('No warnings.', 'Nothing was left out.', 'Warnings',
                       'Left out or limited'):
            self.assertNotIn(absent, shot['text'])

    def test_status_shows_the_check_first(self):
        self.started()
        result = self.run_page(self.answers(), [{'click': 'Status'}, {'snapshot': 'status'}])
        status = result['snapshots']['status']
        self.assertEqual(status['parts'][0], 'This computer')
        self.assertEqual(status['ledes'], ['What is running, who runs it, and whether this '
                                           'computer has what a training needs.'])
        self.assertEqual(status['toolbar'][0]['name'], 'Check this computer')

    def test_settings_has_one_lede_and_one_versions_link(self):
        self.started()
        held = {**SET_UP, 'updates': {'look': True},
                'brand': {'repository': 'git@example.com:team/brand.git', 'release': ''}}
        result = self.run_page(self.answers(held), [{'click': 'Settings'},
                                                    {'snapshot': 'settings'}],
                               notifications='default')
        shot = result['snapshots']['settings']
        self.assertEqual(shot['ledes'], ['How Training Studio works on this computer; what every '
                                         'studio shares is changed in Shared settings.'])
        self.assertEqual(shot['buttons'].count('See the versions'), 1)
        self.assertIn('Turn on notifications', shot['buttons'])
        self.assertEqual(shot['filled'], [])
        parts = [part for part in shot['parts'] if part in (
            'Shared settings', 'Where new work stops', 'Workspace',
            'Where each training is decided', 'Brand skill', 'Updates', 'Notifications',
            'Preview files in your Google Drive', 'This page')]
        self.assertEqual(parts[0], 'Shared settings')
        self.assertEqual(parts[-1], 'This page')
        self.assertLess(parts.index('Workspace'), parts.index('Where each training is decided'))
        self.assertLess(parts.index('Where each training is decided'), parts.index('Notifications'))
        self.assertLess(parts.index('Brand skill'), parts.index('Updates'))
        self.assertLess(parts.index('Updates'), parts.index('Notifications'))

    def test_the_index_downloads_from_its_toolbar(self):
        self.started()
        over = 'Finished, and ready to use.'
        index = '# Rolling restarts\n\nPlatform engineers new to it.\n'
        read = ok({'artifact': 'README.md', 'file': 'README.md', 'size': len(index),
                   'binary': False, 'text': index, 'truncated': False})
        answers = self.answers(**{
            'GET /api/trainings': [self.listed('done', over)],
            'GET /api/training': [self.detail('done', over)],
            'GET /api/run': [a_run('done', over, steps=steps(*['done'] * 7), finished={
                'ready': True, 'limitations': [], 'blocking': [], 'index': 'README.md'})],
            'GET /api/file': [read]})
        result = self.run_page(answers, [{'click': 'Open Rolling restarts'},
                                         {'click': 'Open the index'}, {'snapshot': 'index'}])
        shot = result['snapshots']['index']
        self.assertEqual(shot['toolbar'][0], {'name': 'Download the index', 'filled': True,
                                              'quiet': False})
        self.assertEqual(shot['ledes'], ['Everything this training made, with where each file '
                                         'is.'])

    def test_set_up_has_one_heading_per_card(self):
        fresh = {**SET_UP, 'configured': False, 'workspace': None}
        result = self.run_page(self.answers(fresh), [{'snapshot': 'set-up'}])
        shot = result['snapshots']['set-up']
        self.assertEqual(shot['heading'], 'Set up Training Studio')
        self.assertTrue(shot['cardHeadings'])
        for tags in shot['cardHeadings']:
            self.assertLessEqual(len(tags), 1, tags)
        self.assertIn('Checked for you', shot['text'])


if __name__ == '__main__':
    unittest.main()
