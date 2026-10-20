"""Installation diagnostics use disposable homes and never provision software."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core import git_diagnostics, install_log


class InstallLogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='studio-install-log-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.environment = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin',
                            'PYTHONPATH': str(ROOT / 'core'), 'PYTHONDONTWRITEBYTECODE': '1'}

    def run_script(self, body, arguments=(), extra=None):
        script = self.home / 'installer.py'
        script.write_text('import subprocess,sys\nfrom studio_core.install_log import session\n'
                          'with session("Test Studio"):\n' + body)
        return subprocess.run([sys.executable, str(script), *arguments],
                              env={**self.environment, **(extra or {})}, capture_output=True,
                              text=True, timeout=20)

    def logs(self, home=None):
        return list((home or self.home).glob('.local/state/marketing-studio/logs/install-*'))

    def test_captured_output_json_and_silent_failure_are_recorded_without_changing_stdout(self):
        done = self.run_script(' subprocess.run([sys.executable,"-c",'
                               '"import sys; print(123); print(456,file=sys.stderr); sys.exit(7)"],'
                               'capture_output=True,text=True)\n'
                               ' print(\'{"installed": true}\')\n raise SystemExit(9)\n')
        self.assertEqual(done.returncode, 9)
        self.assertEqual(json.loads(done.stdout), {'installed': True})
        log, = self.logs()
        record = log.read_text()
        for expected in ('Python ', 'Run: ', 'stdout:', '123', 'stderr:', '456', 'exit 7', 'exit 9'):
            self.assertIn(expected, record)
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        self.assertEqual(log.parent.stat().st_mode & 0o777, 0o700)
        self.assertIn(str(log), done.stderr)

    def test_nested_installers_share_the_log_and_keep_json_machine_readable(self):
        child = self.home / 'child.py'
        child.write_text('from studio_core.install_log import session\n'
                         'with session("Child Studio"):\n print(\'{"child": true}\')\n')
        done = self.run_script(' result = subprocess.run([sys.executable,' + repr(str(child)) + '],'
                               'capture_output=True,text=True,check=True)\n print(result.stdout,end="")\n')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {'child': True})
        log, = self.logs()
        self.assertIn('Child Studio', log.read_text())

    def test_timeout_missing_program_and_checked_failure_record_errors(self):
        for command, exception in [('["/missing/studio-tool"]', 'FileNotFoundError'),
                                  ('[sys.executable,"-c","import time; time.sleep(5)"]', 'TimeoutExpired'),
                                  ('[sys.executable,"-c","raise SystemExit(6)"]', 'CalledProcessError')]:
            done = self.run_script(f' subprocess.run({command},timeout=0.1,check=True,capture_output=True)\n')
            self.assertNotEqual(done.returncode, 0)
            self.assertTrue(any(exception in log.read_text() for log in self.logs()))

    def test_alternate_home_and_help_do_not_write_to_the_callers_home(self):
        destination = self.home / 'another home'
        done = self.run_script(' print("done")\n', ['--home', str(destination)])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.logs(destination)), 1)
        self.assertEqual(self.logs(), [])
        self.run_script(' print("help")\n', ['--help'])
        self.assertEqual(self.logs(), [])

    def test_commands_mask_credentials_and_do_not_record_environment_or_stdin(self):
        with patch.dict(os.environ, {'API_KEY': 'environment-secret'}):
            value = install_log.command_text(['git', 'clone', 'https://user:private@example.com/repo',
                                              '--token', 'argument-secret', '--api-key=other-secret',
                                              'https://example.com/?access_token=query-secret'])
            for secret in ('private', 'argument-secret', 'other-secret', 'query-secret'):
                self.assertNotIn(secret, value)
            self.assertEqual(install_log.redact('environment-secret'), '[redacted]')
        done = self.run_script(' subprocess.run([sys.executable,"-c","print(42)"],'
                               'input="private stdin",text=True,capture_output=True)\n',
                               extra={'SYNTHETIC_API_KEY': 'environment-secret'})
        self.assertEqual(done.returncode, 0, done.stderr)
        log, = self.logs()
        self.assertNotIn('private stdin', log.read_text())
        self.assertNotIn('environment-secret', log.read_text())

    def test_log_symlinks_and_nonprivate_files_are_refused(self):
        target = self.home / 'existing'
        target.write_text('keep')
        link = self.home / 'log-link'
        link.symlink_to(target)
        for path in (target, link):
            done = self.run_script(' print("unreachable")\n', extra={install_log.LOG_ENV: str(path)})
            self.assertNotEqual(done.returncode, 0)
            self.assertEqual(target.read_text(), 'keep')

    def test_brand_audit_child_command_is_logged_without_polluting_json_output(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is not installed')
        source = self.home / 'synthetic brand'
        library = source / 'scripts/lib'
        library.mkdir(parents=True)
        (source / 'package.json').write_text('{"version":"1.0.0"}')
        (library / 'shared-install.mjs').write_text(
            'export async function planShared(){return {needsReplacement:false}};\n'
            'export async function activateShared(plan,options){await options.verify('
            + json.dumps(str(source)) + ')};\n')
        (library / 'install-targets.mjs').write_text('export function personalTargets(){return []}\n')
        audit = source / 'scripts/audit-brand.mjs'
        audit.write_text('console.log("Synthetic audit passed")\n')
        log = self.home / 'install.log'
        log.touch(mode=0o600)
        command = [node, str(ROOT / 'scripts/local_bundle/install-brand.mjs'), str(source),
                   str(self.home), 'codex', 'install']
        done = subprocess.run(command, env={**self.environment, install_log.LOG_ENV: str(log)},
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['status'], 'installed')
        self.assertIn('audit-brand.mjs', log.read_text())
        self.assertIn('Synthetic audit passed', log.read_text())
        self.assertIn('exit 0', log.read_text())
        audit.write_text('console.error("Synthetic audit failed"); process.exit(6)\n')
        failed = subprocess.run(command, env={**self.environment, install_log.LOG_ENV: str(log)},
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(failed.returncode, 1)
        self.assertIn('Command failed: 6', log.read_text())

    def test_git_diagnostic_uses_disposable_identity_and_leaves_existing_workspaces_alone(self):
        suite = self.home / '.local/share/marketing-studio/current'
        python = suite / 'runtime/python/bin/python3'
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        tools = self.home / 'private tools'
        git = tools / 'tools/bin/git'
        git.parent.mkdir(parents=True)
        git.symlink_to(shutil.which('git'))
        record = self.home / '.local/share/presentation-studio-local-bundle/installation.json'
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({'tools': str(tools), 'suite': str(suite)}))
        workspace = self.home / 'Studios/presentation-workspace'
        workspace.mkdir(parents=True)
        sentinel = workspace / 'keep.txt'
        sentinel.write_text('preserve existing work')
        script = ROOT / 'scripts/local_bundle/diagnose-git.sh'
        done = subprocess.run(['bash', str(script)], env=self.environment, capture_output=True,
                              text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn('PASS:', done.stdout)
        self.assertEqual(sentinel.read_text(), 'preserve existing work')
        self.assertFalse((workspace / '.git').exists())
        log, = self.home.glob('.local/state/marketing-studio/logs/git-check-*.json')
        self.assertEqual(len(json.loads(log.read_text())['checks']), 5)
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        # Reproduce a blocked/silent executable and keep its exact exit status.
        git.unlink()
        git.write_text('#!/bin/sh\nexit 23\n')
        git.chmod(0o755)
        failed = subprocess.run(['bash', str(script)], env=self.environment, capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(failed.returncode, 1)
        self.assertIn('"exit": 23', failed.stdout)

    def test_each_studio_exposes_the_failing_git_command_and_executable(self):
        fakebin = self.home / 'bin'
        fakebin.mkdir()
        git = fakebin / 'git'
        git.write_text('#!/bin/sh\nexit 23\n')
        git.chmod(0o755)
        for product in ('presentation', 'training', 'blog'):
            scripts = ROOT / 'studios' / product / 'skills' / (product + '-studio/scripts')
            module = 'studio_sync.support' if product == 'blog' else 'hub'
            env = {**self.environment, 'PYTHONPATH': str(scripts), 'PATH': str(fakebin),
                   product.upper() + '_STUDIO_DATA': str(self.home / product)}
            program = ('from pathlib import Path; import ' + module + ' as hub; '
                       'hub.git(Path.cwd(), "init", "--quiet")')
            done = subprocess.run([sys.executable, '-c', program], cwd=self.home,
                                  env=env, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn('Git init failed with exit status 23', done.stderr)
            log, = (self.home / product / 'logs').glob('git-*.json')
            report = json.loads(log.read_text())
            self.assertEqual(report['executable'], str(git))
            self.assertEqual(report['working_directory'], str(self.home))

    def test_silent_git_failure_records_only_metadata_with_signal_and_exit_status(self):
        with patch.dict(os.environ, {'PRESENTATION_STUDIO_DATA': str(self.home)}):
            for code, expected in [(1, 'exit status 1'), (-signal.SIGKILL, 'signal SIGKILL')]:
                done = subprocess.CompletedProcess(['git', 'init', 'private-argument'], code, '', '')
                done.studio_git, done.studio_cwd = '/private/bin/git', '/temporary/workspace'
                reason = git_diagnostics.silent_failure(done, 'init', 'presentation')
                self.assertIn(expected, reason)
                self.assertIn('Git init failed', reason)
            logs = list((self.home / 'logs').glob('git-*.json'))
            self.assertEqual(len(logs), 2)
            for log in logs:
                record = json.loads(log.read_text())
                self.assertEqual(record['command'], 'git init')
                self.assertNotIn('private-argument', log.read_text())
                self.assertEqual(log.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
