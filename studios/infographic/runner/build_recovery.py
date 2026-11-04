"""Small persisted recovery receipt; never replays a provider operation."""
import json
import secrets
import re
import traceback
from .contracts import canonical
from .workspace import _atomic, _read

FILE = 'jobs/build-recovery.json'
LABELS = {'composition': 'Compose the page', 'font-check': 'Check fonts and preview',
    'artwork': 'Prepare the artwork', 'place-artwork': 'Place saved artwork',
    'preview': 'Render the preview', 'export': 'Prepare approved files'}
ACTIONS = {'composition': ('build', 'Retry composition'), 'font-check': ('preview', 'Retry preview'),
    'preview': ('preview', 'Retry preview'), 'export': ('export', 'Retry export'),
    'place-artwork': ('compose-image', 'Place saved artwork'), 'artwork': (None, 'Review image work needs attention')}


def read(store, ident):
    try:
        value = json.loads(_read(store.root, f'projects/{ident}/{FILE}', 16000))
        if not isinstance(value, dict) or value.get('schema') != 1 or value.get('step') not in LABELS: return None
        if type(value.get('revision')) is not int or value.get('state') not in ('working', 'failed', 'complete'): return None
        action, label = ACTIONS[value['step']]
        if value.get('next_action') not in (None, action): return None
        values = value.get('next_values')
        allowed = {'request_id'} if action == 'build' else {'asset_id'} if action == 'compose-image' else {'draft'} if action == 'export' else set()
        if not isinstance(values, dict) or not set(values) <= allowed: return None
        if any(not isinstance(v, str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', v) for k,v in values.items() if k != 'draft'): return None
        if 'draft' in values and values['draft'] is not False: return None
        if not isinstance(value.get('completed'), list) or len(value['completed']) > 8 or any(not isinstance(v,str) or len(v)>100 for v in value['completed']): return None
        if value.get('diagnostic') and not re.fullmatch('[a-f0-9]{16}', value['diagnostic']): return None
        value.update(label=LABELS[value['step']], next_label=label)
        current = store.read(ident)
        value['current'] = value.get('revision') == current['revision']
        if not value['current']: value.update(next_action=None, next_label='Earlier recovery; review the current page')
        return value
    except (ValueError, OSError): return None


def keep(store, ident, step, completed=(), *, state='working', error=None, values=None):
    project = store.read(ident)
    action, label = ACTIONS[step]
    data = {'schema': 1, 'step': step, 'label': LABELS[step], 'state': state,
        'completed': list(completed), 'revision': project['revision'],
        'next_action': action if state == 'failed' else None, 'next_label': label,
        'next_values': values or {}, 'category': step if state == 'failed' else None}
    if error:
        reference = secrets.token_hex(8)
        data['diagnostic'] = reference
        # No exception values, prompts, credentials or absolute paths enter the receipt.
        diagnostic = {'schema': 1, 'reference': reference, 'type': type(error).__name__, 'step': step,
            'stack': [{'file': frame.filename.rsplit('/', 1)[-1], 'line': frame.lineno, 'function': frame.name}
                for frame in traceback.extract_tb(error.__traceback__)[-12:]]}
        with store.locked():
            store.write_blob(ident, 'jobs/diagnostics/' + reference + '.json', canonical(diagnostic))
    with store.locked():
        _atomic(store._project(ident) / FILE, canonical(data))
    if error is not None: error.workflow_recovery = data
    return data
