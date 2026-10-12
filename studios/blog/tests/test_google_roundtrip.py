"""Formatting round trips against a stateful native-Docs fixture; no live accounts."""

import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import google_roundtrip as rt
import google_drive as gd
import google_workflow as gw
import studio


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
        (
            'The delay is in handoffs.\n',
            {'fontSize': {'magnitude': 22, 'unit': 'PT'}},
            {'namedStyleType': 'HEADING_2', 'spaceAbove': {'magnitude': 14, 'unit': 'PT'}},
        ),
        (
            '😀 This isn’t slow.\n',
            {},
            {'spaceBelow': {'magnitude': 8, 'unit': 'PT'}, 'lineSpacing': 130},
        ),
        (
            'Keep this link.\n',
            {'link': {'url': 'https://example.invalid'}},
            {'namedStyleType': 'NORMAL_TEXT'},
        ),
    ]:
        end = start + rt.utf16(text)
        blocks.append(
            {
                'startIndex': start,
                'endIndex': end,
                'paragraph': {
                    'paragraphStyle': pstyle,
                    'elements': [
                        {
                            'startIndex': start,
                            'endIndex': end,
                            'textRun': {'content': text, 'textStyle': style},
                        }
                    ],
                },
            }
        )
        start = end
    return {
        'documentId': 'fixture-doc',
        'revisionId': 'r1',
        'title': 'Private blog',
        'tabs': [
            {
                'tabProperties': {'tabId': 't.0', 'title': 'Blog'},
                'documentTab': {'body': {'content': blocks}},
            }
        ],
    }


