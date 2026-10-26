"""The engine, from the form to gate 3, with scripted workers and the stand-in for
harness-research. No agent is started and nothing touches the network. What comes after
the blueprints is in test_runner_flow.py.

Most classes drive the engine in the test's own thread, so each step has finished when a
call returns. LiveTests lets it run on threads of its own, as the runner does.
"""
import json
import re
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401
from runner_support import (FORM, FOUR, LEAVES, QUESTIONS, StudioCase, asks, fails,
                            still_running, written)

import home
import workspace
from runner import agents, companion, gitstate, pipeline, research, settings, worker_tools
from runner.agents import Outcome
from runner.engine import ACTIONS
from workspace import WorkspaceError

AVOIDED = re.compile(r'\b(artifacts?|stale|lineage)\b', re.IGNORECASE)
SLOW = 'It did not finish in 900 seconds, so it was stopped.'
STEPS = ['intake', 'research-plan', 'gate:research-plan', 'research-start', 'research',
         'research-report', 'gate:research', 'blueprint', 'gate:blueprint', 'document',
         'gate:document', 'brief', 'gate:brief', 'package']


class Crash(BaseException):
    """The runner's process ending in the middle of something."""


class WhereThisTrainingStopsTests(StudioCase):
    """Where a training stops is chosen on its form. The shared level, in a studios config of
    the test's own, is written only with the chip, and refused when another studio changed it
    since the form read it. Matrix rows 119 and 120."""

    def setUp(self):
        super().setUp()
        self.review_capture.stop()    # the test's own studios config is read for real
        from runner import studios_config
        self.shared = studios_config
        self.shared.update({'review': {'level': 'balanced'}})

    def test_row_119_where_this_training_stops_is_chosen_on_the_form(self):
        root = self.start(review_level='automatic', review_seen='balanced')
        self.assertEqual(self.engine._load(root)['review_policy'],
                         {'schema': 1, 'level': 'automatic'})
        self.assertEqual(self.shared.read()[0]['review'], {'level': 'balanced'})

    def test_row_119_a_per_training_choice_survives_a_new_shared_default(self):
        self.shared.update({'review': {'level': 'step_by_step'}})
        root = self.start(review_level='automatic', review_seen='balanced',
                          review_default=False)
        self.assertEqual(self.engine._load(root)['review_policy']['level'], 'automatic')
        self.assertEqual(self.shared.read()[0]['review'], {'level': 'step_by_step'})

    def test_row_120_a_start_refused_after_the_chip_wrote_can_be_tried_again(self):
        self.start(title='Taken title', review_level='step_by_step', review_seen='balanced')
        self.shared.update({'review': {'level': 'balanced'}})
        with self.assertRaises(WorkspaceError):
            self.start(title='Taken title', review_level='automatic', review_seen='balanced',
                       review_default=True)
        self.assertEqual(self.shared.read()[0]['review'], {'level': 'automatic'})
        # The same form, its title put right: with the chip, or without it.
        root = self.start(title='Free title', review_level='automatic', review_seen='balanced',
                          review_default=True)
        self.assertEqual(self.engine._load(root)['review_policy']['level'], 'automatic')
        root = self.start(title='Another free title', review_level='automatic',
                          review_seen='balanced')
        self.assertEqual(self.engine._load(root)['review_policy']['level'], 'automatic')

    def test_row_120_the_shared_default_is_written_only_with_the_chip(self):
        from studio_core import review_policy
        self.start(title='Second training', review_level='automatic', review_seen='balanced',
                   review_default=True)
        self.assertEqual(self.shared.read()[0]['review'], {'level': 'automatic'})
        self.shared.update({'review': {'level': 'step_by_step'}})
        before = sorted(self.space.repo.iterdir())
        with self.assertRaises(WorkspaceError) as caught:
            self.start(title='Stale training', review_level='balanced',
                       review_seen='automatic', review_default=True)
        self.assertEqual(str(caught.exception), review_policy.STALE)
        self.assertEqual(sorted(self.space.repo.iterdir()), before, 'nothing is made')
        self.assertEqual(self.shared.read()[0]['review'], {'level': 'step_by_step'})
        with self.assertRaisesRegex(WorkspaceError, 'true or false'):
            pipeline.check_form({**FORM, 'review_default': 'yes'})


