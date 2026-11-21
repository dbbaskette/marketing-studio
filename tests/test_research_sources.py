import base64
import json
from pathlib import Path
import tempfile
import unittest
import unittest.mock
import marketing_studio  # noqa: F401
from studio_core import google_reference, research_sources, source_folders
from studio_core.research_sources import Sources
import pptx_fixture
import xlsx_fixture

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
    def test_a_link_row_carries_the_page_title_and_how_much_text_was_read(self):
        pages = {'https://example.invalid/post': (b'<html><head><title> Rolling &amp;\n restarts </title></head><body><p>Instances restart one at a time.</p></body></html>', 'text/html; charset=utf-8'),
                 'https://example.invalid/files/Field%20guide.pdf': (b'Plain synthetic text.', 'text/plain'),
                 'https://example.invalid/untitled': (b'<html><body><p>No title here.</p></body></html>', 'text/html')}
        self.sources.fetch = lambda url: {'raw': pages[url][0], 'mime': pages[url][1], 'url': url}
        for url in pages:
            self.act('capture', kind='url', url=url)
        shown = {s['origin']: s for s in self.sources.shown(self.sources.load(self.value['id']))['sources']}
        post = shown['https://example.invalid/post']
        self.assertEqual(post['name'], 'Rolling & restarts')
        self.assertEqual(post['characters'], len(self.sources.preview(self.value['id'], post['id'])['text']))
        self.assertIn('Instances restart one at a time.', self.sources.preview(self.value['id'], post['id'])['text'])
        self.assertEqual(shown['https://example.invalid/untitled']['name'], 'https://example.invalid/untitled')
        self.assertEqual(shown['https://example.invalid/files/Field%20guide.pdf']['name'], 'https://example.invalid/files/Field%20guide.pdf')
        from studio_core.research_sources import page_name
        self.assertEqual(page_name(b'%PDF-', 'application/pdf', 'https://example.invalid/files/Field%20guide.pdf'), 'Field guide.pdf')

    def test_one_research_run_reads_a_thousand_links(self):
        from studio_core import research_sources
        self.assertEqual(research_sources.RESEARCH_ENTRIES, 2000)
        links = [{'kind': 'url', 'status': 'ready'}] * 1000
        self.assertIsNone(research_sources.over(links))
        self.assertIn('at most 1,000 links, or 2,000 files', research_sources.over(links + links[:1]))

    @unittest.mock.patch('studio_core.research_sources.RESEARCH_ENTRIES', 200)
    def test_more_than_one_research_run_can_read_is_said_before_start(self):
        for n in range(100):
            self.act('capture', kind='url', url=f'https://example.invalid/page-{n}')
        self.assertIsNone(self.sources.shown(self.sources.load(self.value['id']))['over'])
        self.assertEqual(len(self.sources.prepared(self.value['id'], self.value['revision'])['sources']), 100)
        self.act('capture', kind='url', url='https://example.invalid/one-more')
        said = self.sources.shown(self.sources.load(self.value['id']))['over']
        self.assertIn('at most 100 links', said)
        self.assertIn('You have 101 links, which is 2 over', said)
        with self.assertRaisesRegex(ValueError, 'at most 100 links'):
            self.sources.prepared(self.value['id'], self.value['revision'])
        last = self.value['sources'][-1]['id']
        self.act('exclude', source=last)
        self.assertIsNone(self.sources.shown(self.sources.load(self.value['id']))['over'])
        self.sources.prepared(self.value['id'], self.value['revision'])

    def test_the_ceiling_on_files_and_pasted_texts_fits_inside_one_research_run(self):
        from studio_core import research_sources, source_folders
        self.assertEqual(research_sources.MOST, 400)
        # Each file or pasted text is one research entry, so a full draft still starts.
        self.assertLessEqual(research_sources.MOST, research_sources.RESEARCH_ENTRIES)
        self.assertLessEqual(source_folders.FOLDER_MOST, research_sources.MOST)
        self.assertIsNone(research_sources.over([{'kind': 'file', 'status': 'ready'}] * research_sources.MOST))

    @unittest.mock.patch('studio_core.research_sources.MOST', 40)
    def test_links_are_not_counted_and_files_and_pasted_text_still_are(self):
        for n in range(40):
            self.act('capture', kind='text', name=f'Notes {n}', text=f'Synthetic supplied notes {n}.')
        with self.assertRaisesRegex(ValueError, 'at most 40 files and pasted texts in one request. Links are not counted'):
            self.act('capture', kind='text', name='One more', text='Synthetic supplied notes.')
        for n in range(45):
            self.act('capture', kind='url', url=f'https://example.invalid/reference-{n}')
        self.assertEqual(len(self.value['sources']), 85)
        self.assertEqual(len(self.sources.prepared(self.value['id'], self.value['revision'])['sources']), 85)

    def test_a_draft_made_from_saved_inputs_holds_them_and_changes_none(self):
        # Change settings (#296): the source panel opens on what an item's research reads.
        from studio_core.research_sources import install
        self.act('capture', kind='text', name='Notes', text='Synthetic supplied notes.')
        self.act('capture', kind='url', url='https://example.invalid/reference')
        item = self.root / 'item'
        saved = install(self.sources.prepared(self.value['id'], self.value['revision']), item)
        manifest = (item / 'sources/research-inputs/manifest.json').read_bytes()
        chosen = {'documents': True, 'sites': [], 'web': True, 'widened_at': 'kept by a record'}
        draft = self.sources.from_inputs(item, saved, chosen, sites=['https://docs.example.invalid'])
        self.assertNotEqual(draft['id'], self.value['id'])
        self.assertEqual([s['name'] for s in draft['sources']], [s['name'] for s in self.value['sources']])
        self.assertTrue(draft['external'])
        self.assertFalse(draft['restricted'])
        self.assertEqual(draft['sites'], ['https://docs.example.invalid'])
        again = self.sources.prepared(draft['id'], draft['revision'])
        self.assertEqual(again['research_from'], {'documents': True, 'sites': [], 'web': True})
        self.assertEqual(sorted(s['sha256'] for s in again['sources']),
                         sorted(s['sha256'] for s in self.value['sources']))
        self.assertEqual((item / 'sources/research-inputs/manifest.json').read_bytes(), manifest)
        # A URL capture can be read again from the new draft; nothing was fetched to make it.
        self.assertEqual(self.network, ['https://example.invalid/reference'])
        self.assertTrue(self.sources.from_inputs(self.root / 'none', None, None)['sources'] == [])
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

    def test_narrowing_tabs_removes_unreferenced_earlier_full_document_capture(self):
        self.sources.google=lambda url, **options: {'name':'Synthetic reference','kind':'google-doc','origin':url,
            'tabs':[{'id':'a','title':'One'},{'id':'b','title':'Two'}], 'selected_tabs':options.get('selected') or ['a','b'],
            'raw': b'Selected one only' if options.get('selected') else b'Old full document body',
            'extracted':{'text':'Selected one only' if options.get('selected') else 'Old full document body','warnings':[]}}
        self.act('capture',kind='url',url='https://docs.google.com/document/d/synthetic/edit')
        before=self.sources.load(self.value['id'])['sources'][0]
        self.act('tabs',source=before['id'],selected=['a'])
        private=self.sources.folder(self.value['id'])
        self.assertFalse((private/before['file']).exists())
        self.assertFalse((private/before['original']).exists())
        self.assertNotIn('Old full',self.sources.preview(self.value['id'],before['id'])['text'])

    def test_same_start_has_one_creation_across_independent_callers(self):
        import threading
        from studio_core.research_sources import Start
        workspace=self.root/'workspace';workspace.mkdir()
        source=Sources(workspace/'.research-sources')
        value=source.create();reference={'id':value['id'],'expected':value['revision']}
        created=[];results=[];failures=[];barrier=threading.Barrier(3)
        def caller():
            try:
                barrier.wait(3)
                with Start(workspace,reference,{'product':'Synthetic Studio','title':'Synthetic'}) as start:
                    result=start.previous()
                    if result is None:
                        target=workspace/'items'/'synthetic';target.mkdir(parents=True)
                        created.append(target)
                        result={'id':'synthetic','path':str(target)};start.keep(result)
                    results.append(result)
            except BaseException as error: failures.append(error)
        threads=[threading.Thread(target=caller) for _ in range(3)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertFalse(failures,failures)
        self.assertEqual(len(created),1)
        self.assertEqual(len(results),3)
        self.assertTrue(all(result==results[0] for result in results))


class FolderTests(unittest.TestCase):
    """Add a folder, for a folder on this computer: a disposable tree, no network."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.kit = self.root / 'Field kit'
        for folder in ('Compete/Battlecards', 'Notes', '.git', 'Notes/.cache'):
            (self.kit / folder).mkdir(parents=True)
        (self.kit / 'Compete/Battlecards/EDB battlecard.md').write_text('Synthetic battlecard.')
        (self.kit / 'Notes/overview.txt').write_text('Synthetic overview.')
        (self.kit / 'Notes/Overview copy.TXT').write_text('Synthetic overview.')      # the same bytes
        (self.kit / 'Notes/.cache/hidden.md').write_text('Hidden synthetic text.')
        (self.kit / '.git/config.md').write_text('Hidden synthetic settings.')
        (self.kit / '.notes.md').write_text('Hidden synthetic notes.')
        (self.kit / 'deck.pptx').write_bytes(pptx_fixture.deck(pptx_fixture.SAMPLE))
        (self.kit / 'picture.png').write_bytes(b'not a document')
        (self.kit / 'empty.md').write_bytes(b'')
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'secret.md').write_text('OUTSIDE THE FOLDER')
        (self.kit / 'escape.md').symlink_to(outside / 'secret.md')
        (self.kit / 'Elsewhere').symlink_to(outside, target_is_directory=True)
        (self.kit / 'Notes/again').symlink_to(self.kit, target_is_directory=True)     # a loop
        self.network = []
        self.sources = Sources(self.root / 'store', fetch=lambda url: self.network.append(url),
                               drive=lambda account: self.network.append('drive'))
        self.value = self.sources.create()

    def add(self, location=None):
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], 'folder',
                                         location=str(location or self.kit))
        return self.value.pop('folder')

    def test_a_folder_on_this_computer_becomes_ordinary_sources_and_says_what_it_left(self):
        report = self.add()
        added = {s['name']: s for s in self.value['sources']}
        self.assertEqual(sorted(added), ['Compete/Battlecards/EDB battlecard.md', 'Notes/Overview copy.TXT', 'deck.pptx'])
        self.assertTrue(all(s['kind'] == 'file' and s['status'] == 'ready' for s in added.values()))
        self.assertTrue(all(research_sources.re.fullmatch('[a-f0-9]{32}', s['id']) for s in added.values()))
        # Where it came from is the folder's name and the path below it, never this computer's path.
        self.assertEqual(added['Compete/Battlecards/EDB battlecard.md']['origin'], 'Field kit/Compete/Battlecards/EDB battlecard.md')
        private = {s['name']: s for s in self.sources.load(self.value['id'])['sources']}
        self.assertEqual(private['deck.pptx']['local_path'], str(self.kit / 'deck.pptx'))
        self.assertEqual(private['deck.pptx']['folder'], str(self.kit))
        deck = self.sources.preview(self.value['id'], added['deck.pptx']['id'])['text']
        self.assertIn('Synthetic opening', deck)
        self.assertIn('Closing speaker context.', deck)
        self.assertEqual((report['where'], report['title'], report['added'], report['found']), ('local', 'Field kit', 3, 5))
        skipped = {row['name']: row for row in report['skipped']}
        self.assertEqual({name: row['code'] for name, row in skipped.items()}, {
            'empty.md': 'unreadable', 'escape.md': 'outside', 'Elsewhere': 'outside', 'picture.png': 'unsupported',
            'Notes/overview.txt': 'duplicate', 'Notes/again/': 'repeat'})
        self.assertEqual(skipped['Notes/again/']['reason'], 'Appears more than once in this folder. It leads back to a folder already scanned.')
        self.assertEqual(skipped['Notes/overview.txt']['reason'],
                         'Already a source here. It has the same content as “Notes/Overview copy.TXT”.')
        self.assertEqual(skipped['picture.png']['reason'], 'Not a type that can be read.')
        self.assertEqual(skipped['escape.md']['reason'], 'A link that leads outside the folder.')
        self.assertEqual(report['skipped_count'], 6)
        self.assertEqual(report['reasons'], {'unreadable': 1, 'outside': 2, 'unsupported': 1, 'duplicate': 1, 'repeat': 1})
        self.assertEqual(report['hidden'], 3)       # .git, .notes.md and Notes/.cache: counted, never opened
        self.assertIsNone(report['stopped'])
        everything = json.dumps([self.value, report]) + ''.join(
            self.sources.preview(self.value['id'], s['id'])['text'] for s in self.value['sources'])
        self.assertNotIn('OUTSIDE THE FOLDER', everything)
        self.assertNotIn('Hidden synthetic', everything)
        self.assertEqual(self.network, [], 'a folder on this computer asks nothing of the network or Google')

    def test_what_a_folder_added_starts_and_installs_like_any_other_source(self):
        from studio_core.research_sources import install, sources
        self.add()
        ready = self.sources.prepared(self.value['id'], self.value['revision'])
        self.assertEqual(ready['research_from'], {'documents': True, 'sites': [], 'web': False})
        item = self.root / 'item'
        saved = install(ready, item)
        self.assertEqual(saved['count'], 3)
        manifest = (item / 'sources/research-inputs/manifest.json').read_text()
        self.assertNotIn(str(self.root), manifest, 'the path on this computer stays in the private draft')
        plan, offered = sources(item, saved)
        self.assertEqual(sorted(row['title'] for row in plan), sorted(s['name'] for s in self.value['sources']))
        named = {row['title']: row for row in plan}
        self.assertTrue(named['deck.pptx']['original_file'].endswith('.original.pptx'))
        self.assertEqual(named['deck.pptx']['origin'], 'Field kit/deck.pptx')
        self.assertTrue(all(row['permission'] == 'selected' for row in offered))

    def test_adding_the_same_folder_again_adds_nothing_twice(self):
        self.add()
        before = self.value['revision']
        again = self.add()
        self.assertEqual(again['added'], 0)
        self.assertEqual(self.value['revision'], before, 'nothing added leaves the draft as it was')
        self.assertEqual(len(self.value['sources']), 3)
        self.assertEqual(again['reasons']['duplicate'], 4)
        row = next(r for r in again['skipped'] if r['name'] == 'deck.pptx')
        self.assertEqual(row['reason'], 'Already a source here. It has the same content as “deck.pptx”.')

    def test_one_add_is_bounded_and_adding_again_continues(self):
        with unittest.mock.patch.object(source_folders, 'FOLDER_MOST', 2):
            first = self.add()
            self.assertEqual(first['added'], 2)
            over = [row for row in first['skipped'] if row['code'] == 'over-limit']
            self.assertEqual([row['name'] for row in over], ['Notes/Overview copy.TXT', 'Notes/overview.txt'])
            self.assertEqual(over[0]['reason'], 'Over the limit. One folder add takes 2 documents. Add the folder again to read the next ones.')
            self.assertEqual((first['again'], first['next']), (True, 'Add the same folder again to read the next ones.'))
            second = self.add()
            self.assertEqual(second['added'], 1)
        self.assertEqual(len(self.value['sources']), 3)

    def test_the_drafts_own_ceiling_holds_and_is_said(self):
        with unittest.mock.patch.object(research_sources, 'MOST', 1):
            report = self.add()
        self.assertEqual(report['added'], 1)
        over = [row for row in report['skipped'] if row['code'] == 'over-limit']
        self.assertEqual(len(over), 4, 'every document past the ceiling is named, none is dropped unsaid')
        self.assertEqual(over[0]['reason'], 'Over the limit. These sources hold 1 files and pasted texts, the most one request takes.')
        self.assertEqual((report['again'], report['next']), (False, None), 'a full draft is not helped by adding again')

    def test_depth_looking_and_time_are_bounded_and_said(self):
        deep = self.root / 'deep'
        (deep / 'a/b/c').mkdir(parents=True)
        (deep / 'top.md').write_text('Top synthetic text.')
        (deep / 'a/b/c/low.md').write_text('Low synthetic text.')
        scan = source_folders.local(deep, research_sources.TYPES, research_sources.LIMIT, depth=2)
        self.assertEqual([item['name'] for item in scan['found']], ['top.md'])
        self.assertEqual(scan['skipped'], [{'name': 'a/b/c/', 'code': 'too-deep', 'reason': 'More than 6 folders deep.'}])
        self.assertEqual(source_folders.FOLDER_DEPTH, 6)
        stopped = source_folders.local(self.kit, research_sources.TYPES, research_sources.LIMIT, looked=3)
        self.assertTrue(stopped['stopped'])
        self.assertEqual(stopped['looked'], 3)
        said = source_folders.report(stopped, 0, where='local', title='Field kit')
        self.assertEqual(said['stopped'], 'The scan stopped after looking at 3 files and folders. Add a smaller folder to read the rest.')
        ticks = iter([0, 0, 1000, 1000, 1000, 1000, 1000])
        self.sources.clock = lambda: next(ticks)
        late = self.add()
        self.assertEqual(late['added'], 1)
        self.assertEqual(late['reasons']['out-of-time'], 4)
        self.assertIn({'name': 'empty.md', 'code': 'out-of-time', 'reason': 'Not read in time. Add the folder again to read the rest.'}, late['skipped'])

    def test_a_file_over_8_mb_is_left_and_said(self):
        big = self.root / 'big'; big.mkdir()
        with (big / 'large.txt').open('wb') as handle:
            handle.truncate(research_sources.LIMIT + 1)
        (big / 'small.txt').write_text('Small synthetic text.')
        report = self.add(big)
        self.assertEqual([s['name'] for s in self.value['sources']], ['small.txt'])
        self.assertEqual(report['skipped'], [{'name': 'large.txt', 'code': 'too-large', 'reason': 'Larger than 8 MB.'}])

    def test_files_on_this_computer_are_read_several_at_a_time_with_the_same_result(self):
        import threading
        from studio_core import source_documents
        expected = self.add()
        names = [s['name'] for s in self.value['sources']]
        watch, met, seen = threading.Lock(), threading.Event(), {'active': 0, 'peak': 0}
        def extract(raw, kind):
            with watch:
                seen['active'] += 1
                seen['peak'] = max(seen['peak'], seen['active'])
                if seen['active'] >= 2:
                    met.set()
            try:
                assert met.wait(5), 'files were not read at the same time'
                return source_documents.extract(raw, kind)
            finally:
                with watch:
                    seen['active'] -= 1
        together = Sources(self.root / 'together', extract=extract)
        value = together.create()
        value = together.mutate(value['id'], value['revision'], 'folder', location=str(self.kit))
        self.assertGreater(seen['peak'], 1)
        self.assertLessEqual(seen['peak'], source_folders.FOLDER_WORKERS)
        self.assertEqual([s['name'] for s in value['sources']], names)
        self.assertEqual(value['folder'], expected)
        self.assertEqual((expected['again'], expected['next']), (False, None))

    def test_a_workbook_in_a_folder_is_read_sheet_by_sheet(self):
        books = self.root / 'books'; books.mkdir()
        (books / 'Pipeline.xlsx').write_bytes(xlsx_fixture.workbook(xlsx_fixture.SAMPLE))
        (books / 'broken.xlsx').write_bytes(b'not a workbook')
        report = self.add(books)
        source = self.value['sources'][0]
        self.assertEqual((source['name'], source['kind'], source['warnings']), ('Pipeline.xlsx', 'file', []))
        self.assertEqual(self.sources.preview(self.value['id'], source['id'])['text'], xlsx_fixture.SAMPLE_TEXT)
        self.assertEqual(report['skipped'], [{'name': 'broken.xlsx', 'code': 'unreadable',
                                              'reason': 'Could not be read. ' + research_sources.xlsx_sheets.UNREADABLE}])

    def test_a_long_skipped_list_is_counted_in_full_and_listed_up_to_its_limit(self):
        scan = source_folders.started()
        scan['skipped'] = [source_folders.skip(f'file-{n}.png', 'unsupported') for n in range(source_folders.FOLDER_REPORTED + 7)]
        said = source_folders.report(scan, 0, where='local', title='Many')
        self.assertEqual((len(said['skipped']), said['skipped_count'], said['unlisted']), (source_folders.FOLDER_REPORTED, source_folders.FOLDER_REPORTED + 7, 7))
        self.assertEqual(said['reasons'], {'unsupported': source_folders.FOLDER_REPORTED + 7})

    def test_sources_changed_in_another_view_add_nothing_and_leave_no_files(self):
        stale = self.value['revision']
        other = self.sources.mutate(self.value['id'], stale, 'capture', kind='text', name='Notes', text='Synthetic notes.')
        with self.assertRaisesRegex(ValueError, 'another view'):
            self.sources.mutate(self.value['id'], stale, 'folder', location=str(self.kit))
        kept = self.sources.read(self.value['id'])
        self.assertEqual(kept['revision'], other['revision'])
        self.assertEqual(len(kept['sources']), 1)
        private = self.sources.load(self.value['id'])['sources'][0]
        files = sorted(p.name for p in (self.sources.folder(self.value['id']) / 'captures').iterdir())
        self.assertEqual(files, sorted([Path(private['file']).name, Path(private['original']).name]))

    def test_what_counts_as_a_folder_is_a_whole_path_or_a_google_drive_folder_link(self):
        for given in ('https://drive.google.com/drive/folders/1AbC_def-0123456789',
                      'https://drive.google.com/drive/u/0/folders/1AbC_def-0123456789?lfhs=2',
                      'https://drive.google.com/drive/folders/1AbC_def-0123456789/?usp=sharing',
                      '  "1AbC_def-0123456789"  ', '1AbC_def-0123456789'):
            self.assertEqual(source_folders.location(given), ('drive', '1AbC_def-0123456789'), given)
        self.assertEqual(source_folders.location(' ' + str(self.kit) + ' '), ('local', self.kit))
        self.assertEqual(source_folders.location("'" + str(self.kit) + "'"), ('local', self.kit))
        for given, said in (('Field kit/Notes', 'whole folder path'), (str(self.kit / 'missing'), 'was not found'),
                            (str(self.kit / 'deck.pptx'), 'was not found'),
                            ('https://docs.google.com/document/d/1AbC_def-0123456789/edit', 'starts with https://drive.google.com/drive/folders/'),
                            ('http://drive.google.com/drive/folders/1AbC_def-0123456789', 'starts with'),
                            ('https://drive.google.com.example.invalid/drive/folders/1AbC_def-0123456789', 'starts with'),
                            ('https://user:secret@drive.google.com/drive/folders/1AbC_def-0123456789', 'starts with'),
                            ('', 'folder path on this computer or a Google Drive folder link'), (7, 'folder path')):
            with self.assertRaisesRegex(ValueError, said):
                source_folders.location(given)
        for sent in ({}, {'location': str(self.kit), 'kind': 'file'}):
            with self.assertRaisesRegex(ValueError, 'folder path on this computer or a Google Drive folder link'):
                self.sources.mutate(self.value['id'], self.value['revision'], 'folder', **sent)

    def test_dispatch_takes_a_folder_as_the_page_sends_it(self):
        answer = self.sources.dispatch({'action': 'folder', 'id': self.value['id'], 'expected': self.value['revision'],
                                        'location': str(self.kit / 'Notes')})
        self.assertEqual(answer['folder']['added'], 1)
        self.assertEqual([s['name'] for s in answer['sources']], ['Overview copy.TXT'])
        self.assertIn('.pptx', answer['formats'])

    def test_an_uploaded_powerpoint_file_is_read_with_its_speaker_notes(self):
        deck = pptx_fixture.deck(pptx_fixture.SAMPLE)
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], 'capture', kind='file',
                                         name='Synthetic.PPTX', content=base64.b64encode(deck).decode())
        source = self.value['sources'][0]
        self.assertEqual((source['status'], source['kind']), ('ready', 'file'))
        text = self.sources.preview(self.value['id'], source['id'])['text']
        self.assertIn('Count 12', text)
        self.assertIn('Opening speaker context.', text)
        self.assertNotIn('Slide image placeholder', text)
        self.assertEqual(source['warnings'], ['Images, charts, video and WordArt are not interpreted. Supply their meaningful text or data separately.'])
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], 'capture', kind='file',
                                         name='broken.pptx', content=base64.b64encode(b'not a deck').decode())
        self.assertEqual(self.value['sources'][-1]['problem'], research_sources.PPTX_UNREADABLE)
        self.assertNotIn('Google', research_sources.PPTX_UNREADABLE)
