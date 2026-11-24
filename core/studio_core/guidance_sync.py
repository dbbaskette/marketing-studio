"""Fetch, pin and verify the guidance a studio's work follows: the part the studios that
build slides share, kept once.

Each studio's scripts/sync_guidance.py keeps its own module and binds `NAMES` into it with
`studio_core.modules.bind`, so these functions read that module's names and every patch on
it. The studio module gives them:

    PRODUCT, ITEM        its full product name and the word for one piece of its work
    RUNTIME              the installed copy (the folder above its scripts folder)
    DEFAULT_SOURCE       the repository, branch and manifest guidance comes from
    STATE_DIR            the folder in a piece of work that holds its pin
    SOURCE_VARIABLE, MANIFEST_VARIABLE
                         the environment variables that name another source
    CONTINUES            what is said when saved instructions cannot be used
    SyncError, NeedsNewer
                         its refusals
    helper()             how the studio's helper is run
    has_item(project)    whether a folder holds work in progress
    home, Path, PurePosixPath
                         imported, as the functions here read them

Its `__file__` and `__doc__` are its own, so an installed copy is found by the studio's
script and the command line describes itself in the studio's words.

Guidance is the skill's SKILL.md, references and assets. It can be newer than the installed
scripts, so it is fetched from the skill's repository. Scripts are never fetched: every
command runs from the installed copy, whatever the work was started on. Only guidance this
helper fetched itself from the source branch is used, and git runs without the user's
config or environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess

PARTS = ('SKILL.md', 'references', 'assets')
COMMIT = re.compile(r'[0-9a-f]{40}')
BRANCH = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]*')
OLD_FOLDER = re.compile(r'[0-9a-f]{12}')           # how versions before 0.18.1 named guidance

# The local copy of the source branch: a bare repository holding one ref, with this config.
MAIN = 'refs/remotes/source/main'
CACHE_CONFIG = b'[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = true\n'
CACHE_ENTRIES = {'HEAD', 'config', 'objects', 'refs', 'packed-refs', 'FETCH_HEAD'}

# Given to every git this runs, whatever any config says: no hooks or commands of anyone
# else's, no replaced or grafted history, and only https or a local folder to fetch from.
ISOLATED = ('--no-replace-objects',
            '-c', f'core.hooksPath={os.devnull}', '-c', 'core.fsmonitor=false',
            '-c', 'core.commitGraph=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
            '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
            '-c', 'protocol.file.allow=always')


def runtime_version() -> str:
    return (RUNTIME / 'VERSION').read_text(encoding='utf-8').strip()


def address() -> Path:
    """Where this skill is reached, for anything handed out or saved. An installed copy is
    in `versions/<id>`, a folder an update leaves behind and a clean-up removes; the
    `current` link beside `versions` always names the installed one, so that is its address.
    A checkout is its own."""
    for folder in (RUNTIME, *RUNTIME.parents):
        if folder.parent.name == 'versions':
            current = folder.parent.parent / 'current' / RUNTIME.relative_to(folder)
            if (current / 'scripts' / Path(__file__).name).is_file():
                return current
            break
    return RUNTIME


def source() -> dict:
    """Where guidance comes from: the installed source.json, or the public repository."""
    configured = home.read_json(RUNTIME / 'source.json', {})
    found = {**DEFAULT_SOURCE, **(configured if isinstance(configured, dict) else {})}
    if os.environ.get(SOURCE_VARIABLE):
        found['repository'] = os.environ[SOURCE_VARIABLE]
    if found['repository'] != DEFAULT_SOURCE['repository']:
        found['manifest'] = (configured or {}).get('manifest', 'guidance/manifest.json')
    if os.environ.get(MANIFEST_VARIABLE):
        found['manifest'] = os.environ[MANIFEST_VARIABLE]
    return found


def bundled() -> Path:
    """The guidance that came with the installed scripts, used when nothing newer can be had."""
    base = address()
    inside = base / 'guidance'
    return inside if (inside / 'SKILL.md').is_file() else base


def guidance_root() -> Path:
    return home.data_root() / 'guidance'


def folder_for(commit: str) -> Path:
    """Where one commit's guidance is kept. Nowhere else is read."""
    return guidance_root() / commit


# --- git ----------------------------------------------------------------------

def run_git(*args: str, repo: Path | None = None,
            input: bytes | None = None) -> subprocess.CompletedProcess:
    """Run git apart from the user's setup: no system or global config, no GIT_* variables,
    and the settings in ISOLATED. `repo` is a bare repository, named so none is searched for."""
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0')
    where = guidance_root()
    where.mkdir(parents=True, exist_ok=True)
    command = ['git', *([f'--git-dir={repo}'] if repo else []), *ISOLATED, *args]
    try:
        return subprocess.run(command, cwd=where, env=env, input=input, capture_output=True,
                              stdin=subprocess.DEVNULL if input is None else None,
                              timeout=120)
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise SyncError(f'git could not run: {failure}')


