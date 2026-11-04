"""A synthesis and an independent review are told their exact shape up front, and a refusal
lists every problem at once (#303), refusing nothing Harness Research accepts."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import marketing_studio  # noqa: F401  Shared core import path.
from studio_core import research_contract as rc, research_session, research_text
from synthesis_fixture import TEXT, dossier, review

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')
GATED = unittest.skipUnless(RUNTIME and shutil.which('node'),
                            'Select the pinned disposable Harness Research runtime.')
PROSE = ('findings', 'sections', 'brief')


def comparison():
    return {'title': 'Two synthetic options', 'subjects': ['One', 'Two'], 'rows': [
        {'criterion': 'Capacity', 'cells': [
            {'subject': 'One', 'text': 'Keeps capacity.', 'refs': ['fact-a']},
            {'subject': 'Two', 'text': 'Unknown here.', 'refs': ['fact-a']}]}]}


class ShapeTests(unittest.TestCase):
    """What needs no helper: the studio's own synthesis shape and the review template."""

    def test_every_missing_part_of_a_synthesis_is_listed(self):
        self.assertEqual(research_session.compose_shape({'schema': 2, 'sections': [], 'notes': 'x'}), [
            'Return findings, sections, brief and optional comparisons only. Evidence is kept unchanged.',
            'Return findings as a nonempty array.', 'Return sections as a nonempty array.',
            'Return brief as a nonempty array.'])
        with self.assertRaisesRegex(ValueError, 'Return findings as a nonempty array. Return sections'):
            research_session.preparation({'schema': 2, 'brief': [{}]}, {'research_mode': 'compose'})

    def test_a_review_left_as_its_template_lists_everything_to_fill_in(self):
        template = {'schema': 2, 'digest': 'a' * 64,
                    'originals': [{'source': 's1', 'sha256': 'b' * 64, 'read_original': False}],
                    'facts': [{'id': 'fact-a', 'verdict': 'pending', 'note': ''}],
                    'findings': [{'id': 'one', 'verdict': 'pending', 'note': ''}],
                    'prose': [{'id': 'explain:0', 'verdict': 'pending', 'note': ''}],
                    'assessment': {'coverage': 'pending', 'usefulness': 'pending', 'note': ''}}
        said = '\n'.join(rc.review_problems(copy.deepcopy(template), template))
        for part in ('Original s1: read_original is false, so give access_error',
                     'facts: set verdict to one of supported, unsupported, narrow for 1 item(s), such as fact-a',
                     'findings: give a note explaining the verdict', 'prose: set verdict',
                     'assessment.coverage must be one of accurate, needs-revision',
                     'assessment.usefulness must be one of adequate, needs-revision',
                     'assessment.note must explain the assessment'):
            self.assertIn(part, said)
        filled = review(template)
        self.assertEqual(rc.review_problems(filled, template), [])
        filled['facts'].append(dict(filled['facts'][0]))
        filled['digest'] = 'c' * 64
        said = '\n'.join(rc.review_problems(filled, template))
        self.assertIn('facts must hold exactly one entry for each of the 1', said)
        self.assertIn("Set digest to 'aaaa", said)


