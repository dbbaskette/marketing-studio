"""The actual collection contract must reject bad evidence inside its author job."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import marketing_studio  # Shared core import path.
from studio_core import research_contract as rc, research_session, research_text
from synthesis_fixture import TEXT, dossier

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')


@unittest.skipUnless(RUNTIME, 'Select the pinned disposable Harness Research runtime.')
class CollectionPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        rc.write(self.root, 'sources/source.txt', TEXT)
        base = dossier('author-1')
        self.value = {key: base[key] for key in ('schema', 'sources', 'facts')}
        self.value['gaps'] = []
        self.spec = {'runtime': RUNTIME, 'folder': str(self.root), 'worker': 'author-1',
                     'task': {key: base[key] for key in rc.TASK_FIELDS},
                     'research_mode': 'evidence', 'captures': [{
                         'file': 'sources/source.txt', 'local': 'sources/source.txt',
                         'origin': 'https://example.invalid/docs', 'permission': 'public'}]}

    def check(self, value):
        return rc.check_json(json.dumps(value), self.spec)

    def test_collection_rejects_every_unknown_nested_field_before_acceptance(self):
        cases = [('fact', 'kind', 'inference'), ('fact', 'confidence', 'high'),
                 ('citation', 'kind', 'quote'), ('citation', 'page', 1),
                 ('source', 'invented_metadata', 'retain for correction')]
        for group, key, value in cases:
            with self.subTest(group=group, key=key):
                bad = copy.deepcopy(self.value)
                item = bad['facts'][0] if group == 'fact' else bad['facts'][0]['citations'][0] if group == 'citation' else bad['sources'][0]
                item[key] = value
                problems, _, _, kept = self.check(bad)
                self.assertTrue(problems)
                self.assertIn(key, ' '.join(problems))
                self.assertIn('within this job', ' '.join(problems))
                self.assertEqual(json.loads(kept)['facts'], bad['facts'], 'Do not silently discard a fact classification')
        problems, _, _, kept = self.check(self.value)
        self.assertFalse(problems, problems)
        self.assertEqual(json.loads(kept)['facts'], self.value['facts'])
        self.assertFalse((self.root / '.harness-research').exists(), 'Preflight must not alter production state')

    def test_bad_quotes_and_permissions_cannot_pass_the_collection_check(self):
        bad = copy.deepcopy(self.value)
        bad['facts'][0]['citations'][0]['quote'] = 'Not in the captured source.'
        self.assertTrue(self.check(bad)[0])
        bad = copy.deepcopy(self.value)
        bad['sources'][0]['permission'] = 'selected'
        self.assertTrue(self.check(bad)[0])

    def test_selected_originals_and_source_date_alias_pass_the_same_contract(self):
        selected = copy.deepcopy(self.value)
        selected['sources'][0].update(permission='selected', origin='Supplied notes', date='2026-10-01')
        self.spec['task']['source_mode'] = 'selected'
        self.spec['captures'][0].update(permission='selected', origin='Supplied notes', original='sources/original.txt')
        rc.write(self.root, 'sources/original.txt', TEXT)
        problems, _, _, kept = self.check(selected)
        self.assertFalse(problems, problems)
        self.assertEqual(json.loads(kept)['sources'][0]['source_date'], '2026-10-01')

    def test_unavailable_checker_never_falls_back_to_report_validation(self):
        for error in (OSError('Unavailable'), subprocess.TimeoutExpired('helper', 120)):
            with self.subTest(error=type(error).__name__), patch.object(rc, 'collection_preflight', side_effect=error), patch.object(rc.subprocess, 'run') as command:
                problems = rc.refused(dossier('author-1'), self.spec)
                self.assertIn('not accepted', ' '.join(problems))
                command.assert_not_called()

    def test_packet_gap_bounds_are_checked_after_evidence_preparation(self):
        bad = copy.deepcopy(self.value)
        bad['gaps'] = ['x' * 20001]
        problems = self.check(bad)[0]
        self.assertTrue(problems)
        self.assertIn('gaps', ' '.join(problems))
        self.value['gaps'] = ['A bounded unresolved question for synthesis.']
        self.assertFalse(self.check(self.value)[0])

    def test_json_transport_corrects_the_packet_in_the_same_phase(self):
        calls = []
        data = {'task': self.spec['task'], 'worker': 'author-1',
                'return': research_session.EVIDENCE, '_execution': {'mode': 'evidence'}}
        offered = [{'file': 'sources/source.txt', 'origin': 'https://example.invalid/docs',
                    'permission': 'public', 'title': 'Synthetic source', 'text': TEXT}]

        def call(phase, payload, guidance):
            calls.append(phase)
            self.assertNotIn('Sections/brief have', guidance)
            if len(calls) == 1:
                bad = copy.deepcopy(self.value)
                bad['facts'][0]['kind'] = 'inference'
                return bad
            self.assertIn('Unknown fact field: kind', payload['validation_error'])
            self.assertEqual(json.loads(payload['previous_output'])['facts'][0]['kind'], 'inference')
            return self.value

        kept, captures = research_text.Transport(RUNTIME, call)('investigate', 'Synthetic guide', data, offered, False)
        self.assertEqual(calls, ['investigate', 'investigate'])
        self.assertEqual(json.loads(kept)['facts'], self.value['facts'])
        self.assertEqual(captures, offered)
