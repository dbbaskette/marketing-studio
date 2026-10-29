"""Each studio's remembered workspace, read from its own records without starting it.

A studio keeps which workspace it uses in its per-user data folder: `workspace.json` names
a repository folder and the studio's folder in it, whose `hub.json` says which repository
and branch the work lives in. Blog Studio's native launcher also remembers a plain writing
folder in `page.json`. Only those records are read, never a folder's name; a record whose
folder is gone counts as no workspace.
"""
import json
import os
from pathlib import Path

from studio_core import workspace_setup

from . import catalog

DATA = {'blog': 'BLOG_STUDIO_DATA', 'training': 'TRAINING_STUDIO_DATA',
        'presentation': 'PRESENTATION_STUDIO_DATA', 'infographic': 'INFOGRAPHIC_STUDIO_DATA'}


def data_root(identifier):
    """The studio's per-user data folder, as its own launcher finds it."""
    named = os.environ.get(DATA[identifier])
    if named:
        return Path(named).expanduser()
    return Path.home() / '.local/share' / catalog.STUDIOS[identifier][1]


def _json(path):
    try:
        if path.is_symlink():
            return None
        found = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def _marker(folder, tool):
    """The studio's hub.json in a folder, when it is that studio's."""
    found = _json(Path(folder) / 'hub.json')
    if found and found.get('tool') == tool and isinstance(found.get('branch'), str):
        return found
    return None


def remembered(identifier):
    """The workspace a studio remembers: {'root', 'repository', 'branch'}, or None."""
    data, tool = data_root(identifier), catalog.STUDIOS[identifier][1]
    kept = _json(data / 'workspace.json')
    if identifier == 'infographic' and kept and kept.get('schema') == 1 and isinstance(kept.get('root'), str):
        root = Path(kept['root'])
        marker = _json(root / '.infographic-studio/workspace.json') if root.is_absolute() and not root.is_symlink() else None
        if marker and marker.get('product') == 'Infographic Studio' and marker.get('owner') == kept.get('owner'):
            return {'root': str(root), 'repository': None, 'branch': 'main'}
    if kept and kept.get('schema') == 1 and isinstance(kept.get('repo'), str) \
            and isinstance(kept.get('folder'), str) and Path(kept['repo']).is_absolute():
        root = Path(kept['repo']) / kept['folder']
        marker = _marker(root, tool)
        if marker:
            return {'root': str(root), 'repository': marker.get('repository') or None,
                    'branch': marker['branch']}
    if identifier == 'blog':
        page = _json(data / 'page.json')
        root = page.get('workspace') if page else None
        if isinstance(root, str) and root and Path(root).expanduser().is_absolute() \
                and Path(root).expanduser().is_dir():
            marker = _marker(Path(root).expanduser(), tool)
            return {'root': root, 'repository': (marker or {}).get('repository') or None,
                    'branch': marker['branch'] if marker else None}
    return None


def connection(identifier, shared):
    """How a studio's workspace relates to the storage the shared settings name.

    `state` is `connected` (the shared repository), `local` (local Git, as the settings
    say), `disconnected` (another place, or a plain folder that is not Git: the Connect
    action moves its work) or `none` (no workspace yet: one is set up when the studio is
    opened or prepared)."""
    found = remembered(identifier)
    wanted = workspace_setup.target(shared, identifier)
    to = {key: wanted.get(key) for key in ('repository', 'root', 'branch')}
    if identifier == 'infographic':
        return {'state': 'local' if found else 'none', 'connect': False, 'workspace': found, 'to': to,
                'summary': 'Local supplied-information workspace' if found else 'A local workspace is set up when you open Infographic Studio.',
                'detail': 'Drafts stay local. Use Infographic Studio’s Team library to connect the shared repository and share selected files.'}
    if found is None:
        return {'state': 'none', 'connect': False, 'workspace': None, 'to': to,
                'summary': 'No workspace yet. It is set up when you open the studio.',
                'detail': None}
    plain = found['branch'] is None and not found['repository']   # a folder no hub.json marks
    joined = not plain and workspace_setup.matches(found['repository'], found['branch'], shared, identifier)
    where = (f"{found['repository']} ({found['branch']})" if found['repository']
             else f"a folder on this computer, {found['root']}" if plain
             else f"local Git on this computer, {found['root']}")
    if joined and found['repository']:
        return {'state': 'connected', 'connect': False, 'workspace': found, 'to': to,
                'summary': f"Connected to {found['repository']} ({found['branch']})",
                'detail': None}
    if joined:
        return {'state': 'local', 'connect': False, 'workspace': found, 'to': to,
                'summary': 'Local Git on this computer', 'detail': found['root']}
    if wanted.get('repository'):
        summary = 'Not connected to the shared repository'
        detail = (f'Works in {where}. Connect carries its work into {wanted["repository"]}'
                  ' and leaves this workspace in place.')
    elif plain:
        summary = 'Not using local Git'
        detail = (f'Works in {where}, which is not Git. Connect carries its work into local Git '
                  f'at {wanted["root"]} and leaves this folder in place.')
    else:
        summary = 'Not using local Git'
        detail = (f'Connected to {where}, while shared settings say local Git. Connect carries '
                  f'its work into {wanted["root"]} and leaves this workspace in place.')
    return {'state': 'disconnected', 'connect': True, 'workspace': found, 'to': to,
            'summary': summary, 'detail': detail}
