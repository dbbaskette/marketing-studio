"""Save: check and seal a working copy, put it in storage and commit it there.
marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from . import brand_skill
from .errors import WorkspaceError

from .brand_files import fingerprint, no_links, put, read_json
from .brand_git import Storage, identity, outgoing_commits, reason
from .brand_parts import save_ready
from .brand_terms import SEALS
from .brand_work import (
    LIVE, SAVING, TASKS, _read, folder_of, idle, inside, keep, record, target)


def _store():
    """marketing_studio.brand_store, read when called. Callers and tests replace names on it
    (LOCK, git, walk, write_json and others), and a call made here reaches what they put there."""
    from . import brand_store
    return brand_store


# Brands folders this process made a repository in with its own git init (a first Save).
# Another Save that began before it may commit there; any other repository that appears
# is refused, as before.
INITIALIZED: set[str] = set()


GITATTRIBUTES = '* -text\n'


def save(found, place: Storage, key: str) -> dict:
    """Check and seal the working copy, put it in storage and commit it there. Nothing in
    storage changes unless every check passed; the working copy is removed after.

    Harness Brand's checks and seal run without LOCK, so the page and other brands carry
    on meanwhile. This working copy is marked as saving (SAVING) for the whole Save: a
    second Save of it is refused at once, as are an edit, a new task and Discard."""
    with _store().LOCK:
        if key in SAVING:
            raise WorkspaceError('This working copy is already being saved. Wait for that save to finish.')
        work = record(key)
        idle(key)
        why = save_ready(work)
        if why:
            raise WorkspaceError(why)
        if Path(work['storage']) != place.folder:
            raise WorkspaceError(f"This working copy was made for {work['storage']}, but storage is "
                                 f'now {place.folder}. Discard it and start again.')
        here = inside(work)
        folder = here / 'pack' if work['kind'] == 'brand' else here
        if work['kind'] == 'brand':
            brand = read_json(folder / 'brand.json', {})
            if isinstance(brand, dict) and any(field in brand for field in SEALS):
                _store().write_json(folder / 'brand.json', {k: v for k, v in brand.items() if k not in SEALS})
        SAVING.add(key)
    try:
        return _save(found, place, key, work, here, folder)
    finally:
        with _store().LOCK:
            SAVING.discard(key)


def _save(found, place: Storage, key: str, work: dict, here: Path, folder: Path) -> dict:
    """Save after its first checks, with `key` in SAVING and without LOCK."""
    env = brand_skill.environment(folder_of(key) / 'brands')
    result = _store().checked(found, folder, env=env)
    with _store().LOCK:
        work = _read(key)
        work['checked'] = result
        keep(work)
    if not result['ok']:
        refused = WorkspaceError('pack check does not pass yet, so nothing was saved: '
                                 + ' '.join(result['problems'][:3]))
        refused.details = {'problems': result['problems']}
        raise refused
    if work['kind'] == 'brand':
        code, sealed = brand_skill.answer(found, ['pack', 'seal', str(folder), '--json'], env=env)
        if code != 0:
            raise WorkspaceError('pack seal did not seal the pack: ' + brand_skill.said(json.dumps(sealed), code))
        again = _store().checked(found, folder, env=env)
        if not again['ok']:
            raise WorkspaceError('The sealed pack does not pass pack check: ' + ' '.join(again['problems'][:3]))
    # Each file is read and hashed once, here; under the locks below, a file whose stat is
    # unchanged keeps its hash and only a changed one is read again.
    digests: dict = {}
    verified = fingerprint(here, digests)
    # The entire Save owns the repository lock; task files remain available after a failure.
    repo = place.folder
    with _store().repo_lock(repo), _store().write_lock(Storage(place.folder, place.team, repo, place.address)), _store().LOCK:
        work = record(key)
        running = TASKS.get(key)
        if running and running[0].is_alive():
            raise WorkspaceError('Wait for what is running to finish, or stop it, first.')
        if fingerprint(here, digests) != verified:
            raise WorkspaceError('The working copy changed during validation. Review it and save again.')
        stored = target(place, work)
        if fingerprint(stored) != work['base']:
            raise WorkspaceError('The brand in storage changed after this working copy was made. Discard it and start an update from the newer version.')
        if place.repo is None:
            place.folder.mkdir(parents=True, exist_ok=True)
            parent = _store().git(repo, 'rev-parse', '--show-toplevel')
            if parent.returncode == 0:
                # Only a repository this process made here with its own git init, during a
                # Save that began alongside this one, and with no remote, is taken; any
                # other is refused, as before.
                ours = (Path(parent.stdout.strip()).resolve() == place.folder.resolve()
                        and str(place.folder.resolve()) in INITIALIZED
                        and not _store().git(repo, 'remote').stdout.strip())
                if not ours:
                    raise WorkspaceError('The brands folder is now inside another repository. Review Shared settings, Brand.')
            else:
                made = _store().git(repo, 'init', '--quiet', '-b', 'main')
                if made.returncode:
                    raise WorkspaceError(f'Could not initialize the brands repository ({reason(made)}).')
                INITIALIZED.add(str(place.folder.resolve()))
            place = Storage(repo, False, repo, None)
        identity(repo)
        scope = [stored.relative_to(repo).as_posix()]
        dirty = _store().git(repo, 'status', '--porcelain', '--untracked-files=all', '--', *scope)
        if dirty.returncode or dirty.stdout.strip():
            raise WorkspaceError('This brand has uncommitted files in the repository. Commit or set them aside before saving this working copy.')
        attributes = no_links(repo / '.gitattributes')
        new_attributes = not attributes.exists()
        if new_attributes:
            scope.append('.gitattributes')
        staged = Path(tempfile.mkdtemp(prefix='.brand-save-', dir=repo))
        incoming, backup = staged / 'incoming', staged / 'before'
        index = staged / 'index'
        index_env = {'GIT_INDEX_FILE': str(index)}
        moved = False
        committed = False
        head = _store().git(repo, 'rev-parse', '--verify', 'HEAD')
        try:
            shutil.copytree(here, incoming, ignore=shutil.ignore_patterns('.*'))
            stored.parent.mkdir(parents=True, exist_ok=True)
            if stored.exists():
                os.replace(stored, backup)
            moved = True
            os.replace(incoming, stored)
            if new_attributes:
                put(attributes, GITATTRIBUTES.encode())
            ready = _store().git(repo, 'read-tree', head.stdout.strip() if head.returncode == 0 else '--empty', env=index_env)
            if ready.returncode:
                raise WorkspaceError(f'Could not prepare the brand commit ({reason(ready)}).')
            added = _store().git(repo, 'add', '-A', '--', *scope, env=index_env)
            if added.returncode:
                raise WorkspaceError(f'Could not prepare the brand commit ({reason(added)}).')
            what = 'brand pack' if work['kind'] == 'brand' else 'icon library'
            message = f"{'Update' if work['update'] else 'Add'} the {work['name']} {what}"
            changed = _store().git(repo, 'diff', '--cached', '--quiet', env=index_env)
            if changed.returncode not in (0, 1):
                raise WorkspaceError('Git could not compare the prepared brand commit.')
            if changed.returncode == 1:
                done = _store().git(repo, '-c', 'core.hooksPath=/dev/null', 'commit', '--quiet', '-m', message, env=index_env)
                if done.returncode:
                    raise WorkspaceError(f'Git did not record the brand ({reason(done)}). Nothing was saved; retry this working copy.')
                committed = True
                # Selected paths were clean before Save; refresh only those index entries.
                refreshed = _store().git(repo, 'reset', '--quiet', 'HEAD', '--', *scope)
                if refreshed.returncode:
                    raise WorkspaceError('The brand was committed, but Git could not refresh its index. Review the repository before continuing.')
            shutil.rmtree(folder_of(key))
            TASKS.pop(key, None)
            LIVE.pop(key, None)
        except BaseException:
            if not committed and moved:
                shutil.rmtree(stored, ignore_errors=True)
                if backup.exists():
                    os.replace(backup, stored)
                if new_attributes:
                    attributes.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(staged, ignore_errors=True)
    answer = {'saved': work['id'], 'kind': work['kind'], 'name': work['name'],
              'committed': committed, 'message': message, 'where': place.where}
    if place.team:
        answer['push'] = outgoing_commits(place)
    return answer
