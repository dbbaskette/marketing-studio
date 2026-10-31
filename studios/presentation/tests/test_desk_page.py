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
KEEP_CHOICES = ('Keep in library', 'Only this project')   # where a file added on the desk is kept


def cards_of(desk: dict) -> list:
    return [card for part in desk['sections'] for card in part['slides']]


def to(number: int) -> dict:
    """The step that chooses a slide in the desk's navigator."""
    return {'click': f'Slide {number}:'}


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
        self.assertIn('1. What you start from', kinds['parts'])
        for kind in ('An idea', 'A document', 'An existing deck'):
            self.assertTrue(any(name.startswith(kind) for name in kinds['buttons']), kind)
        steps = ['1. What you start from', '2. Audience and goal', '3. Research and settings']
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

    def test_the_source_comes_first_then_the_goal_then_the_settings(self):
        result = self.new_deck([{'click': 'An idea'}, {'snapshot': 'idea'},
                                {'click': 'Brand, output and assistant'}, {'snapshot': 'options'}])
        idea, options = result['snapshots']['idea'], result['snapshots']['options']
        sheet = idea['sheet']
        steps = ['1. What you start from', '2. Audience and goal', '3. Research and settings',
                 'What happens after Start']
        at = [sheet.index(step) for step in steps]
        self.assertEqual(at, sorted(at))
        source, goal, settings, plan = (sheet[at[0]:at[1]], sheet[at[1]:at[2]],
                                        sheet[at[2]:at[3]], sheet[at[3]:])
        self.assertIn('What should it cover? (optional)', source)
        for asked in ('A short title', 'Who is it for?', 'What should they take away?',
                      'About how long, in minutes (optional)',
                      'Is this deck for a talk or a handout?'):
            self.assertIn(asked, goal)
        for asked in ('Research first', 'Pick it when the samples are drawn',
                      'These start as your defaults.', 'Brand, output and assistant',
                      'The brand', 'Delivered as'):
            self.assertIn(asked, settings)
        self.assertIn('Approve the slide text.', plan)
        self.assertTrue(plan.rstrip().endswith('Start\nCancel'), plan[-200:])
        # The brand, the output and the assistant keep the defaults, folded away until they
        # are opened.
        for folded in ('PowerPoint (.pptx)', 'Claude Code'):
            self.assertNotIn(folded, idea['buttons'])
            self.assertIn(folded, options['buttons'])
        self.assertNotIn('Its model', idea['fields'])
        self.assertIn('Its model', options['fields'])
        self.assertEqual(options['keyedTwice'], [])

    def test_start_checks_every_step_and_focuses_the_first_gap(self):
        result = self.new_deck([{'click': 'A document'}, {'click': 'Start'},
                                {'snapshot': 'missing'}])
        missing = result['snapshots']['missing']
        self.assertEqual(missing['posts'], 0)
        for said in ('Something above is missing.', 'Give it a title first.',
                     'Choose the file first.'):
            self.assertIn(said, missing['sheet'])
        # The document comes first, in the first step, before the title and goal.
        self.assertEqual(missing['focus'], 'new-file')

    def plan_of(self, shot: dict) -> str:
        return shot['sheet'][shot['sheet'].index('What happens after Start'):]

    def test_an_idea_is_researched_whatever_a_document_was_marked(self):
        result = self.new_deck([
            {'click': 'A document'}, {'click': 'It lays out the slides'},
            {'click': 'Research first'}, {'snapshot': 'script'},
            {'click': 'An idea'}, {'snapshot': 'idea'}])
        self.assertNotIn('Research.', self.plan_of(result['snapshots']['script']))
        plan = self.plan_of(result['snapshots']['idea'])
        self.assertIn('Research. It is planned from your questions', plan)
        self.assertLess(plan.index('Research.'), plan.index('Approve the slide text.'))

    def test_a_redesign_lists_its_look_before_its_changes(self):
        default = self.get('setup').get('output')
        other = 'Google Slides' if default == 'pptx' else 'PowerPoint (.pptx)'
        result = self.new_deck([
            {'click': 'An existing deck'}, {'click': 'Redesign, keep content'},
            {'snapshot': 'pick'}, {'click': 'Use the brand’s default look'},
            {'snapshot': 'default'}, {'click': 'Brand, output and assistant'},
            {'click': other}, {'snapshot': 'changed'}])
        shots = result['snapshots']
        # The runner reads the deck, draws the looks, waits for the pick, then changes it.
        pick = self.plan_of(shots['pick'])
        order = ['Pick the look.', 'The changes are made.', 'Review the deck.', 'Deliver.']
        self.assertEqual([pick.index(step) for step in order],
                         sorted(pick.index(step) for step in order))
        self.assertIn('Pick the look. The brand draws a slide in each of its looks', pick)
        self.assertIn('A brand with no looks to show uses its own, with no stop.', pick)
        self.assertNotIn('Approve the slide text.', pick)
        self.assertIn('Before the desk, it waits for you to pick the look.', pick)
        default_plan = self.plan_of(shots['default'])
        self.assertIn('The brand’s default look. The slides are designed in it, with no '
                      'stop.', default_plan)
        self.assertLess(default_plan.index('The brand’s default look.'),
                        default_plan.index('The changes are made.'))
        # The defaults line says when this deck no longer uses them.
        self.assertIn('These start as your defaults.', shots['default']['sheet'])
        self.assertIn('Changed for this deck.', shots['changed']['sheet'])
        self.assertNotIn('These start as your defaults.', shots['changed']['sheet'])

    def test_what_happens_after_start_follows_the_choices(self):
        result = self.new_deck([
            {'click': 'An idea'}, {'snapshot': 'idea'},
            {'click': 'Use the brand’s default look'}, {'snapshot': 'default'},
            {'click': 'A document'}, {'click': 'Research first'}, {'snapshot': 'unread'},
            {'click': 'It lays out the slides'}, {'snapshot': 'script'},
            {'click': 'It is material to build from'}, {'snapshot': 'material'}])
        shots = result['snapshots']

        def plan(name):
            sheet = shots[name]['sheet']
            return sheet[sheet.index('What happens after Start'):]

        idea = plan('idea')
        self.assertIn('Before the desk, it waits for you twice: to approve the slide text, '
                      'then to pick the look.', idea)
        self.assertNotIn('Research.', idea)
        self.assertIn('Once the text is approved, the brand draws a slide in each of its '
                      'looks', idea)
        # The look choice tells the plan again in place, with no stop for the default.
        default = plan('default')
        self.assertIn('Before the desk, it waits for you to approve the slide text.', default)
        self.assertIn('The brand’s default look.', default)
        self.assertNotIn('Pick the look.', default)
        # Research on a document whose reading is left to the runner is said as maybe; a
        # finished script is never researched; material is.
        self.assertIn('Research. Only if your document turns out to be material to build '
                      'from.', plan('unread'))
        self.assertNotIn('Research.', plan('script'))
        self.assertIn('Research. It is planned from your questions', plan('material'))
        for name in shots:
            self.assertNotIn('It stops once', shots[name]['text'])

    def test_another_kind_of_deck_keeps_what_was_typed_and_chosen(self):
        sites = ['blog.example.com/platform', 'docs.example.com']
        refused = {'status': 400, 'body': {'error': 'The workspace is busy.'}}
        result = self.new_deck([
            {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Rolling restarts'},
            {'fill': 'Who is it for?', 'value': 'Operators'},
            {'fill': 'What should they take away?', 'value': 'When capacity holds.'},
            {'fill': 'About how long, in minutes (optional)', 'value': '20'},
            {'click': 'A handout'}, {'click': 'Use the brand’s default look'},
            {'click': 'Research first'}, {'tick': 'your sites'},
            {'fill': 'What should the research answer? (optional)', 'value': 'Why now?'},
            {'click': 'A document'},
            {'attach': 'The document', 'files': [{'name': 'notes.md', 'bytes': '# Notes'}]},
            {'snapshot': 'document'},
            {'click': 'An existing deck'}, {'snapshot': 'existing'},
            {'attach': 'The deck, as a .pptx',
             'files': [{'name': 'old.pptx', 'bytes': test_desk.DECK.decode('latin-1')}]},
            {'click': 'A document'}, {'snapshot': 'back'},
            {'fill': 'A short title', 'value': ''}, {'click': 'Start'},
            {'snapshot': 'missing'},
            {'fill': 'A short title', 'value': 'Rolling restarts'}, {'click': 'Start'},
            {'snapshot': 'refused'}, {'click': 'Start'}],
            **{'GET /api/setup': [self.setup_with(research_sites=sites)],
               'POST /api/decks': [refused, ok({'path': '/nowhere', 'id': 'x'})]})
        shots = result['snapshots']
        typed = {'A short title': 'Rolling restarts', 'Who is it for?': 'Operators',
                 'What should they take away?': 'When capacity holds.',
                 'About how long, in minutes (optional)': '20'}
        for name in ('document', 'existing', 'back', 'refused'):
            with self.subTest(shot=name):
                shot = shots[name]
                self.assertEqual({key: shot['fields'].get(key) for key in typed}, typed)
                self.assertIn('A handout', shot['pressed'])
        # A document keeps the research and where it may look, and the look chosen.
        for name in ('document', 'back', 'refused'):
            with self.subTest(shot=name):
                shot = shots[name]
                self.assertIn('Research first', shot['chosen'])
                self.assertIn('your sites (2)', shot['ticked'])
                self.assertEqual(shot['fields']['What should the research answer? (optional)'],
                                 'Why now?')
                self.assertIn('Use the brand’s default look', shot['pressed'])
                self.assertIn('Chosen: notes.md', shot['sheet'])
        # Each kind keeps its own file: the deck is not offered the document, and the document
        # comes back when its kind does.
        self.assertIn('Nothing chosen yet.', shots['existing']['sheet'])
        self.assertNotIn('notes.md', shots['existing']['sheet'])
        self.assertNotIn('old.pptx', shots['back']['sheet'])
        self.assertIn('Give it a title first.', shots['missing']['sheet'])
        self.assertIn('Your answers are still here.', shots['refused']['sheet'])
        posted = [body for address, body in self.posts(result) if address == '/api/decks']
        self.assertEqual(len(posted), 2)
        self.assertEqual(posted[0], posted[1])
        form = posted[1]['form']
        self.assertEqual((form['route'], form['title'], form['audience'], form['goal'],
                          form['minutes'], form['delivery'], form['look'], form['research'],
                          form['research_questions'], form['source']),
                         ('document', 'Rolling restarts', 'Operators', 'When capacity holds.',
                          20, 'reading', 'default', True, ['Why now?'],
                          {'kind': 'upload', 'name': 'notes.md'}))
        self.assertEqual(form['research_from'], {'documents': True, 'sites': sites,
                                                 'web': True})
        self.assertEqual(set(posted[1]['uploads']), {'notes.md'})

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
                         ['1. What you start from', '2. Audience and goal', '3. Research and settings'])
        sheet = existing['sheet']
        first = sheet[sheet.index('1. What you start from'):sheet.index('2. Audience and goal')]
        for level in ('Brand only', 'Polish', 'Redesign, keep content', 'Full rework',
                      'Selected changes'):
            self.assertIn(level, first)
        self.assertNotIn('Which slides, and what to fix', existing['fields'])
        # The deck itself is in the first step, before its levels; an existing deck has no
        # research, and no look to pick until it is redesigned.
        self.assertLess(first.index('The deck, as a .pptx'), first.index('Brand only'))
        for gone in ('Research first', 'Pick it when the samples are drawn', 'Review level',
                     'Where it stops'):
            self.assertNotIn(gone, sheet)
        self.assertIn('Choose how much changes.', shots['missing']['sheet'])
        self.assertEqual(shots['missing']['posts'], 0)
        self.assertIn('Which slides, and what to fix', selected['fields'])
        first = selected['sheet'][:selected['sheet'].index('2. Audience and goal')]
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


