"""The studio bridges against the real studios, disposable data roots and a bare repository.

Every path here is under a temporary folder: the home folder, the studios config, each
studio's data root and Marketing Studio's own. The remote is a local bare repository with no
commits, as a host makes one. No studio server is started and no assistant job runs.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from marketing_studio import catalog, shared, workspaces
from marketing_studio.launcher import Launcher

ROOT = Path(__file__).resolve().parents[1]
STUDIOS = ('blog', 'training', 'presentation')


def git(folder, *arguments):
    done = subprocess.run(['git', *arguments], cwd=folder, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(done.stderr)
    return done.stdout


@unittest.skipUnless(shutil.which('git'), 'git is needed to join a repository.')
class BridgeConnectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='marketing-connect-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        (self.base / 'home').mkdir()
        (self.base / 'gitconfig').write_text(
            '[user]\n\tname = Synthetic Author\n\temail = author@example.invalid\n'
            '[init]\n\tdefaultBranch = main\n')
        patcher = mock.patch.dict(os.environ, {
            'HOME': str(self.base / 'home'),
            'STUDIOS_CONFIG': str(self.base / 'studios-config.json'),
            'MARKETING_STUDIO_DATA': str(self.base / 'marketing-data'),
            'BLOG_STUDIO_DATA': str(self.base / 'blog-data'),
            'TRAINING_STUDIO_DATA': str(self.base / 'training-data'),
            'PRESENTATION_STUDIO_DATA': str(self.base / 'presentation-data'),
            'GIT_CONFIG_GLOBAL': str(self.base / 'gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1'})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'MARKETING_STUDIO_HANDOFF'):
            os.environ.pop(name, None)
        # An empty repository of the kind a host makes, with main as its branch.
        self.remote = self.base / 'team.git'
        self.remote.mkdir()
        git(self.remote, 'init', '--quiet', '--bare')
        git(self.remote, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        self.local = {'schema': 1, 'local': {'root': str(self.base / 'Studios')},
                      'assistant': {'agent': 'codex'}, 'output': 'pptx', 'setup': {'version': 1}}
        self.team = {**self.local, 'team': {'repository': str(self.remote), 'branch': 'main'}, 'share': 'asked'}
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.preferences = {'paths': {}}
        for identifier in STUDIOS:
            self.assertEqual(catalog.locate(identifier, {}), (ROOT / 'studios' / identifier).resolve())

    def settings(self, values):
        """What the studios read for themselves is what Marketing Studio hands the bridge."""
        shared.path().parent.mkdir(parents=True, exist_ok=True)
        shared.path().write_text(json.dumps(values, indent=2))
        return values

    def remote_tree(self):
        return set(git(self.remote, 'ls-tree', '-r', '--name-only', 'main').split())

    def seed_local_work(self):
        """One piece of work in each studio's local workspace, as the studios lay it out."""
        studios = self.base / 'Studios'
        training = studios / 'training-workspace/trainings/intro/.training-studio'
        training.mkdir(parents=True)
        (training / 'run.json').write_text(json.dumps({'schema': 3, 'driver': None, 'steps': {}}))
        (training.parent / 'README.md').write_text('# Intro\n')
        deck = studios / 'presentation-workspace/presentations/launch'
        deck.mkdir(parents=True)
        (deck / 'run.json').write_text(json.dumps({'schema': 1, 'id': 'launch', 'title': 'Launch', 'driver': None}))
        blogs = studios / 'blog-workspace/blogs'
        (blogs / 'hello-world').mkdir(parents=True)
        (blogs / 'hello-world/session.json').write_text(json.dumps({'title': 'Hello world'}))
        (blogs / 'hello-world/DRAFT.md').write_text('Draft.\n')
        (blogs / '.shared/references/ref-1').mkdir(parents=True)
        (blogs / '.shared/references/ref-1/record.json').write_text(json.dumps({'purposes': ['reference']}))
        (blogs / '.shared/voices/voice-1').mkdir(parents=True)
        (blogs / '.shared/voices/voice-1/record.json').write_text(json.dumps({'status': 'active'}))
        (blogs / '.uploads/material/upload-1').mkdir(parents=True)
        (blogs / '.uploads/material/upload-1/record.json').write_text(json.dumps({'purposes': ['material']}))

    def test_local_workspaces_connect_to_an_empty_repository_side_by_side_with_their_work(self):
        prepared = self.launcher.prepare(self.preferences, self.settings(self.local))
        self.assertEqual(set(prepared), set(STUDIOS))
        for identifier, report in prepared.items():
            with self.subTest(identifier=identifier):
                self.assertNotIn('connect', report)
                self.assertIsNone(report['workspace']['repository'])
                self.assertEqual(workspaces.connection(identifier, self.local)['state'], 'local')
        self.assertTrue((self.base / 'Studios/training-workspace/trainings/hub.json').is_file())
        self.assertTrue((self.base / 'Studios/blog-workspace/blogs/hub.json').is_file())
        self.seed_local_work()

        # The shared settings now name the repository: nothing moves by itself.
        prepared = self.launcher.prepare(self.preferences, self.settings(self.team))
        self.assertEqual({identifier: report['connect']['carry'] for identifier, report in prepared.items()},
                         {'blog': {'blogs': 1, 'references': 1, 'voices': 1},
                          'training': {'trainings': 1}, 'presentation': {'decks': 1}})
        for identifier in STUDIOS:
            with self.subTest(identifier=identifier):
                self.assertEqual(prepared[identifier]['connect']['to']['repository'], str(self.remote))
                self.assertEqual(workspaces.connection(identifier, self.team)['state'], 'disconnected')
        self.assertFalse(git(self.remote, 'show-ref').strip() if subprocess.run(
            ['git', 'show-ref'], cwd=self.remote, capture_output=True).returncode == 0 else '')

        # The first studio joining makes the branch, with its folder, and pushes it.
        done = self.launcher.connect('training', self.preferences, self.team)
        self.assertEqual((done['carried'], done['left'], done['shared']), ({'trainings': 1}, [], True))
        self.assertEqual(done['from']['root'], str(self.base / 'Studios/training-workspace/trainings'))
        self.assertIn('trainings/intro/.training-studio/run.json', self.remote_tree())
        copied = json.loads((Path(done['to']['root']) / 'intro/.training-studio/run.json').read_text())
        self.assertEqual(copied['steps'], {})
        self.assertEqual(copied['driver']['name'], 'Synthetic Author')
        self.assertTrue((self.base / 'Studios/training-workspace/trainings/intro/README.md').is_file())

        # The others clone that branch and add their own folders beside it.
        done = self.launcher.connect('presentation', self.preferences, self.team)
        self.assertEqual((done['carried'], done['shared']), ({'decks': 1}, True))
        done = self.launcher.connect('blog', self.preferences, self.team)
        self.assertEqual((done['carried'], done['left'], done['shared']),
                         ({'blogs': 1, 'references': 1, 'voices': 1}, [], True))
        tree = self.remote_tree()
        for path in ('trainings/hub.json', 'presentations/hub.json', 'blogs/hub.json',
                     'presentations/launch/run.json', 'blogs/hello-world/DRAFT.md',
                     'blogs/hello-world/run.json', 'blogs/.shared/references/ref-1/record.json',
                     'blogs/.shared/voices/voice-1/record.json'):
            self.assertIn(path, tree)
        self.assertFalse({path for path in tree if 'upload-1' in path or '.uploads' in path})
        claim = json.loads((Path(done['to']['root']) / 'hello-world/run.json').read_text())
        self.assertEqual(claim['driver']['name'], 'Synthetic Author')
        self.assertTrue((self.base / 'Studios/blog-workspace/blogs/hello-world/DRAFT.md').is_file())
        self.assertEqual(json.loads((self.base / 'blog-data/page.json').read_text())['workspace'], done['to']['root'])

        # Now every studio is connected, and connecting again changes nothing.
        prepared = self.launcher.prepare(self.preferences, self.team)
        for identifier in STUDIOS:
            with self.subTest(identifier=identifier):
                self.assertNotIn('connect', prepared[identifier])
                self.assertEqual(prepared[identifier]['workspace']['repository'], str(self.remote))
                self.assertEqual(workspaces.connection(identifier, self.team)['state'], 'connected')
        before = git(self.remote, 'rev-parse', 'main')
        self.assertTrue(self.launcher.connect('blog', self.preferences, self.team)['already'])
        self.assertTrue(self.launcher.connect('training', self.preferences, self.team)['already'])
        self.assertEqual(git(self.remote, 'rev-parse', 'main'), before)

    def test_studios_without_a_workspace_join_the_empty_repository_on_prepare(self):
        self.settings(self.team)
        first = self.launcher.prepare(self.preferences, self.team, only='training')['training']
        self.assertNotIn('connect', first)
        self.assertEqual(first['workspace']['repository'], str(self.remote))
        self.assertEqual(self.remote_tree() & {'trainings/hub.json', 'trainings/README.md'},
                         {'trainings/hub.json', 'trainings/README.md'})
        second = self.launcher.prepare(self.preferences, self.team, only='presentation')['presentation']
        self.assertNotIn('connect', second)
        self.assertIn('presentations/hub.json', self.remote_tree())
        self.assertIn('trainings/hub.json', self.remote_tree())
        third = self.launcher.prepare(self.preferences, self.team, only='blog')['blog']
        self.assertNotIn('connect', third)
        self.assertEqual(self.remote_tree() & {'blogs/hub.json', 'trainings/hub.json', 'presentations/hub.json'},
                         {'blogs/hub.json', 'trainings/hub.json', 'presentations/hub.json'})
        for identifier in STUDIOS:
            self.assertEqual(workspaces.connection(identifier, self.team)['state'], 'connected')
        # Clearing the repository in the settings offers to move each studio to local Git.
        for identifier in STUDIOS:
            self.assertEqual(workspaces.connection(identifier, self.local)['state'], 'disconnected')
        prepared = self.launcher.prepare(self.preferences, self.settings(self.local), only='training')['training']
        self.assertEqual(prepared['connect']['to']['root'], str(self.base / 'Studios/training-workspace'))


if __name__ == '__main__':
    unittest.main()
