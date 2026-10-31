"""Research from your documents, your sites and/or the public web."""
import json
import unittest

from test_home import IsolatedHome
from marketing_studio import shared
from studio_core import onboarding, preferences, research_sites as rs

TANZU = 'https://blogs.vmware.com/tanzu'
DOCS = 'https://docs.example.com'


class SiteFormatTests(unittest.TestCase):
    def test_canonical_sites(self):
        for given, wanted in (
                ('https://blogs.vmware.com/tanzu/', TANZU),
                ('blogs.vmware.com/tanzu', TANZU),
                ('  HTTPS://Blogs.VMware.com/tanzu  ', TANZU),
                ('https://docs.example.com/', DOCS),
                ('https://docs.example.com:443/Guide', 'https://docs.example.com/Guide'),
                ('docs.example.com', DOCS)):
            with self.subTest(given=given):
                self.assertEqual(rs.site(given), wanted)

    def test_refused_sites_name_the_entry(self):
        for given in ('http://blogs.vmware.com/tanzu', 'https://blogs.vmware.com/tanzu?x=1',
                      'https://blogs.vmware.com/tanzu#top', 'https://me:pw@example.com',
                      'https://me@example.com', 'https://example.com:8443/', 'ftp://example.com',
                      'https://localhost/', 'https://127.0.0.1/', 'https://10.0.0.4/docs',
                      'https://192.168.1.1', 'https://[::1]/', 'https://169.254.169.254/',
                      'https://intranet/', 'https://wiki.corp.internal/', 'https://printer.local',
                      'https://app.localhost', 'https://example.com/a/../b', 'https://example.com/./a',
                      'https://exa mple.com', '', 'x' * 3000, 'https://', 'https://-bad.example.com'):
            with self.subTest(given=given), self.assertRaises(ValueError) as caught:
                rs.site(given)
            self.assertTrue(str(caught.exception).strip())

    def test_public_ip_literal_is_a_site(self):
        self.assertEqual(rs.site('https://8.8.8.8/x'), 'https://8.8.8.8/x')

    def test_list_is_deduplicated_ordered_and_limited(self):
        self.assertEqual(rs.sites([TANZU + '/', DOCS, 'blogs.vmware.com/tanzu']), [TANZU, DOCS])
        self.assertEqual(rs.sites([]), [])
        with self.assertRaises(ValueError):
            rs.sites([f'https://s{n}.example.com' for n in range(51)])
        self.assertEqual(len(rs.sites([f'https://s{n}.example.com' for n in range(50)])), 50)
        for wrong in ('https://example.com', None, [1], {'a': 1}):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                rs.sites(wrong)
        with self.assertRaises(ValueError) as caught:
            rs.sites([TANZU, 'http://bad.example.com'])
        self.assertIn('http://bad.example.com', str(caught.exception))

    def test_shown_as_host_and_path(self):
        self.assertEqual(rs.shown(TANZU), 'blogs.vmware.com/tanzu')
        self.assertEqual(rs.shown(DOCS), 'docs.example.com')

    def test_defaults_read_the_shared_list_and_skip_what_cannot_be_used(self):
        self.assertEqual(rs.defaults({}), [])
        self.assertEqual(rs.defaults({'research': {'sites': [TANZU, 'http://x.example', DOCS]}}),
                         [TANZU, DOCS])
        self.assertEqual(rs.defaults({'research': 'nonsense'}), [])


class UnderTests(unittest.TestCase):
    def test_host_and_segment_boundaries(self):
        sites = [TANZU, DOCS]
        for url in ('https://blogs.vmware.com/tanzu', 'https://blogs.vmware.com/tanzu/',
                    'https://blogs.vmware.com/tanzu/2024/post?x=1#y',
                    'https://BLOGS.vmware.com/tanzu/a', 'https://docs.example.com/',
                    'https://docs.example.com/any/page', 'https://docs.example.com:443/a'):
            with self.subTest(url=url):
                self.assertIsNotNone(rs.under(url, sites))
        for url in ('https://blogs.vmware.com/tanzu-other/', 'https://blogs.vmware.com/tanzuX',
                    'https://blogs.vmware.com/', 'https://blogs.vmware.com/Tanzu/a',
                    'https://blogs.vmware.com.evil.example/tanzu/', 'https://evil.example/blogs.vmware.com/tanzu',
                    'https://sub.docs.example.com/', 'http://docs.example.com/a',
                    'https://docs.example.com:8443/a', 'https://blogs.vmware.com/tanzu/../other',
                    'https://blogs.vmware.com/tanzu/%2e%2e/other', 'https://blogs.vmware.com/tanzu%2f..%2fother',
                    'https://user@docs.example.com/', 'not a url', ''):
            with self.subTest(url=url):
                self.assertIsNone(rs.under(url, sites))