NO_SOURCES = 'Add readable sources or allow additional external search before starting.'


class ResearchStartTests(DeskPageCase):
    """Issue #255: Start with Research first on, through the shared source editor the page
    loads (research.js), for a deck from an idea and one from a document, with sources and
    without. Each answer the editor reads is the runner's own for that request, and the deck
    is started by sending the runner what the page sent."""

    TEXT = 'Synthetic reference: rolling restarts keep one instance serving.'

    def drafts(self, *steps) -> list:
        """The runner's answers to the source editor, in order: the draft it creates, then
        each change. A step is ('text', words) or ('external', on)."""
        made = [self.post('research-sources', {'action': 'create'})]
        for kind, value in steps:
            last = {'id': made[-1]['id'], 'expected': made[-1]['revision']}
            if kind == 'text':
                made.append(self.post('research-sources', {**last, 'action': 'capture',
                                                           'kind': 'text',
                                                           'name': 'Pasted notes',
                                                           'text': value}))
            else:
                made.append(self.post('research-sources', {**last, 'action': 'configure',
                                                           'external': value}))
        return [ok(one) for one in made]

    def goal(self) -> list:
        return [{'fill': 'A short title', 'value': 'Rolling restarts'},
                {'fill': 'Who is it for?', 'value': 'Platform teams'},
                {'fill': 'What should they take away?', 'value': 'When capacity holds.'}]

    def start(self, route_steps: list, steps: list, drafts: list, more=None, **plan) -> dict:
        return self.run_page(self.answers(**{**STARTED, **NOT_THERE,
                                             'POST /api/research-sources': drafts,
                                             **(more or {})}),
                             [{'click': 'New deck'}, *route_steps, *self.goal(),
                              {'click': 'Research first'}, *steps,
                              {'click': 'Start'}, {'snapshot': 'started'}],
                             research=True, **plan)

    def started_here(self, result: dict) -> dict:
        """The deck the runner starts from what the page sent, and the body it was sent."""
        body = next(body for address, body in self.posts(result) if address == '/api/decks')
        self.assertLessEqual({'form', 'uploads', 'research_inputs'}, set(body))
        self.assertLessEqual(set(body), {'form', 'uploads', 'research_inputs', 'library'})
        with mock.patch.object(self.engine, 'wake'):
            made = self.post('decks', body)
        return self.engine._load(runner_support.Path(made['path'])), body

    def pasted(self) -> list:
        return [{'click': 'Paste text'}, {'fill': 'Source text', 'value': self.TEXT},
                {'click': 'Add text'}]

    def test_an_idea_with_a_pasted_source_starts_and_is_researched(self):
        result = self.start([{'click': 'An idea'}], self.pasted(),
                            self.drafts(('text', self.TEXT)))
        shot = result['snapshots']['started']
        self.assertNotIn(NO_SOURCES, shot['text'])
        self.assertEqual(shot['sheet'], '', 'the sheet closes once the deck is started')
        record, body = self.started_here(result)
        self.assertTrue(body['form']['research'])
        self.assertEqual(body['form']['research_from'],
                         {'documents': True, 'sites': [], 'web': False})
        self.assertEqual(record['form']['research_from'],
                         {'documents': True, 'sites': [], 'web': False})
        self.assertEqual(record['research_inputs']['count'], 1)
        # Its run researches first: the research stop is among its steps.
        from runner import stages
        self.assertIn('gate:research', {step.name for step in stages.steps(record)})

    def test_an_idea_with_no_sources_is_refused_beside_them(self):
        result = self.start([{'click': 'An idea'}], [], self.drafts())
        shot = result['snapshots']['started']
        self.assertEqual(shot['posts'], 1, 'only the source draft is made')
        self.assertIn(NO_SOURCES, shot['sheet'])
        self.assertIn('Something above is missing.', shot['sheet'])
        # The first gap is where sources are added.
        self.assertEqual(shot['focusKey'], 'research-urls')

    def test_an_idea_with_no_sources_starts_once_external_search_is_allowed(self):
        result = self.start([{'click': 'An idea'}],
                            [{'click': 'Start'}, {'snapshot': 'refused'},
                             {'tick': 'Search for additional external sources'},
                             {'snapshot': 'allowed'}],
                            self.drafts(('external', True)))
        self.assertIn(NO_SOURCES, result['snapshots']['refused']['sheet'])
        # Once the sources can be used, the refusal goes.
        self.assertNotIn(NO_SOURCES, result['snapshots']['allowed']['sheet'])
        record, body = self.started_here(result)
        self.assertEqual(body['form']['research_from'],
                         {'documents': False, 'sites': [], 'web': True})
        self.assertEqual(record['research_inputs']['count'], 0)
        self.assertEqual(record['form']['research_from']['web'], True)

    def document(self) -> list:
        return [{'click': 'A document'}, {'click': 'Paste the text'},
                {'fill': 'The text', 'value': 'Synthetic notes to build from.'}]

    def test_a_document_with_a_pasted_source_starts_and_is_researched(self):
        result = self.start(self.document(), [{'snapshot': 'research'}, *self.pasted()],
                            self.drafts(('text', self.TEXT)))
        self.assertIn('Your source document is included with these references.',
                      result['snapshots']['research']['sheet'])
        self.assertEqual(result['snapshots']['started']['sheet'], '')
        record, body = self.started_here(result)
        self.assertEqual(body['form']['route'], 'document')
        self.assertEqual(record['research_inputs']['count'], 1)
        self.assertTrue(record['form']['research_from']['documents'])

    def test_a_document_with_no_other_sources_starts_on_its_own(self):
        result = self.start(self.document(), [], self.drafts())
        shot = result['snapshots']['started']
        self.assertNotIn(NO_SOURCES, shot['text'])
        self.assertEqual(shot['sheet'], '')
        record, body = self.started_here(result)
        self.assertEqual(body['form']['research_from'],
                         {'documents': True, 'sites': [], 'web': False})
        self.assertEqual(record['research_inputs']['count'], 0)

    # --- the start's sources and the desk's Sources card (#255, item 3) ---------------------

    def library(self):
        """A disposable Document Library holding one readable brief."""
        import os
        import tempfile
        from studio_core import document_library
        place = tempfile.TemporaryDirectory()
        self.addCleanup(place.cleanup)
        patcher = mock.patch.dict(os.environ, {'STUDIOS_LIBRARY': place.name + '/library'})
        patcher.start()
        self.addCleanup(patcher.stop)
        return document_library.opened(create=True).add_upload(
            'brief.md', b'# Brief\n\nCapacity holds with two instances.\n')

    def test_the_start_offers_the_desks_add_from_library_and_keep_choice(self):
        result = self.start([{'click': 'An idea'}], [{'snapshot': 'sources'}], self.drafts())
        shot = result['snapshots']['sources']
        for offered in ('Add links', 'Choose files', 'Paste text', 'Add from library',
                        'Use saved research'):
            self.assertIn(offered, shot['buttons'])
        # An uploaded file is kept in the library unless Only this project, as on the desk.
        self.assertIn('Where an uploaded file is kept', shot['sheet'])
        self.assertEqual([name for name in shot['pressed'] if name in KEEP_CHOICES],
                         ['Keep in library'])

    def test_a_library_document_chosen_at_the_start_is_pinned_as_a_deck_source(self):
        from runner import documents
        brief = self.library()
        pick = {'id': brief['id'], 'revision': brief['revision']}
        read = self.post('library-document', pick)
        result = self.start([{'click': 'An idea'}],
                            [{'click': 'Add from library'}, {'snapshot': 'picked'}],
                            self.drafts(), {'POST /api/library-document': [ok(read)]},
                            library=[pick])
        picked = result['snapshots']['picked']
        self.assertEqual(result['library'], [{'studio': 'presentation', 'max': 40,
                                              'refocus': 'research-library'}])
        self.assertIn('brief\nFrom the Document Library, revision 1', picked['sheet'])
        self.assertIn('Remove brief', picked['buttons'])
        # The library document is research's own material: no other source is needed.
        self.assertNotIn('Add material here', picked['sheet'])
        self.assertEqual(result['snapshots']['started']['sheet'], '')
        record, body = self.started_here(result)
        self.assertEqual(body['library'], [pick])
        self.assertEqual(body['form']['research_from'],
                         {'documents': True, 'sites': [], 'web': False})
        root = self.deck_root(record)
        listed = documents.listed(root)
        self.assertEqual([(one['title'], one['library']['id']) for one in listed],
                         [('brief', brief['id'])])
        sources = self.engine._desk_view(root, record)['sources']
        self.assertEqual([one['title'] for one in sources], ['brief'])

    def deck_root(self, record: dict):
        """The folder of the one deck the runner started here."""
        found = [path.parent for path in self.engine.space().root.rglob('run.json')
                 if '.research-sources' not in path.parts]
        self.assertEqual(len(found), 1, found)
        return found[0]

    def test_the_desk_lists_the_sources_research_was_given_at_the_start(self):
        from studio_core import research_sources
        from runner import documents
        result = self.start([{'click': 'An idea'}], self.pasted(),
                            self.drafts(('text', self.TEXT)))
        record, _ = self.started_here(result)
        root = self.deck_root(record)
        sources = self.engine._desk_view(root, record)['sources']
        self.assertEqual([(one['title'], one['readable'], one['given']) for one in sources],
                         [('Pasted notes', True, 'given at the start, for research')])
        # Every source research reads is listed, and the words jobs read them too.
        read = [*documents.sources(root)[0],
                *research_sources.sources(root, record['research_inputs'])[0]]
        self.assertEqual(len(read), len(sources))
        self.assertIn(self.TEXT, self.engine._desk_sources(root, record))
        # The card says where it came from.
        path = self.desk_deck()
        view = self.run_of(path)
        view['desk']['sources'] = sources
        shot = self.open_deck(path, view, [{'snapshot': 'desk'}])['snapshots']['desk']
        self.assertIn('Pasted notes · given at the start, for research', shot['text'])
        self.assertNotIn('No sources yet.', shot['text'])


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
        path = self.saved_started()
        result = self.open_deck(path, self.run_of(path), [{'snapshot': 'gated'}])
        shot = result['snapshots']['gated']
        self.assertIsNone(self.run_of(path)['desk'])
        self.assertEqual(shot['filled'], ['Approve'])
        self.assertNotIn(NOTHING_NEEDED, shot['text'])
        self.assertNotIn('Section 1', shot['headings'])


