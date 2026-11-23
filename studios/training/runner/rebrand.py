"""Rebrand a finished deck as a copy, with a rebranding skill on this computer.

A rebranding skill (`tanzu-brand`, `true-source-brand`, `broadcom-brand`, or any folder
named `<something>-brand` that holds `scripts/brand.py`: since Harness Brand 1.1 each is a
shortcut to its one shared rebranding worker, with the brand fixed) takes a deck that is already in
Google Slides and returns a new native copy in its brand. It keeps what the deck says, its
slide order, notes, charts and pictures. Nothing is drawn again and no assistant is asked,
so it takes minutes, where drawing a deck again takes as long as the first drawing did.

What a caller needs to know
---------------------------
    rebrand.skills(home=None)                 # [{'id', 'name', 'path'}], by name
    rebrand.source_id(text)                   # the Drive ID in a deck-link.md, or None
    result = rebrand.run(skill, source, name, run_dir, execute=None)

- `run` starts the skill's own command with the Google access this computer already has
  and returns what it printed: {'status', 'url'?, 'error'?, ...}. It never edits the source
  deck. A `status` of branded or branded_with_exceptions is a finished copy.
- Nothing here signs in, stores a credential, or changes the training.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from workspace import WorkspaceError

VARIABLE = 'TRAINING_STUDIO_REBRAND_HOME'
FINISHED = ('branded', 'branded_with_exceptions')
MINUTES = 20
NO_SKILL = ('No rebranding skill is on this computer. Install one, such as true-source-brand '
            'or tanzu-brand, to rebrand a deck as a copy. If one was installed and Harness Brand '
            'has been updated since, run `node scripts/harness-brand.mjs rebrand setup` once in '
            'the Harness Brand skill folder (its `current` folder), then try again.')
NOT_SET_UP = ('{name} is not set up yet. In a terminal, run `node scripts/harness-brand.mjs '
              'rebrand setup` in the Harness Brand skill folder once, then try again. (An '
              'older brand skill is set up with `bash scripts/setup.sh --fetch` in {path}.)')


def _name(folder: Path) -> str:
    """What a skill calls its brand: its own first heading, else its folder's name."""
    try:
        for line in (folder / 'SKILL.md').read_text(encoding='utf-8').splitlines()[:40]:
            if line.startswith('# '):
                said = re.sub(r'\s+brand(ing)?$', '', line[2:].strip(), flags=re.I)
                if said:
                    return said[:60]
    except (OSError, UnicodeError):
        pass
    return folder.name.removesuffix('-brand').replace('-', ' ').title()


def skills(home: Path | None = None) -> list[dict]:
    """Every rebranding skill installed on this computer, once each. It is looked for where
    every studio looks for a brand skill (studio_core.brand_skills): each installer's own
    folder, then the Claude Code, `~/.agents`, Codex and Cursor skills folders."""
    from studio_core import brand_skills
    # A test names an empty folder here, so no run of the tests reads this person's skills.
    named = os.environ.get(VARIABLE)
    home, found, seen = home or (Path(named) if named else Path.home()), [], set()
    for folder in brand_skills.installed(home):
        # An installer's folder is `<id>/current`; a skills folder's is `<id>`.
        ident = folder.parent.name if folder.name == 'current' else folder.name
        if not ident.endswith('-brand') or ident in seen \
                or not (folder / 'scripts' / 'brand.py').is_file():
            continue
        seen.add(ident)
        found.append({'id': ident, 'name': _name(folder), 'path': str(folder)})
    return sorted(found, key=lambda one: one['name'].lower())


def python(folder: Path) -> Path:
    """The Python a set-up rebranding skill runs with: its own, in `.venv`."""
    return folder / '.venv' / 'bin' / 'python3'


def source_id(text: str) -> str | None:
    """The Drive ID a deck-link.md names, or None."""
    found = re.search(r'^- ID: ([A-Za-z0-9_-]{10,})\s*$', text or '', flags=re.M)
    return found.group(1) if found else None


def run(skill: dict, source: str, name: str, run_dir: Path, execute=None) -> dict:
    """Make the rebranded copy. Returns the skill's own result."""
    folder = Path(skill['path'])
    if not (folder / '.venv').is_dir():
        raise WorkspaceError(NOT_SET_UP.format(name=skill['id'], path=folder))
    # The skill's own Python, which its setup filled; this studio's has none of its packages.
    command = [str(python(folder)), str(folder / 'scripts' / 'brand.py'), source,
               '--name', name, '--run-dir', str(run_dir)]
    from studio_core import brand_skills
    # The brands the shared settings name (`brand.brands`), not a folder recorded earlier.
    execute = execute or (lambda command: subprocess.run(
        command, cwd=folder, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=MINUTES * 60, env=brand_skills.environment()))
    try:
        done = execute(command)
    except subprocess.TimeoutExpired:
        raise WorkspaceError(f'{skill["name"]} did not finish rebranding in {MINUTES} minutes. '
                             'A copy may still have been made: look in Google Drive before '
                             'trying again.') from None
    except OSError as failure:
        raise WorkspaceError(f'{skill["id"]} could not be started: {failure}') from None
    # Its result is the JSON it prints; a refusal is the last line of what it says aside.
    aside = (done.stderr or '').strip().splitlines()
    result = None
    for text in (done.stdout, aside[-1] if aside else ''):
        try:
            result = json.loads(text) if text and text.strip() else None
        except ValueError:
            result = None
        if isinstance(result, dict):
            break
    if not isinstance(result, dict):
        raise WorkspaceError(f'{skill["name"]} ended without saying what it made. Look in '
                             f'{run_dir} for its report.')
    return result


def says(skill: dict, result: dict) -> dict:
    """A result as the desk keeps it: finished with its address, or what went wrong."""
    url = result.get('url')
    if result.get('status') in FINISHED and url:
        return {'state': 'done', 'url': str(url)[:500],
                'exceptions': result.get('status') == 'branded_with_exceptions'}
    return {'state': 'failed', 'url': str(url)[:500] if url else None,
            'said': str(result.get('error') or f'{skill["name"]} could not finish the copy.')[:600]}
