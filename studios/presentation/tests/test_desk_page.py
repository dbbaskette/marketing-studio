"""The deck desk's page (deck-desk.js), run for real in page_harness.js: the start in three
steps, a desk deck's progress with only the look pick to ask for, and the desk itself, with a
card per slide under its section, the slide and whole-deck notes, Stop, the Outline tab and
Deliver.

Each view the page reads is what the runner's page answers for a real desk deck over the
tests' stand-ins, changed only where a test says so. Nothing starts an agent, looks at the real
computer or touches the network.
"""
import base64
import copy
import json
import unittest
from datetime import UTC, datetime
from unittest import mock

import runner_support
import test_desk
from test_desk import FORBIDDEN_WORDS, NODE, ok
from test_runner_page import PageCase

NOT_THERE = {'GET /api/run': [{'status': 404, 'body': {'error': 'There is no deck there.'}}]}
STARTED = {'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})]}
WORDS_LINE = ('A note changes how the slide is drawn. To change its words, edit them on the '
              'Outline tab.')
NOTHING_NEEDED = 'Nothing needed from you. The deck opens here when it is ready.'
NO_RECORD = 'This computer has no record yet of how long that takes.'
LOOK_PAUSE = 'One thing needs you: pick the look. The deck is drawn in it.'
WAITS = ('The deck cannot be delivered yet: a change to it is still waiting or under way. '
         'Deliver when it is done.')


def cards_of(desk: dict) -> list:
    return [card for part in desk['sections'] for card in part['slides']]


def plan_on(number: int):
    """A scripted plan job for a Selected changes deck: the second run of the slide's second
    object, made shorter."""
    def act(tools, job):
        spec = tools.job['artifacts']['patch']
        plan = {'sourceSha256': spec['sha256'], 'operations': [
            {'slide': number, 'object': '3', 'expectedHash': spec['objects'][f'{number}:3'],
             'runs': [{'index': 1, 'text': 'in minutes.'}]}]}
        made = tools.submit_artifact('patch', json.dumps(plan))
        assert made[0], made[1]
    return act


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class DeskPageCase(test_desk.ScriptedPage, PageCase):
    answers = test_desk.ScreenTests.answers
    setup_with = test_desk.ScreenTests.setup_with

    def setUp(self):
        super().setUp()
        self.brand.run.offers_looks = True
        self.brand.run.guides = True
        self.workers.outline_said = runner_support.LONG_OUTLINE

    def desk_deck(self, **changes) -> str:
        """A deck started from the desk's start with the brand's default look: it runs with
        no stop to the desk."""
        path = self.started(flow='desk', look='default', **changes)
        self.assertEqual(self.run_of(path)['gate']['name'], 'gate:build')
        self.assertTrue(self.run_of(path)['desk']['arrived'])
        return path

    def open_deck(self, path: str, view: dict, steps: list, **more) -> dict:
        """The deck's own screen, opened as a reload opens it, with `view` as its run."""
        return self.run_page(self.answers(**{'GET /api/run': [ok(view)], **more}), steps,
                             state={'screen': 'deck', 'path': path})

    def new_deck(self, steps: list, **more) -> dict:
        return self.run_page(self.answers(**{**STARTED, **NOT_THERE, **more}),
                             [{'click': 'New deck'}, *steps])


class StartTests(DeskPageCase):
    """Task 1.12: New deck opens the desk's start, in three numbered steps."""

    def test_the_start_is_three_numbered_steps(self):
        result = self.new_deck([{'snapshot': 'kinds'}, {'click': 'An idea'},
                                {'snapshot': 'idea'}])
        kinds, idea = result['snapshots']['kinds'], result['snapshots']['idea']
        self.assertEqual(kinds['heading'], 'Home')
        self.assertIn('1. Kind of deck', kinds['parts'])
        for kind in ('An idea', 'A document', 'An existing deck'):
            self.assertTrue(any(name.startswith(kind) for name in kinds['buttons']), kind)
        steps = ['1. Kind of deck', '2. Sources and settings', '3. What you have']
        self.assertEqual([part for part in idea['parts'] if part[:2] in ('1.', '2.', '3.', '4.')],
                         steps)
        self.assertTrue(idea['sheet'].rstrip().endswith('Start\nCancel'), idea['sheet'][-200:])
        self.assertEqual(idea['filled'], ['Start'])
        for shot in (kinds, idea):
            self.assertNotIn('Review level', shot['text'] + shot['sheet'])
            self.assertNotIn('Where it stops', shot['sheet'])
        self.assertNotIn('See the first draft before the deck is checked', idea['buttons'])

    def test_an_idea_sends_the_desk_form(self):
        result = self.new_deck([
            {'click': 'An idea'}, {'fill': 'A short title', 'value': 'Rolling restarts'},
            {'fill': 'What should they take away?', 'value': 'When capacity holds.'},
            {'fill': 'What should it cover? (optional)', 'value': ' Rollback first. '},
            {'click': 'Start'}])
        (address, body), = self.posts(result)
        self.assertEqual(address, '/api/decks')
        form = body['form']
        self.assertEqual((form['route'], form['flow'], form['look'], form['title'],
                          form['notes']),
                         ('scratch', 'desk', 'pick', 'Rolling restarts', 'Rollback first.'))
        for gone in ('review_level', 'review_seen', 'review_default', 'initial_review',
                     'reading'):
            self.assertNotIn(gone, form)
        # What the page sends is what the server takes: a deck on the desk.
        made = self.post('decks', body)
        shown = self.run_of(made['path'])
        self.assertIsNotNone(shown['desk'])
        self.assertEqual(shown['gate']['name'], 'gate:look')

    def test_the_look_choice_is_offered_with_the_default_named_second(self):
        result = self.new_deck([{'click': 'An idea'}, {'snapshot': 'idea'},
                                {'click': 'Use the brand’s default look'},
                                {'fill': 'A short title', 'value': 'Rolling restarts'},
                                {'snapshot': 'default'}, {'click': 'Start'}])
        idea, default = result['snapshots']['idea'], result['snapshots']['default']
        looks = [name for name in idea['buttons']
                 if name in ('Pick it when the samples are drawn', 'Use the brand’s default look')]
        self.assertEqual(looks, ['Pick it when the samples are drawn',
                                 'Use the brand’s default look'])
        self.assertEqual([name for name in idea['pressed'] if name in looks],
                         ['Pick it when the samples are drawn'])
        self.assertIn('Use the brand’s default look', default['pressed'])
        (_, body), = self.posts(result)
        self.assertEqual(body['form']['look'], 'default')
        made = self.post('decks', body)
        self.assertEqual(self.run_of(made['path'])['gate']['name'], 'gate:build')

    def test_a_document_may_say_how_to_read_it(self):
        result = self.new_deck([
            {'click': 'A document'}, {'snapshot': 'document'},
            {'click': 'Paste the text'}, {'fill': 'The text', 'value': 'Synthetic notes.'},
            {'fill': 'A short title', 'value': 'Synthetic deck'},
            {'click': 'It is material to build from'}, {'snapshot': 'material'},
            {'click': 'Start'}])
        document, material = result['snapshots']['document'], result['snapshots']['material']
        for line in ('It lays out the slides', 'It is material to build from'):
            self.assertIn(line, document['buttons'])
        # Unset, the document is read first, as it is now.
        self.assertEqual([name for name in document['pressed']
                          if name.startswith('It ')], [])
        self.assertIn('It is read first, to tell a finished script from material to build '
                      'from.', document['sheet'])
        self.assertIn('It is material to build from', material['pressed'])
        (_, body), = self.posts(result)
        form = body['form']
        self.assertEqual((form['route'], form['flow'], form['reading'], form['source']),
                         ('document', 'desk', 'material', {'kind': 'paste',
                                                           'text': 'Synthetic notes.'}))
        made = self.post('decks', body)
        self.assertEqual(self.run_of(made['path'])['route'], 'document')

    def test_a_document_left_unread_sends_no_reading(self):
        result = self.new_deck([
            {'click': 'A document'}, {'click': 'Paste the text'},
            {'fill': 'The text', 'value': 'Synthetic notes.'},
            {'fill': 'A short title', 'value': 'Synthetic deck'}, {'click': 'Start'}])
        (_, body), = self.posts(result)
        self.assertNotIn('reading', body['form'])

    def test_research_offers_your_documents_your_sites_and_the_web(self):
        sites = ['blog.example.com/platform', 'docs.example.com']
        result = self.new_deck([
            {'click': 'A document'}, {'click': 'Research first'}, {'snapshot': 'research'},
            {'fill': 'What should the research answer? (optional)', 'value': 'Why?'},
            {'click': 'Paste the text'}, {'fill': 'The text', 'value': 'Synthetic notes.'},
            {'fill': 'A short title', 'value': 'Synthetic deck'}, {'click': 'Start'}],
            **{'GET /api/setup': [self.setup_with(research_sites=sites)]})
        shot = result['snapshots']['research']
        self.assertIn('Research from', shot['sheet'])
        for choice in ('your documents', 'your sites (2)', 'the public web'):
            self.assertIn(choice, shot['buttons'])
        self.assertEqual(shot['ticked'], ['your documents'])
        self.assertIn('The research is planned from your questions', shot['sheet'])
        self.assertNotIn('You approve the research plan', shot['sheet'])
        (_, body), = self.posts(result)
        self.assertEqual(body['form']['research_from'],
                         {'documents': True, 'sites': [], 'web': False})
        self.assertEqual(body['form']['research_questions'], ['Why?'])

    def test_the_sources_and_settings_hold_the_deck_s_settings(self):
        result = self.new_deck([{'click': 'An idea'}, {'snapshot': 'idea'},
                                {'click': 'Options'}, {'snapshot': 'options'}])
        idea, options = result['snapshots']['idea'], result['snapshots']['options']
        sheet = idea['sheet']
        settings = sheet[sheet.index('2. Sources and settings'):sheet.index('3. What you have')]
        for asked in ('Research first', 'About how long, in minutes (optional)',
                      'Who is it for?', 'Is this deck for a talk or a handout?', 'The brand',
                      'Delivered as', 'Pick it when the samples are drawn', 'Options'):
            self.assertIn(asked, settings)
        have = sheet[sheet.index('3. What you have'):]
        for asked in ('A short title', 'What should they take away?',
                      'What should it cover? (optional)'):
            self.assertIn(asked, have)
        # The assistant and its model are folded under Options until they are opened.
        self.assertNotIn('Its model', idea['fields'])
        self.assertIn('Its model', options['fields'])
        self.assertIn('Claude Code', options['buttons'])
        self.assertEqual(options['keyedTwice'], [])

    def test_start_checks_every_step_and_focuses_the_first_gap(self):
        result = self.new_deck([{'click': 'A document'}, {'click': 'Start'},
                                {'snapshot': 'missing'}])
        missing = result['snapshots']['missing']
        self.assertEqual(missing['posts'], 0)
        for said in ('Something above is missing.', 'Give it a title first.',
                     'Choose the file first.'):
            self.assertIn(said, missing['sheet'])
        # Title and goal come before the document, in the third step.
        self.assertEqual(missing['focus'], 'new-title')

    def test_an_existing_deck_shows_its_levels_on_the_first_step(self):
        result = self.new_deck([
            {'click': 'An existing deck'}, {'snapshot': 'existing'},
            {'click': 'Start'}, {'snapshot': 'missing'},
            {'click': 'Selected changes'}, {'snapshot': 'selected'},
            {'fill': 'Which slides, and what to fix', 'value': 'Slide 2: shorten it.'},
            {'click': 'Redesign, keep content'}, {'snapshot': 'redesign'},
            {'click': 'Selected changes'},
            {'attach': 'The deck, as a .pptx',
             'files': [{'name': 'old.pptx', 'bytes': test_desk.DECK.decode('latin-1')}]},
            {'fill': 'A short title', 'value': 'Old deck'}, {'click': 'Start'}])
        shots = result['snapshots']
        existing, selected = shots['existing'], shots['selected']
        self.assertEqual([part for part in existing['parts'] if part[:2] in ('1.', '2.', '3.')],
                         ['1. Kind of deck', '2. Sources and settings', '3. What you have'])
        sheet = existing['sheet']
        first = sheet[sheet.index('1. Kind of deck'):sheet.index('2. Sources and settings')]
        for level in ('Brand only', 'Polish', 'Redesign, keep content', 'Full rework',
                      'Selected changes'):
            self.assertIn(level, first)
        self.assertNotIn('Which slides, and what to fix', existing['fields'])
        # The deck itself is in the third step; an existing deck has no research, and no look
        # to pick until it is redesigned.
        have = sheet[sheet.index('3. What you have'):]
        self.assertIn('The deck, as a .pptx', have)
        for gone in ('Research first', 'Pick it when the samples are drawn', 'Review level',
                     'Where it stops'):
            self.assertNotIn(gone, sheet)
        self.assertIn('Choose how much changes.', shots['missing']['sheet'])
        self.assertEqual(shots['missing']['posts'], 0)
        self.assertIn('Which slides, and what to fix', selected['fields'])
        first = selected['sheet'][:selected['sheet'].index('2. Sources and settings')]
        self.assertIn('Which slides, and what to fix', first)
        self.assertIn('Pick it when the samples are drawn', shots['redesign']['buttons'])
        self.assertNotIn('Which slides, and what to fix', shots['redesign']['fields'])
        (_, body), = self.posts(result)
        form = body['form']
        self.assertEqual((form['route'], form['flow'], form['level'], form['selected'],
                          form['source'], form['title']),
                         ('existing', 'desk', 'selected', 'Slide 2: shorten it.',
                          {'kind': 'upload', 'name': 'old.pptx'}, 'Old deck'))
        self.assertFalse(form['research'])
        for gone in ('review_level', 'review_seen', 'review_default', 'initial_review'):
            self.assertNotIn(gone, form)
        # What the page sends is what the server takes: a deck on the desk.
        self.workers.then('patch', plan_on(2))
        made = self.post('decks', body)
        shown = self.run_of(made['path'])
        self.assertIsNotNone(shown['desk'])
        self.assertEqual(shown['gate']['name'], 'gate:build', shown['sentence'])


class ProgressTests(DeskPageCase):
    """Task 1.13: before the desk, progress, with only the look pick to ask for."""

    def working(self, path: str, **changes) -> dict:
        """The desk deck as it is while its first steps run, before it reaches the desk."""
        shown = self.run_of(path)
        desk = {**shown['desk'], 'arrived': False, 'working': None,
                'progress': {'minutes_left': None,
                             'started_at': datetime.now(UTC).isoformat()}}
        shown.update({'state': 'working', 'gate': None, 'sentence': 'Drafting the outline.',
                      'desk': desk, 'question': None, 'problem': None, **changes})
        return shown

    def test_progress_says_nothing_is_needed_and_how_long(self):
        path = self.desk_deck()
        view = self.working(path)
        result = self.open_deck(path, view, [{'snapshot': 'progress'}])
        shot = result['snapshots']['progress']
        lines = shot['text'].split('\n')
        at = lines.index(NOTHING_NEEDED)
        self.assertEqual(lines[at + 1], NO_RECORD)
        self.assertEqual(shot['ledes'], [NOTHING_NEEDED])
        self.assertIn('Drafting the outline.', shot['text'])
        self.assertEqual(shot['filled'], [])
        # A record of the steps here says how long, in piece 3's words.
        timed = self.working(path)
        timed['desk']['progress']['minutes_left'] = 4
        shot = self.open_deck(path, timed, [{'snapshot': 'timed'}])['snapshots']['timed']
        self.assertIn('Nothing needed from you. The deck opens here when it is ready, in about '
                      '4 minutes.', shot['text'])
        self.assertNotIn(NO_RECORD, shot['text'])

    def test_the_look_pause_leads_the_screen(self):
        path = self.started(flow='desk', look='pick')
        view = self.run_of(path)
        self.assertEqual(view['gate']['name'], 'gate:look')
        self.assertFalse(view['desk']['arrived'])
        looks = view['gate']['offered']['looks']
        picked = self.run_of(path)
        result = self.open_deck(path, view, [
            {'snapshot': 'pause'}, {'click': looks[1]['name']},
            {'click': 'Draw the deck in this look'}, {'snapshot': 'picked'}],
            **{'POST /api/desk-look': [ok(picked)]})
        pause = result['snapshots']['pause']
        self.assertEqual(pause['parts'][0], 'Pick the look')
        lines = pause['text'].split('\n')
        self.assertEqual(lines[lines.index('Pick the look') + 1], LOOK_PAUSE)
        self.assertEqual(pause['filled'], ['Draw the deck in this look'])
        # The pick is the only thing asked: nothing else on the screen is a decision.
        for gone in ('Approve', 'Ask for changes', 'Choose another brand', NOTHING_NEEDED):
            self.assertNotIn(gone, pause['buttons'] + [pause['text']])
        self.assertEqual(self.posts(result),
                         [('/api/desk-look', {'path': path, 'look': looks[1]['id']})])
        # What the page sends is what the server takes.
        after = self.post('desk-look', {'path': path, 'look': looks[1]['id']})
        self.assertEqual(after['gate']['name'], 'gate:build')

    def test_a_look_pick_is_asked_for_before_it_is_sent(self):
        path = self.started(flow='desk', look='pick')
        result = self.open_deck(path, self.run_of(path), [
            {'click': 'Draw the deck in this look'}, {'snapshot': 'unpicked'}])
        self.assertIn('Pick a look first.', result['snapshots']['unpicked']['text'])
        self.assertEqual(self.posts(result), [])

    def test_a_question_and_a_problem_come_before_progress(self):
        path = self.desk_deck()
        view = self.working(path, question={'id': 'q1', 'from': 'The worker drafting the outline',
                                            'text': 'Should rollback come first?'},
                            problem={'state': 'failed', 'why': 'The outline step timed out.',
                                     'action': 'more-time', 'seconds': 600})
        result = self.open_deck(path, view, [{'snapshot': 'asked'}])
        shot = result['snapshots']['asked']
        text = shot['text']
        asked = text.index('Should rollback come first?')
        failed = text.index('The outline step timed out.')
        self.assertLess(asked, failed)
        self.assertLess(failed, text.index(NOTHING_NEEDED) if NOTHING_NEEDED in text
                        else text.index('Drafting the outline.'))
        self.assertEqual(shot['parts'][0], 'Needs you')
        self.assertIn('Give it more time and try again', shot['buttons'])
        self.assertEqual(shot['filled'], ['Send answer'])

    def test_a_note_on_a_preview_is_one_note_box(self):
        path = self.desk_deck()
        progress = {'incomplete': False, 'slides': [
            {'ref': 'a' * 32, 'number': 3, 'title': 'Capacity holds', 'part': 'section-1',
             'revision': 'b' * 64}]}
        view = self.working(path, build_progress=progress)
        result = self.open_deck(path, view, [
            {'snapshot': 'previews'},
            {'fill': 'How should this slide change?', 'value': 'Fewer words.'},
            {'click': 'Send note'}, {'snapshot': 'sent'}],
            **{'POST /api/build-feedback': [ok(view)]})
        shot = result['snapshots']['previews']
        self.assertIn('Slides taking shape', shot['parts'])
        self.assertIn('How should this slide change?', shot['text'])
        self.assertIn('Send note', shot['buttons'])
        for gone in ('Send slide feedback', 'Note for the next step',
                     'Ask for changes to this slide'):
            self.assertNotIn(gone, shot['text'])
            self.assertNotIn(gone, shot['buttons'])
        self.assertEqual(self.posts(result), [('/api/build-feedback', {
            'path': path, 'ref': 'a' * 32, 'note': 'Fewer words.', 'number': 3})])

    def test_a_gated_deck_keeps_its_own_screen(self):
        path = self.started()
        result = self.open_deck(path, self.run_of(path), [{'snapshot': 'gated'}])
        shot = result['snapshots']['gated']
        self.assertIsNone(self.run_of(path)['desk'])
        self.assertEqual(shot['filled'], ['Approve'])
        self.assertNotIn(NOTHING_NEEDED, shot['text'])
        self.assertNotIn('Section 1', shot['headings'])


class DeskTests(DeskPageCase):
    """Task 1.14: the desk, with its cards, notes, Stop, the Outline tab and Deliver."""

    def test_the_desk_has_one_filled_button_and_cards_under_section_headings(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [{'snapshot': 'desk'}])
        shot = result['snapshots']['desk']
        self.assertEqual(shot['filled'], ['Deliver'])
        self.assertEqual(shot['toolbar'][0], {'name': 'Deliver', 'filled': True, 'quiet': False})
        self.assertIn('Download', [control['name'] for control in shot['toolbar']])
        for tab in ('Slides', 'Outline'):
            self.assertIn(tab, shot['buttons'])
        numbered = [part['number'] for part in view['desk']['sections'] if not part['lead']]
        self.assertEqual(numbered, [1, 2])
        self.assertEqual([heading for heading in shot['headings']
                          if heading.startswith('Section')], ['Section 1', 'Section 2'])
        # A card per slide, and only content slides take a note.
        cards = cards_of(view['desk'])
        for card in cards:
            self.assertIn(f"Slide {card['number']}", ' '.join(shot['parts']))
        content = [card['number'] for card in cards if not card['lead']]
        lead = [card['number'] for card in cards if card['lead']]
        self.assertEqual(lead, [1, 8])
        redraws = [name for name in shot['buttons'] if name.startswith('Redraw slide')]
        self.assertEqual(redraws, [f'Redraw slide {number}' for number in content])
        self.assertEqual(shot['text'].count('How should this slide change?'), len(content))
        # The section headings sit outside the cards: no card holds another.
        self.assertEqual(shot['nested'], 0)

    def test_a_slide_note_shows_its_price_and_posts_the_deck_on_screen(self):
        path = self.desk_deck()
        view = self.run_of(path)
        card = next(card for card in cards_of(view['desk']) if card['number'] == 3)
        self.assertTrue(card['price'])
        after = copy.deepcopy(view)
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'}, {'click': 'Redraw slide 3'}, {'snapshot': 'empty'},
            {'fill': 'How should this slide change? Slide 3', 'value': 'Shorter.'},
            {'click': 'Redraw slide 3'}, {'snapshot': 'sent'}],
            **{'POST /api/desk-note': [ok(after)]})
        shots = result['snapshots']
        self.assertIn(card['price'], shots['desk']['text'])
        self.assertIn('Say how the slide should change.', shots['empty']['text'])
        self.assertEqual(self.posts(result), [('/api/desk-note', {
            'path': path, 'number': 3, 'note': 'Shorter.', 'expected': view['desk']['expected']})])
        # What the page sends is what the server takes.
        done = self.post('desk-note', {'path': path, 'number': 3, 'note': 'Shorter.',
                                       'expected': view['desk']['expected']})
        noted = next(one for one in cards_of(done['desk']) if one['number'] == 3)
        self.assertEqual(noted['note']['status'], 'done')

    def test_the_outline_tab_line_is_gone_once_words_are_edited_here(self):
        path = self.desk_deck()
        view = self.run_of(path)
        shot = self.open_deck(path, view, [{'snapshot': 'desk'}])['snapshots']['desk']
        content = [card for card in cards_of(view['desk']) if not card['lead']]
        self.assertNotIn('To change its words, edit them on the Outline tab.', shot['text'])
        self.assertNotIn(WORDS_LINE, shot['text'])
        # The price still comes straight under the note's button.
        lines = shot['text'].split('\n')
        self.assertEqual(lines[lines.index(f"Redraw slide {content[0]['number']}") + 1],
                         content[0]['price'])
        # The words and the speaker notes are boxes on the card now.
        number = content[0]['number']
        self.assertEqual(shot['fields'][f'Title of slide {number}'],
                         content[0]['words']['title'])
        self.assertEqual(shot['fields'][f'Speaker notes for slide {number}'],
                         content[0]['notes'])

    def test_a_redraw_in_progress_offers_stop(self):
        path = self.desk_deck()
        view = self.run_of(path)
        busy = copy.deepcopy(view)
        busy['state'] = 'working'
        busy['desk']['working'] = {'what': 'Redrawing: 1 of 2 sections', 'done': 1, 'total': 2}
        for card in cards_of(busy['desk']):
            card['busy'] = card['section'] == 'section-2'
        result = self.open_deck(path, busy, [
            {'snapshot': 'working'}, {'click': 'Stop'}, {'snapshot': 'stopped'}],
            **{'POST /api/desk-stop': [ok(view)]})
        shot = result['snapshots']['working']
        lines = shot['text'].split('\n')
        self.assertIn('Redrawing: 1 of 2 sections', lines)
        self.assertLess(lines.index('Redrawing: 1 of 2 sections'), lines.index('Section 1'))
        self.assertEqual(self.posts(result), [('/api/desk-stop', {'path': path})])
        # A card whose section is redrawn says so, and its controls wait.
        self.assertIn('Redrawing…', shot['text'])
        for number in (5, 6, 7):
            self.assertIn(f'Redraw slide {number}', shot['off'])
        self.assertNotIn('Redraw slide 3', shot['off'])
        self.assertIn('Deliver', shot['off'])

    def test_the_whole_deck_note_says_its_price_and_redraws_every_section(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'},
            {'fill': 'How should the whole deck change?', 'value': 'Fewer words.'},
            {'click': 'Redraw every section'}],
            **{'POST /api/desk-deck-note': [ok(view)]})
        shot = result['snapshots']['desk']
        self.assertIn(view['desk']['deck_price'], shot['text'])
        self.assertLess(shot['text'].index('How should the whole deck change?'),
                        shot['text'].index('Section 1'))
        self.assertEqual(self.posts(result), [('/api/desk-deck-note', {
            'path': path, 'note': 'Fewer words.', 'expected': view['desk']['expected']})])

    def test_the_outline_tab_prices_a_save_before_it_posts(self):
        path = self.desk_deck()
        view = self.run_of(path)
        outline = view['desk']['outline']
        edited = copy.deepcopy(outline['slides'])
        edited[2]['title'] = 'Capacity holds with two instances'
        priced = self.post('desk-outline-price', {'path': path, 'slides': edited})
        self.assertTrue(priced['says'])
        result = self.open_deck(path, view, [
            {'click': 'Outline'}, {'snapshot': 'outline'},
            {'fill': 'Title of slide 3', 'value': 'Capacity holds with two instances'},
            {'snapshot': 'priced'}, {'click': 'Save'}, {'snapshot': 'saved'}],
            **{'POST /api/desk-outline-price': [ok(priced)],
               'POST /api/desk-outline': [ok(view)]})
        shots = result['snapshots']
        self.assertIn('Save', shots['outline']['off'], 'nothing to save until it is edited')
        self.assertNotIn('How should this slide change?', shots['outline']['text'])
        self.assertIn(priced['says'], shots['priced']['text'])
        self.assertNotIn('Save', shots['priced']['off'])
        posts = self.posts(result)
        self.assertEqual([address for address, _ in posts],
                         ['/api/desk-outline-price', '/api/desk-outline'])
        self.assertEqual(posts[0][1], {'path': path, 'slides': edited})
        # The slides priced are the slides saved, against the outline the page read; the
        # price above is the server's own answer for them.
        self.assertEqual(posts[1][1], {'path': path, 'slides': edited,
                                       'expected': outline['expected']})

    def test_the_outline_tab_changes_the_look_and_the_reading_at_their_price(self):
        path = self.desk_deck()
        view = self.run_of(path)
        read = copy.deepcopy(view)
        read['route'] = 'document'
        read['desk']['outline']['reading'] = {'kind': 'material',
                                              'price': 'Redraws every section. Expect minutes.'}
        result = self.open_deck(path, read, [
            {'click': 'Outline'}, {'snapshot': 'outline'}, {'click': 'Read it the other way'},
            {'click': 'Change the look'}],
            **{'POST /api/desk-reread': [ok(read)], 'POST /api/desk-look-again': [ok(read)]})
        shot = result['snapshots']['outline']
        look = view['desk']['outline']['look']
        self.assertIn('Read as material to build from.', shot['text'])
        self.assertIn('Redraws every section. Expect minutes.', shot['text'])
        self.assertIn(look['price'], shot['text'])
        self.assertIn(look['name'], shot['text'])
        self.assertEqual(self.posts(result), [('/api/desk-reread', {'path': path, 'kind': 'spec'}),
                                              ('/api/desk-look-again', {'path': path})])

    def test_deliver_with_a_blocker_asks_first(self):
        path = self.desk_deck()
        view = self.run_of(path)
        desk = view['desk']
        blocked = copy.deepcopy(view)
        blocked['desk']['blockers'] = [{'number': 3, 'says': 'Text runs off the slide.'}]
        result = self.open_deck(path, blocked, [
            {'click': 'Deliver'}, {'snapshot': 'sheet'}, {'click': 'Deliver anyway'}],
            **{'POST /api/desk-deliver': [ok(view)]})
        sheet = result['snapshots']['sheet']['sheet']
        self.assertIn('Slide 3: Text runs off the slide.', sheet)
        self.assertIn('The brand check found 1 problem that blocks delivery. Deliver anyway, or '
                      'fix them first.', sheet)
        self.assertIn('This deck has not been reviewed.', sheet)
        self.assertEqual(result['snapshots']['sheet']['filled'], ['Deliver anyway'])
        self.assertEqual(self.posts(result), [('/api/desk-deliver', {
            'path': path, 'expected': desk['expected'],
            'blockers_seen': blocked['desk']['blockers_seen']})])

    def test_two_blockers_are_problems_and_none_delivers_on_the_deck_on_screen(self):
        path = self.desk_deck()
        view = self.run_of(path)
        blocked = copy.deepcopy(view)
        blocked['desk']['blockers'] = [{'number': 3, 'says': 'Text runs off the slide.'},
                                       {'number': 5, 'says': 'A logo is missing.'}]
        shot = self.open_deck(path, blocked, [{'click': 'Deliver'}, {'snapshot': 'two'}])
        self.assertIn('The brand check found 2 problems that block delivery.',
                      shot['snapshots']['two']['sheet'])
        clear = copy.deepcopy(view)
        clear['desk'].update(blockers=[], reviewed=True)
        result = self.open_deck(path, clear, [
            {'click': 'Deliver'}, {'snapshot': 'clear'}, {'click': 'Deliver'}],
            **{'POST /api/desk-deliver': [ok(view)]})
        sheet = result['snapshots']['clear']['sheet']
        self.assertIn('The brand check found nothing that blocks delivery.', sheet)
        self.assertNotIn('Deliver anyway', sheet)
        self.assertIn('This deck was reviewed.', sheet)
        self.assertEqual(self.posts(result), [('/api/desk-deliver', {
            'path': path, 'expected': view['desk']['expected']})])

    def test_a_delivered_deck_says_its_revision_and_what_a_change_makes(self):
        path = self.desk_deck()
        view = self.run_of(path)
        delivered = self.post('desk-deliver', {'path': path, 'expected': view['desk']['expected'],
                                               'blockers_seen': view['desk']['blockers_seen']})
        self.assertEqual(delivered['desk']['delivered']['revision'], 1)
        shot = self.open_deck(path, delivered, [{'snapshot': 'delivered'}])['snapshots']
        self.assertIn('Delivered as revision 1.', shot['delivered']['text'])
        changed = self.post('desk-note', {'path': path, 'number': 3, 'note': 'Shorter.',
                                          'expected': delivered['desk']['expected']})
        self.assertTrue(changed['desk']['revision'])
        shot = self.open_deck(path, changed, [{'snapshot': 'again'}])['snapshots']['again']
        self.assertIn(changed['desk']['revision'], shot['text'])
        self.assertEqual(shot['filled'], ['Deliver'])

    def test_a_deck_with_no_drawing_here_offers_to_draw_it(self):
        path = self.desk_deck()
        view = self.run_of(path)
        away = copy.deepcopy(view)
        away['desk'].update(drawn_here=False, no_drawing='There is no drawing of this deck on '
                            'this computer.', draw_here_price='Redraws every section. Expect '
                            'minutes, not seconds.')
        result = self.open_deck(path, away, [{'snapshot': 'away'}, {'click': 'Draw it here'}],
                                **{'POST /api/desk-draw-here': [ok(view)]})
        shot = result['snapshots']['away']
        for said in ('There is no drawing of this deck on this computer.',
                     'Redraws every section. Expect minutes, not seconds.'):
            self.assertIn(said, shot['text'])
        self.assertEqual(self.posts(result), [('/api/desk-draw-here', {'path': path})])

    def test_no_word_a_person_should_not_read(self):
        path = self.desk_deck()
        view = self.run_of(path)
        blocked = copy.deepcopy(view)
        blocked['desk']['blockers'] = [{'number': 3, 'says': 'Text runs off the slide.'}]
        result = self.open_deck(path, blocked, [
            {'snapshot': 'desk'}, {'click': 'Outline'}, {'snapshot': 'outline'},
            {'click': 'Slides'}, {'click': 'Deliver'}, {'snapshot': 'deliver'}])
        for name, shot in result['snapshots'].items():
            with self.subTest(name):
                said = shot['text'] + shot['sheet']
                self.assertIsNone(FORBIDDEN_WORDS.search(said))
                self.assertNotIn(view['desk']['expected'], said)
                self.assertNotIn(view['desk']['expected'][:12], said)
                self.assertNotIn(view['desk']['blockers_seen'][:12], said)
        self.assertIn('Section 1', json.dumps(result['snapshots']['desk']['headings']))