class DeskTests(DeskPageCase):
    """Task 1.14: the desk, with its cards, notes, Stop, the Outline tab and Deliver."""

    def test_the_desk_is_a_navigator_beside_one_slide(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [{'snapshot': 'desk'}, to(3), {'snapshot': 'three'},
                                             {'click': 'Next slide'}, {'snapshot': 'four'}])
        shot, three, four = (result['snapshots'][name] for name in ('desk', 'three', 'four'))
        self.assertEqual(shot['filled'], ['Deliver'])
        self.assertEqual(shot['toolbar'][0], {'name': 'Deliver', 'filled': True, 'quiet': False})
        self.assertIn('Download', [control['name'] for control in shot['toolbar']])
        for tab in ('Slides', 'Outline'):
            self.assertIn(tab, shot['buttons'])
        numbered = [part['number'] for part in view['desk']['sections'] if not part['lead']]
        self.assertEqual(numbered, [1, 2])
        # The navigator names every slide; the first is the one shown.
        cards = cards_of(view['desk'])
        for card in cards:
            self.assertTrue(any(name.startswith(f"Slide {card['number']}: ")
                                for name in shot['buttons']), card['number'])
        self.assertEqual([name for name in shot['current'] if name.startswith('Slide')],
                         [f"Slide 1: {cards[0]['words']['title']}"])
        self.assertIn('Slide 1 of 8', shot['text'].split('\n'))
        lead = [card['number'] for card in cards if card['lead']]
        self.assertEqual(lead, [1, 8])
        # A lead slide takes no note; a content slide takes one, and only it is shown.
        self.assertFalse([name for name in shot['buttons'] if name.startswith('Redraw slide')])
        self.assertIn('Slide 3 · Section 1', three['parts'])
        self.assertEqual([name for name in three['buttons'] if name.startswith('Redraw slide')],
                         ['Redraw slide 3'])
        self.assertEqual(three['text'].count('How should this slide change?'), 1)
        # The focus stays on what was pressed: the slide in the navigator, then Next.
        self.assertEqual(three['focus'], three['current'][-1])
        self.assertTrue(three['focus'].startswith('Slide 3: '))
        self.assertIn('Slide 4 of 8', four['text'].split('\n'))
        self.assertEqual(four['focus'], 'Next slide')
        self.assertEqual([name for name in four['buttons'] if name.startswith('Redraw slide')],
                         ['Redraw slide 4'])
        # No card holds another.
        for one in (shot, three, four):
            self.assertEqual(one['nested'], 0)

    def test_a_slide_note_shows_its_price_and_posts_the_deck_on_screen(self):
        path = self.desk_deck()
        view = self.run_of(path)
        card = next(card for card in cards_of(view['desk']) if card['number'] == 3)
        self.assertTrue(card['price'])
        after = copy.deepcopy(view)
        result = self.open_deck(path, view, [
            to(3), {'snapshot': 'desk'}, {'click': 'Redraw slide 3'}, {'snapshot': 'empty'},
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
        content = [card for card in cards_of(view['desk']) if not card['lead']]
        shot = self.open_deck(path, view, [to(content[0]['number']), {'snapshot': 'desk'}])[
            'snapshots']['desk']
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
            to(5), {'snapshot': 'working'}, to(3), {'snapshot': 'three'}, {'click': 'Stop'},
            {'snapshot': 'stopped'}],
            **{'POST /api/desk-stop': [ok(view)]})
        shot = result['snapshots']['working']
        lines = shot['text'].split('\n')
        self.assertIn('Redrawing: 1 of 2 sections', lines)
        self.assertLess(lines.index('Redrawing: 1 of 2 sections'), lines.index('Slide 5 of 8'))
        self.assertEqual(self.posts(result), [('/api/desk-stop', {'path': path})])
        # A slide whose section is redrawn says so, in the navigator too, and its controls wait.
        self.assertIn('Redrawing…', shot['text'])
        for number in (5, 6, 7):
            self.assertTrue(any(name.startswith(f'Slide {number}: ')
                                and name.endswith(', redrawing') for name in shot['buttons']))
        self.assertIn('Redraw slide 5', shot['off'])
        self.assertNotIn('Redraw slide 3', result['snapshots']['three']['off'])
        self.assertIn('Redraw slide 3', result['snapshots']['three']['buttons'])
        self.assertIn('Deliver', shot['off'])

    def test_the_whole_deck_note_says_its_price_and_redraws_every_section(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            {'snapshot': 'desk'}, {'click': 'Change the whole deck'}, {'snapshot': 'open'},
            {'fill': 'How should the whole deck change?', 'value': 'Fewer words.'},
            {'click': 'Redraw every section'}],
            **{'POST /api/desk-deck-note': [ok(view)]})
        shot, opened = result['snapshots']['desk'], result['snapshots']['open']
        # A second way to change the deck, folded under the slide, that says what it redraws.
        self.assertNotIn('How should the whole deck change?', shot['fields'])
        self.assertIn('How should the whole deck change?', opened['fields'])
        self.assertIn(view['desk']['deck_price'], opened['text'])
        self.assertIn('This redraws every section of the deck: 2 sections, 8 slides.',
                      opened['text'])
        self.assertLess(opened['text'].index('Slide 1 of 8'),
                        opened['text'].index('How should the whole deck change?'))
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


