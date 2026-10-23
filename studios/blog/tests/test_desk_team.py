"""The writing desk in a team workspace: a disposable bare remote, never a real one."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import blog_runner
import management
import team_workspace as teams
import tool_jobs
from studio_sync import gitstate, support
from test_desk import DRAFT


class DeskTeamTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='desk-team-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        environment = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.base / 'data'),
                'STUDIOS_CONFIG': str(self.base / 'studios-config.json'),
                'BRAND_SKILL_RUNTIME': str(self.base / 'no-brand'),
                'HARNESS_RESEARCH_RUNTIME': str(self.base / 'no-research'),
                'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_AUTHOR_NAME': 'Synthetic Author',
                'GIT_AUTHOR_EMAIL': 'author@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic Author',
                'GIT_COMMITTER_EMAIL': 'author@example.invalid',
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.remote = self.base / 'team.git'
        subprocess.run(
            ['git', 'init', '--bare', '--initial-branch=main', str(self.remote)],
            check=True,
            capture_output=True,
        )
        seed = self.base / 'seed'
        subprocess.run(
            ['git', 'clone', str(self.remote), str(seed)], check=True, capture_output=True
        )
        (seed / 'presentations').mkdir()
        (seed / 'presentations/hub.json').write_text('{"schema":1,"tool":"presentation-studio"}')
        support.git(seed, 'add', '.')
        support.git(seed, 'commit', '-m', 'fixture')
        support.git(seed, 'push', 'origin', 'main')
        self.root = teams.join(str(self.remote))
        self.found = teams.space(self.root)
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        self.made = management.dispatch(
            self.root, 'desk-create', {'operation': 'a' * 32, 'title': 'T', 'manuscript': DRAFT}
        )
        self.part = self.made['sections'][0]['id']

    def remote_commits(self):
        return int(support.git(self.remote, 'rev-list', '--count', 'main'))

    def local_commits(self):
        return int(support.git(self.found.repo, 'rev-list', '--count', 'HEAD'))

    def test_a_settled_result_is_recorded_and_the_next_request_works(self):
        queued = management.dispatch(
            self.root,
            'desk-note',
            {'id': self.made['id'], 'seen': 1, 'part': self.part, 'note': 'More.'},
        )

        def worker(engine, payload, guidance, **options):
            return {'content': 'Settled text.', 'notes': '', 'gaps': []}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(gitstate.changed(self.found), [])
        shown = management.view(self.root, 'desk', {'id': [self.made['id']]})
        self.assertEqual(shown['sections'][0]['text'], 'Settled text.')
        self.assertTrue(tool_jobs.read(self.root, queued['working']['id'])['applied'])
        management.dispatch(
            self.root,
            'desk-save',
            {
                'id': self.made['id'],
                'seen': shown['revision'],
                'part': 'title',
                'text': 'After settle',
                'session': 'b' * 16,
            },
        )
        self.assertEqual(
            management.view(self.root, 'desk', {'id': [self.made['id']]})['title'], 'After settle'
        )


if __name__ == '__main__':
    unittest.main()
