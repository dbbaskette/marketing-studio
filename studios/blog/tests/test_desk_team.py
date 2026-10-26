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


class TeamCase(unittest.TestCase):
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


class DeskTeamTests(TeamCase):
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

    def test_finishing_suggestions_wait_here_and_only_apply_is_shared(self):
        import json

        ident = self.made['id']
        queued = management.dispatch(
            self.root, 'desk-finish', {'id': ident, 'seen': 1, 'tool': 'humanize', 'level': 'light'}
        )
        suggestion = {'part': self.part, 'before': 'First text.', 'after': 'The first text.'}

        def worker(engine, payload, guidance, **options):
            return {'content': json.dumps({'suggestions': [suggestion]}), 'notes': ''}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(gitstate.changed(self.found), [])
        remote = self.remote_commits()
        job = queued['working']['id']
        management.dispatch(self.root, 'desk-skip', {'id': ident, 'job': job, 'items': ['p1']})
        self.assertEqual(self.remote_commits(), remote)
        self.assertEqual(gitstate.changed(self.found), [])
        # A second set, applied: a decision, recorded and shared.
        management.dispatch(
            self.root, 'desk-finish', {'id': ident, 'seen': 1, 'tool': 'humanize', 'level': 'light'}
        )
        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        shown = management.view(self.root, 'desk', {'id': [ident]})
        second = shown['finishing']['humanize']['job']
        management.dispatch(
            self.root,
            'desk-apply',
            {'id': ident, 'seen': shown['revision'], 'job': second, 'items': [{'id': 'p1'}]},
        )
        self.assertEqual(self.remote_commits(), self.local_commits())
        self.assertIn(
            'The first text.',
            support.git(self.remote, 'show', 'main:blogs/' + ident + '/DRAFT.md'),
        )

    def finish_view(self):
        return management.view(self.root, 'desk', {'id': [self.made['id']]})

    def finish_worker(self, content):
        import json

        def worker(engine, payload, guidance, **options):
            text = content if isinstance(content, str) else json.dumps(content)
            return {'content': text, 'notes': ''}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))

    def test_finishing_leaves_the_team_workspace_clean_at_every_step(self):
        import secrets

        ident = self.made['id']
        clean = lambda: self.assertEqual(gitstate.changed(self.found), [])  # noqa: E731
        # An unreadable result: said on the job, nothing to record.
        management.dispatch(
            self.root, 'desk-finish', {'id': ident, 'seen': 1, 'tool': 'humanize', 'level': 'light'}
        )
        self.finish_worker('not json')
        clean()
        self.assertIn('cannot read', self.finish_view()['jobs'][-1]['error'])
        # Proofread reads only.
        remote = self.remote_commits()
        management.view(self.root, 'desk-proofread', {'id': [ident]})
        clean()
        self.assertEqual(self.remote_commits(), remote)
        # Applying a headline is a decision, shared; its sibling is skipped.
        management.dispatch(self.root, 'desk-finish', {'id': ident, 'seen': 1, 'tool': 'headline'})
        self.finish_worker(
            {'titles': [{'text': 'New title A'}, {'text': 'New title B'}], 'openings': []}
        )
        shown = self.finish_view()
        management.dispatch(
            self.root,
            'desk-apply',
            {
                'id': ident,
                'seen': shown['revision'],
                'job': shown['finishing']['headline']['job'],
                'items': [{'id': 'p1'}],
            },
        )
        clean()
        self.assertEqual(self.remote_commits(), self.local_commits())
        self.assertTrue(
            support.git(self.remote, 'show', 'main:blogs/' + ident + '/DRAFT.md').startswith(
                '# New title A'
            )
        )
        # A repurposed copy is a new blog, shared, once.
        job = management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'job-create',
                'kind': 'repurpose',
                'id': ident,
                'operation': secrets.token_hex(16),
                'format': 'linkedin',
                'words': 100,
            },
        )
        saved = tool_jobs.read(self.root, job['id'])
        saved.update(status='ready', result={'content': 'A short post.', 'notes': ''})
        tool_jobs.write(self.root, saved)
        made = management.dispatch(
            self.root,
            'desk-repurpose',
            {'id': ident, 'job': job['id'], 'title': 'Copy post', 'content': 'A short post.'},
        )['made']
        clean()
        self.assertTrue(
            support.git(self.remote, 'ls-tree', 'main', 'blogs/' + made['id'] + '/DRAFT.md')
        )
        # Skip records nothing, so it leaves a result an older process finished for the next
        # request that is shared, never uncommitted.
        management.dispatch(
            self.root,
            'desk-finish',
            {
                'id': ident,
                'seen': self.finish_view()['revision'],
                'tool': 'humanize',
                'level': 'light',
            },
        )
        self.finish_worker(
            {
                'suggestions': [
                    {'part': self.part, 'before': 'First text.', 'after': 'The first text.'}
                ]
            }
        )
        humanize = self.finish_view()['finishing']['humanize']['job']
        queued = management.dispatch(
            self.root,
            'desk-note',
            {
                'id': ident,
                'seen': self.finish_view()['revision'],
                'part': self.part,
                'note': 'More.',
            },
        )
        ready = tool_jobs.read(self.root, queued['working']['id'])
        ready.update(
            status='ready', result={'content': 'Rewritten elsewhere.', 'notes': ''}, finished_at='x'
        )
        tool_jobs.write(self.root, ready)
        management.dispatch(self.root, 'desk-skip', {'id': ident, 'job': humanize, 'items': ['p1']})
        clean()
        self.assertFalse(tool_jobs.read(self.root, ready['id']).get('settled_at'))

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

    def test_leaving_the_desk_with_nothing_unshared_fetches_and_pushes_nothing(self):
        remote = self.remote_commits()
        with patch('team_workspace.refresh', side_effect=AssertionError('no fetch or push')):
            shared = management.dispatch(self.root, 'desk-share', {'id': self.made['id']})
        self.assertFalse(shared['shared'])
        self.assertEqual(self.remote_commits(), remote)

    def test_leaving_the_desk_never_claims_a_blog(self):
        ident = self.made['id']
        support.git(self.found.repo, 'rm', '-q', str(self.root / ident / 'run.json'))
        support.git(self.found.repo, 'commit', '-q', '-m', 'Nobody drives it')
        support.git(self.found.repo, 'push', '-q', 'origin', 'HEAD:main')
        local, remote = self.local_commits(), self.remote_commits()
        shared = management.dispatch(self.root, 'desk-share', {'id': ident})
        self.assertFalse(shared['shared'])
        self.assertFalse((self.root / ident / 'run.json').exists(), 'viewing claims nothing')
        self.assertEqual((self.local_commits(), self.remote_commits()), (local, remote))

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

    def test_a_failed_local_commit_leaves_head_and_the_index_as_they_were(self):
        seen = self.save(1, 'One')['revision']
        head = support.git(self.found.repo, 'rev-parse', 'HEAD')
        with patch.object(gitstate, 'commit', side_effect=support.GitError('synthetic failure')):
            with self.assertRaises(support.GitError):
                self.save(seen, 'Two')
        self.assertEqual(support.git(self.found.repo, 'rev-parse', 'HEAD'), head)
        self.assertTrue(support.passes(self.found.repo, 'diff', '--cached', '--quiet'))
        # The edit is in the files; the next save commits it in the same session commit.
        self.save(seen + 1, 'Three')
        self.assertEqual(
            support.git(self.found.repo, 'rev-parse', 'HEAD~1'),
            support.git(self.found.repo, 'rev-parse', head + '~1'),
        )
        self.assertEqual(gitstate.changed(self.found), [])


