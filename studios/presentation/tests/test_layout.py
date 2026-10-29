"""The layout pass: each screen in the order a person works, run for real in page_harness.js.

Every journey here is held to the layout rules on every snapshot (`run_page` with
`layout=True`): one lede at most, one heading level in a card, no card inside a card, and a
toolbar whose one filled action comes first with the rest quiet. Nothing starts an agent,
looks at the real computer or touches the network.
"""
import base64
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

import test_desk
import test_runner_page
from runner_support import read_word_for_word
from test_desk import DECK, PICTURE, ok

NOT_THERE = {'GET /api/run': [{'status': 404, 'body': {'error': 'There is no deck there.'}}]}


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
        path = self.saved_started(title=title)
        for _ in range(20):
            if self.run_of(path)['gate'] is None:
                break
            self.decided(path)
        return path

    def every_kind(self) -> dict:
        """Decks needing you, working and finished, as the runner lists them."""
        self.saved_started(title='Waiting deck')
        self.finished('Finished deck')
        decks = self.get('decks')
        working = {**decks['needs'][0], 'path': '/elsewhere/working', 'id': 'working',
                   'title': 'Working deck', 'state': 'working', 'needs': False,
                   'sentence': 'Drafting the outline.'}
        decks['working'] = [working]
        return decks

    # --- the toolbar ---------------------------------------------------------------

    def test_the_filled_action_comes_first_and_the_rest_are_quiet(self):
        self.saved_started(title='Waiting deck')
        result = self.run_page(self.answers(), [{'snapshot': 'home'}])
        bar = result['snapshots']['home']['toolbar']
        self.assertEqual(bar[0], {'name': 'Review Waiting deck', 'filled': True, 'quiet': False})
        self.assertGreater(len(bar), 1)
        self.assertEqual([control for control in bar[1:] if not control['quiet']], [])

    def test_a_phone_wraps_the_toolbar_and_has_no_more_menu(self):
        path = self.saved_started(title='Paused deck')
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
        self.saved_started(title='Waiting deck')
        result = self.run_page(self.answers(), [
            {'click': 'Start from a document'}, {'snapshot': 'document'}])
        shot = result['snapshots']['document']
        # Home's way in opens the desk's start at that kind, with the document asked for.
        self.assertIn('3. What you have', shot['parts'])
        self.assertIn('Paste the text', shot['buttons'])
        self.assertEqual(shot['heading'], 'Home')

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
        self.saved_started(title='Waiting deck')
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


    # --- the new-deck sheet, Bring in a deck, and the research choice ---------------

    def test_new_deck_is_one_sheet_in_numbered_steps(self):
        result = self.run_page(self.answers(), [
            {'click': 'New deck'}, {'snapshot': 'routes'},
            {'click': 'A document'}, {'snapshot': 'document'}])
        shots = result['snapshots']
        self.assertEqual(shots['routes']['heading'], 'Home')
        self.assertIn('1. Kind of deck', shots['routes']['sheet'])
        sheet = shots['document']['sheet']
        steps = ['1. Kind of deck', '2. Sources and settings', '3. What you have']
        self.assertEqual([step for step in steps if step in sheet], steps)
        self.assertEqual(sorted(steps, key=sheet.index), steps)
        self.assertNotIn('4. ', sheet)
        self.assertTrue(sheet.rstrip().endswith('Start\nCancel'), sheet[-200:])
        self.assertEqual(shots['document']['filled'], ['Start'])
        self.assertEqual(shots['document']['heading'], 'Home')

    def test_an_idea_has_the_same_three_steps_with_its_brief_and_no_document(self):
        result = self.run_page(self.answers(), [
            {'click': 'New deck'}, {'click': 'An idea'}, {'snapshot': 'idea'}])
        sheet = result['snapshots']['idea']['sheet']
        for step in ('1. Kind of deck', '2. Sources and settings', '3. What you have'):
            self.assertIn(step, sheet)
        self.assertNotIn('4. ', sheet)
        self.assertIn('What should it cover? (optional)', sheet)
        self.assertNotIn('Where the document is', sheet)

    def test_start_checks_every_step_and_focuses_the_first_gap(self):
        result = self.run_page(self.answers(), [
            {'click': 'New deck'}, {'click': 'A document'},
            {'click': 'Start'}, {'snapshot': 'missing'}])
        missing = result['snapshots']['missing']
        self.assertEqual(missing['posts'], 0)
        self.assertIn('Something above is missing.', missing['sheet'])
        self.assertIn('Choose the file first.', missing['sheet'])
        self.assertIn('Give it a title first.', missing['sheet'])
        # The desk's start asks for the title before the document, in its third step.
        self.assertEqual(missing['focus'], 'new-title')

    def test_the_sheet_sends_what_the_wizard_sent(self):
        answers = self.answers(**{'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})],
                                  **NOT_THERE})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An existing deck'},
            {'attach': 'The deck, as a .pptx',
             'files': [{'name': 'old.pptx', 'bytes': DECK.decode('latin-1')}]},
            {'click': 'Selected changes'}, {'click': 'Polish'},
            {'fill': 'A short title', 'value': 'Old deck'}, {'click': 'Start'}])
        (address, body), = self.posts(result)
        self.assertEqual(address, '/api/decks')
        form = body['form']
        self.assertEqual((form['route'], form['level'], form['source'], form['title'],
                          form['flow']),
                         ('existing', 'polish', {'kind': 'upload', 'name': 'old.pptx'},
                          'Old deck', 'desk'))
        self.assertEqual(base64.b64decode(body['uploads']['old.pptx']), DECK)
        self.workers.queued['outline'] = [read_word_for_word(self)]
        self.assertEqual(self.run_of(self.post('decks', body)['path'])['gate']['name'],
                         'gate:build')

    def test_cancel_keeps_the_draft_for_the_session(self):
        result = self.run_page(self.answers(), [
            {'click': 'New deck'}, {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Kept for later'}, {'click': 'Cancel'},
            {'snapshot': 'closed'}, {'click': 'New deck'}, {'snapshot': 'again'}])
        shots = result['snapshots']
        self.assertEqual(shots['closed']['sheet'], '')
        self.assertEqual(shots['again']['fields']['A short title'], 'Kept for later')
        self.assertEqual(result['requests'][-1]['method'], 'GET')
        self.assertEqual(self.posts(result), [])

    def test_screen_new_still_opens_the_form(self):
        result = self.run_page(self.answers(), [{'snapshot': 'opened'}],
                               state={'screen': 'new', 'path': None})
        opened = result['snapshots']['opened']
        self.assertEqual(opened['heading'], 'Home')
        self.assertIn('1. Kind of deck', opened['sheet'])

    def test_research_from_is_ticks(self):
        sites = ['blog.example.com/platform', 'docs.example.com']
        answers = self.answers(**{'GET /api/setup': [self.setup_with(research_sites=sites)],
                                  'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})],
                                  **NOT_THERE})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Synthetic deck'},
            {'click': 'Research first'}, {'snapshot': 'research'},
            {'tick': 'your sites'}, {'snapshot': 'sites'},
            {'tick': 'the public web'}, {'snapshot': 'off'}, {'click': 'Start'}])
        shots = result['snapshots']
        self.assertEqual(shots['research']['ticked'], ['the public web'])
        self.assertIn('Research from', shots['research']['sheet'])
        self.assertEqual(shots['sites']['ticked'], ['your sites (2)', 'the public web', *sites])
        self.assertEqual(shots['off']['ticked'], ['your sites (2)', *sites])
        (_, body), = self.posts(result)
        self.assertEqual(body['form']['research_from'],
                         {'documents': False, 'sites': sites, 'web': False})

    def test_bring_in_a_deck_picks_then_brings(self):
        known = [{'title': 'Old deck', 'path': '/old/a'}, {'title': 'Other deck', 'path': '/old/b'}]
        self.saved_started(title='Waiting deck')
        answers = self.answers(**{'GET /api/known-decks': [ok({'decks': known})],
                                  'POST /api/bring': [ok({'path': '/nowhere'})], **NOT_THERE})
        result = self.run_page(answers, [
            {'click': 'Decks'}, {'click': 'Bring in a deck'}, {'snapshot': 'picks'},
            {'click': 'Other deck'}, {'snapshot': 'picked'}, {'click': 'Bring it in'}])
        shots = result['snapshots']
        sheet = shots['picks']['sheet']
        self.assertIn('1. Choose the deck', sheet)
        self.assertTrue(sheet.rstrip().endswith('Bring it in\nCancel'), sheet[-120:])
        self.assertEqual(shots['picks']['posts'], 0)
        self.assertIn('Bring it in', shots['picks']['off'])
        self.assertEqual(shots['picked']['filled'], ['Bring it in'])
        self.assertEqual(shots['picked']['posts'], 0)
        self.assertEqual(self.posts(result), [('/api/bring', {'path': '/old/b'})])

    def test_back_a_step_and_another_way_to_begin_are_gone(self):
        result = self.run_page(self.answers(), [
            {'click': 'New deck'}, {'snapshot': 'routes'}, {'click': 'A document'},
            {'snapshot': 'document'}])
        for shot in result['snapshots'].values():
            for gone in ('Back a step', 'Another way to begin', 'Continue'):
                self.assertNotIn(gone, shot['buttons'])
        sheet = result['snapshots']['document']['sheet']
        self.assertLess(sheet.index('1. Kind of deck'), sheet.index('An idea'))
        self.assertLess(sheet.index('An existing deck'), sheet.index('2. Sources and settings'))


    # --- the deck screen, kept light -----------------------------------------------

    def test_the_deck_opens_with_its_lede(self):
        path = self.saved_started(title='Rolling restarts')
        run = self.run_of(path)
        shot = self.deck_screen(path, [{'snapshot': 'deck'}])['snapshots']['deck']
        self.assertEqual(shot['ledes'], [run['sentence']])
        before = shot['text'][:shot['text'].index(run['sentence'])].rstrip()
        self.assertTrue(before.endswith(shot['toolbar'][-1]['name']), before[-200:])

    def test_undo_sits_beside_the_lede(self):
        path = self.saved_started(title='Paused deck')
        result = self.deck_screen(path, [{'snapshot': 'deck'}, {'click': 'Undo the last step'},
                                         {'snapshot': 'undo'}],
                                  **{'GET /api/run': [ok(self.paused(path))]})
        deck = result['snapshots']['deck']
        self.assertIn('Undo the last step', deck['buttons'])
        self.assertNotIn('Undo the last step', [control['name'] for control in deck['toolbar']])
        self.assertLess(deck['text'].index(self.paused(path)['sentence']),
                        deck['text'].index('Undo the last step', len('Skip')))
        self.assertIn('Undo', result['snapshots']['undo']['sheet'])

    def test_what_needs_you_comes_before_what_is_made(self):
        path = self.saved_started(title='Rolling restarts')
        shown = self.run_of(path)
        shown['build_progress'] = {'incomplete': True, 'slides': [
            {'ref': 'r1', 'number': 1, 'revision': '3f2a1c9b0d4e5f6a', 'title': 'Cover'}]}
        shot = self.deck_screen(path, [{'snapshot': 'deck'}],
                                **{'GET /api/run': [ok(shown)]})['snapshots']['deck']
        parts = shot['parts']
        gate = next(part for part in parts if part in ('The outline', 'Review the direction'))
        for later in ('Slides taking shape', 'Where it is', 'Delete this deck'):
            self.assertIn(later, parts)
        self.assertLess(parts.index(gate), parts.index('Slides taking shape'))
        self.assertLess(parts.index('Slides taking shape'), parts.index('Where it is'))
        self.assertLess(parts.index('Where it is'), parts.index('Delete this deck'))

    def test_the_direction_review_has_no_card_in_a_card(self):
        from studio_core import review_policy
        self.brand.run.offers_looks = True
        with mock.patch.object(review_policy, 'capture',
                               return_value={'schema': 1, 'level': 'balanced'}):
            path = self.saved_started(research=True)
        record = self.engine._load(Path(path))
        record['research_contract'] = {'schema': 2}
        self.engine._store(Path(path), record)
        gate = self.run_of(path)['gate']
        self.assertEqual(gate['label'], 'Review the direction')
        self.assertTrue(gate.get('research', {}).get('text'))
        result = self.deck_screen(path, [
            {'snapshot': 'review'},
            {'fill': 'What should change in the research?', 'value': 'Look at the docs.'},
            {'click': 'Cancel'}, {'snapshot': 'cancelled'}],
            **{'GET /api/slide': [PICTURE] * 3})
        review = result['snapshots']['review']
        self.assertEqual(review['nested'], 0)
        self.assertIn('What should change in the research?', review['fields'])
        text = review['text']
        start = text.index('What should change in the research?')
        self.assertLess(text.index('Research again', start), text.index('Cancel', start))
        self.assertEqual(result['snapshots']['cancelled']['fields']
                         ['What should change in the research?'], '')
        self.assertEqual(self.posts(result), [])

    def test_a_phone_sends_marks_from_the_review_bar(self):
        path = self.saved_started(title='Rolling restarts')
        self.assertEqual(self.run_of(path)['gate']['name'], 'gate:outline')
        phone = self.deck_screen(path, [{'snapshot': 'deck'}], narrow=True)['snapshots']['deck']
        self.assertEqual([control for control in phone['toolbar'] if control['filled']], [])
        self.assertEqual(phone['filled'], ['Approve'])
        self.assertNotIn('Approve', [control['name'] for control in phone['toolbar']])
        desk = self.deck_screen(path, [{'snapshot': 'deck'}])['snapshots']['deck']
        self.assertEqual(desk['toolbar'][0], {'name': 'Approve', 'filled': True, 'quiet': False})
        self.assertEqual(desk['buttons'].count('Approve'), 1)

    def test_a_slide_picture_can_be_cancelled(self):
        path = self.saved_started()
        gate = self.run_of(path)['gate']
        content = next(one for one in gate['slides'] if one.get('kind') == 'content')
        title = content['title']
        result = self.deck_screen(path, [
            {'click': f'Add a picture to “{title}”'}, {'snapshot': 'form'},
            {'fill': 'What it shows', 'value': 'A rack.'}, {'click': 'Cancel'},
            {'snapshot': 'cancelled'}, {'click': f'Add a picture to “{title}”'},
            {'snapshot': 'again'}])
        shots = result['snapshots']
        text = shots['form']['text']
        start = text.index('The picture, a PNG or JPEG file')
        self.assertLess(text.index('Add the picture', start), text.index('Cancel', start))
        self.assertNotIn('What it shows', shots['cancelled']['fields'])
        self.assertEqual(shots['again']['fields']['What it shows'], '')
        self.assertEqual(self.posts(result), [])


    # --- what the review found -------------------------------------------------------

    def test_several_decks_are_told_what_one_is_told_before_they_go(self):
        decks = self.four()
        answers = self.previews(decks)
        for title, share, drive in (('Document deck', 'decision', []),
                                    ('Rollback drill', None, [{'what': 'Preview',
                                                               'name': 'Preview: Rollback drill',
                                                               'url': 'https://drive.google.com/x'}])):
            path = '/decks/' + title.lower().replace(' ', '-')
            answers['GET /api/delete?' + urlencode({'path': path})] = [ok({
                'path': path, 'title': title, 'may': True, 'documents': 0, 'revisions': 0,
                'drive': drive, 'share': share, 'stops': title == 'Document deck'})]
        result = self.decks([
            {'tick': 'Select Document deck'}, {'tick': 'Select Rollback drill'},
            {'click': 'Delete 2 decks'}, {'snapshot': 'asked'},
            {'click': 'Delete 2 decks'}, {'snapshot': 'done'}], decks=decks, **answers,
            **{'POST /api/delete': [ok({'notice': 'Press Share now to tell your team.'}),
                                    ok({})]})
        asked = result['snapshots']['asked']['sheet']
        self.assertIn('Document deck: its folder and what only this computer kept for it. Your '
                      'team sees it gone straight away.', asked)
        self.assertIn('It is working now. Deleting it stops it first', asked)
        self.assertIn('Presentation Studio never deletes anything in your Google Drive.', asked)
        self.assertIn('Preview: Preview: Rollback drill', asked)
        self.assertIn('Deleted 2 of 2 decks. Press Share now to tell your team.',
                      result['snapshots']['done']['text'])

    def test_nothing_can_be_cancelled_or_sent_again_while_several_go(self):
        decks = self.four()
        result = self.decks([
            {'tick': 'Select Capacity planning'}, {'tick': 'Select Rollback drill'},
            {'click': 'Delete 2 decks'}, {'click': 'Delete 2 decks'}, {'snapshot': 'sending'},
            {'key': 'Escape'}, {'snapshot': 'still'}], decks=decks, **self.previews(decks),
            **{'POST /api/delete': [{'pending': True}]})
        sending = result['snapshots']['sending']
        self.assertIn('Cancel', sending['off'])
        self.assertIn('Delete 2 decks', sending['off'])
        self.assertIn('Delete 2 decks?', result['snapshots']['still']['sheet'])
        self.assertEqual(len(self.posts(result)), 1)

    def test_the_sheet_keeps_the_focus_when_it_opens_from_an_address(self):
        self.saved_started(title='Waiting deck')
        result = self.run_page(self.answers(), [
            {'snapshot': 'home'}, {'back': True}, {'snapshot': 'opened'}],
            earlier=[{'screen': 'new', 'path': None}], transitions=True)
        opened = result['snapshots']['opened']
        self.assertIn('1. Kind of deck', opened['sheet'])
        self.assertEqual(opened['focus'], 'sheet')

    def test_a_search_typed_and_not_sent_stays_when_a_choice_changes(self):
        result = self.decks([
            {'fill': 'Search', 'value': 'capacity', 'stay': True},
            {'fill': 'Where it stands', 'value': 'finished'}, {'snapshot': 'chosen'},
            {'click': 'Search'}, {'snapshot': 'searched'}])
        chosen = result['snapshots']['chosen']
        self.assertEqual(chosen['fields']['Search'], 'capacity')
        self.assertEqual(self.opens(chosen), ['Capacity planning', 'Rollback drill'])
        self.assertEqual(self.opens(result['snapshots']['searched']), ['Capacity planning'])
        published = [{'path': '/decks/a', 'title': 'Capacity planning', 'revision': 2,
                      'at': '2026-10-20T10:00:00Z', 'by': 'Sam Lee', 'ready': True,
                      'current': True},
                     {'path': '/decks/b', 'title': 'Rollback drill', 'revision': 1,
                      'at': '2026-10-21T10:00:00Z', 'by': 'Alex Doe', 'ready': True,
                      'current': True}]
        shelf = self.run_page(self.answers(**{'GET /api/published': [ok({'published':
                                                                         published})]}), [
            {'click': 'Decks'}, {'click': 'Published'},
            {'fill': 'Search', 'value': 'rollback', 'stay': True},
            {'fill': 'Delivered', 'value': 'yes'}, {'snapshot': 'chosen'}])['snapshots']['chosen']
        self.assertEqual(shelf['fields']['Search'], 'rollback')
        self.assertEqual(len([name for name in shelf['buttons'] if name.startswith('Open ')]), 2)

    def test_no_two_parts_of_the_new_deck_sheet_share_a_key(self):
        result = self.run_page(self.answers(), [
            {'click': 'New deck'}, {'click': 'An idea'}, {'click': 'Options'},
            {'snapshot': 'options'}])
        self.assertEqual(result['snapshots']['options']['keyedTwice'], [])

    def test_a_phone_keeps_the_review_send_after_a_sheet_closes(self):
        path = self.saved_started(title='Rolling restarts')
        result = self.deck_screen(path, [
            {'click': 'Ask for changes'}, {'snapshot': 'open'}, {'key': 'Escape'},
            {'snapshot': 'closed'}], narrow=True)
        self.assertEqual(result['snapshots']['closed']['filled'], ['Approve'])
        self.assertEqual(result['snapshots']['closed']['sheet'], '')


if __name__ == '__main__':
    unittest.main()
