"""Native install/rollback boundaries in disposable homes, with no provisioning."""
import json
import os
from pathlib import Path
import subprocess
import sys

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
        self.assertEqual(self.invoke('install')['version'], first['version'])
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

    def test_new_version_rollback_keeps_old_immutable_runtime(self):
        self.invoke('install')
        current = self.home / '.local/share/infographic-studio/current'
        before = os.readlink(current)
        source = self.temp / 'new-source'
        for original in files(NATIVE):
            target = source / original.relative_to(NATIVE); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        (source / 'VERSION').write_text('0.1.1\n')
        self.invoke('install', source=source)
        self.assertNotEqual(os.readlink(current), before)
        self.invoke('rollback')
        self.assertEqual(os.readlink(current), before)
        self.assertTrue((current / 'runner/studio.py').is_file())
