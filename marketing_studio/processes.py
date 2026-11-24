"""The process list, as Marketing Studio reads it to know whether a studio it recorded is
still its own and which assistant jobs run under it, and stopping those processes.
marketing_studio.launcher re-exports every name here."""

import os
import re
import signal
import subprocess
import threading
import time
from collections import namedtuple
from contextlib import contextmanager


def _launcher():
    """marketing_studio.launcher, read when called. Callers and tests replace names on it
    (ps, started, command_of, stop_group, group_alive, WAIT), and a call made here reaches
    what they put there."""
    from . import launcher
    return launcher


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
            self.rows = listing(_launcher().ps(*LISTING))
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
        return _launcher().ps('-o', 'pid=', '-p', str(os.getpid())) is not None
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


def started(pid):
    rows = _inspected()
    if rows is not _OUTSIDE:
        row = rows.get(pid) if rows else None
        return row.started if row else None
    found = _launcher().ps('-o', 'lstart=', '-p', str(pid))
    return found.strip() or None if found else None


def command_of(pid):
    rows = _inspected()
    if rows is not _OUTSIDE:
        row = rows.get(pid) if rows else None
        return row.command.strip() or None if row else None
    found = _launcher().ps('-ww', '-o', 'command=', '-p', str(pid))
    return found.strip() or None if found else None


def alive(pid):
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    # A finished process its parent has not collected yet is not running.
    rows = _inspected()
    if rows is _OUTSIDE:
        status = _launcher().ps('-o', 'stat=', '-p', str(pid))
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
    table = _launcher().ps('-axo', 'pgid=,stat=')
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
            same = running and bool(job.get('started')) and _launcher().started(pid) == job['started'] \
                and assistant(_launcher().command_of(pid) or '') == job['assistant']
        if running:
            if not same:
                continue
            try:
                group = os.getpgid(pid)
            except ProcessLookupError:
                group = None
            if group == pid and group != own:
                _launcher().stop_group(pid)
            elif group is not None:
                stop_one(pid)
        with _live():
            if not alive(pid):
                gone.append(job)
    return gone


def stop_one(pid):
    with _live():
        for signalled, wait in ((signal.SIGTERM, _launcher().WAIT), (signal.SIGKILL, 5)):
            try:
                os.kill(pid, signalled)
            except (ProcessLookupError, PermissionError):
                return
            if waited_out(lambda: alive(pid), wait):
                return


def describe_job(job):
    name = job['assistant'] + (' job ' + job['label'] if job.get('label') else '')
    return f"{name} ({duration(job['seconds'])})"


def stop_group(pid):
    """Stop a recorded process group, led by `pid`, until none of it is running."""
    if pid == os.getpgrp():
        return
    with _live():
        for signalled, wait in ((signal.SIGTERM, _launcher().WAIT), (signal.SIGKILL, 5)):
            try:
                os.killpg(pid, signalled)
            except (ProcessLookupError, PermissionError):
                return
            if waited_out(lambda: _launcher().group_alive(pid), wait):
                return
