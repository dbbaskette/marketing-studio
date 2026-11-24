"""Bounded summary-only adapters for the launchpad; no engine imports or processes."""
import itertools
import os
from pathlib import Path
import threading
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


# The home page asks every 5 seconds, from each open tab and phone. A studio's listing is
# reused while nothing a cheap look can see has changed, for at most FRESH_SECONDS: the
# look sees saved work added or removed, every summary a studio saves (its index), private
# drafts and a moved workspace, and the age bound covers what it cannot see, such as older
# work rewritten in place. Changes made through Marketing Studio itself read it fresh.
FRESH_SECONDS = 10
_kept = {}   # identifier: (freshness key, when, listing, the number it was begun with)
_keeping = threading.Lock()
_begun = itertools.count()


def _seen(path):
    try:
        found = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    return (found.st_ino, found.st_mtime_ns, found.st_size)


def freshness(identifier):
    """What a cached listing was made from: the studio's workspace record and a few
    stats. No folder is listed and no saved work is read."""
    data = workspaces.data_root(identifier)
    remembered = workspaces.remembered(identifier)
    key = [str(data), _seen(data / 'workspace.json'), _seen(data / 'page.json'),
           _seen(data / 'intake-drafts'), remembered and remembered.get('root')]
    if remembered:
        folder = Path(remembered['root']) / ('projects' if identifier == 'infographic'
                                             else 'articles' if identifier == 'blog' else '')
        index = work_summary.index_root(folder)
        key += [_seen(folder), *(_seen(index / shelf) for shelf in work_summary.STATES)]
    return tuple(key)


def cached(identifier, fresh=False):
    key = freshness(identifier)
    now = time.monotonic()
    with _keeping:
        kept = _kept.get(identifier)
        begun = next(_begun)   # taken before listing: a later listing has a larger number
    if not fresh and kept and kept[0] == key and now - kept[1] < FRESH_SECONDS:
        return kept[2]
    found = listing(identifier)
    with _keeping:
        # A listing begun before the one kept never replaces it: a slow read that started
        # before a change must not stand in for a fresh one made after it.
        held = _kept.get(identifier)
        if held is None or held[3] < begun:
            _kept[identifier] = (key, now, found, begun)
    return found


def snapshot(studios, fresh=False):
    return {row['id']:cached(row['id'], fresh) for row in studios if row.get('installed')}


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
