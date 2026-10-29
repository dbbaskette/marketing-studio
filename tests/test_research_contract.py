import copy
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

    def run_with(self, invoke, readable=None):
        def counted(phase, guidance, payload, sources, fetch):
            self.calls.append((phase, sources))
            return invoke(phase, guidance, payload, sources, fetch)
        with mock.patch.object(contract, 'read_bundle', return_value=({'facts': 'read'}, {})):
            return contract.Workflow(self.runtime, self.helper).run(
                self.root, self.task, counted, readable=readable)


class CitationHandoffTests(WorkflowCase):
    def test_non_native_handoff_reconciles_only_an_exact_capture_handle(self):
        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                value = self.authored(payload)
                value['facts'][0]['citations'][0]['source'] = 's1'
                captures = [dict(self.captured()[0], id='s1')]
                return json.dumps(value), captures
            self.assertEqual(payload['dossier']['facts'][0]['citations'][0]['source'], 'source-a')
            return json.dumps(review(payload['review_template'])), []
        self.run_with(invoke)
        self.assertEqual([phase for phase, _ in self.calls], ['author', 'review'])
        self.assertEqual(self.helper.saved[0]['facts'][0]['citations'][0]['source'], 'source-a')

    def test_non_native_handoff_refuses_a_missing_source_before_save_or_review(self):
        def invoke(phase, guidance, payload, sources, fetch):
            value = self.authored(payload)
            value['facts'][0]['citations'][0]['source'] = 'missing'
            return json.dumps(value), self.captured()
        with self.assertRaisesRegex(ValueError, 'Available source IDs'):
            self.run_with(invoke)
        self.assertEqual(self.helper.saved, [])
        self.assertEqual([phase for phase, _ in self.calls], ['author'])
        self.assertFalse((self.root / contract.CASE / self.FILE).exists())


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
    """A check that could not read an original the studio offered, when that is all it
    objected to and the studio's own tools cannot serve that original either, cannot be
    satisfied by any correction: the research stops after that round and says it is the
    studio's problem. Anything less is the check's to put right in the next round."""

    def unread(self, template, error='There is no tool to read it.', verdict='narrow'):
        result = review(template)
        result['originals'][0].update(read_original=False, access_error=error)
        for item in result['facts']:
            item.update(verdict=verdict, note='The original could not be inspected.')
        return result

    def with_original(self):
        value = self.authored({'worker': 'author-1'})
        value['sources'][0]['original_file'] = self.ORIGINAL
        return value

    def test_unread_originals_are_the_cause_only_when_every_objection_rests_on_them(self):
        value = self.with_original()
        template = {'originals': [{'source': 'source-a', 'read_original': True}],
                    'facts': [{'id': 'fact-a'}], 'findings': [], 'prose': []}
        unread = self.unread(template, 'No tool serves it.')
        self.assertEqual(contract.unreadable_originals(unread, value), [{
            'source': 'source-a', 'title': 'Synthetic source', 'file': self.FILE,
            'original': self.ORIGINAL, 'access_error': 'No tool serves it.'}])
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

    def test_a_source_with_no_original_is_never_the_cause(self):
        # A Markdown document is its own capture: a check that says it could not read the
        # original of one has only to read the capture, so the next round may finish.
        value = self.authored({'worker': 'author-1'})
        template = {'originals': [{'source': 'source-a', 'read_original': True}],
                    'facts': [{'id': 'fact-a'}], 'findings': [], 'prose': []}
        self.assertEqual(contract.unreadable_originals(self.unread(template), value), [])

    def test_an_objection_that_rests_on_a_readable_source_too_or_on_coverage_is_real(self):
        value = self.with_original()
        value['sources'].append({**value['sources'][0], 'id': 'source-b', 'file': 'sources/b.txt'})
        value['sources'][1].pop('original_file')
        value['facts'][0]['citations'].append({'source': 'source-b', 'quote': 'x'})
        template = {'originals': [{'source': 'source-a'}, {'source': 'source-b'}],
                    'facts': [{'id': 'fact-a'}], 'findings': [], 'prose': []}
        both = self.unread(template)
        self.assertEqual(contract.unreadable_originals(both, value), [],
                         'the fact also rests on a source the check could read')
        alone = self.with_original()
        template = {'originals': [{'source': 'source-a'}], 'facts': [{'id': 'fact-a'}],
                    'findings': [], 'prose': []}
        coverage = self.unread(template, verdict='supported')
        coverage['assessment'] = {'coverage': 'needs-revision', 'usefulness': 'adequate',
                                  'note': 'Alternatives are missing.'}
        self.assertEqual(contract.unreadable_originals(coverage, alone), [],
                         'coverage the author can put right is a real objection')
        coverage['assessment']['coverage'] = 'accurate'
        self.assertEqual(len(contract.unreadable_originals(coverage, alone)), 1)

    def blind(self, phase, guidance, payload, sources, fetch):
        if phase == 'author':
            return json.dumps(self.authored(payload)), self.captured()
        return json.dumps(self.unread(payload['review_template'])), []

    def test_the_research_stops_after_a_round_whose_original_the_studio_cannot_serve(self):
        asked = []

        def readable(cause):
            asked.append(cause)
            return 'The original of s1 is not in this job, so it cannot be read.'
        with self.assertRaises(contract.CheckCouldNotFinish) as caught:
            self.run_with(self.blind, readable)
        self.assertEqual([phase for phase, _ in self.calls], ['author', 'review'])
        self.assertEqual(asked[0][0]['original'], self.ORIGINAL)
        refusal = caught.exception
        self.assertIsInstance(refusal, contract.ReviewRefused)
        self.assertEqual(refusal.rounds, 0)
        self.assertEqual(refusal.cause[0]['original'], self.ORIGINAL)
        self.assertEqual(str(refusal), (
            'The research check could not read the original of "Synthetic source" (The original '
            'of s1 is not in this job, so it cannot be read.). That is a studio problem, not a '
            'research problem: nothing was found wrong with the report, but the check could not '
            'finish. Nothing to correct until the original is readable.'))
        self.assertTrue(refusal.objections)

    def test_an_original_the_studio_can_serve_is_the_check_s_to_read_next_round(self):
        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'review' and len(self.calls) > 2:
                return json.dumps(review(payload['review_template'])), []
            return self.blind(phase, guidance, payload, sources, fetch)
        self.assertEqual(self.run_with(invoke, lambda cause: None)[0], {'facts': 'read'})
        self.assertEqual([phase for phase, _ in self.calls], ['author', 'review'] * 2)

    def test_a_check_that_never_reads_a_servable_original_ends_as_any_refusal_does(self):
        with self.assertRaises(contract.ReviewRefused) as caught:
            self.run_with(self.blind, lambda cause: None)
        self.assertNotIsInstance(caught.exception, contract.CheckCouldNotFinish)
        self.assertEqual(len(self.calls), 2 * contract.ROUNDS)
        self.assertIn('1 fact the check calls narrow', str(caught.exception))

    def test_without_a_way_to_ask_the_studio_the_check_s_word_stands(self):
        with self.assertRaises(contract.CheckCouldNotFinish) as caught:
            self.run_with(self.blind)
        self.assertIn('(There is no tool to read it.)', str(caught.exception))

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