class SynthesisAtStartTests(StudioCase):
    """A training is not started on a Harness Research that cannot synthesize: the start is
    refused with nothing made. A training brought in from a conversation is not a start, and
    is not refused. Matrix row 137."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(self.engines, 'LEGACY_RESEARCH', False)
        patch.start()
        self.addCleanup(patch.stop)

    def made(self):
        """What a start could leave behind: the trainings driven and remembered, the
        workspace's folders and commits, and the shared studios config's bytes."""
        config = self.base / 'studios.json'
        return (self.engine.trainings(), [entry['path'] for entry in home.trainings()],
                sorted(path.name for path in self.space.root.iterdir()), self.log(),
                config.read_bytes() if config.exists() else None)

    def test_row_137_a_training_is_not_started_without_synthesis(self):
        before = self.made()
        with self.assertRaises(WorkspaceError) as caught:
            self.start(review_level='automatic', review_seen='automatic', review_default=True)
        self.assertEqual(str(caught.exception), self.engines.NO_SYNTHESIS)
        self.assertEqual(self.made(), before, 'nothing is made')
        # A read error is refused the same way, with a real-looking Harness Research found.
        from stand_ins import research as research_stand_in
        from studio_core import research_contract
        runtime = self.base / 'harness-research'
        (runtime / 'scripts' / 'lib').mkdir(parents=True)
        (runtime / 'package.json').write_text('{"version": "1.0.0"}\n', encoding='utf-8')
        (runtime / 'scripts' / 'lib' / 'synthesis-cli.mjs').write_text('', encoding='utf-8')
        self.research = research.Research(runtime=runtime, run=research_stand_in.StandIn())
        with mock.patch.object(research_contract, 'snapshot', return_value=None), \
                self.assertRaises(WorkspaceError) as caught:
            self.start()
        self.assertEqual(str(caught.exception), self.engines.NO_SYNTHESIS)
        self.assertEqual(self.made(), before, 'nothing is made')

    def test_a_conversation_training_brought_in_is_not_refused(self):
        chat = self.base / 'started-in-a-chat'
        chat.mkdir()
        workspace.init(chat, 'Started in a chat')
        workspace.write_atomic(chat / 'intake.md', pipeline.intake_text(
            pipeline.check_form({**FORM, 'title': 'Started in a chat'})).encode())
        workspace.save(chat, 'intake', built=True)
        workspace.approve(chat, 'intake')
        self.assertNotIn('research_contract', workspace.load(chat))
        made = self.engine.bring(chat)
        self.assertNotIn('research_contract', self.engine._load(Path(made['path'])))


class SavedWorkTests(StudioCase):
    """`studio saved-work`: which saved trainings still need each older path. Each run is
    begun on the legacy queue, as a saved one was, and its record set as the case needs."""

    QUEUE = 'Its research has not run, and it was started before Harness Research could synthesize.'
    CHAT = 'A conversation training whose research has not started.'
    LAYOUT = 'It began before the current review layout, and its final review is still to come.'

    def needed(self, said, ident):
        return {entry['path']: entry['why'] for entry in
                next(found for found in said['paths'] if found['id'] == ident)['needed_by']}

    def saved(self, title, **changes):
        """A training started from the form, its run record then changed as `changes` says:
        a value of None takes the key out."""
        return self.changed(self.start(title=title), **changes)

    def changed(self, root, **changes):
        record = self.engine._load(root)
        for key, value in changes.items():
            if value is None:
                record.pop(key, None)
            else:
                record[key] = value
        self.engine._store(root, record)
        return root

    def chat(self, title='Started in a chat'):
        root = self.base / workspace.slugify(title)
        root.mkdir()
        workspace.init(root, title)
        home.remember(root, title, [])
        return root

    def done(self, *steps):
        """The engine's survey, with `steps` done as well."""
        survey = self.engine._survey
        return mock.patch.object(self.engine, '_survey', lambda root, record, copies=None: replace(
            survey(root, record, copies), done=survey(root, record, copies).done | set(steps)))

    def test_a_run_begun_on_the_queue_needs_it_until_its_research_has_run(self):
        waiting = self.saved('Waiting training')
        said = self.engine.saved_work()
        self.assertEqual(self.needed(said, 'research-queue'), {str(waiting): self.QUEUE})
        self.assertEqual(said['paths'][0]['needed_by'][0]['title'], 'Waiting training')
        with self.done('research'):
            self.assertEqual(self.needed(self.engine.saved_work(), 'research-queue'), {})
        # A training folder given outside the workspace is looked at too.
        import shutil
        outside = self.base / 'elsewhere' / 'waiting-training'
        shutil.copytree(waiting, outside)
        self.assertEqual(self.needed(self.engine.saved_work(folders=(outside,)),
                                     'research-queue'),
                         {str(waiting): self.QUEUE, str(outside): self.QUEUE})
        self.changed(waiting, research_contract={'schema': 2, 'version': '1.0.0',
                                                 'digest': 'abc'}, schema=3)
        self.assertEqual(self.needed(self.engine.saved_work(), 'research-queue'), {})

    def test_a_conversation_training_whose_research_has_not_started_needs_it(self):
        chat = self.chat()
        said = self.engine.saved_work()
        self.assertEqual(self.needed(said, 'research-queue'), {str(chat): self.CHAT})
        session = workspace.load(chat)
        session['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        workspace.store(chat, session)
        self.assertEqual(self.needed(self.engine.saved_work(), 'research-queue'), {})

    def test_a_balanced_run_with_no_layout_needs_layout_1_until_its_final_review(self):
        balanced = {'schema': 1, 'level': 'balanced'}
        older = self.saved('Older layout', review_layout=None, review_policy=balanced,
                           schema=2)
        self.saved('Current layout', review_policy=balanced, schema=2)
        self.saved('Step by step', review_layout=None)
        said = self.engine.saved_work()
        self.assertEqual(self.needed(said, 'review-layout-1'), {str(older): self.LAYOUT})
        with self.done('review:final'):
            self.assertEqual(self.needed(self.engine.saved_work(), 'review-layout-1'), {})

    def test_the_old_slides_branches_are_always_unused_and_nothing_changes(self):
        self.saved('Waiting training')
        chat = self.chat()
        outside = self.base / 'elsewhere'
        before = (self.git('status', '--porcelain'),
                  {path: path.read_bytes() for path in sorted(self.base.rglob('*'))
                   if path.is_file() and '.git' not in path.parts})
        said = self.engine.saved_work(folders=(chat, outside))
        self.assertEqual([entry['id'] for entry in said['paths']],
                         ['research-queue', 'review-layout-1', 'old-harness-slides'])
        self.assertEqual(said['unused'], ['review-layout-1', 'old-harness-slides'])
        self.assertEqual((self.git('status', '--porcelain'),
                          {path: path.read_bytes() for path in sorted(self.base.rglob('*'))
                           if path.is_file() and '.git' not in path.parts}), before)


class ObjectionsTests(StudioCase):
    def test_read_every_objection_is_offered_only_where_the_check_objected(self):
        root = self.start()
        (root / 'reviews').mkdir(exist_ok=True)
        (root / 'reviews' / 'research.md').write_text('## Your request\n\nAdd a source.\n')
        record = self.engine._load(root)
        record['problem'] = {'step': 'research', 'state': 'failed', 'what': 'It timed out.',
                             'kept': 'Kept.', 'action': 'retry', 'label': 'Try again'}
        self.engine._store(root, record)
        self.assertNotIn('objections', self.view(root)['problem'])
        record['problem']['objected'] = True
        self.engine._store(root, record)
        self.assertEqual(self.view(root)['problem']['objections'], 'reviews/research.md')


class NoCostYetTests(StudioCase):
    def test_a_training_that_ran_only_its_own_steps_reports_no_cost_yet(self):
        root = self.start()
        record = self.engine._load(root)
        record['steps'] = {'intake': {'attempts': [{'seconds': 0.5, 'dollars': None}]}}
        self.engine._store(root, record)
        ahead = self.view(root)['ahead']
        self.assertIsNone(ahead['dollars'])
        self.assertNotIn('$', ahead['spent'])


class LaterDocumentTests(StudioCase):
    def test_the_research_update_is_priced_before_it_is_sent(self):
        root = self.start(source_scope='supplied-only')
        self.engine.supply(root, 'add', 'handbook.txt', b'Capacity holds with two.\n')
        self.engine.supply(root, 'done')
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        self.engine._store(root, record)
        self.assertNotIn('update_price', self.engine.view(root)['documents'])
        shown = self.engine.supply(root, 'add', 'more.txt', b'More.\n')['documents']
        self.assertTrue(shown['update_price']['words'].startswith(
            'Asking for changes runs the research again'), shown['update_price'])


class AheadTests(StudioCase):
    """Each training's view says how many steps are left, where it next stops for the person
    under its own level, and what its agent's jobs have spent so far."""

    def test_runner_only_steps_do_not_claim_a_reported_zero_cost(self):
        root = self.start()
        record = self.engine._load(root)
        found = self.engine._survey(root, record)
        kinds = {step.id: step.kind for step in found.steps}
        record['steps'] = {name: entry for name, entry in record['steps'].items()
                           if kinds.get(name) == 'code'}
        self.assertTrue(record['steps'])
        ahead = self.engine._still_to_come(record, found)
        self.assertIsNone(ahead['dollars'])
        self.assertIn('the assistant reported no cost', ahead['spent'])

    def test_the_view_says_steps_left_the_next_stop_and_spent(self):
        root = self.start()
        shown = self.view(root)
        ahead = shown['ahead']
        left = [step for step in shown['steps'] if step['status'] != 'done']
        self.assertEqual(ahead['steps_left'], len(left))
        self.assertEqual(ahead['next_gate'], 'gate:research-plan')
        self.assertEqual(ahead['next_stop'], next(step['label'] for step in left
                                                   if step['id'] == 'gate:research-plan'))
        # The scripted agents report no cost: the line says so, never $0.00.
        self.assertIsNone(ahead['dollars'])
        self.assertTrue(ahead['spent'].endswith('; the assistant reported no cost'),
                        ahead['spent'])
        record = self.engine._load(root)
        kinds = {step['id']: step['kind'] for step in shown['steps']}
        priced = 0
        for name, entry in record['steps'].items():
            if kinds.get(name, kinds.get(name.partition(':')[0], 'agent')) == 'agent':
                for attempt in entry.get('attempts', []):
                    attempt['dollars'] = 0.25
                    priced += 1
        self.assertGreater(priced, 0)
        self.engine._store(root, record)
        self.assertEqual(self.view(root)['ahead']['dollars'], round(0.25 * priced, 2))
        # Balanced reads the research plan too; Automatic draft goes on past it.
        from unittest import mock
        with mock.patch('studio_core.review_policy.capture',
                        return_value={'schema': 1, 'level': 'automatic'}):
            fast = self.start(title='Fast training')
        self.assertNotEqual(self.view(fast)['ahead']['next_gate'], 'gate:research-plan')


class RedoTests(StudioCase):
    """Ask for changes says, before it is sent, what it writes again and what that took."""

    def test_a_change_request_says_what_it_writes_again(self):
        root = self.start()
        self.to_gate(root, 'blueprint')
        redo = self.engine.redo(str(root), 'blueprint')
        self.assertEqual(redo['names'][0], 'the blueprint')
        self.assertGreater(redo['steps'], 1, 'what is written from the blueprint comes again')
        # Nothing after the blueprint has run yet: there is no record of what it all costs.
        # What is counted is what is written from the blueprint, and the words say so.
        self.assertTrue(redo['says'].startswith('Drawn again: the blueprint and what is '
                                                f"written from it, {redo['steps']} steps; "
                                                'this computer has no record'), redo['says'])
        # The research stops keep their own words: Phase 3 prices them.
        self.assertIsNone(self.engine.redo(str(root), 'research'))
        self.assertIsNone(self.engine.redo(str(root), 'research-plan'))
        # The blueprint alone, once run: what its last try took, priced as reported.
        record = self.engine._load(root)
        record['steps']['blueprint']['attempts'][-1].update(seconds=120, dollars=0.3)
        self.engine._store(root, record)
        alone = self.engine._redo_steps(record, ['blueprint'])
        self.assertEqual(alone, (120.0, 0.3))

    def test_each_item_of_a_combined_review_says_what_it_writes_again(self):
        from unittest import mock
        with mock.patch('studio_core.review_policy.capture',
                        return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start()
        review = self.view(root)['review']
        self.assertEqual(review['phase'], 'final')
        items = {item['target']: item for item in review['items']}
        said = items['blueprint']['redo']['says']
        # Everything written from the blueprint has run once here, its agent reporting no cost.
        self.assertTrue(said.startswith('Drawn again: the blueprint and what is written from '
                                        'it, '), said)
        self.assertTrue(said.endswith('; the assistant reported no cost.'), said)
        self.assertIsNone(items.get('research', {}).get('redo'))


class FormToGateThreeTests(StudioCase):
    def test_the_form_becomes_a_training_made_through_the_core_in_page_mode(self):
        root = self.start()
        self.assertEqual(root, self.space.training('rolling-restarts'))
        status = workspace.status(root)
        self.assertEqual((status['approval'], status['artifacts']['intake'], status['title']),
                         ('page', 'approved', 'Rolling restarts'))
        session = workspace.load(root)
        self.assertEqual(session['artifacts']['intake']['approved']['by'], 'page')
        self.assertEqual((root / 'intake.md').read_text(), (
            '## Topic\n\nRolling restarts on the platform\n\n## Levels\n\nNone\n\n'
            '## Brief\n\nproduct\n\n## Audience\n\nSolutions engineers who deploy apps\n\n'
            '## Purpose\n\nField enablement\n\n## Source scope\n\nPublic web\n\n'
            '## Time limit\n\n25 minutes\n'))
        with self.assertRaisesRegex(WorkspaceError, 'decided on the page'):
            workspace.approve(root, 'research-plan')

    def test_it_stops_at_each_gate_and_a_decision_wakes_it(self):
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence'], view['agent'], view['model']),
                         ('waiting', 'The research plan is waiting for your review.',
                          'claude', None))
        self.assertEqual([step['id'] for step in view['steps']], STEPS)
        self.assertEqual({step['id']: step['status'] for step in view['steps']}, {
            **dict.fromkeys(STEPS, 'to-do'), 'intake': 'done', 'research-plan': 'done',
            'gate:research-plan': 'waiting'})
        self.assertEqual((view['workers'], view['question'], view['problem']),
                         ([], None, None))
        status = workspace.status(root)
        self.assertEqual((status['gate'], status['pending_question'], status['stage']),
                         ('research-plan', 'Approve the research plan?', 'research-plan'))
        self.assertEqual(len(self.workers.jobs), 1)

        said = self.decide(root, 'research-plan')
        self.assertEqual(said['said'],
                         'Approved. The research report is waiting for your review.')
        self.assertEqual(said['next']['artifact'], 'research')
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'research'))
        self.assertEqual(self.view(root)['sentence'],
                         'The research report is waiting for your review.')
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 3, 'contradicted': 1})
        self.assertEqual(len(self.workers.of('question')), 4)

        self.decide(root, 'research')
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'blueprint'))
        self.assertEqual(len(self.workers.jobs), 6)

        said = self.decide(root, 'blueprint')
        self.assertEqual(said['said'], 'Approved. The learner guide is waiting for your review.')
        view, status = self.view(root), workspace.status(root)
        self.assertEqual((view['state'], status['stage'], status['gate']),
                         ('waiting', 'document', 'document'))
        self.assertEqual({status['artifacts'][name] for name in
                          ('intake', 'research-plan', 'research', 'blueprint')}, {'approved'})
        self.assertEqual([step['id'] for step in view['steps']],
                         STEPS[:-1] + ['scenario:main', 'gate:scenario:main', 'package'],
                         'the blueprint has named a practice scenario')
        self.assertEqual(len(self.workers.jobs), 7)

    def test_every_kept_step_and_every_decision_is_a_commit_that_says_what_happened(self):
        (self.space.repo / 'README.md').write_text('# Another tool keeps this\n')
        (self.space.repo / 'notes.txt').write_text('Staged by someone else.\n')
        self.git('add', 'notes.txt')
        self.engine = self.make(at_once=1)
        root = self.start()
        self.to_end(root)
        self.assertEqual(self.log(), ['Set up the Training Studio workspace in trainings/'] + [
            f'Rolling restarts: {what}' for what in (
                'start the training from the form',
                'keep the research plan',
                'ask for a review of the research plan',
                'The research plan was approved on the page.',
                'hand the approved questions to research',
                'keep the finding for availability',
                'keep the finding for instance-min',
                'keep the finding for health-checks',
                'keep the finding for zero-downtime',
                'keep the research report',
                'ask for a review of the research report',
                'The research report was approved on the page.',
                'keep the blueprint',
                'ask for a review of the blueprint',
                'The blueprint was approved on the page.',
                'keep the learner guide',
                'ask for a review of the learner guide',
                'The learner guide was approved on the page.',
                'keep the brief',
                'ask for a review of the brief',
                'The brief was approved on the page.',
                'keep the practice scenario',
                'ask for a review of the practice scenario',
                'The practice scenario was approved on the page.',
                'write the index; the training is finished')])
        self.assertEqual(self.git('status', '--porcelain'), 'A  notes.txt\n?? README.md'.strip())
        changed = self.git('log', '--format=', '--name-only').split()
        self.assertTrue(changed)
        self.assertEqual({name.split('/')[0] for name in changed}, {'trainings'})
        self.assertNotIn('sources', {part for name in changed for part in name.split('/')})
        self.assertTrue(list((root / 'sources').glob('docs-example-com-*.txt')))
        self.assertEqual(self.git('log', '-1', '--format=%an <%ae>'),
                         'Alex <alex@example.com>')

    def test_with_levels_every_blueprint_is_drafted_and_each_is_reviewed_in_turn(self):
        made = self.engine.start(pipeline.check_form({**FORM, 'levels': ['301', '101']}))
        root = Path(made['path'])
        self.assertEqual(made, {'path': str(root), 'id': 'rolling-restarts', 'gates': 8})
        self.assertEqual([step['id'] for step in self.view(root)['steps']][7:11],
                         ['blueprint@101', 'blueprint@301', 'gate:blueprint@101',
                          'gate:blueprint@301'])
        self.to_gate(root, 'blueprint@101')
        self.assertEqual([spec['artifacts']['blueprint']['level']
                          for _, _, spec in self.workers.jobs[-2:]], ['101', '301'])
        self.assertIn('This blueprint is for level 301.', self.workers.jobs[-1][1].task)
        self.assertIn('## This blueprint is for level 301', self.workers.jobs[-1][1].guidance)
        self.assertEqual(self.view(root)['sentence'],
                         'The level 101 blueprint is waiting for your review.')
        self.decide(root, 'blueprint@101')
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'blueprint@301'))
        self.decide(root, 'blueprint@301')
        self.assertEqual((self.state(root), self.view(root)['sentence']), (
            'waiting', 'The level 101 learner guide is waiting for your review.'))
        self.assertIn('Level: 301', (root / '301' / 'blueprint.md').read_text())

    def test_the_run_record_holds_what_the_files_cannot_say_and_is_committed(self):
        settings.save(replace(settings.load(), model='a-model', effort='high',
                              step_seconds=300))
        self.workers.cost = 0.25
        root = self.start()
        record = self.record(root)
        self.assertEqual((record['agent'], record['model'], record['effort'],
                          record['limits']),
                         ('claude', 'a-model', 'high',
                          {'step_seconds': 300, 'training_dollars': 20.0}))
        self.assertEqual({(job.model, job.effort) for _, job, _ in self.workers.jobs},
                         {('a-model', 'high')})
        attempt = record['steps']['research-plan']['attempts'][0]
        self.assertEqual((attempt['outcome'], attempt['error'], attempt['dollars'],
                          attempt['tokens'], attempt['seconds']),
                         ('kept', None, 0.25, 1200, 1.5))
        self.assertRegex(attempt['started_at'] + attempt['ended_at'],
                         r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ){2}$')
        committed = self.git('show', 'HEAD:trainings/rolling-restarts/.training-studio/run.json')
        self.assertEqual(json.loads(committed), record)
        view = self.view(root)
        self.assertEqual((view['spent'], view['model'], view['effort']),
                         ({'dollars': 0.25, 'tokens': 1200, 'stops_at': 20.0}, 'a-model', 'high'))
        step = self.steps(root)['research-plan']
        self.assertEqual((step['attempts'], step['seconds'], step['dollars'], step['kind'],
                          step['label']), (1, 1.5, 0.25, 'agent', 'Draft the research plan'))
        self.assertEqual((self.steps(root)['gate:research-plan']['kind'],
                          self.steps(root)['intake']['kind']), ('gate', 'code'))

    def test_the_agent_is_chosen_when_the_training_starts_and_does_not_change(self):
        other = type(self.workers)()
        self.engine.adapters['codex'] = agents.Scripted(other)
        root = self.start(agent='codex', model='their-model', effort='ultra')
        self.assertEqual((self.view(root)['agent'], self.view(root)['model'],
                          self.view(root)['effort']), ('codex', 'their-model', 'ultra'))
        settings.save(replace(settings.load(), agent='claude', model='another',
                              effort='low'))
        self.to_gate(root, 'blueprint')
        self.assertEqual((len(other.jobs), len(self.workers.jobs)), (6, 0))
        self.assertEqual({(job.model, job.effort) for _, job, _ in other.jobs},
                         {('their-model', 'ultra')})
        self.assertEqual(self.view(root)['agent'], 'codex')

    def test_a_form_that_names_its_agent_is_taken_as_it_is(self):
        # The page always names the agent, so "The agent's own choice" means just that,
        # whatever the settings say. A form that names no agent takes the settings' own.
        settings.save(replace(settings.load(), model='a-model', effort='high'))
        own = self.start(agent='claude')
        chosen = self.start(title='Health checks', agent='claude', effort='max')
        either = self.start(title='Probes')
        self.assertEqual([(self.record(root)['model'], self.record(root)['effort'])
                          for root in (own, chosen, either)],
                         [(None, None), (None, 'max'), ('a-model', 'high')])

    def test_a_level_the_agent_does_not_take_starts_nothing(self):
        with self.assertRaisesRegex(WorkspaceError, 'The reasoning level is one of: low, '
                                    'medium, high, xhigh, max,'):
            self.start(effort='ultra')
        self.assertFalse(self.space.training('rolling-restarts').exists())

    def test_a_level_the_model_does_not_take_starts_nothing(self):
        for model, effort, said in (
                ('claude-haiku-4-5', 'high', 'Haiku 4.5 takes no reasoning level'),
                ('claude-opus-4-6', 'xhigh', 'Opus 4.6 takes one of these reasoning levels')):
            with self.subTest(model=model), self.assertRaisesRegex(WorkspaceError, said):
                self.start(agent='claude', model=model, effort=effort)
        # Nor does one the settings hold for a form that names no agent.
        settings.save(replace(settings.load(), model='claude-haiku-4-5', effort=None))
        with self.assertRaisesRegex(WorkspaceError, 'Haiku 4.5 takes no reasoning level'):
            self.start(effort='low')
        self.assertFalse(self.space.training('rolling-restarts').exists())
        self.assertEqual(self.workers.jobs, [])

    def test_an_agent_that_is_not_ready_starts_nothing(self):
        away = agents.Readiness('claude', True, True, False, '2.1', 'Claude Code is signed '
                                'in but cannot be used from this network. Try another.')
        with mock.patch.object(self.adapters['claude'], 'ready', return_value=away):
            with self.assertRaisesRegex(WorkspaceError, 'cannot be used from this network'):
                self.start()
        self.assertEqual((self.engine.trainings(), self.workers.jobs), ([], []))
        self.assertFalse(self.space.training('rolling-restarts').exists())

    def test_a_title_already_in_the_workspace_is_refused(self):
        self.start()
        with self.assertRaisesRegex(WorkspaceError, 'already has a training in trainings/'
                                    'rolling-restarts. Give this one a different title'):
            self.start(topic='Something else')
        self.assertEqual(len(self.engine.trainings()), 1)

    def test_without_a_workspace_nothing_starts(self):
        gitstate.settings_path().unlink()
        with self.assertRaisesRegex(WorkspaceError, 'No workspace is set up on this computer'):
            self.start()

    def test_nothing_a_person_reads_uses_the_words_the_page_avoids(self):
        self.workers.then('research-plan', asks('Which platform is this about?'))
        self.workers.then('question:health-checks', fails(SLOW, 'timeout'), fails(SLOW),
                          fails(SLOW))
        self.workers.then('blueprint', fails(), fails(), fails())
        root, said = self.start(), []

        def note() -> None:
            view = self.view(root)
            said.extend([view['sentence'], *(step['label'] for step in view['steps']),
                         *(step['error'] or '' for step in view['steps']),
                         *(view['question'] or {}).values(),
                         *((view['problem'] or {}).values())])

        note()
        self.engine.answer(root, self.view(root)['question']['id'], 'The public platform.')
        note()
        self.decide(root, 'research-plan')
        note()
        said.append(self.decide(root, 'research')['said'])
        note()
        self.assertEqual(self.state(root), 'failed')
        said += [(root / 'reviews' / f'{name}.md').read_text()
                 for name in ('research-plan', 'research')]
        said += self.log()
        for text in said:
            self.assertIsNone(AVOIDED.search(str(text or '')), text)


