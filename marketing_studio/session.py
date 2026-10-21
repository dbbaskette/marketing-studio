"""Start, stop and restart Marketing Studio and its studios from the command line.

The running Marketing Studio answers over its private control socket (see control.py).
Without one, only studios recorded in this data root's run/ folder are ever touched,
and only while this command holds the home lock, so a running Marketing Studio's own
studios can never be mistaken for ones left behind.
"""
import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import time

from . import catalog, control, network, shared, state
from .errors import WorkspaceError
from .launcher import Launcher, describe_job, end_jobs, launch_problem
from .page import Home

ROOT = Path(__file__).resolve().parents[1]
READY = 60   # seconds Marketing Studio has to start, or to stop with its studios


def name(identifier):
    return catalog.STUDIOS[identifier][0]


def flag(identifier):
    return '--' + identifier[0] + 's'


def working(busy):
    """Why a stop is refused: [(identifier, jobs)] with at least one job."""
    lines = [f'{name(identifier)} is working: ' + ', '.join(map(describe_job, jobs)) + '.'
             for identifier, jobs in busy]
    many = sum(len(jobs) for _, jobs in busy) > 1
    advice = ('Their' if many else 'Its') + ' work so far would be lost. Wait for it, or add --force.'
    return ' '.join(lines + [advice]) if len(lines) == 1 else '\n'.join(lines + [advice])


# --- inside the running Marketing Studio ----------------------------------------------

def snapshot(launcher, desk, lan):
    """What the 'state' command answers: this same-user socket's caller may hold the link."""
    studios = []
    for identifier in catalog.STUDIOS:
        if launcher.process(identifier):
            studios.append({'id': identifier, 'name': name(identifier),
                            'jobs': launcher.jobs(identifier),
                            'earlier': not launcher.running(identifier)})
    phone = lan.snapshot() if lan else None
    return {'pid': os.getpid(), 'port': desk.port, 'url': desk.url,
            'lan': lan.host if lan else None, 'phone': phone['url'] if phone else None,
            'studios': studios}


def start_studio(launcher, identifier):
    values, problem = shared.read()
    if problem:
        raise WorkspaceError(problem)
    if not Home.configured(values):
        raise WorkspaceError('Finish shared setup before starting a studio: marketing-studio setup')
    was = launcher.running(identifier)
    launcher.open(identifier, state.read(), values)
    return {'started': not was}


def stop_studio(launcher, identifier, force):
    jobs = launcher.jobs(identifier)
    if jobs and not force:
        return {'error': working([(identifier, jobs)]), 'jobs': jobs}
    stopped = launcher.stop(identifier)
    if not jobs:
        return {'stopped': stopped, 'jobs': []}
    # Assistants run in their own sessions, so stopping the studio may leave them running.
    gone = end_jobs(jobs)
    return {'stopped': stopped, 'jobs': gone, 'left': [job for job in jobs if job not in gone]}


# --- from the command line ------------------------------------------------------------

def ask(action):
    """The running Marketing Studio's reply, or None when none answers."""
    return control.request(state.data_root(), action)


class EarlierVersion(WorkspaceError):
    """A Marketing Studio from before start and stop is running."""


def current():
    """The running Marketing Studio's state, or None."""
    found = ask({'command': 'state'})
    if found is not None and 'error' in found:
        raise EarlierVersion('This Marketing Studio is from an earlier version and cannot be managed '
                             'from the command line. Stop its terminal with Ctrl-C, then run: '
                             'marketing-studio start')
    return found


def quietly_current():
    try:
        return current()
    except (OSError, ValueError, WorkspaceError):
        return None  # It is starting, stopping, or too old to answer.


def lock_held():
    target = state.data_root() / 'home.lock'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(stream, fcntl.LOCK_UN)
        return False


@contextmanager
def left_behind():
    """A launcher for studios left running, while no Marketing Studio can start."""
    target = state.data_root() / 'home.lock'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkspaceError('Marketing Studio is starting or stopping. Try again shortly.') from exc
        yield Launcher()


def serving(lan=None, port=0):
    return (['--lan'] + ([] if lan == 'auto' else [lan]) if lan else []) + (['--port', str(port)] if port else [])


def start_home(arguments):
    """Start Marketing Studio in the background and wait until it answers."""
    log = state.data_root() / 'logs' / 'home.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.chmod(log, 0o600)
    try:
        # A pipe, never a terminal: the server writes no key to its log.
        process = subprocess.Popen([sys.executable, str(ROOT / 'marketing-studio'), 'serve', *arguments],
                                   stdin=subprocess.DEVNULL, stdout=descriptor, stderr=descriptor,
                                   start_new_session=True, cwd=ROOT)
    finally:
        os.close(descriptor)
    deadline = time.monotonic() + READY
    while time.monotonic() < deadline:
        found = quietly_current()
        if found:
            return found
        if process.poll() is not None:
            raise WorkspaceError(launch_problem('Marketing Studio stopped before it was ready.', log))
        time.sleep(.2)
    Launcher.stop_process(process)
    raise WorkspaceError(launch_problem('Marketing Studio took too long to start.', log))


def stop_home():
    """Ask Marketing Studio to shut down and wait until it has closed everything."""
    try:
        ask({'command': 'shutdown'})
    except (OSError, ValueError):
        pass  # It closed the connection while stopping.
    deadline = time.monotonic() + READY
    while time.monotonic() < deadline:
        if not lock_held():
            return
        time.sleep(.2)
    raise WorkspaceError('Marketing Studio is still stopping. Check again with: marketing-studio status')


def differs(found, lan, port):
    """Why a running Marketing Studio does not match the asked LAN address or port."""
    problems = []
    if port and port != found['port']:
        problems.append(f"on port {found['port']}")
    if lan:
        wanted = network.discover_address() if lan == 'auto' else network.private_address(lan)
        if found.get('lan') != wanted:
            problems.append('without phone access' if not found.get('lan')
                            else f"with phone access on {found['lan']}")
    if not problems:
        return None
    again = ' '.join(['marketing-studio restart --all', *serving(lan, port)])
    return ('Marketing Studio is already running ' + ' and '.join(problems) + '. To change that, run: ' + again)
