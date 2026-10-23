import json
import re
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from runner import decks, gitstate
from workspace import WorkspaceError


class FirstDraftWordsTests(unittest.TestCase):
    def test_the_first_draft_choice_is_refused_in_its_own_words(self):
        from runner.steps import deliver
        with self.assertRaisesRegex(WorkspaceError, '^Choose a checked deck, or the first draft '
                                    'before the check.$'):
            decks.check_form({'route': 'scratch', 'title': 'A deck', 'output': 'pptx',
                              'initial_review': 'whatever'}, None)
        run = {'title': 'A deck', 'form': {'initial_review': 'user-first'}}
        self.assertEqual(deliver._title(run, 1), 'A deck — first draft, not checked')

BRANDS = [{'brand': 'acme', 'variants': ['light']},
          {'brand': 'globex', 'variants': ['light', 'dark']}]


def form(**over):
    sent = {'route': 'scratch', 'title': 'Spring AI on Acme', 'audience': 'Platform teams',
            'goal': 'Show the path to production', 'brand': 'acme', 'variant': 'light',
            'output': 'google', 'research': False}
    sent.update(over)
    return sent


UPLOAD = {'kind': 'upload', 'name': 'a.pptx'}
SITES = ['https://blog.example.com/platform', 'https://docs.example.com']


