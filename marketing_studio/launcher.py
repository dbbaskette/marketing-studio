"""Start at most one child per studio; keep private links in memory only.

Each running studio is also recorded in the data root's run/ folder (its process,
never its link), so a later Marketing Studio can find a studio left behind by one
that stopped abruptly. Only processes recorded there, and still running this
data root's studio bridge, are ever stopped.
"""

import json
import os
import queue
import secrets
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import bridge_protocol as protocol, catalog, state
from .errors import WorkspaceError

# Moved into focused modules beside this one. Every name stays importable from here, and
# moved code reads the names callers and tests replace (ps, started, stop_group, ...)
# from here when it runs.
from .processes import (
    ASSISTANTS, INTERPRETERS, WAIT, ps, Row, LISTING, _inspecting, _Listing, listing,
    inspection, _live, _inspected, _OUTSIDE, listed, waited_out, started, command_of, alive,
    group_alive, seconds, assistant, label, descendant_jobs, duration, end_jobs, stop_one,
    describe_job, stop_group)
from .bridge_protocol import marker
from .run_records import (
    home_key, records, record, forget)
from .studio_links import (
    local_link, LIBRARY_ID, LIBRARY_REVISIONS, library_item, with_library)

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
        if marker(identifier) not in command or f' {protocol.HOME_DATA} ' + home_key() not in command \
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
            process, link = self.launch(identifier, root, name, shared)
            with self.state:
                # Closing waits for this studio's lock, so it stops this child next.
                self.children[identifier] = (process, link)
            record(identifier, process.pid)
            return self.link(identifier, link, remote)

    def launch(self, identifier, root, name, shared):
        """Start the studio's bridge and wait for the link it announces: (its process, the
        link). A bridge that stops, fails or takes too long to open is stopped, and the
        failure says why, with the end of its launch log."""
        token = secrets.token_urlsafe(32)
        env = {**self.environment(), protocol.HANDOFF: protocol.handoff(token, shared),
               'PYTHONUNBUFFERED': '1'}
        log = state.data_root() / 'logs' / (identifier + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        if log.exists():
            # One earlier launch is kept to compare with.
            os.replace(log, log.with_name(identifier + '.previous.log'))
        with log.open('w') as errors:
            os.chmod(log, 0o600)
            process = subprocess.Popen(protocol.command(ROOT, identifier, root, protocol.HOME_DATA, home_key()),
                                       env=env, cwd=root,
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
        return process, link

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
                result = self.bridge(identifier, root, shared, protocol.PREPARE, TIMEOUT,
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
            result = self.bridge(identifier, root, shared, protocol.CONNECT, CONNECT_TIMEOUT,
                                 'Connecting took too long. Check the repository connection and try again.')
            if result.get('connected') is not True:
                raise WorkspaceError(name + ': ' + (
                    result.get('error') or 'Connecting failed. Check Git and the studio installation.'))
            return {**result, 'studio': identifier, 'name': name, 'stopped': stopped}

    def bridge(self, identifier, root, shared, flag, timeout, slow):
        """Run the studio's bridge once for `flag` and read the report it prints last.
        Returns {} when it printed none; the caller reads 'error' from a failed one."""
        env = {**self.environment(), protocol.HANDOFF: protocol.handoff(secrets.token_urlsafe(32), shared)}
        process = subprocess.Popen(
            protocol.command(ROOT, identifier, root, flag),
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
