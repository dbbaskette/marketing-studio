"""Exercise shell provisioning with fake tools; never install packages on the host."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='marketing-bootstrap-', dir='/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls'
        # Remove host discovery paths from a disposable copy so an installed host tool
        # cannot turn a simulated missing-tool case into a false pass.
        source = (ROOT / 'installer/install.sh').read_text()
        source = source.replace('export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"',
                                'export PATH="$HOME/.local/bin:$PATH"')
        for path in ('/opt/homebrew/bin/python3', '/usr/local/bin/python3',
                     '/Library/Frameworks/Python.framework/Versions/Current/bin/python3'):
            source = source.replace(path, 'unavailable-python')
        self.script = self.root / 'install.sh'
        self.script.write_text(source)
        self.env = {'PATH': str(self.bin), 'HOME': str(self.root), 'CALLS': str(self.log),
                    'READY': str(self.root / 'ready')}
        self.tool('dirname', '#!/bin/bash\n[ "$1" != -- ] || shift\necho "${1%/*}"\n')
        self.tool('uname', '#!/bin/bash\necho Darwin\n')
        for name in ('python3', 'git', 'node', 'npm'):
            self.tool(name, '''#!/bin/bash
name="${0##*/}"
if [ "$name" = python3 ] && [ "${1:-}" != -c ]; then
  printf 'python:' >> "$CALLS"
  printf '<%s>' "$@" >> "$CALLS"
  printf '\\n' >> "$CALLS"
  exit 0
fi
[ -f "$READY" ] || exit 1
if [ "$name" = npm ]; then
  printf 'npm:%s\\n' "$*" >> "$CALLS"
  assistant=codex
  case "$*" in *claude-code*) assistant=claude;; esac
  /bin/mkdir -p "$HOME/.local/bin"
  printf '#!/bin/bash\\nexit 0\\n' > "$HOME/.local/bin/$assistant"
  /bin/chmod +x "$HOME/.local/bin/$assistant"
fi
''')
        self.tool('brew', '''#!/bin/bash
printf 'brew:%s\\n' "$*" >> "$CALLS"
: > "$READY"
''')
        for assistant in ('codex', 'claude'):
            self.tool(assistant, '#!/bin/bash\nexit 0\n')

    def tool(self, name, source):
        path = self.bin / name
        path.write_text(source)
        path.chmod(0o755)

    def run_setup(self, *args):
        return subprocess.run(['/bin/bash', str(self.script), *args], env=self.env,
                              input='', capture_output=True, text=True, timeout=20)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ''

    def test_missing_tools_are_provisioned_then_forwarded_to_native_setup(self):
        done = self.run_setup('--yes', '--target', 'codex', '--studios', 'blog')
        self.assertEqual(done.returncode, 0, done.stderr)
        calls = self.calls()
        self.assertIn('brew:install python3 git node', calls)
        self.assertIn('<--studios><blog>', calls)
        self.assertIn('<--companions><install>', calls)
        self.assertLess(calls.index('brew:'), calls.index('python:'))

    def test_existing_tools_are_reused_and_assistants_only_for_the_selected_target(self):
        (self.root / 'ready').touch()
        (self.bin / 'codex').unlink()
        (self.bin / 'claude').unlink()
        done = self.run_setup('--yes', '--target', 'codex', '--companions', 'skip')
        self.assertEqual(done.returncode, 0, done.stderr)
        calls = self.calls()
        self.assertNotIn('brew:', calls)
        self.assertIn('@openai/codex', calls)
        self.assertNotIn('@anthropic-ai/claude-code', calls)

    def test_skip_and_inspection_never_run_package_managers(self):
        (self.root / 'ready').touch()
        for args in (('--prerequisites', 'skip', '--yes'), ('--dry-run',), ('check', '--yes'),
                     ('rollback', '--yes'), ('--home', '/tmp/disposable-home', '--yes')):
            with self.subTest(args=args):
                self.log.unlink(missing_ok=True)
                done = self.run_setup(*args)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn('brew:', self.calls())
                self.assertNotIn('npm:', self.calls())

    def test_linux_package_manager_uses_native_package_names(self):
        (self.bin / 'brew').unlink()
        self.tool('uname', '#!/bin/bash\necho Linux\n')
        self.tool('id', '#!/bin/bash\necho 0\n')
        self.tool('apt-get', '''#!/bin/bash
printf 'apt-get:%s\\n' "$*" >> "$CALLS"
: > "$READY"
''')
        done = self.run_setup('--yes', '--assistants', 'skip', '--companions', 'install')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('apt-get:update', self.calls())
        self.assertIn('apt-get:install -y python3 git nodejs npm', self.calls())

    def test_failed_package_install_stops_before_studio_changes(self):
        self.tool('brew', '#!/bin/bash\nexit 9\n')
        done = self.run_setup('--yes')
        self.assertEqual(done.returncode, 9)
        self.assertNotIn('python:', self.calls())

    def test_help_does_not_require_python_or_install_anything(self):
        done = self.run_setup('--target', 'codex', '--help')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('--prerequisites', done.stdout)
        self.assertEqual(self.calls(), '')

    def test_missing_tools_check_and_unattended_prompt_refuse_without_changes(self):
        for args in (('--prerequisites', 'check', '--yes'), (), ('--unknown',)):
            with self.subTest(args=args):
                done = self.run_setup(*args)
                self.assertNotEqual(done.returncode, 0)
                self.assertEqual(self.calls(), '')


if __name__ == '__main__':
    unittest.main()
