"""The shared running-step check (core/studio_core/sync_guard.py `worker_in_progress`) over
decks the Presentation Studio engine itself makes with its production options (GitHub issue
#541). Every run record schema the engine writes is a known, idle deck whose work and
sources folders are skipped; a step in hand is busy; a record the engine does not write is
refused, naming its folder.

`RunningCheckTests` always runs: the workers are scripted and Harness Research is the
stand-in, with its collection support stood in where a start needs it (the slide-story and
section-combining starts stop at the story before any research runs).
`PinnedHelperRunningCheckTests` makes the same decks over the pinned Harness Research helper
and runs only when STUDIO_TEST_RESEARCH_RUNTIME names it. Neither reaches a provider."""
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import runner_support
import test_slide_story as story_tests
from runner import decks, desk_chat
from studio_core import presentation_migration, research_session, sync_guard
from studio_core.sync_guard import worker_in_progress

# What `runner/engine.py` Engine() is built with when nothing is said.
PRODUCTION = {'parallel_research': True, 'content_first': True, 'story_first': True,
              'section_synthesis': True}
# What `research_session.execution` returns for a Harness Research with collection support.
COLLECTION = {'schema': 1, 'protocol': research_session.PROTOCOL, 'workers': 3,
              'capability': {'protocol': research_session.PROTOCOL, 'digest': '0' * 64}}


class Checks:
    """What every recognised deck must show, whichever helper made it."""

    def idle_and_known(self, root, schema):
        record = json.loads((root / 'run.json').read_text())
        self.assertEqual(record['schema'], schema)
        repo = self.space.repo
        self.assertFalse(worker_in_progress(repo))
        self.assertTrue(presentation_migration.written(record))
        # A known deck's work and sources are its own caches: a record there that only looks
        # like a worker is skipped, not read as one.
        for cache in ('work', 'sources'):
            odd = root / cache / 'kept/.blog-runs/odd.json'
            odd.parent.mkdir(parents=True, exist_ok=True)
            odd.write_text('{}')
            self.assertFalse(worker_in_progress(repo))
            odd.unlink()
        # A step really in hand is busy.
        lock = root / 'work/step.lock'
        lock.write_text('drawing')
        self.assertTrue(worker_in_progress(repo))
        lock.unlink()
        self.assertFalse(worker_in_progress(repo))
        return record

    def refused_by_name(self, root, change):
        raw = (root / 'run.json').read_bytes()
        record = json.loads(raw)
        change(record)
        (root / 'run.json').write_text(json.dumps(record))
        try:
            with self.assertRaises(ValueError) as caught:
                worker_in_progress(self.space.repo)
            where = root.relative_to(self.space.repo).as_posix()
            self.assertEqual(str(caught.exception), sync_guard.unchecked(where, sync_guard.UNKNOWN_DECK))
            self.assertNotIn(str(self.base), str(caught.exception))
        finally:
            (root / 'run.json').write_bytes(raw)
        self.assertFalse(worker_in_progress(self.space.repo))


