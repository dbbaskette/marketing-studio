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
SLOW = 'It did not finish in 1350 seconds, so it was stopped.'
STEPS = ['intake', 'research-plan', 'gate:research-plan', 'research-start', 'research',
         'research-report', 'gate:research', 'blueprint', 'gate:blueprint', 'document',
         'gate:document', 'brief', 'gate:brief', 'package']


class Crash(BaseException):
    """The runner's process ending in the middle of something."""


class WhereThisTrainingStopsTests(StudioCase):
    """Retired form choices cannot change the saved shared review setting."""

    def test_old_review_fields_refuse_without_writing(self):
        from runner import studios_config
        studios_config.update({'review': {'level': 'balanced'}})
        before = (self.base / 'studios.json').read_bytes()
        for field in ('review_level', 'review_seen', 'review_default'):
            with self.subTest(field=field), self.assertRaisesRegex(WorkspaceError, 'review'):
                self.start(**{field: 'automatic'})
        self.assertEqual((self.base / 'studios.json').read_bytes(), before)
        self.assertEqual(self.engine.trainings(), [])

class SynthesisAtStartTests(StudioCase):
    """A training is not started on a Harness Research that cannot synthesize: the start is
    refused with nothing made. A training brought in from a conversation is not a start, and
    is not refused. Matrix row 137."""

    def setUp(self):
        super().setUp()
        from stand_ins.research import saved_queue
        self.research = saved_queue()

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
            self.start()
        self.assertEqual(str(caught.exception), self.engines.NO_SYNTHESIS)
        self.assertEqual(self.made(), before, 'nothing is made')
        # A read error is refused the same way, with a real-looking Harness Research found.
        from stand_ins import research as research_stand_in
        from studio_core import research_contract
        runtime = self.base / 'harness-research'
        (runtime / 'scripts' / 'lib').mkdir(parents=True)
        (runtime / 'package.json').write_text('{"version": "1.0.0"}\n', encoding='utf-8')
        (runtime / 'scripts' / 'lib' / 'synthesis-cli.mjs').write_text('', encoding='utf-8')
        self.research = research.Research(runtime=runtime, run=research_stand_in.SavedQueueStandIn())
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

    def test_inventory_reports_unresolved_candidates_without_writing(self):
        missing = self.base / 'missing-inventory-folder'
        said = self.engine.saved_work(folders=(missing,))
        self.assertFalse(said['complete'])
        self.assertEqual(said['unused'], [])
        self.assertFalse(missing.exists())
        self.assertTrue(any(entry['path'] == str(missing) for entry in said['issues']))

    def test_inventory_does_not_follow_linked_candidates(self):
        target = self.base / 'inventory-target'
        target.mkdir()
        linked = self.space.root / 'inventory-link'
        linked.symlink_to(target, target_is_directory=True)
        said = self.engine.saved_work()
        self.assertFalse(said['complete'])
        self.assertEqual(said['unused'], [])

    def test_inventory_reports_corrupt_or_unsupported_records(self):
        folder = self.space.root / 'inventory-broken'
        folder.mkdir()
        record = folder / '.training-studio/run.json'
        record.parent.mkdir(parents=True, exist_ok=True)
        for content in ('{', '{"schema": 999}'):
            record.write_text(content)
            said = self.engine.saved_work()
            self.assertFalse(said['complete'])
            self.assertEqual(said['unused'], [])
            self.assertEqual(record.read_text(), content)

    def test_registered_missing_training_is_not_filtered_out(self):
        missing = self.base / 'remembered-missing'
        home.write_json(home.registry_path(), {'schema': 1, 'trainings': {str(missing): {}}})
        before = home.registry_path().read_bytes()
        said = self.engine.saved_work()
        self.assertFalse(said['complete'])
        self.assertEqual(said['unused'], [])
        self.assertTrue(any(entry['path'] == str(missing) for entry in said['issues']))
        self.assertEqual(home.registry_path().read_bytes(), before)
        self.assertFalse(missing.exists())

    def test_invalid_configured_scope_stays_unknown_with_explicit_folder(self):
        for content in ('{', '{"schema": 999}'):
            gitstate.settings_path().write_text(content)
            said = self.engine.saved_work(folders=(self.base,))
            self.assertFalse(said['complete'])
            self.assertEqual(said['unused'], [])
            self.assertTrue(any(entry['path'] == str(gitstate.settings_path())
                                for entry in said['issues']))
            self.assertEqual(gitstate.settings_path().read_text(), content)

    def test_missing_workspace_marker_stays_unknown_with_explicit_folder(self):
        (self.space.root / gitstate.MARKER).unlink()
        said = self.engine.saved_work(folders=(self.base,))
        self.assertFalse(said['complete'])
        self.assertEqual(said['unused'], [])
        self.assertTrue(any(entry['path'] == str(self.space.root / gitstate.MARKER)
                            for entry in said['issues']))

    def test_session_only_conversation_training_needs_gated_flow(self):
        root = self.chat()
        said = self.engine.saved_work()
        self.assertIn(str(root), self.needed(said, 'gated-flow'))
        self.assertEqual(next(entry['status'] for entry in said['paths']
                              if entry['id'] == 'gated-flow'), 'needed')

    def test_inventory_excludes_session_and_material_links_before_reading(self):
        for conversation in (False, True):
            for linked in ('session', 'material', 'dangling-run'):
                with self.subTest(conversation=conversation, linked=linked):
                    root = self.chat(f'linked-chat-{linked}') if conversation else self.saved(f'linked-run-{linked}')
                    outside = self.base / f'outside-{conversation}-{linked}'
                    outside.mkdir()
                    if linked == 'session':
                        session = root / workspace.STATE_DIR / 'session.json'
                        target = outside / 'session.json'
                        target.write_bytes(session.read_bytes())
                        session.unlink()
                        session.symlink_to(target)
                    elif linked == 'material':
                        (outside / 'report.md').write_text('Synthetic private material')
                        material = root / 'research'
                        if material.exists():
                            import shutil
                            shutil.rmtree(material)
                        material.symlink_to(outside, target_is_directory=True)
                    else:
                        run = root / '.training-studio/run.json'
                        run.unlink(missing_ok=True)
                        run.symlink_to(outside / 'missing.json')
                    before = {path: path.read_bytes() for path in outside.iterdir() if path.is_file()}
                    original = Path.read_text
                    def guarded(path, *args, **kwargs):
                        if path.resolve().is_relative_to(outside.resolve()):
                            raise AssertionError('Inventory read excluded bytes')
                        return original(path, *args, **kwargs)
                    original_load = workspace.load
                    def guarded_load(folder):
                        if folder == root:
                            raise AssertionError('Linked candidate reached a material reader')
                        return original_load(folder)
                    with mock.patch.object(Path, 'read_text', guarded), \
                            mock.patch.object(workspace, 'load', guarded_load):
                        said = self.engine.saved_work()
                    self.assertFalse(said['complete'])
                    self.assertEqual(said['unused'], [])
                    self.assertTrue(any(entry['path'] == str(root) for entry in said['issues']))
                    self.assertEqual({path: path.read_bytes() for path in outside.iterdir() if path.is_file()}, before)

    QUEUE = 'Its research has not run, and it was started before Harness Research could synthesize.'
    CHAT = 'A conversation training whose research has not started.'
    LAYOUT = 'It began before the current review layout, and its final review is still to come.'

    def needed(self, said, ident):
        return {entry['path']: entry['why'] for entry in
                next(found for found in said['paths'] if found['id'] == ident)['needed_by']}

    # Saved trainings the earlier flow left at their research plan or before research ran,
    # each a stored copy (saved_fixtures.py); a test takes the next one for each it needs.
    STORED = ('research-plan-gate', 'question-before-plan', 'failure-before-plan',
              'research-gate')

    def saved(self, title, **changes):
        """A saved training begun on the legacy queue whose research has not run (a stored
        copy; `title` names it in the test only), its run record then changed as `changes`
        says: a value of None takes the key out."""
        import saved_fixtures
        taken = self.__dict__.setdefault('taken', [])
        state = next(name for name in self.STORED if name not in taken)
        taken.append(state)
        return self.changed(saved_fixtures.load(self, state), **changes)

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
        survey = self.engine._survey_files
        return mock.patch.object(self.engine, '_survey_files', lambda root, record: replace(
            survey(root, record), done=survey(root, record).done | set(steps)))

    def test_nothing_is_run_or_asked_online_to_answer(self):
        # Seeing what this computer has for a deck runs the slides tool and the brand skill,
        # and may ask Google Drive; the answer needs only the files.
        waiting = self.saved('Waiting training')
        asked = mock.Mock(side_effect=AssertionError('the computer was looked at'))
        with mock.patch.object(pipeline, 'wanted', lambda found: {'deck'}), \
                mock.patch.object(self.engine, 'deck_needs', asked):
            with self.assertRaises(AssertionError):
                self.engine._survey(waiting, self.engine._load(waiting))
            said = self.engine.saved_work()
        self.assertEqual(self.needed(said, 'research-queue'), {str(waiting): self.QUEUE})
        asked.assert_called_once()

    def test_a_run_begun_on_the_queue_needs_it_until_its_research_has_run(self):
        waiting = self.saved('Waiting training')
        said = self.engine.saved_work()
        self.assertEqual(self.needed(said, 'research-queue'), {str(waiting): self.QUEUE})
        self.assertEqual(said['paths'][0]['needed_by'][0]['title'], 'Stop research-plan')
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
                         ['research-queue', 'review-layout-1', 'old-harness-slides', 'gated-flow'])
        self.assertEqual(said['unused'], [])
        self.assertFalse(said['complete'])
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