class SecondReviewTests(DeskPageCase):
    """What the second review of the desk found on the page."""

    def test_change_the_look_on_the_desk_leads_with_the_look_pause(self):
        path = self.desk_deck()
        again = self.post('desk-look-again', {'path': path})
        self.assertTrue(again['desk']['arrived'])
        self.assertEqual(again['gate']['name'], 'gate:look')
        looks = again['gate']['offered']['looks']
        picked = self.run_of(path)
        result = self.open_deck(path, again, [
            {'snapshot': 'pause'}, {'click': looks[1]['name']},
            {'click': 'Draw the deck in this look'}],
            **{'POST /api/desk-look': [ok(picked)]})
        pause = result['snapshots']['pause']
        self.assertEqual(pause['parts'][0], 'Pick the look')
        lines = pause['text'].split('\n')
        self.assertEqual(lines[lines.index('Pick the look') + 1], LOOK_PAUSE)
        self.assertEqual(pause['filled'], ['Draw the deck in this look'])
        self.assertIn('Deliver', pause['off'])
        self.assertNotIn('Redrawing', pause['text'])
        self.assertEqual(self.posts(result),
                         [('/api/desk-look', {'path': path, 'look': looks[1]['id']})])
        after = self.post('desk-look', {'path': path, 'look': looks[1]['id']})
        self.assertEqual(after['gate']['name'], 'gate:build')

    def test_a_redraw_that_stopped_offers_stop_beside_the_problem(self):
        path = self.desk_deck()
        view = self.run_of(path)
        halted = copy.deepcopy(view)
        halted['state'] = 'failed'
        halted['problem'] = {'state': 'failed', 'why': 'A section could not be drawn.',
                             'action': 'retry'}
        halted['desk'].update(deliverable=False, working={
            'what': 'The redraw stopped. Stop it to keep what was redrawn, or carry on.',
            'done': 1, 'total': 2, 'halted': True})
        result = self.open_deck(path, halted, [{'snapshot': 'halted'}, {'click': 'Stop'}],
                                **{'POST /api/desk-stop': [ok(view)]})
        shot = result['snapshots']['halted']
        self.assertIn('The redraw stopped. Stop it to keep what was redrawn, or carry on.',
                      shot['text'].split('\n'))
        self.assertIn('Try again', shot['buttons'])
        self.assertIn('Stop', shot['buttons'])
        self.assertEqual(self.posts(result), [('/api/desk-stop', {'path': path})])

    def test_deliver_waits_while_the_deck_is_not_deliverable(self):
        path = self.desk_deck()
        view = self.run_of(path)
        self.assertIs(view['desk']['deliverable'], True)
        waiting = copy.deepcopy(view)
        waiting['desk']['deliverable'] = False
        shot = self.open_deck(path, waiting, [{'snapshot': 'waiting'}])['snapshots']['waiting']
        self.assertIn('Deliver', shot['off'])
        # A sheet opened before the deck moved on says why, and sends nothing.
        answers = self.answers(**{'GET /api/run': [ok(view), ok(view), ok(waiting)]})
        result = self.run_page(answers, [
            {'click': 'Deliver'}, {'poll': True}, {'click': 'Deliver'}, {'snapshot': 'sheet'}],
            state={'screen': 'deck', 'path': path})
        self.assertIn('Deliver the deck', result['snapshots']['sheet']['sheet'])
        self.assertIn(WAITS, result['snapshots']['sheet']['sheet'])
        self.assertEqual(self.posts(result), [])

    def test_a_blocker_with_no_slide_has_no_slide_prefix(self):
        path = self.desk_deck()
        view = self.run_of(path)
        blocked = copy.deepcopy(view)
        blocked['desk']['blockers'] = [{'number': None, 'says': 'The deck has no title slide.'}]
        sheet = self.open_deck(path, blocked, [{'click': 'Deliver'}, {'snapshot': 'sheet'}])[
            'snapshots']['sheet']['sheet']
        self.assertIn('The deck has no title slide.', sheet)
        self.assertNotIn('Slide null', sheet)
        self.assertNotIn('Slide None', sheet)

    def test_save_waits_while_the_deck_is_redrawn(self):
        path = self.desk_deck()
        view = self.run_of(path)
        busy = copy.deepcopy(view)
        busy['state'] = 'working'
        busy['desk'].update(deliverable=False, working={
            'what': 'Redrawing: 1 of 2 sections', 'done': 1, 'total': 2})
        result = self.open_deck(path, busy, [
            {'click': 'Outline'},
            {'fill': 'Title of slide 3', 'value': 'Capacity holds with two instances'},
            {'snapshot': 'edited'}, {'click': 'Save'}])
        shot = result['snapshots']['edited']
        self.assertIn('Save', shot['off'])
        self.assertIn('The deck is being redrawn now. Save the outline when that ends.',
                      shot['text'])
        self.assertEqual(self.posts(result), [])


