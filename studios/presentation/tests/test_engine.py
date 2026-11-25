"""The engine: a deck walked through its steps by scripted workers, stopping at each gate,
with the slides tool, a brand skill and harness-research as stand-ins. Nothing real is
started, rendered or sent."""
import json
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import runner_support
from stand_ins import brand as brand_stand_in
from runner_support import LONG_OUTLINE, OUTLINE, StudioCase, asks, fails, unsettled
from workspace import WorkspaceError

import home
from runner import decks, gitstate, jobs, marks, stages, worker_tools
from runner.steps import build


def grave(slides):
    """A major finding about how the second slide is drawn."""
    return [{'slide': slides[1]['id'], 'question': 6, 'severity': 'major',
             'about': 'drawing', 'note': 'The two boxes crowd the left half of the slide.'}]


class DispatchTests(unittest.TestCase):
    def test_every_step_of_the_pipeline_has_what_the_engine_does_for_it(self):
        from runner import engine
        self.assertEqual(set(engine.RUN), {step.name for step in stages.PIPELINE})
        for name, method in engine.RUN.items():
            self.assertTrue(callable(getattr(engine.Engine, method)), name)


class SynthesisAtStartTests(StudioCase):
    """A deck's research is not started on a Harness Research that cannot synthesize: the
    start is refused with nothing made. A deck without research, and a deck brought in, are
    not refused."""

    def setUp(self):
        super().setUp()
        from stand_ins.research import saved_queue
        self.research = saved_queue()

    def made(self):
        """What a start could leave behind: the workspace's folders, the decks this computer
        remembers, the workspace's commits and the shared studios config's bytes."""
        import home
        config = self.base / 'studios-config.json'
        return (sorted(path.name for path in self.space.root.iterdir()),
                [entry['path'] for entry in home.decks()], self.log(),
                config.read_bytes() if config.exists() else None)

    def refused(self, **changes):
        before = self.made()
        with self.assertRaises(WorkspaceError) as caught:
            self.start(research=True, **changes)
        self.assertEqual(str(caught.exception), self.engines.NO_SYNTHESIS)
        self.assertEqual(self.made(), before, 'nothing is made')

    def test_a_deck_with_research_is_refused_without_synthesis(self):
        self.start(title='Earlier deck')
        self.refused()

    def test_a_deck_without_research_starts_as_before(self):
        root = self.start(research=False)
        self.assertNotIn('research_contract', decks.read_run(root))
        self.assertIn(str(root), [entry['path'] for entry in __import__('home').decks()])

    def test_a_read_error_is_refused_the_same_way(self):
        from runner import research as tool
        from stand_ins import research as research_stand_in
        runtime = self.base / 'harness-research'
        (runtime / 'scripts' / 'lib').mkdir(parents=True)
        (runtime / 'package.json').write_text('{"version": "1.0.0"}\n', encoding='utf-8')
        (runtime / 'scripts' / 'lib' / 'synthesis-cli.mjs').write_text('', encoding='utf-8')
        self.research = tool.Research(runtime=runtime, run=research_stand_in.SavedQueueStandIn())
        from studio_core import research_contract
        with mock.patch.object(research_contract, 'snapshot', return_value=None):
            self.refused()

    def test_a_deck_brought_in_is_not_refused(self):
        import shutil
        root = self.start(research=False)
        outside = self.base / 'outside' / 'restarts'
        shutil.copytree(root, outside, ignore=shutil.ignore_patterns('work', 'sources'))
        record = decks.read_run(outside)
        record['form']['research'] = True
        record.pop('research_contract', None)
        decks.write_run(outside, record)
        made = self.engine.bring(outside)
        self.assertNotIn('research_contract', decks.read_run(Path(made['path'])))