class ChoiceTests(unittest.TestCase):
    def test_choice_shape_and_validation(self):
        self.assertEqual(rs.choice({'documents': True, 'sites': [TANZU + '/'], 'web': False}),
                         {'documents': True, 'sites': [TANZU], 'web': False})
        self.assertEqual(rs.choice({'web': True}), {'documents': False, 'sites': [], 'web': True})
        for wrong in ({}, {'documents': False, 'sites': [], 'web': False}, 'web', None,
                      {'web': 'yes'}, {'web': True, 'other': 1}):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                rs.choice(wrong)
        # Documents count only when documents were given.
        with self.assertRaises(ValueError) as caught:
            rs.choice({'documents': True}, documents_given=False)
        self.assertIn('your sites or the public web', str(caught.exception))
        self.assertEqual(rs.choice({'documents': True, 'web': True}, documents_given=False),
                         {'documents': False, 'sites': [], 'web': True})

    def test_legacy_values(self):
        documents = {'documents': True, 'sites': [], 'web': False}
        both = {'documents': True, 'sites': [], 'web': True}
        for old in ('supplied-only', 'documents', 'selected'):
            self.assertEqual(rs.legacy(old), documents)
        for old in ('web-allowed', 'public', 'public-web', 'both', 'mixed'):
            self.assertEqual(rs.legacy(old), both)
        self.assertIsNone(rs.legacy('none'))
        self.assertEqual(rs.legacy({'documents': False, 'sites': [DOCS], 'web': False}),
                         {'documents': False, 'sites': [DOCS], 'web': False})
        self.assertEqual(rs.effective(rs.legacy('public'), documents_given=False),
                         {'documents': False, 'sites': [], 'web': True})

    def test_modes_and_scopes(self):
        cases = (({'documents': True, 'sites': [], 'web': False}, 'selected', 'supplied-only'),
                 ({'documents': True, 'sites': [TANZU], 'web': False}, 'mixed', 'public-web'),
                 ({'documents': False, 'sites': [TANZU], 'web': False}, 'public', 'public-web'),
                 ({'documents': True, 'sites': [], 'web': True}, 'mixed', 'public-web'),
                 ({'documents': False, 'sites': [], 'web': True}, 'public', 'public-web'))
        for chosen, mode, scope in cases:
            with self.subTest(chosen=chosen):
                self.assertEqual(rs.source_mode(chosen), mode)
                self.assertEqual(rs.plan_scope(chosen), scope)
                self.assertEqual(rs.fetches(chosen), scope == 'public-web')

    def test_summary_names_the_sites(self):
        self.assertEqual(rs.summary({'documents': True, 'sites': [TANZU, DOCS, 'https://c.example.com'], 'web': False}),
                         'from your documents and 3 of your sites (blogs.vmware.com/tanzu, docs.example.com, c.example.com)')
        self.assertEqual(rs.summary({'documents': False, 'sites': [TANZU], 'web': True}),
                         'from 1 of your sites (blogs.vmware.com/tanzu) and the public web')
        self.assertEqual(rs.summary({'documents': True, 'sites': [], 'web': True}),
                         'from your documents and the public web')
        self.assertEqual(rs.summary({'documents': True, 'sites': [TANZU], 'web': True}),
                         'from your documents, 1 of your sites (blogs.vmware.com/tanzu) and the public web')
        many = [f'https://s{n}.example.com' for n in range(7)]
        self.assertTrue(rs.summary({'documents': False, 'sites': many, 'web': False}).endswith('and 2 more)'))

    def test_scope_text_and_guidance(self):
        sites_only = {'documents': False, 'sites': [TANZU, DOCS], 'web': False}
        text = rs.scope_text(sites_only)
        self.assertIn('blogs.vmware.com/tanzu', text)
        self.assertIn('docs.example.com', text)
        self.assertIn('not', text)
        self.assertIn('site:blogs.vmware.com/tanzu', rs.guidance(sites_only))
        self.assertIn('only', rs.guidance(sites_only))
        mixed = {'documents': True, 'sites': [TANZU], 'web': True}
        self.assertIn('gaps', rs.guidance(mixed))
        self.assertIn('gaps', rs.scope_text(mixed))
        self.assertEqual(rs.guidance({'documents': True, 'sites': [], 'web': False}), '')


