"""The brands repository: every brand the studios use, kept apart from any team's storage.

What a caller needs to know
---------------------------
    brand_data.place(address)     # the folder the brands are read from, without changing anything
    brand_data.bring(address)     # on the person's request: clone or update it, and record it
    brand_data.harness_folder()   # the folder Harness Brand reads by itself, or None
    brand_data.chosen(address)    # `place(address)`, or Harness Brand's folder with no address

- The shared setting `brand.brands` names the repository: an https or ssh Git address, or an
  absolute folder on this computer. A folder is used as it is and never changed.
- A Git address is cloned into Marketing Studio's data folder (MARKETING_STUDIO_DATA, else
  ~/.local/share/marketing-studio), under `brands/`, and brought up to date only by `bring`:
  a fast-forward pull, never a merge, a reset or a push. Nothing here runs by itself.
- `bring` records the folder in the file `harness-brand data --set` writes
  (XDG_CONFIG_HOME, else ~/.config, then harness-brand/data), which is how Harness Brand
  and its brand shortcuts find the brands wherever they are run: from a studio, from chat
  or by hand.
- With no `brand.brands` set, the brands are the ones Harness Brand reads (`harness_folder`):
  the folder HARNESS_BRAND_DATA names, else the one `harness-brand data --set` recorded, else
  the local brands folder `harness-brand data --install` fills. So Marketing Studio, the
  studios, the brand shortcuts and Harness Brand run by hand all read one folder. `bring`
  then uses that folder as it is and records nothing.
- A brands folder holds one folder per brand with its Harness Brand pack (`<id>/pack/`)
  or rebranding profile (`<id>/rebrand/`, or `<id>/apply-brand/` as older brands folders
  have it); `bring` refuses a repository that holds none.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from studio_core import preferences
from studio_core.process_lock import ProcessRLock

SECONDS = 300     # for one clone or pull
# What makes a folder a brand: its Harness Brand pack, its rebranding profile (Harness Brand
# 1.1), or the apply-brand profile older brands folders hold.
PROFILES = ('pack', 'rebrand', 'apply-brand')


def data_root() -> Path:
    return Path(os.environ.get('MARKETING_STUDIO_DATA', '~/.local/share/marketing-studio')).expanduser()


def pointer_file() -> Path:
    """The file Harness Brand reads the brands folder from when nothing else names one."""
    config = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    return Path(config) / 'harness-brand' / 'data'


def harness_folder() -> Path | None:
    """The brands folder Harness Brand reads when no command names one, in its own order:
    HARNESS_BRAND_DATA, the recorded folder, then its local brands folder. None when it has
    none of them."""
    named = os.environ.get('HARNESS_BRAND_DATA', '').strip()
    if named:
        return Path(named).expanduser()
    try:
        recorded = pointer_file().read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError):
        recorded = ''
    if recorded:
        return Path(recorded).expanduser()
    local = (Path.home() / 'Library' / 'Application Support' / 'Harness Brand' / 'brands'
             if sys.platform == 'darwin' else
             Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
             / 'harness-brand' / 'brands')
    return local if local.is_dir() else None


NO_FOLDER = ('Harness Brand has no brands folder yet. Give the brands repository here and save '
             'settings, or set one with `harness-brand data --set FOLDER`.')


def chosen(address) -> Path:
    """The folder Marketing Studio reads brands from: the setting's, or with none set the one
    Harness Brand reads. Refuses when there is neither."""
    if isinstance(address, str) and address.strip():
        return place(address.strip())
    folder = harness_folder()
    if folder is None:
        raise preferences.WorkspaceError(NO_FOLDER)
    return folder


def _local(address: str) -> bool:
    return Path(address).expanduser().is_absolute() and not re.match(r'^[\w.-]+@[\w.-]+:', address)


def place(address: str) -> Path:
    """The folder the brands are read from: the folder itself, or where its clone is kept."""
    preferences.repository(address)
    if _local(address):
        return Path(address).expanduser()
    name = re.sub(r'[^A-Za-z0-9._-]', '-', address.rstrip('/').rsplit('/', 1)[-1].rsplit(':', 1)[-1])
    name = name.removesuffix('.git').strip('.-') or 'brands'
    return data_root() / 'brands' / f'{name}-{hashlib.sha256(address.encode()).hexdigest()[:8]}'


def brands(folder: Path) -> list[str]:
    """The brand ids in a brands folder: folders with a pack or a rebranding profile."""
    try:
        return sorted(entry.name for entry in folder.iterdir() if entry.is_dir() and not entry.name.startswith('.')
                      and any((entry / kind / 'brand.json').is_file() for kind in PROFILES))
    except OSError:
        return []


def _git(*args, cwd=None) -> subprocess.CompletedProcess:
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
    try:
        return subprocess.run(['git', *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=SECONDS)
    except FileNotFoundError:
        raise preferences.WorkspaceError('Git is needed to get the brands repository. Install Git, then try again.')
    except subprocess.TimeoutExpired:
        raise preferences.WorkspaceError('The brands repository did not answer in time. Check the network, then try again.')


def _said(done: subprocess.CompletedProcess) -> str:
    lines = [line.strip() for line in (done.stderr or done.stdout or '').splitlines() if line.strip()]
    return lines[-1] if lines else f'git ended with exit code {done.returncode}'


def _clone(address: str, folder: Path) -> None:
    folder.parent.mkdir(parents=True, exist_ok=True)
    pending = folder.parent / f'.getting-{secrets.token_hex(4)}'
    try:
        done = _git('clone', '--quiet', '--', address, str(pending))
        if done.returncode:
            raise preferences.WorkspaceError(f'Could not get {address}: {_said(done)}. Check the address, and that '
                                             'git can sign in to it without asking.')
        pending.replace(folder)
    finally:
        shutil.rmtree(pending, ignore_errors=True)


def _update(address: str, folder: Path) -> None:
    origin = _git('remote', 'get-url', 'origin', cwd=folder)
    if origin.returncode or origin.stdout.strip() != address:
        raise preferences.WorkspaceError(f'{folder} is not a copy of {address}. Move it aside, then try again.')
    done = _git('pull', '--ff-only', '--quiet', cwd=folder)
    if done.returncode:
        raise preferences.WorkspaceError(f'Could not update the brands from {address}: {_said(done)}. The copy at '
                                         f'{folder} was left as it was.')


def record(folder: Path) -> None:
    """Record the brands folder for Harness Brand and its brand shortcuts, as `harness-brand data --set` does."""
    target = pointer_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_name(f'.data-{secrets.token_hex(4)}')
    pending.write_text(f'{folder}\n')
    pending.replace(target)


def lock_path(folder: Path) -> Path:
    identity = hashlib.sha256(str(Path(folder).resolve()).encode()).hexdigest()
    return data_root() / 'locks' / f'brands-{identity}.lock'


def bring(address) -> dict:
    # Get brands and Brands Save/Push share one stable lock, even before a clone exists.
    if not isinstance(address, str) or not address.strip():
        return _following()
    with ProcessRLock(lambda: lock_path(place(address.strip())), refusal=preferences.WorkspaceError):
        return _bring(address)


def _following() -> dict:
    """With no repository set: the brands Harness Brand already reads, used as they are."""
    folder = chosen(None)
    if not folder.is_dir():
        raise preferences.WorkspaceError(f'Harness Brand reads its brands from {folder}, and there is no folder there.')
    found = brands(folder)
    if not found:
        raise preferences.WorkspaceError(f'{folder} holds no brands: no folder with a pack/ or rebrand/ in it.')
    return {'folder': str(folder), 'brands': found, 'action': 'used', 'following': True}


def _bring(address) -> dict:
    """Get the brands repository the setting names, or bring its copy up to date, and record it.
    {'folder', 'brands', 'action'}, the action being 'used', 'cloned' or 'updated'."""
    if not isinstance(address, str) or not address.strip():
        raise preferences.WorkspaceError('Give the brands repository first, then save settings.')
    address = address.strip()
    folder = place(address)
    if _local(address):
        if not folder.is_dir():
            raise preferences.WorkspaceError(f'There is no folder at {folder}.')
        action = 'used'
    elif (folder / '.git').exists():
        _update(address, folder)
        action = 'updated'
    else:
        _clone(address, folder)
        action = 'cloned'
    found = brands(folder)
    if not found:
        if action == 'cloned':   # a fresh copy that holds no brands is not kept
            shutil.rmtree(folder, ignore_errors=True)
        raise preferences.WorkspaceError(f'{address} holds no brands: no folder with a pack/ or rebrand/ in it.')
    # Harness Brand reads this folder from now on. When it read another until now, say which,
    # so nobody is left with two folders of brands without knowing.
    before = harness_folder()
    record(folder)
    replaced = before is not None and before.resolve() != folder.resolve()
    return {'folder': str(folder), 'brands': found, 'action': action,
            **({'replaced': str(before)} if replaced else {})}