class SavedWorkTests(StudioCase):
    """`studio saved-work`: which saved decks still need each older path, read from decks
    written as files, with nothing started and nothing changed."""

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
        record = folder / decks.RUN
        record.parent.mkdir(parents=True, exist_ok=True)
        for content in ('{', '{"schema": 999}'):
            record.write_text(content)
            said = self.engine.saved_work()
            self.assertFalse(said['complete'])
            self.assertEqual(said['unused'], [])
            self.assertEqual(record.read_text(), content)

    def test_supported_policy_and_contract_schemas_remain_known(self):
        for schema, extra in ((2, {'review_policy': {'schema': 1, 'level': 'balanced'}}),
                              (3, {'research_contract': {'schema': 2}})):
            root = self.deck(f'supported-{schema}', schema=schema, **extra)
            said = self.engine.saved_work()
            self.assertTrue(said['complete'], said['issues'])
            self.assertIn(str(root), self.needed(said, 'gated-flow'))

    def test_raw_registry_includes_outside_and_missing_candidates(self):
        outside = self.deck('registered', at=self.base / 'elsewhere')
        missing = self.base / 'missing-registered'
        home.write_json(home.registry_path(), {'schema': 1, 'decks': {
            str(outside): {}, str(missing): {}}})
        said = self.engine.saved_work()
        self.assertIn(str(outside), self.needed(said, 'gated-flow'))
        self.assertFalse(said['complete'])
        self.assertEqual(said['unused'], [])
        self.assertTrue(any(entry['path'] == str(missing) for entry in said['issues']))
        home.registry_path().write_text('{')
        self.assertFalse(self.engine.saved_work()['complete'])

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

    QUEUE = 'Its research has not run, and it was started before Harness Research could synthesize.'
    DRAWN = 'It was drawn a cover to show its brand.'
    MAY = 'It may need it: its brand was exported before it reached the look.'

    def deck(self, ident, research=True, done=(), gates=None, files=(), at=None, **extra):
        """A deck's folder as a saved run leaves it: its record and the files named."""
        root = (at or self.space.root) / ident
        root.mkdir(parents=True)
        decks.write_run(root, {
            'schema': decks.SCHEMA, 'id': ident, 'title': ident.title(), 'route': 'scratch',
            'form': {**runner_support.FORM, 'title': ident.replace('-', ' ').title(),
                     'research': research},
            'created': '2026-01-01T00:00:00Z', 'driver': None, 'gates': gates or {},
            'steps': {name: {'done': '2026-01-01T00:00:00Z'} for name in done},
            'classified': None, 'look': None, 'revisions': [], 'halted': None, **extra})
        for name in files:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text('kept\n', encoding='utf-8')
        return root

    def kept(self):
        self.git('add', '-A')
        self.git('commit', '--quiet', '-m', 'Decks saved before')

    def tree(self, *folders):
        return {path: path.read_bytes() for folder in folders for path in
                sorted(folder.rglob('*')) if path.is_file() and '.git' not in path.parts}

    def needed(self, said, ident):
        return {entry['path']: entry['why'] for entry in
                next(found for found in said['paths'] if found['id'] == ident)['needed_by']}

    def test_a_deck_begun_on_the_queue_needs_it_until_its_research_has_run(self):
        waiting = self.deck('waiting-deck')
        self.deck('researched-deck', done=('research',))
        self.deck('contract-deck', research_contract={'schema': 2, 'version': '1.0.0',
                                                      'digest': 'abc'})
        self.deck('plain-deck', research=False)
        said = self.engine.saved_work()
        self.assertEqual(self.needed(said, 'research-queue'), {str(waiting): self.QUEUE})
        self.assertEqual(said['paths'][0]['needed_by'][0]['title'], 'Waiting Deck')

    def test_an_undelivered_deck_may_need_the_cover_sample(self):
        drawn = self.deck('drawn-deck', research=False, files=('look.md',))
        self.deck('shown-deck', research=False, files=('look.md', 'work/look/shown.json'))
        exported = self.deck('exported-deck', research=False,
                             files=('brand/brand-contract.json',))
        self.deck('looked-deck', research=False, files=('brand/brand-contract.json',),
                  gates={'gate:look': {'state': 'approved'}})
        self.deck('delivered-deck', done=('research', 'deliver'),
                  files=('look.md', 'brand/brand-contract.json'))
        said = self.engine.saved_work()
        self.assertEqual(self.needed(said, 'cover-sample'), {str(drawn): self.DRAWN,
                                                             str(exported): self.MAY})
        self.assertEqual(self.needed(said, 'research-queue'), {})

    def test_the_old_slides_branches_are_always_unused(self):
        self.deck('waiting-deck', files=('look.md',))
        said = self.engine.saved_work()
        self.assertEqual([entry['id'] for entry in said['paths']],
                         ['research-queue', 'cover-sample', 'old-harness-slides', 'gated-flow'])
        self.assertEqual(said['unused'], ['old-harness-slides'])

    def test_a_folder_given_outside_the_workspace_is_looked_at_too(self):
        outside = self.deck('outside-deck', at=self.base / 'elsewhere')
        self.assertEqual(self.needed(self.engine.saved_work(), 'research-queue'), {})
        said = self.engine.saved_work(folders=(outside, self.base / 'no-deck-here'))
        self.assertEqual(self.needed(said, 'research-queue'), {str(outside): self.QUEUE})

    def test_nothing_in_the_workspace_changes(self):
        self.deck('waiting-deck', files=('look.md', 'brand/brand-contract.json'))
        outside = self.deck('outside-deck', at=self.base / 'elsewhere')
        self.kept()
        before = self.tree(self.space.repo, outside)
        said = self.engine.saved_work(folders=(outside,))
        self.assertEqual(len(self.needed(said, 'research-queue')), 2)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.tree(self.space.repo, outside), before)


class AheadTests(StudioCase):
    """Each deck's view says how many steps are left, where it next stops for the person
    under its own level, and what its agent's jobs have spent so far."""

    def test_runner_only_steps_do_not_claim_a_reported_zero_cost(self):
        root = self.start()
        record = decks.read_run(root)
        record['steps'] = {name: entry for name, entry in record['steps'].items()
                           if (stages.BY_NAME.get(name) or
                               stages.BY_NAME[name.partition(':')[0]]).kind == 'code'}
        self.assertTrue(record['steps'])
        ahead = self.engine._still_to_come(record)
        self.assertIsNone(ahead['dollars'])
        self.assertIn('the assistant reported no cost', ahead['spent'])


class NoCostYetTests(StudioCase):
    """Only the runner's own steps have run, or the build's jobs reported no cost: nothing
    is said as $0.00."""

    def test_a_deck_that_ran_only_its_own_steps_reports_no_cost_yet(self):
        root = self.start()
        run = decks.read_run(root)
        run['steps'] = {'intake-source': {'failed': 0, 'done': True,
                                          'tries': [{'seconds': 2, 'dollars': None}]}}
        decks.write_run(root, run)
        ahead = self.view(root)['ahead']
        self.assertIsNone(ahead['dollars'])
        self.assertNotIn('$', ahead['spent'])
        self.assertTrue(ahead['spent'].endswith('; the assistant reported no cost'))

    def test_build_completion_markers_are_not_unpriced_assistant_jobs(self):
        record = {'steps': {
            'build-sections': {'tries': [{'seconds': 0, 'dollars': None}]},
            'build-repair': {'tries': [{'seconds': 0, 'dollars': None}]},
            'build-sections:1': {'tries': [
                {'outcome': 'kept', 'seconds': 30, 'dollars': 0.25}]},
            'build-review': {'tries': [
                {'outcome': 'kept', 'seconds': 20, 'dollars': 0.25},
                {'outcome': 'kept', 'seconds': 0, 'dollars': None, 'runner': True}]}}}
        self.assertEqual(self.engine._last_build(record)['dollars'], 0.5)
        # An actual assistant review without dollars still makes the total unknown.
        record['steps']['build-review']['tries'].append(
            {'outcome': 'kept', 'seconds': 10, 'dollars': None})
        self.assertIsNone(self.engine._last_build(record)['dollars'])

    def test_the_last_build_reports_no_dollars_when_a_build_job_reported_none(self):
        record = {'steps': {
            'build-sections:1': {'tries': [{'outcome': 'kept', 'seconds': 300, 'dollars': 1.5}]},
            'build-review': {'tries': [{'outcome': 'kept', 'seconds': 120, 'dollars': None}]},
            'build-render': {'tries': [{'outcome': 'kept', 'seconds': 30, 'dollars': None}]}}}
        self.assertIsNone(self.engine._last_build(record)['dollars'])
        record['steps']['build-review']['tries'][0]['dollars'] = 0.5
        self.assertEqual(self.engine._last_build(record)['dollars'], 2.0)