class RefusedTests(unittest.TestCase):
    def test_sites_only_refuses_outside_and_names_the_sites(self):
        chosen = {'documents': False, 'sites': [TANZU], 'web': False}
        self.assertIsNone(rs.refused('https://blogs.vmware.com/tanzu/post', chosen))
        for url in ('https://blogs.vmware.com/tanzu-other/', 'https://blogs.vmware.com.evil.example/tanzu/x',
                    'https://example.org/'):
            with self.subTest(url=url):
                said = rs.refused(url, chosen)
                self.assertIn('blogs.vmware.com/tanzu', said)
                self.assertIn('not saved', said)
        said = rs.refused('https://example.org/', chosen, redirected_from='https://blogs.vmware.com/tanzu/a')
        self.assertIn('redirected', said)
        self.assertIn('example.org', said)

    def test_web_on_allows_any_public_url(self):
        for chosen in ({'documents': False, 'sites': [TANZU], 'web': True},
                       {'documents': True, 'sites': [], 'web': True}):
            with self.subTest(chosen=chosen):
                self.assertIsNone(rs.refused('https://example.org/anything', chosen))
                self.assertIsNone(rs.refused('http://example.org/anything', chosen))

    def test_documents_only_saves_nothing(self):
        self.assertIn('your documents', rs.refused('https://example.org/', {'documents': True, 'sites': [], 'web': False}))

    def test_scope_object(self):
        scope = rs.Scope({'documents': False, 'sites': [TANZU], 'web': False})
        self.assertIsNone(scope.refuse('https://blogs.vmware.com/tanzu/a'))
        self.assertIn('blogs.vmware.com/tanzu', scope.refuse('https://blogs.vmware.com/'))
        self.assertEqual(rs.Scope.load(scope.dump()).choice, scope.choice)


def server_view(url):
    """(host, path) as urllib sends a URL and a lenient server would act on it: once
    decoded, backslashes as slashes, ;-parameters dropped from each segment, dot segments
    resolved. Nothing is fetched."""
    import posixpath
    import re
    import urllib.request
    from urllib.parse import unquote
    request = urllib.request.Request(url.strip())
    host = re.sub(r':0*443$|:$', '', request.host.lower().rsplit('@', 1)[-1]).rstrip('.')
    path = unquote(request.selector.split('?', 1)[0]).replace('\\', '/')
    path = '/'.join(segment.split(';', 1)[0] for segment in path.split('/'))
    path = posixpath.normpath(path) if path else '/'
    return host, '/' + path.lstrip('/') if path.startswith('//') else path


def really_under(host, path, listed):
    from urllib.parse import urlsplit
    for base in listed:
        target = urlsplit(base)
        prefix = target.path.rstrip('/')
        if target.hostname == host and (not prefix or path == prefix or path.startswith(prefix + '/')):
            return True
    return False


