"""Research from your documents, your sites and/or the public web.

The form's choice, the run that pins it, the worker tools that keep to the sites, the
research jobs that name them and the research stop that says what was refused. Tests named
row_129 and row_130 cover those rows of the state-transition matrix in
docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md. Nothing touches the
network: pages come from a pretend web, and settings are a disposable studios config.
"""
import json
import unittest
import urllib.request
from dataclasses import replace
from unittest import mock

import helpers  # noqa: F401
from runner_support import FORM, PAGE, PUBLIC, URL, JobCase, StudioCase

import workspace
from runner import page, pipeline, settings, setup, studios_config, worker_tools
from studio_core import research_contract, research_sites
from workspace import WorkspaceError

TANZU = 'https://blogs.vmware.com/tanzu'
DOCS = 'https://docs.example.com'
OTHER = 'https://elsewhere.example.com/rolling-restarts'
WEB = {'documents': False, 'sites': [], 'web': True}
SITES = {'documents': False, 'sites': [TANZU], 'web': False}


class FormTests(unittest.TestCase):
    def test_row_129_the_form_says_where_research_may_look(self):
        form = pipeline.check_form({**FORM, 'research_from': {
            'documents': True, 'sites': ['blogs.vmware.com/tanzu/', DOCS], 'web': False}})
        self.assertEqual(form['research_from'],
                         {'documents': True, 'sites': [TANZU, DOCS], 'web': False})
        # Documents and pages: the training waits for the documents, then saves pages.
        self.assertEqual(form['source_scope'], 'both')
        self.assertIn('## Source scope\n\nYour documents and your sites\n'
                      'Sites: blogs.vmware.com/tanzu, docs.example.com\n',
                      pipeline.intake_text(form))
        for chosen, scope, words in (
                (SITES, 'public-web', 'Your sites\nSites: blogs.vmware.com/tanzu'),
                ({**SITES, 'web': True}, 'public-web',
                 'Your sites and the public web\nSites: blogs.vmware.com/tanzu'),
                ({'documents': True, 'sites': [TANZU], 'web': True}, 'both',
                 'Your documents, your sites and the public web\nSites: blogs.vmware.com/tanzu'),
                ({'documents': True}, 'supplied-only', 'Your documents only'),
                ({'documents': True, 'web': True}, 'both', 'The public web and your documents'),
                ({'web': True}, 'public-web', 'Public web')):
            with self.subTest(chosen):
                form = pipeline.check_form({**FORM, 'research_from': chosen})
                self.assertEqual(form['source_scope'], scope)
                self.assertEqual(pipeline.sources_words(form['research_from']), words)
                # A training brought in from a conversation reads it back from intake.md.
                self.assertEqual(pipeline.intake_research(words), form['research_from'])
        self.assertEqual(pipeline.intake_research('Something else'), WEB)
        self.assertEqual(pipeline.intake_research(''), WEB)   # no answer: as before

    def test_row_129_intake_is_read_without_regard_to_case_and_never_widens_to_the_web(self):
        documents = {'documents': True, 'sites': [], 'web': False}
        for said, chosen in (
                ('Your sites\nsites: blogs.vmware.com/tanzu', SITES),
                ('your documents and your sites\nSITES: blogs.vmware.com/tanzu',
                 {**SITES, 'documents': True}),
                ('YOUR SITES AND THE PUBLIC WEB\nSites: blogs.vmware.com/tanzu', {**SITES, 'web': True}),
                ('Supplied documents only', documents), ('your documents only', documents)):
            with self.subTest(said):
                self.assertEqual(pipeline.intake_research(said), chosen)
        # A site that cannot be used, or sites named with none listed, is refused: the
        # research is never widened to the public web for want of reading them.
        for said, named in (('Your sites\nSites: http://blogs.vmware.com/tanzu', 'https only'),
                            ('Your sites\nSites: blogs.vmware.com/../admin', '".." parts'),
                            ('Your documents and your sites\nSites: localhost/docs',
                             'not a public site'),
                            ('Your sites', 'names no site')):
            with self.subTest(said), self.assertRaises(WorkspaceError) as caught:
                pipeline.intake_research(said)
            self.assertIn(named, str(caught.exception))
            self.assertIn('Source scope', str(caught.exception))

    def test_documents_alone_with_none_added_say_there_is_no_research(self):
        none = {'documents': {'scope': 'supplied-only', 'done': '2026-10-23', 'count': 0},
                'research_from': {'documents': True, 'sites': [], 'web': False}}
        self.assertEqual(pipeline.research_words(none), 'No research: no documents were added.')
        both = {'documents': {'scope': 'both', 'done': '2026-10-23', 'count': 0},
                'research_from': {'documents': True, 'sites': [], 'web': True}}
        self.assertEqual(pipeline.research_words(both), 'Research from the public web.')
        waiting = {**both, 'documents': {'scope': 'both', 'done': None, 'count': 0}}
        self.assertEqual(pipeline.research_words(waiting),
                         'Research from your documents and the public web.')

    def test_row_129_nothing_that_applies_or_a_site_that_is_not_one_is_refused(self):
        for chosen, said in (
                ({}, research_sites.EMPTY),
                ({'documents': False, 'sites': [], 'web': False}, research_sites.EMPTY),
                ({'web': 'yes'}, research_sites.EMPTY), ('web', research_sites.EMPTY),
                ({'sites': ['http://blogs.vmware.com/tanzu']}, 'research sites use https only'),
                ({'sites': ['localhost/docs']}, 'is not a public site'),
                ({'sites': [TANZU + '?page=2']}, 'leave out the part after ?')):
            with self.subTest(chosen), self.assertRaises(WorkspaceError) as caught:
                pipeline.check_form({**FORM, 'research_from': chosen})
            self.assertIn(said, str(caught.exception))

    def test_row_129_older_words_are_read_in_the_new_shape(self):
        for scope, chosen in (('public-web', WEB),
                              ('supplied-only', {'documents': True, 'sites': [], 'web': False}),
                              ('both', {'documents': True, 'sites': [], 'web': True})):
            with self.subTest(scope):
                form = pipeline.check_form({**FORM, 'source_scope': scope})
                self.assertEqual((form['research_from'], form['source_scope']), (chosen, scope))
                # A run record saved before the choice was asked keeps only its scope.
                saved = {'documents': None if scope == 'public-web'
                         else {'scope': scope, 'done': None, 'count': 0}}
                self.assertEqual(pipeline.research_of(saved), chosen)
        self.assertEqual(pipeline.research_of({}), WEB)
        # The new words win over the older ones where a form sends both.
        self.assertEqual(pipeline.check_form({**FORM, 'source_scope': 'both',
                                              'research_from': SITES})['research_from'], SITES)