def long_deck(view: dict, count: int) -> dict:
    """The deck on screen made up to `count` slides from its own: its cover, one section of
    content slides and its closing slide, each content slide a copy of its first."""
    shown = copy.deepcopy(view)
    cards = cards_of(shown['desk'])
    cover, closing = cards[0], cards[-1]
    model = next(card for card in cards if not card['lead'])
    content = []
    for number in range(2, count):
        card = copy.deepcopy(model)
        card.update(number=number, id=f'synthetic-{number}', section='section-1',
                    image={'kind': 'build', 'ref': number})
        card['words']['title'] = f'Synthetic slide {number}'
        content.append(card)
    shown['desk']['sections'] = [
        {'id': None, 'lead': True, 'number': None, 'slides': [cover]},
        {'id': 'section-1', 'lead': False, 'number': 1, 'slides': content},
        {'id': None, 'lead': True, 'number': None, 'slides': [{**closing, 'number': count}]}]
    return shown


def reviewed_on(view: dict, number: int) -> dict:
    """The deck on screen with a fix the review proposed for one slide, to apply or skip. As
    the runner makes it, the proposal is the slide's own review finding."""
    shown = copy.deepcopy(view)
    card = next(card for card in cards_of(shown['desk']) if card['number'] == number)
    finding = {'severity': 'major', 'about': 'drawing', 'question': None,
               'note': 'The labels overlap the chart.', 'fix': 'Move the labels under the chart.'}
    card['findings'] = [finding]
    shown['desk']['finishing'] = {'review': {'job': 'review-job', 'kind': 'finish-review',
                                             'items': [{
        'id': 'finding-1', 'number': number, 'part': card['id'], 'state': 'open',
        'present': True, 'severity': 'major', 'about': 'drawing', 'note': finding['note'],
        'fix': finding['fix'], 'after': finding['fix'],
        'price': 'Redraws section 1. Expect minutes, not seconds.'}]}}
    return shown


