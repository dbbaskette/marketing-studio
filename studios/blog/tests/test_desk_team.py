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

    def test_check_spelling_and_grammar_leaves_the_tree_clean_and_shares_only_accepts(self):
        made = management.dispatch(
            self.root,
            'desk-create',
            {'operation': 'c' * 32, 'title': 'T2', 'manuscript': DRAFT, 'first_pass': 'copyedit'},
        )
        ident = made['id']
        self.assertEqual(made['working']['kind'], 'finish-copyedit')
        clean = lambda: self.assertEqual(gitstate.changed(self.found), [])  # noqa: E731
        clean()
        part = made['sections'][0]['id']
        self.finish_worker(
            {
                'suggestions': [
                    {'part': part, 'before': 'First text.', 'after': 'The first text.'},
                    {'part': 'opening', 'before': 'An opening paragraph.', 'after': 'An opening.'},
                ]
            }
        )
        clean()
        shown = management.view(self.root, 'desk', {'id': [ident]})
        job = shown['finishing']['copyedit']['job']
        remote = self.remote_commits()
        management.dispatch(self.root, 'desk-skip', {'id': ident, 'job': job, 'items': ['p2']})
        clean()
        self.assertEqual(self.remote_commits(), remote)
        management.dispatch(
            self.root,
            'desk-apply',
            {'id': ident, 'seen': shown['revision'], 'job': job, 'items': [{'id': 'p1'}]},
        )
        clean()
        self.assertEqual(self.remote_commits(), self.local_commits())
        body = support.git(self.remote, 'show', 'main:blogs/' + ident + '/DRAFT.md')
        self.assertIn('The first text.', body)
        self.assertIn('An opening paragraph.', body)

    def test_the_human_sounding_chain_leaves_the_tree_clean_and_shares_only_accepts(self):
        made = management.dispatch(
            self.root,
            'desk-create',
            {
                'operation': 'd' * 32,
                'title': 'T3',
                'manuscript': DRAFT,
                'first_pass': 'copyedit',
                'humanize': 'light',
            },
        )
        ident, part = made['id'], made['sections'][0]['id']
        clean = lambda: self.assertEqual(gitstate.changed(self.found), [])  # noqa: E731
        remote = self.remote_commits()
        self.finish_worker(
            {'suggestions': [{'part': part, 'before': 'First text.', 'after': 'The first text.'}]}
        )
        clean()
        shown = management.view(self.root, 'desk', {'id': [ident]})
        self.assertEqual(shown['working']['kind'], 'finish-humanize')
        self.finish_worker(
            {
                'suggestions': [
                    {'part': 'opening', 'before': 'An opening paragraph.', 'after': 'An opening.'}
                ]
            }
        )
        clean()
        self.assertEqual(self.remote_commits(), remote, 'waiting suggestions are not decisions')
        shown = management.view(self.root, 'desk', {'id': [ident]})
        self.assertIsNone(shown['working'])
        self.assertEqual(sorted(shown['finishing']), ['copyedit', 'humanize'])
        # Check again reruns both and still writes nothing tracked.
        management.dispatch(self.root, 'desk-review', {'id': ident, 'seen': shown['revision']})
        clean()
        self.assertEqual(self.remote_commits(), remote)
        management.dispatch(
            self.root,
            'desk-stop',
            {
                'id': ident,
                'job': management.view(self.root, 'desk', {'id': [ident]})['working']['id'],
            },
        )
        clean()
        management.dispatch(
            self.root,
            'desk-apply',
            {
                'id': ident,
                'seen': shown['revision'],
                'job': shown['finishing']['humanize']['job'],
                'items': [{'id': 'p1'}],
            },
        )
        clean()
        self.assertEqual(self.remote_commits(), self.local_commits())
        body = support.git(self.remote, 'show', 'main:blogs/' + ident + '/DRAFT.md')
        self.assertIn('An opening.', body)

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


