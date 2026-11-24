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
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from . import catalog, state
from .errors import WorkspaceError

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 90
CONNECT_TIMEOUT = 600  # joining, carrying work over and pushing it
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


# --- one process list per inspection --------------------------------------------------
#
# A look at the studios (is a recorded studio still ours, which jobs run under it) asks
# several questions of the process list. Inside `inspection()` they are all answered from
# one `ps` run, read the first time one is asked. Nothing is signalled inside one: every
# signal and every wait for a process to end looks at the processes as they are now.

Row = namedtuple('Row', 'ppid pgid stat seconds started command')
LISTING = ('-axww', '-o', 'pid=,ppid=,pgid=,stat=,etime=,lstart=,command=')
_inspecting = threading.local()


class _Listing:
    def __init__(self):
        self.asked = False
        self.rows = None

    def read(self):
        if not self.asked:
            self.asked = True
            self.rows = listing(ps(*LISTING))
        return self.rows


def listing(output):
    """{pid: Row} from the full process list, or None when there is none."""
    if output is None:
        return None
    rows = {}
    for line in output.splitlines():
        parts = line.split(None, 10)
        if len(parts) < 10:
            continue
        try:
            number, parent, group, elapsed = int(parts[0]), int(parts[1]), int(parts[2]), seconds(parts[4])
        except ValueError:
            continue
        # lstart as `ps -o lstart=` prints it on its own: the day of the month padded to two.
        began = f'{parts[5]} {parts[6]} {parts[7]:>2} {parts[8]} {parts[9]}'
        rows[number] = Row(parent, group, parts[3], elapsed, began, parts[10] if len(parts) > 10 else '')
    return rows


@contextmanager
def inspection():
    """Answer every process question asked inside from one process list. Nested
    inspections share the outer one's list."""
    if getattr(_inspecting, 'listing', None) is not None:
        yield
        return
    _inspecting.listing = _Listing()
    try:
        yield
    finally:
        _inspecting.listing = None


@contextmanager
def _live():
    """Signals and waits look at the processes as they are now, never at an inspection's list."""
    kept = getattr(_inspecting, 'listing', None)
    _inspecting.listing = None
    try:
        yield
    finally:
        _inspecting.listing = kept


def _inspected():
    found = getattr(_inspecting, 'listing', None)
    return found.read() if found is not None else _OUTSIDE


_OUTSIDE = object()


def listed():
    """Whether this computer's process list can be read."""
    rows = _inspected()
    if rows is _OUTSIDE:
        return ps('-o', 'pid=', '-p', str(os.getpid())) is not None
    return rows is not None


def waited_out(running, seconds):
    """Wait up to `seconds` for `running()` to turn false, looking less often as it goes on:
    an ending process is usually gone at the first or second look. True when it did."""
    deadline = time.monotonic() + seconds
    pause = .05
    while True:
        if not running():
            return True
        left = deadline - time.monotonic()
        if left <= 0:
            return False
        time.sleep(min(pause, left))
        pause = min(pause * 2, .5)


def home_key():
    """Names this data root on each studio bridge's command line, so a bridge started
    for another data root can never be taken for one of these."""
    return hashlib.sha256(str(state.data_root().expanduser().resolve()).encode()).hexdigest()[:16]


def marker(identifier):
    return f'marketing_studio/bridge.py {identifier} '


def started(pid):
    rows = _inspected()
    if rows is not _OUTSIDE:
        row = rows.get(pid) if rows else None
        return row.started if row else None
    found = ps('-o', 'lstart=', '-p', str(pid))
    return found.strip() or None if found else None


def command_of(pid):
    rows = _inspected()
    if rows is not _OUTSIDE:
        row = rows.get(pid) if rows else None
        return row.command.strip() or None if row else None
    found = ps('-ww', '-o', 'command=', '-p', str(pid))
    return found.strip() or None if found else None


