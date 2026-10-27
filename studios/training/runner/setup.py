"""Setting this computer up for the runner: the workspace, the agent, the limits and how a
deck's previews are rendered.

What a caller needs to know
---------------------------
    setup.describe(engine)        the workspace, the default agent and the limits, as saved,
                                  with what this computer has for previews and for a brand
    setup.check(sent)             whether a repository or a folder can be used; changes nothing
    setup.save_brand(engine, sent)   the brand skill's repository, once it can be read
    wanted = setup.read(sent)     what the set-up screen sent, once it all makes sense
    setup.apply(engine, wanted)   set the workspace up, save the settings, and describe them

- A workspace is given as a repository's address or as a folder on this computer, never
  both. A repository is cloned into a copy of the runner's own; a folder is used as it is.
- `check` looks before anything is written: the place can be reached and written to, git
  knows who the person is, and the folder for trainings is not another tool's. It reads a
  repository through a shallow copy that it removes again, and asks the remote whether it
  would take a push without sending one.
- `found` says what the place already holds. When a Training Studio `hub.json` is there,
  its name, folder and branch are the ones that will be used, and nothing it says is asked
  for again.
- When to share is written `each-decision` or `when-asked` here; `gitstate` calls them
  `decision` and `asked`.
- `previews` is the person's choice between LibreOffice on this computer (`local`) and
  Google Drive (`drive`), with which of the two this computer can use (`drive` is None
  once LibreOffice is chosen: Drive is not asked then), and the preview files the runner
  has left in Drive. It never deletes one, so it lists them. `brand` is the brand skill
  that was found and the brands it has, with every brand skill found under `skills` as
  {'name', 'path', 'chosen'}; `brand_skill` names one of those paths to use. Both are
  asked of the engine, which looks at this computer and reuses the look, so asking for
  this again starts nothing while nothing has changed. `brand` also has `repository` and
  `release`: where the brand skill is installed from, as kept by `save_brand`.
- `save_brand(engine, {"repository", "release"})` keeps the brand skill's repository once
  `brand_source.check` can read it with this person's git access, and refuses in a sentence
  otherwise. An empty repository forgets it. A brand skill installed by hand is used
  either way.
- `notify` is {'on', 'can', 'problem'}: whether the runner tells the person through the
  computer's own notifications when no page is open, whether this computer has a way to,
  and a sentence when it has none. It is sent as true or false, and cannot be turned on
  where there is no way.
- `updates` is {'look'}: whether the runner looks online, at most once a day, for newer
  releases. It is sent as `look_for_updates`, true or false. `upkeep` is what the runner
  found when it last looked at Training Studio and its skills on this computer, or None
  where it does not look (see `upkeep.Upkeep.report`).
- The values every studio shares are kept only in the studios config (`studios_config`),
  and saving one here writes it there: the agent, its model and its level and the brand
  skill's repository and release (see `settings`), when to share for a team workspace, and
  the team repository when set-up joins another one, with its branch where the file names
  no branch for that repository. A folder on this computer writes no `team` and no `share`.
  While the file cannot be read, a save that would change one of them is refused before
  anything changes, and one that changes none goes through. Every write that depends on
  what the file holds is worked out from it under the lock every studio takes to write it,
  so a value another studio writes meanwhile is kept, or the save is refused.
- `shared_seen`, sent with the set-up or with the brand skill's repository, is the `shared`
  the page's form was shown. Then only what the person changed from it is written: a value
  another studio changed while the form was open is kept, and a change to a value another
  studio changed too is refused, in a sentence, before anything changes: before the
  workspace is joined or moved, and before anything is written. Without it, a value is
  written where it differs from what the file holds now. Where another studio changes one
  while the workspace is being joined or moved, the workspace stays as it now is, with the
  team repository written as for any join, and the refusal says so instead.
- `shared` is what the file holds that Training Studio can use, in the file's own shape:
  `team` {repository, branch}, `assistant` {agent, model, effort}, `brand` {repository,
  release, brand, variant}, `output`, `share` and `research` {sites}, your sites as
  canonical https addresses. A value that would be refused here is left out, and so is
  anything Training Studio does not use. `shared_problem` is a sentence when the file could
  not be read, which is then as if there were none. The page fills in a first set-up's
  team repository, a new training's deck and the sites its research may keep to from
  `shared`. Training Studio never writes your sites: they are changed in Shared settings.
- `team_moved` is {"repository", "branch", "says"} when the file names a team repository
  that is not the one this computer's workspace is a copy of, which happens when it is
  changed in another studio, and None otherwise. The workspace is never moved by itself:
  `says` is one sentence for the page, which offers to join the new one through set-up. A
  folder on this computer is never compared, and only the repository is: a Training Studio
  folder in a repository keeps the branch its hub.json names.
- `migrate()`, when the runner starts, moves the shared values this computer kept as its
  own before they were shared (agent, model, level, the brand skill's repository and
  release in runner.json; when to share, and the team repository and branch it joined, in
  the workspace record) into the file where it has none, and takes them out of runner.json
  and the record. The record keeps its repository and branch, which say what the clone is.
  When to share moves from a record of a team repository even where its clone or marker is
  gone, and leaves the record only once the file holds it.
  A value the file holds already stays as it is. A model and a level go only beside the
  same agent, a release only beside the same repository, and a branch only beside the same
  team repository. Where a value differed, `shared_notice` is a sentence that says so, until
  `notice_read()`. While the file cannot be read nothing is moved. What moves is worked out
  again under the file's lock, so a value another studio writes meanwhile stays.
"""
from __future__ import annotations

