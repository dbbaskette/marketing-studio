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
                'analyze': False,
                **extra,
            },
        )

    def test_fields_survive_a_revision_a_refresh_and_the_hub_projection(self):
        isolation.voices_on(self.root)  # These exercise the older voice tools.
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


SITE = 'https://blog.example/team/'
OTHER = 'https://other.example/blog/'
DOC = 'https://docs.google.com/document/d/1AbC_dEf-2gHiJkLmNoPqRsTuVwXyZ012345/edit'


def encoded_file(name, body):
    return {'filename': name, 'content': base64.b64encode(body).decode()}


class AddTests(RunnerCase):
    """Task 4: Add to library, in one sheet, with the author typed or each post's own."""

    class Docs:
        """The Google Docs API as the Doc reader sees it: one Doc, one tab."""

        def __init__(self, account=None):
            pass

        def native_read(self, file_id, inline=False, **_):
            return {
                'documentId': file_id,
                'revisionId': 'r1',
                'title': 'Messaging Doc',
                'tabs': [
                    {
                        'tabProperties': {'tabId': 't.0', 'title': 'Tab 1'},
                        'documentTab': {
                            'body': {
                                'content': [
                                    {'sectionBreak': {}},
                                    {
                                        'paragraph': {
                                            'paragraphStyle': {'namedStyleType': 'NORMAL_TEXT'},
                                            'elements': [
                                                {
                                                    'textRun': {
                                                        'content': 'The platform name is open.\n',
                                                        'textStyle': {},
                                                    }
                                                }
                                            ],
                                        }
                                    },
                                ]
                            }
                        },
                    }
                ],
            }

        def export(self, file_id, fmt):
            return b''

    def add(self, route, data, reader=None):
        import google_intake

        with (
            patch.object(library, 'fetch', reader or Pages({})),
            patch.object(google_intake.drive, 'Client', self.Docs),
            patch.object(library.time, 'sleep', lambda seconds: None),
        ):
            return management.dispatch(self.root, route, data)

    def test_files_a_doc_and_links_preview_then_land_with_role_author_and_kind(self):
        reader = Pages(
            {
                SITE + 'one/': page('One', 'Jordan Lee'),
                SITE + 'moved/': ValueError(library.OUT_OF_SCOPE),
            }
        )
        request = {
            'files': [
                encoded_file('post.html', page('An earlier post', 'Avery Quinn')),
                encoded_file('facts.md', b'The gateway retries twice.'),
                {'google': DOC},
            ],
            'links': '# links\n' + SITE + 'one/\n' + SITE + 'moved/\n',
            'role': 'example',
            'author': 'Avery Quinn',
            'kind': 'product-announcement',
        }
        shown = self.add('library-add-preview', request)
        self.assertEqual(shown['status'], 'ready')
        self.assertEqual(
            [(item['kind'], item['state']) for item in shown['items']],
            [
                ('file', 'ready'),
                ('file', 'ready'),
                ('google-doc', 'ready'),
                ('link', 'new'),
                ('link', 'new'),
            ],
        )
        self.assertEqual(shown['items'][0]['bylines'], ['Avery Quinn'])
        self.assertGreater(shown['items'][0]['chars'], 10)
        self.assertEqual(shown['items'][1]['chars'], len('The gateway retries twice.'))
        self.assertEqual(shown['items'][2]['title'], 'Messaging Doc')
        self.assertEqual(shown['items'][3]['site'], 'blog.example/team/')
        self.assertEqual(
            shown['sites'],
            [{'site': 'blog.example', 'scope': SITE, 'shown': 'blog.example/team/', 'links': 2}],
        )
        self.assertEqual((shown['to_fetch'], shown['in_library'], shown['comments']), (2, 0, 1))
        self.assertEqual(shown['kind_name'], 'Product announcement')
        self.assertFalse(list((self.root / 'sources').iterdir()), 'a check saves nothing')
        self.assertEqual(reader.calls, [])
        # Adding saves the files and the Doc, then fetches the links once each.
        data = {**request, 'operation': 'a' * 32, 'expected': shown['expected']}
        result = self.add('library-add', data, reader)
        self.assertEqual(result['state'], 'saved')
        self.assertEqual(
            result['counts'],
            {'imported': 4, 'in-library': 0, 'failed': 1, 'pending': 0, 'samples': 0},
        )
        rows = {row.get('filename') or row.get('url'): row for row in result['items']}
        self.assertEqual(rows[SITE + 'moved/']['status'], 'failed')
        self.assertIn('moved outside blog.example/team/', rows[SITE + 'moved/']['reason'])
        for key, origin in (
            ('post.html', 'upload'),
            ('facts.md', 'upload'),
            ('Messaging Doc', 'google-doc'),
            (SITE + 'one/', 'link'),
        ):
            directory, record = studio.item(self.root, 'sources', rows[key]['id'])
            self.assertEqual(record['purposes'], ['reference', 'inspiration'], key)
            self.assertEqual(record['author'], 'Avery Quinn', key)
            self.assertEqual(record['library']['kind'], 'product-announcement', key)
            self.assertEqual(record['library']['origin_kind'], origin, key)
            self.assertTrue((directory / 'content.md').is_file())
            self.assertEqual(rows[key]['role'], 'example')
        self.assertEqual(rows[SITE + 'one/']['title'], 'One')
        self.assertEqual([g['author'] for g in result['groups']], ['Avery Quinn'])
        self.assertEqual(result['groups'][0]['count'], 4)
        self.assertEqual(result['held'], [])
        self.assertEqual(len(reader.calls), 2)
        self.assertEqual(
            library.catalog(self.root, role='example', kind='product-announcement')['total'], 4
        )
        self.assertIn(
            'Links from blog.example/team/',
            [c['name'] for c in library.collections(self.root).values()],
        )
        # The same request again saves nothing twice and fetches nothing again.
        again = self.add('library-add', data, reader)
        self.assertEqual(
            [r.get('id') for r in again['items']], [r.get('id') for r in result['items']]
        )
        self.assertEqual(len(list((self.root / 'sources').iterdir())), 4)
        self.assertEqual(len(reader.calls), 2)
        # A post already in the library takes a new role in a new revision, not a copy.
        second = {'links': SITE + 'one/\n', 'role': 'facts', 'author': '', 'kind': ''}
        checked = self.add('library-add-preview', second)
        self.assertEqual(checked['items'][0]['state'], 'in-library')
        self.assertEqual(checked['items'][0]['bylines'], ['Avery Quinn'])
        kept = self.add(
            'library-add',
            {**second, 'operation': 'b' * 32, 'expected': checked['expected']},
            reader,
        )
        self.assertEqual(kept['items'][0]['status'], 'in-library')
        _, record = studio.item(self.root, 'sources', rows[SITE + 'one/']['id'])
        self.assertEqual(
            (record['revision'], record['purposes']), (1, ['reference', 'inspiration'])
        )
        self.assertEqual(len(reader.calls), 2)
        # Refusals, before anything is saved.
        refused = lambda pattern, **changes: self.assertRaisesRegex(ValueError, pattern)  # noqa: E731
        with refused('facts, approved messaging or an example'):
            self.add('library-add-preview', {**request, 'role': ''})
        with refused('changed since the check'):
            self.add('library-add', {**request, 'operation': 'c' * 32, 'expected': 'stale'})
        with refused('different add-to-library request'):
            self.add(
                'library-add', {**second, 'operation': 'a' * 32, 'expected': checked['expected']}
            )
        with refused('kind of post'):
            self.add('library-add-preview', {**request, 'kind': 'no-such-style'})
        with refused('docs.google.com/document'):
            self.add(
                'library-add-preview',
                {'files': [{'google': 'https://example.com/doc'}], 'role': 'facts'},
            )
        with refused('could not be read'):
            self.add(
                'library-add-preview',
                {'files': [encoded_file('bad.docx', b'not a zip')], 'role': 'facts'},
            )
        with patch.object(library, 'MAX_BINARY', 8), refused('at most 10 MiB'):
            self.add(
                'library-add-preview',
                {'files': [encoded_file('big.md', b'x' * 9)], 'role': 'facts'},
            )
        with refused('Choose files, paste links'):
            self.add('library-add-preview', {'role': 'facts', 'links': '  '})
        with refused('No usable links'):
            self.add('library-add-preview', {'role': 'facts', 'links': 'not a link'})
        self.assertEqual(len(list((self.root / 'sources').iterdir())), 4)

    def test_a_failed_link_is_fetched_again_when_asked_and_only_then(self):
        request = {
            'links': SITE + 'one/\n' + SITE + 'two/\n',
            'role': 'facts',
            'author': 'Jordan Lee',
            'kind': '',
        }
        failing = Pages({SITE + 'one/': page('One', 'Jordan Lee')})  # two/ answers 404
        shown = self.add('library-add-preview', request)
        data = {**request, 'operation': 'c' * 32, 'expected': shown['expected']}
        first = self.add('library-add', data, failing)
        self.assertEqual((first['counts']['imported'], first['counts']['failed']), (1, 1))
        self.assertIn('Try the failed links again', first['next_step'])
        fixed = Pages(
            {SITE + 'one/': page('One', 'Jordan Lee'), SITE + 'two/': page('Two', 'Jordan Lee')}
        )
        # The same list checked again keeps its operation: a plain repeat fetches nothing.
        shown = self.add('library-add-preview', request)
        self.assertEqual(shown['expected'], data['expected'])
        self.assertEqual(self.add('library-add', data, fixed)['counts']['failed'], 1)
        self.assertEqual(fixed.calls, [])
        # Asking to retry fetches the failed link once more, and nothing else.
        again = self.add('library-add', {**data, 'retry': True}, fixed)
        self.assertEqual([call[0] for call in fixed.calls], [SITE + 'two/'])
        self.assertEqual((again['counts']['imported'], again['counts']['failed']), (2, 0))
        two = next(row for row in again['items'] if row['url'] == SITE + 'two/')
        self.assertEqual((two['title'], two['author']), ('Two', 'Jordan Lee'))
        with self.assertRaisesRegex(ValueError, 'retry'):
            self.add('library-add', {**data, 'retry': 'yes'}, fixed)

    def test_organisation_bylines_from_meta_or_a_byline_class_are_held(self):
        reader = Pages(
            {
                SITE + 'meta/': (
                    b'<html><head><title>Meta</title><meta property="og:site_name" '
                    b'content="Example Publishing"><meta name="author" content="Example Publishing">'
                    b'</head><body><p>The company speaks.</p></body></html>'
                ),
                SITE + 'team/': page('Team', 'The Example Team', 'byline'),
                SITE + 'person/': page('Person', 'Avery Quinn', 'meta'),
            }
        )
        request = {
            'links': SITE + 'meta/\n' + SITE + 'team/\n' + SITE + 'person/\n',
            'role': 'facts',
            'author': '*each',
            'kind': '',
        }
        shown = self.add('library-add-preview', request)
        result = self.add(
            'library-add', {**request, 'operation': 'e' * 32, 'expected': shown['expected']}, reader
        )
        self.assertEqual(
            [(g['author'], g['count']) for g in result['groups']], [('Avery Quinn', 1)]
        )
        reasons = {h['url']: h['reason'] for h in result['held']}
        self.assertEqual(
            reasons,
            {
                SITE + 'meta/': 'The byline is an organisation, Example Publishing, not a person.',
                SITE + 'team/': 'The byline is an organisation, The Example Team, not a person.',
            },
        )

    def test_a_voice_sample_only_item_is_listed_as_a_voice_sample(self):
        sample = self.command(
            'source',
            'add',
            '--name',
            'Sample',
            '--file',
            str(self._file('Words.')),
            '--purpose',
            'voice-sample',
            '--author',
            'Avery',
        )
        rows = {row['id']: row for row in library.catalog(self.root)['items']}
        self.assertEqual(rows[sample['id']]['role'], 'voice-sample')
        self.assertEqual(library.catalog(self.root, role='facts')['total'], 0)
        self.assertEqual(library.catalog(self.root, role='voice-sample')['total'], 1)

    def _file(self, words):
        self.file.write_text(words)
        return self.file

    def test_each_posts_own_author_imports_first_then_groups_by_byline(self):
        isolation.voices_on(self.root)  # These exercise the older voice tools.
        coauthored = (
            b'<html><head><title>Co</title><script type="application/ld+json">{"author":[{"name":"Avery Quinn"},'
            b'{"name":"Jordan Lee"}]}</script></head><body><p>Two voices wrote this.</p></body></html>'
        )
        organisation = (
            b'<html><head><title>Org</title><script type="application/ld+json">{"author":{"@type":"Organization",'
            b'"name":"Example Publishing"}}</script></head><body><p>The company speaks.</p></body></html>'
        )
        reader = Pages(
            {
                SITE + 'a/': page('A', 'Darin Zook'),
                SITE + 'b/': page('B', 'Zook, Darin', 'meta'),
                SITE + 'c/': page('C', 'Sam Rivera', 'byline'),
                SITE + 'org/': organisation,
                SITE + 'co/': coauthored,
                SITE + 'none/': page('None'),
                OTHER + 'x/': page('X', 'Darin Zook'),
            }
        )
        request = {
            'links': ''.join(SITE + n + '/\n' for n in ('a', 'b', 'c', 'org', 'co', 'none'))
            + OTHER
            + 'x/\n',
            'role': 'facts',
            'author': '*each',
            'kind': '',
        }
        shown = self.add('library-add-preview', request)
        self.assertEqual(
            [s['site'] for s in shown['sites']],
            ['blog.example', 'other.example'],
            'every site is imported, each in its own scope',
        )
        self.assertEqual(shown['to_fetch'], 7)
        result = self.add(
            'library-add', {**request, 'operation': 'd' * 32, 'expected': shown['expected']}, reader
        )
        self.assertEqual({call[1] for call in reader.calls if call[0].startswith(SITE)}, {SITE})
        self.assertEqual({call[1] for call in reader.calls if call[0].startswith(OTHER)}, {OTHER})
        self.assertEqual(result['counts']['imported'], 7)
        rows = {row['url']: row for row in result['items']}
        _, b = studio.item(self.root, 'sources', rows[SITE + 'b/']['id'])
        self.assertEqual((b['author'], b['library']['author']), ('Zook, Darin', 'Zook, Darin'))
        self.assertEqual(b['purposes'], ['reference'])
        self.assertEqual(b['library']['origin_kind'], 'link')
        _, co = studio.item(self.root, 'sources', rows[SITE + 'co/']['id'])
        self.assertIsNone(co['author'])
        self.assertEqual(co['library']['bylines'], ['Avery Quinn', 'Jordan Lee'])
        # Grouped by author, variants folded; held posts are counted for nobody.
        self.assertEqual(
            [(g['author'], g['count']) for g in result['groups']],
            [('Darin Zook', 3), ('Sam Rivera', 1)],
        )
        self.assertEqual(
            sorted(h['url'] for h in result['held']),
            sorted(SITE + n + '/' for n in ('org', 'co', 'none')),
        )
        reasons = {h['url']: h['reason'] for h in result['held']}
        self.assertEqual(reasons[SITE + 'co/'], 'Several bylines: Avery Quinn, Jordan Lee')
        self.assertEqual(
            reasons[SITE + 'org/'],
            'The byline is an organisation, Example Publishing, not a person.',
        )
        self.assertEqual(reasons[SITE + 'none/'], 'No byline on the page.')
        self.assertEqual(result['groups'][0]['samples'], [])
        self.assertIn('Mark the posts as voice samples', result['next_step'])
        # Rename a group; merge a group into another; set the author of a held post.
        sam = result['groups'][1]['ids']
        renamed = management.dispatch(
            self.root,
            'library-add-author',
            {'operation': 'd' * 32, 'ids': sam, 'author': 'Samantha Rivera'},
        )
        self.assertEqual(
            [(g['author'], g['count']) for g in renamed['groups']],
            [('Darin Zook', 3), ('Samantha Rivera', 1)],
        )
        _, c = studio.item(self.root, 'sources', sam[0])
        self.assertEqual(
            (c['author'], c['library']['author'], c['revision']),
            ('Samantha Rivera', 'Sam Rivera', 2),
        )
        merged = management.dispatch(
            self.root,
            'library-add-author',
            {'operation': 'd' * 32, 'ids': sam, 'author': 'Darin Zook'},
        )
        self.assertEqual([(g['author'], g['count']) for g in merged['groups']], [('Darin Zook', 4)])
        held = next(h['id'] for h in merged['held'] if h['url'] == SITE + 'none/')
        named = management.dispatch(
            self.root,
            'library-add-author',
            {'operation': 'd' * 32, 'ids': [held], 'author': 'Casey Park'},
        )
        self.assertEqual(
            [(g['author'], g['count']) for g in named['groups']],
            [('Darin Zook', 4), ('Casey Park', 1)],
        )
        self.assertEqual(len(named['held']), 2)
        with self.assertRaisesRegex(ValueError, 'this add-to-library operation saved'):
            management.dispatch(
                self.root,
                'library-add-author',
                {'operation': 'd' * 32, 'ids': ['elsewhere'], 'author': 'X'},
            )
        # A run that pinned one of the posts stays open when it becomes a sample.
        found = self.create(sources=[rows[SITE + 'a/']['id']])
        before = runner.survey(self.root, found['id'])
        marked = management.dispatch(self.root, 'library-add-samples', {'operation': 'd' * 32})
        self.assertEqual([len(g['samples']) for g in marked['groups']], [4, 1])
        self.assertEqual(marked['groups'][0]['learnable'], marked['groups'][0]['samples'])
        import voice_links

        for ident in marked['groups'][0]['ids']:
            _, record = studio.item(self.root, 'sources', ident)
            self.assertIn('voice-sample', record['purposes'])
            # A folded variant keeps its own byline on the record; the group names the voice.
            self.assertTrue(voice_links.same_author(record['author'], 'Darin Zook'))
        _, a = studio.item(self.root, 'sources', rows[SITE + 'a/']['id'])
        self.assertEqual(a['revision'], 2)
        for ident in (h['id'] for h in marked['held']):
            self.assertNotIn(
                'voice-sample', studio.item(self.root, 'sources', ident)[1]['purposes']
            )
        after = runner.survey(self.root, found['id'])
        self.assertEqual(
            (after['stages'], after['expected']), (before['stages'], before['expected'])
        )
        self.assertEqual(
            management.dispatch(self.root, 'library-add-samples', {'operation': 'd' * 32})[
                'changed'
            ],
            [],
            'marking again changes nothing',
        )
        self.assertIn('Learn a voice from a group', marked['next_step'])
        # Learning still asks before any analysis.
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            management.dispatch(
                self.root,
                'tool-action',
                {
                    'action': 'job-create',
                    'kind': 'voice-learn',
                    'operation': 'e' * 32,
                    'name': 'Darin Zook',
                    'samples': marked['groups'][0]['learnable'],
                },
            )