class RedoTests(StudioCase):
    """Ask for changes says, before it is sent, what it writes again and what that took."""

    def test_a_change_request_says_what_it_writes_again(self):
        self.pause_after('blueprint')
        root = self.start()
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

    def test_every_kept_step_and_every_decision_is_a_commit_that_says_what_happened(self):
        (self.space.repo / 'README.md').write_text('# Another tool keeps this\n')
        (self.space.repo / 'notes.txt').write_text('Staged by someone else.\n')
        self.git('add', 'notes.txt')
        self.engine = self.make(at_once=1)
        root = self.start()
        self.to_end(root)
        self.all_ready(root)
        self.assertEqual(self.log(), ['Set up the Training Studio workspace in trainings/'] + [
            f'Rolling restarts: {what}' for what in (
                'start the training from the form',
                'keep the research plan',
                'continue the research plan on the desk',
                'hand the approved questions to research',
                'record independent research job: author',
                'record independent research job: review',
                'complete independent research review',
                'keep the reviewed research bundle',
                'continue the research report on the desk',
                'keep the blueprint',
                'continue the blueprint on the desk',
                'keep the learner guide',
                'continue the learner guide on the desk',
                'keep the brief',
                'continue the brief on the desk',
                'keep the practice scenario',
                'continue the practice scenario on the desk',
                'mark every material ready',
                'write the index; the training is finished')])
        self.assertEqual(self.git('status', '--porcelain'), 'A  notes.txt\n?? README.md'.strip())
        changed = self.git('log', '--format=', '--name-only').split()
        self.assertTrue(changed)
        self.assertEqual({name.split('/')[0] for name in changed}, {'trainings'})
        self.assertNotIn('sources', {part for name in changed for part in name.split('/')})
        self.assertTrue(any((root / 'sources').iterdir()))
        self.assertEqual(self.git('log', '-1', '--format=%an <%ae>'),
                         'Alex <alex@example.com>')

    def test_the_run_record_holds_what_the_files_cannot_say_and_is_committed(self):
        settings.save(replace(settings.load(), model='a-model', effort='high',
                              step_seconds=300))
        self.workers.cost = 0.25
        self.pause_after('research-plan')
        root = self.start()
        record = self.record(root)
        self.assertEqual((record['agent'], record['model'], record['effort'],
                          record['limits']),
                         ('claude', 'a-model', 'high',
                          {'step_seconds': 300}))
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
                         ({'dollars': 0.25, 'tokens': 1200}, 'a-model', 'high'))
        step = self.steps(root)['research-plan']
        self.assertEqual((step['attempts'], step['seconds'], step['dollars'], step['kind'],
                          step['label']), (1, 1.5, 0.25, 'agent', 'Draft the research plan'))
        self.assertEqual((self.steps(root)['gate:research-plan']['kind'],
                          self.steps(root)['intake']['kind']), ('gate', 'code'))

    def test_the_agent_is_chosen_when_the_training_starts_and_does_not_change(self):
        other = type(self.workers)()
        self.engine.adapters['codex'] = agents.Scripted(other)
        self.pause_after('research-plan', workers=other)
        root = self.start(agent='codex', model='their-model', effort='ultra')
        self.assertEqual((self.view(root)['agent'], self.view(root)['model'],
                          self.view(root)['effort']), ('codex', 'their-model', 'ultra'))
        settings.save(replace(settings.load(), agent='claude', model='another',
                              effort='low'))
        self.pause_after('blueprint', workers=other)
        self.engine.act(root, 'resume')
        self.assertEqual((len(other.jobs), len(self.workers.jobs)), (4, 0))
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
        note()
        self.assertEqual(self.state(root), 'failed')
        said += [path.read_text() for path in sorted((root / 'reviews').glob('*.md'))]
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
        self.workers.then('research-result', *[looking(self.workers.research_result)] * 2)
        self.workers.then('blueprint', looking(self.workers.blueprint))
        self.pause_after('blueprint')
        root = self.start()
        profiles = [(kind.partition(':')[0], job.profile, spec['fetch'], spec['ask'])
                    for kind, job, spec in self.workers.jobs]
        self.assertEqual(profiles, [('research-plan', 'write', False, True),
                                    ('research-result', 'research', True, False),
                                    ('research-result', 'write', False, False),
                                    ('blueprint', 'write', False, True)])
        for kind, job, spec in self.workers.jobs:
            self.assertEqual(list(job.tools), worker_tools.command(job.folder))
            self.assertEqual(job.folder.parent, agents.staging())
            self.assertNotIn(self.space.repo, job.folder.parents)
            self.assertEqual(job.limits, agents.Limits(seconds=None))
        for folder, held in seen:
            self.assertIn(held, (['inputs', 'job.json', 'sources'], ['job.json', 'sources']))
            self.assertFalse(folder.exists(), 'a job folder is removed once its work is kept')
        self.assertEqual(len({folder for folder, _ in seen}), 4)

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
                                        + pipeline.RESEARCH_USE), text[:200])
        self.assertNotIn('Cite stable finding IDs', text)
        self.assertNotIn(research_contract.HANDOFF, text)
        for told in ('local configuration', 'hypothetical exercise assumptions',
                     'teach the check or conditional decision', 'omit the dependent claim'):
            self.assertIn(told, text)
        self.assertIn('# Prioritized handoff', text)

    def test_the_checks_warnings_reach_a_writer_as_notes_and_not_as_orders(self):
        from synthesis_fixture import research_stop
        root = self.start()
        research_stop(root / 'research')
        brief = root / 'research/brief.md'
        head, _, rest = brief.read_text().partition('\n\n')
        brief.write_text(head + '\n\n> Preserve the automatic warnings below and do not reuse '
                         'excluded claims.\n\n> Training Studio’s automatic review included '
                         'with warning: Two documents disagree.\n\n' + rest)
        record = {'schema': 2, 'digest': 'synthetic-digest', 'findings': [], 'facts': [],
                  'sources': [], 'creator_review': {'by': 'assistant', 'choices': {
                      'assessment:coverage': 'include', 'assessment:usefulness': 'include',
                      'findings:section-one': 'include', 'facts:f-1': 'include-plain'},
                      'notes': {'assessment:coverage': 'Two documents disagree.',
                                'assessment:usefulness': 'Two documents disagree.',
                                'findings:section-one': 'The table says three engines.',
                                'facts:f-1': 'A point of wording.'}}}
        with mock.patch.object(pipeline.workspace, 'research_record', return_value=record):
            text = pipeline.findings_text(root)
        self.assertNotIn('> ', text)
        self.assertNotIn('Preserve the automatic warnings', text)
        self.assertIn('# Prioritized handoff', text)
        notes = text[text.index('## The check\'s notes on this research'):]
        self.assertIn('teach its condition, put it in instructor preflight, or omit the dependent claim',
                      notes)
        self.assertEqual(notes.count('Two documents disagree.'), 1)
        self.assertIn('- findings:section-one: The table says three engines.', notes)
        self.assertNotIn('A point of wording.', notes)


