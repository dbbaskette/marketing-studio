import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from runner_support import StudioCase, URL
from runner import research
from studio_core import research_contract, review_policy
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


def updated_helper(folder: Path) -> tuple[Path, Path]:
    """Harness Research as its installer leaves it after an update: `current` names a
    newer version, which must not run here, and the version a run started with is retained."""
    shared = folder / 'Harness Research'
    version = json.loads((Path(RUNTIME) / 'package.json').read_text())['version']
    old = shared / 'versions' / (version + '-' + 'a' * 20)
    newer = shared / 'versions' / ('9.9.9-' + 'b' * 20)
    for kept in (old, newer):
        shutil.copytree(RUNTIME, kept, ignore=shutil.ignore_patterns('tests', 'docs'))
    (newer / 'scripts/harness-research.mjs').write_text(
        "console.error('This updated helper must not be used.'); process.exit(3);\n")
    (shared / 'current').symlink_to('versions/' + old.name)
    return shared, old


def update(shared: Path) -> None:
    (shared / 'current').unlink()
    (shared / 'current').symlink_to('versions/' + '9.9.9-' + 'b' * 20)

@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for the real helper integration.')
class SynthesisIntegrationTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.research = research.Research(Path(RUNTIME))
        self.web.page(URL, TEXT, 'text/plain')
        self.workers.then('research-result', self.author, self.checker)

    def author(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        self.assertTrue(tools.save_source(URL)[0])
        source = tools._index()[0]
        value = dossier(payload['worker'], source['file'], source['url'])
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def checker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        self.assertTrue(tools.read_source('s1')[0])
        accepted = tools.submit_artifact('research-result', json.dumps(review(payload['review_template'])))
        self.assertTrue(accepted[0], accepted)

    def test_new_deck_uses_reviewed_report_then_combined_direction_gate(self):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            root = self.start(research=True)
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(shown['gate']['name'], 'gate:outline')
        self.assertEqual(self.engine._load(root)['schema'], 3)
        facts, manifest = research_contract.read_bundle(root / 'research')
        self.assertIn('presentation', facts['purpose'])
        self.assertEqual(len(self.workers.of('research-result')), 2)
        self.assertFalse((root / '.harness-research/research.json').exists())
        self.assertIn('What to explain first', (root / 'research/brief.md').read_text())
        self.assertNotEqual(facts['review']['worker'], self.engine._load(root).get('author'))
        self.assertEqual(facts['review']['digest'], manifest['digest'])

    def test_existing_record_does_not_switch_formats_on_resume(self):
        from stand_ins.research import stand_in
        self.research = stand_in()
        root = self.start(research=True)
        self.assertNotIn('research_contract', self.engine._load(root))
        self.research = research.Research(Path(RUNTIME))
        self.assertNotIn('research_contract', self.engine._load(root))

    def test_stopping_a_research_worker_keeps_the_draft_without_a_failure(self):
        from runner.agents import Outcome
        self.workers.queued['research-result'] = [lambda tools, job: Outcome(False, 'stopped', 'Stopped')]
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start(research=True)
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertFalse((root / 'research/output.json').exists())
        entry = self.engine._load(root)['steps']['research:author-1']
        self.assertIn('stopped', str(entry))

    def test_a_research_job_that_runs_out_of_time_offers_more_time(self):
        from runner.agents import Outcome
        slow = 'It did not finish in 900 seconds, so it was stopped.'
        self.workers.queued['research-result'] = [
            lambda tools, job: Outcome(False, 'timeout', slow), self.author, self.checker]
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start(research=True)
        problem = self.view(root)['problem']
        self.assertEqual((problem['action'], problem['seconds']), ('more-time', 900))
        self.assertTrue(problem['why'].startswith('The research ran out of the time a step may '
                                                  'take: it was stopped after 15 minutes.'))
        entry = self.engine._load(root)['steps']['research:author-1']
        self.assertEqual((entry['tries'][0]['outcome'], entry['tries'][0]['error']),
                         ('failed', slow))
        self.engine.act(root, 'more-time')
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual([job.limits.seconds for job in self.workers.of('research-result')],
                         [900, 1800, 1800])

    def test_finding_marks_use_synthesis_ids_and_never_rewrite_the_checked_report(self):
        def authored(tools, job):
            payload = json.loads(tools.read_input('research-task')[1])
            self.assertTrue(tools.save_source(URL)[0])
            source = tools._index()[0]
            value = dossier(payload['worker'], source['file'], source['url'])
            value['findings'][0]['id'] = 'finding-first'
            value['findings'][1]['id'] = 'finding-second'
            value['brief'][0]['blocks'][0]['refs'] = ['finding-first']
            self.assertTrue(tools.submit_artifact('research-result', json.dumps(value))[0])
        self.workers.queued['research-result'] = [authored, self.checker, authored, self.checker]
        root = self.start(research=True)
        self.decide(root)  # research plan
        self.assertEqual(self.waiting(root), 'gate:research')
        self.decide(root, decision='changes', note='Explain this boundary.',
                    extra={'again': {'finding-first': 'Clarify the boundary.'}})
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual(self.waiting(root), 'gate:research')
        facts, before = research_contract.read_bundle(root / 'research')
        self.decide(root, extra={'left_out': ['finding-second']})
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual(self.waiting(root), 'gate:outline')
        self.assertEqual(research_contract.read_bundle(root / 'research')[1], before)
        self.assertEqual(self.engine._load(root)['research']['left_out'], ['finding-second'])
        self.assertEqual(self.engine._marked_ids(root, 'gate:research', {}), ['finding-first', 'finding-second'])

    def test_unfinished_research_continues_with_the_retained_helper_after_an_update(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        shared, old = updated_helper(Path(holder.name).resolve())
        self.research = research.Research(shared / 'current')
        root = self.start(research=True)
        update(shared)
        self.decide(root)  # research plan
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual(self.waiting(root), 'gate:research')
        research_contract.read_bundle(root / 'research')
        shutil.rmtree(old)
        self.workers.then('research-result', self.author, self.checker)
        self.decide(root, decision='changes', note='Explain this boundary.')
        self.assertIn('Restore it before continuing', str(self.view(root)['problem']))


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for the real helper integration.')
class SuppliedOriginalTests(StudioCase):
    """A document the person supplied is checked against what they sent: a web page against
    its own file, a Markdown document against its text, which is all it is."""

    PAGE = ('<html><body><p>' + TEXT + '</p></body></html>').encode()

    def setUp(self):
        super().setUp()
        self.research = research.Research(Path(RUNTIME))
        self.read = []
        self.workers.then('research-result', self.author, self.checker)

    def author(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        source = tools._index()[0]
        value = dossier(payload['worker'], source['file'], source['url'], 'selected')
        value['source_mode'] = 'mixed'
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def checker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        result = review(payload['review_template'])
        for entry, attested in zip(tools._index(), result['originals']):
            self.assertTrue(tools.read_source(entry['id'])[0])
            if 'original_sha256' in attested:
                ok, said = tools.read_source(entry['id'], original=True)
                self.read.append(said)
                attested['read_original'] = ok
                if not ok:
                    attested['access_error'] = said
        accepted = tools.submit_artifact('research-result', json.dumps(result))
        self.assertTrue(accepted[0], accepted)

    def deck(self, name, data):
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            return self.start(route='document', source={'kind': 'upload', 'name': name},
                              uploads={name: data}, research=True)

    def test_a_supplied_web_page_is_checked_against_the_file_that_was_sent(self):
        root = self.deck('notes.html', self.PAGE)
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual(len(self.read), 1)
        self.assertIn('original: sources/supplied/notes-html.original.html', self.read[0])
        self.assertIn('<p>Complete synthetic source context.', self.read[0])
        facts, _ = research_contract.read_bundle(root / 'research')
        self.assertEqual(facts['sources'][0]['original_file'],
                         'sources/supplied/notes-html.original.html')

    def test_a_supplied_markdown_document_is_its_own_capture(self):
        root = self.deck('notes.md', TEXT.encode())
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertEqual(self.read, [])
        facts, _ = research_contract.read_bundle(root / 'research')
        self.assertNotIn('original_file', facts['sources'][0])

    def test_a_check_that_still_objects_says_its_groups_and_what_its_rounds_took(self):
        def objects(tools, job):
            payload = json.loads(tools.read_input('research-task')[1])
            result = review(payload['review_template'], False)
            for attested in result['originals']:
                tools.read_source('s1', original=True)
            self.assertTrue(tools.submit_artifact('research-result', json.dumps(result))[0])
        self.workers.cost = 0.5
        self.workers.queued['research-result'] = [self.author, objects] * 3
        root = self.deck('notes.html', self.PAGE)
        why = self.view(root)['problem']['why']
        self.assertEqual(len(self.workers.of('research-result')), 6)
        self.assertIn('after 3 rounds of correction: 5 objections in 3 groups: 1 fact the check '
                      'calls narrow (fact-a:', why)
        self.assertTrue(why.endswith("This try's 6 research jobs took 9 seconds and $3.00."), why)
        self.assertIn('## 2 findings the check calls narrow',
                      (root / 'research/review.md').read_text())

    def test_a_check_that_cannot_read_the_original_stops_after_one_round(self):
        def blind(tools, job):
            payload = json.loads(tools.read_input('research-task')[1])
            result = review(payload['review_template'])
            for attested in result['originals']:
                if 'original_sha256' in attested:
                    attested.update(read_original=False, access_error='No tool serves it.')
            for item in result['facts']:
                item.update(verdict='narrow', note='The original could not be inspected.')
            self.assertTrue(tools.submit_artifact('research-result', json.dumps(result))[0])
        self.workers.queued['research-result'] = [self.author, blind]
        root = self.deck('notes.html', self.PAGE)
        view = self.view(root)
        self.assertEqual(len(self.workers.of('research-result')), 2)
        self.assertEqual(view['state'], 'failed')
        self.assertTrue(view['problem']['why'].startswith(
            'The research check could not read the original of "Synthetic source" (No tool '
            'serves it.). That is a studio problem, not a research problem: the report is not '
            'wrong, the check could not finish. Nothing to correct until the original is '
            'readable.'), view['problem']['why'])
        # The studio can serve it, so Try again runs the research again.
        self.workers.then('research-result', self.author, self.checker)
        self.engine.act(root, 'retry')
        self.assertIsNone(self.view(root)['problem'], self.view(root))
