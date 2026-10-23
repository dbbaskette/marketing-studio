"""Research from your documents, your sites and/or the public web, in Blog Studio.

Every test uses a disposable workspace and studios config. Captures go through stub
resolvers and connections, never the network, and no provider job starts.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch

from test_blog_runner import RunnerCase
import blog_library
import blog_runner as runner
import management
import studio
import synthesis_research
from studio_core import research_contract, research_sites

SITES = ['https://blogs.vmware.com/tanzu', 'https://docs.example.com']
# A synthetic Harness Research version, so a run may research from your sites.
CONTRACT = {'schema': 2, 'version': '1.0.0', 'digest': 'a' * 64}
PUBLIC = [(2, 1, 6, '', ('8.8.8.8', 443))]


def page(status=200, body=b'<p>A synthetic page.</p>', location=None):
    """A stub connection answering one request."""
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = status
    headers = {'Content-Type': 'text/html'}
    if location:
        headers['Location'] = location
    response.getheader.side_effect = lambda name, default=None: headers.get(name, default)
    response.read1.side_effect = [body, b'']
    return connection


class SharedSitesCase(RunnerCase):
    """A run case whose shared settings hold a research sites list."""

    def setUp(self):
        super().setUp()
        self.config = Path(os.environ['STUDIOS_CONFIG'])
        held = json.loads(self.config.read_text())
        held['research'] = {'sites': list(SITES)}
        held['person'] = {'name': 'Synthetic Author'}
        self.config.write_text(json.dumps(held, indent=2) + '\n')
        # Research from your sites needs Harness Research; this computer has a synthetic one.
        helper = patch.object(runner.research_contract, 'snapshot', return_value=dict(CONTRACT))
        self.helper = helper.start()
        self.addCleanup(helper.stop)

    def shared(self):
        return self.config.read_bytes()

    def start(self, page=True, **extra):
        return runner.create(
            self.root,
            {
                'title': 'Synthetic gateway guide',
                'audience': 'New authors',
                'goal': 'Explain a fictional gateway',
                **extra,
            },
            'page' if page else 'conversation',
        )


class StartFormTests(SharedSitesCase):
    def test_settings_send_the_shared_sites_and_the_sentences_the_form_uses(self):
        shown = runner.settings(self.root)
        self.assertEqual(shown['research_sites'], SITES)
        self.assertEqual(
            shown['defaults']['research'], {'documents': True, 'sites': False, 'web': False}
        )
        self.assertEqual(
            shown['research_words'],
            {
                'empty': research_sites.EMPTY,
                'no_documents': research_sites.NO_DOCUMENTS,
                'no_sites': research_sites.NO_SITES,
            },
        )
        self.assertEqual(runner.options(self.root)['settings']['research_sites'], SITES)

    def test_the_three_choices_and_the_pinned_site_list_round_trip(self):
        source = self.source('The gateway retries a failed call once.')
        before = self.shared()
        found = self.start(
            sources=[source['id']],
            research_from={
                'documents': True,
                # One shared site, and one added for this blog only, as the form sends them.
                'sites': ['https://blogs.vmware.com/tanzu', 'extra.example.org/guide/'],
                'web': False,
            },
        )
        _, record, run = runner.load(self.root, found['id'])
        pinned = ['https://blogs.vmware.com/tanzu', 'https://extra.example.org/guide']
        self.assertEqual(
            record['research_from'], {'documents': True, 'sites': pinned, 'web': False}
        )
        self.assertEqual(record['research_policy'], 'web-allowed')
        self.assertEqual(run['pipeline'][:2], ['research-plan', 'research'])
        self.assertEqual(self.shared(), before, 'a site added for one blog stays off the list')
        self.assertEqual(runner.settings(self.root)['research_sites'], SITES)
        # The run pins the list it used: a later change to the shared list changes nothing.
        held = json.loads(self.config.read_text())
        held['research'] = {'sites': ['https://other.example.net']}
        self.config.write_text(json.dumps(held))
        _, record, _ = runner.load(self.root, found['id'])
        self.assertEqual(record['research_from']['sites'], pinned)
        shown = runner.survey(self.root, found['id'])
        self.assertEqual(shown['research_from'], record['research_from'])
        self.assertEqual(
            shown['research_says'],
            'Research from your documents and 2 of your sites '
            '(blogs.vmware.com/tanzu, extra.example.org/guide).',
        )
        _, payload, _ = runner.job(self.root, found['id'])
        self.assertEqual(payload['research_from'], record['research_from'])

    def test_each_choice_maps_to_its_research_stages(self):
        source = self.source('The gateway retries a failed call once.')
        cases = [
            ({'documents': True, 'sites': [], 'web': False}, ['claims-map'], 'supplied-only'),
            ({'documents': True, 'sites': [], 'web': True}, ['research-plan'], 'web-allowed'),
            (
                {'documents': False, 'sites': SITES[:1], 'web': False},
                ['research-plan'],
                'web-allowed',
            ),
            ({'documents': False, 'sites': [], 'web': True}, ['research-plan'], 'web-allowed'),
        ]
        for chosen, first, policy in cases:
            with self.subTest(chosen=chosen):
                found = self.start(sources=[source['id']], research_from=chosen)
                _, record, run = runner.load(self.root, found['id'])
                self.assertEqual(run['pipeline'][: len(first)], first)
                self.assertEqual(record['research_policy'], policy)
                self.assertEqual(record['research_from'], chosen)

    def test_documents_count_only_when_documents_were_given(self):
        found = self.start(research_from={'documents': True, 'sites': SITES, 'web': False})
        _, record, _ = runner.load(self.root, found['id'])
        self.assertEqual(
            record['research_from'], {'documents': False, 'sites': SITES, 'web': False}
        )
        # Only your documents, and none given: no research, as Blog Studio has always done.
        found = self.start(research_from={'documents': True, 'sites': [], 'web': False})
        _, record, run = runner.load(self.root, found['id'])
        self.assertIsNone(record['research_from'])
        self.assertEqual(run['pipeline'][0], 'outline')
        self.assertEqual(runner.survey(self.root, found['id'])['research_says'], 'No research.')

    def test_a_choice_with_nothing_or_a_bad_site_is_refused_with_its_sentence(self):
        cases = [
            ({'documents': False, 'sites': [], 'web': False}, research_sites.EMPTY),
            ({'sites': ['http://blogs.vmware.com/tanzu']}, 'https only'),
            ({'sites': ['https://localhost/docs']}, 'not a public site'),
            ({'sites': ['https://blogs.vmware.com/tanzu?page=2']}, 'leave out the part after'),
            ({'web': 'yes'}, research_sites.EMPTY),
            ({'somewhere': True}, research_sites.EMPTY),
            ('web-allowed', research_sites.EMPTY),
        ]
        for chosen, said in cases:
            with self.subTest(chosen=chosen):
                with self.assertRaises(ValueError) as caught:
                    self.start(research_from=chosen)
                self.assertIn(said, str(caught.exception))
        with self.assertRaisesRegex(ValueError, 'not both'):
            self.start(research='none', research_from={'web': True})
        self.assertEqual(list((self.root / 'articles').iterdir()), [], 'nothing was started')

    def test_from_files_research_reads_the_files_and_your_sites(self):
        files = self.material(('notes.md', 'Retries cost money. ' * 40))
        found = self.start(
            mode='from-files',
            sources=files,
            goal='A post',
            point=True,
            research_from={'documents': True, 'sites': SITES[:1], 'web': False},
        )
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(run['pipeline'][:3], ['research-plan', 'research', 'outline'])
        self.assertEqual(record['research_from']['sites'], SITES[:1])
        # Your documents only: the files are read at every step, and no research stage is added.
        found = self.start(
            mode='from-files',
            sources=self.material(('plain.txt', 'Hops add latency. ' * 40)),
            goal='A post',
            research_from={'documents': True, 'sites': [], 'web': False},
        )
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(run['after_angles'], {'research': 'none', 'stop': 'package'})
        self.assertEqual(record['research_from'], {'documents': True, 'sites': [], 'web': False})

    def material(self, *files):
        import base64

        with patch.object(blog_library.shutil, 'which', return_value=None):
            result = management.dispatch(
                self.root,
                'upload',
                {
                    'operation': studio.digest(repr(files).encode())[:32],
                    'purpose': 'material',
                    'keep': False,
                    'analyze': False,
                    'files': [
                        {'filename': name, 'content': base64.b64encode(body.encode()).decode()}
                        for name, body in files
                    ],
                },
            )
        return [row['source']['id'] for row in result['files']]

    def test_from_files_angles_keep_your_sites_for_after_the_pick(self):
        files = self.material(('notes.md', 'Retries cost money. ' * 40))
        found = self.start(
            mode='from-files',
            sources=files,
            goal='A post',
            research_from={'documents': True, 'sites': SITES[:1], 'web': False},
        )
        _, record, run = runner.load(self.root, found['id'])
        self.assertEqual(run['after_angles'], {'research': 'web-allowed', 'stop': 'package'})
        self.assertEqual(record['research_policy'], 'web-allowed')

    def test_a_site_added_for_this_blog_is_checked_by_the_server_and_not_saved(self):
        before = self.shared()
        added = management.dispatch(self.root, 'research-site', {'site': 'Example.ORG/Guide/'})
        self.assertEqual(added, {'site': 'https://example.org/Guide', 'shown': 'example.org/Guide'})
        for wrong, said in (
            ('http://example.org', 'https only'),
            ('https://192.168.1.4/docs', 'not a public site'),
            ('https://user:secret@example.org', 'name or password'),
        ):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, said):
                management.dispatch(self.root, 'research-site', {'site': wrong})
        with self.assertRaises(ValueError):
            management.dispatch(self.root, 'research-site', {'site': 'example.org', 'more': 1})
        self.assertEqual(self.shared(), before)

    def test_the_command_line_speaks_the_new_shape_and_keeps_the_old_words(self):
        source = self.source('The gateway retries a failed call once.')

        def create(*words):
            args = studio.parser().parse_args(
                [
                    '--root',
                    str(self.root),
                    'run',
                    'create',
                    '--audience',
                    'Authors',
                    '--goal',
                    'Explain',
                    '--title',
                    'Synthetic',
                    '--source',
                    source['id'],
                    *words,
                ]
            )
            found = runner.command(self.root, args)
            return runner.load(self.root, found['id'])[1]

        record = create('--research-from', 'documents,sites')
        self.assertEqual(record['research_from'], {'documents': True, 'sites': SITES, 'web': False})
        record = create('--research-from', 'sites,web', '--site', 'docs.example.com/guide')
        self.assertEqual(
            record['research_from'],
            {'documents': False, 'sites': ['https://docs.example.com/guide'], 'web': True},
        )
        record = create('--research', 'web-allowed')
        self.assertEqual(record['research_from'], {'documents': True, 'sites': [], 'web': True})
        record = create('--research', 'supplied-only')
        self.assertEqual(record['research_from'], {'documents': True, 'sites': [], 'web': False})
        record = create('--research', 'none')
        self.assertIsNone(record['research_from'])
        with self.assertRaisesRegex(ValueError, 'documents, sites or web'):
            create('--research-from', 'documents,intranet')
        with self.assertRaisesRegex(ValueError, 'not both'):
            create('--research-from', 'web', '--research', 'none')
        held = json.loads(self.config.read_text())
        held['research'] = {'sites': []}
        self.config.write_text(json.dumps(held))
        with self.assertRaisesRegex(ValueError, research_sites.NO_SITES):
            create('--research-from', 'sites')


class OldRunTests(SharedSitesCase):
    """Runs saved before the choice had three parts read their research policy."""

    def forget(self, found):
        directory, record, _ = runner.load(self.root, found['id'])
        record.pop('research_from')
        studio.persist(directory, 'articles', record)
        return runner.survey(self.root, found['id'])

    def test_old_saved_values_are_mapped(self):
        source = self.source('The gateway retries a failed call once.')
        shown = self.forget(self.start(sources=[source['id']], research='supplied-only'))
        self.assertEqual(shown['research_from'], {'documents': True, 'sites': [], 'web': False})
        self.assertEqual(shown['research_says'], 'Research from your documents.')
        shown = self.forget(self.start(sources=[source['id']], research='web-allowed'))
        self.assertEqual(shown['research_from'], {'documents': True, 'sites': [], 'web': True})
        self.assertEqual(shown['research_says'], 'Research from your documents and the public web.')
        shown = self.forget(self.start(sources=[source['id']], research='none'))
        self.assertIsNone(shown['research_from'])
        self.assertEqual(shown['research_says'], 'No research.')
        # An old run's payload, and so its stage pins, carry no research_from.
        _, record, run = runner.load(self.root, shown['id'])
        self.assertNotIn('research_from', runner.inputs(self.root, record, run))

    def test_old_writing_default_values_are_mapped(self):
        path = self.root / '.blog-run-settings.json'
        for old, new in (
            ('none', {'documents': False, 'sites': False, 'web': False}),
            ('supplied-only', {'documents': True, 'sites': False, 'web': False}),
            ('web-allowed', {'documents': True, 'sites': False, 'web': True}),
        ):
            with self.subTest(old=old):
                studio.write_json(path, {'schema': 1, 'defaults': {'research': old}})
                self.assertEqual(runner.settings(self.root)['defaults']['research'], new)

    def test_the_writing_default_saves_the_new_shape(self):
        shown = runner.settings(self.root)
        values = {
            **shown['defaults'],
            'research': {'documents': True, 'sites': True, 'web': False},
            'shared_before': shown['shared_before'],
        }
        saved = runner.settings(self.root, values)
        self.assertEqual(
            saved['defaults']['research'], {'documents': True, 'sites': True, 'web': False}
        )
        self.assertEqual(
            studio.read_json(self.root / '.blog-run-settings.json')['defaults']['research'],
            {'documents': True, 'sites': True, 'web': False},
        )
        self.assertIn(b'"research"', self.shared(), 'the shared list is kept')
        self.assertEqual(runner.settings(self.root)['research_sites'], SITES)
        for wrong in (
            {'documents': True},
            {'documents': 'yes', 'sites': False, 'web': False},
            'all',
        ):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, 'research'):
                runner.settings(
                    self.root,
                    {**values, 'research': wrong, 'shared_before': shown['shared_before']},
                )
        # The old words are still read from an older page.
        saved = runner.settings(
            self.root,
            {**values, 'research': 'web-allowed', 'shared_before': shown['shared_before']},
        )
        self.assertEqual(
            saved['defaults']['research'], {'documents': True, 'sites': False, 'web': True}
        )


class CaptureTests(unittest.TestCase):
    """blog_library.fetch keeps a research capture to the run's sites, on every hop."""

    SITES_ONLY = research_sites.Scope({'documents': False, 'sites': SITES[:1], 'web': False})
    SITES_AND_WEB = research_sites.Scope({'documents': False, 'sites': SITES[:1], 'web': True})

    def fetch(self, url, scope, *pages, address=PUBLIC):
        with (
            patch.object(blog_library.socket, 'getaddrinfo', return_value=address) as resolve,
            patch.object(blog_library, 'PinnedHTTPS', side_effect=list(pages)) as connect,
        ):
            try:
                return blog_library.fetch(url, scope), resolve, connect
            except ValueError as error:
                error.resolve, error.connect = resolve, connect
                raise

    def test_a_page_under_a_listed_site_is_saved(self):
        found, _, connect = self.fetch(
            'https://blogs.vmware.com/tanzu/post', self.SITES_ONLY, page()
        )
        self.assertEqual(found[1], 'https://blogs.vmware.com/tanzu/post')
        connect.assert_called_once_with('blogs.vmware.com', '8.8.8.8')
        found, _, _ = self.fetch('https://BLOGS.vmware.com/tanzu', self.SITES_ONLY, page())
        self.assertEqual(found[1], 'https://blogs.vmware.com/tanzu')

    def test_pages_outside_the_sites_are_refused_before_any_lookup(self):
        for url in (
            'https://blogs.vmware.com.evil.example/tanzu/post',
            'https://blogs.vmware.com/tanzu-other/post',
            'https://www.blogs.vmware.com/tanzu/post',
            'https://blogs.vmware.com/',
            'https://blogs.vmware.com/tanzu/../admin',
            'https://blogs.vmware.com/tanzu%2F..%2Fadmin',
            'http://blogs.vmware.com/tanzu/post',
        ):
            with self.subTest(url=url):
                with self.assertRaises(blog_library.Outside) as caught:
                    self.fetch(url, self.SITES_ONLY, page())
                self.assertIn(
                    'Save pages from under: blogs.vmware.com/tanzu.', str(caught.exception)
                )
                caught.exception.resolve.assert_not_called()
                caught.exception.connect.assert_not_called()

    def test_a_redirect_off_the_sites_is_refused_and_names_where_it_led(self):
        with self.assertRaises(blog_library.Outside) as caught:
            self.fetch(
                'https://blogs.vmware.com/tanzu/post',
                self.SITES_ONLY,
                page(302, location='https://elsewhere.example/landing'),
                page(),
            )
        said = str(caught.exception)
        self.assertIn('redirected to elsewhere.example/landing', said)
        self.assertIn('blogs.vmware.com/tanzu', said)
        caught.exception.connect.assert_called_once_with('blogs.vmware.com', '8.8.8.8')
        # A redirect that stays under the site is followed.
        found, _, connect = self.fetch(
            'https://blogs.vmware.com/tanzu/old',
            self.SITES_ONLY,
            page(301, location='/tanzu/new'),
            page(),
        )
        self.assertEqual(found[1], 'https://blogs.vmware.com/tanzu/new')
        self.assertEqual(connect.call_count, 2)
        with self.assertRaises(blog_library.Outside):
            self.fetch(
                'https://blogs.vmware.com/tanzu/old',
                self.SITES_ONLY,
                page(301, location='/tanzu-other/new'),
                page(),
            )

    def test_with_the_public_web_any_public_page_and_redirect_is_allowed(self):
        found, _, _ = self.fetch(
            'https://blogs.vmware.com.evil.example/tanzu/post', self.SITES_AND_WEB, page()
        )
        self.assertEqual(found[1], 'https://blogs.vmware.com.evil.example/tanzu/post')
        found, _, connect = self.fetch(
            'https://blogs.vmware.com/tanzu/post',
            self.SITES_AND_WEB,
            page(302, location='https://elsewhere.example/landing'),
            page(),
        )
        self.assertEqual(found[1], 'https://elsewhere.example/landing')
        self.assertEqual(connect.call_count, 2)
        # The private-address refusals stay, whatever the choice.
        with self.assertRaisesRegex(ValueError, 'public addresses'):
            self.fetch(
                'https://blogs.vmware.com/tanzu/post',
                self.SITES_AND_WEB,
                page(),
                address=[(2, 1, 6, '', ('127.0.0.1', 443))],
            )
        with self.assertRaisesRegex(ValueError, 'public addresses'):
            self.fetch(
                'https://blogs.vmware.com/tanzu/post',
                self.SITES_ONLY,
                page(),
                address=[(2, 1, 6, '', ('10.0.0.8', 443))],
            )

    def test_a_fragment_or_a_parameter_dot_segment_never_escapes_the_site(self):
        # The reviewer's addresses: a '#' that hides '..' from one parser, and '..;' segments
        # that servers dropping ;-parameters read as '..'.
        for url in (
            'https://blogs.vmware.com/tanzu#/x/../../admin#z',
            'https://blogs.vmware.com/tanzu/x/..;/..;/admin',
            'https://blogs.vmware.com/tanzu/x/..;jsessionid=1/admin',
        ):
            with self.subTest(url=url):
                with self.assertRaises(blog_library.Outside) as caught:
                    self.fetch(url, self.SITES_ONLY, page())
                caught.exception.resolve.assert_not_called()
                caught.exception.connect.assert_not_called()

    def test_the_request_target_never_carries_a_fragment_or_leaves_the_site(self):
        sent = []  # (host, request target) of every request a stubbed connection received

        def fetch(url, *, location=None):
            sent.clear()
            pages = iter([page(302, location=location)] if location else [])

            def make(host, address):
                made = next(pages, None) or page()
                made.request.side_effect = lambda method, target, **_: sent.append((host, target))
                return made

            with (
                patch.object(blog_library.socket, 'getaddrinfo', return_value=PUBLIC),
                patch.object(blog_library, 'PinnedHTTPS', side_effect=make),
            ):
                return blog_library.fetch(url, self.SITES_ONLY)

        found = fetch('https://blogs.vmware.com/tanzu/post#section-2')
        self.assertEqual(sent, [('blogs.vmware.com', '/tanzu/post')])
        self.assertEqual(found[1], 'https://blogs.vmware.com/tanzu/post')
        # A redirect's own fragment is dropped before it is checked and requested.
        fetch('https://blogs.vmware.com/tanzu/old', location='/tanzu/new#/../../admin')
        self.assertEqual(
            sent, [('blogs.vmware.com', '/tanzu/old'), ('blogs.vmware.com', '/tanzu/new')]
        )
        for location in ('/tanzu/x/..;/..;/admin', '/tanzu#/../admin#z', '/admin#/tanzu'):
            with self.subTest(location=location), self.assertRaises(blog_library.Outside):
                fetch('https://blogs.vmware.com/tanzu/old', location=location)
            self.assertTrue(
                all(
                    host == 'blogs.vmware.com' and target.startswith('/tanzu/')
                    for host, target in sent
                ),
                sent,
            )

    def test_a_collection_scope_keeps_its_behaviour(self):
        with self.assertRaisesRegex(ValueError, 'outside the approved collection scope'):
            self.fetch('https://team.example/other', 'https://team.example/blog', page())
        with self.assertRaises(ValueError) as caught:
            self.fetch(
                'https://team.example/blog/a',
                'https://team.example/blog',
                page(302, location='https://elsewhere.example/a'),
            )
        self.assertNotIsInstance(caught.exception, blog_library.Outside)


