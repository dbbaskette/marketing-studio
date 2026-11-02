"""A published post brought to the desk for a GEO review: by its link (read from a local fake
site on 127.0.0.1, never the real network), from a team collection, and with Review for AI
search (GEO) as the first pass. Page access is advice only. No provider job runs."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)

import desk_jobs
import published_post
import studio
import tool_jobs
from fake_site import Site
from test_desk import RouteCase

POST = """<!doctype html><html><head><title>Retry budgets | Example blog</title>
<meta name="description" content="Synthetic.">
{head}</head><body>
<header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
<main><article>
<h1>Retry budgets</h1>
<p class="byline">By Jane Doe</p>
<p class="post-date"><time datetime="2025-03-01">1 March 2025</time></p>
<p>A retry budget caps the retries each route may make. It keeps a slow service from being
flooded by its own clients.</p>
<h2>How it works</h2>
<p>Each route keeps a <a href="/glossary#budget">budget</a> of retries per minute.</p>
<img src="/images/budget-chart.png">
<img src="/images/flow.png" alt="Requests flowing through the budget">
<h2>Next steps</h2>
<p>Try a budget on one route first.</p>
</article>
<article><h2>Related posts</h2><p>Another post.</p></article>
</main><footer>Footer links</footer></body></html>"""


def page(head=''):
    return POST.replace('{head}', head)


class ReadTests(RouteCase):
    URL = 'https://blog.example.com/posts/retry-budgets'

    def site(self, head='', robots=None, **headers):
        site = Site()
        site.page('/posts/retry-budgets', page(head), **headers)
        if robots is not None:
            site.page('/robots.txt', robots, kind='text/plain')
        return site

    def read(self, site, url=None):
        with site.serving():
            return published_post.read(url or self.URL)

    def check(self, found, key):
        return next(check for check in found['access']['checks'] if check['key'] == key)

    def test_the_article_is_read_as_markdown_without_the_sites_furniture(self):
        site = self.site(robots='User-agent: *\nAllow: /\n')
        found = self.read(site)
        self.assertEqual(found['title'], 'Retry budgets')
        text = found['markdown']
        self.assertTrue(text.startswith('# Retry budgets\n\nA retry budget caps'))
        self.assertIn('## How it works', text)
        self.assertIn('[budget](https://blog.example.com/glossary#budget)', text)
        self.assertIn('![](https://blog.example.com/images/budget-chart.png)', text)
        self.assertIn(
            '![Requests flowing through the budget](https://blog.example.com/images/flow.png)',
            text,
        )
        for furniture in ('Home', 'Footer links', 'By Jane Doe', 'Related posts', '1 March'):
            self.assertNotIn(furniture, text)
        self.assertEqual(len(found['images']), 2)
        self.assertEqual(found['final_url'], self.URL)
        # Only the page and robots.txt were asked for, from the post's own host.
        self.assertEqual(
            [path for _, path in site.requests], ['/posts/retry-budgets', '/robots.txt']
        )
        self.assertEqual({host for host, _ in site.requests}, {'blog.example.com'})

    def test_page_access_reads_a_noindex_header(self):
        found = self.read(self.site(**{'X-Robots-Tag': 'noindex, nofollow'}))
        said = self.check(found, 'noindex')
        self.assertEqual(said['status'], 'problem')
        self.assertIn('X-Robots-Tag header', said['said'])
        self.assertNotIn('robots meta tag', said['said'])

    def test_page_access_reads_a_noindex_meta_tag(self):
        found = self.read(self.site(head='<meta name="robots" content="noindex">'))
        said = self.check(found, 'noindex')
        self.assertEqual(said['status'], 'problem')
        self.assertIn('robots meta tag', said['said'])
        clear = self.read(self.site())
        self.assertEqual(self.check(clear, 'noindex')['status'], 'ok')

    def test_page_access_reads_a_robots_txt_that_blocks_an_ai_search_crawler(self):
        robots = 'User-agent: OAI-SearchBot\nDisallow: /posts/\n\nUser-agent: GPTBot\nDisallow: /\n'
        said = self.check(self.read(self.site(robots=robots)), 'robots')
        self.assertEqual(said['status'], 'problem')
        self.assertEqual(said['blocked'], ['OAI-SearchBot'])
        self.assertIn('ChatGPT search (OAI-SearchBot)', said['said'])
        self.assertTrue(said['training_blocked'])
        self.assertIn('does not affect search', said['said'])

    def test_a_missing_robots_txt_is_not_checked_rather_than_a_problem(self):
        said = self.check(self.read(self.site()), 'robots')
        self.assertEqual(said['status'], 'unknown')
        self.assertIn('Couldn’t check robots.txt', said['said'])

    def test_page_access_says_when_json_ld_disagrees_with_the_byline(self):
        head = (
            '<script type="application/ld+json">{"@context": "https://schema.org", '
            '"@type": "BlogPosting", "headline": "Retry budgets", "author": {"@type": '
            '"Person", "name": "Sam Roe"}, "datePublished": "2025-03-01"}</script>'
        )
        found = self.read(self.site(head=head))
        said = self.check(found, 'structured')
        self.assertEqual(said['status'], 'problem')
        self.assertEqual(
            said['disagree'], [{'field': 'author', 'data': 'Sam Roe', 'page': 'Jane Doe'}]
        )
        byline = self.check(found, 'byline')
        self.assertEqual((byline['status'], byline['byline']), ('ok', 'Jane Doe'))
        self.assertEqual(byline['dates'], ['2025-03-01'])
        self.assertIn('eligibility checks', found['access']['eligibility'])
        self.assertIn('belong to the site owner', found['access']['site_owner'])

    def test_a_login_wall_an_unsupported_type_and_a_large_page_are_refused_plainly(self):
        site = Site()
        site.page('/locked', 'Sign in', kind='text/html', status=401)
        site.page(
            '/login',
            '<html><body><main><h1>Sign in</h1><form><input type="password"></form></main></body></html>',
        )
        site.page('/report.pdf', b'%PDF-1.4', kind='application/pdf')
        site.page('/huge', b'<p>' + b'x' * (2 * 1024 * 1024 + 10) + b'</p>')
        site.page('/gone', 'Gone', status=404)
        with site.serving():
            for path, said in (
                ('/locked', 'asks for a sign-in'),
                ('/login', 'asks for a sign-in'),
                ('/report.pdf', 'it is application/pdf'),
                ('/huge', 'larger than Blog Studio reads'),
                ('/gone', 'not found'),
            ):
                with self.subTest(path=path):
                    with self.assertRaisesRegex(ValueError, said):
                        published_post.read('https://blog.example.com' + path)
        with self.assertRaisesRegex(ValueError, 'public https link'):
            published_post.read('http://blog.example.com/post')

    def test_a_redirect_to_another_site_is_not_followed(self):
        site = Site()
        site.page('/moved', '', status=302, Location='https://elsewhere.example.net/post')
        with site.serving():
            with self.assertRaisesRegex(ValueError, 'moves to another site'):
                published_post.read('https://blog.example.com/moved')
        self.assertEqual([path for _, path in site.requests], ['/moved'])


class DeskLinkTests(RouteCase):
    URL = ReadTests.URL

    def preview(self):
        site = Site()
        site.page('/posts/retry-budgets', page())
        with site.serving():
            return self.post('published-preview', {'url': self.URL})

    def test_a_link_is_previewed_then_brought_to_the_desk_as_a_copy_with_the_geo_review(self):
        shown = self.preview()
        self.assertEqual(shown['status'], 'preview')
        self.assertEqual(shown['title'], 'Retry budgets')
        self.assertEqual(shown['summary']['images_without_alt'], 1)
        self.assertEqual(list(studio.inside(self.root, 'articles').glob('*')), [])
        self.assertEqual(tool_jobs.listing(self.root), [], 'reading starts nothing')
        made = self.post(
            'desk-create',
            {
                'operation': 'b' * 32,
                'first_pass': 'geo',
                'published': {'preview': shown['preview'], 'expected': shown['expected']},
            },
        )
        self.assertEqual(made['title'], 'Retry budgets')
        self.assertIsNone(made['first_pass_problem'])
        _, record = studio.item(self.root, 'articles', made['id'])
        self.assertEqual(record['published_post']['url'], self.URL)
        self.assertNotIn('markdown', record['published_post'], 'the record keeps the link')
        self.assertTrue(record['geo_review']['include'])
        self.assertTrue(record['geo_review']['queued_at'])
        job = tool_jobs.read(self.root, made['working']['id'])
        self.assertEqual(job['kind'], 'finish-geo')
        self.assertEqual(record['geo_review']['job'], job['id'])
        self.assertIn('Retry budgets', job['payload']['title'])
        # The review proposes; nothing in the text changes, and it never queues twice.
        self.assertEqual(desk_jobs.geo_due(self.root, made['id']), False)
        self.assertEqual(made['geo_review']['status'], 'working')

    def test_a_changed_or_unknown_read_is_refused(self):
        shown = self.preview()
        for chosen, said in (
            ({'preview': shown['preview'], 'expected': 'f' * 32}, 'changed'),
            ({'preview': 'e' * 32, 'expected': shown['expected']}, 'no longer kept'),
            ({'preview': 'x'}, 'Read the page first'),
        ):
            with self.subTest(said=said):
                with self.assertRaisesRegex(ValueError, said):
                    self.post(
                        'desk-create',
                        {'operation': 'c' * 32, 'first_pass': 'leave', 'published': chosen},
                    )

    def test_review_for_ai_search_works_for_a_pasted_draft(self):
        made = self.start(first_pass='geo')
        job = tool_jobs.read(self.root, made['working']['id'])
        self.assertEqual(job['kind'], 'finish-geo')
        self.assertTrue(job['metadata']['desk'].get('auto'))


class CollectionTests(RouteCase):
    def imported(self):
        """A post saved by Import old blogs, as its batch saves one."""
        ident = 'post-' + 'a' * 32
        directory = studio.inside(self.root, 'sources', ident)
        directory.mkdir(parents=True)
        (directory / 'original.html').write_text(page())
        (directory / 'content.md').write_text('Retry budgets as plain text.')
        record = {
            'id': ident,
            'name': 'Retry budgets',
            'purposes': ['reference'],
            'revision': 1,
            'created_at': studio.now(),
            'status': 'ready',
            'original_path': 'original.html',
            'library': {
                'identity': ReadTests.URL,
                'collections': ['old-blog'],
                'canonical_url': ReadTests.URL,
                'historical': True,
                'curation': 'active',
            },
        }
        studio.persist(directory, 'sources', record)
        return ident, directory

    def test_a_collection_post_comes_to_the_desk_as_a_copy_and_the_entry_stays(self):
        ident, directory = self.imported()
        before = {path.name: path.read_bytes() for path in directory.iterdir()}
        shown = self.post('published-preview', {'item': ident, 'location': 'local'})
        self.assertIn('## How it works', shown['content'])
        self.assertEqual(shown['collection_item']['id'], ident)
        made = self.post(
            'desk-create',
            {
                'operation': 'd' * 32,
                'first_pass': 'geo',
                'published': {'preview': shown['preview'], 'expected': shown['expected']},
            },
        )
        _, record = studio.item(self.root, 'articles', made['id'])
        self.assertEqual(
            record['published_post']['collection_item'], {'id': ident, 'location': 'local'}
        )
        self.assertEqual([s['source_id'] for s in record['sources']], [], 'not pinned as a source')
        self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, before)

    def test_only_a_collection_post_is_taken(self):
        ident, directory = self.imported()
        _, record = studio.item(self.root, 'sources', ident)
        record['library'] = {'curation': 'active'}
        studio.persist(directory, 'sources', record)
        with self.assertRaisesRegex(ValueError, 'imported from one of your team collections'):
            self.post('published-preview', {'item': ident, 'location': 'local'})
