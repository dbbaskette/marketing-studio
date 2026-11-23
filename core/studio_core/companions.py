"""The companion skills every installer brings: from their repository's `main`, checked.

There are no release locks and no tags. A pin names a companion's repository, its `main`
branch, and the oldest version this Marketing Studio works with (`version`, `requirement`):
a floor only, never what is installed. An install fetches `main`, checks it file for file
before anything of it runs (no links, no hooks, its entry and installer where the pin says,
a version at or above the floor) and runs its own installer. An update means that the
installed copy's commit differs from `main`'s: `main` is installed again. An offline bundle
carries whatever `main` was when it was built, with that commit and its checksum.
"""
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
BRANCH = 'main'   # every companion is installed and updated from its main branch
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
    """The companions: {name: {repository, branch, version, stub, installer, ...}}. `version`
    is the oldest accepted; `branch` is always `main`. A bundle's own record may add the
    `commit` and `sha256` of the `main` it carries."""
    try:
        kept = json.loads(path.read_text(encoding='utf-8'))
        pins = kept['companions']
        if kept['schema'] != 1 or not isinstance(pins, dict):
            raise ValueError
        for name, pin in pins.items():
            for key in ('repository', 'version', 'stub', 'installer'):
                if not isinstance(pin[key], str) or not pin[key]:
                    raise ValueError
            pin.setdefault('branch', BRANCH)
            inside = [Path(pin[key]) for key in ('stub', 'installer')]
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name) \
                    or not VERSION.match(pin['version']) or pin['branch'] != BRANCH \
                    or any(key in pin and not pattern.match(str(pin[key]))
                           for key, pattern in HEX.items()) \
                    or any(part.is_absolute() or '..' in part.parts for part in inside):
                raise ValueError
            if version_key(pin['version']) < version_key(minimum_version(pin)):
                raise ValueError
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise InstallError(f'{path} does not say which companion skills to install, or says '
                           'it in a way this installer does not read. Get this repository '
                           'again.')
    return pins


def as_tuple(version: str) -> tuple:
    return tuple(int(part) for part in version.split('-', 1)[0].split('.'))


def version_key(version: str) -> tuple:
    """Order stable and prerelease versions, including numeric prerelease identifiers."""
    core, separator, prerelease = version.partition('-')
    identifiers = tuple((0, int(part)) if part.isdigit() else (1, part)
                        for part in prerelease.split('.')) if separator else ()
    return as_tuple(core), not separator, identifiers


def minimum_version(pin: dict) -> str:
    """The oldest installed copy that is accepted, and the oldest `main` that is installed:
    the requirement's version, else the pin's own `version`."""
    requirement = pin.get('requirement')
    if requirement is None and 'requirement' not in pin:
        return pin['version']
    match = re.fullmatch(r'>=(\d+\.\d+\.\d+)', requirement) if isinstance(requirement, str) else None
    if not match:
        raise ValueError('Companion requirements must use >= followed by a stable version.')
    return match[1]


def main_commit(pin: dict) -> str:
    """The commit `main` of a companion's repository is at now. Only the branch is read:
    nothing is downloaded or run."""
    code, said = git(['ls-remote', '--', pin['repository'], 'refs/heads/' + pin.get('branch', BRANCH)],
                     Path(tempfile.gettempdir()))
    found = said.split()[0] if code == 0 and said.split() else ''
    if not HEX['commit'].fullmatch(found):
        raise InstallError(f"The main branch of {pin['repository']} could not be read. Retry "
                           'when the repository is reachable.')
    return found


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
    # No template, so no hook is ever placed, and none could run: hooks are switched off.
    for step in (['init', '-q', '--template='],
                 ['-c', 'core.hooksPath=/dev/null', 'fetch', '-q', '--depth', '1', '--no-tags',
                  repository, revision],
                 ['-c', 'core.autocrlf=false', '-c', 'advice.detachedHead=false',
                  '-c', 'core.hooksPath=/dev/null', 'checkout', '-q', '--detach', 'FETCH_HEAD']):
        code, said = git(step, into)
        if code != 0:
            why = said.splitlines()[-1] if said else 'git gave no reason'
            raise InstallError(f'{revision} could not be fetched from {repository}: {why}')
    code, commit = git(['rev-parse', 'HEAD'], into)
    if code != 0 or not HEX['commit'].match(commit):
        raise InstallError(f'What was fetched from {repository} could not be read.')
    shutil.rmtree(into / '.git')
    return commit