class WorkerTests(StudioCase):
    """What a worker is given, and that it is given nothing else."""

    def test_a_worker_has_only_the_worker_tools_and_a_folder_outside_the_workspace(self):
        seen = []

        def looking(act):
            def script(tools, job):
                seen.append((job.folder, sorted(path.name for path in job.folder.iterdir())))
                return act(tools, job)
            return script

        self.workers.then('research-plan', looking(self.workers.research_plan))
        self.workers.then('question', *[looking(self.workers.question)] * 4)
        self.workers.then('blueprint', looking(self.workers.blueprint))
        root = self.start()
        self.to_gate(root, 'blueprint')
        profiles = {kind.partition(':')[0]: (job.profile, spec['fetch'], spec['ask'])
                    for kind, job, spec in self.workers.jobs}
        self.assertEqual(profiles, {'research-plan': ('write', False, True),
                                    'question': ('research', True, False),
                                    'blueprint': ('write', False, True)})
        for kind, job, spec in self.workers.jobs:
            self.assertEqual(list(job.tools), worker_tools.command(job.folder))
            self.assertEqual(job.folder.parent, agents.staging())
            self.assertNotIn(self.space.repo, job.folder.parents)
            self.assertEqual((job.limits.seconds, job.limits.dollars), (900, 20.0))
        for folder, held in seen:
            self.assertIn(held, (['inputs', 'job.json', 'sources'], ['job.json', 'sources']))
            self.assertFalse(folder.exists(), 'a job folder is removed once its work is kept')
        self.assertEqual(len({folder for folder, _ in seen}), 6)

    def test_what_a_worker_is_told_says_what_the_training_is_about(self):
        root = self.start()
        self.to_gate(root, 'blueprint')
        plan, question, blueprint = (self.workers.of(kind)[0] for kind in
                                     ('research-plan', 'question:instance-min', 'blueprint'))
        for job in (plan, question, blueprint):
            self.assertIn('Topic: Rolling restarts on the platform', job.task)
            self.assertIn('Audience: Solutions engineers who deploy apps', job.task)
            self.assertIn('Purpose: Field enablement', job.task)
        self.assertEqual(plan.guidance, pipeline.briefs.guidance('research-plan-queue'))
        self.assertIn('Hand the questions back with submit_artifact under the name '
                      '"research-plan".', plan.task)
        self.assertIn('Sources that may be used: the public web.', plan.task)
        self.assertEqual(question.guidance, pipeline.briefs.guidance('research-question'))
        self.assertIn('Question ID: instance-min\nQuestion: How many instances keep capacity '
                      'during a restart?\nSearch words to start from: rolling restart '
                      'instance-min', question.task)
        self.assertEqual(blueprint.guidance, pipeline.briefs.guidance('blueprint'))
        self.assertIn('Your inputs are "intake" and "research findings".', blueprint.task)
        self.assertIn('Practice scenarios are wanted: plan them.', blueprint.task)
        spec = self.workers.jobs[-1][2]
        self.assertEqual([entry['name'] for entry in spec['inputs']],
                         ['intake', 'research findings'])
        self.assertEqual(spec['artifacts']['blueprint']['findings'], {
            'availability': 'supported', 'instance-min': 'supported',
            'health-checks': 'supported', 'zero-downtime': 'contradicted'})
        findings = pipeline.findings_text(root)
        self.assertIn('## instance-min\n\nQuestion: How many instances keep capacity during a '
                      'restart?\nVerdict: supported\nSummary: What the page says about '
                      'instance-min.\nLimits: none\nQuoted from Rolling restarts '
                      '(https://docs.example.com/restarts): "Capacity holds only when more '
                      'than one instance is running."', findings)

    def test_findings_text_leads_with_the_handoff(self):
        from studio_core import research_contract
        from synthesis_fixture import research_stop
        root = self.start()
        research_stop(root / 'research')
        record = {'schema': 2, 'digest': 'synthetic-digest', 'findings': [], 'facts': [],
                  'sources': []}
        with mock.patch.object(pipeline.workspace, 'research_record', return_value=record):
            text = pipeline.findings_text(root)
        self.assertTrue(text.startswith('# Reviewed research handoff\n\n'
                                        + research_contract.HANDOFF), text[:200])
        self.assertNotIn('Cite stable finding IDs', text)
        self.assertIn('# Prioritized handoff', text)

    def test_the_review_at_a_gate_carries_the_checks_and_the_workers_own_notes(self):
        root = self.start()
        review = (root / 'reviews' / 'research-plan.md').read_text()
        self.assertRegex(review, r'## Ready for your review, \d{4}-')
        self.assertIn('> Checked for you: 1 check passed.', review)
        self.assertIn("> The worker's own notes on its draft. They are its judgment, not a "
                      'check:\n>\n> Four questions. I left rollback out: it is a topic of its '
                      'own.', review)
        self.to_gate(root, 'blueprint')
        self.assertIn('> 3 of 4 questions have an answer the sources support.\n> 1 more state '
                      'a claim that the sources contradict.\n> Every question was researched '
                      'and settled.', (root / 'reviews' / 'research.md').read_text())
        blueprint = (root / 'reviews' / 'blueprint.md').read_text()
        self.assertIn('> Checked for you: 4 checks passed.', blueprint)
        # Approving a blueprint commits the person to a decision on each scenario it plans.
        self.assertIn('> It plans 1 practice scenario: main. Each comes to you for review: 1 '
                      'more decision for this blueprint. To have fewer, ask for changes here.',
                      blueprint)


class RetryTests(StudioCase):
    def test_a_draft_the_checks_refuse_is_fixed_by_the_worker_and_then_kept(self):
        def careless(tools, job):
            first = tools.submit_artifact('research-plan', json.dumps(
                {'topic': 'Rolling restarts', 'items': [{'id': 'Not An ID', 'question': ''}]}))
            assert not first[0] and 'needs an "id"' in first[1], first
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', careless)
        root = self.start()
        step = self.steps(root)['research-plan']
        self.assertEqual((self.state(root), step['status'], step['attempts'], step['error']),
                         ('waiting', 'done', 1, None))
        kept = json.loads((root / pipeline.PLAN).read_text())
        self.assertEqual(([item['id'] for item in kept['items']], kept['scope'],
                          kept['purpose']), (list(QUESTIONS), 'public-web', 'planning'))

    def test_a_try_that_hands_nothing_back_is_made_again_with_the_reason(self):
        def never_right(tools, job):
            tools.submit_artifact('research-plan', '{"topic": "Rolling restarts"}')

        self.workers.then('research-plan', fails(SLOW, 'timeout'), never_right)
        root = self.start()
        first, second, third = self.workers.of('research-plan')
        self.assertNotIn('An earlier try', first.task)
        self.assertIn(f'An earlier try at this job did not work: {SLOW}', second.task)
        self.assertIn('An earlier try at this job did not work: What it handed back did not '
                      'pass the checks: "items" must hold 1 to 30 questions.', third.task)
        self.assertEqual(len({first.folder, second.folder, third.folder}), 3)
        step, entry = self.steps(root)['research-plan'], self.record(root)['steps'][
            'research-plan']
        self.assertEqual((self.state(root), step['status'], step['attempts'], step['error']),
                         ('waiting', 'done', 3, None))
        self.assertEqual(([attempt['outcome'] for attempt in entry['attempts']],
                          entry['failed'], entry['attempts'][0]['error']),
                         (['failed', 'failed', 'kept'], 0, SLOW))
        self.assertIn('Rolling restarts: a try at this step did not work: Draft the research '
                      'plan', self.log())

    def test_a_step_that_fails_three_times_stops_the_training_and_says_what_went_wrong(self):
        self.workers.then('research-plan', fails(SLOW, 'timeout'), fails(), fails(
            'It stopped without finishing: its spending limit was reached', 'limit'))
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], len(self.workers.jobs)), ('failed', 3))
        self.assertEqual(view['problem'], {
            'what': 'This step did not work in 3 tries: Draft the research plan. The last '
                    'one: It stopped without finishing: its spending limit was reached',
            'kept': 'Everything kept before this step is still here. Nothing from the tries '
                    'that failed was kept.',
            'action': 'retry', 'label': 'Try again'})
        self.assertEqual(view['sentence'], view['problem']['what'])
        step = self.steps(root)['research-plan']
        self.assertEqual((step['status'], step['attempts']), ('failed', 3))
        self.assertIn('its spending limit was reached', step['error'])
        self.assertFalse((root / pipeline.PLAN).exists())
        self.assertEqual(workspace.status(root)['artifacts']['research-plan'], 'not-started')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertTrue(self.log()[-1].startswith('Rolling restarts: stop. This step did not'))

        self.engine.wake(root)
        self.assertEqual(len(self.workers.jobs), 3, 'a failed run starts nothing by itself')
        after = self.engine.act(root, 'retry')
        self.assertEqual((after['state'], after['problem'], len(self.workers.jobs)),
                         ('waiting', None, 4))
        self.assertEqual(self.steps(root)['research-plan']['status'], 'done')

    def test_an_agent_that_cannot_be_used_is_not_tried_again_until_asked(self):
        self.workers.then('research-plan', fails('Claude Code is not installed on this '
                                                 'computer.', 'unavailable'))
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], len(self.workers.jobs)), ('failed', 1))
        self.assertEqual(view['problem']['what'], 'scripted could not be used. Claude Code is '
                         'not installed on this computer. Check this computer, on the Status screen, says what it needs.')
        self.assertEqual(self.engine.act(root, 'retry')['state'], 'waiting')

    def test_an_account_at_its_usage_limit_stops_at_once_and_says_to_wait(self):
        self.workers.then('research-plan', fails("You've hit your usage limit.", 'limit'))
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], len(self.workers.jobs)), ('failed', 1))
        self.assertEqual(view['problem']['what'], "scripted's account reached a usage or rate "
                         'limit. Wait until it resets, then Try again.')
        self.assertEqual(view['problem']['action'], 'retry')

    def test_a_worker_that_runs_out_of_time_is_tried_again(self):
        self.workers.then('blueprint', fails(SLOW, 'timeout'))
        root = self.start()
        self.to_gate(root, 'blueprint')
        self.assertEqual(self.steps(root)['blueprint']['attempts'], 2)
        self.assertIn(SLOW, self.workers.of('blueprint')[1].task)

    def test_something_the_runner_did_not_expect_stops_one_training_and_says_so(self):
        def broken(tools, job):
            raise RuntimeError('the adapter broke')

        self.workers.then('research-plan', broken)
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], view['problem']['what'], view['problem']['action']),
                         ('failed', 'The runner could not go on: RuntimeError: the adapter '
                          'broke', 'retry'))
        self.assertEqual(self.engine.act(root, 'retry')['state'], 'waiting')