class ReviewTests(unittest.TestCase):
    """Cases from the review of the first version: none may pass under() and land
    outside the sites as a lenient server reads the request."""

    SITES = [TANZU, DOCS]
    CASES = (
        'https://blogs.vmware.com/tanzu/a', 'https://BLOGS.VMWARE.COM/tanzu/a', 'https://blogs.vmware.com./tanzu/a',
        'https://blogs.vmware.com:443/tanzu/a', 'https://blogs.vmware.com:0443/tanzu/a', 'https://blogs.vmware.com:8443/tanzu/a',
        'https://user@blogs.vmware.com/tanzu/a', 'https://@blogs.vmware.com/tanzu/a', 'https://blogs.vmware.com@evil.com/tanzu/a',
        'https://evil.com@blogs.vmware.com/tanzu/a', 'https://evil.com#@blogs.vmware.com/tanzu', 'https://evil.com?@blogs.vmware.com/tanzu',
        'https://blogs.vmware.com/tanzu/%2e%2e/admin', 'https://blogs.vmware.com/tanzu/%252e%252e/admin', 'https://blogs.vmware.com/tanzu/.%2e/admin',
        'https://blogs.vmware.com/tanzu/..%2fadmin', 'https://blogs.vmware.com/tanzu/..%252fadmin', 'https://blogs.vmware.com/tanzu/..;/admin',
        'https://blogs.vmware.com/tanzu/..\\admin', 'https://blogs.vmware.com/tanzu%2f..%2fadmin', 'https://blogs.vmware.com/tanzu/../admin',
        'https://blogs.vmware.com//tanzu/a', 'https://blogs.vmware.com/tanzu//a', 'https://blogs.vmware.com/tanzu-other/a', 'https://blogs.vmware.com/Tanzu/a',
        'https://blogs.vmware.com/tanzu?x=/../admin', 'https://blogs.vmware.com/admin?/tanzu', 'https://blogs.vmware.com/admin#/tanzu',
        'https://blogs.vmware.com/', 'https://blogs.vmware.com', 'https://blogs.vmware.com/tanzu', 'https://blogs.vmware.com/tanz%75/a',
        'http://blogs.vmware.com/tanzu/a', 'HTTPS://blogs.vmware.com/tanzu/a', 'https:/blogs.vmware.com/tanzu/a', 'https:blogs.vmware.com/tanzu/a',
        'https://blogs.vmware.com.evil.example/tanzu/a', 'https://evilblogs.vmware.com/tanzu', 'https://x.blogs.vmware.com/tanzu',
        'https://blogs.vmwаre.com/tanzu', 'https://blogs.vmware.com\\@evil.com/tanzu', 'https://blogs.vmware.com%2f@evil.com/tanzu',
        'https://blogs.vmware.com%40evil.com/tanzu', ' https://blogs.vmware.com/tanzu/a', 'https://blogs.vmware.com/tanzu/a\n',
        'https://blogs.vmware.com/tanzu/%00', 'https://blogs.vmware.com/tanzu/%0d%0aHost:evil', 'https://[::1]/tanzu', 'https://127.0.0.1/tanzu',
        'https://docs.example.com/anything', 'https://docs.example.com:443@evil.com/', 'https://docs.example.com../', 'https://docs.example.com/%2e%2e/%2e%2e/x',
        'https://blogs.vmware.com/tanzu/a/../../admin', 'https://blogs.vmware.com/tanzu/a/%2e%2e/%2e%2e/admin', 'https://blogs.vmware.com/tanzu/a/.%252e/admin',
        'https://blogs.vmware.com/%74anzu/../admin', 'https://blogs.vmware.com/tanzu/..%00/admin', 'https://blogs.vmware.com/tanzu/..%20/admin',
        'https://blogs.vmware.com/tanzu/...', 'https://blogs.vmware.com/tanzu/a?b', 'https://blogs.vmware.com/tanzu/a#..',
        'https://blogs.vmware.com:/tanzu/a', 'https://blogs.vmware.com:443:443/tanzu', 'https://[blogs.vmware.com]/tanzu',
        'https://blogs.vmware.com/tanzu#/x/../../admin#z', 'https://blogs.vmware.com/tanzu/x/..;/..;/admin',
        'https://blogs.vmware.com/tanzu/x/.;a/..;b/..;c/admin', 'https://blogs.vmware.com/tanzu/%2e%2e;/admin',
    )

    def check(self, url):
        if not rs.under(url, self.SITES):
            return
        try:
            host, path = server_view(rs.fetchable(url))
        except Exception:
            return
        self.assertTrue(really_under(host, path, self.SITES), f'{url!r} reaches {host} {path}')

    def test_table(self):
        for url in self.CASES:
            with self.subTest(url=url):
                self.check(url)
        for url in ('https://blogs.vmware.com/tanzu#/x/../../admin#z', 'https://blogs.vmware.com/tanzu/x/..;/..;/admin',
                    'https://blogs.vmware.com/tanzu/..;/admin'):
            self.assertIsNone(rs.under(url, self.SITES), url)
        self.assertIsNotNone(rs.under('https://blogs.vmware.com/tanzu/a;jsessionid=1', self.SITES))

    def test_fuzz(self):
        import random
        chance = random.Random(1)
        alphabet = ['/', '.', '..', '%2e', '%2E', '%25', '%2f', ';', '\\', '@', ':', '#', '?', 'tanzu',
                    'admin', 'a', '%00', '%5c', '//', '%252e', ' ', '\t', '%3b', '%2e%2e']
        for _ in range(40000):
            url = TANZU + ''.join(chance.choice(alphabet) for _ in range(chance.randint(1, 8)))
            self.check(url)

    def test_fetchable_drops_the_fragment(self):
        self.assertEqual(rs.fetchable('https://blogs.vmware.com/tanzu/a?b=1#c#d'), 'https://blogs.vmware.com/tanzu/a?b=1')
        self.assertEqual(rs.fetchable('https://blogs.vmware.com/tanzu'), 'https://blogs.vmware.com/tanzu')

    def test_numeric_hex_and_unicode_hosts(self):
        for given in ('https://127.1', 'https://0x7f.1', 'https://2130706433', 'https://1.2.3.04',
                      'https://10.0x1', 'https://100.64.0.1', 'https://0.0.0.0', 'https://[::ffff:127.0.0.1]',
                      'https://foo.home.arpa', 'https://metadata.google.internal', 'https://169.254.169.254'):
            with self.subTest(given=given), self.assertRaises(ValueError):
                rs.site(given)
        self.assertEqual(rs.site('bücher.de'), 'https://xn--bcher-kva.de')
        self.assertEqual(rs.site('xn--bcher-kva.de/a'), 'https://xn--bcher-kva.de/a')
        self.assertTrue(rs.under('https://bücher.de/a/b', ['https://xn--bcher-kva.de/a']))
        self.assertTrue(rs.under('https://xn--bcher-kva.de/a', [rs.site('bücher.de/a')]))
        self.assertIsNone(rs.under('https://blogs.vmwаre.com/tanzu', [TANZU]))
        self.assertEqual(rs.site('https://[2606:4700::1111]/x'), 'https://[2606:4700::1111]/x')
        self.assertTrue(rs.under('https://[2606:4700::1111]/x/y', ['https://[2606:4700::1111]/x']))

    def test_outside_sentence(self):
        self.assertIsNone(rs.outside(0, [TANZU]))
        self.assertIsNone(rs.outside(2, []))
        self.assertEqual(rs.outside(1, [TANZU]),
                         '1 page was outside your sites (blogs.vmware.com/tanzu) and was not saved.')
        self.assertEqual(rs.outside(2, [TANZU, DOCS]),
                         '2 pages were outside your sites (blogs.vmware.com/tanzu, docs.example.com) and were not saved.')
        many = [f'https://s{n}.example.com' for n in range(7)]
        self.assertIn('and 2 more)', rs.outside(3, many))


