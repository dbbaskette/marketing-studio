"""Published posts from a list of links become voice samples through the library import.

Every page comes from a local stub fetcher, so no test reaches the network.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
from unittest.mock import patch

from hub_fixtures import FakeProvider
from hub import Registry
from hub_workspace import Workspace
from test_editorial_tools import Fixture
import article_tools
import blog_library as library
import management
import studio
import voice_links

SITE = 'https://blog.example/team/'
AUTHOR = 'Avery Quinn'


def page(title, author=None, how='json-ld'):
    head = '<title>' + title + '</title>'
    byline = ''
    if author and how == 'json-ld':
        head += (
            '<script type="application/ld+json">'
            + json.dumps(
                {
                    '@context': 'https://schema.org',
                    '@graph': [
                        {'@type': 'WebPage', 'name': title},
                        {'@type': 'BlogPosting', 'headline': title, 'author': {'name': author}},
                    ],
                }
            )
            + '</script>'
        )
    elif author and how == 'meta':
        head += '<meta name="author" content="' + author + '">'
    elif author and how == 'byline':
        byline = '<p class="post-byline byline">By <a href="/people/x">' + author + '</a></p>'
    return (
        '<html><head>'
        + head
        + '</head><body><article><h1>'
        + title
        + '</h1>'
        + byline
        + '<p>A synthetic paragraph about platform engineering and delivery.</p>'
        '</article></body></html>'
    ).encode()


class Pages:
    """A stub fetcher: {url: bytes or an exception}, recording every request."""

    def __init__(self, pages):
        self.pages, self.calls = dict(pages), []

    def __call__(self, url, scope):
        self.calls.append((url, scope))
        if not library.in_scope(url, scope):
            raise ValueError('URL is outside the approved collection scope.')
        found = self.pages.get(url)
        if isinstance(found, Exception):
            raise found
        if found is None:
            raise ValueError('Source returned HTTP 404; historical snapshots were retained.')
        return found, url, 'text/html; charset=utf-8'


class ParseTests(Fixture):
    def test_comments_blanks_duplicates_markers_and_http_are_handled(self):
        found = voice_links.parse(
            '# Avery Quinn posts\n\n'
            + SITE
            + 'first-post/\n'
            + '  '
            + SITE
            + 'first-post/  \n'
            + 'http://blog.example/team/second-post/\n'
            + '- '
            + SITE
            + 'third-post/\n'
            + 'not a link\n'
            + 'ftp://blog.example/team/file\n'
            + SITE
            + 'fourth-post/#comments\n'
            + SITE
            + 'fourth-post/\n'
        )
        self.assertEqual(found['status'], 'ready')
        self.assertEqual(
            found['links'],
            [
                SITE + 'first-post/',
                SITE + 'second-post/',
                SITE + 'third-post/',
                SITE + 'fourth-post/',
            ],
        )
        self.assertEqual(found['duplicates'], 2)
        self.assertEqual(found['comments'], 1)
        self.assertEqual(found['upgraded'], 1)
        self.assertEqual(found['unusable'], 2)
        self.assertEqual([row['line'] for row in found['skipped']], [7, 8])
        self.assertEqual(found['scope'], SITE)
        self.assertEqual(found['shown_scope'], 'blog.example/team/')

    def test_scope_is_the_common_folder_and_never_the_post_itself(self):
        scope = voice_links.scope_for
        self.assertEqual(scope([SITE + 'a/', SITE + 'b/']), SITE)
        self.assertEqual(scope([SITE + '2024/a', SITE + '2025/b']), SITE)
        self.assertEqual(scope([SITE + 'only-post/']), SITE)
        self.assertEqual(
            scope(['https://blog.example/a', 'https://blog.example/b/c']), 'https://blog.example/'
        )
        for link in (SITE + 'a/', SITE + '2024/a'):
            self.assertTrue(library.in_scope(link, SITE))

    def test_mixed_sites_ask_which_one_and_unknown_site_is_refused(self):
        text = SITE + 'a/\n' + SITE + 'b/\nhttps://other.example/blog/c/\n'
        found = voice_links.parse(text)
        self.assertEqual(found['status'], 'choose-site')
        self.assertIn('2 sites', found['problem'])
        self.assertEqual(
            [(s['site'], s['shown'], s['links']) for s in found['sites']],
            [
                ('blog.example', 'blog.example/team/', 2),
                ('other.example', 'other.example/blog/', 1),
            ],
        )
        chosen = voice_links.parse(text, 'blog.example')
        self.assertEqual(chosen['links'], [SITE + 'a/', SITE + 'b/'])
        self.assertEqual(chosen['left_out'], 1)
        with self.assertRaisesRegex(ValueError, 'None of these links'):
            voice_links.parse(text, 'third.example')

    def test_empty_oversized_and_too_many_lists_are_refused(self):
        for text in ('', '# only a comment\n', 'not a link\n'):
            with self.assertRaises(ValueError):
                voice_links.parse(text)
        with self.assertRaisesRegex(ValueError, '256 KiB'):
            voice_links.parse((SITE + 'x/\n') * 20000)
        with patch.object(library, 'MAX_POSTS', 2):
            with self.assertRaisesRegex(ValueError, 'at most 2'):
                voice_links.parse(SITE + 'a/\n' + SITE + 'b/\n' + SITE + 'c/\n')

    def test_author_is_suggested_from_the_file_name(self):
        self.assertEqual(voice_links.author_from_filename('avery-quinn-blog-links.txt'), AUTHOR)
        self.assertEqual(voice_links.author_from_filename('Avery_Quinn posts.txt'), AUTHOR)
        self.assertEqual(voice_links.author_from_filename('links.txt'), '')


class BylineTests(Fixture):
    def test_bylines_from_json_ld_meta_rel_and_byline_class(self):
        self.assertEqual(voice_links.bylines(page('One', AUTHOR, 'json-ld')), [AUTHOR])
        self.assertEqual(voice_links.bylines(page('Two', AUTHOR, 'meta')), [AUTHOR])
        self.assertEqual(voice_links.bylines(page('Three', AUTHOR, 'byline')), [AUTHOR])
        self.assertEqual(
            voice_links.bylines(b'<a rel="author" href="/a">Jordan Lee</a><p>Body</p>'),
            ['Jordan Lee'],
        )
        self.assertEqual(voice_links.bylines(page('None')), [])
        # A profile address is not a name, and JSON-LD wins over a weaker byline.
        self.assertEqual(
            voice_links.bylines(
                b'<meta property="article:author" content="https://social.example/aq">'
                b'<p class="byline">By Jordan Lee</p>'
            ),
            ['Jordan Lee'],
        )
        coauthored = (
            b'<script type="application/ld+json">{"author":[{"name":"Avery Quinn"},'
            b'{"name":"Jordan Lee"}]}</script>'
        )
        self.assertEqual(voice_links.bylines(coauthored), [AUTHOR, 'Jordan Lee'])
        self.assertEqual(voice_links.bylines(b'<script type="application/ld+json">{broken'), [])
        # A publisher credited as the author in JSON-LD is not a byline: the page's own
        # byline decides, so an organisation never marks every post as someone else's.
        published = (
            b'<script type="application/ld+json">{"author":{"@type":"Organization",'
            b'"name":"Example Publishing"}}</script><p class="byline">By Avery Quinn</p>'
        )
        self.assertEqual(voice_links.bylines(published), [AUTHOR])
        self.assertEqual(voice_links.organisation(published), None, 'a person is credited too')
        # An organisation named in a meta tag or a byline is not a person either: held, by name.
        site = (
            b'<meta property="og:site_name" content="Example Publishing">'
            b'<meta name="author" content="Example Publishing">'
        )
        self.assertEqual(voice_links.bylines(site), [])
        self.assertEqual(voice_links.organisation(site), 'Example Publishing')
        team = b'<p class="byline">By The Example Team</p>'
        self.assertEqual(
            (voice_links.bylines(team), voice_links.organisation(team)), ([], 'The Example Team')
        )
        ld = b'<script type="application/ld+json">{"author":{"@type":"Organization","name":"Example Co"}}</script>'
        self.assertEqual(
            (voice_links.bylines(ld), voice_links.organisation(ld)), ([], 'Example Co')
        )
        nested = b'<script type="application/ld+json">' + b'[' * 2000 + b']' * 2000 + b'</script>'
        self.assertEqual(voice_links.bylines(nested), [])

    def test_names_match_without_case_accents_order_or_initials(self):
        for byline in (
            'avery quinn',
            'By Avery Quinn',
            'Quinn, Avery',
            'Avery J. Quinn',
            'Avéry Quinn',
        ):
            self.assertTrue(voice_links.same_author(byline, AUTHOR), byline)
        for byline in ('Jordan Lee', 'Avery Lee', 'Team Blog', ''):
            self.assertFalse(voice_links.same_author(byline, AUTHOR), byline)


class ImportTests(Fixture):
    def links(self, *names):
        return ''.join(SITE + name + '/\n' for name in names)

    def run_links(self, text, reader, operation='a' * 32, **extra):
        shown = voice_links.preview(self.root, {'text': text, 'author': AUTHOR})
        return voice_links.run(
            self.root,
            {
                'operation': operation,
                'text': text,
                'author': AUTHOR,
                'expected': shown['expected'],
                **extra,
            },
            reader=reader,
            delay=0,
        ), shown

    def sources(self):
        return sorted(p.name for p in (self.root / 'sources').iterdir() if p.is_dir())

    def test_import_classifies_matching_posts_and_reports_every_link(self):
        reader = Pages(
            {
                SITE + 'mine/': page('Mine', AUTHOR),
                SITE + 'unsigned/': page('Unsigned'),
                SITE + 'theirs/': page('Theirs', 'Jordan Lee', 'meta'),
                SITE + 'down/': ValueError(library.UNREACHABLE),
                SITE + 'moved/': ValueError(library.OUT_OF_SCOPE),
            }
        )
        text = '# synthetic list\n' + self.links('mine', 'unsigned', 'theirs', 'down', 'moved')
        result, shown = self.run_links(text, reader)
        self.assertEqual((shown['links'], shown['to_fetch'], shown['in_library']), (5, 5, 0))
        self.assertEqual([call[1] for call in reader.calls], [SITE] * 5)
        rows = {row['url'].rsplit('/', 2)[-2]: row for row in result['results']}
        self.assertEqual(rows['mine']['status'], 'imported')
        self.assertTrue(rows['mine']['sample'])
        self.assertEqual(rows['mine']['byline'], [AUTHOR])
        self.assertTrue(rows['unsigned']['sample'])
        self.assertEqual(rows['unsigned']['byline'], [])
        self.assertTrue(rows['theirs']['mismatch'])
        self.assertFalse(rows['theirs']['sample'])
        self.assertEqual(rows['theirs']['byline'], ['Jordan Lee'])
        self.assertEqual(rows['down']['status'], 'failed')
        # A post that now redirects elsewhere explains itself in the list's own terms.
        self.assertEqual(rows['moved']['status'], 'failed')
        self.assertEqual(
            rows['moved']['reason'],
            'This page has moved outside ' + shown['shown_scope'] + '; use its new address.',
        )
        self.assertIn('could not be reached', rows['down']['reason'])
        self.assertEqual(
            result['counts'],
            {
                'imported': 3,
                'in-library': 0,
                'failed': 2,
                'pending': 0,
                'mismatch': 1,
                'no_text': 0,
                'samples': 2,
            },
        )
        for name in ('mine', 'unsigned'):
            _, record = studio.item(self.root, 'sources', rows[name]['id'])
            self.assertIn('voice-sample', record['purposes'])
            self.assertIn('reference', record['purposes'])
            self.assertEqual(record['author'], AUTHOR)
            # The library entry keeps the published byline; a list of links gave none.
            self.assertIsNone(record['library']['author'])
            self.assertTrue(record['library']['historical'])
        _, theirs = studio.item(self.root, 'sources', rows['theirs']['id'])
        self.assertNotIn('voice-sample', theirs['purposes'])
        listed = {s['id'] for s in article_tools.voices(self.root)['samples']}
        self.assertEqual(listed, {rows['mine']['id'], rows['unsigned']['id']})
        studio.validate_samples(self.root, sorted(listed))
        self.assertIn('choose up to twenty', result['next_step'])
        self.assertIn(
            'Published posts by ' + AUTHOR,
            [c['name'] for c in library.collections(self.root).values()],
        )

        # The same request again fetches nothing and copies nothing.
        before = (len(reader.calls), self.sources())
        again, _ = self.run_links(text, reader)
        self.assertEqual((len(reader.calls), self.sources()), before)
        self.assertEqual(again['counts'], result['counts'])

        # Keeping the mismatched post makes it a sample; a retry fetches only the failed link.
        reader.pages[SITE + 'down/'] = page('Down', AUTHOR)
        kept, _ = self.run_links(text, reader, keep=[SITE + 'theirs/'])
        self.assertTrue(next(r for r in kept['results'] if r['url'].endswith('theirs/'))['kept'])
        self.assertEqual(len(reader.calls), before[0])
        retried, _ = self.run_links(text, reader, keep=[SITE + 'theirs/'], retry=True)
        self.assertEqual(
            {c[0] for c in reader.calls[before[0] :]}, {SITE + 'down/', SITE + 'moved/'}
        )
        self.assertEqual(len(reader.calls), before[0] + 2)
        self.assertEqual(retried['counts']['samples'], 4)
        self.assertEqual(retried['counts']['failed'], 1)

    def test_links_can_become_style_samples_without_a_byline_check(self):
        import styles

        reader = Pages(
            {
                SITE + 'one/': page('One', 'Someone Else'),
                SITE + 'two/': page('Two'),
            }
        )
        text = self.links('one', 'two')
        data = {'text': text, 'author': 'Product announcements', 'purpose': 'style-sample'}
        shown = voice_links.preview(self.root, data)
        self.assertEqual(shown['purpose'], 'style-sample')
        voice = voice_links.preview(self.root, {'text': text, 'author': 'Product announcements'})
        self.assertNotEqual(shown['expected'], voice['expected'])
        result = voice_links.run(
            self.root,
            {**data, 'operation': 'c' * 32, 'expected': shown['expected']},
            reader=reader,
            delay=0,
        )
        samples = [row for row in result['results'] if row.get('sample')]
        self.assertEqual(
            len(samples), 2, 'a byline naming someone else does not hold a style sample back'
        )
        self.assertEqual(result['counts']['mismatch'], 0)
        for row in samples:
            _, record = studio.item(self.root, 'sources', row['id'])
            self.assertIn('style-sample', record['purposes'])
            self.assertNotIn('voice-sample', record['purposes'])
            self.assertNotEqual(
                record.get('author'), 'Product announcements', 'the label is not an author'
            )
            self.assertNotEqual(
                (record.get('library') or {}).get('author'), 'Product announcements'
            )
        self.assertEqual(
            {row['id'] for row in styles.catalog(self.root)['samples']},
            {row['id'] for row in samples},
        )
        self.assertEqual(article_tools.voices(self.root)['samples'], [])
        self.assertIn('style', result['next_step'])
        self.assertIn(
            'Examples: Product announcements',
            [c['name'] for c in library.collections(self.root).values()],
        )
        # The same list as a voice import is a different operation, not this one continued.
        self.assertNotEqual(
            voice_links.operation_for(text, 'Product announcements'),
            voice_links.operation_for(text, 'Product announcements', purpose='style-sample'),
        )
        with self.assertRaisesRegex(ValueError, 'voice samples or style samples'):
            voice_links.preview(self.root, {**data, 'purpose': 'reference'})
        with self.assertRaisesRegex(ValueError, 'voice samples or style samples'):
            voice_links.run(
                self.root,
                {**data, 'purpose': 'reference', 'operation': 'e' * 32},
                reader=reader,
            )

    def test_a_kept_mismatch_keeps_the_published_byline_and_names_the_previous_owner(self):
        reader = Pages({SITE + 'theirs/': page('Theirs', 'Jordan Lee')})
        text = self.links('theirs')
        shown = voice_links.preview(self.root, {'text': text, 'author': 'Jordan Lee'})
        first = voice_links.run(
            self.root,
            {
                'operation': 'a' * 32,
                'text': text,
                'author': 'Jordan Lee',
                'expected': shown['expected'],
            },
            reader=reader,
            delay=0,
        )
        directory, record = studio.item(self.root, 'sources', first['samples'][0])
        self.assertEqual(record['author'], 'Jordan Lee')
        record['library']['author'] = 'Jordan Lee'  # as a feed import records a byline
        studio.persist(directory, 'sources', record)
        held, _ = self.run_links(text, reader, operation='b' * 32)
        self.assertTrue(held['results'][0]['mismatch'])
        self.assertFalse(held['results'][0]['sample'])
        kept, _ = self.run_links(text, reader, operation='b' * 32, keep=[SITE + 'theirs/'])
        self.assertTrue(kept['results'][0]['sample'])
        self.assertEqual(kept['results'][0]['note'], "was Jordan Lee's sample; now Avery Quinn's")
        _, record = studio.item(self.root, 'sources', kept['samples'][0])
        self.assertEqual((record['author'], record['library']['author']), (AUTHOR, 'Jordan Lee'))
        self.assertEqual(record['purposes'].count('voice-sample'), 1)

    def test_a_style_import_keeps_a_voice_sample_and_a_repeat_changes_nothing(self):
        reader = Pages({SITE + 'one/': page('One', AUTHOR)})
        text = self.links('one')
        voice, _ = self.run_links(text, reader)
        ident = voice['samples'][0]
        data = {'text': text, 'author': 'Field notes', 'purpose': 'style-sample'}

        def style(operation):
            shown = voice_links.preview(self.root, data)
            return voice_links.run(
                self.root,
                {**data, 'operation': operation, 'expected': shown['expected']},
                reader=reader,
                delay=0,
            )

        style('b' * 32)
        _, record = studio.item(self.root, 'sources', ident)
        self.assertIn('voice-sample', record['purposes'])
        self.assertIn('style-sample', record['purposes'])
        self.assertEqual(record['author'], AUTHOR)
        revision = record['revision']
        again = style('c' * 32)
        _, record = studio.item(self.root, 'sources', ident)
        self.assertEqual(record['revision'], revision)
        self.assertNotIn('note', again['results'][0])
        self.assertEqual(len(reader.calls), 1)

    def test_posts_already_in_the_library_are_reused_not_fetched_or_copied(self):
        reader = Pages({SITE + n + '/': page(n, AUTHOR) for n in ('one', 'two', 'three')})
        self.run_links(self.links('one', 'two'), reader)
        sources, calls = self.sources(), len(reader.calls)
        text = self.links('two', 'three', 'one')
        shown = voice_links.preview(self.root, {'text': text, 'author': AUTHOR})
        self.assertEqual((shown['in_library'], shown['to_fetch']), (2, 1))
        self.assertEqual([p['status'] for p in shown['posts']], ['in-library', 'new', 'in-library'])
        result, _ = self.run_links(text, reader, operation='b' * 32)
        self.assertEqual(len(reader.calls), calls + 1)
        self.assertEqual(reader.calls[-1][0], SITE + 'three/')
        self.assertEqual(len(self.sources()), len(sources) + 1)
        self.assertEqual(
            [r['status'] for r in result['results']], ['in-library', 'imported', 'in-library']
        )
        self.assertTrue(all(r['sample'] for r in result['results']))
        names = sorted(c['name'] for c in library.collections(self.root).values())
        self.assertEqual(len(names), 2)
        self.assertTrue(names[1].startswith('Published posts by ' + AUTHOR + ' · '))

    def test_a_library_refresh_keeps_the_classified_author(self):
        reader = Pages({SITE + 'one/': page('One', AUTHOR)})
        result, _ = self.run_links(self.links('one'), reader)
        key = next(iter(library.collections(self.root)))
        preview = library.preview(self.root, key, reader=reader)['preview']
        refreshed = library.import_batch(self.root, preview, reader=reader, delay=0)
        self.assertEqual(refreshed['counts']['unchanged'], 1)
        _, record = studio.item(self.root, 'sources', result['samples'][0])
        self.assertEqual((record['author'], record['library']['author']), (AUTHOR, None))
        self.assertIn('voice-sample', record['purposes'])

    def test_batches_limits_and_changed_previews(self):
        names = ['post-' + str(n) for n in range(27)]
        reader = Pages({SITE + n + '/': page(n, AUTHOR) for n in names})
        text = self.links(*names)
        first, _ = self.run_links(text, reader)
        self.assertEqual((first['counts']['imported'], first['remaining']), (25, 2))
        self.assertIn('2 links are still to import', first['next_step'])
        rest, _ = self.run_links(text, reader)
        self.assertEqual((rest['counts']['imported'], rest['remaining']), (27, 0))
        self.assertEqual(len(reader.calls), 27)
        with self.assertRaisesRegex(ValueError, 'changed since the check'):
            voice_links.run(
                self.root,
                {
                    'operation': 'c' * 32,
                    'text': self.links('new'),
                    'author': AUTHOR,
                    'expected': 'stale',
                },
                reader=reader,
            )
        with self.assertRaisesRegex(ValueError, 'different list'):
            voice_links.run(
                self.root,
                {'operation': 'a' * 32, 'text': self.links('new'), 'author': AUTHOR},
                reader=reader,
            )
        with self.assertRaisesRegex(ValueError, 'one site at a time'):
            voice_links.run(
                self.root,
                {
                    'operation': 'd' * 32,
                    'text': text + 'https://other.example/x/\n',
                    'author': AUTHOR,
                },
                reader=reader,
            )
        with self.assertRaisesRegex(ValueError, 'author name'):
            voice_links.preview(self.root, {'text': text, 'author': '  '})

    def test_desk_routes_check_then_import_with_the_library_fetcher(self):
        reader = Pages({SITE + 'one/': page('One', AUTHOR, 'byline')})
        text = self.links('one')
        with patch.object(library, 'fetch', side_effect=reader):
            shown = management.dispatch(
                self.root, 'voice-links-preview', {'text': text, 'author': AUTHOR}
            )
            self.assertEqual(reader.calls, [])
            with self.assertRaisesRegex(ValueError, 'Check the links'):
                management.dispatch(
                    self.root,
                    'voice-links-import',
                    {'operation': 'a' * 32, 'text': text, 'author': AUTHOR},
                )
            result = management.dispatch(
                self.root,
                'voice-links-import',
                {
                    'operation': 'a' * 32,
                    'text': text,
                    'author': AUTHOR,
                    'expected': shown['expected'],
                    'keep': [],
                },
            )
        self.assertEqual(result['sharing'], 'local-only')
        self.assertEqual(result['counts']['samples'], 1)
        self.assertNotIn(str(self.root), json.dumps(result))
        with self.assertRaisesRegex(ValueError, 'Unknown voice import field'):
            management.dispatch(
                self.root, 'voice-links-preview', {'text': text, 'author': AUTHOR, 'x': 1}
            )

    def test_desk_routes_and_command_line_take_style_samples(self):
        reader = Pages({SITE + 'one/': page('One', 'Someone Else')})
        text = self.links('one')
        data = {'text': text, 'author': 'Release notes', 'purpose': 'style-sample'}
        with patch.object(library, 'fetch', side_effect=reader):
            shown = management.dispatch(self.root, 'voice-links-preview', data)
            result = management.dispatch(
                self.root,
                'voice-links-import',
                {**data, 'operation': 'a' * 32, 'expected': shown['expected']},
            )
        self.assertEqual(result['counts']['samples'], 1)
        _, record = studio.item(self.root, 'sources', result['samples'][0])
        self.assertIn('style-sample', record['purposes'])
        listing = self.base / 'release-notes.txt'
        listing.write_text(self.links('two'))
        reader.pages[SITE + 'two/'] = page('Two', 'Someone Else')
        args = studio.parser().parse_args(
            ['--root', str(self.root), 'library', 'voice-links', '--file', str(listing)]
            + ['--purpose', 'style-sample', '--import']
        )
        with (
            patch.object(library, 'fetch', side_effect=reader),
            patch.object(library.time, 'sleep'),
        ):
            found = library.command(self.root, args)
        self.assertEqual((found['author'], found['counts']['samples']), ('Release Notes', 1))
        _, record = studio.item(self.root, 'sources', found['samples'][0])
        self.assertEqual(record['purposes'].count('style-sample'), 1)
        self.assertNotIn('voice-sample', record['purposes'])

    def test_a_style_list_without_a_label_asks_for_one(self):
        listing = self.base / 'links.txt'
        listing.write_text(self.links('one'))
        for purpose, wording in (
            ('style-sample', 'Label these examples'),
            ('voice-sample', 'Name the author'),
        ):
            args = studio.parser().parse_args(
                ['--root', str(self.root), 'library', 'voice-links', '--file', str(listing)]
                + ['--purpose', purpose]
            )
            with self.assertRaisesRegex(ValueError, wording):
                library.command(self.root, args)

    def test_command_line_checks_then_imports_the_same_list(self):
        listing = self.base / 'avery-quinn-blog-links.txt'
        listing.write_text('# Synthetic\n' + self.links('one', 'two'))
        reader = Pages({SITE + n + '/': page(n, AUTHOR) for n in ('one', 'two')})
        parser = studio.parser()
        args = parser.parse_args(
            ['--root', str(self.root), 'library', 'voice-links', '--file', str(listing)]
        )
        with patch.object(library, 'fetch', side_effect=reader):
            shown = library.command(self.root, args)
            self.assertEqual(
                (shown['author'], shown['links'], shown['shown_scope']),
                (AUTHOR, 2, 'blog.example/team/'),
            )
            self.assertEqual(reader.calls, [])
            args = parser.parse_args(
                [
                    '--root',
                    str(self.root),
                    'library',
                    'voice-links',
                    '--file',
                    str(listing),
                    '--import',
                ]
            )
            with patch.object(library.time, 'sleep'):
                result = library.command(self.root, args)
                again = library.command(self.root, args)
        self.assertEqual(result['counts']['samples'], 2)
        self.assertEqual(again['operation'], result['operation'])
        self.assertEqual(len(reader.calls), 2)


class TeamHubTests(Fixture):
    def test_samples_are_shared_with_the_selected_hub(self):
        provider = FakeProvider(self.base / 'remotes')
        registry = Registry(self.base / 'hubs', provider)
        hub_id = registry.create('fixture/voices', 'voices')['hub']
        adapter = Workspace(self.root, registry.hub(hub_id))
        reader = Pages(
            {SITE + 'one/': page('One', AUTHOR), SITE + 'two/': page('Two', 'Jordan Lee')}
        )
        text = SITE + 'one/\n' + SITE + 'two/\n'
        with patch('hub_workspace.active', return_value=adapter):
            shown = voice_links.preview(self.root, {'text': text, 'author': AUTHOR})
            result = voice_links.run(
                self.root,
                {
                    'operation': 'a' * 32,
                    'text': text,
                    'author': AUTHOR,
                    'expected': shown['expected'],
                },
                reader=reader,
                delay=0,
            )
            self.assertIn(result['hub_sync']['status'], ('synchronized', 'shared'))
            shared = {
                row['record']['library']['canonical_url']: row['record']
                for row in library.source_rows(self.root)
            }
            graph = adapter.hub.graph()
        heads = {
            graph['revisions'][heads[0]]['data']['studio']['library']['canonical_url']: graph[
                'revisions'
            ][heads[0]]['data']['studio']
            for heads in graph['heads'].values()
            if graph['revisions'][heads[0]]['kind'] == 'source'
        }
        self.assertIn('voice-sample', heads[SITE + 'one/']['purposes'])
        self.assertEqual(heads[SITE + 'one/']['author'], AUTHOR)
        self.assertNotIn('voice-sample', heads[SITE + 'two/']['purposes'])
        self.assertEqual(set(shared), set(heads))


if __name__ == '__main__':
    import unittest

    unittest.main()