SESSION_SHAPE = r'^[0-9a-f]{16}$'


class WordsTests(DeskPageCase):
    """Task 2.5: a slide's words, its speaker notes and its History, on its card."""

    def card(self, view: dict, number: int) -> dict:
        return next(card for card in cards_of(view['desk']) if card['number'] == number)

    def test_typing_saves_a_second_after_the_last_key(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'fill': 'Title of slide 3', 'value': 'Batches restart in turn'},
            {'snapshot': 'typed'}, {'timer': 'flush'}, {'snapshot': 'saved'}],
            **{'POST /api/desk-words': [ok(view)]})
        self.assertEqual(result['snapshots']['typed']['posts'], 0, 'nothing is sent while typing')
        (address, body), = self.posts(result)
        self.assertEqual(address, '/api/desk-words')
        self.assertRegex(body.pop('session'), SESSION_SHAPE)
        self.assertEqual(body, {'path': path, 'number': 3, 'field': 'title',
                                'text': 'Batches restart in turn',
                                'seen': view['desk']['seen']})
        self.assertIn('Saved.', result['snapshots']['saved']['text'])
        # What the page sends is what the server takes.
        after = self.post('desk-words', {**body, 'session': 'a' * 16})
        self.assertEqual(self.card(after, 3)['words']['title'], 'Batches restart in turn')

    def test_a_point_saves_by_its_place_in_the_slide(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'fill': 'Point 2 text of slide 3', 'value': 'Requests are dropped.'},
            {'timer': 'flush'}], **{'POST /api/desk-words': [ok(view)]})
        (_, body), = self.posts(result)
        self.assertEqual((body['field'], body['text']), (['points', 1, 'text'],
                                                          'Requests are dropped.'))

    def test_an_old_form_is_said_on_its_card_and_keeps_the_words(self):
        path = self.desk_deck()
        view = self.run_of(path)
        refused = {'status': 400, 'body': {'error': 'This slide changed since you opened '
                                                    'it. Reload to see the latest.'}}
        result = self.open_deck(path, view, [
            {'fill': 'Title of slide 3', 'value': 'Batches restart in turn'},
            {'timer': 'flush'}, {'snapshot': 'refused'}],
            **{'POST /api/desk-words': [refused]})
        shot = result['snapshots']['refused']
        self.assertIn('This slide changed since you opened it.', shot['text'])
        self.assertEqual(shot['fields']['Title of slide 3'], 'Batches restart in turn')

    def test_speaker_notes_are_their_own_box(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'},
            {'fill': 'Speaker notes for slide 3', 'value': 'Say why one instance drops.'},
            {'timer': 'flush'}], **{'POST /api/desk-notes': [ok(view)]})
        shot = result['snapshots']['desk']
        # Its own box, labelled "Speaker notes", and the slide named for a screen reader.
        self.assertIn('Speaker notes for slide 3', shot['text'].split('\n'))
        self.assertEqual(shot['fields']['Speaker notes for slide 3'], self.card(view, 3)['notes'])
        self.assertNotIn('Speaker notes: ', shot['text'])
        (address, body), = self.posts(result)
        self.assertEqual(address, '/api/desk-notes')
        self.assertRegex(body.pop('session'), SESSION_SHAPE)
        self.assertEqual(body, {'path': path, 'number': 3, 'text': 'Say why one instance drops.',
                                'seen': view['desk']['seen']})
        after = self.post('desk-notes', {**body, 'session': 'b' * 16})
        self.assertEqual(self.card(after, 3)['notes'], 'Say why one instance drops.')

    def test_selecting_words_shows_the_shared_selection_bar(self):
        path = self.desk_deck()
        view = self.run_of(path)
        title = self.card(view, 3)['words']['title']
        start = title.index('more than one')
        result = self.open_deck(path, view, [
            {'snapshot': 'none'},
            {'select': 'Title of slide 3', 'start': start, 'end': start + len('more than one')},
            {'snapshot': 'selected'}, {'click': 'Shorten'}],
            **{'POST /api/desk-selection': [ok(view)]})
        shots = result['snapshots']
        self.assertNotIn('Rephrase', shots['none']['buttons'])
        selected = shots['selected']
        for action in ('Rephrase', 'Shorten', 'Expand', 'Fix', 'Ask…'):
            self.assertIn(action, selected['buttons'])
        self.assertLessEqual(len(selected['filled']), 1)
        self.assertEqual(self.posts(result), [('/api/desk-selection', {
            'path': path, 'number': 3, 'field': 'title', 'start': start,
            'end': start + len('more than one'), 'action': 'shorten',
            'seen': view['desk']['seen'], 'passage': 'more than one'})])

    def test_ask_asks_what_should_change_first(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'select': 'Title of slide 3', 'start': 0, 'end': 8}, {'click': 'Ask…'},
            {'click': 'Go'}, {'snapshot': 'empty'},
            {'fill': 'What should change in the selected words?', 'value': 'Say it plainly.'},
            {'click': 'Go'}], **{'POST /api/desk-selection': [ok(view)]})
        self.assertIn('Say what should change in the words first.',
                      result['snapshots']['empty']['text'])
        (_, body), = self.posts(result)
        self.assertEqual((body['action'], body['instruction'], body['start'], body['end']),
                         ('ask', 'Say it plainly.', 0, 8))

    def test_an_unfit_edit_offers_redraw_with_the_price_or_discard(self):
        path = self.desk_deck()
        view = self.run_of(path)
        unfit = copy.deepcopy(view)
        card = self.card(unfit, 3)
        card['unfit'] = {'number': 3, 'field': 'title', 'text': 'A much longer title',
                         'lines': ['when-capacity-holds: the title runs off the slide.'],
                         'at': '2026-10-27T09:00:00Z',
                         'says': 'These words do not fit the slide as it is drawn.'}
        result = self.open_deck(path, unfit, [
            {'snapshot': 'unfit'}, {'click': 'Redraw with these words'}, {'click': 'Discard'}],
            **{'POST /api/desk-redraw-words': [ok(unfit)], 'POST /api/desk-discard': [ok(view)]})
        shot = result['snapshots']['unfit']
        lines = shot['text'].split('\n')
        for said in ('These words do not fit the slide as it is drawn.',
                     'when-capacity-holds: the title runs off the slide.'):
            self.assertIn(said, shot['text'])
        self.assertIn('A much longer title', shot['text'] + json.dumps(shot['fields']))
        self.assertEqual(lines[lines.index('Redraw with these words') + 2], card['price'])
        self.assertIn('Discard', shot['buttons'])
        self.assertEqual(self.posts(result), [
            ('/api/desk-redraw-words', {'path': path, 'number': 3, 'field': 'title',
                                        'text': 'A much longer title',
                                        'expected': view['desk']['expected']}),
            ('/api/desk-discard', {'path': path, 'number': 3})])

    def test_history_compares_words_and_pictures(self):
        path = self.desk_deck()
        first = self.run_of(path)
        card = self.card(first, 3)
        self.post('desk-words', {'path': path, 'number': 3, 'field': 'title',
                                 'text': 'Batches restart in turn', 'seen': first['desk']['seen'],
                                 'session': 'c' * 16})
        view = self.run_of(path)
        found = self.get('desk-versions', path=path, slide=card['id'])
        self.assertEqual(found['versions'][0]['source'], 'save')
        self.assertTrue(found['versions'][0]['picture'])
        result = self.open_deck(path, view, [
            {'click': 'History of slide 3'}, {'snapshot': 'history'}, {'click': 'Restore'}],
            **{'GET /api/desk-versions': [ok(found)], 'POST /api/desk-restore': [ok(view)]})
        shot = result['snapshots']['history']
        sheet = shot['sheet']
        self.assertIn('History of slide 3', sheet)
        self.assertIn('Before words you typed', sheet)
        # The words then, compared with the words now.
        self.assertIn(card['words']['title'].split()[0], sheet)
        self.assertIn('Batches restart in turn', sheet)
        kinds = sorted(picture['of'].split('kind=')[1].split('&')[0]
                       for picture in shot['pictures'])
        self.assertIn('version', kinds)
        self.assertIn('build', kinds)
        self.assertEqual(self.posts(result), [('/api/desk-restore', {
            'path': path, 'slide': card['id'], 'index': 0, 'seen': view['desk']['seen'],
            'stamp': found['versions'][0]['stamp']})])
        asked = [request['address'] for request in result['requests']
                 if request['address'].startswith('/api/desk-versions')]
        self.assertTrue(asked)
        # What the page sends is what the server takes.
        after = self.post('desk-restore', self.posts(result)[0][1])
        self.assertEqual(self.card(after, 3)['words']['title'], card['words']['title'])

    def test_restore_is_bound_to_the_version_by_its_stamp(self):
        path = self.desk_deck()
        view = self.run_of(path)
        card = self.card(view, 3)
        older = {'at': '2026-10-27T08:00:00Z', 'source': 'save', 'stamp': 'b' * 16,
                 'words': {**card['words'], 'title': 'An older title', 'notes': card['notes']},
                 'picture': None}
        newer = {**older, 'at': '2026-10-27T09:00:00Z', 'stamp': 'a' * 16,
                 'words': {**older['words'], 'title': 'A newer title'}}
        result = self.open_deck(path, view, [
            {'click': 'History of slide 3'}, {'snapshot': 'history'},
            {'click': 'Restore the version kept'}],
            **{'GET /api/desk-versions': [ok({'versions': [newer, older]})],
               'POST /api/desk-restore': [ok(view)]})
        sheet = result['snapshots']['history']['sheet']
        self.assertLess(sheet.index('A newer title'), sheet.index('An older title'))
        self.assertEqual(self.posts(result), [('/api/desk-restore', {
            'path': path, 'slide': card['id'], 'index': 0, 'seen': view['desk']['seen'],
            'stamp': 'a' * 16})])

    def test_words_typed_and_not_saved_offer_no_selection_bar(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'fill': 'Title of slide 3', 'value': 'Batches restart in turn'},
            {'select': 'Title of slide 3', 'start': 0, 'end': 7}, {'snapshot': 'typed'}])
        self.assertNotIn('Rephrase', result['snapshots']['typed']['buttons'])
        unfit = copy.deepcopy(view)
        self.card(unfit, 3)['unfit'] = {
            'number': 3, 'field': 'title', 'text': 'A much longer title', 'lines': ['Too long.'],
            'at': '2026-10-27T09:00:00Z', 'says': 'These words do not fit the slide as it is '
                                                  'drawn.'}
        result = self.open_deck(path, unfit, [
            {'select': 'Title of slide 3', 'start': 0, 'end': 6}, {'snapshot': 'unfit'}])
        self.assertNotIn('Rephrase', result['snapshots']['unfit']['buttons'])

    def test_a_restore_that_does_not_fit_shows_the_version_and_redraws_it(self):
        path = self.desk_deck()
        view = self.run_of(path)
        unfit = copy.deepcopy(view)
        card = self.card(unfit, 3)
        kept = {**card['words'], 'title': 'An older, much longer title',
                'caveat': 'An older caveat.', 'notes': 'Older notes.'}
        card['unfit'] = {'number': 3, 'field': 'restore', 'text': '', 'words': kept,
                         'lines': ['when-capacity-holds: the title runs off the slide.'],
                         'at': '2026-10-27T09:00:00Z',
                         'says': 'These words do not fit the slide as it is drawn.'}
        result = self.open_deck(path, unfit, [
            {'snapshot': 'unfit'}, {'click': 'Redraw with these words'}],
            **{'POST /api/desk-redraw-words': [ok(view)]})
        text = result['snapshots']['unfit']['text']
        for said in ('These words do not fit the slide as it is drawn.',
                     'An older, much longer title', 'An older caveat.', 'Older notes.',
                     kept['points'][0]['text']):
            self.assertIn(said, text)
        self.assertNotIn('Your words: “”', text)
        self.assertEqual(self.posts(result), [('/api/desk-redraw-words', {
            'path': path, 'number': 3, 'field': 'restore', 'text': '',
            'expected': view['desk']['expected']})])

    def test_the_boxes_take_as_many_characters_as_the_runner(self):
        path = self.desk_deck()
        shot = self.open_deck(path, self.run_of(path), [{'snapshot': 'desk'}])['snapshots']['desk']
        self.assertEqual(shot['limits']['Speaker notes for slide 3'], 4000)
        self.assertEqual(shot['limits']['Title of slide 3'], 2000)
        self.assertEqual(shot['limits']['Point 1 text of slide 3'], 2000)

    def test_a_lead_slide_s_words_are_boxes_with_no_points(self):
        path = self.desk_deck()
        view = self.run_of(path)
        shot = self.open_deck(path, view, [{'snapshot': 'desk'}])['snapshots']['desk']
        self.assertEqual(shot['fields']['Title of slide 1'], self.card(view, 1)['words']['title'])
        self.assertFalse([label for label in shot['fields'] if label.startswith('Point')
                          and label.endswith('of slide 1')])
        self.assertNotIn('How should this slide change? Slide 1', shot['fields'])

    def test_no_word_a_person_should_not_read_on_the_words(self):
        path = self.desk_deck()
        view = self.run_of(path)
        card = self.card(view, 3)
        found = {'versions': [{'at': '2026-10-27T09:00:00Z', 'source': 'save',
                               'words': {**card['words'], 'notes': card['notes']},
                               'stamp': 'abcdef1234567890', 'picture': None}]}
        result = self.open_deck(path, view, [
            {'select': 'Title of slide 3', 'start': 0, 'end': 8}, {'snapshot': 'bar'},
            {'click': 'History of slide 3'}, {'snapshot': 'history'}],
            **{'GET /api/desk-versions': [ok(found)]})
        for name, shot in result['snapshots'].items():
            with self.subTest(name):
                said = shot['text'] + shot['sheet']
                self.assertIsNone(FORBIDDEN_WORDS.search(said))
                self.assertNotIn('abcdef1234567890', said)