def _checked(name: str, pin: dict, folder: Path) -> str:
    """The version a fetched companion holds, once it is checked as one: its entry names it,
    its installer is where the pin says, and it is not older than the pin's floor. Nothing
    of it is run."""
    stub = folder / pin['stub']
    named = re.search(r'^name: *(\S+) *$', stub.read_text(encoding='utf-8'), re.MULTILINE) \
        if stub.is_file() and not stub.is_symlink() else None
    try:
        version = json.loads((folder / 'package.json').read_text(encoding='utf-8'))['version']
    except (OSError, ValueError, KeyError, TypeError):
        version = None
    if not named or named.group(1) != name or not (folder / pin['installer']).is_file() \
            or not isinstance(version, str) or not VERSION.match(version):
        raise InstallError(f'{name} on its main branch does not hold the entry, the installer '
                           'and the version this installer expects. None of it was run.')
    floor = minimum_version(pin)
    if version_key(version) < version_key(floor):
        raise InstallError(f'The main branch of {name} holds {version}, older than the {floor} '
                           'this version needs. None of it was run. Try again once it is updated.')
    return version


def fetch_main(name: str, pin: dict, root: Path) -> tuple[Path, dict]:
    """The companion's repository at `main` as it is now, checked, in this installer's own
    folder: (the folder, the pin with the `version`, `commit` and `sha256` it holds). A copy
    fetched before at the same commit is used when it is still whole, file for file. A pin
    that carries a `commit` and `sha256`, as a bundle's record does, is fetched exactly."""
    if pin.get('commit') and pin.get('sha256'):
        kept = fetch_companion(name, pin, root)
        return kept, {**pin, 'version': _checked(name, pin, kept)}
    commit = main_commit(pin)
    kept = root / 'companions' / name / commit[:12]
    record = kept.with_name(kept.name + '.sha256')
    if kept.is_dir() and record.is_file():
        digest = record.read_text(encoding='utf-8').strip()
        if tree_digest(kept) != digest:
            raise InstallError(f'{kept} has changed since it was fetched. Remove that folder '
                               'and run this again.')
        return kept, {**pin, 'version': _checked(name, pin, kept), 'commit': commit, 'sha256': digest}
    kept.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix='.pending-', dir=kept.parent))
    try:
        fetched = fetch_revision(pin['repository'], 'refs/heads/' + pin.get('branch', BRANCH), pending)
        if fetched != commit:   # main moved while it was fetched: what was fetched is used
            commit, kept = fetched, root / 'companions' / name / fetched[:12]
            record = kept.with_name(kept.name + '.sha256')
        digest = tree_digest(pending)   # refuses a link before anything is read
        version = _checked(name, pin, pending)
        shutil.rmtree(kept, ignore_errors=True)
        os.replace(pending, kept)
        record.write_text(digest + '\n', encoding='utf-8')
    finally:
        shutil.rmtree(pending, ignore_errors=True)
    return kept, {**pin, 'version': version, 'commit': commit, 'sha256': digest}


