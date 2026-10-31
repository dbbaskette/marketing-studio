"""Add existing work to library: a preview of the studios' remembered workspaces, then an
import only on confirm, with Blog Studio's team library read through its legacy adapter.

Every workspace here is a disposable folder of synthetic Blog Studio records written by the
test; the library, the studios config and HOME are disposable too. No studio, assistant,
Team Hub, Git, reader program or network is used.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401  puts the core on the import path
from studio_core import document_library as library
from studio_core.document_library import adopt


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree(root):
    """Every file under a folder with its bytes' hash: what a test proves is left alone."""
    return {str(path.relative_to(root)): sha(path.read_bytes())
            for path in sorted(Path(root).rglob('*')) if path.is_file()}


class Workspace:
    """A synthetic Blog Studio workspace, plain (sources/) or a team one (hub.json)."""

    def __init__(self, root, team=False):
        self.root = Path(root)
        self.team = team
        self.root.mkdir(parents=True)
        if team:
            (self.root / 'hub.json').write_text(json.dumps({'tool': 'blog-studio', 'branch': 'main'}))
            self.sources = self.root / '.shared' / 'references'
            self.articles = self.root
        else:
            (self.root / 'studio.json').write_text(json.dumps({'schema_version': 1}))
            self.sources = self.root / 'sources'
            self.articles = self.root / 'articles'
        self.sources.mkdir(parents=True)

    def source(self, ident, name, text='', purposes=('reference',), status='ready', library=None,
               original=None, filename=None, revision=1, author=None, **extra):
        folder = self.sources / ident
        folder.mkdir(exist_ok=True)
        record = {'id': ident, 'name': name, 'origin': 'synthetic', 'purposes': list(purposes),
                  'status': status, 'revision': revision, 'author': author,
                  'content_sha256': sha(text.encode()) if text else None,
                  'original_filename': filename, 'original_path': None, 'original_sha256': None,
                  **extra}
        if text:
            (folder / 'content.md').write_text(text)
        if original is not None:
            ending = Path(filename).suffix
            (folder / ('original' + ending)).write_bytes(original)
            record.update(original_path='original' + ending, original_sha256=sha(original))
        if library:
            record['library'] = library
        (folder / 'record.json').write_text(json.dumps(record))
        return folder

    def blog(self, ident, voice=None, style=None):
        folder = self.articles / ident
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'session.json').write_text(json.dumps({
            'id': ident, 'title': 'Synthetic blog', 'voice': voice or {'mode': 'tone', 'tone': 'Plain'},
            'style': style, 'sources': []}))


class AdoptCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.config = self.base / 'studios-config.json'
        patcher = mock.patch.dict(os.environ, {'HOME': str(self.base / 'home'),
                                               'STUDIOS_CONFIG': str(self.config),
                                               'STUDIOS_LIBRARY': str(self.base / 'library')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.blogs = Workspace(self.base / 'writing')
        self.blogs.blog('gateway-guide-1a2b3c4d',
                        voice={'mode': 'profile', 'profile_id': 'avery-0a0a0a0a', 'revision': 3},
                        style={'style_id': 'product-announcement', 'revision': 2})
        self.blogs.source('gateway-guide-1a2b3c4e', 'Gateway guide', '# Gateway guide\n\nRoutes.\n',
                          purposes=('reference', 'inspiration'), author='Avery',
                          library={'origin_kind': 'written-here', 'article': 'gateway-guide-1a2b3c4d',
                                   'kind': 'product-announcement'})
        self.blogs.source('pricing-notes-5e6f7a8b', 'Pricing notes', 'Plans start at two seats.\n',
                          original=b'Plans start at two seats.\n', filename='pricing.md',
                          library={'origin_kind': 'upload'})
        self.blogs.source('old-post-9c0d1e2f', 'An old post', 'Posted in 2019.\n',
                          library={'origin_kind': 'import'})
        self.blogs.source('avery-sample-3a4b5c6d', 'Avery sample', 'How Avery writes.\n',
                          purposes=('voice-sample',), author='Avery')
        self.blogs.source('scan-7e8f9a0b', 'A scanned page', status='pending',
                          original=b'%PDF-1.4 synthetic', filename='scan.pdf',
                          library={'origin_kind': 'upload'})
        # Left alone: one blog's own file, a Team Hub snapshot, a copy from the library.
        self.blogs.source('material-0123456789abcdef', 'Upload for one blog', 'Private.\n',
                          purposes=('material',))
        self.blogs.source('pinned-1b2c3d4e', 'Team Hub snapshot', 'Snapshot.\n', pinned_reference=True)
        self.known = {'blog': {'root': str(self.blogs.root)}, 'presentation': None,
                      'training': {'root': str(self.base / 'training-work')}}

    def catalog(self):
        found = library.opened()
        return found.catalog(limit=50)['items'] if found else []

    def revision(self, row):
        place = library.opened().root / 'documents' / row['id'] / 'revisions' / str(row['revision'])
        return json.loads((place / 'revision.json').read_text())


class PreviewTests(AdoptCase):
    def test_preview_reads_only_known_workspaces_and_writes_nothing(self):
        before = tree(self.blogs.root)
        found = adopt.preview(self.known)
        self.assertFalse((self.base / 'library').exists())
        self.assertFalse(self.config.exists())
        self.assertEqual(tree(self.blogs.root), before)
        places = {row['studio']: row for row in found['workspaces']}
        self.assertEqual(places['blog']['state'], 'found')
        self.assertEqual(places['blog']['count'], 5)
        self.assertEqual(places['presentation']['state'], 'none')
        self.assertEqual(places['training']['state'], 'not-offered')
        self.assertEqual(places['infographic']['state'], 'none')
        self.assertEqual((found['total'], found['new'], found['adding']), (5, 5, 5))
        rows = {row['title']: row for row in found['items']}
        self.assertNotIn('Upload for one blog', rows)
        self.assertNotIn('Team Hub snapshot', rows)
        self.assertEqual(rows['Gateway guide']['kind_label'], 'Blog')
        self.assertEqual(rows['Gateway guide']['note'], 'Finished blog')
        self.assertIn('no PDF', ' '.join(rows['Gateway guide']['gaps']))
        self.assertEqual(rows['Pricing notes']['format_labels'], ['Markdown', 'Original'])
        self.assertEqual(rows['An old post']['kind_label'], 'Blog')
        self.assertEqual(rows['An old post']['origin_label'], 'Imported')
        self.assertEqual(rows['Avery sample']['note'], 'Voice sample')
        self.assertEqual(rows['A scanned page']['format_labels'], ['Original'])
        self.assertFalse(rows['A scanned page']['readable'])
        self.assertTrue(all(row['state_label'] == 'Will be added' for row in found['items']))
        self.assertNotIn(str(self.base), json.dumps(found['items']))   # no local path in rows

    def test_damaged_linked_and_missing_items_are_gaps_not_candidates(self):
        damaged = self.blogs.source('damaged-aaaa1111', 'Damaged', 'Edited by hand.\n')
        (damaged / 'content.md').write_text('Changed after it was kept.\n')
        linked = self.blogs.source('linked-bbbb2222', 'Linked', 'Was here.\n')
        (linked / 'content.md').unlink()
        (linked / 'content.md').symlink_to(self.base / 'elsewhere.md')
        (self.base / 'elsewhere.md').write_text('Was here.\n')
        self.blogs.source('empty-cccc3333', 'Empty', status='pending')
        found = adopt.preview(self.known)
        titles = {row['title'] for row in found['items']}
        self.assertFalse({'Damaged', 'Linked', 'Empty'} & titles)
        gaps = ' '.join(next(row for row in found['workspaces'] if row['studio'] == 'blog')['gaps'])
        self.assertIn('“Damaged” was left out', gaps)
        self.assertIn('“Linked” was left out', gaps)
        self.assertIn('“Empty” was left out', gaps)
        # A workspace that is gone, or not Blog Studio's, offers nothing.
        gone = adopt.preview({'blog': {'root': str(self.base / 'gone')}})
        self.assertEqual(gone['workspaces'][0]['state'], 'missing')
        (self.base / 'plain').mkdir()
        other = adopt.preview({'blog': {'root': str(self.base / 'plain')}})
        self.assertEqual((other['workspaces'][0]['state'], other['total']), ('unreadable', 0))

    def test_retired_and_odd_records_are_gaps_and_never_stop_the_preview(self):
        self.blogs.source('retired-ffff6666', 'Retired post', 'Old words.\n',
                          library={'origin_kind': 'import', 'curation': 'retired'})
        # A written-here record whose blog ID is not text: read as a reference, not a crash.
        self.blogs.source('odd-abcd7777', 'Odd record', 'Odd words.\n',
                          library={'origin_kind': 'written-here', 'article': 42})
        found = adopt.preview(self.known)
        rows = {row['title']: row for row in found['items']}
        self.assertNotIn('Retired post', rows)
        self.assertEqual((rows['Odd record']['kind_label'], found['total']), ('Uploaded document', 6))
        gaps = ' '.join(next(row for row in found['workspaces'] if row['studio'] == 'blog')['gaps'])
        self.assertIn('“Retired post” was left out: it is retired', gaps)
        # Whatever else a record holds that the adapter cannot read is one gap, not a failure.
        real = adopt.blog_existing._candidate

        def odd(places, folder):
            if folder.name == 'odd-abcd7777':
                raise TypeError('synthetic')
            return real(places, folder)
        with mock.patch.object(adopt.blog_existing, '_candidate', odd):
            found = adopt.preview(self.known)
        self.assertEqual(found['total'], 5)
        gaps = ' '.join(next(row for row in found['workspaces'] if row['studio'] == 'blog')['gaps'])
        self.assertIn('“odd-abcd7777” was left out: its record is not in a shape', gaps)

    def test_a_file_already_kept_at_upload_is_not_added_again(self):
        # Keep in library kept this file when it was uploaded (no key); the team library holds
        # the same bytes as Pricing notes. It is shown as already there, never added twice.
        made = library.opened(create=True)
        made.add_upload('pricing.md', b'Plans start at two seats.\n', studio='blog')
        found = adopt.preview(self.known)
        row = next(row for row in found['items'] if row['title'] == 'Pricing notes')
        self.assertEqual((row['state'], row['state_label']), ('kept', 'Already in the library'))
        self.assertIn('Kept in the library when it was uploaded.', row['gaps'])
        self.assertEqual((found['adding'], found['kept']), (4, 1))
        adopt.confirm(self.known, found['signature'])
        self.assertEqual(sum(row['title'] in ('Pricing notes', 'pricing') for row in self.catalog()), 1)
        self.assertEqual(adopt.preview(self.known)['adding'], 0)

    def test_team_workspace_layout(self):
        team = Workspace(self.base / 'team', team=True)
        team.source('launch-notes-dddd4444', 'Launch notes', 'Shared notes.\n',
                    library={'origin_kind': 'link'})
        found = adopt.preview({'blog': {'root': str(team.root)}})
        self.assertEqual([row['title'] for row in found['items']], ['Launch notes'])
        self.assertEqual(found['items'][0]['origin_label'], 'Link')
        self.assertIn('Team Hub', ' '.join(found['workspaces'][0]['gaps']))


class ConfirmTests(AdoptCase):
    def test_confirm_adds_once_with_native_metadata_and_again_adds_nothing(self):
        before = tree(self.blogs.root)
        found = adopt.preview(self.known)
        done = adopt.confirm(self.known, found['signature'])
        self.assertEqual((done['added'], done['revised'], done['unchanged'], done['failed']),
                         (5, 0, 0, []))
        self.assertEqual(tree(self.blogs.root), before)    # no workspace file changed
        rows = {row['title']: row for row in self.catalog()}
        self.assertEqual(len(rows), 5)
        blog = self.revision(rows['Gateway guide'])
        self.assertEqual((blog['key'], blog['kind'], blog['origin'], blog['author']),
                         ('blog:gateway-guide-1a2b3c4d', 'blog', 'created', 'Avery'))
        self.assertEqual(blog['native']['voice'],
                         {'mode': 'profile', 'profile_id': 'avery-0a0a0a0a', 'revision': 3})
        self.assertEqual(blog['native']['style'], {'style_id': 'product-announcement', 'revision': 2})
        self.assertEqual((blog['native']['source'], blog['native']['revision'], blog['native']['post_kind']),
                         ('gateway-guide-1a2b3c4e', 1, 'product-announcement'))
        self.assertEqual(blog['project']['revision'], 1)
        sample = self.revision(rows['Avery sample'])
        self.assertEqual((sample['kind'], sample['native']['role'], sample['native']['purposes']),
                         ('upload', 'voice-sample', ['voice-sample']))
        pricing = library.opened().download(rows['Pricing notes']['id'], 1, 'original')
        self.assertEqual(pricing, ('pricing.md', 'text/markdown', b'Plans start at two seats.\n'))
        self.assertEqual(rows['A scanned page']['state'], 'needs-text')
        # Again: the preview finds everything there, and a confirm adds nothing.
        again = adopt.preview(self.known)
        self.assertEqual((again['kept'], again['adding']), (5, 0))
        self.assertTrue(all(row['state_label'] == 'Already in the library' for row in again['items']))
        done = adopt.confirm(self.known, again['signature'])
        self.assertEqual((done['added'], done['revised'], done['unchanged']), (0, 0, 5))
        self.assertEqual([row['revision'] for row in self.catalog()], [1] * 5)

    def test_a_changed_workspace_refuses_the_old_preview_and_adds_nothing(self):
        found = adopt.preview(self.known)
        self.blogs.source('late-eeee5555', 'Arrived after the preview', 'New.\n')
        with self.assertRaisesRegex(library.LibraryError, 'Preview again'):
            adopt.confirm(self.known, found['signature'])
        self.assertIsNone(library.opened())
        with self.assertRaises(library.LibraryError):
            adopt.confirm(self.known, 'not a signature')

    def test_a_new_native_revision_adds_a_library_revision_and_finishing_reuses_it(self):
        adopt.confirm(self.known, adopt.preview(self.known)['signature'])
        self.blogs.source('pricing-notes-5e6f7a8b', 'Pricing notes', 'Plans start at three seats.\n',
                          original=b'Plans start at two seats.\n', filename='pricing.md',
                          library={'origin_kind': 'upload'}, revision=2)
        found = adopt.preview(self.known)
        row = next(row for row in found['items'] if row['title'] == 'Pricing notes')
        self.assertEqual((row['state'], row['state_label']), ('changed', 'Adds revision 2'))
        done = adopt.confirm(self.known, found['signature'])
        self.assertEqual((done['added'], done['revised'], done['unchanged']), (0, 1, 4))
        pricing = next(row for row in self.catalog() if row['title'] == 'Pricing notes')
        self.assertEqual((pricing['revision'], self.revision(pricing)['native']['revision']), (2, 2))
        # Blog Studio's Finish keeps the blog under the same key: the same text adds nothing.
        made = library.opened(create=True)
        kept = made.retain('blog:gateway-guide-1a2b3c4d', 'blog', 'blog', 'Gateway guide',
                           '# Gateway guide\n\nRoutes.\n')
        self.assertEqual((kept['changed'], kept['revision']), (False, 1))

    def test_one_failure_is_reported_and_the_rest_are_added(self):
        found = adopt.preview(self.known)
        real = adopt.blog_existing.load

        def flaky(root, candidate):
            if candidate['title'] == 'An old post':
                raise ValueError('“An old post” changed in Blog Studio after the preview.')
            return real(root, candidate)
        with mock.patch.object(adopt.blog_existing, 'load', flaky):
            done = adopt.confirm(self.known, found['signature'])
        self.assertEqual((done['added'], [one['title'] for one in done['failed']]), (4, ['An old post']))
        again = adopt.preview(self.known)
        self.assertEqual((again['adding'], again['kept']), (1, 4))
        self.assertEqual(adopt.confirm(self.known, again['signature'])['added'], 1)


class HomeTests(AdoptCase):
    """The Marketing Studio Library screen's routes, over the workspace Blog Studio remembers."""

    def setUp(self):
        super().setUp()
        from marketing_studio.launcher import Launcher
        from marketing_studio.page import Home
        data = self.base / 'blog-data'
        data.mkdir()
        (data / 'page.json').write_text(json.dumps({'workspace': str(self.blogs.root)}))
        patcher = mock.patch.dict(os.environ, {
            'MARKETING_STUDIO_DATA': str(self.base / 'data'), 'BLOG_STUDIO_DATA': str(data),
            'PRESENTATION_STUDIO_DATA': str(self.base / 'none'),
            'TRAINING_STUDIO_DATA': str(self.base / 'none'),
            'INFOGRAPHIC_STUDIO_DATA': str(self.base / 'none')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.page = Home(8000, self.launcher)

    def write(self, path, sent):
        return json.loads(self.page.write(path, sent)[2])

    def test_preview_then_confirm_from_the_library_screen(self):
        from marketing_studio.errors import WorkspaceError
        found = self.write('/api/library-existing', {})
        self.assertEqual(found['adding'], 5)
        self.assertFalse((self.base / 'library').exists())
        with self.assertRaises(WorkspaceError):
            self.write('/api/library-adopt', {'signature': '0' * 64})
        done = self.write('/api/library-adopt', {'signature': found['signature']})
        self.assertEqual(done['added'], 5)
        self.assertEqual(self.write('/api/library', {})['total'], 5)
        self.assertEqual(self.write('/api/library-existing', {})['adding'], 0)


@unittest.skipUnless(__import__('shutil').which('node'), 'Node.js runs the page script.')
class PageTests(AdoptCase):
    """The Library screen's card, run through the shared settings page harness."""

    def run_page(self, steps):
        import subprocess
        plan = self.base / 'plan.json'
        plan.write_text(json.dumps({'steps': steps}))
        done = subprocess.run(['node', str(Path(__file__).with_name('settings_page_harness.js')), str(plan)],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_preview_lists_workspaces_and_items_then_confirm_sends_its_signature(self):
        found = adopt.preview(self.known)
        done = {'added': 4, 'revised': 0, 'unchanged': 0, 'location': '~/Studios/library',
                'failed': [{'title': 'An old post', 'problem': 'It changed after the preview.'}]}
        shots = self.run_page([
            {'responses': {'library-existing': found, 'library-adopt': done}},
            {'press': '#library-existing-preview'},
            {'snapshot': 'preview', 'ids': ['library-existing-result']},
            {'press': 'Add 5 to library', 'within': '#library-existing-result'},
            {'snapshot': 'added', 'ids': ['library-existing-result'], 'read': ['#problem']},
        ])
        shown = shots['preview']['words']['library-existing-result']
        for words in ('Blog Studio', 'Workspace: ', 'Presentation Studio has no workspace',
                      'not offered yet', '5 items found: 5 new', 'Gateway guide',
                      'Blog · Blog Studio · Finished blog · Markdown', 'Markdown, Original',
                      'Voice sample', 'Will be added', 'Add 5 to library', 'Cancel',
                      'Nothing is shared with your team'):
            self.assertIn(words, shown)
        added = shots['added']
        self.assertEqual(added['requests'][-1]['sent'], {'signature': found['signature']})
        self.assertIn('4 added.', added['words']['library-existing-result'])
        self.assertIn('An old post: It changed after the preview.', added['words']['library-existing-result'])
        self.assertEqual(added['toasts'], ['Some existing work could not be added.'])

    def test_the_preview_is_announced_and_a_refused_confirm_keeps_its_count(self):
        found = adopt.preview(self.known)
        shots = self.run_page([
            {'responses': {'library-existing': found,
                           'library-adopt': {'error': 'Something the preview offered changed.'}}},
            {'press': '#library-existing-preview'},
            {'press': 'Add 5 to library', 'within': '#library-existing-result'},
            {'snapshot': 'refused', 'ids': ['library-existing-result']},
        ])
        shown = shots['refused']['words']['library-existing-result']
        self.assertIn('5 items can be added. Nothing is added until you confirm.', shown)
        self.assertIn('Something the preview offered changed.', shown)
        self.assertIn('Add 5 to library', shown)
        self.assertNotIn('Adding…', shown)


if __name__ == '__main__':
    unittest.main()
