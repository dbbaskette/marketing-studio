import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import marketing_studio  # Puts the shared core on the import path.
from studio_core import research_contract as contract
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


class HelperAnswerTests(unittest.TestCase):
    """Harness Research 1.0.1 exits 1 for a needs-revision review and stale evidence."""

    def answer(self, action, code, out, err=''):
        done = subprocess.CompletedProcess([], code, out, err)
        with mock.patch.object(contract.shutil, 'which', return_value='/usr/bin/node'), \
                mock.patch.object(contract.subprocess, 'run', return_value=done):
            return contract.Workflow('/opt/harness-research').command(
                Path('/t/case'), action, *(('review.json', 'reviewer-1') if action in ('save', 'review') else ()))

    def test_results_that_exit_one_are_read_for_review_verify_and_status(self):
        self.assertEqual(self.answer('review', 1, '{"status":"needs-revision"}', 'Rejected.\n'),
                         {'status': 'needs-revision'})
        self.assertEqual(self.answer('verify', 1, '{"status":"stale","artifact_integrity":"failed"}\n'),
                         {'status': 'stale', 'artifact_integrity': 'failed'})
        self.assertEqual(self.answer('status', 1, '{"status":"stale"}'), {'status': 'stale'})

    def test_a_non_zero_exit_without_a_json_result_is_a_failure(self):
        for out in ('', 'Usage: harness-research', '[1]'):
            with self.assertRaisesRegex(ValueError, 'Evidence is stale'):
                self.answer('review', 1, out, 'Evidence is stale. Save revised content.\n')
        with self.assertRaisesRegex(ValueError, 'Harness Research failed'):
            self.answer('verify', 2, '{"status":"stale"}')

    def test_other_actions_still_fail_on_any_non_zero_exit(self):
        with self.assertRaisesRegex(ValueError, 'Invalid dossier'):
            self.answer('save', 1, '{"status":"draft"}', 'Invalid dossier.\n')
        self.assertEqual(contract.answered(['synthesis', 'save'], 1, '{}'), False)
        self.assertEqual(contract.answered(['status'], 1, '{}'), False)
        self.assertEqual(contract.answered(('synthesis', 'verify'), 1, '{}'), True)

class ReviewRefusedTests(unittest.TestCase):
    """What a research check that still objects after its last round says, and keeps."""

    def case(self, review):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        case = Path(temp.name)
        if review is not None:
            (case / 'review.json').write_text(review if isinstance(review, str) else json.dumps(review))
        return case

    def test_objections_name_each_unsupported_verdict_and_an_assessment_asking_for_revision(self):
        case = self.case({
            'facts': [{'id': 'fact-a', 'verdict': 'supported', 'note': 'Checked.'},
                      {'id': 'fact-b', 'verdict': 'unsupported', 'note': 'The  source does\nnot say so.'}],
            'findings': [{'id': 'instance-min', 'verdict': 'narrow', 'note': ''}],
            'prose': [{'id': 'brief:teaching:0', 'verdict': 'supported', 'note': 'Fine.'}],
            'assessment': {'coverage': 'needs-revision', 'usefulness': 'adequate', 'note': 'Alternatives are missing.'}})
        self.assertEqual(contract.objections(case), [
            'fact-b (unsupported): The source does not say so.',
            'instance-min (narrow): no note',
            'Coverage needs revision: Alternatives are missing.'])
        self.assertEqual(contract.objections(self.case(None)), [])
        self.assertEqual(contract.objections(self.case('{broken')), [])
        self.assertEqual(contract.objections(self.case([1, 2])), [])

    def test_the_refusal_says_how_many_objections_and_the_first_of_them(self):
        refusal = contract.ReviewRefused(['fact-b (unsupported): The source does not say so.',
                                          'Coverage needs revision: Alternatives are missing.',
                                          'instance-min (narrow): no note'], 3)
        self.assertEqual(str(refusal), (
            'The independent check of the research still needs changes after 3 rounds of '
            'correction: 3 objections, such as fact-b (unsupported): The source does not say so. '
            'Coverage needs revision: Alternatives are missing. The draft report and the check’s '
            'notes are saved for correction.'))
        self.assertEqual((refusal.rounds, len(refusal.objections)), (3, 3))
        self.assertIsInstance(refusal, ValueError)
        bare = contract.ReviewRefused([], 3)
        self.assertIn('did not say what: read the saved check.', str(bare))
        long = contract.ReviewRefused(['x' * 400], 3)
        self.assertIn('x' * 159 + '…', str(long))
        self.assertNotIn('x' * 161, str(long))


