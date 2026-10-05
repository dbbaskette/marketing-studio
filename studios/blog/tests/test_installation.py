"""Managed installation behavior in disposable homes; no sign-in or global changes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', REPO / 'installer/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def rehash(source):
    manifest = json.loads((source / 'install-manifest.json').read_text())
    manifest['files'] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in manifest['files']}
    (source / 'install-manifest.json').write_text(json.dumps(manifest))


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / 'home with spaces'
        self.home.mkdir()
        self.root = self.home / '.local/share/blog-studio'
        self.targets = installer.targets(self.home, ('codex', 'claude'))
        self.source = self.home / 'installer source'
        shutil.copytree(REPO / 'bootstrap/blog-studio', self.source, ignore=shutil.ignore_patterns('__pycache__'))

    def install(self, **kwargs):
        return installer.install(self.source, self.root, self.targets, **kwargs)

    def test_both_targets_share_one_verified_runtime_and_repeat_is_idempotent(self):
        result = self.install()
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(self.targets['codex'].resolve(), self.targets['claude'].resolve())
        self.assertTrue((self.targets['codex'] / 'scripts/studio.py').is_file())
        config = json.loads((self.targets['codex'] / 'config.json').read_text())
        self.assertEqual(config['python'], str(Path(sys.executable).resolve()))
        self.assertEqual(self.install()['status'], 'already-installed')
        checked = installer.inspect(self.root, self.targets)
        self.assertEqual(checked['runtime_integrity'], 'verified')
        self.assertNotEqual(checked['live_harness_discovery'], 'verified')

    def test_google_runtime_requires_its_managed_helper(self):
        manifest_path = self.source / 'install-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest['version'], '1.13.1')
        name = 'scripts/google_workflow.py'
        (self.source / name).unlink()
        del manifest['files'][name]
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(installer.InstallError, 'Required runtime files'):
            self.install()
        self.assertFalse((self.root / 'installation.json').exists())

    def test_optional_google_setup_offline_and_dry_run_do_not_start_login(self):
        for flags in (['--offline'], ['--dry-run', '--offline']):
            args = ['install.py', 'install', '--home', str(self.home), '--source', str(self.source),
                    '--target', 'both', '--google-docs', 'gcloud', '--yes', '--json', *flags]
            with patch.object(sys, 'argv', args), patch.object(installer, 'tool_status', return_value={
                    'python_supported': True, 'git': True}), patch.object(installer, 'install', return_value={'status':'installed'}), \
                    patch.object(installer, 'inspect', return_value={'status':'checked'}), \
                    patch.object(installer.subprocess, 'run') as run:
                self.assertEqual(installer.main(), 0)
                run.assert_not_called()

    def test_optional_google_json_setup_never_starts_interactive_login(self):
        args = ['install.py', 'install', '--home', str(self.home), '--source', str(self.source),
                '--target', 'both', '--google-docs', 'gcloud', '--yes', '--json']
        with patch.object(sys, 'argv', args), patch.object(installer, 'ensure_repository_access', return_value={
                'python_supported': True, 'git': True, 'repository_access':'ready'}), \
                patch.object(installer, 'install', return_value={'status':'installed'}), \
                patch.object(installer.subprocess, 'run') as run:
            self.assertEqual(installer.main(), 0)
            run.assert_not_called()

    def test_repair_stages_intact_runtime_without_deleting_damaged_version(self):
        self.install()
        damaged = self.targets['codex'].resolve()
        (damaged / 'scripts/studio.py').write_text('damaged runtime')
        with self.assertRaises(installer.InstallError):
            self.install()
        self.install(repair=True)
        self.assertNotEqual(self.targets['codex'].resolve(), damaged)
        self.assertEqual((damaged / 'scripts/studio.py').read_text(), 'damaged runtime')
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')

    def test_corrupt_runtime_configuration_is_detected_and_repairable(self):
        self.install()
        config = self.targets['codex'] / 'config.json'
        config.write_text('{broken')
        self.assertIn('invalid', installer.inspect(self.root, self.targets)['runtime_integrity'])
        self.install(repair=True)
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')

    def test_record_cannot_point_outside_managed_versions(self):
        self.install()
        state_path = self.root / 'installation.json'
        state = json.loads(state_path.read_text())
        state['version'] = str(self.source)
        state_path.write_text(json.dumps(state))
        with self.assertRaises(installer.InstallError):
            installer.inspect(self.root, self.targets)

    def test_failed_interpreter_smoke_preserves_active_version(self):
        self.install()
        previous = self.targets['codex'].resolve()
        with self.assertRaisesRegex(installer.InstallError, 'Python'):
            self.install(interpreter=str(self.home / 'missing-python'))
        self.assertEqual(self.targets['codex'].resolve(), previous)
        self.assertFalse(any(p.name.startswith('.') for p in (self.root / 'versions').iterdir()))

    def test_individual_harness_targets_can_be_added(self):
        installer.install(self.source, self.root, {'codex': self.targets['codex']})
        self.assertFalse(self.targets['claude'].exists())
        result = installer.install(self.source, self.root, {'claude': self.targets['claude']})
        self.assertEqual(set(result['targets']), {'codex', 'claude'})

    def test_unmanaged_skill_requires_backup_and_is_preserved(self):
        target = self.targets['codex']
        target.mkdir(parents=True)
        (target / 'custom.md').write_text('User-owned instructions.')
        with self.assertRaisesRegex(installer.InstallError, 'backup'):
            self.install()
        self.assertEqual((target / 'custom.md').read_text(), 'User-owned instructions.')
        result = self.install(replace=True)
        self.assertEqual(len(result['backups']), 1)
        backup = Path(result['backups'][0]['backup'])
        self.assertEqual((backup / 'custom.md').read_text(), 'User-owned instructions.')

    def test_failed_activation_restores_both_targets_and_previous_version(self):
        first = self.install()
        self.change_package()
        previous = self.targets['codex'].resolve()
        # A newly selected third location exercises failure after the shared switch.
        extra = self.home / 'extra/skills/blog-studio'
        chosen = {'codex': self.targets['codex'], 'claude': extra}
        def fail(path, target):
            installer.replace_link(path, target)
            if path == extra:
                raise OSError('Disposable activation failure')
        with self.assertRaises(OSError):
            installer.install(self.source, self.root, chosen, activate=fail)
        self.assertEqual(self.targets['codex'].resolve(), previous)
        self.assertEqual(self.targets['claude'].resolve(), previous)
        self.assertFalse(extra.is_symlink())
        self.assertIn(first['version'], (self.root / 'installation.json').read_text())

    def change_package(self):
        path = self.source / 'SKILL.md'
        path.write_text(path.read_text() + '\nA tested guidance metadata update.\n')
        rehash(self.source)

    def test_runtime_update_and_rollback_keep_old_versions(self):
        first = self.install()
        old = self.targets['codex'].resolve()
        self.change_package()
        second = self.install()
        self.assertNotEqual(first['version'], second['version'])
        self.assertTrue(old.exists())
        rolled = installer.rollback(self.root)
        self.assertEqual(rolled['version'], first['version'])
        self.assertEqual(self.targets['codex'].resolve(), old)
        self.assertEqual(self.targets['claude'].resolve(), old)

    def test_uninstall_preserves_work_and_other_target_then_refuses_foreign_link(self):
        self.install()
        article = self.home / 'writing/.blog-studio/articles/one/DRAFT.md'
        article.parent.mkdir(parents=True)
        article.write_text('Private draft.')
        installer.uninstall(self.root, ('codex',))
        self.assertFalse(self.targets['codex'].is_symlink())
        self.assertTrue(self.targets['claude'].exists())
        self.assertEqual(article.read_text(), 'Private draft.')
        self.targets['claude'].unlink()
        self.targets['claude'].symlink_to(article.parent)
        with self.assertRaisesRegex(installer.InstallError, 'preserved'):
            installer.uninstall(self.root, ('claude',))
        self.assertTrue(article.exists())

    def test_changed_package_and_symlink_parent_are_rejected(self):
        self.change_package()
        (self.source / 'SKILL.md').write_text('Corrupt after manifest.')
        with self.assertRaises(installer.InstallError):
            self.install()
        rehash(self.source)
        foreign = self.home / 'foreign'
        foreign.mkdir()
        (self.home / '.agents').symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(installer.InstallError, 'parent is a symlink'):
            self.install()

    def test_check_does_not_create_installation_or_contact_remote_when_offline(self):
        result = subprocess.run([sys.executable, str(REPO / 'installer/install.py'), 'check',
            '--home', str(self.home), '--offline', '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['tools']['repository_access'], 'not-checked')
        self.assertFalse(self.root.exists())

    def test_setup_summary_does_not_claim_discovery_or_advertise_unselected_target(self):
        installer.install(self.source,self.root,{'codex':self.targets['codex']})
        checked=installer.inspect(self.root,{'codex':self.targets['codex']})
        checked['tools']['codex_available']=True
        summary=installer.setup_summary(checked)
        self.assertIn('$blog-studio',summary)
        self.assertNotIn('/blog-studio',summary.replace(str(self.targets['codex']),''))
        self.assertIn('verify discovery',summary)
        (self.targets['codex'].resolve()/'scripts/studio.py').write_text('damaged')
        damaged=installer.setup_summary(installer.inspect(self.root,{'codex':self.targets['codex']}))
        self.assertNotIn('managed files verified',damaged)
        self.assertIn('repair',damaged)

    def test_human_check_reports_missing_prerequisites_without_mutation(self):
        checked=installer.inspect(self.root,{'claude':self.targets['claude']})
        checked['tools'].update(python_supported=False,git=False,repository_access='unavailable',claude_code_available=False)
        summary=installer.setup_summary(checked)
        for expected in ('python.org','git-scm.com','membership','Install/open Claude Code','not installed'):
            self.assertIn(expected,summary)
        self.assertNotIn('$blog-studio',summary)
        self.assertFalse(self.root.exists())

    def test_configuration_collision_and_busy_lock(self):
        with self.assertRaises(installer.InstallError):
            installer.targets(self.home, ('codex', 'claude'), str(self.home / '.agents'))
        self.root.mkdir(parents=True)
        (self.root / '.install.lock').write_text('another installer')
        with self.assertRaisesRegex(installer.InstallError, 'Another installer'):
            self.install()

    def test_corrupt_previous_version_cannot_be_activated_by_rollback(self):
        self.install()
        previous = self.targets['codex'].resolve()
        self.change_package()
        self.install()
        (previous / 'SKILL.md').write_text('Damaged old runtime.')
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.root)
        self.assertNotEqual(self.targets['codex'].resolve(), previous)

    def test_interactive_auth_decline_changes_no_installation(self):
        unavailable = {'repository_access': 'unavailable'}
        with patch.object(installer, 'tool_status', return_value=unavailable), patch('builtins.input', return_value='2'):
            self.assertEqual(installer.ensure_repository_access(True), unavailable)
        self.assertFalse(self.root.exists())

    def test_interactive_auth_rechecks_exact_private_repository(self):
        bad = {'repository_access': 'unavailable'}
        good = {'repository_access': 'ready'}
        with patch.object(installer, 'tool_status', side_effect=[bad, good]), \
                patch('builtins.input', return_value='1'), \
                patch.object(installer.shutil, 'which', return_value='/fixture/gh'), \
                patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(installer.ensure_repository_access(True), good)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][-2:], ['--hostname', 'github.com'])


if __name__ == '__main__':
    unittest.main()
