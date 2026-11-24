"""Finding the installed Harness Research and running one of its helper commands.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here, and keeps snapshot, runtime_for and matching itself, since
callers and tests replace them there."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


# Where the Harness Research installer keeps `current` and versions/<version>-<digest>.
SHARED = (Path('Library/Application Support/Harness Research'), Path('.local/share/harness-research'))


# Harness Research 1.0.1 and newer exit 1 for a needs-revision review and for stale
# evidence while still printing the result. Callers judge that result's status.
RESULTS = {('synthesis', 'review'), ('synthesis', 'verify'), ('synthesis', 'status')}


def answered(args, code, out):
    """True when a command that exited 1 still printed its JSON result."""
    if code != 1 or tuple(args[:2]) not in RESULTS:
        return False
    try:
        return isinstance(json.loads(out), dict)
    except (TypeError, ValueError):
        return False


HELPER_SECONDS = 120   # the longest one helper command may take
HELPER_TICK = 0.2      # seconds between looks at whether a running helper command was stopped
HELPER_STOPPED = 'Research stopped; accepted evidence is kept.'


def run_helper(command, seconds=HELPER_SECONDS, cancelled=None):
    """Run one Harness Research helper command where no studio call runs it (a studio's own
    call runs it through its companion.run_command): a CompletedProcess with text output.

    `cancelled` is the research run's Stop, asked while the command runs. A command running
    when Stop comes is ended with everything it started (its process group), and
    InterruptedError is raised, as a stopped research run raises. A command started once
    Stop has come, such as the one that records the stop, runs to its end. A command that
    takes longer than `seconds` is ended and TimeoutExpired raised, as before."""
    if cancelled is None or cancelled():
        return subprocess.run(command, capture_output=True, text=True, timeout=seconds,
                              stdin=subprocess.DEVNULL)
    grouped = hasattr(os, 'killpg')   # elsewhere only the command itself can be ended
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=grouped)
    finished = False
    deadline = time.monotonic() + seconds
    try:
        while True:
            try:
                out, err = process.communicate(
                    timeout=max(0.0, min(HELPER_TICK, deadline - time.monotonic())))
                finished = True
                return subprocess.CompletedProcess(command, process.returncode, out, err)
            except subprocess.TimeoutExpired:
                if cancelled():
                    raise InterruptedError(HELPER_STOPPED) from None
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(command, seconds) from None
    finally:
        # A command that did not finish (stopped, late or failed) leaves nothing running:
        # it is ended with everything it started. One that finished is left as it ended.
        if not finished:
            try:
                if grouped:
                    os.killpg(process.pid, signal.SIGKILL)
                elif process.poll() is None:
                    process.kill()
            except (ProcessLookupError, PermissionError):
                pass
            process.communicate()


def capability(runtime):
    """The schema, version and digest of the helper files a run depends on, or None for a
    helper without synthesis."""
    package = json.loads((runtime / 'package.json').read_text())
    if not (runtime / 'scripts/lib/synthesis-cli.mjs').is_file():
        return None
    relevant = sorted([runtime / 'package.json', *runtime.glob('scripts/**/*.mjs'),
                       *runtime.glob('references/*')])
    digest = hashlib.sha256()
    for path in relevant:
        if path.is_file():
            digest.update(str(path.relative_to(runtime)).encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {'schema': 2, 'version': package['version'], 'digest': digest.hexdigest()}


def stable(value):
    """What a saved helper capability says that outlives an update of Harness Research: its
    schema or protocol, never a version or a digest of the installed files. Identities that
    decide whether finished research is still current are made of this, so an update never
    makes research, its sections or its review run again."""
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if key not in ('version', 'digest')}


def stable_place(place):
    """`place`, said through its installer's `current` link when it is a version folder of one,
    else as it was named. This file also runs on its own, so it does not import the shared
    rule in `studio_core.packaging.stable_place`, which this follows."""
    place = Path(place).absolute()
    try:
        resolved = place.resolve()
    except (OSError, RuntimeError):
        return place
    if resolved.parent.name == 'versions':
        current = resolved.parent.parent / 'current'
        try:
            if current.is_symlink() and current.resolve() == resolved:
                return current
        except OSError:
            pass
    return place


def find_runtime():
    override = os.environ.get('HARNESS_RESEARCH_RUNTIME')
    roots = [Path(override)] if override else [
        *(Path.home() / root / 'current' for root in SHARED),
        Path.home() / '.agents/skills/harness-research',
        Path.home() / '.claude/skills/harness-research',
        Path.home() / '.cursor/skills/harness-research',
    ]
    for root in roots:
        if (root / 'scripts/harness-research.mjs').is_file():
            # Its stable address: an update replaces the version folder behind `current`,
            # and a run or a job spec that named that folder would stop working.
            return stable_place(root)
    raise ValueError('Install the shared Harness Research 1.0 or newer before starting synthesis research.')
