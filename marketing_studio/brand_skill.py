"""The brand skill the studios use, whether it is Harness Brand, and running its command.

What a caller needs to know
---------------------------
    found = brand_skill.find(chosen, data)    # Found, or WorkspaceError with the one line
    code, out, err = brand_skill.run(found.command + ['pack', 'check', pack, '--json'])
    brand_skill.answer(found, ['pack', 'check', pack, '--json'])   # its JSON, exit code aside

- The brand skill in use is found as the studios find it: the folder Shared settings name
  (`brand.skill`), else BRAND_SKILL_RUNTIME, else the first installed skill whose command
  lists brands (in `~/Library/Application Support/*/current`, `~/.local/share/*/current`,
  and the Claude Code, `~/.agents` and Cursor skills folders), else an installed Harness
  Brand, which lists no brands until it has a pack. Its command is the script in its
  `scripts` folder named for the skill, run only when the folder holds a SKILL.md and the
  script mentions brands, and then with Node.
- `find` refuses in one sentence when there is no Node, no brand skill, or the brand skill
  in use is not Harness Brand; that sentence says how to get Harness Brand. Nothing is
  installed or changed.
- `run` runs a command once, in a process group of its own that is ended when it finishes,
  when its time runs out or when `stop` is set (then Stopped is raised). `each` is given
  each line it prints as text.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import WorkspaceError

VARIABLE = 'BRAND_SKILL_RUNTIME'
SKILL = 'Harness Brand'
WHERE = 'https://github.com/dbbaskette/harness-brand-skill'
NAMED = re.compile(r'^[\w.-]{1,80}$')
NUMBER = re.compile(r'^\d+\.\d+\.\d+$')
ASK_SECONDS = 20
OUTPUT_LIMIT = 4_000_000
SHARED = (('Library', 'Application Support'), ('.local', 'share'))
SKILLS = (('.claude', 'skills'), ('.agents', 'skills'), ('.cursor', 'skills'))
GET = (f'Brands are made with {SKILL}: install it from {WHERE}, choose it under Shared '
       'settings, Brand, if another brand skill is installed too, and open Brands again.')


class Stopped(Exception):
    """A command was ended because the person stopped what it was part of."""


@dataclass(frozen=True)
class Found:
    runtime: Path          # the skill's folder, with links followed
    script: Path           # its command
    name: str              # what it calls itself, without its version
    version: str | None
    node: str
    data: Path | None = None

    @property
    def command(self) -> list[str]:
        return [self.node, str(self.script)]

    def guide(self, name: str) -> str:
        """One of the skill's own documents, such as references/building-a-pack.md."""
        path = self.runtime / name
        try:
            return path.read_text(encoding='utf-8')
        except OSError as failure:
            raise WorkspaceError(f'{SKILL} at {self.runtime} has no {name}, so the assistant '
                                 'cannot be told how to build a pack. Install it whole.') from failure


# --- running a command -----------------------------------------------------------------

def run(command, cwd=None, env=None, seconds=120, stop=None, stdin='', each=None,
        said='Harness Brand'):
    """Run once: (exit code, standard output, standard error). Ends everything it started."""
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
    except OSError as failure:
        raise WorkspaceError(f'{said} could not be started ({failure}).') from failure
    printed, complained = [], []
    oversized = threading.Event()
    kept_bytes = [0]
    output_lock = threading.Lock()

    def feed():
        try:
            process.stdin.write(stdin.encode('utf-8'))
            process.stdin.close()
        except OSError:
            pass

    def read(stream, kept, tell):
        while line := stream.readline(65_537):
            with output_lock:
                kept_bytes[0] += len(line)
                if kept_bytes[0] > OUTPUT_LIMIT:
                    oversized.set()
                else:
                    kept.append(line)
            if oversized.is_set():
                continue
            if tell is not None:
                try:
                    tell(line.decode('utf-8', 'replace'))
                except Exception:   # a listener's failure never stops the command
                    pass
        stream.close()

    threads = [threading.Thread(target=feed, daemon=True),
               threading.Thread(target=read, args=(process.stdout, printed, each), daemon=True),
               threading.Thread(target=read, args=(process.stderr, complained, None), daemon=True)]
    for thread in threads:
        thread.start()
    limit, late = time.monotonic() + seconds, False
    try:
        while process.poll() is None:
            if oversized.is_set() or (stop is not None and stop.is_set()):
                break
            if time.monotonic() >= limit:
                late = True
                break
            time.sleep(0.05)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        process.wait()
        for thread in threads:
            thread.join(2)
    if stop is not None and stop.is_set():
        raise Stopped(f'{said} was stopped before it finished.')
    if oversized.is_set():
        raise WorkspaceError(f'{said} returned too much output, so it was stopped before anything was kept.')
    if late:
        raise WorkspaceError(f'{said} did not finish in {seconds:g} seconds, so it was stopped.')
    text = lambda parts: b''.join(parts).decode('utf-8', 'replace')
    return process.returncode, text(printed), text(complained)