class SelectionTests(RunnerCase):
    """Task 5: the library screen filters, and acts on a selection."""

    def setUp(self):
        super().setUp()
        isolation.voices_on(self.root)  # These exercise the older voice tools.

    def items(self, *names, author=None, operation='a'):
        result = management.dispatch(
            self.root,
            'upload',
            {
                'operation': operation * 32,
                'purpose': 'material',
                'keep': True,
                'analyze': False,
                'files': [encoded_file(name, b'Words about ' + name.encode()) for name in names],
                **({'author': author} if author else {}),
            },
        )
        return [row['source']['id'] for row in result['files']]

    def disk(self):
        return {
            path.relative_to(self.root): path.read_bytes()
            for path in (self.root / 'sources').rglob('*')
            if path.is_file()
        }

    def test_a_learn_selection_takes_twenty_readable_items_and_names_the_rest(self):
        # An upload takes at most twenty files, so the twenty-one posts go up in two.
        ready = self.items(*['post%d.md' % n for n in range(20)], author='Avery') + self.items(
            'post20.md', author='Avery', operation='8'
        )
        with patch.object(library.shutil, 'which', return_value=None):
            scan = self.items('scan.pdf', author='Avery', operation='9')
        result = management.dispatch(
            self.root, 'library-selection', {'action': 'style-learn', 'ids': scan + ready}
        )
        self.assertEqual([c['id'] for c in result['candidates']], ready[:20])
        self.assertEqual(result['left_out'], [{'id': ready[20], 'name': 'post20'}])
        self.assertEqual(
            result['skipped'],
            [{'id': scan[0], 'name': 'scan', 'reason': 'It has no readable text yet.'}],
        )
        with self.assertRaisesRegex(ValueError, 'readable text'):
            management.dispatch(
                self.root, 'library-selection', {'action': 'voice-learn', 'ids': scan}
            )

    def test_the_view_names_the_kinds_and_filters_by_role_kind_and_author(self):
        self.items('one.md', author='Avery')
        shown = management.view(self.root, 'library', {})
        self.assertIn(
            {'id': 'product-announcement', 'name': 'Product announcement'}, shown['kinds']
        )
        self.assertEqual(shown['total'], 1)
        self.assertEqual(management.view(self.root, 'library', {'role': ['example']})['total'], 0)
        self.assertEqual(management.view(self.root, 'library', {'role': ['facts']})['total'], 1)
        self.assertEqual(management.view(self.root, 'library', {'author': ['Avery']})['total'], 1)
        self.assertEqual(management.view(self.root, 'library', {'kind': ['how-to']})['total'], 0)

    def test_a_selection_learns_a_style_a_voice_or_starts_a_blog(self):
        mine = self.items('one.md', 'two.md', author='Avery')
        theirs = self.items('three.md', author='Jordan', operation='b')
        unnamed = self.items('four.md', operation='c')
        act = lambda **data: management.dispatch(self.root, 'library-selection', data)  # noqa: E731
        before = self.disk()
        # Learning offers the items as candidates; nothing is marked or shared yet.
        styled = act(action='style-learn', ids=mine + theirs)
        self.assertEqual([c['id'] for c in styled['candidates']], mine + theirs)
        self.assertEqual(styled['candidates'][0], {'id': mine[0], 'name': 'one', 'author': 'Avery'})
        with self.assertRaisesRegex(ValueError, 'more than one author'):
            act(action='voice-learn', ids=mine + theirs)
        with self.assertRaisesRegex(ValueError, 'whose writing'):
            act(action='voice-learn', ids=unnamed)
        with self.assertRaisesRegex(ValueError, 'whose writing'):
            act(action='voice-learn', ids=mine + unnamed)  # never Avery's name for another item
        voiced = act(action='voice-learn', ids=mine + unnamed, author='Avery')
        self.assertEqual([c['id'] for c in voiced['candidates']], mine + unnamed)
        self.assertEqual(voiced['author'], 'Avery')
        with self.assertRaisesRegex(ValueError, 'more than one author'):
            act(action='voice-learn', ids=mine, author='Jordan')
        self.assertEqual(act(action='voice-learn', ids=mine)['author'], 'Avery', 'from the items')
        self.assertEqual(self.disk(), before, 'nothing changes on disk before confirmation')
        # The learn job marks them when its permission is confirmed, and only then.
        job = lambda **data: management.dispatch(
            self.root, 'tool-action', {'action': 'job-create', 'mark': True, **data}
        )  # noqa: E731
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            job(kind='voice-learn', operation='1' * 32, name='Avery', samples=mine + unnamed)
        with self.assertRaisesRegex(ValueError, 'is by Jordan'):
            job(
                kind='voice-learn',
                operation='2' * 32,
                name='Avery',
                samples=mine + theirs,
                confirmed=True,
            )
        self.assertEqual(self.disk(), before, 'a refused job marks nothing')
        started = job(
            kind='voice-learn',
            operation='3' * 32,
            name='Avery',
            samples=mine + unnamed,
            confirmed=True,
        )
        self.assertEqual(started['kind'], 'voice-learn')
        for ident in mine + unnamed:
            _, record = studio.item(self.root, 'sources', ident)
            self.assertEqual(
                (record['author'], record['purposes'], record['revision']),
                ('Avery', ['reference', 'voice-sample'], 2),
            )
        job(kind='style-learn', operation='4' * 32, name='Notes', samples=theirs, confirmed=True)
        _, record = studio.item(self.root, 'sources', theirs[0])
        self.assertEqual(
            (record['author'], record['purposes']), ('Jordan', ['reference', 'style-sample'])
        )
        with self.assertRaisesRegex(ValueError, 'voice-sample'):
            management.dispatch(
                self.root,
                'tool-action',
                {
                    'action': 'job-create',
                    'kind': 'voice-learn',
                    'operation': '5' * 32,
                    'name': 'Jordan',
                    'samples': theirs,
                    'confirmed': True,
                },
            )
        blog = act(action='blog', ids=mine)
        self.assertEqual(
            blog['files'],
            [
                {
                    'id': ident,
                    'filename': name,
                    'state': 'ready',
                    'chars': len('Words about ' + name + '.md'),
                    'role': 'inspiration',
                    'library': True,
                }
                for ident, name in zip(mine, ('one', 'two'), strict=True)
            ],
        )
        with self.assertRaisesRegex(ValueError, 'library action'):
            act(action='delete', ids=mine)
        with self.assertRaisesRegex(ValueError, 'one to fifty'):
            act(action='blog', ids=[])
        material = management.dispatch(
            self.root,
            'upload',
            {
                'operation': 'd' * 32,
                'purpose': 'material',
                'analyze': False,
                'files': [encoded_file('m.md', b'Mine.')],
            },
        )['files'][0]['source']['id']
        with self.assertRaisesRegex(ValueError, 'not a library item'):
            act(action='blog', ids=[material])

    def test_select_all_matching_returns_every_match_and_a_learn_selection_takes_more(self):
        ones = self.items(*['a%d.md' % n for n in range(20)], author='Avery')
        twos = self.items(*['b%d.md' % n for n in range(20)], author='Avery', operation='b')
        threes = self.items(*['c%d.md' % n for n in range(20)], author='Avery', operation='c')
        jordan = self.items('j.md', author='Jordan', operation='d')
        everything = management.view(self.root, 'library-matching', {})
        self.assertEqual(everything['total'], 61, 'more than one page of fifty')
        self.assertEqual(
            sorted(row['id'] for row in everything['items']), sorted(ones + twos + threes + jordan)
        )
        self.assertEqual({row['location'] for row in everything['items']}, {'local'})
        self.assertFalse(everything['capped'])
        filtered = management.view(self.root, 'library-matching', {'author': ['Jordan']})
        self.assertEqual([row['id'] for row in filtered['items']], jordan)
        # More than fifty ticked can still be learned from; the first twenty are read.
        many = [row['id'] for row in everything['items']]
        learned = management.dispatch(
            self.root, 'library-selection', {'action': 'style-learn', 'ids': many}
        )
        self.assertEqual(len(learned['candidates']), 20)
        self.assertEqual(len(learned['left_out']), 41)
        with self.assertRaisesRegex(ValueError, 'one to fifty'):
            management.dispatch(
                self.root, 'library-selection', {'action': 'blog', 'ids': many[:51]}
            )