class GroupedObjectionTests(unittest.TestCase):
    """Real objections are counted by what they are about and what the check called them,
    so forty notes with one cause read as one group."""

    def review(self):
        return {
            'facts': [*({'id': f'f{number:02}', 'verdict': 'narrow', 'note': f'Too broad {number}.'}
                        for number in range(1, 13)),
                      {'id': 'f13', 'verdict': 'supported', 'note': 'Fine.'}],
            'findings': [{'id': name, 'verdict': 'unsupported', 'note': 'No fact says so.'}
                         for name in ('instance-min', 'health-checks', 'batches')],
            'prose': [{'id': 'brief:teaching:0', 'verdict': 'narrow', 'note': ''}],
            'assessment': {'coverage': 'needs-revision', 'usefulness': 'adequate',
                           'note': 'Alternatives are missing.'}}

    def case(self, review):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        (Path(temp.name) / 'review.json').write_text(json.dumps(review))
        return Path(temp.name)

    def test_objections_are_grouped_by_kind_and_verdict_with_a_count_and_the_first_note(self):
        groups = contract.grouped(self.case(self.review()))
        self.assertEqual([(group['title'], group['count'], group['note']) for group in groups], [
            ('12 facts the check calls narrow', 12, 'f01: Too broad 1.'),
            ('3 findings unsupported', 3, 'instance-min: No fact says so.'),
            ('1 passage of the report or brief the check calls narrow', 1,
             'brief:teaching:0: no note'),
            ('coverage needs revision', 1, 'Alternatives are missing.')])
        self.assertEqual(groups[0]['items'][:2], ['f01: Too broad 1.', 'f02: Too broad 2.'])
        self.assertEqual(len(groups[0]['items']), 12)
        self.assertEqual(contract.grouped(self.case([])), [])

    def test_a_refusal_with_groups_says_each_group_and_its_first_note(self):
        case = self.case(self.review())
        refusal = contract.ReviewRefused(contract.objections(case), 3, contract.grouped(case))
        self.assertEqual(str(refusal), (
            'The independent check of the research still needs changes after 3 rounds of '
            'correction: 17 objections in 4 groups: 12 facts the check calls narrow (f01: Too '
            'broad 1.), 3 findings unsupported (instance-min: No fact says so.), 1 passage of '
            'the report or brief the check calls narrow (brief:teaching:0: no note), coverage '
            'needs revision (Alternatives are missing.). The draft report and the check’s '
            'notes are saved for correction.'))
        self.assertEqual((refusal.rounds, len(refusal.groups)), (3, 4))

    def test_what_the_rounds_took_is_said_plainly(self):
        self.assertEqual(contract.took(2880, 9.8), '48 minutes and $9.80')
        self.assertEqual(contract.took(45, None), '45 seconds')
        self.assertEqual(contract.took(61, 0.005), '1 minute and $0.01')
        self.assertEqual(contract.took(5400, 12), '1 hour 30 minutes and $12.00')
        self.assertEqual(contract.took(0, None), '')


