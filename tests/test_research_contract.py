import json
import os
from pathlib import Path
import tempfile
import unittest
import marketing_studio  # Puts the shared core on the import path.
from studio_core import research_contract as contract
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')

@unittest.skipUnless(RUNTIME, 'Set STUDIO_TEST_RESEARCH_RUNTIME to the exact locked release source for helper integration.')
class ResearchContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.txt'
        self.source.write_text(TEXT)
        self.calls = []
        self.task = dict(topic='Fictional example', audience='New learners', purpose='Teach the concept and its limits', scope='Synthetic only', source_mode='selected')

    def invoke(self, phase, guidance, payload, sources, fetch):
        self.calls.append((phase, payload['worker'], fetch))
        if phase == 'author':
            result = dossier(payload['worker'], permission='selected')
        else:
            result = review(payload['review_template'])
        return json.dumps(result), [dict(file='sources/source.txt', path=self.source, origin='https://example.invalid/docs', offered=True)]

    def test_real_helper_handoff_preserves_purpose_brief_sources_and_independent_review(self):
        facts, manifest = contract.Workflow(RUNTIME).run(self.root, self.task, self.invoke)
        self.assertEqual(facts['purpose'], self.task['purpose'])
        self.assertNotEqual(self.calls[0][1], self.calls[1][1])
        self.assertEqual([v[2] for v in self.calls], [False, False])
        contract.publish(self.root / contract.CASE, self.root / 'research')
        self.assertIn('What to explain first', (self.root / 'research/brief.md').read_text())
        self.assertEqual(facts['review']['digest'], manifest['digest'])
        capture = self.root / 'research' / facts['sources'][0]['snapshot'].removeprefix('research/')
        capture.write_text('Changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            contract.read_bundle(self.root / 'research')

    def test_needs_revision_keeps_draft_and_bounds_correction_cycles(self):
        def refusing(phase, guidance, payload, sources, fetch):
            text, captures = self.invoke(phase, guidance, payload, sources, fetch)
            return (json.dumps(review(payload['review_template'], False)) if phase == 'review' else text), captures
        with self.assertRaisesRegex(ValueError, 'needs changes'):
            contract.Workflow(RUNTIME).run(self.root, self.task, refusing)
        self.assertEqual(len(self.calls), 6)
        facts, _ = contract.read_bundle(self.root / contract.CASE / 'research', complete=False)
        self.assertEqual(facts['status'], 'needs-revision')

    def test_generated_permission_and_uncaptured_source_are_refused(self):
        def bad(phase, guidance, payload, sources, fetch):
            text, captures = self.invoke(phase, guidance, payload, sources, fetch)
            value = json.loads(text)
            value['sources'][0]['permission'] = 'public'
            return json.dumps(value), captures
        with self.assertRaisesRegex(ValueError, 'permission'):
            contract.Workflow(RUNTIME).run(self.root, self.task, bad)
        self.assertFalse((self.root / contract.CASE / '.harness-research/synthesis.json').exists())

    def test_links_and_legacy_bundles_cannot_be_read_as_schema_two(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / 'linked').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'links'):
            contract.inside(self.root, 'linked/private.txt')
        (self.root / 'output.json').write_text('{"schema":1,"owner":"harness-research"}')
        with self.assertRaisesRegex(ValueError, 'format'):
            contract.read_bundle(self.root)

    def test_explicit_import_preserves_resumable_state_and_refuses_legacy_conversion(self):
        contract.Workflow(RUNTIME).run(self.root, self.task, self.invoke)
        destination = self.root / 'new-studio'
        destination.mkdir()
        contract.adopt_case(self.root / contract.CASE, destination)
        contract.read_bundle(destination / 'research')
        self.assertTrue((destination / contract.CASE / '.harness-research/synthesis.json').is_file())
        # Repeating an unchanged handoff is safe.
        contract.adopt_case(self.root / contract.CASE, destination)
        (destination / '.harness-research').mkdir()
        (destination / '.harness-research/research.json').write_text('Legacy content')
        with self.assertRaisesRegex(ValueError, 'legacy'):
            contract.adopt_case(self.root / contract.CASE, destination)

    def test_importing_a_case_in_place_checks_its_working_sources(self):
        contract.Workflow(RUNTIME).run(self.root, self.task, self.invoke)
        case = self.root / contract.CASE
        (case / 'sources/source.txt').write_text('Changed original working capture')
        with self.assertRaisesRegex(ValueError, 'working research source changed'):
            contract.adopt_case(case, self.root)
        self.assertFalse((self.root / 'research/output.json').exists())

    def test_import_command_runs_as_a_standalone_file(self):
        import subprocess
        import sys
        contract.Workflow(RUNTIME).run(self.root, self.task, self.invoke)
        destination = self.root / 'standalone-studio'
        result = subprocess.run([sys.executable, contract.__file__, '--case',
                                 str(self.root / contract.CASE), '--project', str(destination)],
                                env={**os.environ, 'HARNESS_RESEARCH_RUNTIME': RUNTIME},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output['contract']['schema'], 2)
        self.assertEqual(output['status'], 'complete')
        contract.read_bundle(destination / 'research')