class VoicesForEveryAuthorTests(RunnerCase):
    """Create voices for every author: one learning job per ticked author, confirmed once."""

    def setUp(self):
        super().setUp()
        isolation.voices_on(self.root)  # These exercise the older voice tools.

    items = SelectionTests.items

    def jobs(self):
        folder = self.root / '.blog-runs' / 'tools'
        return sorted(path.stem for path in folder.glob('*.json')) if folder.is_dir() else []

    def test_authors_are_listed_with_counts_and_two_readable_posts_make_a_voice(self):
        self.items('one.md', 'two.md', 'three.md', author='Avery Quinn')
        self.items('solo.md', author='Jordan Lee', operation='b')
        self.items('nobody.md', operation='c')
        with patch.object(library.shutil, 'which', return_value=None):
            self.items('scan.pdf', author='Avery Quinn', operation='d')
        found = management.view(self.root, 'library-authors', {})
        self.assertEqual(found['unnamed'], 1)
        self.assertEqual(found['minimum'], 2)
        avery, jordan = found['authors']
        self.assertEqual(
            (avery['author'], avery['posts'], avery['readable'], avery['ready'], avery['reason']),
            ('Avery Quinn', 4, 3, True, ''),
            'a scan without text is not readable',
        )
        self.assertEqual(len(avery['samples']), 3)
        self.assertIsNone(avery['profile'])
        self.assertEqual((jordan['author'], jordan['ready']), ('Jordan Lee', False))
        self.assertEqual(jordan['reason'], 'Only 1 readable post; a voice needs at least 2.')

    def test_one_confirmation_queues_one_job_per_author_and_updates_an_existing_voice(self):
        avery = self.items('one.md', 'two.md', author='Avery Quinn')
        sam = self.items('s1.md', 's2.md', 's3.md', author='Sam Rivera', operation='b')
        self.items('solo.md', author='Jordan Lee', operation='c')
        self.file.write_text('Short direct sentences.')
        existing = self.command(
            'profile',
            'create',
            '--name',
            'Sam Rivera',
            '--guide-file',
            str(self.file),
            '--status',
            'confirmed',
        )
        listed = {
            row['author']: row
            for row in management.view(self.root, 'library-authors', {})['authors']
        }
        self.assertEqual(listed['Sam Rivera']['profile']['id'], existing['id'])
        create = lambda **data: management.dispatch(self.root, 'library-voices', data)  # noqa: E731
        before = self.jobs()
        with self.assertRaisesRegex(ValueError, 'permission'):
            create(operation='a' * 32, authors=['Avery Quinn', 'Sam Rivera'])
        with self.assertRaisesRegex(ValueError, 'Jordan Lee: Only 1 readable post'):
            create(operation='a' * 32, authors=['Avery Quinn', 'Jordan Lee'], confirmed=True)
        self.assertEqual(self.jobs(), before, 'a refusal queues nothing')
        for ident in avery:
            self.assertNotIn(
                'voice-sample',
                studio.item(self.root, 'sources', ident)[1]['purposes'],
                'and marks nothing',
            )
        result = create(operation='a' * 32, authors=['Avery Quinn', 'Sam Rivera'], confirmed=True)
        self.assertEqual([row['author'] for row in result['jobs']], ['Avery Quinn', 'Sam Rivera'])
        self.assertEqual(len(self.jobs()), 2, 'one job per ticked author')
        first, second = result['jobs']
        self.assertEqual((first['update'], first['samples']), (False, 2))
        self.assertEqual((second['update'], second['profile']['id']), (True, existing['id']))
        for row in result['jobs']:
            self.assertEqual((row['job']['kind'], row['job']['status']), ('voice-learn', 'queued'))
        import tool_jobs

        saved = tool_jobs.read(self.root, second['job']['id'])
        self.assertEqual(saved['metadata']['profile'], existing['id'], 'an update, not a new voice')
        self.assertEqual(sorted(saved['metadata']['samples']), sorted(sam))
        self.assertIsNone(tool_jobs.read(self.root, first['job']['id'])['metadata']['profile'])
        for ident in avery + sam:
            self.assertIn('voice-sample', studio.item(self.root, 'sources', ident)[1]['purposes'])
        again = create(operation='a' * 32, authors=['Avery Quinn', 'Sam Rivera'], confirmed=True)
        self.assertEqual(
            [row['job']['id'] for row in again['jobs']],
            [row['job']['id'] for row in result['jobs']],
            'sending the batch again returns the same jobs',
        )
        self.assertEqual(len(self.jobs()), 2)
        self.assertEqual(again['failed'], [])

    def test_another_batch_reuses_an_authors_queued_job(self):
        self.items('a1.md', 'a2.md', author='Avery Quinn')
        self.items('s1.md', 's2.md', author='Sam Rivera', operation='b')
        create = lambda op, names: management.dispatch(  # noqa: E731
            self.root, 'library-voices', {'operation': op * 32, 'authors': names, 'confirmed': True}
        )
        first = create('a', ['Avery Quinn'])
        second = create('c', ['Avery Quinn', 'Sam Rivera'])
        self.assertEqual(len(self.jobs()), 2, 'one new job, for Sam Rivera only')
        avery, sam = second['jobs']
        self.assertEqual(avery['job']['id'], first['jobs'][0]['job']['id'])
        self.assertTrue(avery['already'], 'the queued job is shown, not doubled')
        self.assertFalse(sam['already'])
        import tool_jobs

        saved = tool_jobs.read(self.root, avery['job']['id'])
        saved['status'] = 'ready'
        tool_jobs.write(self.root, saved)
        third = create('d', ['Avery Quinn'])
        self.assertFalse(
            third['jobs'][0]['already'], 'a finished learning does not hold back a new one'
        )
        self.assertEqual(len(self.jobs()), 3)

    def test_the_newest_first_order_keeps_a_hub_items_place_after_checkout(self):
        import library_add

        record = {'library': {'published': '2026-01-01'}, 'retrieved_at': 't'}
        shared = {
            'id': 'hub-item',
            'location': 'hub',
            'record': record,
            'binding': {'item': 'hub-item'},
        }
        local = {
            'id': 'local-1',
            'location': 'local',
            'record': record,
            'binding': {'item': 'hub-item', 'revision': 'r'},
        }
        plain = {'id': 'local-2', 'location': 'local', 'record': record, 'binding': {}}
        self.assertEqual(library_add._newest(shared), library_add._newest(local))
        self.assertEqual(library_add._newest(plain)[-1], 'local-2')

    def big(self, names, author, operation):
        """Posts longer than a learning job reads, each about 250,000 characters."""
        result = management.dispatch(
            self.root,
            'upload',
            {
                'operation': operation * 32,
                'purpose': 'material',
                'keep': True,
                'analyze': False,
                'author': author,
                'files': [encoded_file(name, ('word ' * 50_000).encode()) for name in names],
            },
        )
        return [row['source']['id'] for row in result['files']]

    def purposes(self, idents):
        return [studio.item(self.root, 'sources', ident)[1]['purposes'] for ident in idents]

    def test_a_refusal_for_any_author_queues_nothing_and_marks_nothing(self):
        avery = self.items('a1.md', 'a2.md', author='Avery Quinn')
        bob = self.big(['b1.md', 'b2.md'], 'Bob Stone', 'b')
        before = self.purposes(avery + bob)
        with self.assertRaisesRegex(ValueError, 'Bob Stone: Use shorter authored voice samples'):
            management.dispatch(
                self.root,
                'library-voices',
                {'operation': 'c' * 32, 'authors': ['Avery Quinn', 'Bob Stone'], 'confirmed': True},
            )
        self.assertEqual(self.jobs(), [], 'not even the author checked first is queued')
        self.assertEqual(self.purposes(avery + bob), before, 'and nobody’s posts are marked')

    def test_one_voice_from_the_library_marks_nothing_when_its_learning_is_refused(self):
        bob = self.big(['b1.md', 'b2.md'], 'Bob Stone', 'b')
        before = self.purposes(bob)
        with self.assertRaisesRegex(ValueError, 'shorter authored voice samples'):
            management.dispatch(
                self.root,
                'tool-action',
                {
                    'action': 'job-create',
                    'kind': 'voice-learn',
                    'operation': 'd' * 32,
                    'name': 'Bob Stone',
                    'samples': bob,
                    'confirmed': True,
                    'mark': True,
                },
            )
        self.assertEqual((self.jobs(), self.purposes(bob)), ([], before))

    def test_a_failure_after_the_checks_says_which_authors_were_queued(self):
        self.items('a1.md', 'a2.md', author='Avery Quinn')
        self.items('s1.md', 's2.md', author='Sam Rivera', operation='b')
        import article_tools

        real = article_tools.request

        def flaky(root, data):
            if data['name'] == 'Sam Rivera':
                raise OSError('The disk is full.')
            return real(root, data)

        with patch.object(article_tools, 'request', flaky):
            result = management.dispatch(
                self.root,
                'library-voices',
                {
                    'operation': 'e' * 32,
                    'authors': ['Avery Quinn', 'Sam Rivera'],
                    'confirmed': True,
                },
            )
        self.assertEqual([row['author'] for row in result['jobs']], ['Avery Quinn'])
        self.assertEqual(
            result['failed'], [{'author': 'Sam Rivera', 'reason': 'The disk is full.'}]
        )
        self.assertEqual(len(self.jobs()), 1)

    def test_authors_group_and_match_voices_only_by_their_exact_name(self):
        self.items('d1.md', author='Dan', operation='d')
        smith = self.items('s1.md', author='Dan Smith', operation='e') + self.items(
            's2.md', author='  dan   SMITH ', operation='f'
        )
        self.file.write_text('Short direct sentences.')
        self.command(
            'profile',
            'create',
            '--name',
            'Dan Baskette',
            '--guide-file',
            str(self.file),
            '--status',
            'confirmed',
        )
        groups = management.view(self.root, 'library-authors', {})['authors']
        self.assertEqual(
            [(g['author'], g['posts'], g['profile']) for g in groups],
            [('Dan Smith', 2, None), ('Dan', 1, None)],
            'a first name is not someone else’s full name, and no voice matches by a part of it',
        )
        result = management.dispatch(
            self.root,
            'library-voices',
            {'operation': 'f' * 32, 'authors': ['Dan Smith'], 'confirmed': True},
        )
        import tool_jobs

        saved = tool_jobs.read(self.root, result['jobs'][0]['job']['id'])
        self.assertEqual(
            (saved['metadata']['name'], saved['metadata']['profile']), ('Dan Smith', None)
        )
        self.assertEqual(sorted(saved['metadata']['samples']), sorted(smith))
        with self.assertRaisesRegex(ValueError, 'Dan: Only 1 readable post'):
            management.dispatch(
                self.root,
                'library-voices',
                {'operation': '9' * 32, 'authors': ['Dan'], 'confirmed': True},
            )

    def test_a_batch_names_at_most_the_limit_of_authors(self):
        import library_add

        names = ['Author %d' % n for n in range(library_add.AUTHOR_BATCH_LIMIT + 1)]
        with self.assertRaisesRegex(
            ValueError, 'at most %d authors' % library_add.AUTHOR_BATCH_LIMIT
        ):
            management.dispatch(
                self.root,
                'library-voices',
                {'operation': 'a' * 32, 'authors': names, 'confirmed': True},
            )
        self.assertEqual(
            management.view(self.root, 'library-authors', {})['batch_limit'],
            library_add.AUTHOR_BATCH_LIMIT,
            'the page is told the same limit',
        )