def alive(pid):
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    # A finished process its parent has not collected yet is not running.
    rows = _inspected()
    if rows is _OUTSIDE:
        status = ps('-o', 'stat=', '-p', str(pid))
    else:
        # Not listed reads as ps does for a missing process: confirmed by a second probe.
        status = None if rows is None else rows[pid].stat if pid in rows else ''
    if not (status or '').strip():
        # It can exit between the first PID probe and ps. Missing process-list
        # access still means unknown/alive when a second PID probe succeeds.
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
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

    A job may run in its own session; it is still a descendant. With no `table` (pid,
    ppid, etime, command per line), the inspection's process list is read, with each
    job's start time from the same list."""
    live = table is None
    if live:
        with inspection():
            rows = _inspected()
        if not rows:
            return []
    else:
        rows = {}
        for line in table.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            try:
                number, parent, elapsed = int(parts[0]), int(parts[1]), seconds(parts[2])
            except ValueError:
                continue
            rows[number] = Row(parent, None, '', elapsed, None, parts[3])
    children = {}
    for number, row in rows.items():
        children.setdefault(row.ppid, []).append(number)
    jobs, pending, seen = [], list(children.get(pid, ())), set()
    while pending:
        number = pending.pop(0)
        if number in seen:
            continue
        seen.add(number)
        row = rows[number]
        name = assistant(row.command)
        if name:
            # One job is the outermost assistant process; its own helpers are part of it.
            jobs.append({'assistant': name, 'label': label(row.command), 'pid': number, 'seconds': row.seconds,
                         **({'started': row.started} if live else {})})
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
        # Who it is now, from one process list, just before it would be signalled.
        with _live(), inspection():
            running = alive(pid)
            same = running and bool(job.get('started')) and started(pid) == job['started'] \
                and assistant(command_of(pid) or '') == job['assistant']
        if running:
            if not same:
                continue
            try:
                group = os.getpgid(pid)
            except ProcessLookupError:
                group = None
            if group == pid and group != own:
                stop_group(pid)
            elif group is not None:
                stop_one(pid)
        with _live():
            if not alive(pid):
                gone.append(job)
    return gone


def stop_one(pid):
    with _live():
        for signalled, wait in ((signal.SIGTERM, WAIT), (signal.SIGKILL, 5)):
            try:
                os.kill(pid, signalled)
            except (ProcessLookupError, PermissionError):
                return
            if waited_out(lambda: alive(pid), wait):
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
    with _live():
        for signalled, wait in ((signal.SIGTERM, WAIT), (signal.SIGKILL, 5)):
            try:
                os.killpg(pid, signalled)
            except (ProcessLookupError, PermissionError):
                return
            if waited_out(lambda: group_alive(pid), wait):
                return


def local_link(link):
    try:
        url = urlsplit(link)
        return (url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port
                and url.path == '/' and not url.query and not url.username and not url.password
                and re.fullmatch(r'(?:token=)?[A-Za-z0-9_-]{32,128}', url.fragment))
    except (ValueError, TypeError):
        return False


# A Document Library item a studio is opened with (Continue in another studio): the library's
# own document ID and a revision number, nothing else.
LIBRARY_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
LIBRARY_REVISIONS = 1_000      # the most revisions one document keeps (document_library.LIMITS)


def library_item(value):
    """(id, revision) of `{'id', 'revision'}` sent to /api/open, refused unless the id is in
    the Document Library's own format, the revision is a whole number it can hold, and that
    revision is in the library, readable and not removed from it. Nothing is written."""
    if not isinstance(value, dict) or set(value) - {'id', 'revision'}:
        raise WorkspaceError('Choose a document shown in the Library.')
    ident, revision = value.get('id'), value.get('revision')
    if not isinstance(ident, str) or not LIBRARY_ID.fullmatch(ident) \
            or type(revision) is not int or not 1 <= revision <= LIBRARY_REVISIONS:
        raise WorkspaceError('Choose a document shown in the Library.')
    from studio_core import document_library
    found = document_library.opened()
    if found is None:
        raise WorkspaceError('The Document Library has not been made on this computer yet.')
    try:
        row = found.describe(ident, revision)
    except document_library.LibraryError as failure:
        raise WorkspaceError(str(failure)) from None
    if row.get('hidden'):
        raise WorkspaceError(f'“{row["title"]}” was removed from the library. Restore it first.')
    if not row.get('readable'):
        raise WorkspaceError(f'“{row["title"]}” has no text a studio can use: {row.get("problem") or ""}'.strip())
    return ident, revision


def with_library(link, ident, revision):
    """`link` with `library=<id>@<revision>` added to its fragment, built here from a checked
    id and revision: no text from a request reaches the link. Any earlier `library=` is
    replaced; everything else in the fragment (the token above all) is kept as it was."""
    if not isinstance(ident, str) or not LIBRARY_ID.fullmatch(ident) \
            or type(revision) is not int or not 1 <= revision <= LIBRARY_REVISIONS:
        raise WorkspaceError('Choose a document shown in the Library.')
    parsed = urlsplit(link)
    fragment = [part for part in parsed.fragment.split('&') if part and part.partition('=')[0] != 'library']
    fragment.append(f'library={ident}@{revision}')
    return parsed._replace(fragment='&'.join(fragment)).geturl()