class HonestStopTests(StudioCase):
    def test_a_google_doc_document_needs_google_before_the_deck_is_made(self):
        from runner.steps import existing
        before = self.engine.decks()
        with mock.patch.object(type(self.engine), '_google_ready', lambda me: False):
            with self.assertRaises(WorkspaceError) as caught:
                self.start(route='document', source={
                    'kind': 'google', 'link': 'https://docs.google.com/document/d/abc/edit'})
        self.assertEqual(str(caught.exception), existing.NOT_READY)
        self.assertEqual(existing.NOT_READY, 'Sign in to Google first: Status → Check this '
                         'computer says how. Or download the file and upload it.')
        self.assertEqual(self.engine.decks(), before, 'nothing is made')

    def test_an_unexpected_failure_says_its_message_without_its_class(self):
        root = self.start()
        self.engine._trouble(root, ValueError('boom'))
        problem = self.view(root)['problem']
        self.assertEqual(problem['why'], 'The runner could not go on: boom.')
        self.assertNotIn('ValueError', json.dumps(self.view(root)))


class RetryTests(StudioCase):
    def test_a_step_that_fails_three_times_stops_and_retry_carries_on(self):
        self.workers.then('outline', fails(), fails(), fails('The model gave up again.'))
        root = self.start()
        view = self.view(root)
        self.assertEqual(view['state'], 'failed')
        self.assertIn('This step did not work in 3 tries: Draft the outline. The last one: '
                      'The model gave up again.', view['sentence'])
        self.assertEqual(view['problem']['action'], 'retry')
        self.assertEqual(len(self.workers.of('outline')), 3)
        self.assertIn('An earlier try at this job did not work',
                      self.workers.of('outline')[1].task)
        self.engine.act(root, 'retry')
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertEqual(len(self.workers.of('outline')), 4)

    def test_a_draft_the_checks_refuse_is_tried_again_with_the_reason(self):
        def wrong(tools, job):
            tools.submit_outline(json.dumps({'version': 1, 'slides': []}))
        self.workers.then('outline', wrong)
        root = self.start()
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertIn('did not pass the checks', self.workers.of('outline')[1].task)

    def test_an_agent_that_cannot_be_used_stops_at_once(self):
        self.workers.then('outline', fails('Not signed in.', reason='unavailable'))
        root = self.start()
        self.assertEqual(self.state(root), 'failed')
        self.assertIn('could not be used. Not signed in. Check this computer, on the Status '
                      'screen, says what it needs.', self.view(root)['sentence'])
        self.assertEqual(len(self.workers.of('outline')), 1)

    def test_an_account_at_its_usage_limit_stops_at_once_and_says_where_to_look(self):
        self.workers.then('outline', fails("You've hit your usage limit.", reason='limit'))
        root = self.start()
        self.assertEqual(self.state(root), 'failed')
        self.assertEqual(self.view(root)['sentence'], "scripted's account reached a usage or "
                         'rate limit. Wait until it resets, then Try again.')
        self.assertEqual(len(self.workers.of('outline')), 1)

    def test_no_assistant_job_is_ended_for_how_long_it_takes(self):
        self.workers.then('outline', *[fails()] * 3)
        root = self.start()
        # No job is given a time limit, whatever Settings still holds.
        self.assertEqual(self.settings.load().step_seconds, 1350)
        self.assertEqual({job.limits.seconds for job in self.workers.of('outline')}, {None})
        self.assertEqual(self.view(root)['problem']['action'], 'retry')
        # A deck that stopped at a time limit before is still carried on by its own action.
        with self.engine.files:
            record = self.engine._load(root)
            record['halted'].update(action='more-time', seconds=1350)
            self.engine._store(root, record)
            self.engine._commit(root, 'as a deck stopped at a time limit before')
        self.engine.act(root, 'more-time')
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertIsNone(self.workers.of('outline')[-1].limits.seconds)


class QuestionTests(StudioCase):
    def test_a_workers_question_waits_for_an_answer_which_goes_into_the_task(self):
        self.workers.then('outline', asks('Who presents it?'))
        root = self.start()
        view = self.view(root)
        self.assertEqual(view['state'], 'waiting')
        self.assertEqual(view['question']['text'], 'Who presents it?')
        self.engine.answer(root, view['question']['id'], 'A platform engineer.')
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertIn('Answer: A platform engineer.', self.workers.of('outline')[-1].task)


class SharedDataTests(StudioCase):
    def test_a_data_folder_others_share_stops_the_deck_before_any_worker_with_a_sentence(self):
        from runner import agents
        import home
        shared = lambda: [home.data_root().parent]   # noqa: E731
        with mock.patch.object(agents, 'shared_temporary', shared):
            said = agents.data_shared()
            self.assertIn('a temporary folder other programs share', said)
            self.assertIn('PRESENTATION_STUDIO_DATA', said)
            self.assertNotIn('staging', said)
            self.assertEqual(self.engine.status()['problem'], said)
            root = self.start()
            record = self.record(root)
            self.assertEqual(self.state(root), 'stopped')
            self.assertEqual(record['halted']['why'], said)
            self.assertEqual(self.workers.jobs, [])
            self.assertFalse(any((entry or {}).get('failed')
                                 for entry in record['steps'].values()
                                 if isinstance(entry, dict)), 'no try was spent on it')
        self.assertIsNone(agents.data_shared())
        self.assertIsNone(self.engine.status()['problem'])