class AuthorClarifyTests(RunnerCase):
    """Names that might be one person are suggested, never merged; the person decides."""

    items = SelectionTests.items

    def setUp(self):
        super().setUp()
        isolation.voices_on(self.root)  # These exercise the older voice tools.
        self.dan = self.items('d1.md', author='Dan', operation='d')
        self.smith = self.items('s1.md', 's2.md', author='Dan Smith', operation='e')
        self.file.write_text('Short direct sentences.')
        self.command(
            'profile',
            'create',
            '--name',
            'Dan Baskette',
            '--guide-file',
            str(self.file),
            '--status',
            'confirmed',
        )

    def groups(self):
        return {
            g['author']: g for g in management.view(self.root, 'library-authors', {})['authors']
        }

    def record(self, ident):
        return studio.item(self.root, 'sources', ident)[1]

    def test_a_short_name_suggests_every_fuller_name_and_voice(self):
        groups = self.groups()
        self.assertEqual(
            [s['name'] for s in groups['Dan']['suggestions']], ['Dan Smith', 'Dan Baskette']
        )
        self.assertEqual(
            [(s['posts'], bool(s['voice'])) for s in groups['Dan']['suggestions']],
            [(2, False), (0, True)],
        )
        self.assertFalse(groups['Dan']['ready'], 'a group too small to learn alone still shows')
        self.assertEqual(groups['Dan Smith']['suggestions'], [], 'a fuller name suggests nothing')
        self.assertEqual(self.record(self.dan[0])['author'], 'Dan', 'a suggestion changes nothing')

    def test_same_person_names_the_posts_by_the_fuller_name_explicitly(self):
        expected = self.groups()['Dan']['expected']
        result = management.dispatch(
            self.root,
            'library-author-same',
            {'author': 'Dan', 'into': 'Dan Smith', 'expected': expected},
        )
        groups = {g['author']: g for g in result['authors']}
        self.assertNotIn('Dan', groups)
        self.assertEqual((groups['Dan Smith']['posts'], groups['Dan Smith']['ready']), (3, True))
        record = self.record(self.dan[0])
        self.assertEqual((record['author'], record['revision']), ('Dan Smith', 2))
        self.assertIn('author', record['curation_overrides'])
        self.assertTrue(
            (self.root / 'sources' / self.dan[0] / 'revisions' / '1' / 'record.json').is_file(),
            'the earlier author is kept in the item’s history',
        )
        # The single-voice path reads the corrected author too.
        candidates = management.view(self.root, 'voices', {})['candidates']
        self.assertIn(('d1', 'Dan Smith'), [(c['name'], c.get('author')) for c in candidates])

    def test_a_voice_name_can_take_the_posts_and_other_names_are_refused(self):
        expected = self.groups()['Dan']['expected']
        with self.assertRaisesRegex(ValueError, 'one of the suggested'):
            management.dispatch(
                self.root,
                'library-author-same',
                {'author': 'Dan', 'into': 'Zed Ray', 'expected': expected},
            )
        result = management.dispatch(
            self.root,
            'library-author-same',
            {'author': 'Dan', 'into': 'Dan Baskette', 'expected': expected},
        )
        group = {g['author']: g for g in result['authors']}['Dan Baskette']
        self.assertEqual(group['profile']['name'], 'Dan Baskette', 'and it now meets its voice')

    def test_a_stale_choice_is_refused_and_changes_nothing(self):
        expected = self.groups()['Dan']['expected']
        self.items('d2.md', author='Dan', operation='f')  # Another post arrives meanwhile.
        with self.assertRaisesRegex(management.CurationConflict, 'changed'):
            management.dispatch(
                self.root,
                'library-author-same',
                {'author': 'Dan', 'into': 'Dan Smith', 'expected': expected},
            )
        self.assertEqual(self.record(self.dan[0])['author'], 'Dan')

    def test_different_person_is_remembered_and_keeps_the_groups_apart(self):
        with self.assertRaisesRegex(ValueError, 'Zed Ray is not suggested'):
            management.dispatch(
                self.root,
                'library-author-different',
                {'author': 'Dan', 'others': ['Dan Smith', 'Zed Ray']},
            )
        self.assertEqual(
            [s['name'] for s in self.groups()['Dan']['suggestions']],
            ['Dan Smith', 'Dan Baskette'],
            'a refused request saves no pair at all',
        )
        result = management.dispatch(
            self.root, 'library-author-different', {'author': 'Dan', 'others': ['Dan Smith']}
        )
        groups = {g['author']: g for g in result['authors']}
        self.assertEqual([s['name'] for s in groups['Dan']['suggestions']], ['Dan Baskette'])
        self.assertEqual(
            [s['name'] for s in self.groups()['Dan']['suggestions']],
            ['Dan Baskette'],
            'the choice holds for later reads',
        )
        self.assertEqual(self.record(self.dan[0])['author'], 'Dan')
        both = management.dispatch(
            self.root,
            'library-author-different',
            {'author': 'Dan', 'others': ['Dan Baskette']},
        )
        self.assertEqual({g['author']: g for g in both['authors']}['Dan']['suggestions'], [])

    def test_a_voice_named_like_a_group_but_for_case_is_not_suggested_twice(self):
        self.file.write_text('Another guide.')
        self.command(
            'profile',
            'create',
            '--name',
            'dan  SMITH',
            '--guide-file',
            str(self.file),
        )
        self.assertEqual(
            [s['name'] for s in self.groups()['Dan']['suggestions']],
            ['Dan Smith', 'Dan Baskette'],
        )

    def test_a_failure_partway_through_same_person_says_how_far_it_got(self):
        from hub_store import HubError

        more = self.items('d2.md', author='Dan', operation='f')
        expected = self.groups()['Dan']['expected']
        real, calls = management.curate_source, []

        def flaky(root, adapter, route, data):
            calls.append(data['id'])
            if len(calls) == 2:
                raise HubError('The Team Hub could not be reached.')
            return real(root, adapter, route, data)

        with patch.object(management, 'curate_source', flaky):
            with self.assertRaisesRegex(
                HubError, r'^1 of 2 posts now name Dan Smith\. The Team Hub could not be reached\.'
            ):
                management.dispatch(
                    self.root,
                    'library-author-same',
                    {'author': 'Dan', 'into': 'Dan Smith', 'expected': expected},
                )
        with patch.object(
            management, 'curate_source', lambda *a: (_ for _ in ()).throw(OSError('Disk full.'))
        ):
            with self.assertRaisesRegex(
                ValueError, r'^0 of 1 posts now name Dan Smith\. Disk full\.'
            ):
                management.dispatch(
                    self.root,
                    'library-author-same',
                    {
                        'author': 'Dan',
                        'into': 'Dan Smith',
                        'expected': self.groups()['Dan']['expected'],
                    },
                )
        self.assertEqual(
            sorted(self.record(i)['author'] for i in self.dan + more), ['Dan', 'Dan Smith']
        )

    def test_review_details_edits_an_items_author_both_ways(self):
        ident = self.dan[0]
        curate = lambda author: management.dispatch(  # noqa: E731
            self.root,
            'curate',
            {
                'id': ident,
                'location': 'local',
                'expected': management.source_detail(self.root, ident)['expected'],
                'author': author,
            },
        )
        curate('Dan Smith')
        self.assertEqual(self.record(ident)['author'], 'Dan Smith')
        curate('Dan')
        self.assertEqual(self.record(ident)['author'], 'Dan')
        curate('')
        self.assertFalse(self.record(ident).get('author'), 'an author can be cleared')
        stale = management.source_detail(self.root, ident)['expected']
        curate('Dan')
        with self.assertRaises(management.CurationConflict):
            management.dispatch(
                self.root,
                'curate',
                {'id': ident, 'location': 'local', 'expected': stale, 'author': 'Dan Smith'},
            )
        self.assertEqual(self.record(ident)['author'], 'Dan')


