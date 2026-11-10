"""Compact native work metadata. Reading summaries never opens or initializes work."""
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat

FILE = 'work/.studio-summary.json'
LIMIT = 12_000
IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')


def save(root, title, state='needs-you', action='Open saved work'):
    root = Path(root)
    if state not in STATES: return
    if root.is_symlink() or not root.is_dir() or not IDENT.fullmatch(root.name): return
    value = {'schema': 1, 'id': root.name, 'title': str(title or 'Untitled')[:200],
        'state': state, 'action': str(action)[:120], 'observed_at': datetime.now(timezone.utc).isoformat()}
    local = root / 'work'
    if local.is_symlink() or local.exists() and not local.is_dir(): return
    local.mkdir(exist_ok=True)
    target = root / FILE
    if target.is_symlink() or target.exists() and not target.is_file(): return
    pending = local / ('.summary-' + secrets.token_hex(8))
    try:
        with pending.open('x', encoding='utf-8') as stream:
            os.chmod(pending, 0o600); json.dump(value, stream)
        os.replace(pending, target)
        index_save(root, value)
    finally: pending.unlink(missing_ok=True)


INDEX = 'studios-work-overview'
STATES = ('needs-you', 'in-progress', 'recent')


def index_root(folder):
    cache = Path(os.environ.get('XDG_CACHE_HOME') or (Path.home() / '.cache'))
    key = hashlib.sha256(str(Path(folder).resolve()).encode()).hexdigest()
    return cache / INDEX / key


def index_save(root, value):
    """Incremental metadata only; never rebuild a workspace index on a Home read."""
    base = index_root(root.parent)
    if base.is_symlink():
        return
    folder = base / value['state']
    if folder.is_symlink():
        return
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = folder / (root.name + '.json')
    if target.is_symlink():
        return
    pending = folder / ('.summary-' + secrets.token_hex(8))
    try:
        with pending.open('x', encoding='utf-8') as stream:
            os.chmod(pending, 0o600)
            json.dump({'schema': 1, 'id': root.name}, stream)
        os.replace(pending, target)
        for other in STATES:
            stale = base / other / target.name
            if other != value['state'] and not stale.parent.is_symlink():
                stale.unlink(missing_ok=True)
    finally:
        pending.unlink(missing_ok=True)


def indexed(folder, limit=100):
    """Bounded candidate ids by decision priority. Actual owned summaries stay authoritative."""
    base = index_root(folder)
    if base.is_symlink() or not base.is_dir():
        return [], False, False
    found, limited = [], False
    for state in STATES:
        shelf = base / state
        if shelf.is_symlink():
            continue
        try:
            with os.scandir(shelf) as entries:
                seen = 0
                for entry in entries:
                    seen += 1
                    if seen > limit:
                        limited = True
                        break
                    ident = entry.name.removesuffix('.json')
                    if entry.name.endswith('.json') and IDENT.fullmatch(ident) and not entry.is_symlink() and entry.is_file(follow_symlinks=False):
                        found.append(ident)
        except OSError:
            continue
    return list(dict.fromkeys(found)), True, limited


def read(folder):
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir(): return None
    if (folder / 'work').is_symlink(): return None
    path = folder / FILE
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT: return None
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): return None
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT: return None
        row = json.loads(raw)
        if not isinstance(row, dict) or row.get('schema') != 1 or row.get('id') != folder.name or not IDENT.fullmatch(folder.name): return None
        if row.get('state') not in ('needs-you', 'in-progress', 'recent'): return None
        if any(not isinstance(row.get(key),str) or len(row[key])>bound for key,bound in [('title',200),('action',120),('observed_at',100)]): return None
        # A summary saved before spending limits were removed may carry `warning`; it is ignored.
        return {key: row[key] for key in ('id','title','state','action','observed_at')}
    except (ValueError, OSError, RecursionError): return None


def describe(product, root, record):
    """Conservative saved-state hints; never claims a worker is currently alive."""
    title = record.get('title') or (record.get('brief') or {}).get('topic') or Path(root).name
    state, action = 'recent', 'Open saved work'
    if product == 'training':
        if record.get('problem'): state, action = 'needs-you', 'Review the stopped step'
        elif record.get('question'): state, action = 'needs-you', 'Answer the pending question'
        elif (record.get('outline_first') or {}).get('outline') and not (record.get('training_plan') or {}).get('approved'):
            state, action = 'needs-you', 'Review the training outline'
        elif record.get('halt'): state, action = 'needs-you', 'Resume the training'
    elif product == 'presentation':
        waiting = [name for name, gate in (record.get('gates') or {}).items() if gate.get('state') == 'waiting']
        if record.get('halted'): state, action = 'needs-you', 'Review the stopped step'
        elif waiting:
            state, action = 'needs-you', {'gate:story':'Review the slide story','gate:outline':'Review slide text','gate:build':'Review delivery'}.get(waiting[-1], 'Review the pending decision')
    progress = (record.get('research_execution') or {}).get('progress') or {}
    if state == 'recent' and ((progress.get('agents') or {}).get('count') or any(
            job.get('status') in ('working','waiting','running') for job in (record.get('drafts') or {}).get('jobs') or [])):
        state, action = 'in-progress', 'Open saved progress'
    if product == 'blog':
        stage = (record.get('editorial') or {}).get('stage') or record.get('stage')
        state, action = ('recent', 'Open editorial work') if stage in ('ready', 'published') else ('needs-you', 'Continue the saved blog')
    if product == 'infographic':
        title = (record.get('brief') or {}).get('title') or title
        state, action = ('recent', 'Open delivery') if record.get('approval') else ('needs-you', 'Review the saved infographic')
    return {'title': str(title)[:200], 'state': state, 'action': action}


def native(product, root, record):
    try: save(root, **describe(product, root, record))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError): pass


def legacy(product, folder):
    """Bounded current metadata only; never traverse content/history or write a sidecar."""
    folder = Path(folder)
    if folder.is_symlink() or not IDENT.fullmatch(folder.name): return None
    relative = {'training': '.training-studio/run.json', 'presentation': 'run.json',
        'blog': 'session.json', 'infographic': 'current.json'}[product]
    def read_json(path, expected=None):
        if path.is_symlink(): return None, None
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 128_000: return None, None
            raw = stream.read(128_001)
        if len(raw) > 128_000 or expected and hashlib.sha256(raw).hexdigest() != expected: return None, None
        return json.loads(raw), info
    try:
        path=folder/relative
        # Reject a redirected metadata directory, as well as the final file.
        if path.parent.is_symlink(): return None
        record, info=read_json(path)
        if product == 'infographic':
            if not isinstance(record,dict) or record.get('id') != folder.name or type(record.get('revision')) is not int or not re.fullmatch('[a-f0-9]{64}',str(record.get('sha256',''))):return None
            expected=record['sha256']
            path=folder/'versions'/f"{record['revision']}-{expected}.json"
            if path.parent.is_symlink(): return None
            record,info=read_json(path, expected)
        if not isinstance(record,dict) or info is None:return None
        row=describe(product,folder,record)
        return {'id':folder.name,**row,'observed_at':datetime.fromtimestamp(info.st_mtime,timezone.utc).isoformat()}
    except (OSError,ValueError,KeyError,TypeError,AttributeError,RecursionError):return None
