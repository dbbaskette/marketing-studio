"""The deck desk's page (deck-desk.js), run for real in page_harness.js: the start in three
steps, a desk deck's progress with only the look pick to ask for, and the desk itself, with a
card per slide under its section, the slide and whole-deck notes, Stop, the Outline tab and
Deliver.

Each view the page reads is what the runner's page answers for a real desk deck over the
tests' stand-ins, changed only where a test says so. Nothing starts an agent, looks at the real
computer or touches the network.
"""
import unittest

import runner_support
import test_desk
from test_desk import NODE, ok
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


if __name__ == '__main__':
    unittest.main()
