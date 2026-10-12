"""Visual historical imports use real discovery/checkpoints in disposable workspaces."""
import base64
import json
from unittest.mock import patch
from test_editorial_tools import Fixture
import blog_library as library
import management
import studio


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

    # --- Collections become real on the first confirmed import ---

    def archive(self, name, operation, url='https://team.example/blog'):
        return {'operation': operation, 'name': name, 'type': 'archive', 'url': url, 'scope': 'https://team.example/blog'}

    def test_failed_or_abandoned_preview_leaves_no_collection_and_the_name_stays_free(self):
        def unreachable(url, scope):raise ValueError(library.UNREACHABLE)
        with patch.object(library, 'fetch', side_effect=unreachable):
            with self.assertRaisesRegex(ValueError, 'could not be reached'):
                management.dispatch(self.root, 'library-preview', self.archive('Engineering blog', 'a' * 32, 'https://team.example/blog/typo'))
        self.assertEqual(library.collections(self.root), {})
        self.assertEqual(management.collection_rows(self.root)['items'], [])
        # The corrected request reuses the name: nothing was registered by the failed one.
        page = b'<a href="/blog/first">First post</a>'
        with patch.object(library, 'fetch', side_effect=lambda url, scope:(page if url.endswith('/blog') else b'<h1>First</h1><p>Text.</p>', url, 'text/html')):
            preview = management.dispatch(self.root, 'library-preview', self.archive('Engineering blog', 'b' * 32))
            self.assertFalse(preview['saved_collection']);self.assertEqual(preview['collection'], 'Engineering blog')
            # Discovery alone still registers and shares nothing; an abandoned preview is not a collection.
            self.assertEqual(library.collections(self.root), {})
            again = management.dispatch(self.root, 'library-preview', self.archive('Engineering blog', 'c' * 32))
            self.assertEqual(again['candidates'], 1)
            # The first confirmed import is what saves the collection.
            result = self.save(again, 'd' * 32)
        self.assertEqual(result['counts']['imported'], 1);self.assertTrue(result['saved_collection'])
        saved = library.collections(self.root)
        self.assertEqual([c['name'] for c in saved.values()], ['Engineering blog'])
        self.assertEqual(library.imported_count(self.root, next(iter(saved))), 1)
        # A name whose collection holds saved posts is taken; the abandoned preview cannot claim it later.
        with self.assertRaisesRegex(ValueError, 'already has that name'):
            management.dispatch(self.root, 'library-preview', self.archive('engineering BLOG', 'e' * 32))
        with patch.object(library, 'fetch', side_effect=lambda url, scope:(b'<h1>First</h1>', url, 'text/html')):
            with self.assertRaisesRegex(ValueError, 'already named'):self.save(preview, 'f' * 32)
        self.assertEqual(len(library.collections(self.root)), 1)

    def test_empty_collection_name_is_reused_in_place(self):
        export = self.base / 'ghost.json';export.write_text('[]')
        library.setup(self.root, {'key': 'ghost', 'name': 'Old posts', 'type': 'export', 'path': str(export)})
        self.assertEqual(library.imported_count(self.root, 'ghost'), 0)
        preview = management.dispatch(self.root, 'library-preview', dict(self.payload(2), name='Old posts'))
        self.assertFalse(preview['saved_collection'])
        self.assertEqual(library.collections(self.root)['ghost']['local_path'], str(export.resolve()))  # Untouched until an import.
        result = self.save(preview)
        self.assertEqual(result['counts']['imported'], 2)
        saved = library.collections(self.root)
        self.assertEqual(list(saved), ['ghost']);self.assertNotEqual(saved['ghost']['local_path'], str(export.resolve()))
        self.assertEqual(library.imported_count(self.root, 'ghost'), 2)

    # --- Refreshing a desk-chosen folder, and never duplicating a post ---

    def files(self, **texts):
        return [{'path': path, 'content': base64.b64encode(text.encode()).decode()} for path, text in texts.items()]

    def test_refresh_takes_a_new_selection_under_the_same_collection(self):
        first = self.files(**{'Posts/one.md': '# First\n\nRetained text one.', 'Posts/two.md': '# Second\n\nRetained text two.'})
        preview = management.dispatch(self.root, 'library-preview', {'operation': 'a' * 32, 'name': 'Past blogs', 'type': 'folder', 'files': first})
        self.assertEqual(self.save(preview)['counts']['imported'], 2)
        key = next(iter(library.collections(self.root)))
        row = management.collection_rows(self.root)['items'][0]
        self.assertTrue(row['refresh_files']);self.assertNotIn('local_path', row)
        staged = self.root / '.library' / 'desk-inputs'
        self.assertEqual([p.name for p in staged.iterdir()], ['a' * 32])
        # The same folder chosen again with one new and one edited post.
        newer = self.files(**{'Posts/one.md': '# First\n\nRetained text one.', 'Posts/two.md': '# Second\n\nEdited text two.',
                              'Posts/three.md': '# Third\n\nA new post.'})
        refreshed = management.dispatch(self.root, 'library-preview', {'operation': 'c' * 32, 'collection': key, 'files': newer})
        self.assertEqual(refreshed['candidates'], 3);self.assertTrue(refreshed['saved_collection'])
        result = self.save(refreshed, 'd' * 32)
        self.assertEqual((result['counts']['imported'], result['counts']['updated'], result['counts']['unchanged']), (1, 1, 1))
        self.assertEqual(library.catalog(self.root)['total'], 3)
        self.assertEqual([p.name for p in staged.iterdir()], ['c' * 32])  # The superseded copy is gone.
        self.assertEqual(list(library.collections(self.root)), [key])
        # Without a new selection, refresh re-checks the files chosen last.
        again = management.dispatch(self.root, 'library-preview', {'operation': 'e' * 32, 'collection': key})
        self.assertEqual(self.save(again, 'f' * 32)['counts']['unchanged'], 3)
        # A wrong kind of selection, or a collection that reads a real folder, is refused before anything is staged.
        with self.assertRaisesRegex(ValueError, 'folder for a folder collection'):
            management.dispatch(self.root, 'library-preview', {'operation': '1' * 32, 'collection': key, 'export': base64.b64encode(b'[]').decode()})
        folder = self.base / 'real-folder';folder.mkdir();(folder / 'post.md').write_text('A post read in place.')
        library.setup(self.root, {'key': 'in-place', 'name': 'In place', 'type': 'folder', 'path': str(folder)})
        self.assertFalse(next(r for r in management.collection_rows(self.root)['items'] if r['key'] == 'in-place')['refresh_files'])
        with self.assertRaisesRegex(ValueError, 'reads a folder on this computer directly'):
            management.dispatch(self.root, 'library-preview', {'operation': '2' * 32, 'collection': 'in-place', 'files': first})
        self.assertEqual(library.collections(self.root)['in-place']['local_path'], str(folder.resolve()))
        self.assertEqual([p.name for p in staged.iterdir()], ['c' * 32])

    def test_the_same_file_under_another_folder_or_collection_is_one_post(self):
        first = self.files(**{'Posts/one.md': '# First\n\nRetained text one.', 'Posts/two.md': '# Second\n\nRetained text two.'})
        preview = management.dispatch(self.root, 'library-preview', {'operation': 'a' * 32, 'name': 'Past blogs', 'type': 'folder', 'files': first})
        self.save(preview)
        before = {row['id'] for row in library.catalog(self.root)['items']}
        # The same two files under a renamed top folder and a new collection name, plus one new post.
        moved = self.files(**{'Archive/one.md': '# First\n\nRetained text one.', 'Archive/nested/two.md': '# Second\n\nRetained text two.',
                              'Archive/three.md': '# Third\n\nA new post.'})
        other = management.dispatch(self.root, 'library-preview', {'operation': 'c' * 32, 'name': 'Past blogs again', 'type': 'folder', 'files': moved})
        result = self.save(other, 'd' * 32)
        self.assertEqual((result['counts']['imported'], result['counts']['updated'], result['counts']['failed']), (1, 2, 0))
        rows = library.catalog(self.root)['items']
        self.assertEqual(len(rows), 3);self.assertTrue(before <= {row['id'] for row in rows})
        self.assertEqual(sorted(row['title'] for row in rows), ['one', 'three', 'two'])
        shared = [row for row in rows if row['id'] in before]
        self.assertTrue(all(len(row['library']['collections']) == 2 for row in shared))  # One post, two collections.
        for row in shared:
            directory, record = studio.item(self.root, 'sources', row['id'])
            self.assertEqual(record['revision'], 2);self.assertTrue((directory / 'revisions' / '1' / 'record.json').is_file())
        # Importing either collection again changes nothing.
        key = next(k for k, c in library.collections(self.root).items() if c['name'] == 'Past blogs')
        again = management.dispatch(self.root, 'library-preview', {'operation': 'e' * 32, 'collection': key})
        self.assertEqual(self.save(again, 'f' * 32)['counts']['unchanged'], 2)
        self.assertEqual(library.catalog(self.root)['total'], 3)
        # Explicit identities are never merged by content: two export posts with the same text stay two posts.
        export = [{'external_id': 'x-1', 'title': 'Twin A', 'text': 'Identical text.'}, {'external_id': 'x-2', 'title': 'Twin B', 'text': 'Identical text.'}]
        twins = management.dispatch(self.root, 'library-preview', {'operation': '1' * 32, 'name': 'Twins', 'type': 'export',
                                                                    'export': base64.b64encode(json.dumps(export).encode()).decode()})
        self.assertEqual(self.save(twins, '2' * 32)['counts']['imported'], 2)