STRICT_WORDS = ("This deck keeps your own deck's words exactly. Change them in your deck, or "
                'start again at Redesign, keep content.')
OWN_NOTES = ('Speaker notes in your own deck are kept as they are. Selected changes changes '
             'only the text on the slides.')


class ExistingDeskTests(DeskPageCase):
    """Task 3.4: an existing deck on the desk. Its cards show each slide as it was in your
    deck beside the slide now; at Brand only and Polish the words are read, not edited, with
    the reason; at Selected changes the words of each part of your own slide are the boxes,
    and there is no speaker notes box."""

    def existing(self, level: str, **more) -> tuple[str, dict]:
        self.workers.queued['outline'] = [runner_support.read_word_for_word(self)]
        if level == 'selected':
            self.workers.then('patch', plan_on(2))
            more.setdefault('selected', 'Shorten the words on slide 2')
        path = self.started(route='existing', level=level, title='Old deck', flow='desk',
                            look='default', source={'kind': 'upload', 'name': 'old.pptx'},
                            uploads={'old.pptx': test_desk.DECK}, **more)
        view = self.run_of(path)
        self.assertEqual(view['gate']['name'], 'gate:build', view['sentence'])
        return path, view

    def test_an_existing_deck_s_cards_show_before_and_after(self):
        path, view = self.existing('polish')
        card = next(card for card in cards_of(view['desk']) if card['number'] == 2)
        self.assertEqual(card['before'], {'kind': 'original', 'ref': 2})
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'}, {'see': 'Slide 2 as it was in your deck'},
            {'see': 'Slide 2'}, {'snapshot': 'seen'}])
        shot = result['snapshots']['desk']
        lines = shot['text'].split('\n')
        self.assertIn('Before', lines)
        self.assertIn('After', lines)
        self.assertIn('Slide 2 as it was in your deck. ', shot['text'])
        kinds = sorted(picture['of'].split('kind=')[1].split('&')[0]
                       for picture in result['snapshots']['seen']['pictures'])
        self.assertIn('original', kinds)
        self.assertIn('build', kinds)
        # Before comes first, then the slide now.
        text = shot['text']
        self.assertLess(text.index('Before'), text.index('After'))

    def test_brand_only_cards_show_words_read_only_with_the_reason(self):
        path, view = self.existing('brand-only')
        self.assertEqual(view['desk']['words_locked'], STRICT_WORDS)
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'},
            {'fill': 'Speaker notes for slide 2', 'value': 'Two minutes.'}, {'timer': 'flush'}],
            **{'POST /api/desk-notes': [ok(view)]})
        shot = result['snapshots']['desk']
        self.assertIn(STRICT_WORDS, shot['text'])
        boxes = list(shot['fields'])
        self.assertFalse([label for label in boxes if label.startswith(('Title', 'Point',
                                                                        'Subtitle'))], boxes)
        self.assertIn('Speaker notes for slide 2', boxes)
        card = next(card for card in cards_of(view['desk']) if card['number'] == 2)
        self.assertIn(card['words']['title'], shot['text'])
        self.assertEqual([address for address, _ in self.posts(result)], ['/api/desk-notes'])
        # A note on the slide still redraws it.
        self.assertIn('Redraw slide 2', shot['buttons'])

    def test_selected_changes_hide_the_notes_box_with_the_reason(self):
        path, view = self.existing('selected')
        self.assertEqual(view['desk']['notes_locked'], OWN_NOTES)
        card = next(card for card in cards_of(view['desk']) if card['number'] == 2)
        self.assertEqual(card['objects'][1]['runs'], ['Ship apps ', 'in minutes.'])
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'},
            {'fill': 'Text box 2, part 1 of slide 2', 'value': 'Ship fast'},
            {'timer': 'flush'}], **{'POST /api/desk-words': [ok(view)]})
        shot = result['snapshots']['desk']
        self.assertIn(OWN_NOTES, shot['text'])
        self.assertFalse([label for label in shot['fields'] if 'Speaker notes' in label])
        self.assertEqual(shot['fields']['Text box 2, part 2 of slide 2'], 'in minutes.')
        first = next(card for card in cards_of(view['desk']) if card['number'] == 1)
        self.assertEqual(shot['fields']['Text box 1 of slide 1'],
                         first['objects'][0]['runs'][0])
        # Your own deck has no sections and no whole-deck note; its slides take a note.
        self.assertFalse([heading for heading in shot['headings']
                          if heading.startswith('Section')])
        self.assertNotIn('Redraw every section', shot['buttons'])
        self.assertNotIn('History of slide 2', shot['buttons'])
        # A note plans the slide's changes again: nothing of your own deck is redrawn.
        self.assertIn('Change slide 2', shot['buttons'])
        self.assertFalse([name for name in shot['buttons'] if name.startswith('Redraw')])
        self.assertNotIn('Outline', shot['buttons'])
        self.assertIn('Before', shot['text'].split('\n'))
        (address, body), = self.posts(result)
        self.assertEqual(address, '/api/desk-words')
        self.assertEqual((body['number'], body['field'], body['text']),
                         (2, ['object', '3', 0], 'Ship fast'))
        # What the page sends is what the server takes.
        after = self.post('desk-words', body)
        self.assertEqual(next(card for card in cards_of(after['desk'])
                              if card['number'] == 2)['objects'][1]['runs'],
                         ['Ship fast ', 'in minutes.'])

    def test_a_change_your_deck_could_not_take_offers_only_discard(self):
        path, view = self.existing('selected')
        view = copy.deepcopy(view)
        card = next(card for card in cards_of(view['desk']) if card['number'] == 2)
        refused = ('This change could not be made to the copy of your deck, so the copy is as '
                   'it was before it.')
        card['unfit'] = {'number': 2, 'field': ['object', '3', 0], 'text': 'Ship fast',
                         'lines': ['slide 2, object 3: geometry-style-or-relationships-changed.'],
                         'says': refused}
        result = self.open_deck(path, view, [{'snapshot': 'desk'}, {'click': 'Discard'}],
                                **{'POST /api/desk-discard': [ok(self.run_of(path))]})
        shot = result['snapshots']['desk']
        self.assertIn(refused, shot['text'])
        self.assertEqual(shot['fields']['Text box 2, part 1 of slide 2'], 'Ship fast')
        self.assertNotIn('Redraw with these words', shot['buttons'])
        self.assertEqual(self.posts(result), [('/api/desk-discard', {'path': path, 'number': 2})])

    def test_no_word_a_person_should_not_read_on_an_existing_deck(self):
        for level in ('brand-only', 'selected'):
            path, view = self.existing(level)
            result = self.open_deck(path, view, [{'snapshot': 'desk'}])
            with self.subTest(level):
                said = result['snapshots']['desk']['text']
                self.assertIsNone(FORBIDDEN_WORDS.search(said))
                self.assertNotIn(view['desk']['expected'], said)


