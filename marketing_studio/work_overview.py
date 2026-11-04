"""Bounded summary-only adapters for the launchpad; no engine imports or processes."""
import os
from pathlib import Path
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from studio_core import work_summary
from . import workspaces

MAX_FOLDERS = 100
MAX_SHOWN = 12


def listing(identifier):
    started = time.monotonic()
    remembered = workspaces.remembered(identifier)
    if not remembered:
        data = workspaces.data_root(identifier)
        configured = (data / 'workspace.json').exists() or identifier == 'blog' and (data / 'page.json').exists()
        return {'state':'unavailable' if configured else 'empty','items':[],'note':'No readable saved workspace metadata.'}
    root = Path(remembered['root'])
    folder = root / ('projects' if identifier == 'infographic' else 'articles' if identifier == 'blog' else '')
    if folder.is_symlink() or not folder.is_dir(): return {'state':'unavailable','items':[],'note':'The saved workspace is unavailable.'}
    rows, visited, limited, scanned = [], 0, False, 0
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                scanned += 1
                if scanned > 200: limited=True;break
                if entry.name.startswith('.'): continue
                if visited >= MAX_FOLDERS: limited=True;break
                visited += 1
                if entry.is_symlink() or not entry.is_dir(follow_symlinks=False): continue
                row = work_summary.read(Path(entry.path))
                if row: rows.append(row)
    except OSError: return {'state':'unavailable','items':[],'note':'The saved workspace is unavailable.'}
    rows.sort(key=lambda row: row['observed_at'], reverse=True)
    return {'state':'saved','items':rows[:MAX_SHOWN],'limited':limited or len(rows)>MAX_SHOWN,
        'note':'Saved status; opening work checks its current state. Older work without summaries appears after its next native save.',
        'folders_read':visited,'seconds':round(time.monotonic()-started,4)}


def snapshot(studios):
    return {row['id']:listing(row['id']) for row in studios if row.get('installed')}


def link(identifier, ident, base):
    """Only a saved owned summary can produce a resume destination."""
    if not isinstance(ident,str) or not work_summary.IDENT.fullmatch(ident): raise ValueError('Choose saved work shown on the home page.')
    remembered = workspaces.remembered(identifier)
    if not remembered: raise ValueError('The saved workspace is unavailable; no studio was started.')
    root=Path(remembered['root'])
    folder=root/('projects' if identifier=='infographic' else 'articles' if identifier=='blog' else '')/ident
    if not work_summary.read(folder): raise ValueError('This saved work is unavailable; refresh the home page.')
    parsed=urlsplit(base);fragment=dict(parse_qsl(parsed.fragment));fragment['resume']=ident
    return urlunsplit(parsed._replace(fragment=urlencode(fragment)))


def check(identifier, ident):
    # Validate before launching, then decorate the actual authorized launch link.
    link(identifier, ident, 'http://localhost/')