class RequestTests(StudioCase):
    def test_asking_for_changes_runs_the_step_again_with_the_note(self):
        root = self.start()
        shorter = {**FOUR, 'items': FOUR['items'][:3]}

        def revised(tools, job):
            tools.submit_artifact('research-plan', json.dumps(shorter))
            tools.submit_review('I dropped the zero-downtime question, as asked.')

        self.workers.then('research-plan', revised)
        said = self.decide(root, 'research-plan', 'revise',
                           'Drop the zero-downtime question.')
        self.assertIn('Your changes are noted.', said['said'])
        task = self.workers.of('research-plan')[1].task
        self.assertIn('You are revising an earlier draft. What the person asked for:\n\n'
                      'Drop the zero-downtime question.', task)
        self.assertIn('The earlier draft:\n\n- availability: When does a rolling restart '
                      'keep capacity?\n', task)
        status = workspace.status(root)
        self.assertEqual((status['requests'], status['gate'], self.state(root)),
                         ([], 'research-plan', 'waiting'))
        self.assertEqual(len(json.loads((root / pipeline.PLAN).read_text())['items']), 3)
        review = (root / 'reviews' / 'research-plan.md').read_text()
        self.assertIn('> This version was made because you asked for changes: Drop the '
                      'zero-downtime question.', review)
        self.assertEqual(self.log()[-3:], [
            'Rolling restarts: Changes to the research plan were asked for on the page: Drop '
            'the zero-downtime question.',
            'Rolling restarts: keep the research plan',
            'Rolling restarts: ask for a review of the research plan'])
        self.assertEqual(self.steps(root)['research-plan']['attempts'], 2)

    def test_asking_for_a_rebuild_runs_the_step_again_from_the_start(self):
        root = self.start()
        self.to_gate(root, 'blueprint')
        self.decide(root, 'blueprint', 'rebuild')
        task = self.workers.of('blueprint')[1].task
        self.assertIn('The person asked for the blueprint to be made again from the start.',
                      task)
        self.assertEqual((workspace.status(root)['requests'], workspace.status(root)['gate']),
                         ([], 'blueprint'))
        self.assertIn('> This version was made because you asked for a new draft.',
                      (root / 'reviews' / 'blueprint.md').read_text())

    def test_a_request_gives_a_step_that_had_failed_a_fresh_start(self):
        root = self.start()
        self.workers.then('research-plan', fails(), fails(), fails())
        self.decide(root, 'research-plan', 'revise', 'Ask about rollback too.')
        self.assertEqual((self.state(root), len(self.workers.jobs)), ('failed', 4))
        self.assertEqual(workspace.status(root)['artifacts']['research-plan'], 'draft',
                         'the earlier draft is kept')
        self.decide(root, 'research-plan', 'revise', 'Ask about rollback, briefly.')
        self.assertEqual((self.state(root), len(self.workers.jobs)), ('waiting', 5))
        self.assertIn('Ask about rollback, briefly.', self.workers.jobs[-1][1].task)

    def test_leaving_a_stage_out_is_committed_and_the_run_carries_on_where_it_was(self):
        root = self.start(deck_target='pptx')
        said = self.decide(root, 'deck', 'skip', 'No slides for this one.')
        self.assertIn('This stage is left out.', said['said'])
        status = workspace.status(root)
        self.assertNotIn('deck', status['settings']['stages'])
        self.assertEqual((status['gate'], status['pending_question'], self.state(root)),
                         ('research-plan', 'Approve the research plan?', 'waiting'))
        self.assertEqual(self.log()[-2:], [
            'Rolling restarts: The deck stage was left out on the page: No slides for this '
            'one.', 'Rolling restarts: ask for a review of the research plan'])
        self.assertEqual(len(self.workers.jobs), 1)
        self.decide(root, 'research-plan')
        self.assertEqual(workspace.status(root)['gate'], 'research')

    def test_changing_the_approved_plan_later_researches_only_the_questions_that_changed(self):
        root = self.start()
        self.to_gate(root, 'blueprint')
        wider = {**FOUR, 'items': FOUR['items'] + [
            {'id': 'rollback', 'question': 'How is a failed restart rolled back?',
             'public_query': 'rolling restart rollback'}]}
        self.workers.plan = wider
        self.decide(root, 'research-plan', 'revise', 'Add a question about rollback.')
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')
        before = len(self.workers.jobs)
        self.decide(root, 'research-plan')
        asked = [kind for kind, _, _ in self.workers.jobs[before:]
                 if kind.startswith('question:')]
        self.assertEqual(asked, ['question:rollback'],
                         'the four questions asked as before keep their findings')
        self.assertEqual(workspace.findings_index(workspace.research_record(root)),
                         {'availability': 'supported', 'instance-min': 'supported',
                          'health-checks': 'supported', 'zero-downtime': 'contradicted',
                          'rollback': 'supported'})
        self.assertEqual(workspace.status(root)['gate'], 'research')
        self.decide(root, 'research')
        status = workspace.status(root)
        self.assertEqual((status['gate'], status['artifacts']['blueprint'], self.state(root)),
                         ('blueprint', 'draft', 'waiting'))
        again = self.workers.of('blueprint')
        self.assertEqual(len(again), 2, 'the blueprint is drafted again from the new research')
        self.assertIn('What the blueprint was made from has changed since the earlier draft, '
                      'and the person approved the change, so it is being made again.',
                      again[1].task)
        self.assertIn('The earlier draft:\n\n# Blueprint: Rolling restarts', again[1].task)
        self.assertIn('> This version was made because what the earlier one was made from '
                      'changed, and you approved the change.',
                      (root / 'reviews' / 'blueprint.md').read_text())
        self.assertIn('## rollback', pipeline.findings_text(root))


class QuestionTests(StudioCase):
    def test_a_workers_question_waits_for_an_answer_which_goes_into_the_brief(self):
        self.workers.then('research-plan', asks('Which of the two platforms is this about?'))
        root = self.start()
        view = self.view(root)
        asked = view['question']
        self.assertEqual((view['state'], view['sentence']), (
            'waiting', 'A question is waiting for you: Which of the two platforms is this '
            'about?'))
        self.assertEqual((sorted(asked), asked['text'], asked['from']), (
            ['from', 'id', 'text'], 'Which of the two platforms is this about?',
            'The worker drafting the research plan'))
        self.assertEqual((self.steps(root)['research-plan']['status'], view['problem']),
                         ('waiting', None))
        self.assertEqual(self.log()[-1],
                         'Rolling restarts: a worker asks a question: Draft the research plan')
        self.engine.wake(root)
        self.assertEqual(len(self.workers.jobs), 1, 'nothing runs until it is answered')

        with self.assertRaisesRegex(WorkspaceError, 'not waiting for an answer any more'):
            self.engine.answer(root, 'another-question', 'The first.')
        after = self.engine.answer(root, asked['id'], ' The newer one.\n')
        self.assertEqual((after['state'], after['question']), ('waiting', None))
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')
        task = self.workers.of('research-plan')[1].task
        self.assertIn('A worker on this job asked the person before. Do not ask these again:'
                      '\n\nQuestion: Which of the two platforms is this about?\nAnswer: The '
                      'newer one.', task)
        with self.assertRaisesRegex(WorkspaceError, 'not waiting for an answer any more'):
            self.engine.answer(root, asked['id'], 'Again.')
        entry = self.record(root)['steps']['research-plan']
        self.assertEqual(([attempt['outcome'] for attempt in entry['attempts']],
                          entry['failed']), (['question', 'kept'], 0))
        self.assertIn("Rolling restarts: a worker's question was answered on the page",
                      self.log())

    def test_a_step_may_ask_only_so_many_questions(self):
        self.workers.then('research-plan', asks('One?'), asks('Two?'), asks('Three?'))
        root = self.start()
        for _ in range(3):
            self.assertTrue(self.workers.jobs[-1][2]['ask'])
            self.engine.answer(root, self.view(root)['question']['id'], 'Yes.')
        self.assertFalse(self.workers.jobs[-1][2]['ask'])
        self.assertEqual((self.state(root), len(self.workers.jobs)), ('waiting', 4))
        self.assertIsNone(self.view(root)['question'])


class NoteTests(StudioCase):
    """A note for the next step goes with the next job that starts, once, and stops nothing."""

    def test_a_note_goes_with_the_next_job_only_and_is_kept_in_history(self):
        root = self.start()
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')
        before = len(self.workers.jobs)
        self.assertEqual(self.view(root)['note'], {'pending': None, 'used': [], 'expected': '0'})
        noted = self.engine.note(root, '  Lean on the operator handbook.  ', '0')
        self.assertEqual((noted['note']['pending']['text'], noted['note']['expected']),
                         ('Lean on the operator handbook.', '1'))
        self.assertEqual(self.log()[-1], 'Rolling restarts: note for the next step: Lean on '
                         'the operator handbook.')
        with self.assertRaisesRegex(WorkspaceError, 'The note changed'):
            self.engine.note(root, 'Keep each answer short.', '0')
        noted = self.engine.note(root, 'Keep each answer short.', '1')
        self.assertEqual(noted['note']['pending']['text'], 'Keep each answer short.')
        self.assertIn('Rolling restarts: replace the note for the next step: Keep each answer '
                      'short.', self.log())
        self.assertEqual(len(self.workers.jobs), before, 'nothing started for a note')
        self.decide(root, 'research-plan')
        started = [job for seen, job, spec in self.workers.jobs[before:]]
        self.assertGreater(len(started), 1)
        carried = [job for job in started
                   if '## Note from the author for this step' in job.task]
        self.assertEqual(len(carried), len(started),
                         'every research question worked on together carries it')
        self.assertIn('> Keep each answer short.', carried[0].task)
        self.assertNotIn('operator handbook', carried[0].task)
        record = self.record(root)
        self.assertIsNone(record['pending_note'])
        self.assertEqual([(note['text'], note['step'].partition(':')[0])
                          for note in record['notes_used']],
                         [('Keep each answer short.', 'research')])
        shown = self.view(root)['note']
        self.assertEqual((shown['pending'], shown['used'][0]['text'], shown['expected']),
                         (None, 'Keep each answer short.', '3'))
        self.assertTrue(any(line.startswith('Rolling restarts: the note for the next step goes '
                                            'with: Researching the question ')
                            for line in self.log()))

    def test_a_note_made_while_a_job_runs_waits_for_the_next_one(self):
        def noting(tools, job):
            [root] = self.engine.trainings()
            self.engine.note(root, 'Name the two platforms.')
            return self.workers.research_plan(tools, job)
        self.workers.then('research-plan', noting)
        root = self.start()
        self.assertNotIn('Note from the author', self.workers.of('research-plan')[0].task,
                         'nothing reaches a job already running')
        self.assertEqual(self.view(root)['note']['pending']['text'], 'Name the two platforms.')
        self.decide(root, 'research-plan')
        carried = [job for seen, job, spec in self.workers.jobs
                   if 'Name the two platforms.' in job.task]
        self.assertEqual(len(carried), len(self.workers.of('question')))
        self.assertEqual(len(self.record(root)['notes_used']), 1, 'history records it once')

    def test_a_try_again_at_a_question_carries_the_note_and_a_reviewer_takes_none(self):
        self.workers.then('question', fails())
        root = self.start()
        self.engine.note(root, 'Cite the handbook.\r\nNothing else.')
        self.decide(root, 'research-plan')
        questions = self.workers.of('question')
        self.assertGreater(len(questions), len(QUESTIONS), 'one question was tried again')
        for job in questions:
            self.assertIn('> Cite the handbook.\n> Nothing else.', job.task)
        # A reviewer's job leaves a waiting note for the next writer.
        self.engine.note(root, 'For the blueprint.')
        work = pipeline.Work('guidance', 'task', 'write', {'review': {}})
        for ident in ('deck-review@201', 'research-review', 'research:review-2'):
            step = pipeline.Step(ident, 'agent', 'Review it', 'Reviewing it', 'deck')
            self.assertIs(self.engine._noted(root, step, work), work)
        self.assertEqual(self.record(root)['pending_note']['text'], 'For the blueprint.')
        self.assertTrue(all(note.get('done') for note in self.record(root)['notes_used']),
                        'a later step\'s job closed the research notes')

    def test_a_note_is_refused_when_empty_too_long_finished_or_stopped(self):
        root = self.start()
        with self.assertRaisesRegex(WorkspaceError, 'Write the note first'):
            self.engine.note(root, '   ')
        with self.assertRaisesRegex(WorkspaceError, 'at most 2000 characters'):
            self.engine.note(root, 'x' * 2001)
        self.engine.act(root, 'stop')
        with self.assertRaisesRegex(WorkspaceError, 'stopped'):
            self.engine.note(root, 'Too late.')
        self.engine.act(root, 'resume')
        self.to_end(root)
        self.assertEqual(self.state(root), 'done')
        with self.assertRaisesRegex(WorkspaceError, 'finished'):
            self.engine.note(root, 'Too late.')
        self.assertIsNone(self.record(root).get('pending_note'))

    def test_a_stuck_training_takes_no_note(self):
        root = self.start()
        stuck = pipeline.Next('stuck', why='Its folder cannot be read.')
        found = self.engine._survey(root, self.record(root))
        with mock.patch.object(self.engine, '_survey', return_value=replace(found, next=stuck)):
            with self.assertRaisesRegex(WorkspaceError, 'cannot go on'):
                self.engine.note(root, 'Too late.')