class DeskDriverTests(TeamCase):
    """A teammate on another computer takes over, or is handed, a blog on the desk."""

    def other(self):
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        root = teams.join(str(self.remote))
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(root), None))
        return root

    def desk(self, root):
        return management.view(root, 'desk', {'id': [self.made['id']]})

    def save(self, root, seen, text):
        return management.dispatch(
            root,
            'desk-save',
            {
                'id': self.made['id'],
                'seen': seen,
                'part': 'title',
                'text': text,
                'session': 'e' * 16,
            },
        )

    def decide(self, root, action, expected):
        return management.dispatch(
            root,
            'team-' + action,
            {'id': self.made['id'], 'expected': expected, 'confirmed': True},
        )

    def test_a_teammate_takes_over_a_desk_blog(self):
        ours = self.desk(self.root)
        self.assertTrue(ours['team'])
        self.assertTrue(ours['driver']['here'])
        self.assertIsNone(ours['elsewhere'])
        other = self.other()
        shown = self.desk(other)
        self.assertTrue(shown['team'])
        self.assertFalse(shown['driver']['here'])
        self.assertIn('Take it over to change it.', shown['elsewhere'])
        with self.assertRaisesRegex(ValueError, 'another computer'):
            self.save(other, shown['revision'], 'Not yet')
        self.decide(other, 'takeover', shown['expected'])
        shown = self.desk(other)
        self.assertTrue(shown['driver']['here'])
        self.assertIsNone(shown['elsewhere'])
        self.save(other, shown['revision'], 'Taken over')
        self.assertEqual(self.desk(other)['title'], 'Taken over')

    def test_a_takeover_stops_a_desk_job_working_here(self):
        # Sharing waits while a step works here (sync_guard), so the takeover is learned
        # only when a queued job starts just after that check: as the run worker was, the
        # desk job working then is stopped.
        queued = management.dispatch(
            self.root,
            'desk-note',
            {'id': self.made['id'], 'seen': 1, 'part': self.part, 'note': 'More.'},
        )['working']
        job = tool_jobs.read(self.root, queued['id'])
        runner = blog_runner.engine(self.root)
        other = self.other()
        self.decide(other, 'takeover', self.desk(other)['expected'])
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'data')
        checked, calls = gitstate.worker_in_progress, []

        def check_then_start(*arguments, **options):
            busy = checked(*arguments, **options)
            calls.append(busy)
            # The last check is the one made after the fetch, just before replaying.
            if not busy and len(calls) == 2:
                # tool_jobs.once starts the job here, after sharing checked for steps.
                tool_jobs.write(self.root, {**job, 'status': 'working', 'attempts': 1})
                runner.current = 'tool:' + job['id']
            return busy

        with patch.object(gitstate, 'worker_in_progress', check_then_start):
            teams.refresh(self.root)
        self.assertTrue(runner.stop.is_set())
        stopped = tool_jobs.read(self.root, queued['id'])
        self.assertEqual(stopped['status'], 'cancelled')
        self.assertIn('Another computer took this blog over', stopped['error'])
        self.assertEqual(stopped['payload'], job['payload'])  # Its inputs are kept.
        self.assertFalse(self.desk(self.root)['driver']['here'])

    def test_take_over_refuses_a_desk_view_that_changed(self):
        other = self.other()
        outdated = self.desk(other)['expected']
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'data')
        self.save(self.root, self.desk(self.root)['revision'], 'Changed by the driver')
        management.dispatch(self.root, 'desk-share', {'id': self.made['id']})
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        with self.assertRaisesRegex(
            ValueError, 'This blog changed. Reload before changing its driver or publishing it.'
        ):
            self.decide(other, 'takeover', outdated)
        self.assertFalse(self.desk(other)['driver']['here'])

    def test_hand_over_from_the_desk(self):
        shown = self.desk(self.root)
        self.decide(self.root, 'handover', shown['expected'])
        shown = self.desk(self.root)
        self.assertIsNone(shown['driver'])
        self.assertEqual(
            shown['elsewhere'],
            'Nobody is running this blog. Take it to carry on with it from this computer.',
        )
        with self.assertRaisesRegex(ValueError, 'Nobody is running this blog'):
            self.save(self.root, shown['revision'], 'Handed over')
        other = self.other()
        self.decide(other, 'take', self.desk(other)['expected'])
        shown = self.desk(other)
        self.assertTrue(shown['driver']['here'])
        self.save(other, shown['revision'], 'Taken')

    def test_a_teammate_takes_over_a_start_that_stopped_and_retries_it(self):
        started = management.dispatch(
            self.root,
            'desk-create',
            {'operation': 'c' * 32, 'title': 'Stalled topic', 'way': 'topic', 'point': 'P.'},
        )

        def worker(engine, payload, guidance, **options):
            raise ValueError('The assistant stopped.')

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        self.assertEqual(
            management.view(self.root, 'desk', {'id': [started['id']]})['start']['problem'],
            'The assistant stopped.',
        )
        other = self.other()
        shown = management.view(other, 'desk', {'id': [started['id']]})
        self.assertIsNone(shown['start']['ended_at'])
        self.assertTrue(shown['start']['problem'], 'stopped, as this computer sees it')
        self.assertFalse(shown['driver']['here'])
        self.assertIn('Take it over to change it.', shown['elsewhere'])
        with self.assertRaisesRegex(ValueError, 'another computer'):
            management.dispatch(other, 'desk-retry', {'id': started['id']})
        management.dispatch(
            other,
            'team-takeover',
            {'id': started['id'], 'expected': shown['expected'], 'confirmed': True},
        )
        shown = management.view(other, 'desk', {'id': [started['id']]})
        self.assertTrue(shown['driver']['here'])
        self.assertIsNone(shown['elsewhere'])
        retried = management.dispatch(other, 'desk-retry', {'id': started['id']})
        self.assertEqual(retried['working']['kind'], 'desk-outline')
        self.assertEqual(retried['start']['problem'], '')