class HaltTests(StudioCase):
    def test_pause_stop_resume_and_what_is_refused(self):
        root = self.start()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.act(root, 'pause')
        self.assertIn('Only a deck that is working can be paused', str(caught.exception))
        with self.assertRaises(WorkspaceError):
            self.engine.act(root, 'retry')
        self.engine.act(root, 'stop')
        self.assertEqual(self.state(root), 'stopped')
        with self.assertRaises(WorkspaceError):
            self.engine.act(root, 'stop')
        self.engine.act(root, 'resume')
        self.assertEqual(self.waiting(root), 'gate:build')

    def test_a_deck_carries_on_whatever_its_jobs_report_they_cost(self):
        self.workers.cost = 500.0
        self.workers.then('outline', asks('One thing first?'))
        root = self.start()
        self.assertEqual(self.record(root)['limits'], {'step_seconds': 1350})
        self.assertNotIn('spending_policy', self.record(root))
        self.engine.answer(root, self.view(root)['question']['id'], 'Yes.')
        self.assertEqual(self.waiting(root), 'gate:build')
        view = self.view(root)
        self.assertIsNone(view['problem'])
        self.assertTrue(self.workers.of('section'))
        # What was reported is still said, as information only.
        self.assertGreaterEqual(view['spent']['dollars'], 1000.0)
        self.assertNotIn('spending', view)
        self.assertNotIn('spending', (root / 'work' / 'activity-log.jsonl').read_text())

    def test_a_job_that_says_it_reached_a_spending_limit_is_an_ordinary_failed_try(self):
        from runner.agents import Outcome
        self.workers.then('outline', lambda tools, job: Outcome(
            False, 'limit', 'It stopped without finishing: its spending limit was reached',
            cost=1.0))
        root = self.start()
        # Nothing stopped for money: the step was tried again and worked.
        self.assertEqual(self.waiting(root), 'gate:build')
        tried = self.record(root)['steps']['outline']['tries']
        self.assertEqual([one['outcome'] for one in tried], ['failed', 'kept'])

    def test_a_deck_saved_while_spending_was_limited_still_opens_and_resumes(self):
        root = self.start()
        self.assertEqual(self.waiting(root), 'gate:build')
        with self.engine.files:
            record = self.engine._load(root)
            record.update(
                spending_policy='hard-stop', cleared=1.5,
                spending_warning={'at': '2026-10-01T10:00:00Z', 'dollars': 1.5, 'limit': 1.0},
                limits={**record['limits'], 'dollars': 1.0},
                halted={'state': 'stopped', 'step': None, 'action': 'resume', 'limit': True,
                        'why': 'This deck has spent $1.50. It stops and asks each time it '
                               'has spent another $1.00.',
                        'kept': 'Everything made so far is kept.',
                        'at': '2026-10-01T10:00:00Z'})
            record['steps']['outline']['tries'].insert(0, {
                'started_at': '2026-10-01T09:00:00Z', 'ended_at': '2026-10-01T09:01:00Z',
                'seconds': 60.0, 'dollars': 1.5, 'tokens': None, 'outcome': 'limit',
                'error': 'its spending limit was reached'})
            self.engine._store(root, record)
            self.engine._commit(root, 'as an older runner left it')
        before = (root / 'run.json').read_bytes()
        view = self.view(root)
        self.assertEqual((view['state'], view['problem']['action']), ('stopped', 'resume'))
        self.assertIn('This deck has spent $1.50', view['sentence'])
        self.assertNotIn('spending', view)
        self.assertGreaterEqual(view['spent']['dollars'], 1.5)
        self.assertTrue(self.engine.activity(root) is not None)
        self.assertEqual((root / 'run.json').read_bytes(), before,
                         'reading it rewrites nothing')
        self.engine.act(root, 'resume')
        self.assertEqual(self.waiting(root), 'gate:build')
        kept = self.record(root)
        self.assertEqual((kept['spending_policy'], kept['cleared']), ('hard-stop', 1.5))

    def test_a_research_job_that_still_ends_for_its_time_offers_try_again(self):
        from runner import research_steps
        from runner.agents import Outcome
        late = WorkspaceError('Research did not finish its author job in round 1 of 3.')
        late.outcome = Outcome(False, 'timeout', 'It did not finish in 1350 seconds, so it was stopped.')
        with mock.patch.object(research_steps.research_contract, 'native', side_effect=late):
            root = self.start(research=True)
        problem = self.view(root)['problem']
        # No job is given a time limit now, so there is no more time to offer: it is tried
        # again like any other step that failed.
        self.assertEqual(problem['action'], 'retry')
        self.assertNotIn('seconds', problem)
        self.assertEqual(problem['why'],
                         'Research did not finish its author job in round 1 of 3.')

    def test_undo_takes_back_the_last_step(self):
        root = self.start()
        self.assertEqual(self.log()[-1], 'Rolling restarts: the deck is on the desk')
        count = len(self.log())
        self.engine.act(root, 'undo')
        # The step was taken back and taken again: its commit undone, then made again.
        taken = self.git('reflog', '--format=%gs').splitlines()
        self.assertEqual(taken[0], 'commit: Rolling restarts: the deck is on the desk')
        self.assertIn('branch: Reset to HEAD~1', taken[1:3])
        self.assertEqual(len(self.log()), count)
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertEqual(self.log()[-1], 'Rolling restarts: the deck is on the desk')


