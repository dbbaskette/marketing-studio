"""One team library: every item carries a role, a kind of post and where it came from."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import base64
from unittest.mock import patch

from hub_fixtures import FakeProvider
from hub import Registry
from hub_workspace import Workspace
from test_blog_runner import RunnerCase
from test_editorial_tools import Fixture
from test_voice_links import Pages, page
import blog_library as library
import blog_runner as runner
import management
import studio


class LibraryFieldTests(Fixture):
    """Task 1: library.kind, library.origin_kind and library.article on a source."""

    def test_fields_are_validated_and_only_given_values_appear(self):
        self.assertEqual(library.library_fields(self.root), {})
        self.assertEqual(
            library.library_fields(
                self.root, kind='product-announcement', origin_kind='upload', article='blog-1'
            ),
            {'kind': 'product-announcement', 'origin_kind': 'upload', 'article': 'blog-1'},
        )
        with self.assertRaisesRegex(ValueError, 'kind of post'):
            library.library_fields(self.root, kind='no-such-style')
        with self.assertRaisesRegex(ValueError, 'written here'):
            library.library_fields(self.root, origin_kind='email')
        with self.assertRaisesRegex(ValueError, 'ID'):
            library.library_fields(self.root, article='Not an id')

    def upload(self, operation, **extra):
        return management.dispatch(
            self.root,
            'upload',
            {
                'operation': operation * 32,
                'filename': 'post.md',
                'content': base64.b64encode(b'An earlier announcement.').decode(),
                'purpose': 'inspiration',
                'as_blog': False,
                'analyze': False,
                **extra,
            },
        )

    def test_fields_survive_a_revision_a_refresh_and_the_hub_projection(self):
        provider = FakeProvider(self.base / 'remotes')
        a, b = Registry(self.base / 'a-hubs', provider), Registry(self.base / 'b-hubs', provider)
        ident = a.create('fixture/library', 'Library')['hub']
        b.join('fixture/library')
        other = self.base / 'other'
        studio.initialize(other)
        wa, wb = Workspace(self.root, a.hub(ident)), Workspace(other, b.hub(ident))
        with patch(
            'hub_workspace.active', side_effect=lambda root: wa if root == self.root else wb
        ):
            saved = self.upload('1', kind='product-announcement', author='Avery')['source']
            directory, record = studio.item(self.root, 'sources', saved['id'])
            self.assertEqual(
                record['library'], {'kind': 'product-announcement', 'origin_kind': 'upload'}
            )
            self.assertEqual(record['purposes'], ['reference', 'inspiration'])
            # A new revision keeps the fields.
            management.dispatch(
                self.root,
                'tool-action',
                {'action': 'source-purpose', 'source': saved['id'], 'purpose': 'style-sample'},
            )
            _, record = studio.item(self.root, 'sources', saved['id'])
            self.assertEqual(record['revision'], 2)
            self.assertEqual(record['library']['kind'], 'product-announcement')
            # The catalog exposes them, and filters by role, kind and author.
            rows = library.catalog(self.root)['items']
            self.assertEqual(rows[0]['library']['origin_kind'], 'upload')
            self.assertEqual(rows[0]['library']['kind'], 'product-announcement')
            self.assertEqual(rows[0]['kind_name'], 'Product announcement')
            self.assertEqual(rows[0]['role'], 'example')
            self.assertEqual(library.catalog(self.root, role='example')['total'], 1)
            self.assertEqual(library.catalog(self.root, role='facts')['total'], 0)
            self.assertEqual(library.catalog(self.root, role='style-sample')['total'], 1)
            self.assertEqual(library.catalog(self.root, kind='product-announcement')['total'], 1)
            self.assertEqual(library.catalog(self.root, kind='how-to')['total'], 0)
            self.assertEqual(library.catalog(self.root, author='Avery')['total'], 1)
            with self.assertRaisesRegex(ValueError, 'role'):
                library.catalog(self.root, role='manuscript')
            # The Hub projection carries them to a second clone.
            wb.hub.refresh()
            shared = wa.state['items']['sources/' + saved['id']]
            local_id = wb.checkout_selected({'sources': [shared['item']]})['items'][0]['local_id']
            _, theirs = studio.item(other, 'sources', local_id)
            self.assertEqual(theirs['library']['kind'], 'product-announcement')
            self.assertEqual(theirs['library']['origin_kind'], 'upload')
            self.assertEqual(theirs['author'], 'Avery')
            # A link import says it came from a link, and a refresh keeps that.
            reader = Pages({'https://blog.example/team/one/': page('One', 'Avery')})
            shown = management.dispatch(
                self.root,
                'voice-links-preview',
                {'text': 'https://blog.example/team/one/\n', 'author': 'Avery'},
            )
            with patch.object(library, 'fetch', reader):
                result = management.dispatch(
                    self.root,
                    'voice-links-import',
                    {
                        'operation': 'b' * 32,
                        'text': 'https://blog.example/team/one/\n',
                        'author': 'Avery',
                        'expected': shown['expected'],
                    },
                )
            linked = result['results'][0]['id']
            _, record = studio.item(self.root, 'sources', linked)
            self.assertEqual(record['library']['origin_kind'], 'link')
            with patch.object(library, 'fetch', reader):
                again = management.dispatch(
                    self.root,
                    'voice-links-import',
                    {
                        'operation': 'b' * 32,
                        'text': 'https://blog.example/team/one/\n',
                        'author': 'Avery',
                        'expected': shown['expected'],
                        'retry': True,
                    },
                )
            self.assertEqual(again['counts']['samples'], 1)
            _, record = studio.item(self.root, 'sources', linked)
            self.assertEqual(record['library']['origin_kind'], 'link')
            self.assertEqual(library.catalog(self.root, author='Avery')['total'], 2)
            self.assertEqual(library.catalog(self.root, role='voice-sample')['total'], 1)

    def test_a_kind_must_be_a_known_style_before_anything_is_saved(self):
        with self.assertRaisesRegex(ValueError, 'kind of post'):
            self.upload('2', kind='no-such-style')
        self.assertFalse(list((self.root / 'sources').iterdir()))


class KeptFileTests(Fixture):
    """Task 3: a blog's files land in the team library with their role, author and kind."""

    def upload(self, operation, **extra):
        files = [
            {
                'filename': 'post.md',
                'content': base64.b64encode(b'An earlier post.').decode(),
                'purpose': 'inspiration',
            },
            {'filename': 'facts.md', 'content': base64.b64encode(b'The facts.').decode()},
        ]
        return management.dispatch(
            self.root,
            'upload',
            {
                'operation': operation * 32,
                'purpose': 'material',
                'analyze': False,
                'files': files,
                **extra,
            },
        )

    def test_kept_files_carry_role_author_and_kind_and_just_this_blog_stays_material(self):
        kept = self.upload('a', keep=True, author='Avery', kind='product-announcement')
        example, facts = (row['source']['id'] for row in kept['files'])
        for ident, purposes in ((example, ['reference', 'inspiration']), (facts, ['reference'])):
            _, record = studio.item(self.root, 'sources', ident)
            self.assertEqual(record['purposes'], purposes)
            self.assertEqual(record['author'], 'Avery')
            self.assertEqual(
                record['library'], {'kind': 'product-announcement', 'origin_kind': 'upload'}
            )
        rows = library.catalog(self.root, kind='product-announcement')['items']
        self.assertEqual({row['role'] for row in rows}, {'example', 'facts'})
        self.assertEqual(len(kept['receipts']), 2)
        # Unticked: just this blog. The files are material, outside the library.
        mine = self.upload('b', keep=False, author='Avery', kind='product-announcement')
        for row in mine['files']:
            _, record = studio.item(self.root, 'sources', row['source']['id'])
            self.assertIn('material', record['purposes'])
            self.assertNotIn('library', record)
        self.assertEqual(library.catalog(self.root)['total'], 2)
        with self.assertRaisesRegex(ValueError, 'kind of post'):
            self.upload('c', keep=True, kind='no-such-style')


