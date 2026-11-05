"""Private unfinished intake, independent of projects, assistants and shared settings."""
import hashlib
import json
import os
from pathlib import Path
import secrets
from datetime import datetime, timezone
from contextlib import contextmanager

from .process_lock import ProcessRLock

LIMIT = 32_000_000


class Conflict(ValueError):
    """Another tab saved this intake after the form was read."""


def path(data, scope):
    key = hashlib.sha256(json.dumps(scope, sort_keys=True, default=str).encode()).hexdigest()
    return Path(data) / 'intake-drafts' / (key + '.json')


def read(file):
    if file.is_symlink():
        raise ValueError('The saved intake must be an ordinary private file.')
    if not file.exists():
        return {'revision': 0, 'draft': None}
    try:
        if file.stat().st_size > LIMIT:
            raise ValueError('The saved intake is too large to read.')
        value = json.loads(file.read_text(encoding='utf-8'))
        if (not isinstance(value, dict) or set(value) != {'revision', 'draft'}
                or type(value['revision']) is not int or value['revision'] < 0
                or value['draft'] is not None and not isinstance(value['draft'], dict)):
            raise ValueError('The saved intake cannot be read.')
        return value
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('The saved intake cannot be read. Its file has been kept.') from error


def _workspace(scope):
    if isinstance(scope, (tuple, list)) and len(scope) == 4:
        return str(scope[1])
    if isinstance(scope, dict) and (scope.get('kind') == 'blog-intake' or scope.get('product') == 'Infographic Studio'):
        return str(scope.get('workspace', ''))
    return None


def _summary(file, scope, held):
    try:
        _write_summary(file, scope, held)
    except (OSError, ValueError, TypeError):
        pass  # Discovery cannot turn a successful private save into a failed edit.


