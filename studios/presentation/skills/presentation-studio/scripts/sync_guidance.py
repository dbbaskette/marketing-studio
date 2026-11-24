#!/usr/bin/env python3
"""Fetch, pin and verify the guidance a deck follows.

Guidance is the skill's SKILL.md, references and assets. It can be newer than the installed
scripts, so it is fetched from the skill's repository. Scripts are never fetched: every
command runs from the installed copy, whatever a deck was started on.

New work takes the newest guidance. A deck in progress keeps the instructions it was
saved with: its pin names their commit and nothing else, no folder and no installed version.
Nothing stops because an update happened or a cache was cleaned: a pin that cannot be read,
or whose commit the source branch does not have, continues on the current guidance and is
saved again. The one refusal is saved instructions that need a newer Presentation Studio
than the one installed.

Only guidance this helper fetched itself from the source branch is used. Of a deck's
pin only the commit is read, and nothing else from it is trusted: its guidance is kept in
the per-user data folder by commit, checked against that commit's own files, and the commit
must be on the source branch. git runs without the user's config or environment, and the
local copy of the branch is used only as this helper made it; anything else is rebuilt.

The fetching, pinning and checking are shared with Training Studio
(`studio_core.guidance_sync`) and bound into this module; Presentation Studio's words, its
source, how its helper is run and how a deck folder is known stay here.
"""
import sys

if sys.version_info < (3, 11):
    sys.exit('Presentation Studio needs Python 3.11 or newer; this is '
             + sys.version.split()[0] + '.')

# ruff: noqa: F821  names bound from studio_core.guidance_sync are unseen by a linter;
# the root test_studio_scripts checks the bound parts, and the suites call the rest.

import os
from pathlib import Path, PurePosixPath  # noqa: F401  PurePosixPath: read by the shared parts

import home  # noqa: F401  read by the shared parts
from studio_core import guidance_sync as _shared
from studio_core import modules

PRODUCT, ITEM = 'Presentation Studio', 'deck'
RUNTIME = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = {'repository': 'https://github.com/dbbaskette/marketing-studio.git',
                  'branch': 'main', 'manifest': 'studios/presentation/guidance/manifest.json'}
STATE_DIR = '.presentation-studio'
SOURCE_VARIABLE = 'PRESENTATION_STUDIO_SOURCE'
MANIFEST_VARIABLE = 'PRESENTATION_STUDIO_SOURCE_MANIFEST'
CONTINUES = ('The instructions saved with this deck could not be used, so it continues '
             'on the current ones.')
modules.bind(globals(), _shared, _shared.NAMES)


class SyncError(Exception):
    """A reason guidance could not be fetched or used, to show as it is."""


class NeedsNewer(SyncError):
    """Guidance that asks for a newer Presentation Studio than the one installed. `needed`
    is the version it asks for."""

    def __init__(self, needed: str):
        self.needed = needed
        super().__init__(f'The newest guidance needs Presentation Studio {needed} or later; '
                         f'{runtime_version()} is installed. Update the skill to use it.')


def helper() -> str:
    """How to run the helper: the installer's `presentation` command when that is what ran
    this or it stands beside the installed copy, since it finds a Python new enough;
    otherwise what that command runs, the runner's studio.py: beside the scripts in an
    installed copy, at the top of a checkout. Never a `versions/<id>` path: see `address`."""
    command = os.environ.get('PRESENTATION_STUDIO_HELPER')
    if command and Path(command).is_file():
        return command
    base = address()
    command = base.parent / 'presentation'
    if base != RUNTIME and base.name == 'current' and command.is_file():
        return str(command)
    places = (base / 'runner' / 'studio.py', base.parent.parent / 'runner' / 'studio.py')
    return str(next((place for place in places if place.is_file()), places[0]))


def has_item(project: Path) -> bool:
    """Whether `project` holds a deck."""
    return (project / 'run.json').is_file()


if __name__ == '__main__':
    sys.exit(main())