def said(err: str, code: int) -> str:
    """What the command said was wrong, in its own sentences, without its usage."""
    lines = []
    for line in (line.strip() for line in err.splitlines()):
        if line.startswith('Usage:'):
            break
        if line and not line.startswith(('(node:', '(Use `node')):
            lines.append(line)
    return ' '.join(lines) or f'It ended with exit code {code}.'


def environment(data=None):
    # This override is only for the explicit Brands command, never studio launch.
    env = dict(os.environ)
    env.pop('HARNESS_BRAND_DATA', None)
    if data is not None:
        env['HARNESS_BRAND_DATA'] = str(data)
    return env


def answer(found: Found, args, env=None, seconds=120, stop=None, each=None):
    """The JSON a command printed, whatever its exit code (pack check prints its problems
    and fails). Refuses with what it said when it printed none."""
    code, out, err = run(found.command + list(args), env=env if env is not None else environment(found.data), seconds=seconds, stop=stop,
                         each=each)
    try:
        return code, json.loads(out)
    except ValueError:
        raise WorkspaceError(said(err, code)) from None


# --- finding the brand skill -----------------------------------------------------------

def locations(home=None):
    """Every folder that may be an installed brand skill. BRAND_SKILL_RUNTIME, when set, is
    the only place looked."""
    if os.environ.get(VARIABLE):
        return [Path(os.environ[VARIABLE]).expanduser()]
    user = Path(home) if home else Path.home()

    def inside(folder):
        try:
            return sorted(folder.iterdir())
        except OSError:
            return []
    return [place / 'current' for parts in SHARED for place in inside(user.joinpath(*parts))] \
        + [place for parts in SKILLS for place in inside(user.joinpath(*parts))]


def companion(folder: Path, *names):
    """The skill's command: the script named for it that mentions brands, or None."""
    try:
        if not (folder / 'SKILL.md').is_file():
            return None
        package = json.loads((folder / 'package.json').read_text(encoding='utf-8')).get('name')
    except (OSError, ValueError, AttributeError):
        package = None
    for name in (package, folder.name, *names):
        if not isinstance(name, str) or not NAMED.match(name):
            continue
        script = folder / 'scripts' / f'{name}.mjs'
        try:
            with open(script, encoding='utf-8', errors='replace') as stream:
                return script if 'brands' in stream.read(200_000) else None
        except OSError:
            continue
    return None


def _named(node, script, otherwise):
    try:
        code, out, _ = run([node, str(script), 'version'], seconds=ASK_SECONDS)
    except WorkspaceError:
        code, out = 1, ''
    name, _, number = (out.strip().partition('\n')[0] if code == 0 else '').rpartition(' ')
    number = number.removeprefix('v')
    return name.strip()[:80] or otherwise, number if NUMBER.match(number) else None


def _lists(node, script, env):
    try:
        code, out, _ = run([node, str(script), 'brands', '--json'], env=env, seconds=ASK_SECONDS)
        listed = json.loads(out) if code == 0 else None
    except (WorkspaceError, ValueError):
        return False
    return isinstance(listed, list) and bool(listed)


def find(chosen=None, data=None, home=None, which=shutil.which):
    """The brand skill in use, when it is Harness Brand. `chosen` is Shared settings'
    brand skill folder, `data` the brands folder its command is told."""
    node = which('node')
    if not node:
        raise WorkspaceError(f'{SKILL} needs Node.js 20 or newer, which was not found on this '
                             'computer. Install it, then open Brands again.')
    env = environment(data)
    places = [Path(chosen).expanduser()] if chosen else locations(home)
    candidates, seen = [], set()
    for place in places:
        try:
            folder = place.resolve()
        except (OSError, RuntimeError):
            continue
        if folder in seen:
            continue
        seen.add(folder)
        hints = [name for name in (place.name, place.parent.name) if name != 'current'] or ['brand']
        script = companion(folder, *hints)
        if script is not None:
            candidates.append((folder, script, hints[0]))
    if not candidates:
        where = f'in {chosen}' if chosen else 'on this computer'
        raise WorkspaceError(f'No brand skill was found {where}. {GET}')
    in_use = None
    if chosen or len(candidates) == 1:
        in_use = candidates[0]
    else:
        in_use = next((one for one in candidates if _lists(node, one[1], env)), None)
    if in_use is None:
        # None lists brands: an installed Harness Brand with no pack yet is the one.
        for one in candidates:
            name, version = _named(node, one[1], one[2])
            if name.startswith(SKILL):
                return Found(one[0], one[1], name, version, node, data)
        in_use = candidates[0]
    name, version = _named(node, in_use[1], in_use[2])
    if not name.startswith(SKILL):
        raise WorkspaceError(f'The brand skill in use is {name}, not {SKILL}. {GET}')
    return Found(in_use[0], in_use[1], name, version, node, data)