class OlderSlidesToolTests(StudioCase):
    """A slides tool older than the floor, kept by a brand skill's own installer."""

    def brand_bringing(self, version: str) -> None:
        folder = self.base / 'acme-brand'
        (folder / 'scripts' / 'lib').mkdir(parents=True, exist_ok=True)
        (folder / 'scripts' / 'lib' / 'harness-install-sources.json').write_text(
            json.dumps({'slides': {'version': version}}), encoding='utf-8')
        self.brand.runtime, self.brand.name = folder, 'Acme Brand'

    def too_old(self):
        from runner import slides as slides_tool
        return mock.patch.object(self.engine, 'slides',
                                 mock.Mock(side_effect=slides_tool.TooOld('0.15.1')))

    def test_status_says_when_arial_is_missing(self):
        asked = []

        def fonts():
            asked.append(1)
            return 'Arial was not found on this computer, so slides may be drawn in another font. Install licensed Arial.'
        self.brand.fonts = fonts
        needs = self.engine.deck_needs(fresh=True)
        self.assertEqual(needs['fonts'], 'Arial was not found on this computer, so slides may be drawn in another font. Install licensed Arial.')
        [item] = [item for item in needs['items'] if item['id'] == 'deck-fonts']
        self.assertEqual((item['state'], item['fix']), ('problem', 'Arial was not found on this computer, so slides may be drawn in another font. Install licensed Arial.'))
        self.assertNotIn('Arial was not found on this computer, so slides may be drawn in another font. Install licensed Arial.', needs['missing'], 'another font holds no deck up')
        self.engine.deck_needs()
        self.assertEqual(len(asked), 1, 'asked once within a look')
        self.brand.fonts = lambda: None
        needs = self.engine.deck_needs(fresh=True)
        self.assertIsNone(needs['fonts'])
        self.assertEqual([item for item in needs['items'] if item['id'] == 'deck-fonts'], [])

    def test_status_names_the_brand_installer_that_kept_an_old_tool(self):
        self.brand_bringing('0.15.1')
        with self.too_old():
            missing = self.engine.deck_needs(fresh=True)['missing']
        self.assertIn('harness-slides 0.15.1 is installed, and a deck needs 0.19.0 or newer. '
                      "Acme Brand's own installer brings 0.15.1. Update Harness Slides, then try again.",
                      missing)
        self.assertEqual(self.engine.brought_by('0.15.1'), 'Acme Brand')
        self.brand_bringing('0.19.0')
        with self.too_old():
            missing = self.engine.deck_needs(fresh=True)['missing']
        self.assertIn('harness-slides 0.15.1 is installed, and a deck needs 0.19.0 or newer. '
                      'Update Harness Slides, then try again.', missing)
        self.assertIsNone(self.engine.brought_by('0.15.1'))

    def test_a_brand_skill_older_than_the_floor_is_said_and_holds_a_new_deck(self):
        from runner import brand as brand_skill
        said = brand_skill.too_old('0.13.2')
        self.brand.version = '0.13.2'
        needs = self.engine.deck_needs(fresh=True)
        self.assertNotIn(said, needs['missing'], 'it holds up no deck already exported')
        [item] = [item for item in needs['items'] if item['id'] == 'deck-brand']
        self.assertEqual((item['state'], item['fix']), ('problem', said))
        root = self.start()
        view = self.view(root)
        self.assertEqual(view['state'], 'stopped')
        self.assertIn(said, view['sentence'])
        self.assertEqual(self.workers.of('outline'), [], 'nothing that needs the brand ran')
        self.brand.version = '0.14.0'
        self.assertNotIn(said, json.dumps(self.engine.deck_needs(fresh=True)['items']))

    def test_a_begun_deck_carries_on_with_an_old_brand_skill(self):
        def begun(tools, job):
            # The deck has begun: its outline is being drafted when the brand skill turns old.
            self.brand.version = '0.13.2'
            self.engine.deck_needs(fresh=True)
            return self.workers.outline(tools, job)
        self.workers.then('outline', begun)
        root = self.start()
        view = self.view(root)
        self.assertEqual(self.brand.version, '0.13.2')
        self.assertNotEqual(view['state'], 'stopped', view.get('problem'))
        self.assertNotEqual(view['state'], 'failed', view.get('problem'))

    def test_a_deck_begun_on_an_older_tool_stops_at_its_next_step_and_keeps_its_files(self):
        old, before = self.too_old(), []

        def begun(tools, job):
            # The outline is drafted and checked when the slides tool turns out too old.
            [root] = self.engine.every()
            # What it has, but the lock of the job in hand, which is let go when it ends.
            before.extend(sorted(str(path.relative_to(root)) for path in root.rglob('*')
                                 if path.name != 'step.lock'))
            old.start()
            self.engine.deck_needs(fresh=True)
            return self.workers.text_check(tools, job)
        self.workers.then('text-check', begun)
        try:
            root = self.start()
            view = self.view(root)
        finally:
            old.stop()
        self.assertTrue(before)
        self.assertIn(view['state'], ('stopped', 'failed'))
        self.assertIn('harness-slides 0.15.1 is installed, and a deck needs 0.19.0 or newer. '
                      'Update Harness Slides, then try again.', json.dumps(view))
        after = sorted(str(path.relative_to(root)) for path in root.rglob('*'))
        self.assertLessEqual(set(before), set(after), 'nothing it had is lost')


class BrandTests(StudioCase):
    def test_a_brand_that_changed_stops_the_deck_before_the_next_step_that_uses_it(self):
        rules = self.brand.run.home / 'references' / 'brand-rules.md'

        def changed(tools, job):
            # The brand changes once the outline is drafted and its text checked.
            said = self.workers.text_check(tools, job)
            rules.write_text(rules.read_text() + 'Round corners now.\n')
            return said
        self.workers.then('text-check', changed)
        root = self.start()
        view = self.view(root)
        self.assertEqual(view['state'], 'stopped')
        self.assertTrue(view['sentence'].startswith('The brand changed since this deck began'))
        self.assertFalse((root / 'work' / 'look' / 'sample.png').exists())

    def without_a_brand_skill(self):
        """No brand skill on this computer, as the engine looks at it afresh."""
        self.installed, self.brand = self.brand, None
        self.engine.deck_needs(fresh=True)

    def test_without_a_brand_skill_a_deck_runs_until_it_needs_its_brand(self):
        from runner import engine
        self.without_a_brand_skill()
        root = self.start(research=True, brand='', variant='')
        self.assertIn('your brand, chosen when the brand skill is installed',
                      (root / 'intake.md').read_text())
        # The research, which does not need the brand, ran; the deck stopped after it.
        self.assertTrue(self.record(root)['steps']['research']['done'])
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence']), ('stopped', engine.NO_BRAND))
        self.assertEqual(view['problem']['action'], 'retry')
        self.assertEqual(self.workers.of('outline'), [], 'nothing that needs the brand ran')
        self.brand = self.installed
        self.engine.act(root, 'retry')
        self.assertEqual(self.waiting(root), 'gate:build')
        form = json.loads((root / 'run.json').read_text())['form']
        self.assertEqual((form['brand'], form['variant']), ('example', 'light'),
                         'the first brand the brand skill lists, and its first variant')

    def test_a_brand_named_in_settings_is_the_one_a_deck_with_none_chosen_gets(self):
        from dataclasses import replace
        self.settings.save(replace(self.settings.load(), brand='example', variant='dark'))
        self.without_a_brand_skill()
        root = self.start(brand='', variant='')
        self.assertEqual(self.state(root), 'stopped')
        self.brand = self.installed
        self.engine.act(root, 'retry')
        form = json.loads((root / 'run.json').read_text())['form']
        self.assertEqual((form['brand'], form['variant']), ('example', 'dark'))

    def test_a_brand_skill_named_where_there_is_none_is_said_as_it_is(self):
        from runner import engine
        self.without_a_brand_skill()
        with mock.patch.dict('os.environ', {'BRAND_SKILL_RUNTIME': str(self.base / 'nowhere')}):
            root = self.start(brand='', variant='')
        view = self.view(root)
        self.assertNotEqual(view['sentence'], engine.NO_BRAND)
        self.assertEqual(view['sentence'], f"BRAND_SKILL_RUNTIME names {self.base / 'nowhere'}, "
                         'which does not hold a brand skill. Point it at an installed one, or '
                         'unset it.')

    def test_a_brand_the_brand_skill_does_not_offer_stops_the_deck(self):
        from runner import decks as named
        self.without_a_brand_skill()
        for form, says in (
                ({'brand': 'globex', 'variant': ''},
                 named.NOT_OFFERED.format(brand='globex', listed='example')),
                ({'brand': 'example', 'variant': 'neon'},
                 named.NO_VARIANT.format(variant='neon', brand='example',
                                         listed='light, dark'))):
            self.brand = None
            root = self.start(title=f"Restarts in {form['variant'] or form['brand']}", **form)
            self.brand = self.installed
            self.engine.act(root, 'retry')
            view = self.view(root)
            self.assertEqual((view['state'], view['sentence']), ('stopped', says))
            kept = json.loads((root / 'run.json').read_text())['form']
            self.assertEqual((kept['brand'], kept['variant']),
                             (form['brand'], form['variant'] or None), 'never switched')
            self.assertEqual(self.workers.of('outline'), [])

    def test_the_brand_chosen_for_a_deck_is_said_in_its_intake(self):
        self.without_a_brand_skill()
        root = self.start(brand='', variant='')
        self.brand = self.installed
        self.engine.act(root, 'retry')
        self.assertIn('## Brand\nexample (light)\n', (root / 'intake.md').read_text())
        self.assertNotIn('chosen when the brand skill is installed',
                         (root / 'intake.md').read_text())

    def test_without_a_brand_skill_an_existing_deck_is_still_listed_slide_by_slide(self):
        from runner import engine
        from runner.steps import outline as outlines
        self.without_a_brand_skill()
        root = self.start(route='existing', level='polish', brand='', variant='',
                          source={'kind': 'upload', 'name': 'old.pptx'},
                          uploads={'old.pptx': ExistingTests.DECK})
        # Listed slide by slide, then stopped where the brand is first needed.
        self.assertEqual(len(json.loads((root / outlines.INVENTORY).read_text())['slides']), 3)
        self.assertEqual(self.view(root)['sentence'], engine.NO_BRAND)


