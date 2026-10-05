"""Blog-folder migration preserves revision bytes, queued saves and selected scope."""
import json
import posixpath
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hub import Registry
from hub_fixtures import FakeProvider
import hub_store as store
from hub_browse import render, verify, changes


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.provider = FakeProvider(self.base / 'remote')
        self.a = Registry(self.base / 'a', self.provider)
        self.ident = self.a.create('fixture/layout', 'Layout fixture')['hub']
        self.ha = self.a.hub(self.ident)
        self.b = Registry(self.base / 'b', self.provider)
        self.b.join('fixture/layout');self.hb = self.b.hub(self.ident)
        self.remote = self.provider.transport({'repository': 'fixture/layout'})

    def files(self):
        return store.tree_files(self.remote, store.git(self.remote, 'rev-parse', 'main').decode().strip())

    def publish(self, additions):
        base = store.git(self.remote, 'rev-parse', 'main').decode().strip()
        commit = store.commit_files(self.remote, base, additions, 'Legacy fixture', 'Fixture')
        store.git(self.remote, 'update-ref', 'refs/heads/main', commit)

    def legacy(self):
        files = self.files()
        manifest = json.loads(files['hub.json'])
        manifest.pop('storage_schema');manifest.pop('history_schema', None);manifest['browse_schema'] = 1
        manifest['minimum_runtime'] = '1.12.2'
        kept = {'hub.json': store.encoded(manifest), 'README.md': b'# Custom hub introduction\n'}
        kept.update(render(kept, store.validate_files(kept)))
        self.publish({**{k: None for k in files if store.generated_path(k)}, **kept})
        self.ha.refresh();self.hb.refresh()

    def save_legacy_article(self):
        saved = self.ha.save('article', 'Columnar filters', 'Old draft', sync=False,
            data={'studio': {'author': 'Dan', 'stage': 'review', 'reviews': {
                'proofread': {'status': 'current', 'result': {'coverage': 'Entire draft',
                    'findings': [{'original': 'old text', 'replacement': 'new text', 'status': 'applied'}]}}}}},
            artifacts={'ORIGINAL.md': (b'Original manuscript', 'text'),
                       'DRAFT.md': (b'Old draft', 'text'),
                       'history/imported.docx': (b'PK\x00original snapshot', 'binary')})
        additions = self.ha._intent_files(self.ha._intents()[-1])
        files = {**self.files(), **additions}
        additions.update(render(files, store.validate_files(files)))
        self.publish(additions);self.ha.refresh();self.hb.refresh()
        return saved

    def test_legacy_migration_is_byte_preserving_readable_and_idempotent(self):
        self.legacy();saved = self.save_legacy_article()
        before = self.files();old_graph = store.validate_files(before)
        result = self.ha.sync();self.assertEqual(result['status'], 'shared')
        after = self.files();graph = store.validate_files(after);verify(after, graph)
        self.assertEqual(store.immutable_files(before, old_graph), store.immutable_files(after, graph))
        self.assertFalse(any(k.startswith('memory/items/') for k in after))
        folder = 'blogs/dan/columnar-filters/'
        self.assertEqual(after[folder + 'original.md'], b'Original manuscript')
        self.assertEqual(after[folder + 'draft.md'], b'Old draft')
        self.assertEqual(after[folder + 'history/files/imported.docx'], b'PK\x00original snapshot')
        self.assertIn(b'old text', after[folder + 'reviews/proofread.md'])
        self.assertIn(b'new text', after[folder + 'reviews/proofread.md'])
        self.assertIn(b'Entire draft', after[folder + 'reviews/proofread.md'])
        self.assertEqual(Path(self.hb.read(saved['item'])['paths']['BODY.md']).read_bytes(), b'Old draft')
        self.hb.refresh()
        self.assertEqual(Path(self.hb.read(saved['item'])['paths']['BODY.md']).read_bytes(), b'Old draft')
        self.assertIn(b'Custom hub introduction', after['README.md'])
        self.assertEqual(self.ha.sync()['revision'], result['revision'])
        self.assertEqual(changes(after, graph), {})
        with patch.object(store, 'VERSION', '1.12.2'):
            with self.assertRaisesRegex(store.HubError, 'newer'):store.validate_files(after)
        for name, body in after.items():
            if not store.generated_path(name) or not name.endswith('.md'):continue
            for target in re.findall(r'\]\(([^)]+)\)', body.decode()):
                if '://' not in target:
                    self.assertIn(posixpath.normpath(posixpath.join(posixpath.dirname(name), target)), after)

    def test_old_outbox_survives_other_writer_migrating_and_retrying(self):
        self.legacy();saved = self.save_legacy_article()
        queued = self.hb.save('article', 'Columnar filters', 'Queued revision', item=saved['item'], offline=True)
        intent = next(i for i in self.hb._intents() if i['operation'] == queued['operation'])
        original_hash = intent['payload_hash']
        self.ha.sync();self.hb.refresh()
        self.assertEqual(self.hb.find('Queued revision')['total'], 1)
        synced = self.hb.sync();self.assertEqual(synced['queued'], 0)
        self.assertEqual(Path(self.hb.read(saved['item'])['paths']['BODY.md']).read_text(), 'Queued revision')
        self.assertEqual(len(self.hb.graph()['revisions']), 2)
        self.assertEqual(next(i for i in self.hb._intents() if i['operation'] == queued['operation'])['payload_hash'], original_hash)
        retry = self.hb.save('article', 'Columnar filters', 'Queued revision', item=saved['item'], operation=queued['operation'])
        self.assertEqual(retry['revision'], queued['revision'])

    def test_sources_and_memory_are_scoped_and_views_cannot_be_overwritten(self):
        source = self.ha.save('source', 'Selected benchmark', 'Selected evidence')
        self.ha.save('source', 'Other source', 'Unrelated evidence')
        rule = self.ha.save('rule', 'Team punctuation', 'Use consistent punctuation')
        self.ha.save('note', 'Only this blog', 'Article-only context', scope={'level': 'article', 'key': 'blog'})
        self.ha.save('article', 'Filters', 'Draft', data={'studio': {'author': 'Dan'}},
            dependencies=[{'item': source['item'], 'revision': source['revision'], 'kind': 'source', 'role': 'source'}])
        files = self.files()
        blogs = b'\n'.join(v for k, v in files.items() if k.startswith('blogs/'))
        memory = b'\n'.join(v for k, v in files.items() if k.startswith('memory/'))
        self.assertIn(b'Selected evidence', blogs);self.assertNotIn(b'Unrelated evidence', blogs)
        self.assertIn(b'Use consistent punctuation', memory)
        self.assertNotIn(b'Article-only context', memory)
        self.assertNotIn(b'Selected evidence', memory)
        source_path = next(k for k in files if '/sources/selected-benchmark-' in k)
        self.publish({source_path: b'Manual source view change'})
        with self.assertRaisesRegex(store.HubError, 'edited'):
            self.ha.save('note', 'New note', 'Keep queued work')
        self.assertEqual(self.ha.status()['queued'], 1)

    def test_large_binary_snapshot_and_relocation_deletion_guard(self):
        binary = b'\x00' * (store.MAX_TEXT + 1)
        saved = self.ha.save('article', 'Snapshots', 'Draft', artifacts={'history/import.docx': (binary, 'binary')})
        files = self.files()
        self.assertEqual(files['blogs/unassigned/snapshots/history/files/import.docx'], binary)
        path = store.record_path(self.ha.graph()['revisions'][saved['revision']], 'BODY.md')
        with self.assertRaisesRegex(store.HubError, 'Only generated'):
            store.commit_files(self.remote, self.ha._state()['revision'], {path: None}, 'Bad deletion', 'Fixture')


if __name__ == '__main__':unittest.main()