class SharedSitesTests(IsolatedHome):
    def test_save_canonicalizes_and_preserves_unrelated_values(self):
        shared.path().write_text('{"schema": 1, "unrelated": {"keep": [1, 2]}, "output": "pptx"}')
        seen = preferences.visible(shared.read()[0])
        self.assertEqual(seen['research'], {'sites': []})
        preferences.save(shared, {'research': {'sites': ['blogs.vmware.com/tanzu/', DOCS + '/']}}, seen)
        values = shared.read()[0]
        self.assertEqual(values['research'], {'sites': [TANZU, DOCS]})
        self.assertIn('"unrelated": {"keep": [1, 2]}', shared.path().read_text())
        self.assertEqual(values['output'], 'pptx')

    def test_invalid_site_is_refused_with_its_name_and_nothing_is_written(self):
        shared.path().write_text('{"schema": 1}')
        with self.assertRaises(ValueError) as caught:
            preferences.save(shared, {'research': {'sites': ['https://10.0.0.1/wiki']}}, preferences.visible({}))
        self.assertIn('10.0.0.1', str(caught.exception))
        self.assertNotIn('research', shared.read()[0])
        for wrong in ({'sites': 'https://example.com'}, {'sites': [TANZU], 'other': 1}, ['x']):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                preferences.save(shared, {'research': wrong}, preferences.visible({}))

    def test_outdated_form_is_refused(self):
        shared.path().write_text(json.dumps({'schema': 1, 'research': {'sites': [TANZU]}}))
        seen = preferences.visible(shared.read()[0])
        shared.update({'research': {'sites': [TANZU, DOCS]}})
        with self.assertRaises(ValueError) as caught:
            preferences.save(shared, {'research': {'sites': []}}, seen)
        self.assertIn('Load newer settings', str(caught.exception))
        self.assertEqual(shared.read()[0]['research']['sites'], [TANZU, DOCS])
        # The form that read the current list saves.
        preferences.save(shared, {'research': {'sites': []}}, preferences.visible(shared.read()[0]))
        self.assertEqual(shared.read()[0]['research']['sites'], [])

    def test_a_studio_config_read_refuses_a_research_section_that_is_not_an_object(self):
        shared.path().write_text('{"schema": 1, "research": ["x"]}')
        self.assertTrue(shared.read()[1])

    def test_one_site_is_checked_by_the_server_at_add_and_nothing_is_saved(self):
        from email.message import Message
        from marketing_studio.errors import WorkspaceError
        shared.path().write_text('{"schema": 1}')
        self.assertEqual(self.write('/api/research-site', {'site': 'Blogs.VMware.com/tanzu/'}), {'site': TANZU})
        for wrong in ('https://127.1/', 'http://docs.example.com', 42):
            with self.subTest(wrong=wrong), self.assertRaises(WorkspaceError):
                self.write('/api/research-site', {'site': wrong})
        page = onboarding.Controller(8000, 'a' * 40, 'Training Studio', 'X-Test-Token', lambda _: None, shared)
        headers = Message()
        for key, value in {'Host': '127.0.0.1:8000', 'Origin': 'http://127.0.0.1:8000',
                           'Content-Type': 'application/json', 'X-Test-Token': 'a' * 40}.items():
            headers[key] = value
        for sent, status, wanted in (({'site': 'docs.example.com'}, 200, {'site': DOCS}),
                                     ({'site': 'https://[::1]/'}, 409, None)):
            answer = page.answer('/onboarding/api/research-site', headers, 'POST', json.dumps(sent).encode())
            self.assertEqual(answer[0], status)
            if wanted:
                self.assertEqual(json.loads(answer[2]), wanted)
        self.assertEqual(json.loads(shared.path().read_text()), {'schema': 1})

    def test_marketing_and_standalone_pages_round_trip_the_list(self):
        shared.path().write_text('{"schema": 1}')
        self.write('/api/shared', {'changes': {'research': {'sites': [TANZU]}}, 'seen': {}})
        self.assertEqual(self.page.snapshot()['shared']['research'], {'sites': [TANZU]})
        page = onboarding.Controller(8000, 'a' * 40, 'Blog Studio', 'X-Test-Token', lambda _: None, shared)
        self.assertEqual(page.snapshot()['shared']['research'], {'sites': [TANZU]})
        page.store.update  # the same file
        preferences.save(page.store, {'research': {'sites': [TANZU, DOCS]}},
                         preferences.visible(page.store.read()[0]))
        self.assertEqual(self.page.snapshot()['shared']['research'], {'sites': [TANZU, DOCS]})


