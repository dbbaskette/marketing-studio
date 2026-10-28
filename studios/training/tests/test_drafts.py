"""The training desk in the runner: a desk start, which saves no review level; a desk run,
which the engine carries past every gate with a desk receipt; and holds, which keep what a
desk change reaches until the person updates it or keeps it as it is. Scripted workers, the
stand-in for harness-research and a studios config of the test's own; nothing real is
started. Tests named row_138 to row_141, row_144 to row_149, row_158 and row_161 cover those
rows of the state-transition matrix in
docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md."""
import json  # noqa: I001  the path-setting imports must come before runner
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


def edit(case, root: Path, name: str, change) -> None:
    """Type a change into a material, as the desk saves it, and accept it on the desk (on a
    saved run, approve it on the page)."""
    session = workspace.load(root)
    file = root / workspace.artifact(root, session, name)['file']
    typed = case.base / 'typed' / file.name
    typed.parent.mkdir(exist_ok=True)
    typed.write_text(change(file.read_text(encoding='utf-8')), encoding='utf-8')
    workspace.save(root, name, source=typed, edit=True, via='save')
    if drafts.on_desk(case.record(root)):
        workspace.accept_desk(root, name)
    else:
        workspace.approve(root, name, by='page')


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
        self.assertEqual(self.view(root)['flow'], 'desk', 'the page opens it on the desk')
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
        self.assertIsNone(self.view(root)['flow'], 'a saved run keeps its own screens')
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
        # Everything is written and nothing waits, but nothing is Ready yet: the desk's
        # acceptances never write the index.
        found = self.engine._survey(root, record)
        self.assertEqual(found.next.kind, 'done', 'nothing is left for the run to do')
        self.assertNotIn('package', [step.id for step in found.steps], 'the index is not due')
        self.assertFalse((root / pipeline.INDEX).is_file())
        self.assertNotEqual(workspace.load(root)['stage'], 'done')
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