class RunningCheckTests(Checks, runner_support.DeskCase):
    scanner = story_tests.SlideStoryTests.scanner

    def setUp(self):
        super().setUp()
        self.engine = self.make(**PRODUCTION)
        self.workers.then('scan', *([self.scanner] * 4))

    def collection(self):
        return mock.patch.object(research_session, 'execution', return_value=COLLECTION)

    def test_a_desk_deck_without_research_is_schema_1(self):
        self.idle_and_known(self.start_desk(title='No research'), 1)

    def test_a_deck_started_in_conversation_is_schema_1(self):
        form = {**runner_support.FORM, 'flow': 'desk', 'scope': ['outline'], 'title': 'Talked'}
        root = Path(desk_chat.create(self.engine, form)['path'])
        self.assertEqual(self.idle_and_known(root, 1)['execution'], 'conversation')

    def test_research_without_the_slide_story_or_collection_support_is_schema_3(self):
        # With the slide story on, a start without collection support is refused; without
        # it, the stand-in helper's research contract alone is saved.
        engine = self.make(**{**PRODUCTION, 'story_first': False})
        self.idle_and_known(self.start_desk(title='Contract only', research=True, engine=engine), 3)

    def test_parallel_research_without_the_slide_story_is_schema_4(self):
        engine = self.make(**{**PRODUCTION, 'story_first': False, 'section_synthesis': False})
        with self.collection():
            root = self.start_desk(title='Parallel', research=True, engine=engine)
        self.idle_and_known(root, 4)

    def test_research_with_the_slide_story_is_schema_5(self):
        engine = self.make(**{**PRODUCTION, 'section_synthesis': False})
        with self.collection():
            root = self.start_desk(title='Story first', research=True, engine=engine)
        self.assertEqual(engine.view(root)['gate']['name'], 'gate:story')
        self.idle_and_known(root, 5)

    def test_research_with_production_defaults_is_schema_6(self):
        with self.collection():
            root = self.start_desk(title='Researched', research=True)
        self.assertEqual(self.view(root)['gate']['name'], 'gate:story')
        self.idle_and_known(root, 6)

    def test_records_the_engine_does_not_write_are_refused_by_folder(self):
        with self.collection():
            root = self.start_desk(title='Researched', research=True)
        self.idle_and_known(root, 6)
        for name, change in (
                ('unknown schema', lambda r: r.update(schema=7)),
                ('no collection protocol', lambda r: r.pop('research_execution')),
                ('no section combining', lambda r: r.pop('section_synthesis')),
                ('no slide story', lambda r: r.pop('slide_story')),
                ('slide story off the desk', lambda r: r.pop('flow')),
                ('broken story budget', lambda r: r['slide_story'].update(limits={'seconds': -1})),
                ('no research contract', lambda r: r.pop('research_contract'))):
            with self.subTest(name):
                self.refused_by_name(root, change)

    def test_a_deck_record_is_never_made_eligible_to_migrate(self):
        with self.collection():
            root = self.start_desk(title='Researched', research=True)
        record = json.loads((root / 'run.json').read_text())
        self.assertTrue(presentation_migration.written(record))
        self.assertFalse(presentation_migration.supported(record))


@unittest.skipUnless(os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME'), 'Pinned research helper required.')
class PinnedHelperRunningCheckTests(Checks, runner_support.DeskCase):
    """The same records, with the collection support the pinned helper really reports."""
    scanner = story_tests.SlideStoryTests.scanner
    worker = story_tests.SlideStoryTests.worker

    def setUp(self):
        super().setUp()
        from runner import research
        from synthesis_fixture import TEXT
        self.research = research.Research(Path(os.environ['STUDIO_TEST_RESEARCH_RUNTIME']))
        self.web.page(runner_support.URL, TEXT, 'text/plain')
        self.phases, self.caps, self.questions, self.tasks = [], [], [], []
        self.barrier = None
        self.workers.then('scan', *([self.scanner] * 4))
        self.workers.then('research-result', *([self.worker] * 12))

    def test_production_defaults_write_schema_6(self):
        engine = self.make(**PRODUCTION)
        root = self.start_desk(title='Researched', research=True, engine=engine)
        self.assertEqual(engine.view(root)['gate']['name'], 'gate:story')
        self.idle_and_known(root, 6)

    def test_without_section_combining_schema_5(self):
        engine = self.make(**{**PRODUCTION, 'section_synthesis': False})
        root = self.start_desk(title='Story first', research=True, engine=engine)
        self.idle_and_known(root, 5)

    def test_without_the_slide_story_schema_4(self):
        engine = self.make(**{**PRODUCTION, 'story_first': False, 'section_synthesis': False})
        root = self.start_desk(title='Parallel', research=True, engine=engine)
        self.idle_and_known(root, 4)


if __name__ == '__main__':
    unittest.main()