class DeskPublishTests(TeamCase):
    """Publishing a desk blog to the team as a numbered revision: once the desk counts it
    finished (marked as published, with no desk job under way), as the blog list does."""

    def act(self, ident, action, **data):
        return management.dispatch(
            self.root,
            action,
            {
                'id': ident,
                'expected': management.detail(self.root, ident)['expected'],
                **data,
            },
        )

    def publish(self, ident):
        return self.act(ident, 'team-publish', confirmed=True)

    def mark_published(self, ident):
        self.act(
            ident,
            'schedule',
            stage='published',
            confirm_stage=True,
            publication_url='https://example.invalid/fictional-post',
        )

    def tags(self):
        return support.git(self.found.repo, 'tag')

    def test_a_desk_blog_is_published_once_the_desk_counts_it_finished(self):
        ident = self.made['id']
        with self.assertRaisesRegex(ValueError, '^' + teams.DESK_UNPUBLISHED + '$'):
            self.publish(ident)
        self.assertEqual(self.tags(), '')
        self.mark_published(ident)
        queued = management.dispatch(
            self.root, 'desk-note', {'id': ident, 'seen': 1, 'part': self.part, 'note': 'More.'}
        )['working']
        with self.assertRaisesRegex(ValueError, '^' + teams.DESK_WORKING + '$'):
            self.publish(ident)
        self.assertEqual(self.tags(), '')
        management.dispatch(self.root, 'desk-stop', {'id': ident, 'job': queued['id']})
        published = self.publish(ident)
        self.assertIn('blog-studio/blogs/' + ident + '/1', self.tags())
        self.assertTrue(published)

    def test_a_finished_run_opened_on_the_desk_is_published_as_before(self):
        import saved_fixtures

        tree = saved_fixtures.FIXTURES / 'finished-page'
        (ident,) = [path.name for path in (tree / 'articles').iterdir()]
        for path in sorted(tree.rglob('*')):
            if path.is_file():
                relative = path.relative_to(tree)
                if relative.parts[0] == 'articles':
                    relative = Path(*relative.parts[1:])
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        support.git(self.found.repo, 'add', '-A')
        support.git(self.found.repo, 'commit', '-qm', 'A finished blog of the earlier flow')
        support.git(self.found.repo, 'push', '-q', 'origin', 'HEAD:main')
        management.dispatch(
            self.root,
            'team-take',
            {
                'id': ident,
                'expected': blog_runner.survey(self.root, ident)['expected'],
                'confirmed': True,
            },
        )
        management.dispatch(self.root, 'desk-open', {'id': ident})
        self.assertTrue(blog_runner.engine(self.root).describe(ident)['on_desk'])
        self.assertTrue(blog_runner.survey(self.root, ident)['complete'])
        # Not marked as published on the desk: its complete run lets it be published.
        self.publish(ident)
        self.assertIn('blog-studio/blogs/' + ident + '/1', self.tags())

    def test_a_blog_moved_to_the_desk_is_judged_as_desk_work(self):
        import desk_chat
        import saved_fixtures

        tree = saved_fixtures.FIXTURES / 'draft-gate'
        (ident,) = [path.name for path in (tree / 'articles').iterdir()]
        for path in sorted(tree.rglob('*')):
            if path.is_file():
                relative = path.relative_to(tree)
                if relative.parts[0] == 'articles':
                    relative = Path(*relative.parts[1:])
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        support.git(self.found.repo, 'add', '-A')
        support.git(self.found.repo, 'commit', '-qm', 'A saved blog of the earlier flow')
        support.git(self.found.repo, 'push', '-q', 'origin', 'HEAD:main')
        # Taken, as a saved blog is taken in a team repository to open it on the desk.
        management.dispatch(
            self.root,
            'team-take',
            {
                'id': ident,
                'expected': blog_runner.survey(self.root, ident)['expected'],
                'confirmed': True,
            },
        )
        shown = desk_chat.migration_preview(self.root, ident)
        management.dispatch(self.root, 'desk-migrate', {'id': ident, 'expected': shown['expected']})
        self.assertTrue(blog_runner.engine(self.root).describe(ident)['on_desk'])
        # Its run is kept with stages never approved, but the desk judges it: not by stages.
        self.assertFalse(blog_runner.survey(self.root, ident)['complete'])
        with self.assertRaisesRegex(ValueError, '^' + teams.DESK_UNPUBLISHED + '$'):
            self.publish(ident)
        self.assertEqual(self.tags(), '')
        self.mark_published(ident)
        self.publish(ident)
        self.assertIn('blog-studio/blogs/' + ident + '/1', self.tags())
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

    def test_an_image_pasted_on_the_desk_is_committed_with_the_draft(self):
        from test_desk import IMAGE_ONE

        ident = self.made['id']
        management.dispatch(
            self.root,
            'desk-save',
            {
                'id': ident,
                'seen': 1,
                'part': self.part,
                'text': 'First.\n\n![](' + IMAGE_ONE + ')',
                'session': 'f' * 16,
            },
        )
        self.assertEqual(gitstate.changed(self.found), [])
        files = support.git(self.found.repo, 'show', '--name-only', '--format=', 'HEAD').split()
        self.assertIn('blogs/' + ident + '/desk/images.json', files)
        self.assertIn('blogs/' + ident + '/desk/draft.json', files)
        self.assertNotIn('data:image', (self.folder(ident) / 'desk' / 'draft.json').read_text())
        self.assertIn(IMAGE_ONE, (self.folder(ident) / 'DRAFT.md').read_text())


