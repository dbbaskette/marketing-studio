"""Blog Studio and the shared Document Library: finished and published blogs kept there,
and library documents chosen for one blog as its own files, with their roles.

The library is a disposable folder (STUDIOS_LIBRARY). No assistant, analysis, Team Hub or
network is used.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import os
from pathlib import Path
from unittest.mock import patch

from test_blog_runner import RunnerCase
import test_team_library as team
import blog_library
import blog_runner as runner
import management
import shared_library
import studio
from studio_core import document_library

OPERATION = 'e' * 32


class SharedLibraryCase(RunnerCase):
    def setUp(self):
        super().setUp()
        patcher = patch.dict(os.environ, {'STUDIOS_LIBRARY': str(self.base / 'shared-library')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def shared(self):
        found = document_library.opened()
        return found.catalog(kind='blog')['items'] if found else []


class KeepTests(SharedLibraryCase):
    finish = team.FinishTests.finish
    desk = team.DeskPublishTests.desk
    publish = team.DeskPublishTests.publish

    def test_finish_keeps_the_blog_as_markdown_and_again_only_when_changed(self):
        found = self.finish(self.create(style='product-announcement', author='Avery'))
        rows = self.shared()
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            (rows[0]['title'], rows[0]['studio'], rows[0]['author']),
            ('Synthetic gateway guide', 'blog', 'Avery'),
        )
        draft = studio.inside(self.root, 'articles', found['id']) / 'DRAFT.md'
        library = document_library.opened()
        self.assertEqual(library.snapshot(rows[0]['id'], 1)['text'], draft.read_text())
        self.assertTrue(found['decisions'][-1]['event'].endswith(' · kept in the team library'))
        found = runner.decide(
            self.root, found['id'], found['expected'], 'changes', 'Tighter.', target='draft'
        )
        found = self.finish(self.approve(self.submit(found, '# draft\nTighter words.')))
        rows = self.shared()
        self.assertEqual((len(rows), rows[0]['revision']), (1, 2))

    def test_desk_publish_keeps_it_and_a_library_failure_never_stops_publishing(self):
        made = self.desk(style='product-announcement')
        result = self.publish(made['id'])
        self.assertEqual(result['document_library']['state'], 'kept')
        self.assertEqual(len(self.shared()), 1)
        again = self.desk(operation='f')
        with patch.object(
            document_library, 'opened', side_effect=document_library.LibraryError('Busy.')
        ):
            result = self.publish(again['id'])
        self.assertEqual(result['document_library'], {'state': 'failed', 'reason': 'Busy.'})
        self.assertEqual(len(team.FinishTests.kept(self)), 2)


class TakeTests(SharedLibraryCase):
    def setUp(self):
        super().setUp()
        self.library = document_library.opened(create=True)
        self.facts = self.library.add_upload('Gateway facts.md', b'The gateway holds 40 routes.\n')
        self.example = self.library.retain(
            'presentation:launch', 'presentation', 'presentation', 'Launch deck', '# Launch\n'
        )

    def take(self, picks, operation=OPERATION):
        return management.dispatch(
            self.root, shared_library.TAKE, {'operation': operation, 'picks': picks}
        )

    def test_chosen_documents_become_files_for_one_blog_with_their_roles(self):
        result = self.take(
            [
                {'id': self.facts['id'], 'revision': 1, 'role': 'facts'},
                {'id': self.example['document'], 'revision': 1, 'role': 'example'},
            ]
        )
        sources = [row['source'] for row in result['files']]
        self.assertEqual(
            [s['purposes'] for s in sources], [['material'], ['material', 'inspiration']]
        )
        for source in sources:
            directory, record = studio.item(self.root, 'sources', source['id'])
            self.assertTrue(studio.is_material(self.root, directory, record))
            self.assertEqual(record['document_library']['revision'], 1)
        self.assertEqual(
            (studio.item(self.root, 'sources', sources[0]['id'])[0] / 'content.md').read_text(),
            'The gateway holds 40 routes.\n',
        )
        # Not team library items: the team catalog and the Team Hub never see them.
        self.assertEqual(blog_library.catalog(self.root)['items'], [])
        # The same operation returns what it made; another request under it is refused.
        self.assertEqual(
            self.take(
                [
                    {'id': self.facts['id'], 'revision': 1, 'role': 'facts'},
                    {'id': self.example['document'], 'revision': 1, 'role': 'example'},
                ]
            ),
            result,
        )
        with self.assertRaisesRegex(ValueError, 'different request'):
            self.take([{'id': self.facts['id'], 'revision': 1, 'role': 'messaging'}])
        # A blog pins them as it pins uploaded files; an example stays an example.
        made = management.dispatch(
            self.root,
            'desk-create',
            {
                'operation': 'c' * 32,
                'title': 'Library post',
                'manuscript': '# Library post\n\nWords.\n',
                'sources': [s['id'] for s in sources],
            },
        )
        _, record = studio.item(self.root, 'articles', made['id'])
        pinned = {entry['source_id']: entry['purposes'] for entry in record['sources']}
        self.assertEqual(pinned[sources[1]['id']], ['material', 'inspiration'])
        self.assertEqual(sorted(record['material']), sorted(s['id'] for s in sources))

    def test_unreadable_or_unknown_documents_change_nothing(self):
        broken = self.library.add_upload('broken.docx', b'not a zip')
        before = (
            sorted(Path(studio.material(self.root)).glob('*'))
            if studio.material(self.root).exists()
            else []
        )
        for picks in (
            [
                {'id': self.facts['id'], 'revision': 1, 'role': 'facts'},
                {'id': broken['id'], 'revision': 1, 'role': 'facts'},
            ],
            [{'id': self.facts['id'], 'revision': 9, 'role': 'facts'}],
            [{'id': self.facts['id'], 'revision': 1, 'role': 'voice-sample'}],
            [],
        ):
            with self.subTest(picks=picks), self.assertRaises(ValueError):
                self.take(picks, operation='d' * 32)
        after = (
            sorted(Path(studio.material(self.root)).glob('*'))
            if studio.material(self.root).exists()
            else []
        )
        self.assertEqual(after, before)

    def test_browsing_routes_and_the_sheet_are_served(self):
        found = management.dispatch(self.root, 'document-library', {'filters': {'kind': 'upload'}})
        self.assertEqual([row['id'] for row in found['items']], [self.facts['id']])
        shown = management.dispatch(
            self.root, 'document-library-document', {'id': self.facts['id']}
        )
        self.assertIn('40 routes', shown['text'])
        name, media = management.STATIC['/library.js']
        self.assertTrue(Path(name).is_file())
        self.assertTrue(media.startswith('text/javascript'))


class UpdateTests(SharedLibraryCase):
    """Update available on the desk: a newer revision is shown, and taken only when asked."""

    def setUp(self):
        super().setUp()
        self.library = document_library.opened(create=True)
        self.deck = self.library.retain(
            'presentation:launch',
            'presentation',
            'presentation',
            'Launch deck',
            '# Launch\n\nOne.\n',
        )
        taken = management.dispatch(
            self.root,
            shared_library.TAKE,
            {
                'operation': OPERATION,
                'picks': [{'id': self.deck['document'], 'revision': 1, 'role': 'facts'}],
            },
        )
        self.source = taken['files'][0]['source']['id']
        self.blog = management.dispatch(
            self.root,
            'desk-create',
            {
                'operation': 'c' * 32,
                'title': 'Library post',
                'manuscript': '# Library post\n\nWords.\n',
                'sources': [self.source],
            },
        )['id']

    def newer(self):
        self.library.retain(
            'presentation:launch',
            'presentation',
            'presentation',
            'Launch deck',
            '# Launch\n\nTwo.\n',
        )

    def shown(self):
        import desk_jobs

        names = desk_jobs.view(self.root, self.blog)['source_names']
        return next(row for row in names if row['id'] == self.source)

    def update(self, source=None):
        return management.dispatch(
            self.root, 'desk-library-update', {'id': self.blog, 'source': source or self.source}
        )

    def test_a_newer_revision_is_shown_and_taken_only_when_asked(self):
        self.assertEqual(
            self.shown()['library'],
            {'id': self.deck['document'], 'revision': 1, 'head': 1, 'update': False},
        )
        with self.assertRaisesRegex(ValueError, 'already uses the newest'):
            self.update()
        self.newer()
        self.assertEqual(
            (self.shown()['library']['update'], self.shown()['library']['head']), (True, 2)
        )
        folder, _ = studio.item(self.root, 'sources', self.source)
        # Showing it changed nothing: the blog still reads revision 1.
        self.assertEqual((folder / 'content.md').read_text(), '# Launch\n\nOne.\n')
        self.assertEqual(self.update()['id'], self.blog)
        folder, after = studio.item(self.root, 'sources', self.source)
        self.assertEqual((after['revision'], after['document_library']['revision']), (2, 2))
        self.assertEqual((folder / 'content.md').read_text(), '# Launch\n\nTwo.\n')
        self.assertTrue(studio.is_material(self.root, folder, after))
        _, record = studio.item(self.root, 'articles', self.blog)
        pin = next(entry for entry in record['sources'] if entry['source_id'] == self.source)
        self.assertEqual((pin['revision'], pin['purposes']), (2, ['material']))
        self.assertFalse(self.shown()['library']['update'])
        # What the blog read before stays readable at the revision it pinned.
        self.assertEqual(runner.pinned_source(folder, after, 1)[1], '# Launch\n\nOne.\n')
        self.assertEqual(runner.pinned_source(folder, after, 2)[1], '# Launch\n\nTwo.\n')
        self.assertEqual(blog_library.catalog(self.root)['items'], [])

    def test_refused_while_a_job_runs_or_when_the_library_is_gone(self):
        import desk_jobs

        self.newer()
        with (
            patch.object(desk_jobs, 'jobs', return_value=[{'status': 'working'}]),
            patch.object(desk_jobs, 'busy', return_value=True),
            self.assertRaisesRegex(ValueError, 'desk job is working'),
        ):
            self.update()
        with (
            patch.object(document_library, 'opened', return_value=None),
            self.assertRaisesRegex(ValueError, 'no longer in the Document Library'),
        ):
            self.update()
        with self.assertRaisesRegex(ValueError, 'not a source of this blog'):
            self.update('material-0000000000000000')
        _, record = studio.item(self.root, 'sources', self.source)
        self.assertEqual(record['revision'], 1)


class KeepUploadTests(SharedLibraryCase):
    """Keep in library at upload: a local copy, beside whatever the file is kept as."""

    def upload(self, keep, operation=OPERATION, name='Gateway facts.md'):
        import base64

        return management.dispatch(
            self.root,
            'upload',
            {
                'operation': operation,
                'files': [
                    {
                        'filename': name,
                        'content': base64.b64encode(b'The gateway holds 40 routes.\n').decode(),
                        'purpose': 'material',
                    }
                ],
                'purpose': 'material',
                'keep': False,
                'analyze': False,
                'document_library': keep,
            },
        )

    def test_keep_in_library_keeps_a_copy_and_only_this_blog_keeps_none(self):
        result = self.upload(True)
        row = result['files'][0]
        self.assertEqual(row['document_library']['state'], 'kept')
        library = document_library.opened()
        listed = library.catalog()['items']
        self.assertEqual(
            [(item['title'], item['studio'], item['formats']) for item in listed],
            [('Gateway facts', 'blog', ['markdown', 'original'])],
        )
        # The file itself is still this blog's own upload, never a team library item.
        directory, record = studio.item(self.root, 'sources', row['source']['id'])
        self.assertTrue(studio.is_material(self.root, directory, record))
        self.assertNotIn('document_library', record)
        self.assertEqual(blog_library.catalog(self.root)['items'], [])
        # The same upload again returns what it did, and the library keeps it once.
        self.assertEqual(self.upload(True), result)
        self.assertEqual(len(library.catalog()['items']), 1)
        # The same file uploaded again under another operation, for another blog, is the same
        # library document: its operation comes from the file's name, bytes and title.
        again = self.upload(True, operation='f' * 32)
        self.assertEqual(again['files'][0]['document_library']['id'], row['document_library']['id'])
        self.assertEqual(len(library.catalog()['items']), 1)
        only = self.upload(False, operation='b' * 32, name='Private.md')
        self.assertNotIn('document_library', only['files'][0])
        self.assertEqual(len(library.catalog()['items']), 1)
        with self.assertRaisesRegex(ValueError, 'Keep in library or Only this blog'):
            self.upload('yes', operation='d' * 32)

    def test_a_library_failure_never_stops_the_upload(self):
        with patch.object(
            document_library, 'opened', side_effect=document_library.LibraryError('Busy.')
        ):
            result = self.upload(True)
        row = result['files'][0]
        self.assertEqual(row['document_library'], {'state': 'failed', 'reason': 'Busy.'})
        studio.item(self.root, 'sources', row['source']['id'])