def git(*args: str, repo: Path | None = None, input: bytes | None = None) -> bytes:
    done = run_git(*args, repo=repo, input=input)
    if done.returncode != 0:
        message = done.stderr.decode('utf-8', 'replace').strip().splitlines()
        raise SyncError(message[-1] if message else 'git failed')
    return done.stdout


def ours(path: Path) -> bool:
    """True when the cache is as this helper makes it: its config, its files, its one ref.

    git reads far more of a repository than its config (alternates, grafts, replace refs,
    hooks, commit graphs), so rather than clean what is there, anything else is rebuilt."""
    try:
        if path.is_symlink() or not path.is_dir():
            return False
        entries = list(path.iterdir())
        if any(entry.is_symlink() for entry in entries) \
                or not {entry.name for entry in entries} <= CACHE_ENTRIES \
                or (path / 'config').read_bytes() != CACHE_CONFIG:
            return False
        objects = path / 'objects'
        if any((objects / 'info').iterdir()) or any(
                entry.is_symlink() or not (entry.name in ('info', 'pack')
                                           or re.fullmatch(r'[0-9a-f]{2}', entry.name))
                for entry in objects.iterdir()):
            return False
    except OSError:
        return False
    refs = run_git('for-each-ref', '--format=%(refname)', repo=path)
    return refs.returncode == 0 and set(refs.stdout.split()) <= {MAIN.encode()}


def cache() -> Path:
    """The local copy of the source branch, rebuilt empty unless it is as this helper made it."""
    path = guidance_root() / 'cache.git'
    if ours(path):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
    for old in guidance_root().iterdir():
        if old.is_dir() and not old.is_symlink() and OLD_FOLDER.fullmatch(old.name):
            shutil.rmtree(old, ignore_errors=True)
    git('init', '--quiet', '--bare', '--template=', str(path))
    (path / 'config').write_bytes(CACHE_CONFIG)
    return path


def as_tuple(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split('.'))
    except ValueError:
        raise SyncError(f'"{version}" is not a version number.')


def fetch() -> str:
    """Fetch the source branch, with its history, into the cache; return its commit.

    Nothing is fetched by commit ID: a host can serve commits by ID that were never on the
    branch, such as a fork's."""
    where = source()
    repository, branch = str(where['repository']), str(where['branch'])
    if repository.startswith('-') or not BRANCH.fullmatch(branch) or '..' in branch:
        raise SyncError('The guidance source is not one this version can fetch from.')
    repo = cache()
    git('fetch', '--quiet', '--no-tags', repository, f'+refs/heads/{branch}:{MAIN}', repo=repo)
    return git('rev-parse', '--verify', f'{MAIN}^{{commit}}', repo=repo).decode().strip()


def on_main(commit: str, repo: Path) -> bool:
    """True when the cache has a commit and it is on the source branch as last fetched."""
    return run_git('merge-base', '--is-ancestor', commit, MAIN, repo=repo).returncode == 0


def manifest(commit: str, repo: Path | None = None) -> dict:
    """The guidance manifest at a commit, checked against the installed scripts."""
    try:
        found = json.loads(git('cat-file', 'blob', f"{commit}:{source().get('manifest', 'guidance/manifest.json')}",
                               repo=repo or cache()))
    except ValueError:
        raise SyncError('The guidance manifest is not valid JSON.')
    if not isinstance(found, dict) or found.get('schema') != 1 \
            or not isinstance(found.get('content_root'), str):
        raise SyncError('The guidance manifest is not one this version understands.')
    root = PurePosixPath(found['content_root'].strip('/'))
    if not root.parts or any(part in ('.', '..') for part in root.parts):
        raise SyncError('The guidance manifest is not one this version understands.')
    needed = str(found.get('minimum_runtime', '0'))
    if as_tuple(needed) > as_tuple(runtime_version()):
        raise NeedsNewer(needed)
    return found


def listing(commit: str, root: str, repo: Path) -> dict[str, str]:
    """The guidance files at a commit, as {path under the content root: blob ID}."""
    found = {}
    out = git('ls-tree', '-r', '-z', '--full-tree', commit, '--',
              *(f'{root}/{part}' for part in PARTS), repo=repo)
    for line in filter(None, out.split(b'\0')):
        meta, _, name = line.partition(b'\t')
        mode, kind, ident = meta.split()
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            continue
        try:
            inside = PurePosixPath(name.decode('utf-8')).relative_to(root)
        except (UnicodeDecodeError, ValueError):
            raise SyncError('The fetched guidance has a file this version cannot place.')
        if any(part in ('', '.', '..') for part in inside.parts):
            raise SyncError('The fetched guidance has a file this version cannot place.')
        found[inside.as_posix()] = ident.decode()
    return found