@GATED
class PinnedSynthesisTests(unittest.TestCase):
    """The real pinned helper decides; the studio says everything it would refuse at once."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        rc.write(self.root, 'job/sources/source.txt', TEXT)
        self.full = dossier('investigator-1')
        task = {key: self.full[key] for key in rc.TASK_FIELDS}
        base = {'schema': 2, **task, **{key: self.full[key] for key in ('sources', 'facts')}}
        self.captures = [{'file': 'sources/source.txt', 'local': 'sources/source.txt',
                          'origin': 'https://example.invalid/docs', 'permission': 'public'}]
        self.compose = {'runtime': RUNTIME, 'folder': str(self.root / 'job'), 'worker': 'synthesizer-1',
                        'node': shutil.which('node'), 'task': task, 'research_mode': 'compose',
                        'evidence_base': base, 'captures': self.captures}
        self.serial = {**self.compose, 'research_mode': None, 'worker': 'investigator-1'}
        self.serial.pop('evidence_base')

    def synthesis(self):
        """A synthesis built from the outline: the fixture's findings, sections and brief."""
        return {'schema': 2, **{key: copy.deepcopy(self.full[key]) for key in PROSE}}

    def check(self, value, spec=None):
        return rc.check_json(json.dumps(value), spec or self.compose)[0]

    def test_the_outline_describes_what_the_helper_takes(self):
        outline = rc.synthesis_outline(RUNTIME)
        self.assertEqual(list(outline['return']), ['findings', 'sections', 'brief', 'comparisons'])
        self.assertTrue(outline['return']['brief'].startswith('Required, with at least one item.'))
        self.assertTrue(outline['return']['comparisons'].startswith('Optional.'))
        self.assertEqual(set(outline['shapes']), {'finding', 'section', 'statement', 'comparison'})
        self.assertIn('One of summary, inference, recommendation, gap', outline['shapes']['statement']['kind'])
        self.assertIn('at least 1', outline['shapes']['finding']['support'])
        self.assertTrue(outline['rules'])
        fields = rc.review_outline(RUNTIME)['fields']
        self.assertIn('One of supported, unsupported, narrow', fields['facts']['each']['verdict'])
        self.assertTrue(fields['originals']['each']['access_error'].startswith('Required when read_original is false.'))

    def test_a_synthesis_built_from_the_outline_passes_the_first_time(self):
        self.assertEqual(self.check(self.synthesis()), [])
        with_comparison = {**self.synthesis(), 'comparisons': [comparison()]}
        self.assertEqual(self.check(with_comparison), [])

    def test_a_synthesis_missing_several_parts_is_refused_once_listing_all(self):
        bad = self.synthesis()
        del bad['brief']
        bad['findings'] = []
        bad['sections'][0]['blocks'][0].update(kind='claim', refs=['nowhere'])
        bad['comparisons'] = [{**comparison(), 'subjects': ['One']}]
        problems = self.check(bad)
        said = '\n'.join(problems)
        for part in ('Return findings as a nonempty array.', 'Return brief as a nonempty array.',
                     'Report section explain: block 1 kind must be one of summary, inference, recommendation, gap',
                     'block 1 refs name unknown ID(s): nowhere',
                     'Comparison 1: subjects must be at least two distinct, nonempty names'):
            self.assertIn(part, said)
        self.assertEqual(problems[-1], rc.SYNTHESIS_TAIL)
        self.assertEqual(said.count(rc.SYNTHESIS_TAIL), 1)
        bad = self.synthesis()
        finding = bad['findings'][0]
        finding.update(support=[], title='')
        finding['summary'].update(kind='gap', refs=['health-checks'])
        finding['conditions'][0]['refs'] = ['fact-a', 'fact-a']
        bad['brief'][0]['blocks'][0]['refs'] = []
        said = '\n'.join(self.check(bad))
        for part in ('Finding instance-min: title is empty', 'summary refs name unknown ID(s): health-checks',
                     'its summary is a gap', 'support need at least one ID', 'conditions 1 refs repeat an ID',
                     'Brief section teaching: block 1 refs need at least one ID'):
            self.assertIn(part, said)

    def test_the_studio_refuses_only_what_the_helper_refuses(self):
        def finding(v):
            return v['findings'][0]

        refused = {
            'finding id invalid': lambda v: finding(v).update(id='Instance'),
            'finding id repeated': lambda v: v['findings'][1].update(id='instance-min'),
            'finding id is a fact id': lambda v: v['findings'][1].update(id='fact-a'),
            'finding id is a source id': lambda v: v['findings'][1].update(id='source-a'),
            'finding title blank': lambda v: finding(v).update(title=' '),
            'finding not an object': lambda v: v['findings'].append('a finding'),
            'summary missing': lambda v: finding(v).pop('summary'),
            'summary text empty': lambda v: finding(v)['summary'].update(text=''),
            'summary text too long': lambda v: finding(v)['summary'].update(text='x' * 30001),
            'summary kind unknown': lambda v: finding(v)['summary'].update(kind='claim'),
            'summary is a gap': lambda v: finding(v)['summary'].update(kind='gap'),
            'summary refs a finding': lambda v: finding(v)['summary'].update(refs=['health-checks']),
            'summary refs empty': lambda v: finding(v)['summary'].update(refs=[]),
            'summary refs not an array': lambda v: finding(v)['summary'].update(refs='fact-a'),
            'support empty': lambda v: finding(v).update(support=[]),
            'support unknown': lambda v: finding(v).update(support=['fact-z']),
            'counter repeated': lambda v: finding(v).update(counter=['fact-a', 'fact-a']),
            'counter missing': lambda v: finding(v).pop('counter'),
            'gaps missing': lambda v: finding(v).pop('gaps'),
            'condition kind missing': lambda v: finding(v)['conditions'][0].pop('kind'),
            'sections empty': lambda v: v.update(sections=[]),
            'sections not an array': lambda v: v.update(sections={}),
            'section id repeated': lambda v: v['sections'].append(copy.deepcopy(v['sections'][0])),
            'section title missing': lambda v: v['sections'][0].pop('title'),
            'section blocks empty': lambda v: v['sections'][0].update(blocks=[]),
            'section block refs unknown': lambda v: v['sections'][0]['blocks'][0].update(refs=['nowhere']),
            'brief empty': lambda v: v.update(brief=[]),
            'brief null': lambda v: v.update(brief=None),
            'brief section id invalid': lambda v: v['brief'][0].update(id='Teaching'),
            'comparisons not an array': lambda v: v.update(comparisons={}),
            'comparison one subject': lambda v: v.update(comparisons=[{**comparison(), 'subjects': ['One']}]),
            'comparison repeated subject': lambda v: v.update(comparisons=[{**comparison(), 'subjects': ['One', 'One']}]),
            'comparison title missing': lambda v: v.update(comparisons=[{k: c for k, c in comparison().items() if k != 'title'}]),
            'comparison criterion repeated': lambda v: v.update(comparisons=[{**comparison(), 'rows': comparison()['rows'] * 2}]),
            'comparison cell missing': lambda v: v.update(comparisons=[{**comparison(), 'rows': [
                {'criterion': 'Capacity', 'cells': comparison()['rows'][0]['cells'][:1]}]}]),
            'comparison cell refs a finding': lambda v: v.update(comparisons=[json.loads(
                json.dumps(comparison()).replace('"refs": ["fact-a"]}]', '"refs": ["instance-min"]}]'))]),
            'comparison cell too long': lambda v: v.update(comparisons=[json.loads(
                json.dumps(comparison()).replace('Unknown here.', 'x' * 10001))]),
        }
        for name, change in refused.items():
            with self.subTest(refused=name):
                value = copy.deepcopy(self.full)
                change(value)
                self.assertTrue(rc.synthesis_problems(value, RUNTIME), 'the studio finds it')
                self.assertTrue(rc.refused(value, self.serial), 'and Harness Research refuses it too')
        accepted = {
            'as it is': lambda v: None,
            'no brief': lambda v: v.pop('brief'),
            'no findings': lambda v: (v.update(findings=[]),
                                      v['sections'][0]['blocks'][0].update(refs=['fact-a']),
                                      v['brief'][0]['blocks'][0].update(refs=['fact-a'])),
            'a gap block without refs': lambda v: v['sections'][0]['blocks'].append(
                {'text': 'Unknown.', 'kind': 'gap', 'refs': []}),
            'a section block citing a finding': lambda v: v['sections'][0]['blocks'][0].update(refs=['instance-min']),
            'comparisons null': lambda v: v.update(comparisons=None),
            'a comparison': lambda v: v.update(comparisons=[comparison()]),
            'block text at the limit': lambda v: v['sections'][0]['blocks'][0].update(text='x' * 30000),
        }
        for name, change in accepted.items():
            with self.subTest(accepted=name):
                value = copy.deepcopy(self.full)
                change(value)
                self.assertEqual(rc.refused(value, self.serial), [], 'Harness Research accepts it')
                self.assertEqual(rc.synthesis_problems(value, RUNTIME), [], 'so the studio does too')

    def test_a_whole_dossier_lists_its_source_and_prose_problems_together(self):
        value = copy.deepcopy(self.full)
        del value['sources'][0]['publisher']
        value['brief'] = []
        problems = self.check(value, self.serial)
        self.assertEqual(len(problems), 2, problems)
        self.assertIn('publisher is missing', problems[0])
        self.assertIn('The brief needs at least one section.', problems[1])


