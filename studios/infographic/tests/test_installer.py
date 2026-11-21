"""Native install/rollback boundaries in disposable homes, with no provisioning."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import mock

from helpers import Isolated, NATIVE
from runner.workspace import file_lock
from studio_core.packaging import files


class InstallerTests(Isolated):
    def invoke(self, action, *, source=NATIVE, success=True):
        done = subprocess.run([sys.executable, str(source / 'installer/install.py'), action,
                               '--home', str(self.home), '--target', 'codex', '--yes', '--json'],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0 if success else 2, done.stdout + done.stderr)
        return json.loads(done.stdout if success else done.stderr)

    def test_install_repeat_uninstall_preserve_settings_and_unselected_skills(self):
        unrelated = self.home / '.claude/skills/infographic-studio'; unrelated.mkdir(parents=True)
        (unrelated / 'keep').write_text('Unrelated synthetic skill')
        first = self.invoke('install')
        current = self.home / '.local/share/infographic-studio/current'
        metadata = (current.parent / 'installation.json').read_bytes()
        self.assertEqual(self.invoke('install')['version'], first['version'])
        self.assertEqual((current.parent / 'installation.json').read_bytes(), metadata,
                         'Repeating an identical install must not grow recursive rollback metadata.')
        self.assertFalse(any(p.is_symlink() for p in current.resolve().rglob('*')))
        sentinel = current.parent / 'workspace.json'; sentinel.write_text('{"synthetic":"keep"}')
        self.invoke('uninstall')
        self.assertFalse(current.exists())
        self.assertEqual(sentinel.read_text(), '{"synthetic":"keep"}')
        self.assertEqual((unrelated / 'keep').read_text(), 'Unrelated synthetic skill')

    def test_active_lease_and_unrelated_selected_skill_are_refused(self):
        data = self.home / '.local/share/infographic-studio'
        with file_lock(data / '.studio-running.lock'):
            self.invoke('install', success=False)
        selected = self.home / '.agents/skills/infographic-studio'; selected.mkdir(parents=True)
        (selected / 'keep').write_text('Unrelated')
        self.invoke('install', success=False)
        self.assertEqual((selected / 'keep').read_text(), 'Unrelated')

    GONE = ('The earlier version is no longer on this computer: an update keeps only the newest. '
            'Install the release you want instead. Nothing was changed.')

    def later(self):
        """A copy of this studio standing in for a later release."""
        source = self.temp / 'new-source'
        for original in files(NATIVE):
            target = source / original.relative_to(NATIVE); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        (source / 'VERSION').write_text('0.1.1\n')
        return source

    def keep_from_removal(self, folder):
        """Make a folder one that cannot be removed, and put that right when the test ends."""
        folders = [folder, *(path for path in folder.rglob('*') if path.is_dir())]
        for path in folders: path.chmod(0o555)
        self.addCleanup(lambda: [path.chmod(0o755) for path in folders if path.is_dir()])

    def test_an_update_keeps_one_version_and_everything_goes_through_current(self):
        first = self.invoke('install')
        data = self.home / '.local/share/infographic-studio'
        written = [data / 'studio', data / 'infographic', self.home / 'Applications/Open Infographic Studio.command']
        before = {path: path.read_bytes() for path in written}
        # What an interrupted install and someone's own link can leave beside the versions.
        outside = self.temp / 'kept elsewhere'; outside.mkdir()
        (outside / 'mine.txt').write_text('Not the installer\'s.')
        (data / 'versions/linked').symlink_to(outside, target_is_directory=True)
        stale = data / 'versions/.install-0123abcd/native'; stale.mkdir(parents=True)
        (stale / 'SKILL.md').write_text('Half staged.')
        second = self.invoke('install', source=self.later())
        self.assertNotEqual(second['version'], first['version'])
        self.assertEqual([p.name for p in (data / 'versions').iterdir()], [second['version']])
        self.assertEqual(sorted(second['removed']), sorted(str(data / 'versions' / name) for name in
                                                           (first['version'], 'linked', '.install-0123abcd')))
        self.assertEqual(second['retained'], [])
        self.assertEqual((outside / 'mine.txt').read_text(), "Not the installer's.", 'A link is unlinked, never followed.')
        self.assertEqual((second['runtime'], second['id'], second['versionDirectory']),
                         (str(data / 'current'), second['version'], str(data / 'versions' / second['version'])))
        # Nothing written down names a version folder, so the update rewrote none of it.
        self.assertEqual(os.readlink(self.home / '.agents/skills/infographic-studio'), str(data / 'current'))
        self.assertEqual((self.home / '.agents/skills/infographic-studio/VERSION').read_text(), '0.1.1\n')
        for path in written:
            self.assertEqual(path.read_bytes(), before[path], path.name)
            self.assertNotIn('versions/', path.read_text())
        state = json.loads((data / 'installation.json').read_text())
        self.assertEqual(state['version'], second['version'])
        # Only the rollback records name a folder: the pointer they would put back.
        self.assertNotIn('versions/', json.dumps({k: v for k, v in state.items() if k not in ('previous', 'original')}))
        done = subprocess.run(['/bin/sh', str(data / 'infographic'), '--help'], capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_rollback_after_an_update_refuses_and_changes_nothing(self):
        self.invoke('install')
        self.invoke('install', source=self.later())
        data = self.home / '.local/share/infographic-studio'
        pointer, record = os.readlink(data / 'current'), (data / 'installation.json').read_bytes()
        self.assertEqual(self.invoke('rollback', success=False), {'error': self.GONE})
        self.assertEqual(os.readlink(data / 'current'), pointer)
        self.assertEqual((data / 'installation.json').read_bytes(), record)
        self.assertTrue((data / 'current/runner/studio.py').is_file())

    def test_a_version_that_cannot_be_removed_is_reported_and_can_be_rolled_back_to(self):
        first = self.invoke('install')
        current = self.home / '.local/share/infographic-studio/current'
        before = os.readlink(current)
        self.keep_from_removal(current.resolve())
        second = self.invoke('install', source=self.later())
        self.assertEqual(second['removed'], [])
        self.assertEqual([kept['path'] for kept in second['retained']],
                         [str(current.parent / 'versions' / first['version'])])
        self.assertTrue(second['retained'][0]['reason'])
        self.assertNotEqual(os.readlink(current), before)
        self.invoke('rollback')
        self.assertEqual(os.readlink(current), before)
        self.assertTrue((current / 'runner/studio.py').is_file())

    def test_a_failed_install_restores_the_old_pointer_and_keeps_the_old_version(self):
        first = self.invoke('install')
        data = self.home / '.local/share/infographic-studio'
        pointer, record = os.readlink(data / 'current'), (data / 'installation.json').read_bytes()
        launcher = (data / 'studio').read_bytes()
        spec = importlib.util.spec_from_file_location('infographic_installer', NATIVE / 'installer/install.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        write = installer._atomic

        def fail(path, data_, **options):
            if path.name == 'installation.json':
                raise OSError('Disposable late failure')
            return write(path, data_, **options)

        with mock.patch.object(installer, 'ROOT', self.later()), mock.patch.object(installer, '_atomic', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'late failure'):
                installer.main(['install', '--home', str(self.home), '--target', 'codex', '--yes', '--json'])
        self.assertEqual(os.readlink(data / 'current'), pointer)
        self.assertEqual((data / 'installation.json').read_bytes(), record)
        self.assertEqual((data / 'studio').read_bytes(), launcher)
        self.assertIn(first['version'], [p.name for p in (data / 'versions').iterdir()], 'Nothing is removed by a failed install.')
        self.assertEqual((self.home / '.agents/skills/infographic-studio').resolve(), data / 'versions' / first['version'])
        done = subprocess.run(['/bin/sh', str(data / 'infographic'), '--help'], capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_private_python_inside_an_installed_version_is_named_through_current(self):
        suite = self.home / '.local/share/marketing-studio'
        private = suite / 'versions/4.0.0-abcdef012345/runtime/python/bin/python3'
        private.parent.mkdir(parents=True); private.write_text('')
        (suite / 'current').symlink_to(suite / 'versions/4.0.0-abcdef012345')
        spec = importlib.util.spec_from_file_location('infographic_installer', NATIVE / 'installer/install.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        # The interpreter may say where it is resolved past the link; the launcher must not.
        with mock.patch.object(installer.sys, 'executable', str(private)):
            installer.main(['install', '--home', str(self.home), '--target', 'codex', '--yes', '--json'])
        data = self.home / '.local/share/infographic-studio'
        for name in ('studio', 'infographic'):
            text = (data / name).read_text()
            self.assertIn('exec ' + str(suite / 'current/runtime/python/bin/python3') + ' ', text)
            self.assertNotIn('versions/', text)

    def test_the_marketing_studio_installer_removes_older_versions_itself(self):
        first = self.invoke('install')
        done = subprocess.run([sys.executable, str(self.later() / 'installer/install.py'), 'install', '--home', str(self.home),
                               '--target', 'codex', '--yes', '--json', '--defer-cleanup'], capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        second = json.loads(done.stdout)
        self.assertEqual((second['removed'], second['retained']), ([], []))
        self.assertEqual(sorted(p.name for p in (self.home / '.local/share/infographic-studio/versions').iterdir()),
                         sorted([first['version'], second['version']]))