class Provider:
    def __init__(self):
        self.doc = document()
        self.version = '1'
        self.writes = 0

    def native_read(self, file_id, inline=False):
        return copy.deepcopy(self.doc)

    def metadata(self, file_id):
        return {'version': self.version}

    def export(self, file_id, format):
        return word() if format == 'docx' else b'## The delay is in handoffs.\n\nExample.\n'

    def native_update(self, file_id, revision, requests):
        if revision != self.doc['revisionId']:
            raise gd.GoogleError('stale')
        self.writes += 1
        blocks = self.doc['tabs'][0]['documentTab']['body']['content']

        def locate(index):
            for block in blocks:
                if 'paragraph' not in block:
                    continue
                text = ''.join(e['textRun']['content'] for e in block['paragraph']['elements'])
                if block['startIndex'] <= index < block['endIndex']:
                    offset = index - block['startIndex']
                    pos = next(i for i in range(len(text) + 1) if rt.utf16(text[:i]) == offset)
                    return block, pos
            raise AssertionError(index)

        def expand(block):
            return [
                (c, copy.deepcopy(e['textRun'].get('textStyle', {})))
                for e in block['paragraph']['elements']
                for c in e['textRun']['content']
            ]

        def save(block, chars):
            block['paragraph']['elements'] = [
                {'textRun': {'content': c, 'textStyle': style}} for c, style in chars
            ]
            start = 1
            for b in blocks:
                if 'paragraph' not in b:
                    continue
                b['startIndex'] = start
                for e in b['paragraph']['elements']:
                    e['startIndex'] = start
                    start += rt.utf16(e['textRun']['content'])
                    e['endIndex'] = start
                b['endIndex'] = start

        for request in requests:
            if 'deleteContentRange' in request:
                r = request['deleteContentRange']['range']
                block, start = locate(r['startIndex'])
                endblock, end = locate(r['endIndex'])
                assert block is endblock
                chars = expand(block)
                del chars[start:end]
                save(block, chars)
            elif 'insertText' in request:
                r = request['insertText']
                block, start = locate(r['location']['index'])
                chars = expand(block)
                chars[start:start] = [(c, {}) for c in r['text']]
                save(block, chars)
            else:
                r = request['updateTextStyle']
                block, start = locate(r['range']['startIndex'])
                endblock, end = locate(r['range']['endIndex'])
                assert block is endblock
                chars = expand(block)
                chars[start:end] = [(c, r['textStyle']) for c, _ in chars[start:end]]
                save(block, chars)
        self.doc['revisionId'] = 'r2'
        self.version = '2'
        return {'status': 'written-unverified'}


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client = Provider()

    def edits(self):
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        return [
            {
                'tab_id': 't.0',
                'start_index': b['startIndex'],
                'before': b['paragraph']['elements'][0]['textRun']['content'][:-1],
                'after': after,
            }
            for b, after in zip(
                blocks[1:3],
                ['The delay comes from handoffs.', '😀 This is not slow.'],
                strict=False,
            )
        ]

    def test_capture_hashes_and_private_files(self):
        folder = self.root / 'snapshot'
        result = rt.capture(self.client, 'fixture-doc', 't.0', folder)
        self.assertEqual(result['status'], 'captured-unreviewed')
        obs = json.loads((folder / 'observation.json').read_text())
        text = (folder / 'document.md').read_text()
        self.assertFalse(obs['structure_verified'])
        files = gw.formatted_snapshot(folder, obs, text)
        self.assertEqual(
            set(files), {'document.md', 'document.docx', 'native.json', 'snapshot.json'}
        )
        self.assertEqual((folder / 'document.docx').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(gd.GoogleError):
            rt.capture(self.client, 'fixture-doc', 't.0', folder)
        (folder / 'document.md').write_text('tampered')
        with self.assertRaises(ValueError):
            gw.formatted_snapshot(folder, obs, text)

    def test_snapshot_invalid_word_returns_bounded_error(self):
        folder = self.root / 'snapshot'
        rt.capture(self.client, 'fixture-doc', 't.0', folder)
        meta = json.loads((folder / 'snapshot.json').read_text())
        (folder / 'document.docx').write_bytes(b'not word')
        meta['files']['document.docx'] = gd.digest(b'not word')
        (folder / 'snapshot.json').write_text(json.dumps(meta))
        obs = json.loads((folder / 'observation.json').read_text())
        with self.assertRaises(ValueError):
            gw.formatted_snapshot(folder, obs, (folder / 'document.md').read_text())

    def test_capture_rejects_other_tabs_suggestions_and_revision_races(self):
        original = copy.deepcopy(self.client.doc)
        self.client.doc['tabs'].append(copy.deepcopy(self.client.doc['tabs'][0]))
        with self.assertRaises(gd.GoogleError):
            rt.capture(self.client, 'fixture-doc', 't.0', self.root / 'a')
        self.client.doc = copy.deepcopy(original)
        self.client.doc['suggestedDocumentStyleChanges'] = {'s': {}}
        with self.assertRaises(gd.GoogleError):
            rt.capture(self.client, 'fixture-doc', 't.0', self.root / 'b')
        self.client.doc = original
        self.client.metadata = Mock(side_effect=[{'version': '1'}, {'version': '2'}])
        with self.assertRaises(gd.GoogleError):
            rt.capture(self.client, 'fixture-doc', 't.0', self.root / 'c')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_multi_paragraph_unicode_patch_preserves_heading_spacing_and_link(self):
        original = rt.semantic(self.client.doc)
        plan = rt.build_plan(self.client.doc, self.edits())
        result = rt.apply(self.client, plan, self.root / 'receipt.json')
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(self.client.writes, 1)
        before = original['tabs'][0]['documentTab']['body']['content']
        after = rt.semantic(self.client.doc)['tabs'][0]['documentTab']['body']['content']
        for a, b in zip(before[1:], after[1:], strict=False):
            self.assertEqual(a['paragraph']['paragraphStyle'], b['paragraph']['paragraphStyle'])
        self.assertEqual(before[-1], after[-1])
        self.assertTrue(
            all(
                e['style'].get('fontSize', {}).get('magnitude') == 22
                for e in after[1]['paragraph']['elements']
            )
        )
        self.assertEqual(rt.verify(self.client, plan)['status'], 'verified')
        with self.assertRaises(gd.GoogleError):
            rt.apply(self.client, plan, self.root / 'receipt2.json')
        self.assertEqual(self.client.writes, 1)

    def test_stale_tampered_or_repeated_plan_cannot_write(self):
        plan = rt.build_plan(self.client.doc, self.edits())
        tampered = copy.deepcopy(plan)
        tampered['requests'].append({'deleteContentRange': {}})
        with self.assertRaises(gd.GoogleError):
            rt.apply(self.client, tampered, self.root / 'r')
        self.assertEqual(self.client.writes, 0)

        def uncertain(*args):
            raise gd.GoogleError('timeout')

        self.client.native_update = Mock(side_effect=uncertain)
        with self.assertRaises(gd.GoogleError):
            rt.apply(self.client, plan, self.root / 'r')
        with self.assertRaises(FileExistsError):
            rt.apply(self.client, plan, self.root / 'r')
        self.assertEqual(self.client.native_update.call_count, 1)

    def test_readback_style_drift_is_unverified(self):
        plan = rt.build_plan(self.client.doc, self.edits())
        rt.apply(self.client, plan, self.root / 'r')
        self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph'][
            'paragraphStyle'
        ]['lineSpacing'] = 250
        self.assertEqual(rt.verify(self.client, plan)['status'], 'written-unverified')

    def test_structural_edits_and_ambiguous_run_replacements_blocked(self):
        edits = self.edits()
        edits[0]['after'] = 'New\nheading'
        with self.assertRaises(gd.GoogleError):
            rt.build_plan(self.client.doc, edits)
        edits = self.edits()
        edits[0]['before'] = 'wrong'
        with self.assertRaises(gd.GoogleError):
            rt.build_plan(self.client.doc, edits)
        paragraph = self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']
        paragraph['elements'] = [
            {
                'startIndex': 1,
                'endIndex': 4,
                'textRun': {'content': 'The', 'textStyle': {'bold': True}},
            },
            {
                'startIndex': 4,
                'endIndex': 26,
                'textRun': {'content': ' delay is in handoffs.\n', 'textStyle': {}},
            },
        ]
        edits = [
            {
                'tab_id': 't.0',
                'start_index': 1,
                'before': 'The delay is in handoffs.',
                'after': 'Replacement',
            }
        ]
        with self.assertRaises(gd.GoogleError):
            rt.build_plan(self.client.doc, edits)

    def restyle(self, runs):
        """Replace the first paragraph with the given (text, style) runs and renumber the document."""
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        blocks[1]['paragraph']['elements'] = [
            {'textRun': {'content': text, 'textStyle': style}} for text, style in runs
        ]
        start = 1
        for block in blocks[1:]:
            block['startIndex'] = start
            for element in block['paragraph']['elements']:
                element['startIndex'] = start
                start += rt.utf16(element['textRun']['content'])
                element['endIndex'] = start
            block['endIndex'] = start

    def inserted(self, runs, before, after):
        self.restyle(runs)
        requests = rt.build_plan(self.client.doc, [{'before': before, 'after': after}])['requests']
        texts = [r['insertText']['text'] for r in requests if 'insertText' in r]
        styles = [r['updateTextStyle']['textStyle'] for r in requests if 'updateTextStyle' in r]
        return list(zip(texts, styles, strict=False))

    def test_inserted_text_takes_the_right_neighbours_style_and_never_lengthens_a_link(self):
        link = {'link': {'url': 'https://example.invalid'}, 'underline': True}
        bold = {'bold': True}
        guide = [('Read ', {}), ('the guide', link), ('\n', {})]
        fast = [('This is ', {}), ('fast', bold), ('.\n', {})]
        # Text added after a link, before a link, or onto a linked word stays outside the link.
        self.assertEqual(
            self.inserted(guide, 'Read the guide', 'Read the guide today'), [(' today', {})]
        )
        self.assertEqual(
            self.inserted(
                [('docs', link), (' are here.\n', {})], 'docs are here.', 'Our docs are here.'
            ),
            [('Our ', {})],
        )
        self.assertEqual(
            self.inserted(
                [('See ', {}), ('docs', link), (' here.\n', {})],
                'See docs here.',
                'See docsets here.',
            ),
            [('ets', {})],
        )
        # Inside a link both neighbours share it, so the link continues.
        self.assertEqual(
            self.inserted(guide, 'Read the guide', 'Read the best guide'), [('best ', link)]
        )
        # A new word before bold text is not bold; a word that grows keeps its own style.
        self.assertEqual(
            self.inserted(fast, 'This is fast.', 'This is very fast.'), [('very ', {})]
        )
        self.assertEqual(self.inserted(fast, 'This is fast.', 'This is faster.'), [('er', bold)])
        self.assertEqual(
            self.inserted([('happy', bold), (' days\n', {})], 'happy days', 'unhappy days'),
            [('un', bold)],
        )
        # Applied and read back: the link still covers exactly "the guide".
        self.restyle(guide)
        plan = rt.build_plan(
            self.client.doc, [{'before': 'Read the guide', 'after': 'Read the guide today'}]
        )
        self.assertEqual(
            rt.apply(self.client, plan, self.root / 'link-receipt.json')['status'], 'verified'
        )
        elements = self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph'][
            'elements'
        ]
        linked = ''.join(
            e['textRun']['content'] for e in elements if e['textRun']['textStyle'].get('link')
        )
        self.assertEqual(linked, 'the guide')
        self.assertEqual(
            json.loads((self.root / 'link-receipt.json').read_text())['status'], 'verified'
        )

    def test_edits_are_located_by_paragraph_text_and_pending_suggestions_block_only_their_paragraph(
        self,
    ):
        plan = rt.build_plan(
            self.client.doc,
            [{'before': 'The delay is in handoffs.', 'after': 'The delay comes from handoffs.'}],
        )
        self.assertEqual((plan['edits'][0]['tab_id'], plan['edits'][0]['start_index']), ('t.0', 1))
        with self.assertRaisesRegex(gd.GoogleError, 'optional tab_id'):
            rt.build_plan(self.client.doc, [{'tab': 't.0', 'before': 'x', 'after': 'y'}])
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        twin = copy.deepcopy(blocks[1])
        twin['startIndex'] = 200
        twin['endIndex'] = 226
        blocks.append(twin)
        with self.assertRaisesRegex(gd.GoogleError, 'appears 2 times'):
            rt.build_plan(
                self.client.doc, [{'before': 'The delay is in handoffs.', 'after': 'Changed.'}]
            )
        blocks.pop()
        # A colleague's pending suggestion sits in the second paragraph.
        blocks[2]['paragraph']['suggestedParagraphStyleChanges'] = {
            'teammate-1': {'paragraphStyle': {'lineSpacing': 200}}
        }
        with self.assertRaisesRegex(gd.GoogleError, 'pending suggestion'):
            rt.build_plan(self.client.doc, [self.edits()[1]])
        self.assertEqual(
            rt.apply(
                self.client, rt.build_plan(self.client.doc, [self.edits()[0]]), self.root / 'r'
            )['status'],
            'verified',
        )
        self.assertIn('teammate-1', json.dumps(self.client.doc))

    def test_definite_refusal_releases_the_patch_receipt(self):
        plan = rt.build_plan(self.client.doc, self.edits())
        self.client.native_update = Mock(
            side_effect=gd.GoogleError('Google rejected the write.', status=400)
        )
        with self.assertRaises(gd.GoogleError):
            rt.apply(self.client, plan, self.root / 'r')
        self.assertFalse((self.root / 'r').exists())

    def cli(self, *words):
        with patch.object(rt, 'Client', return_value=self.client):
            return rt.run(rt.build_parser().parse_args([str(word) for word in words]))

    def test_cli_stages_files_in_the_workspace_and_writes_only_to_linked_docs(self):
        work = self.root / 'work'
        studio.initialize(work)
        captured = self.cli('--root', work, 'capture', '--file-id', 'fixture-doc')
        folder = Path(captured['directory'])
        self.assertEqual(folder.parent, (work / '.google-staging').resolve())
        self.assertEqual(captured['summary']['structure']['headings'], 1)
        self.assertEqual(captured['summary']['projection'], rt.PROJECTION)
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        with self.assertRaisesRegex(gd.GoogleError, '--root'):
            self.cli('capture', '--file-id', 'fixture-doc')
        edits = self.root / 'edits.json'
        edits.write_text(json.dumps([self.edits()[0]]))
        # Wording patches are writes: without a linked Doc they are refused before anything is read.
        self.client.native_read = Mock(wraps=self.client.native_read)
        with self.assertRaisesRegex(gd.GoogleError, 'limited to Google Docs linked'):
            self.cli('plan', '--file-id', 'fixture-doc', '--edits', edits)
        with self.assertRaisesRegex(gd.GoogleError, 'not linked to a blog'):
            self.cli('--root', work, 'plan', '--file-id', 'fixture-doc', '--edits', edits)
        self.client.native_read.assert_not_called()
        planned = self.cli(
            '--root', work, 'plan', '--file-id', 'fixture-doc', '--edits', edits, '--first-handoff'
        )
        self.assertTrue(gd.staged(work, planned['file']))
        with self.assertRaisesRegex(gd.GoogleError, 'not linked to a blog'):
            self.cli('--root', work, 'apply', '--plan', planned['file'])
        self.assertEqual(self.client.writes, 0)
        # Once a blog in this workspace is linked to the Doc, the same commands need no extra flag.
        args = studio.parser().parse_args(
            ['--root', str(work), 'article', 'create', '--title', 'Linked', '--mode', 'existing']
        )
        with studio.locked(work):
            aid = studio.article_command(work, args)['id']
        directory, record = studio.item(work, 'articles', aid)
        record['google'] = {
            'schema': 1,
            'transfers': {},
            'receipts': [],
            'baselines': {
                'draft': {
                    'transfer': 'a' * 32,
                    'local_sha256': 'b' * 64,
                    'document': {'document_id': 'fixture-doc', 'tab_ids': ['t.0']},
                }
            },
        }
        studio.persist(directory, 'articles', record)
        self.assertEqual(gd.linked_documents(work), {'fixture-doc'})
        kept_plan = self.root / 'kept-plan.json'
        kept_plan.write_bytes(Path(planned['file']).read_bytes())
        unchanged = copy.deepcopy(self.client.doc)
        self.assertEqual(
            self.cli('--root', work, 'apply', '--plan', planned['file'])['status'], 'verified'
        )
        self.assertEqual(self.client.writes, 1)
        # The staged plan is cleared; its receipt stays, and the same plan can never be applied twice.
        self.assertFalse(Path(planned['file']).exists())
        receipts = list((work / '.google-staging').glob('patch-receipt-*.json'))
        self.assertEqual(
            [json.loads(receipt.read_text())['status'] for receipt in receipts], ['verified']
        )
        self.client.doc = (
            unchanged  # Even if Google looked exactly as planned again, the receipt stops a repeat.
        )
        with self.assertRaisesRegex(gd.GoogleError, 'already has a receipt'):
            self.cli('--root', work, 'apply', '--plan', kept_plan)
        self.assertEqual(self.client.writes, 1)


if __name__ == '__main__':
    unittest.main()
