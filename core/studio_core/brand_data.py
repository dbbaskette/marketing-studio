"""Where Harness Brand reads brand packs: the `brands` folder kept with the studios' storage.

What a caller needs to know
---------------------------
    folder(shared, repository, address)   # the brands folder for a studio's workspace
    unplaced(shared, checkouts)           # for a caller with no workspace of its own
    current(repository, address)          # folder(), with the shared settings read here
    environment(env, data)                # env, telling the brand command where packs are
    missing(data)                         # Setup's one line when no usable pack is there

- With a team repository (`team.repository` in the shared settings) the packs are in
  `brands/` at the root of the repository, in the studio's own workspace checkout of it.
  With local Git storage (`local.root`, by default ~/Studios) they are in
  `<local.root>/brands/`, shared by every studio. Changing storage changes where packs
  are looked for, and nothing else.
- None means the folder cannot be known: a team repository and no checkout of it, or
  shared settings that cannot be read. The brand command is then told nothing and finds
  packs its own way, or says it has none.
- The brand command is told the folder in HARNESS_BRAND_DATA, unless the person has set
  that already. Nothing here writes into the folder or runs Git.
"""
from __future__ import annotations

import os
from pathlib import Path

from studio_core.workspace_setup import DEFAULT_ROOT, same_address

VARIABLE = 'HARNESS_BRAND_DATA'
SKILL = 'Harness Brand'   # how the brand skill that reads packs names itself
FORMAT = 'https://github.com/dbbaskette/harness-brand-skill/blob/main/docs/brand-pack-format.md'
LIBRARIES = 'icon-libraries'   # a reserved name in the folder, never a brand


def folder(shared: dict, repository=None, address=None) -> Path | None:
    """The brands folder for a studio whose workspace is in `repository`, a checkout of
    `address` (None for a folder with no remote), as the shared settings say. None when it
    cannot be known: a team repository, and a workspace that is not a checkout of it."""
    shared = shared or {}
    team = shared.get('team') or {}
    if team.get('repository'):
        if repository and same_address(address, team['repository']):
            return Path(repository) / 'brands'
        return None
    return Path((shared.get('local') or {}).get('root') or DEFAULT_ROOT).expanduser() / 'brands'


def unplaced(shared: dict, checkouts=()) -> Path | None:
    """The brands folder for a caller that has no workspace of its own, such as Marketing
    Studio's Settings listing the brands. With local Git storage it is the one folder every
    studio shares, so no workspace is needed. With a team repository it is the first of
    `checkouts`, (repository folder, address) pairs of the studios' workspaces in a fixed
    order, that is a checkout of the team repository and holds a `brands` folder: every
    checkout of that repository carries the same packs once it is up to date, so any one
    will do, and one that has the folder is preferred over one that has not been brought up
    to date. None when no checkout has one."""
    team = (shared or {}).get('team') or {}
    if not team.get('repository'):
        return folder(shared)
    for repository, address in checkouts:
        found = folder(shared, repository, address)
        if found is not None and found.is_dir():
            return found
    return None


def current(repository=None, address=None) -> Path | None:
    """`folder`, with the shared settings read from the studios config. None when the
    settings cannot be read."""
    from studio_core import studios_config
    try:
        shared, problem = studios_config.read()
    except OSError:
        return None
    return None if problem else folder(shared, repository, address)


def environment(env: dict, data, environ=None) -> dict:
    """`env` with HARNESS_BRAND_DATA: the value already set in `environ` (this process's
    environment by default), which is the person's own and is kept, else `data`. Neither:
    `env` as it was. `env` itself is not changed."""
    environ = os.environ if environ is None else environ
    told = dict(env)
    if environ.get(VARIABLE):
        told[VARIABLE] = environ[VARIABLE]
    elif data is not None and not told.get(VARIABLE):
        told[VARIABLE] = str(data)
    return told


def missing(data) -> str:
    """Setup's one line for a Harness Brand that has no usable brand pack, given the brands
    folder it was told (None when none could be). It only says what is wrong: nothing is
    made or changed."""
    if data is None:
        return (f'{SKILL} cannot tell where your brand packs are: with a team repository they '
                "are in its brands folder, and this studio's workspace has no copy of it yet. "
                f'The brand pack format: {FORMAT}')
    data = Path(data)
    if not data.is_dir():
        return (f'{SKILL} finds no brands folder at {data}, so no brand is offered. Add your '
                f'brand packs there, in the brand pack format: {FORMAT}')
    return (f'{data} holds no brand pack {SKILL} can use, so no brand is offered. Check the '
            f'packs against the brand pack format: {FORMAT}')