BLOCKED = {'status': 'BLOCKED', 'warnings': [],
           'blockers': [{'slide': 3, 'says': 'Text runs off the slide.', 'code': 'OUT_OF_BOUNDS'}]}


class FinishingPageTests(DeskPageCase):
    """Task 4.6: Sources and Research in the desk's aside, and Finishing as a panel."""

    def research_deck(self) -> str:
        return self.desk_deck(research=True)

    def test_add_a_source_is_an_aside_with_a_file_and_pasted_text(self):
        path = self.desk_deck()
        view = self.run_of(path)
        self.assertEqual(view['desk']['sources'], [])
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'},
            {'attach': 'A file', 'files': [{'name': 'runbook.md',
                                            'text': '# Runbook\n\nTwo batches at a time.\n'}]},
            {'polls': 1},
            {'click': 'Add the pasted text'}, {'snapshot': 'empty'},
            {'fill': 'Or paste its text', 'value': 'Health checks gate each batch.'},
            {'fill': 'Its title', 'value': 'Pasted notes'},
            {'click': 'Add the pasted text'}],
            **{'POST /api/desk-source': [ok(view), ok(view)]})
        shot = result['snapshots']['desk']
        lines = shot['text'].split('\n')
        # The aside comes after the slides, under its own heading.
        self.assertLess(lines.index('Section 2'), lines.index('Sources'))
        self.assertIn('Add a source', lines)
        for label in ('A file', 'Or paste its text', 'Its title'):
            self.assertIn(label, shot['fields'])
        self.assertIn('No sources yet.', shot['text'])
        self.assertNotIn('Research again', shot['buttons'], 'a deck with no research')
        self.assertIn('Paste the text of the source first.', result['snapshots']['empty']['text'])
        (file_address, sent_file), (text_address, sent_text) = self.posts(result)
        self.assertEqual((file_address, text_address), ('/api/desk-source', '/api/desk-source'))
        self.assertEqual((sent_file['path'], sent_file['name']), (path, 'runbook.md'))
        self.assertEqual(base64.b64decode(sent_file['content']),
                         b'# Runbook\n\nTwo batches at a time.\n')
        self.assertEqual(sent_text, {'path': path, 'text': 'Health checks gate each batch.',
                                     'title': 'Pasted notes'})
        # What the page sends is what the server takes, and nothing is drawn.
        jobs = len(self.workers.jobs)
        self.post('desk-source', sent_file)
        added = self.post('desk-source', sent_text)
        self.assertEqual([one['title'] for one in added['desk']['sources']],
                         ['runbook', 'Pasted notes'])
        self.assertEqual(len(self.workers.jobs), jobs)
        shot = self.open_deck(path, added, [{'snapshot': 'listed'}])['snapshots']['listed']
        self.assertIn('Pasted notes', shot['text'].split('\n'))

    def test_research_again_says_its_price_before_it_posts(self):
        path = self.research_deck()
        view = self.run_of(path)
        desk = view['desk']
        self.assertTrue(desk['research_price'])
        first = desk['research_items'][0]
        result = self.open_deck(path, view, [
            {'snapshot': 'research'}, {'tick': 'Leave out ' + first['title']},
            {'click': 'Leave out the ticked findings'}, {'click': 'Research again'}],
            **{'POST /api/desk-leave-out': [ok(view)],
               'POST /api/desk-research-again': [ok(view)]})
        shot = result['snapshots']['research']
        lines = shot['text'].split('\n')
        self.assertEqual(lines[lines.index('Research again') + 1], desk['research_price'])
        self.assertEqual(lines[lines.index('Leave out the ticked findings') + 1],
                         desk['leave_out_price'])
        self.assertIn('Leave out the ticked findings', shot['off'], 'nothing is ticked yet')
        self.assertEqual(self.posts(result), [
            ('/api/desk-leave-out', {'path': path, 'ids': [first['id']]}),
            ('/api/desk-research-again', {'path': path, 'expected': desk['expected']})])
        # What the page sends is what the server takes.
        again = self.post('desk-research-again', {'path': path, 'expected': desk['expected']})
        self.assertIsNotNone(again['desk'])

    def test_finishing_opens_as_a_panel_with_four_tools(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'}, {'click': 'Finishing'}, {'snapshot': 'panel'},
            {'click': 'Rehearse'}, {'snapshot': 'rehearse'}, {'click': 'All tools'},
            {'click': 'Close'}, {'snapshot': 'closed'}])
        shots = result['snapshots']
        self.assertNotIn('All tools', shots['desk']['buttons'])
        panel = shots['panel']
        for tool in ('Brand check', 'Review the deck', 'Speaker notes', 'Rehearse'):
            self.assertTrue(any(name.startswith(tool) for name in panel['buttons']), tool)
        self.assertIn('Finishing', panel['headings'])
        self.assertEqual(panel['filled'], ['Deliver'])
        self.assertEqual(panel['toolbar'][0]['name'], 'Deliver')
        self.assertIn(view['desk']['rehearse']['says'], shots['rehearse']['text'])
        self.assertNotIn('Rehearse', shots['closed']['headings'])
        self.assertEqual(self.posts(result), [], 'opening a tool that proposes nothing posts '
                         'nothing')

    def test_finishing_and_the_aside_sit_beside_the_slides(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'}, {'click': 'Finishing'}, {'snapshot': 'panel'}, {'poll': True},
            {'snapshot': 'polled'}, {'click': 'Outline'}, {'snapshot': 'outline'},
            {'click': 'Close'}, {'snapshot': 'closed'}])
        shots = result['snapshots']
        # The slides in a column, and beside it the aside, or Finishing while it is open.
        self.assertEqual(shots['desk']['desks'], [{'classes': ['desk-layout'],
                                                   'children': [['desk-column'], ['desk-aside']]}])
        for name in ('panel', 'polled'):
            self.assertEqual(shots[name]['desks'], [{
                'classes': ['desk-layout', 'desk-finishing'],
                'children': [['desk-column'], ['desk-finish']]}], name)
            lines = shots[name]['text'].split('\n')
            self.assertLess(lines.index('Section 2'), lines.index('Sources'), name)
            self.assertLess(lines.index('Sources'), lines.index('Finishing'), name)
        # The Outline tab has no aside: the column alone, until Finishing opens beside it.
        self.assertEqual(shots['outline']['desks'][0]['children'],
                         [['desk-column'], ['desk-finish']])
        self.assertEqual(shots['closed']['desks'], [])

    def test_apply_on_a_finding_shows_the_redraw_price_first(self):
        path = self.desk_deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            checked = self.post('desk-finish', {'path': path, 'tool': 'brand', 'again': True})
        brand = checked['desk']['finishing']['brand']
        (item,) = brand['items']
        self.assertTrue(item['price'])
        result = self.open_deck(path, checked, [
            {'click': 'Finishing'}, {'click': 'Brand check'}, {'snapshot': 'brand'},
            {'click': 'Apply'}, {'snapshot': 'priced'}, {'click': 'Apply and redraw slide 3'}],
            **{'POST /api/desk-apply': [ok(checked)]})
        shots = result['snapshots']
        self.assertIn('Text runs off the slide.', shots['brand']['text'])
        self.assertIn('Blocks delivery', shots['brand']['text'])
        noted = f"Its note: “{item['after']}”"
        brand_lines, priced = shots['brand']['text'].split('\n'), shots['priced']['text'].split('\n')
        self.assertEqual(brand_lines[brand_lines.index(noted) + 1], 'Apply')
        # Apply says what it redraws first, beside the button that sends it.
        self.assertEqual(priced[priced.index(noted) + 1:priced.index(noted) + 4],
                         [item['price'], 'Apply and redraw slide 3', 'Cancel'])
        self.assertEqual(shots['priced']['posts'], 0, 'nothing is sent before the price')
        self.assertEqual(self.posts(result), [('/api/desk-apply', {
            'path': path, 'set': brand['job'], 'ids': [{'id': item['id']}],
            'seen': checked['desk']['seen']})])
        # What the page sends is what the server takes: slide 3's section is redrawn.
        drawn = len(self.workers.of('section'))
        done = self.post('desk-apply', self.posts(result)[0][1])
        self.assertEqual(done['finished'], {'applied': 1, 'left': []})
        self.assertEqual(len(self.workers.of('section')), drawn + 1)

    def test_rehearse_shows_the_long_slides(self):
        path = self.desk_deck()
        view = self.run_of(path)
        long = copy.deepcopy(view)
        long['desk']['rehearse'] = {
            'slides': [{'number': 4, 'minutes': 11}, {'number': 5, 'minutes': 1}],
            'total': 27, 'long': [4],
            'says': "Slide 4's notes take about 11 minutes; the deck's notes take about 27 of "
                    'your 25 minutes.'}
        result = self.open_deck(path, long, [{'click': 'Finishing'}, {'click': 'Rehearse'},
                                             {'snapshot': 'rehearse'}])
        text = result['snapshots']['rehearse']['text']
        self.assertIn(long['desk']['rehearse']['says'], text)
        self.assertIn('The slides that run long', text)
        self.assertIn('Slide 4: about 11 minutes', text)
        self.assertNotIn('Slide 5: about', text)
        self.assertEqual(self.posts(result), [])

    def test_speaker_notes_show_the_old_and_new_and_apply_with_no_redraw(self):
        path = self.desk_deck()
        proposed = self.post('desk-finish', {'path': path, 'tool': 'notes'})
        proposed = self.run_of(path)
        kept = proposed['desk']['finishing']['notes']
        first = kept['items'][0]
        result = self.open_deck(path, proposed, [
            {'click': 'Finishing'}, {'click': 'Speaker notes'}, {'snapshot': 'notes'},
            {'click': 'Apply'}],
            **{'POST /api/desk-apply': [ok(proposed)]})
        shot = result['snapshots']['notes']
        self.assertIn(proposed['desk']['finish_prices']['notes'], shot['text'])
        self.assertIn('Before', shot['text'].split('\n'))
        self.assertIn(first['after'], shot['text'])
        self.assertEqual(self.posts(result), [('/api/desk-apply', {
            'path': path, 'set': kept['job'], 'ids': [{'id': first['id']}],
            'seen': proposed['desk']['seen']})])
        drawn = len(self.workers.of('section'))
        self.post('desk-apply', self.posts(result)[0][1])
        self.assertEqual(len(self.workers.of('section')), drawn)

    def test_no_word_a_person_should_not_read_in_finishing(self):
        path = self.research_deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            checked = self.post('desk-finish', {'path': path, 'tool': 'brand', 'again': True})
        result = self.open_deck(path, checked, [
            {'snapshot': 'aside'}, {'click': 'Finishing'}, {'snapshot': 'tools'},
            {'click': 'Brand check'}, {'snapshot': 'brand'}, {'click': 'All tools'},
            {'click': 'Review the deck'}, {'snapshot': 'review'}])
        for name, shot in result['snapshots'].items():
            with self.subTest(name):
                said = shot['text'] + shot['sheet']
                self.assertIsNone(FORBIDDEN_WORDS.search(said))
                self.assertNotIn(checked['desk']['expected'][:12], said)
                self.assertNotIn(checked['desk']['finishing']['brand']['job'][:12], said)