class DiscoveryTests(unittest.TestCase):
    """synthesis_research discovery: what it is told, what it captures and what it refuses."""

    def setUp(self):
        import tempfile

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        from synthesis_fixture import research_stop

        research_stop(self.directory / 'research')

    def research(self, research_from, urls, sources=(), pages=None):
        seen = {'tasks': [], 'jobs': [], 'events': [], 'connected': []}
        pages = pages or {}

        def worker(engine, data, guidance, **options):
            seen['jobs'].append({'data': data, 'guidance': guidance, 'options': options})
            if 'task' in data and 'worker' not in data:
                return {'content': json.dumps({'urls': urls}), 'notes': ''}
            return {'content': '{}', 'notes': ''}

        def run(workflow, folder, task, invoke, captured):
            seen['tasks'].append(task)
            invoke('review', 'Synthetic review.', {'worker': 'checker'}, captured, None)

        def connect(host, address):
            seen['connected'].append(host)
            return pages.get(host) or page()

        payload = {
            'title': 'Synthetic',
            'sources': list(sources),
            'documents': {},
            'research_policy': 'web-allowed',
        }
        if research_from is not None:
            payload['research_from'] = research_from
        with (
            patch.object(research_contract, 'runtime_for', return_value=self.directory),
            patch.object(research_contract.Workflow, 'run', run),
            patch.object(research_contract, 'publish'),
            patch.object(blog_library.socket, 'getaddrinfo', return_value=PUBLIC),
            patch.object(blog_library, 'PinnedHTTPS', side_effect=connect),
            patch('studio_core.model_profiles.route', return_value=None),
        ):
            synthesis_research.generate(
                self.directory,
                {'brief': {'goal': 'Explain retries'}, 'research_contract': {}, 'engine': 'codex'},
                payload,
                worker,
                seconds=60,
                stop=threading.Event(),
                progress=seen['events'].append,
            )
        seen['task'] = seen['tasks'][0]
        seen['review'] = seen['jobs'][-1]['data']
        seen['discovery'] = seen['jobs'][0]
        return seen

    URLS = [
        'https://blogs.vmware.com/tanzu/retries',
        'https://blogs.vmware.com.evil.example/tanzu/retries',
        'https://blogs.vmware.com/tanzu-other/retries',
    ]
    SOURCE = {
        'id': 'source-a',
        'name': 'Specification',
        'origin': 'upload:specification.md',
        'purposes': ['reference'],
        'status': 'ready',
        'text': 'The gateway retries once.',
    }

    def test_with_your_sites_only_pages_under_them_are_saved_and_the_rest_are_limits(self):
        seen = self.research({'documents': False, 'sites': SITES[:1], 'web': False}, self.URLS)
        captured = [source['origin'] for source in seen['review']['sources']]
        self.assertEqual(captured, ['https://blogs.vmware.com/tanzu/retries'])
        self.assertEqual(seen['connected'], ['blogs.vmware.com'])
        limits = seen['review']['source_limits']
        self.assertEqual([limit['url'] for limit in limits], self.URLS[1:])
        for limit in limits:
            self.assertIn('Save pages from under: blogs.vmware.com/tanzu.', limit['reason'])
        self.assertIn({'outside': {'count': 2, 'sites': SITES[:1]}}, seen['events'], seen['events'])
        task = seen['task']
        self.assertIn('Allowed sites: blogs.vmware.com/tanzu.', task['scope'])
        self.assertIn('Pages from anywhere else on the public web are not allowed.', task['scope'])
        self.assertEqual(task['source_mode'], 'public')
        guidance = seen['discovery']['guidance']
        self.assertIn('site:blogs.vmware.com/tanzu', guidance)
        self.assertIn(research_sites.guidance({'sites': SITES[:1], 'web': False}), guidance)
        self.assertTrue(seen['discovery']['options']['web'])

    def test_your_documents_and_sites_are_mixed_and_the_documents_are_read(self):
        seen = self.research(
            {'documents': True, 'sites': SITES[:1], 'web': False}, self.URLS[:1], [self.SOURCE]
        )
        self.assertEqual(seen['task']['source_mode'], 'mixed')
        self.assertIn('Use the supplied documents.', seen['task']['scope'])
        permissions = sorted(source['permission'] for source in seen['review']['sources'])
        self.assertEqual(permissions, ['public', 'selected'])

    def test_documents_left_out_are_not_read_by_the_research(self):
        seen = self.research(
            {'documents': False, 'sites': [], 'web': True}, self.URLS[:1], [self.SOURCE]
        )
        self.assertEqual(seen['task']['source_mode'], 'public')
        self.assertEqual([source['permission'] for source in seen['review']['sources']], ['public'])
        self.assertIn('Any public page may be used.', seen['task']['scope'])

    def test_with_the_public_web_too_any_public_page_is_saved(self):
        seen = self.research({'documents': False, 'sites': SITES[:1], 'web': True}, self.URLS)
        self.assertEqual(len(seen['review']['sources']), 3)
        self.assertEqual(seen['review']['source_limits'], [])
        self.assertIn('The wider public web may fill gaps', seen['task']['scope'])
        self.assertIn('only for gaps the listed sites leave', seen['discovery']['guidance'])

    def test_an_old_web_allowed_run_researches_as_before(self):
        seen = self.research(None, self.URLS[:2], [self.SOURCE])
        self.assertEqual(seen['task']['source_mode'], 'mixed')
        # A run saved before research_from keeps its exact scope text.
        self.assertEqual(
            seen['task']['scope'],
            'Evidence, objections and qualifications for the blog goal: Explain retries',
        )
        self.assertEqual(len(seen['review']['sources']), 3)
        self.assertNotIn('site:', seen['discovery']['guidance'])
        self.assertFalse(any('outside' in event for event in seen['events']))