class SynthesisStopTests(StudioCase):
    """How a deck's research, done as one authored report and one independent check,
    stops: and what Try again does then."""

    CAUSE = [{'source': 'source-a', 'title': 'Handbook',
              'file': 'sources/supplied/handbook-html.txt',
              'original': 'sources/supplied/handbook-html.original.html',
              'access_error': 'There is no tool to read it.'}]

    def synthesis(self, refusal):
        """A desk deck with research, whose research stops as `refusal` says."""
        from runner import research_steps
        with mock.patch.object(research_steps.research_contract, 'native', side_effect=refusal):
            return self.start(research=True)

    def test_a_check_that_could_not_read_an_original_stops_and_says_whose_problem_it_is(self):
        from studio_core import research_contract
        said = str(research_contract.CheckCouldNotFinish(['fact-a (narrow): Not read.'], 0,
                                                        self.CAUSE))
        refusal = WorkspaceError(said)
        refusal.objections, refusal.rounds, refusal.cause = ['fact-a (narrow): Not read.'], 0, self.CAUSE
        root = self.synthesis(refusal)
        view = self.view(root)
        self.assertEqual((view['state'], view['problem']['why']), ('failed', said))
        self.assertIn('could not read the original of "Handbook"', view['sentence'])
        self.assertIn('Try again works once the original can be read:\n- Handbook: There is '
                      'no tool to read it.', view['problem']['kept'])
        self.assertEqual(self.record(root)['halted']['unreadable'], self.CAUSE)
        # Try again is refused, in the same words, while the original still cannot be read.
        # The dry read is done before the deck's files are held.
        def unread(*given):
            self.assertFalse(self.engine.files._is_owned())
            return 'No.'
        with mock.patch.object(research_contract, 'dry_read', side_effect=unread) as read, \
                mock.patch.object(research_contract, 'native') as again:
            with self.assertRaises(WorkspaceError) as caught:
                self.engine.act(root, 'retry')
        self.assertEqual(str(caught.exception), said)
        self.assertEqual((read.call_args[0][2], again.call_count), (self.CAUSE, 0))
        # Once it can be read, Try again runs the research again.
        with mock.patch.object(research_contract, 'dry_read', return_value=None), \
                mock.patch.object(research_contract, 'native', side_effect=refusal) as again:
            self.engine.act(root, 'retry')
        self.assertEqual(again.call_count, 1)

    def test_objections_are_kept_under_their_groups(self):
        from runner import research_steps
        refusal = WorkspaceError('The independent check of the research still needs changes.')
        refusal.objections, refusal.rounds = ['f01 (narrow): Too broad.'], 3
        refusal.groups = [{'title': '1 fact the check calls narrow', 'count': 1,
                           'note': 'f01: Too broad.', 'items': ['f01: Too broad.']}]
        root = self.synthesis(refusal)
        kept = self.view(root)['problem']['kept']
        self.assertIn('every objection is listed under its group in research/review.md', kept)
        self.assertTrue(kept.endswith('\n- 1 fact the check calls narrow (f01: Too broad.)'))
        self.assertEqual((root / 'research/review.md').read_text(), (
            '# Independent research check\n\nAfter 3 rounds of correction the independent '
            'check still objected. Each objection names the fact, finding or passage it '
            'concerns.\n\n## 1 fact the check calls narrow\n\n- f01: Too broad.\n'))
        # The stop's pointer opens: the page may read the file, and the stop names it.
        from runner import page
        self.assertIn('research/review.md', page.FILES)
        self.assertEqual(self.view(root)['problem']['objections'], 'research/review.md')
        # Research that later passes leaves no objections behind.
        with mock.patch.object(research_steps.research_contract, 'native', return_value=None):
            self.engine.act(root, 'retry')
        self.assertFalse((root / 'research/review.md').exists())
        self.assertNotIn('research/review.md', self.git('ls-files'))

    def test_a_dry_read_reads_each_original_as_the_check_would(self):
        from studio_core import research_contract
        root = self.start(route='document', source={'kind': 'upload', 'name': 'handbook.html'},
                          uploads={'handbook.html': b'<p>Restart one batch at a time.</p>'})
        self.assertIsNone(research_contract.dry_read(self.engine, root, self.CAUSE))
        with mock.patch.object(worker_tools.WorkerTools, '_original',
                               side_effect=worker_tools.Refusal('No tool serves it.')):
            self.assertEqual(research_contract.dry_read(self.engine, root, self.CAUSE),
                             'No tool serves it.')
            # A source with no original of its own needs nothing read.
            self.assertIsNone(research_contract.dry_read(self.engine, root, [
                {'file': 'sources/supplied/other.txt'}]))


