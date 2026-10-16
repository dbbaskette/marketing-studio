"""Blog research on harness-research: what Blog Studio adds around the shared command."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from hub_fixtures import SCRIPTS  # noqa: F401  (puts the scripts on the path, and the stand-in)
import brand_skill
import deep_research
import studio
from studio_research import project, runtime
from studio_sync import gitstate


class Recording:
    """A harness-research that remembers what it was asked, for the adapter's own rules."""

    def __init__(self):
        self.planned = []

    def plan(self, project, file, allow_web=False):
        self.planned.append((json.loads(Path(file).read_text()), allow_web))
        return {'run': 'r1', 'status': 'in-progress'}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'workspace'
        studio.initialize(self.root)

    def article(self, policy):
        result = subprocess.run(
            [
                'python3',
                str(Path(deep_research.__file__).with_name('studio.py')),
                '--root',
                str(self.root),
                'article',
                'create',
                '--title',
                'Synthetic blog',
                '--mode',
                'outline-only',
                '--research',
                policy,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        ident = json.loads(result.stdout)['id']
        return ident, self.root / 'articles' / ident

    def plan(self, ident, scope):
        query = 'synthetic public question' if scope == 'public-web' else None
        return deep_research.plan(
            self.root,
            ident,
            {
                'purpose': 'planning',
                'scope': scope,
                'items': [{'id': 'q', 'question': 'What?', 'public_query': query, 'claim': None}],
            },
        )

    def test_allow_web_is_passed_only_for_web_research(self):
        recording = Recording()
        with mock.patch.object(deep_research, 'tool', return_value=recording):
            open_ident, _ = self.article('web-allowed')
            self.plan(open_ident, 'public-web')
            self.plan(open_ident, 'supplied-only')
        self.assertEqual([allow for _, allow in recording.planned], [True, False])
        handed = recording.planned[0][0]
        self.assertEqual(handed['topic'], 'Synthetic blog')
        self.assertEqual(handed['sources'], [])
        self.assertEqual(handed['items'][0]['claim'], None)

    def test_record_keeps_where_harness_research_writes(self):
        recording = Recording()
        with mock.patch.object(deep_research, 'tool', return_value=recording):
            ident, directory = self.article('supplied-only')
            record = self.plan(ident, 'supplied-only')
        self.assertEqual(record['research']['engine'], 'harness-research')
        self.assertEqual(record['research']['report'], '.harness-research/research-report.md')
        self.assertEqual(record['research']['plan'], 'research/plan.json')
        self.assertTrue((directory / 'research' / 'plan.md').is_file())
        self.assertEqual(record['research']['run'], 'r1')

    def test_research_saved_before_harness_research_is_stale_and_kept(self):
        ident, directory = self.article('supplied-only')
        studio.write_json(directory / 'derived' / 'research.json', {'schema': 1, 'run': 'old'})
        (directory / 'derived' / 'research-report.md').write_text('# Research brief\n')
        found = deep_research.status(self.root, ident)
        self.assertEqual(found['status'], 'stale')
        self.assertTrue(found['legacy'])
        self.assertIn('Plan it again', found['note'])
        self.assertTrue(found['report'].endswith('derived/research-report.md'))
        self.assertTrue((directory / 'derived' / 'research.json').is_file())

    def test_a_reference_has_the_same_snapshot_name_wherever_it_is_opened(self):
        _, directory = self.article('supplied-only')
        document = {
            'title': 'N',
            'origin': 'https://example.org/notes',
            'text': 'x',
            'status': 'ready',
        }
        key = project.key(document['origin'], document['text'])
        manifest = project.snapshot(directory, [document, dict(document)])  # a duplicate is one
        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0]['file'], f'research/sources/{key}.md')
        self.assertEqual((directory / 'research' / 'sources' / f'{key}.md').read_text(), 'x')
        waiting = project.snapshot(directory, [{**document, 'text': 'y', 'status': 'extracting'}])
        self.assertIsNone(waiting[0]['file'])
        self.assertIn('not ready', waiting[0]['limits'])
        self.assertFalse((directory / 'research' / 'sources' / f'{key}.md').exists())
        self.assertEqual(key, project.key('https://example.org/notes', 'x'))  # never a local ID