class CaptureTests(JobCase):
    """`save_source` asks every hop whether it is under the sites."""

    def research(self, chosen):
        return self.tools(finding='instance-min', fetch=True, ask=False, research=chosen)

    def test_a_job_keeps_its_choice_canonical_and_refuses_one_that_is_not(self):
        self.research({'sites': ['blogs.vmware.com/tanzu/'], 'web': False})
        self.assertEqual(json.loads((self.job / 'job.json').read_text())['research'], SITES)
        for number, wrong in enumerate(('web', {'web': 'yes'}, {'others': True},
                                        {'sites': ['http://blogs.vmware.com']})):
            with self.subTest(wrong), self.assertRaises(WorkspaceError):
                worker_tools.prepare(self.base / f'other-{number}', fetch=True, research=wrong)

    def test_a_job_prepared_without_a_choice_saves_any_public_page(self):
        url = self.web.page(OTHER, PAGE)
        tools = self.tools(finding='instance-min', fetch=True, ask=False)
        self.assertNotIn('research', tools.job)
        self.assertTrue(self.ok(tools.save_source(url)).startswith('Saved as s1'))

    def test_row_130_a_page_outside_the_sites_is_refused_naming_them(self):
        url = self.web.page(OTHER, PAGE)
        said = self.refused(self.research(SITES).save_source(url))
        self.assertEqual(said, 'That page is outside the sites this research may use, so it '
                               'was not saved. Save pages from under: blogs.vmware.com/tanzu.')
        self.assertEqual(self.web.asked, [])   # not even looked up
        handed = worker_tools.collect(self.job)
        self.assertEqual((handed['sources'], handed['outside']), ([], [url]))

    def test_row_130_a_redirect_off_the_sites_is_refused_naming_where_it_led(self):
        self.web.page(OTHER, PAGE)
        url = self.web.page(TANZU + '/old', '', status=302, headers={'location': OTHER})
        said = self.refused(self.research(SITES).save_source(url))
        self.assertEqual(said, 'That page redirected to elsewhere.example.com/rolling-restarts, '
                               'outside the sites this research may use, so it was not saved. '
                               'Save pages from under: blogs.vmware.com/tanzu.')
        self.assertEqual(self.web.asked, [(url, PUBLIC)])
        self.assertEqual(worker_tools.collect(self.job)['outside'], [OTHER])

    def test_row_130_a_lookalike_host_or_a_neighbouring_path_is_not_under_a_site(self):
        tools = self.research(SITES)
        for url in ('https://blogs.vmware.com.evil.example/tanzu/x',
                    'https://evil.blogs.vmware.com/tanzu/x',
                    'https://blogs.vmware.com/tanzu-other/x', 'https://blogs.vmware.com/',
                    'http://blogs.vmware.com/tanzu/x',
                    'https://blogs.vmware.com/tanzu/../other',
                    'https://blogs.vmware.com/tanzu%2f..%2fother'):
            with self.subTest(url):
                self.web.page(url, PAGE)
                self.assertIn('outside the sites this research may use',
                              self.refused(tools.save_source(url)))
        self.assertEqual(self.web.asked, [])

    def test_row_130_pages_under_a_site_are_saved_and_a_redirect_within_it_followed(self):
        self.web.page(TANZU + '/rolling-restarts', PAGE)
        url = self.web.page(TANZU + '/old', '', status=301, headers={'location': '/tanzu/rolling-restarts'})
        tools = self.research({**SITES, 'sites': [TANZU, DOCS]})
        self.assertTrue(self.ok(tools.save_source(url)).startswith('Saved as s1'))
        self.assertTrue(self.ok(tools.save_source(self.web.page(URL, PAGE))).startswith('Saved as s2'))
        self.assertEqual(worker_tools.collect(self.job)['outside'], [])

    def test_row_130_with_the_public_web_too_any_public_page_is_saved(self):
        url = self.web.page(OTHER, PAGE)
        self.assertTrue(self.ok(self.research({**SITES, 'web': True}).save_source(url))
                        .startswith('Saved as s1'))

    def recorded(self, chosen):
        """Tools whose opener records each request as urllib sends it: (host, selector)."""
        self.research(chosen)
        sent = []

        def opener(url, address, limit):
            request = urllib.request.Request(url)
            sent.append((request.host, request.selector))
            return self.web.opener(url, address, limit)

        return sent, worker_tools.WorkerTools(self.job, opener=opener, resolver=self.web.resolver)

    def test_row_130_a_fragment_never_hides_a_path_outside_the_sites(self):
        for url in (TANZU, TANZU + '/page', 'https://blogs.vmware.com/admin'):
            self.web.page(url, PAGE)
        sent, tools = self.recorded(SITES)
        for url in (TANZU + '#/x/../../admin#z', TANZU + '/x/..;/..;/admin',
                    'https://blogs.vmware.com/admin', TANZU + '#/../../admin'):
            with self.subTest(url):
                tools.save_source(url)
        self.assertTrue(self.ok(tools.save_source(TANZU + '/page#section')).startswith('Saved'))
        self.assertTrue(sent)
        for host, selector in sent:
            self.assertEqual(host, 'blogs.vmware.com')
            self.assertNotIn('#', selector)
            self.assertTrue(selector == '/tanzu' or selector.startswith('/tanzu/'), selector)
        self.assertIn(('blogs.vmware.com', '/tanzu/page'), sent)
        self.assertNotIn(TANZU + '/page#section',
                         [entry['url'] for entry in worker_tools.collect(self.job)['sources']])

    def test_row_130_a_redirect_with_a_fragment_is_checked_without_it(self):
        self.web.page(TANZU, PAGE)
        self.web.page('https://blogs.vmware.com/admin', 'secret')
        url = self.web.page(TANZU + '/old', '', status=302,
                            headers={'location': 'https://blogs.vmware.com/admin#/tanzu'})
        sent, tools = self.recorded(SITES)
        self.assertIn('redirected to blogs.vmware.com/admin', self.refused(tools.save_source(url)))
        self.assertEqual(sent, [('blogs.vmware.com', '/tanzu/old')])

    def test_a_fragment_is_never_sent_with_the_public_web_either(self):
        self.web.page(OTHER, PAGE)
        sent, tools = self.recorded(WEB)
        self.assertTrue(self.ok(tools.save_source(OTHER + '#part')).startswith('Saved'))
        self.assertEqual(sent, [('elsewhere.example.com', '/rolling-restarts')])

    def test_the_addresses_refused_outside_the_sites_are_capped(self):
        tools = self.research(SITES)
        with mock.patch.object(worker_tools, 'MAX_SOURCES', 3):
            for number in range(6):
                tools.save_source(f'https://elsewhere.example.com/{number}')
        self.assertEqual(worker_tools.collect(self.job)['outside'],
                         [f'https://elsewhere.example.com/{number}' for number in range(3)])

    def test_private_addresses_are_refused_on_the_sites_too(self):
        url = self.web.page(TANZU + '/admin', PAGE, addresses=['10.0.0.5'])
        self.assertIn('not on the public internet', self.refused(self.research(SITES).save_source(url)))
        self.assertEqual(self.web.asked, [])


