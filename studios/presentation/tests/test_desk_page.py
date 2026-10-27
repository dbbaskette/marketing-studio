"""The deck desk's page (deck-desk.js), run for real in page_harness.js: the start in three
steps, a desk deck's progress with only the look pick to ask for, and the desk itself, with a
card per slide under its section, the slide and whole-deck notes, Stop, the Outline tab and
Deliver.

Each view the page reads is what the runner's page answers for a real desk deck over the
tests' stand-ins, changed only where a test says so. Nothing starts an agent, looks at the real
computer or touches the network.
"""
import copy
import json
import unittest
from datetime import UTC, datetime

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


def cards_of(desk: dict) -> list:
    return [card for part in desk['sections'] for card in part['slides']]


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

    def test_the_existing_deck_card_opens_the_form_it_has_now(self):
        result = self.new_deck([
            {'click': 'An existing deck'}, {'snapshot': 'existing'},
            {'attach': 'The deck, as a .pptx',
             'files': [{'name': 'old.pptx', 'bytes': test_desk.DECK.decode('latin-1')}]},
            {'click': 'Polish'}, {'fill': 'A short title', 'value': 'Old deck'},
            {'click': 'Start the deck'}])
        existing = result['snapshots']['existing']
        for part in ('1. How it begins', '2. Your deck and what changes', '5. Where it stops'):
            self.assertIn(part, existing['parts'])
        self.assertIn('Review level', existing['sheet'])
        (_, body), = self.posts(result)
        self.assertEqual((body['form']['route'], body['form']['level']), ('existing', 'polish'))
        self.assertNotIn('flow', body['form'])


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

    def test_the_first_pull_request_says_where_words_change(self):
        path = self.desk_deck()
        view = self.run_of(path)
        shot = self.open_deck(path, view, [{'snapshot': 'desk'}])['snapshots']['desk']
        content = [card for card in cards_of(view['desk']) if not card['lead']]
        self.assertEqual(shot['text'].count(WORDS_LINE), len(content))
        lines = shot['text'].split('\n')
        self.assertEqual(lines[lines.index(WORDS_LINE) - 1],
                         content[0]['price'], 'the price comes first, under the button')
        # The words and the speaker notes are shown, and are not boxes to type in.
        self.assertIn(content[0]['words']['title'], shot['text'])
        self.assertIn(content[0]['notes'], shot['text'])
        self.assertNotIn('Title of slide 2', shot['fields'])

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


if __name__ == '__main__':
    unittest.main()