import os  # noqa: F401  read by the shared parts
import re  # noqa: F401  read by the shared parts
import secrets
import shutil
from dataclasses import replace
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
from studio_core import research_sites, review_policy
from studio_core.workspace_setup import same_address
import home
import hub
import workspace  # noqa: F401  read by the shared parts
from workspace import WorkspaceError

from runner import brand_source, gitstate, settings, studios_config  # noqa: F401  read by the shared parts

from studio_core import modules
from studio_core.shared_runner import setup as _shared
PRODUCT, ITEMS = 'Training Studio', 'trainings'
modules.bind(globals(), _shared, _shared.NAMES)

PROBE = 'training-studio-write-check'   # a branch name that is asked about, never made
NOBODY = ('-c', 'user.name=Training Studio', '-c', 'user.email=check@example.invalid')
WORD = 100      # characters in a brand's or a variant's name
OUTPUTS = ('google', 'pptx')    # what a studio makes by default, as the shared file says


def describe(engine) -> dict:
    """What is set up on this computer, in the shape the page reads."""
    space, chosen = engine.workspace, settings.load()
    found = None if space is None else {
        'name': space.name, 'repository': space.address, 'path': str(space.repo),
        'folder': space.folder, 'branch': space.branch, 'share_when': WHEN[space.share],
        **engine.shared()}
    needs = engine.deck_needs()
    can, problem = engine.notifier.can()
    values, unread = shared()
    return {'configured': space is not None, 'workspace': found,
            'review_level': review_policy.level({'review_policy': review_policy.capture()}),
            'shared': values, 'shared_problem': unread,
            'team_moved': moved(space, values), 'shared_notice': notice(),
            'notify': {'on': chosen.notify, 'can': can, 'problem': problem},
            'updates': {'look': chosen.look_for_updates},
            'upkeep': keeping.report() if (keeping := getattr(engine, 'upkeep', None))
            else None,
            'agent': {'default': chosen.agent, 'model': chosen.model,
                      'effort': chosen.effort},
            'limits': chosen.limits,
            'previews': {'how': chosen.previews, 'pool': needs['pool'], 'drive': needs['drive'],
                         'local': needs['local'], 'left': engine.previews_left()},
            'brand': {**needs['brand'], 'skills': engine.brand_skills(),
                      'repository': chosen.brand_repository,
                      'release': chosen.brand_release}}


# --- the studios config ------------------------------------------------------------------

def _group(found: dict, name: str) -> dict:
    value = found.get(name)
    return value if isinstance(value, dict) else {}


def _word(value, most: int = WORD) -> str | None:
    """A plain word from the file, or None for anything else."""
    if not isinstance(value, str) or not value.strip() or len(value) > most \
            or any(ord(mark) < 32 for mark in value):
        return None
    return value.strip()