class ResearchRoundTests(StudioCase):
    """A deck's research done as one authored report and one independent check: its jobs
    count under the research step, and the page says which round is in hand."""

    def desk_synthesis(self):
        """A desk deck with research, its research step's jobs as below: the step itself is
        not finished, as while its rounds are in hand."""
        import shutil
        from studio_core import research_contract
        root = self.start(research=True)
        record = self.engine._load(root)
        record['steps'].pop('research')
        self.engine._store(root, record)
        # No draft is saved yet, as before the first round handed one back.
        shutil.rmtree(root / research_contract.CASE / '.harness-research')
        return self.rounds(root)

    def rounds(self, root):
        record = self.engine._load(root)
        record['research_contract'] = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        tried = lambda at, seconds, dollars, outcome='kept': {
            'started_at': at, 'ended_at': at, 'seconds': seconds, 'dollars': dollars,
            'tokens': 1000, 'outcome': outcome, 'error': None}
        record['steps'].update({
            'research-author': {'failed': 0, 'tries': [tried('2030-01-01T00:00:00Z', 50, 0.1)]},
            'research:author-1': {'failed': 0, 'tries': [tried('2030-01-02T00:00:00Z', 300, 0.8)]},
            'research:review-1': {'failed': 0, 'tries': [tried('2030-01-02T00:10:00Z', 120, 0.4)]},
            'research:author-2': {'failed': 1, 'tries': [
                tried('2030-01-02T00:20:00Z', 60, 0.2, 'failed')]}})
        self.engine._store(root, record)
        return root

    def test_every_research_job_counts_under_the_research_step(self):
        root = self.desk_synthesis()
        row = next(row for row in self.view(root)['timeline'] if row['name'] == 'research')
        self.assertEqual((row['attempts'], row['seconds'], row['dollars']), (4, 530.0, 1.5))

    def test_the_stop_says_what_the_last_try_of_the_research_took(self):
        root = self.desk_synthesis()
        self.engine._problem(root, 'research', 'failed', 'It stopped.', 'Kept.')
        self.assertEqual(self.view(root)['problem']['research'], {
            'rounds': 2, 'jobs': 3, 'seconds': 480.0, 'dollars': 1.4, 'most': 3,
            'drafted': False})
        (root / '.studio-research/.harness-research').mkdir(parents=True)
        (root / '.studio-research/.harness-research/synthesis.json').write_text('{}')
        self.assertIs(self.view(root)['problem']['research']['drafted'], True)
        self.engine._problem(root, 'outline', 'failed', 'It stopped.', 'Kept.')
        self.assertNotIn('research', self.view(root)['problem'])

    def test_the_round_in_hand_is_said_while_it_runs(self):
        root = self.desk_synthesis()
        self.assertEqual(jobs.first(self.engine._load(root)).name, 'research')
        run = self.engine._run(root)
        run.workers['research:review-2'] = {
            'label': 'Independently checking the corrected research (round 2 of 3)',
            'started_at': 'now', 'lines': []}
        try:
            shown = self.view(root)
        finally:
            run.workers.clear()
        self.assertEqual((shown['state'], shown['sentence']), (
            'working', 'Independently checking the corrected research (round 2 of 3).'))
        self.assertEqual(shown['workers'][0]['label'],
                         'Independently checking the corrected research (round 2 of 3)')


PNG_BYTES = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
             b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf'
             b'\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`'
             b'\x82')


class DocumentTests(StudioCase):

    def test_an_upload_waits_under_sources_and_is_taken_in(self):
        read = []

        def reads(tools, job):
            read.append(tools.read_input('notes')[1])
            self.workers.classification(tools, job)

        self.workers.then('classification', reads)
        root = self.start(route='document', source={'kind': 'upload', 'name': 'notes.md'},
                          uploads={'notes.md': b'# Notes\n\nCapacity holds with two.\n'})
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertIn('Capacity holds with two.', read[0])
        self.assertFalse((root / 'sources' / 'incoming').exists())
        self.assertEqual(self.view(root)['desk']['sources'][0]['name'], 'notes.md')

    def test_an_upload_that_was_not_sent_starts_nothing(self):
        before = self.log()
        with self.assertRaises(WorkspaceError) as caught:
            self.start(route='document', source={'kind': 'upload', 'name': 'notes.md'})
        self.assertIn('"notes.md" was not sent', str(caught.exception))
        self.assertEqual(self.log(), before)
        self.assertEqual(self.engine.every(), [])


class ExistingTests(StudioCase):
    DECK = b'PK\x03\x04' + b'stand-in deck'

    def test_a_google_deck_while_google_is_not_reached_starts_nothing(self):
        self.slides.run.drive = False
        before = self.log()
        with self.assertRaises(WorkspaceError) as caught:
            self.start(route='existing', level='polish',
                       source={'kind': 'google', 'link': 'abc123'})
        self.assertIn('Sign in to Google', str(caught.exception))
        self.assertEqual(self.log(), before)


class PictureTests(StudioCase):
    def test_progress_images_are_named_by_current_refs_and_do_not_replace_the_gate(self):
        from runner import build_progress
        root = self.start()
        self.assertEqual(self.waiting(root), 'gate:build')
        basis = build.read_state(root)['start']['folder']
        shown = build_progress.view(root, basis)
        self.assertTrue(shown['slides'])
        ref = shown['slides'][0]['ref']
        self.assertTrue(self.engine.picture(root, 'progress', ref).startswith(b'\x89PNG'))
        self.assertIsNone(self.engine.view(root)['build_progress'])
        with self.assertRaises(FileNotFoundError):
            self.engine.picture(root, 'progress', '../../private')

    def test_only_pictures_the_steps_recorded_are_served(self):
        root = self.start()
        self.assertEqual(self.waiting(root), 'gate:build')
        (root / 'secret.png').write_bytes(runner_support.png())
        for kind, ref in (('build', 99), ('build', '../secret'), ('look', 7),
                          ('original', 1)):
            with self.subTest(kind=kind, ref=ref):
                with self.assertRaises((FileNotFoundError, WorkspaceError)):
                    self.engine.picture(root, kind, ref)
        with self.assertRaises(WorkspaceError):
            self.engine.picture(root, 'secret', 1)