class Launcher:
    """Opens, prepares, connects and stops studios.

    Each studio has its own lock, held for the whole of opening, preparing, connecting or
    stopping it, so connecting one studio never holds up opening or stopping another.
    `self.state` guards only `children` and `closed`.

    Lock order: a studio's lock, then `self.state`. `self.state` is never held across a
    subprocess, a signal or a wait, and no studio lock is taken while it is held. No code
    holds two studio locks at once: preparing and closing take them one at a time."""

    def __init__(self, network=None):
        self.network = network
        # Set once the home page is listening; until then no studio is told a port.
        self.home_port = None
        self.children = {}
        self.closed = False
        self.state = threading.Lock()
        self.studio_locks = {}

    def studio_lock(self, identifier):
        with self.state:
            return self.studio_locks.setdefault(identifier, threading.RLock())

    def child(self, identifier):
        with self.state:
            return self.children.get(identifier)

    def running(self, identifier):
        child = self.child(identifier)
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
        with self.state:
            ours = [child[0].pid for child in self.children.values()]
        if pid in ours:
            return None
        with inspection():
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
        child = self.child(identifier)
        if child and child[0].poll() is None:
            return child[0].pid
        return self.orphan(identifier)

    def jobs(self, identifier):
        """Assistant jobs running under this studio, whether started here or earlier."""
        with inspection():
            pid = self.process(identifier)
            return descendant_jobs(pid) if pid else []

    def stop(self, identifier):
        """Stop one studio. True when one was running."""
        with self.studio_lock(identifier):
            with self.state:
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

        With keep_busy, a studio with a running assistant job is left alone. Every studio
        is looked at from one process list before any is stopped.
        """
        with inspection():
            left = [(identifier, pid, descendant_jobs(pid)) for identifier, pid in
                    ((identifier, self.orphan(identifier)) for identifier in catalog.STUDIOS) if pid]
        report = []
        for identifier, pid, jobs in left:
            row = {'id': identifier, 'name': catalog.STUDIOS[identifier][0], 'jobs': jobs,
                   'stopped': not (keep_busy and jobs)}
            if row['stopped']:
                with self.studio_lock(identifier):
                    stop_group(pid)
                    forget(identifier)
                # Assistants run in their own sessions, outside the studio's group.
                row['jobs'] = end_jobs(jobs)
            report.append(row)
        return report

    def is_closed(self):
        with self.state:
            return self.closed

    def open(self, identifier, preferences, shared, remote=False):
        """The studio's link, starting it first when it is not running. `remote` is a caller
        that reached Marketing Studio over the network bridge: only it is given, and only it
        starts, the studio's own bridge. Everyone else is given the loopback link."""
        closing = WorkspaceError('Marketing Studio is closing. Open it again to launch a studio.')
        if self.is_closed():
            raise closing
        if not isinstance(identifier, str) or identifier not in catalog.STUDIOS:
            raise WorkspaceError('Choose one of the studios shown on the home page.')
        with self.studio_lock(identifier):
            if self.is_closed():
                raise closing
            child = self.child(identifier)
            if child and child[0].poll() is None:
                return self.link(identifier, child[1], remote)
            root = catalog.locate(identifier, preferences.get('paths', {}))
            if root is None:
                raise WorkspaceError('This studio was not found. Install it or set its folder in Settings.')
            name = catalog.STUDIOS[identifier][0]
            with inspection():
                left = self.orphan(identifier)
                jobs = descendant_jobs(left) if left else []
            if left:
                # An earlier Marketing Studio left it running; its link died with that session.
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
            with self.state:
                # Closing waits for this studio's lock, so it stops this child next.
                self.children[identifier] = (process, link)
            record(identifier, process.pid)
            return self.link(identifier, link, remote)

    def environment(self):
        """This process's environment for a studio, naming the home port only when it is known.

        A port inherited from elsewhere is never passed on; a studio started before the home
        page listens shows no way back rather than a wrong one."""
        env = {key: value for key, value in os.environ.items() if key != HOME_PORT}
        port = self.home_port
        if type(port) is int and 0 < port < 65536:
            env[HOME_PORT] = str(port)
        return env

    def link(self, identifier, link, remote=False):
        """The loopback link for this computer, or the studio's bridge for a network caller."""
        return self.network.share(identifier, link) if self.network and remote else link

    def prepare(self, preferences, shared, only=None):
        """Set up installed studios' missing workspaces as the shared settings say, without
        starting their servers, and learn how each one's workspace relates to those settings.

        Returns each studio's report by its identifier: {'prepared': True, 'workspace': …}
        and 'connect' when the studio keeps a different workspace, which only the Connect
        action moves. Each studio's lock is held only while that studio is prepared."""
        prepared = {}
        for identifier in catalog.STUDIOS:
            if only is not None and identifier != only:
                continue
            root = catalog.locate(identifier, preferences.get('paths', {}))
            if root is None:
                continue
            with self.studio_lock(identifier):
                result = self.bridge(identifier, root, shared, '--prepare', TIMEOUT,
                                     'Workspace setup took too long. Check the repository connection and try again.')
            if result.get('prepared') is not True:
                raise WorkspaceError(catalog.STUDIOS[identifier][0] + ': ' + (
                    result.get('error') or 'Workspace setup failed. Check Git and the studio installation.'))
            prepared[identifier] = result
        return prepared

    def connect(self, identifier, preferences, shared):
        """Connect one studio to the storage the shared settings name, through the studio's
        own join, carrying its work over. A studio running an assistant job is refused, and
        so is a running one when the process list cannot say; an idle running studio is
        stopped first, and the report says so."""
        if not isinstance(identifier, str) or identifier not in catalog.STUDIOS:
            raise WorkspaceError('Choose one of the studios shown on the home page.')
        with self.studio_lock(identifier):
            root = catalog.locate(identifier, preferences.get('paths', {}))
            name = catalog.STUDIOS[identifier][0]
            if root is None:
                raise WorkspaceError('This studio was not found. Install it or set its folder in Settings.')
            stopped = False
            with inspection():
                pid = self.process(identifier)
                readable = bool(pid) and listed()
                jobs = descendant_jobs(pid) if readable else []
            if pid:
                if not readable:
                    raise WorkspaceError(f'{name} is running, and this computer cannot say whether it is '
                                         f'working on a job. Stop it first with: marketing-studio stop '
                                         f'--{identifier[0]}s, then connect.')
                if jobs:
                    raise WorkspaceError(f'{name} is working: ' + ', '.join(map(describe_job, jobs))
                                         + '. Wait for it to finish, then connect.')
                stopped = self.stop(identifier)
            result = self.bridge(identifier, root, shared, '--connect', CONNECT_TIMEOUT,
                                 'Connecting took too long. Check the repository connection and try again.')
            if result.get('connected') is not True:
                raise WorkspaceError(name + ': ' + (
                    result.get('error') or 'Connecting failed. Check Git and the studio installation.'))
            return {**result, 'studio': identifier, 'name': name, 'stopped': stopped}

    def bridge(self, identifier, root, shared, flag, timeout, slow):
        """Run the studio's bridge once for `flag` and read the report it prints last.
        Returns {} when it printed none; the caller reads 'error' from a failed one."""
        env = {**self.environment(), 'MARKETING_STUDIO_HANDOFF': json.dumps(
            {'token': secrets.token_urlsafe(32), 'shared': shared})}
        process = subprocess.Popen(
            [sys.executable, str(ROOT / 'marketing_studio/bridge.py'), identifier, str(root), flag],
            cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            output, _ = process.communicate(timeout=timeout)
        except BaseException as failure:
            self.stop_process(process)
            process.communicate()
            if isinstance(failure, subprocess.TimeoutExpired):
                raise WorkspaceError(slow) from failure
            raise
        try:
            result = json.loads(output.splitlines()[-1])
        except (ValueError, IndexError):
            result = {}
        if process.returncode or not isinstance(result, dict):
            return {'error': result.get('error')} if isinstance(result, dict) else {}
        return result

    @staticmethod
    def stop_process(process):
        """Stop a child studio and every process left in its group."""
        if process.poll() is not None:
            return
        with _live():
            try:
                os.killpg(process.pid, signal.SIGTERM)
                deadline = time.monotonic() + WAIT
                process.wait(timeout=WAIT)
                if waited_out(lambda: group_alive(process.pid), max(0, deadline - time.monotonic())):
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
        """Stop every studio started here. No studio opens once this has begun. A studio
        that is being opened, prepared or connected is stopped once that ends; every other
        studio is stopped first, without waiting for it."""
        with self.state:
            self.closed = True
            identifiers = list(dict.fromkeys([*catalog.STUDIOS, *self.children]))
        waiting = []
        for identifier in identifiers:
            lock = self.studio_lock(identifier)
            if lock.acquire(blocking=False):
                try:
                    self.close_one(identifier)
                finally:
                    lock.release()
            else:
                waiting.append(identifier)
        for identifier in waiting:
            with self.studio_lock(identifier):
                self.close_one(identifier)

    def close_one(self, identifier):
        with self.state:
            child = self.children.pop(identifier, None)
        if child:
            self.stop_process(child[0])
            forget(identifier)
