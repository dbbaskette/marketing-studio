"""Production runner transport with fictional evidence and the real pinned helper."""
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import threading
import time
import unittest

from runner_support import StudioCase, URL
from runner import engine as engines, research
from studio_core import research_contract as contract, research_session as parallel, research_transport, research_units
from studio_core.shared_runner.worker_tools import tidy
from synthesis_fixture import TEXT, dossier, review

# Text with double and trailing spaces and three blank lines, as Google Slides can read.
UNTIDY = 'Overview of  Synthetic  Queues   \n' + TEXT.replace('. More', '.  More') + '  \n\n\n\nDATA TSL \n'

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


def checks(content):
    """The check jobs of one round: a new training on a Harness Research with review units
    (1.6.0, #378) checks each unit that holds evidence and then the final unit; on an older one,
    one review."""
    return ['review'] * (content + 1 if RUNTIME and research_units.capability(RUNTIME) else 1)


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for pinned helper tests.')
class ParallelNativeTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.engine.parallel_research = True
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.workers.then('research-result', *([self.worker] * 12))
        self.barrier = threading.Barrier(3)
        self.phases = []
        self.reject_once = False

    def worker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        if 'questions' in payload and getattr(self, 'supplied', False):
            self.phases.append('investigate')
            source = next(s for s in tools._index() if s.get('offered'))
            # The outline names each offered source as the job's own tools do (#303).
            self.assertEqual([(e['id'], e['file'], e['origin'], e['permission'])
                              for e in payload['source_outline']['sources']],
                             [(s['id'], s['file'], s['url'], s.get('permission') or 'selected')
                              for s in tools._index() if s.get('offered')])
            value = dossier(payload['worker'], source['file'], source['url'], 'selected')
            value['sources'][0]['original_file'] = source['original']
            value = {k: value[k] for k in ('schema', 'sources', 'facts')}
            value['gaps'] = []
        elif 'questions' in payload:
            self.phases.append('investigate')
            if self.barrier: self.barrier.wait(10)
            self.assertTrue(tools.save_source(URL)[0])
            source = tools._index()[0]
            value = dossier(payload['worker'], source['file'], source['url'])
            value = {k: value[k] for k in ('schema', 'sources', 'facts')}
            value['gaps'] = []
        elif 'evidence' in payload and 'review_template' not in payload:
            self.phases.append('synthesize')
            evidence = payload['evidence']
            value = dossier(payload['worker'])
            first = evidence['facts'][0]['id']
            value['findings'] = [{**copy.deepcopy(value['findings'][0]), 'id': q['id'],
                'summary': {'text': 'More than one instance keeps capacity.', 'kind': 'summary', 'refs': [first]},
                'support': [first], 'conditions': []} for q in payload['task']['planning_questions']]
            value['sections'][0]['blocks'][0]['refs'] = [first]
            value['brief'][0]['blocks'][0]['refs'] = [value['findings'][0]['id']]
            value = {k: value[k] for k in ('schema', 'findings', 'sections', 'brief')}
        else:
            self.phases.append('review')
            for source in tools._index(): self.assertTrue(tools.read_source(source['id'])[0])
            value = review(payload['review_template'])
        if getattr(self, 'source_metadata_alias', False) and 'questions' in payload:
            value['sources'][0].update(date='2026-10-01', unsupported_note='Synthetic unknown field')
            refused = tools.submit_artifact('research-result', json.dumps(value))
            self.assertFalse(refused[0], 'Unknown source fields must be refused inside the same job')
            self.assertIn('unsupported_note', refused[1])
            value['sources'][0].pop('unsupported_note')
        if getattr(self, 'fact_kind_correction', False) and 'questions' in payload:
            value['facts'][0]['kind'] = 'inference'
            refused = tools.submit_artifact('research-result', json.dumps(value))
            self.assertFalse(refused[0], 'Collection-only fact fields must be rejected before the job finishes')
            self.assertIn('Fact fact-a: unknown field(s) kind', refused[1])
            self.assertIn('Do not remove a kind label to turn an inference into a fact', refused[1])
            # The scripted author rechecks this quoted assertion; production never
            # discards the classification on its behalf.
            value['facts'][0].pop('kind')
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def test_default_new_run_is_versioned_parallel_and_publishes_reviewed_bundle(self):
        self.assertIs(inspect.signature(engines.Engine).parameters['parallel_research'].default, True)
        root = self.start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        record = self.engine._load(root)
        self.assertEqual(record['schema'], parallel.RECORD_SCHEMA)
        self.assertTrue(parallel.protocol(record))
        self.assertCountEqual(self.phases, ['investigate'] * 3 + ['synthesize'] + checks(3))
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(len({f['author'] for f in facts['facts']}), 3)
        self.assertEqual(shown['research_progress']['phase'], 'complete')
        self.assertNotIn('spending_policy', record)
        self.assertTrue(all(a.get('research_attempt') for name, entry in record['steps'].items()
                            if contract.job_round(name) for a in entry['attempts']))
        self.assertIn('active_seconds', shown['timing'])

    def test_incomplete_check_has_specific_retry_and_retained_work_message(self):
        from unittest.mock import patch
        from studio_core.research_quality import IncompleteCheck
        with patch.object(parallel.Workflow, 'run', side_effect=IncompleteCheck({'read': 1, 'total': 3, 'unread': 2})):
            root = self.start()
        problem = self.view(root)['problem']
        self.assertEqual(problem['label'], 'Retry independent check')
        self.assertEqual(problem['action'], 'retry')
        self.assertIn('does not repeat investigation', problem['kept'])
        self.assertEqual(self.engine._load(root)['problem']['check_incomplete']['unread'], 2)

    def test_stop_keeps_terminal_agent_observation_without_accepting_research(self):
        from unittest.mock import patch
        def stopping(root, task, invoke, sources, **options):
            tell = options['progress']
            tell({'phase':'investigate','agents':{'count':1,'active':[]}})
            self.engine._run(root).stop.set()
            tell({'phase':'investigate','agents':{'count':1,'active':[]}})
            self.assertEqual(self.engine._load(root)['research_execution']['progress']['phase'], 'stopping')
            tell({'phase':'investigate','agents':{'count':0,'active':[]}})
            raise InterruptedError('Synthetic confirmed stop')
        with patch.object(parallel.Workflow, 'run', side_effect=stopping):
            root = self.start()
        progress = self.view(root)['research_progress']
        self.assertEqual(progress['phase'], 'stopped')
        self.assertEqual(progress['agents']['count'], 0)
        self.assertFalse((root/'research/output.json').exists())

    def test_source_metadata_is_checked_before_the_helper_registry_without_recollecting(self):
        self.source_metadata_alias = True
        root = self.start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['sources'])
        self.assertTrue(all(source.get('source_date') == '2026-10-01' for source in facts['sources']))
        self.assertTrue(all('date' not in source and 'unsupported_note' not in source for source in facts['sources']))
        self.assertCountEqual(self.phases, ['investigate'] * 3 + ['synthesize'] + checks(3))

    def test_fact_kind_correction_stays_in_the_same_investigator_invocation(self):
        self.fact_kind_correction = True
        root = self.start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertTrue(all('kind' not in fact for fact in facts['facts']))
        self.assertCountEqual(self.phases, ['investigate'] * 3 + ['synthesize'] + checks(3))

    def test_parallel_research_prepares_one_topics_review_before_materials(self):
        from runner import training_plan
        self.engine.plan_first = True
        self.assertIs(inspect.signature(engines.Engine).parameters['plan_first'].default, True)
        root = self.start(flow='desk')
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        record = self.engine._load(root)
        self.assertEqual(record['schema'], training_plan.RECORD_SCHEMA)
        self.assertTrue(parallel.protocol(record))
        self.assertEqual(shown['research_progress']['phase'], 'complete')
        self.assertEqual(shown['state'], 'waiting')
        self.assertTrue(shown['training_plan']['levels'][0]['modules'])
        self.assertFalse(self.workers.of('document'))
        self.assertCountEqual(self.phases, ['investigate'] * 3 + ['synthesize'] + checks(3))

    def test_missing_or_unknown_parallel_protocol_refuses_resume(self):
        self.barrier = None
        root = self.start()
        record = self.engine._load(root)
        record['research_execution']['schema'] = 99
        self.engine._store(root, record)
        from workspace import WorkspaceError
        with self.assertRaisesRegex(WorkspaceError, 'parallel research protocol'):
            engines.read_record(root)

    def test_source_backed_retry_reopens_the_same_training_without_a_second_creation(self):
        from unittest.mock import patch
        from runner_support import FORM
        from runner import pipeline
        from studio_core import research_sources
        source=research_sources.Sources(self.engine.space().root / '.research-sources')
        draft=source.create()
        draft=source.mutate(draft['id'],draft['revision'],'capture',kind='text',text=TEXT)
        form=pipeline.check_form({**FORM,'flow':'desk'})
        reference={'id':draft['id'],'expected':draft['revision']}
        with patch.object(self.engine,'wake'):
            first=self.engine.start(form,research_inputs=reference)
            second=self.engine.start(form,research_inputs=reference)
        self.assertEqual(first,second)
        self.assertEqual(self.engine._load(Path(first['path']))['research_from'],{'documents':True,'sites':[],'web':False})

    def supplied_start(self, text):
        """A training researched only from pasted text, untidy as a Google Slides deck reads."""
        from unittest.mock import patch
        from runner_support import FORM
        from runner import pipeline
        from studio_core import research_sources
        self.supplied, self.barrier = True, None
        store = research_sources.Sources(self.engine.space().root / '.research-sources')
        draft = store.create()
        draft = store.mutate(draft['id'], draft['revision'], 'capture', kind='text', name='Synthetic deck', text=text)
        with patch.object(self.engine, 'wake'):
            started = self.engine.start(pipeline.check_form({**FORM, 'flow': 'desk'}),
                                        research_inputs={'id': draft['id'], 'expected': draft['revision']})
        root = Path(started['path'])
        self.engine.wake(root)
        return root

    def registered(self, root):
        entries = json.loads((parallel.case_for(root) / 'sources.json').read_text())['entries']
        return [entry['capture_sha256'] for entry in entries if entry.get('capture_sha256')]

    def researched(self, root):
        """The reviewed research bundle. Only research is scripted for these trainings, so
        a later step may stop; research itself must not."""
        problem = json.dumps(self.view(root)['problem'])
        self.assertNotIn('harness-research', problem)
        self.assertNotIn('capture differs', problem)
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        return facts

    def test_untidy_supplied_text_passes_the_dossier_check(self):
        root = self.supplied_start(UNTIDY)
        facts = self.researched(root)
        self.assertEqual({source['permission'] for source in facts['sources']}, {'selected'})
        supplied = self.engine._sources(root, self.engine._load(root))[1][0]['text']
        self.assertNotEqual(tidy(supplied), supplied, 'The supplied text is not already tidy')
        self.assertEqual(self.registered(root), [hashlib.sha256(tidy(supplied).encode()).hexdigest()])

    def test_a_supplied_document_leaves_no_folder_of_this_computer_in_the_published_bundle(self):
        # #550: a research bundle built from supplied documents with parallel collection is
        # shared; it names no folder of the computer that made it, in any published file.
        import tempfile
        root = self.supplied_start(TEXT)
        facts = self.researched(root)
        if not contract.labels_supplied(RUNTIME):
            self.skipTest('The bundle names no folder only on a Harness Research that records a supplied document as supplied:<name> (1.6.0 and newer); an older one records the folder it was taken from.')
        origins = {source['origin'] for source in facts['sources']}
        self.assertTrue(origins and all(origin.startswith('supplied:') for origin in origins), origins)
        places = {str(root), str(root.resolve()), tempfile.gettempdir(),
                  str(Path(tempfile.gettempdir()).resolve()), str(Path.home())}
        published = [path for path in (root / 'research').rglob('*') if path.is_file()]
        self.assertTrue(published)
        for path in published:
            said = path.read_bytes().decode('utf-8', 'replace')
            for place in places:
                self.assertNotIn(place, said, path.name)

    def test_try_again_recovers_a_capture_registered_untidied(self):
        # #295: an earlier version registered the text as it came, the kept investigations
        # hold the tidied text the assistant read, and the dossier check refused synthesis.
        from unittest.mock import patch
        with patch.object(parallel, 'capture_text', lambda text, kept: text):
            root = self.supplied_start(UNTIDY)
        problem = self.view(root)['problem']
        self.assertIn('capture differs from the accepted asset inventory', json.dumps(problem))
        self.assertEqual(self.phases[-1], 'synthesize')
        self.assertIn('investigate', self.phases)
        self.phases.clear()
        self.engine.act(root, 'retry')
        self.researched(root)
        # One supplied document is one source, so one unit holds evidence.
        self.assertEqual(self.phases, ['synthesize'] + checks(1),
                         'Try again keeps the investigations; synthesis and review run again')