class FormTests(unittest.TestCase):
    def test_notes_are_kept_and_limited(self):
        self.assertEqual(decks.check_form(form(notes='  Cover rollback first.  '), BRANDS)['notes'], 'Cover rollback first.')
        self.assertEqual(decks.check_form(form(), BRANDS)['notes'], '')
        with self.assertRaisesRegex(WorkspaceError, '^The brief can be at most 4000 characters.$'):
            decks.check_form(form(notes='x' * 4001), BRANDS)

    def test_the_research_questions_are_kept_as_written(self):
        self.assertEqual(decks.check_form({**form(), 'research_questions': '  Why?  \n\nWhat next?'}, None)['research_questions'], ['Why?', 'What next?'])
        for given, message in ((['Why?'] * 9, 'Ask research at most 8'), (['x' * 301], 'Keep each research question to 300'), ([7], 'one a line')):
            with self.assertRaisesRegex(WorkspaceError, message):
                decks.check_form({**form(), 'research_questions': given}, None)

    def test_research_from_a_document_says_where_it_may_look(self):
        sent = form(route='document', research=True, source={'kind': 'paste', 'text': 'Synthetic notes.'})
        for given, expected, words in (
                ({'documents': True, 'sites': [], 'web': False},
                 {'documents': True, 'sites': [], 'web': False}, 'from your documents'),
                ({'documents': True, 'sites': ['blog.example.com/platform/', 'https://docs.example.com'],
                  'web': False},
                 {'documents': True, 'sites': SITES, 'web': False},
                 'from your documents and 2 of your sites (blog.example.com/platform, docs.example.com)'),
                ({'documents': False, 'sites': SITES[:1], 'web': True},
                 {'documents': False, 'sites': SITES[:1], 'web': True},
                 'from 1 of your sites (blog.example.com/platform) and the public web'),
                ({'documents': True, 'web': True},
                 {'documents': True, 'sites': [], 'web': True},
                 'from your documents and the public web')):
            with self.subTest(given):
                checked = decks.check_form({**sent, 'research_from': given}, BRANDS)
                self.assertEqual(checked['research_from'], expected)
                self.assertNotIn('research_sources', checked)
                self.assertEqual(decks.research_from(checked), expected)
                self.assertIn('## Research\nyes, ' + words + '\n', decks.intake(checked))
        self.assertNotIn('research_from', decks.check_form(form(), BRANDS))
        self.assertIn('## Research\nno\n', decks.intake(decks.check_form(form(), BRANDS)))

    def test_research_must_look_somewhere_that_applies(self):
        from studio_core import research_sites
        sent = form(route='document', research=True, source={'kind': 'paste', 'text': 'Notes.'})
        for given, said in (({'documents': False, 'sites': [], 'web': False}, research_sites.EMPTY),
                            ({}, research_sites.EMPTY), ('web', research_sites.EMPTY),
                            ({'documents': True, 'other': True}, research_sites.EMPTY),
                            ({'sites': ['http://docs.example.com']}, 'research sites use https only'),
                            ({'sites': ['https://localhost/x']}, 'is not a public site')):
            with self.subTest(given):
                with self.assertRaisesRegex(WorkspaceError, re.escape(said)):
                    decks.check_form({**sent, 'research_from': given}, BRANDS)
        # A deck from an idea has no documents of its own: they never count.
        with self.assertRaisesRegex(WorkspaceError, re.escape(research_sites.NO_DOCUMENTS)):
            decks.check_form(form(research=True, research_from={'documents': True}), BRANDS)
        checked = decks.check_form(form(research=True, research_from={
            'documents': True, 'sites': SITES, 'web': False}), BRANDS)
        self.assertEqual(checked['research_from'], {'documents': False, 'sites': SITES, 'web': False})

    def test_a_site_added_for_one_deck_leaves_the_shared_list_alone(self):
        import os
        from studio_core import research_sites, studios_config
        config = Path(os.environ['STUDIOS_CONFIG'])
        before = config.read_bytes() if config.exists() else None
        self.addCleanup(lambda: config.write_bytes(before) if before is not None
                        else config.unlink(missing_ok=True))
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'research': {'sites': SITES[:1]}, 'output': 'pptx'}))
        held = config.read_bytes()
        shared = research_sites.defaults(studios_config.read()[0])
        checked = decks.check_form(form(research=True, research_from={
            'sites': [*shared, 'https://extra.example.org/guide']}), BRANDS)
        self.assertEqual(checked['research_from']['sites'],
                         [SITES[0], 'https://extra.example.org/guide'])
        self.assertEqual(config.read_bytes(), held)
        self.assertEqual(research_sites.defaults(studios_config.read()[0]), SITES[:1])

    def test_old_saved_forms_stay_readable(self):
        documents_only = {'documents': True, 'sites': [], 'web': False}
        both = {'documents': True, 'sites': [], 'web': True}
        web = {'documents': False, 'sites': [], 'web': True}
        for saved, expected in (
                ({'route': 'document', 'research': True, 'research_sources': 'documents'}, documents_only),
                ({'route': 'document', 'research': True, 'research_sources': 'both'}, both),
                ({'route': 'document', 'research': True}, both),
                ({'route': 'scratch', 'research': True}, web),
                ({'route': 'scratch', 'research': True, 'research_sources': 'both'}, web)):
            with self.subTest(saved):
                self.assertEqual(decks.research_from(saved), expected)
        self.assertIsNone(decks.research_from({'route': 'scratch', 'research': False}))
        self.assertIsNone(decks.research_from({'route': 'existing', 'research': True}))
        # A plan's own scope speaks for a deck that kept no choice; one that would look
        # nowhere looks only at the documents, and fetches nothing.
        self.assertEqual(decks.research_from({}, 'supplied-only'), documents_only)
        self.assertEqual(decks.research_from({}, 'supplied-only', documents_given=False),
                         documents_only)
        self.assertEqual(decks.research_from({}, 'public-web', documents_given=False), web)
        # A form sent the old way is still taken, in the new shape.
        sent = form(route='document', research=True, source={'kind': 'paste', 'text': 'Notes.'})
        for value, expected in ((None, documents_only), ('documents', documents_only), ('both', both)):
            with self.subTest(value):
                checked = decks.check_form({**sent, **({'research_sources': value} if value else {})}, BRANDS)
                self.assertEqual(checked['research_from'], expected)
                self.assertNotIn('research_sources', checked)
        self.assertEqual(decks.check_form(form(research=True), BRANDS)['research_from'], web)
        with self.assertRaisesRegex(WorkspaceError, 'Choose where research may look'):
            decks.check_form({**sent, 'research_sources': 'web'}, BRANDS)

    def test_scratch_form(self):
        checked = decks.check_form(form(), BRANDS)
        self.assertEqual(checked['route'], 'scratch')
        self.assertEqual(checked['output'], 'google')

    def test_talk_or_handout_is_asked_once_with_a_default_by_route(self):
        self.assertEqual(decks.check_form(form(), BRANDS)['delivery'], 'live',
                         'an idea or a brief is a talk')
        for route, extra in (('document', {'source': {'kind': 'paste', 'text': 'Notes.'}}),
                             ('existing', {'source': UPLOAD, 'level': 'polish'})):
            with self.subTest(route=route):
                checked = decks.check_form(form(route=route, **extra), BRANDS)
                self.assertEqual(checked['delivery'], 'reading', 'material is a handout')
        self.assertEqual(decks.check_form(form(delivery='reading'), BRANDS)['delivery'],
                         'reading')
        self.assertEqual(decks.check_form(form(route='document', delivery='live',
                                               source={'kind': 'paste', 'text': 'x'}),
                                          BRANDS)['delivery'], 'live')
        with self.assertRaisesRegex(WorkspaceError, 'a talk or a handout'):
            decks.check_form(form(delivery='podcast'), BRANDS)
        self.assertIn('## Delivery\na talk', decks.intake(decks.check_form(form(), BRANDS)))

    def test_a_brand_with_no_variants_takes_none(self):
        brands = [{'brand': 'plain', 'variants': []}]
        for variant in (None, ''):
            checked = decks.check_form(form(brand='plain', variant=variant), brands)
            self.assertIsNone(checked['variant'])
        with self.assertRaisesRegex(WorkspaceError, 'has no "dark" variant'):
            decks.check_form(form(brand='plain', variant='dark'), brands)

    def test_unknown_route(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(route='video'), BRANDS)

    def test_existing_needs_a_level(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(route='existing', source=UPLOAD), BRANDS)

    def test_selected_needs_what_to_change(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(route='existing', level='selected', source=UPLOAD), BRANDS)

    def test_selected_keeps_its_text(self):
        checked = decks.check_form(form(route='existing', level='selected', source=UPLOAD,
                                        selected='Slide 3: shorter'), BRANDS)
        self.assertEqual(checked['selected'], 'Slide 3: shorter')

    def test_no_research_for_existing(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(route='existing', level='polish', research=True,
                                  source=UPLOAD), BRANDS)

    def test_unknown_variant(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(variant='dark'), BRANDS)

    def test_unknown_brand(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(brand='nope'), BRANDS)

    def test_title_limit(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(title='x' * 121), BRANDS)

    def test_missing_title(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(title='  '), BRANDS)

    def test_document_needs_a_source_and_keeps_only_a_reference(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(route='document'), BRANDS)
        checked = decks.check_form(form(route='document',
                                        source={'kind': 'paste', 'text': 'secret body'}), BRANDS)
        self.assertEqual(checked['source'], {'kind': 'paste'})

    def test_existing_refuses_pasted_source(self):
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(route='existing', level='polish',
                                  source={'kind': 'paste', 'text': 'x'}), BRANDS)

    def test_minutes(self):
        self.assertEqual(decks.check_form(form(minutes='30'), BRANDS)['minutes'], 30)
        with self.assertRaises(WorkspaceError):
            decks.check_form(form(minutes=241), BRANDS)