class LockTests(StudioCase):
    def test_a_render_in_hand_never_holds_up_a_decision_on_another_deck(self):
        other = self.start(title='Another deck')
        expected = self.view(other)['desk']['expected']
        entered, release, real = threading.Event(), threading.Event(), build.render
        slow = []

        def held(root, *args, **named):
            if Path(root).name != other.name:
                entered.set()
                release.wait(30)
            return real(root, *args, **named)

        with mock.patch.object(build, 'render', held):
            going = threading.Thread(target=lambda: slow.append(self.start()))
            going.start()                           # a new deck runs to its render
            try:
                self.assertTrue(entered.wait(60), 'the render was reached')
                clock = time.monotonic()
                drawn = len(self.workers.of('section'))
                self.engine.desk_deck_note(other, 'Shorter, please.', expected)
                self.assertLess(time.monotonic() - clock, 10,
                                "a decision waited for another deck's render")
                self.assertEqual(self.waiting(other), 'gate:build')
                self.assertIn('Shorter, please.', self.workers.of('section')[drawn].task)
            finally:
                release.set()
                going.join(60)
        self.assertEqual(self.waiting(slow[0]), 'gate:build')


class ListTests(StudioCase):
    def test_decks_are_listed_by_what_they_need(self):
        waiting = self.start()
        done = self.start(title='Second deck')
        self.deliver_desk(done)
        listed = self.engine.decks()
        self.assertEqual([entry['id'] for entry in listed['needs']], [waiting.name])
        self.assertEqual([entry['id'] for entry in listed['finished']], [done.name])
        self.assertTrue(listed['finished'][0]['link'].startswith('https://'))
        self.assertEqual(listed['working'], [])
        self.assertEqual(listed['elsewhere'], [])


class DrivenTests(StudioCase):
    def test_a_deck_folder_reached_through_a_link_or_dots_is_not_driven(self):
        root = self.start()
        space = self.engine.space().root
        self.assertEqual(self.engine.driven(root), root)
        self.assertEqual(self.engine.every(), [root])
        outside = self.base / 'elsewhere' / 'outside'
        outside.mkdir(parents=True)
        decks.write_run(outside, {'schema': 1, 'id': 'outside'})
        linked = space / 'linked'
        linked.symlink_to(outside, target_is_directory=True)
        self.assertIsNone(self.engine.driven(linked))
        self.assertIsNone(self.engine.driven(space / '..' / space.name / root.name))
        self.assertIsNone(self.engine.driven(space / 'linked' / '..' / root.name))
        self.assertEqual(self.engine.every(), [root])


if __name__ == '__main__':
    unittest.main()


class ModelProfileTests(StudioCase):
    def configure(self, agent='claude'):
        from studio_core import studios_config
        studios_config.update({'assistant': {'agent': agent}, 'models': {
            'schema': 1, 'agent': agent, 'mode': 'by_task', 'profiles': {
                name: {'selection': 'explicit', 'model': name + '-model', 'effort': effort}
                for name, effort in [('quick', 'low'), ('main', 'medium'), ('complex', 'high')]}}})

    def test_profiles_reach_real_dispatch_and_are_saved_across_settings_changes(self):
        from studio_core import studios_config
        self.configure()
        from runner import setup
        self.assertEqual(setup.describe(self.engine)['shared']['models']['mode'], 'by_task')
        self.workers.found = [grave]
        def later(tools, job):
            # Settings change once the outline is drafted, before the deck is drawn.
            studios_config.update({'models': {'profiles': {'main': {'model': 'later'}}}})
            return self.workers.text_check(tools, job)
        self.workers.then('text-check', later)
        root = self.start()
        self.assertEqual(self.workers.of('outline')[0].model, 'quick-model')
        self.assertEqual(self.waiting(root), 'gate:build')
        choices = self.record(root)['model_jobs']
        # Settings saved before the kinds of work: Writing and Checking take Main's model.
        self.assertTrue(any(c['profile'] == 'writing' and c['model'] == 'main-model' for c in choices))
        self.assertTrue(any(c['profile'] == 'checking' and c['model'] == 'main-model' for c in choices))
        self.assertTrue(all(c['model'] != 'later' for c in choices))
        for choice in choices:
            self.assertIsNone(choice['actual_model'])
        for kind, job, spec in self.workers.jobs:
            if kind == 'review':
                self.assertEqual((job.model, job.effort), ('main-model', 'medium'))
            elif kind == 'section':
                self.assertIn(job.model, ('main-model', 'complex-model'))

    def test_codex_and_explicit_work_override(self):
        self.configure('codex')
        root = self.start(title='By task')
        self.assertEqual(self.record(root)['model_profiles']['mode'], 'by_task')
        self.assertEqual(self.workers.of('outline')[-1].model, 'quick-model')
        other = self.start(title='Work override', agent='codex', model='own-model', effort='high')
        self.assertEqual(self.record(other)['model_profiles']['mode'], 'single')
        self.assertEqual(self.workers.of('outline')[-1].model, 'own-model')


class PreviewRepairEngineTests(StudioCase):
    def test_a_slide_the_preview_flags_is_drawn_again_before_the_review(self):
        second = OUTLINE['slides'][1]['id']
        self.slides.run.screens = {second: [
            {'severity': 'error', 'code': 'text-overflow', 'detail': 'Text runs off.'}]}
        root = self.start()
        self.assertEqual(self.waiting(root), 'gate:build')
        state = build.read_state(root)
        # The first round went back to its composer before any review; later rounds within
        # REPAIRS too; the review came after.
        self.assertEqual(state['repaired'], build.REPAIRS)
        self.assertIsNone(state['rounds'][0]['review'])
        self.assertTrue(state['rounds'][0]['preview_repair'])
        self.assertIsNotNone(state['rounds'][-1]['review'])
        told = [spec for seen, job, spec in self.workers.jobs if seen == 'section'
                and any(entry['name'] == 'what the preview found' for entry in spec['inputs'])]
        self.assertTrue(told)


class PreviewLinkTests(StudioCase):
    def test_a_pooled_preview_is_never_listed_as_a_file_the_deck_left(self):
        root = self.start()
        kept = root / build.BUILD / 'drive-preview.json'
        kept.parent.mkdir(parents=True, exist_ok=True)
        own = {'name': 'Preview: Rolling restarts', 'id': 'file-1',
               'url': 'https://docs.example.com/file-1'}
        kept.write_text(json.dumps(own))
        self.assertEqual([entry['url'] for entry in self.engine.leaving(root)['drive']],
                         ['https://docs.example.com/file-1'])
        kept.write_text(json.dumps({**own, 'pool': 'pool-2:7'}))
        self.assertEqual(self.engine.leaving(root)['drive'], [],
                         'its link may show another deck\'s slides by now')
