"""Pinned companion installation shared by suite and standalone installers."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from types import FunctionType

InstallError = ValueError
VERSION = re.compile(r'^\d+\.\d+\.\d+$')
HEX = {'commit': re.compile(r'^[0-9a-f]{40}$'), 'sha256': re.compile(r'^[0-9a-f]{64}$')}
NODE_NEEDED = 20
HARNESS = {'claude': 'Claude Code', 'codex': 'Codex'}


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def skill_link(home, harness):
    return home / ('.agents' if harness == 'codex' else '.claude') / 'skills' / 'studio'


def ask(command: tuple, cwd: Path | None = None, timeout: int = 20) -> tuple[int, str] | None:
    """Run one command that only reports: (its exit code, what it printed). None when the
    program is not on this computer."""
    try:
        done = subprocess.run(list(command), capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL, cwd=cwd)
    except FileNotFoundError:
        return None
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''
    return done.returncode, (done.stdout or done.stderr).strip()


def node_version() -> str | None:
    found = ask(('node', '--version'))
    return found[1] if found and found[0] == 0 else None


def node_is_enough(node: str | None) -> bool:
    digits = (node or '').lstrip('v').split('.')[0]
    return digits.isdigit() and int(digits) >= NODE_NEEDED


def read_pins(path: Path) -> dict:
    """The pinned companions: {name: {repository, version, commit, sha256, stub, installer}}."""
    try:
        kept = json.loads(path.read_text(encoding='utf-8'))
        pins = kept['companions']
        if kept['schema'] != 1 or not isinstance(pins, dict):
            raise ValueError
        for name, pin in pins.items():
            for key in ('repository', 'version', 'commit', 'sha256', 'stub', 'installer'):
                if not isinstance(pin[key], str) or not pin[key]:
                    raise ValueError
            inside = [Path(pin[key]) for key in ('stub', 'installer')]
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name) \
                    or not VERSION.match(pin['version']) \
                    or any(not pattern.match(pin[key]) for key, pattern in HEX.items()) \
                    or any(part.is_absolute() or '..' in part.parts for part in inside):
                raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise InstallError(f'{path} does not say which companion skills to install, or says '
                           'it in a way this installer does not read. Get this repository '
                           'again.')
    return pins


def as_tuple(version: str) -> tuple:
    return tuple(int(part) for part in version.split('.'))


def tree_digest(folder: Path) -> str:
    """One SHA-256 for every file under a folder: each file's path and its own SHA-256, in
    order. A link, or anything that is not a plain file, is refused."""
    lines = []
    for path in sorted(folder.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise InstallError(f'{path.relative_to(folder)} is a link or a special file, '
                               'which a companion skill never holds.')
        if path.is_file():
            lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  '
                         + path.relative_to(folder).as_posix() + '\n')
    return hashlib.sha256(''.join(lines).encode()).hexdigest()


def git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run git without anyone's sign-in being asked for: (exit code, what it said)."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('GIT_') or key.startswith('GIT_CONFIG_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    try:
        done = subprocess.run(['git', *args], cwd=cwd, env=env, capture_output=True, text=True,
                              timeout=300, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise InstallError('git is needed to fetch a companion skill, and was not found.')
    except (OSError, subprocess.TimeoutExpired) as failure:
        return 1, type(failure).__name__
    return done.returncode, (done.stdout if done.returncode == 0 else done.stderr).strip()


def fetch_revision(repository: str, revision: str, into: Path) -> str:
    """Put one revision of a repository into an empty folder as plain files, with nothing of
    git left in it. Returns the commit that was fetched."""
    for step in (['init', '-q'],
                 ['fetch', '-q', '--depth', '1', '--no-tags', repository, revision],
                 ['-c', 'core.autocrlf=false', '-c', 'advice.detachedHead=false', 'checkout',
                  '-q', '--detach', 'FETCH_HEAD']):
        code, said = git(step, into)
        if code != 0:
            why = said.splitlines()[-1] if said else 'git gave no reason'
            raise InstallError(f'{revision} could not be fetched from {repository}: {why}')
    code, commit = git(['rev-parse', 'HEAD'], into)
    if code != 0 or not HEX['commit'].match(commit):
        raise InstallError(f'What was fetched from {repository} could not be read.')
    shutil.rmtree(into / '.git')
    return commit


def fetch_companion(name: str, pin: dict, root: Path) -> Path:
    """The companion's repository at its pinned revision, checked, in this installer's own
    folder. Refuses anything that is not exactly what companions.json names."""
    kept = root / 'companions' / name / pin['commit'][:12]
    if kept.is_dir():
        if tree_digest(kept) != pin['sha256']:
            raise InstallError(f'{kept} has changed since it was fetched. Remove that folder '
                               'and run this again.')
        return kept
    kept.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix='.pending-', dir=kept.parent))
    try:
        commit = fetch_revision(pin['repository'], pin['commit'], pending)
        if commit != pin['commit'] or tree_digest(pending) != pin['sha256']:
            raise InstallError(f"What {pin['repository']} gave for {name} {pin['version']} "
                               'is not what this installer expects, file for file. None of '
                               'it was kept and none of it was run.')
        stub = pending / pin['stub']
        named = re.search(r'^name: *(\S+) *$', stub.read_text(encoding='utf-8'), re.MULTILINE) \
            if stub.is_file() else None
        if not named or named.group(1) != name or not (pending / pin['installer']).is_file():
            raise InstallError(f'{name} at its pinned revision does not hold the entry and '
                               'the installer this installer expects. None of it was run.')
        os.replace(pending, kept)
    finally:
        shutil.rmtree(pending, ignore_errors=True)
    return kept


def companion_found(home: Path, harnesses: list[str], name: str) -> dict:
    """The version of a companion each assistant has: None when it has none, '' when one is
    there whose version cannot be read."""
    found = {}
    for harness in harnesses:
        skill = skill_link(home, harness).parent / name
        if not skill.exists() and not skill.is_symlink():
            found[harness] = None
            continue
        try:
            version = json.loads((skill / 'package.json').read_text(encoding='utf-8'))['version']
        except (OSError, ValueError, KeyError, TypeError):
            version = ''
        found[harness] = version if isinstance(version, str) and VERSION.match(version) else ''
    return found


def wanting(found: dict, wanted: str) -> list[str]:
    """The assistants that have no copy of a companion, or an older one than is pinned."""
    return [harness for harness, version in found.items()
            if version is None or (version and as_tuple(version) < as_tuple(wanted))]


def companion_command(node: str, checkout: Path, pin: dict, home: Path) -> list[str]:
    """How a companion's own installer is run. Only a home that is not the person's own is
    named to it; otherwise it is left to its own defaults."""
    command = [node, str(checkout / pin['installer'])]
    return command if home == Path.home().resolve() else [*command, '--home', str(home)]


def run_companion(name: str, pin: dict, checkout: Path, home: Path,
                  harnesses: list[str]) -> dict:
    """Run a companion's own installer from its checked copy, then look at what it left."""
    node = shutil.which('node')
    if not node:
        return {'state': 'failed', 'detail': 'Node was not found, and its installer runs on '
                                             'Node.'}
    env = dict(os.environ)
    if home != Path.home().resolve():
        env.update({'HOME': str(home), 'USERPROFILE': str(home)})
        env.pop('CLAUDE_CONFIG_DIR', None)
    try:
        done = subprocess.run(companion_command(node, checkout, pin, home), env=env,
                              capture_output=True, text=True, timeout=900,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as failure:
        return {'state': 'failed', 'detail': f'its installer did not finish '
                                             f'({type(failure).__name__}).'}
    if done.returncode != 0:
        said = (done.stderr or done.stdout).strip().splitlines()
        return {'state': 'failed', 'detail': 'its installer said: '
                + (said[-1][:300] if said else 'nothing, and stopped.')}
    try:
        said = json.loads(done.stdout)
    except ValueError:
        said = {}
    outcome = {'state': 'installed'}
    if isinstance(said, dict) and isinstance(said.get('next'), str):
        outcome['next'] = said['next'][:300]   # what its installer says is still to do
    stub = (checkout / pin['stub']).read_bytes()
    found = companion_found(home, harnesses, name)
    for harness in harnesses:
        entry = skill_link(home, harness).parent / name / 'SKILL.md'
        if wanting({harness: found[harness]}, pin['version']) or not entry.is_file() \
                or entry.read_bytes() != stub:
            return {'state': 'failed', 'detail': 'its installer finished, but did not leave '
                    f'the entry this installer checked for {HARNESS[harness]}.'}
    return outcome


def bring_companions(home: Path, root: Path, harnesses: list[str], pins: dict, agree,
                     state: dict, declined: str | None = None) -> dict:
    """Bring each companion that is missing or older than its pin, when the person agrees.
    One that is as new or newer is left alone. Nothing here undoes the studio's own
    installation: what goes wrong is reported. `declined` says why one was not agreed to."""
    outcomes = {}
    for name, pin in pins.items():
        found = companion_found(home, harnesses, name)
        outcome = {'wanted': pin['version'], 'found': found, 'state': 'left alone'}
        if wanting(found, pin['version']):
            if not node_is_enough(node_version()):
                outcome.update({'state': 'failed', 'detail': f'its installer needs Node '
                                f'{NODE_NEEDED} or newer.'})
            elif not agree(name, pin, found):
                outcome['state'] = 'waiting'
                if declined:
                    outcome['why'] = declined
            else:
                try:
                    checkout = fetch_companion(name, pin, root)
                    outcome.update(run_companion(name, pin, checkout, home, harnesses))
                except InstallError as refusal:
                    outcome.update({'state': 'refused', 'detail': str(refusal)})
                outcome['found'] = companion_found(home, harnesses, name)
                if outcome['state'] == 'installed':
                    state.setdefault('companions', {})[name] = {
                        'version': pin['version'], 'commit': pin['commit'],
                        'installed_at': now()}
        outcomes[name] = outcome
    return outcomes

SHARED = ('read_pins', 'as_tuple', 'tree_digest', 'git', 'fetch_revision', 'fetch_companion', 'companion_found', 'wanting', 'companion_command', 'run_companion', 'bring_companions')


def bind(namespace):
    """Retain each native installer's public globals and test injection points."""
    for name in SHARED:
        original = globals()[name]
        function = FunctionType(original.__code__, namespace, name, original.__defaults__, original.__closure__)
        function.__doc__ = original.__doc__
        function.__kwdefaults__ = original.__kwdefaults__
        namespace[name] = function