class TeamTests(unittest.TestCase):
    def test_reference_snapshots_are_never_shared(self):
        self.assertIn('**/research/sources/', gitstate.IGNORED)
        self.assertIn('**/.harness-research/guidance/', gitstate.IGNORED)
        if not shutil.which('git'):
            self.skipTest('git is not installed')
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run(['git', 'init', '-q', folder], check=True)
            Path(folder, '.gitignore').write_text('\n'.join(gitstate.IGNORED) + '\n')
            article = Path(folder, 'blogs', 'one')
            (article / 'research' / 'sources').mkdir(parents=True)
            (article / 'research' / 'sources' / 'k.md').write_text('private reference text')
            (article / 'research' / 'plan.json').write_text('{}')
            (article / '.harness-research').mkdir()
            (article / '.harness-research' / 'research.json').write_text('{}')

            def ignored(name):
                return (
                    subprocess.run(
                        ['git', '-C', folder, 'check-ignore', 'blogs/one/' + name],
                        capture_output=True,
                    ).returncode
                    == 0
                )

            self.assertTrue(ignored('research/sources/k.md'))
            self.assertFalse(ignored('research/plan.json'))
            self.assertFalse(ignored('.harness-research/research.json'))


class VersionTests(unittest.TestCase):
    def test_companion_versions_are_asked_with_double_dash_version(self):
        with tempfile.TemporaryDirectory() as folder:
            place = Path(folder) / 'harness-research'
            (place / 'scripts').mkdir(parents=True)
            (place / 'scripts' / 'harness-research.mjs').write_text('')
            asked = []

            def run(command, cwd, seconds, said):
                asked.append(command)
                return 0, 'harness-research 0.8.1\n', ''

            with (
                mock.patch.object(
                    brand_skill.companion, 'locations', side_effect=lambda *a, **k: [place]
                ),
                mock.patch.object(brand_skill.companion, 'run_command', side_effect=run),
            ):
                found = brand_skill._companions()
        self.assertEqual(asked[0][-1], '--version')
        self.assertEqual(found['harness-research'], '0.8.1')


@unittest.skipUnless(shutil.which('node'), 'Node is not installed')
class LiveTests(unittest.TestCase):
    """The real harness-research, when it is installed here; skipped otherwise."""

    def setUp(self):
        saved = os.environ.pop(runtime.STAND_IN, None)
        self.addCleanup(lambda: saved and os.environ.__setitem__(runtime.STAND_IN, saved))
        try:
            self.tool = runtime.Research()
        except ValueError:
            self.skipTest('harness-research is not installed on this computer')

    def test_plan_record_and_status_against_the_installed_command(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / 'BRIEF.md').write_text('# Brief\nWhat the post covers.\n')
            (project / 'notes.md').write_text('ExampleDB 2.0 supports predicate pruning.')
            plan = project / 'plan.json'
            plan.write_text(
                json.dumps(
                    {
                        'topic': 'Live check',
                        'purpose': 'planning',
                        'scope': 'supplied-only',
                        'input_files': ['BRIEF.md'],
                        'sources': [
                            {
                                'id': 'notes',
                                'title': 'Notes',
                                'origin': 'supplied notes.md',
                                'file': 'notes.md',
                                'limits': 'none',
                            }
                        ],
                        'items': [
                            {'id': 'q', 'question': 'Pruning?', 'public_query': None, 'claim': None}
                        ],
                    }
                )
            )
            run = self.tool.plan(project, plan)['run']
            quote = 'ExampleDB 2.0 supports predicate pruning.'
            done = self.tool.record(
                project,
                run,
                'q',
                {
                    'status': 'supported',
                    'headline': 'Yes.',
                    'summary': 'The notes say so.',
                    'limits': 'Notes only.',
                    'evidence': [
                        {
                            'file': 'notes.md',
                            'title': 'Notes',
                            'origin': 'supplied notes.md',
                            'quote': quote,
                            'start': 0,
                            'locator': 'line 1',
                            'source_id': 'notes',
                        }
                    ],
                },
            )
            self.assertEqual(done['status'], 'complete')
            report = Path(self.tool.status(project)['report']).read_text()
        self.assertIn('Answer: Yes.', report)
        self.assertRegex(self.tool.version(), r'^\d+\.\d+\.\d+$')


if __name__ == '__main__':
    unittest.main()