def shared() -> tuple[dict, str | None]:
    """The studios config's values that Training Studio can use, in the file's own shape,
    and a sentence when the file could not be read. A value that would be refused here, such
    as an address that carries a password, is left out."""
    found, problem = studios_config.read()
    team, brand = (_group(found, name) for name in ('team', 'brand'))
    branch = _word(team.get('branch'), 200)
    usable = settings.from_shared(found)
    values = {
        'team': {'repository': settings.passes(settings.check_repository,
                                                _word(team.get('repository'), PLACE)),
                 'branch': branch if branch and BRANCH.match(branch) and '..' not in branch
                 and not branch.endswith(('/', '.', '.lock')) else None},
        'assistant': {name: usable[name] for name in ('agent', 'model', 'effort')},
        'brand': {'repository': usable['brand_repository'],
                  'release': usable['brand_release'], 'skill': usable['brand_skill'],
                  'brand': _word(brand.get('brand')), 'variant': _word(brand.get('variant'))},
        'output': found.get('output') if found.get('output') in OUTPUTS else None,
        'render': {'previews': settings.shared_now(found)['previews']},
        'models': {'mode': _group(found, 'models').get('mode')
                   if _group(found, 'models').get('mode') in ('single', 'by_task') else None},
        'share': found.get('share') if found.get('share') in gitstate.SHARE else None,
        # Your sites, which a new training's research may keep to. Read here and never
        # written: the list is changed in Shared settings.
        'research': {'sites': research_sites.defaults(found) or None}}
    kept = {}
    for key, value in values.items():
        if isinstance(value, dict):
            value = {name: inner for name, inner in value.items() if inner is not None}
        if value:
            kept[key] = value
    return kept, problem


# What the person is told of a value the file held already, when this computer had another.
LABELS = {'agent': 'the agent', 'model': 'the model', 'effort': 'the reasoning level',
          'brand_repository': "the brand skill's repository",
          'brand_release': "the brand skill's release", 'share': 'when to share',
          'previews': 'slide previews', 'brand_skill': 'the installed brand skill'}


def migrate() -> list[str]:
    """Move the shared values this computer kept as its own into the studios config, where it
    has none of them, and take them out of this computer's files. A value the file holds
    already is left as it is, and the notice says so. Answers what was written, as the keys
    of the file, such as "assistant.agent". Nothing moves while the file cannot be read or
    written: this computer's own copies then wait for the next start."""
    found, problem = studios_config.read()
    if problem:
        return []
    from studio_core.preferences import ready
    if ready(found):
        # A completed shared setup owns even empty choices (automatic previews/brand).
        settings.forget_own()
        gitstate.forget_own_share()
        return []
    kept, share, record = settings.own(), gitstate.own_share(), gitstate.current()
    moving = {}

    def wanted(held: dict) -> dict:
        moving['changes'], moving['differed'] = _moving(held, kept, share, record)
        return moving['changes']

    # Worked out again under the lock, from what the file holds then.
    if wanted(found):
        try:
            studios_config.update(wanted)
        except WorkspaceError:
            return []
    settings.forget_own()
    gitstate.forget_own_share()
    differed = moving['differed']
    if differed:
        home.write_json(notice_path(), {'says': (
            f'Training Studio now keeps the values every studio shares only in '
            f'{studios_config.shown(studios_config.path())}, which said otherwise for '
            f'{_words(differed)}, so what this computer had chosen for those is no longer '
            'used.')})
    return [f'{key}.{name}' if isinstance(value, dict) else key
            for key, value in moving['changes'].items()
            for name in (value if isinstance(value, dict) else [None])]


def _moving(found: dict, kept: dict, share: str | None, record) -> tuple[dict, list]:
    """What moves into the studios config while it holds `found`, and what it said otherwise
    for, as the notice names them."""
    mine = [(*settings.SHARED[name], name, value) for name, value in kept.items()]
    if share:
        mine.append((None, 'share', 'share', share))
    if record is not None and record.address:
        team = _group(found, 'team')
        mine.append(('team', 'repository', None, record.address))
        if team.get('repository') is None or same_address(team['repository'], record.address):
            mine.append(('team', 'branch', None, record.branch))
    # A model and a level are for their agent, and a release for its repository: beside
    # another agent or another repository in the file, this computer's are not used.
    owns = {'model': 'agent', 'effort': 'agent', 'brand_release': 'brand_repository'}
    others = {name for name in ('agent', 'brand_repository') if name in kept
              and _group(found, settings.SHARED[name][0]).get(settings.SHARED[name][1])
              not in (None, kept[name])}
    changes, differed = {}, []
    for group, key, name, value in mine:
        if group is not None and found.get(group) is not None \
                and not isinstance(found[group], dict):
            continue    # a value of the file's own that is not an object is not replaced
        held = _group(found, group).get(key) if group else found.get(key)
        if owns.get(name) in others:
            if not _same(held, value):
                differed.append(LABELS[name])
        elif held is None:
            (changes.setdefault(group, {}) if group else changes)[key] = value
        elif not _same(held, value) and name is not None:
            differed.append(LABELS[name])
    return changes, differed


