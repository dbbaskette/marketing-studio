"""Formatting round trips against a stateful native-Docs fixture; no live accounts."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import google_roundtrip as rt
import google_drive as gd
import google_workflow as gw


def word():
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', '<document/>')
    return data.getvalue()


def document():
    blocks = [{'startIndex': 0, 'endIndex': 1, 'sectionBreak': {'sectionStyle': {}}}]
    start = 1
    for text, style, pstyle in [
        ('The delay is in handoffs.\n', {'fontSize': {'magnitude': 22, 'unit': 'PT'}}, {'namedStyleType': 'HEADING_2', 'spaceAbove': {'magnitude': 14, 'unit': 'PT'}}),
        ('😀 This isn’t slow.\n', {}, {'spaceBelow': {'magnitude': 8, 'unit': 'PT'}, 'lineSpacing': 130}),
        ('Keep this link.\n', {'link': {'url': 'https://example.invalid'}}, {'namedStyleType': 'NORMAL_TEXT'})]:
        end = start + rt.utf16(text)
        blocks.append({'startIndex': start, 'endIndex': end, 'paragraph': {'paragraphStyle': pstyle,
            'elements': [{'startIndex': start, 'endIndex': end, 'textRun': {'content': text, 'textStyle': style}}]}})
        start = end
    return {'documentId': 'fixture-doc', 'revisionId': 'r1', 'title': 'Private blog',
            'tabs': [{'tabProperties': {'tabId': 't.0', 'title': 'Blog'}, 'documentTab': {'body': {'content': blocks}}}]}


class Provider:
    def __init__(self):
        self.doc = document(); self.version = '1'; self.writes = 0
    def native_read(self, file_id, inline=False): return copy.deepcopy(self.doc)
    def metadata(self, file_id): return {'version': self.version}
    def export(self, file_id, format): return word() if format == 'docx' else b'## The delay is in handoffs.\n\nExample.\n'
    def native_update(self, file_id, revision, requests):
        if revision != self.doc['revisionId']: raise gd.GoogleError('stale')
        self.writes += 1
        blocks = self.doc['tabs'][0]['documentTab']['body']['content']
        def locate(index):
            for block in blocks:
                if 'paragraph' not in block: continue
                text = ''.join(e['textRun']['content'] for e in block['paragraph']['elements'])
                if block['startIndex'] <= index < block['endIndex']:
                    offset = index - block['startIndex']
                    pos = next(i for i in range(len(text)+1) if rt.utf16(text[:i]) == offset)
                    return block, pos
            raise AssertionError(index)
        def expand(block):
            return [(c, copy.deepcopy(e['textRun'].get('textStyle', {}))) for e in block['paragraph']['elements'] for c in e['textRun']['content']]
        def save(block, chars):
            block['paragraph']['elements'] = [{'textRun': {'content': c, 'textStyle': style}} for c, style in chars]
            start = 1
            for b in blocks:
                if 'paragraph' not in b: continue
                b['startIndex'] = start
                for e in b['paragraph']['elements']:
                    e['startIndex'] = start; start += rt.utf16(e['textRun']['content']); e['endIndex'] = start
                b['endIndex'] = start
        for request in requests:
            if 'deleteContentRange' in request:
                r = request['deleteContentRange']['range']; block, start = locate(r['startIndex']); endblock, end = locate(r['endIndex'])
                assert block is endblock
                chars = expand(block); del chars[start:end]; save(block, chars)
            elif 'insertText' in request:
                r = request['insertText']; block, start = locate(r['location']['index']); chars = expand(block)
                chars[start:start] = [(c, {}) for c in r['text']]; save(block, chars)
            else:
                r = request['updateTextStyle']; block, start = locate(r['range']['startIndex']); endblock, end = locate(r['range']['endIndex'])
                assert block is endblock
                chars = expand(block); chars[start:end] = [(c, r['textStyle']) for c, _ in chars[start:end]]; save(block, chars)
        self.doc['revisionId'] = 'r2'; self.version = '2'
        return {'status': 'written-unverified'}


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.client = Provider()
    def edits(self):
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        return [{'tab_id': 't.0', 'start_index': b['startIndex'],
                 'before': b['paragraph']['elements'][0]['textRun']['content'][:-1], 'after': after}
                for b, after in zip(blocks[1:3], ['The delay comes from handoffs.', '😀 This is not slow.'])]
    def test_capture_hashes_and_private_files(self):
        folder = self.root/'snapshot'; result = rt.capture(self.client, 'fixture-doc', 't.0', folder)
        self.assertEqual(result['status'], 'captured-unreviewed')
        obs = json.loads((folder/'observation.json').read_text()); text = (folder/'document.md').read_text()
        self.assertFalse(obs['structure_verified'])
        files = gw.formatted_snapshot(folder, obs, text)
        self.assertEqual(set(files), {'document.md', 'document.docx', 'native.json', 'snapshot.json'})
        self.assertEqual((folder/'document.docx').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(gd.GoogleError): rt.capture(self.client, 'fixture-doc', 't.0', folder)
        (folder/'document.md').write_text('tampered')
        with self.assertRaises(ValueError): gw.formatted_snapshot(folder, obs, text)
    def test_snapshot_invalid_word_returns_bounded_error(self):
        folder = self.root/'snapshot'; rt.capture(self.client, 'fixture-doc', 't.0', folder)
        meta = json.loads((folder/'snapshot.json').read_text())
        (folder/'document.docx').write_bytes(b'not word')
        meta['files']['document.docx'] = gd.digest(b'not word')
        (folder/'snapshot.json').write_text(json.dumps(meta))
        obs = json.loads((folder/'observation.json').read_text())
        with self.assertRaises(ValueError): gw.formatted_snapshot(folder, obs, (folder/'document.md').read_text())

    def test_capture_rejects_other_tabs_suggestions_and_revision_races(self):
        original = copy.deepcopy(self.client.doc)
        self.client.doc['tabs'].append(copy.deepcopy(self.client.doc['tabs'][0]))
        with self.assertRaises(gd.GoogleError): rt.capture(self.client, 'fixture-doc', 't.0', self.root/'a')
        self.client.doc = copy.deepcopy(original); self.client.doc['suggestedDocumentStyleChanges'] = {'s': {}}
        with self.assertRaises(gd.GoogleError): rt.capture(self.client, 'fixture-doc', 't.0', self.root/'b')
        self.client.doc = original; self.client.metadata = Mock(side_effect=[{'version':'1'}, {'version':'2'}])
        with self.assertRaises(gd.GoogleError): rt.capture(self.client, 'fixture-doc', 't.0', self.root/'c')
        self.assertEqual(list(self.root.iterdir()), [])
    def test_multi_paragraph_unicode_patch_preserves_heading_spacing_and_link(self):
        original = rt.semantic(self.client.doc)
        plan = rt.build_plan(self.client.doc, self.edits())
        result = rt.apply(self.client, plan, self.root/'receipt.json')
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(self.client.writes, 1)
        before = original['tabs'][0]['documentTab']['body']['content']
        after = rt.semantic(self.client.doc)['tabs'][0]['documentTab']['body']['content']
        for a, b in zip(before[1:], after[1:]):
            self.assertEqual(a['paragraph']['paragraphStyle'], b['paragraph']['paragraphStyle'])
        self.assertEqual(before[-1], after[-1])
        self.assertTrue(all(e['style'].get('fontSize', {}).get('magnitude') == 22 for e in after[1]['paragraph']['elements']))
        self.assertEqual(rt.verify(self.client, plan)['status'], 'verified')
        with self.assertRaises(gd.GoogleError): rt.apply(self.client, plan, self.root/'receipt2.json')
        self.assertEqual(self.client.writes, 1)
    def test_stale_tampered_or_repeated_plan_cannot_write(self):
        plan = rt.build_plan(self.client.doc, self.edits()); tampered = copy.deepcopy(plan)
        tampered['requests'].append({'deleteContentRange': {}})
        with self.assertRaises(gd.GoogleError): rt.apply(self.client, tampered, self.root/'r')
        self.assertEqual(self.client.writes, 0)
        def uncertain(*args): raise gd.GoogleError('timeout')
        self.client.native_update = Mock(side_effect=uncertain)
        with self.assertRaises(gd.GoogleError): rt.apply(self.client, plan, self.root/'r')
        with self.assertRaises(FileExistsError): rt.apply(self.client, plan, self.root/'r')
        self.assertEqual(self.client.native_update.call_count, 1)
    def test_readback_style_drift_is_unverified(self):
        plan = rt.build_plan(self.client.doc, self.edits())
        rt.apply(self.client, plan, self.root/'r')
        self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['paragraphStyle']['lineSpacing'] = 250
        self.assertEqual(rt.verify(self.client, plan)['status'], 'written-unverified')
    def test_structural_edits_and_ambiguous_run_replacements_blocked(self):
        edits = self.edits(); edits[0]['after'] = 'New\nheading'
        with self.assertRaises(gd.GoogleError): rt.build_plan(self.client.doc, edits)
        edits = self.edits(); edits[0]['before'] = 'wrong'
        with self.assertRaises(gd.GoogleError): rt.build_plan(self.client.doc, edits)
        paragraph = self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']
        paragraph['elements'] = [
            {'startIndex': 1, 'endIndex': 4, 'textRun': {'content': 'The', 'textStyle': {'bold': True}}},
            {'startIndex': 4, 'endIndex': 26, 'textRun': {'content': ' delay is in handoffs.\n', 'textStyle': {}}}]
        edits = [{'tab_id':'t.0','start_index':1,'before':'The delay is in handoffs.','after':'Replacement'}]
        with self.assertRaises(gd.GoogleError): rt.build_plan(self.client.doc, edits)


if __name__ == '__main__': unittest.main()
