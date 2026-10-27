"""The layout pass: each screen in the order a person works, run for real in page_harness.js.

Every journey here is held to the layout rules on every snapshot (`run_page` with
`layout=True`): one lede at most, one heading level in a card, no card inside a card, and a
toolbar whose one filled action comes first with the rest quiet. Nothing starts an agent,
looks at the real computer or touches the network.
"""
import unittest
from urllib.parse import urlencode

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


    # --- Decks and Published -------------------------------------------------------

    def four(self) -> dict:
        """Four decks: one needs you, one working from a document, two finished from scratch."""
        self.started(title='Waiting deck')
        brief = self.get('decks')['needs'][0]

        def like(title, state, route, needs=False):
            name = title.lower().replace(' ', '-')
            return {**brief, 'path': '/decks/' + name, 'id': name, 'title': title,
                    'state': state, 'route': route, 'needs': needs, 'sentence': title + '.'}
        return {'needs': [like('Waiting deck', 'waiting', 'scratch', True)],
                'working': [like('Document deck', 'working', 'document')],
                'finished': [like('Capacity planning', 'finished', 'scratch'),
                             like('Rollback drill', 'finished', 'scratch')],
                'elsewhere': []}

    def decks(self, steps, decks=None, narrow=False, **more) -> dict:
        decks = decks or self.four()
        return self.run_page(self.answers(**{'GET /api/decks': [ok(decks)], **more}),
                             [{'click': 'Decks'}, *steps], narrow=narrow)

    def opens(self, shot) -> list:
        return sorted(name[len('Open '):] for name in shot['buttons'] if name.startswith('Open '))

    def test_decks_filter_by_where_it_stands_and_how_it_began(self):
        result = self.decks([
            {'snapshot': 'all'},
            {'fill': 'Where it stands', 'value': 'finished'}, {'snapshot': 'finished'},
            {'fill': 'How it began', 'value': 'document'}, {'snapshot': 'none'},
            {'fill': 'How it began', 'value': ''}, {'fill': 'Where it stands', 'value': ''},
            {'fill': 'Search', 'value': 'capacity', 'stay': True}, {'snapshot': 'typed'},
            {'click': 'Search'}, {'snapshot': 'searched'}])
        shots = result['snapshots']
        self.assertEqual(shots['all']['ledes'], ['Every deck in this workspace, to find, open or '
                                                 'delete.'])
        self.assertIn('4 decks.', shots['all']['text'])
        self.assertEqual(self.opens(shots['finished']), ['Capacity planning', 'Rollback drill'])
        self.assertIn('2 of 4 decks match.', shots['finished']['text'])
        self.assertEqual(self.opens(shots['none']), [])
        self.assertIn('0 of 4 decks match.', shots['none']['text'])
        self.assertEqual(len(self.opens(shots['typed'])), 4)
        self.assertEqual(self.opens(shots['searched']), ['Capacity planning'])
        self.assertEqual(shots['all']['toolbar'][0], {'name': 'New deck', 'filled': True,
                                                      'quiet': False})

    def test_a_phone_shows_search_and_a_filters_button(self):
        result = self.decks([
            {'snapshot': 'phone'}, {'click': 'Filters'}, {'snapshot': 'open'},
            {'fill': 'Where it stands', 'value': 'finished'}, {'snapshot': 'chosen'}],
            narrow=True)
        shots = result['snapshots']
        self.assertNotIn('Where it stands', shots['phone']['fields'])
        self.assertIn('Search', shots['phone']['fields'])
        self.assertIn('Filters', shots['phone']['buttons'])
        self.assertIn('Where it stands', shots['open']['fields'])
        self.assertIn('Filters (1)', shots['chosen']['buttons'])
        desktop = self.decks([{'snapshot': 'wide'}])['snapshots']['wide']
        self.assertNotIn('Filters', desktop['buttons'])
        self.assertIn('Where it stands', desktop['fields'])

    def test_ticks_survive_filter_changes_and_the_bar_says_so(self):
        result = self.decks([
            {'snapshot': 'none'},
            {'tick': 'Select Capacity planning'}, {'tick': 'Select Rollback drill'},
            {'snapshot': 'two'},
            {'fill': 'Where it stands', 'value': 'needs'}, {'snapshot': 'hidden'},
            {'click': 'Clear'}, {'snapshot': 'cleared'}])
        shots = result['snapshots']
        self.assertEqual(shots['none']['bar'], '')
        self.assertIn('2 selected', shots['two']['bar'])
        self.assertIn('Delete 2 decks', shots['two']['buttons'])
        self.assertEqual(sorted(shots['two']['ticked']), ['Select Capacity planning',
                                                          'Select Rollback drill'])
        self.assertIn('2 selected', shots['hidden']['bar'])
        self.assertIn('2 of them are not in this view.', shots['hidden']['bar'])
        self.assertEqual(shots['cleared']['bar'], '')
        self.assertEqual(shots['cleared']['ticked'], [])
        # Delete is a danger button, so the screen keeps its one filled one.
        self.assertEqual(shots['two']['filled'], ['New deck'])

    def test_select_all_on_this_page_ticks_every_deck_shown(self):
        result = self.decks([{'tick': 'Select all on this page'}, {'snapshot': 'all'}])
        self.assertIn('4 selected', result['snapshots']['all']['bar'])

    def previews(self, decks, refused=()):
        answers = {}
        for kind in ('needs', 'working', 'finished'):
            for brief in decks[kind]:
                found = ({'path': brief['path'], 'title': brief['title'], 'may': False,
                          'why': 'Someone else runs it.'} if brief['title'] in refused else
                         {'path': brief['path'], 'title': brief['title'], 'may': True,
                          'documents': 0, 'revisions': 0, 'drive': [], 'share': None})
                answers['GET /api/delete?' + urlencode({'path': brief['path']})] = [ok(found)]
        return answers

    def test_deleting_several_decks_asks_first_and_carries_on_past_a_refusal(self):
        decks = self.four()
        result = self.decks([
            {'tick': 'Select Document deck'}, {'tick': 'Select Capacity planning'},
            {'tick': 'Select Rollback drill'},
            {'click': 'Delete 3 decks'}, {'snapshot': 'asked'},
            {'click': 'Delete 2 decks'}, {'snapshot': 'done'}], decks=decks,
            **self.previews(decks, refused=('Capacity planning',)),
            **{'POST /api/delete': [ok({}), ok({})]})
        shots = result['snapshots']
        asked = shots['asked']
        self.assertIn('Delete 3 decks?', asked['sheet'])
        self.assertIn('Capacity planning: Someone else runs it. It stays.', asked['sheet'])
        self.assertIn('Document deck: its folder and what only this computer kept for it.',
                      asked['sheet'])
        self.assertIn('This cannot be undone from this page.', asked['sheet'])
        self.assertEqual(asked['posts'], 0)
        reads = [request for request in result['requests']
                 if request['address'].startswith('/api/delete')]
        self.assertEqual([request['method'] for request in reads[:3]], ['GET'] * 3)
        self.assertEqual(asked['filled'], [])
        posted = self.posts(result)
        self.assertEqual(posted, [('/api/delete', {'path': '/decks/document-deck',
                                                   'title': 'Document deck'}),
                                  ('/api/delete', {'path': '/decks/rollback-drill',
                                                   'title': 'Rollback drill'})])
        self.assertIn('Deleted 2 of 2 decks.', shots['done']['text'])
        self.assertEqual(shots['done']['sheet'], '')

    def test_a_failed_delete_is_named_and_the_others_go(self):
        decks = self.four()
        result = self.decks([
            {'tick': 'Select Capacity planning'}, {'tick': 'Select Rollback drill'},
            {'click': 'Delete 2 decks'}, {'click': 'Delete 2 decks'}, {'snapshot': 'done'}],
            decks=decks, **self.previews(decks),
            **{'POST /api/delete': [{'status': 409, 'body': {'error': 'It is working now.'}},
                                    ok({})]})
        self.assertEqual(len(self.posts(result)), 2)
        self.assertIn('Deleted 1 of 2 decks. Capacity planning: It is working now.',
                      result['snapshots']['done']['text'])

    def test_published_is_a_table_with_one_open_per_row(self):
        published = [{'path': '/decks/a', 'title': 'Capacity planning', 'revision': 2,
                      'at': '2026-10-20T10:00:00Z', 'by': 'Sam Lee', 'ready': True,
                      'current': True},
                     {'path': '/decks/b', 'title': 'Rollback drill', 'revision': 1,
                      'at': '2026-10-21T10:00:00Z', 'by': 'Alex Doe', 'ready': False,
                      'current': True}]
        result = self.run_page(self.answers(**{'GET /api/published': [ok({'published':
                                                                          published})]}), [
            {'click': 'Decks'}, {'click': 'Published'}, {'snapshot': 'all'},
            {'fill': 'Delivered', 'value': 'no'}, {'snapshot': 'waiting'},
            {'click': 'More filters'}, {'snapshot': 'more'}])
        shots = result['snapshots']
        everything = shots['all']
        self.assertEqual(everything['ledes'], ['2 decks are published in this workspace, each at '
                                               'its latest revision.'])
        self.assertEqual([name for name in everything['buttons'] if name.startswith('Open ')],
                         ['Open Capacity planning', 'Open Rollback drill'])
        self.assertIn('A revision is never moved once it is published.', everything['text'])
        self.assertNotIn('Published by', everything['fields'])
        self.assertEqual([name for name in shots['waiting']['buttons'] if name.startswith('Open ')],
                         ['Open Rollback drill'])
        self.assertIn('Published by', shots['more']['fields'])
        self.assertNotIn('Published decks', everything['parts'])

    def test_find_a_deck_and_delete_are_reachable(self):
        shot = self.decks([{'snapshot': 'decks'}])['snapshots']['decks']
        self.assertIn('Search', shot['buttons'])
        self.assertIn('Search', shot['fields'])
        for title in ('Waiting deck', 'Document deck', 'Capacity planning', 'Rollback drill'):
            self.assertIn('Delete ' + title, shot['buttons'])


if __name__ == '__main__':
    unittest.main()