@unittest.skipUnless(RUNTIME and research_units.capability(RUNTIME), 'Harness Research with review units required.')
class UnitNativeTests(StudioCase):
    """A new training's check in review units through the native jobs (#378)."""

    def setUp(self):
        super().setUp()
        self.engine.parallel_research = True
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.workers.then('research-result', *([self.worker] * 12))
        self.barrier, self.phases, self.units, self.fail_unit = None, [], [], False

    def worker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        if 'review_template' in payload:
            unit = payload['review_template']['unit']
            self.units.append((unit, sorted(source['file'] for source in tools._index())))
            if self.fail_unit and unit != research_units.FINAL:
                from runner import agents
                self.fail_unit = False
                self.phases.append('review')
                return agents.Outcome(False, 'failed', 'Synthetic unit check failed.', seconds=1)
        return ParallelNativeTests.worker(self, tools, job)

    def test_each_unit_is_its_own_job_with_its_own_captures_and_a_failed_one_is_checked_again_alone(self):
        self.fail_unit = True
        root = self.start()
        self.assertEqual(self.engine._load(root)['research_execution']['review'], research_units.entry(RUNTIME))
        self.assertTrue(self.view(root)['problem'])
        # The stop names the part that failed and keeps the others' checks (#379), in the
        # words the progress says it in.
        saved = self.engine._load(root)
        progress = saved['research_execution']['progress']
        ended = progress['ended_in']
        self.assertEqual((ended['part'], ended['how'], ended['total']), ('review-unit', 'failed', 4))
        # One ending, one sentence: the stop says what the progress says, counted once the
        # peers that were still working had ended (both kept).
        self.assertEqual(saved['problem']['what'], ended['said'])
        self.assertRegex(ended['said'], r'^The independent check of “.+\?” could not finish: Synthetic unit check '
                         r'failed\. The checks of the other 2 parts are kept; only what is left is checked again, then '
                         r'the whole research\.$')
        self.assertEqual(sorted(unit['status'] for unit in progress['review_units']), ['failed', 'kept', 'kept', 'waiting'])
        self.assertEqual(research_transport.describe(progress), ended['said'])
        self.assertEqual(len(self.units), 3, 'every content unit ran; the final waits')
        self.assertTrue(all(len(files) == 1 for _, files in self.units), 'a content unit holds its own capture only')
        self.phases.clear(); self.units.clear()
        self.engine.act(root, 'retry')
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.phases, ['review', 'review'], 'investigation and synthesis are kept')
        self.assertEqual(self.units[-1][0], research_units.FINAL)
        names = [name for name in self.engine._load(root)['steps'] if contract.job_round(name) == ('review', 1)]
        self.assertEqual(len(names), 4)
        self.assertIn('research:review-1-final', names)

    def test_a_research_stop_is_said_in_the_run_s_one_sentence_and_nothing_else_claims_kept(self):
        # Stop while an area is gathered: the training's stop text is the run's sentence, and
        # the generic line that everything finished is kept is not shown with it (#379).
        def worker(tools, job):
            payload = json.loads(tools.read_input('research-task')[1])
            if 'source_outline' in payload and not getattr(self, 'stopping', False):
                self.stopping = True
                root = self.engine.trainings()[0]
                threading.Thread(target=self.engine.act, args=(root, 'stop'), daemon=True).start()
                deadline = time.monotonic() + 10
                while not self.engine._run(root).stop.is_set() and time.monotonic() < deadline:
                    time.sleep(0.02)
            return self.worker(tools, job)
        self.workers.queued['research-result'][:] = [worker] * 12
        root = self.start()
        deadline = time.monotonic() + 10
        while self.view(root)['state'] != 'stopped' and time.monotonic() < deadline:
            time.sleep(0.05)
        view = self.view(root)
        progress = self.engine._load(root)['research_execution']['progress']
        said = progress['ended_in']['said']
        self.assertEqual((progress['ended_in']['part'], progress['ended_in']['how']), ('research', 'stopped'))
        self.assertTrue(said.startswith('Research stopped. '), said)
        self.assertEqual((view['state'], view['sentence']), ('stopped', said))
        self.assertNotIn('finished before it is kept', view['sentence'])

    def test_a_part_out_of_time_is_named_with_what_is_kept_and_offers_more_time(self):
        from runner import agents
        def worker(tools, job):
            payload = json.loads(tools.read_input('research-task')[1])
            if 'review_template' in payload and payload['review_template']['unit'] != research_units.FINAL \
                    and not getattr(self, 'timed', False):
                self.timed = True
                return agents.Outcome(False, 'timeout', 'Synthetic: the job reached its time limit.', seconds=900)
            return self.worker(tools, job)
        self.workers.queued['research-result'][:] = [worker] * 12
        root = self.start()
        saved = self.engine._load(root)
        ended = saved['research_execution']['progress']['ended_in']
        self.assertEqual((ended['part'], ended['how']), ('review-unit', 'timed-out'))
        self.assertEqual(saved['problem']['what'], ended['said'])
        self.assertRegex(ended['said'], r'^The independent check of “.+\?” ran out of time: ')
        self.assertIn(' are kept; only what is left is checked again, then the whole research.', ended['said'])
        self.assertEqual(saved['problem']['action'], 'more-time')
        self.assertTrue(saved['problem']['kept'].startswith('It ran out of the time a step may take'))
