"""The training desk in the runner: a desk start, which saves no review level, and a desk
run, which the engine carries past every gate with a desk receipt. Scripted workers, the
stand-in for harness-research and a studios config of the test's own; nothing real is
started. Tests named row_138 and row_140 cover those rows of the state-transition matrix in
docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md."""
import json
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401
import home
import workspace
from runner_support import FORM
from studio_core import research_contract, review_policy
from test_runner_deck import DeckCase
from workspace import WorkspaceError

from runner import drafts, pipeline
from runner import engine as engines

CONTRACT = {'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}
NO_CONTRACT = 'This run is missing its saved research contract. Restore its run record.'


class DeskStartTests(DeckCase):
    """A training started on the desk is a schema 4 run with `flow: 'desk'` and no review
    level, and a saved training keeps the gates it began with."""

    def made(self):
        """What a start could leave behind: the trainings driven and remembered, the
        workspace's folders and its commits."""
        return (self.engine.trainings(), [entry['path'] for entry in home.trainings()],
                sorted(path.name for path in self.space.root.iterdir()), self.log())

    def test_row_138_a_desk_start_saves_no_review_level(self):
        made = self.engine.start(pipeline.check_form(
            {**FORM, 'flow': 'desk', 'source_scope': 'supplied-only'}))
        root = Path(made['path'])
        self.assertEqual(made['gates'], 0)
        record = self.record(root)
        self.assertEqual((record['schema'], record['flow']), (4, 'desk'))
        self.assertNotIn('review_policy', record)
        self.assertNotIn('review_layout', record)
        self.assertEqual(record['drafts'], {'jobs': [], 'updates': {}, 'findings_before': None})
        self.assertTrue(drafts.on_desk(record))
        session = workspace.load(root)
        self.assertEqual(session['flow'], 'desk')
        self.assertNotIn('review_policy', session)
        self.assertEqual(session['artifacts']['intake']['approved']['by'], 'page')
        self.assertIsNone(self.view(root)['review_level'], 'a desk run has no review level')
        # The documents come first: nothing is researched from part of them.
        self.assertEqual(self.workers.jobs, [])
        self.assertFalse([name for name in record['steps'] if name.startswith('research')])
        self.send(root, 'handbook.md')
        self.assertEqual(self.workers.jobs, [])
        self.engine.supply(root, 'done')
        self.assertTrue([name for name in self.record(root)['steps']
                         if name.startswith('research')])

    def test_a_desk_start_keeps_its_research_contract(self):
        with mock.patch.object(research_contract, 'snapshot', return_value=CONTRACT):
            root = self.start(flow='desk')
        record = self.record(root)
        self.assertEqual((record['schema'], record['research_contract']), (4, CONTRACT))
        self.assertEqual(workspace.load(root)['research_contract'], CONTRACT)

    def test_the_form_takes_only_a_listed_flow(self):
        with self.assertRaisesRegex(WorkspaceError, '^Choose a listed flow.$'):
            pipeline.check_form({**FORM, 'flow': 'review'})
        self.assertEqual(pipeline.check_form({**FORM, 'flow': 'desk'})['flow'], 'desk')
        self.assertIsNone(pipeline.check_form(FORM).get('flow'))
        self.assertIsNone(pipeline.check_form({**FORM, 'flow': None}).get('flow'))

    def test_row_140_a_desk_start_needs_synthesis(self):
        before = self.made()
        with mock.patch.object(engines, 'LEGACY_RESEARCH', False), \
                self.assertRaises(WorkspaceError) as caught:
            self.start(flow='desk')
        self.assertEqual(str(caught.exception), drafts.NEEDS_SYNTHESIS)
        # One refusal for every start: the desk's is the engine's own (row 137).
        self.assertEqual(drafts.NEEDS_SYNTHESIS, engines.NO_SYNTHESIS)
        self.assertEqual(self.made(), before, 'nothing is made')

    def test_a_desk_start_writes_no_shared_level(self):
        from runner import studios_config
        studios_config.update({'review': {'level': 'balanced'}})
        config = self.base / 'studios.json'
        before = config.read_bytes()
        with mock.patch.object(review_policy, 'change',
                               side_effect=AssertionError('the shared level was changed')):
            root = self.start(flow='desk', review_level='automatic', review_seen='balanced',
                              review_default=True)
        self.assertEqual(config.read_bytes(), before)
        record = self.record(root)
        self.assertNotIn('review_policy', record)
        self.assertNotIn('review_policy', workspace.load(root))

    def test_a_desk_record_is_read_with_its_research_contract(self):
        root = self.start(flow='desk')
        record = self.record(root)
        path = root / engines.RECORD

        def read(**changes):
            path.write_text(json.dumps({**record, **changes}), encoding='utf-8')
            return engines.read_record(root)

        # The tests' legacy queue lets a desk run read without one, as it lets it start.
        self.assertEqual(read()['flow'], 'desk')
        with mock.patch.object(engines, 'LEGACY_RESEARCH', False):
            self.assertEqual(read(research_contract=CONTRACT)['schema'], 4)
            for changes in ({}, {'research_contract': {'schema': 1}},
                            {'research_contract': CONTRACT, 'flow': None}):
                with self.subTest(changes=changes), \
                        self.assertRaisesRegex(WorkspaceError, f'^{NO_CONTRACT}$'):
                    read(**changes)
            # A saved run opened on the desk keeps the schema it was saved with.
            for schema, extra in ((1, {}), (2, {'review_policy': {'schema': 1,
                                                                  'level': 'balanced'}}),
                                  (3, {'research_contract': CONTRACT})):
                with self.subTest(schema=schema):
                    self.assertEqual(read(schema=schema, **extra)['flow'], 'desk')

    def test_saved_runs_keep_their_gates(self):
        root = self.start()
        record = self.record(root)
        self.assertNotIn('flow', record)
        self.assertEqual(record['schema'], 1)
        self.assertEqual(record['review_policy'], {'schema': 1, 'level': 'step_by_step'})
        self.assertIn('review_layout', record)
        self.assertEqual(workspace.load(root)['review_policy'], record['review_policy'])
        self.to_gate(root, 'research-plan')
        self.assertEqual(self.state(root), 'waiting')
        self.assertEqual(self.view(root)['review_level'], 'step_by_step')
        self.assertFalse(self.record(root).get('review_events'))
        with mock.patch.object(review_policy, 'capture',
                               return_value={'schema': 1, 'level': 'balanced'}):
            balanced = self.start(title='Balanced restarts')
        self.assertEqual(workspace.status(balanced)['gate'], 'research-plan')
        self.assertEqual(self.state(balanced), 'waiting')
        self.assertEqual(self.record(balanced)['schema'], 2)
        self.assertNotIn('flow', self.record(balanced))
