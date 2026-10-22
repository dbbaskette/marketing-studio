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


class FakeHelper:
    """Harness Research's synthesis commands as Workflow.run reads them: each dossier saved,
    a review template for it, and a review judged as the helper judges one, where an
    original not read refuses it."""

    def __init__(self):
        self.saved, self.actions, self.accepted = [], [], False

    def __call__(self, *args):
        action, case = args[1], Path(args[3])
        self.actions.append(action)
        if action == 'save':
            dossier = json.loads((case / 'dossier.json').read_text())
            self.saved.append(dossier)
            for name in ('report.md', 'brief.md', 'evidence.md'):
                contract.write(case, 'research/' + name, 'Synthetic ' + name)
            prose = [f"{section['id']}:{number}" for section in dossier['sections']
                     for number, _ in enumerate(section['blocks'])]
            prose += [f"brief:{section['id']}:{number}" for section in dossier['brief']
                      for number, _ in enumerate(section['blocks'])]
            pending = {'verdict': 'pending', 'note': ''}
            return {'status': 'draft', 'review_template': {
                'schema': 2, 'digest': f'digest-{len(self.saved)}',
                'originals': [{'source': source['id'], 'sha256': 'capture-hash',
                               **({'original_sha256': 'original-hash'}
                                  if source.get('original_file') else {}),
                               'read_original': False} for source in dossier['sources']],
                'facts': [{'id': fact['id'], **pending} for fact in dossier['facts']],
                'findings': [{'id': finding['id'], **pending} for finding in dossier['findings']],
                'prose': [{'id': ident, **pending} for ident in prose],
                'assessment': {'coverage': 'pending', 'usefulness': 'pending', 'note': ''}}}
        if action == 'review':
            given = json.loads((case / 'review.json').read_text())
            self.accepted = (all(item.get('read_original') for item in given['originals'])
                             and all(item['verdict'] == 'supported'
                                     for group in ('facts', 'findings', 'prose')
                                     for item in given[group])
                             and given['assessment'].get('coverage') == 'accurate'
                             and given['assessment'].get('usefulness') == 'adequate')
            return {'status': 'complete' if self.accepted else 'needs-revision'}
        return {'status': 'complete' if self.accepted else 'needs-revision'}


def helper_runtime(folder):
    """The references a workflow hands its workers, and nothing else of the helper."""
    (folder / 'references').mkdir(parents=True)
    for name in ('investigate.md', 'synthesize.md', 'studio-handoff.md', 'review-synthesis.md'):
        (folder / 'references' / name).write_text('Synthetic guidance: ' + name)
    return folder


class WorkflowCase(unittest.TestCase):
    """One workflow against FakeHelper, with a supplied document as its one source."""

    FILE = 'sources/supplied/notes-pdf.txt'
    ORIGINAL = 'sources/supplied/notes-pdf.original.pdf'

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.runtime = helper_runtime(self.root / 'helper')
        self.capture = self.root / 'kept/notes.txt'
        self.capture.parent.mkdir()
        self.capture.write_text(TEXT)
        self.original = self.root / 'kept/notes.original.pdf'
        self.original.write_bytes(b'%PDF-1.7 synthetic')
        self.helper, self.calls = FakeHelper(), []
        self.task = dict(topic='Fictional example', audience='New learners', purpose='Teach it',
                         scope='Synthetic only', source_mode='selected')

    def captured(self, original=True):
        return [dict(file=self.FILE, path=self.capture, origin='supplied notes.pdf',
                     offered=True, **(dict(original=self.ORIGINAL, original_path=self.original)
                                      if original else {}))]

    def authored(self, payload, named=None):
        value = dossier(payload['worker'], self.FILE, 'supplied notes.pdf', 'selected')
        if named:
            value['sources'][0]['original_file'] = named
        return value

    def run_with(self, invoke):
        def counted(phase, guidance, payload, sources, fetch):
            self.calls.append((phase, sources))
            return invoke(phase, guidance, payload, sources, fetch)
        with mock.patch.object(contract, 'read_bundle', return_value=({'facts': 'read'}, {})):
            return contract.Workflow(self.runtime, self.helper).run(self.root, self.task, counted)


