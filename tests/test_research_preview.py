"""Accepted preview identity, bounded payloads and immutable restore."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_preview as preview


class EvidencePreviewTests(unittest.TestCase):
    def test_bounded_read_only_projection(self):
        packet = dict(request_digest='scope', generation=2, attempt=3,
                      facts=[dict(statement='x' * 3000, citations=[]) for _ in range(50)],
                      sources=[], limitations=[], gaps=['Unknown'])
        view = preview.evidence(packet, 'source-basis')
        self.assertEqual(len(view['facts']), 12)
        self.assertEqual(len(view['facts'][0]['statement']), 1200)
        self.assertTrue(view['truncated'])
        self.assertEqual(view['limitations'], ['Unknown'])
        self.assertEqual(len(packet['facts']), 50)

    def test_restore_requires_current_packet_hash_scope_generation_and_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp)
            packet = dict(request_digest='scope', generation=2, attempt=3, workstream='a', investigator='worker', facts=[], sources=[])
            raw = json.dumps(packet).encode(); (case / 'packet.json').write_bytes(raw)
            attempt = dict(status='accepted', number=3, investigator='worker', packet=dict(file='packet.json', sha256=hashlib.sha256(raw).hexdigest()))
            state = dict(request_digest='scope', generation=2, workstreams=[dict(id='a', attempts=[attempt])])
            self.assertIn('a', preview.restored(case, state, 'basis'))
            for key, value in [('generation', 3), ('request_digest', 'changed'), ('status', 'stopped')]:
                self.assertEqual(preview.restored(case, {**state, key: value}, 'basis'), {})
            attempt['number'] = 4
            self.assertEqual(preview.restored(case, state, 'basis'), {})
            attempt['number'] = 3; (case / 'packet.json').write_text('{}')
            self.assertEqual(preview.restored(case, state, 'basis'), {})
