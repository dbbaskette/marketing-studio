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

    def test_a_supplied_document_is_shown_as_one_never_as_a_folder_of_this_computer(self):
        """#550: Harness Research 1.6.0 records a new supplied document as supplied:<name>,
        an earlier one by the absolute path of its folder copy. Both are shown as supplied."""
        from studio_core import research_contract as rc
        sources = [dict(id='s1', title='Notes', origin='supplied:notes/guide.md', permission='selected'),
                   dict(id='s2', title='Deck', origin='/private/var/folders/x/inputs/a1.txt', permission='selected'),
                   dict(id='s3', title='Page', origin='https://example.invalid/page', permission='public'),
                   dict(id='s4', title='Label', origin='Supplied synthetic deck', permission='selected')]
        packet = dict(request_digest='scope', generation=1, attempt=1, facts=[], sources=sources, limitations=[], gaps=[])
        shown = [source['origin'] for source in preview.evidence(packet, 'basis')['sources']]
        self.assertEqual(shown, [rc.SUPPLIED, rc.SUPPLIED, 'https://example.invalid/page', 'Supplied synthetic deck'])
        for origin in ('supplied:a.txt', '/var/x/a.txt', 'C:\\inputs\\a.txt', '\\\\server\\a.txt', 'file:///x/a.txt'):
            self.assertTrue(rc.local_origin(origin), origin)
            self.assertEqual(rc.shown_origin(origin), rc.SUPPLIED)
        self.assertEqual(rc.shown_origin(None), '')
        # The creator-approved evidence a Training Studio research report publishes.
        from studio_core import research_decisions
        value = dict(topic='Synthetic', sources=sources[:3], facts=[], findings=[], sections=[], brief=[],
                     comparisons=[], creator_review=dict(choices={}, notes={}))
        evidence = research_decisions.render(value)['evidence.md']
        self.assertNotIn('/private/var', evidence)
        self.assertNotIn('supplied:', evidence)
        self.assertEqual(evidence.count(rc.SUPPLIED), 2)
        self.assertIn('[Original source](https://example.invalid/page)', evidence)

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
