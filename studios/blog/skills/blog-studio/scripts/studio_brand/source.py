"""The brand skill's own repository: where its main branch is, and installing main with the
brand skill's own installer.

What a caller needs to know
---------------------------
    found = brand_source.check(address, place)          # refuses in a sentence
    found['chosen']                 # {'tag': 'main', 'version': None, 'commit'}: what to install
    commit = brand_source.head(address, place)          # the commit main is at, or a refusal
    folder, how = brand_source.fetch(address, commit, into, stop)
    brand_source.version_of(folder)                     # the version main holds
    brings = brand_source.bootstraps(folder)            # {'harness-slides': '0.15.1'}
    code, late, said = brand_source.install(folder, home, seconds, stop)

- The repository is the person's choice, and is reached with their own git access, as the
  workspace is: through `hub.run`, which never asks on a terminal and gives ssh BatchMode.
  The guidance's isolated git, which ignores the person's settings, is never used here.
- There are no releases to choose from and no tags are read: the brand skill is installed
  and updated from its repository's `main`. An update is due when main is at another commit
  than the one installed. `order` still orders version numbers, for the oldest companion an installer accepts:
  a version whose first number is a year, 2000 to 2099, is from an older way of numbering
  and comes before every other.
- `check` reads where main is with `git ls-remote` and nothing else. A repository that
  cannot be read is refused with a sentence that says whether git could not sign in, the
  repository was not found, or it could not be reached. One with no main branch is refused
  too.
- `fetch` clones main at depth one into a new folder inside `into`, with the person's own
  git access, and its commit must be `commit`, the one the person was shown. Nothing of it
  is run, and it holds no hooks.
- `install` runs main's own installer from that folder, under `companion.supervise`:
  `scripts/install-mac.mjs --yes --research skip` on a Mac, else
  `scripts/install-skill.mjs --research skip`. `--research skip` keeps it from touching
  harness-research. It has no such option for harness-slides, which it leaves alone only
  when one it can use is installed; `bootstraps` reads the oldest version it accepts, from
  main's own record of what it installs. `home`, when it is not the person's own, is given
  to it as HOME.
- Nothing here is run before the person's yes; the caller asks for that.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from studio_sync import support as hub
from studio_sync.support import WorkspaceError

from . import companion, settings

PRODUCT = 'Blog Studio'  # a copy of the shared runner's, for Blog Studio

LOOK_SECONDS = 30  # for the repository to say where main is
FETCH_SECONDS = 600  # for main to be cloned
BRANCH = 'main'  # the only thing installed: main, as it is now
COMMIT = re.compile(r'^[0-9a-f]{40}$')
YEARS = range(2000, 2100)  # a first number in here is a year: the older way of numbering
SOURCES = Path('scripts') / 'lib' / 'harness-install-sources.json'
SKIPPED = ('harness-research',)  # what `--research skip` keeps the installer from touching
PLATFORM = sys.platform
SIGN_IN = (
    'terminal prompts disabled',
    'could not read username',
    'could not read password',
    'authentication failed',
    'permission denied',
    'host key verification failed',
    'invalid username or password',
)
NOT_FOUND = (
    'not found',
    'does not appear to be a git repository',
    'does not exist',
    'no such file',
)


def order(version) -> tuple:
    """How versions are ordered: one numbered from a year before every other, then by its
    numbers. Something that is not a version comes first of all."""
    try:
        parts = tuple(int(part) for part in str(version).split('.'))
    except ValueError:
        return ()
    return (0 if parts[0] in YEARS else 1, *parts)


def plain(reason: str) -> str:
    """Why a repository could not be read, as a sentence a person can act on."""
    said = reason.lower()
    if any(words in said for words in SIGN_IN):
        return (
            f'git could not sign in to it without asking ({reason}). Sign git in with an '
            'account that may read it, through its credential helper for an https '
            'address or an ssh key for an ssh one, then try again.'
        )
    if any(words in said for words in NOT_FOUND):
        return (
            f'It was not found ({reason}). Check the address. A private repository is '
            'not found by someone who may not read it, either.'
        )
    return (
        f'It could not be reached ({reason}). Check the address and that this computer '
        'is online, then try again.'
    )


def head(address: str, place: Path, seconds: float = LOOK_SECONDS) -> str:
    """The commit the repository's main branch is at. Refuses in a sentence when it cannot
    be read with this person's own git access, or has no main branch."""
    done = hub.run(place, 'ls-remote', '--', address, 'refs/heads/' + BRANCH, timeout=seconds)
    if done.returncode != 0:
        raise WorkspaceError(
            f"The brand skill's repository could not be read. {plain(hub.reason(done))}"
        )
    found = (done.stdout.split() or [''])[0]
    if not COMMIT.match(found):
        raise WorkspaceError(
            f'{address} has no main branch, which the brand skill is installed '
            'from. Check the address.'
        )
    return found


def _address(address: str) -> str:
    """An address, or a folder's whole path. A folder must say where it is."""
    if '://' in address or re.match(r'^[\w.-]+@[\w.-]+:', address):
        return address
    folder = Path(address).expanduser()
    if not folder.is_absolute():
        raise WorkspaceError(
            "Give the brand skill's repository as an https or ssh address, "
            "or a folder's whole path, starting from / or from ~."
        )
    return str(folder)