class ResearchTests(StudioCase):
    def test_a_question_that_fails_three_times_is_named_at_the_gate(self):
        self.workers.then('question:health-checks', fails(SLOW, 'timeout'),
                          fails(SLOW, 'timeout'), fails(SLOW, 'timeout'))
        root = self.start()
        self.decide(root, 'research-plan')
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'research'))
        tried = self.workers.of('question:health-checks')
        self.assertEqual((len(tried), len(self.workers.of('question'))), (3, 6))
        self.assertIn(f'An earlier try at this job did not work: {SLOW}', tried[2].task)
        review = (root / 'reviews' / 'research.md').read_text()
        self.assertIn('> 2 of 4 questions have an answer the sources support.', review)
        self.assertIn(f'> Not researched (1):\n> - health-checks: What starts the next batch? '
                      f'({SLOW})', review)
        step = self.steps(root)['research']
        self.assertEqual((step['status'], step['attempts'], step['error']), (
            'done', 6, f'1 question could not be answered. The last reason: {SLOW}'))
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 2, 'contradicted': 1, 'pending': 1})

        self.decide(root, 'research', 'rebuild')
        self.assertEqual(len(self.workers.of('question:health-checks')), 4)
        self.assertEqual(len(self.workers.of('question')), 7, 'only that question is redone')
        self.assertIn('> Every question was researched and settled.',
                      (root / 'reviews' / 'research.md').read_text().rpartition('## Ready')[2])
        self.assertEqual((workspace.status(root)['gate'], workspace.status(root)['requests'],
                          self.steps(root)['research']['error']), ('research', [], None))

    def test_a_finding_the_sources_do_not_settle_is_named_at_the_gate(self):
        def unsure(tools, job):
            tools.submit_finding('instance-min', 'insufficient', 'The page does not say.',
                                 limits='Only one page was found.')

        self.workers.then('question:instance-min', unsure)
        root = self.start()
        self.decide(root, 'research-plan')
        self.assertIn('> Not settled (1):\n> - instance-min: How many instances keep capacity '
                      'during a restart? (insufficient)',
                      (root / 'reviews' / 'research.md').read_text())
        self.decide(root, 'research', 'revise', 'Look at the scaling guide for this.')
        self.assertEqual((len(self.workers.of('question:instance-min')),
                          len(self.workers.of('question'))), (2, 5))
        self.assertIn('The person looked at the research and asked for this, which may or may '
                      'not be about your question:\n\nLook at the scaling guide for this.',
                      self.workers.of('question:instance-min')[1].task)
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 3, 'contradicted': 1})

    def test_a_note_that_names_a_question_has_that_one_researched_again(self):
        root = self.start()
        self.to_gate(root, 'research')
        self.decide(root, 'research', 'revise',
                    'The answer for health-checks misses readiness probes.')
        self.assertEqual((len(self.workers.of('question:health-checks')),
                          len(self.workers.of('question'))), (2, 5))
        self.assertEqual(workspace.status(root)['gate'], 'research')
        self.decide(root, 'research', 'rebuild')
        self.assertEqual(len(self.workers.of('question')), 9,
                         'with nothing named and nothing open, every question is redone')

    def test_research_that_answers_nothing_stops_the_training(self):
        self.workers.then('question', *[fails(SLOW, 'timeout')] * 12)
        root = self.start()
        self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual((view['state'], len(self.workers.of('question'))), ('failed', 12))
        self.assertEqual(view['problem'], {
            'what': f'None of the 4 research questions could be answered. {SLOW}',
            'kept': 'The research plan you approved is kept.', 'action': 'retry',
            'label': 'Try again'})
        self.assertEqual(self.steps(root)['research']['status'], 'failed')
        self.assertEqual(workspace.status(root)['artifacts']['research'], 'draft')
        self.assertIsNone(workspace.status(root)['gate'])
        self.assertEqual(self.engine.act(root, 'retry')['state'], 'waiting')
        self.assertEqual(workspace.status(root)['gate'], 'research')

    def test_the_research_purpose_is_the_shared_one(self):
        from runner import engine as engine_module
        from studio_core import research_contract
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        self.engine._store(root, record)
        captured = []

        def native(engine, root, run, task, sources, product):
            captured.append(task)
            raise WorkspaceError('Stopped here by the test.')
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=native), \
                mock.patch.object(engine_module.research_contract, 'purpose',
                                  wraps=research_contract.purpose) as built:
            self.decide(root, 'research-plan')
        kind, goal, priorities = built.call_args[0]
        self.assertTrue(kind.startswith('training'), kind)
        self.assertIn('Prioritize learner tasks', priorities)
        self.assertEqual(captured[0]['purpose'], research_contract.purpose(kind, goal, priorities))

    def test_bringing_the_research_up_to_date_reaches_the_author(self):
        from types import SimpleNamespace
        from runner import engine as engine_module
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        self.engine._store(root, record)
        found = self.engine._survey(root, self.engine._load(root))
        captured = []

        def native(engine, root_, run, task, sources, product):
            captured.append(task)
            raise WorkspaceError('Stopped here by the test.')
        for request in (None, {'artifact': 'research', 'kind': 'revise', 'note': 'Newer.',
                               'refresh': True, 'at': 'now'}):
            step = SimpleNamespace(id='research', request=request, questions=[])
            with mock.patch.object(engine_module.research_contract, 'native',
                                   side_effect=native), self.assertRaises(WorkspaceError):
                self.engine._research(root, None, found, step)
        self.assertEqual([task['refresh'] for task in captured], [False, True])

    def test_a_check_that_still_objects_stops_at_research_and_says_what_it_objected_to(self):
        from runner import engine as engine_module
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        self.engine._store(root, record)
        refusal = WorkspaceError(
            'The independent check of the research still needs changes after 3 rounds of '
            'correction: 2 objections, such as fact-b (unsupported): The source does not say so. '
            'Coverage needs revision: Alternatives are missing. The draft report and the check’s '
            'notes are saved for correction.')
        refusal.objections = ['fact-b (unsupported): The source does not say so.',
                              'Coverage needs revision: Alternatives are missing.']
        refusal.rounds = 3
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=refusal):
            self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual(view['state'], 'failed')
        self.assertEqual(view['problem'], {
            'what': str(refusal), 'action': 'retry', 'label': 'Try again',
            'kept': 'The draft report and the check’s objections are kept with this training: '
                    'Read every objection shows them. The research plan you approved is kept.',
            'objections': 'reviews/research.md',
            # What the page says Try again does: no research job ran here.
            'research': {'rounds': 0, 'jobs': 0, 'seconds': 0, 'dollars': None, 'most': 3,
                         'drafted': False}})
        self.assertEqual(self.record(root)['problem']['step'], 'research')
        review = (root / 'reviews' / 'research.md').read_text()
        self.assertIn('## Independent research review: changes still needed', review)
        self.assertIn('> - fact-b (unsupported): The source does not say so.', review)
        self.assertIn('> - Coverage needs revision: Alternatives are missing.', review)
        self.assertEqual(self.workers.of('question'), [])
        # Try again re-runs the research, both jobs, from the start.
        with mock.patch.object(engine_module.research_contract, 'native',
                               side_effect=refusal) as again:
            self.assertEqual(self.engine.act(root, 'retry')['state'], 'failed')
        self.assertEqual(again.call_count, 1)

    def test_objections_in_groups_are_listed_under_each_group(self):
        from runner import engine as engine_module
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        self.engine._store(root, record)
        refusal = WorkspaceError('The independent check of the research still needs changes.')
        refusal.objections = ['f01 (narrow): Too broad.', 'f02 (narrow): Too broad too.',
                              'Coverage needs revision: Alternatives are missing.']
        refusal.groups = [
            {'title': '2 facts the check calls narrow', 'count': 2, 'note': 'f01: Too broad.',
             'items': ['f01: Too broad.', 'f02: Too broad too.']},
            {'title': 'coverage needs revision', 'count': 1, 'note': 'Alternatives are missing.',
             'items': ['Alternatives are missing.']}]
        refusal.rounds = 3
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=refusal):
            self.decide(root, 'research-plan')
        self.assertIn('Read every objection shows them, under what the check called them.',
                      self.view(root)['problem']['kept'])
        self.assertNotIn('reviews/research.md', self.view(root)['problem']['kept'])
        review = (root / 'reviews' / 'research.md').read_text()
        self.assertIn('> 2 facts the check calls narrow:\n> - f01: Too broad.\n'
                      '> - f02: Too broad too.\n>\n> coverage needs revision:\n'
                      '> - Alternatives are missing.', review)

    def test_a_check_that_could_not_read_an_original_stops_at_once_and_says_whose_problem(self):
        from runner import engine as engine_module
        from studio_core import research_contract
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        self.engine._store(root, record)
        cause = [{'source': 'source-a', 'title': 'Handbook', 'file': 'sources/supplied/handbook.text',
                  'original': 'sources/supplied/handbook.md',
                  'access_error': 'There is no tool to read it.'}]
        said = str(research_contract.CheckCouldNotFinish(['fact-a (narrow): Not read.'], 0, cause))
        refusal = WorkspaceError(said)
        refusal.objections, refusal.rounds, refusal.cause = ['fact-a (narrow): Not read.'], 0, cause
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=refusal):
            self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual(view['state'], 'failed')
        self.assertEqual(view['problem']['what'], said)
        self.assertIn('could not read the original of "Handbook"', said)
        self.assertIn('Try again works once the original can be read.', view['problem']['kept'])
        self.assertEqual(self.record(root)['problem']['unreadable'], cause)
        review = (root / 'reviews' / 'research.md').read_text()
        self.assertIn('## Independent research review: the check could not finish', review)
        self.assertIn('Handbook: sources/supplied/handbook.md (There is no tool to read it.)', review)
        self.assertNotIn('rounds of correction', review)
        # Try again is refused, in the same words, while the original still cannot be read.
        # The dry read is done before the training's files are held.
        def unread(*given):
            self.assertFalse(self.engine.files._is_owned())
            return 'It cannot be read.'
        with mock.patch.object(engine_module.research_contract, 'dry_read',
                               side_effect=unread) as read, \
                mock.patch.object(engine_module.research_contract, 'native') as again:
            with self.assertRaises(WorkspaceError) as caught:
                self.engine.act(root, 'retry')
        self.assertEqual(str(caught.exception), said)
        self.assertEqual((read.call_args[0][2], again.call_count), (cause, 0))
        self.assertEqual(self.view(root)['state'], 'failed')
        # Once it can be read, Try again runs the research again.
        with mock.patch.object(engine_module.research_contract, 'dry_read', return_value=None), \
                mock.patch.object(engine_module.research_contract, 'native',
                                  side_effect=refusal) as again:
            self.engine.act(root, 'retry')
        self.assertEqual(again.call_count, 1)

    def test_an_agent_that_cannot_be_used_stops_the_research_at_once(self):
        self.engine = self.make(at_once=1)
        self.workers.then('question:instance-min', fails('Not signed in.', 'unavailable'))
        root = self.start()
        self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual((view['state'], view['problem']['what'],
                          len(self.workers.of('question'))),
                         ('failed', 'scripted could not be used. Not signed in. Check this computer, on the Status screen, says what it needs.', 2))
        self.assertEqual(self.engine.act(root, 'retry')['state'], 'waiting')
        self.assertEqual(len(self.workers.of('question')), 5)

    def test_without_harness_research_the_training_stops_before_research_and_says_so(self):
        with mock.patch.object(research, 'locations', return_value=[self.base / 'nowhere']):
            self.engine = self.make(research=research.Research)
            root = self.start()
            self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence']), (
            'stopped', 'The harness-research skill is not installed on this computer, so '
            'research cannot run. Install it, then try again.'))
        self.assertEqual((view['problem']['kept'], view['problem']['action'],
                          view['problem']['label']),
                         ('The research plan you approved is kept.', 'retry', 'Try again'))
        self.assertEqual((self.steps(root)['research-start']['status'],
                          self.workers.of('question')), ('failed', []))
        self.assertFalse((root / '.harness-research').exists())
        self.engine.research = lambda: self.research
        self.assertEqual(self.engine.act(root, 'retry')['state'], 'waiting')
        self.assertEqual(workspace.status(root)['gate'], 'research')

    def test_the_stand_in_is_called_as_the_research_pipeline_lays_it_out(self):
        self.engine = self.make(at_once=1)
        root = self.start()
        self.decide(root, 'research-plan')
        calls = [call[0] for call in self.research.run.calls]
        self.assertEqual(calls, ['plan', 'record', 'record', 'record', 'record', 'status'])
        self.assertEqual(self.research.run.calls[0][1:], [
            '--project', str(root), '--file', str(root / pipeline.PLAN)])
        self.assertEqual(self.record(root)['research']['run'],
                         workspace.research_record(root)['run'])


class SynthesisWordsTests(StudioCase):
    """What a run whose research is one authored report and one independent check says
    while that research is in hand. The record is read as it lies; nothing is run."""

    STAMPS = ('2030-01-01T00:00:00Z', '2030-01-01T00:05:00Z', '2030-01-01T00:10:00Z')

    def test_a_synthesis_run_says_which_of_its_two_jobs_is_in_hand(self):
        from types import SimpleNamespace
        root = self.start()
        self.assertEqual(self.state(root), 'waiting')
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        record['research'] = {'run': 'synthesis', 'plan': 'plan'}
        record['steps']['research-start'] = {'failed': 0, 'attempts': [
            {'started_at': self.STAMPS[0], 'ended_at': self.STAMPS[0], 'outcome': 'kept'}]}
        step = pipeline.Step('research', 'agent', 'Investigate the sources and write the '
                             'report, then check it independently',
                             'Investigating the sources and checking the research', 'research')
        found = SimpleNamespace(next=SimpleNamespace(kind='agent', step=step))
        run = self.engine._run(root)

        def live(*jobs: str) -> None:
            run.workers.clear()
            for job in jobs:
                run.workers[job] = {'label': job, 'started_at': self.STAMPS[1], 'lines': []}

        def says() -> str:
            return self.engine._doing(record, found, run)

        first = 'Investigating sources and writing the report (round 1 of 3, job 1 of 2).'
        checking = 'Independently checking the research (round 1 of 3, job 2 of 2).'
        correcting = ('Correcting the research after its independent check (round 2 of 3, '
                      'job 1 of 2).')
        self.assertEqual(says(), first)
        live('research:author-1')
        self.assertEqual(says(), first)
        live('research:review-1')
        self.assertEqual(says(), checking)
        # The check asked for corrections: the author's job runs again, then the check.
        live('research:author-2')
        self.assertEqual(says(), correcting)
        live('research:review-2')
        self.assertEqual(says(), 'Independently checking the corrected research '
                                 '(round 2 of 3, job 2 of 2).')
        # Between jobs, the next one is worked out from the last one kept.
        live()
        record['steps']['research:author-1'] = {'failed': 0, 'attempts': [
            {'started_at': self.STAMPS[1], 'ended_at': self.STAMPS[1], 'outcome': 'kept'}]}
        self.assertEqual(says(), checking)
        record['steps']['research:review-1'] = {'failed': 0, 'attempts': [
            {'started_at': self.STAMPS[2], 'ended_at': self.STAMPS[2], 'outcome': 'kept'}]}
        self.assertEqual(says(), correcting)
        # A job recorded under its old name is the research's too.
        live('research-review')
        self.assertEqual(says(), checking)
        # A change the person asked for starts the rounds again: the check before it is
        # not one of this research's rounds.
        record['research']['again'] = {'at': '2030-01-02T00:00:00Z', 'left': ['synthesis']}
        live()
        self.assertEqual(says(), first)

    def test_a_research_job_s_folder_is_named_for_the_research_not_a_question(self):
        from runner.engine import folder_name
        self.assertEqual(folder_name('research:author-1'), 'research-author-1')
        self.assertEqual(folder_name('research:review-3'), 'research-review-3')
        self.assertEqual(folder_name('research:instance-min'), 'question-instance-min')

    def test_a_stop_at_the_research_says_what_its_last_try_took(self):
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        kept = {'outcome': 'kept', 'error': None, 'tokens': 1000}
        record['steps'].update({
            'research:author-1': {'failed': 0, 'attempts': [
                {**kept, 'started_at': self.STAMPS[0], 'seconds': 300.0, 'dollars': 0.8},
                {**kept, 'started_at': self.STAMPS[2], 'seconds': 200.0, 'dollars': 0.5}]},
            'research:review-1': {'failed': 0, 'attempts': [
                {**kept, 'started_at': self.STAMPS[1], 'seconds': 100.0, 'dollars': 0.3}]}})
        self.engine._store(root, record)
        self.engine._problem(root, 'research', 'failed', 'It stopped.', 'Kept.')
        self.assertEqual(self.view(root)['problem']['research'], {
            'rounds': 1, 'jobs': 1, 'seconds': 200.0, 'dollars': 0.5, 'most': 3,
            'drafted': False})
        self.engine._problem(root, 'blueprint', 'failed', 'It stopped.', 'Kept.')
        self.assertNotIn('research', self.view(root)['problem'])

    def test_the_research_row_carries_both_jobs_time_and_money(self):
        from types import SimpleNamespace
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        record['steps']['research-author'] = {'failed': 0, 'attempts': [
            {'started_at': self.STAMPS[0], 'ended_at': self.STAMPS[1], 'seconds': 300.0,
             'dollars': 0.8, 'tokens': 40000, 'outcome': 'kept', 'error': None}]}
        record['steps']['research-review'] = {'failed': 1, 'attempts': [
            {'started_at': self.STAMPS[1], 'ended_at': self.STAMPS[2], 'seconds': 120.5,
             'dollars': 0.25, 'tokens': 9000, 'outcome': 'failed',
             'error': 'The agent could not be reached.'}]}
        step = pipeline.Step('research', 'agent', *pipeline.SYNTHESIS, 'research')
        found = SimpleNamespace(steps=[step], done=frozenset(),
                                next=SimpleNamespace(kind='agent', step=step),
                                research=SimpleNamespace(unread=[]))
        row, = self.engine._steps(record, found, 'working')
        self.assertEqual((row['id'], row['status'], row['attempts'], row['seconds'],
                          row['dollars']), ('research', 'working', 2, 420.5, 1.05))

    def test_a_run_that_researches_each_question_keeps_its_count(self):
        from types import SimpleNamespace
        root = self.start()
        self.assertEqual(self.state(root), 'waiting')
        record = self.engine._load(root)
        step = pipeline.Step('research', 'agent', 'Research each question',
                             'Researching the questions', 'research')
        found = SimpleNamespace(next=SimpleNamespace(kind='agent', step=step),
                                research=SimpleNamespace(
                                    verdicts={'q1': 'supported', 'q2': 'pending',
                                              'q3': 'pending'}, unread=['q2', 'q3']))
        self.assertEqual(self.engine._doing(record, found, self.engine._run(root)),
                         'Researching the questions: 1 of 3 answered so far.')