@GATED
class PinnedReviewTests(unittest.TestCase):
    """A review is checked against its template inside its job exactly as the helper checks it."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.case = Path(temporary.name) / 'case'
        rc.write(self.case, 'sources/source.txt', TEXT)
        rc.write(self.case, 'dossier.json', json.dumps(dossier('author-1')))
        self.helper = rc.Workflow(RUNTIME)
        self.template = self.helper.command(self.case, 'save', 'dossier.json', 'author-1')['review_template']

    def helper_refuses(self, value):
        rc.write(self.case, 'review.json', json.dumps(value))
        try:
            self.helper.command(self.case, 'review', 'review.json', 'reviewer-1')
        except ValueError:
            return True
        return False

    def test_the_studio_refuses_only_what_the_helper_refuses(self):
        def item(group):
            return lambda v: v[group][0]

        refused = {
            'left pending': lambda v: v['facts'][0].update(verdict='pending'),
            'note empty': lambda v: v['findings'][0].update(note=' '),
            'note missing': lambda v: v['prose'][0].pop('note'),
            'a fact left out': lambda v: v['facts'].pop(),
            'a finding twice': lambda v: v['findings'].append(dict(v['findings'][0])),
            'an unknown prose id': lambda v: v['prose'][0].update(id='nowhere:0'),
            'schema 1': lambda v: v.update(schema=1),
            'another digest': lambda v: v.update(digest='0' * 64),
            'another capture hash': lambda v: v['originals'][0].update(sha256='0' * 64),
            'read_original as text': lambda v: v['originals'][0].update(read_original='yes'),
            'unread without a reason': lambda v: v['originals'][0].update(read_original=False),
            'originals left out': lambda v: v.update(originals=[]),
            'coverage pending': lambda v: v['assessment'].update(coverage='pending'),
            'usefulness unknown': lambda v: v['assessment'].update(usefulness='fine'),
            'assessment note empty': lambda v: v['assessment'].update(note=''),
            'no assessment': lambda v: v.pop('assessment'),
            'facts not an array': lambda v: v.update(facts={}),
        }
        for name, change in refused.items():
            with self.subTest(refused=name):
                value = review(self.template)
                change(value)
                self.assertTrue(rc.review_problems(value, self.template, RUNTIME), 'the studio finds it')
                self.assertTrue(self.helper_refuses(value), 'and Harness Research refuses it too')
        accepted = {
            'unread with a reason': lambda v: v['originals'][0].update(read_original=False,
                                                                      access_error='The tool could not read it.'),
            'narrow, with revision asked': lambda v: (v['facts'][0].update(verdict='narrow'),
                                                     v['assessment'].update(coverage='needs-revision')),
            'an extra field': lambda v: v['facts'][0].update(seen=True),
            'as filled in': lambda v: None,
        }
        for name, change in accepted.items():
            with self.subTest(accepted=name):
                value = review(self.template)
                change(value)
                self.assertEqual(rc.review_problems(value, self.template, RUNTIME), [], 'the studio accepts it')
                self.assertFalse(self.helper_refuses(value), 'as Harness Research does')

    def test_a_review_job_is_told_everything_at_once_and_corrects_it(self):
        sent = []
        data = {'task': {key: dossier('x')[key] for key in rc.TASK_FIELDS}, 'worker': 'reviewer-1',
                'review_template': self.template, 'review_outline': rc.review_outline(RUNTIME),
                'return': 'Review it.', '_execution': {}}
        offered = [{'file': 'sources/source.txt', 'origin': 'https://example.invalid/docs',
                    'permission': 'public', 'title': 'Synthetic source', 'text': TEXT}]

        def call(phase, payload, guidance):
            sent.append((payload, guidance))
            return copy.deepcopy(self.template) if len(sent) == 1 else review(self.template)

        text, _ = research_text.Transport(RUNTIME, call)('review', 'Guide', data, offered, False)
        self.assertFalse(self.helper_refuses(json.loads(text)))
        self.assertIn('review_outline', sent[0][1])
        error = sent[1][0]['validation_error']
        self.assertIn('- facts: set verdict', error)
        self.assertIn('- assessment.note must explain the assessment.', error)

    def test_a_native_review_check_uses_its_template(self):
        spec = {'kind': 'research-json', 'captures': [], 'runtime': RUNTIME, 'review_template': self.template}
        problems = rc.check_json(json.dumps(self.template), spec)[0]
        self.assertTrue(any('set verdict' in problem for problem in problems))
        self.assertEqual(rc.check_json(json.dumps(review(self.template)), spec)[0], [])
        # Without its template a review keeps the schema check alone, as before.
        self.assertEqual(rc.check_json(json.dumps(self.template), {'kind': 'research-json', 'captures': []})[0], [])


if __name__ == '__main__':
    unittest.main()