class RetryTests(StudioCase):
    def test_a_draft_the_checks_refuse_is_fixed_by_the_worker_and_then_kept(self):
        def careless(tools, job):
            first = tools.submit_artifact('research-plan', json.dumps(
                {'topic': 'Rolling restarts', 'items': [{'id': 'Not An ID', 'question': ''}]}))
            assert not first[0] and 'needs an "id"' in first[1], first
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', careless)
        self.pause_after('research-plan')
        root = self.start()
        step = self.steps(root)['research-plan']
        self.assertEqual((self.state(root), step['status'], step['attempts'], step['error']),
                         ('paused', 'done', 1, None))
        kept = json.loads((root / pipeline.PLAN).read_text())
        self.assertEqual(([item['id'] for item in kept['items']], kept['scope'],
                          kept['purpose']), (list(QUESTIONS), 'public-web', 'planning'))

    def test_a_try_that_hands_nothing_back_is_made_again_with_the_reason(self):
        def never_right(tools, job):
            tools.submit_artifact('research-plan', '{"topic": "Rolling restarts"}')

        self.workers.then('research-plan', fails(SLOW, 'timeout'), never_right)
        self.pause_after('research-plan', later=True)
        root = self.start()
        first, second, third = self.workers.of('research-plan')
        self.assertNotIn('An earlier try', first.task)
        self.assertIn(f'An earlier try at this job did not work: {SLOW}', second.task)
        self.assertIn('An earlier try at this job did not work: What it handed back did not '
                      'pass the checks: "items" must hold 1 to 8 questions.', third.task)
        self.assertEqual(len({first.folder, second.folder, third.folder}), 3)
        step, entry = self.steps(root)['research-plan'], self.record(root)['steps'][
            'research-plan']
        self.assertEqual((self.state(root), step['status'], step['attempts'], step['error']),
                         ('paused', 'done', 3, None))
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
        self.pause_after('research-plan')
        after = self.engine.act(root, 'retry')
        self.assertEqual((after['state'], after['problem'], len(self.workers.jobs)),
                         ('paused', None, 4))
        self.assertEqual(self.steps(root)['research-plan']['status'], 'done')

    def test_an_agent_that_cannot_be_used_is_not_tried_again_until_asked(self):
        self.workers.then('research-plan', fails('Claude Code is not installed on this '
                                                 'computer.', 'unavailable'))
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], len(self.workers.jobs)), ('failed', 1))
        self.assertEqual(view['problem']['what'], 'scripted could not be used. Claude Code is '
                         'not installed on this computer. Check this computer, on the Status screen, says what it needs.')
        self.pause_after('research-plan')
        self.assertEqual(self.engine.act(root, 'retry')['state'], 'paused')

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
        self.pause_after('research-plan')
        self.assertEqual(self.engine.act(root, 'retry')['state'], 'paused')


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
        self.pause_after('research-plan')
        after = self.engine.answer(root, asked['id'], ' The newer one.\n')
        self.assertEqual((after['state'], after['question']), ('paused', None))
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
        self.pause_after('research-plan', later=True)
        root = self.start()
        for _ in range(3):
            self.assertTrue(self.workers.jobs[-1][2]['ask'])
            self.engine.answer(root, self.view(root)['question']['id'], 'Yes.')
        self.assertFalse(self.workers.jobs[-1][2]['ask'])
        self.assertEqual((self.state(root), len(self.workers.jobs)), ('paused', 4))
        self.assertIsNone(self.view(root)['question'])


