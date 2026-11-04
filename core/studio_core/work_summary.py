"""Compact native work metadata. Reading summaries never opens or initializes work."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import stat

FILE = '.studio-summary.json'
LIMIT = 12_000
IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')


def save(root, title, state='needs-you', action='Open saved work'):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or not IDENT.fullmatch(root.name): return
    value = {'schema': 1, 'id': root.name, 'title': str(title or 'Untitled')[:200],
        'state': state, 'action': str(action)[:120], 'observed_at': datetime.now(timezone.utc).isoformat()}
    target = root / FILE
    if target.is_symlink() or target.exists() and not target.is_file(): return
    pending = root / ('.summary-' + secrets.token_hex(8))
    try:
        with pending.open('x', encoding='utf-8') as stream:
            os.chmod(pending, 0o600); json.dump(value, stream)
        os.replace(pending, target)
    finally: pending.unlink(missing_ok=True)


def read(folder):
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir(): return None
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
        return {key: row[key] for key in ('id','title','state','action','observed_at')}
    except (ValueError, OSError): return None


def _native(product, root, record):
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
    try: save(root, title, state, action)
    except OSError: pass  # Metadata cannot turn an otherwise successful native save into failure.


def native(product, root, record):
    try: _native(product, root, record)
    except (OSError, ValueError, KeyError, TypeError, AttributeError): pass
