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


SITE = 'https://blog.example/team/'
OTHER = 'https://other.example/blog/'
DOC = 'https://docs.google.com/document/d/1AbC_dEf-2gHiJkLmNoPqRsTuVwXyZ012345/edit'


def encoded_file(name, body):
    return {'filename': name, 'content': base64.b64encode(body).decode()}


class AddTests(RunnerCase):
    """Task 4: Add to library, in one sheet, with the author typed or each post's own."""

    def captured(self, title='Messaging Doc', body='# Messaging\n\nThe platform name is open.'):
        def capture(_client, file_id, _revision, snapshot):
            snapshot.mkdir(parents=True)
            (snapshot / 'document.md').write_text(body)
            studio.write_json(snapshot / 'native.json', {'title': title})
            return {'summary': {}}

        return capture

    def add(self, route, data, reader=None):
        import google_intake

        with (
            patch.object(library, 'fetch', reader or Pages({})),
            patch.object(google_intake.roundtrip, 'capture', self.captured()),
            patch.object(google_intake.drive, 'Client', lambda account: object()),
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
        with refused('facts or an example'):
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

    def test_each_posts_own_author_imports_first_then_groups_by_byline(self):
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
        self.assertEqual(reasons[SITE + 'org/'], 'No byline on the page.')
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
                'receipts'
            ],
            [],
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
