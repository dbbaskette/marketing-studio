"""Visual historical imports use real discovery/checkpoints in disposable workspaces."""
import base64
import json
from unittest.mock import patch
from test_editorial_tools import Fixture
import blog_library as library
import management


class ManagementImportTests(Fixture):
    def payload(self, posts=2, operation='a' * 32):
        return {'operation': operation, 'name': 'Engineering history', 'type': 'export',
                'export': base64.b64encode(json.dumps([{'external_id': str(n), 'title': 'Post ' + str(n),
                    'text': 'A retained technical example.'} for n in range(posts)]).encode()).decode()}

    def save(self, preview, operation='b' * 32, retry=False, selected=None):
        return management.dispatch(self.root, 'library-import', {'operation': operation, 'preview': preview['preview'],
            'expected': preview['expected'], 'confirm': True, 'retry': retry,
            'selected': selected if selected is not None else [p['key'] for p in preview['posts']]})

    def test_export_preview_import_batches_and_safe_replay(self):
        preview = management.dispatch(self.root, 'library-preview', self.payload(26))
        self.assertEqual(preview['candidates'], 26)
        self.assertEqual(library.catalog(self.root)['total'], 0)
        self.assertEqual(management.dispatch(self.root, 'library-preview', self.payload(26))['preview'], preview['preview'])
        first = self.save(preview)
        self.assertEqual(first['counts']['imported'], 25)
        self.assertEqual(first['remaining'], 1)
        self.assertEqual(self.save(preview), first)  # A repeated POST does not import the next batch.
        with self.assertRaisesRegex(ValueError, 'preview changed'):
            self.save(preview, 'c' * 32)
        latest = management.library_preview_state(self.root, preview['preview'])
        finished = self.save(latest, 'd' * 32)
        self.assertEqual(finished['remaining'], 0)
        self.assertEqual(library.catalog(self.root)['total'], 26)
        self.assertEqual(list((self.root / 'articles').iterdir()), [])
        self.assertNotIn(str(self.root), json.dumps(finished))

    def test_folder_picker_keeps_originals_pending_pdf_and_refresh_identity(self):
        files = [{'path': 'Posts/nested/one.md', 'content': base64.b64encode(b'# First\n\nRetained text.').decode()},
                 {'path': 'Posts/two.pdf', 'content': base64.b64encode(b'%PDF fixture').decode()}]
        preview = management.dispatch(self.root, 'library-preview', {'operation':'a'*32, 'name':'Past blogs', 'type':'folder', 'files':files})
        result = self.save(preview)
        self.assertEqual(result['counts']['pending_extraction'], 1)
        rows = library.catalog(self.root)['items']
        self.assertTrue(all(row['historical'] for row in rows))
        key = next(iter(library.collections(self.root)))
        refreshed = management.dispatch(self.root, 'library-preview', {'operation':'c'*32, 'collection':key})
        again = self.save(refreshed, 'd'*32)
        self.assertEqual(again['counts']['unchanged'], 2)
        self.assertEqual(library.catalog(self.root)['total'], 2)
        for row in rows:
            directory, record = __import__('studio').item(self.root, 'sources', row['id'])
            self.assertEqual((directory / record['original_path']).read_bytes(), b'%PDF fixture' if record['status']=='pending' else b'# First\n\nRetained text.')

    def test_web_preview_scope_and_explicit_post_fetch(self):
        archive = b'<a href="/blog/first">Post</a><a href="https://outside.example/post">Other</a>'
        calls=[]
        def fetch(url, scope):
            calls.append((url, scope))
            return (archive if url.endswith('/archive') else b'<h1>First</h1><p>Source text.</p>', url, 'text/html')
        with patch.object(library, 'fetch', side_effect=fetch):
            preview=management.dispatch(self.root, 'library-preview', {'operation':'a'*32,'name':'Web posts','type':'archive',
                'url':'https://team.example/archive','scope':'https://team.example/blog','discovery_scope':'https://team.example/archive'})
            self.assertEqual(calls, [('https://team.example/archive','https://team.example/archive')])
            self.assertIn('Other archive pages have not been followed', preview['coverage_note'])
            self.assertEqual(preview['candidates'],1)
            self.assertEqual(len(preview['excluded']),1)
            self.save(preview)
            self.assertEqual(calls[-1], ('https://team.example/blog/first','https://team.example/blog'))

    def test_staging_boundary_invalid_source_and_permission(self):
        for name in ('../escape.md','/escape.md','Posts/.hidden.md','Posts/one.md/../../escape.md','Posts\\escape.md','Posts/other.exe'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                management.dispatch(self.root,'library-preview',{'operation':'a'*32,'name':'Bad','type':'folder',
                    'files':[{'path':name,'content':base64.b64encode(b'text').decode()}]})
        with self.assertRaises(ValueError):
            management.dispatch(self.root,'library-preview', {'operation':'a'*32,'name':'Bad','type':'export','export':base64.b64encode(b'{}').decode()})
        with patch.object(management,'authorize_write',side_effect=ValueError('Read-only access')):
            with self.assertRaisesRegex(ValueError,'Read-only'):
                management.dispatch(self.root,'library-preview',self.payload(operation='f'*32))
        self.assertEqual(library.catalog(self.root)['total'],0)
        with self.assertRaisesRegex(ValueError,'different import'):
            management.dispatch(self.root,'library-preview', self.payload(operation='a'*32))

    def test_partial_failure_requires_reloading_checkpoint(self):
        preview=management.dispatch(self.root,'library-preview',self.payload())
        real_import=library.import_batch
        def interrupted(root, ident, **kwargs):
            real_import(root,ident,limit=1,delay=0)
            raise OSError('Interrupted after retained post')
        with patch.object(library,'import_batch',side_effect=interrupted), self.assertRaises(OSError):self.save(preview)
        with self.assertRaisesRegex(ValueError,'preview changed'):self.save(preview)
        result=self.save(management.library_preview_state(self.root,preview['preview']),'c'*32)
        self.assertEqual(result['counts']['imported'],2)
        self.assertEqual(library.catalog(self.root)['total'],2)

    def test_only_checked_posts_import_and_all_candidates_are_visible(self):
        preview=management.dispatch(self.root,'library-preview',self.payload(29))
        self.assertEqual(len(preview['posts']),29)
        self.assertEqual(preview['selected'],[])
        chosen=[preview['posts'][i]['key'] for i in (1,21,28)]
        result=self.save(preview,selected=chosen)
        self.assertEqual(result['counts']['imported'],3)
        self.assertEqual(result['remaining'],26)
        self.assertEqual({r['title'] for r in library.catalog(self.root)['items']},{'Post 1','Post 21','Post 28'})
        self.assertEqual(result['selected'],chosen)
        for selection in ([],['unknown'],[preview['posts'][0]['key']]*2):
            with self.subTest(selection=selection),self.assertRaises(ValueError):
                self.save(result,operation='c'*32,selected=selection)
        self.assertEqual(library.catalog(self.root)['total'],3)

    def test_unchecked_author_and_category_links_are_never_fetched(self):
        calls=[]
        archive=b'<a href="/blog/post"><b>Useful post</b></a><a href="/blog/author/sam">Sam</a><a href="/blog/category/news">News</a>'
        def fetch(url,scope):
            calls.append(url)
            return (archive if url.endswith('/blog') else b'<title>Useful post title</title><p>Text</p>',url,'text/html')
        with patch.object(library,'fetch',side_effect=fetch):
            preview=management.dispatch(self.root,'library-preview',{'operation':'a'*32,'name':'Archive','type':'archive',
                'url':'https://team.example/blog','scope':'https://team.example/blog'})
            self.assertEqual([p['title'] for p in preview['posts']],['Useful post','Sam','News'])
            self.save(preview,selected=[preview['posts'][0]['key']])
        self.assertEqual(calls,['https://team.example/blog','https://team.example/blog/post'])
        self.assertEqual(library.catalog(self.root)['items'][0]['title'],'Useful post title')

    def test_retry_only_selected_failure_and_preserves_unchecked_posts(self):
        preview=management.dispatch(self.root,'library-preview',{'operation':'a'*32,'name':'Links','type':'urls',
            'url':'https://team.example/blog/a\nhttps://team.example/blog/b\nhttps://team.example/blog/c','scope':'https://team.example/blog'})
        keys=[p['key'] for p in preview['posts']]
        def broken(url,scope):raise OSError('Temporary fetch failure')
        with patch.object(library,'fetch',side_effect=broken):result=self.save(preview,selected=keys[:2])
        self.assertEqual(result['counts']['failed'],2)
        calls=[]
        def recovered(url,scope):
            calls.append(url);return b'<title>Recovered</title>',url,'text/html'
        with patch.object(library,'fetch',side_effect=recovered):
            result=self.save(result,'c'*32,retry=True,selected=keys[:1])
        self.assertEqual(calls,['https://team.example/blog/a'])
        self.assertEqual(result['counts']['imported'],1)
        self.assertEqual(result['counts']['failed'],1)
        self.assertEqual(result['remaining'],1)