class RunTests(StudioCase):
    def shared(self, *sites):
        studios_config.update({'research': {'sites': list(sites)}})

    def test_row_129_the_run_pins_the_sites_and_the_shared_list_is_only_read(self):
        self.shared(TANZU)
        self.assertEqual(setup.shared()[0]['research'], {'sites': [TANZU]})
        # A site added for this training does not change the shared list.
        root = self.saved_start(research_from={'documents': False, 'sites': [TANZU, DOCS + '/'],
                                         'web': False})
        self.assertEqual(studios_config.read()[0]['research'], {'sites': [TANZU]})
        pinned = {'documents': False, 'sites': [TANZU, DOCS], 'web': False}
        self.assertEqual(self.record(root)['research_from'], pinned)
        self.assertIsNone(self.record(root)['documents'])   # nothing to wait for
        # A later change to the shared list never changes a run that has started.
        self.shared('https://other.example.com')
        shown = self.view(root)['research_from']
        self.assertEqual({key: shown[key] for key in pinned}, pinned)
        self.assertEqual(shown['summary'], 'Research from 2 of your sites '
                                           '(blogs.vmware.com/tanzu, docs.example.com).')
        # Saving Training Studio's own settings keeps the shared list as it is.
        settings.save(replace(settings.load(), agent='codex'))
        self.assertEqual(studios_config.read()[0]['research'],
                         {'sites': ['https://other.example.com']})

    def test_row_130_research_keeps_to_the_sites_and_its_stop_says_what_was_refused(self):
        self.web.page(OTHER, PAGE)
        tried = []

        def wanders(tools, job):
            tried.append(tools.save_source(OTHER))
            return self.workers.question(tools, job)

        self.workers.then('question:availability', wanders)
        root = self.saved_start(research_from={'sites': [DOCS], 'web': False})
        self.to_gate(root, 'research')
        plan, = self.workers.jobs[:1]
        self.assertEqual(plan[2]['artifacts']['research-plan']['scope'], 'public-web')
        self.assertIn('Allowed sites: docs.example.com. Pages from anywhere else on the public '
                      'web are not allowed.', plan[1].task)
        for kind, job, spec in self.workers.jobs[1:]:
            with self.subTest(kind):
                self.assertEqual(spec['research'], {'documents': False, 'sites': [DOCS],
                                                    'web': False})
                self.assertIn('site:docs.example.com', job.guidance)
                self.assertIn('Allowed sites: docs.example.com.', job.task)
        self.assertEqual(tried, [(False, research_sites.refused(OTHER, {'sites': [DOCS]}))])
        self.assertNotIn(OTHER, [asked for asked, _ in self.web.asked])
        said = research_sites.outside(1, [DOCS])
        self.assertEqual(said, '1 page was outside your sites (docs.example.com) and was not saved.')
        self.assertEqual(self.view(root)['research_from']['outside'], said)
        self.assertEqual(page.RunnerPage(8765, self.engine).gate(str(root), 'research')['outside'],
                         said)

    def test_a_training_started_with_the_older_words_researches_as_before(self):
        root = self.saved_start(source_scope='public-web')
        self.to_gate(root, 'research')
        self.assertEqual(self.record(root)['research_from'], WEB)
        kind, job, spec = self.workers.jobs[1]
        self.assertEqual(spec['research'], WEB)
        self.assertNotIn('site:', job.guidance)
        self.assertIsNone(self.view(root)['research_from']['outside'])

    def test_row_129_the_research_task_names_the_sites_and_chooses_the_source_mode(self):
        seen = []

        def native(engine, root, run, task, offered, product):
            seen.append(task)
            raise WorkspaceError('Stopped here by the test.')

        contract = {'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}
        for number, (chosen, mode, documents) in enumerate((
                ({'sites': [TANZU, DOCS]}, 'public', False),
                ({'sites': [TANZU], 'web': True}, 'public', False),
                ({'documents': True, 'sites': [TANZU]}, 'mixed', True))):
            with self.subTest(chosen), \
                    mock.patch.object(research_contract, 'snapshot', return_value=contract), \
                    mock.patch.object(research_contract, 'native', native):
                root = self.saved_start(title=f'Restarts {number}', research_from=chosen, saved_contract=contract)
                if documents:
                    self.send(root, 'handbook.md')
                    self.engine.supply(root, 'done')
                self.to_gate(root, 'research-plan')
                planned = self.workers.of('research-plan')[-1]
                # A plan's search words hold no slash: the filter names the host.
                self.assertIn('such as site:blogs.vmware.com.', planned.task)
                self.assertIn('Allowed sites: blogs.vmware.com/tanzu', planned.task)
                self.decide(root, 'research-plan')
                task = seen[-1]
                looks = research_sites.effective(research_sites.choice(chosen))
                self.assertEqual(task['source_mode'], mode)
                self.assertIn(research_sites.scope_text(looks), task['scope'])
                self.assertIn('Selected materials:', task['scope'])
        self.assertIn('Allowed sites: blogs.vmware.com/tanzu, docs.example.com. Pages from '
                      'anywhere else on the public web are not allowed.', seen[0]['scope'])
        self.assertIn('The wider public web may fill gaps', seen[1]['scope'])
        self.assertIn('Use the supplied documents.', seen[2]['scope'])

    def test_a_run_saved_before_the_choice_keeps_its_research_task_scope(self):
        seen = []

        def native(engine, root, run, task, offered, product):
            seen.append(task)
            raise WorkspaceError('Stopped here by the test.')

        contract = {'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}
        with mock.patch.object(research_contract, 'snapshot', return_value=contract), \
                mock.patch.object(research_contract, 'native', native):
            root = self.saved_start(source_scope='public-web', saved_contract=contract)
            with self.engine.files:   # as a run record written before the choice was saved
                record = self.engine._load(root)
                record.pop('research_from')
                self.engine._store(root, record)
            self.to_gate(root, 'research-plan')
            self.decide(root, 'research-plan')
        task, = seen
        self.assertEqual(task['source_mode'], 'public')
        self.assertNotIn(research_sites.scope_text(WEB), task['scope'])
        self.assertTrue(task['scope'].startswith('Topic: '))
        # The scope it was always researched under: what the training is about, and no more.
        self.assertTrue(task['scope'].splitlines()[-1].startswith('Selected materials:'))


if __name__ == '__main__':
    unittest.main()