class FinishTests(RunnerCase):
    """Task 2: Finish keeps the approved draft in the library, once per blog."""

    def finish(self, found, page=False):
        while found['next']:
            found = self.approve(self.submit(found, page=page), page=page)
        return found

    def kept(self):
        return [
            row
            for row in library.catalog(self.root)['items']
            if row['library'].get('origin_kind') == 'written-here'
        ]

    def test_finish_keeps_one_library_item_and_a_second_finish_updates_it(self):
        found = self.finish(self.create(style='product-announcement', author='Avery'))
        self.assertTrue(found['complete'])
        rows = self.kept()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(
            row['library'],
            {'kind': 'product-announcement', 'origin_kind': 'written-here', 'article': found['id']},
        )
        self.assertEqual(row['purposes'], ['reference', 'inspiration'])
        self.assertEqual(row['role'], 'example')
        self.assertEqual((row['title'], row['author']), ('Synthetic gateway guide', 'Avery'))
        self.assertEqual(row['kind_name'], 'Product announcement')
        directory, record = studio.item(self.root, 'sources', row['id'])
        draft = studio.inside(self.root, 'articles', found['id']) / 'DRAFT.md'
        self.assertEqual((directory / 'content.md').read_text(), draft.read_text())
        self.assertEqual(record['status'], 'ready')
        self.assertEqual(record['revision'], 1)
        self.assertEqual(record['origin'], found['id'])
        self.assertIn(row['id'], [s['id'] for s in runner.options(self.root)['sources']])
        self.assertIn('library', found['decisions'][-1]['event'])
        # Finishing again after a change updates the same item.
        found = runner.decide(
            self.root, found['id'], found['expected'], 'changes', 'Tighter.', target='draft'
        )
        found = self.submit(found, '# draft\nTighter synthetic writing.')
        found = self.finish(self.approve(found))
        rows = self.kept()
        self.assertEqual([r['id'] for r in rows], [row['id']])
        self.assertEqual(rows[0]['revision'], 2)
        _, record = studio.item(self.root, 'sources', row['id'])
        self.assertEqual(
            (directory / 'content.md').read_text(), '# draft\nTighter synthetic writing.'
        )
        self.assertEqual(
            studio.read_json(directory / 'revisions' / '1' / 'record.json')['revision'], 1
        )
        # The same draft finished again is not a new revision.
        found = runner.decide(
            self.root, found['id'], found['expected'], 'changes', 'Again.', target='package'
        )
        found = self.finish(found)
        self.assertEqual(self.kept()[0]['revision'], 2)
        # Deleting the blog keeps the library item, and restoring it keeps the link.
        management.dispatch(
            self.root,
            'blog-delete',
            {'id': found['id'], 'expected': found['expected'], 'title': found['title']},
        )
        self.assertEqual([r['id'] for r in self.kept()], [row['id']])
        management.dispatch(self.root, 'blog-restore', {'id': found['id']})
        self.assertEqual(library.written_here(self.root, found['id'])[1]['id'], row['id'])

    def test_a_stop_without_a_draft_keeps_nothing_and_a_draft_stop_keeps_the_draft(self):
        self.finish(self.create(mode='ideas'))
        self.assertEqual(self.kept(), [])
        found = self.finish(self.create(stop='draft'))
        self.assertEqual(found['stages'][-1]['stage'], 'draft')
        self.assertEqual(len(self.kept()), 1)
        self.assertNotIn('kind', self.kept()[0]['library'])

    def test_a_pinned_library_item_run_reads_it_with_its_role(self):
        self.finish(self.create())
        kept = self.kept()[0]
        again = self.create(title='The next one', sources=[kept['id']])
        _, payload, _ = runner.job(self.root, again['id'])
        self.assertEqual(payload['sources'], [], 'an example is not a citable source')
        self.assertEqual([e['name'] for e in payload['examples']], ['Synthetic gateway guide'])
        self.assertEqual(payload['examples'][0]['purposes'], ['reference', 'inspiration'])

    def test_a_team_workspace_shares_the_finished_blog(self):
        from hub_workspace import Workspace
        import hub_workspace

        provider = FakeProvider(self.base / 'remotes')
        registry = Registry(self.base / 'hubs', provider)
        ident = registry.create('fixture/finished', 'Finished')['hub']
        adapter = Workspace(self.root, registry.hub(ident))
        with patch.object(hub_workspace, 'active', return_value=adapter):
            found = self.finish(self.create(author='Avery'))
            graph = adapter.hub.graph()
        shared = [
            graph['revisions'][heads[0]]['data']['studio']
            for heads in graph['heads'].values()
            if graph['revisions'][heads[0]]['kind'] == 'source'
        ]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]['library']['article'], found['id'])
        self.assertEqual(shared[0]['library']['origin_kind'], 'written-here')
        self.assertEqual(shared[0]['purposes'], ['reference', 'inspiration'])
        self.assertEqual(shared[0]['author'], 'Avery')


if __name__ == '__main__':
    import unittest

    unittest.main()