class CreateTests(unittest.TestCase):
    def setUp(self):
        self.space = gitstate.local(Path(tempfile.mkdtemp()) / 'ws')

    def test_create_writes_intake_run_and_readme(self):
        root = decks.create(self.space, decks.check_form(form(), BRANDS))
        self.assertEqual(root.name, 'spring-ai-on-acme')
        run = decks.read_run(root)
        self.assertEqual(run['route'], 'scratch')
        self.assertIn('# Spring AI on Acme', (root / 'README.md').read_text())
        self.assertIn('Platform teams', (root / 'intake.md').read_text())

    def test_create_commits(self):
        root = decks.create(self.space, decks.check_form(form(), BRANDS))
        self.assertTrue(gitstate.known(self.space, root))
        self.assertEqual(gitstate.changed(self.space), [])

    def test_same_title_twice_gets_a_new_id(self):
        first = decks.create(self.space, decks.check_form(form(), BRANDS))
        second = decks.create(self.space, decks.check_form(form(), BRANDS))
        self.assertEqual(second.name, first.name + '-2')

    def test_run_round_trip(self):
        root = decks.create(self.space, decks.check_form(form(), BRANDS))
        run = decks.read_run(root)
        run['gates']['outline'] = {'state': 'waiting', 'round': 1}
        decks.write_run(root, run)
        self.assertEqual(decks.read_run(root)['gates']['outline']['state'], 'waiting')

    def test_index_lists_decks(self):
        decks.create(self.space, decks.check_form(form(), BRANDS))
        decks.write_index(self.space)
        self.assertIn('Spring AI on Acme', (self.space.root / 'README.md').read_text())


class DeliveredTests(unittest.TestCase):
    def setUp(self):
        self.space = gitstate.local(Path(tempfile.mkdtemp()) / 'ws')
        self.root = decks.create(self.space, decks.check_form(form(), BRANDS))
        self.run = decks.read_run(self.root)

    def test_readme_shows_the_google_link(self):
        text = decks.readme(self.run, {'output': 'google', 'url': 'https://slides.example/x',
                                       'fileId': 'x', 'pptx': None, 'revision': 1, 'at': 't'})
        self.assertIn('https://slides.example/x', text)
        self.assertIn('finished', text)

    def test_readme_shows_the_pptx_name(self):
        text = decks.readme(self.run, {'output': 'pptx', 'url': None, 'fileId': None,
                                       'pptx': 'talk.pptx', 'revision': 1, 'at': 't'})
        self.assertIn('talk.pptx', text)

    def test_index_and_state_follow_deliver_json(self):
        self.assertEqual(decks.state(self.run, self.root), 'in progress')
        (self.root / decks.DELIVER).write_text(json.dumps(
            {'output': 'google', 'url': 'https://slides.example/x', 'fileId': 'x',
             'pptx': None, 'revision': 1, 'at': 't'}))
        self.assertEqual(decks.state(self.run, self.root), 'finished')
        row = decks.index(self.space)
        self.assertIn('https://slides.example/x', row)
        self.assertIn('spring-ai-on-acme/README.md', row)
        self.assertIn('finished', row)

    def test_index_for_pptx(self):
        (self.root / decks.DELIVER).write_text(json.dumps({'output': 'pptx', 'pptx': 'a.pptx'}))
        self.assertIn('PowerPoint file', decks.index(self.space))