def fetch_companion(name: str, pin: dict, root: Path) -> Path:
    """The companion's repository at the exact `commit` a pin names, checked file for file
    against its `sha256`, in this installer's own folder: what a bundle built from `main`
    recorded. Refuses anything that is not exactly that."""
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
            raise InstallError(f"What {pin['repository']} gave for {name} at {pin['commit'][:12]} "
                               'is not what this installer expects, file for file. None of '
                               'it was kept and none of it was run.')
        stub = pending / pin['stub']
        named = re.search(r'^name: *(\S+) *$', stub.read_text(encoding='utf-8'), re.MULTILINE) \
            if stub.is_file() else None
        if not named or named.group(1) != name or not (pending / pin['installer']).is_file():
            raise InstallError(f'{name} at its recorded revision does not hold the entry and '
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
    """The assistants that have no copy of a companion, one older than `wanted`, or one
    whose version cannot be read (`''`: its package.json is missing or broken), which is
    repaired by installing it again. A prerelease comes before its release: 1.3.1-alpha.1
    does not meet 1.3.1."""
    return [harness for harness, version in found.items()
            if not version or version_key(version) < version_key(wanted)]


def stub_text(data: bytes) -> str | bytes:
    """A companion's entry (SKILL.md) as it is compared once its installer has run: the
    same words, whatever line endings, byte order mark, trailing spaces or blank lines at
    its end an installer left. Bytes that are not text are compared as they are."""
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    return '\n'.join(line.rstrip() for line in lines).strip('\n')


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
    stub = stub_text((checkout / pin['stub']).read_bytes())
    found = companion_found(home, harnesses, name)
    for harness in harnesses:
        entry = skill_link(home, harness).parent / name / 'SKILL.md'
        if wanting({harness: found[harness]}, pin['version']) or not entry.is_file() \
                or stub_text(entry.read_bytes()) != stub:
            return {'state': 'failed', 'detail': 'its installer finished, but did not leave '
                    f'the entry this installer checked for {HARNESS[harness]}.'}
    return outcome


def installed_commit(state: dict, name: str) -> str | None:
    """The commit of `main` this installer last installed of a companion, or None."""
    kept = ((state or {}).get('companions') or {}).get(name)
    commit = kept.get('commit') if isinstance(kept, dict) else None
    return commit if isinstance(commit, str) and HEX['commit'].fullmatch(commit) else None


def bring_companions(home: Path, root: Path, harnesses: list[str], pins: dict, agree,
                     state: dict, declined: str | None = None, update: bool = False) -> dict:
    """Install each companion that is missing, or older than this version needs, after
    asking; with `update`, also each whose installed commit differs from its `main` now,
    or was not installed from here. What is installed is `main`, fetched once the person
    has agreed and checked file for file (`fetch_main`). Nothing is looked up or fetched
    before that yes, and an installed copy that is new enough is otherwise left alone.
    Nothing here undoes the studio's own installation: what goes wrong is reported.
    `declined` says why one was not agreed to."""
    outcomes = {}
    for name, pin in pins.items():
        found = companion_found(home, harnesses, name)
        outcome = {'wanted': pin['version'], 'found': found, 'state': 'left alone'}
        short = wanting(found, minimum_version(pin))
        moved = None
        if update and not short:
            try:
                head = main_commit(pin)
            except InstallError as refusal:
                outcome['looked'] = str(refusal)
                head = None
            if head is not None and head != installed_commit(state, name):
                moved = head
        if short or moved:
            if not node_is_enough(node_version()):
                outcome.update({'state': 'failed', 'detail': f'its installer needs Node '
                                f'{NODE_NEEDED} or newer.'})
            elif not agree(name, pin, found):
                outcome['state'] = 'waiting'
                if declined:
                    outcome['why'] = declined
            else:
                try:
                    checkout, fetched = fetch_main(name, pin, root)
                    outcome['wanted'] = fetched['version']
                    outcome['commit'] = fetched['commit']
                    outcome.update(run_companion(name, fetched, checkout, home, harnesses))
                except InstallError as refusal:
                    outcome.update({'state': 'refused', 'detail': str(refusal)})
                    fetched = None
                outcome['found'] = companion_found(home, harnesses, name)
                if outcome['state'] == 'installed':
                    state.setdefault('companions', {})[name] = {
                        'version': fetched['version'], 'commit': fetched['commit'],
                        'sha256': fetched['sha256'], 'branch': fetched.get('branch', BRANCH),
                        'installed_at': now()}
        outcomes[name] = outcome
    return outcomes

SHARED = ('minimum_version', 'main_commit', 'read_pins', 'as_tuple', 'version_key', 'stub_text', 'tree_digest', 'git', 'fetch_revision', '_checked', 'fetch_main', 'fetch_companion', 'companion_found', 'wanting', 'companion_command', 'run_companion', 'installed_commit', 'bring_companions')


def bind(namespace):
    """Retain each native installer's public globals and test injection points."""
    namespace['VERSION'] = VERSION
    namespace.setdefault('BRANCH', BRANCH)
    for name in SHARED:
        original = globals()[name]
        function = FunctionType(original.__code__, namespace, name, original.__defaults__, original.__closure__)
        function.__doc__ = original.__doc__
        function.__kwdefaults__ = original.__kwdefaults__
        namespace[name] = function
