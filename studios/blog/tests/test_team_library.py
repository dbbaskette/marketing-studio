"""One team library: every item carries a role, a kind of post and where it came from."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import base64
from unittest.mock import patch

from hub_fixtures import FakeProvider
from hub import Registry
from hub_workspace import Workspace
from test_editorial_tools import Fixture
from test_voice_links import Pages, page
import blog_library as library
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


if __name__ == '__main__':
    import unittest

    unittest.main()