class LibraryPickTests(RunnerCase):
    """Task 6: a run reads library items with a role for this blog only."""

    def items(self):
        result = management.dispatch(
            self.root,
            'upload',
            {
                'operation': 'a' * 32,
                'purpose': 'material',
                'keep': True,
                'analyze': False,
                'author': 'Avery',
                'files': [
                    {**encoded_file('post.md', b'An earlier post. ' * 5), 'purpose': 'inspiration'},
                    encoded_file('facts.md', b'The gateway retries twice.'),
                ],
            },
        )
        return [row['source']['id'] for row in result['files']]

    def test_create_pins_library_items_with_the_role_for_this_blog_only(self):
        example, facts = self.items()
        found = self.create(
            library=[{'id': example, 'role': 'facts'}, {'id': facts, 'role': 'example'}]
        )
        _, record, run = runner.load(self.root, found['id'])
        pinned = {s['source_id']: s for s in record['sources']}
        self.assertEqual(pinned[example]['purposes'], ['reference'])
        self.assertEqual(pinned[facts]['purposes'], ['reference', 'inspiration'])
        self.assertEqual(pinned[facts]['revision'], 1)
        self.assertEqual(record['material'], [])
        payload = runner.inputs(self.root, record, run)
        self.assertEqual([s['name'] for s in payload['sources']], ['post'])
        self.assertEqual([s['name'] for s in payload['examples']], ['facts'])
        # The library records are unchanged.
        for ident, purposes in ((example, ['reference', 'inspiration']), (facts, ['reference'])):
            _, saved = studio.item(self.root, 'sources', ident)
            self.assertEqual((saved['purposes'], saved['revision']), (purposes, 1))
        # Library items alone can start a blog from my files; the CLI reads examples too.
        files = runner.create(
            self.root,
            {'mode': 'from-files', 'goal': 'A post', 'library': [{'id': facts, 'role': 'facts'}]},
            'page',
        )
        self.assertEqual(files['next'], 'angles')
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'run',
                'create',
                '--title',
                'T',
                '--audience',
                'A',
                '--goal',
                'G',
                '--research',
                'none',
                '--example',
                facts,
            ]
        )
        chat = runner.command(self.root, args)
        _, record, _ = runner.load(self.root, chat['id'])
        self.assertEqual(record['sources'][0]['purposes'], ['reference', 'inspiration'])
        # Refusals.
        for chosen, pattern in (
            ([{'id': facts}], 'id and a role'),
            ([{'id': facts, 'role': 'voice'}], 'id and a role'),
            ([{'id': facts, 'role': 'facts'}, {'id': facts, 'role': 'example'}], 'once'),
            ([{'id': 'no-such-item', 'role': 'facts'}], 'Unknown sources ID'),
        ):
            with self.assertRaisesRegex(ValueError, pattern):
                self.create(library=chosen)
        with self.assertRaisesRegex(ValueError, 'once'):
            self.create(sources=[facts], library=[{'id': facts, 'role': 'example'}])
        material = management.dispatch(
            self.root,
            'upload',
            {
                'operation': 'b' * 32,
                'purpose': 'material',
                'analyze': False,
                'files': [encoded_file('m.md', b'Mine.')],
            },
        )['files'][0]['source']['id']
        with self.assertRaisesRegex(ValueError, 'not a library item'):
            self.create(library=[{'id': material, 'role': 'facts'}])

    def test_a_library_item_can_be_read_as_approved_messaging(self):
        example, facts = self.items()
        found = self.create(library=[{'id': facts, 'role': 'messaging'}])
        _, record, _ = runner.load(self.root, found['id'])
        self.assertEqual(record['sources'][0]['purposes'], ['reference', 'messaging'])
        management.dispatch(self.root, 'source-role', {'id': example, 'role': 'messaging'})
        self.assertEqual(library.catalog(self.root, role='messaging')['total'], 1)
        self.assertEqual(library.catalog(self.root, role='facts')['total'], 1)
        self.assertEqual(library.catalog(self.root, role='example')['total'], 0)
        import library_add

        found = library_add.checked(
            self.root, {'role': 'messaging', 'files': [encoded_file('brief.md', b'The brief.')]}
        )
        self.assertEqual(found['purposes'], ['reference', 'messaging'])
        args = studio.parser().parse_args(
            ['--root', str(self.root), 'run', 'create', '--audience', 'A', '--goal', 'G']
            + ['--title', 'T', '--research', 'none', '--messaging', facts]
        )
        chat = runner.command(self.root, args)
        _, record, _ = runner.load(self.root, chat['id'])
        self.assertEqual(record['sources'][0]['purposes'], ['reference', 'messaging'])