def blob_id(content: bytes) -> str:
    return hashlib.sha1(b'blob %d\0' % len(content) + content).hexdigest()


def present(folder: Path) -> dict[str, str] | None:
    """What a folder holds, as `listing` gives it; None if it is not a plain folder of files."""
    if folder.is_symlink() or not folder.is_dir():
        return None
    found = {}
    for path in folder.rglob('*'):
        if path.is_symlink():
            return None
        if path.is_file():
            found[path.relative_to(folder).as_posix()] = blob_id(path.read_bytes())
    return found


def blobs(idents: list[str], repo: Path) -> dict[str, bytes]:
    out = git('cat-file', '--batch', repo=repo,
              input=''.join(f'{ident}\n' for ident in idents).encode())
    found, at = {}, 0
    for _ in idents:
        end = out.index(b'\n', at)
        header = out[at:end].split()
        if len(header) != 3 or header[1] != b'blob':
            raise SyncError('The fetched guidance could not be read.')
        size = int(header[2])
        found[header[0].decode()] = out[end + 1:end + 1 + size]
        at = end + 1 + size + 1
    return found


def materialize(commit: str, repo: Path | None = None) -> Path:
    """One commit's guidance files, in its folder and exactly as in its tree; return it."""
    repo = repo or cache()
    folder = folder_for(commit)
    root = manifest(commit, repo)['content_root'].strip('/')
    expected = listing(commit, root, repo)
    if 'SKILL.md' not in expected:
        raise SyncError('The fetched guidance has no SKILL.md.')
    if present(folder) == expected:
        return folder
    pending = folder.with_name(f'.{folder.name}.pending')
    shutil.rmtree(pending, ignore_errors=True)
    content = blobs(sorted(set(expected.values())), repo)
    for name, ident in expected.items():
        target = pending / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content[ident])
    if present(pending) != expected:
        shutil.rmtree(pending, ignore_errors=True)
        raise SyncError('The fetched guidance could not be written as it was fetched.')
    if folder.is_symlink() or folder.is_file():
        folder.unlink()
    else:
        shutil.rmtree(folder, ignore_errors=True)
    pending.replace(folder)
    return folder


# --- pins ---------------------------------------------------------------------

def pin_path(project: Path) -> Path:
    return project / STATE_DIR / 'guidance.json'


def write_pin(project: Path, commit: str | None) -> dict:
    """Save which instructions a piece of work follows: their commit, or None for the ones
    installed with the skill. No folder and no digests of files are kept: both go out of
    date when an update moves the installed copy, and a pin from an older version that has
    them is read without them. `runtime` is the version the work started on, to show;
    nothing is ever compared with it."""
    pin = {'schema': 1, 'commit': commit, 'runtime': runtime_version(),
           'pinned_at': home.now()}
    home.write_json(pin_path(project), pin)
    return pin


def pinned(project: Path) -> Path | None:
    """The folder of the guidance work in progress follows, when this computer has it.
    The work names only the commit; the folder is always the one in the data folder."""
    pin = home.read_json(pin_path(project), None)
    commit = pin.get('commit') if isinstance(pin, dict) else None
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        return None
    folder = folder_for(commit)
    return folder if (folder / 'SKILL.md').is_file() else None


def answer(folder: Path, commit: str | None, freshness: str, pinned: bool,
           notice: str | None = None) -> dict:
    return {'entry': str(folder / 'SKILL.md'), 'helper': helper(), 'commit': commit,
            'freshness': freshness, 'pinned': pinned, 'runtime': runtime_version(),
            'notice': notice}


def latest(head: str | None = None) -> tuple[Path, str | None, str, str | None]:
    """The newest usable guidance: folder, commit, freshness and a notice if it fell back.
    `head` is the source branch's commit when it was fetched a moment ago."""
    try:
        commit = head or fetch()
        fresh = 'cached' if (folder_for(commit) / 'SKILL.md').is_file() else 'fetched'
        return materialize(commit), commit, fresh, None
    except SyncError as failure:
        return bundled(), None, 'installed', (
            f'Could not get the newest guidance: {failure} Using the guidance installed '
            'with the skill, which may be older.')


def start(project: Path) -> dict:
    """The guidance to follow here: the saved one for work in progress, else the newest."""
    if pin_path(project).is_file():
        return resume(project)
    folder, commit, freshness, notice = latest()
    home.write_json(guidance_root() / 'last.json', {'commit': commit})
    in_progress = has_item(project)
    if in_progress:
        write_pin(project, commit)
    return answer(folder, commit, freshness, in_progress, notice)


