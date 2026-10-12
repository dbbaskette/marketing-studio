"""Managed installation of the whole skill in disposable homes; no sign-in, network or global changes."""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / 'skills/blog-studio'
VERSION = (SKILL / 'VERSION').read_text().strip()
spec = importlib.util.spec_from_file_location('installer', REPO / 'installer/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

HOLD_LOCK = (
    "import importlib.util, sys, time, pathlib\n"
    "spec = importlib.util.spec_from_file_location('installer', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
    "with module.installation_lock(pathlib.Path(sys.argv[2])):\n"
    "    print('locked', flush=True); time.sleep(120)\n")


class InstallationCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / 'home with spaces'
        self.home.mkdir()
        self.root = self.home / '.local/share/blog-studio'
        self.targets = installer.targets(self.home, ('codex', 'claude'))
        # A source checkout: the installer computes the manifest from the folder.
        self.source = self.home / 'installer source/skills/blog-studio'
        shutil.copytree(SKILL, self.source, ignore=shutil.ignore_patterns('__pycache__'))

    def install(self, **kwargs):
        return installer.install(self.source, self.root, self.targets, **kwargs)

    def change_package(self):
        path = self.source / 'SKILL.md'
        path.write_text(path.read_text() + '\nA tested guidance update.\n')

    def state(self):
        return json.loads((self.root / 'installation.json').read_text())

    def main(self, *arguments):
        """Run the command line in-process against the disposable home; returns (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        argv = ['install.py', *arguments, '--home', str(self.home), '--source', str(self.source)]
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = installer.main()
        return code, out.getvalue(), err.getvalue()


class InstallationTests(InstallationCase):
    def test_both_targets_share_one_verified_copy_of_the_whole_skill_and_repeat_is_idempotent(self):
        result = self.install()
        self.assertEqual(result['status'], 'installed')
        self.assertTrue(result['version'].startswith(VERSION + '-'))
        self.assertEqual(self.targets['codex'].resolve(), self.targets['claude'].resolve())
        installed = self.targets['codex']
        for name in ('SKILL.md', 'VERSION', 'scripts/studio.py', 'references/entry-flows.md', 'install-manifest.json'):
            self.assertTrue((installed / name).is_file(), name)
        self.assertFalse((installed / 'scripts/sync_guidance.py').exists())
        self.assertEqual(json.loads((installed / 'install-manifest.json').read_text())['version'], VERSION)
        self.assertEqual(self.install()['status'], 'already-installed')
        checked = installer.inspect(self.root, self.targets)
        self.assertEqual(checked['runtime_integrity'], 'verified')
        self.assertEqual(checked['version'], VERSION)
        self.assertEqual(checked['interpreter']['status'], 'ready')
        self.assertNotEqual(checked['live_harness_discovery'], 'verified')

    def test_one_version_file_feeds_installer_and_hub_compatibility(self):
        self.assertRegex(VERSION, r'^[0-9]+\.[0-9]+\.[0-9]+$')
        self.assertEqual(installer.package_manifest(SKILL)['version'], VERSION)
        spec = importlib.util.spec_from_file_location('hub_store_version_probe', SKILL / 'scripts/hub_store.py')
        store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(store)
        self.assertEqual(store.VERSION, VERSION)
        # No hand-kept list of releases: support is proven by each version's own manifest.
        self.assertNotRegex((REPO / 'installer/install.py').read_text(), r"'1\.\d+\.\d+'")

    def test_upgrade_notice_for_earlier_installs_stays_in_the_repository(self):
        tombstone = json.loads((REPO / 'guidance/manifest.json').read_text())
        self.assertEqual(tombstone['schema'], 1)
        self.assertEqual(tombstone['entry'], 'skills/blog-studio/SKILL.md')
        self.assertEqual(tombstone['content_root'], 'skills/blog-studio')
        # Every 1.x helper compares this against its own version and asks for the installer update.
        self.assertGreaterEqual(tuple(int(n) for n in tombstone['minimum_runtime'].split('.')), (2, 0, 0))

    def test_shipped_manifest_is_verified_and_changed_packages_are_rejected(self):
        manifest = installer.package_manifest(self.source)
        (self.source / 'install-manifest.json').write_text(json.dumps(manifest))
        self.assertEqual(self.install()['status'], 'installed')
        (self.source / 'SKILL.md').write_text('Changed after the manifest was written.')
        with self.assertRaisesRegex(installer.InstallError, 'recorded hash'):
            self.install()
        (self.source / 'install-manifest.json').write_text(json.dumps(installer.package_manifest(self.source)))
        (self.source / 'references/unlisted.md').write_text('Not in the manifest.')
        with self.assertRaisesRegex(installer.InstallError, 'inventory'):
            self.install()

    def test_package_without_required_files_is_not_installed(self):
        (self.source / 'scripts/studio.py').unlink()
        with self.assertRaisesRegex(installer.InstallError, 'Required skill files'):
            self.install()
        (self.source / 'VERSION').unlink()
        with self.assertRaisesRegex(installer.InstallError, 'VERSION'):
            self.install()
        self.assertFalse((self.root / 'installation.json').exists())

    def test_finder_metadata_does_not_break_setup_or_later_checks(self):
        (self.source / '.DS_Store').write_bytes(b'\0')
        (self.source / 'references/.DS_Store').write_bytes(b'\0')
        manifest = installer.package_manifest(self.source)
        self.assertFalse(any('.DS_Store' in name for name in manifest['files']))
        (self.source / 'install-manifest.json').write_text(json.dumps(manifest))
        self.install()
        installed = self.targets['claude'].resolve()
        self.assertFalse((installed / 'references/.DS_Store').exists())
        (installed / '.DS_Store').write_bytes(b'\0')
        (installed / 'scripts/.DS_Store').write_bytes(b'\0')
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')
        self.assertEqual(self.install()['status'], 'already-installed')

    def test_installing_over_a_damaged_runtime_stages_a_replacement_and_keeps_the_damaged_copy(self):
        self.install()
        damaged = self.targets['codex'].resolve()
        (damaged / 'scripts/studio.py').write_text('damaged runtime')
        self.assertIn('hash', installer.inspect(self.root, self.targets)['runtime_integrity'])
        # A plain install is enough; the download is intact and is not blamed.
        self.assertEqual(self.install()['status'], 'installed')
        replacement = self.targets['codex'].resolve()
        self.assertNotEqual(replacement, damaged)
        self.assertEqual((damaged / 'scripts/studio.py').read_text(), 'damaged runtime')
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')
        self.assertEqual(self.install()['status'], 'already-installed')
        self.assertEqual(self.targets['codex'].resolve(), replacement)
        self.assertNotIn(str(damaged), self.state()['history'])

    def test_corrupt_runtime_configuration_is_detected_and_rewritten(self):
        self.install()
        config = self.targets['codex'] / 'config.json'
        config.write_text('{broken')
        self.assertIn('invalid', installer.inspect(self.root, self.targets)['runtime_integrity'])
        self.assertEqual(self.install(repair=True)['status'], 'repaired')
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')

    def test_record_cannot_point_outside_managed_versions(self):
        self.install()
        state = self.state()
        state['version'] = str(self.source)
        (self.root / 'installation.json').write_text(json.dumps(state))
        with self.assertRaises(installer.InstallError):
            installer.inspect(self.root, self.targets)

    def test_unusable_requested_interpreter_preserves_active_version(self):
        self.install()
        previous = self.targets['codex'].resolve()
        with self.assertRaisesRegex(installer.InstallError, 'Python'):
            self.install(interpreter=str(self.home / 'missing-python'))
        self.change_package()
        with self.assertRaisesRegex(installer.InstallError, 'Python'):
            self.install(interpreter=str(self.home / 'missing-python'))
        self.assertEqual(self.targets['codex'].resolve(), previous)
        self.assertFalse(any(p.name.startswith('.') for p in (self.root / 'versions').iterdir()))

    def test_interpreter_path_is_stable_and_never_resolved_into_a_versioned_cellar(self):
        prefix = self.home / 'brew'
        cellar = prefix / 'Cellar/python@3.99/3.99.1/bin'
        cellar.mkdir(parents=True)
        (cellar / 'python3.99').write_text('')
        (prefix / 'opt').mkdir()
        (prefix / 'opt/python@3.99').symlink_to('../Cellar/python@3.99/3.99.1', target_is_directory=True)
        (prefix / 'bin').mkdir()
        (prefix / 'bin/python3').symlink_to('../Cellar/python@3.99/3.99.1/bin/python3.99')
        stable = prefix / 'opt/python@3.99/bin/python3.99'
        self.assertEqual(installer.stable_interpreter(cellar / 'python3.99'), stable)
        # A path the user's shell already uses is kept as given, not resolved.
        self.assertEqual(installer.stable_interpreter(prefix / 'bin/python3'), prefix / 'bin/python3')
        self.install()
        recorded = json.loads((self.targets['codex'] / 'config.json').read_text())['python']
        self.assertEqual(recorded, str(installer.stable_interpreter(sys.executable)))

    def test_removed_interpreter_is_reported_by_check_and_replaced_by_the_next_setup(self):
        old = self.home / 'old-python/bin/python3'
        old.parent.mkdir(parents=True)
        old.symlink_to(sys.executable)
        self.install(interpreter=str(old))
        config = self.targets['codex'] / 'config.json'
        self.assertEqual(json.loads(config.read_text())['python'], str(old))
        self.assertEqual(installer.inspect(self.root, self.targets)['interpreter']['status'], 'ready')
        old.unlink()  # for example, a package manager removed that Python
        checked = installer.inspect(self.root, self.targets)
        self.assertEqual(checked['interpreter'], {'path': str(old), 'status': 'missing'})
        summary = installer.setup_summary(checked)
        self.assertIn('repair', summary)
        self.assertNotIn('managed files verified', summary)
        self.assertEqual(self.install()['status'], 'repaired')
        self.assertEqual(json.loads(config.read_text())['python'], str(installer.stable_interpreter(sys.executable)))
        self.assertEqual(installer.inspect(self.root, self.targets)['interpreter']['status'], 'ready')

    def test_individual_harness_targets_can_be_added(self):
        installer.install(self.source, self.root, {'codex': self.targets['codex']})
        self.assertFalse(self.targets['claude'].exists())
        result = installer.install(self.source, self.root, {'claude': self.targets['claude']})
        self.assertEqual(set(result['targets']), {'codex', 'claude'})

    def test_unmanaged_skill_needs_consent_and_its_backup_is_outside_every_skill_folder(self):
        target = self.targets['claude']
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('User-owned instructions.')
        with self.assertRaisesRegex(installer.InstallError, 'backup'):
            self.install()
        self.assertEqual((target / 'SKILL.md').read_text(), 'User-owned instructions.')
        self.assertFalse((self.root / 'installation.json').exists())
        result = self.install(replace=True)
        self.assertEqual(len(result['backups']), 1)
        backup = Path(result['backups'][0]['backup'])
        self.assertEqual((backup / 'SKILL.md').read_text(), 'User-owned instructions.')
        self.assertEqual(backup.parent, self.root / 'backups')
        # A backup beside the skill would be discovered as a second Blog Studio.
        self.assertEqual([p.name for p in target.parent.iterdir()], ['blog-studio'])
        self.assertEqual([p.name for p in self.targets['codex'].parent.iterdir()], ['blog-studio'])

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

    def test_interrupt_after_the_switch_is_undone_and_setup_can_run_again(self):
        first = self.install()
        previous = self.targets['codex'].resolve()
        self.change_package()
        def interrupted(path, target):
            installer.replace_link(path, target)
            raise KeyboardInterrupt()  # also how a termination signal arrives in the command line
        with self.assertRaises(KeyboardInterrupt):
            self.install(activate=interrupted)
        self.assertEqual(self.targets['codex'].resolve(), previous)
        self.assertEqual(Path(self.state()['version']).name, first['version'])
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')
        second = self.install()
        self.assertEqual(second['status'], 'installed')
        self.assertNotEqual(second['version'], first['version'])

    def test_setup_killed_between_switch_and_record_is_completed_by_the_next_run(self):
        first = self.install()
        record = (self.root / 'installation.json').read_bytes()
        self.change_package()
        second = self.install()
        # The process died after `current` moved but before the record was written.
        (self.root / 'installation.json').write_bytes(record)
        self.assertIn('interrupted', installer.inspect(self.root, self.targets)['runtime_integrity'])
        for repair in (True, False):
            (self.root / 'installation.json').write_bytes(record)
            result = self.install(repair=repair)
            self.assertEqual(result['status'], 'installed')
            self.assertIn('recovered', result)
            self.assertEqual(Path(self.state()['version']).name, second['version'])
            self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')
        self.assertEqual(installer.rollback(self.root)['version'], first['version'])
        # The same holds when the very first setup lost its record.
        (self.root / 'installation.json').unlink()
        self.assertEqual(self.install()['status'], 'installed')
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')

    def test_update_and_rollback_keep_old_versions_and_author_work(self):
        first = self.install()
        old = self.targets['codex'].resolve()
        draft = self.home / 'blogs/.blog-studio/articles/example/DRAFT.md'
        other = self.home / '.codex/skills/research/SKILL.md'
        for path in (draft, other):
            path.parent.mkdir(parents=True)
            path.write_text('User-owned content.')
        self.change_package()
        second = self.install()
        self.assertNotEqual(first['version'], second['version'])
        for target in self.targets.values():
            self.assertIn('A tested guidance update.', (target / 'SKILL.md').read_text())
        self.assertNotIn('A tested guidance update.', (old / 'SKILL.md').read_text())
        rolled = installer.rollback(self.root)
        self.assertEqual(rolled['version'], first['version'])
        self.assertEqual(self.targets['codex'].resolve(), old)
        self.assertEqual(self.targets['claude'].resolve(), old)
        for path in (draft, other):
            self.assertEqual(path.read_text(), 'User-owned content.')

    def test_existing_1x_installation_upgrades_in_place_and_can_roll_back(self):
        # The layout written by the 1.x installer: a bootstrap folder, its own manifest and config.
        old = self.root / 'versions/1.12.3-0123456789ab'
        files = {'SKILL.md': 'Bootstrap entry.', 'scripts/studio.py': 'print("1.x")',
                 'scripts/sync_guidance.py': 'VERSION = "1.12.2"', 'references/google/start.md': 'Old reference.'}
        for name, text in files.items():
            (old / name).parent.mkdir(parents=True, exist_ok=True)
            (old / name).write_text(text)
        (old / 'install-manifest.json').write_text(json.dumps({'schema': 1, 'version': '1.12.3',
            'files': {name: installer.file_hash(old / name) for name in files}}))
        gone = '/opt/homebrew/Cellar/python@3.13/3.13.1/Frameworks/Python.framework/Versions/3.13/bin/python3.13'
        (old / 'config.json').write_text(json.dumps({'python': gone, 'runtime_version': '1.12.3',
            'trusted_source': 'https://github.com/dbbaskette/blog-studio.git'}))
        installer.replace_link(self.root / 'current', old)
        for path in self.targets.values():
            path.parent.mkdir(parents=True)
            installer.replace_link(path, self.root / 'current')
        (self.root / 'installation.json').write_text(json.dumps({'schema': 1, 'version': str(old), 'history': [],
            'targets': {k: str(v) for k, v in self.targets.items()}, 'backups': []}))
        self.assertEqual(installer.verify_package(old)['version'], '1.12.3')
        upgraded = self.install()
        self.assertEqual(upgraded['status'], 'installed')
        self.assertTrue(upgraded['version'].startswith(VERSION + '-'))
        self.assertEqual(self.state()['history'], [str(old)])
        self.assertTrue((self.targets['claude'] / 'references/entry-flows.md').is_file())
        self.assertEqual(installer.rollback(self.root)['version'], old.name)
        self.assertEqual(self.targets['codex'].resolve(), old.resolve())
        config = json.loads((old / 'config.json').read_text())
        self.assertTrue(installer.interpreter_works(config['python']))
        self.assertEqual(config['trusted_source'], 'https://github.com/dbbaskette/blog-studio.git')
        self.assertEqual(installer.inspect(self.root, self.targets)['runtime_integrity'], 'verified')

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

    def test_symlinked_discovery_parent_and_shared_folder_are_rejected(self):
        with self.assertRaises(installer.InstallError):
            installer.targets(self.home, ('codex', 'claude'), str(self.home / '.agents'))
        foreign = self.home / 'foreign'
        foreign.mkdir()
        (self.home / '.agents').symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(installer.InstallError, 'parent is a symlink'):
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


class LockTests(InstallationCase):
    def test_running_installer_blocks_a_second_one_and_a_leftover_file_does_not(self):
        self.root.mkdir(parents=True)
        # The file left by an earlier crashed run (or by the 1.x installer) is not a lock.
        (self.root / '.install.lock').write_text('another installer')
        self.assertEqual(self.install()['status'], 'installed')
        held = os.open(self.root / '.install.lock', os.O_RDWR)
        self.addCleanup(os.close, held)
        fcntl.flock(held, fcntl.LOCK_EX)
        with self.assertRaisesRegex(installer.InstallError, 'Another installer'):
            self.install()
        with self.assertRaisesRegex(installer.InstallError, 'Another installer'):
            installer.rollback(self.root)

    def test_terminated_lock_holder_does_not_block_the_next_run(self):
        self.root.mkdir(parents=True)
        holder = subprocess.Popen([sys.executable, '-c', HOLD_LOCK, str(REPO / 'installer/install.py'), str(self.root)],
                                  stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), 'locked')
            with self.assertRaisesRegex(installer.InstallError, 'Another installer'):
                self.install()
            holder.send_signal(signal.SIGTERM)
            holder.wait(timeout=30)
        finally:
            holder.kill()
            holder.wait()
            holder.stdout.close()
        self.assertTrue((self.root / '.install.lock').exists())
        self.assertEqual(self.install()['status'], 'installed')


class CommandLineTests(InstallationCase):
    def test_setup_needs_no_repository_access_git_or_sign_in(self):
        source = (REPO / 'installer/install.py').read_text()
        for removed in ('ls-remote', 'gh auth', 'repository_access', 'TRUSTED_SOURCE'):
            self.assertNotIn(removed, source)
        with patch.object(installer.shutil, 'which', return_value=None), \
                patch.object(installer.subprocess, 'run', wraps=subprocess.run) as run:
            code, out, err = self.main('install', '--target', 'both', '--yes', '--offline', '--json')
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['status'], 'installed')
        for call in run.call_args_list:
            self.assertNotIn(Path(call.args[0][0]).name, ('git', 'gh', 'brew'))

    def test_check_reads_only_and_reports_optional_team_hub_tools(self):
        result = subprocess.run([sys.executable, str(REPO / 'installer/install.py'), 'check',
            '--home', str(self.home), '--offline', '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        checked = json.loads(result.stdout)
        self.assertEqual(checked['installation'], 'absent')
        self.assertIn('Team Hub', checked['tools']['team_hub_note'])
        self.assertFalse(self.root.exists())
        code, out, _ = self.main('check')
        self.assertEqual(code, 0)
        self.assertIn('not installed', out)
        self.assertIn('Team Hub (optional)', out)
        self.assertFalse(self.root.exists())

    def test_update_repair_and_check_default_to_the_harnesses_chosen_at_installation(self):
        code, out, err = self.main('install', '--target', 'codex', '--yes', '--json')
        self.assertEqual(code, 0, err)
        self.change_package()
        for action in ('install', 'repair'):
            code, out, err = self.main(action, '--yes', '--json')
            self.assertEqual(code, 0, err)
            self.assertEqual(set(json.loads(out)['targets']), {'codex'})
        self.assertFalse(self.targets['claude'].exists() or self.targets['claude'].is_symlink())
        code, out, _ = self.main('check', '--json')
        self.assertEqual(set(json.loads(out)['targets']), {'codex'})
        # A guided update offers the other tool once instead of silently adding or hiding it.
        with patch('builtins.input', side_effect=['', '']) as asked:
            code, out, err = self.main('install')
        self.assertEqual(code, 0, err)
        self.assertIn('Add Claude Code too?', asked.call_args_list[0].args[0])
        self.assertFalse(self.targets['claude'].is_symlink())
        with patch('builtins.input', side_effect=['y', '']):
            code, out, err = self.main('install')
        self.assertEqual(code, 0, err)
        self.assertTrue(self.targets['claude'].is_symlink())
        code, out, err = self.main('install', '--target', 'both', '--yes', '--json')
        self.assertEqual(set(json.loads(out)['targets']), {'codex', 'claude'})

    def test_run_without_a_terminal_names_the_noninteractive_command(self):
        result = subprocess.run([sys.executable, str(REPO / 'installer/install.py'), '--home', str(self.home),
            '--source', str(self.source)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('sh installer/install.sh install --target <codex|claude|both> --yes', result.stderr)
        self.assertFalse((self.root / 'installation.json').exists())

    def test_termination_signal_unwinds_setup_instead_of_killing_it_mid_switch(self):
        before = signal.getsignal(signal.SIGTERM)
        with self.assertRaises(installer.Interrupted):
            with installer.interruptible():
                os.kill(os.getpid(), signal.SIGTERM)
                signal.pause()  # the handler raises here; without it the process would die
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)
        self.install()
        active = self.targets['codex'].resolve()
        self.change_package()
        def terminated(args):
            def stop(path, target):
                installer.replace_link(path, target)
                raise installer.Interrupted()
            installer.install(args.source, self.root, self.targets, activate=stop)
        with patch.object(installer, 'run', side_effect=terminated):
            code, _, err = self.main('install', '--yes')
        self.assertEqual(code, 130)
        self.assertIn('previous installation', err)
        self.assertEqual(self.targets['codex'].resolve(), active)

    def test_legacy_codex_copy_is_moved_to_backups_only_with_consent(self):
        legacy = self.home / '.codex/skills/blog-studio'
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text('Manual copy.')
        code, _, err = self.main('install', '--target', 'codex', '--yes')
        self.assertEqual(code, 1)
        self.assertIn('--replace', err)
        self.assertTrue(legacy.is_dir())
        code, out, err = self.main('install', '--target', 'codex', '--yes', '--replace', '--json')
        self.assertEqual(code, 0, err)
        self.assertFalse(legacy.exists())
        moved = json.loads(out)['moved_to_backup']
        self.assertEqual(Path(moved[0]).parent, self.root / 'backups')
        self.assertEqual((Path(moved[0]) / 'SKILL.md').read_text(), 'Manual copy.')

    def test_setup_summary_does_not_claim_discovery_or_advertise_unselected_target(self):
        installer.install(self.source, self.root, {'codex': self.targets['codex']})
        checked = installer.inspect(self.root, {'codex': self.targets['codex']})
        checked['tools']['codex_available'] = True
        summary = installer.setup_summary(checked)
        self.assertIn('$blog-studio', summary)
        self.assertIn('version ' + VERSION, summary)
        self.assertNotIn('/blog-studio', summary.replace(str(self.targets['codex']), ''))
        self.assertIn('verify discovery', summary)
        (self.targets['codex'].resolve() / 'scripts/studio.py').write_text('damaged')
        damaged = installer.setup_summary(installer.inspect(self.root, {'codex': self.targets['codex']}))
        self.assertNotIn('managed files verified', damaged)
        self.assertIn('repair', damaged)

    def test_human_check_reports_missing_harness_without_mutation(self):
        checked = installer.inspect(self.root, {'claude': self.targets['claude']})
        checked['tools'].update(python_supported=False, git=False, github_cli=False, claude_code_available=False)
        summary = installer.setup_summary(checked)
        for expected in ('python.org', 'Install/open Claude Code', 'not installed', 'Git not found', 'Local writing needs neither'):
            self.assertIn(expected, summary)
        self.assertNotIn('$blog-studio', summary)
        self.assertFalse(self.root.exists())

    def test_optional_google_setup_offline_and_dry_run_do_not_start_login(self):
        for flags in (['--offline'], ['--dry-run', '--offline']):
            with patch.object(installer, 'install', return_value={'status': 'installed'}), \
                    patch.object(installer, 'inspect', return_value={'status': 'checked'}), \
                    patch.object(installer.subprocess, 'run') as run:
                code, out, err = self.main('install', '--target', 'both', '--google-docs', 'gcloud', '--yes', '--json', *flags)
            self.assertEqual(code, 0, err)
            run.assert_not_called()

    def test_optional_google_json_setup_never_starts_interactive_login(self):
        with patch.object(installer, 'install', return_value={'status': 'installed'}), \
                patch.object(installer.subprocess, 'run') as run:
            code, out, err = self.main('install', '--target', 'both', '--google-docs', 'gcloud', '--yes', '--json')
        self.assertEqual(code, 0, err)
        run.assert_not_called()
        google = json.loads(out)['google']
        self.assertEqual(google['status'], 'needs-interactive-login')
        self.assertIn('sh installer/google-setup.sh --login', google['next_step'])
        self.assertNotIn('VM', google['next_step'])


if __name__ == '__main__':
    unittest.main()