class GateTests(SharedSitesCase):
    def test_the_research_gate_names_the_sites_that_refused_pages(self):
        found = self.start(research_from={'documents': False, 'sites': SITES[:1], 'web': False})
        engine = runner.Engine(self.root, lambda *a, **k: self.fail('No provider job'))
        self.addCleanup(engine.close)
        engine.note_research(found['id'], {'outside': {'count': 2, 'sites': SITES[:1]}})
        shown = engine.describe(found['id'])
        self.assertEqual(
            shown['research']['outside'],
            '2 pages were outside your sites (blogs.vmware.com/tanzu) and were not saved.',
        )
        engine.note_research(found['id'], {'outside': {'count': 1, 'sites': SITES}})
        self.assertEqual(
            engine.describe(found['id'])['research']['outside'],
            '1 page was outside your sites (blogs.vmware.com/tanzu, docs.example.com) and was '
            'not saved.',
        )
        engine.note_research(found['id'], {'outside': {'count': 0, 'sites': SITES}})
        self.assertIsNone(engine.describe(found['id'])['research']['outside'])


class WithoutHarnessResearchTests(SharedSitesCase):
    """Your sites never become the open web: without Harness Research, research from your
    sites alone is refused, and no worker is given web search for it."""

    def setUp(self):
        super().setUp()
        self.helper.return_value = None

    def test_your_sites_alone_need_harness_research(self):
        for chosen in (
            {'documents': False, 'sites': SITES[:1], 'web': False},
            {'documents': True, 'sites': SITES, 'web': False},
        ):
            with self.subTest(chosen=chosen), self.assertRaises(ValueError) as caught:
                self.start(sources=[self.source()['id']], research_from=chosen)
            self.assertEqual(str(caught.exception), runner.NEEDS_HARNESS_RESEARCH)
            self.assertIn('Open Status', str(caught.exception))
        self.assertEqual(list((self.root / 'articles').iterdir()), [], 'nothing was started')
        # With the public web ticked too, the run starts on the older research path.
        found = self.start(research_from={'documents': False, 'sites': SITES[:1], 'web': True})
        _, record, run = runner.load(self.root, found['id'])
        self.assertNotIn('research_contract', run)
        self.assertEqual(run['pipeline'][:2], ['research-plan', 'research'])
        self.assertEqual(record['research_from']['web'], True)

    def test_status_says_whether_harness_research_is_here(self):
        import computer

        found = next(
            row for row in computer.report(sign_in=False)['checks'] if row['key'] == 'research'
        )
        self.assertEqual(found['status'], 'optional')
        self.assertTrue(found['optional'])
        self.assertIn('Research from your sites needs it', found['detail'])
        with patch.object(computer, 'harness_research', return_value=True):
            found = next(
                row for row in computer.report(sign_in=False)['checks'] if row['key'] == 'research'
            )
        self.assertEqual(found['status'], 'ready')

    def research_job(self, change=None):
        """The web search option the worker is given for a run's research stage."""
        found = self.start(research_from={'documents': False, 'sites': SITES[:1], 'web': True})
        if change is not None:
            # A run saved this way, however it came to be: the worker must follow its choice.
            directory, record, _ = runner.load(self.root, found['id'])
            change(record)
            studio.persist(directory, 'articles', record)
            found = runner.survey(self.root, found['id'])
        found = self.approve(self.submit(found, page=True), page=True)
        self.assertEqual(found['next'], 'research')
        seen = []

        def worker(engine, payload, guidance, **options):
            seen.append(options['web'])
            return {'content': '# Research\nSynthetic findings.', 'notes': 'Synthetic.'}

        engine = runner.Engine(self.root, worker)
        self.addCleanup(engine.close)
        engine.control(found['id'], 'resume')
        engine._once(found['id'])
        self.assertEqual(engine.describe(found['id'])['error'], '')
        return seen

    def test_no_worker_searches_the_web_for_your_sites_alone(self):
        self.assertEqual(self.research_job(), [True], 'sites and the public web may search')

        def sites_only(record):
            record['research_from']['web'] = False

        self.assertEqual(self.research_job(sites_only), [False])

        def old(record):
            record.pop('research_from')  # Saved before the choice: its policy says web-allowed.

        self.assertEqual(self.research_job(old), [True])


if __name__ == '__main__':
    unittest.main()