class WorkbenchTests(DeskPageCase):
    """Issue 218: the Slides tab is a workbench. A summary says what stands before Deliver
    and goes to each slide it names; the navigator reaches any slide at once; the slide
    chosen and the words typed on it stay through the tabs, Finishing and the sheets."""

    def test_any_of_thirty_slides_is_one_choice_away_on_a_desktop_and_a_phone(self):
        path = self.desk_deck()
        view = long_deck(self.run_of(path), 30)
        for narrow in (False, True):
            with self.subTest(phone=narrow):
                result = self.run_page(self.answers(**{'GET /api/run': [ok(view)]}), [
                    {'snapshot': 'first'}, to(17), {'snapshot': 'seventeen'},
                    {'press': 'End', 'on': 'Slide 17:'}, {'snapshot': 'last'},
                    {'click': 'Next slide'}, {'snapshot': 'still'},
                    {'press': 'ArrowLeft', 'on': 'Slide 30:'}, {'snapshot': 'back'}],
                    state={'screen': 'deck', 'path': path}, narrow=narrow)
                shots = result['snapshots']
                first = shots['first']
                self.assertEqual(len([name for name in first['buttons']
                                      if name.startswith('Slide ')]), 30)
                self.assertIn('Slide 1 of 30', first['text'].split('\n'))
                # The summary stays short: past five slides, the rest are counted.
                self.assertRegex(first['text'], r'\nAnd \d+ more\. The navigator marks each '
                                                r'slide\.\n')
                self.assertLessEqual(len([line for line in first['text'].split('\n')
                                          if line.endswith('brand warning.')]), 5)
                seventeen = shots['seventeen']
                self.assertIn('Slide 17 of 30', seventeen['text'].split('\n'))
                self.assertIn('Slide 17 · Section 1', seventeen['parts'])
                self.assertEqual(seventeen['fields']['Title of slide 17'], 'Synthetic slide 17')
                # Only the slide chosen has boxes.
                self.assertEqual({label.rsplit(' ', 1)[-1] for label in seventeen['fields']
                                  if ' of slide ' in label or ' for slide ' in label}, {'17'})
                # End goes to the last slide, and the focus follows it.
                self.assertIn('Slide 30 of 30', shots['last']['text'].split('\n'))
                self.assertTrue(shots['last']['focus'].startswith('Slide 30: '))
                # Next at the last slide stays there, and says it is off.
                self.assertIn('Slide 30 of 30', shots['still']['text'].split('\n'))
                self.assertIn('Slide 29 of 30', shots['back']['text'].split('\n'))
                self.assertTrue(shots['back']['focus'].startswith('Slide 29: '))
                self.assertEqual(self.posts(result), [])

    def test_the_slide_and_its_unsaved_words_stay_through_tabs_finishing_and_deliver(self):
        path = self.desk_deck()
        view = self.run_of(path)
        title, note = 'Title of slide 3', 'How should this slide change? Slide 3'
        result = self.open_deck(path, view, [
            to(3), {'fill': title, 'value': 'Typed, not saved', 'stay': True},
            {'fill': note, 'value': 'Shorter.'},
            {'click': 'Outline'}, {'snapshot': 'outline'}, {'click': 'Slides'},
            {'snapshot': 'tabs'},
            {'click': 'Finishing'}, {'click': 'Rehearse'}, {'snapshot': 'finishing'},
            {'click': 'Close Finishing'}, {'snapshot': 'closed'},
            {'click': 'Deliver'}, {'snapshot': 'sheet'}, {'click': 'Cancel'},
            {'snapshot': 'cancelled'}])
        shots = result['snapshots']
        self.assertNotIn('Slide 3 of 8', shots['outline']['text'].split('\n'))
        for name in ('tabs', 'finishing', 'closed', 'cancelled'):
            with self.subTest(name):
                shot = shots[name]
                self.assertIn('Slide 3 of 8', shot['text'].split('\n'))
                self.assertEqual(shot['fields'][title], 'Typed, not saved')
                self.assertEqual(shot['fields'][note], 'Shorter.')
                # The summary says the words are not saved yet, and goes to their slide.
                self.assertIn('Slide 3: Words not saved yet.', shot['text'].split('\n'))
        # The sheet is over the same slide, and Cancel gives the focus back to Deliver.
        self.assertIn('Deliver the deck', shots['sheet']['sheet'])
        self.assertEqual(shots['cancelled']['focus'], 'Deliver')
        # Nothing was sent: no words saved, no note drawn, no version kept.
        self.assertEqual(self.posts(result), [])

    def test_a_reload_opens_the_deck_at_the_slide_chosen(self):
        path = self.desk_deck()
        view = self.run_of(path)
        card = next(card for card in cards_of(view['desk']) if card['number'] == 5)
        chosen = self.open_deck(path, view, [to(5), {'snapshot': 'chosen'}])
        kept = chosen['snapshots']['chosen']['state']
        self.assertEqual((kept['screen'], kept['path'], kept['deskSlide']),
                         ('deck', path, card['id']))
        reloaded = self.run_page(self.answers(**{'GET /api/run': [ok(view)]}),
                                 [{'snapshot': 'again'}], state=kept)
        self.assertIn('Slide 5 of 8', reloaded['snapshots']['again']['text'].split('\n'))
        # A slide since moved keeps its place by its ID; one since removed falls back.
        gone = self.run_page(self.answers(**{'GET /api/run': [ok(view)]}),
                             [{'snapshot': 'gone'}], state={**kept, 'deskSlide': 'not-there',
                                                            'deskNumber': 4})
        self.assertIn('Slide 4 of 8', gone['snapshots']['gone']['text'].split('\n'))

    def test_the_summary_goes_to_each_slide_and_keeps_warnings_apart_from_blockers(self):
        path = self.desk_deck()
        view = self.run_of(path)
        shown = copy.deepcopy(view)
        cards = {card['number']: card for card in cards_of(shown['desk'])}
        shown['desk']['blockers'] = [{'number': 3, 'says': 'Text runs off the slide.'}]
        cards[3]['audit'] = [{'says': 'Text runs off the slide.', 'kind': 'error'}]
        cards[5]['audit'] = [{'says': 'A colour is not in the palette.', 'kind': 'warning'}]
        cards[6]['findings'] = [{'severity': 'minor', 'about': 'drawing', 'question': None,
                                 'note': 'The chart is hard to read from the back.',
                                 'fix': 'Make the bars wider.'}]
        result = self.open_deck(path, shown, [
            {'snapshot': 'summary'}, {'click': 'Go to slide 5'}, {'snapshot': 'five'},
            {'click': 'Go to slide 6'}, {'snapshot': 'six'}])
        summary, five, six = (result['snapshots'][name] for name in ('summary', 'five', 'six'))
        lines = summary['text'].split('\n')
        # The slide that blocks delivery is the one shown first.
        self.assertIn('Slide 3 of 8', lines)
        self.assertIn('The brand check: Text runs off the slide. It blocks delivery.', lines)
        self.assertEqual(summary['sheet'], '')
        self.assertIn('1 problem blocks delivery. Deliver asks you before it sends the deck '
                      'anyway.', lines)
        blocks, looks = lines.index('Blocks delivery'), lines.index('Worth a look')
        self.assertEqual(lines[blocks + 2], 'Slide 3: Text runs off the slide.')
        self.assertEqual(lines[looks + 1], 'These do not block delivery.')
        # What Deliver will use is said before its sheet is opened.
        delivery = lines.index('What Deliver will use')
        for line in ('Slide 5: 1 brand warning.', 'Slide 6: 1 review finding.'):
            self.assertIn(line, lines[looks:delivery])
        self.assertNotIn('Slide 3: Text runs off the slide.', lines[looks:delivery])
        self.assertLess(lines.index('Before you deliver'), delivery)
        self.assertEqual(lines[delivery + 1], 'The 8 slides as they are drawn now, not reviewed: '
                         'only the brand check ran. It goes to Google Slides. Nothing is sent '
                         'until you confirm it in Deliver.')
        # The navigator says the same of each slide, a blocker apart from a warning.
        self.assertTrue([name for name in summary['buttons']
                         if name.startswith('Slide 3: ') and name.endswith(', blocks delivery')])
        self.assertTrue([name for name in summary['buttons']
                         if name.startswith('Slide 5: ') and name.endswith(', worth a look')])
        # A line of the summary goes to its slide, and the focus to the slide itself.
        self.assertIn('Slide 5 of 8', five['text'].split('\n'))
        self.assertEqual(five['focus'], 'desk-slide-title')
        self.assertIn('The brand check: A colour is not in the palette. A warning: it does not '
                      'block delivery.', five['text'].split('\n'))
        self.assertNotIn('It blocks delivery.', five['text'])
        # The review's finding, in its words, with its severity and what it suggests.
        self.assertIn('MinorAbout how it was drawnThe chart is hard to read from the back.'
                      'Suggested: Make the bars wider.', six['text'].split('\n'))
        self.assertEqual(self.posts(result), [])

    def test_a_fix_found_on_a_slide_says_what_it_redraws_before_it_is_applied_or_skipped(self):
        path = self.desk_deck()
        shown = reviewed_on(self.run_of(path), 4)
        (item,) = shown['desk']['finishing']['review']['items']
        result = self.open_deck(path, shown, [
            {'snapshot': 'summary'}, {'click': 'Go to slide 4'}, {'snapshot': 'found'},
            {'click': 'Apply'}, {'snapshot': 'priced'}, {'click': 'Apply and redraw slide 4'}],
            **{'POST /api/desk-apply': [ok(shown)]})
        shots = result['snapshots']
        summary = shots['summary']['text'].split('\n')
        self.assertIn('Slide 4: 1 fix to apply or skip.', summary)
        # The finding the fix was made from is counted, and shown, once: as the fix.
        self.assertNotIn('Slide 4: 1 review finding.', summary)
        found = shots['found']['text'].split('\n')
        self.assertIn('Proposed by the review Major', found)
        self.assertIn(item['note'], found)
        self.assertEqual(shots['found']['text'].count(item['note']), 1)
        self.assertIn('Suggested: ' + item['fix'], found)
        priced = shots['priced']['text'].split('\n')
        self.assertEqual(priced[priced.index(item['price']) + 1:priced.index(item['price']) + 3],
                         ['Apply and redraw slide 4', 'Cancel'])
        self.assertEqual(shots['priced']['posts'], 0, 'nothing is sent before the price')
        self.assertEqual(self.posts(result), [('/api/desk-apply', {
            'path': path, 'set': 'review-job', 'ids': [{'id': item['id']}],
            'seen': shown['desk']['seen']})])
        skipped = self.open_deck(path, shown, [{'click': 'Go to slide 4'}, {'click': 'Skip'}],
                                 **{'POST /api/desk-skip': [ok(shown)]})
        self.assertEqual(self.posts(skipped), [('/api/desk-skip', {
            'path': path, 'set': 'review-job', 'ids': [item['id']]})])

    def test_the_slide_shown_first_stays_when_what_drew_the_desk_to_it_is_resolved(self):
        path = self.desk_deck()
        view = self.run_of(path)
        blocked = copy.deepcopy(view)
        blocked['desk']['blockers'] = [{'number': 4, 'says': 'Text runs off the slide.'}]
        next(card for card in cards_of(blocked['desk']) if card['number'] == 4)['audit'] = [
            {'says': 'Text runs off the slide.', 'kind': 'error'}]
        result = self.open_deck(path, blocked, [
            {'snapshot': 'first'}, {'fill': 'Title of slide 4', 'value': 'A shorter title'},
            {'timer': 'flush'}, {'snapshot': 'saved'}],
            **{'POST /api/desk-words': [ok(view)]})
        first, saved = result['snapshots']['first'], result['snapshots']['saved']
        self.assertIn('Slide 4 of 8', first['text'].split('\n'))
        # The save answers with the blocker gone: the desk stays on slide 4, in its box.
        self.assertNotIn('Blocks delivery', saved['text'].split('\n'))
        self.assertIn('Slide 4 of 8', saved['text'].split('\n'))
        self.assertEqual(saved['focus'], 'desk-title-4')
        self.assertEqual(saved['state']['deskNumber'], 4)

    def test_a_brand_fix_for_a_blocker_is_shown_and_counted_once(self):
        path = self.desk_deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            checked = self.post('desk-finish', {'path': path, 'tool': 'brand', 'again': True})
        (item,) = checked['desk']['finishing']['brand']['items']
        result = self.open_deck(path, checked, [{'snapshot': 'three'}])
        shot = result['snapshots']['three']
        lines = shot['text'].split('\n')
        self.assertIn('Slide 3 of 8', lines)
        # The check's line is the fix: once on the slide, with its tag, and once in the summary.
        self.assertEqual(shot['text'].count(item['says']), 2)
        self.assertNotIn('The brand check: Text runs off the slide. It blocks delivery.', lines)
        self.assertIn('Proposed by the brand check Blocks delivery', lines)
        self.assertIn('Slide 3: Text runs off the slide.', lines)
        self.assertFalse([line for line in lines if line.startswith('Slide 3: 1 fix')])

    def test_a_slide_the_stopped_whole_deck_note_left_says_to_redraw_it(self):
        path = self.desk_deck()
        view = copy.deepcopy(self.run_of(path))
        next(card for card in cards_of(view['desk']) if card['number'] == 6)['note'] = {
            'status': 'set aside', 'whole': True, 'note': 'Fewer words.'}
        shot = self.open_deck(path, view, [{'snapshot': 'desk'}])['snapshots']['desk']
        self.assertTrue([name for name in shot['buttons']
                         if name.startswith('Slide 6: ') and name.endswith(', not redrawn')])
        self.assertIn('Slide 6: Not redrawn when the whole-deck note was stopped: Redraw slide 6 '
                      'draws it again.', shot['text'].split('\n'))

    def test_the_first_key_typed_marks_the_slide_and_keeps_the_box(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            to(3), {'fill': 'Title of slide 3', 'value': 'Typed', 'stay': True},
            {'snapshot': 'typed'}])
        shot = result['snapshots']['typed']
        self.assertIn('Slide 3: Words not saved yet.', shot['text'].split('\n'))
        self.assertTrue([name for name in shot['buttons']
                         if name.startswith('Slide 3: ') and name.endswith(', waits for you')])
        self.assertEqual(shot['focus'], 'desk-title-3')
        self.assertEqual(shot['fields']['Title of slide 3'], 'Typed')
        self.assertEqual(self.posts(result), [])

    def test_with_no_deliver_here_the_summary_says_where_the_deck_stands(self):
        path = self.desk_deck()
        view = self.run_of(path)
        delivered = self.post('desk-deliver', {'path': path, 'expected': view['desk']['expected'],
                                               'blockers_seen': view['desk']['blockers_seen']})
        shot = self.open_deck(path, delivered, [{'snapshot': 'delivered'}])['snapshots'][
            'delivered']
        lines = shot['text'].split('\n')
        self.assertIn('Where the deck stands', lines)
        self.assertNotIn('Before you deliver', lines)
        self.assertNotIn('Nothing blocks delivery.', lines)
        self.assertNotIn('What Deliver will use', lines)
        self.assertIn('The brand check found nothing that blocks delivery.', lines)

    def test_the_caveat_and_source_are_folded_and_the_whole_deck_note_comes_last(self):
        path = self.desk_deck()
        view = self.run_of(path)
        card = next(card for card in cards_of(view['desk'])
                    if not card['lead'] and (card['words'].get('caveat')
                                             or card['words'].get('source')))
        number = card['number']
        result = self.open_deck(path, view, [
            to(number), {'snapshot': 'folded'}, {'click': 'Caveat and source'},
            {'snapshot': 'open'}])
        folded, opened = result['snapshots']['folded'], result['snapshots']['open']
        boxes = [label for label in opened['fields']
                 if label.startswith(('Caveat', 'Source')) and label.endswith(f'slide {number}')]
        self.assertTrue(boxes)
        for label in boxes:
            self.assertNotIn(label, folded['fields'])
        lines = folded['text'].split('\n')
        self.assertLess(lines.index(f'Slide {number} of 8'), lines.index('Change the whole deck'))
        # The note's price says the section it redraws, and the slides in it.
        self.assertIn(card['price'], lines)
        self.assertIn('Redraws section', card['price'])