class NoteTests(StudioCase):
    """A note for the next step goes with the next job that starts, once, and stops nothing."""

    def test_a_note_is_refused_when_empty_too_long_finished_or_stopped(self):
        self.pause_after('research-plan')
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

    def test_the_research_purpose_is_the_shared_one(self):
        from runner import engine as engine_module
        from studio_core import research_contract
        captured = []

        def native(engine, root, run, task, sources, product):
            captured.append(task)
            raise WorkspaceError('Stopped here by the test.')
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=native), \
                mock.patch.object(engine_module.research_contract, 'purpose',
                                  wraps=research_contract.purpose) as built:
            root = self.start()
        kind, goal, priorities = built.call_args[0]
        self.assertTrue(kind.startswith('training'), kind)
        self.assertIn('Prioritize learner tasks', priorities)
        self.assertIn('for each such statement, report what the sources say about it',
                      priorities)
        self.assertIn('their own organization\'s material on the subject', priorities)
        self.assertNotIn('outline for this training', priorities)
        self.assertEqual(captured[0]['purpose'], research_contract.purpose(kind, goal, priorities))

    def test_bringing_the_research_up_to_date_reaches_the_author(self):
        from types import SimpleNamespace
        from runner import engine as engine_module
        root = self.start()
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
        refusal = WorkspaceError(
            'The independent check of the research still needs changes after 3 rounds of '
            'correction: 2 objections, such as fact-b (unsupported): The source does not say so. '
            'Coverage needs revision: Alternatives are missing. The draft report and the check’s '
            'notes are saved for correction.')
        refusal.objections = ['fact-b (unsupported): The source does not say so.',
                              'Coverage needs revision: Alternatives are missing.']
        refusal.rounds = 3
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=refusal):
            root = self.start()
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
            root = self.start()
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
        cause = [{'source': 'source-a', 'title': 'Handbook', 'file': 'sources/supplied/handbook.text',
                  'original': 'sources/supplied/handbook.md',
                  'access_error': 'There is no tool to read it.'}]
        said = str(research_contract.CheckCouldNotFinish(['fact-a (narrow): Not read.'], 0, cause))
        refusal = WorkspaceError(said)
        refusal.objections, refusal.rounds, refusal.cause = ['fact-a (narrow): Not read.'], 0, cause
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=refusal):
            root = self.start()
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


