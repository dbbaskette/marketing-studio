import base64
import json
from pathlib import Path
import tempfile
import unittest
import marketing_studio  # noqa: F401
from studio_core import google_reference
from studio_core.research_sources import Sources

class SourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.network = []
        def fetch(url):
            self.network.append(url)
            return {'raw': b'Captured synthetic source text.', 'mime': 'text/plain', 'url': url}
        self.sources = Sources(self.root, fetch=fetch)
        self.value = self.sources.create()
    def act(self, operation, **data):
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], operation, **data)
        return self.value
    def test_text_url_and_file_share_the_same_selected_start_boundary(self):
        self.act('capture', kind='text', name='Notes', text='Synthetic supplied notes.')
        self.act('capture', kind='url', url='https://example.invalid/reference')
        self.act('capture', kind='file', name='notes.md', content=base64.b64encode(b'Synthetic file.').decode())
        self.assertEqual(len(self.value['sources']), 3)
        ready = self.sources.prepared(self.value['id'], self.value['revision'])
        self.assertEqual(ready['research_from'], {'documents': True, 'sites': [], 'web': False})
        self.assertTrue(all(s['permission'] == 'selected' for s in ready['sources']))
        self.assertEqual(self.network, ['https://example.invalid/reference'])
        self.assertEqual(ready['workers'], 3)
    def test_bad_source_does_not_erase_ready_peers_or_silently_enter_research(self):
        self.act('capture', kind='text', name='Readable', text='Useful synthetic notes.')
        self.act('capture', kind='file', name='unsupported.exe', content='AA==')
        self.assertEqual([s['status'] for s in self.value['sources']], ['ready', 'needs-attention'])
        with self.assertRaisesRegex(ValueError, 'exclude unreadable'): self.sources.prepared(self.value['id'], self.value['revision'])
        self.act('exclude', source=self.value['sources'][-1]['id'])
        self.assertEqual(len(self.sources.prepared(self.value['id'], self.value['revision'])['sources']), 1)
    def test_stale_revision_cannot_overwrite_another_view(self):
        before = self.value['revision']
        self.act('configure', external=True, workers=2)
        with self.assertRaisesRegex(ValueError, 'another view'):
            self.sources.mutate(self.value['id'], before, 'configure', external=False)
        self.assertTrue(self.sources.read(self.value['id'])['external'])
    def test_source_bytes_are_verified_at_preview_and_start(self):
        self.act('capture', kind='text', name='Notes', text='Synthetic notes.')
        private = self.sources.load(self.value['id'])['sources'][0]
        (self.sources.folder(self.value['id']) / private['file']).write_text('Changed outside the recorded capture')
        with self.assertRaisesRegex(ValueError, 'capture changed'): self.sources.preview(self.value['id'], private['id'])
        with self.assertRaisesRegex(ValueError, 'source changed'): self.sources.prepared(self.value['id'], self.value['revision'])
    def test_empty_sources_need_an_explicit_external_choice(self):
        with self.assertRaisesRegex(ValueError, 'allow additional'): self.sources.prepared(self.value['id'], self.value['revision'])
        self.act('configure', external=True)
        self.assertTrue(self.sources.prepared(self.value['id'], self.value['revision'])['research_from']['web'])
    def test_google_tab_link_preserves_only_selected_content_and_no_account_form(self):
        native = {'documentId': 'fictional', 'tabs': [
            {'tabProperties': {'tabId': ident, 'title': title}, 'documentTab': {'body': {'content': [
                {'paragraph': {'elements': [{'textRun': {'content': text}}]}}]}}}
            for ident, title, text in [('t.first', 'Overview', 'DO NOT RETAIN UNSELECTED BODY'), ('t.second', 'Main reference', 'Selected synthetic body.')]]}
        class Client:
            def file(self, ident): return {'id': ident, 'mimeType': google_reference.DOC_MIME, 'name': 'Reference', 'version': '1', 'modifiedTime': '2026-01-01', 'capabilities': {'canDownload': True}}
            def document(self, ident): return native
        result = google_reference.capture('https://docs.google.com/document/d/fictional/edit?tab=t.second', client=Client())
        self.assertNotIn(b'DO NOT RETAIN', result['raw'])
        self.assertNotIn('DO NOT RETAIN', result['extracted']['text'])
        self.assertEqual(result['selected_tabs'], ['t.second'])
        self.assertEqual([t['title'] for t in result['tabs']], ['Overview', 'Main reference'])
        all_tabs = google_reference.capture('https://docs.google.com/document/d/fictional/edit', client=Client())
        self.assertEqual(len(all_tabs['selected_tabs']), 2)
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            google_reference.capture('https://docs.google.com/document/d/fictional/edit?tab=t.missing', client=Client())

    def test_retry_replaces_the_failed_row_and_retains_valid_peers(self):
        self.act('capture', kind='text', text='Synthetic valid reference.')
        self.sources.fetch = lambda url: (_ for _ in ()).throw(ValueError('Synthetic read failure'))
        self.act('capture',kind='url',url='https://example.invalid/retry')
        failed=self.value['sources'][-1]['id']
        self.sources.fetch=lambda url:{'url':url,'raw':b'Recovered synthetic context.','mime':'text/plain'}
        self.act('capture',kind='url',source=failed,url='https://example.invalid/retry')
        self.assertEqual(len(self.value['sources']),2)
        self.assertTrue(all(s['status']=='ready' for s in self.value['sources']))

    def test_native_primary_allows_empty_reference_draft_without_enabling_search(self):
        value=self.sources.prepared(self.value['id'],self.value['revision'],primary=True)
        self.assertEqual(value['research_from'],{'documents':True,'sites':[],'web':False})