class LimitTests(StudioCase):
    def test_a_training_that_has_spent_what_it_may_stops_and_asks(self):
        settings.save(replace(settings.load(), training_dollars=1.0))
        self.workers.cost = 0.6
        self.engine = self.make(at_once=1)
        root = self.start()
        self.assertEqual(self.workers.jobs[0][1].limits.dollars, 1.0)
        self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence'], view['spent']['dollars']), (
            'stopped', 'This training has spent $1.20. It stops and asks each time it has '
            'spent another $1.00.', 1.2))
        self.assertEqual(view['problem'], {
            'what': view['sentence'], 'action': 'resume', 'label': 'Carry on',
            # Carry on is one way on; raising the limit in Settings is the other.
            'kept': 'Everything made so far is kept. Carry on lets it spend up to another $1.00. To let it spend more before it asks, raise the limit in Settings, under Limits, then carry on.'})
        self.assertEqual(([job.limits.dollars for job in self.workers.of('question')],
                          self.steps(root)['research']['status']), ([0.4], 'to-do'))
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 1, 'pending': 3})

        self.assertEqual(self.engine.act(root, 'resume')['state'], 'stopped')
        self.assertEqual(self.view(root)['spent'], {'dollars': 2.4, 'tokens': 4800, 'stops_at': 2.2})
        after = self.engine.act(root, 'resume')
        self.assertEqual((after['state'], after['problem'], after['spent']['dollars']),
                         ('waiting', None, 3.0))
        self.assertEqual(workspace.status(root)['gate'], 'research')

    def test_a_step_that_spends_what_is_left_stops_for_money_not_as_a_failed_try(self):
        from runner.agents import Outcome
        settings.save(replace(settings.load(), training_dollars=1.0))
        self.workers.then('research-plan', lambda tools, job: Outcome(
            False, 'limit', 'It stopped without finishing: its spending limit was reached',
            cost=1.0, budget=True))
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], len(self.workers.jobs)), ('stopped', 1))
        self.assertEqual(view['problem'], {
            'what': 'Draft the research plan was stopped when this training reached what it '
                    'may spend: it has spent $1.00. It stops and asks each time it has spent '
                    'another $1.00.',
            'kept': 'Everything finished before this step is kept, and the step starts again '
                    'when you carry on. Carry on lets it spend up to another $1.00. To let it '
                    'spend more before it asks, raise the limit in Settings, under Limits, then '
                    'carry on.',
            'action': 'resume', 'label': 'Carry on'})
        entry = self.record(root)['steps']['research-plan']
        self.assertEqual((entry['failed'], entry['attempts'][0]['outcome']), (0, 'limit'))
        self.assertEqual(self.engine.act(root, 'resume')['state'], 'waiting')
        self.assertEqual(len(self.workers.jobs), 2)

    def test_no_job_starts_with_too_little_left_to_spend(self):
        settings.save(replace(settings.load(), training_dollars=20.0))
        self.workers.cost = 19.7
        self.engine = self.make(at_once=1)
        root = self.start()
        self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual(self.workers.of('question'), [], 'no job starts with $0.30 left')
        self.assertEqual((view['state'], view['sentence']), (
            'stopped', 'This training has spent $19.70, and the $0.30 it may still spend is too '
            'little to start another step. It stops and asks each time it has spent another '
            '$20.00.'))
        self.assertEqual(view['problem']['action'], 'resume')

    def test_a_step_that_runs_out_of_time_offers_more_time_for_this_training(self):
        settings.save(replace(settings.load(), step_seconds=600))
        self.workers.then('research-plan', *[fails(SLOW, 'timeout')] * 3)
        root = self.start()
        view = self.view(root)
        self.assertEqual(view['problem'], {
            'what': 'Draft the research plan ran out of the time a step may take: its last try '
                    'was stopped after 10 minutes, and it did not work in 3 tries. That limit, '
                    '10 minutes a step, is in Settings, under Limits.',
            'kept': 'Everything kept before this step is still here. Nothing from the tries '
                    'that failed was kept.',
            'action': 'more-time', 'label': 'Give it more time and try again', 'seconds': 600})
        self.assertEqual([job.limits.seconds for job in self.workers.of('research-plan')],
                         [600] * 3)
        with self.assertRaisesRegex(WorkspaceError, 'nothing to resume'):
            self.engine.act(root, 'resume')
        self.assertEqual(self.engine.act(root, 'more-time')['state'], 'waiting')
        self.assertEqual(self.workers.of('research-plan')[-1].limits.seconds, 1200)
        # The run keeps its time when its limits are read again; Settings keeps its own.
        self.assertEqual((self.record(root)['limits']['step_seconds'],
                          self.record(root)['more_time'], settings.load().step_seconds),
                         (1200, 1200, 600))
        self.decide(root, 'research-plan')
        self.assertEqual({job.limits.seconds for job in self.workers.of('question')}, {1200})

    def test_running_out_of_the_time_more_time_gave_names_the_run_s_own_limit(self):
        settings.save(replace(settings.load(), step_seconds=600))
        self.workers.then('research-plan', *[fails(SLOW, 'timeout')] * 6)
        root = self.start()
        self.engine.act(root, 'more-time')
        self.assertEqual(self.view(root)['problem']['what'], (
            'Draft the research plan ran out of the time a step may take: its last try was '
            'stopped after 20 minutes, and it did not work in 3 tries. That limit, now 20 '
            'minutes a step for this training, was given when you asked for more time; the limit '
            'for every training is in Settings, under Limits.'))
        self.assertEqual(self.view(root)['problem']['seconds'], 1200)

    def test_a_research_job_that_runs_out_of_time_or_money_says_so(self):
        from runner import engine as engine_module
        from runner.agents import Outcome
        root = self.start()
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        self.engine._store(root, record)
        late = WorkspaceError('Research did not finish its author job in round 1 of 3.')
        late.outcome = Outcome(False, 'timeout', SLOW)
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=late):
            self.decide(root, 'research-plan')
        problem = self.view(root)['problem']
        self.assertEqual((problem['action'], problem['seconds']), ('more-time', 900))
        self.assertTrue(problem['what'].startswith('The research ran out of the time a step may '
                                                   'take: it was stopped after 15 minutes.'))
        spent = WorkspaceError('Research did not finish its review job in round 2 of 3.')
        spent.outcome = Outcome(False, 'limit', 'its spending limit was reached', budget=True)
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=spent):
            self.engine.act(root, 'more-time')
        problem = self.view(root)['problem']
        self.assertEqual(problem['action'], 'resume')
        self.assertTrue(problem['what'].startswith('The research was stopped when this training '
                                                   'reached what it may spend'))

    def test_a_step_is_given_its_time_and_what_the_training_may_still_spend(self):
        settings.save(replace(settings.load(), step_seconds=120, training_dollars=5.0))
        self.workers.cost = 1.5
        root = self.start()
        self.decide(root, 'research-plan')
        limits = [(job.limits.seconds, job.limits.dollars) for _, job, _ in self.workers.jobs]
        self.assertEqual(limits[0], (120, 5.0))
        self.assertEqual({seconds for seconds, _ in limits}, {120})
        self.assertLessEqual(max(dollars for _, dollars in limits[1:]), 3.5)

    def test_carrying_on_or_trying_again_takes_up_the_limits_this_computer_has_now(self):
        self.workers.then('research-plan', fails(), fails(), fails())
        root = self.start()
        settings.save(replace(settings.load(), step_seconds=1200, training_dollars=50.0))
        self.engine.act(root, 'retry')
        self.assertEqual(self.record(root)['limits'],
                         {'step_seconds': 1200, 'training_dollars': 50.0})
        self.assertEqual(self.workers.jobs[-1][1].limits.seconds, 1200)


