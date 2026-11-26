"""What Blog Studio's team sharing, joining, replay, locks and brand export do, held fixed.

These were written against Blog Studio's own copies of the team-sync and brand code, before
that code moved onto the shared runner (issue #543), and are kept unchanged after: each test
says what a person or a teammate's computer relies on. Every repository, Git identity,
settings file, data folder and process here is disposable, and nothing reaches a provider.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import studios_config
import team_workspace as teams
from studio_brand import brand, companion, source
from studio_core.process_lock import ProcessRLock, workspace_lock_path
from studio_sync import gitstate, support, team

IDENTITY = {
    'GIT_CONFIG_GLOBAL': '/dev/null',
    'GIT_CONFIG_NOSYSTEM': '1',
    'GIT_AUTHOR_NAME': 'Synthetic Author',
    'GIT_AUTHOR_EMAIL': 'author@example.invalid',
    'GIT_COMMITTER_NAME': 'Synthetic Author',
    'GIT_COMMITTER_EMAIL': 'author@example.invalid',
}


class Disposable(unittest.TestCase):
    """A data folder, a shared settings file and a team repository of the test's own."""

    def setUp(self):
        made = tempfile.TemporaryDirectory(prefix='blog-team-kept-')
        self.addCleanup(made.cleanup)
        self.base = Path(made.name).resolve()
        self.config = self.base / 'config' / 'studios-config.json'
        environment = mock.patch.dict(
            os.environ,
            {
                **IDENTITY,
                'BLOG_STUDIO_DATA': str(self.base / 'data'),
                'STUDIOS_CONFIG': str(self.config),
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.remote = self.repository('team.git')

    def repository(self, name):
        """A bare repository with one synthetic commit on main."""
        remote = self.base / name
        subprocess.run(
            ['git', 'init', '--quiet', '--bare', '--initial-branch=main', str(remote)], check=True
        )
        seed = self.base / f'seed-{name}'
        subprocess.run(
            ['git', 'clone', '--quiet', str(remote), str(seed)], check=True, capture_output=True
        )
        (seed / 'README.md').write_text('A synthetic team repository.\n')
        support.git(seed, 'add', '.')
        support.git(seed, 'commit', '-m', 'Synthetic start')
        support.git(seed, 'push', 'origin', 'main')
        return remote

    def held(self):
        """The bytes of the remembered workspace and the shared settings, None for one
        missing. A workspace's own hub.json is compared where a test has one."""
        files = (gitstate.settings_path(), self.config)
        return [path.read_bytes() if path.is_file() else None for path in files]


class OpeningTests(Disposable):
    """An existing workspace opens with no migration and nothing rewritten on reading."""

    def test_a_joined_workspace_as_written_today_opens_with_nothing_rewritten(self):
        space = gitstate.join(str(self.remote), folder='blogs')
        studios_config.update({'share': 'asked'})
        self.assertEqual(
            json.loads(gitstate.settings_path().read_text()),
            {'schema': 1, 'name': 'team', 'repo': str(space.repo), 'folder': 'blogs'},
        )
        self.assertEqual(
            json.loads((space.root / 'hub.json').read_text()),
            {
                'tool': 'blog-studio',
                'schema': 1,
                'name': 'team',
                'repository': str(self.remote),
                'branch': 'main',
                'folder': 'blogs',
                'minimum_runtime': support.runtime_version(),
            },
        )
        marker = (space.root / 'hub.json').read_bytes()
        before = self.held()
        for _ in range(2):
            found = gitstate.current()
            self.assertEqual(
                found,
                gitstate.Workspace('team', space.repo, 'blogs', 'main', str(self.remote), 'asked'),
            )
            self.assertEqual(teams.space(space.root), found)
        self.assertEqual(self.held(), before)
        self.assertEqual((space.root / 'hub.json').read_bytes(), marker)
        self.assertFalse((self.base / 'data' / 'config-migration.json').exists())
        self.assertEqual(found.blog('alpha'), space.root / 'alpha')

    def test_a_local_workspace_opens_with_no_address_and_no_shared_settings_file(self):
        space = gitstate.local(self.base / 'mine')
        before = self.held()
        self.assertIsNone(before[1])
        found = gitstate.current()
        branch = support.git(space.repo, 'branch', '--show-current')
        self.assertEqual(found, gitstate.Workspace('mine', space.repo, 'blogs', branch, None))
        self.assertIsNone(json.loads((space.root / 'hub.json').read_text())['repository'])
        self.assertEqual(self.held(), before)

    def test_the_older_shape_moves_its_shared_values_once_and_keeps_the_rest(self):
        space = gitstate.join(str(self.remote), folder='blogs')
        older = {
            'schema': 1,
            'name': 'team',
            'repo': str(space.repo),
            'folder': 'blogs',
            'branch': 'main',
            'address': str(self.remote),
            'share': 'asked',
        }
        gitstate.settings_path().write_text(json.dumps(older))
        marker = (space.root / 'hub.json').read_bytes()
        found = gitstate.current()
        self.assertEqual(
            found,
            gitstate.Workspace('team', space.repo, 'blogs', 'main', str(self.remote), 'asked'),
        )
        self.assertEqual(
            json.loads(gitstate.settings_path().read_text()),
            {'schema': 1, 'name': 'team', 'repo': str(space.repo), 'folder': 'blogs'},
        )
        shared = json.loads(self.config.read_text())
        self.assertEqual(shared['share'], 'asked')
        self.assertEqual(shared['team'], {'repository': str(self.remote), 'branch': 'main'})
        self.assertEqual((space.root / 'hub.json').read_bytes(), marker)
        moved = self.held()
        self.assertEqual(gitstate.current(), found)
        self.assertEqual(self.held(), moved)

    def test_a_remembered_workspace_whose_folder_lost_its_marker_is_not_opened(self):
        space = gitstate.join(str(self.remote), folder='blogs')
        (space.root / 'hub.json').unlink()
        before = self.held()
        self.assertIsNone(gitstate.current())
        self.assertEqual(self.held(), before)


class GuardedJoinTests(Disposable):
    """Nothing is remembered, and the shared settings are not written, unless the join got
    through and the guarded save succeeded."""

    def setUp(self):
        super().setUp()
        self.previous = gitstate.local(self.base / 'mine')
        studios_config.update({'share': 'asked'})

    def test_a_join_that_could_not_share_remembers_nothing_and_writes_no_setting(self):
        before = self.held()
        with mock.patch.object(gitstate, 'sync', return_value={'shared': False}):
            with self.assertRaisesRegex(ValueError, 'could not be shared'):
                teams.join(str(self.remote), share='decision')
        self.assertEqual(self.held(), before)
        self.assertEqual(gitstate.current().root, self.previous.root)

    def test_a_join_whose_clone_fails_remembers_nothing_and_writes_no_setting(self):
        before = self.held()
        with self.assertRaisesRegex(ValueError, 'Could not clone'):
            teams.join(str(self.base / 'missing.git'), share='decision')
        self.assertEqual(self.held(), before)
        self.assertEqual(gitstate.current().root, self.previous.root)
        self.assertFalse((gitstate.clones() / 'missing').exists())

    def test_a_join_remembers_only_after_the_guarded_save(self):
        said = []
        update, remember = studios_config.update, gitstate.remember

        def updating(*args, **kwargs):
            said.append(
                ('update', args[0] if args else kwargs.get('changes'), 'expected' in kwargs)
            )
            return update(*args, **kwargs)

        def remembering(found):
            said.append(('remember', str(gitstate.current().root)))
            return remember(found)

        with (
            mock.patch.object(studios_config, 'update', updating),
            mock.patch.object(gitstate, 'remember', remembering),
        ):
            root = teams.join(str(self.remote), share='decision')
        self.assertEqual(
            said,
            [
                ('update', {}, True),
                ('update', {'team': {'repository': str(self.remote)}, 'share': 'decision'}, True),
                ('remember', str(self.previous.root)),
            ],
        )
        self.assertEqual(gitstate.current().root, root)
        self.assertEqual(json.loads(self.config.read_text())['share'], 'decision')

    def test_an_outdated_form_still_refuses_before_git(self):
        before = teams.status(self.previous.root)['shared_before']
        studios_config.update({'share': 'decision'})
        held = self.held()
        with mock.patch.object(gitstate, 'join') as join:
            with self.assertRaisesRegex(ValueError, 'changed in another studio'):
                teams.join(str(self.remote), share='asked', shared_before=before)
            join.assert_not_called()
        self.assertEqual(self.held(), held)


HOLDER = """
import sys, time
from pathlib import Path
repo, kind, ready, release = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
if kind == 'blog':
    from studio_sync import support
    held = support.Held(repo / '.git' / 'blog-studio.lock')
    held.__enter__()
else:
    from studio_core.process_lock import ProcessRLock, workspace_lock_path
    first = ProcessRLock(lambda: workspace_lock_path(repo, Path(sys.argv[5])))
    second = ProcessRLock(lambda: repo / '.git' / 'blog-studio.lock')
    first.__enter__()
    second.__enter__()
ready.touch()
end = time.monotonic() + 20
while not release.exists() and time.monotonic() < end:
    time.sleep(0.01)
"""


class LockTests(Disposable):
    """A sync holds the shared settings lock, then Blog Studio's own lock, then the
    workspace. A Blog Studio process and a deck studio's process syncing the same repository
    exclude each other, and so do two of either. Each holder here is a process of its own."""

    def setUp(self):
        super().setUp()
        self.repo = self.base / 'shared-repository'
        (self.repo / '.git').mkdir(parents=True)
        wait = mock.patch.dict(os.environ, {'BLOG_STUDIO_LOCK_WAIT': '0.2'})
        wait.start()
        self.addCleanup(wait.stop)

    def holding(self, kind):
        """A process that holds the locks a `kind` ('blog' or 'deck') sync holds."""
        ready, release = self.base / f'{kind}-ready', self.base / f'{kind}-release'
        for path in (ready, release):
            path.unlink(missing_ok=True)
        child = subprocess.Popen(
            [
                sys.executable,
                '-c',
                HOLDER,
                str(self.repo),
                kind,
                str(ready),
                str(release),
                str(self.base / 'deck-data'),
            ],
            env={**os.environ, 'PYTHONPATH': str(isolation.SCRIPTS)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        def end():
            release.touch()
            try:
                child.communicate(timeout=10)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()

        self.addCleanup(end)
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(0.01)
        self.assertTrue(ready.exists(), child.poll() is not None and child.communicate())
        return end

    def deck_takes(self):
        """Whether a deck studio's sync could take its locks now (both, or neither)."""
        locks = [
            ProcessRLock(lambda: workspace_lock_path(self.repo, self.base / 'deck-data')),
            ProcessRLock(lambda: self.repo / '.git' / 'blog-studio.lock'),
        ]
        taken = []
        try:
            for lock in locks:
                if not lock.acquire(timeout=0.1):
                    return False
                taken.append(lock)
            return True
        finally:
            for lock in reversed(taken):
                lock.release()

    def deck_takes_either(self):
        """Whether a deck studio could take either of the two files on its own."""
        for path in (
            workspace_lock_path(self.repo, self.base / 'deck-data'),
            self.repo / '.git' / 'blog-studio.lock',
        ):
            lock = ProcessRLock(lambda path=path: path)
            if lock.acquire(timeout=0.1):
                lock.release()
                return True
        return False

    def blog_takes_its_own(self):
        """Whether Blog Studio's own lock class could take its own file alone, without the
        shared settings lock in front of it: the two lock classes meet on that file."""
        import hub_store

        taken = hub_store.acquire_lock(self.repo / '.git' / 'blog-studio.lock', wait=0.1)
        if taken is None:
            return False
        hub_store.release_lock(taken)
        return True

    def blog_takes(self):
        """Whether a Blog Studio sync could take its locks now."""
        try:
            with support.Held(self.repo / '.git' / 'blog-studio.lock'):
                return True
        except support.WorkspaceError:
            return False

    def test_the_two_lock_files_are_the_same_for_both_kinds_of_studio(self):
        self.assertEqual(
            workspace_lock_path(self.repo, self.base / 'deck-data'),
            self.repo / '.git' / 'studios-write.lock',
        )

    def test_a_blog_studio_sync_excludes_a_deck_studio_sync(self):
        end = self.holding('blog')
        self.assertFalse(self.deck_takes_either())
        end()
        self.assertTrue(self.deck_takes())

    def test_a_deck_studio_sync_excludes_a_blog_studio_sync(self):
        end = self.holding('deck')
        self.assertFalse(self.blog_takes())
        self.assertFalse(self.blog_takes_its_own())
        end()
        self.assertTrue(self.blog_takes())
        self.assertTrue(self.blog_takes_its_own())

    def test_two_blog_studio_syncs_exclude_each_other(self):
        end = self.holding('blog')
        self.assertFalse(self.blog_takes())
        end()
        self.assertTrue(self.blog_takes())

    def test_two_deck_studio_syncs_exclude_each_other(self):
        end = self.holding('deck')
        self.assertFalse(self.deck_takes_either())
        end()
        self.assertTrue(self.deck_takes())

    def test_a_blog_studio_sync_takes_the_shared_lock_before_its_own(self):
        order = []
        taken = ProcessRLock.acquire

        def acquire(lock, *args, **kwargs):
            order.append(Path(lock._path()).name)
            return taken(lock, *args, **kwargs)

        import hub_store

        acquired = hub_store.acquire_lock

        def flocked(path, *args, **kwargs):
            order.append(Path(path).name)
            return acquired(path, *args, **kwargs)

        with (
            mock.patch.object(ProcessRLock, 'acquire', acquire),
            mock.patch.object(hub_store, 'acquire_lock', flocked),
        ):
            with support.Held(self.repo / '.git' / 'blog-studio.lock'):
                pass
        self.assertEqual(order, ['studios-write.lock', 'blog-studio.lock'])

    def test_a_blog_studio_sync_holds_its_own_lock_by_default(self):
        space = gitstate.Workspace('team', self.repo, 'blogs', 'main', 'synthetic-address')
        seen = []

        def asked(repo, *args, **kwargs):
            seen.append(self.deck_takes_either())
            return subprocess.CompletedProcess(args, 1, '', 'fatal: synthetic, unreachable')

        with (
            mock.patch.object(gitstate, 'on_branch', return_value='main'),
            mock.patch.object(gitstate, 'tracking', return_value='origin/main'),
            mock.patch.object(gitstate.hub, 'run', asked),
            mock.patch.object(gitstate.hub, 'ahead', return_value=0),
        ):
            report = gitstate.sync(space)
        self.assertFalse(report['reached'])
        self.assertEqual(seen, [True])  # never held while the remote is asked


class TeamTests(Disposable):
    """Drivers, notifications, numbered publication tags and bringing a folder in."""

    def setUp(self):
        super().setUp()
        self.space = gitstate.join(str(self.remote), folder='blogs')
        (self.space.root / 'alpha').mkdir()
        (self.space.root / 'alpha' / 'draft.md').write_text('A synthetic draft.\n')
        gitstate.commit(self.space, 'Synthetic draft', ['alpha'])
        gitstate.sync(self.space)

    def tags(self, repo):
        listed = support.git(repo, 'for-each-ref', '--format=%(refname:short)', 'refs/tags/')
        return sorted(listed.split())

    def test_revisions_are_numbered_tags_under_blog_studio_and_never_moved(self):
        first = team.publish(self.space, 'alpha', 'Alpha', True, 'Synthetic Author')
        self.assertEqual(
            first, {'revision': 1, 'tag': 'blog-studio/blogs/alpha/1', 'shared': True, 'why': None}
        )
        second = team.publish(self.space, 'alpha', 'Alpha again', False, 'Synthetic Author')
        self.assertEqual(second['tag'], 'blog-studio/blogs/alpha/2')
        self.assertEqual(
            self.tags(self.remote), ['blog-studio/blogs/alpha/1', 'blog-studio/blogs/alpha/2']
        )
        said = support.git(
            self.space.repo,
            'for-each-ref',
            '--format=%(contents)',
            'refs/tags/blog-studio/blogs/alpha/2',
        )
        heading, _, about = said.strip().partition('\n\n')
        self.assertEqual(heading, 'Publish Alpha again, revision 2')
        about = json.loads(about)
        self.assertEqual(set(about), {'id', 'title', 'revision', 'ready', 'at', 'by'})
        self.assertEqual(
            (about['id'], about['revision'], about['ready'], about['by']),
            ('alpha', 2, False, 'Synthetic Author'),
        )
        self.assertEqual(team.revisions(self.space, 'alpha'), 2)
        listed = team.published(self.space)
        self.assertEqual(len(listed), 1)
        self.assertEqual(
            {
                key: listed[0][key]
                for key in ('path', 'id', 'title', 'revision', 'by', 'ready', 'current')
            },
            {
                'path': str(self.space.root / 'alpha'),
                'id': 'alpha',
                'title': 'Alpha again',
                'revision': 2,
                'by': 'Synthetic Author',
                'ready': False,
                'current': True,
            },
        )
        (self.space.root / 'alpha' / 'draft.md').write_text('Changed since.\n')
        gitstate.commit(self.space, 'Synthetic change', ['alpha'])
        self.assertFalse(team.published(self.space)[0]['current'])

    def test_a_teammates_copy_takes_the_next_number(self):
        team.publish(self.space, 'alpha', 'Alpha', True, 'Synthetic Author')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'teammate')
        other = gitstate.join(str(self.remote), folder='blogs')
        self.assertEqual(team.publish(other, 'alpha', 'Alpha', True, 'Teammate')['revision'], 2)
        self.assertTrue(team.fetch_tags(self.space))
        self.assertEqual(team.revisions(self.space, 'alpha'), 2)

    def test_tags_in_another_layout_are_not_revisions(self):
        for name in ('blogs/alpha/1', 'blog-studio/blogs/alpha/r1', 'blog-studio/alpha/1'):
            support.git(
                self.space.repo,
                'tag',
                '--annotate',
                '-m',
                'Foreign',
                '-m',
                json.dumps({'id': 'alpha', 'title': 'Foreign'}),
                name,
                'HEAD',
            )
        self.assertEqual(team.published(self.space), [])
        self.assertEqual(team.revisions(self.space, 'alpha'), 0)

    def test_a_workspace_with_no_remote_publishes_here_only(self):
        mine = gitstate.local(self.base / 'mine')
        (mine.root / 'beta').mkdir()
        (mine.root / 'beta' / 'draft.md').write_text('Synthetic.\n')
        gitstate.commit(mine, 'Synthetic', ['beta'])
        self.assertEqual(
            team.publish(mine, 'beta', 'Beta', True, 'Synthetic Author'),
            {
                'revision': 1,
                'tag': 'blog-studio/blogs/beta/1',
                'shared': False,
                'why': 'this workspace has no shared repository',
            },
        )
        self.assertFalse(team.fetch_tags(mine))

    def test_drivers_and_the_sentences_a_person_reads(self):
        here = team.computer()
        self.assertRegex(here, r'^[0-9a-f]{16}$')
        self.assertEqual(
            json.loads((self.base / 'data' / 'computer.json').read_text()),
            {'schema': 1, 'id': here},
        )
        self.assertEqual(team.computer(), here)
        claimed = team.claim(self.space)
        self.assertEqual((claimed['name'], claimed['computer']), ('Synthetic Author', here))
        record = {'driver': claimed}
        self.assertTrue(team.ours(self.space, record))
        self.assertIsNone(team.elsewhere(self.space, record))
        self.assertEqual(team.driver(self.space, record)['here'], True)
        theirs = {
            'driver': {'name': 'Teammate', 'computer': '0' * 16, 'since': '2026-01-02T03:04:05Z'}
        }
        self.assertFalse(team.ours(self.space, theirs))
        self.assertEqual(
            team.elsewhere(self.space, theirs),
            'Teammate has been running this blog from another computer since '
            '2026-01-02 at 03:04 UTC. It can be read here. Take it over to '
            'change it.',
        )
        self.assertEqual(
            team.elsewhere(self.space, {}),
            'Nobody is running this blog. Take it to carry on with it from this computer.',
        )
        mine = gitstate.local(self.base / 'mine')
        self.assertIsNone(team.claim(mine))
        self.assertTrue(team.ours(mine, theirs))
        self.assertIsNone(team.driver(mine, theirs))

    def test_the_notifier_names_blog_studio_and_its_own_variable(self):
        ran = []

        def run(command, **kwargs):
            ran.append(command)
            return subprocess.CompletedProcess(command, 0)

        notifier = team.Notifier(
            run=run,
            environ={'BLOG_STUDIO_NOTIFY': 'synthetic-notify --x'},
            which=lambda name: None,
            system=lambda: 'Linux',
        )
        self.assertEqual(notifier.can(), (True, None))
        self.assertTrue(notifier.send('Alpha'))
        self.assertEqual(
            ran, [['synthetic-notify', '--x', 'Blog Studio', '"Alpha" needs a decision.']]
        )
        silent = team.Notifier(
            run=run,
            environ={'TRAINING_STUDIO_NOTIFY': 'other'},
            which=lambda name: None,
            system=lambda: 'Linux',
        )
        self.assertEqual(silent.can(), (False, team.NO_WAY))

    def test_a_folder_brought_in_is_copied_whole_without_its_own_repository_or_locks(self):
        folder = self.base / 'outside'
        (folder / '.git').mkdir(parents=True)
        (folder / '.blog-studio').mkdir()
        (folder / '.blog-studio' / 'lock').write_text('')
        (folder / 'run.lock').write_text('')
        (folder / 'draft.md').write_text('Synthetic.\n')
        self.assertIsNone(team.unacceptable(folder))
        target = self.space.root / 'gamma'
        team.copy_in(folder, target)
        self.assertEqual(
            sorted(path.relative_to(target).as_posix() for path in target.rglob('*')),
            ['.blog-studio', 'draft.md'],
        )
        self.assertTrue((folder / '.git').is_dir())


class BrandExportTests(unittest.TestCase):
    """The exact command line the brand skill is given for a blog."""

    def setUp(self):
        made = tempfile.TemporaryDirectory(prefix='blog-brand-kept-')
        self.addCleanup(made.cleanup)
        self.base = Path(made.name)
        self.runtime = self.base / 'synthetic-brand'
        (self.runtime / 'scripts').mkdir(parents=True)
        self.script = self.runtime / 'scripts' / 'synthetic-brand.mjs'
        self.script.write_text('// synthetic\n')
        self.ran = []

    def run_command(self, command, cwd=None):
        self.ran.append(command)
        if command[2:3] == ['--version'] or command[2:3] == ['version']:
            return 0, 'Synthetic Brand 1.0.0\n', ''
        if command[2:4] == ['contract', 'export']:
            out = Path(command[command.index('--output') + 1])
            out.mkdir(parents=True, exist_ok=True)
            for name in ('brand-contract.json', 'DESIGN.md', 'VOICE.md'):
                (out / name).write_text('{}' if name.endswith('.json') else 'Synthetic.\n')
            return 0, '{}', ''
        return 0, '{}', ''

    def exported(self, **given):
        self.ran.clear()
        made = brand.Brand(self.runtime, run=self.run_command)
        self.ran.clear()
        folder = self.base / f'export-{len(os.listdir(self.base))}'
        made.export(folder, 'fictional', given.pop('variant', 'light'), **given)
        self.assertEqual(len(self.ran), 1)
        return self.ran[0], folder

    def test_without_a_voice_profile(self):
        command, folder = self.exported()
        self.assertEqual(
            command,
            [
                'node',
                str(self.script),
                'contract',
                'export',
                '--medium',
                'blog',
                '--brand',
                'fictional',
                '--variant',
                'light',
                '--output',
                str(folder),
            ],
        )

    def test_with_a_voice_profile_and_no_variant(self):
        profile = self.base / 'voice-profile.json'
        command, folder = self.exported(variant=None, voice_profile=profile)
        self.assertEqual(
            command,
            [
                'node',
                str(self.script),
                'contract',
                'export',
                '--medium',
                'blog',
                '--brand',
                'fictional',
                '--output',
                str(folder),
                '--voice-profile',
                str(profile),
            ],
        )

    def test_the_brand_skill_is_run_with_the_shared_brands_folder(self):
        from studio_core import brand_skills

        with mock.patch.object(brand.companions, 'run_command', return_value=(0, '[]', '')) as run:
            brand.run_command(['node', 'synthetic'])
        run.assert_called_once_with(
            ['node', 'synthetic'],
            None,
            brand.TIMEOUT,
            'The brand skill',
            brand_skills.environment(),
        )

    def test_the_sentence_when_no_brand_skill_is_found(self):
        with (
            mock.patch.dict(os.environ, {brand.VARIABLE: ''}),
            mock.patch.object(brand, '_installed', return_value=iter(())),
        ):
            os.environ.pop(brand.VARIABLE)
            with self.assertRaises(support.WorkspaceError) as refused:
                brand.Brand(run=self.run_command)
        self.assertEqual(
            str(refused.exception),
            'No brand skill was found on this computer, so a blog cannot use a '
            'brand. Install one, or name its folder in BRAND_SKILL_RUNTIME, then '
            'try again.',
        )


class CompanionAndSourceTests(unittest.TestCase):
    """Running a companion's command, and the brand skill's own repository."""

    def test_a_command_is_run_once_and_its_words_come_back(self):
        code, out, err = companion.run_command(
            [sys.executable, '-c', 'import sys; print("out"); print("err", file=sys.stderr)'],
            None,
            30,
            'A synthetic command',
        )
        self.assertEqual((code, out, err.strip()), (0, 'out\n', 'err'))

    def test_a_command_that_cannot_start_is_refused_in_a_sentence(self):
        with self.assertRaises(support.WorkspaceError) as refused:
            companion.run_command(
                ['/nonexistent/synthetic-command'], None, 30, 'A synthetic command'
            )
        self.assertTrue(
            str(refused.exception).startswith('A synthetic command could not be started (')
        )

    def test_a_missing_companion_is_refused_in_a_sentence(self):
        with mock.patch.dict(os.environ, {'SYNTHETIC_RUNTIME': ''}):
            os.environ.pop('SYNTHETIC_RUNTIME')
            with self.assertRaises(support.WorkspaceError) as refused:
                companion.find_runtime(
                    [],
                    Path('scripts/x.mjs'),
                    'SYNTHETIC_RUNTIME',
                    'synthetic',
                    'nothing can be made',
                )
        self.assertEqual(
            str(refused.exception),
            'The synthetic skill is not installed on this computer, so nothing can '
            'be made. Install it, then try again.',
        )

    def test_an_unreadable_repository_is_refused_as_a_workspace_error(self):
        with tempfile.TemporaryDirectory() as place:
            with mock.patch.dict(os.environ, IDENTITY):
                with self.assertRaises(support.WorkspaceError) as refused:
                    source.head(str(Path(place) / 'missing'), Path(place))
        self.assertTrue(
            str(refused.exception).startswith(
                "The brand skill's repository could not be read. It was not found ("
            )
        )

    def test_a_folder_with_no_installer_names_blog_studio(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(support.WorkspaceError) as refused:
                source.installer(Path(folder), 'node')
        self.assertEqual(
            str(refused.exception),
            'Its main branch has no installer Blog Studio knows how to run: '
            'scripts/install-mac.mjs on a Mac, or scripts/install-skill.mjs. '
            'Nothing was run',
        )

    def test_the_repository_setting_is_blog_studios_own_check(self):
        with self.assertRaises(ValueError) as refused:
            source.check('relative/folder', Path(tempfile.gettempdir()))
        self.assertEqual(
            str(refused.exception),
            'Use an https or ssh repository address, or an absolute folder path.',
        )


if __name__ == '__main__':
    unittest.main()
