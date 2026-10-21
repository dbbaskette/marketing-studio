"""Start at most one child per studio; keep private links in memory only.

Each running studio is also recorded in the data root's run/ folder (its process,
never its link), so a later Marketing Studio can find a studio left behind by one
that stopped abruptly. Only processes recorded there, and still running this
data root's studio bridge, are ever stopped.
"""
import json
import os
import queue
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from . import catalog, state
from .errors import WorkspaceError

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 90
LOG_LINES = 12     # lines of a launch log shown with a failure
LOG_TAIL = 64_000  # bytes read from its end to find them


def launch_problem(message, log):
    """A launch failure with where its log is and how the log ends."""
    try:
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - LOG_TAIL))
            lines = stream.read().decode('utf-8', 'replace').splitlines()[-LOG_LINES:]
    except OSError:
        lines = []
    lines = [line if len(line) <= 300 else line[:299] + '…' for line in lines]
    ending = ('Last lines:\n' + '\n'.join(lines)) if any(lines) else 'The launch log is empty.'
    return f'{message} Launch log: {log}\n{ending}'


ASSISTANTS = ('codex', 'claude', 'gemini')
WAIT = 8           # seconds a studio has to stop before it is killed


def ps(*arguments):
    """The process list's output, or None where ps is missing or refused."""
    try:
        done = subprocess.run(['ps', *arguments], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def started(pid):
    found = ps('-o', 'lstart=', '-p', str(pid))
    return found.strip() or None if found else None


def command_of(pid):
    found = ps('-ww', '-o', 'command=', '-p', str(pid))
    return found.strip() or None if found else None


def alive(pid):
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    # A finished process its parent has not collected yet is not running.
    status = ps('-o', 'stat=', '-p', str(pid))
    return not (status or '').strip().startswith('Z')


def seconds(elapsed):
    """ps's elapsed time, [[dd-]hh:]mm:ss, in seconds."""
    days, _, clock = elapsed.rpartition('-')
    parts = [int(part) for part in clock.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0)
    return int(days or 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def assistant(command):
    """codex, claude or gemini when the command runs one, directly or through node."""
    for token in command.split()[:2]:
        name = os.path.basename(token)
        for suffix in ('.js', '.mjs', '.cjs'):
            name = name.removesuffix(suffix)
        if name in ASSISTANTS:
            return name
    return None


def descendant_jobs(pid, table=None):
    """Assistant jobs started, at any depth, under the studio process `pid`."""
    if table is None:
        table = ps('-axww', '-o', 'pid=,ppid=,etime=,command=')
    if not table:
        return []
    rows, children = {}, {}
    for line in table.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            number, parent, elapsed = int(parts[0]), int(parts[1]), seconds(parts[2])
        except ValueError:
            continue
        rows[number] = (elapsed, parts[3])
        children.setdefault(parent, []).append(number)
    jobs, pending, seen = [], list(children.get(pid, ())), set()
    while pending:
        number = pending.pop(0)
        if number in seen:
            continue
        seen.add(number)
        elapsed, command = rows[number]
        name = assistant(command)
        if name:
            # One job is the outermost assistant process; its own helpers are part of it.
            found = re.search(r'--cd[= ]\S*?/jobs/([^/\s]+)', command)
            jobs.append({'assistant': name, 'label': found.group(1) if found else None,
                         'pid': number, 'seconds': elapsed})
            continue
        pending.extend(children.get(number, ()))
    return jobs


def duration(elapsed):
    minutes = elapsed // 60
    if minutes < 1:
        return 'under 1 min'
    if minutes < 60:
        return f'{minutes} min'
    return f'{minutes // 60} h {minutes % 60} min'


def describe_job(job):
    name = job['assistant'] + (' job ' + job['label'] if job.get('label') else '')
    return f"{name} ({duration(job['seconds'])})"


def records():
    return state.data_root() / 'run'


def record(identifier, pid):
    """Note a running studio's process (never its link) for a later cleanup."""
    folder = records()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / (identifier + '.json')
    pending = folder / ('.' + identifier + '-' + secrets.token_hex(6))
    try:
        with pending.open('x') as stream:
            os.chmod(pending, 0o600)
            json.dump({'pid': pid, 'started': started(pid),
                       'command': 'marketing_studio/bridge.py ' + identifier}, stream)
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def forget(identifier):
    (records() / (identifier + '.json')).unlink(missing_ok=True)


def stop_group(pid):
    """Stop a recorded studio, a session leader, with everything it started."""
    for signalled, wait in ((signal.SIGTERM, WAIT), (signal.SIGKILL, 5)):
        try:
            os.killpg(pid, signalled)
        except (ProcessLookupError, PermissionError):
            return
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if not alive(pid):
                return
            time.sleep(.1)


def local_link(link):
    try:
        url = urlsplit(link)
        return (url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port
                and url.path == '/' and not url.query and not url.username and not url.password
                and re.fullmatch(r'(?:token=)?[A-Za-z0-9_-]{32,128}', url.fragment))
    except (ValueError, TypeError):
        return False


class Launcher:
    def __init__(self, network=None):
        self.network = network
        self.children = {}
        self.lock = threading.RLock()
        self.closed = False

    def running(self, identifier):
        child = self.children.get(identifier)
        return bool(child and child[0].poll() is None)

    def orphan(self, identifier):
        """The process of a studio an earlier Marketing Studio left running, if any.

        Only a process recorded in this data root, still running its studio bridge
        and leading its own session, counts. Stale records are removed.
        """
        target = records() / (identifier + '.json')
        try:
            found = json.loads(target.read_text())
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            target.unlink(missing_ok=True)
            return None
        pid = found.get('pid') if isinstance(found, dict) else None
        if any(child[0].pid == pid for child in list(self.children.values())):
            return None
        try:
            if type(pid) is not int or pid <= 1 or not alive(pid) or os.getpgid(pid) != pid:
                raise ProcessLookupError
        except (ProcessLookupError, PermissionError):
            target.unlink(missing_ok=True)
            return None
        command = command_of(pid)
        if command is None:
            return None  # Unverifiable without ps: never signal it, keep the record.
        if ('marketing_studio/bridge.py ' + identifier) not in command or (
                found.get('started') and started(pid) != found['started']):
            target.unlink(missing_ok=True)
            return None
        return pid

    def process(self, identifier):
        child = self.children.get(identifier)
        if child and child[0].poll() is None:
            return child[0].pid
        return self.orphan(identifier)

    def jobs(self, identifier):
        """Assistant jobs running under this studio, whether started here or earlier."""
        pid = self.process(identifier)
        return descendant_jobs(pid) if pid else []

    def stop(self, identifier):
        """Stop one studio. True when one was running."""
        with self.lock:
            child = self.children.pop(identifier, None)
            if child and child[0].poll() is None:
                self.stop_process(child[0])
                forget(identifier)
                return True
            pid = self.orphan(identifier)
            if pid:
                stop_group(pid)
                forget(identifier)
                return True
            if child:
                forget(identifier)
            return False

    def clean_orphans(self, keep_busy=False):
        """Stop studios earlier Marketing Studio sessions of this data root left running.

        With keep_busy, a studio with a running assistant job is left alone.
        """
        report = []
        for identifier in catalog.STUDIOS:
            pid = self.orphan(identifier)
            if not pid:
                continue
            jobs = descendant_jobs(pid)
            row = {'id': identifier, 'name': catalog.STUDIOS[identifier][0], 'jobs': jobs,
                   'stopped': not (keep_busy and jobs)}
            if row['stopped']:
                stop_group(pid)
                forget(identifier)
            report.append(row)
        return report

    def open(self, identifier, preferences, shared):
        with self.lock:
            if self.closed:
                raise WorkspaceError('Marketing Studio is closing. Open it again to launch a studio.')
            if not isinstance(identifier, str) or identifier not in catalog.STUDIOS:
                raise WorkspaceError('Choose one of the studios shown on the home page.')
            if self.running(identifier):
                return self.link(identifier, self.children[identifier][1])
            root = catalog.locate(identifier, preferences.get('paths', {}))
            if root is None:
                raise WorkspaceError('This studio was not found. Install it or set its folder in Settings.')
            name = catalog.STUDIOS[identifier][0]
            left = self.orphan(identifier)
            if left:
                # An earlier Marketing Studio left it running; its link died with that session.
                jobs = descendant_jobs(left)
                if jobs:
                    raise WorkspaceError(
                        f'{name} is still running from an earlier Marketing Studio session and is working: '
                        + ', '.join(map(describe_job, jobs)) + '. Wait for it, or stop it with: '
                        f'marketing-studio stop --{identifier[0]}s --force')
                stop_group(left)
                forget(identifier)
            token = secrets.token_urlsafe(32)
            env = {**os.environ, 'MARKETING_STUDIO_HANDOFF': json.dumps({'token': token, 'shared': shared}),
                   'PYTHONUNBUFFERED': '1'}
            log = state.data_root() / 'logs' / (identifier + '.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            if log.exists():
                # One earlier launch is kept to compare with.
                os.replace(log, log.with_name(identifier + '.previous.log'))
            with log.open('w') as errors:
                os.chmod(log, 0o600)
                process = subprocess.Popen([sys.executable, str(ROOT / 'marketing_studio/bridge.py'),
                                            identifier, str(root)], env=env, cwd=root,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=errors, text=True, start_new_session=True)
            announced = queue.Queue()

            def collect():
                try:
                    for line in process.stdout:
                        if len(line) > 64000:
                            continue
                        try:
                            found = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(found, dict) and any(key in found for key in ('address', 'link', 'error')):
                            announced.put(found)
                    announced.put({'stopped': True})
                finally:
                    process.stdout.close()
            reader = threading.Thread(target=collect, daemon=True)
            reader.start()
            try:
                result = announced.get(timeout=TIMEOUT)
                if result.get('stopped'):
                    raise WorkspaceError(launch_problem(name + ' stopped before opening.', log))
                if result.get('error'):
                    raise WorkspaceError(result['error'])
                link = result.get('link') or (result.get('address', '') + '#token=' + token)
                if not local_link(link):
                    raise WorkspaceError('The studio returned an invalid local address.')
            except BaseException as failure:
                self.stop_process(process)
                reader.join(timeout=2)
                if isinstance(failure, queue.Empty):
                    raise WorkspaceError(launch_problem(name + ' took too long to open. Try again.', log)) from failure
                raise
            self.children[identifier] = (process, link)
            record(identifier, process.pid)
            return self.link(identifier, link)

    def link(self, identifier, link):
        return self.network.share(identifier, link) if self.network else link

    def prepare(self, preferences, shared):
        """Persist first-run setup for installed studios, without starting their servers."""
        with self.lock:
            prepared = []
            for identifier in catalog.STUDIOS:
                root = catalog.locate(identifier, preferences.get('paths', {}))
                if root is None:
                    continue
                env = {**os.environ, 'MARKETING_STUDIO_HANDOFF': json.dumps(
                    {'token': secrets.token_urlsafe(32), 'shared': shared})}
                process = subprocess.Popen(
                    [sys.executable, str(ROOT / 'marketing_studio/bridge.py'), identifier,
                     str(root), '--prepare'], cwd=root, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    start_new_session=True)
                try:
                    output, _ = process.communicate(timeout=TIMEOUT)
                except BaseException as failure:
                    self.stop_process(process)
                    process.communicate()
                    if isinstance(failure, subprocess.TimeoutExpired):
                        raise WorkspaceError('Workspace setup took too long. Check the repository connection and try again.') from failure
                    raise
                try:
                    result = json.loads(output.splitlines()[-1])
                except (ValueError, IndexError):
                    result = {}
                if process.returncode or not isinstance(result, dict) or result.get('prepared') is not True:
                    message = result.get('error') if isinstance(result, dict) else None
                    message = message or 'Workspace setup failed. Check Git and the studio installation.'
                    raise WorkspaceError(catalog.STUDIOS[identifier][0] + ': ' + message)
                prepared.append(identifier)
            return prepared

    @staticmethod
    def stop_process(process):
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=8)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)

    def close(self):
        with self.lock:
            self.closed = True
            for identifier, (process, _) in self.children.items():
                self.stop_process(process)
                forget(identifier)
            self.children.clear()