class OpenOnDeskPageTests(DeskPageCase):
    """Task 5.1: a saved deck, delivered the gated way, opens on the desk from its screen."""

    def delivered(self, **changes) -> str:
        """A deck started the gated way, approved stop by stop with the first look, and
        delivered."""
        path = self.started(**changes)
        for _ in range(12):
            gate = self.run_of(path)['gate']
            if gate is None:
                break
            offered = gate.get('offered') or (gate.get('look') or {}).get('offered')
            picked = {'extra': {'look': offered['looks'][0]['id']}} \
                if offered and not offered['chosen'] else {}
            self.decided(path, gate['name'], **picked)
        return path

    def test_open_on_the_desk_says_what_the_deck_s_level_lets_change(self):
        path = self.delivered()
        view = self.run_of(path)
        said = {None: 'Open it on the desk to note a slide, or change its words or its speaker '
                      'notes.',
                'redesign': 'Open it on the desk to note a slide, or change its words or its '
                            'speaker notes.',
                'brand-only': 'Open it on the desk to note a slide or change its speaker '
                              'notes. Its words stay your own deck’s.',
                'polish': 'Open it on the desk to note a slide or change its speaker notes. '
                          'Its words stay your own deck’s.',
                'selected': 'Open it on the desk to change your deck’s words on a copy, or '
                            'note a slide.'}
        for level, line in said.items():
            with self.subTest(level):
                shown = copy.deepcopy(view)
                shown['level'] = level
                text = self.open_deck(path, shown, [{'snapshot': 'delivered'}])[
                    'snapshots']['delivered']['text']
                self.assertIn(line + ' It stays delivered until you change it; a change '
                              'makes the next revision.', text)
                self.assertNotIn('to change a slide, its words or its speaker notes', text)

    def test_an_opened_powerpoint_delivery_still_goes_to_google_slides(self):
        path = self.delivered(output='pptx')
        opened = self.post('desk-open', {'path': path})
        self.assertTrue(opened['deliver']['to_google'])
        result = self.open_deck(path, opened, [
            {'snapshot': 'desk'}, {'click': 'Send to Google Slides'}],
            **{'POST /api/deliver': [ok(opened)]})
        self.assertIn('Send to Google Slides', result['snapshots']['desk']['buttons'])
        self.assertEqual(self.posts(result), [('/api/deliver', {'path': path})])

    def test_a_delivered_deck_offers_open_on_the_desk(self):
        path = self.delivered()
        view = self.run_of(path)
        self.assertIsNone(view['desk'])
        opened = self.post('desk-open', {'path': path})
        result = self.open_deck(path, view, [
            {'snapshot': 'delivered'}, {'click': 'Open on the desk'}, {'snapshot': 'desk'}],
            **{'POST /api/desk-open': [ok(opened)], 'GET /api/run': [ok(view), ok(view), ok(opened)]})
        delivered, desk = result['snapshots']['delivered'], result['snapshots']['desk']
        self.assertIn('Open on the desk', delivered['buttons'])
        self.assertNotIn('Open on the desk', delivered['filled'])
        self.assertIn('Delivered', delivered['text'])
        self.assertEqual(self.posts(result), [('/api/desk-open', {'path': path})])
        # The screen is the desk now: the deck's cards under their sections, still delivered.
        self.assertIn('Section 1', desk['headings'])
        self.assertIn('Delivered as revision 1.', desk['text'])
        self.assertNotIn('Open on the desk', desk['buttons'])
        # A deck on the desk already is not offered it again.
        shot = self.open_deck(path, opened, [{'snapshot': 'again'}])['snapshots']['again']
        self.assertNotIn('Open on the desk', shot['buttons'])