class RoundCostTests(WorkflowCase):
    """What every round of a research run took is said when the research stops."""

    def test_the_last_round_raises_its_objections_in_groups(self):
        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                return json.dumps(self.authored(payload)), self.captured()
            return json.dumps(review(payload['review_template'], False)), []
        with self.assertRaises(contract.ReviewRefused) as caught:
            self.run_with(invoke)
        self.assertEqual(len(self.calls), 2 * contract.ROUNDS)
        self.assertEqual([group['title'] for group in caught.exception.groups], [
            '1 fact the check calls narrow', '2 findings the check calls narrow',
            '2 passages of the report or brief the check calls narrow'])
        self.assertIn('5 objections in 3 groups', str(caught.exception))



class JobNameTests(unittest.TestCase):
    """Research jobs are recorded under the research step, with their round."""

    def test_a_job_is_named_for_its_step_phase_and_round(self):
        self.assertEqual(contract.job_name('author', 2), 'research:author-2')
        self.assertEqual(contract.job_round('research:review-3'), ('review', 3))
        self.assertEqual(contract.job_round('research-author'), ('author', None))
        for other in ('research:instance-min', 'research', 'outline', 'research:author-x'):
            self.assertIsNone(contract.job_round(other))

    def test_each_job_says_its_round_while_it_runs(self):
        self.assertEqual(contract.doing_words('author', 1),
                         'Investigating sources and writing the report (round 1 of 3)')
        self.assertEqual(contract.doing_words('review', 1),
                         'Independently checking the research (round 1 of 3)')
        self.assertEqual(contract.doing_words('author', 2),
                         'Correcting the research after its independent check (round 2 of 3)')
        self.assertEqual(contract.doing_words('review', 3),
                         'Independently checking the corrected research (round 3 of 3)')

    def test_the_last_try_is_what_ran_since_its_last_first_round(self):
        def tried(at, seconds, dollars=None):
            return {'started_at': at, 'seconds': seconds, 'dollars': dollars}
        record = {'research:author-1': [tried('1', 100, 1.0), tried('5', 200, 2.0)],
                  'research:review-1': [tried('2', 50, 0.5), tried('6', 60, 0.25)],
                  'research:author-2': [tried('3', 100, 1.0), tried('7', 300)],
                  'research:review-2': [tried('4', 50, 0.5)],
                  'research:instance-min': [tried('9', 999, 9.0)], 'outline': [tried('9', 9)]}
        self.assertEqual(contract.last_rounds(record),
                         {'rounds': 2, 'jobs': 3, 'seconds': 560, 'dollars': 2.25})
        self.assertEqual(contract.last_rounds({'research-author': [tried('1', 10, 0.1)],
                                               'research-review': [tried('2', 20)]}),
                         {'rounds': 0, 'jobs': 2, 'seconds': 30, 'dollars': 0.1})
        self.assertIsNone(contract.last_rounds({'outline': [tried('1', 5)]}))



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

    def test_a_markdown_document_once_offered_as_its_own_original_finishes_on_retry(self):
        # The live deck: a Google Doc kept as Markdown, whose original was offered and could
        # not be read. Its saved state names the original; the next try offers none.
        file, original = 'sources/supplied/google-doc-md.txt', 'sources/supplied/google-doc-md.original.md'
        (self.root / 'sources/supplied').mkdir(parents=True)
        for name in (file, original):
            (self.root / name).write_text(TEXT)

        def captured(offered):
            return [dict(file=file, path=self.root / file, origin='supplied google-doc.md',
                         offered=True, **(dict(original=original, original_path=self.root / original)
                                          if offered else {}))]

        def before(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                return json.dumps(dossier(payload['worker'], file, 'supplied google-doc.md',
                                          'selected')), captured(True)
            result = review(payload['review_template'])
            for item in result['originals']:
                item.update(read_original=False, access_error='No tool serves it.')
            for item in result['facts']:
                item.update(verdict='narrow', note='The original could not be inspected.')
            return json.dumps(result), []
        with self.assertRaises(contract.ReviewRefused):
            contract.Workflow(RUNTIME).run(self.root, self.task, before)
        state = json.loads((self.root / contract.CASE / '.harness-research/synthesis.json').read_text())
        self.assertEqual(state['dossier']['sources'][0]['original_file'], original)
        seen = {}

        def after(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                value = dossier(payload['worker'], file, 'supplied google-doc.md', 'selected')
                value['sources'] = copy.deepcopy(payload['previous_dossier']['sources'])
                return json.dumps(value), captured(False)
            seen.update(template=payload['review_template'], offered=sources)
            return json.dumps(review(payload['review_template'])), []
        facts, manifest = contract.Workflow(RUNTIME).run(self.root, self.task, after)
        self.assertEqual(manifest['status'], 'complete')
        self.assertNotIn('original_sha256', seen['template']['originals'][0])
        self.assertNotIn('original', seen['offered'][0])
        self.assertNotIn('original_file', facts['sources'][0])

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

class AuthorGuideTests(WorkflowCase):
    """The author is handed its own stage references, and told what the tools did for it."""

    def authored_once(self):
        seen = []

        def invoke(phase, guidance, payload, sources, fetch):
            if phase == 'author':
                seen.append((guidance, payload['return']))
                return json.dumps(self.authored(payload)), self.captured()
            return json.dumps(review(payload['review_template'])), []
        self.run_with(invoke)
        return seen[0]

    def test_author_is_handed_its_stage_references_only(self):
        guide, _ = self.authored_once()
        self.assertIn('Synthetic guidance: investigate.md', guide)
        self.assertIn('Synthetic guidance: synthesize.md', guide)
        self.assertNotIn('studio-handoff.md', guide)

    def test_author_return_line_names_the_tools_captures(self):
        _, said = self.authored_once()
        self.assertIn("The studio's tools have saved every capture for you: that is the capture "
                      '`investigate.md` asks for. Set each sources[].file to the exact Capture file '
                      'path the tools returned. Write no files yourself.', said)
        self.assertIn(contract.SOURCE_IDS, said)
        self.assertNotIn('Cite each source by the file path', said)
        self.assertNotIn('research/sources/', said)


class RefreshTests(AuthorGuideTests):
    """Bringing the research up to date hands the author Harness Research's own refresh
    section, and asks it to read its sources again."""

    def setUp(self):
        super().setUp()
        (self.runtime / 'references' / 'synthesis-reuse.md').write_text(
            '# Resume, reuse and refresh synthesis\n\nIntro.\n\n'
            '## Resume the saved work\n\nResume words.\n\n'
            '## Use the report as source material\n\nReuse words.\n\n'
            '## Refresh selected evidence\n\nSave new captures with access dates.\n\n'
            'Not a heading: ## inside a line.\n')

    def test_refresh_hands_the_refresh_section(self):
        self.task['refresh'] = True
        guide, said = self.authored_once()
        self.assertIn('## Refresh selected evidence\n\nSave new captures with access dates.',
                      guide)
        self.assertNotIn('Resume words.', guide)
        self.assertNotIn('Reuse words.', guide)
        self.assertIn("Bring the evidence up to date: re-read each source with the studio's "
                      'capture tool, so that each new capture is saved with the date it was '
                      'read; then update what changed. The studio saves the dossier you hand '
                      'back and arranges its independent review.', said)
        self.assertNotIn('Bring the evidence up to date: re-read each source, save', said)
        self.assertIn("The studio's tools save every capture and the studio arranges the "
                      'review: write no files yourself.', guide)

    def test_without_refresh_no_reuse_section_is_handed(self):
        guide, said = self.authored_once()
        self.assertNotIn('Refresh selected evidence', guide)
        self.assertNotIn('Bring the evidence up to date', said)

    def test_refresh_is_never_a_dossier_field(self):
        self.assertNotIn('refresh', contract.TASK_FIELDS)

    def test_refresh_words(self):
        from studio_core import research_view
        self.assertEqual(research_view.refresh_words(None), 'Re-reads the sources and checks '
                         'the report again: about as long and as costly as the research was.')
        self.assertEqual(research_view.refresh_words({'seconds': 2880, 'dollars': 9.8}),
                         'Re-reads the sources and checks the report again: its last try took '
                         '48 minutes and $9.80.')
        self.assertEqual(research_view.price({})['refresh'], research_view.refresh_words(None))


class HandoffAndPurposeTests(unittest.TestCase):
    """What every writer is told of the research, and the purpose every studio asks for."""

    def test_the_handoff_sentence(self):
        self.assertEqual(contract.HANDOFF, (
            'The research is reviewed. Read its brief first: it says what matters for this '
            'piece. Use the facts and findings to check what you write. Their IDs, digests and '
            'verdicts are for checking and for provenance, notes and source lines: never put '
            'one in the words a reader reads.'))

    def test_compares(self):
        for goal in ('Compare Redis and Valkey', 'Redis versus Valkey', 'Redis vs Valkey',
                     'Redis vs. Valkey for caching', 'Choose between two caches',
                     'Redis or Valkey for sessions', 'Which is better for sessions?',
                     'A comparison of three queues', 'Alternatives to a message bus'):
            self.assertTrue(contract.compares(goal), goal)
        for goal in ('Explain how caching works', 'cache reads or writes', 'Teach Kubernetes',
                     '', None, 'Survey the options'):
            self.assertFalse(contract.compares(goal), goal)

    def test_purpose(self):
        self.assertTrue(contract.purpose('a presentation', 'Redis or Valkey',
                                         'Prioritize X.').endswith(contract.COMPARISON))
        self.assertEqual(contract.purpose('a presentation', 'Explain caching', 'Prioritize X.'),
                         'Inform a presentation: Explain caching. Prioritize X.')
        self.assertEqual(contract.purpose('a blog', '', 'Prioritize Y.'),
                         'Inform a blog: explain the topic. Prioritize Y.')
        self.assertEqual(contract.COMPARISON, 'The goal compares options: include a comparison '
                         'with one criterion per row, and say where something is unknown rather '
                         'than absent.')


class PlanningQuestionTests(WorkflowCase):
    def test_the_author_is_told_to_name_findings_for_their_questions(self):
        for questions in (None, [], [dict(id='q-one', question='Why?')]):
            with self.subTest(questions=questions):
                self.task['planning_questions'] = questions
                seen = []
                def invoke(phase, guidance, payload, sources, fetch):
                    if phase == 'author':
                        seen.append(payload['return'])
                        return json.dumps(self.authored(payload)), self.captured()
                    return json.dumps(review(payload['review_template'])), []
                self.run_with(invoke)
                self.assertEqual('Planning questions have IDs.' in seen[0], bool(questions))