class SynthesisWordsTests(StudioCase):
    """What a run whose research is one authored report and one independent check says
    while that research is in hand. The record is read as it lies; nothing is run."""

    STAMPS = ('2030-01-01T00:00:00Z', '2030-01-01T00:05:00Z', '2030-01-01T00:10:00Z')

    def test_a_synthesis_run_says_which_of_its_two_jobs_is_in_hand(self):
        from types import SimpleNamespace
        root = self.start()
        self.assertEqual(self.state(root), 'done')
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
        self.pause_after('research-plan')
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
        self.pause_after('research-plan')
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


class LimitTests(StudioCase):
    def test_a_training_carries_on_whatever_it_has_cost(self):
        self.workers.cost = 500.0
        self.engine = self.make(at_once=1)
        root = self.start()
        view = self.view(root)
        self.assertEqual((view['state'], view['problem']), ('done', None))
        # What the agent reported is still shown, and nothing else is said of money.
        self.assertGreaterEqual(view['spent']['dollars'], 1000.0)
        self.assertEqual(set(view['spent']), {'dollars', 'tokens'})
        self.assertNotIn('spending', view)
        record = self.record(root)
        self.assertEqual(record['limits'], {'step_seconds': 1350})
        for gone in ('spending_policy', 'cleared', 'spending_warning'):
            self.assertNotIn(gone, record)
        self.assertEqual({job.limits for _, job, _ in self.workers.jobs},
                         {agents.Limits(seconds=None)})

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
        # The stop is one a saved training may hold: no job is given a time limit now.
        self.assertEqual([job.limits.seconds for job in self.workers.of('research-plan')],
                         [None] * 3)
        with self.assertRaisesRegex(WorkspaceError, 'nothing to resume'):
            self.engine.act(root, 'resume')
        self.pause_after('research-plan')
        self.assertEqual(self.engine.act(root, 'more-time')['state'], 'paused')
        self.assertIsNone(self.workers.of('research-plan')[-1].limits.seconds)
        # The run keeps its time when its limits are read again; Settings keeps its own.
        self.assertEqual((self.record(root)['limits']['step_seconds'],
                          self.record(root)['more_time'], settings.load().step_seconds),
                         (1200, 1200, 600))
        self.engine.act(root, 'resume')
        self.assertEqual({job.limits.seconds for _, job, _ in self.workers.jobs}, {None})

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

    def test_a_research_job_that_runs_out_of_time_says_so(self):
        from runner import engine as engine_module
        from runner.agents import Outcome
        late = WorkspaceError('Research did not finish its author job in round 1 of 3.')
        late.outcome = Outcome(False, 'timeout', SLOW)
        with mock.patch.object(engine_module.research_contract, 'native', side_effect=late):
            root = self.start()
        problem = self.view(root)['problem']
        self.assertEqual((problem['action'], problem['seconds']), ('more-time', 1350))
        self.assertTrue(problem['what'].startswith('The research ran out of the time a step may '
                                                   'take: it was stopped after 22.5 minutes.'))

    def test_a_step_is_given_no_time_limit_and_no_spending_limit(self):
        settings.save(replace(settings.load(), step_seconds=120))
        self.workers.cost = 1.5
        root = self.start()
        self.assertEqual({job.limits for _, job, _ in self.workers.jobs},
                         {agents.Limits(seconds=None)})

    def test_carrying_on_or_trying_again_takes_up_the_limits_this_computer_has_now(self):
        self.workers.then('research-plan', fails(), fails(), fails())
        root = self.start()
        settings.save(replace(settings.load(), step_seconds=1200))
        self.engine.act(root, 'retry')
        self.assertEqual(self.record(root)['limits'], {'step_seconds': 1200})
        self.assertIsNone(self.workers.jobs[-1][1].limits.seconds)