class OriginalClaimTests(WorkflowCase):
    """An original is claimed for a source only when the studio offered one."""

    def test_an_original_the_studio_did_not_offer_is_not_claimed(self):
        # A previous draft named the Markdown export of a Google Doc as an original; the
        # studio no longer offers one, because the export is its capture.
        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                value = self.authored(payload, 'sources/supplied/notes-md.original.md')
                return json.dumps(value), self.captured(original=False)
            return json.dumps(review(payload['review_template'])), []
        self.run_with(invoke)
        self.assertNotIn('original_file', self.helper.saved[0]['sources'][0])
        self.assertNotIn('original', self.calls[1][1][0])
        self.assertNotIn('original_sha256', json.loads(
            (self.root / contract.CASE / 'review.json').read_text())['originals'][0])

    def test_an_offered_original_is_claimed_saved_and_offered_to_the_check(self):
        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                return json.dumps(self.authored(payload)), self.captured()
            return json.dumps(review(payload['review_template'])), []
        self.run_with(invoke)
        self.assertEqual(self.helper.saved[0]['sources'][0]['original_file'], self.ORIGINAL)
        case = self.root / contract.CASE
        self.assertEqual((case / self.ORIGINAL).read_bytes(), b'%PDF-1.7 synthetic')
        offered = self.calls[1][1][0]
        self.assertEqual((offered['original'], offered['original_path']),
                         (self.ORIGINAL, case / self.ORIGINAL))

    def test_naming_another_original_than_the_one_offered_is_refused(self):
        def invoke(phase, guidance, payload, sources, fetch):
            return json.dumps(self.authored(payload, 'sources/elsewhere.pdf')), self.captured()
        with self.assertRaisesRegex(ValueError, 'did not capture'):
            self.run_with(invoke)



class UnfinishedCheckTests(WorkflowCase):
    """A check that cannot read an original it must attest to cannot be satisfied by any
    correction: the research stops after that round, and says it is the studio's problem."""

    def unread(self, template, error='There is no tool to read it.', verdict='narrow'):
        result = review(template)
        result['originals'][0].update(read_original=False, access_error=error)
        for item in result['facts']:
            item.update(verdict=verdict, note='The original could not be inspected.')
        return result

    def test_unread_originals_are_the_cause_only_when_every_objection_rests_on_them(self):
        value = self.authored({'worker': 'author-1'})
        template = {'originals': [{'source': 'source-a', 'read_original': True}],
                    'facts': [{'id': 'fact-a'}], 'findings': [], 'prose': []}
        unread = self.unread(template, 'No tool serves it.')
        self.assertEqual(contract.unreadable_originals(unread, value), [{
            'source': 'source-a', 'title': 'Synthetic source', 'file': self.FILE,
            'original': None, 'access_error': 'No tool serves it.'}])
        # Prose and findings trace to their facts, and so to the source.
        for group, ident in (('findings', 'instance-min'), ('prose', 'explain:0'),
                             ('prose', 'brief:teaching:0')):
            with self.subTest(ident):
                shaped = {**unread, 'facts': [], 'findings': [], 'prose': [],
                          group: [{'id': ident, 'verdict': 'unsupported', 'note': ''}]}
                self.assertEqual(len(contract.unreadable_originals(shaped, value)), 1)
        # An objection that rests on something else can still be corrected.
        value['facts'].append({'id': 'fact-b', 'citations': [{'source': 'source-b'}]})
        mixed = {**unread, 'facts': [*unread['facts'], {'id': 'fact-b', 'verdict': 'unsupported'}]}
        self.assertEqual(contract.unreadable_originals(mixed, value), [])
        self.assertEqual(contract.unreadable_originals(review(template), value), [])

    def test_the_research_stops_after_the_round_that_could_not_read_an_original(self):
        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                return json.dumps(self.authored(payload)), self.captured()
            return json.dumps(self.unread(payload['review_template'])), []
        with self.assertRaises(contract.CheckCouldNotFinish) as caught:
            self.run_with(invoke)
        self.assertEqual([phase for phase, _ in self.calls], ['author', 'review'])
        refusal = caught.exception
        self.assertIsInstance(refusal, contract.ReviewRefused)
        self.assertEqual(refusal.rounds, 0)
        self.assertEqual(refusal.cause[0]['original'], self.ORIGINAL)
        self.assertEqual(str(refusal), (
            'The research check could not read the original of "Synthetic source" (There is '
            'no tool to read it.). That is a studio problem, not a research problem: the report '
            'is not wrong, the check could not finish. Nothing to correct until the original is '
            'readable.'))
        self.assertTrue(refusal.objections)

    def test_a_real_objection_still_goes_back_for_correction(self):
        reviews = []

        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                return json.dumps(self.authored(payload)), self.captured()
            reviews.append(1)
            if len(reviews) == 1:
                return json.dumps(review(payload['review_template'], False)), []
            return json.dumps(review(payload['review_template'])), []
        self.assertEqual(self.run_with(invoke)[0], {'facts': 'read'})
        self.assertEqual([phase for phase, _ in self.calls], ['author', 'review'] * 2)



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
