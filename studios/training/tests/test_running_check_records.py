"""The shared running-step check (core/studio_core/sync_guard.py `worker_in_progress`) over
trainings the Training Studio engine itself makes with its production options (GitHub issue
#541). Every run record schema it writes today, from the runner and from a conversation, is
a known training whose work and sources folders are skipped; a step in hand is busy; a
record it does not write is not a known training, so its folders are walked like any other.

`RunningCheckTests` always runs: the workers are scripted and Harness Research is the
stand-in, with its collection support stood in where a start needs it.
`PinnedHelperRunningCheckTests` makes the outline-first trainings over the pinned Harness
Research helper and runs only when STUDIO_TEST_RESEARCH_RUNTIME names it. Neither reaches a
provider."""
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import helpers  # noqa: F401
from runner_support import FORM, StudioCase
from runner import agents, desk_chat, outline_first
from studio_core import research_session, sync_guard
from studio_core.sync_guard import worker_in_progress

# What `runner/engine.py` Engine() is built with when nothing is said.
PRODUCTION = {'parallel_research': True, 'content_first': True, 'plan_first': True,
              'outline_first': True, 'section_synthesis': True}
# What `research_session.execution` returns for a Harness Research with collection support.
COLLECTION = {'schema': 1, 'protocol': research_session.PROTOCOL, 'workers': 3,
              'capability': {'protocol': research_session.PROTOCOL, 'digest': '0' * 64}}
RUN = '.training-studio/run.json'


class Checks:
    def scanner(self, tools, job):
        okay, said = tools.submit_artifact('scan', json.dumps(outline_first.seed('Synthetic training')))
        self.assertTrue(okay, said)
        return agents.Outcome(True, cost=0.01, seconds=1)

    def make_training(self, engine, **changes):
        from runner import pipeline
        return Path(engine.start(pipeline.check_form({**FORM, 'flow': 'desk', **changes}))['path'])

    def caches_skipped(self, root):
        """Whether the check skips this training's work and sources folders: a record there
        that only looks like a worker counts only when they are walked."""
        repo, seen = self.space.repo, []
        for cache in ('work', 'sources'):
            odd = root / cache / 'kept/.blog-runs/odd.json'
            odd.parent.mkdir(parents=True, exist_ok=True)
            odd.write_text('{"status":"working"}')
            seen.append(worker_in_progress(repo))
            odd.unlink()
        self.assertEqual(len(set(seen)), 1, seen)
        return not seen[0]

    def idle_and_known(self, root, schema):
        record = json.loads((root / RUN).read_text())
        self.assertEqual(record['schema'], schema)
        repo = self.space.repo
        self.assertFalse(worker_in_progress(repo))
        self.assertTrue(self.caches_skipped(root))
        self.assertTrue(sync_guard.training_written(record))
        # A step really in hand is busy.
        lock = root / '.training-studio/step.lock'
        lock.write_text('writing')
        self.assertTrue(worker_in_progress(repo))
        lock.unlink()
        self.assertFalse(worker_in_progress(repo))
        return record


class RunningCheckTests(Checks, StudioCase):
    def setUp(self):
        super().setUp()
        self.engine = self.make(**PRODUCTION)
        self.workers.then('scan', *([self.scanner] * 4))

    def collection(self):
        return mock.patch.object(research_session, 'execution', return_value=COLLECTION)

    def test_a_training_started_in_conversation_is_schema_4(self):
        root = Path(desk_chat.create(self.engine, {**FORM, 'materials': [], 'scope': ['outline']})['path'])
        record = self.idle_and_known(root, 4)
        self.assertEqual(record['execution'], 'conversation')
        self.assertNotIn('research_contract', record)

    def test_without_the_plan_or_collection_support_is_schema_4(self):
        engine = self.make(**{**PRODUCTION, 'plan_first': False, 'outline_first': False})
        self.idle_and_known(self.make_training(engine), 4)

    def test_parallel_research_without_the_plan_is_schema_5(self):
        engine = self.make(**{**PRODUCTION, 'plan_first': False, 'outline_first': False})
        with self.collection():
            root = self.make_training(engine)
        self.idle_and_known(root, 5)

    def test_the_plan_with_parallel_research_is_schema_6(self):
        engine = self.make(**{**PRODUCTION, 'outline_first': False})
        with self.collection():
            root = self.make_training(engine)
        self.assertIn('research_execution', self.idle_and_known(root, 6))

    def test_the_plan_without_collection_support_is_schema_6(self):
        engine = self.make(**{**PRODUCTION, 'outline_first': False})
        record = self.idle_and_known(self.make_training(engine), 6)
        self.assertNotIn('research_execution', record)

    def test_outline_first_without_section_combining_is_schema_7(self):
        engine = self.make(**{**PRODUCTION, 'section_synthesis': False})
        with self.collection():
            root = self.make_training(engine)
        self.assertEqual(engine.view(root)['state'], 'waiting')
        self.idle_and_known(root, 7)

    def test_production_defaults_are_schema_8(self):
        with self.collection():
            root = self.make_training(self.engine)
        self.assertEqual(self.view(root)['state'], 'waiting')
        self.idle_and_known(root, 8)

    def test_records_the_engine_does_not_write_are_walked_like_any_folder(self):
        with self.collection():
            root = self.make_training(self.engine)
        self.idle_and_known(root, 8)
        raw = (root / RUN).read_bytes()
        for name, change in (
                ('unknown schema', lambda r: r.update(schema=9)),
                ('no collection protocol', lambda r: r.pop('research_execution')),
                ('no section combining', lambda r: r.pop('section_synthesis')),
                ('no plan', lambda r: r.pop('training_plan')),
                ('no outline pin', lambda r: r.pop('outline_first')),
                ('off the desk', lambda r: r.pop('flow')),
                ('changed material order', lambda r: r['material_flow'].update(order='other')),
                ('no research contract', lambda r: r.pop('research_contract'))):
            with self.subTest(name):
                record = json.loads(raw)
                change(record)
                (root / RUN).write_text(json.dumps(record))
                try:
                    self.assertFalse(sync_guard.training_written(record))
                    self.assertFalse(worker_in_progress(self.space.repo))
                    self.assertFalse(self.caches_skipped(root))
                finally:
                    (root / RUN).write_bytes(raw)
        self.assertTrue(self.caches_skipped(root))


@unittest.skipUnless(os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME'), 'Pinned research helper required.')
class PinnedHelperRunningCheckTests(Checks, StudioCase):
    """The outline-first trainings, with the collection support the pinned helper reports."""

    def setUp(self):
        super().setUp()
        from runner import research
        self.research = research.Research(Path(os.environ['STUDIO_TEST_RESEARCH_RUNTIME']))
        self.workers.then('scan', *([self.scanner] * 4))

    def test_production_defaults_write_schema_8(self):
        engine = self.make(**PRODUCTION)
        self.idle_and_known(self.make_training(engine), 8)

    def test_without_section_combining_schema_7(self):
        engine = self.make(**{**PRODUCTION, 'section_synthesis': False})
        self.idle_and_known(self.make_training(engine), 7)


if __name__ == '__main__':
    unittest.main()