class HaltTests(StudioCase):
    """What a person may ask of a run, which depends on the state it is in."""

    def refused(self, root: Path, action: str, said: str) -> None:
        before = self.record(root)
        with self.assertRaisesRegex(WorkspaceError, said):
            self.engine.act(root, action)
        self.assertEqual(self.record(root), before)

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
        self.assertEqual(self.state(root), 'done')
        self.assertIsNone(self.engine._load(root).get('halt_after'))

    def test_a_paused_training_can_be_stopped(self):
        def pauses(tools, job):
            self.engine.act(self.space.training('rolling-restarts'), 'pause')
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', pauses)
        root = self.start()
        self.assertEqual(self.state(root), 'paused')
        self.assertEqual(self.engine.act(root, 'stop')['state'], 'stopped')
        self.assertEqual(self.engine.act(root, 'resume')['state'], 'done')

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
        self.assertEqual(self.engine.act(root, 'resume')['state'], 'done')

    def test_what_cannot_be_done_as_things_stand_is_refused_in_a_sentence(self):
        self.workers.then('research-plan', asks('Which platform is this about?'))
        root = self.start()
        self.assertEqual(self.state(root), 'waiting')
        self.refused(root, 'pause', 'Only a training that is working can be paused. This one '
                     'is waiting for you.')
        self.refused(root, 'resume', 'This training is not paused or stopped, so there is '
                     'nothing to resume.')
        self.refused(root, 'retry', 'Nothing here failed, so there is nothing to try again.')
        self.refused(root, 'restart', 'A run can be asked to: pause, resume, stop, retry, '
                     'finish-level, more-time, without, slide-text, leave-deck, bring-deck.')

        self.workers.then('research-plan', fails(), fails(), fails())
        failed = self.start(title='Health checks')
        self.assertEqual(self.state(failed), 'failed')
        self.refused(failed, 'pause', 'This one is stopped on a problem.')
        self.refused(failed, 'stop', 'This training is stopped on a problem, so there is '
                     'nothing to stop.')
        self.refused(failed, 'resume', 'not paused or stopped')

        self.engine.answer(root, self.view(root)['question']['id'], 'The public one.')
        self.assertEqual(self.state(root), 'done')
        for action in ACTIONS:
            with self.subTest(action):
                self.refused(root, action, 'finished as far as the runner takes it|not paused '
                             'or stopped|Nothing here failed|not offered|not waiting for a picture')
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

    def test_a_restart_respects_a_pause_a_question_and_a_failure(self):
        self.workers.then('research-plan', asks('Which platform?'))
        asking = self.start()
        self.workers.then('blueprint', fails(), fails(), fails())
        failing = self.start(title='Health checks')
        def pauses(tools, job):
            self.engine.act(self.space.training('blue-green-deploys'), 'pause')
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', pauses)
        paused = self.start(title='Blue green deploys')
        self.pause_after('research-plan', title='canary-releases')
        stopped = self.start(title='Canary releases')
        self.engine.act(stopped, 'stop')
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

    def test_only_a_step_the_runner_ended_in_the_middle_of_is_discarded(self):
        seen = []

        def dies(tools, job):
            seen.append((root / self.engines.IN_HAND).read_text())
            raise Crash()

        root = self.space.training('rolling-restarts')
        self.workers.then('document', dies)
        with self.assertRaises(Crash):
            self.start()
        self.assertEqual(seen, ['document\n'])
        (root / 'document.md').write_text('# Half made\n')
        self.assertEqual(self.git('status', '--porcelain', '--', str(root)),
                         '?? trainings/rolling-restarts/document.md',
                         'the note that a step is in hand is never shared')
        self.restart()
        self.assertFalse((root / self.engines.IN_HAND).exists())
        self.assertEqual((self.state(root), len(self.workers.of('document'))), ('done', 2))
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

    def test_the_last_thing_the_runner_does_is_shared_without_another_decision(self):
        root = self.start()
        self.to_end(root)
        self.all_ready(root)
        self.assertEqual(self.state(root), 'done')
        self.assertEqual(self.shared()[0],
                         'Rolling restarts: write the index; the training is finished')
        self.assertEqual(self.engine.shared(), {'shared': True, 'notice': None})

    def test_a_desk_run_that_comes_to_rest_shares_its_last_commit(self):
        # Issue #549: the earlier flow shared after the runner's last step. A desk run that
        # has written everything and waits for Mark ready shares what it made, unasked.
        root = self.start()
        self.assertEqual(self.state(root), 'done')
        self.assertEqual(self.shared()[0], self.log()[-1])
        self.assertEqual(self.engine.shared(), {'shared': True, 'notice': None})

    def test_a_desk_run_that_comes_to_rest_shares_nothing_when_sharing_is_asked_for(self):
        self.gitstate.share_when('asked')
        root = self.start()
        self.assertEqual(self.state(root), 'done')
        self.assertEqual(self.shared()[0], 'Rolling restarts: start the training from the form')

    def test_a_desk_run_shares_once_at_its_end(self):
        # Second fix round of GitHub issue #549: counted, as the earlier flow shared: once
        # when the run comes to rest, then once for the decision and once for the index.
        calls, real = [], self.engine.share

        def share():
            calls.append(1)
            return real()
        with mock.patch.object(self.engine, 'share', share):
            root = self.start()
            self.assertEqual(len(calls), 1, 'coming to rest shares once')
            self.all_ready(root)
        self.assertEqual(self.state(root), 'done')
        self.assertEqual(len(calls), 3, 'then the decision, and the index, each once')
        self.assertEqual(self.shared()[0],
                         'Rolling restarts: write the index; the training is finished')

    def unshared(self, root: Path) -> None:
        """Only the claim that starts the training reached the team, though more was made."""
        self.assertEqual(self.shared()[0], 'Rolling restarts: start the training from the form')
        self.assertNotEqual(self.log()[-1], self.shared()[0], 'more was made here')

    def test_a_desk_run_stopped_at_a_question_shares_nothing(self):
        # The planner's ruling on #549: shared where the earlier flow shared, never at a stop.
        self.workers.then('blueprint', asks('Which platform is this about?'))
        root = self.start()
        self.assertEqual(self.state(root), 'waiting')
        self.unshared(root)

    def test_a_desk_run_paused_or_stopped_shares_nothing(self):
        self.pause_after('blueprint')
        root = self.start()
        self.assertEqual(self.state(root), 'paused')
        self.unshared(root)

        def stopping(tools, job):
            self.engine.act(self.space.training('health-checks'), 'stop')
            return self.workers.blueprint(tools, job)
        self.workers.then('blueprint', stopping)
        stopped = self.start(title='Health checks')
        self.assertEqual(self.state(stopped), 'stopped')
        self.assertNotIn('Health checks: write the blueprint', ' '.join(self.shared()))

    def test_a_desk_run_that_failed_or_waits_shares_nothing(self):
        self.workers.then('blueprint', fails(), fails(), fails())
        root = self.start()
        self.assertEqual(self.state(root), 'failed')
        self.unshared(root)

        def waiting(tools, job):
            here = self.space.training('health-checks')
            done = self.workers.blueprint(tools, job)
            self.engine._problem(here, 'blueprint', 'waiting', 'Waiting on Google.', 'Kept.')
            return done
        self.workers.then('blueprint', waiting)
        other = self.start(title='Health checks')
        self.assertEqual(self.record(other)['problem']['state'], 'waiting')
        self.assertFalse(any(line.startswith('Health checks') and 'start the training'
                             not in line for line in self.shared()), self.shared())

    def test_a_desk_run_paused_when_a_level_is_finished_shares_nothing(self):
        def finishing(tools, job):
            self.engine.act(self.space.training('rolling-restarts'), 'finish-level')
            return self.workers.document(tools, job)
        self.workers.then('document', finishing)
        root = self.start(levels=['101', '201'])
        self.assertEqual(self.state(root), 'paused')
        self.assertIsNone(self.record(root).get('halt_after'))
        self.unshared(root)

    def test_a_repository_that_cannot_be_reached_never_holds_a_run_up(self):
        root = self.start()
        self.remote.rename(self.base / 'moved-away.git')
        self.all_ready(root)
        self.assertEqual(self.state(root), 'done')
        found = self.engine.shared()
        self.assertFalse(found['shared'])
        self.assertIn('could not be reached', found['notice'])
        self.assertIn('is not shared yet', found['notice'])
        self.assertEqual(self.engine.share()['shared'], False)

    def test_sharing_only_when_asked(self):
        self.gitstate.share_when('asked')
        root = self.start()
        self.assertEqual(self.shared()[0], 'Rolling restarts: start the training from the form',
                         'only the claim that starts a training is sent without being asked')
        self.assertEqual(self.engine.shared(), {'shared': False, 'notice': None})
        self.assertEqual(self.engine.share(), {'shared': True, 'notice': None})
        self.assertIn('Rolling restarts: continue the research plan on the desk',
                      self.shared())
        self.assertEqual(self.engine.shared(), {'shared': True, 'notice': None})

    def test_a_workspace_with_no_remote_has_nowhere_to_share_to(self):
        self.gitstate.local(self.base / 'alone')
        self.assertEqual(self.engine.shared(), {'shared': False, 'notice': None})
        found = self.engine.share()
        self.assertEqual(found['shared'], False)
        self.assertIn('no shared repository', found['notice'])