if __name__ == '__main__':
    unittest.main()


class DeskStartTeamTests(TeamCase):
    """A desk start in a team workspace never leaves files outside a recorded decision."""

    def note_elsewhere(self):
        shown = management.view(self.root, 'desk', {'id': [self.made['id']]})
        noted = management.dispatch(
            self.root,
            'desk-note',
            {'id': self.made['id'], 'seen': shown['revision'], 'part': self.part, 'note': 'x'},
        )
        management.dispatch(
            self.root, 'desk-stop', {'id': self.made['id'], 'job': noted['working']['id']}
        )

    def start(self):
        return management.dispatch(
            self.root,
            'desk-create',
            {
                'operation': 'b' * 32,
                'title': 'Topic',
                'way': 'topic',
                'point': 'P.',
                'research_from': {'sites': [], 'web': True},
            },
        )

    def test_a_research_phase_leaves_nothing_to_record_and_other_blogs_go_on(self):
        made = self.start()
        during = []

        def worker(engine, payload, guidance, **options):
            if not during:
                during.append(gitstate.changed(self.found))
                self.note_elsewhere()  # Another blog's decision while research works.
                raise ValueError('Research ran out of time.')
            return {'content': 'x', 'notes': ''}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(during, [[]])
        self.assertEqual(gitstate.changed(self.found), [])
        shown = management.view(self.root, 'desk', {'id': [made['id']]})
        self.assertEqual(shown['start']['problem'], 'Research ran out of time.')
        # After the failed step: another blog's note and a new desk blog both work.
        self.note_elsewhere()
        management.dispatch(
            self.root,
            'desk-create',
            {'operation': 'c' * 32, 'title': 'B', 'manuscript': '# B\n\n## S\n\nText.\n'},
        )
        retried = management.dispatch(self.root, 'desk-retry', {'id': made['id']})
        self.assertEqual(retried['working']['kind'], 'desk-research')

    def test_research_under_way_leaves_the_tree_clean_for_refresh_shares_and_sync(self):
        made = self.start()
        other = self.made['id']
        during = []

        def worker(engine, payload, guidance, **options):
            if 'research questions' in guidance:
                return {'content': '1. What stops jobs?', 'notes': ''}
            during.append(gitstate.changed(self.found))
            # Meanwhile the person refreshes, leaves another blog's desk, and the page's
            # background check runs: none is refused for the research under way.
            management.dispatch(self.root, 'refresh', {})
            management.dispatch(self.root, 'desk-share', {'id': other})
            teams.refresh(self.root)
            during.append(gitstate.changed(self.found))
            return {'content': '# Findings\n\nTimeouts.', 'notes': ''}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(during, [[], []])
        self.assertEqual(gitstate.changed(self.found), [])
        folder = self.root / made['id'] / 'derived'
        self.assertTrue((folder / 'blog-research-plan.md').is_file())
        self.assertTrue((folder / 'blog-research.md').is_file())
        shared = support.git(self.remote, 'ls-tree', '-r', '--name-only', 'main')
        self.assertIn(made['id'] + '/derived/blog-research.md', shared)

    def test_refresh_keeps_desk_leftovers_first(self):
        folder = self.root / self.made['id'] / 'desk'
        (folder / 'start.json').write_text('{"left": true}')
        management.dispatch(self.root, 'refresh', {})
        self.assertEqual(gitstate.changed(self.found), [])
        (folder / 'start.json').write_text('{"left": 2}')
        management.dispatch(self.root, 'team-sync', {})
        self.assertEqual(gitstate.changed(self.found), [])
        # The page's background check, once.
        (folder / 'start.json').write_text('{"left": 3}')

        class Once:
            def is_set(self):
                return False

            def wait(self, seconds):
                return True

        engine = blog_runner.Engine(self.root)
        engine.closed = Once()
        engine.sync_team()
        self.assertEqual(gitstate.changed(self.found), [])
        report = (self.root / '.team-sync.json').read_text()
        self.assertNotIn('Local files changed', report)

    def test_a_chat_save_of_a_desk_blog_is_one_shared_decision(self):
        import sys

        import desk
        import studio

        edited = self.base / 'edited.md'
        body = (self.root / self.made['id'] / 'DRAFT.md').read_text().replace('First', 'Fixed')
        edited.write_text(body)
        remote = self.remote_commits()
        argv = ['studio.py', '--root', str(self.root), 'article', 'save', '--id', self.made['id']]
        argv += ['--kind', 'draft', '--file', str(edited)]
        with patch.object(sys, 'argv', argv), patch('builtins.print'):
            self.assertEqual(studio.main(), 0)
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertGreater(self.remote_commits(), remote)
        shown = management.view(self.root, 'desk', {'id': [self.made['id']]})
        self.assertIn('Fixed', shown['sections'][0]['text'])
        self.assertEqual(desk.versions(self.root, self.made['id'], self.part)[0]['source'], 'chat')

    def test_leftovers_under_any_desk_blog_are_kept_before_the_next_decision(self):
        folder = self.root / self.made['id'] / 'desk'
        (folder / 'start.json').write_text('{"left": true}')
        other = management.dispatch(
            self.root,
            'desk-create',
            {'operation': 'd' * 32, 'title': 'B', 'manuscript': '# B\n\n## S\n\nText.\n'},
        )
        self.assertTrue(other['id'])
        self.assertEqual(gitstate.changed(self.found), [])