# --- what was sent -----------------------------------------------------------------------


def _anywhere() -> Path:
    """A folder to run git in when no repository is involved yet."""
    base = gitstate.clones()
    base.mkdir(parents=True, exist_ok=True)
    return base


# --- looking before anything is written --------------------------------------------------


def _marked(repo: Path, folder: str | None, branch: str | None, name: str,
            on: str) -> tuple[dict, str | None]:
    """What a repository's folder for trainings holds, and why it cannot be used if it
    cannot."""
    found = {'name': name, 'folder': folder or gitstate.FOLDER, 'branch': branch or on,
             'existing': False}
    try:
        where = gitstate.find_folder(repo, folder)
        marker = gitstate.marker(repo, where)
        gitstate.check_name(name, 'A workspace name')
    except WorkspaceError as refusal:
        return found, str(refusal)
    found['folder'] = where
    if marker is None:
        slot = repo / where
        if slot.is_symlink() or (slot.exists() and not slot.is_dir()):
            return found, (f'{where} in this repository is not a plain folder, so it cannot '
                           'hold trainings. Name a different folder.')
        return found, None
    found.update(name=marker['name'], branch=marker['branch'], existing=True)
    if branch is not None and branch != marker['branch']:
        return found, (f"{where}/{gitstate.MARKER} says this workspace's work is on the "
                       f"branch {marker['branch']}, not {branch}. Leave the branch out to "
                       'use it.')
    return found, None


def _remote(address: str, folder: str | None, branch: str | None) -> tuple[dict, list]:
    """Look at a repository by its address, through a shallow copy that is then removed."""
    name = hub.name_from(address)
    found = {'name': name, 'folder': folder or gitstate.FOLDER, 'branch': branch or 'main',
             'existing': False}
    reach, write, slot = 'The repository can be reached', 'The repository can be written to', \
        'The folder for trainings can be used'
    later = 'This is looked at once the repository can be reached.'
    if hub.ADDRESS_WITH_SECRET.match(address):
        return found, [_check(reach, 'That address carries a password or token. Give the '
                              'address without it; git signs in with your own credentials.'),
                       _check(write, later), _check(slot, later)]
    base = _anywhere()
    listed = hub.run(base, 'ls-remote', '--symref', '--', address, 'HEAD', 'refs/heads/*')
    if listed.returncode != 0:
        return found, [_check(reach, f'The repository could not be reached '
                              f'({hub.reason(listed)}). Check the address, and that git can '
                              'sign in to it without asking.'),
                       _check(write, later), _check(slot, later)]
    heads = {line.split('\t')[1].removeprefix('refs/heads/')
             for line in listed.stdout.splitlines()
             if '\t' in line and line.split('\t')[1].startswith('refs/heads/')}
    probe = base / f'.checking-{secrets.token_hex(4)}'
    try:
        wanted = ['--branch', branch] if branch in heads else []
        cloned = hub.run(base, 'clone', '--quiet', '--depth', '1', '--no-tags', *wanted,
                         *hub.COPY_AS_IS, '--', address, str(probe))
        if cloned.returncode != 0:
            return found, [_check(reach, f'The repository could not be read '
                                  f'({hub.reason(cloned)}).'),
                           _check(write, later), _check(slot, later)]
        found, unusable = _marked(probe, folder, branch, name, gitstate.on_branch(probe))
        return found, [_check(reach, None), _check(write, _unwritable(probe, address)),
                       _check(slot, unusable)]
    finally:
        shutil.rmtree(probe, ignore_errors=True)


# --- setting it up -----------------------------------------------------------------------

def chosen(sent: dict) -> settings.Settings:
    """This computer's settings, with what was sent in place of what was saved."""
    kept = settings.load()
    limits = sent.get('limits')
    if limits is not None and not isinstance(limits, dict):
        raise WorkspaceError('Give the limits as step_seconds, training_dollars and parallel.')
    agent = sent.get('agent') or kept.agent
    same = agent == kept.agent
    model = sent['model'] if 'model' in sent else (kept.model if same else None)
    effort = sent['effort'] if 'effort' in sent else (kept.effort if same else None)
    wanted = {name: (limits or {}).get(name, getattr(kept, name))
              for name in ('step_seconds', 'training_dollars', 'parallel')}
    previews = sent['previews'] if sent.get('previews') is not None else kept.previews
    skill = sent['brand_skill'] if sent.get('brand_skill') is not None else kept.brand_skill
    notify = sent['notify'] if sent.get('notify') is not None else kept.notify
    look = sent['look_for_updates'] if sent.get('look_for_updates') is not None \
        else kept.look_for_updates
    return settings.check(replace(kept, agent=agent, model=model, effort=effort,
                                  previews=previews, brand_skill=skill, notify=notify,
                                  look_for_updates=look, **wanted))