def check(address, place: Path) -> dict:
    """Whether the brand skill can be installed from this repository, by this person:
    {'repository', 'branch', 'commit', 'chosen', 'newest'}. It is installed and updated
    from main: `chosen` and `newest` are main, as {'tag': 'main', 'version': None,
    'commit'}."""
    address = settings.check_repository(address)
    if address is None:
        raise WorkspaceError("Give the brand skill's repository address.")
    address = _address(address)
    commit = head(address, place)
    chosen = {'tag': BRANCH, 'version': None, 'commit': commit}
    return {
        'repository': address,
        'branch': BRANCH,
        'commit': commit,
        'newest': chosen,
        'chosen': chosen,
    }


# --- fetching main ------------------------------------------------------------------------


def _text(data: bytes) -> str:
    return data.decode('utf-8', 'replace').replace('\r\n', '\n')


def _run(
    command: list[str], seconds: float, stop, env: dict | None = None, cwd: Path | None = None
) -> tuple[int, bool, str, str]:
    """Run a command once under `companion.supervise`: (exit code, whether it ran out of
    time, output, complaint). One that cannot start has failed. Stopped is raised on
    `stop`."""
    printed: list[bytes] = []
    with tempfile.TemporaryFile() as errors:
        try:
            code, late = companion.supervise(
                command, cwd, env, '', seconds, errors, printed.append, stop
            )
        except OSError as failure:
            return 127, False, '', str(failure)
        errors.seek(0)
        complaint = _text(errors.read())
    if stop is not None and stop.is_set():
        raise companion.Stopped('It was stopped before it finished.')
    if late:
        return code, True, '', f'it did not finish in {seconds:g} seconds'
    return code, False, _text(b''.join(printed)), complaint


def last_line(*said: str) -> str:
    """The last thing said, in one short line."""
    for text in said:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1][:300].rstrip('.')
    return 'it said nothing'


def fetch(address: str, commit: str, into: Path, stop=None) -> tuple[Path, str]:
    """Main, cloned at depth one into a new folder inside the empty folder `into`, with the
    person's own git access: (its folder, 'main'). Its commit must be `commit`, the one that
    was shown. No hook is placed or run."""
    if stop is not None and stop.is_set():
        raise companion.Stopped('It was stopped before it finished.')
    tree = into / 'tree'
    done = hub.run(
        into,
        '-c',
        'core.hooksPath=/dev/null',
        'clone',
        '--quiet',
        '--depth',
        '1',
        '--no-tags',
        '--template=',
        '--branch',
        BRANCH,
        *hub.COPY_AS_IS,
        '--',
        address,
        str(tree),
        timeout=FETCH_SECONDS,
    )
    if done.returncode != 0:
        raise WorkspaceError(f'Its main branch could not be fetched. {plain(hub.reason(done))}')
    found = hub.run(tree, 'rev-parse', 'HEAD')
    if found.returncode != 0 or found.stdout.strip() != commit:
        raise WorkspaceError(
            f'main was fetched at another commit than the {commit[:12]} you '
            'were shown. Look at it again before you install'
        )
    return tree, BRANCH


def version_of(folder: Path) -> str | None:
    """The version main holds, from its package.json, or None when it says none."""
    try:
        version = json.loads((Path(folder) / 'package.json').read_text(encoding='utf-8'))['version']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return version if isinstance(version, str) and order(version) else None


# --- its own installer ---------------------------------------------------------------------


def bootstraps(folder: Path) -> dict:
    """The companion versions main's installer brings when it finds none it can use, as it
    records them: {'harness-slides': '0.15.1', ...}. A record of `version` is that version;
    one of a `branch` with a `minimumVersion`, as Harness Brand 1.4.0 and newer keep, brings
    that branch, at that version or newer, and the minimum is given. Empty when it records
    none."""
    try:
        kept = json.loads((folder / SOURCES).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    found = {}
    for kind, entry in kept.items() if isinstance(kept, dict) else ():
        if not re.fullmatch(r'[a-z]{1,40}', str(kind)) or not isinstance(entry, dict):
            continue
        version = entry.get('version', entry.get('minimumVersion'))
        if isinstance(version, str) and order(version):
            found[f'harness-{kind}'] = version
    return found


def installer(folder: Path, node: str) -> list[str]:
    """How main's own installer is run: the Mac one on a Mac, else the other."""
    mac, other = folder / 'scripts' / 'install-mac.mjs', folder / 'scripts' / 'install-skill.mjs'
    if PLATFORM == 'darwin' and mac.is_file():
        return [node, str(mac), '--yes', '--research', 'skip']
    if other.is_file():
        return [node, str(other), '--research', 'skip']
    raise WorkspaceError(
        f'Its main branch has no installer {PRODUCT} knows how to run: '
        'scripts/install-mac.mjs on a Mac, or scripts/install-skill.mjs. '
        'Nothing was run'
    )


def install(folder: Path, home: Path, seconds: float, stop=None) -> tuple[int, bool, str]:
    """Run main's own installer: (its exit code, whether it ran out of time, the last thing
    it said)."""
    node = shutil.which('node')
    if node is None:
        raise WorkspaceError(
            'Its installer needs Node.js 20 or newer, which was not found '
            'on this computer. Nothing was run'
        )
    command = installer(folder, node)
    env = dict(os.environ)
    if Path(home).resolve() != Path.home().resolve():
        env.update({'HOME': str(home), 'USERPROFILE': str(home)})
        env.pop('CLAUDE_CONFIG_DIR', None)
    code, late, out, err = _run(command, seconds, stop, env, folder)
    return code, late, last_line(err, out) if code else last_line(out)
