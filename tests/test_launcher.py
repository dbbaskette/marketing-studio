import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from marketing_studio import bridge, catalog, launcher as launching
from marketing_studio.errors import WorkspaceError
from marketing_studio.launcher import Launcher


def ps_works():
    """Process listing is refused in some sandboxes; those tests skip there."""
    try:
        return subprocess.run(['ps', '-o', 'pid=', '-p', str(os.getpid())],
                              capture_output=True).returncode == 0
    except OSError:
        return False


PS = ps_works()
SLEEPER = """import json, os, time
handoff = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF'))
print(json.dumps({'address': 'http://127.0.0.1:12345/'}), flush=True)
time.sleep(60)
"""


def end(process):
    """Stop a process this test started, and only that one."""
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
    process.wait(timeout=5)


def waited(check, seconds=5):
    deadline = time.monotonic() + seconds
    while True:
        found = check()
        if found or time.monotonic() > deadline:
            return found
        time.sleep(.05)


class BridgeTests(unittest.TestCase):
    def test_existing_workspace_is_never_moved(self):
        gitstate = mock.Mock()
        existing = gitstate.current.return_value
        result = bridge.configure(gitstate, {'local': {'root': '/unused'}}, 'training')
        self.assertIs(result, existing)
        gitstate.local.assert_not_called()
        gitstate.join.assert_not_called()

    def test_local_default_and_remote_are_explicit_choices(self):
        gitstate = mock.Mock()
        gitstate.current.return_value = None
        bridge.configure(gitstate, {'local': {'root': '/work'}}, 'training')
        gitstate.local.assert_called_once_with(Path('/work/training-workspace'), branch='main')
        gitstate.reset_mock()
        bridge.configure(gitstate, {'team': {'repository': '/tmp/team.git', 'branch': 'main'},
                                   'share': 'asked'}, 'presentation')
        gitstate.join.assert_called_once_with('/tmp/team.git', branch='main', share='asked')
        gitstate.local.assert_not_called()


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(self.root / 'data')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.install = self.root / 'studio'
        (self.install / 'runner').mkdir(parents=True)
        (self.install / 'runner/studio.py').write_text('# fixture')
        self.preferences = {'paths': {'training': str(self.install.resolve())}}
        self.fixture_root = self.root / 'marketing'
        (self.fixture_root / 'marketing_studio').mkdir(parents=True)

    def fixture(self, content):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text(content)
        return mock.patch('marketing_studio.launcher.ROOT', self.fixture_root)

    def test_launch_reuse_and_child_cleanup(self):
        content = """import json, os, time
handoff = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF'))
print(json.dumps({'address': 'http://127.0.0.1:12345/'}), flush=True)
time.sleep(60)
"""
        with self.fixture(content):
            link = self.launcher.open('training', self.preferences, {})
            self.assertIn('#token=', link)
            self.assertTrue(self.launcher.running('training'))
            process = self.launcher.children['training'][0]
            self.assertEqual(link, self.launcher.open('training', self.preferences, {}))
            self.assertEqual(process.pid, self.launcher.children['training'][0].pid)
            self.launcher.close()
            self.assertIsNotNone(process.poll())
            self.assertFalse(self.launcher.children)
        self.assertNotIn(link, (self.root / 'data/logs/training.log').read_text())

    def test_a_studio_is_told_the_home_port_only_once_it_is_known(self):
        content = """import json, os, time
handoff = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF'))
with open(os.environ['FIXTURE_SEEN'], 'w') as seen:
    seen.write(json.dumps(os.environ.get('MARKETING_STUDIO_HOME_PORT')))
print(json.dumps({'address': 'http://127.0.0.1:12345/'}), flush=True)
time.sleep(60)
"""
        seen = self.root / 'seen.json'
        # A port inherited from another session is never passed on.
        inherited = {'FIXTURE_SEEN': str(seen), 'MARKETING_STUDIO_HOME_PORT': '1111'}
        with self.fixture(content), mock.patch.dict(os.environ, inherited):
            self.assertIsNone(self.launcher.home_port)
            self.launcher.open('training', self.preferences, {})
            self.assertIsNone(json.loads(seen.read_text()))
            self.launcher.stop('training')
            for port, told in ((True, None), ('8790', None), (0, None), (65536, None), (8790, '8790')):
                with self.subTest(port=port):
                    self.launcher.home_port = port
                    self.assertEqual(self.launcher.environment().get('MARKETING_STUDIO_HOME_PORT'), told)
            self.launcher.open('training', self.preferences, {})
            self.assertEqual(json.loads(seen.read_text()), '8790')
            self.assertEqual(os.environ['MARKETING_STUDIO_HOME_PORT'], '1111')

    def test_failure_and_timeout_stop_the_child(self):
        with self.fixture("import json\nprint(json.dumps({'error':'Fixture refused'}), flush=True)\n"):
            with self.assertRaisesRegex(WorkspaceError, 'Fixture refused'):
                self.launcher.open('training', self.preferences, {})
        with self.fixture('import time\ntime.sleep(60)\n'), mock.patch('marketing_studio.launcher.TIMEOUT', .1):
            with self.assertRaisesRegex(WorkspaceError, 'too long'):
                self.launcher.open('training', self.preferences, {})
        self.assertFalse(self.launcher.children)

    def test_stopped_studio_names_its_log_and_last_lines(self):
        with self.fixture("import sys\nfor n in range(1, 21):\n    print('fixture line', n, file=sys.stderr)\n"):
            with self.assertRaises(WorkspaceError) as raised:
                self.launcher.open('training', self.preferences, {})
        message = str(raised.exception)
        log = self.root / 'data/logs/training.log'
        self.assertIn('Training Studio stopped before opening', message)
        self.assertIn(str(log), message)
        for n in range(9, 21):
            self.assertIn(f'fixture line {n}\n' if n < 20 else 'fixture line 20', message)
        self.assertNotIn('fixture line 8\n', message)
        self.assertFalse(self.launcher.children)

    def test_slow_studio_names_its_log(self):
        content = "import sys, time\nprint('fixture is waiting', file=sys.stderr)\ntime.sleep(60)\n"
        with self.fixture(content), mock.patch('marketing_studio.launcher.TIMEOUT', 2):
            with self.assertRaises(WorkspaceError) as raised:
                self.launcher.open('training', self.preferences, {})
        message = str(raised.exception)
        self.assertIn('took too long', message)
        self.assertIn(str(self.root / 'data/logs/training.log'), message)
        self.assertIn('fixture is waiting', message)

    def test_previous_launch_log_is_kept(self):
        logs = self.root / 'data/logs'
        for run in ('first run', 'second run'):
            with self.fixture(f"import sys\nprint({run!r}, file=sys.stderr)\n"):
                with self.assertRaises(WorkspaceError):
                    self.launcher.open('training', self.preferences, {})
        self.assertEqual((logs / 'training.log').read_text(), 'second run\n')
        self.assertEqual((logs / 'training.previous.log').read_text(), 'first run\n')
        self.assertEqual((logs / 'training.previous.log').stat().st_mode & 0o777, 0o600)

    def test_external_link_is_refused_and_browser_not_started(self):
        with self.fixture("import json\nprint(json.dumps({'link':'https://evil.example/'}), flush=True)\n"):
            with self.assertRaisesRegex(WorkspaceError, 'invalid local address'):
                self.launcher.open('training', self.preferences, {})

    def test_prepare_is_bounded_and_propagates_failure(self):
        with self.fixture("import json\nprint(json.dumps({'error':'Git identity needed'}), flush=True)\n"), mock.patch('marketing_studio.catalog.STUDIOS', {'training': catalog.STUDIOS['training']}):
            with self.assertRaisesRegex(WorkspaceError, 'Git identity needed'):
                self.launcher.prepare(self.preferences, {})
        with self.fixture('import time\ntime.sleep(60)\n'), mock.patch('marketing_studio.catalog.STUDIOS', {'training': catalog.STUDIOS['training']}), mock.patch('marketing_studio.launcher.TIMEOUT', .1):
            with self.assertRaisesRegex(WorkspaceError, 'too long'):
                self.launcher.prepare(self.preferences, {})

    def test_prepare_reports_each_studios_workspace_and_connect(self):
        report = {'prepared': True, 'workspace': {'root': '/work/trainings', 'repository': None, 'branch': 'main'},
                  'connect': {'from': {'root': '/work/trainings'}, 'to': {'repository': '/team.git'},
                              'carry': {'trainings': 2}}}
        content = f"import json\nprint('noise')\nprint(json.dumps({report!r}), flush=True)\n"
        with self.fixture(content), mock.patch('marketing_studio.catalog.STUDIOS', {'training': catalog.STUDIOS['training']}):
            self.assertEqual(self.launcher.prepare(self.preferences, {}), {'training': report})
            self.assertEqual(self.launcher.prepare(self.preferences, {}, only='blog'), {})

    def connecting_bridge(self):
        """A bridge that serves, and when asked to connect reports what it carried."""
        return """import json, os, sys, time
handoff = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF'))
if '--connect' in sys.argv:
    print(json.dumps({'connected': True, 'carried': {'trainings': 1}, 'left': [],
                      'to': {'repository': handoff['shared']['team']['repository']}}), flush=True)
    raise SystemExit(0)
print(json.dumps({'address': 'http://127.0.0.1:12345/'}), flush=True)
time.sleep(60)
"""

    def test_connect_relays_the_report_and_stops_an_idle_studio_first(self):
        shared = {'team': {'repository': '/team.git', 'branch': 'main'}}
        with self.fixture(self.connecting_bridge()):
            found = self.launcher.connect('training', self.preferences, shared)
            self.assertEqual((found['connected'], found['carried'], found['stopped'], found['name']),
                             (True, {'trainings': 1}, False, 'Training Studio'))
            self.assertEqual(found['to'], {'repository': '/team.git'})
            self.launcher.open('training', self.preferences, shared)
            process = self.launcher.children['training'][0]
            found = self.launcher.connect('training', self.preferences, shared)
            self.assertTrue(found['stopped'])
            self.assertIsNotNone(process.poll())
            self.assertFalse(self.launcher.running('training'))
            with self.assertRaises(WorkspaceError):
                self.launcher.connect('other', self.preferences, shared)
            with mock.patch.dict(os.environ, {'BLOG_STUDIO_INSTALL': str(self.root / 'missing')}):
                with self.assertRaisesRegex(WorkspaceError, 'not found'):
                    self.launcher.connect('blog', self.preferences, shared)

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_connect_refuses_a_studio_with_a_running_job(self):
        with self.fixture(self.busy_bridge()):
            self.launcher.open('training', self.preferences, {})
            self.assertTrue(waited(lambda: self.launcher.jobs('training')))
            with self.assertRaisesRegex(WorkspaceError, 'is working: codex job'):
                self.launcher.connect('training', self.preferences, {})
            self.assertTrue(self.launcher.running('training'))

    def test_connect_failure_and_delay_name_the_studio(self):
        with self.fixture("import json\nprint(json.dumps({'error':'Git identity needed'}), flush=True)\nraise SystemExit(2)\n"):
            with self.assertRaisesRegex(WorkspaceError, 'Training Studio: Git identity needed'):
                self.launcher.connect('training', self.preferences, {})
        with self.fixture('import time\ntime.sleep(60)\n'), mock.patch('marketing_studio.launcher.CONNECT_TIMEOUT', .1):
            with self.assertRaisesRegex(WorkspaceError, 'too long'):
                self.launcher.connect('training', self.preferences, {})

    def test_pid_file_is_written_and_removed(self):
        record = self.root / 'data/run/training.json'
        with self.fixture(SLEEPER):
            self.launcher.open('training', self.preferences, {})
            process = self.launcher.children['training'][0]
            found = json.loads(record.read_text())
            self.assertEqual(found['pid'], process.pid)
            self.assertEqual(found['command'], 'marketing_studio/bridge.py training … --home-data '
                             + launching.home_key())
            self.assertEqual(process.args[-2:], ['--home-data', launching.home_key()])
            if PS:
                self.assertTrue(found['started'])
            self.assertEqual(record.stat().st_mode & 0o777, 0o600)
            self.assertTrue(self.launcher.stop('training'))
            self.assertIsNotNone(process.poll())
            self.assertFalse(record.exists())
            self.assertFalse(self.launcher.running('training'))
            self.assertFalse(self.launcher.stop('training'))
            self.launcher.open('training', self.preferences, {})
            self.assertTrue(record.exists())
            self.launcher.close()
            self.assertFalse(record.exists())

    def orphan(self, data, identifier, bridge_file=True, belongs=None, started=True):
        """A studio left running by an earlier Marketing Studio, recorded in `data`.

        Its command line names the data root `belongs` (by default `data`) as a bridge does."""
        script = (self.fixture_root / 'marketing_studio/bridge.py') if bridge_file else (self.root / 'plain.py')
        if not script.exists():
            script.write_text('import time\ntime.sleep(60)\n')
        with mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(belongs or data)}):
            key = launching.home_key()
        process = subprocess.Popen([sys.executable, str(script), identifier, str(self.install), '--home-data', key],
                                   start_new_session=True, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(end, process)
        with mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(data)}):
            if started:
                if PS:
                    # The command line must be visible before it is recorded.
                    waited(lambda: '--home-data' in (launching.command_of(process.pid) or ''))
                launching.record(identifier, process.pid)
            else:
                folder = launching.records()
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (identifier + '.json')).write_text(json.dumps(
                    {'pid': process.pid, 'command': 'marketing_studio/bridge.py ' + identifier}))
        return process

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_orphan_cleanup_reaches_only_this_data_roots_records(self):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text('import time\ntime.sleep(60)\n')
        mine, other = self.root / 'data', self.root / 'other-data'
        left = self.orphan(mine, 'training')
        elsewhere = self.orphan(other, 'training')
        unrelated = self.orphan(mine, 'blog', bridge_file=False)
        finished = subprocess.Popen([sys.executable, '-c', 'pass'])
        finished.wait()
        with mock.patch.dict(os.environ, {'MARKETING_STUDIO_DATA': str(mine)}):
            launching.record('presentation', finished.pid)
            report = Launcher().clean_orphans()
        self.assertEqual([(row['id'], row['stopped']) for row in report], [('training', True)])
        self.assertIsNotNone(waited(lambda: left.poll() is not None or None))
        self.assertIsNone(elsewhere.poll())
        self.assertIsNone(unrelated.poll())
        self.assertEqual(list((mine / 'run').iterdir()), [])
        self.assertTrue((other / 'run/training.json').is_file())

    def busy_bridge(self, name='tanzu-postgres-vs-edb-or-diy-oss--deck-outline-1', own_session=False):
        """A bridge whose studio runs a fake codex job, the way the studios start one."""
        tools = self.root / 'bin'
        tools.mkdir(exist_ok=True)
        codex = tools / 'codex'
        codex.write_text('#!/bin/sh\nsleep 60\n')
        codex.chmod(0o755)
        folder = self.root / 'Application Support/jobs' / name / 'stand'
        return f"""import json, os, subprocess, time
os.environ.pop('MARKETING_STUDIO_HANDOFF', None)
subprocess.Popen([{str(codex)!r}, 'exec', '--json', '--cd', {str(folder)!r}, '--output-schema', 'x'],
                 start_new_session={own_session!r})
print(json.dumps({{'address': 'http://127.0.0.1:12345/'}}), flush=True)
time.sleep(60)
"""

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_jobs_find_an_assistant_under_the_studio_and_name_it(self):
        with self.fixture(self.busy_bridge()):
            self.launcher.open('training', self.preferences, {})
            jobs = waited(lambda: self.launcher.jobs('training'))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['assistant'], 'codex')
        self.assertEqual(jobs[0]['label'], 'tanzu-postgres-vs-edb-or-diy-oss--deck-outline-1')
        self.assertRegex(launching.describe_job(jobs[0]),
                         r'^codex job tanzu-postgres-vs-edb-or-diy-oss--deck-outline-1 \(.+\)$')
        self.assertEqual(self.launcher.jobs('blog'), [])

    def test_jobs_tolerate_a_missing_process_list(self):
        with mock.patch.object(launching.subprocess, 'run', side_effect=FileNotFoundError('ps')):
            self.assertIsNone(launching.ps('-o', 'pid='))
            self.assertEqual(launching.descendant_jobs(os.getpid()), [])
        self.assertEqual(launching.descendant_jobs(1, table='not a table\n'), [])
        table = ('  10     1   04:10 python bridge.py training\n'
                 '  11    10   03:59 /usr/local/bin/node /usr/local/bin/codex exec --cd /d/jobs/a-b/stand\n'
                 '  12    11   03:58 /vendor/codex/codex exec\n'
                 '  13    10 1-02:03:04 claude -p\n'
                 '  14     1   00:01 gemini\n')
        jobs = launching.descendant_jobs(10, table=table)
        self.assertEqual([(job['assistant'], job['label'], job['seconds']) for job in jobs],
                         [('codex', 'a-b', 239), ('claude', None, 93784)])
        self.assertEqual(launching.describe_job(jobs[1]), 'claude (26 h 3 min)')
        self.assertEqual(launching.describe_job({**jobs[0], 'seconds': 20}), 'codex job a-b (under 1 min)')
        spaced = ('  20     1   05:00 python bridge.py training\n'
                  '  21    20   04:00 /Users/a/Library/Application Support/bin/claude-code -p --mcp-config '
                  '/Users/a/Library/Application Support/marketing/jobs/deck-2/mcp.json --verbose\n'
                  '  22    20   03:00 codex exec --cd /Users/a/My Data/jobs/brief 3/stand --json\n'
                  '  23    20   02:00 git commit -m claude\n')
        jobs = launching.descendant_jobs(20, table=spaced)
        self.assertEqual([(job['assistant'], job['label']) for job in jobs],
                         [('claude', 'deck-2'), ('codex', 'brief 3')])

    def test_process_list_reads_times_in_one_locale(self):
        done = subprocess.CompletedProcess([], 0, stdout='x\n')
        with mock.patch.dict(os.environ, {'LC_ALL': 'fr_FR.UTF-8', 'TZ': 'Asia/Tokyo'}), \
                mock.patch.object(launching.subprocess, 'run', return_value=done) as run:
            launching.started(123)
        env = run.call_args.kwargs['env']
        self.assertEqual((env['LC_ALL'], env['TZ']), ('C', 'UTC'))

    def test_an_unknown_start_time_keeps_the_record_and_signals_nothing(self):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text('import time\ntime.sleep(60)\n')
        with mock.patch.object(launching, 'started', return_value='Mon Oct 20 10:00:00 2026'):
            left = self.orphan(self.root / 'data', 'training')
        key = launching.home_key()
        command = f'python {self.fixture_root}/marketing_studio/bridge.py training {self.install} --home-data {key}'
        with mock.patch.object(launching, 'command_of', return_value=command), \
                mock.patch.object(launching, 'started', return_value=None), \
                mock.patch.object(launching, 'stop_group', side_effect=AssertionError('Signalled')):
            self.assertIsNone(Launcher().orphan('training'))
            self.assertEqual(Launcher().clean_orphans(), [])
        self.assertTrue((self.root / 'data/run/training.json').exists())
        self.assertIsNone(left.poll())

    def test_a_record_without_a_start_time_is_never_signalled(self):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text('import time\ntime.sleep(60)\n')
        left = self.orphan(self.root / 'data', 'training', started=False)
        key = launching.home_key()
        command = f'python {self.fixture_root}/marketing_studio/bridge.py training {self.install} --home-data {key}'
        with mock.patch.object(launching, 'command_of', return_value=command), \
                mock.patch.object(launching, 'started', return_value='Mon Oct 20 10:00:00 2026'), \
                mock.patch.object(launching, 'stop_group', side_effect=AssertionError('Signalled')):
            self.assertEqual(Launcher().clean_orphans(), [])
        self.assertIsNone(left.poll())

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_a_start_time_recorded_elsewhere_still_matches(self):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text('import time\ntime.sleep(60)\n')
        with mock.patch.dict(os.environ, {'TZ': 'America/New_York', 'LC_ALL': 'fr_FR.UTF-8', 'LANG': 'fr_FR.UTF-8'}):
            left = self.orphan(self.root / 'data', 'training')
        with mock.patch.dict(os.environ, {'TZ': 'Asia/Tokyo', 'LC_ALL': 'de_DE.UTF-8', 'LANG': 'de_DE.UTF-8'}):
            self.assertEqual(Launcher().orphan('training'), left.pid)

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_another_data_roots_bridge_is_never_signalled(self):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text('import time\ntime.sleep(60)\n')
        theirs = self.orphan(self.root / 'data', 'training', belongs=self.root / 'other-data')
        self.assertEqual(Launcher().clean_orphans(), [])
        self.assertIsNone(theirs.poll())

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_force_ends_a_job_started_in_its_own_session(self):
        with self.fixture(self.busy_bridge('deck-9', own_session=True)):
            self.launcher.open('training', self.preferences, {})
            jobs = waited(lambda: self.launcher.jobs('training'))
        job = jobs[0]
        self.addCleanup(lambda: launching.alive(job['pid']) and os.killpg(job['pid'], signal.SIGKILL))
        self.assertEqual(os.getpgid(job['pid']), job['pid'])
        self.assertTrue(self.launcher.stop('training'))
        self.assertTrue(launching.alive(job['pid']))  # its own session outlives the studio
        self.assertEqual(launching.end_jobs([{**job, 'started': 'Sat Jan  1 00:00:00 2000'}]), [])
        self.assertTrue(launching.alive(job['pid']))
        self.assertEqual(launching.end_jobs(jobs), jobs)
        self.assertFalse(launching.alive(job['pid']))

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_stopping_a_group_waits_for_every_member(self):
        stubborn = self.root / 'stubborn.sh'
        stubborn.write_text("#!/bin/sh\ntrap '' TERM\nwhile :; do sleep 1; done\n")
        stubborn.chmod(0o755)
        member = self.root / 'member.pid'
        (self.fixture_root / 'marketing_studio/bridge.py').write_text(
            f"import subprocess, time\np = subprocess.Popen([{str(stubborn)!r}])\n"
            f"open({str(member)!r}, 'w').write(str(p.pid))\ntime.sleep(60)\n")
        left = self.orphan(self.root / 'data', 'training')
        pid = int(waited(lambda: member.exists() and member.read_text()))
        with mock.patch.object(launching, 'WAIT', 1):
            report = Launcher().clean_orphans()
        self.assertEqual([row['stopped'] for row in report], [True])
        self.assertTrue(waited(lambda: left.poll() is not None))
        self.assertTrue(waited(lambda: not launching.alive(pid)))

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_start_up_cleanup_keeps_an_orphan_with_a_running_job(self):
        (self.fixture_root / 'marketing_studio').mkdir(exist_ok=True)
        content = self.busy_bridge('deck-1').replace("print(json.dumps({'address': 'http://127.0.0.1:12345/'}), flush=True)\n", '')
        (self.fixture_root / 'marketing_studio/bridge.py').write_text(content)
        busy = self.orphan(self.root / 'data', 'training')
        self.assertTrue(waited(lambda: launching.descendant_jobs(busy.pid)))
        kept = Launcher().clean_orphans(keep_busy=True)
        self.assertEqual([(row['id'], row['stopped']) for row in kept], [('training', False)])
        self.assertEqual(kept[0]['jobs'][0]['label'], 'deck-1')
        self.assertIsNone(busy.poll())
        stopped = Launcher().clean_orphans()
        self.assertEqual([(row['id'], row['stopped']) for row in stopped], [('training', True)])
        self.assertTrue(waited(lambda: busy.poll() is not None))
        self.assertFalse((self.root / 'data/run/training.json').exists())

    @unittest.skipUnless(PS, 'Listing processes is not permitted here.')
    def test_an_idle_orphan_gives_way_to_a_new_launch(self):
        (self.fixture_root / 'marketing_studio/bridge.py').write_text('import time\ntime.sleep(60)\n')
        left = self.orphan(self.root / 'data', 'training')
        with self.fixture(SLEEPER):
            self.launcher.open('training', self.preferences, {})
        self.assertTrue(waited(lambda: left.poll() is not None))
        recorded = json.loads((self.root / 'data/run/training.json').read_text())
        self.assertEqual(recorded['pid'], self.launcher.children['training'][0].pid)

    def test_installed_blog_layout_is_found(self):
        installed = self.root / 'installed-blog'
        (installed / 'scripts').mkdir(parents=True)
        (installed / 'scripts/start_studio.py').write_text('# fixture')
        self.assertEqual(catalog.locate('blog', {'blog': str(installed)}), installed.resolve())

    def test_blog_version_is_read_from_its_skill_in_a_checkout(self):
        checkout = self.root / 'blog-checkout'
        skill = checkout / 'skills/blog-studio'
        (skill / 'scripts').mkdir(parents=True)
        (skill / 'scripts/start_studio.py').write_text('# fixture')
        (skill / 'VERSION').write_text('9.8.7\n')
        installed = self.root / 'installed-blog'
        (installed / 'scripts').mkdir(parents=True)
        (installed / 'scripts/start_studio.py').write_text('# fixture')
        (installed / 'VERSION').write_text('1.2.3\n')
        for root, expected in ((checkout, '9.8.7'), (installed, '1.2.3')):
            with self.subTest(root=root.name):
                rows = catalog.describe({'blog': str(root)}, lambda _: False)
                self.assertEqual(rows[0]['version'], expected)

    def test_checkout_copies_are_told_apart_from_installed_releases(self):
        home = self.root / 'home'
        installed = home / '.local/share/training-studio/current'
        (installed / 'runner').mkdir(parents=True)
        (installed / 'runner/studio.py').write_text('# fixture')
        (home / '.git').mkdir()  # a home folder kept in Git is still not a checkout copy
        (self.root / 'repository/.git').mkdir(parents=True)
        checkout = self.root / 'repository/studios/training'
        (checkout / 'runner').mkdir(parents=True)
        (checkout / 'runner/studio.py').write_text('# fixture')
        with mock.patch.dict(os.environ, {'HOME': str(home)}):
            for root, expected in ((installed, False), (checkout, True), (self.install, False)):
                with self.subTest(root=str(root)):
                    row = catalog.describe({'training': str(root)}, lambda _: False)[2]
                    self.assertEqual(row['checkout'], expected)

    def test_configured_path_is_authoritative(self):
        self.assertEqual(catalog.locate('training', self.preferences['paths']), self.install.resolve())
        self.assertIsNone(catalog.locate('training', {'training': '/does-not-exist'}))


if __name__ == '__main__':
    unittest.main()
