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


    # --- Trainings and Published ---------------------------------------------------

    def four(self) -> dict:
        """Four trainings the page runs: one needs you, one in progress, two finished, every
        one paused or done, so each may be deleted from here."""
        self.started()
        self.at_the_questions_gate()
        going = self.another('going')
        first, second = self.another('capacity'), self.another('failover')
        found = self.read('trainings')
        for item in found['body']['trainings']:
            item['run'] = {'state': 'paused', 'sentence': 'Paused.'}
            if item['path'] == str(going):
                item.update(state='in-progress', sentence='Drafting the guide.')
            elif item['path'] in (str(first), str(second)):
                item.update(state='finished', sentence='Finished.', ready=True,
                            run={'state': 'done', 'sentence': 'Finished.'})
        self.paths = {item['title']: item['path'] for item in found['body']['trainings']}
        return found

    def trainings(self, steps: list, found: dict | None = None, **more) -> dict:
        answers = self.answers(**{'GET /api/trainings': [found or self.four()], **more})
        return self.run_page(answers, [{'click': 'Trainings'}, *steps])

    def test_trainings_filter_by_where_it_stands(self):
        result = self.trainings([
            {'snapshot': 'all'},
            {'fill': 'Where it stands', 'value': 'finished'}, {'snapshot': 'finished'},
            {'fill': 'Search', 'value': 'capacity'}, {'snapshot': 'typed'},
            {'click': 'Search'}, {'snapshot': 'searched'}])
        shots = result['snapshots']
        self.assertEqual(shots['all']['ledes'], ['4 trainings on this computer, the one that '
                                                 'changed last first.'])
        self.assertEqual(shots['all']['toolbar'][0]['name'], 'New training')
        self.assertIn('4 of 4 trainings match.', shots['all']['text'])
        self.assertIn('2 of 4 trainings match.', shots['finished']['text'])
        self.assertNotIn('Going', shots['finished']['text'])
        # Typing searches nothing until Search is pressed.
        self.assertIn('2 of 4 trainings match.', shots['typed']['text'])
        self.assertIn('1 of 4 trainings match.', shots['searched']['text'])
        self.assertIn('Capacity', shots['searched']['text'])
        self.assertNotIn('Failover', shots['searched']['text'])

    def test_a_phone_shows_search_and_a_filters_button(self):
        answers = self.answers(**{'GET /api/trainings': [self.four()]})
        result = self.run_page(answers, [
            {'click': 'Trainings'}, {'snapshot': 'phone'}, {'click': 'Filters'},
            {'fill': 'Where it stands', 'value': 'finished'}, {'snapshot': 'chosen'}],
            narrow=True)
        phone = result['snapshots']['phone']
        self.assertNotIn('Where it stands', phone['fields'])
        self.assertIn('Filters', phone['buttons'])
        self.assertIn('Search', phone['fields'])
        self.assertIn('Filters (1)', result['snapshots']['chosen']['buttons'])

    def test_ticks_survive_filter_changes_and_the_bar_says_so(self):
        result = self.trainings([
            {'fill': 'Where it stands', 'value': 'finished'},
            {'tick': 'Select Capacity'}, {'tick': 'Select Failover'},
            {'snapshot': 'ticked'},
            {'fill': 'Where it stands', 'value': 'needs-you'}, {'snapshot': 'hidden'},
            {'click': 'Clear'}, {'snapshot': 'cleared'}])
        shots = result['snapshots']
        self.assertIn('2 selected', shots['ticked']['bar'])
        self.assertIn('Delete 2 trainings', shots['ticked']['buttons'])
        self.assertIn('2 selected', shots['hidden']['bar'])
        self.assertIn('2 of them are not in this view.', shots['hidden']['bar'])
        self.assertEqual(shots['cleared']['bar'], '')
        self.assertEqual(shots['cleared']['ticked'], [])
        self.assertEqual(self.posts(result), [])

    def test_select_all_on_this_page_ticks_what_is_shown(self):
        result = self.trainings([
            {'fill': 'Where it stands', 'value': 'finished'},
            {'tick': 'Select all on this page'}, {'snapshot': 'all'}])
        shot = result['snapshots']['all']
        self.assertIn('2 selected', shot['bar'])
        self.assertEqual(sorted(shot['ticked']), ['Select Capacity',
                                                  'Select Failover',
                                                  'Select all on this page'])

    def test_deleting_several_trainings_asks_first_and_carries_on_past_a_refusal(self):
        found = self.four()
        paths = self.paths
        asked = {f"GET /api/delete?{urlencode({'path': path})}": [test_desk.leaving(
            path, 'paused', may=title != 'Going', title=title,
            why=None if title != 'Going' else 'Someone else runs it.')]
            for title, path in paths.items()}
        result = self.trainings([
            {'fill': 'Where it stands', 'value': ''},
            {'tick': 'Select Going'}, {'tick': 'Select Capacity'},
            {'tick': 'Select Failover'},
            {'click': 'Delete 3 trainings'}, {'snapshot': 'asked'},
            {'click': 'Delete 2 trainings'}, {'snapshot': 'done'}], found=found,
            **asked, **{'POST /api/delete': [ok({'notice': None})]})
        shots = result['snapshots']
        sheet = shots['asked']['sheet']
        self.assertIn('Delete 3 trainings?', sheet)
        self.assertIn('Going: Someone else runs it. It stays.', sheet)
        self.assertIn('Capacity: its folder and what only this computer kept for it.',
                      sheet)
        self.assertEqual(shots['asked']['posts'], 0)
        gets = [request['address'] for request in result['requests']
                if request['address'].startswith('/api/delete')
                and request['method'] == 'GET']
        self.assertEqual(len(gets), 3)
        self.assertEqual(shots['asked']['filled'], [])
        self.assertEqual(sorted(body['title'] for _, body in self.posts(result)),
                         ['Capacity', 'Failover'])
        self.assertEqual({address for address, _ in self.posts(result)}, {'/api/delete'})
        self.assertIn('Deleted 2 of 2 trainings.', shots['done']['toasts'])

    def test_a_failed_delete_is_named_and_the_others_go(self):
        found = self.four()
        paths = self.paths
        asked = {f"GET /api/delete?{urlencode({'path': path})}": [test_desk.leaving(
            path, 'paused', title=title)] for title, path in paths.items()}
        result = self.trainings([
            {'fill': 'Where it stands', 'value': 'finished'},
            {'tick': 'Select all on this page'},
            {'click': 'Delete 2 trainings'}, {'click': 'Delete 2 trainings'},
            {'snapshot': 'done'}], found=found, **asked, **{'POST /api/delete': [
                {'status': 409, 'body': {'error': 'It is working now.'}}, ok({'notice': None})]})
        posted = [body['title'] for _, body in self.posts(result)]
        self.assertEqual(len(posted), 2)
        toast = result['snapshots']['done']['toasts']
        self.assertIn('Deleted 1 of 2 trainings. ' + posted[0] + ': It is working now.', toast)

    def test_a_conversation_mode_list_has_filters_too(self):
        self.started()
        plain = {'GET /api/trainings': [self.read('trainings')],
                 'GET /api/computer': [self.read('computer')]}
        result = self.run_page(plain, [{'click': 'Trainings'}, {'snapshot': 'list'}])
        shot = result['snapshots']['list']
        self.assertIn('Where it stands', shot['fields'])
        self.assertNotIn('New training', shot['buttons'])
        self.assertEqual(shot['bar'], '')

    def test_published_is_a_table_with_one_open_per_row(self):
        self.started()
        other = str(self.another('blue-green'))
        entries = [
            {'path': str(self.root), 'id': 'rolling-restarts', 'title': 'Rolling restarts',
             'revision': 3, 'at': '2026-10-20T09:00:00Z', 'by': 'Dana', 'ready': False,
             'current': True},
            {'path': other, 'id': 'blue-green', 'title': 'Blue-green deploys',
             'revision': 1, 'at': '2026-10-16T09:00:00Z', 'by': 'Pat', 'ready': True,
             'current': True}]
        answers = self.answers(**{'GET /api/published': [ok({'published': entries})]})
        result = self.run_page(answers, [
            {'click': 'Trainings'}, {'click': 'Published'}, {'snapshot': 'list'},
            {'fill': 'Ready to use', 'value': 'not-ready'}, {'snapshot': 'not ready'},
            {'click': 'More filters'}, {'snapshot': 'more'}])
        shots = result['snapshots']
        shot = shots['list']
        self.assertEqual(shot['ledes'], ['2 trainings are published in this workspace, each '
                                         'shown at its latest revision.'])
        opens = [name for name in shot['buttons'] if name.startswith('Open the index')]
        self.assertEqual(opens, ['Open the index of Rolling restarts',
                                 'Open the index of Blue-green deploys'])
        for column in ('Training', 'Revision', 'Published', 'Ready to use'):
            self.assertIn(column, shot['text'])
        self.assertIn('A revision is never moved once it is published.', shot['text'])
        self.assertNotIn('Published by', shot['fields'])
        left = shots['not ready']
        self.assertIn('Rolling restarts', left['text'])
        self.assertNotIn('Blue-green deploys', left['text'])
        self.assertIn('Published by', shots['more']['fields'])
        self.assertEqual(shot['bar'], '')

    def test_moved_controls_on_the_lists_are_reachable(self):
        result = self.trainings([{'snapshot': 'list'}])
        shot = result['snapshots']['list']
        self.assertIn('Search', shot['fields'])
        self.assertIn('Delete Going', shot['buttons'])
        self.assertIn('Published', shot['buttons'])


if __name__ == '__main__':
    unittest.main()
