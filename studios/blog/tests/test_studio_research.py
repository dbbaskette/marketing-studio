"""The shared research component's contract tests. They run unchanged in every studio."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from hub_fixtures import SCRIPTS  # noqa: F401  (puts the scripts on the path, and the stand-in)
from studio_research import project, runtime, steps, tools

PAGE = (
    b'<html><head><title>Release notes</title><script>x()</script></head><body>'
    b'<p>ExampleDB 2.0 adds predicate pruning to every column scan.</p></body></html>'
)


def documents():
    return [
        {
            'title': 'Product notes',
            'origin': 'supplied notes.md',
            'text': 'ExampleDB 2.0 supports predicate pruning on column scans.\n',
            'status': 'ready',
        }
    ]


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve() / 'item'
        self.folder.mkdir()
        (self.folder / 'BRIEF.md').write_text('# Brief\nWhat it covers.\n')
        self.staging = Path(self.tmp.name).resolve() / 'jobs'

    def save(self, allow_web=False, query=None):
        sources = project.snapshot(self.folder, documents())
        plan = project.build_plan(
            'ExampleDB pruning',
            'planning',
            'public-web' if allow_web else 'supplied-only',
            [{'id': 'pruning', 'question': 'Does ExampleDB 2.0 prune?', 'public_query': query}],
            sources,
            ['BRIEF.md'],
        )
        return project.save_plan(self.folder, plan, allow_web=allow_web)


class ProjectTests(Folder):
    def test_layout_and_status_before_and_after_a_plan(self):
        self.assertEqual(project.status(self.folder)['status'], 'not-started')
        answered = self.save()
        self.assertTrue((self.folder / 'research' / 'plan.json').is_file())
        self.assertIn('pruning', (self.folder / 'research' / 'plan.md').read_text())
        found = project.status(self.folder)
        self.assertEqual(found['run'], answered['run'])
        self.assertEqual(found['pending'], ['pruning'])
        self.assertEqual(
            set(found),
            {
                'run',
                'status',
                'pending',
                'unresolved',
                'stale_items',
                'carried',
                'source_gaps',
                'completed',
                'total',
                'report',
                'file',
            },
        )
        key = project.key('supplied notes.md', documents()[0]['text'])
        self.assertEqual(project.planned(self.folder), {key})

    def test_busy_saves_are_offered_again(self):
        calls = []

        class Busy:
            def record(self, folder, run, item, finding):
                calls.append(item)
                if len(calls) < 3:
                    raise runtime.Refused(runtime.BUSY + '; retry after the current save.')
                return {'status': 'complete'}

        project.BUSY_WAIT, saved = 0, project.BUSY_WAIT
        self.addCleanup(setattr, project, 'BUSY_WAIT', saved)
        self.assertEqual(project.record(self.folder, 'r', 'q', {}, Busy())['status'], 'complete')
        self.assertEqual(len(calls), 3)

    def test_report_is_copied_for_the_gate(self):
        self.save()
        project.status(self.folder)
        copy = project.publish_report(self.folder)
        self.assertEqual(copy.read_bytes(), (self.folder / project.HARNESS_REPORT).read_bytes())


class ToolTests(Folder):
    def job(self, fetch=True, opener=None, resolver=None):
        self.jobs = getattr(self, 'jobs', 0) + 1  # each job in a folder of its own
        folder = tools.prepare(
            self.staging / f'pruning.{self.jobs}',
            {'id': 'pruning', 'question': 'Does ExampleDB 2.0 prune?', 'public_query': None},
            inputs={'about': 'Title: A blog'},
            sources=[{**documents()[0], 'file': 'research/sources/k.md', 'supplied': 'k'}],
            fetch=fetch,
        )
        return tools.ResearchTools(
            folder, opener=opener, resolver=resolver or (lambda host: ['93.184.216.34'])
        )

    def test_quotes_are_placed_in_the_sources_own_wording(self):
        text = 'It said “pruning works” — mostly.\nSecond   line here.'
        self.assertEqual(
            tools.place(text, 'It said "pruning works" - mostly.'),
            (0, 'It said “pruning works” — mostly.'),
        )
        self.assertEqual(tools.place(text, 'Second line here.')[1], 'Second   line here.')
        self.assertIsNone(tools.place(text, 'Not there at all.'))

    def test_only_public_addresses_are_fetched(self):
        for address in ('127.0.0.1', '10.0.0.5', '169.254.1.1', '::1', 'fd00::1', '100.64.0.1'):
            self.assertFalse(tools.public(address), address)
        self.assertTrue(tools.public('93.184.216.34'))
        private = self.job(resolver=lambda host: ['10.0.0.5'])
        self.assertIn(
            'not on the public internet', private.save_source('https://intranet.example/')[1]
        )
        signed = self.job()
        self.assertIn('name or password', signed.save_source('https://me:pw@example.org/')[1])
        self.assertIn('Only http and https', signed.save_source('file:///etc/passwd')[1])

    def test_each_redirect_is_checked_again(self):
        hops = iter([(302, {'location': 'http://internal.example/'}, b''), (200, {}, PAGE)])
        resolved = {'example.org': ['93.184.216.34'], 'internal.example': ['192.168.1.2']}
        job = self.job(
            opener=lambda url, address, limit: next(hops), resolver=lambda host: resolved[host]
        )
        self.assertIn('not on the public internet', job.save_source('https://example.org/')[1])

    def test_a_saved_page_is_kept_as_text_named_by_its_content(self):
        job = self.job(
            opener=lambda url, address, limit: (200, {'content-type': 'text/html'}, PAGE)
        )
        ok, said = job.save_source('https://example.org/notes')
        self.assertTrue(ok, said)
        entry = next(item for item in job._index() if item['id'] == 's2')
        text = Path(job.folder / entry['local']).read_text()
        self.assertNotIn('x()', text)
        self.assertEqual(
            entry['file'], 'research/web/' + hashlib.sha256(text.encode()).hexdigest() + '.md'
        )
        self.assertEqual(entry['title'], 'Release notes')

    def test_save_source_is_offered_only_when_fetching_is_allowed(self):
        names = {entry['name'] for entry in self.job(fetch=False).offered()}
        self.assertNotIn('save_source', names)
        self.assertNotIn('ask_person', names)
        self.assertIn('submit_finding', names)
        self.assertIn('cannot fetch', self.job(fetch=False).save_source('https://example.org/')[1])

    def test_a_finding_is_checked_and_its_quotes_placed(self):
        job = self.job(fetch=False)
        refused = job.submit_finding('other', 'supported', 'S', evidence=[], headline='Yes.')
        self.assertIn('answers pruning', refused[1])
        refused = job.submit_finding('pruning', 'supported', 'S', evidence=[], headline='')
        self.assertIn('headline is empty', refused[1])
        self.assertIn('at least one quoted passage', refused[1])
        refused = job.submit_finding(
            'pruning',
            'supported',
            'S',
            headline='Yes.',
            evidence=[{'source_id': 's1', 'quote': 'Invented words here, long enough.'}],
        )
        self.assertIn('not in s1 as written', refused[1])
        ok, said = job.submit_finding(
            'pruning',
            'supported',
            'The notes say so.',
            headline='Yes, it prunes.',
            evidence=json.dumps(
                [
                    {
                        'source_id': 's1',
                        'quote': 'ExampleDB 2.0 supports predicate pruning on column scans.',
                    }
                ]
            ),
        )
        self.assertTrue(ok, said)
        finding = tools.collect(job.folder)['finding']
        self.assertEqual(finding['evidence'][0]['file'], 'research/sources/k.md')
        self.assertEqual(finding['evidence'][0]['source_id'], 'k')
        self.assertEqual(finding['evidence'][0]['start'], 0)

    def test_the_server_answers_as_an_agent_expects(self):
        job = self.job(fetch=False)
        listed = tools.answer(job, {'id': 1, 'method': 'tools/list'})['result']['tools']
        self.assertIn('read_source', [entry['name'] for entry in listed])
        out = io.StringIO()
        tools.serve(
            job,
            [
                json.dumps(
                    {
                        'id': 2,
                        'method': 'tools/call',
                        'params': {'name': 'list_inputs', 'arguments': {}},
                    }
                ),
                'not json',
            ],
            out,
        )
        reply = json.loads(out.getvalue())
        self.assertFalse(reply['result']['isError'])
        self.assertIn('Question pruning', reply['result']['content'][0]['text'])
        self.assertIn('No such method', json.dumps(tools.answer(job, {'id': 3, 'method': 'nope'})))


class FlowTests(Folder):
    def finder(self, quote='ExampleDB 2.0 supports predicate pruning on column scans.'):
        """A worker that answers with the supplied document."""

        def run_job(folder, guidance, task, command, web):
            self.assertIn('Research one question', guidance)
            self.assertIn('Question ID: pruning', task)
            worker = tools.ResearchTools(folder)
            ok, said = worker.submit_finding(
                'pruning',
                'supported',
                'The notes say so.',
                headline='Yes.',
                evidence=[{'source_id': 's1', 'quote': quote}],
            )
            self.assertTrue(ok, said)

        return run_job

    def test_a_finding_is_recorded_and_the_report_written(self):
        self.save()
        done = steps.research(
            self.folder, self.finder(), self.staging, about='Title: A blog', kind='blog post'
        )
        self.assertEqual(done['researched'], ['pruning'])
        self.assertEqual(done['status'], 'complete')
        self.assertIn('Answer: Yes.', (self.folder / project.REPORT).read_text())
        self.assertEqual(list(self.staging.iterdir()), [])

    def test_three_failed_tries_are_recorded_as_unavailable(self):
        self.save()
        tries = []

        def failing(folder, guidance, task, command, web):
            tries.append(folder.name)
            raise RuntimeError('the agent could not finish')

        done = steps.research(self.folder, failing, self.staging, about='x')
        self.assertEqual(tries, ['pruning.1', 'pruning.2', 'pruning.3'])
        self.assertEqual(done['unavailable'], ['pruning'])
        record = project.read_record(self.folder)
        self.assertIn('could not finish', record['results']['pruning']['limits'])

    def test_a_stopped_run_leaves_the_question_pending(self):
        self.save()

        def stopped(folder, guidance, task, command, web):
            raise steps.Stopped()

        with self.assertRaises(steps.Stopped):
            steps.research(self.folder, stopped, self.staging, about='x')
        self.assertEqual(project.status(self.folder)['pending'], ['pruning'])
        self.assertFalse((self.folder / project.REPORT).exists())

    def test_a_saved_page_a_finding_quotes_is_kept_with_the_item(self):
        self.save(allow_web=True, query='ExampleDB predicate pruning release notes')

        def from_the_web(folder, guidance, task, command, web):
            self.assertTrue(web)
            worker = tools.ResearchTools(
                folder,
                opener=lambda url, address, limit: (200, {'content-type': 'text/html'}, PAGE),
                resolver=lambda host: ['93.184.216.34'],
            )
            self.assertTrue(worker.save_source('https://example.org/notes')[0])
            ok, said = worker.submit_finding(
                'pruning',
                'supported',
                'The release notes say so.',
                headline='Yes.',
                evidence=[
                    {
                        'source_id': 's2',
                        'quote': 'ExampleDB 2.0 adds predicate pruning to every column scan.',
                    }
                ],
            )
            self.assertTrue(ok, said)

        done = steps.research(self.folder, from_the_web, self.staging, about='x', allow_web=True)
        self.assertEqual(done['status'], 'complete')
        saved = list((self.folder / 'research' / 'web').glob('*.md'))
        self.assertEqual(len(saved), 1)
        self.assertIn('predicate pruning', saved[0].read_text())

    def test_a_drafted_plan_is_checked(self):
        plan = steps.draft_plan(
            json.dumps(
                {'topic': 'T', 'items': [{'id': 'a-b', 'question': 'Q?', 'public_query': None}]}
            )
        )
        self.assertEqual(plan['items'][0]['claim'], None)
        for bad in (
            'not json',
            '{"topic": "T", "items": []}',
            '{"topic": "T", "items": [{"id": "Bad ID", "question": "Q"}]}',
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                steps.draft_plan(bad)


class CopyTests(unittest.TestCase):
    def test_this_copy_is_the_component_its_record_names(self):
        """Every studio carries the component unchanged: each file must match vendor.json."""
        package = Path(project.__file__).resolve().parent
        record = json.loads((package / 'vendor.json').read_text())
        self.assertEqual(record['component'], 'studio_research')
        listed = set(record['files'])
        present = {path.name for path in package.glob('*.py')}
        self.assertEqual(listed, present)
        for name, entry in record['files'].items():
            digest = hashlib.sha256((package / name).read_bytes()).hexdigest()
            self.assertEqual(digest, entry['sha256'], f'{name} differs from vendor.json')
        for path in package.glob('*.py'):
            self.assertNotRegex(
                path.read_text(),
                r'(?m)^(import|from) (studio|blog_|hub|deep_research)\b',
                path.name,
            )


if __name__ == '__main__':
    unittest.main()
