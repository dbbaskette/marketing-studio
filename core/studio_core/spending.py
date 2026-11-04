"""Saved spending policy and finite per-job caps; never starts work or providers."""
import hashlib
import json
import math
from . import activity_log

POLICIES = ('warn', 'hard-stop')
JOB_DOLLARS = 5.0


def check(value):
    if value not in POLICIES:
        raise ValueError('Choose Warn and continue or Stop and ask for the spending limit.')
    return value


def policy(record):
    return check(record.get('spending_policy', 'hard-stop'))


def shared(found, product):
    group = found.get('spending')
    value = group.get(product) if isinstance(group, dict) else None
    return value if value in POLICIES else 'warn'


def cap(record, remaining):
    return JOB_DOLLARS if policy(record) == 'warn' else max(0.01, remaining)


def identity(record):
    value = [record.get('spending_policy', 'hard-stop'), record.get('limits'),
             record.get('driver'), record.get('cleared')]
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def notice(record, used, limit):
    if record.get('execution') == 'conversation' or policy(record) != 'warn' or not isinstance(used, (int, float)) or isinstance(used, bool) \
            or not math.isfinite(used) or not isinstance(limit, (int, float)) or isinstance(limit, bool) \
            or not math.isfinite(limit) or limit <= 0 or used < limit:
        return None
    return {'spent': round(used, 4), 'limit': limit, 'crossing': int(used // limit),
            'message': f'Reported spending ${used:,.2f} reached the ${limit:,.2f} warning. '
                       f'Work continues with a ${JOB_DOLLARS:.2f} budget for each assistant job.'}


def observe(path, record, used, limit):
    found = notice(record, used, limit)
    previous = record.get('spending_warning') or {}
    if found and (previous.get('limit'), previous.get('crossing')) != (found['limit'], found['crossing']):
        record['spending_warning'] = found
        activity_log.checkpoint(path, 'spending-warning', found['message'])


def info(record, used, limit):
    return {'available': record.get('execution') != 'conversation', 'policy': policy(record), 'job_dollars': JOB_DOLLARS if policy(record) == 'warn' else None,
            'limit': limit, 'reported': used, 'warning': notice(record, used, limit),
            'expected': identity(record)}


def get(engine, path, product):
    from workspace import WorkspaceError
    root = engine.driven(path)
    if root is None: raise WorkspaceError('Choose saved work in this workspace.')
    with engine.files:
        record = engine._load(root)
        used = engine.view(root).get('spent', {}).get('dollars')
        limits = record.get('limits') or {}
        amount = limits.get('training_dollars' if product == 'training' else 'dollars')
        return info(record, used, amount)


def change(engine, path, expected, selected, product):
    from workspace import WorkspaceError
    try: check(selected)
    except ValueError as error: raise WorkspaceError(str(error)) from None
    with engine.files:
        root = engine._held(path)
        record = engine._load(root)
        view = engine.view(root)
        if record.get('execution') == 'conversation':
            raise WorkspaceError('Conversation requests use the assistant’s own limits; no runner policy was changed.')
        if view.get('mine') is False or view.get('workers') or view.get('state') == 'working':
            raise WorkspaceError('Stop the work or wait for it before changing its spending behavior.')
        if expected != identity(record):
            raise WorkspaceError('The spending settings changed. Open this choice again; nothing was saved.')
        record['spending_policy'] = selected
        engine._store(root, record)
        engine._commit(root, 'change spending behavior to ' + selected)
    return engine.view(root)
