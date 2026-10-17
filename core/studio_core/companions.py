"""Companion requirements and verified release locks for all installers."""
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
VERSION = re.compile(r'^\d+\.\d+\.\d+(?:-[a-z0-9]+(?:\.[a-z0-9]+)*)?$')
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
            if as_tuple(pin['version']) < as_tuple(minimum_version(pin)):
                raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise InstallError(f'{path} does not say which companion skills to install, or says '
                           'it in a way this installer does not read. Get this repository '
                           'again.')
    return pins


def as_tuple(version: str) -> tuple:
    return tuple(int(part) for part in version.split('-', 1)[0].split('.'))


def minimum_version(pin: dict) -> str:
    """Exact locks remain readable; a requirement opts into newer stable tags."""
    requirement = pin.get('requirement')
    if requirement is None and 'requirement' not in pin:
        return pin['version']
    match = re.fullmatch(r'>=(\d+\.\d+\.\d+)', requirement) if isinstance(requirement, str) else None
    if not match:
        raise ValueError('Companion requirements must use >= followed by a stable version.')
    return match[1]


def available_version(pin: dict, known: dict) -> str:
    """Choose an allowed version from cached release metadata, without network access."""
    locked = pin['version']
    if not pin.get('requirement') or not isinstance(known, dict):
        return locked
    latest = known.get('latest')
    if not isinstance(latest, str) or not re.fullmatch(r'\d+\.\d+\.\d+', latest) \
            or str(known.get('repository', '')).removesuffix('.git') != pin['repository'].removesuffix('.git'):
        return locked
    return latest if as_tuple(latest) >= max(as_tuple(locked), as_tuple(minimum_version(pin))) else locked


def select_release(pin: dict) -> dict:
    """Look up stable tags only. No source is downloaded and no installer runs."""
    if 'requirement' not in pin:
        return dict(pin)
    code, said = git(['ls-remote', '--tags', '--', pin['repository']], Path(tempfile.gettempdir()))
    if code:
        raise InstallError('Companion releases could not be checked. Retry when the repository is reachable.')
    tags = {}
    for line in said.splitlines():
        parts = line.split()
        if len(parts) != 2 or not HEX['commit'].fullmatch(parts[0]):
            continue
        match = re.fullmatch(r'refs/tags/(v?\d+\.\d+\.\d+)(\^\{\})?', parts[1])
        if match:
            tags.setdefault(match[1], {})['peeled' if match[2] else 'commit'] = parts[0]
    floor = max(as_tuple(pin['version']), as_tuple(minimum_version(pin)))
    candidates = {}
    for tag, values in tags.items():
        version = tag.removeprefix('v')
        if as_tuple(version) < floor:
            continue
        commit = values.get('peeled', values.get('commit'))
        if version in candidates and candidates[version] != commit:
            raise InstallError('Two companion tags name the same version at different commits.')
        candidates[version] = commit
    if not candidates:
        raise InstallError('No stable companion tag satisfies ' + pin['requirement'] + ' and the saved release lock.')
    version = max(candidates, key=as_tuple)
    commit = candidates[version]
    if version == pin['version']:
        if commit != pin['commit']:
            raise InstallError('The locked companion release tag changed. Its saved commit and checksum were preserved.')
        return dict(pin)
    # The old release's checksum must never be attributed to newly selected code.
    return {**pin, 'version': version, 'commit': commit, 'sha256': None}


def lock_companion(name: str, pin: dict) -> dict:
    """Resolve new bytes at the selected immutable commit, without executing code."""
    if pin['sha256'] is not None:
        return dict(pin)
    with tempfile.TemporaryDirectory(prefix='studio-companion-lock-') as temporary:
        folder = Path(temporary)
        commit = fetch_revision(pin['repository'], pin['commit'], folder)
        if commit != pin['commit']:
            raise InstallError('The companion did not resolve to its selected commit.')
        sha256 = tree_digest(folder)  # Refuse links before opening package metadata.
        try:
            version = json.loads((folder / 'package.json').read_text(encoding='utf-8'))['version']
            stub = (folder / pin['stub']).read_text(encoding='utf-8')
        except (OSError, ValueError, KeyError, TypeError) as failure:
            raise InstallError('The companion release has no readable package and entry.') from failure
        named = re.search(r'^name: *(\S+) *$', stub, re.MULTILINE)
        if version != pin['version'] or not named or named.group(1) != name \
                or not (folder / pin['installer']).is_file():
            raise InstallError('The companion release does not match its tag, entry, or installer.')
    return {**pin, 'sha256': sha256}


def resolve_companion(name: str, pin: dict) -> dict:
    """Resolve a requirement into an exact version, commit and source checksum."""
    return lock_companion(name, select_release(pin))


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
    """Resolve allowed stable releases on an explicit install/update, then ask before fetching.
    Installed releases as new or newer than the selected release are left alone. Nothing here undoes the studio's own
    installation: what goes wrong is reported. `declined` says why one was not agreed to."""
    outcomes = {}
    for name, original in pins.items():
        pin = original
        found = companion_found(home, harnesses, name)
        outcome = {'wanted': pin['version'], 'found': found, 'state': 'left alone'}
        if declined not in ('skipped', 'nobody to ask'):
            try:
                pin = select_release(pin)
                outcome['wanted'] = pin['version']
            except InstallError as refusal:
                outcome.update({'state': 'refused', 'detail': str(refusal)})
                outcomes[name] = outcome
                continue
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
                    pin = lock_companion(name, pin)
                    checkout = fetch_companion(name, pin, root)
                    outcome.update(run_companion(name, pin, checkout, home, harnesses))
                except InstallError as refusal:
                    outcome.update({'state': 'refused', 'detail': str(refusal)})
                outcome['found'] = companion_found(home, harnesses, name)
                if outcome['state'] == 'installed':
                    state.setdefault('companions', {})[name] = {
                        'version': pin['version'], 'commit': pin['commit'], 'sha256': pin['sha256'],
                        'installed_at': now()}
        outcomes[name] = outcome
    return outcomes

SHARED = ('minimum_version', 'select_release', 'lock_companion', 'resolve_companion', 'read_pins', 'as_tuple', 'tree_digest', 'git', 'fetch_revision', 'fetch_companion', 'companion_found', 'wanting', 'companion_command', 'run_companion', 'bring_companions')


def bind(namespace):
    """Retain each native installer's public globals and test injection points."""
    namespace['VERSION'] = VERSION
    for name in SHARED:
        original = globals()[name]
        function = FunctionType(original.__code__, namespace, name, original.__defaults__, original.__closure__)
        function.__doc__ = original.__doc__
        function.__kwdefaults__ = original.__kwdefaults__
        namespace[name] = function
