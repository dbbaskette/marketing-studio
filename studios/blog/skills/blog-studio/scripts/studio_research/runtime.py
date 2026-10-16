"""The harness-research command line, called from Python.

What a caller needs to know
---------------------------
    research = Research()                     # finds the installed runtime, or refuses
    status = research.plan(project, project / 'research' / 'plan.json', allow_web=False)
    status = research.record(project, status['run'], 'question-id', finding)
    status = research.status(project)
    research.version()                        # '0.8.1'

- Every call returns the command's own JSON: `run`, `status` (`not-started`, `in-progress`,
  `complete` or `stale`), `pending`, `unresolved`, `staleItems`, `completed`, `total`,
  `sourceGaps`, `carried` after a plan, and where the record and the `report` are.
- When the command says no, Refused is raised: a ResearchError, which is a ValueError, carrying
  the one line it printed in `line`. `busy` is true when another save held its lock.
- The runtime is the folder HARNESS_RESEARCH_RUNTIME names when that is set, else the first
  usual install location that holds one: harness-research's own installer folder, then each
  assistant's skills folder. Node 20 or newer runs it.
- `Research(run=...)` replaces how the command is run. STAND_IN (tests only) names a Python
  script that answers as the command does, run with this Python in place of Node and the
  skill; stand_in.py is that script.
- Part of the shared research component (docs/research-component-spec.md). Started from
  Training Studio's runner/research.py and runner/companion.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

VARIABLE = 'HARNESS_RESEARCH_RUNTIME'
SCRIPT = Path('scripts') / 'harness-research.mjs'
LOCK = Path('.harness-research') / 'research.lock'
TIMEOUT = 120
BUSY = 'Research storage is busy'
STAND_IN = 'STUDIO_RESEARCH_STAND_IN'
SHARED = (
    ('Library', 'Application Support', 'Harness Research'),
    ('.local', 'share', 'harness-research'),
)
SKILLS = (('.claude', 'skills'), ('.agents', 'skills'), ('.cursor', 'skills'))


class ResearchError(ValueError):
    """A refusal said in one sentence a person can read."""


class Refused(ResearchError):
    """harness-research said no. `line` is the one line it gave."""

    def __init__(self, line: str):
        super().__init__(f'harness-research refused: {line}')
        self.line = line

    @property
    def busy(self) -> bool:
        """True when another save was in progress, so trying again may work."""
        return self.line.startswith(BUSY)


def locations(home: Path | None = None) -> list[Path]:
    """Every folder that may hold an installed harness-research. The override, when set, is
    the only place looked."""
    override = os.environ.get(VARIABLE)
    if override:
        return [Path(override).expanduser()]
    user = home or Path.home()
    return [user.joinpath(*parts) / 'current' for parts in SHARED] + [
        user.joinpath(*parts) / 'harness-research' for parts in SKILLS
    ]


def find_runtime(home: Path | None = None) -> Path:
    """The installed harness-research, with links followed so one version is used throughout."""
    for place in locations(home):
        if (place / SCRIPT).is_file():
            return place.resolve()
    if os.environ.get(VARIABLE):
        raise ResearchError(
            f'{VARIABLE} names {os.environ[VARIABLE]}, which does not hold harness-research. '
            'Point it at the installed skill, or unset it.'
        )
    raise ResearchError(
        'The harness-research skill is not installed on this computer, so research cannot run. '
        'Install it, then try again.'
    )


def unlock(project: Path) -> bool:
    """Remove the lock a save left behind when its process died. True when there was one.
    Only for a caller that knows no save is in progress."""
    lock = Path(project) / LOCK
    found = lock.is_file()
    lock.unlink(missing_ok=True)
    return found


def run_command(command: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run the command line once: (exit code, standard output, standard error). It runs in a
    process group of its own, which is ended whole when it takes longer than TIMEOUT."""
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=hasattr(os, 'killpg'),
        )
    except OSError as failure:
        raise ResearchError(f'harness-research could not be started ({failure}).') from None
    try:
        out, err = process.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        if hasattr(os, 'killpg'):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.communicate()
        raise ResearchError(f'harness-research did not answer in {TIMEOUT} seconds.') from None
    text = lambda data: data.decode('utf-8', errors='replace')  # noqa: E731
    return process.returncode, text(out), text(err)


class Research:
    """The plan, record and status commands of one installed harness-research."""

    def __init__(self, runtime: Path | None = None, run=None):
        self.run = run or run_command
        stand_in = None if run or runtime else os.environ.get(STAND_IN)
        if stand_in:
            self.runtime, self.node, self.script = Path(stand_in), sys.executable, Path(stand_in)
            return
        self.runtime = Path(runtime) if runtime else find_runtime()
        self.script = self.runtime / SCRIPT
        self.node = 'node' if run else shutil.which('node')
        if self.node is None:
            raise ResearchError(
                'harness-research needs Node.js 20 or newer, which was not found on this '
                'computer. Install it, then try again.'
            )

    def _call(self, *args: str) -> str:
        code, out, err = self.run([self.node, str(self.script), *args])
        if code != 0:
            lines = [line.strip() for line in err.splitlines() if line.strip()]
            raise Refused(lines[-1] if lines else f'it ended with exit code {code}')
        return out

    def _json(self, *args: str) -> dict:
        said = self._call(*args)  # outside the try: Refused is a ValueError
        try:
            found = json.loads(said)
        except ValueError:
            found = None
        if not isinstance(found, dict):
            raise ResearchError(
                'harness-research answered with something other than the JSON it should. '
                'Check that it is installed whole.'
            )
        return found

    def version(self) -> str:
        """The runtime's version, as it states it."""
        return self._call('--version').strip().rpartition(' ')[2]

    def plan(self, project: Path, file: Path, allow_web: bool = False) -> dict:
        """Hand over a plan. The same plan again continues its run; a changed one starts a new
        run that keeps the findings of questions defined exactly as before, when the topic,
        purpose, scope, sources and inputs are unchanged, listed in `carried`. `allow_web`
        permits a plan that widens supplied-only research to the public web."""
        extra = ['--allow-web'] if allow_web else []
        return self._json('plan', '--project', str(project), '--file', str(file), *extra)

    def record(self, project: Path, run: str, item: str, finding: dict) -> dict:
        """Record one question's finding in a run. A `headline` is passed on when there is one."""
        wanted = {key: finding.get(key) for key in ('status', 'summary', 'limits', 'evidence')}
        if finding.get('headline'):
            wanted['headline'] = finding['headline']
        handle, name = tempfile.mkstemp(suffix='.json', prefix='finding-')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(wanted, stream)
            return self._json(
                'record', '--project', str(project), '--file', name, '--run', run, '--item', item
            )
        finally:
            Path(name).unlink(missing_ok=True)

    def status(self, project: Path) -> dict:
        """Where the research stands. The command rewrites its report when asked."""
        return self._json('status', '--project', str(project))
