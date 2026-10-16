"""The companion skills Blog Studio uses, brought at the revision companions.json pins.

What a caller needs to know
---------------------------
    pins = companions.read_pins(companions.PINS)
    outcomes = companions.bring(home, root, skills, pins, agree)   # skills: {agent: skill path}
    found = companions.found(skills, 'harness-research')         # {agent: version, '' or None}
    notes = companions.notes(pins, outcomes)

- Ported from Training Studio's installer/install.py (read_pins, tree_digest, git,
  fetch_revision, fetch_companion, companion_found, wanting, companion_command,
  run_companion, bring_companions), the same steps Training and Presentation Studio take, so
  every studio installs harness-research the same way. The adaptation: a companion's
  folder is found beside each Blog Studio skill link, from installer.targets().
- Each companion is fetched from its own repository at the pinned commit, checked file for
  file against the pinned SHA-256, and installed by its own installer, which needs Node 20
  or newer. Nothing of it is kept in this repository, and nothing is run unless it matches.
- One that is installed and as new as its pin is left alone. `agree(name, pin, found)` is
  asked before anything is fetched; answering no leaves it `waiting`.
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

PINS = Path(__file__).resolve().parent / 'companions.json'
NODE_NEEDED = 20
VERSION = re.compile(r'^\d+\.\d+\.\d+$')
HEX = {'commit': re.compile(r'^[0-9a-f]{40}$'), 'sha256': re.compile(r'^[0-9a-f]{64}$')}
LABELS = {'codex': 'Codex', 'claude': 'Claude Code'}
NEEDS = {'harness-research': 'research and fact-checking cannot run without it'}


class CompanionError(Exception):
    """A companion that could not be brought, said in one sentence."""


def read_pins(path=PINS):
    """The pinned companions: {name: {repository, version, commit, sha256, stub, installer}}."""
    try:
        kept = json.loads(Path(path).read_text(encoding='utf-8'))
        pins = kept['companions']
        if kept['schema'] != 1 or not isinstance(pins, dict):
            raise ValueError
        for name, pin in pins.items():
            for key in ('repository', 'version', 'commit', 'sha256', 'stub', 'installer'):
                if not isinstance(pin[key], str) or not pin[key]:
                    raise ValueError
            inside = [Path(pin[key]) for key in ('stub', 'installer')]
            if (
                not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name)
                or not VERSION.match(pin['version'])
                or any(not pattern.match(pin[key]) for key, pattern in HEX.items())
                or any(part.is_absolute() or '..' in part.parts for part in inside)
            ):
                raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise CompanionError(
            f'{path} does not say which companion skills to install, or says it in a way this '
            'installer does not read. Get this repository again.'
        ) from None
    return pins


def as_tuple(version):
    return tuple(int(part) for part in version.split('.'))


def tree_digest(folder):
    """One SHA-256 for every file under a folder: each file's path and its own SHA-256, in
    order. A link, or anything that is not a plain file, is refused."""
    folder, lines = Path(folder), []
    for path in sorted(folder.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise CompanionError(
                f'{path.relative_to(folder)} is a link or a special file, which a companion '
                'skill never holds.'
            )
        if path.is_file():
            lines.append(
                hashlib.sha256(path.read_bytes()).hexdigest()
                + '  '
                + path.relative_to(folder).as_posix()
                + '\n'
            )
    return hashlib.sha256(''.join(lines).encode()).hexdigest()


def git(args, cwd):
    """Run git without anyone's sign-in being asked for: (exit code, what it said)."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith('GIT_') or key.startswith('GIT_CONFIG_')
    }
    env['GIT_TERMINAL_PROMPT'] = '0'
    try:
        done = subprocess.run(
            ['git', *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise CompanionError(
            'git is needed to fetch a companion skill, and was not found.'
        ) from None
    except (OSError, subprocess.TimeoutExpired) as failure:
        return 1, type(failure).__name__
    return done.returncode, (done.stdout if done.returncode == 0 else done.stderr).strip()


def fetch_revision(repository, revision, into):
    """Put one revision of a repository into an empty folder as plain files, with nothing of
    git left in it. Returns the commit that was fetched."""
    for step in (
        ['init', '-q'],
        ['fetch', '-q', '--depth', '1', '--no-tags', repository, revision],
        [
            '-c',
            'core.autocrlf=false',
            '-c',
            'advice.detachedHead=false',
            'checkout',
            '-q',
            '--detach',
            'FETCH_HEAD',
        ],
    ):
        code, said = git(step, into)
        if code != 0:
            why = said.splitlines()[-1] if said else 'git gave no reason'
            raise CompanionError(f'{revision} could not be fetched from {repository}: {why}')
    code, commit = git(['rev-parse', 'HEAD'], into)
    if code != 0 or not HEX['commit'].match(commit):
        raise CompanionError(f'What was fetched from {repository} could not be read.')
    shutil.rmtree(Path(into) / '.git')
    return commit


def fetch(name, pin, root):
    """The companion's repository at its pinned revision, checked, in this installation's own
    folder. Refuses anything that is not exactly what companions.json names."""
    kept = Path(root) / 'companions' / name / pin['commit'][:12]
    if kept.is_dir():
        if tree_digest(kept) != pin['sha256']:
            raise CompanionError(
                f'{kept} has changed since it was fetched. Remove that folder and run this again.'
            )
        return kept
    kept.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix='.pending-', dir=kept.parent))
    try:
        commit = fetch_revision(pin['repository'], pin['commit'], pending)
        if commit != pin['commit'] or tree_digest(pending) != pin['sha256']:
            raise CompanionError(
                f'What {pin["repository"]} gave for {name} {pin["version"]} is not what this '
                'installer expects, file for file. None of it was kept and none of it was run.'
            )
        stub = pending / pin['stub']
        named = (
            re.search(r'^name: *(\S+) *$', stub.read_text(encoding='utf-8'), re.MULTILINE)
            if stub.is_file()
            else None
        )
        if not named or named.group(1) != name or not (pending / pin['installer']).is_file():
            raise CompanionError(
                f'{name} at its pinned revision does not hold the entry and the installer this '
                'installer expects. None of it was run.'
            )
        os.replace(pending, kept)
    finally:
        shutil.rmtree(pending, ignore_errors=True)
    return kept