class DeskTeamImageTests(TeamCase):
    def folder(self, ident):
        import studio

        return studio.inside(self.root, 'articles', ident)

    def test_an_older_record_is_cleaned_on_viewing_as_its_own_recorded_change(self):
        from test_desk import OPENING, owner_shaped

        ident = self.made['id']
        body = owner_shaped(self, self.made)
        gitstate.commit(self.found, 'A record kept before images moved out', [ident])
        self.assertEqual(gitstate.changed(self.found), [])
        commits = self.local_commits()
        shown = management.view(self.root, 'desk', {'id': [ident]})
        self.assertEqual(shown['opening'], OPENING)
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertEqual(self.local_commits(), commits + 1)
        self.assertIn('images', support.git(self.found.repo, 'log', '-1', '--format=%s'))
        self.assertEqual((self.folder(ident) / 'DRAFT.md').read_text(), body)
        # A desk page open before the cleaning saves as it would have.
        management.dispatch(
            self.root,
            'desk-save',
            {
                'id': ident,
                'seen': 2,
                'part': 'opening',
                'text': OPENING + ' More.',
                'session': 'e' * 16,
            },
        )
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertIn('More.', (self.folder(ident) / 'DRAFT.md').read_text())


if __name__ == '__main__':
    unittest.main()