def adopt(project: Path) -> dict | None:
    """Pin new work to the guidance the last start resolved. Called by init."""
    last = home.read_json(guidance_root() / 'last.json', None)
    if not isinstance(last, dict):
        return None
    commit = last.get('commit')
    if commit is None:
        return write_pin(project, None)
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit) \
            or not (folder_for(commit) / 'SKILL.md').is_file():
        return None
    return write_pin(project, commit)


def carry_on(project: Path, head: str | None = None) -> dict:
    """Continue work whose saved instructions cannot be used at all, on the newest usable
    guidance, and save that as its pin. It is said once, in the notice; nothing is asked of
    the person and nothing has to be run."""
    folder, commit, freshness, notice = latest(head)
    write_pin(project, commit)
    return answer(folder, commit, freshness, True, f'{CONTINUES} {notice}' if notice else CONTINUES)


def resume(project: Path) -> dict:
    """The guidance work in progress follows: the instructions it was saved with, by its
    pin's commit and from the source branch only, with no network when this computer has
    them.

    Only the pin's `schema` and `commit` are read. A pin that cannot be read, or whose
    commit the source branch does not have, carries on with the current guidance. Saved
    instructions that cannot be had for now (no network, damaged files) use the installed
    ones for this visit and keep the pin. Only saved instructions that need a newer studio
    than the one installed are refused: following older ones in their place would quietly
    change the work."""
    if not pin_path(project).is_file():
        return start(project)
    pin = home.read_json(pin_path(project), None)
    commit = pin.get('commit') if isinstance(pin, dict) and pin.get('schema') == 1 else False
    if commit is None:
        return answer(bundled(), None, 'installed', True)
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        return carry_on(project)
    head = None
    try:
        repo = cache()
        if not on_main(commit, repo):
            head = fetch()
        known = on_main(commit, repo)
    except SyncError as failure:
        return answer(bundled(), None, 'installed', True, (
            f'The guidance this {ITEM} was saved with is not on this computer and '
            f'could not be fetched: {failure} Using the guidance installed with the skill.'))
    if not known:
        return carry_on(project, head)
    try:
        folder = materialize(commit, repo)
    except NeedsNewer as failure:
        raise SyncError(f"This {ITEM}'s instructions need {PRODUCT} {failure.needed} "
                        f'or later; {runtime_version()} is installed. Update {PRODUCT} '
                        'to continue it.')
    except SyncError as failure:
        return answer(bundled(), None, 'installed', True, (
            f'The guidance this {ITEM} was saved with cannot be used: {failure} Using the '
            'guidance installed with the skill.'))
    return answer(folder, commit, 'pinned', True)


def update(project: Path) -> dict:
    """Move work to the newest guidance, when the person asks for that. Nothing needs it:
    work carries on without it after any update. Checks may give different results
    afterwards."""
    if not has_item(project):
        raise SyncError(f'No {ITEM} in this directory.')
    before = home.read_json(pin_path(project), None)
    before = before.get('commit') if isinstance(before, dict) else None
    commit = fetch()
    folder = materialize(commit)
    write_pin(project, commit)
    return answer(folder, commit, 'fetched', True, (
        f"Guidance moved from {str(before or 'the installed copy')[:12]} to "
        f'{commit[:12]}. Run the checks again; results can differ.')
        if before != commit else None)


def summary(project: Path) -> dict | None:
    """Which instructions work follows, for status output. `runtime` is the version of the
    studio it started on, to show and nothing more."""
    pin = home.read_json(pin_path(project), None)
    if not isinstance(pin, dict):
        return None
    return {'commit': pin.get('commit'), 'pinned_at': pin.get('pinned_at'),
            'runtime': pin.get('runtime')}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('action', choices=('start', 'resume', 'update'))
    parser.add_argument('--project', default='.', help=f'the {ITEM} directory')
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()
    try:
        result = {'start': start, 'resume': resume, 'update': update}[args.action](project)
    except (SyncError, OSError) as failure:
        print(json.dumps({'error': str(failure)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


NAMES = ('PARTS', 'COMMIT', 'BRANCH', 'OLD_FOLDER', 'MAIN', 'CACHE_CONFIG', 'CACHE_ENTRIES',
         'ISOLATED', 'runtime_version', 'address', 'source', 'bundled', 'guidance_root',
         'folder_for', 'run_git', 'git', 'ours', 'cache', 'as_tuple', 'fetch', 'on_main',
         'manifest', 'listing', 'blob_id', 'present', 'blobs', 'materialize', 'pin_path',
         'write_pin', 'pinned', 'answer', 'latest', 'start', 'adopt', 'carry_on', 'resume',
         'update', 'summary', 'main')