def stale(what: str) -> WorkspaceError:
    return settings.Stale(what)


def _address(found: dict) -> str | None:
    """The team repository the studios config names, as it is written there."""
    named = _group(found, 'team').get('repository')
    return named if isinstance(named, str) else None


def _team(joined: gitstate.Workspace, was: str | None) -> None:
    """Make the team repository just joined the one every studio shares, with its branch
    where the file names no branch for that repository. The file is read under its lock: a
    team repository another studio wrote there since set-up read `was` is kept, and
    `team_moved` says so, and a branch it names for this one stays."""
    def wanted(found: dict) -> dict:
        held, named = _group(found, 'team'), _address(found)
        if named is not None and named != was and not same_address(named, was) \
                and not same_address(named, joined.address):
            return {}
        team = {'repository': joined.address}
        if held.get('branch') is None or not same_address(named, joined.address):
            team['branch'] = joined.branch
        return {'team': team}
    studios_config.update(wanted)


def apply(engine, wanted: dict) -> dict:
    """Set the workspace up, save the settings, and describe both.

    Without a repository or a folder, the workspace stays as it is and only the settings
    and when to share change. A save that changes a value every studio shares is refused
    before anything changes while the studios config cannot be read.
    """
    repository, path, share = wanted['repository'], wanted['path'], wanted['share']
    named = wanted.get('brand_skill')
    if named is not None and named not in [skill['path'] for skill in engine.brand_skills()]:
        raise WorkspaceError('Choose the brand skill from those found on this computer.')
    can, problem = engine.notifier.can()
    if wanted['settings'].notify and not can:
        raise WorkspaceError(problem)
    before = engine.workspace
    # What the form was shown: only what the person changed from it is written, and a
    # change to a value another studio changed meanwhile is refused.
    told = wanted.get('seen')
    shown = None if told is None else settings.seen(told)
    holds = studios_config.read()[0]
    now = shared()[0]
    team = bool(repository) and (before is None or not same_address(before.address,
                                                                     repository))
    if team and told is not None:
        was, held = (_group(found, 'team').get('repository') for found in (told, now))
        if held and not same_address(held, was) and not same_address(held, repository):
            raise stale('The team repository')
    # When to share belongs to a team workspace: a folder on this computer never sets it.
    was = gitstate.shared_share() if told is None else (
        told.get('share') if told.get('share') in gitstate.SHARE else gitstate.SHARE[0])
    if not (repository or (not path and before is not None and before.address)) \
            or share == was:
        share = None
    elif gitstate.shared_share() not in (was, share):
        raise stale('When to share')
    # A change to a value another studio changed too is refused here, before the workspace
    # is joined or moved and before anything is written.
    settings.writes(wanted['settings'], shown or settings.load(), holds)
    if team or share or settings.changes(shown or settings.load(), wanted['settings']):
        studios_config.writable()
    if not repository and not path:
        if share:
            gitstate.share_when(share)
    else:
        moving = before is not None and (
            before.address != repository if repository
            else before.address is not None or before.repo != path.resolve())
        if moving and any((engine.brief(root) or {}).get('state') == 'working'
                          for root in engine.trainings()):
            raise WorkspaceError('Trainings are working in the workspace this computer uses '
                                 'now. Pause or stop them before moving to another.')
        with engine.files:
            if repository:
                gitstate.join(repository, wanted['folder'], wanted['branch'],
                              wanted['name'], share)
            else:
                gitstate.local(path, wanted['folder'], wanted['branch'], wanted['name'])
        if team:
            _team(gitstate.current(), _address(holds))
    try:
        settings.save(wanted['settings'], shown)
    except settings.Stale as refusal:
        # Another studio changed a value while the workspace was joined or moved, after it
        # was looked at: the workspace stays as it is now, and the sentence says so.
        if not repository and not path:
            raise
        where = f'joined {repository}' if repository else f'now keeps its trainings in {path}'
        raise WorkspaceError(f'Training Studio {where}, but {refusal.what[0].lower()}'
                             f'{refusal.what[1:]} was changed in another studio meanwhile, so '
                             'your other settings were not saved. Set-up shows them as they '
                             'are now: look again, then save.') from None
    engine.saved()
    engine.resume()
    return describe(engine)