class DeskHoldTests(DeckCase):
    """What a desk change reaches is held, not remade: it waits until the person presses
    Update, which remakes it, or Keep as it is. A saved run remakes as it always did."""

    def edit(self, root: Path, name: str, change) -> None:
        edit(self, root, name, change)

    def guide_edit(self, root: Path) -> None:
        self.edit(root, 'document@101', lambda text: text + '\nOne line more.\n')

    def drawn_count(self) -> tuple[int, int]:
        return len(self.workers.of('outline')), len(self.workers.of('section'))

    def held(self, root: Path) -> frozenset:
        return drafts.held(root, workspace.load(root), self.record(root))

    def says(self, root: Path, name: str) -> str | None:
        return drafts.hold_says(root, workspace.load(root), self.held(root), name)

    def desk_deck(self) -> Path:
        root = self.begin(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        self.assertIsNone(self.record(root)['problem'], self.view(root))
        self.assertEqual(self.held(root), frozenset())
        return root

    def test_row_144_a_guide_edit_holds_the_deck(self):
        root = self.desk_deck()
        before = self.drawn_count()
        self.guide_edit(root)
        self.assertEqual(self.held(root), {'deck@101'})
        self.engine.wake(root)
        self.assertEqual(self.to_end(root), [])
        self.assertEqual(self.drawn_count(), before, 'a held deck is not drawn again')
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(self.held(root), {'deck@101'})
        listed = {step.id for step in self.engine._survey(root, self.engine._load(root)).steps}
        self.assertFalse({workspace.qualify(step, '101') for step in pipeline.DECK_STEPS}
                         & listed, 'none of its steps is due')
        self.assertEqual(self.says(root, 'deck@101'), 'Built from an earlier guide.')
        self.assertIsNone(self.says(root, 'document@101'))

    def test_a_running_desk_that_needs_the_person_does_not_say_nothing_is_needed(self):
        root = self.desk_deck()
        self.guide_edit(root)
        with mock.patch.object(self.engine, '_state',
                               return_value=('working', 'Writing the practice scenario.')):
            found = drafts.view(self.engine, root)
        self.assertEqual(found['needs'], ['the level 101 slide deck'])
        self.assertTrue(found['progress']['running'])
        self.assertIsInstance(found['progress']['minutes'], int)
        self.assertEqual(found['progress']['line'], '')

    def test_row_145_update_remakes_only_what_was_held(self):
        root = self.desk_deck()
        outlines, sections = self.drawn_count()
        documents = len(self.workers.of('document'))
        self.guide_edit(root)
        self.engine.wake(root)
        with self.assertRaisesRegex(WorkspaceError, '^This is up to date.$'):
            self.engine.update(root, 'document@101')
        self.engine.update(root, 'deck@101')
        self.assertEqual(self.to_end(root), [])
        self.assertIsNone(self.record(root)['problem'], self.view(root))
        self.assertEqual(len(self.workers.of('outline')), outlines + 1,
                         "the deck's steps ran once")
        # What the deck says is written as before, so its drawn sections are kept.
        self.assertEqual(len(self.workers.of('section')), sections)
        self.assertEqual(len(self.workers.of('document')), documents, 'nothing else is made')
        self.assertEqual(self.held(root), frozenset())
        self.assertEqual(self.record(root)['drafts']['updates'], {})
        session = workspace.load(root)
        self.assertEqual(workspace.statuses(root, session)['deck@101'], 'approved')
        self.assertEqual(session['artifacts']['deck@101']['built_from']['document@101'],
                         workspace.sha256_file(root / '101' / 'document.md'))
        self.assertIn('Rolling restarts: update the level 101 slide deck from the guide',
                      self.log())

    def test_an_update_waits_for_the_one_under_way(self):
        root = self.desk_deck()
        self.guide_edit(root)
        record = self.engine._load(root)
        record['drafts']['updates']['brief@101'] = {'at': home.now(), 'by': 'page',
                                                    'scope': None}
        self.engine._store(root, record)
        commits = self.log()
        with self.assertRaisesRegex(WorkspaceError, f'^{drafts.BUSY}$'):
            self.engine.update(root, 'deck@101')
        self.assertEqual(self.log(), commits)
        self.assertEqual(drafts.BUSY, 'A change is already being made to this training. '
                                      'Wait for it, or stop it.')

    def test_row_146_keep_as_it_is_from_the_page(self):
        root = self.desk_deck()
        before = self.drawn_count()
        self.guide_edit(root)
        self.engine.keep(root, 'deck@101')
        self.assertEqual(self.held(root), frozenset())
        self.assertEqual(self.to_end(root), [])
        self.assertEqual(self.drawn_count(), before, 'no deck step runs')
        session = workspace.load(root)
        self.assertEqual(workspace.statuses(root, session)['deck@101'], 'approved')
        decision = session['decisions'][-1]
        self.assertEqual((decision['artifact'], decision['decision'], decision['by']),
                         ('deck@101', 'kept-as-is', 'page'))
        self.assertIn('Rolling restarts: keep the level 101 slide deck as it is', self.log())
        with self.assertRaisesRegex(WorkspaceError, '^This is up to date.$'):
            self.engine.keep(root, 'deck@101')

    def test_a_card_below_a_held_one_waits(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        report = root / '.harness-research' / 'research-report.md'
        report.write_text(report.read_text(encoding='utf-8') + '\nOne finding more.\n',
                          encoding='utf-8')
        held = self.held(root)
        self.assertIn('blueprint@101', held)
        self.assertIn('document@101', held)
        self.assertEqual(self.says(root, 'document@101'),
                         'Waiting for the plan to be updated or kept.')
        commits = self.log()
        for act in (self.engine.keep, self.engine.update):
            with self.subTest(act=act.__name__), self.assertRaisesRegex(
                    WorkspaceError, '^Update or keep the level 101 blueprint first.$'):
                act(root, 'document@101')
        self.assertEqual(self.log(), commits)
        self.assertEqual(self.record(root)['drafts']['updates'], {})
        # Once the plan's update is asked for, the card below waits only for that.
        session = workspace.load(root)
        self.assertEqual(drafts.hold_says(root, session, held - {'blueprint@101'},
                                          'document@101', asked={'blueprint@101': {}}),
                         'Waiting for the plan to be updated.')

    def test_row_158_the_practice_plan_holds_its_scenario(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        plan = (root / '101' / 'blueprint.md').read_text(encoding='utf-8')
        line = next(line for line in plan.splitlines() if line.startswith('- main:'))
        self.edit(root, 'blueprint@101',
                  lambda text: text.replace(line, line + ' Who now asks about cost.'))
        self.assertIn('scenario:main@101', self.held(root))
        self.assertEqual(drafts.input_of(root, workspace.load(root), 'scenario:main@101'),
                         ['practice'])
        self.assertEqual(self.says(root, 'scenario:main@101'), drafts.PRACTICE)
        self.assertEqual(drafts.PRACTICE, 'The plan for this practice changed.')
        scenarios = len(self.workers.of('scenario'))
        self.engine.wake(root)
        self.assertEqual(len(self.workers.of('scenario')), scenarios, 'it is not drafted again')
        self.assertIn('scenario:main@101', self.held(root))

    def test_what_the_studio_does_not_make_again_is_only_kept(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        # The person wrote this scenario: it is taken in as it is, never drafted again.
        record = self.engine._load(root)
        record['drafted'] = [name for name in record.get('drafted') or ()
                             if name != 'scenario:main@101']
        self.engine._store(root, record)
        plan = (root / '101' / 'blueprint.md').read_text(encoding='utf-8')
        line = next(line for line in plan.splitlines() if line.startswith('- main:'))
        self.edit(root, 'blueprint@101',
                  lambda text: text.replace(line, line + ' Who now asks about cost.'))
        self.assertIn('scenario:main@101', self.held(root))
        commits = self.log()
        with self.assertRaisesRegex(
                WorkspaceError, '^The level 101 practice scenario is not made again by the '
                                'studio. Keep it as it is, or change it yourself.$'):
            self.engine.update(root, 'scenario:main@101')
        self.assertEqual(self.log(), commits)
        self.assertFalse(drafts.busy(self.record(root)))
        self.assertEqual(self.record(root)['drafts']['updates'], {})
        self.engine.keep(root, 'scenario:main@101')
        self.assertNotIn('scenario:main@101', self.held(root))
        self.assertIsNone(self.record(root)['problem'])

    def test_an_update_names_no_scope_yet(self):
        root = self.desk_deck()
        self.guide_edit(root)
        with self.assertRaisesRegex(WorkspaceError, f'^{drafts.NO_SCOPE}$'):
            self.engine.update(root, 'deck@101', scope='slides 1-3')
        self.assertEqual(self.record(root)['drafts']['updates'], {})

    def test_saved_runs_still_remake(self):
        root = self.begin(levels=['101'])
        self.drawn(root, '101')
        self.to_end(root)
        self.assertIsNone(workspace.status(root)['gate'])
        outlines = len(self.workers.of('outline'))
        self.guide_edit(root)
        self.assertEqual(drafts.held(root, workspace.load(root), self.record(root)),
                         frozenset())
        self.engine.wake(root)
        self.assertEqual(len(self.workers.of('outline')), outlines + 1,
                         'the deck is put back through its steps, as today')
        for act in (self.engine.update, self.engine.keep):
            with self.subTest(act=act.__name__), self.assertRaisesRegex(
                    WorkspaceError, f'^{drafts.NOT_ON_DESK}$'):
                act(root, 'deck@101')


class DeskReadyTests(DeckCase):
    """Mark ready is the person's approval on the desk, one material or one level at a
    time; the desk's acceptance never is. The index is written only once every material is
    Ready, with no stop."""

    def seen(self, root: Path, name: str) -> str:
        session = workspace.load(root)
        return workspace.sha256_file(root / workspace.artifact(root, session, name)['file'])

    def person(self, root: Path) -> dict:
        return workspace.person_statuses(root, workspace.load(root))

    def drafted(self, root: Path) -> list[str]:
        return [name for name, status in self.person(root).items() if status == 'draft']

    def ready(self, root: Path) -> bool:
        """Whether the core's check says the training is ready, as the index says it."""
        import assess
        return assess.run_checks(root)['ready']

    def desk(self, **changes) -> Path:
        root = self.start(flow='desk', levels=['101'], **changes)
        self.assertEqual(self.to_end(root), [])
        self.assertIsNone(self.record(root)['problem'], self.view(root))
        return root

    def grave(self, root: Path) -> None:
        """Leave a grave finding open in the deck's last review."""
        shows = pipeline.place(root, '101', pipeline.SHOWS)
        kept = json.loads(shows.read_text(encoding='utf-8'))
        kept['findings'] = [*kept['findings'], {
            'slide': 'what-it-does', 'number': 2, 'severity': 'critical', 'about': 'drawing',
            'note': 'The diagram contradicts the guide.', 'fix': None}]
        shows.write_text(json.dumps(kept), encoding='utf-8')

    def test_row_147_mark_ready_is_the_person_s_approval(self):
        root = self.desk()
        name = 'document@101'
        self.assertEqual(self.person(root)[name], 'draft')
        commits = self.log()
        with self.assertRaisesRegex(
                WorkspaceError, '^The level 101 learner guide has changed since it was '
                                r'opened\. Read the new version before deciding\.$'):
            self.engine.mark_ready(root, name, seen='0' * 64)
        # Without the version the person saw, nothing is marked: it is never approved unseen.
        for unseen in (None, '', 42):
            with self.subTest(seen=unseen), self.assertRaisesRegex(
                    WorkspaceError, '^The level 101 learner guide has changed since it was '
                                    r'opened\. Read the new version before deciding\.$'):
                self.engine.mark_ready(root, name, seen=unseen)
        self.assertEqual(self.log(), commits)
        self.assertEqual(self.person(root)[name], 'draft')
        self.engine.mark_ready(root, name, seen=self.seen(root, name))
        self.assertEqual(self.person(root)[name], 'approved')
        self.assertEqual(workspace.load(root)['artifacts'][name]['approved']['by'], 'page')
        self.assertIn('Rolling restarts: mark the level 101 learner guide ready', self.log())
        self.assertEqual(self.git('status', '--porcelain'), '')
        # A change afterwards is a draft again, even once the desk has accepted it.
        edit(self, root, name, lambda text: text + '\nOne line more.\n')
        self.assertEqual(self.person(root)[name], 'draft')

    def test_a_held_material_is_not_marked_ready(self):
        root = self.begin(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        edit(self, root, 'document@101', lambda text: text + '\nOne line more.\n')
        commits = self.log()
        with self.assertRaisesRegex(
                WorkspaceError, '^The level 101 slide deck is built from an earlier guide. '
                                'Update it or keep it as it is first.$'):
            self.engine.mark_ready(root, 'deck@101', seen=self.seen(root, 'deck@101'))
        self.assertEqual(self.log(), commits)
        self.assertNotEqual(self.person(root)['deck@101'], 'approved')
        # A held material is never Ready, so the index waits for it.
        self.assertIs(self.ready(root), False)

    def test_a_held_card_says_what_to_settle_first(self):
        root = self.desk()
        plan = (root / '101' / 'blueprint.md').read_text(encoding='utf-8')
        line = next(line for line in plan.splitlines() if line.startswith('- main:'))
        edit(self, root, 'blueprint@101',
             lambda text: text.replace(line, line + ' Who now asks about cost.'))
        commits = self.log()
        name = 'scenario:main@101'
        with self.assertRaisesRegex(
                WorkspaceError, '^The plan for this practice changed. Update the level 101 '
                                'practice scenario or keep it as it is first.$'):
            self.engine.mark_ready(root, name, seen=self.seen(root, name))
        # A card whose own input is held waits for that input.
        report = root / '.harness-research' / 'research-report.md'
        report.write_text(report.read_text(encoding='utf-8') + '\nOne finding more.\n',
                          encoding='utf-8')
        with self.assertRaisesRegex(
                WorkspaceError, '^Update or keep the level 101 blueprint first.$'):
            self.engine.mark_ready(root, 'document@101', seen=self.seen(root, 'document@101'))
        self.assertEqual(self.log(), commits)

    def test_mark_ready_is_the_desk_s_alone(self):
        root = self.start(levels=['101'])
        with self.assertRaisesRegex(WorkspaceError, f'^{drafts.NOT_ON_DESK}$'):
            self.engine.mark_ready(root, 'intake', seen=self.seen(root, 'intake'))
        with self.assertRaisesRegex(WorkspaceError, f'^{drafts.NOT_ON_DESK}$'):
            self.engine.mark_level_ready(root, '101', {})

    def test_a_level_of_a_levelled_training_must_be_chosen(self):
        root = self.desk()
        commits = self.log()
        with self.assertRaisesRegex(WorkspaceError, '^Choose a level.$'):
            self.engine.mark_level_ready(root, None, {})
        with self.assertRaisesRegex(WorkspaceError, '^This training has no level 999.$'):
            self.engine.mark_level_ready(root, '999', {})
        self.assertEqual(self.log(), commits)

    def test_row_148_a_level_is_marked_ready_in_order(self):
        root = self.begin(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        self.grave(root)
        found = self.engine._survey(root, self.record(root))
        self.assertEqual(drafts.needs_you(root, found, 'deck@101'),
                         ['Critical on what-it-does: The diagram contradicts the guide.'])
        self.assertEqual(drafts.needs_you(root, found, 'brief@101'), [])
        seen = {name: self.seen(root, name) for name in self.drafted(root)}
        commits = len(self.log())
        marked = self.engine.mark_level_ready(root, '101', seen)
        self.assertEqual(marked['marked'], ['blueprint@101', 'document@101', 'brief@101'])
        self.assertEqual(marked['stopped'], {
            'name': 'deck@101',
            'said': 'Settle what needs you on the level 101 slide deck before marking it '
                    'ready.'})
        self.assertEqual(len(self.log()), commits + 1, 'one commit')
        self.assertEqual(self.log()[-1], 'Rolling restarts: mark level 101 ready')
        person = self.person(root)
        self.assertEqual([person[name] for name in marked['marked']], ['approved'] * 3)
        self.assertEqual(person['deck@101'], 'draft')
        self.assertEqual(drafts.ORDER,
                         ('blueprint', 'document', 'brief', 'deck', 'scenario', 'yoodli'))
        with self.assertRaisesRegex(
                WorkspaceError, '^Settle what needs you on the level 101 slide deck before '
                                'marking it ready.$'):
            self.engine.mark_ready(root, 'deck@101', seen=self.seen(root, 'deck@101'))

    def test_a_level_stops_at_a_material_that_changed_since_it_was_opened(self):
        root = self.desk()
        seen = {name: self.seen(root, name) for name in self.drafted(root)}
        seen['document@101'] = '0' * 64
        marked = self.engine.mark_level_ready(root, '101', seen)
        self.assertEqual(marked['marked'], ['blueprint@101'])
        self.assertEqual(marked['stopped']['name'], 'document@101')
        self.assertTrue(marked['stopped']['said'].endswith(
            'has changed since it was opened. Read the new version before deciding.'))
        self.assertEqual(self.person(root)['document@101'], 'draft')

    def test_row_149_the_index_is_written_once_everything_is_ready(self):
        root = self.desk()
        names = self.drafted(root)
        self.assertTrue(names)
        for name in names[:-1]:
            self.engine.mark_ready(root, name, seen=self.seen(root, name))
        self.assertEqual(self.to_end(root), [])
        self.assertFalse((root / pipeline.INDEX).is_file(), 'one material is still a draft')
        self.assertIs(self.ready(root), False)
        self.engine.mark_ready(root, names[-1], seen=self.seen(root, names[-1]))
        self.assertEqual(self.to_end(root), [])
        self.assertTrue((root / pipeline.INDEX).is_file())
        self.assertIsNone(workspace.status(root)['gate'])
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(workspace.load(root)['stage'], 'done')
        self.assertIs(self.ready(root), True)
        self.assertIn('Rolling restarts: write the index; the training is finished',
                      self.log())

    def test_the_desk_s_acceptance_never_lets_the_package_run(self):
        root = self.desk()
        session = workspace.load(root)
        accepted = [name for name, entry in session['artifacts'].items()
                    if (entry.get('approved') or {}).get('by') == 'desk']
        self.assertTrue({'blueprint@101', 'document@101', 'brief@101'} <= set(accepted))
        state = workspace.statuses(root, session)
        self.assertTrue(all(state[name] == 'approved' for name in accepted),
                        'every material is accepted on the desk')
        marked = [name for name in accepted
                  if workspace.split(name)[0].partition(':')[0] in workspace.PERSON_MARKED]
        self.assertTrue(marked)
        self.assertEqual({self.person(root)[name] for name in marked}, {'draft'},
                         'and none is marked ready')
        found = self.engine._survey(root, self.record(root))
        self.assertNotIn('package', found.done)
        self.assertNotIn('package', [step.id for step in found.steps])
        self.assertIs(self.ready(root), False)
        self.assertFalse((root / pipeline.INDEX).is_file())
        self.engine.wake(root)
        self.assertFalse((root / pipeline.INDEX).is_file(), 'waking it writes nothing')

    def test_a_desk_run_never_asks_whether_a_gate_is_held(self):
        root = self.desk()
        name = 'document@101'
        with mock.patch.object(pipeline, 'holding',
                               side_effect=AssertionError('a desk run is never held')):
            self.engine.mark_ready(root, name, seen=self.seen(root, name))
            self.assertIsNotNone(self.record(root).get('last_decision_stop'))
            self.view(root)

    def test_saved_runs_still_write_their_index(self):
        root = self.start(levels=['101'])
        self.to_end(root)
        self.assertTrue((root / pipeline.INDEX).is_file())
        self.assertEqual(self.state(root), 'done')


class DeskTypingTests(DeckCase):
    """Typing on the desk saves one part of a guide, brief or plan into the material's file,
    as an edit, and the edits are committed together: at most once a minute while typing,
    and always before a job, a Mark ready, an Update or a Keep, and when the person leaves
    the desk. A test named row_141 covers that row of the state-transition matrix."""

    NAME = 'document@101'

    def desk(self, **changes) -> Path:
        root = self.begin(flow='desk', levels=['101'], **changes)
        self.assertEqual(self.to_end(root), [])
        self.assertIsNone(self.record(root)['problem'], self.view(root))
        return root

    def part(self, root: Path, heading: str, name: str = NAME) -> tuple[dict, dict]:
        """The card's view as the page reads it, and its part under `heading`."""
        card = self.engine.draft_card(root, name)
        return card, next(section for section in card['sections']
                          if section['heading'] == heading)

    def type(self, root: Path, heading: str, text: str, name: str = NAME,
             session: str | None = 'ab12') -> dict:
        card, section = self.part(root, heading, name)
        return self.engine.draft_save(root, name, section['id'], card['revision'], text,
                                      session)

    def seen(self, root: Path, name: str) -> str:
        return workspace.sha256_file(root / workspace.artifact(
            root, workspace.load(root), name)['file'])

    def text(self, root: Path, name: str = NAME) -> str:
        return (root / workspace.artifact(root, workspace.load(root), name)['file']) \
            .read_text(encoding='utf-8')

    def person(self, root: Path) -> dict:
        return workspace.person_statuses(root, workspace.load(root))

    def held(self, root: Path) -> frozenset:
        return drafts.held(root, workspace.load(root), self.record(root))

    def test_row_141_a_typed_save_keeps_the_inputs_and_holds_what_is_below(self):
        root = self.desk()
        self.engine.mark_ready(root, self.NAME, seen=self.seen(root, self.NAME))
        self.assertEqual(self.person(root)[self.NAME], 'approved')
        self.assertEqual(self.held(root), frozenset())
        built = workspace.load(root)['artifacts'][self.NAME]['built_from']
        card, section = self.part(root, 'Summary')
        self.assertEqual(card['state'], 'ready')
        answer = self.engine.draft_save(root, self.NAME, section['id'], card['revision'],
                                        'Typed on the desk.', 'ab12')
        self.assertIn('\n## Summary\n\nTyped on the desk.\n', self.text(root))
        session = workspace.load(root)
        event = [event for event in session['events'] if event['event'] == 'save'][-1]
        self.assertEqual((event['artifact'], event['via'], event['session']),
                         (self.NAME, 'save', 'ab12'))
        entry = session['artifacts'][self.NAME]
        self.assertEqual(entry['built_from'], built, 'an edit keeps what it was built from')
        # Accepted on the desk again, and no longer what the person marked ready.
        self.assertEqual(entry['approved']['by'], 'desk')
        self.assertEqual(workspace.statuses(root, session)[self.NAME], 'approved')
        self.assertEqual(self.person(root)[self.NAME], 'draft')
        self.assertEqual(self.held(root), {'deck@101'})
        # The answer is the card's new view, with its parts as the save left them.
        self.assertEqual((answer['name'], answer['state'], answer['revision']),
                         (self.NAME, 'draft', card['revision'] + 1))
        self.assertEqual(next(part for part in answer['sections']
                              if part['id'] == section['id'])['text'], 'Typed on the desk.')
        deck = next(one for one in answer['desk']['cards'] if one['name'] == 'deck@101')
        self.assertEqual(deck['state'], 'held')

    def test_typed_saves_are_committed_together(self):
        root = self.desk()
        commits = self.log()
        for words in ('One.', 'One. Two.', 'One. Two. Three.'):
            self.type(root, 'Summary', words)
        self.assertEqual(self.log(), commits, 'nothing is committed while typing')
        self.assertIn(root, self.engine.pending_commit)
        self.assertEqual(self.engine.draft_share(root), {'committed': True})
        edited = 'Rolling restarts: edit the level 101 learner guide on the desk'
        self.assertEqual(self.log(), [*commits, edited])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertNotIn(root, self.engine.pending_commit)
        self.assertEqual(self.engine.draft_share(root), {'committed': False})
        # A Mark ready commits the edits first, in a commit of their own.
        self.type(root, 'Summary', 'Four.')
        commits = self.log()
        self.engine.mark_ready(root, self.NAME, seen=self.seen(root, self.NAME))
        self.assertEqual(self.log()[len(commits):len(commits) + 2],
                         [edited, 'Rolling restarts: mark the level 101 learner guide ready'])
        # So does Keep as it is.
        self.type(root, 'Summary', 'Five.')
        commits = self.log()
        self.engine.keep(root, 'deck@101', 'It still reads right.')
        self.assertEqual(self.log()[len(commits):len(commits) + 2],
                         [edited, 'Rolling restarts: keep the level 101 slide deck as it is'])
        self.assertEqual(self.engine.pending_commit, {})

    def test_typing_is_committed_at_most_once_a_minute(self):
        root = self.desk()
        commits = self.log()
        self.type(root, 'Summary', 'One.')
        self.assertEqual(self.log(), commits)
        self.engine.pending_commit[root]['since'] -= engines.DESK_EVERY
        self.type(root, 'Summary', 'Two.')
        self.assertEqual(self.log(), [
            *commits, 'Rolling restarts: edit the level 101 learner guide on the desk'])
        self.assertNotIn(root, self.engine.pending_commit)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_edits_are_committed_before_a_job(self):
        self.workers.then('brief', fails(), fails(), fails())
        root = self.start(flow='desk', levels=['101'], materials=['document', 'brief'])
        self.assertEqual(self.record(root)['problem']['step'], 'brief@101')
        self.type(root, 'Summary', 'Typed while the brief waits.')
        commits = self.log()
        self.engine.act(root, 'retry')
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(self.log()[len(commits):len(commits) + 2], [
            'Rolling restarts: edit the level 101 learner guide on the desk',
            'Rolling restarts: asked to try again on the page'])
        brief = root / workspace.artifact(root, workspace.load(root), 'brief@101')['file']
        self.assertTrue(brief.is_file(), 'and then the brief was written')
        # Typed while nothing asked for a commit, it is committed before the next job.
        self.type(root, 'Summary', 'Typed before the next job.')
        brief.unlink()   # so the brief is to be written again
        commits = self.log()
        self.engine.wake(root)
        self.assertEqual(self.log()[len(commits)],
                         'Rolling restarts: edit the level 101 learner guide on the desk')
        self.assertTrue(brief.is_file())

    def test_a_locked_part_cannot_be_typed_in(self):
        root = self.desk()
        before, commits = self.text(root), self.log()
        with self.assertRaisesRegex(WorkspaceError, '^Sources is kept from the findings '
                                    r'cited\. Change the references in the text instead\.$'):
            self.type(root, 'Sources', '1. Nothing at all.')
        self.assertEqual((self.text(root), self.engine.pending_commit), (before, {}))
        # Only a guide, a brief or a plan is typed in parts; a stale form is told to reload.
        with self.assertRaisesRegex(WorkspaceError, '^Only a guide, a brief or a plan is '
                                    r'written in parts\.$'):
            self.engine.draft_save(root, 'deck@101', 'opening', 1, 'Typed.', None)
        card, section = self.part(root, 'Summary')
        self.type(root, 'Summary', 'One.')
        with self.assertRaisesRegex(WorkspaceError, '^This draft changed since you opened '
                                    r'it\. Reload to see the latest\.$'):
            self.engine.draft_save(root, self.NAME, section['id'], card['revision'], 'Two.',
                                   'cd34')
        self.assertIn('\n## Summary\n\nOne.\n', self.text(root))
        self.assertEqual(self.log(), commits)
        # A material being made again is not typed in.
        record = self.record(root)
        record.setdefault('drafts', {}).setdefault('updates', {})[self.NAME] = {
            'at': home.now(), 'by': 'page', 'scope': None}
        self.engine._store(root, record)
        with self.assertRaisesRegex(WorkspaceError, '^A change is already being made'):
            self.type(root, 'Summary', 'Three.')

    def test_history_and_restore_on_the_desk(self):
        root = self.desk()
        first = self.part(root, 'Summary')[1]['text']
        self.type(root, 'Summary', 'One.', session='ab12')
        self.type(root, 'Summary', 'Two.', session='cd34')
        card, section = self.part(root, 'Summary')
        found = self.engine.draft_versions(root, self.NAME, section['id'])
        self.assertEqual([(one['source'], one['label'], one['text'])
                          for one in found['versions']],
                         [('save', 'Saved', 'One.'), ('save', 'Saved', first)])
        self.assertEqual(found['sources'], drafts.SOURCE_WORDS)
        self.assertEqual(card['versions'], {section['id']: 2})
        answer = self.engine.draft_restore(root, self.NAME, section['id'], card['revision'], 1)
        self.assertEqual(next(part for part in answer['sections']
                              if part['id'] == section['id'])['text'], first)
        event = [event for event in workspace.load(root)['events']
                 if event['event'] == 'save'][-1]
        self.assertEqual(event['via'], 'restore')
        newest = self.engine.draft_versions(root, self.NAME, section['id'])['versions'][0]
        self.assertEqual((newest['source'], newest['label'], newest['text']),
                         ('restore', 'Restored', 'Two.'))
        with self.assertRaisesRegex(WorkspaceError, '^Choose a saved version.$'):
            self.engine.draft_restore(root, self.NAME, section['id'], answer['revision'], 9)
