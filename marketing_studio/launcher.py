"""Start at most one child per studio; keep private links in memory only.

Each running studio is also recorded in the data root's run/ folder (its process,
never its link), so a later Marketing Studio can find a studio left behind by one
that stopped abruptly. Only processes recorded there, and still running this
data root's studio bridge, are ever stopped.
"""
import hashlib
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
# A studio started from here is told the home page's port, so its page can link back to it.
HOME_PORT = 'MARKETING_STUDIO_HOME_PORT'


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


ASSISTANTS = {'codex': 'codex', 'claude': 'claude', 'claude-code': 'claude', 'gemini': 'gemini'}
INTERPRETERS = ('node', 'bun', 'deno', 'sh', 'bash', 'zsh')
WAIT = 8           # seconds a studio has to stop before it is killed


def ps(*arguments):
    """The process list's output, or None where ps is missing or refused.

    Start times are read in one locale and time zone, so a record written by one
    terminal still matches when another reads it."""
    try:
        done = subprocess.run(['ps', *arguments], capture_output=True, text=True, timeout=10,
                              env={**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC'})
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def home_key():
    """Names this data root on each studio bridge's command line, so a bridge started
    for another data root can never be taken for one of these."""
    return hashlib.sha256(str(state.data_root().expanduser().resolve()).encode()).hexdigest()[:16]


def marker(identifier):
    return f'marketing_studio/bridge.py {identifier} '


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


def group_alive(group):
    """Whether any process of the group is still running."""
    try:
        os.killpg(group, 0)
    except (ProcessLookupError, PermissionError):
        return False
    table = ps('-axo', 'pgid=,stat=')
    if table is None:
        return True
    return any(fields[0] == str(group) and not fields[1].startswith('Z')
               for fields in (line.split() for line in table.splitlines()) if len(fields) == 2)


def seconds(elapsed):
    """ps's elapsed time, [[dd-]hh:]mm:ss, in seconds."""
    days, _, clock = elapsed.rpartition('-')
    parts = [int(part) for part in clock.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0)
    return int(days or 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def assistant(command):
    """codex, claude or gemini when the command runs one, directly or through node.

    Only the program, before its first option, is read. A folder name with a space
    splits its path into words, which are followed while they continue the path."""
    words = command.split(' -', 1)[0].split()
    for index, word in enumerate(words[:3]):
        if index:
            continues = words[index - 1].startswith('/') and '/' in word
            through = index == 1 and os.path.basename(words[0]) in INTERPRETERS
            if not (continues or through):
                return None
        name = os.path.basename(word)
        for suffix in ('.js', '.mjs', '.cjs'):
            name = name.removesuffix(suffix)
        if name in ASSISTANTS:
            return ASSISTANTS[name]
    return None


def label(command):
    """The job's name, from a job folder (…/jobs/<name>/…) on its command line."""
    folder = re.search(r'--cd[= ](.+?)(?= --|$)', command)
    if folder:
        found = re.search(r'/jobs/([^/]+)', folder.group(1))
        if found:
            return found.group(1).strip()
    found = re.search(r'/jobs/([^/\s]+)/', command)
    return found.group(1) if found else None


def descendant_jobs(pid, table=None):
    """Assistant jobs started, at any depth, under the studio process `pid`.

    A job may run in its own session; it is still a descendant."""
    live = table is None
    if live:
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
            jobs.append({'assistant': name, 'label': label(command), 'pid': number, 'seconds': elapsed,
                         **({'started': started(number)} if live else {})})
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


def end_jobs(jobs):
    """End assistant jobs found earlier, each with its process group when it leads one.

    A job is signalled only while it is still the same process: same start time and
    still an assistant. Returns the jobs that are gone."""
    gone = []
    own = os.getpgrp()
    for job in jobs:
        pid = job.get('pid')
        if type(pid) is not int or pid <= 1:
            continue
        if alive(pid):
            if not job.get('started') or started(pid) != job['started'] \
                    or assistant(command_of(pid) or '') != job['assistant']:
                continue
            try:
                group = os.getpgid(pid)
            except ProcessLookupError:
                group = None
            if group == pid and group != own:
                stop_group(pid)
            elif group is not None:
                stop_one(pid)
        if not alive(pid):
            gone.append(job)
    return gone


def stop_one(pid):
    for signalled, wait in ((signal.SIGTERM, WAIT), (signal.SIGKILL, 5)):
        try:
            os.kill(pid, signalled)
        except (ProcessLookupError, PermissionError):
            return
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline and alive(pid):
            time.sleep(.1)
        if not alive(pid):
            return


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
                       'command': marker(identifier) + '… --home-data ' + home_key()}, stream)
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def forget(identifier):
    (records() / (identifier + '.json')).unlink(missing_ok=True)


def stop_group(pid):
    """Stop a recorded process group, led by `pid`, until none of it is running."""
    if pid == os.getpgrp():
        return
    for signalled, wait in ((signal.SIGTERM, WAIT), (signal.SIGKILL, 5)):
        try:
            os.killpg(pid, signalled)
        except (ProcessLookupError, PermissionError):
            return
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if not group_alive(pid):
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
        # Set once the home page is listening; until then no studio is told a port.
        self.home_port = None
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
        if not isinstance(found.get('started'), str) or not found['started']:
            return None  # Never signal a process whose start was not recorded.
        command, began = command_of(pid), started(pid)
        if command is None or began is None:
            return None  # Unverifiable without ps: never signal it, keep the record.
        if marker(identifier) not in command or ' --home-data ' + home_key() not in command \
                or began != found['started']:
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
                # Assistants run in their own sessions, outside the studio's group.
                row['jobs'] = end_jobs(jobs)
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
            env = {**self.environment(), 'MARKETING_STUDIO_HANDOFF': json.dumps({'token': token, 'shared': shared}),
                   'PYTHONUNBUFFERED': '1'}
            log = state.data_root() / 'logs' / (identifier + '.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            if log.exists():
                # One earlier launch is kept to compare with.
                os.replace(log, log.with_name(identifier + '.previous.log'))
            with log.open('w') as errors:
                os.chmod(log, 0o600)
                process = subprocess.Popen([sys.executable, str(ROOT / 'marketing_studio/bridge.py'),
                                            identifier, str(root), '--home-data', home_key()], env=env, cwd=root,
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

    def environment(self):
        """This process's environment for a studio, naming the home port only when it is known.

        A port inherited from elsewhere is never passed on; a studio started before the home
        page listens shows no way back rather than a wrong one."""
        env = {key: value for key, value in os.environ.items() if key != HOME_PORT}
        port = self.home_port
        if type(port) is int and 0 < port < 65536:
            env[HOME_PORT] = str(port)
        return env

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
                env = {**self.environment(), 'MARKETING_STUDIO_HANDOFF': json.dumps(
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
        """Stop a child studio and every process left in its group."""
        if process.poll() is not None:
            return
        deadline = time.monotonic() + WAIT
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=WAIT)
            while time.monotonic() < deadline and group_alive(process.pid):
                time.sleep(.1)
            if not group_alive(process.pid):
                return
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            pass
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
