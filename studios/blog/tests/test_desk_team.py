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

    def save(self, seen, text, session='c' * 16):
        return management.dispatch(
            self.root,
            'desk-save',
            {
                'id': self.made['id'],
                'seen': seen,
                'part': 'title',
                'text': text,
                'session': session,
            },
        )

    def test_typing_is_kept_locally_once_per_session_and_shared_on_leaving(self):
        remote, local = self.remote_commits(), self.local_commits()
        seen = 1
        for n in range(3):
            seen = self.save(seen, 'Title %d' % n)['revision']
        self.assertEqual(self.remote_commits(), remote)
        self.assertEqual(self.local_commits(), local + 1)
        self.assertEqual(gitstate.changed(self.found), [])
        # Another editing session is its own commit.
        seen = self.save(seen, 'Title again', session='d' * 16)['revision']
        self.assertEqual(self.local_commits(), local + 2)
        shared = management.dispatch(self.root, 'desk-share', {'id': self.made['id']})
        self.assertTrue(shared['team_sync']['shared'])
        self.assertEqual(self.remote_commits(), self.local_commits())

    def test_a_decision_after_typing_shares_the_typing_too(self):
        seen = self.save(1, 'Typed title')['revision']
        management.dispatch(
            self.root,
            'desk-note',
            {'id': self.made['id'], 'seen': seen, 'part': self.part, 'note': 'More.'},
        )
        self.assertEqual(self.remote_commits(), self.local_commits())
        self.assertIn(
            'Typed title',
            support.git(self.remote, 'show', 'main:blogs/' + self.made['id'] + '/DRAFT.md'),
        )

    def test_a_share_that_failed_is_committed_by_the_next_desk_request(self):
        management.dispatch(
            self.root,
            'desk-note',
            {'id': self.made['id'], 'seen': 1, 'part': self.part, 'note': 'More.'},
        )

        def worker(engine, payload, guidance, **options):
            return {'content': 'Settled.', 'notes': '', 'gaps': []}

        with patch.object(
            teams, 'saved', side_effect=support.WorkspaceError('Busy. Retry shortly.')
        ):
            tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertTrue(gitstate.changed(self.found))
        shown = management.view(self.root, 'desk', {'id': [self.made['id']]})
        management.dispatch(
            self.root,
            'desk-note',
            {'id': self.made['id'], 'seen': shown['revision'], 'part': self.part, 'note': 'Again.'},
        )
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertIn(
            'Settled.',
            support.git(self.remote, 'show', 'main:blogs/' + self.made['id'] + '/DRAFT.md'),
        )


if __name__ == '__main__':
    unittest.main()