class MigrationPageTests(DeskPageCase):
    def saved(self):
        root = runner_support.DeskCase.gated(self)
        return str(root), self.run_of(str(root))

    def test_preview_cancel_preserves_saved_screen_and_has_no_apply(self):
        path, view = self.saved()
        preview = self.get('desk-migration-preview', path=path)
        result = self.open_deck(path, view, [
            {'click': 'Open on the desk'}, {'snapshot': 'preview'}, {'click': 'Cancel'},
            {'snapshot': 'saved'}], **{'GET /api/desk-migration-preview': [ok(preview)]})
        shot = result['snapshots']['preview']
        self.assertIn('existing slide parts', shot['sheet'])
        self.assertIn('Apply', shot['filled'])
        self.assertEqual(shot['sheetCards'], 1)
        self.assertNotIn(preview['expected'], shot['sheet'])
        self.assertEqual(self.posts(result), [])

    def test_apply_then_explicit_ready_without_delivery(self):
        path, view = self.saved()
        preview = self.get('desk-migration-preview', path=path)
        opened = self.post('desk-migrate', {'path': path, 'expected': preview['expected']})
        context = self.get('desk-ready-context', path=path)
        response = 'I reviewed these slides and approve them as ready.'
        approved = self.post('desk-ready', {'path': path, 'expected_basis': context['expected_basis'],
            'seen': context['requirements']['seen'], 'response': response})
        self.assertEqual(approved['state'], 'ready')
        self.assertIsNone(approved['deliver'])
        result = self.open_deck(path, view, [
            {'click': 'Open on the desk'}, {'click': 'Apply'}, {'snapshot': 'desk'},
            {'click': 'Mark ready'}, {'snapshot': 'approval'},
            {'fill': 'Your approval', 'value': response}, {'click': 'Mark ready'},
            {'snapshot': 'ready'}], **{
                'GET /api/desk-migration-preview': [ok(preview)],
                'POST /api/desk-migrate': [ok(opened)],
                'GET /api/desk-ready-context': [ok(context)],
                'POST /api/desk-ready': [ok(approved)],
                'GET /api/run': [ok(view), ok(view), ok(opened), ok(approved)]})
        self.assertNotIn('Deliver', result['snapshots']['desk']['buttons'])
        self.assertEqual(result['snapshots']['approval']['sheetCards'], 1)
        self.assertIn('nothing has been delivered', result['snapshots']['ready']['text'])
        self.assertEqual([address for address, _ in self.posts(result)],
                         ['/api/desk-migrate', '/api/desk-ready'])


if __name__ == '__main__':
    unittest.main()
