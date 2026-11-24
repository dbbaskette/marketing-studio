"""The brands folder and its Git repository: where it is, its locks, commits not yet
shared, and Push. marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

import hashlib
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from studio_core import brand_data
from studio_core.process_lock import ProcessRLock
from .errors import WorkspaceError

from .brand_files import canonical
from .brand_terms import LIBRARIES, SLUG


def _store():
    """marketing_studio.brand_store, read when called. Callers and tests replace names on it
    (LOCK, git, walk, write_json and others), and a call made here reaches what they put there."""
    from . import brand_store
    return brand_store


# Lock order, the same everywhere: a brands repository's lock in this process (repo_lock),
# then the repository's lock shared with other processes and Get brands (write_lock), then
# LOCK. None of them is held while Harness Brand's Node.js commands run. The first makes a
# second Save or Push in this process wait for the one before it, however long that takes,
# instead of giving up on write_lock's timeout.
_REPOS: dict[str, threading.Lock] = {}
_REPOS_GUARD = threading.Lock()


def repo_lock(folder: Path) -> threading.Lock:
    with _REPOS_GUARD:
        return _REPOS.setdefault(str(Path(folder).resolve()), threading.Lock())


@dataclass(frozen=True)
class Storage:
    folder: Path            # the brands folder
    team: bool              # a configured remote brands repository
    repo: Path | None       # the repository the folder is committed in; None until made
    address: str | None     # the configured remote brands repository

    @property
    def where(self) -> str:
        return (f'{self.address}, through the copy at {self.repo}' if self.team
                else f'{self.folder}, kept with local Git')


def git(repo, *args, env=None, seconds=60, input_text=None):
    try:
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                              timeout=seconds, input=input_text,
                              stdin=subprocess.DEVNULL if input_text is None else None,
                              env={**os.environ, 'GIT_TERMINAL_PROMPT': '0',
                                   'GIT_SSH_COMMAND': 'ssh -o BatchMode=yes', **(env or {})})
    except FileNotFoundError as failure:
        raise WorkspaceError('Saving a brand needs Git, which is not installed. Install it and '
                             'try again.') from failure
    except subprocess.TimeoutExpired as failure:
        raise WorkspaceError(f'Git did not answer in {seconds} seconds.') from failure


def reason(done) -> str:
    lines = [line.strip() for line in (done.stderr or done.stdout or '').splitlines() if line.strip()]
    return lines[-1] if lines else f'it ended with exit code {done.returncode}'


def storage(shared, checkouts=()) -> Storage:
    """The brands folder the shared settings say, for Marketing Studio, which has no
    workspace of its own."""
    shared = shared if isinstance(shared, dict) else {}
    address = (shared.get('brand') or {}).get('brands')
    if not isinstance(address, str) or not address.strip():
        # No repository set: the folder Harness Brand reads, used as a folder on this computer.
        try:
            address = str(brand_data.chosen(None))
        except ValueError as failure:
            raise WorkspaceError(str(failure)) from failure
    address = address.strip()
    try:
        folder = brand_data.place(address).resolve()
    except ValueError as failure:
        raise WorkspaceError(str(failure)) from failure
    remote = not brand_data._local(address)
    if remote and not (folder / '.git').exists():
        raise WorkspaceError('The brands repository has no copy here yet. Use Get brands in Shared settings, Brand first.')
    repo = folder if (folder / '.git').exists() else None
    if repo is not None:
        top = _store().git(repo, 'rev-parse', '--show-toplevel')
        if top.returncode or Path(top.stdout.strip()).resolve() != folder:
            raise WorkspaceError('Choose the root of the brands repository, not a folder inside another repository.')
        if remote:
            origin = _store().git(repo, 'remote', 'get-url', 'origin')
            if origin.returncode or origin.stdout.strip() != address:
                raise WorkspaceError('This copy belongs to a different brands repository. Review Shared settings, Brand.')
    elif folder.exists():
        parent = _store().git(folder, 'rev-parse', '--show-toplevel')
        if parent.returncode == 0:
            raise WorkspaceError('Choose a separate brands repository, outside any existing repository.')
    return Storage(folder, remote, repo, address if remote else None)


def write_lock(place: Storage):
    """The stable repository lock also held by Get brands."""
    return ProcessRLock(lambda: brand_data.lock_path(place.folder),
                        refusal=WorkspaceError)


def identity(repo: Path) -> None:
    done = _store().git(repo, 'var', 'GIT_AUTHOR_IDENT')
    if done.returncode != 0 or not done.stdout.rpartition(' <')[0].strip():
        raise WorkspaceError(
            'Git does not know who you are, so the brand cannot be recorded. Tell it once with '
            'git config --global user.name "Your Name" and git config --global user.email '
            '"you@example.com", then save again.')


def _owner(path: str) -> str:
    """What `git rev-list -- <pack id>` or `-- icon-libraries/<id>` would match a path by."""
    if path.startswith('"'):        # a quoted unusual name: its first folder is plain
        path = path[1:]
    bits = path.split('/')
    return '/'.join(bits[:2]) if bits[0] == LIBRARIES and len(bits) >= 2 else bits[0]


def unshared_counts(place: Storage) -> dict[str, int]:
    """{pack id or icon-libraries/<id>: what `git rev-list --count @{u}..HEAD -- <it>`
    says}, for every pack and library at once, from one Git run.

    `git log -m --boundary` gives each commit's changed paths against each parent (a parent
    with the same tree prints no block) and each commit's and boundary commit's tree. The
    path-limited walk is then followed as rev-list's default history simplification does it:
    a commit is counted when it changes the path against its parent; a merge the same as an
    interesting parent for the path is not counted and only that parent is followed; a merge
    whose parents are all upstream is counted when it differs from one of them. The
    upstream's own commit counts as interesting there, as rev-list's "bottom" does, so it is
    resolved first: two Git runs for the whole listing, whatever the number of packs. No
    upstream, or a Git failure, counts nothing, as before."""
    if not place.team or place.repo is None:
        return {}
    upstream = _store().git(place.repo, 'rev-parse', '--verify', '--quiet', '@{u}^{commit}')
    bottom = upstream.stdout.strip()
    if upstream.returncode or not bottom:
        return {}
    done = _store().git(place.repo, '-c', 'core.quotePath=false', 'log', '-m', '--boundary', '--no-renames',
               '--name-only', '--format=%x01%m %H %T %P', f'{bottom}..HEAD')
    if done.returncode:
        return {}
    trees, parents, blocks, head = {}, {}, {}, None
    for block in done.stdout.split('\x01')[1:]:
        line, _, paths = block.partition('\n')
        fields = line.split()
        if len(fields) < 3:
            return {}
        mark, commit, tree, its = fields[0], fields[1], fields[2], fields[3:]
        trees[commit] = tree
        if mark == '-':
            continue
        head = head or commit
        parents[commit] = its
        owners = {_owner(path) for path in paths.splitlines() if path.strip()}
        if owners:
            blocks.setdefault(commit, []).append(owners)
    against = {}
    for commit, its in parents.items():
        given = blocks.get(commit, [])
        if not its:
            against[commit] = [given[0] if given else set()]
            continue
        differing = [p for p in its if trees.get(p) != trees[commit]]
        if len(given) == len(differing):
            placed = dict(zip(differing, given))
            against[commit] = [placed.get(p, set()) for p in its]
        else:   # not expected from Git: take the merge as changing all it shows against each
            every = set().union(*given) if given else set()
            against[commit] = [every for _ in its]
    counts = {}
    for name in set().union(*(o for each in against.values() for o in each)) if against else ():
        seen, shown, todo = set(), 0, [head]
        while todo:
            commit = todo.pop()
            if commit in seen or commit not in parents:
                continue
            seen.add(commit)
            its, diffs = parents[commit], against[commit]
            if not its:
                shown += name in diffs[0]
                continue
            relevant = changed = irrelevant = False
            same = None
            for parent, diff in zip(its, diffs):
                if parent in parents or parent == bottom:
                    relevant = True
                    if name not in diff:
                        same = parent
                        break
                    changed = True
                elif name in diff:
                    irrelevant = True
            if same is not None:
                todo.append(same)
                continue
            shown += changed if relevant else irrelevant
            todo.extend(its)
        if shown:
            counts[name] = shown
    return counts


def outgoing_commits(place: Storage) -> dict:
    """Read-only disclosure, bound to the exact head and configured destination."""
    branch = _store().git(place.repo, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip()
    head = _store().git(place.repo, 'rev-parse', '--verify', 'HEAD').stdout.strip()
    base = _store().git(place.repo, 'rev-parse', '--verify', f'refs/remotes/origin/{branch}')
    preview = {'branch': branch, 'address': place.address, 'head': head, 'commits': 0,
               'brands': 0, 'items': [], 'blocked': None}
    if not branch or base.returncode:
        preview['blocked'] = 'The saved branch has no matching origin branch. Review its upstream with Git first.'
    else:
        commits = _store().git(place.repo, 'rev-list', f'{base.stdout.strip()}..{head}')
        if commits.returncode:
            preview['blocked'] = 'Git could not read the outgoing commits.'
        else:
            ids = commits.stdout.splitlines()
            preview['commits'] = len(ids)
            items = set()
            paths_by_commit = {}
            if ids:
                # A NUL marks each commit. Git quotes unusual pathnames in the name-only output.
                changed = _store().git(place.repo, 'diff-tree', '--stdin', '--root', '--format=%x00%H',
                              '--no-notes', '--name-only', '-r', input_text=commits.stdout)
                if changed.returncode:
                    preview['blocked'] = 'Git could not read the outgoing changes.'
                else:
                    for block in changed.stdout.split('\0')[1:]:
                        commit, _, paths = block.partition('\n\n')
                        paths_by_commit[commit] = paths.splitlines()
            for commit in ids:
                # diff-tree omits empty commits and merges under its default merge policy.
                paths = paths_by_commit.get(commit, [])
                owned = set()
                for path in paths:
                    bits = path.split('/')
                    if path == '.gitattributes':
                        continue
                    if bits[0] == LIBRARIES and len(bits) >= 3 and SLUG.fullmatch(bits[1]):
                        owned.add('/'.join(bits[:2]))
                    elif len(bits) >= 2 and SLUG.fullmatch(bits[0]) and bits[0] != LIBRARIES:
                        owned.add(bits[0])
                    else:
                        preview['blocked'] = 'An outgoing commit includes files outside a brand or icon library. Review and push it with Git.'
                if len(owned) != 1:
                    preview['blocked'] = 'Each outgoing commit must contain exactly one brand or icon library. Review and push it with Git.'
                items.update(owned)
            preview['brands'] = len(ids)
            preview['items'] = sorted(items)
    preview['expected'] = hashlib.sha256(canonical({**preview, 'base': base.stdout.strip()}).encode()).hexdigest()
    return preview


def push(place: Storage, expected=None) -> dict:
    if not place.team:
        raise WorkspaceError('This local brands repository has no configured remote push. The commit is the save.')
    with _store().repo_lock(place.folder), _store().write_lock(place):
        preview = outgoing_commits(place)
        if not isinstance(expected, str) or expected != preview['expected']:
            raise WorkspaceError('The push preview changed. Review the saved commits and say yes again.')
        if preview['blocked']:
            raise WorkspaceError(preview['blocked'])
        if not preview['commits']:
            raise WorkspaceError('There are no saved commits to push.')
        # An exact SHA and the configured address cannot follow a changed branch or pushurl.
        done = _store().git(place.repo, 'push', '--quiet', place.address,
                   f"{preview['head']}:refs/heads/{preview['branch']}", seconds=120)
        if done.returncode:
            raise WorkspaceError(f'The brands repository did not take the push ({reason(done)}). The brand stays committed on this computer. Review and update the repository before retrying.')
        # Keep the local tracking reference in step with the exact head just sent.
        _store().git(place.repo, 'update-ref', f"refs/remotes/origin/{preview['branch']}", preview['head'])
        return {'pushed': True, 'branch': preview['branch'], 'address': place.address}
