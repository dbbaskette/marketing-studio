"""The training desk in the runner: a desk start, which saves no review level, and a desk
run, which the engine carries past every gate with a desk receipt. Scripted workers, the
stand-in for harness-research and a studios config of the test's own; nothing real is
started. Tests named row_138 to row_140 and row_161 cover those rows of the
state-transition matrix in docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md."""
import json
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401
import home
import workspace
from runner_support import FORM, fails
from studio_core import research_contract, review_policy
from test_runner_deck import DeckCase
from workspace import WorkspaceError

from runner import drafts, pipeline
from runner import engine as engines

CONTRACT = {'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}
NO_CONTRACT = 'This run is missing its saved research contract. Restore its run record.'
CONTINUED = 'continued-on-the-desk'


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
        # Automatic draft still stops at a drawn deck and at the finished materials.
        self.brand.offers_looks = True
        with mock.patch.object(review_policy, 'capture',
                               return_value={'schema': 1, 'level': 'automatic'}):
            automatic = self.begin(title='Automatic restarts', levels=['101'])
        self.assertEqual(workspace.status(automatic)['gate'], 'deck@101', self.view(automatic))
        self.assertEqual(self.state(automatic), 'waiting')
        self.decide(automatic, 'deck@101')
        shown = self.view(automatic)
        self.assertEqual((shown['state'], shown['review']['phase']), ('waiting', 'final'))
        self.assertIn('review:final', [step['id'] for step in shown['steps']])
        events = self.record(automatic)['review_events']
        self.assertTrue(events)
        self.assertEqual({event['by'] for event in events}, {'review-policy'})


class DeskRunTests(DeckCase):
    """A desk run never stops for review: the engine continues each gate, outline and look
    with a desk receipt. What goes wrong is still a problem, with its action."""

    def gates(self, root: Path) -> list[str]:
        return [step.id for step in self.engine._survey(root, self.engine._load(root)).steps
                if step.kind == 'gate']

    def continued(self, root: Path) -> dict:
        return {event['gate']: event for event in self.record(root).get('review_events') or ()}

    def test_row_139_a_desk_training_reaches_its_end_with_no_stop(self):
        with mock.patch.object(pipeline, 'holding',
                               side_effect=AssertionError('a desk run is never held')):
            root = self.start(flow='desk', materials=['document', 'brief'])
            self.assertEqual(self.to_end(root), [], 'nothing was put to the person')
        session = workspace.load(root)
        for name in ('research-plan', 'research', 'blueprint', 'document', 'brief'):
            with self.subTest(name=name):
                self.assertTrue((root / workspace.artifact(root, session, name)['file'])
                                .is_file())
                self.assertEqual(session['artifacts'][name]['approved']['by'], 'desk')
        record = self.record(root)
        self.assertIsNone(record['problem'])
        self.assertIsNone(workspace.status(root)['gate'])
        self.assertEqual(self.state(root), 'done')
        gates = self.gates(root)
        self.assertEqual(gates, ['gate:research-plan', 'gate:research', 'gate:blueprint',
                                 'gate:document', 'gate:brief'])
        continued = self.continued(root)
        for gate in gates:
            with self.subTest(gate=gate):
                event = continued[gate]
                self.assertEqual((event['by'], event['decision'], event['level']),
                                 ('desk', CONTINUED, None))
                self.assertTrue(event['evidence'] and event['at'])
        self.assertFalse([step for step in self.engine._survey(root, record).steps
                          if step.id.startswith('review:')])
        self.assertIn('Rolling restarts: continue the blueprint on the desk', self.log())
        # The person has marked nothing ready: each was only continued on the desk.
        person = workspace.person_statuses(root, session)
        self.assertEqual((person['blueprint'], person['document']), ('draft', 'draft'))

    def test_a_desk_deck_is_continued_in_the_default_look(self):
        self.brand.offers_looks = True
        root = self.begin(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        record = self.record(root)
        self.assertIsNone(record['problem'], self.view(root))
        continued = self.continued(root)
        for gate in ('gate:deck-outline@101', 'gate:deck-look@101', 'gate:deck@101'):
            with self.subTest(gate=gate):
                self.assertEqual((continued[gate]['by'], continued[gate]['decision']),
                                 ('desk', CONTINUED))
        name = self.brand.LOOKS[0]['name']
        words = f"You chose the brand's default look at the start: {name}."
        self.assertEqual(continued['gate:deck-look@101']['note'], words)
        kept = record['deck']['101']
        self.assertEqual((kept['look']['chosen']['by'], kept['look']['chosen']['words']),
                         ('desk', words))
        self.assertEqual(kept['approved']['by'], 'desk')
        self.assertEqual(workspace.load(root)['artifacts']['deck@101']['approved']['by'], 'desk')
        self.assertTrue((root / workspace.artifact(root, workspace.load(root),
                                                   'deck@101')['file']).is_file())

    def test_a_desk_run_is_never_grouped_for_review(self):
        root = self.start(flow='desk', materials=['document'])
        record = self.engine._load(root)
        # A finished saved training opened on the desk keeps the level it ran under.
        record['review_policy'] = {'schema': 1, 'level': 'balanced'}
        self.engine._store(root, record)
        listed = self.engine._survey(root, self.engine._load(root)).steps
        self.assertFalse([step.id for step in listed if step.id.startswith('review:')])

    def test_row_161_a_failed_step_on_the_desk_is_a_problem_not_a_gate(self):
        root = self.space.training(workspace.slugify(FORM['title']))
        before = []

        def failing(tools, job):
            before.append(workspace.load(root)['gate'])
            return fails()(tools, job)

        self.workers.then('document', failing, fails(), fails())
        root = self.start(flow='desk', levels=['101'])
        problem = self.record(root)['problem']
        self.assertEqual((problem['step'], problem['action']), ('document@101', 'retry'))
        self.assertEqual(workspace.load(root)['gate'], before[0])
        self.assertEqual(self.state(root), 'failed')
        self.assertEqual(self.continued(root)['gate:blueprint@101']['by'], 'desk')
        self.assertNotIn('gate:document@101', self.continued(root))
        # A step out of time three times offers more time, and is no gate either.
        slow = 'It did not finish in 900 seconds, so it was stopped.'
        self.workers.then('document', *[fails(slow, 'timeout')] * 3)
        other = self.start(flow='desk', title='Slow restarts')
        problem = self.record(other)['problem']
        self.assertEqual((problem['step'], problem['action']), ('document', 'more-time'))
        self.assertIsNone(workspace.load(other)['gate'])