class HaltTests(StudioCase):
    """What a person may ask of a run, which depends on the state it is in."""

    def refused(self, root: Path, action: str, said: str) -> None:
        before = self.record(root)
        with self.assertRaisesRegex(WorkspaceError, said):
            self.engine.act(root, action)
        self.assertEqual(self.record(root), before)

    def test_pausing_lets_the_step_in_hand_finish_and_starts_nothing_new(self):
        paused = []

        def pauses(tools, job):
            paused.append(self.engine.act(self.space.training('rolling-restarts'), 'pause'))
            self.workers.question(tools, job)

        self.engine = self.make(at_once=1)
        root = self.start()
        self.workers.then('question:availability', pauses)
        self.decide(root, 'research-plan')
        self.assertEqual((paused[0]['state'], paused[0]['sentence']),
                         ('paused', 'Pausing. The step in hand finishes first.'))
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence'], len(self.workers.of('question'))),
                         ('paused', 'Paused. Nothing new starts until you resume.', 1))
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 1, 'pending': 3})
        self.refused(root, 'pause', 'Only a training that is working can be paused. This one '
                     'is paused.')
        resumed = self.engine.act(root, 'resume')
        self.assertEqual((resumed['state'], len(self.workers.of('question'))), ('waiting', 4))
        self.assertIn('Rolling restarts: paused on the page', self.log())
        self.assertIn('Rolling restarts: resumed on the page', self.log())

    def test_finishing_the_level_in_hand_pauses_before_the_next_level_starts(self):
        asked = []

        def finishes(tools, job):
            asked.append(self.engine.act(self.space.training('rolling-restarts'), 'finish-level'))
            return self.workers.document(tools, job)

        self.workers.then('document', finishes)
        with mock.patch('studio_core.review_policy.capture',
                        return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start(levels=['101', '201'], materials=['document'])
        self.assertEqual((asked[0]['state'], asked[0]['controls']['finishing'],
                          asked[0]['controls']['finish_level']), ('working', '101', None))
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence']),
                         ('paused', 'Paused. Nothing new starts until you resume.'))
        # The level 101 guide was finished; the level 201 guide was not started.
        self.assertEqual(len(self.workers.of('document')), 1)
        self.assertEqual(view['controls'], {'grouped': True, 'finish_level': None, 'finishing': None,
                                            'skip_deck': False})
        self.assertIn('Rolling restarts: level 101 finished; paused as asked on the page', self.log())
        self.refused(root, 'finish-level', 'Only a training that is working can finish its '
                     'level first. This one is paused.')
        resumed = self.engine.act(root, 'resume')
        self.assertEqual((resumed['state'], resumed['review']['phase']), ('waiting', 'final'))
        self.assertEqual(len(self.workers.of('document')), 2)

    def test_a_blueprint_is_for_the_whole_training_so_it_has_no_level_to_finish_first(self):
        # Every level's blueprint is drafted before any level is built, so "finish this
        # level" means nothing there yet, and nothing pauses after the first blueprint.
        refused, seen = [], []

        def tries(tools, job):
            seen.append(self.engine.view(self.space.training('rolling-restarts'))['controls'])
            with self.assertRaisesRegex(WorkspaceError, 'whole training') as caught:
                self.engine.act(self.space.training('rolling-restarts'), 'finish-level')
            refused.append(str(caught.exception))
            return self.workers.blueprint(tools, job)

        self.workers.then('blueprint', tries)
        with mock.patch('studio_core.review_policy.capture',
                        return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start(levels=['101', '201'], materials=['document'])
        self.assertEqual(len(refused), 1)
        self.assertEqual((seen[0]['finish_level'], seen[0]['finishing']), (None, None))
        shown = self.view(root)
        self.assertEqual((shown['state'], shown['review']['phase']), ('waiting', 'final'))
        self.assertEqual(len(self.workers.of('document')), 2)

    def test_finishing_the_only_level_arrives_at_the_wait_without_pausing(self):
        asked = []

        def finishes(tools, job):
            asked.append(self.engine.act(self.space.training('rolling-restarts'), 'finish-level'))
            return self.workers.document(tools, job)

        self.workers.then('document', finishes)
        with mock.patch('studio_core.review_policy.capture',
                        return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start(levels=['101'], materials=['document'])
        self.assertEqual(asked[0]['controls']['finishing'], '101')
        # The final review is the wait: nothing pauses before it, and nothing is left to
        # pause before the index afterwards.
        shown = self.view(root)
        self.assertEqual((shown['state'], shown['review']['phase']), ('waiting', 'final'))
        self.assertEqual(shown['controls'], {'grouped': True, 'finish_level': None, 'finishing': None,
                                             'skip_deck': False})
        self.assertIsNone(self.engine._load(root).get('halt_after'))
        self.assertIn('Rolling restarts: level 101 finished; waiting as asked on the page', self.log())
        shown = self.engine.review_decide(root, shown['review']['expected'], 'approve')
        self.assertEqual(shown['state'], 'done')

    def test_a_step_for_the_whole_training_has_no_level_to_finish_first(self):
        refused = []

        def tries(tools, job):
            with self.assertRaisesRegex(WorkspaceError, 'whole training') as caught:
                self.engine.act(self.space.training('rolling-restarts'), 'finish-level')
            refused.append(str(caught.exception))
            return self.workers.research_plan(tools, job)

        self.workers.then('research-plan', tries)
        root = self.start(levels=['101'])
        self.assertEqual(len(refused), 1)
        self.assertEqual(self.state(root), 'waiting')
        self.assertIsNone(self.engine._load(root).get('halt_after'))

    def test_a_stopped_training_stays_stopped_until_it_is_resumed(self):
        root = self.start()
        stopped = self.engine.act(root, 'stop')
        self.assertEqual((stopped['state'], stopped['sentence']),
                         ('stopped', 'Stopped. Everything finished before it is kept; the '
                                     'step that was in hand starts over on resume.'))
        said = self.decide(root, 'research-plan')
        self.assertEqual(said['said'], 'Approved. This training is not running, so nothing '
                         'more happens until you resume it or try again.')
        self.assertEqual((self.state(root), self.workers.of('question')), ('stopped', []))
        self.assertEqual(workspace.status(root)['artifacts']['research-plan'], 'approved')
        self.refused(root, 'stop', 'This training is stopped, so there is nothing to stop.')
        self.assertEqual(self.engine.act(root, 'resume')['state'], 'waiting')
        self.assertEqual(workspace.status(root)['gate'], 'research')

    def test_a_paused_training_can_be_stopped(self):
        def pauses(tools, job):
            self.engine.act(self.space.training('rolling-restarts'), 'pause')
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', pauses)
        root = self.start()
        self.assertEqual(self.state(root), 'paused')
        self.assertEqual(self.engine.act(root, 'stop')['state'], 'stopped')
        self.assertEqual(self.engine.act(root, 'resume')['state'], 'waiting')

    def test_stopping_ends_a_command_a_step_is_running_and_everything_it_started(self):
        # A step that runs the slides tool or a brand skill runs it as this worker does.
        pids, said = self.base / 'pids', []

        def runs_a_command(tools, job):
            companion.run_command(['sh', '-c', LEAVES, 'sh', str(pids)], None, 60, 'A tool')

        def stops():
            written(pids)
            said.append(self.engine.act(self.space.training('rolling-restarts'), 'stop'))

        self.workers.then('research-plan', runs_a_command)
        stopping = threading.Thread(target=stops)
        stopping.start()
        started = time.monotonic()
        root = self.start()
        stopping.join(10)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(still_running(written(pids)), [])
        view = self.view(root)
        self.assertEqual((said[0]['state'], view['state'], view['sentence'], view['problem']),
                         ('stopped', 'stopped', 'Stopped. Everything finished before it is kept; '
                          'the step that was in hand starts over on resume.', None))
        self.assertEqual(self.engine.act(root, 'resume')['state'], 'waiting')
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')

    def test_a_stop_reaches_the_questions_researched_at_once(self):
        seen = []

        def looks(tools, job):
            seen.append(companion.STOP.get())
            self.workers.question(tools, job)

        self.engine = self.make(at_once=2)
        root = self.start()
        self.workers.then('question', *[looks] * len(FOUR['items']))
        self.decide(root, 'research-plan')
        self.assertEqual(seen, [self.engine._run(root).stop] * len(FOUR['items']))

    def test_a_run_stopped_on_a_problem_can_be_resumed_as_well_as_tried_again(self):
        with mock.patch.object(research, 'locations', return_value=[self.base / 'nowhere']):
            self.engine = self.make(research=research.Research)
            root = self.start()
            self.decide(root, 'research-plan')
        view = self.view(root)
        self.assertEqual((view['state'], view['problem']['action']), ('stopped', 'retry'))
        self.engine.research = lambda: self.research
        after = self.engine.act(root, 'resume')
        self.assertEqual((after['state'], after['problem']), ('waiting', None))
        self.assertEqual(workspace.status(root)['gate'], 'research')

    def test_what_cannot_be_done_as_things_stand_is_refused_in_a_sentence(self):
        root = self.start()
        self.assertEqual(self.state(root), 'waiting')
        self.refused(root, 'pause', 'Only a training that is working can be paused. This one '
                     'is waiting for you.')
        self.refused(root, 'resume', 'This training is not paused or stopped, so there is '
                     'nothing to resume.')
        self.refused(root, 'retry', 'Nothing here failed, so there is nothing to try again.')
        self.refused(root, 'restart', 'A run can be asked to: pause, resume, stop, retry, '
                     'finish-level, more-time.')

        self.workers.then('research-plan', fails(), fails(), fails())
        failed = self.start(title='Health checks')
        self.assertEqual(self.state(failed), 'failed')
        self.refused(failed, 'pause', 'This one is stopped on a problem.')
        self.refused(failed, 'stop', 'This training is stopped on a problem, so there is '
                     'nothing to stop.')
        self.refused(failed, 'resume', 'not paused or stopped')

        self.to_end(root)
        self.assertEqual(self.state(root), 'done')
        for action in ACTIONS:
            with self.subTest(action):
                self.refused(root, action, 'finished as far as the runner takes it|not paused '
                             'or stopped|Nothing here failed')
        elsewhere = self.base / 'elsewhere'
        with self.assertRaisesRegex(WorkspaceError, 'No run is driving this training'):
            self.engine.act(elsewhere, 'pause')
        self.assertIsNone(self.engine.view(elsewhere))
        self.assertIsNone(self.engine.brief(elsewhere))


class RestartTests(StudioCase):
    """The runner ending and starting again: the next step comes from the files."""

    def restart(self, **options):
        self.engine.close()
        self.engine = self.make(**options)
        self.engine.resume()

    def test_a_restart_in_the_middle_of_research_does_only_what_is_left(self):
        def dies(tools, job):
            raise Crash()

        self.engine = self.make(at_once=1)
        root = self.start()
        self.workers.then('question:health-checks', dies)
        with self.assertRaises(Crash):
            self.decide(root, 'research-plan')
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 2, 'pending': 2})
        (root / 'blueprint.md').write_text('# Half made\n')
        (root / research.LOCK).write_text('12345\n')  # a save that never finished
        self.restart(at_once=1)
        self.assertFalse((root / 'blueprint.md').exists(), 'what was half-made is discarded')
        self.assertFalse((root / research.LOCK).exists())
        asked = [kind for kind, _, _ in self.workers.jobs if kind.startswith('question')]
        self.assertEqual(asked, ['question:availability', 'question:instance-min',
                                 'question:health-checks', 'question:health-checks',
                                 'question:zero-downtime'])
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'research'))
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_a_finding_that_was_not_committed_is_researched_again(self):
        real = gitstate.commit

        def dying(space, message, paths=None):
            if message.endswith('keep the finding for instance-min'):
                raise Crash()
            return real(space, message, paths)

        self.engine = self.make(at_once=1)
        root = self.start()
        with mock.patch.object(gitstate, 'commit', dying):
            with self.assertRaises(Crash):
                self.decide(root, 'research-plan')
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 2, 'pending': 2})
        self.assertNotEqual(self.git('status', '--porcelain'), '')
        self.restart(at_once=1)
        self.assertEqual((len(self.workers.of('question:availability')),
                          len(self.workers.of('question:instance-min'))), (1, 2))
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'research'))
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.log().count('Rolling restarts: keep the finding for '
                                          'instance-min'), 1)

    def test_a_restart_at_a_gate_waits_there_and_leaves_what_a_person_changed(self):
        root = self.start()
        plan = root / pipeline.PLAN
        plan.write_text(plan.read_text().replace('What starts the next batch?',
                                                 'What decides when the next batch starts?'))
        self.restart()
        self.assertIn('What decides when the next batch starts?', plan.read_text())
        self.assertEqual((self.state(root), len(self.workers.jobs)), ('waiting', 1))
        self.decide(root, 'research-plan')
        self.assertEqual(workspace.status(root)['gate'], 'research')

    def test_a_restart_respects_a_pause_a_question_and_a_failure(self):
        self.workers.then('research-plan', asks('Which platform?'))
        asking = self.start()
        failing = self.start(title='Health checks')
        self.workers.then('blueprint', fails(), fails(), fails())
        self.to_gate(failing, 'research')
        self.decide(failing, 'research')
        def pauses(tools, job):
            self.engine.act(self.space.training('blue-green-deploys'), 'pause')
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', pauses)
        paused = self.start(title='Blue green deploys')
        stopped = self.start(title='Canary releases')
        self.engine.act(stopped, 'stop')
        self.decide(stopped, 'research-plan')
        jobs = len(self.workers.jobs)
        self.restart()
        self.assertEqual([self.state(root) for root in (asking, failing, paused, stopped)],
                         ['waiting', 'failed', 'paused', 'stopped'])
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.view(asking)['question']['text'], 'Which platform?')

    def test_a_training_someone_else_added_to_the_workspace_becomes_known_here(self):
        root = self.start()
        home.registry_path().unlink()
        self.restart()
        self.assertEqual([entry['path'] for entry in home.trainings()], [str(root)])

    def test_a_run_that_is_done_is_left_alone(self):
        root = self.start()
        self.to_end(root)
        (root / 'notes.md').write_text('# Notes someone keeps beside the training\n')
        jobs = len(self.workers.jobs)
        self.restart()
        self.assertTrue((root / 'notes.md').exists())
        self.assertEqual((self.state(root), len(self.workers.jobs)), ('done', jobs))

    def test_what_a_person_changed_while_no_step_was_in_hand_is_never_discarded(self):
        root = self.start()
        self.to_end(root)
        guide = root / 'document.md'
        guide.write_text(guide.read_text() + '\nA line its person added by hand.\n')
        self.assertFalse((root / self.engines.IN_HAND).exists())
        self.restart()
        self.assertIn('A line its person added by hand.', guide.read_text())
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'document'), 'their change is put to them')

    def test_only_a_step_the_runner_ended_in_the_middle_of_is_discarded(self):
        seen = []

        def dies(tools, job):
            seen.append((root / self.engines.IN_HAND).read_text())
            raise Crash()

        root = self.start()
        self.to_gate(root, 'blueprint')
        self.workers.then('document', dies)
        with self.assertRaises(Crash):
            self.decide(root, 'blueprint')
        self.assertEqual(seen, ['document\n'])
        (root / 'document.md').write_text('# Half made\n')
        self.assertEqual(self.git('status', '--porcelain', '--', str(root)),
                         '?? trainings/rolling-restarts/document.md',
                         'the note that a step is in hand is never shared')
        self.restart()
        self.assertFalse((root / self.engines.IN_HAND).exists())
        self.assertEqual((workspace.status(root)['gate'], len(self.workers.of('document'))),
                         ('document', 2))
        self.assertNotIn('Half made', (root / 'document.md').read_text())


class SharingTests(StudioCase):
    """A workspace whose repository is shared: a bare repository stands in for the team's."""

    def set_up(self):
        self.remote = self.base / 'team-repo.git'
        self.remote.mkdir()
        self.git('init', '--quiet', '--bare', repo=self.remote)
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main', repo=self.remote)
        return self.gitstate.join(str(self.remote))

    def shared(self) -> list[str]:
        """What the team's repository has been sent, newest first."""
        if not self.git('for-each-ref', 'refs/heads/main', repo=self.remote):
            return []
        return self.git('log', '--format=%s', 'main', repo=self.remote).splitlines()

    def test_work_is_shared_after_each_decision(self):
        root = self.start()
        self.assertEqual(self.shared()[0], 'Rolling restarts: start the training from the form',
                         'who drives a training is shared before any work is done for it')
        self.decide(root, 'research-plan')
        self.assertEqual(self.shared()[0],
                         'Rolling restarts: The research plan was approved on the page.')
        self.assertEqual(workspace.status(root)['gate'], 'research')
        self.assertEqual(self.engine.shared(), {'shared': False, 'notice': None},
                         'what the run did after the decision waits for the next one')
        self.assertEqual(self.engine.share(), {'shared': True, 'notice': None})
        self.assertEqual(self.shared()[0],
                         'Rolling restarts: ask for a review of the research report')
        self.assertEqual(self.engine.shared(), {'shared': True, 'notice': None})

    def test_the_last_thing_the_runner_does_is_shared_without_another_decision(self):
        root = self.start()
        self.to_end(root)
        self.assertEqual(self.state(root), 'done')
        self.assertEqual(self.shared()[0],
                         'Rolling restarts: write the index; the training is finished')
        self.assertEqual(self.engine.shared(), {'shared': True, 'notice': None})

    def test_a_repository_that_cannot_be_reached_never_holds_a_run_up(self):
        root = self.start()
        self.remote.rename(self.base / 'moved-away.git')
        self.decide(root, 'research-plan')
        self.assertEqual((self.state(root), workspace.status(root)['gate']),
                         ('waiting', 'research'))
        found = self.engine.shared()
        self.assertFalse(found['shared'])
        self.assertIn('could not be reached', found['notice'])
        self.assertIn('is not shared yet', found['notice'])
        self.assertEqual(self.engine.share()['shared'], False)

    def test_sharing_only_when_asked(self):
        self.gitstate.share_when('asked')
        root = self.start()
        self.decide(root, 'research-plan')
        self.assertEqual(self.shared()[0], 'Rolling restarts: start the training from the form',
                         'only the claim that starts a training is sent without being asked')
        self.assertEqual(self.engine.shared(), {'shared': False, 'notice': None})
        self.assertEqual(self.engine.share(), {'shared': True, 'notice': None})
        self.assertIn('Rolling restarts: The research plan was approved on the page.',
                      self.shared())
        self.assertEqual(self.engine.shared(), {'shared': True, 'notice': None})

    def test_a_workspace_with_no_remote_has_nowhere_to_share_to(self):
        self.gitstate.local(self.base / 'alone')
        self.assertEqual(self.engine.shared(), {'shared': False, 'notice': None})
        found = self.engine.share()
        self.assertEqual(found['shared'], False)
        self.assertIn('no shared repository', found['notice'])


