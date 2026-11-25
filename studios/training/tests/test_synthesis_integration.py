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
    """Harness Research as its installer leaves it, with a newer version laid beside the one
    `current` names: (the shared folder, the version a run starts with)."""
    shared = folder / 'Harness Research'
    version = json.loads((Path(RUNTIME) / 'package.json').read_text())['version']
    old = shared / 'versions' / (version + '-' + 'a' * 8)
    newer = shared / 'versions' / ('9.9.9-' + 'b' * 8)
    for kept in (old, newer):
        shutil.copytree(RUNTIME, kept, ignore=shutil.ignore_patterns('tests', 'docs', '.git'))
    package = json.loads((newer / 'package.json').read_text())
    (newer / 'package.json').write_text(json.dumps({**package, 'version': '9.9.9'}))
    (shared / 'current').symlink_to('versions/' + old.name)
    return shared, old


def update(shared: Path) -> None:
    """What its installer does on an update: `current` moves to the newer version and every
    other version folder is removed."""
    (shared / 'current').unlink()
    (shared / 'current').symlink_to('versions/' + '9.9.9-' + 'b' * 8)
    for folder in (shared / 'versions').iterdir():
        if folder.name != '9.9.9-' + 'b' * 8:
            shutil.rmtree(folder)

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
        for finding_id in ('availability', 'zero-downtime'):
            value['findings'].append({**value['findings'][0], 'id': finding_id})
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def checker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        self.assertTrue(tools.read_source('s1')[0])
        accepted = tools.submit_artifact('research-result', json.dumps(review(payload['review_template'])))
        self.assertTrue(accepted[0], accepted)

    def test_new_training_saves_schema_two_and_retains_stable_citations(self):
        root = self.start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        self.assertEqual(self.engine._load(root)['schema'], 4)
        facts, manifest = research_contract.read_bundle(root / 'research')
        self.assertEqual(facts['topic'], 'Rolling restarts on the platform')
        self.assertIn('Selected materials:', facts['scope'])
        self.assertIn('learner tasks', facts['purpose'])
        self.assertIn('training', facts['purpose'])
        self.assertEqual(len(self.workers.of('research-result')), 2)
        self.assertFalse((root / '.harness-research/research.json').exists())
        import workspace
        self.assertEqual(workspace.research_record(root)['schema'], 2)
        self.assertIsNone(workspace.status(root)['gate'])
        self.assertEqual(next(step['status'] for step in shown['steps']
                              if step['id'] == 'blueprint'), 'done')
        self.assertEqual(workspace.load(root)['findings']['instance-min'], 'supported')
        self.assertTrue(workspace.research_intact(root, workspace.load(root)))
        capture = root / 'research' / facts['sources'][0]['snapshot'].removeprefix('research/')
        capture.write_text('Changed evidence')
        self.assertFalse(workspace.research_intact(root, workspace.load(root)))

    def test_source_handle_is_reconciled_before_handoff_and_independent_review_still_runs(self):
        def handled(tools, job):
            payload = json.loads(tools.read_input('research-task')[1])
            self.assertIn(research_contract.SOURCE_IDS, payload['return'])
            ok, shown = tools.save_source(URL)
            self.assertTrue(ok)
            self.assertIn('Dossier source ID: s1', shown)
            source = tools._index()[0]
            value = dossier(payload['worker'], source['file'], source['url'])
            for finding_id in ('availability', 'zero-downtime'):
                value['findings'].append({**value['findings'][0], 'id': finding_id})
            value['facts'][0]['citations'][0]['source'] = source['id']
            ok, said = tools.submit_artifact('research-result', json.dumps(value))
            self.assertTrue(ok, said)

        self.workers.queued['research-result'] = [handled, self.checker]
        root = self.start()
        shown = self.view(root)
        self.assertIsNone(shown['problem'], shown)
        facts, _ = research_contract.read_bundle(root / 'research')
        self.assertEqual(facts['facts'][0]['citations'][0]['source'], 'source-a')
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(len(self.workers.of('research-result')), 2)

    def test_stopping_a_research_worker_keeps_the_draft_without_a_failure(self):
        from runner.agents import Outcome
        self.workers.queued['research-result'] = [lambda tools, job: Outcome(False, 'stopped', 'Stopped')]
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'automatic'}):
            root = self.start()
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        self.assertFalse((root / 'research/output.json').exists())
        entry = self.engine._load(root)['steps']['research:author-1']
        self.assertIn('stopped', str(entry))


@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME for the real helper integration.')
class SuppliedOriginalTests(StudioCase):
    """A document the person supplied is checked against what they sent when that is a
    document of its own, and against its text when its text is all it is."""

    def setUp(self):
        super().setUp()
        self.research = research.Research(Path(RUNTIME))
        self.read = []
        self.workers.then('research-result', self.author, self.checker)

    def author(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        source = tools._index()[0]
        value = dossier(payload['worker'], source['file'], source['url'], 'selected')
        accepted = tools.submit_artifact('research-result', json.dumps(value))
        self.assertTrue(accepted[0], accepted)

    def checker(self, tools, job):
        payload = json.loads(tools.read_input('research-task')[1])
        result = review(payload['review_template'])
        for entry, attested in zip(tools._index(), result['originals']):
            if 'original_sha256' in attested:
                ok, said = tools.read_source(entry['id'], original=True)
                self.read.append(said)
                attested['read_original'] = ok
                if not ok:
                    attested['access_error'] = said
        accepted = tools.submit_artifact('research-result', json.dumps(result))
        self.assertTrue(accepted[0], accepted)

    def researched(self):
        self.hold_before('blueprint')   # the research done, where a saved run waited
        root = self.start(source_scope='supplied-only')
        self.send(root, 'handbook.md', TEXT)
        self.engine.supply(root, 'done')
        self.assertIsNone(self.view(root)['problem'], self.view(root))
        return research_contract.read_bundle(root / 'research')[0]

    def test_a_markdown_document_is_checked_against_its_text_alone(self):
        facts = self.researched()
        self.assertEqual(self.read, [])
        self.assertNotIn('original_file', facts['sources'][0])

    def test_a_document_of_its_own_is_checked_against_the_file_that_was_sent(self):
        self.documents.distinct = True
        facts = self.researched()
        self.assertEqual(len(self.read), 1)
        self.assertIn('original: sources/supplied/handbook.md', self.read[0])
        self.assertEqual(facts['sources'][0]['original_file'], 'sources/supplied/handbook.md')
