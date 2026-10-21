import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from marketing_studio import workspaces
from studio_core import workspace_setup

TEAM = {'team': {'repository': 'https://example.com/team/hub.git', 'branch': 'main'}, 'share': 'asked'}
LOCAL = {'local': {'root': '/work'}}


class RecordTests(unittest.TestCase):
    """Each studio's workspace is read from its own records, never guessed from a folder."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = mock.patch.dict(os.environ, {
            'BLOG_STUDIO_DATA': str(self.root / 'blog-data'),
            'TRAINING_STUDIO_DATA': str(self.root / 'training-data'),
            'PRESENTATION_STUDIO_DATA': str(self.root / 'presentation-data')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def folder(self, identifier, name, repository, branch='main', tool=None):
        """A studio's folder in a repository, with the hub.json its runner writes."""
        slug = {'blog': 'blog-studio', 'training': 'training-studio', 'presentation': 'presentation-studio'}[identifier]
        repo = self.root / name
        folder = repo / {'blog': 'blogs', 'training': 'trainings', 'presentation': 'presentations'}[identifier]
        folder.mkdir(parents=True)
        (folder / 'hub.json').write_text(json.dumps({'tool': tool or slug, 'schema': 1, 'name': name,
                                                     'repository': repository, 'branch': branch,
                                                     'folder': folder.name}))
        return repo, folder

    def remember(self, identifier, repo, folder, **more):
        data = workspaces.data_root(identifier)
        data.mkdir(parents=True, exist_ok=True)
        (data / 'workspace.json').write_text(json.dumps(
            {'schema': 1, 'name': 'team', 'repo': str(repo), 'folder': folder.name, **more}))

    def test_no_record_is_no_workspace(self):
        for identifier in ('blog', 'training', 'presentation'):
            self.assertIsNone(workspaces.remembered(identifier))
            self.assertEqual(workspaces.connection(identifier, TEAM)['state'], 'none')

    def test_runner_record_names_its_repository_from_the_marker(self):
        repo, folder = self.folder('training', 'hub', 'https://example.com/team/hub.git')
        self.remember('training', repo, folder, branch='main', address='https://example.com/team/hub.git')
        found = workspaces.remembered('training')
        self.assertEqual(found, {'root': str(folder), 'repository': 'https://example.com/team/hub.git',
                                 'branch': 'main'})
        self.assertEqual(workspaces.connection('training', TEAM)['state'], 'connected')
        self.assertFalse(workspaces.connection('training', TEAM)['connect'])

    def test_local_folder_is_local_git_until_the_settings_name_a_repository(self):
        repo, folder = self.folder('presentation', 'presentation-workspace', None)
        self.remember('presentation', repo, folder, branch='main', address=None)
        local = workspaces.connection('presentation', LOCAL)
        self.assertEqual((local['state'], local['connect'], local['summary']),
                         ('local', False, 'Local Git on this computer'))
        team = workspaces.connection('presentation', TEAM)
        self.assertEqual((team['state'], team['connect'], team['summary']),
                         ('disconnected', True, 'Not connected to the shared repository'))
        self.assertIn(str(folder), team['detail'])
        self.assertEqual(team['to']['repository'], 'https://example.com/team/hub.git')

    def test_another_repository_or_branch_is_disconnected(self):
        repo, folder = self.folder('training', 'other', 'https://example.com/other.git')
        self.remember('training', repo, folder)
        self.assertEqual(workspaces.connection('training', TEAM)['state'], 'disconnected')
        repo, folder = self.folder('training', 'hub', 'https://example.com/team/hub', branch='work')
        self.remember('training', repo, folder)
        self.assertEqual(workspaces.connection('training', TEAM)['state'], 'disconnected')
        # A blank team branch in the settings takes whatever branch the folder names.
        blank = {'team': {'repository': 'https://example.com/team/hub.git', 'branch': None}}
        self.assertEqual(workspaces.connection('training', blank)['state'], 'connected')

    def test_a_repository_workspace_while_settings_say_local_can_connect_to_local_git(self):
        repo, folder = self.folder('blog', 'hub', 'https://example.com/team/hub.git')
        self.remember('blog', repo, folder)
        found = workspaces.connection('blog', LOCAL)
        self.assertEqual((found['state'], found['connect'], found['summary']),
                         ('disconnected', True, 'Not using local Git'))
        self.assertEqual(found['to']['root'], '/work/blog-workspace')

    def test_blog_page_record_is_a_plain_writing_folder(self):
        data = workspaces.data_root('blog')
        data.mkdir(parents=True)
        writing = self.root / 'writing'
        writing.mkdir()
        (data / 'page.json').write_text(json.dumps({'workspace': str(writing)}))
        self.assertEqual(workspaces.remembered('blog'), {'root': str(writing), 'repository': None, 'branch': None})
        self.assertEqual(workspaces.connection('blog', TEAM)['state'], 'disconnected')
        (data / 'page.json').write_text(json.dumps({'workspace': str(self.root / 'gone')}))
        self.assertIsNone(workspaces.remembered('blog'))

    def test_a_marker_of_another_tool_or_a_gone_folder_is_not_a_workspace(self):
        repo, folder = self.folder('training', 'hub', 'https://example.com/team/hub.git', tool='presentation-studio')
        self.remember('training', repo, folder)
        self.assertIsNone(workspaces.remembered('training'))
        repo, folder = self.folder('presentation', 'hub2', 'https://example.com/team/hub.git')
        self.remember('presentation', repo, folder)
        (folder / 'hub.json').unlink()
        self.assertIsNone(workspaces.remembered('presentation'))
        (workspaces.data_root('blog')).mkdir(parents=True)
        (workspaces.data_root('blog') / 'workspace.json').write_text('not json')
        self.assertIsNone(workspaces.remembered('blog'))