class DefaultVoiceTests(RunnerCase):
    """Task 8: the Settings default voice, and Write as for Interview me."""

    def setUp(self):
        super().setUp()
        isolation.voices_on(self.root)  # These exercise the older voice tools.

    def voice(self, name='Avery', status='confirmed'):
        self.file.write_text('Short direct sentences.')
        return self.command(
            'profile', 'create', '--name', name, '--guide-file', str(self.file), '--status', status
        )

    def test_settings_offer_confirmed_voices_and_save_the_personal_default(self):
        import writing_defaults

        mine, draft = self.voice(), self.voice('Sam', 'provisional')
        shown = runner.settings(self.root)
        self.assertIsNone(shown['voice'])
        self.assertEqual(shown['voices'], [{'id': mine['id'], 'name': 'Avery', 'revision': 1}])
        defaults = dict(shown['defaults'])
        saved = management.dispatch(
            self.root,
            'run-settings',
            {**defaults, 'voice': {'profile_id': mine['id'], 'revision': 1}, 'voice_before': None},
        )
        self.assertEqual(saved['voice'], {'profile_id': mine['id'], 'revision': 1})
        self.assertEqual(
            saved['defaults'], defaults, 'the voice is beside the defaults, not in them'
        )
        self.assertEqual(
            writing_defaults.personal(self.root)['values']['voice'],
            {'profile_id': mine['id'], 'revision': 1},
        )
        self.assertEqual((self.root / '.writing-defaults.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(runner.options(self.root)['default_voice']['profile'], mine['id'])
        # A new blog takes it; None removes it; a provisional or unknown voice is refused.
        found = self.create()
        self.assertEqual(
            studio.item(self.root, 'articles', found['id'])[1]['voice'],
            {'mode': 'profile', 'profile_id': mine['id'], 'revision': 1},
        )
        self.assertIsNone(
            management.dispatch(
                self.root,
                'run-settings',
                {**defaults, 'voice': None, 'voice_before': saved['voice']},
            )['voice']
        )
        self.assertNotIn('voice', writing_defaults.personal(self.root)['values'])
        for bad in (
            {'profile_id': draft['id'], 'revision': 1},
            {'profile_id': 'nobody', 'revision': 1},
            'avery',
        ):
            with self.assertRaisesRegex(ValueError, 'voice'):
                management.dispatch(
                    self.root, 'run-settings', {**defaults, 'voice': bad, 'voice_before': None}
                )
        self.assertEqual(
            management.dispatch(self.root, 'run-settings', defaults)['defaults'], defaults
        )

    def test_a_refused_or_outdated_settings_form_leaves_the_default_voice(self):
        import studios_config
        import writing_defaults

        mine, other = self.voice(), self.voice('Sam')
        shown = runner.settings(self.root)
        defaults, before = dict(shown['defaults']), dict(shown['shared_before'])
        pin = {'profile_id': mine['id'], 'revision': 1}
        voice = lambda: writing_defaults.personal(self.root)['values'].get('voice')  # noqa: E731
        # Another studio changed the shared author since this form was shown.
        studios_config.update({'person': {'name': 'Someone Else'}})
        with self.assertRaisesRegex(ValueError, 'Shared settings changed'):
            management.dispatch(
                self.root,
                'run-settings',
                {
                    **defaults,
                    'author': 'My Name',
                    'voice': pin,
                    'voice_before': None,
                    'shared_before': before,
                },
            )
        self.assertIsNone(voice(), 'a refused save keeps the default voice')
        # An invalid form saves nothing either.
        with self.assertRaisesRegex(ValueError, 'step limit'):
            management.dispatch(
                self.root,
                'run-settings',
                {**defaults, 'seconds': 5, 'voice': pin, 'voice_before': None},
            )
        self.assertIsNone(voice())
        # A form shown before another window set the default voice is refused, and the
        # shared settings it carried are not saved either.
        writing_defaults.set_personal(
            self.root, 'voice', {'profile_id': other['id'], 'revision': 1}
        )
        shown = runner.settings(self.root)
        with self.assertRaisesRegex(ValueError, 'default voice changed'):
            management.dispatch(
                self.root,
                'run-settings',
                {
                    **shown['defaults'],
                    'author': 'Changed',
                    'voice': pin,
                    'voice_before': None,
                    'shared_before': shown['shared_before'],
                },
            )
        self.assertEqual(voice(), {'profile_id': other['id'], 'revision': 1})
        self.assertEqual(runner.settings(self.root)['defaults']['author'], 'Someone Else')
        with self.assertRaisesRegex(ValueError, 'Reload'):
            management.dispatch(self.root, 'run-settings', {**shown['defaults'], 'voice': pin})
        self.assertEqual(voice(), {'profile_id': other['id'], 'revision': 1})

    def test_interview_me_writes_as_the_chosen_voice(self):
        import article_tools

        mine = self.voice()
        brief = {'title': 'Synthetic interview', 'audience': 'Developers', 'goal': 'Explain'}
        voice_of = lambda found: studio.item(self.root, 'articles', found['id'])[1]['voice']  # noqa: E731
        chosen = management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'interview-start',
                'operation': 'a' * 32,
                'profile': mine['id'],
                'revision': 1,
                **brief,
            },
        )
        self.assertEqual(
            voice_of(chosen), {'mode': 'profile', 'profile_id': mine['id'], 'revision': 1}
        )
        again = article_tools.start_interview(
            self.root, {'operation': 'a' * 32, 'profile': mine['id'], 'revision': 1, **brief}
        )
        self.assertEqual(again['id'], chosen['id'], 'the same request resumes the same interview')
        with self.assertRaisesRegex(ValueError, 'another interview'):
            article_tools.start_interview(
                self.root, {'operation': 'a' * 32, 'profile': '', **brief}
            )
        none = article_tools.start_interview(
            self.root, {'operation': 'b' * 32, 'profile': '', **brief}
        )
        self.assertEqual(voice_of(none), {'mode': 'preserve', 'tone': ''}, 'no particular voice')
        plain = article_tools.start_interview(self.root, {'operation': 'c' * 32, **brief})
        self.assertEqual(
            voice_of(plain), {'mode': 'preserve', 'tone': ''}, 'no default voice to apply'
        )
        management.dispatch(
            self.root,
            'run-settings',
            {
                **runner.settings(self.root)['defaults'],
                'voice': {'profile_id': mine['id'], 'revision': 1},
                'voice_before': None,
            },
        )
        defaulted = article_tools.start_interview(self.root, {'operation': 'd' * 32, **brief})
        self.assertEqual(
            voice_of(defaulted),
            {'mode': 'profile', 'profile_id': mine['id'], 'revision': 1},
            'the default voice applies',
        )
        with self.assertRaisesRegex(ValueError, 'revision'):
            article_tools.start_interview(
                self.root, {'operation': 'e' * 32, 'profile': mine['id'], 'revision': 9, **brief}
            )
        with self.assertRaisesRegex(ValueError, 'needs its profile'):
            article_tools.start_interview(
                self.root, {'operation': 'f' * 32, 'revision': 1, **brief}
            )


