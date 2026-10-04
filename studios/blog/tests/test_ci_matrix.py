"""Check the local controller's failure boundary without starting any VM."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
FAKE_TART = r'''#!/usr/bin/env python3
import json, os, pathlib, signal, sys
root = pathlib.Path(os.environ['FAKE_TART_STATE'])
args = sys.argv[1:]
with (root/'calls').open('a') as log:
    log.write(json.dumps(args)+'\n')
if args[0] == '--version':
    print('fake-tart'); sys.exit(0)
if args[0] == 'get':
    system = 'linux' if args[1].startswith('saypipe') else 'darwin'
    print(json.dumps({'Running': os.environ.get('FAKE_BASE_RUNNING') == '1', 'OS': system})); sys.exit(0)
if args[0] == 'clone':
    sys.exit(0)
if args[0] == 'run':
    dirs = [a.removeprefix('--dir=') for a in args if a.startswith('--dir=')]
    mounts = {a.split(':')[0]: a.split(':')[1] for a in dirs}
    mounts['pid'] = os.getpid()
    (root/args[-1]).write_text(json.dumps(mounts))
    signal.pause()
if args[0] == 'stop':
    info = json.loads((root/args[1]).read_text())
    os.kill(info['pid'], signal.SIGTERM); sys.exit(0)
if args[0] == 'exec':
    vm = args[1]
    state = root/vm
    if not state.exists(): sys.exit(1)
    if args[-1] == '/usr/bin/true': sys.exit(0)
    info = json.loads(state.read_text())
    results, source = pathlib.Path(info['results']), pathlib.Path(info['source'])
    # Even a failed guest that leaves a misleading PASS must fail the controller.
    if os.environ.get('FAKE_MISSING_MARKER') != '1':
        (results/'result.txt').write_text('PASS\n')
    (results/'commit.txt').write_text((source/'commit.txt').read_text())
    sys.exit(17 if os.environ.get('FAKE_GUEST_FAILURE') == '1' else 0)
sys.exit(2)
'''


class MatrixControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base/'repo'
        scripts = self.repo/'scripts/ci'
        scripts.mkdir(parents=True)
        shutil.copyfile(REPO/'scripts/ci/tart-matrix.sh', scripts/'tart-matrix.sh')
        (scripts/'matrix-guest.sh').write_text('echo fixture\n')
        self.git('init', '-b', 'main')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'Fixture')
        self.sha = self.git('rev-parse', 'HEAD').strip()
        (self.repo/'uncommitted-credential').write_text('must not be shared')
        tools = self.base/'tools'
        tools.mkdir()
        tart = tools/'tart'
        tart.write_text(FAKE_TART)
        tart.chmod(0o755)
        self.state = self.base/'state'
        self.state.mkdir()
        self.runs = self.base/'runs'
        self.environment = dict(os.environ, PATH=str(tools)+os.pathsep+os.environ['PATH'],
                                FAKE_TART_STATE=str(self.state),
                                BLOG_STUDIO_TART_RUNS_DIR=str(self.runs))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True,
                                       stderr=subprocess.DEVNULL)

    def run_matrix(self, **environment):
        return subprocess.run(['bash', str(self.repo/'scripts/ci/tart-matrix.sh')],
                              env=dict(self.environment, **environment),
                              text=True, capture_output=True, timeout=30)

    def test_exact_commit_archive_excludes_working_files_and_checks_both_platforms(self):
        result = self.run_matrix()
        self.assertEqual(result.returncode, 0, result.stderr)
        runs = list(self.runs.iterdir())
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertEqual((run/'source/commit.txt').read_text().strip(), self.sha)
            self.assertFalse((run/'source/repo/uncommitted-credential').exists())
            self.assertEqual((run/'results/result.txt').read_text(), 'PASS\n')
        calls = [json.loads(line) for line in (self.state/'calls').read_text().splitlines()]
        self.assertFalse(any(call[0] == 'list' for call in calls))
        self.assertEqual(sum(call[0] == 'stop' for call in calls), 2)

    def test_failed_guest_cannot_pass_from_marker_and_other_platform_still_runs(self):
        result = self.run_matrix(FAKE_GUEST_FAILURE='1')
        self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
        self.assertNotIn('PASS:', result.stdout)
        self.assertIn('macos FAIL:', result.stderr)
        self.assertIn('linux FAIL:', result.stderr)
        self.assertEqual(len(list(self.runs.iterdir())), 2)

    def test_running_base_is_refused_without_clone_or_stop(self):
        result = self.run_matrix(FAKE_BASE_RUNNING='1')
        self.assertEqual(result.returncode, 1)
        calls = [json.loads(line) for line in (self.state/'calls').read_text().splitlines()]
        self.assertFalse(any(call[0] in ('clone', 'stop') for call in calls))

    def test_successful_guest_without_completion_marker_is_rejected(self):
        result = self.run_matrix(FAKE_MISSING_MARKER='1')
        self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
        self.assertNotIn('PASS:', result.stdout)


if __name__ == '__main__':
    unittest.main()
