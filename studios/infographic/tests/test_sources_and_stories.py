"""Source-to-story acceptance with disposable content and no assistant/network."""
from copy import deepcopy
from pathlib import Path
from unittest import mock

from helpers import Isolated
from runner import evidence, sources, stories
from runner.contracts import Invalid, digest
from runner.workspace import Store


class SourceStoryTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace, data=self.data)
        self.project = self.store.create('A service restart', direction='hybrid')
        self.ident = self.project['id']

    def capture(self, text='One instance restarts while the others serve.', **options):
        self.project = sources.capture(self.store, self.ident, text.encode(),
                                       expected_revision=self.project['revision'], **options)
        return self.project

    def fact(self):
        source = self.project['sources'][0]
        quote = sources.read(self.store, self.project, source)
        return {'id': 'f1', 'statement': quote, 'value': quote, 'unit': '',
                'status': 'supplied', 'evidence': [{'source_id': source['id'],
                    'start': 0, 'end': len(quote), 'quote': quote}]}

    def proposal(self, **options):
        return {'id': 'story1', 'headline': 'Restart without losing the thread',
                'takeaway': 'Restart one instance while the others serve.',
                'rationale': 'Explain the relationship through a process.',
                'qualifications': ['This is supplied information, not independently checked.'],
                'omissions': [], 'blocks': [{'id': 'b1', 'kind': 'process', 'title': 'One at a time',
                    'text': 'Restart one instance while the other instances continue serving.',
                    'fact_ids': ['f1'], 'required_ids': [], 'illustration': True,
                    'illustration_role': 'Show one instance away and the remaining instances serving.'}], **options}

    def ready(self):
        self.capture()
        self.project = evidence.adopt(self.store, self.ident, [self.fact()],
                                      expected_revision=self.project['revision'])

    def test_capture_keeps_original_and_normalized_bytes_and_urls_never_fetch(self):
        raw = b'\xef\xbb\xbfOriginal\r\nhttps://example.invalid/do-not-fetch\r\n'
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('No fetch')):
            p = sources.capture(self.store, self.ident, raw, kind='markdown',
                                expected_revision=0)
        source = p['sources'][0]
        base = self.workspace / 'projects' / self.ident
        self.assertEqual((base / source['file']).read_bytes(), raw)
        self.assertEqual(sources.read(self.store, p, source), 'Original\nhttps://example.invalid/do-not-fetch\n')
        self.assertNotEqual(source['sha256'], source['normalized_sha256'])
        self.assertEqual(p['revision'], 1)

    def test_invalid_encoding_size_type_and_path_do_not_mutate_project(self):
        for raw, options in [(b'\xff', {}), (b'\x00bin', {}), (b'   ', {}),
                             (b'valid', {'kind': 'pdf'}), (b'valid', {'name': '/private/path.txt'}),
                             (b'x' * (16_000_001), {})]:
            with self.subTest(options=options, size=len(raw)), self.assertRaises(Invalid):
                sources.capture(self.store, self.ident, raw, expected_revision=0, **options)
        self.assertEqual(self.store.read(self.ident), self.project)

    def test_csv_preview_requires_explicit_matching_selection_and_preserves_missing_cells(self):
        raw = b'Name,Count,Date\nFirst,12,2026-01-01\nSecond,,2026-01-02\n'
        preview = sources.csv_preview(raw)
        self.assertEqual(preview['row_count'], 2)
        self.assertEqual(self.store.read(self.ident)['revision'], 0)
        selection = {'confirmed': True, 'sha256': preview['sha256'], 'rows': [2, 1],
                     'columns': [{'name': 'Count', 'type': 'number', 'unit': 'requests'},
                                 {'name': 'Date', 'type': 'date', 'unit': ''}]}
        p = sources.capture(self.store, self.ident, raw, kind='csv', selection=selection,
                            expected_revision=0)
        text = sources.read(self.store, p, p['sources'][0])
        self.assertIn('"Count":null', text)
        self.assertLess(text.index('"row":2'), text.index('"row":1'))
        self.assertNotIn('Second', text, 'Unselected columns do not enter normalized evidence')
        self.assertEqual(p['sources'][0]['selection']['rows'], [2, 1])

    def test_csv_refuses_ambiguous_numbers_duplicates_and_unconfirmed_changed_previews(self):
        raw = b'Count\n"1,200"\n'
        preview = sources.csv_preview(raw)
        selection = {'confirmed': True, 'sha256': preview['sha256'], 'rows': [1],
                     'columns': [{'name': 'Count', 'type': 'number', 'unit': 'requests'}]}
        cases = [selection, dict(selection, confirmed=False), dict(selection, rows=[1, 1]),
                 dict(selection, sha256='0' * 64), dict(selection, rows=[0])]
        for selected in cases:
            with self.subTest(selected=selected), self.assertRaises(Invalid):
                sources.capture(self.store, self.ident, raw, kind='csv', selection=selected, expected_revision=0)
        self.assertEqual(self.store.read(self.ident)['revision'], 0)
        with self.assertRaises(Invalid): sources.csv_preview(b'One,One\n1,2\n')
        with self.assertRaises(Invalid): sources.csv_preview(b'One,Two\n1\n')

    def test_read_file_refuses_links_and_unsupported_formats(self):
        target = self.temp / 'notes.txt'
        target.write_text('Supplied notes')
        link = self.temp / 'linked.txt'
        link.symlink_to(target)
        with self.assertRaises(Invalid): sources.read_file(link)
        unsupported = self.temp / 'notes.docx'
        unsupported.write_bytes(b'not a supported file')
        with self.assertRaises(Invalid): sources.read_file(unsupported)
        self.assertEqual(sources.read_file(target), ('text', b'Supplied notes'))

    def test_located_evidence_rejects_wrong_quote_offset_number_and_corroboration(self):
        self.capture()
        for update in ({'status': 'corroborated'}, {'value': 999, 'unit': 'requests',
                        'period': '', 'denominator': '', 'conditions': '', 'uncertainty': ''}):
            fact = {**self.fact(), **update}
            with self.subTest(update=update), self.assertRaises(Invalid):
                evidence.adopt(self.store, self.ident, [fact], expected_revision=1)
        fact = self.fact()
        fact['evidence'][0]['quote'] = 'Not the source.'
        with self.assertRaises(Invalid): evidence.adopt(self.store, self.ident, [fact], expected_revision=1)
        self.assertEqual(self.store.read(self.ident)['facts'], [])

    def test_source_change_invalidates_story_and_retains_original_history(self):
        self.ready()
        self.project = stories.adopt(self.store, self.ident, [self.proposal()], expected_revision=2)
        self.project = stories.select(self.store, self.ident, 'story1', expected_revision=3)
        old = deepcopy(self.project)
        self.capture('Updated source, without the old assertion.', replace_id=old['sources'][0]['id'])
        self.assertEqual((self.project['facts'], self.project['stories'], self.project['selected_story']), ([], [], None))
        self.assertIn(old, self.store.history(self.ident))
        self.assertEqual(sources.read(self.store, old, old['sources'][0]), self.fact_for_old(old)['value'])
        with self.assertRaises(Invalid):
            sources.capture(self.store, self.ident, b'Stale write', expected_revision=old['revision'])

    def fact_for_old(self, project):
        return project['facts'][0]

    def test_three_direction_modes_select_without_provider_or_approval(self):
        self.ready()
        for mode in ('direct', 'suggest', 'hybrid'):
            self.project = self.store.update(self.ident, {'brief': {**self.project['brief'], 'direction': mode}},
                                             expected_revision=self.project['revision'])
            proposals = [self.proposal()]
            self.project = stories.adopt(self.store, self.ident, proposals,
                                         expected_revision=self.project['revision'])
            self.project = stories.select(self.store, self.ident, 'story1', expected_revision=self.project['revision'])
            self.assertEqual(self.project['selected_story'], 'story1')
            self.assertIsNone(self.project['approval'])
            self.assertEqual(self.project['attempts'], [])

    def test_story_loses_no_locked_words_or_requirements_and_omissions_block_selection(self):
        self.ready()
        self.project = self.store.update(self.ident, {'brief': {**self.project['brief'], 'direction': 'suggest',
                         'locked_words': ['One at a time'], 'must_show': [{'id': 'r1', 'text': 'Retain capacity'}]}},
                         expected_revision=self.project['revision'])
        proposal = self.proposal()
        with self.assertRaises(Invalid): stories.verify(self.project, [proposal])
        proposal['omissions'] = ['r1']
        self.project = stories.adopt(self.store, self.ident, [proposal], expected_revision=self.project['revision'])
        with self.assertRaises(Invalid): stories.select(self.store, self.ident, 'story1', expected_revision=self.project['revision'])
        lost = deepcopy(proposal)
        lost['blocks'][0]['title'] = 'All together'
        with self.assertRaises(Invalid): stories.verify(self.project, [lost])
        with self.assertRaises(Invalid): stories.verify(self.project, [proposal, {**proposal, 'id': 'duplicate'}])

    def test_numeric_context_and_deterministic_calculation(self):
        self.capture('Baseline 12. Comparison 24. Unit: requests. Period: 2026-01. Denominator: per second. Conditions: same benchmark. Uncertainty: not reported.')
        source = self.project['sources'][0]
        facts = []
        for ident, value, label in [('f1', 12, 'Baseline'), ('f2', 24, 'Comparison')]:
            quote = label + ' ' + str(value)
            start = sources.read(self.store, self.project, source).index(quote)
            facts.append({'id': ident, 'statement': label, 'metric': label, 'value': value,
                          'unit': 'requests', 'status': 'supplied', 'period': '2026-01',
                          'denominator': 'per second', 'conditions': 'same benchmark', 'uncertainty': 'not reported',
                          'evidence': [{'source_id': source['id'], 'start': start, 'end': start + len(quote), 'quote': quote}]})
        self.assertEqual(evidence.verify(self.store, self.project, facts), facts)
        evidence.comparable(facts)
        derived = {'id': 'f3', 'statement': 'Ratio', 'value': 2, 'unit': 'ratio', 'status': 'supplied',
                   'evidence': [], 'calculation': {'operator': 'ratio', 'operands': ['f2', 'f1']}}
        evidence.verify(self.store, self.project, facts + [derived])
        with self.assertRaises(Invalid): evidence.verify(self.store, self.project, facts + [{**derived, 'value': 4}])
        facts[1]['period'] = '2025-01'
        with self.assertRaises(Invalid): evidence.comparable(facts)
        facts[1]['period'] = ''
        self.assertEqual(evidence.findings(facts)[0]['kind'], 'missing-context')

    def test_numeric_context_cannot_be_invented_from_a_bare_value(self):
        self.capture('Latency 12')
        source = self.project['sources'][0]
        fact = {'id': 'f1', 'statement': 'Latency', 'value': 12, 'unit': 'milliseconds', 'status': 'supplied',
                'period': '', 'denominator': '', 'conditions': '', 'uncertainty': '',
                'evidence': [{'source_id': source['id'], 'start': 8, 'end': 10, 'quote': '12'}]}
        with self.assertRaises(Invalid): evidence.verify(self.store, self.project, [fact])
        fact['unit'] = 'unknown'
        evidence.verify(self.store, self.project, [fact])
        self.assertIn('unit', evidence.findings([fact])[0]['message'])
        with self.assertRaises(Invalid): evidence.comparable([fact])

    def test_unique_exact_quote_can_resolve_an_assistants_bad_character_count(self):
        self.capture('Preface. One instance restarts while the others serve.')
        fact = self.fact()
        fact['evidence'][0].update(quote='One instance restarts while the others serve.', start=0, end=2)
        fact['value'] = fact['evidence'][0]['quote']
        located = evidence.locate(self.store, self.project, [fact])
        self.assertEqual(located[0]['evidence'][0]['start'], 9)
        evidence.verify(self.store, self.project, located)
        self.assertEqual(fact['evidence'][0]['start'], 0, 'Do not mutate the original assistant response')

    def test_ambiguous_quotes_are_never_guessed(self):
        self.capture('The instance serves. The instance serves.')
        fact = self.fact()
        fact['evidence'][0].update(quote='The instance serves.', start=1, end=2)
        with self.assertRaises(Invalid): evidence.locate(self.store, self.project, [fact])

    def test_numeric_display_retains_source_precision_without_rounding(self):
        self.capture('Price 12.30 USD. Period January. Denominator per subscription. Conditions production. Uncertainty not reported.')
        source = self.project['sources'][0]
        fact = {'id': 'f1', 'statement': 'Price', 'value': 12.3, 'unit': 'USD', 'status': 'supplied',
                'period': 'January', 'denominator': 'per subscription', 'conditions': 'production', 'uncertainty': 'not reported',
                'evidence': [{'source_id': source['id'], 'quote': '12.30'}]}
        located = evidence.locate(self.store, self.project, [fact])
        self.assertEqual(located[0]['literal'], '12.30')
        evidence.verify(self.store, self.project, located)
        located[0]['literal'] = '12.31'
        with self.assertRaises(Invalid): evidence.verify(self.store, self.project, located)
