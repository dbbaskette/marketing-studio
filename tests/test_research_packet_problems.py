"""Investigators are told every source field up front, and a refused evidence packet lists
every problem at once (#303), without accepting anything Harness Research refuses or refusing
anything it accepts."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import marketing_studio  # noqa: F401  Shared core import path.
from studio_core import research_contract as rc, research_session, research_text
from synthesis_fixture import TEXT, dossier

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')
SECOND = 'Second synthetic capture.  Health  checks start\nthe next batch quickly.\n'
ORIGINS = ('https://example.invalid/docs', 'https://example.invalid/two')
# The shape of the pinned source and fact definitions, for the checks that need no helper.
SCHEMA = {'$defs': {
    'source': {'type': 'object', 'required': ['id', 'file', 'origin', 'title', 'publisher', 'permission', 'context'],
               'properties': {'id': {'type': 'string', 'pattern': '^[a-z0-9][a-z0-9-]{0,63}$'},
                              'file': {'type': 'string'}, 'origin': {'type': 'string'},
                              'title': {'type': 'string'}, 'publisher': {'type': 'string'},
                              'permission': {'enum': ['public', 'selected']},
                              'context': {'enum': ['full', 'partial']},
                              'context_note': {'type': 'string'}, 'source_date': {'type': 'string'},
                              'accessed_at': {'type': 'string'}, 'version': {'type': 'string'},
                              'original_file': {'type': 'string'}},
               'allOf': [{'if': {'properties': {'context': {'const': 'partial'}}},
                          'then': {'required': ['context_note']}}]},
    'fact': {'type': 'object', 'required': ['id', 'statement', 'author', 'citations'],
             'properties': {'id': {'type': 'string', 'pattern': '^[a-z0-9][a-z0-9-]{0,63}$'},
                            'statement': {'type': 'string'}, 'author': {'type': 'string'},
                            'citations': {'type': 'array', 'minItems': 1, 'items': {
                                'type': 'object', 'required': ['source', 'quote'],
                                'properties': {'source': {'type': 'string'}, 'quote': {'type': 'string'},
                                               'locator': {'type': 'string'}}}}}}}}


class Case:
    """A disposable job folder holding two captures, and the spec its checks are given."""

    def make(self, runtime=None, schema=SCHEMA):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        if runtime is None:
            runtime = self.root / 'runtime'
            rc.write(runtime, 'references/synthesis.schema.json', json.dumps(schema))
        self.runtime = str(runtime)
        rc.write(self.root, 'job/sources/one.txt', TEXT)
        rc.write(self.root, 'job/sources/two.txt', SECOND)
        self.captures = [{'file': 'sources/one.txt', 'local': 'sources/one.txt', 'origin': ORIGINS[0],
                          'permission': 'public', 'title': 'Synthetic source'},
                         {'file': 'sources/two.txt', 'local': 'sources/two.txt', 'origin': ORIGINS[1],
                          'permission': 'public', 'title': 'Second synthetic source'}]
        base = dossier('author-1')
        self.spec = {'runtime': self.runtime, 'folder': str(self.root / 'job'), 'worker': 'author-1',
                     'node': shutil.which('node'), 'task': {key: base[key] for key in rc.TASK_FIELDS},
                     'research_mode': 'evidence', 'captures': self.captures}

    def outlined(self):
        """A packet built from the outline, with publisher and context filled in and exact quotes."""
        outline = rc.source_outline(self.captures, self.runtime)
        sources = [{**entry, 'publisher': 'Synthetic publisher', 'context': 'full'}
                   for entry in outline['sources']]
        facts = [{'id': 'f1', 'statement': 'More than one instance keeps capacity.', 'author': 'author-1',
                  'citations': [{'source': 's1', 'quote': 'More than one instance keeps capacity.'}]},
                 {'id': 'f2', 'statement': 'Health checks start the next batch.', 'author': 'author-1',
                  'citations': [{'source': 's2', 'quote': 'Health  checks start\nthe next batch'}]}]
        return {'schema': 2, 'sources': sources, 'facts': facts, 'gaps': []}

    def four(self):
        """A missing publisher, a bad context, a wrong origin and a missing quote."""
        bad = self.outlined()
        del bad['sources'][0]['publisher']
        bad['sources'][0]['context'] = 'complete'
        bad['sources'][1]['origin'] = 'https://example.invalid/wrong'
        bad['facts'][0]['citations'][0]['quote'] = 'Words this source never said.'
        return bad

    def check(self, value, **spec):
        return rc.check_json(json.dumps(value), {**self.spec, **spec})

    def assert_four(self, problems):
        said = '\n'.join(problems)
        self.assertIn('Source s1: publisher is missing', said)
        self.assertIn('context must be one of full, partial', said)
        self.assertIn("Source s2 (sources/two.txt): copy its origin exactly as 'https://example.invalid/two'", said)
        self.assertIn("Fact f1: the quote 'Words this source never said.' is not in source s1 exactly", said)
        self.assertEqual(said.count('resubmit within this job'), 1, 'the guidance is said once')
        self.assertEqual(problems[-1], rc.TAIL)


class OutlineTests(Case, unittest.TestCase):
    def setUp(self):
        self.make()

    def test_outline_fills_in_what_the_studio_knows_and_names_what_to_add(self):
        outline = rc.source_outline(self.captures, self.runtime)
        self.assertEqual(outline['sources'], [
            {'id': 's1', 'file': 'sources/one.txt', 'origin': ORIGINS[0], 'title': 'Synthetic source',
             'permission': 'public'},
            {'id': 's2', 'file': 'sources/two.txt', 'origin': ORIGINS[1],
             'title': 'Second synthetic source', 'permission': 'public'}])
        fill = outline['fill_in']
        self.assertEqual(list(fill), ['title', 'publisher', 'context', 'context_note', 'source_date',
                                      'accessed_at', 'version'])
        self.assertTrue(fill['publisher'].startswith('Required.'))
        self.assertIn('One of full, partial.', fill['context'])
        self.assertTrue(fill['context_note'].startswith('Required when context is partial.'))
        self.assertIn('never guess a date', fill['source_date'])
        self.assertTrue(fill['source_date'].startswith('Optional.'))
        self.assertEqual(outline['fields'], list(SCHEMA['$defs']['source']['properties']))
        self.assertIn('leave it out', outline['note'])

    def test_offered_sources_keep_their_permission_and_origin_spelling(self):
        offered = [{'file': 'sources/a.txt', 'url': 'Supplied deck', 'title': 'Deck'},
                   {'file': 'sources/b.txt', 'origin': ORIGINS[0], 'offered': False}]
        entries = rc.source_outline(offered, self.runtime)['sources']
        self.assertEqual(entries[0], {'id': 's1', 'file': 'sources/a.txt', 'origin': 'Supplied deck',
                                      'title': 'Deck', 'permission': 'selected'})
        self.assertEqual(entries[1]['permission'], 'public')
        self.assertNotIn('title', entries[1])

    def test_the_outline_follows_the_pinned_schema(self):
        changed = copy.deepcopy(SCHEMA)
        source = changed['$defs']['source']
        source['properties']['edition'] = {'type': 'string'}
        source['required'].append('edition')
        source['properties']['context']['enum'] = ['full', 'partial', 'summary']
        self.make(schema=changed)
        fill = rc.source_outline(self.captures, self.runtime)['fill_in']
        self.assertEqual(fill['edition'], 'Required.')
        self.assertIn('One of full, partial, summary.', fill['context'])
        self.assertIsNone(rc.source_outline(self.captures, self.root / 'missing'))

    def test_a_packet_built_from_the_outline_has_nothing_to_correct(self):
        with patch.object(rc, 'refused', return_value=[]) as helper:
            self.assertEqual(self.check(self.outlined())[0], [])
        helper.assert_called_once()

    def test_one_refusal_lists_every_problem_and_the_guidance_once(self):
        with patch.object(rc, 'refused', return_value=[]):
            problems, checks, _, _ = self.check(self.four())
        self.assert_four(problems)
        self.assertEqual(checks[0]['problems'], problems)

    def test_the_helper_still_checks_what_the_studio_found_nothing_wrong_with(self):
        with patch.object(rc, 'refused', return_value=['Harness Research refused this evidence packet: x']) as helper:
            self.check(self.four())
        helper.assert_not_called()   # Both sources had a problem: nothing is left to check.
        bad = self.outlined()
        del bad['sources'][1]['publisher']
        bad['facts'].append({'id': 'f3', 'statement': 'Capacity.', 'author': 'author-1',
                             'citations': [{'source': 's1', 'quote': 'Not in the capture.'}]})
        with patch.object(rc, 'refused', return_value=['Harness Research refused: y']) as helper:
            problems = self.check(bad)[0]
        checked = helper.call_args.args[0]
        self.assertEqual([s['id'] for s in checked['sources']], ['s1'])
        self.assertEqual([f['id'] for f in checked['facts']], ['f1'], 'flawed facts are set aside')
        self.assertIn('Harness Research refused: y', problems)

    def test_a_quote_differing_only_in_spacing_is_shown_as_the_capture_has_it(self):
        bad = self.outlined()
        bad['facts'][1]['citations'][0]['quote'] = 'Health checks start the next batch'
        with patch.object(rc, 'refused', return_value=[]):
            problems = self.check(bad)[0]
        self.assertIn("the capture has it as 'Health  checks start\\nthe next batch': copy that", problems[0])

    def test_every_fact_and_source_rule_is_listed_together(self):
        bad = self.outlined()
        bad['schema'] = 1
        bad['sources'][0].update(id='S1', context='partial', source_date='')
        bad['sources'][1]['title'] = '   '
        bad['facts'][0].update(kind='inference', statement='')
        bad['facts'][1]['citations'][0].update(page=2, locator='')
        bad['facts'].append({'id': 'f1', 'statement': 'Repeat.', 'author': 'someone-else', 'citations': []})
        with patch.object(rc, 'refused', return_value=[]):
            said = '\n'.join(self.check(bad)[0])
        for part in ('set "schema": 2', 'Source S1: id must be lowercase', 'context_note is missing',
                     'source_date is empty', 'Source s2: title is empty', 'unknown field(s) kind',
                     'statement is empty', 'citation 1 has unknown field(s) page', 'citation 1 locator is empty',
                     'another fact has the same id', 'it needs at least one citation',
                     'Set every fact author to author-1.'):
            self.assertIn(part, said)

    def test_report_files_keep_their_unknown_fact_fields(self):
        # The report save does not refuse extra fact fields: only an evidence packet does.
        value = dossier('author-1', file='sources/one.txt')
        value['facts'][0]['note'] = 'kept'
        with patch.object(rc, 'refused', return_value=[]):
            self.assertEqual(self.check(value, research_mode=None)[0], [])

    def test_without_a_pinned_helper_the_checks_are_as_before(self):
        spec = {key: value for key, value in self.spec.items() if key not in ('runtime',)}
        spec['research_mode'] = None
        problems = rc.check_json(json.dumps(self.four()), spec)[0]
        self.assertEqual(len(problems), 1, 'only the origin, which needs no helper')

    def test_the_text_transport_hands_back_every_problem_as_a_list(self):
        data = {'task': self.spec['task'], 'worker': 'author-1', 'return': research_session.EVIDENCE,
                'source_outline': rc.source_outline(self.captures, self.runtime),
                '_execution': {'mode': 'evidence'}}
        offered = [{'file': c['file'], 'origin': c['origin'], 'permission': 'public', 'title': c['title'],
                    'text': (self.root / 'job' / c['local']).read_text()} for c in self.captures]
        sent = []

        def call(phase, payload, guidance):
            sent.append((payload, guidance))
            return self.four() if len(sent) == 1 else self.outlined()

        with patch.object(rc, 'refused', return_value=[]):
            kept, _ = research_text.Transport(self.runtime, call)('investigate', 'Guide', data, offered, False)
        self.assertEqual(json.loads(kept)['facts'], self.outlined()['facts'])
        first, guidance = sent[0]
        self.assertIn('source_outline', guidance)
        self.assertEqual(first['source_outline']['sources'][0]['id'], 's1')
        error = sent[1][0]['validation_error']
        self.assertTrue(error.startswith('- '))
        self.assert_four([line[2:] for line in error.splitlines()])


@unittest.skipUnless(RUNTIME and shutil.which('node'), 'Select the pinned disposable Harness Research runtime.')
class PinnedHelperTests(Case, unittest.TestCase):
    """The real pinned helper: what the studio refuses, it refuses too, and the reverse."""

    def setUp(self):
        self.make(RUNTIME)

    def helper(self, value):
        """What the pinned helper alone says of a packet, as the job's preflight asks it."""
        prepared = research_session.preparation(copy.deepcopy(value), self.spec)
        return rc.refused(prepared, self.spec)

    def studio(self, value):
        prepared = research_session.preparation(copy.deepcopy(value), self.spec)
        texts = rc.capture_texts(prepared['sources'], self.captures, self.spec['folder'])
        return rc.packet_problems(prepared, texts, RUNTIME, 'author-1', 'evidence')[0]

    def test_a_packet_built_from_the_outline_passes_the_first_time(self):
        self.assertEqual(self.check(self.outlined())[0], [])
        dated = self.outlined()
        dated['sources'][0].update(context='partial', context_note='Only the first page.',
                                   source_date='2026-10-01', version='1.1')
        self.assertEqual(self.check(dated)[0], [])

    def test_one_refusal_lists_all_four_problems(self):
        self.assert_four(self.check(self.four())[0])

    def test_the_studio_refuses_only_what_the_helper_refuses(self):
        long = 'x' * 4001
        astral = '\U0001F600' * 2001   # 4002 UTF-16 units, as JavaScript counts them
        cases = {
            'publisher missing': lambda v: v['sources'][0].pop('publisher'),
            'publisher blank': lambda v: v['sources'][0].update(publisher=' 　\n'),
            'publisher too long': lambda v: v['sources'][0].update(publisher=long),
            'publisher too long in UTF-16': lambda v: v['sources'][0].update(publisher=astral),
            'publisher not text': lambda v: v['sources'][0].update(publisher=7),
            'title missing': lambda v: v['sources'][0].pop('title'),
            'context missing': lambda v: v['sources'][0].pop('context'),
            'context unknown': lambda v: v['sources'][0].update(context='complete'),
            'partial without a note': lambda v: v['sources'][0].update(context='partial'),
            'partial with a blank note': lambda v: v['sources'][0].update(context='partial', context_note=' '),
            'source_date empty': lambda v: v['sources'][0].update(source_date=''),
            'source_date null': lambda v: v['sources'][0].update(source_date=None),
            'accessed_at empty': lambda v: v['sources'][0].update(accessed_at=''),
            'version empty': lambda v: v['sources'][0].update(version=''),
            'source id uppercase': lambda v: (v['sources'][0].update(id='S1'),
                                              v['facts'][0]['citations'][0].update(source='S1')),
            'source id repeated': lambda v: v['sources'][1].update(id='s1'),
            'fact id invalid': lambda v: v['facts'][0].update(id='Fact 1'),
            'fact id repeated': lambda v: v['facts'][1].update(id='f1'),
            'fact id is a source id': lambda v: v['facts'][0].update(id='s2'),
            'statement empty': lambda v: v['facts'][0].update(statement=' '),
            'statement too long': lambda v: v['facts'][0].update(statement='x' * 10001),
            'fact kind': lambda v: v['facts'][0].update(kind='inference'),
            'citations empty': lambda v: v['facts'][0].update(citations=[]),
            'citation page': lambda v: v['facts'][0]['citations'][0].update(page=1),
            'quote empty': lambda v: v['facts'][0]['citations'][0].update(quote=''),
            'quote missing': lambda v: v['facts'][0]['citations'][0].pop('quote'),
            'quote not in the capture': lambda v: v['facts'][0]['citations'][0].update(quote='Not there.'),
            'quote spaced differently': lambda v: v['facts'][1]['citations'][0].update(
                quote='Health checks start the next batch'),
            'locator empty': lambda v: v['facts'][0]['citations'][0].update(locator=''),
        }
        for name, change in cases.items():
            with self.subTest(refused=name):
                value = self.outlined()
                change(value)
                self.assertTrue(self.studio(value), 'the studio finds it')
                self.assertTrue(self.helper(value), 'and Harness Research refuses it too')
        accepted = {
            'publisher at the limit': lambda v: v['sources'][0].update(publisher='x' * 4000),
            'publisher at the limit in UTF-16': lambda v: v['sources'][0].update(publisher='\U0001F600' * 2000),
            'publisher a control character JavaScript keeps': lambda v: v['sources'][0].update(publisher='\x1c'),
            'a note on a full source, even blank': lambda v: v['sources'][0].update(context_note=''),
            'partial with a note': lambda v: v['sources'][0].update(context='partial', context_note='Page one.'),
            'every optional field': lambda v: v['sources'][0].update(source_date='2026', accessed_at='today',
                                                                    version='1'),
            'a locator': lambda v: v['facts'][0]['citations'][0].update(locator='Section 2'),
            'a quote at the very start': lambda v: v['facts'][0]['citations'][0].update(quote=TEXT[:20]),
            'two citations': lambda v: v['facts'][0]['citations'].append(
                {'source': 's2', 'quote': 'Second synthetic capture.'}),
        }
        for name, change in accepted.items():
            with self.subTest(accepted=name):
                value = self.outlined()
                change(value)
                self.assertEqual(self.helper(value), [], 'Harness Research accepts it')
                self.assertEqual(self.studio(value), [], 'so the studio does too')
                self.assertEqual(self.check(value)[0], [])

    def test_a_problem_only_the_helper_knows_is_listed_with_the_studios(self):
        bad = self.outlined()
        del bad['sources'][1]['publisher']
        bad['gaps'] = ['y' * 20001]
        problems = self.check(bad)[0]
        self.assertIn('Source s2: publisher is missing', problems[0])
        self.assertIn('Harness Research refused this evidence packet', problems[1])
        self.assertIn('gaps', problems[1])
        self.assertEqual(problems[2:], [rc.TAIL])

    def test_report_saves_list_their_problems_together_and_the_helper_decides_valid_ones(self):
        spec = {**self.spec, 'research_mode': None}
        value = dossier('author-1', file='sources/one.txt')
        self.assertEqual(rc.check_json(json.dumps(value), spec)[0], [])
        value['sources'][0]['context'] = 'complete'
        del value['sources'][0]['publisher']
        value['facts'][0]['citations'][0]['quote'] = 'Words this source never said.'
        problems = rc.check_json(json.dumps(value), spec)[0]
        self.assertEqual(len(problems), 2, problems)
        self.assertNotIn(rc.TAIL, problems)


if __name__ == '__main__':
    unittest.main()