def fake_runtime(folder, version, text):
    """Just enough of an installed helper for its capability to be described."""
    (folder / 'scripts/lib').mkdir(parents=True)
    (folder / 'references').mkdir()
    (folder / 'package.json').write_text(json.dumps({'version': version}))
    for name in ('scripts/harness-research.mjs', 'scripts/lib/synthesis-cli.mjs'):
        (folder / name).write_text('// ' + text + '\n')
    (folder / 'references/synthesize.md').write_text(text)
    return folder


class RetainedVersionTests(unittest.TestCase):
    """The Harness Research installer keeps each version in versions/<version>-<digest>."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.shared = self.home / 'Library/Application Support/Harness Research'
        self.old = fake_runtime(self.shared / 'versions/1.0.0-aaaaaaaaaaaaaaaaaaaa', '1.0.0', 'old')
        self.new = fake_runtime(self.shared / 'versions/1.0.1-bbbbbbbbbbbbbbbbbbbb', '1.0.1', 'new')
        (self.shared / 'current').symlink_to('versions/' + self.new.name)
        self.saved = contract.snapshot(SimpleNamespace(runtime=self.old))
        for patch in (mock.patch.dict(os.environ, {'HARNESS_RESEARCH_RUNTIME': str(self.shared / 'current')}),
                      mock.patch.object(Path, 'home', return_value=self.home)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_the_current_helper_is_used_while_it_matches(self):
        current = contract.snapshot(SimpleNamespace(runtime=self.new))
        self.assertEqual(contract.runtime_for(current), self.new)
        tool = SimpleNamespace(runtime=self.shared / 'current', node='node')
        self.assertIs(contract.matching(tool, current), tool)

    def test_unfinished_research_uses_the_retained_version_with_its_saved_digest(self):
        self.assertEqual(contract.runtime_for(self.saved), self.old)
        tool = SimpleNamespace(runtime=self.shared / 'current', node='node')
        kept = contract.matching(tool, self.saved)
        self.assertEqual((kept.runtime, kept.node), (self.old, 'node'))
        self.assertEqual(tool.runtime, self.shared / 'current')
        # A helper found elsewhere still finds the shared installer's retained versions.
        os.environ.pop('HARNESS_RESEARCH_RUNTIME')
        elsewhere = fake_runtime(self.home / 'checkout', '1.0.1', 'checkout')
        self.assertEqual(contract.runtime_for(self.saved, elsewhere), self.old)

    def test_a_changed_linked_or_unknown_version_is_never_used(self):
        for saved in (None, {}, {**self.saved, 'version': '../1.0.0'}, {**self.saved, 'version': '1.0.2'},
                      {**self.saved, 'digest': '0' * 64}):
            with self.subTest(saved=saved):
                self.assertIsNone(contract.runtime_for(saved))
                self.assertIsNone(contract.matching(SimpleNamespace(runtime=self.new), saved))
        (self.old / 'references/synthesize.md').write_text('changed')
        self.assertIsNone(contract.runtime_for(self.saved))
        (self.old / 'references/synthesize.md').write_text('old')
        moved = self.home / 'moved'
        self.old.rename(moved)
        self.old.symlink_to(moved, target_is_directory=True)
        self.assertIsNone(contract.runtime_for(self.saved))


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