def _write_summary(file, scope, held):
    workspace = _workspace(scope)
    if not workspace:
        return
    target = file.with_suffix('.summary.json')
    draft = held['draft']
    step=(draft or {}).get('step',0)
    step=min(20,max(0,step)) if type(step) is int else 0
    current=file.stat()
    value = {'stamp': [current.st_mtime_ns,current.st_size], 'workspace': hashlib.sha256(workspace.encode()).hexdigest(),
             'revision': held['revision'], 'draft': bool(draft),
             'title': str((draft or {}).get('title') or 'Unfinished draft')[:160],
             'step': step,
             'observed_at': datetime.now(timezone.utc).isoformat()}
    pending = target.with_name('.' + target.name + '-' + secrets.token_hex(6))
    try:
        with os.fdopen(os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as out:
            json.dump(value, out)
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def summaries(data, workspace):
    """Read at most 100 tiny private sidecars; never read form or upload content."""
    folder = Path(data) / 'intake-drafts'
    if folder.is_symlink() or not folder.is_dir():
        return []
    key = hashlib.sha256(str(workspace).encode()).hexdigest()
    result = []
    with os.scandir(folder) as entries:
        for index, entry in enumerate(entries):
            if index >= 100: break
            if not entry.name.endswith('.summary.json') or entry.is_symlink(): continue
            try:
                if entry.stat(follow_symlinks=False).st_size > 4096: continue
                value = json.loads(Path(entry.path).read_text())
                if not value.get('draft') or value.get('workspace') != key: continue
                ident = entry.name.removesuffix('.summary.json')
                if len(ident) != 64 or any(c not in '0123456789abcdef' for c in ident): continue
                saved = folder / (ident + '.json')
                if saved.is_symlink() or not saved.is_file(): continue
                stat=saved.stat()
                if value.get('stamp') != [stat.st_mtime_ns,stat.st_size]: continue
                result.append({'id': 'intake-' + ident, 'kind': 'intake', 'state': 'draft',
                    'title': str(value.get('title') or 'Unfinished draft')[:160],
                    'step': min(20,max(0,int(value.get('step',0)))),
                    'observed_at': str(value.get('observed_at',''))[:64], 'action': 'Resume draft'})
            except (OSError, ValueError, TypeError, AttributeError): continue
    return result[:4]


def dispatch(data, scope, sent):
    if not isinstance(sent, dict):
        raise ValueError('Send one intake draft request.')
    file = path(data, scope)
    action = sent.get('action')
    if action == 'read' and set(sent) == {'action'}:
        return read(file)  # Browsing does not create a folder, lock or workspace.
    if action not in ('save', 'discard') or set(sent) != (
            {'action', 'expected', 'patch'} if action == 'save' else {'action', 'expected'}):
        raise ValueError('Choose Save intake or Discard draft.')
    if type(sent['expected']) is not int or sent['expected'] < 0:
        raise ValueError('Read the saved intake before changing it.')
    patch = sent.get('patch', {})
    if not isinstance(patch, dict) or len(patch) > 80 or any(
            not isinstance(key, str) or not key or len(key) > 80
            or key in ('__proto__', 'prototype', 'constructor') for key in patch):
        raise ValueError('Send the intake fields as an object.')
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if file.parent.is_symlink():
        raise ValueError('The intake folder must be private to this studio.')
    with ProcessRLock(lambda: file.with_suffix('.lock')):
        held = read(file)
        if sent['expected'] != held['revision']:
            raise Conflict('This intake changed in another tab. Copy any unsaved answers, then reload the page to read the saved intake. No work has started.')
        draft = {**(held['draft'] or {}), **patch} if action == 'save' else None
        if draft == held['draft']:
            _summary(file, scope, held)
            return held
        value = {'revision': held['revision'] + 1, 'draft': draft}
        encoded = (json.dumps(value, ensure_ascii=False) + '\n').encode()
        if len(encoded) > LIMIT:
            raise ValueError('This intake is too large to save. Use captured sources or Library documents.')
        pending = file.with_name('.' + file.name + '-' + secrets.token_hex(6))
        try:
            with os.fdopen(os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as out:
                out.write(encoded)
            os.replace(pending, file)
            _summary(file, scope, value)
        finally:
            pending.unlink(missing_ok=True)
        return value


def slide_review(data, scope, sent):
    """Private corrections only: no outline, approval or pipeline record is changed."""
    patch = sent.get('patch') if isinstance(sent, dict) else None
    if patch is not None:
        allowed = {'basis', 'edits', 'note', 'selected', 'notes_open', 'intakeOpen'}
        if not isinstance(patch, dict) or set(patch) - allowed:
            raise ValueError('Save only the displayed slide-text corrections.')
        if 'basis' in patch and (not isinstance(patch['basis'], str) or not 1 <= len(patch['basis']) <= 256):
            raise ValueError('Keep the outline identity with these corrections.')
        if 'edits' in patch and patch['edits'] is not None and (not isinstance(patch['edits'], list)
                or len(patch['edits']) > 100 or not all(isinstance(slide, dict) for slide in patch['edits'])):
            raise ValueError('Keep up to one hundred slide corrections.')
        if 'note' in patch and (not isinstance(patch['note'], str) or len(patch['note']) > 4000):
            raise ValueError('Keep feedback within four thousand characters.')
        if 'selected' in patch and (type(patch['selected']) is not int or not 0 <= patch['selected'] < 100):
            raise ValueError('Choose a slide in this review.')
        if len(json.dumps(patch).encode()) > 480_000:
            raise ValueError('These corrections exceed the saved-draft text limit.')
    try:
        held = dispatch(data, {'kind': 'slide-text-review', 'work': scope}, sent)
    except Conflict:
        raise Conflict('These corrections changed in another tab. Copy your unsaved text, then reload this review. No design work started.') from None
    return {'revision': held['revision']} if sent.get('action') == 'save' else held


@contextmanager
def slide_decision(data, scope, sent):
    """Bind a decision to the acknowledged private corrections through its commit."""
    file = path(data, {'kind': 'slide-text-review', 'work': scope})
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if file.parent.is_symlink():
        raise ValueError('The intake folder must be private to this studio.')
    with ProcessRLock(lambda: file.with_suffix('.lock')):
        held = read(file)
        draft = held['draft']
        expected = sent.get('draft_revision')
        if (draft is not None or expected is not None) and (
                type(expected) is not int or expected != held['revision']):
            raise Conflict('These corrections changed in another tab. Reopen the review before deciding. No design work started.')
        if draft is not None and (draft.get('basis') != sent.get('seen')
                or draft.get('edits') != sent.get('edited')
                or sent.get('decision') == 'revise' and (draft.get('note') or '').strip() != (sent.get('note') or '').strip()):
            raise Conflict('Read and save the displayed corrections before deciding. No design work started.')
        yield
