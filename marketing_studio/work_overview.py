"""Bounded summary-only adapters for the launchpad; no engine imports or processes."""
import os
from pathlib import Path
import time
from urllib.parse import quote, urlsplit, urlunsplit
from studio_core import work_summary, intake_drafts
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
    drafts = intake_drafts.summaries(workspaces.data_root(identifier), root)
    folder = root / ('projects' if identifier == 'infographic' else 'articles' if identifier == 'blog' else '')
    if folder.is_symlink() or not folder.is_dir(): return {'state':'unavailable','items':[],'note':'The saved workspace is unavailable.'}
    candidates, indexed, index_limited = work_summary.indexed(folder, MAX_FOLDERS)
    rows, visited, limited, scanned, seen = [], 0, index_limited, 0, set()
    for ident in candidates[:MAX_FOLDERS]:
        visited += 1
        seen.add(ident)
        row = work_summary.read(folder / ident)
        if row: rows.append(row)
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                scanned += 1
                if scanned > 200: limited=True;break
                if entry.name.startswith('.') or entry.name in seen: continue
                if visited >= MAX_FOLDERS: limited=True;break
                visited += 1
                if entry.is_symlink() or not entry.is_dir(follow_symlinks=False): continue
                row = work_summary.read(Path(entry.path)) or work_summary.legacy(identifier, Path(entry.path))
                if row: rows.append(row)
    except OSError: return {'state':'unavailable','items':[],'note':'The saved workspace is unavailable.'}
    priority = {'needs-you': 0, 'in-progress': 1, 'recent': 2}
    rows.sort(key=lambda row: (row['id']))
    rows.sort(key=lambda row: row['observed_at'], reverse=True)
    rows.sort(key=lambda row: priority[row['state']])
    omitted = sum(row['state'] == 'needs-you' for row in rows[MAX_SHOWN:])
    return {'state':'saved','items':[*drafts,*rows[:MAX_SHOWN]],'limited':limited or len(rows)>MAX_SHOWN,
        'note':'Saved status; opening work checks its current state. Older work uses bounded current metadata; oversized or unreadable records are omitted.',
        'pending_omitted':omitted,'pending_more_possible':limited,
        'coverage':'indexed-and-bounded-legacy' if indexed else 'bounded-legacy',
        'folders_read':visited,'indexed_candidates':len(candidates),'seconds':round(time.monotonic()-started,4)}


def snapshot(studios):
    return {row['id']:listing(row['id']) for row in studios if row.get('installed')}


def link(identifier, ident, base):
    """Only a saved owned summary can produce a resume destination."""
    if identifier not in ('blog','training','presentation','infographic'): raise ValueError('Choose one of the studios shown on the home page.')
    if not isinstance(ident,str) or not work_summary.IDENT.fullmatch(ident): raise ValueError('Choose saved work shown on the home page.')
    remembered = workspaces.remembered(identifier)
    if not remembered: raise ValueError('The saved workspace is unavailable; no studio was started.')
    root=Path(remembered['root'])
    if any(row['id']==ident for row in intake_drafts.summaries(workspaces.data_root(identifier),root)):
        parsed=urlsplit(base)
        fragment=[part for part in parsed.fragment.split('&') if part and part.partition('=')[0] not in ('resume','resume-intake')]
        fragment.append('resume-intake=1')
        return urlunsplit(parsed._replace(fragment='&'.join(fragment)))
    folder=root/('projects' if identifier=='infographic' else 'articles' if identifier=='blog' else '')/ident
    if not (work_summary.read(folder) or work_summary.legacy(identifier, folder)): raise ValueError('This saved work is unavailable; refresh the home page.')
    parsed=urlsplit(base)
    fragment=[part for part in parsed.fragment.split('&') if part and part.partition('=')[0]!='resume']
    fragment.append('resume='+quote(ident,safe=''))
    return urlunsplit(parsed._replace(fragment='&'.join(fragment)))


def check(identifier, ident):
    # Validate before launching, then decorate the actual authorized launch link.
    link(identifier, ident, 'http://localhost/')
