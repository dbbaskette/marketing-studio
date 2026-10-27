"""The parts of the runner's `setup` both deck studios share. A studio binds them
into its own module with `studio_core.modules.bind`; they read that module's names.

PROBE and NOBODY stay in each studio: they are values with the product's name in them.
"""
from __future__ import annotations

import re


WHEN = {'decision': 'each-decision', 'asked': 'when-asked'}


SHARE = {said: kept for kept, said in WHEN.items()}


PLACE = 2000    # characters in an address or a path


BRANCH = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$')   # a branch a file may name


def review_choice(sent) -> tuple:
    """The level Settings' Where new work stops sent, and the one the page read."""
    if not isinstance(sent, dict) or set(sent) != {'level', 'seen'}:
        raise WorkspaceError('Send the level and the level the page read.')
    try:
        review_policy.check({'level': sent['level']})
    except ValueError as error:
        raise WorkspaceError(str(error)) from None
    return sent['level'], sent['seen']


def save_review_level(engine, level: str, seen) -> dict:
    """Make `level` the one new work starts at in every studio, under the studios config's
    lock. Refused, with nothing written, when another studio changed the level the page
    read, or the file cannot be read. The set-up described."""
    try:
        review_policy.change(studios_config.update, level, seen)
    except ValueError as error:
        raise WorkspaceError(str(error)) from None
    return describe(engine)


def save_brand(engine, sent: dict) -> dict:
    """Keep the brand skill's repository, and the release to install from it, once this
    person's own git access can read it and the release is one it has. An empty address
    forgets both. What the check found is kept for the versions, and the set-up described."""
    repository = _text(sent, 'repository')
    release = _text(sent, 'release')
    if repository is None and release is not None:
        raise WorkspaceError("A release is chosen from the brand skill's repository: give the "
                             'repository too.')
    told = seen(sent)
    shown = None if told is None else settings.seen(told)
    kept = settings.load()
    if repository is None:
        settings.save(replace(kept, brand_repository=None, brand_release=None), shown)
        return describe(engine)
    studios_config.writable()   # before git is asked anything
    found = brand_source.check(repository, release, _anywhere())
    settings.save(replace(kept, brand_repository=found['repository'],
                          brand_release=found['release']), shown)
    keeping = getattr(engine, 'upkeep', None)
    if keeping is not None:
        keeping.remember_brand(found['repository'], {entry['tag']: entry
                                                     for entry in found['releases']})
    return describe(engine)


def _same(one, other) -> bool:
    return type(one) is type(other) and one == other


def moved(space, values: dict) -> dict | None:
    """The team repository every studio shares, when this computer's workspace is a copy of
    another one, with a sentence that says so. None when they are one, and for a folder."""
    team = values.get('team') or {}
    wanted = team.get('repository')
    if space is None or space.address is None or not wanted \
            or same_address(wanted, space.address):
        return None
    return {'repository': wanted, 'branch': team.get('branch'),
            'says': f'The team repository your studios share is now {wanted}, and {PRODUCT} '
                    f'still works in its copy of {space.address}. Marketing Studio can connect '
                    'this studio: open Marketing Studio and choose Connect on its card, or join '
                    'the new repository from here.'}


def notice_path() -> Path:
    return home.data_root() / 'studios-notice.json'


def notice() -> str | None:
    """What the person is told, once, of what moving to the studios config left alone."""
    kept = home.read_json(notice_path(), None)
    says = kept.get('says') if isinstance(kept, dict) else None
    return says if isinstance(says, str) and says else None


def notice_read() -> None:
    """The person has read the notice: it is not shown again."""
    notice_path().unlink(missing_ok=True)


def _words(labels: list[str]) -> str:
    return labels[0] if len(labels) == 1 else ', '.join(labels[:-1]) + ' and ' + labels[-1]


def _text(sent: dict, name: str) -> str | None:
    value = sent.get(name)
    if value is None or value == '':
        return None
    if not isinstance(value, str) or len(value) > PLACE or '\0' in value:
        raise WorkspaceError(f'Give the {name} as text.')
    return value.strip() or None


def place(sent: dict) -> tuple[str | None, str | None]:
    """The repository's address or the folder's path, whichever was given."""
    repository, path = _text(sent, 'repository'), _text(sent, 'path')
    if repository and path:
        raise WorkspaceError('Give the repository\'s address or a folder on this computer, '
                             'not both.')
    return repository, path


def whole(path: str) -> Path:
    """A folder's path, which must say where it is whatever folder the runner was started
    in."""
    folder = Path(path).expanduser()
    if not folder.is_absolute():
        raise WorkspaceError('Give the folder\'s whole path, starting from / or from ~.')
    return folder


def names(sent: dict) -> tuple[str | None, str | None]:
    """The folder and the branch that were asked for, when they were."""
    folder, branch = _text(sent, 'folder'), _text(sent, 'branch')
    if folder is not None:
        gitstate.check_name(folder, 'A workspace folder')
    if branch is not None and (branch.startswith('-') or not hub.passes(
            _anywhere(), 'check-ref-format', '--branch', branch)):
        raise WorkspaceError(f'"{branch}" cannot be the name of a branch.')
    return folder, branch


def _check(what: str, problem: str | None) -> dict:
    return {'what': what, 'ok': problem is None, 'fix': problem}