class SettingsPageTests(unittest.TestCase):
    def test_review_controls_are_retired(self):
        from pathlib import Path
        web = Path(__file__).resolve().parents[1] / 'core/studio_core/setup_web'
        self.assertNotIn('name="review.level"', (web / 'index.html').read_text())
        self.assertNotIn("wanted.review", (web / 'app.js').read_text())

    def test_settings_page_has_the_research_sites_card(self):
        from pathlib import Path
        web = Path(__file__).resolve().parents[1] / 'core/studio_core/setup_web'
        html = (web / 'index.html').read_text()
        script = (web / 'app.js').read_text()
        self.assertIn('id="research-sites"', html)
        self.assertIn('Research sites', html)
        self.assertIn('id="research-site-add"', html)
        self.assertIn("wanted.research", script)


@unittest.skipUnless(__import__('shutil').which('node'), 'The page journey needs Node.js.')
class SettingsPageJourneyTests(unittest.TestCase):
    def journey(self, steps):
        import subprocess
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp) / 'steps.json'
            typed = [step['type'] for step in steps if 'type' in step]
            answers = {}
            for text in typed:
                try:
                    answers[text] = {'site': rs.site(text)}
                except ValueError as error:
                    answers[text] = {'error': str(error)}
            plan.write_text(json.dumps({'steps': steps, 'answers': answers}))
            done = subprocess.run(['node', str(Path(__file__).with_name('settings_page_harness.js')), str(plan)],
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def page(self, steps, **plan):
        import subprocess
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'steps.json'
            file.write_text(json.dumps({'steps': steps, **plan}))
            done = subprocess.run(['node', str(Path(__file__).with_name('settings_page_harness.js')), str(file)],
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    SHOWN = ("snapshot = {shared: {person: {name: 'Ana'}, research: {sites: []}, review: {level: 'balanced'}, "
             "output: 'pptx', render: {previews: null}}, efforts: {claude: [], '': []}, setup: {done: true}, "
             "studios: [{id: 'blog', name: 'Blog Studio', configured_path: '', path: '/opt/blog'}]};")

    def test_a_setup_step_has_one_title(self):
        shots = self.page([{'run': self.SHOWN + " setup = true; step = 0; show('settings');"},
                           {'snapshot': 'first', 'read': ['#step-label', '#settings-title']}])
        read = shots['first']['read']
        self.assertTrue(read['#step-label']['hidden'] or not read['#step-label']['text'])
        self.assertTrue(read['#settings-title']['hidden'])
        from pathlib import Path
        html = (Path(__file__).resolve().parents[1] / 'core/studio_core/setup_web/index.html').read_text()
        for item in ('1. You and your assistant', '2. Your workspace', '3. Brand and delivery'):
            self.assertIn(item, html)
        self.assertIn('<section id="workspace-part" class="card" data-step="1"><div class="part-head">'
                      '<h3 class="card-title">Your workspace</h3>', html)

    def test_one_save_writes_settings_and_folders(self):
        shots = self.page([
            {'run': self.SHOWN + " setup = false; fill(); renderHome(); show('settings');"},
            {'run': "form.elements['person.name'].value = 'Bea';"
                    " $('#path-fields').children[0].children[1].value = '/srv/blog';"},
            {'responses': {'shared': {'shared': {'person': {'name': 'Bea'}}, 'efforts': {'claude': [], '': []}, 'setup': {'done': True}, 'studios': []},
                           'paths': {'shared': {}, 'efforts': {'claude': [], '': []}, 'setup': {'done': True}, 'studios': []}}},
            {'submit': True}, {'snapshot': 'saved', 'read': ['#problem']}])
        urls = [request['url'] for request in shots['saved']['requests']]
        self.assertEqual([url.split('/api/')[1] for url in urls if url.endswith(('shared', 'paths'))],
                         ['shared', 'paths'])
        sent = [request['sent'] for request in shots['saved']['requests'] if request['url'].endswith('paths')]
        self.assertEqual(sent, [{'paths': {'blog': '/srv/blog'}}])
        from pathlib import Path
        html = (Path(__file__).resolve().parents[1] / 'core/studio_core/setup_web/index.html').read_text()
        self.assertNotIn('id="paths-form"', html)
        self.assertNotIn('Save installation folders', html)

    def test_readiness_refresh_keeps_unsaved_settings_paths_and_seen(self):
        shots = self.page([
            {'run': self.SHOWN + " setup = false; fill(); renderHome(); show('settings');"},
            {'run': "form.elements['person.name'].value = 'Bea';"
                    " $('#path-fields').children[0].children[1].value = '/srv/blog'; view = 'home';"},
            {'responses': {'home': {'studios': [{'id': 'blog', 'name': 'Blog Studio',
                'configured_path': '', 'path': '/new/location', 'installed': True}]}}},
            {'run': "refreshHomeStatus()"},
            {'run': "$('#probe-0').textContent = JSON.stringify({name: form.elements['person.name'].value, "
                    "path: $('#path-fields').children[0].children[1].value, "
                    "shared: snapshot.shared, changes: changesForStep()});"},
            {'snapshot': 'held', 'read': ['#probe-0']}])
        held = json.loads(shots['held']['read']['#probe-0']['text'])
        self.assertEqual((held['name'], held['path']), ('Bea', '/srv/blog'))
        self.assertEqual(held['shared']['person']['name'], 'Ana')
        self.assertEqual(held['shared']['review']['level'], 'balanced')
        self.assertEqual(held['changes']['person']['name'], 'Bea')
        self.assertNotIn('review', held['changes'])

    def test_a_folder_that_fails_says_the_settings_were_saved(self):
        shots = self.page([
            {'run': self.SHOWN + " setup = false; fill(); renderHome(); show('settings');"},
            {'run': " $('#path-fields').children[0].children[1].value = '/nowhere';"},
            {'responses': {'shared': {'shared': {}, 'efforts': {'claude': [], '': []}, 'setup': {'done': True}, 'studios': []},
                           'paths': {'error': 'That folder does not hold Blog Studio.'}}},
            {'submit': True}, {'snapshot': 'refused', 'read': ['#problem-text']}])
        self.assertEqual(shots['refused']['read']['#problem-text']['text'],
                         'Your shared settings were saved. The installation folders were not: '
                         'That folder does not hold Blog Studio.')

    def test_blog_studio_s_own_setup_asks_only_what_it_uses(self):
        shots = self.page([
            {'run': self.SHOWN + " setup = true; step = 0; fill(); show('settings');"},
            {'run': "form.elements['output'].value = 'google';"
                    " $('#probe-0').textContent = JSON.stringify(changesForStep());"
                    " step = 2; show('settings');"
                    " $('#probe-2').textContent = JSON.stringify(changesForStep());"},
            {'snapshot': 'first', 'read': ['#delivery-part', '#probe-0',
                                           '#probe-2']}], product='Blog Studio', standalone=True)
        read = shots['first']['read']
        self.assertTrue(read['#delivery-part']['hidden'])
        first, last = json.loads(read['#probe-0']['text']), json.loads(read['#probe-2']['text'])
        self.assertNotIn('review', first)
        self.assertNotIn('output', last)
        self.assertNotIn('render', last)

    def test_blog_studio_s_shared_settings_after_setup_keep_every_choice(self):
        shots = self.page([
            {'run': self.SHOWN + " setup = false; fill(); show('settings');"},
            {'snapshot': 'later', 'read': ['#delivery-part']}],
            product='Blog Studio', standalone=True)
        read = shots['later']['read']
        self.assertFalse(read['#delivery-part']['hidden'])

    def test_add_remove_refuse_and_save_the_list(self):
        shots = self.journey([
            {'sites': [TANZU]}, {'snapshot': 'shown'},
            {'type': 'https://docs.example.com/'}, {'click': 'add'}, {'snapshot': 'added'},
            {'type': 'docs.example.com'}, {'key': 'Enter'}, {'snapshot': 'duplicate'},
            {'type': 'http://plain.example.com'}, {'click': 'add'}, {'snapshot': 'http'},
            {'type': 'https://10.1.2.3/wiki'}, {'click': 'add'}, {'snapshot': 'private'},
            {'type': 'https://example.com/a?b=1'}, {'click': 'add'}, {'snapshot': 'query'},
            {'type': 'https://127.1/'}, {'click': 'add'}, {'snapshot': 'numeric'},
            {'type': ''}, {'click': 'add'}, {'snapshot': 'blank'},
            {'click': 'remove', 'index': 0}, {'snapshot': 'removed'},
            {'click': 'remove', 'index': 0}, {'snapshot': 'empty'}])
        self.assertEqual(shots['shown']['rows'], ['blogs.vmware.com/tanzu'])
        self.assertEqual(shots['shown']['removeLabels'], ['Remove blogs.vmware.com/tanzu'])
        self.assertTrue(shots['shown']['emptyHidden'])
        self.assertIsNone(shots['shown']['change'])
        self.assertEqual(shots['added']['rows'], ['blogs.vmware.com/tanzu', 'docs.example.com'])
        self.assertEqual(shots['added']['hint'], 'docs.example.com added. Save settings to keep the list.')
        self.assertEqual(shots['added']['input'], '')
        self.assertEqual(shots['added']['change'], {'sites': [TANZU, DOCS]})
        self.assertEqual(shots['duplicate']['hint'], 'docs.example.com is already in your list.')
        self.assertIn('https only', shots['http']['hint'])
        self.assertIn('not a public site', shots['private']['hint'])
        self.assertIn('after ? or #', shots['query']['hint'])
        self.assertEqual(shots['query']['rows'], ['blogs.vmware.com/tanzu', 'docs.example.com'])
        self.assertIn('not a public site', shots['numeric']['hint'])
        # Every typed site was checked by the server; a blank box asks nothing.
        self.assertEqual(shots['numeric']['asked'], 6)
        self.assertEqual(shots['blank']['asked'], 6)
        self.assertIn('Type a site first', shots['blank']['hint'])
        self.assertEqual(shots['removed']['rows'], ['docs.example.com'])
        self.assertEqual(shots['removed']['change'], {'sites': [DOCS]})
        self.assertEqual(shots['empty']['rows'], [])
        self.assertFalse(shots['empty']['emptyHidden'])
        self.assertEqual(shots['empty']['change'], {'sites': []})


if __name__ == '__main__':
    unittest.main()