class DeskTeamHeadingTests(TeamCase):
    def test_an_opening_only_record_is_divided_on_viewing_as_its_own_recorded_change(self):
        import studio
        import json

        from test_desk import EXPORTED, EXPORTED_HEADINGS, opening_only

        made = management.dispatch(
            self.root, 'desk-create', {'operation': 'b' * 32, 'manuscript': EXPORTED}
        )
        ident = made['id']
        self.folder = lambda name: studio.inside(self.root, 'articles', name)
        opening_only(self, made)
        gitstate.commit(self.found, 'A record kept before deeper headings were read', [ident])
        self.assertEqual(gitstate.changed(self.found), [])
        commits = self.local_commits()
        markdown = (self.folder(ident) / 'DRAFT.md').read_bytes()
        shown = management.view(self.root, 'desk', {'id': [ident]})
        self.assertEqual([s['heading'] for s in shown['sections']], EXPORTED_HEADINGS)
        self.assertEqual(shown['revision'], 3)
        self.assertEqual(gitstate.changed(self.found), [])
        self.assertEqual(self.local_commits(), commits + 1)
        self.assertIn('headings', support.git(self.found.repo, 'log', '-1', '--format=%s'))
        self.assertEqual((self.folder(ident) / 'DRAFT.md').read_bytes(), markdown)
        # Viewing again records nothing more, and a form open before on another part saves.
        # The division is recorded here and shared with the next decision.
        management.view(self.root, 'desk', {'id': [ident]})
        self.assertEqual(self.local_commits(), commits + 1)
        remote = self.remote_commits()
        management.dispatch(
            self.root,
            'desk-save',
            {'id': ident, 'seen': 2, 'part': 'title', 'text': 'Renamed', 'session': 'c' * 16},
        )
        self.assertEqual(gitstate.changed(self.found), [])
        management.dispatch(self.root, 'desk-share', {'id': ident})
        self.assertGreater(self.remote_commits(), remote)
        shared = json.loads(
            support.git(self.remote, 'show', 'main:blogs/' + ident + '/desk/draft.json')
        )
        self.assertEqual([s['heading'] for s in shared['sections']], EXPORTED_HEADINGS)


if __name__ == '__main__':
    unittest.main()