def found(skills, name):
    """The version of a companion beside each Blog Studio skill: None when there is none, ''
    when one is there whose version cannot be read."""
    versions = {}
    for agent, skill in skills.items():
        folder = Path(skill).parent / name
        if not folder.exists() and not folder.is_symlink():
            versions[agent] = None
            continue
        try:
            version = json.loads((folder / 'package.json').read_text(encoding='utf-8'))['version']
        except (OSError, ValueError, KeyError, TypeError):
            version = ''
        versions[agent] = version if isinstance(version, str) and VERSION.match(version) else ''
    return versions


def wanting(versions, wanted):
    """The assistants that have no copy of a companion, or an older one than is pinned."""
    return [
        agent
        for agent, version in versions.items()
        if version is None or (version and as_tuple(version) < as_tuple(wanted))
    ]


def node_version():
    try:
        done = subprocess.run(
            ['node', '--version'],
            capture_output=True,
            text=True,
            timeout=20,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def node_is_enough(node):
    digits = (node or '').lstrip('v').split('.')[0]
    return digits.isdigit() and int(digits) >= NODE_NEEDED


def command(node, checkout, pin, home):
    """How a companion's own installer is run. Only a home that is not the person's own is
    named to it; otherwise it is left to its own defaults."""
    run = [node, str(Path(checkout) / pin['installer'])]
    return run if Path(home).resolve() == Path.home().resolve() else [*run, '--home', str(home)]


def run(name, pin, checkout, home, skills):
    """Run a companion's own installer from its checked copy, then look at what it left."""
    node = shutil.which('node')
    if not node:
        return {'state': 'failed', 'detail': 'Node was not found, and its installer runs on Node.'}
    env = dict(os.environ)
    if Path(home).resolve() != Path.home().resolve():
        env.update({'HOME': str(home), 'USERPROFILE': str(home)})
        env.pop('CLAUDE_CONFIG_DIR', None)
    try:
        done = subprocess.run(
            command(node, checkout, pin, home),
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as failure:
        return {
            'state': 'failed',
            'detail': f'its installer did not finish ({type(failure).__name__}).',
        }
    if done.returncode != 0:
        said = (done.stderr or done.stdout).strip().splitlines()
        return {
            'state': 'failed',
            'detail': 'its installer said: '
            + (said[-1][:300] if said else 'nothing, and stopped.'),
        }
    stub = (Path(checkout) / pin['stub']).read_bytes()
    versions = found(skills, name)
    for agent, skill in skills.items():
        entry = Path(skill).parent / name / 'SKILL.md'
        if (
            wanting({agent: versions[agent]}, pin['version'])
            or not entry.is_file()
            or entry.read_bytes() != stub
        ):
            return {
                'state': 'failed',
                'detail': 'its installer finished, but did not leave the entry this installer '
                f'checked for {LABELS.get(agent, agent)}.',
            }
    return {'state': 'installed'}


def bring(home, root, skills, pins, agree):
    """Bring each companion that is missing or older than its pin, when the person agrees.
    One that is as new or newer is left alone. Nothing here undoes Blog Studio's own
    installation: what goes wrong is reported."""
    outcomes = {}
    for name, pin in pins.items():
        versions = found(skills, name)
        outcome = {'wanted': pin['version'], 'found': versions, 'state': 'left alone'}
        if wanting(versions, pin['version']):
            # Asked first: nothing is run, not even node --version, until the person agrees.
            if not agree(name, pin, versions):
                outcome['state'] = 'waiting'
            elif not node_is_enough(node_version()):
                outcome.update(
                    {
                        'state': 'failed',
                        'detail': f'its installer needs Node {NODE_NEEDED} or newer.',
                    }
                )
            else:
                try:
                    outcome.update(run(name, pin, fetch(name, pin, root), home, skills))
                except CompanionError as refusal:
                    outcome.update({'state': 'refused', 'detail': str(refusal)})
                outcome['found'] = found(skills, name)
                if outcome['state'] == 'installed':
                    outcome['installed_at'] = datetime.now(timezone.utc).isoformat(
                        timespec='seconds'
                    )
        outcomes[name] = outcome
    return outcomes


def notes(pins, outcomes):
    """What is worth knowing about each companion, as sentences; none when all is well."""
    said = []
    for name, outcome in outcomes.items():
        pin, need = pins[name], NEEDS.get(name, 'part of Blog Studio cannot run without it')
        again = 'sh installer/install.sh --companions install'
        source = pin['repository'].removesuffix('.git')
        if outcome['state'] in ('refused', 'failed'):
            said.append(
                f'{name} {pin["version"]} was not installed, and {need}: {outcome["detail"]} '
                f'When that is put right, run: {again}'
            )
            continue
        short = wanting(outcome['found'], pin['version'])
        if short:
            who = ' and '.join(LABELS.get(agent, agent) for agent in short)
            what = (
                'is not installed'
                if all(outcome['found'][agent] is None for agent in short)
                else f'is older than the {pin["version"]} Blog Studio was made with'
            )
            said.append(
                f'{name} {what} for {who}: {need}. To install it from {source}, run: {again}'
            )
    return said