class LiveTests(StudioCase):
    """The engine on threads of its own, as the runner serves it."""

    BACKGROUND = True

    def until(self, check, seconds: float = 30):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            found = check()
            if found:
                return found
            time.sleep(0.02)
        self.fail('It did not happen in time.')

    def held(self, act):
        """A worker that does its work, then waits to be let go."""
        entered, go = threading.Event(), threading.Event()
        self.addCleanup(go.set)

        def script(tools, job):
            returned = act(tools, job)
            entered.set()
            go.wait(30)
            return returned
        return script, entered, go

    def test_what_a_worker_is_doing_is_shown_while_it_works(self):
        script, entered, go = self.held(self.workers.research_plan)
        self.workers.then('research-plan', script)
        root = self.start()
        self.assertTrue(entered.wait(30))
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence']),
                         ('working', 'Drafting the research plan.'))
        worker, = view['workers']
        self.assertEqual((worker['id'], worker['label']),
                         ('research-plan', 'Drafting the research plan'))
        self.assertRegex(worker['started_at'], r'^\d{4}-\d\d-\d\dT')
        self.assertEqual(worker['lines'], ['Handing back research-plan',
                                           'The draft was accepted',
                                           'Writing its own notes on the draft'])
        self.assertEqual(self.steps(root)['research-plan']['status'], 'working')
        self.assertEqual(self.engine.brief(root)['needs'], False)
        # The worker's start is the run's last activity, until a try begins or ends later.
        self.assertEqual(self.engine.brief(root)['busy_since'], worker['started_at'])
        from runner import page
        listed = {item['path']: item for item in page.RunnerPage(8765, self.engine).trainings()}
        self.assertEqual(listed[str(root)]['activity_at'], worker['started_at'])
        go.set()
        self.until(lambda: self.state(root) == 'waiting')
        self.assertEqual(self.view(root)['workers'], [])
        self.assertIsNone(self.engine.brief(root)['busy_since'])

    def test_only_so_many_trainings_work_at_once(self):
        settings.save(replace(settings.load(), parallel=1))
        script, entered, go = self.held(self.workers.research_plan)
        self.workers.then('research-plan', script)
        first = self.start()
        self.assertTrue(entered.wait(30))
        second = self.start(title='Health checks')
        self.until(lambda: self.view(second)['sentence'].startswith('Waiting for its turn'))
        time.sleep(0.3)
        view = self.view(second)
        self.assertEqual((view['state'], view['sentence'], view['workers'],
                          len(self.workers.jobs)),
                         ('working', 'Waiting for its turn. It is next.',
                          [], 1))
        go.set()
        self.until(lambda: self.state(first) == self.state(second) == 'waiting')
        self.assertEqual(len(self.workers.jobs), 2)

    def test_research_questions_are_worked_on_several_at_a_time(self):
        self.engine = self.make(at_once=2)
        lock, live, most = threading.Lock(), [0], [0]

        def counted(tools, job):
            with lock:
                live[0] += 1
                most[0] = max(most[0], live[0])
            time.sleep(0.2)
            self.workers.question(tools, job)
            with lock:
                live[0] -= 1

        self.workers.then('question', *[counted] * 4)
        root = self.start()
        self.until(lambda: self.state(root) == 'waiting')
        self.decide(root, 'research-plan')
        self.until(lambda: workspace.status(root)['gate'] == 'research')
        self.assertEqual((most[0], len(self.workers.of('question'))), (2, 4))
        self.assertEqual(workspace.status(root)['research']['findings'],
                         {'supported': 3, 'contradicted': 1})

    def test_after_a_decision_the_page_is_told_what_the_runner_does_next(self):
        root = self.start()
        self.until(lambda: self.state(root) == 'waiting')
        script, entered, go = self.held(self.workers.question)
        self.workers.then('question', script)
        said = self.decide(root, 'research-plan')
        self.assertEqual(said['said'], 'Approved. Researching the questions now. You can '
                         'close this page; it says when it needs you again.')
        self.assertTrue(entered.wait(30))
        go.set()
        self.until(lambda: workspace.status(root)['gate'] == 'research')
        script, entered, go = self.held(self.workers.blueprint)
        self.workers.then('blueprint', script)
        said = self.decide(root, 'research')
        self.assertEqual(said['said'], 'Approved. Drafting the blueprint now. You can close '
                         'this page; it says when it needs you again.')
        go.set()
        self.until(lambda: workspace.status(root)['gate'] == 'blueprint')
        script, entered, go = self.held(self.workers.blueprint)
        self.workers.then('blueprint', script)
        said = self.decide(root, 'blueprint', 'revise', 'Make the example a database.')
        self.assertEqual(said['said'], 'Your changes are noted. Once they are made, the new '
                         'version comes back here for your review. Drafting the blueprint now. '
                         'You can close this page; it says when it needs you again.')
        go.set()
        self.until(lambda: workspace.status(root)['gate'] == 'blueprint')

    def test_stopping_ends_the_step_in_hand_and_keeps_nothing_from_it(self):
        script, entered, go = self.held(self.workers.research_plan)
        self.workers.then('research-plan', script)
        root = self.start()
        self.assertTrue(entered.wait(30))
        self.assertFalse(self.engine._run(root).stop.is_set())
        stopped = self.engine.act(root, 'stop')
        self.assertEqual(stopped['state'], 'stopped')
        self.assertTrue(self.engine._run(root).stop.is_set())
        go.set()
        self.until(lambda: self.record(root)['steps'].get('research-plan'))
        self.until(lambda: self.engine._run(root).thread is None)
        self.assertEqual(self.record(root)['steps']['research-plan']['attempts'][0]['outcome'],
                         'stopped')
        self.assertFalse((root / pipeline.PLAN).exists())
        self.assertEqual((self.state(root), self.git('status', '--porcelain')),
                         ('stopped', ''))
        self.engine.act(root, 'resume')
        self.until(lambda: self.state(root) == 'waiting')
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')

    def test_pausing_lets_the_step_in_hand_finish_and_keeps_it(self):
        script, entered, go = self.held(self.workers.research_plan)
        self.workers.then('research-plan', script)
        root = self.start()
        self.assertTrue(entered.wait(30))
        paused = self.engine.act(root, 'pause')
        self.assertEqual((paused['state'], paused['sentence']),
                         ('paused', 'Pausing. The step in hand finishes first.'))
        go.set()
        self.until(lambda: self.engine._run(root).thread is None)
        self.assertEqual(workspace.status(root)['artifacts']['research-plan'], 'draft')
        self.assertIsNone(workspace.status(root)['gate'], 'no gate is set while it is paused')
        self.engine.act(root, 'resume')
        self.until(lambda: workspace.status(root)['gate'] == 'research-plan')

    def test_closing_the_runner_ends_its_workers(self):
        script, entered, go = self.held(lambda tools, job: None)
        self.workers.then('research-plan', script)
        root = self.start()
        self.assertTrue(entered.wait(30))
        closing = threading.Thread(target=self.engine.close)
        closing.start()
        self.until(lambda: self.engine._run(root).stop.is_set())
        go.set()
        closing.join(30)
        self.assertFalse(closing.is_alive())
        self.assertIsNone(self.engine._run(root).thread)
        self.engine.wake(root)
        self.assertIsNone(self.engine._run(root).thread, 'a closed engine starts nothing')


class OutcomeTests(StudioCase):
    def test_a_draft_accepted_before_the_agent_gave_out_is_still_kept(self):
        def gives_out(tools, job):
            self.workers.research_plan(tools, job)
            return Outcome(False, 'timeout', SLOW, cost=0.1)

        self.workers.then('research-plan', gives_out)
        root = self.start()
        self.assertEqual((self.state(root), self.steps(root)['research-plan']['attempts']),
                         ('waiting', 1))
        self.assertEqual(self.view(root)['spent']['dollars'], 0.1)


if __name__ == '__main__':
    import unittest
    unittest.main()


class ModelProfileTests(StudioCase):
    def configure(self, agent='claude'):
        from studio_core import studios_config
        studios_config.update({'assistant': {'agent': agent}, 'models': {
            'schema': 1, 'agent': agent, 'mode': 'by_task', 'profiles': {
                'main': {'selection': 'explicit', 'model': 'main-model', 'effort': 'medium'},
                'complex': {'selection': 'explicit', 'model': 'complex-model', 'effort': 'high'}}}})

    def test_new_training_saves_profiles_and_research_uses_saved_main(self):
        from studio_core import studios_config
        self.configure()
        from runner import setup
        self.assertEqual(setup.describe(self.engine)['shared']['models']['mode'], 'by_task')
        root = self.start()
        saved = self.record(root)['model_profiles']
        studios_config.update({'models': {'profiles': {'main': {'model': 'later'}}}})
        self.decide(root, 'research-plan')
        self.assertEqual(self.record(root)['model_profiles'], saved)
        choices = self.record(root)['model_jobs']
        self.assertTrue(any(c['step'].startswith('research:') for c in choices))
        self.assertTrue(all(c['model'] == 'main-model' for c in choices))
        for kind, job, spec in self.workers.jobs:
            self.assertEqual((job.model, job.effort), ('main-model', 'medium'))
            self.assertEqual(job.profile, 'research' if kind.startswith('question:') else 'write')

    def test_codex_and_explicit_work_override(self):
        self.configure('codex')
        root = self.start(title='By task')
        self.assertEqual(self.record(root)['model_profiles']['mode'], 'by_task')
        other = self.start(title='Work override', agent='codex', model='own-model', effort='high')
        self.assertEqual(self.record(other)['model_profiles']['mode'], 'single')
        self.assertEqual(self.workers.jobs[-1][1].model, 'own-model')


class FormPlanTests(StudioCase):
    def test_a_requested_revision_changes_a_plan_written_from_the_form(self):
        from studio_core import research_contract
        with mock.patch.object(research_contract, 'snapshot', return_value={'schema': 2}):
            root = self.start(source_scope='supplied-only', research_questions=['Why?'])
        self.send(root, 'synthetic.md')
        self.engine.supply(root, 'done')
        original = json.loads((root / pipeline.PLAN).read_text())
        revised = json.loads(json.dumps(original))
        revised['items'][0]['question'] = 'What does the source say about capacity?'
        self.workers.plan = revised
        self.decide(root, 'research-plan', 'revise',
                    'Replace Why? with What does the source say about capacity?')
        kept = json.loads((root / pipeline.PLAN).read_text())
        self.assertEqual(kept['items'], revised['items'])
        self.assertEqual(kept['scope'], 'supplied-only')
        self.assertEqual(kept['sources'], self.engine.documents.sources(root)[0])
        self.assertEqual(len(self.workers.of('research-plan')), 1)
        task = self.workers.of('research-plan')[0].task
        self.assertIn('Replace Why? with What does the source say about capacity?', task)
        self.assertIn('only the documents the person supplied', task)
        self.assertNotIn('Keep each in the plan, in their words', task)
        self.assertEqual(self.record(root)['research']['plan_from'], 'assistant')
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')

    def test_a_documents_only_training_writes_its_plan_from_the_form(self):
        from studio_core import research_contract
        with mock.patch.object(research_contract, 'snapshot', return_value={'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}):
            root = self.start(source_scope='supplied-only', research_questions=['Why?', 'What next?'])
        self.send(root, 'synthetic.md')
        shown = self.engine.supply(root, 'done')
        plan = json.loads((root / pipeline.PLAN).read_text())
        self.assertEqual([i['question'] for i in plan['items']], ['Why?', 'What next?'])
        self.assertTrue(all(i['public_query'] is None for i in plan['items']))
        self.assertEqual(workspace.statuses(root, workspace.load(root))['research-plan'], 'draft')
        self.assertEqual(self.workers.of('research-plan'), [])
        self.assertEqual(workspace.status(root)['gate'], 'research-plan')

    def test_a_public_web_training_still_drafts_its_plan(self):
        root = self.start(research_questions=['Why now?'])
        self.assertEqual(len(self.workers.of('research-plan')), 1)
        self.assertIn('Why now?', self.workers.of('research-plan')[0].task)


class ResearchAccountTests(StudioCase):
    def test_the_research_review_line_names_the_check_not_a_digest(self):
        from synthesis_fixture import research_stop
        from studio_core import research_contract, research_view
        from types import SimpleNamespace
        import desk
        root = self.start(); self.to_gate(root, 'research')
        research_stop(root / research_contract.CASE / 'research')
        record = self.engine._load(root); record['research_contract'] = {'schema': 2}
        self.engine._store(root, record)
        tool = SimpleNamespace(_json=lambda *a: {'status': 'complete'})
        with mock.patch.object(research_contract, 'matching', return_value=tool):
            step = next(s for s in pipeline.steps([]) if s.id == 'research-report')
            self.engine._report(root, step)
        note = desk.latest_review(root, 'research')
        self.assertIn(research_view.CHECKED + ' An honest account.', note)
        self.assertNotIn('Digest', note)
        self.assertNotIn('synthetic-digest', note)


class ResearchPriceTests(StudioCase):
    def test_a_research_change_is_priced_with_what_it_makes_again(self):
        root = self.start(levels=['101', '201'])
        record = self.engine._load(root); record['research_contract'] = {'schema': 2}
        self.engine._store(root, record)
        session = workspace.load(root)
        for name in ['blueprint@101', 'document@101', 'blueprint@201', 'document@201']:
            workspace.write_atomic(root / workspace.artifact(root, session, name)['file'], b'# Synthetic document\n')
        found = self.engine.research_price(root)
        self.assertTrue(found['words'].endswith('Then it makes again: the level 101 blueprint, the level 101 learner guide, the level 201 blueprint and the level 201 learner guide.'))