SESSION_SHAPE = r'^[0-9a-f]{16}$'


class WordsTests(DeskPageCase):
    """Task 2.5: a slide's words, its speaker notes and its History, on its card."""

    def card(self, view: dict, number: int) -> dict:
        return next(card for card in cards_of(view['desk']) if card['number'] == number)

    def test_typing_saves_a_second_after_the_last_key(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            to(3), {'fill': 'Title of slide 3', 'value': 'Batches restart in turn'},
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
            to(3), {'fill': 'Point 2 text of slide 3', 'value': 'Requests are dropped.'},
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
            to(3), {'fill': 'Title of slide 3', 'value': 'Batches restart in turn'},
            {'timer': 'flush'}, {'snapshot': 'refused'}],
            **{'POST /api/desk-words': [refused]})
        shot = result['snapshots']['refused']
        self.assertIn('This slide changed since you opened it.', shot['text'])
        self.assertEqual(shot['fields']['Title of slide 3'], 'Batches restart in turn')

    def test_speaker_notes_are_their_own_box(self):
        path = self.desk_deck()
        view = self.run_of(path)
        result = self.open_deck(path, view, [
            to(3), {'snapshot': 'desk'},
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
            to(3), {'snapshot': 'none'},
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
            to(3), {'select': 'Title of slide 3', 'start': 0, 'end': 8}, {'click': 'Ask…'},
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
            to(3), {'snapshot': 'unfit'}, {'click': 'Redraw with these words'}, {'click': 'Discard'}],
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
            to(3), {'click': 'History of slide 3'}, {'snapshot': 'history'}, {'click': 'Restore'}],
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
            to(3), {'click': 'History of slide 3'}, {'snapshot': 'history'},
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
            to(3), {'fill': 'Title of slide 3', 'value': 'Batches restart in turn'},
            {'select': 'Title of slide 3', 'start': 0, 'end': 7}, {'snapshot': 'typed'}])
        self.assertNotIn('Rephrase', result['snapshots']['typed']['buttons'])
        unfit = copy.deepcopy(view)
        self.card(unfit, 3)['unfit'] = {
            'number': 3, 'field': 'title', 'text': 'A much longer title', 'lines': ['Too long.'],
            'at': '2026-10-27T09:00:00Z', 'says': 'These words do not fit the slide as it is '
                                                  'drawn.'}
        result = self.open_deck(path, unfit, [
            to(3), {'select': 'Title of slide 3', 'start': 0, 'end': 6}, {'snapshot': 'unfit'}])
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
            to(3), {'snapshot': 'unfit'}, {'click': 'Redraw with these words'}],
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
        shot = self.open_deck(path, self.run_of(path), [to(3), {'snapshot': 'desk'}])[
            'snapshots']['desk']
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
            to(3), {'select': 'Title of slide 3', 'start': 0, 'end': 8}, {'snapshot': 'bar'},
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
            to(2), {'snapshot': 'desk'}, {'see': 'Slide 2 as it was in your deck'},
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
            to(2), {'snapshot': 'desk'},
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
            {'snapshot': 'first'}, to(2), {'snapshot': 'desk'},
            {'fill': 'Text box 2, part 1 of slide 2', 'value': 'Ship fast'},
            {'timer': 'flush'}], **{'POST /api/desk-words': [ok(view)]})
        shot = result['snapshots']['desk']
        self.assertIn(OWN_NOTES, shot['text'])
        self.assertFalse([label for label in shot['fields'] if 'Speaker notes' in label])
        self.assertEqual(shot['fields']['Text box 2, part 2 of slide 2'], 'in minutes.')
        first = next(card for card in cards_of(view['desk']) if card['number'] == 1)
        self.assertEqual(result['snapshots']['first']['fields']['Text box 1 of slide 1'],
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
        result = self.open_deck(path, view, [to(2), {'snapshot': 'desk'}, {'click': 'Discard'}],
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
        self.assertLess(lines.index('Change the whole deck'), lines.index('Sources'))
        self.assertIn('Add a source', lines)
        for label in ('A file', 'Or paste its text', 'Its title'):
            self.assertIn(label, shot['fields'])
        self.assertIn('No sources yet.', shot['text'])
        self.assertNotIn('Research again', shot['buttons'], 'a deck with no research')
        self.assertIn('Paste the text of the source first.', result['snapshots']['empty']['text'])
        # Keep in library is the visible default, chosen before the file is.
        self.assertIn('Keep the file', shot['text'].split('\n'))
        self.assertEqual([name for name in shot['pressed'] if name in KEEP_CHOICES],
                         ['Keep in library'])
        self.assertLess(lines.index('Keep the file'), lines.index('A file'))
        self.assertIn('It is shared with no one either way.', shot['text'])
        (file_address, sent_file), (text_address, sent_text) = self.posts(result)
        self.assertEqual((file_address, text_address), ('/api/desk-source', '/api/desk-source'))
        self.assertEqual((sent_file['path'], sent_file['name'], sent_file['library']),
                         (path, 'runbook.md', True))
        self.assertEqual(base64.b64decode(sent_file['content']),
                         b'# Runbook\n\nTwo batches at a time.\n')
        self.assertEqual(sent_text, {'path': path, 'text': 'Health checks gate each batch.',
                                     'title': 'Pasted notes'})
        # What the page sends is what the server takes, and nothing is drawn.
        jobs = len(self.workers.jobs)
        kept = self.post('desk-source', sent_file)['library_upload']
        added = self.post('desk-source', sent_text)
        self.assertEqual([one['title'] for one in added['desk']['sources']],
                         ['runbook', 'Pasted notes'])
        self.assertEqual(len(self.workers.jobs), jobs)
        # The library has the file as it was sent, kept locally; the deck's own copy is an
        # ordinary supplied source, as it is with Only this project.
        from studio_core import document_library
        row = document_library.opened().describe(kept['id'])
        self.assertEqual((kept['state'], row['studio'], row['kind'], row['scope'],
                          row['original_name']),
                         ('kept', 'presentation', 'upload', 'local', 'runbook.md'))
        self.assertEqual(document_library.opened().download(kept['id'], 1, 'original')[2],
                         b'# Runbook\n\nTwo batches at a time.\n')
        self.assertNotIn('library', added['desk']['sources'][0])
        shot = self.open_deck(path, added, [{'snapshot': 'listed'}])['snapshots']['listed']
        self.assertIn('Pasted notes', shot['text'].split('\n'))

    def test_only_this_project_keeps_the_file_out_of_the_library(self):
        from studio_core import document_library
        path = self.desk_deck()
        view = self.run_of(path)
        upload = {'name': 'limits.md', 'text': '# Limits\n\nForty at most.\n'}
        failed = {**view, 'library_upload': {'state': 'failed', 'problem': 'Not kept: busy.'}}
        # Every refresh after the opening answers with other sources, so the card is drawn
        # again after the failure: what the library said must still be there.
        polled = copy.deepcopy(view)
        polled['desk']['sources'] = [{'name': 'other.md', 'title': 'other', 'readable': True}]
        result = self.open_deck(path, view, [
            {'click': 'Only this project'}, {'snapshot': 'chosen'},
            {'attach': 'A file', 'files': [upload]}, {'polls': 1},
            {'click': 'Keep in library'},
            {'attach': 'A file', 'files': [{**upload, 'name': 'other.md'}]}, {'polls': 1},
            {'poll': True}, {'snapshot': 'failed'}],
            **{'POST /api/desk-source': [ok(view), ok(failed)],
               'GET /api/run': [ok(view), ok(polled)]})
        self.assertIn('other', result['snapshots']['failed']['text'].split('\n'),
                      'the card was drawn again from the refresh')
        self.assertEqual([name for name in result['snapshots']['chosen']['pressed']
                          if name in KEEP_CHOICES], ['Only this project'])
        (_, only), (_, keep) = self.posts(result)
        self.assertEqual((only['library'], keep['library']), (False, True))
        # A failed library save is said on the card; the deck still has the source.
        self.assertIn('Not kept: busy.', result['snapshots']['failed']['text'])
        # The server keeps nothing in the library for Only this project.
        before = document_library.opened(create=True).catalog(limit=50)['total']
        added = self.post('desk-source', only)
        self.assertNotIn('library_upload', added)
        self.assertEqual(document_library.opened().catalog(limit=50)['total'], before)
        self.assertEqual([one['name'] for one in added['desk']['sources']], ['limits.md'])
        # When the library cannot keep it, the deck has its source all the same.
        with mock.patch.object(document_library, 'opened',
                               side_effect=document_library.LibraryError('The library is busy.')):
            said = self.post('desk-source', {**only, 'name': 'other.md', 'library': True})
        self.assertEqual(said['library_upload']['state'], 'failed')
        self.assertIn('The library is busy.', said['library_upload']['problem'])
        self.assertEqual([one['name'] for one in said['desk']['sources']],
                         ['limits.md', 'other.md'])
        refused = self.post('desk-source', {**only, 'name': 'third.md', 'library': 'yes'},
                            expect=400)
        self.assertIn('Keep in library or Only this project', json.dumps(refused))

    def test_a_delivered_deck_says_pdf_saved_only_when_the_library_has_it(self):
        path = self.desk_deck()
        view = self.run_of(path)
        delivered = self.post('desk-deliver', {'path': path, 'expected': view['desk']['expected'],
                                               'blockers_seen': view['desk']['blockers_seen']})
        self.assertEqual(delivered['desk']['library']['pdf'], 'saved')
        shot = self.open_deck(path, delivered, [{'snapshot': 'kept'}])['snapshots']['kept']
        self.assertIn('Kept in the Document Library as a PDF and slide Markdown, revision '
                      f"{delivered['desk']['library']['revision']}. PDF saved.", shot['text'])
        without = copy.deepcopy(delivered)
        without['desk']['library'].update(pdf='needs-export', pdf_note='No PDF was left here.')
        shot = self.open_deck(path, without, [{'snapshot': 'kept'}])['snapshots']['kept']
        self.assertIn('PDF needs export: No PDF was left here.', shot['text'])
        self.assertNotIn('PDF saved', shot['text'])

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
            self.assertLess(lines.index('Change the whole deck'), lines.index('Sources'), name)
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
        path = self.saved_started(**changes)
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
        # The screen is the desk now: the navigator and the slide chosen, still delivered.
        self.assertIn('Previous slide', desk['buttons'])
        self.assertIn('Delivered as revision 1.', desk['text'])
        self.assertNotIn('Open on the desk', desk['buttons'])
        # A deck on the desk already is not offered it again.
        shot = self.open_deck(path, opened, [{'snapshot': 'again'}])['snapshots']['again']
        self.assertNotIn('Open on the desk', shot['buttons'])


class MigrationPageTests(DeskPageCase):
    def test_selected_ready_requires_unchecked_historical_proof_acknowledgment(self):
        from test_desk_migration import ReadyTests
        path = str(ReadyTests.selected_migrated(self))
        view = self.run_of(path)
        context = self.get('desk-ready-context', path=path)
        response = 'I acknowledge missing historical proof and approve the current checked copy.'
        seen = {**context['requirements']['seen'], 'historical_proof_ack': True}
        approved = self.post('desk-ready', {'path': path, 'expected_basis': context['expected_basis'],
            'seen': seen, 'response': response})
        acknowledgment = 'I understand the missing historical byte proof and approve the current checked copy.'
        result = self.open_deck(path, view, [{'click': 'Mark ready'}, {'snapshot': 'unchecked'},
            {'fill': 'Your approval', 'value': response}, {'snapshot': 'typed'},
            {'click': 'Mark ready'}, {'snapshot': 'refused'}, {'tick': acknowledgment},
            {'snapshot': 'acknowledged'}, {'click': 'Mark ready'}, {'snapshot': 'ready'}], **{
                'GET /api/desk-ready-context': [ok(context)], 'POST /api/desk-ready': [ok(approved)],
                'GET /api/run': [ok(view), ok(view), ok(approved)]})
        for name in ('unchecked', 'typed', 'refused'):
            self.assertIn('Mark ready', result['snapshots'][name]['off'])
            self.assertEqual(result['snapshots'][name]['posts'], 0)
        self.assertNotIn('Mark ready', result['snapshots']['acknowledged']['off'])
        self.assertEqual(self.posts(result), [('/api/desk-ready', {'path': path,
            'expected_basis': context['expected_basis'], 'seen': seen, 'response': response})])

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