class HubItemTests(RunnerCase):
    """C2: an item only the Team Hub holds can be picked and acted on, from a teammate's clone."""

    def test_a_teammates_hub_only_item_is_checked_out_to_pick_or_select(self):
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
            management.dispatch(
                self.root,
                'upload',
                {
                    'operation': 'a' * 32,
                    'purpose': 'material',
                    'keep': True,
                    'analyze': False,
                    'author': 'Avery',
                    'files': [encoded_file('teammate-post.md', b'A teammate post. ' * 5)],
                },
            )
            wb.hub.refresh()
            row = library.catalog(other)['items'][0]
            self.assertEqual(row['location'], 'hub')
            hub = {'id': row['id'], 'location': 'hub'}
            # Picked for a blog: checked out here, then pinned as any library item is.
            found = runner.create(
                other,
                {
                    'title': 'Uses the teammate post',
                    'audience': 'A',
                    'goal': 'G',
                    'research': 'none',
                    'library': [{**hub, 'role': 'example'}],
                },
                'page',
            )
            _, record, run = runner.load(other, found['id'])
            local = record['sources'][0]['source_id']
            self.assertTrue(local.startswith('hub-' + row['id']))
            self.assertEqual(record['sources'][0]['purposes'], ['reference', 'inspiration'])
            self.assertEqual(
                runner.inputs(other, record, run)['examples'][0]['name'], 'teammate-post'
            )
            # Selected on the library screen: the same checkout, never a second copy.
            blog = management.dispatch(other, 'library-selection', {'action': 'blog', 'ids': [hub]})
            self.assertEqual([f['id'] for f in blog['files']], [local])
            self.assertEqual(len(list((other / 'sources').iterdir())), 1)
            with self.assertRaisesRegex(ValueError, 'local or shared'):
                management.dispatch(
                    other,
                    'library-selection',
                    {'action': 'blog', 'ids': [{**hub, 'location': 'x'}]},
                )
        # Without the Team Hub a shared item cannot be read.
        with patch('hub_workspace.active', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Team Hub'):
                management.dispatch(other, 'library-selection', {'action': 'blog', 'ids': [hub]})


class HubSyncTests(RunnerCase):
    """I6: a group's changes are published one by one and the Team Hub syncs once."""

    def test_marking_or_renaming_a_group_syncs_the_hub_once(self):
        isolation.voices_on(self.root)  # These exercise the older voice tools.
        import hub
        import hub_workspace

        provider = FakeProvider(self.base / 'remotes')
        registry = Registry(self.base / 'hubs', provider)
        ident = registry.create('fixture/count', 'Count')['hub']
        adapter = Workspace(self.root, registry.hub(ident))
        calls, real = [], hub.Hub.sync

        def counted(hub_self, *args, **kwargs):
            calls.append(1)
            return real(hub_self, *args, **kwargs)

        names = ['p%d' % n for n in range(8)]
        reader = Pages({SITE + n + '/': page(n.upper(), 'Darin Zook') for n in names})
        request = {
            'links': ''.join(SITE + n + '/\n' for n in names),
            'role': 'facts',
            'author': '*each',
            'kind': '',
        }
        with (
            patch.object(hub_workspace, 'active', return_value=adapter),
            patch.object(hub.Hub, 'sync', counted),
            patch.object(library, 'fetch', reader),
            patch.object(library.time, 'sleep', lambda seconds: None),
        ):
            shown = management.dispatch(self.root, 'library-add-preview', request)
            added = management.dispatch(
                self.root,
                'library-add',
                {**request, 'operation': 'a' * 32, 'expected': shown['expected']},
            )
            group = added['groups'][0]['ids']
            calls.clear()
            marked = management.dispatch(self.root, 'library-add-samples', {'operation': 'a' * 32})
            self.assertEqual(len(calls), 1, 'one sync for a group of eight')
            self.assertEqual(len(marked['groups'][0]['samples']), 8)
            self.assertIn(marked['sharing'], ('shared', 'synchronized'))
            calls.clear()
            renamed = management.dispatch(
                self.root,
                'library-add-author',
                {'operation': 'a' * 32, 'ids': group, 'author': 'D. Zook'},
            )
            self.assertEqual(len(calls), 1, 'one sync for a renamed group')
            self.assertEqual(renamed['groups'][0]['author'], 'D. Zook')
            graph = adapter.hub.graph()
        shared = [
            graph['revisions'][heads[0]]['data']['studio']
            for heads in graph['heads'].values()
            if graph['revisions'][heads[0]]['kind'] == 'source'
        ]
        self.assertEqual(len(shared), 8)
        self.assertTrue(
            all(s['author'] == 'D. Zook' and 'voice-sample' in s['purposes'] for s in shared)
        )


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

    def test_a_blog_that_picked_a_finished_blog_keeps_reading_its_first_text(self):
        first = self.finish(self.create(title='Announcing one'))
        kept = self.kept()[0]['id']
        nxt = self.create(title='Announcing two', library=[{'id': kept, 'role': 'example'}])
        nxt = self.approve(self.submit(nxt))
        _, record, run = runner.load(self.root, nxt['id'])
        before = (runner.survey(self.root, nxt['id']), runner.inputs(self.root, record, run))
        old_text = before[1]['examples'][0]['text']
        # Blog one is finished again with different words: its library copy gets revision 2.
        again = runner.decide(
            self.root, first['id'], first['expected'], 'changes', 'Tighter.', target='draft'
        )
        self.finish(self.approve(self.submit(again, '# draft\nA different finished text.')))
        self.assertEqual(studio.item(self.root, 'sources', kept)[1]['revision'], 2)
        # Blog two still reads the words it picked, and nothing of it goes stale.
        after = runner.survey(self.root, nxt['id'])
        self.assertEqual(
            (after['stages'], after['expected']), (before[0]['stages'], before[0]['expected'])
        )
        self.assertEqual(runner.inputs(self.root, record, run), before[1])
        self.assertEqual(old_text, '# draft\nSynthetic writing.')
        self.assertEqual(runner.engine(self.root).describe(nxt['id'])['next'], 'draft')
        nxt = self.finish(runner.survey(self.root, nxt['id']))
        self.assertTrue(nxt['complete'])
        shown = runner.document(self.root, nxt['id'], 'draft')
        self.assertEqual(shown['status'], 'approved')
        self.assertEqual(
            [c['label'] for c in shown['checks']][-1], 'No passage carried over from an example'
        )
        # Without the saved copy of the pinned revision it still refuses.
        directory, _ = studio.item(self.root, 'sources', kept)
        (directory / 'revisions' / '1' / 'content.md').unlink()
        with self.assertRaisesRegex(ValueError, 'selected source changed'):
            runner.survey(self.root, nxt['id'])

    def test_a_second_finish_changes_only_the_text_and_title(self):
        found = self.finish(self.create(style='product-announcement', author='Avery'))
        self.assertEqual(found['library'], {'id': self.kept()[0]['id'], 'revision': 1})
        directory, record = studio.item(self.root, 'sources', found['library']['id'])
        # Someone changes the item in the library: its role, kind and author.
        record.update(purposes=['reference', 'voice-sample'], author='Avery Quinn')
        record['library']['kind'] = 'how-to'
        studio.persist(directory, 'sources', record)
        again = runner.decide(
            self.root, found['id'], found['expected'], 'changes', 'Retitle.', target='draft'
        )
        again = self.submit(again, '# draft\nNew finished words.')
        self.finish(self.approve(again))
        _, record = studio.item(self.root, 'sources', found['library']['id'])
        self.assertEqual(record['revision'], 2)
        self.assertEqual((directory / 'content.md').read_text(), '# draft\nNew finished words.')
        self.assertEqual(
            (record['purposes'], record['author'], record['library']['kind']),
            (['reference', 'voice-sample'], 'Avery Quinn', 'how-to'),
            'what the library changed stays',
        )

    def test_finish_keeps_the_blog_without_a_kind_when_its_style_is_gone(self):
        import styles

        found = self.create(style='product-announcement')
        with patch.object(styles, 'name_of', lambda root, ident: None):
            found = self.finish(found)
        self.assertTrue(found['complete'])
        self.assertEqual(len(self.kept()), 1)
        self.assertNotIn('kind', self.kept()[0]['library'])
        self.assertTrue(found['decisions'][-1]['event'].endswith(' · kept in the team library'))

    def test_finish_is_never_refused_when_the_library_cannot_take_the_blog(self):
        import blog_library

        noted = []
        for failure in (OSError('disk full'), RuntimeError('unexpected')):
            found = self.create(title='Synthetic ' + type(failure).__name__)
            while found['next'] != found['stages'][-1]['stage']:
                found = self.approve(self.submit(found))
            found = self.submit(found)
            with (
                patch.object(blog_library, 'keep_written', side_effect=failure),
                patch.object(management, 'note_unexpected', noted.append),
            ):
                done = self.approve(found)
            self.assertTrue(done['complete'], 'the approval is saved')
            self.assertEqual(set(done['library']), {'reason'})
            self.assertIn('could not be saved', done['library']['reason'])
        self.assertEqual([type(exc).__name__ for exc in noted], ['RuntimeError'])

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


class DeskPublishTests(RunnerCase):
    """Mark as published keeps a desk blog's draft in the library, as Finish does for a run."""

    kept = FinishTests.kept

    def desk(self, operation='d', **extra):
        return management.dispatch(
            self.root,
            'desk-create',
            {
                'operation': operation * 32,
                'title': 'Desk post',
                'manuscript': '# Desk post\n\n## One\n\nPublished words.\n',
                **extra,
            },
        )

    def publish(self, ident, url='https://example.invalid/post'):
        shown = management.view(self.root, 'desk', {'id': [ident]})
        return management.dispatch(
            self.root,
            'schedule',
            {
                'id': ident,
                'expected': shown['expected'],
                'stage': 'published',
                'confirm_stage': True,
                'publication_url': url,
            },
        )

    def test_a_published_desk_blog_is_kept_once_and_updated_when_marked_again(self):
        made = self.desk(style='product-announcement')
        self.assertEqual(self.kept(), [], 'nothing is kept before it is published')
        result = self.publish(made['id'])
        rows = self.kept()
        self.assertEqual(len(rows), 1)
        self.assertEqual(result['library'], {'id': rows[0]['id'], 'revision': 1})
        self.assertEqual(
            rows[0]['library'],
            {'kind': 'product-announcement', 'origin_kind': 'written-here', 'article': made['id']},
        )
        self.assertEqual(rows[0]['purposes'], ['reference', 'inspiration'])
        directory, record = studio.item(self.root, 'sources', rows[0]['id'])
        self.assertEqual((directory / 'content.md').read_text(), made['markdown'])
        self.assertEqual(record['note'], 'Published from the writing desk.')
        # Edited on the desk and marked again at the same address: the same item, revised.
        shown = management.view(self.root, 'desk', {'id': [made['id']]})
        part = shown['sections'][0]['id']
        management.dispatch(
            self.root,
            'desk-save',
            {
                'id': made['id'],
                'seen': shown['revision'],
                'part': part,
                'text': 'Revised words.',
                'session': 'a' * 16,
            },
        )
        again = self.publish(made['id'])
        self.assertEqual(again['library'], {'id': rows[0]['id'], 'revision': 2})
        self.assertEqual([r['id'] for r in self.kept()], [rows[0]['id']])
        self.assertIn('Revised words.', (directory / 'content.md').read_text())
        # The same draft marked again is not a new revision.
        self.assertEqual(self.publish(made['id'])['library']['revision'], 2)

    def test_publishing_a_desk_blog_is_never_refused_when_the_library_cannot_take_it(self):
        import blog_library

        noted = []
        for operation, failure in (('a', OSError('disk full')), ('b', RuntimeError('unexpected'))):
            made = self.desk(operation=operation)
            with (
                patch.object(blog_library, 'keep_written', side_effect=failure),
                patch.object(management, 'note_unexpected', noted.append),
            ):
                result = self.publish(made['id'])
            self.assertEqual(set(result['library']), {'reason'})
            self.assertIn('could not be saved', result['library']['reason'])
            _, record = studio.item(self.root, 'articles', made['id'])
            self.assertEqual(record['editorial']['publication_url'], 'https://example.invalid/post')
        self.assertEqual([type(exc).__name__ for exc in noted], ['RuntimeError'])
        self.assertEqual(self.kept(), [])

    def test_a_team_workspace_shares_the_published_desk_blog(self):
        from hub_workspace import Workspace
        import hub_workspace

        provider = FakeProvider(self.base / 'remotes')
        registry = Registry(self.base / 'hubs', provider)
        ident = registry.create('fixture/published', 'Published')['hub']
        adapter = Workspace(self.root, registry.hub(ident))
        with patch.object(hub_workspace, 'active', return_value=adapter):
            made = self.desk()
            self.publish(made['id'])
            graph = adapter.hub.graph()
        shared = [
            graph['revisions'][heads[0]]['data']['studio']
            for heads in graph['heads'].values()
            if graph['revisions'][heads[0]]['kind'] == 'source'
        ]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]['library']['article'], made['id'])
        self.assertEqual(shared[0]['library']['origin_kind'], 'written-here')