class WaitingForATurnTests(StudioCase):
    """A run waiting for a slot that set-up moves the workspace from (second fix round of
    GitHub issue #549): it has written nothing while it waits, so the move is accepted, and
    once its turn comes it finds its training is no longer in the workspace in use and stops,
    leaving that training as it was."""

    BACKGROUND = True

    def test_a_run_waiting_behind_a_full_slot_lets_set_up_move_and_then_stops(self):
        from runner import setup
        slots = self.engine._slots
        slots.read = lambda: 1
        self.assertTrue(slots.take(lambda: False))      # the one slot is taken
        root = self.start()
        run = self.engine._run(root)
        deadline = time.monotonic() + 30
        while not run.queued and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(run.queued, 'the run waits for its turn')
        with self.engine.files:
            self.assertFalse(self.engine.in_hand(root))
        moved = setup.apply(self.engine, setup.read({'path': str(self.base / 'elsewhere')}))
        self.assertEqual(moved['workspace']['path'], str(self.base / 'elsewhere'))
        before = self.git('rev-parse', 'HEAD')
        with slots.changed:                              # the slot is given back
            slots.used -= 1
            slots.changed.notify_all()
        while (run.busy or run.queued) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(run.busy or run.queued, 'its turn came, and it stopped')
        self.assertEqual(self.workers.jobs, [], 'nothing was worked on')
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.git('status', '--porcelain', '--', str(root)), '')
        self.assertFalse((self.base / 'elsewhere' / 'trainings' / root.name).exists())


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
        said = ['Handing back research-plan', 'The draft was accepted',
                'Writing its own notes on the draft']
        self.assertEqual((worker['now']['text'], worker['count']), (said[-1], 3))
        self.assertNotIn('lines', worker, 'a poll stays small')
        opened = self.engine.activity(root, job=worker['id'], since=0)['lines']
        self.assertEqual([line['text'] for line in opened], said)
        self.assertTrue(all(re.match(r'^\d{4}-\d\d-\d\dT', line['at']) for line in opened))
        # The Activity log has the running job, and nothing finished yet.
        logged = self.engine.activity(root)
        self.assertEqual((logged['jobs'], logged['empty']), ([], 'No activity recorded yet.'))
        self.assertEqual(logged['running'][0]['now']['text'], said[-1])
        self.assertEqual(self.steps(root)['research-plan']['status'], 'working')
        self.assertEqual(self.engine.brief(root)['needs'], False)
        # The worker's start is the run's last activity, until a try begins or ends later.
        self.assertEqual(self.engine.brief(root)['busy_since'], worker['started_at'])
        from runner import page
        listed = {item['path']: item for item in page.RunnerPage(8765, self.engine).trainings()}
        self.assertEqual(listed[str(root)]['activity_at'], worker['started_at'])
        self.engine.act(root, 'pause')    # where a saved run waited: after this step
        go.set()
        self.until(lambda: self.state(root) == 'paused')
        self.assertEqual(self.view(root)['workers'], [])
        self.assertIsNone(self.engine.brief(root)['busy_since'])
        job, = self.engine.activity(root)['jobs']
        self.assertEqual((job['label'], job['step'], job['outcome']),
                         ('Drafting the research plan', 'research-plan', 'finished'))
        self.assertEqual([line['text'] for line in self.engine.activity(
            root, entry=job['id'])['lines']], said)
        self.assertEqual(job['started_at'], worker['started_at'])

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
        self.until(lambda: self.state(first) == self.state(second) == 'done')
        self.assertEqual(len(self.workers.of('research-plan')), 2)

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
        self.until(lambda: self.state(root) == 'done')

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
        self.until(lambda: self.state(root) == 'done')

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
        self.pause_after('research-plan')
        root = self.start()
        self.assertEqual((self.state(root), self.steps(root)['research-plan']['attempts']),
                         ('paused', 1))
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
        self.pause_after('research-plan')
        root = self.start()
        saved = self.record(root)['model_profiles']
        studios_config.update({'models': {'profiles': {'main': {'model': 'later'}}}})
        self.engine.act(root, 'resume')
        self.assertEqual(self.record(root)['model_profiles'], saved)
        choices = self.record(root)['model_jobs']
        self.assertTrue(any(c['step'].startswith('research:') for c in choices))
        self.assertTrue(all(c['model'] == 'main-model' for c in choices))
        for kind, job, spec in self.workers.jobs:
            self.assertEqual((job.model, job.effort), ('main-model', 'medium'))
            self.assertEqual(job.profile, 'research' if kind.startswith('question:')
                             or 'research' in spec else 'write')

    def test_codex_and_explicit_work_override(self):
        self.configure('codex')
        root = self.start(title='By task')
        self.assertEqual(self.record(root)['model_profiles']['mode'], 'by_task')
        other = self.start(title='Work override', agent='codex', model='own-model', effort='high')
        self.assertEqual(self.record(other)['model_profiles']['mode'], 'single')
        self.assertEqual(self.workers.jobs[-1][1].model, 'own-model')


class FormPlanTests(StudioCase):

    def test_a_documents_only_training_writes_its_plan_from_the_form(self):
        from studio_core import research_contract
        with mock.patch.object(research_contract, 'snapshot', return_value={'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}):
            root = self.start(source_scope='supplied-only', research_questions=['Why?', 'What next?'], saved_contract={'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'})
        self.send(root, 'synthetic.md')
        shown = self.engine.supply(root, 'done')
        plan = json.loads((root / pipeline.PLAN).read_text())
        self.assertEqual([i['question'] for i in plan['items']], ['Why?', 'What next?'])
        self.assertTrue(all(i['public_query'] is None for i in plan['items']))
        self.assertEqual(self.workers.of('research-plan'), [])

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
        root = self.start()
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
        self.pause_after('research-plan')
        root = self.start(levels=['101', '201'])
        session = workspace.load(root)
        for name in ['blueprint@101', 'document@101', 'blueprint@201', 'document@201']:
            workspace.write_atomic(root / workspace.artifact(root, session, name)['file'], b'# Synthetic document\n')
        found = self.engine.research_price(root)
        self.assertTrue(found['words'].endswith('Then it makes again: the level 101 blueprint, the level 101 learner guide, the level 201 blueprint and the level 201 learner guide.'))
