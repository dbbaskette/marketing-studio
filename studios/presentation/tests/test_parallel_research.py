"""Production runner transport with fictional evidence and the real pinned helper."""
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import threading
import unittest

from runner_support import StudioCase, URL
from runner import engine as engines, research
from studio_core import research_contract as contract, research_session as parallel, research_units
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for pinned helper tests.')
class ParallelNativeTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.engine.parallel_research = True
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.workers.then('research-result', *([self.worker] * 12))
        self.barrier = threading.Barrier(2)
        self.phases = []
        self.reject_once = False

    def worker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        if 'questions' in payload and getattr(self, 'supplied', False):
            self.phases.append('investigate')
            source = next(s for s in tools._index() if s.get('offered'))
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
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def test_default_new_run_is_versioned_parallel_and_publishes_reviewed_bundle(self):
        self.assertIs(inspect.signature(engines.Engine).parameters['parallel_research'].default, True)
        root = self.start(research=True, research_questions=['Synthetic capacity question?', 'Synthetic health question?'])
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown['problem'])
        record = self.engine._load(root)
        self.assertEqual(record['schema'], 4)
        self.assertTrue(parallel.protocol(record))
        # A new deck on Harness Research 1.6.0 checks each unit that holds evidence, then the
        # final unit (#378); on an older one, one review.
        self.assertCountEqual(self.phases, ['investigate'] * 2 + ['synthesize']
                              + ['review'] * (3 if research_units.capability(RUNTIME) else 1))
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(len({f['author'] for f in facts['facts']}), 2)
        self.assertEqual(shown['research_progress']['phase'], 'complete')
        self.assertEqual(record['limits'], {'step_seconds': 1350})
        self.assertTrue(all(a.get('research_attempt') for name, entry in record['steps'].items()
                            if contract.job_round(name) for a in entry['tries']))


    def test_source_backed_retry_reopens_the_same_deck_without_a_second_creation(self):
        from unittest.mock import patch
        from runner_support import FORM
        from studio_core import research_sources
        source=research_sources.Sources(self.engine.space().root / '.research-sources')
        draft=source.create()
        draft=source.mutate(draft['id'],draft['revision'],'capture',kind='text',text=TEXT)
        form={**FORM,'flow':'desk','research':True}
        reference={'id':draft['id'],'expected':draft['revision']}
        with patch.object(self.engine,'wake'):
            first=self.engine.start(form,research_inputs=reference)
            second=self.engine.start(form,research_inputs=reference)
        self.assertEqual(first,second)
        root=Path(first['path'])
        self.assertEqual(self.engine._load(root)['form']['research_from'],{'documents':True,'sites':[],'web':False})

    def test_untidy_supplied_text_passes_the_dossier_check(self):
        # #295: text with double and trailing spaces and three blank lines, as Google
        # Slides can read, is registered as the tidied text the assistant reads and quotes.
        from runner_support import FORM
        from studio_core import research_sources
        from studio_core.shared_runner.worker_tools import tidy
        self.supplied, self.barrier = True, None
        untidy = 'Overview of  Synthetic  Queues   \n' + TEXT.replace('. More', '.  More') + '  \n\n\n\nDATA TSL \n'
        store = research_sources.Sources(self.engine.space().root / '.research-sources')
        draft = store.create()
        draft = store.mutate(draft['id'], draft['revision'], 'capture', kind='text', name='Synthetic deck', text=untidy)
        started = self.engine.start({**FORM, 'flow': 'desk', 'research': True},
                                    research_inputs={'id': draft['id'], 'expected': draft['revision']})
        root = Path(started['path'])
        problem = json.dumps(self.view(root)['problem'])
        self.assertNotIn('harness-research', problem)
        self.assertNotIn('capture differs', problem)
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual({source['permission'] for source in facts['sources']}, {'selected'})
        entries = json.loads((parallel.case_for(root) / 'sources.json').read_text())['entries']
        registered = [entry['capture_sha256'] for entry in entries if entry.get('capture_sha256')]
        self.assertEqual(len(registered), 1)
        kept = (parallel.case_for(root) / facts['sources'][0]['file']).read_text()
        self.assertNotEqual(kept, untidy)
        self.assertEqual(kept, tidy(kept))
        self.assertEqual(registered, [hashlib.sha256(kept.encode()).hexdigest()])
        # #550: the bundle, shared with a team, names no folder of the computer that made it,
        # only on a Harness Research that records a supplied document as supplied:<name> (1.6.0 and newer); an older one records the folder it was taken from.
        if contract.labels_supplied(RUNTIME):
            import tempfile
            self.assertTrue(all(source['origin'].startswith('supplied:') for source in facts['sources']))
            places = {str(root), str(root.resolve()), tempfile.gettempdir(),
                      str(Path(tempfile.gettempdir()).resolve()), str(Path.home())}
            published = [path for path in (root / 'research').rglob('*') if path.is_file()]
            self.assertTrue(published)
            for path in published:
                said = path.read_bytes().decode('utf-8', 'replace')
                for place in places:
                    self.assertNotIn(place, said, path.name)


@unittest.skipUnless(RUNTIME and research_units.capability(RUNTIME), 'Harness Research with review units required.')
class UnitNativeTests(StudioCase):
    """A new deck's check in review units through the native jobs (#378)."""

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
        root = self.start(research=True, research_questions=['Synthetic capacity question?', 'Synthetic health question?'])
        self.assertEqual(self.engine._load(root)['research_execution']['review'], research_units.entry(RUNTIME))
        self.assertTrue(self.view(root)['problem'])
        self.assertEqual(len(self.units), 2, 'every content unit ran; the final waits')
        self.assertTrue(all(len(files) == 1 for _, files in self.units), 'a content unit holds its own capture only')
        self.phases.clear(); self.units.clear()
        self.engine.act(root, 'retry')
        facts, _ = contract.read_bundle(root / 'research')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.phases, ['review', 'review'], 'investigation and synthesis are kept')
        self.assertEqual(self.units[-1][0], research_units.FINAL)
        names = [name for name in self.engine._load(root)['steps'] if contract.job_round(name) == ('review', 1)]
        self.assertEqual(len(names), 3)
        self.assertIn('research:review-1-final', names)