class TargetTests(unittest.TestCase):
    def test_target_and_matching_follow_the_shared_storage(self):
        self.assertEqual(workspace_setup.target(TEAM, 'blog'),
                         {'repository': 'https://example.com/team/hub.git', 'branch': 'main', 'share': 'asked'})
        self.assertEqual(workspace_setup.target(LOCAL, 'training'),
                         {'root': '/work/training-workspace', 'branch': 'main'})
        self.assertTrue(workspace_setup.matches('https://example.com/team/hub', 'main', TEAM, 'blog'))
        self.assertFalse(workspace_setup.matches('https://example.com/team/hub.git', 'work', TEAM, 'blog'))
        self.assertFalse(workspace_setup.matches(None, 'main', TEAM, 'blog'))
        self.assertTrue(workspace_setup.matches(None, 'main', LOCAL, 'blog'))
        self.assertFalse(workspace_setup.matches('https://example.com/team/hub.git', 'main', LOCAL, 'blog'))

    def test_prepare_sets_a_missing_workspace_up_and_never_moves_one(self):
        gitstate = mock.Mock()
        gitstate.current.return_value = None
        joined = gitstate.join.return_value
        joined.root, joined.address, joined.branch = Path('/clones/hub/trainings'), 'https://example.com/team/hub.git', 'main'
        found = workspace_setup.prepare(gitstate, TEAM, 'training')
        self.assertEqual(found, {'prepared': True, 'workspace': {
            'root': '/clones/hub/trainings', 'repository': 'https://example.com/team/hub.git', 'branch': 'main'}})
        gitstate.join.assert_called_once_with('https://example.com/team/hub.git', branch='main', share='asked')
        local = mock.Mock(root=Path('/work/training-workspace/trainings'), address=None, branch='main')
        gitstate = mock.Mock()
        gitstate.current.return_value = local
        found = workspace_setup.prepare(gitstate, TEAM, 'training', lambda space: {'trainings': 2})
        gitstate.join.assert_not_called()
        gitstate.local.assert_not_called()
        self.assertEqual(found['connect'], {
            'from': {'root': '/work/training-workspace/trainings', 'repository': None, 'branch': 'main'},
            'to': {'repository': 'https://example.com/team/hub.git', 'root': None, 'branch': 'main'},
            'carry': {'trainings': 2}})
        self.assertNotIn('connect', workspace_setup.prepare(gitstate, LOCAL, 'training'))


if __name__ == '__main__':
    unittest.main()
