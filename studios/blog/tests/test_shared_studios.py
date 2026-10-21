"""Synthetic shared-root repositories, driver races, offline queues and shared defaults."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import studio
import studios_config
import blog_runner
import team_workspace as teams
from studio_sync import gitstate, support


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = self.base / 'studios.json'
        self.patch = patch.dict(
            os.environ,
            {'STUDIOS_CONFIG': str(self.config), 'BLOG_STUDIO_DATA': str(self.base / 'data')},
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_completed_shared_setup_keeps_empty_defaults_over_legacy_private_choices(self):
        root = self.base / 'writing'
        studio.initialize(root)
        studio.write_json(
            root / '.blog-run-settings.json',
            {
                'schema': 1,
                'defaults': {**blog_runner.DEFAULTS, 'engine': 'claude', 'model': 'legacy-model'},
            },
        )
        studio.write_json(self.base / 'data/brand.json', {'runtime': '/old/private-brand'})
        values = {
            'schema': 1,
            'setup': {'version': 1},
            'assistant': {'agent': 'codex'},
            'local': {'root': str(self.base / 'work')},
            'output': 'pptx',
        }
        self.config.write_text(json.dumps(values))
        before = self.config.read_bytes()
        found = blog_runner.settings(root)
        self.assertEqual(found['defaults']['engine'], 'codex')
        self.assertTrue(found['configured'])
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(studio.read_json(self.base / 'data/brand.json'), {})
        self.assertNotIn('model', studio.read_json(root / '.blog-run-settings.json')['defaults'])

    def test_shared_changes_and_invalid_file_use_builtins(self):
        self.assertEqual(studios_config.read(), ({}, None))
        studio.initialize(self.base / 'writing')
        root = self.base / 'writing'
        self.config.write_text(
            '{"schema":1,"person":{"name":"Fictional Author"},"assistant":{"agent":"claude","model":"unused"}}'
        )
        defaults = blog_runner.settings(root)
        self.assertEqual(defaults['defaults']['engine'], 'claude')
        self.assertEqual(defaults['defaults']['author'], 'Fictional Author')
        local = {**defaults['defaults'], 'engine': 'codex'}
        blog_runner.settings(root, local)
        self.assertEqual(studios_config.read()[0]['assistant']['agent'], 'codex')
        saved = studio.read_json(root / '.blog-run-settings.json')['defaults']
        self.assertNotIn('engine', saved)
        self.assertNotIn('author', saved)
        self.config.write_text('{invalid')
        self.assertEqual(blog_runner.settings(root)['defaults']['engine'], 'codex')
        self.assertTrue(blog_runner.settings(root)['shared_problem'])
        self.assertEqual(self.config.read_text(), '{invalid')

    def test_settings_changes_only_leaves_and_preserves_unknown_bytes(self):
        raw = '{\n "schema": 1, "person": {"name": "Old", "unknown" : [1,  2]},\n "assistant": {"agent":"codex", "model" : "preserve"}, "future" : { "n": 1e3 }\n}\n'
        self.config.write_text(raw)
        studio.initialize(self.base / 'writing')
        old = blog_runner.settings(self.base / 'writing')['defaults']
        blog_runner.settings(self.base / 'writing', {**old, 'author': 'New'})
        self.assertEqual(self.config.read_text(), raw.replace('"Old"', '"New"'))
        studios_config.update(
            {'team': {'repository': 'git@example.test:team/studios.git', 'branch': 'main'}}
        )
        self.assertIn('"future" : { "n": 1e3 }', self.config.read_text())
        self.assertEqual(studios_config.read()[0]['team']['branch'], 'main')

    def test_new_skill_runs_use_defaults_and_existing_runs_keep_their_choices(self):
        root = self.base / 'writing'
        studio.initialize(root)
        self.config.write_text(
            '{"schema":1,"assistant":{"agent":"claude"},"person":{"name":"First Author"}}'
        )
        args = studio.parser().parse_args(
            [
                '--root',
                str(root),
                'run',
                'create',
                '--title',
                'Synthetic defaults',
                '--audience',
                'Authors',
                '--goal',
                'Explain synthetic defaults',
                '--research',
                'none',
                '--stop',
                'outline',
            ]
        )
        first = blog_runner.command(root, args)
        self.assertEqual(first['engine'], 'claude')
        self.assertEqual(studio.item(root, 'articles', first['id'])[1]['author'], 'First Author')
        self.config.write_text(
            '{"schema":1,"assistant":{"agent":"codex"},"person":{"name":"Second Author"}}'
        )
        self.assertEqual(blog_runner.survey(root, first['id'])['engine'], 'claude')
        self.assertEqual(studio.item(root, 'articles', first['id'])[1]['author'], 'First Author')

    def test_credentials_and_invalid_updates_preserve_file(self):
        self.config.write_text('{"schema":1,"future":"kept"}')
        before = self.config.read_bytes()
        for address in (
            'https://token@example.test/repo.git',
            'https://user:secret@example.test/repo',
            'ext::run',
        ):
            with self.assertRaises(ValueError):
                studios_config.update({'team': {'repository': address}})
            with self.assertRaises(ValueError):
                studios_config.update({'brand': {'repository': address}})
        self.assertEqual(self.config.read_bytes(), before)
        self.config.write_text('[]')
        with self.assertRaises(ValueError):
            studios_config.update({'person': {'name': 'New'}})
        self.assertEqual(self.config.read_text(), '[]')

    def test_migration_moves_missing_values_and_removes_local_copies(self):
        root = self.base / 'writing'
        studio.initialize(root)
        local = dict(
            blog_runner.DEFAULTS,
            engine='codex',
            author='Local Author',
            tone='A local writing preference',
            model='legacy-model',
            effort='high',
            output='google',
        )
        studio.write_json(root / '.blog-run-settings.json', {'schema': 1, 'defaults': local})
        data = self.base / 'data'
        studio.write_json(
            data / 'brand.json',
            {
                'repository': 'https://example.invalid/brand.git',
                'release': 'v1.4.0',
                'runtime': '/synthetic/installed-brand',
                'unrelated': [1, 2],
            },
        )
        studio.write_json(
            data / 'workspace.json',
            {
                'schema': 1,
                'name': 'Synthetic',
                'repo': '/synthetic/clone',
                'folder': 'blogs',
                'address': 'git@example.invalid:team/studios.git',
                'branch': 'main',
                'share': 'decision',
            },
        )
        studio.write_json(root / '.team-sync.json', {'share': 'asked', 'report': {'shared': False}})
        raw = '{"schema":1,"assistant":{"agent":"claude"},"person":{"name":"Shared Author"},"future" : { "n": 1e3 }}\n'
        self.config.write_text(raw)
        shown = blog_runner.settings(root)
        self.assertEqual(shown['defaults']['engine'], 'claude')
        self.assertEqual(shown['defaults']['author'], 'Shared Author')
        self.assertIn('Existing shared values were kept', shown['migration_notice'])
        shared = studios_config.read()[0]
        self.assertEqual(shared['assistant']['model'], 'legacy-model')
        self.assertEqual(shared['brand']['release'], 'v1.4.0')
        self.assertEqual(shared['team']['branch'], 'main')
        self.assertEqual(shared['share'], 'asked')
        self.assertEqual(shared['output'], 'google')
        self.assertIn('"future" : { "n": 1e3 }', self.config.read_text())
        private = studio.read_json(root / '.blog-run-settings.json')['defaults']
        self.assertEqual(private['tone'], 'A local writing preference')
        self.assertFalse(set(private) & {'engine', 'author', 'model', 'effort', 'output'})
        brand = studio.read_json(data / 'brand.json')
        self.assertEqual(brand, {'unrelated': [1, 2]})
        self.assertEqual(studios_config.read()[0]['brand']['skill'], '/synthetic/installed-brand')
        self.assertFalse(
            set(studio.read_json(data / 'workspace.json')) & {'address', 'branch', 'share'}
        )
        self.assertEqual(studio.read_json(root / '.team-sync.json'), {'report': {'shared': False}})
        before, modified = self.config.read_bytes(), self.config.stat().st_mtime_ns
        studios_config.migrate(root)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.config.stat().st_mtime_ns, modified)

    def test_invalid_shared_file_preserves_legacy_values_and_refuses_saving(self):
        root = self.base / 'writing'
        studio.initialize(root)
        local_path = root / '.blog-run-settings.json'
        studio.write_json(
            local_path,
            {
                'schema': 1,
                'defaults': dict(
                    blog_runner.DEFAULTS,
                    engine='claude',
                    author='Legacy Author',
                    tone='Private tone',
                ),
            },
        )
        self.config.write_text('{invalid')
        before = local_path.read_bytes()
        shown = blog_runner.settings(root)
        self.assertEqual(shown['defaults']['engine'], blog_runner.DEFAULTS['engine'])
        self.assertEqual(shown['defaults']['author'], '')
        self.assertEqual(shown['defaults']['tone'], 'Private tone')
        self.assertTrue(shown['shared_problem'])
        with self.assertRaises(ValueError):
            blog_runner.settings(root, {**shown['defaults'], 'author': 'New Author'})
        self.assertEqual(local_path.read_bytes(), before)
        self.assertEqual(self.config.read_text(), '{invalid')

    def test_another_studio_change_is_seen_on_next_read_without_local_shadow(self):
        one, two = self.base / 'one', self.base / 'two'
        studio.initialize(one)
        studio.initialize(two)
        old = blog_runner.settings(one)['defaults']
        blog_runner.settings(
            one, {**old, 'author': 'Author One', 'engine': 'claude', 'tone': 'Local tone'}
        )
        self.assertEqual(blog_runner.settings(two)['defaults']['author'], 'Author One')
        studios_config.update(
            {
                'person': {'name': 'Author Two'},
                'assistant': {'agent': 'codex'},
                'brand': {'repository': 'https://example.invalid/brand.git', 'release': 'v1.4.0'},
            }
        )
        current = blog_runner.settings(one)
        self.assertEqual(current['defaults']['author'], 'Author Two')
        self.assertEqual(current['defaults']['engine'], 'codex')
        self.assertEqual(current['defaults']['tone'], 'Local tone')
        self.assertNotIn('author', studio.read_json(one / '.blog-run-settings.json')['defaults'])

    def test_unreadable_shared_file_never_gets_replaced(self):
        self.config.write_text('{"schema":1,"person":{"name":"Kept"}}')
        original = Path.read_text

        def unreadable(path, *args, **kwargs):
            if path == self.config:
                raise PermissionError('Synthetic unreadable config')
            return original(path, *args, **kwargs)

        before = self.config.read_bytes()
        with patch.object(Path, 'read_text', unreadable):
            self.assertTrue(studios_config.read()[1])
            with self.assertRaises(ValueError):
                studios_config.update({'person': {'name': 'New'}})
        self.assertEqual(self.config.read_bytes(), before)

    def test_a_stale_form_preserves_other_changes_and_refuses_same_member_conflicts(self):
        root = self.base / 'writing'
        studio.initialize(root)
        studios_config.update({'person': {'name': 'Before'}, 'assistant': {'agent': 'codex'}})
        shown = blog_runner.settings(root)
        studios_config.update({'person': {'name': 'Other Studio'}})
        saved = blog_runner.settings(
            root, {**shown['defaults'], 'engine': 'claude', 'shared_before': shown['shared_before']}
        )
        self.assertEqual(saved['defaults']['author'], 'Other Studio')
        self.assertEqual(saved['defaults']['engine'], 'claude')
        before = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed in another studio'):
            blog_runner.settings(
                root,
                {
                    **shown['defaults'],
                    'author': 'Stale Author',
                    'shared_before': shown['shared_before'],
                },
            )
        self.assertEqual(self.config.read_bytes(), before)

    def test_local_save_preserves_an_unsupported_assistant_and_its_model(self):
        root = self.base / 'writing'
        studio.initialize(root)
        raw = '{"schema":1,"assistant":{"agent":"future-agent","model":"future-model","effort":"high"}}'
        self.config.write_text(raw)
        shown = blog_runner.settings(root)
        self.assertEqual(shown['defaults']['engine'], 'codex')
        saved = blog_runner.settings(
            root, {**shown['defaults'], 'tone': 'New tone', 'shared_before': shown['shared_before']}
        )
        self.assertEqual(saved['defaults']['engine'], 'codex')
        self.assertEqual(self.config.read_text(), raw)

    def test_migration_checks_missing_members_inside_the_writer_lock(self):
        root = self.base / 'writing'
        studio.initialize(root)
        studio.write_json(root / '.team-sync.json', {'share': 'asked'})
        original = studios_config.update

        def concurrent(changes, **kwargs):
            original({'share': 'decision', 'person': {'name': 'Another studio'}})
            return original(changes, **kwargs)

        with patch.object(studios_config, 'update', concurrent):
            notice, problem = studios_config.migrate(root)
        self.assertIsNone(problem)
        self.assertIn('share', notice)
        self.assertEqual(studios_config.read()[0]['share'], 'decision')
        self.assertEqual(studios_config.read()[0]['person']['name'], 'Another studio')
        self.assertNotIn('share', studio.read_json(root / '.team-sync.json'))

    def test_missing_clone_still_migrates_share_before_removing_it(self):
        studio.write_json(
            gitstate.settings_path(),
            {
                'schema': 1,
                'name': 'Missing',
                'repo': str(self.base / 'missing'),
                'folder': 'blogs',
                'share': 'asked',
            },
        )
        self.assertIsNone(gitstate.current())
        self.assertEqual(studios_config.read()[0]['share'], 'asked')
        self.assertNotIn('share', studio.read_json(gitstate.settings_path()))


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='blog-studios-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.base / 'one'),
                'STUDIOS_CONFIG': str(self.base / 'none.json'),
                'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_AUTHOR_NAME': 'Synthetic Author',
                'GIT_AUTHOR_EMAIL': 'author@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic Author',
                'GIT_COMMITTER_EMAIL': 'author@example.invalid',
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
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
        (seed / 'trainings/fixture').mkdir(parents=True)
        (seed / 'trainings/hub.json').write_text('{"schema":1,"tool":"training-studio"}')
        (seed / 'trainings/fixture/README.md').write_text('Synthetic training, preserved.\n')
        (seed / 'presentations').mkdir()
        (seed / 'presentations/hub.json').write_text('{"schema":1,"tool":"presentation-studio"}')
        support.git(seed, 'add', '.')
        support.git(seed, 'commit', '-m', 'Synthetic studios fixture')
        support.git(seed, 'push', 'origin', 'main')
        self.root = teams.join(str(self.remote))

    def other(self):
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        return teams.join(str(self.remote))

    def test_shared_team_changes_do_not_silently_move_the_current_clone(self):
        studios_config.update(
            {
                'team': {'repository': 'https://example.invalid/new-team.git', 'branch': 'preview'},
                'share': 'asked',
            }
        )
        found = teams.status(self.root)
        self.assertEqual(found['repository'], 'https://example.invalid/new-team.git')
        self.assertEqual(found['active_repository'], str(self.remote))
        self.assertTrue(found['configuration_notice'])
        self.assertEqual(teams.space(self.root).share, 'asked')
        self.assertEqual(gitstate.current().root, self.root)
        self.assertFalse(
            set(studio.read_json(gitstate.settings_path())) & {'address', 'branch', 'share'}
        )

    def test_stale_join_is_refused_before_git_and_can_retry_after_reload(self):
        before = teams.status(self.root)['shared_before']
        pointer = gitstate.settings_path().read_bytes()
        studios_config.update({'share': 'asked'})
        with patch.object(gitstate, 'join') as join:
            with self.assertRaisesRegex(ValueError, 'changed in another studio'):
                teams.join(str(self.remote), share='decision', shared_before=before)
            join.assert_not_called()
        self.assertEqual(gitstate.settings_path().read_bytes(), pointer)
        reloaded = teams.status(self.root)['shared_before']
        self.assertEqual(
            teams.join(str(self.remote), share='decision', shared_before=reloaded), self.root
        )

    def test_settings_change_during_join_keeps_the_current_workspace(self):
        previous = gitstate.local(self.base / 'other-local', folder='blogs')
        pointer = gitstate.settings_path().read_bytes()
        original = gitstate.sync

        def concurrent(found):
            report = original(found)
            studios_config.update({'share': 'asked'})
            return report

        with patch.object(gitstate, 'sync', concurrent):
            with self.assertRaisesRegex(ValueError, 'changed in another studio'):
                teams.join(str(self.remote), share='decision')
        self.assertEqual(gitstate.settings_path().read_bytes(), pointer)
        self.assertEqual(gitstate.current().root, previous.root)
        self.assertEqual(studios_config.read()[0]['share'], 'asked')
        self.assertTrue(self.root.is_dir())

    def test_page_share_mode_refuses_a_stale_baseline(self):
        import management

        before = teams.status(self.root)['shared_before']
        studios_config.update({'share': 'asked'})
        with self.assertRaisesRegex(ValueError, 'changed in another studio'):
            management.dispatch(
                self.root, 'team-share-mode', {'share': 'decision', 'shared_before': before}
            )
        self.assertEqual(studios_config.read()[0]['share'], 'asked')
        shown = teams.status(self.root)
        saved = management.dispatch(
            self.root,
            'team-share-mode',
            {'share': 'decision', 'shared_before': shown['shared_before']},
        )
        self.assertEqual(saved['share'], 'decision')

    def test_material_is_never_committed_or_pushed(self):
        """In a team workspace the uploaded files stay on this computer, outside Git."""
        import base64
        import management

        result = management.dispatch(
            self.root,
            'upload',
            {
                'operation': '9' * 32,
                'purpose': 'material',
                'analyze': False,
                'files': [
                    {
                        'filename': 'private-notes.md',
                        'content': base64.b64encode(b'Unshared material words.').decode(),
                    }
                ],
            },
        )
        ident = result['files'][0]['source']['id']
        found = blog_runner.create(
            self.root, {'mode': 'from-files', 'sources': [ident], 'goal': 'A team post'}
        )
        repo = teams.space(self.root).repo
        status = support.git(repo, 'status', '--porcelain', '--untracked-files=all')
        self.assertNotIn('material', status)
        self.assertNotIn(ident, status)
        history = support.git(repo, 'log', '--all', '--name-only', '--format=')
        self.assertIn(found['id'] + '/session.json', history)
        self.assertNotIn(ident + '/', history)
        self.assertNotIn('.uploads', history)
        pushed = subprocess.run(
            ['git', '--git-dir', str(self.remote), 'grep', '-l', 'Unshared material words', 'main'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(pushed.stdout, '')
        tracked = subprocess.run(
            ['git', '-C', str(repo), 'grep', '-l', 'Unshared material words', 'HEAD'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(tracked.stdout, '', 'no committed file holds the words')
        self.assertFalse((self.root / '.shared' / 'references' / ident).exists())
        # Another computer that takes this blog is told where its files are.
        other = self.other()
        with self.assertRaisesRegex(ValueError, 'stay on the computer'):
            blog_runner.job(other, found['id'])

    def create(self):
        return blog_runner.create(
            self.root,
            {
                'title': 'Fictional launch',
                'goal': 'Explain a fictional service',
                'audience': 'Authors',
                'research': 'none',
                'stop': 'outline',
            },
        )

    def test_side_by_side_claim_handover_takeover_and_no_foreign_commits(self):
        found = self.create()
        ident = found['id']
        self.assertTrue((self.root / ident / 'session.json').is_file())
        self.assertFalse((self.root / 'articles').exists())
        self.assertTrue(teams.driver(self.root, ident)['here'])
        other = self.other()
        self.assertFalse(teams.driver(other, ident)['here'])
        with self.assertRaisesRegex(ValueError, 'another computer'):
            teams.before(other, ident)
        teams.action(other, ident, 'takeover')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        with self.assertRaisesRegex(ValueError, 'another computer'):
            teams.before(self.root, ident)
        with self.assertRaises(ValueError):
            studio.atomic(self.root / ident / 'DRAFT.md', b'late worker')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        teams.action(other, ident, 'handover')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        teams.action(self.root, ident, 'take')
        self.assertTrue(teams.driver(self.root, ident)['here'])
        changed = support.git(
            self.root.parent, 'diff', '--name-only', 'origin/main~1', 'HEAD'
        ).splitlines()
        self.assertTrue(all(name.startswith('blogs/') for name in changed))
        self.assertEqual(
            (self.root.parent / 'trainings/fixture/README.md').read_text(),
            'Synthetic training, preserved.\n',
        )

    def test_delete_takes_the_blog_out_of_the_shared_branch_and_restore_brings_it_back(self):
        import management

        found = self.create()
        ident = found['id']
        (self.root / ident / '.google-native').mkdir()
        (self.root / ident / '.google-native' / 'kept.json').write_text('{}')
        shown = blog_runner.survey(self.root, ident)
        result = management.dispatch(
            self.root,
            'blog-delete',
            {'id': ident, 'expected': shown['expected'], 'title': found['title']},
        )
        self.assertNotIn('id', result)
        self.assertTrue(result['deleted'])
        self.assertFalse((self.root / ident).exists(), 'ignored leftovers go with the folder')
        self.assertEqual(support.git(self.root.parent, 'status', '--porcelain', '--', 'blogs'), '')
        message = support.git(self.root.parent, 'log', '-1', '--format=%s', 'origin/main')
        self.assertIn('deletes this blog', message)
        self.assertIn('Synthetic Author', message)
        self.assertTrue(teams.refresh(self.root)['shared'])
        record = studio.read_json(self.root / '.blog-runs' / 'deleted' / (ident + '.json'))
        self.assertEqual(record['commit'], support.git(self.root.parent, 'rev-parse', 'HEAD'))
        other = self.other()
        self.assertFalse((other / ident).exists())
        self.assertEqual(blog_runner.catalog(other)['deleted'], [])
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        listed = blog_runner.catalog(self.root)['deleted']
        self.assertEqual([row['title'] for row in listed], ['Fictional launch'])
        restored = management.dispatch(self.root, 'blog-restore', {'id': ident})
        self.assertEqual(restored['id'], ident)
        self.assertTrue((self.root / ident / 'session.json').is_file())
        self.assertTrue((self.root / ident / 'run.json').is_file())
        self.assertEqual(support.git(self.root.parent, 'status', '--porcelain', '--', 'blogs'), '')
        self.assertTrue(teams.refresh(self.root)['shared'])
        self.assertTrue(teams.driver(self.root, ident)['here'])
        self.assertEqual(blog_runner.catalog(self.root)['deleted'], [])
        self.assertFalse(blog_runner.engine(self.root).describe(ident)['enabled'])
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        teams.refresh(other)
        self.assertTrue((other / ident / 'session.json').is_file())

    def test_a_folder_git_has_nothing_to_take_out_is_kept_here_instead(self):
        import management

        found = self.create()
        ident = found['id']
        # A folder git ignores: nothing of it is in the branch, so there is nothing to take out.
        with open(self.root / '.gitignore', 'a') as ignore:
            ignore.write('/' + ident + '/\n')
        support.git(self.root.parent, 'rm', '-r', '-q', '--cached', 'blogs/' + ident)
        support.git(self.root.parent, 'add', 'blogs/.gitignore')
        support.git(self.root.parent, 'commit', '-q', '-m', 'Keep one blog out of the branch')
        self.assertEqual(support.git(self.root.parent, 'ls-files', '--', 'blogs/' + ident), '')
        shown = blog_runner.survey(self.root, ident)
        management.dispatch(
            self.root,
            'blog-delete',
            {'id': ident, 'expected': shown['expected'], 'title': found['title']},
        )
        self.assertFalse((self.root / ident).exists())
        kept = self.root / '.blog-runs' / 'deleted' / ident / 'blog' / 'session.json'
        self.assertTrue(kept.is_file(), 'it is kept here instead')
        record = studio.read_json(self.root / '.blog-runs' / 'deleted' / (ident + '.json'))
        self.assertIsNone(record['commit'], 'no unrelated commit is remembered')
        self.assertNotIn('deletes this blog', support.git(self.root.parent, 'log', '--format=%s'))
        management.dispatch(self.root, 'blog-restore', {'id': ident})
        self.assertTrue((self.root / ident / 'session.json').is_file())
        self.assertEqual(support.git(self.root.parent, 'status', '--porcelain', '--', 'blogs'), '')
        self.assertTrue(teams.refresh(self.root)['shared'])

        import management

        found = self.create()
        ident = found['id']
        other = self.other()
        teams.action(other, ident, 'takeover')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        shown = blog_runner.survey(self.root, ident)
        with self.assertRaisesRegex(ValueError, 'another computer'):
            management.dispatch(
                self.root,
                'blog-delete',
                {'id': ident, 'expected': shown['expected'], 'title': found['title']},
            )
        self.assertTrue((self.root / ident / 'session.json').is_file())

    def test_offline_queue_retry_and_manual_sharing(self):
        found = self.create()
        ident = found['id']
        support.git(self.root.parent, 'remote', 'set-url', 'origin', str(self.base / 'missing.git'))
        current = blog_runner.survey(self.root, ident)
        blog_runner.submit(
            self.root,
            ident,
            'outline',
            {'content': '# Synthetic outline', 'notes': ''},
            current['expected'],
        )
        self.assertGreater(len(gitstate.unshared(teams.space(self.root), ident)), 0)
        report = teams.refresh(self.root, push=True)
        self.assertFalse(report['shared'])
        support.git(self.root.parent, 'remote', 'set-url', 'origin', str(self.remote))
        self.assertTrue(teams.refresh(self.root, push=True)['shared'])
        studios_config.update({'share': 'asked'})
        current = blog_runner.survey(self.root, ident)
        blog_runner.decide(self.root, ident, current['expected'], 'approve')
        self.assertTrue(gitstate.unshared(teams.space(self.root), ident))
        self.assertTrue(teams.refresh(self.root, push=True)['shared'])

    def test_takeover_keeps_unshared_work_and_requires_online_claim(self):
        found = self.create()
        ident = found['id']
        other = self.other()
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        studios_config.update({'share': 'asked'})
        studio.atomic(self.root / ident / 'OUTLINE.md', b'Unshared local writing')
        teams.saved(self.root, ident)
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        teams.action(other, ident, 'takeover')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        runner = blog_runner.engine(self.root)
        runner.current = ident
        runner.keep_local(ident, {'enabled': True, 'status': 'working'})
        teams.refresh(self.root)
        self.assertTrue(runner.stop.is_set())
        self.assertFalse(runner.local(ident)['enabled'])
        runner.current = None
        blog_runner.ENGINES.pop(str(self.root), None)
        kept = gitstate.kept(teams.space(self.root), ident)
        self.assertTrue(kept)
        self.assertIn(
            'Unshared local writing',
            support.git(self.root.parent, 'show', kept[0] + ':blogs/' + ident + '/OUTLINE.md'),
        )
        support.git(self.root.parent, 'remote', 'set-url', 'origin', str(self.base / 'missing.git'))
        with self.assertRaisesRegex(ValueError, 'Check the team repository'):
            teams.action(self.root, ident, 'takeover')


if __name__ == '__main__':
    unittest.main()


class MigrationTests(unittest.TestCase):
    setUp = TeamTests.setUp

    def test_migration_never_copies_material_into_the_shared_references(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        import hub_workspace

        legacy = self.base / 'legacy-material'
        studio.initialize(legacy)
        registry = Registry(self.base / 'legacy-registry', FakeProvider(self.base / 'legacy-rm'))
        hub_id = registry.create('fixture/old-material', 'Old material')['hub']
        adapter = Workspace(legacy, registry.hub(hub_id))
        notes = self.base / 'private-notes.md'
        notes.write_text('Unshared material words.\n')

        def run(*words):
            args = studio.parser().parse_args(['--root', str(legacy), *words])
            return getattr(studio, args.group + '_command')(legacy, args)

        material = run(
            'source', 'add', '--name', 'Notes', '--file', str(notes), '--purpose', 'material'
        )
        article = run('article', 'create', '--title', 'Migrated material', '--mode', 'first-draft')
        run('article', 'attach', '--id', article['id'], '--source', material['id'])
        real_active = hub_workspace.active
        with patch.object(
            hub_workspace,
            'active',
            side_effect=lambda root: (
                adapter if Path(root).resolve() == legacy.resolve() else real_active(root)
            ),
        ):
            teams.migrate(self.root, legacy, [article['id']], sources=[material['id']])
        self.assertTrue((self.root / article['id'] / 'session.json').is_file())
        self.assertFalse((self.root / '.shared' / 'references' / material['id']).exists())
        repo = teams.space(self.root).repo
        history = support.git(repo, 'log', '--all', '--name-only', '--format=')
        self.assertNotIn(material['id'] + '/', history)
        found = subprocess.run(
            ['git', '-C', str(repo), 'grep', '-l', 'Unshared material words', 'HEAD'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(found.stdout, '')

    def test_migration_brings_the_style_a_blog_pins(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        import hub_workspace
        import styles

        legacy = self.base / 'legacy-styles'
        studio.initialize(legacy)
        registry = Registry(self.base / 'legacy-registry', FakeProvider(self.base / 'legacy-rs'))
        hub_id = registry.create('fixture/old-styles', 'Old styles')['hub']
        adapter = Workspace(legacy, registry.hub(hub_id))
        guide = self.base / 'style-guide.md'

        def run(*words):
            args = studio.parser().parse_args(['--root', str(legacy), *words])
            return getattr(studio, args.group + '_command')(legacy, args)

        guide.write_text('Short sections, one observation each.\n')
        learned = run('style', 'create', '--name', 'Field notes', '--guide-file', str(guide))
        guide.write_text('Revised field notes.\n')
        run('style', 'save', '--id', learned['id'], '--guide-file', str(guide))
        article = run('article', 'create', '--title', 'Styled notes', '--mode', 'first-draft')
        directory, record = studio.item(legacy, 'articles', article['id'])
        record['style'] = {'style_id': learned['id'], 'revision': 2}
        studio.persist(directory, 'articles', record)
        here = studio.inside(self.root, 'styles', learned['id'])
        shutil.copytree(legacy / 'styles' / learned['id'], here)
        shutil.rmtree(here / 'revisions' / '2')  # the same style here, without the pinned revision
        teams.saved(self.root, message='Keep a style here')
        real_active = hub_workspace.active
        with patch.object(
            hub_workspace,
            'active',
            side_effect=lambda root: (
                adapter if Path(root).resolve() == legacy.resolve() else real_active(root)
            ),
        ):
            with self.assertRaisesRegex(ValueError, 'overwrite local work: the style'):
                teams.migrate(self.root, legacy, [article['id']])
            self.assertFalse((self.root / article['id']).exists())
            shutil.rmtree(here)
            teams.saved(self.root, message='Remove the style here')
            teams.migrate(self.root, legacy, [article['id']])
        self.assertEqual(here, self.root / '.shared' / 'styles' / learned['id'])
        self.assertEqual(
            styles.pinned(self.root, {'style_id': learned['id'], 'revision': 2})['guide'],
            'Revised field notes.\n',
        )
        # A starter the legacy workspace never copied needs nothing: it reads as revision 1.
        self.assertIsNone(teams._style_plan(self.root, legacy, 'how-to', {1}))
        with self.assertRaisesRegex(ValueError, 'missing'):
            teams._style_plan(self.root, legacy, 'how-to', {2})
        tracked = support.git(teams.space(self.root).repo, 'ls-files')
        self.assertIn('.shared/styles/' + learned['id'] + '/revisions/2/STYLE.md', tracked)
        # The same style here is kept; a revision the legacy copy lacks is named.
        self.assertIsNone(teams._style_plan(self.root, legacy, learned['id'], {2}))
        with self.assertRaisesRegex(
            ValueError, 'style revision that is missing: ' + learned['id'] + ' revision 9'
        ):
            teams._style_plan(self.root, legacy, learned['id'], {2, 9})
        # The same guide under another name is not the same style.
        saved = here / 'revisions' / '2' / 'record.json'
        studio.write_json(saved, {**studio.read_json(saved), 'name': 'Other notes'})
        with self.assertRaisesRegex(ValueError, 'overwrite local work: the style'):
            teams._style_plan(self.root, legacy, learned['id'], {2})

    # Reuse the synthetic repository fixture, with a legacy fake provider kept entirely local.
    def test_selected_migration_is_byte_preserving_and_old_hub_is_unchanged(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        import hub_workspace

        legacy = self.base / 'legacy-writing'
        studio.initialize(legacy)
        provider = FakeProvider(self.base / 'legacy-remotes')
        registry = Registry(self.base / 'legacy-registry', provider)
        hub_id = registry.create('fixture/old-blogs', 'Old blogs')['hub']
        adapter = Workspace(legacy, registry.hub(hub_id))
        source = self.base / 'synthetic.md'
        source.write_text('Synthetic source text.\n')
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'source',
                'add',
                '--name',
                'Synthetic notes',
                '--file',
                str(source),
                '--purpose',
                'reference',
            ]
        )
        reference = studio.source_command(legacy, args)
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'article',
                'create',
                '--title',
                'Migrated fixture',
                '--mode',
                'first-draft',
            ]
        )
        article = studio.article_command(legacy, args)
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'article',
                'attach',
                '--id',
                article['id'],
                '--source',
                reference['id'],
            ]
        )
        studio.article_command(legacy, args)
        source.write_text('# Preserved draft\nSynthetic writing.\n')
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'article',
                'save',
                '--id',
                article['id'],
                '--kind',
                'draft',
                '--file',
                str(source),
            ]
        )
        studio.article_command(legacy, args)
        adapter.publish_selected({'articles': [article['id']]})
        old_files = {
            str(p.relative_to(legacy)): p.read_bytes() for p in legacy.rglob('*') if p.is_file()
        }
        old_head = support.git(adapter.hub.repository, 'rev-parse', 'HEAD')
        real_active = hub_workspace.active
        with patch.object(
            hub_workspace,
            'active',
            side_effect=lambda root: (
                adapter if Path(root).resolve() == legacy.resolve() else real_active(root)
            ),
        ):
            result = teams.migrate(self.root, legacy, [article['id']])
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                teams.migrate(self.root, legacy, [article['id']])
        self.assertTrue(result['legacy_unchanged'])
        self.assertEqual((self.root / article['id'] / 'DRAFT.md').read_bytes(), source.read_bytes())
        # Original session and reference files are copied without rewriting their identities.
        self.assertEqual(
            (self.root / article['id'] / 'session.json').read_bytes(),
            (legacy / 'articles' / article['id'] / 'session.json').read_bytes(),
        )
        self.assertEqual(
            studio.item(self.root, 'sources', reference['id'])[0]
            .joinpath('content.md')
            .read_bytes(),
            (legacy / 'sources' / reference['id'] / 'content.md').read_bytes(),
        )
        self.assertEqual(
            {str(p.relative_to(legacy)): p.read_bytes() for p in legacy.rglob('*') if p.is_file()},
            old_files,
        )
        self.assertEqual(support.git(adapter.hub.repository, 'rev-parse', 'HEAD'), old_head)
        self.assertTrue((self.root / result['archive']).is_dir())


class TeamPageTests(unittest.TestCase):
    setUp = TeamTests.setUp
    create = TeamTests.create

    def test_page_joins_and_switches_workspace_with_driver_controls(self):
        import http.client
        import threading
        import management
        from urllib.parse import urlsplit

        local = self.base / 'local-page'
        studio.initialize(local)
        httpd, url = management.server(local)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        token = urlsplit(url).fragment
        try:
            connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
            connection.request(
                'POST',
                '/api/team-join',
                json.dumps(
                    {
                        'repository': str(self.remote),
                        'branch': 'main',
                        'share': 'asked',
                    }
                ),
                {'X-Blog-Studio-Token': token, 'Content-Type': 'application/json'},
            )
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 200, result)
            self.assertEqual(result['share'], 'asked')
            connection.close()
            connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
            connection.request('GET', '/api/run-settings', headers={'X-Blog-Studio-Token': token})
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(result['workspace'], str(self.root))
            connection.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            blog_runner.engine(self.root).close()
            from hub_store import release_lock

            if getattr(httpd, 'team_runner_lock', None) is not None:
                release_lock(httpd.team_runner_lock)

    def test_fetch_does_not_hold_the_workspace_files_lock(self):
        import threading
        import time

        entered, release = threading.Event(), threading.Event()
        original = support.run
        failures = []

        def run(repo, *args, **kwargs):
            if args[:1] == ('fetch',):
                entered.set()
                release.wait(5)
            return original(repo, *args, **kwargs)

        def refresh():
            try:
                teams.refresh(self.root)
            except Exception as exc:
                failures.append(str(exc))

        with patch.object(support, 'run', side_effect=run):
            thread = threading.Thread(target=refresh)
            thread.start()
            try:
                self.assertTrue(entered.wait(3))
                started = time.monotonic()
                with studio.locked(self.root):
                    self.assertTrue((self.root / 'hub.json').is_file())
                self.assertLess(time.monotonic() - started, 1)
            finally:
                release.set()
                thread.join(timeout=10)
        self.assertFalse(failures)

    def test_google_linked_documents_follow_the_same_driver(self):
        import google_drive

        found = self.create()
        ident = found['id']
        folder, record = studio.item(self.root, 'articles', ident)
        record['google'] = {
            'baselines': {'draft': {'document': {'document_id': 'SyntheticDocument'}}}
        }
        studio.persist(folder, 'articles', record)
        teams.saved(self.root, ident)
        self.assertIn('SyntheticDocument', google_drive.linked_documents(self.root))
        google_drive.require_linked(self.root, 'SyntheticDocument')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        other = teams.join(str(self.remote))
        with self.assertRaisesRegex(ValueError, 'another computer'):
            google_drive.require_linked(other, 'SyntheticDocument')

    def test_external_edits_are_preserved_and_publication_requires_approval(self):
        found = self.create()
        ident = found['id']
        with self.assertRaisesRegex(ValueError, 'Approve every'):
            teams.action(self.root, ident, 'publish')
        draft = self.root / ident / 'OUTLINE.md'
        draft.write_text('Uncommitted synthetic writing.\n')
        with self.assertRaisesRegex(ValueError, 'no local work was overwritten'):
            teams.refresh(self.root, push=True)
        self.assertEqual(draft.read_text(), 'Uncommitted synthetic writing.\n')
