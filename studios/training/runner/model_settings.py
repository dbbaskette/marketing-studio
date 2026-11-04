"""Use the current model settings: a stopped training takes up the model and reasoning the
shared settings now choose for each kind of work (Quick, Research, Combining, Checking,
Writing, Fixing), without starting over.

A training saves its choices when it starts (`model_profiles.capture`), so a later change in
Settings does not reach it. This lets the person bring a stopped or waiting training up to
date: `offer` says whether it may, `preview` lists each kind whose model or reasoning would
change, and `save` makes the change.

- Only the jobs still to run use the new choices. Finished work is kept as it is, a running
  job is never changed, and what stopped the training stays, with its own action (Try
  again, Give it more time, Carry on).
- The training keeps its own assistant and its starting model and reasoning, as when it
  began: a training started with a model of its own keeps one model for everything.
- A save is checked against the choices the preview showed (`expected`), refused while the
  run works, and committed as "use the current model settings: …".
"""
from __future__ import annotations

import hashlib
import json

import home
from workspace import WorkspaceError

import runner  # noqa: F401  puts the core on the import path
from runner import drafts, settings
from studio_core import model_profiles
from studio_core.research_view import series

ALLOWED = ('failed', 'stopped', 'waiting', 'paused')
WORKING = ('It is working now. Stop it, or wait until it stops for you, then use the current '
           'model settings.')
FINISHED = 'This training is finished, so it keeps the models it was made with.'
THEIRS = 'Someone else runs this training, so only they can change its models.'
CONVERSATION = 'It is being worked on in conversation, so its models are changed there.'
OUTDATED = ('This training’s models or the shared settings changed since this was opened. '
            'Close it and open it again; nothing was changed.')
SAME = 'This training already uses the current model settings, so there is nothing to change.'
KEPT = ('Only the jobs still to run use these. Everything finished is kept, and what stopped '
        'it stays as it was.')


def refusal(record: dict, state: str, mine: bool, busy: bool) -> str | None:
    """Why Use the current model settings is not offered now, in a sentence, or None."""
    if drafts.in_conversation(record):
        return CONVERSATION
    if not mine:
        return THEIRS
    if state == 'working' or busy:
        return WORKING
    if state == 'done':
        return FINISHED
    return None if state in ALLOWED else WORKING


def _current(record: dict) -> dict:
    """The training's choices made again from the shared settings, as when it started."""
    agent = record.get('agent')
    try:
        return model_profiles.refreshed(record, agent, record.get('model'),
                                        record.get('effort'), settings.check_effort)
    except ValueError as error:
        raise WorkspaceError(str(error)) from error


def _revision(record: dict, current: dict) -> str:
    shown = {'saved': record.get('model_profiles'), 'current': current}
    return hashlib.sha256(json.dumps(shown, sort_keys=True, default=str).encode()).hexdigest()


def _held(engine, path):
    root = engine._held(path)
    shown = engine.view(root)
    return root, shown


def preview(engine, path) -> dict:
    """What using the current model settings would change, kind by kind."""
    root, shown = _held(engine, path)
    with engine.files:
        record = engine._load(root)
        why = refusal(record, shown['state'], shown['mine'],
                      engine._desk_change_busy(root, record))
        current = _current(record)
        changes = model_profiles.differences(record, current)
        return {'may': why is None, 'why': why, 'changes': changes,
                'expected': _revision(record, current), 'kept': KEPT,
                'mode': current['mode']}


def save(engine, path, sent: dict) -> dict:
    """Use the current model settings for the jobs still to run."""
    root, shown = _held(engine, path)
    with engine.files:
        record = engine._load(root)
        why = refusal(record, shown['state'], shown['mine'],
                      engine._desk_change_busy(root, record))
        if why:
            raise WorkspaceError(why)
        current = _current(record)
        if not isinstance(sent, dict) or sent.get('expected') != _revision(record, current):
            raise WorkspaceError(OUTDATED)
        changes = model_profiles.differences(record, current)
        if not changes:
            raise WorkspaceError(SAME)
        record['model_profiles'] = current
        record.setdefault('model_changes', []).append(
            {'at': home.now(), 'changes': changes})
        engine._store(root, record)
        names = series([change['title'] for change in changes])
        engine._commit(root, 'use the current model settings: ' + names)
    try:
        shown = engine.view(root)
    except Exception:  # noqa: BLE001  the change is saved; the page reads the run again
        shown = {}
    return {**shown, 'changed_models': {'changes': changes, 'kept': KEPT}}