def _identity() -> str | None:
    """Why git cannot record anything for this person, or None when it can."""
    try:
        gitstate.identity(_anywhere())
    except WorkspaceError as refusal:
        return str(refusal)
    return None


def _unwritable(probe: Path, address: str) -> str | None:
    """Why this computer may not push to a repository, or None when the remote says it
    would take a push. Nothing is sent."""
    if Path(address).is_dir() and not os.access(address, os.W_OK):
        return ('This computer may read that repository but not write to it. Ask for write '
                'access, then check again.')
    if not hub.passes(probe, 'rev-parse', '--verify', '--quiet', 'HEAD'):
        hub.run(probe, *NOBODY, 'commit', '--quiet', '--allow-empty', '-m', 'check')
    sent = hub.run(probe, 'push', '--dry-run', '--quiet', 'origin',
                   f'HEAD:refs/heads/{PROBE}')
    if sent.returncode == 0:
        return None
    return (f'This computer may read the repository but not write to it ({hub.reason(sent)}). '
            'Ask for write access, or sign git in as someone who has it, then check again.')


def _first_branch() -> str:
    """The branch git gives a repository it has just made on this computer."""
    probe = _anywhere() / f'.checking-{secrets.token_hex(4)}'
    try:
        probe.mkdir()
        hub.run(probe, 'init', '--quiet')
        return gitstate.on_branch(probe)
    except WorkspaceError:
        return 'main'
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def _local(path: str, folder: str | None, branch: str | None) -> tuple[dict, list]:
    """Look at a folder on this computer that is, or will be, a repository with no remote."""
    reach, write, slot = 'The folder can be reached', 'The folder can be written to', \
        f'The folder for {ITEMS} can be used'
    repo = whole(path).resolve()
    name = hub.name_from(repo.name)
    found = {'name': name, 'folder': folder or gitstate.FOLDER, 'branch': branch or 'main',
             'existing': False}
    later = 'This is looked at once the folder can be reached.'
    skill, unreachable = workspace.SKILL_DIR, None
    if repo == skill or repo in skill.parents or skill in repo.parents:
        unreachable = (f'{repo} holds {PRODUCT} itself. Choose a folder made for '
                       f'{ITEMS}.')
    elif repo.exists() and not repo.is_dir():
        unreachable = f'{repo} is a file. Name a folder for the workspace.'
    elif (repo / '.git').exists() and hub.run(repo, 'remote').stdout.strip():
        unreachable = (f'{repo} is a copy of a shared repository that someone works in. '
                       "Give the repository's address instead: the runner keeps a copy "
                       'of its own, so it never changes yours.')
    if unreachable:
        return found, [_check(reach, unreachable), _check(write, later), _check(slot, later)]
    nearest = next(parent for parent in (repo, *repo.parents) if parent.exists())
    unwritable = None if os.access(nearest, os.W_OK | os.X_OK) else (
        f'{nearest} cannot be written to by you. Choose a folder that can.')
    on = gitstate.on_branch(repo) if (repo / '.git').exists() else _first_branch()
    found, unusable = _marked(repo, folder, branch, name, on)
    return found, [_check(reach, None), _check(write, unwritable), _check(slot, unusable)]


def check(sent: dict) -> dict:
    """Whether a repository or a folder can be the workspace. It changes nothing."""
    repository, path = place(sent)
    if not repository and not path:
        raise WorkspaceError('Give the repository\'s address, or a folder on this computer.')
    folder, branch = names(sent)
    found, checks = (_remote(repository, folder, branch) if repository
                     else _local(path, folder, branch))
    checks.insert(2, _check('git knows who you are', _identity()))
    return {'ok': all(item['ok'] for item in checks), 'found': found, 'checks': checks}


def read(sent: dict) -> dict:
    """What the set-up screen sent, once every part of it makes sense. Refuses, with a
    sentence, before anything is changed."""
    repository, path = place(sent)
    if not repository and not path and gitstate.current() is None:
        raise WorkspaceError('Give the repository\'s address, or a folder on this computer.')
    folder, branch = names(sent)
    name, when = _text(sent, 'name'), sent.get('share_when')
    if name is not None:
        gitstate.check_name(name, 'A workspace name')
    if when is not None and when not in SHARE:
        raise WorkspaceError('Sharing is one of: ' + ', '.join(SHARE) + '.')
    return {'repository': repository, 'path': whole(path) if path else None,
            'brand_skill': sent.get('brand_skill'),
            'folder': folder, 'branch': branch, 'name': name,
            'share': SHARE[when] if when else None, 'settings': chosen(sent),
            'seen': seen(sent)}


def seen(sent: dict) -> dict | None:
    """The shared values the form that sent this was shown, as `shared` gave them, or None
    where it does not say."""
    found = sent.get('shared_seen')
    if found is not None and not isinstance(found, dict):
        raise WorkspaceError('Give shared_seen as the shared values the page was shown.')
    return found


NAMES = ('WHEN', 'SHARE', 'PLACE', 'BRANCH', 'review_choice', 'save_review_level', 'save_brand', '_same', 'moved', 'notice_path', 'notice', 'notice_read', '_words', '_text', 'place', 'whole', 'names', '_check', '_identity', '_unwritable', '_first_branch', '_local', 'check', 'read', 'seen')
METHODS = {}