if __name__ == '__main__':
    import unittest

    unittest.main()


class SourceKeepTests(RunnerCase):
    def test_a_failed_record_write_keeps_the_original_folder_in_place(self):
        ident = self.upload_file()
        before, _ = studio.item(self.root, 'sources', ident)
        with patch.object(studio, 'persist', side_effect=OSError('Synthetic disk failure')):
            with self.assertRaises(OSError):
                management.source_keep(self.root, {'id': ident, 'keep': True})
        self.assertTrue(before.is_dir())
        self.assertFalse((self.root / 'sources' / ident).exists())

    def upload_file(self, keep=False):
        self.upload_number = getattr(self, 'upload_number', 0) + 1
        return management.dispatch(
            self.root,
            'upload',
            {
                'operation': f'{self.upload_number:032x}',
                'files': [
                    {
                        'filename': 'notes.md',
                        'content': base64.b64encode(b'Synthetic source text.').decode(),
                        'purpose': 'inspiration',
                    }
                ],
                'purpose': 'material',
                'keep': keep,
                'analyze': False,
            },
        )['files'][0]['source']['id']

    def test_a_file_moves_both_ways_without_losing_its_text_or_original(self):
        ident = self.upload_file()
        before, record = studio.item(self.root, 'sources', ident)
        text = (before / 'content.md').read_bytes()
        original = (before / record['original_path']).read_bytes()
        result = management.source_keep(self.root, {'id': ident, 'keep': True})
        directory, record = studio.item(self.root, 'sources', ident)
        self.assertTrue(result['kept'])
        self.assertEqual(directory, self.root / 'sources' / ident)
        self.assertEqual(record['purposes'], ['reference', 'inspiration'])
        self.assertEqual(library.catalog(self.root)['total'], 1)
        result = management.source_keep(self.root, {'id': ident, 'keep': False})
        directory, record = studio.item(self.root, 'sources', ident)
        self.assertFalse(result['kept'])
        self.assertEqual(directory, studio.material(self.root, ident))
        self.assertEqual(record['purposes'], ['material', 'inspiration'])
        self.assertEqual((directory / 'content.md').read_bytes(), text)
        self.assertEqual((directory / record['original_path']).read_bytes(), original)
        self.assertEqual(library.catalog(self.root)['total'], 0)

    def test_a_new_unshared_kept_upload_can_be_kept_only_for_this_blog(self):
        ident = self.upload_file(keep=True)
        result = management.source_keep(self.root, {'id': ident, 'keep': False})
        self.assertFalse(result['kept'])

    def test_a_started_blog_keeps_its_sources_in_place(self):
        for keep in (False, True):
            ident = self.upload_file(keep=keep)
            self.create(page=True, title='Pinned ' + str(keep), mode='from-files', sources=[ident])
            with self.assertRaisesRegex(ValueError, 'A started blog read this file from'):
                management.source_keep(self.root, {'id': ident, 'keep': not keep})
            directory, record = studio.item(self.root, 'sources', ident)
            self.assertEqual(studio.is_material(self.root, directory, record), not keep)

    def test_a_shared_reference_stays_in_the_library(self):
        provider = FakeProvider(self.base / 'remotes')
        registry = Registry(self.base / 'hubs', provider)
        hub = registry.create('fixture/source-keep', 'Synthetic library')['hub']
        workspace = Workspace(self.root, registry.hub(hub))
        with patch('hub_workspace.active', return_value=workspace):
            ident = self.upload_file(keep=True)
            with self.assertRaisesRegex(ValueError, 'already shared with your team'):
                management.source_keep(self.root, {'id': ident, 'keep': False})

    def test_an_older_or_nonlocal_reference_cannot_be_removed_from_this_form(self):
        ident = self.upload_file(keep=True)
        directory, record = studio.item(self.root, 'sources', ident)
        record['revision'] = 2
        studio.persist(directory, 'sources', record)
        with self.assertRaisesRegex(ValueError, 'Only a new file added on this computer'):
            management.source_keep(self.root, {'id': ident, 'keep': False})
        other = self.source()
        with self.assertRaisesRegex(ValueError, 'Only a new file added on this computer'):
            management.source_keep(self.root, {'id': other['id'], 'keep': False})
