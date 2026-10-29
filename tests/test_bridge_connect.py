"""The studio bridges against the real studios, disposable data roots and a bare repository.

Every path here is under a temporary folder: the home folder, the studios config, each
studio's data root and Marketing Studio's own. The remote is a local bare repository with no
commits, as a host makes one. No studio server is started and no assistant job runs.
"""
import json
import os
import shutil
import subprocess
import sys
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
    def migrated_carry(self, identifier, scenario='valid', installed=False):
        script = '''
import importlib.util, json, shutil, subprocess, sys
from pathlib import Path
from unittest import mock
root, identifier, scenario, installed = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4] == 'True'
product = root / 'studios' / identifier
sys.path[:0] = [str(product), str(product / 'tests')]
import test_desk_migration
case = test_desk_migration.MigrationTests('test_preview_cancel_is_pure_even_older_document_index_and_no_identity' if identifier == 'presentation' else 'test_row_190_preview_cancel_is_pure_and_bounded')
case.setUp()
try:
 from runner import desk_chat, gitstate, team
 import home
 if identifier == 'presentation':
  from runner import decks as records
  top = case.gated()
  originals = ('run.json',)
  side, receipt = 'desk/migration.json', 'desk/migration-origin.json'
 else:
  import workspace as records
  top = case.pending_google()[0] if scenario == 'valid' else case.saved()
  originals = ('.training-studio/session.json', '.training-studio/run.json')
  side, receipt = '.training-studio/desk/run.json', '.training-studio/desk/migration-origin.json'
 baseline = top / ('work/build/drive-preview.json' if identifier == 'presentation' else '.training-studio/google-baseline.json')
 baseline.parent.mkdir(parents=True, exist_ok=True)
 baseline.write_text('{"revision":"synthetic-saved-google-baseline"}\\n')
 # A native local-only migration can retain a dirty original absent from HEAD.
 for name in originals:
  path = top / name
  path.write_bytes(path.read_bytes() + b' ')
 preview = desk_chat.migration_preview(case.engine, top)
 assert not preview['blockers'], preview
 desk_chat.migrate(case.engine, top, preview['expected'])
 original = {name: (top / name).read_bytes() for name in (*originals, receipt)}
 original[baseline.relative_to(top).as_posix()] = baseline.read_bytes()
 effective = records.read_run(top)
 source = case.snapshot(top)
 # Assemble the supported native installed layout without installation/startup.
 if installed:
  spec = importlib.util.spec_from_file_location('native_installer', product / 'installer/install.py')
  installer = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(installer)
  payload = case.base / 'assembled'
  installer.assemble(product / ('skills/' + identifier + '-studio'), installer.BOOTSTRAP, payload)
  # Verify in a fresh child; overlapping product names never cross interpreters.
  program = """import importlib.util, sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import runner
spec=importlib.util.spec_from_file_location('bridge', Path(sys.argv[3]) / 'marketing_studio/bridge.py')
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
assert bridge.runner_records(sys.argv[4], Path(sys.argv[2])).read_run(Path(sys.argv[2]))['execution'] == 'conversation'
"""
  result = subprocess.run([sys.executable, '-c', program, str(payload), str(top), str(root), identifier], capture_output=True, text=True)
  assert result.returncode == 0, result.stderr
 spec = importlib.util.spec_from_file_location('bridge', root / 'marketing_studio/bridge.py')
 bridge = importlib.util.module_from_spec(spec)
 spec.loader.exec_module(bridge)
 if scenario == 'pending':
  pending = top / 'work/desk/migration-transaction.json'
  pending.parent.mkdir(parents=True, exist_ok=True)
  pending.write_text('{}')
 elif scenario == 'partial':
  (top / receipt).unlink()
 elif scenario == 'unknown':
  value = json.loads((top / side).read_bytes())
  value['schema'] = 999
  (top / side).write_text(json.dumps(value))
 elif scenario == 'capability':
  if identifier == 'presentation': records.migration = None
  else: records.read_run = None
 remote = case.base / 'carry-remote.git'
 subprocess.run(['git', 'init', '--quiet', '--bare', str(remote)], check=True)
 subprocess.run(['git', '-C', str(remote), 'symbolic-ref', 'HEAD', 'refs/heads/main'], check=True)
 shared = {'schema':1, 'team':{'repository':str(remote),'branch':'main'}, 'share':'asked'}
 copies = []
 copy_in = team.copy_in
 def copying(*args):
  copies.append(args[1])
  if scenario not in ('valid', 'corrupt-copy'): raise AssertionError('Invalid migrated source reached copy')
  result = copy_in(*args)
  if scenario == 'corrupt-copy': (args[1] / receipt).unlink()
  return result
 with mock.patch.object(team, 'copy_in', side_effect=copying):
  if scenario == 'corrupt-copy':
   try: bridge.connect_runner(identifier, shared)
   except ValueError as error: assert 'was not switched' in str(error), error
   else: raise AssertionError('Damaged destination was accepted')
  else:
   done = bridge.connect_runner(identifier, shared)
 if scenario == 'corrupt-copy':
  assert len(copies) == 1 and not copies[0].exists(), copies
  assert gitstate.current().root == top.parent
  assert case.snapshot(top) == source
 elif scenario != 'valid':
  assert not copies, copies
  assert done['carried'][bridge.NOUNS[identifier]] == 0, done
  assert len(done['left']) == 1, done
  assert not (Path(done['to']['root']) / top.name).exists(), done
 else:
  assert done['carried'][bridge.NOUNS[identifier]] == 1 and not done['left'], done
  destination = Path(done['to']['root']) / top.name
  changed = records.read_run(destination)
  assert changed['driver']['computer'] == team.computer(), changed
  assert changed['driver']['name'] == gitstate.identity(destination.parent.parent), changed
  assert {k:v for k,v in changed.items() if k != 'driver'} == {k:v for k,v in effective.items() if k != 'driver'}
  for name, data in original.items(): assert (destination / name).read_bytes() == data, name
  assert case.snapshot(top) == source, 'Connect changed its original source'
  peer = case.base / 'carry-peer'
  subprocess.run(['git', 'clone', '--quiet', str(remote), str(peer)], check=True)
  copied = peer / gitstate.current().folder / top.name
  assert records.read_run(copied) == changed
  for name, data in original.items():
   if not name.startswith('work/'): assert (copied / name).read_bytes() == data, name
 print(json.dumps({'ok':True, 'scenario':scenario, 'product':identifier, 'installed':installed}))
finally:
 case.doCleanups()
'''
        done = subprocess.run([sys.executable, '-c', script, str(ROOT), identifier, scenario, str(installed)],
                              cwd=ROOT, capture_output=True, text=True, timeout=90)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(json.loads(done.stdout.splitlines()[-1])['ok'])

    def test_migrated_local_dirty_decks_connect_with_effective_owner_and_peer_proof(self):
        for identifier in ('presentation', 'training'):
            with self.subTest(identifier=identifier):
                self.migrated_carry(identifier, installed=True)

    def test_invalid_migrated_decks_are_refused_before_copy(self):
        for identifier in ('presentation', 'training'):
            for scenario in ('pending', 'partial', 'unknown', 'capability'):
                with self.subTest(identifier=identifier, scenario=scenario):
                    self.migrated_carry(identifier, scenario)

    def test_damaged_migrated_destination_rolls_connect_back_before_commit(self):
        for identifier in ('presentation', 'training'):
            with self.subTest(identifier=identifier):
                self.migrated_carry(identifier, 'corrupt-copy')

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
        self.assertEqual(set(prepared), set(STUDIOS) | {'infographic'})
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
        self.assertEqual({identifier: report['connect']['carry'] for identifier, report in prepared.items() if identifier in STUDIOS},
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

    def seed_training(self, name):
        folder = self.base / 'Studios/training-workspace/trainings' / name / '.training-studio'
        folder.mkdir(parents=True)
        (folder / 'run.json').write_text(json.dumps({'schema': 3, 'driver': None, 'steps': {}}))
        (folder.parent / 'README.md').write_text(f'# {name}\n')

    def test_an_interrupted_carry_switches_nothing_and_the_next_connect_finishes_it(self):
        self.launcher.prepare(self.preferences, self.settings(self.local), only='training')
        self.seed_training('alpha')
        self.seed_training('beta')
        old = workspaces.remembered('training')
        self.settings(self.team)
        # The second copy fails: as if the disk filled while carrying beta over.
        script = '''
import importlib.util, json, sys
from pathlib import Path
root, shared = Path(sys.argv[1]), json.loads(sys.argv[2])
spec = importlib.util.spec_from_file_location('bridge', root / 'marketing_studio/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
sys.path.insert(0, str(root / 'studios/training'))
from runner import team
copies, original = [], team.copy_in
def failing(top, target):
    copies.append(top.name)
    if len(copies) == 2:
        raise OSError('no space left while copying ' + top.name)
    return original(top, target)
team.copy_in = failing
try:
    bridge.connect_runner('training', shared)
    print(json.dumps({'ok': True}))
except Exception as failure:
    print(json.dumps({'error': str(failure), 'copies': copies}))
'''
        done = subprocess.run([sys.executable, '-c', script, str(ROOT), json.dumps(self.team)],
                              capture_output=True, text=True, cwd=ROOT)
        said = json.loads(done.stdout.splitlines()[-1])
        self.assertEqual(said['copies'], ['alpha', 'beta'], done.stderr)
        self.assertIn('Training Studio was not switched', said['error'])
        self.assertIn('no space left', said['error'])
        self.assertIn(old['root'], said['error'])
        self.assertEqual(workspaces.remembered('training'), old, 'the record is as it was')
        self.assertFalse((self.base / 'training-data/marketing-studio-connect.json').exists())
        clone = self.base / 'training-data/workspaces/team/trainings'
        self.assertFalse((clone / 'alpha').exists(), 'the copy that was made is gone again')
        listed = subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'main'], cwd=self.remote,
                                capture_output=True, text=True)   # the remote may still have no branch
        self.assertFalse(set(listed.stdout.split()) & {'trainings/alpha/README.md', 'trainings/beta/README.md'})
        # Connecting again carries both.
        done = self.launcher.connect('training', self.preferences, self.team)
        self.assertEqual((done['carried'], done['left']), ({'trainings': 2}, []))
        self.assertEqual(self.remote_tree() & {'trainings/alpha/README.md', 'trainings/beta/README.md'},
                         {'trainings/alpha/README.md', 'trainings/beta/README.md'})
        # A switch that was made but whose carry was cut short is finished by the next Connect.
        self.seed_training('gamma')
        (self.base / 'training-data/marketing-studio-connect.json').write_text(json.dumps({'from': old['root']}))
        done = self.launcher.connect('training', self.preferences, self.team)
        self.assertTrue(done['already'])
        self.assertEqual(done['carried'], {'trainings': 1})
        self.assertEqual(sorted(item['id'] for item in done['left']), ['alpha', 'beta'])
        self.assertIn('trainings/gamma/README.md', self.remote_tree())
        self.assertFalse((self.base / 'training-data/marketing-studio-connect.json').exists())

    def test_a_blank_team_branch_is_left_blank_and_every_studio_still_matches(self):
        blank = {**self.local, 'team': {'repository': str(self.remote), 'branch': None}}
        self.launcher.prepare(self.preferences, self.settings(self.local), only='blog')
        self.seed_local_work()
        self.settings(blank)
        done = self.launcher.connect('blog', self.preferences, blank)
        self.assertEqual(done['carried']['blogs'], 1)
        written = json.loads(shared.path().read_text())
        self.assertIsNone(written['team'].get('branch'))
        self.assertNotIn('share', written)
        self.assertEqual(workspaces.connection('blog', blank)['state'], 'connected')
        self.launcher.prepare(self.preferences, blank, only='training')
        self.assertEqual(workspaces.connection('training', blank)['state'], 'connected')
        self.assertIsNone(json.loads(shared.path().read_text())['team'].get('branch'))

    def test_a_plain_blog_folder_connects_to_local_git(self):
        writing = self.base / 'writing'
        (writing / 'articles/old-post').mkdir(parents=True)
        (writing / 'articles/old-post/session.json').write_text(json.dumps({'title': 'Old post'}))
        (writing / 'articles/old-post/DRAFT.md').write_text('Draft.\n')
        data = self.base / 'blog-data'
        data.mkdir()
        (data / 'page.json').write_text(json.dumps({'workspace': str(writing)}))
        self.settings(self.local)
        self.assertEqual(workspaces.connection('blog', self.local)['summary'], 'Not using local Git')
        prepared = self.launcher.prepare(self.preferences, self.local, only='blog')['blog']
        self.assertEqual(prepared['connect']['carry']['blogs'], 1)
        self.assertIsNone(prepared['connect']['from']['branch'])
        done = self.launcher.connect('blog', self.preferences, self.local)
        self.assertEqual((done['carried'], done['already'] if 'already' in done else False), ({'blogs': 1}, False))
        root = self.base / 'Studios/blog-workspace/blogs'
        self.assertTrue((root / 'old-post/DRAFT.md').is_file())
        self.assertTrue((writing / 'articles/old-post/DRAFT.md').is_file())
        self.assertEqual(workspaces.connection('blog', self.local)['state'], 'local')
        self.assertEqual(json.loads((data / 'page.json').read_text())['workspace'], str(root))

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
