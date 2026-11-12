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


def read(store, ident, project=None):
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
        current = project if project is not None else store.read(ident)
        value['current'] = value.get('revision') == current['revision']
        if not value['current']: value.update(next_action=None, next_label='Earlier recovery; review the current page')
        category = value.get('error_category')
        from .render import RENDER_ERRORS
        over = value.pop('over', None)
        value.pop('fix', None)
        if category in RENDER_ERRORS:
            value['message'], value['help'] = RENDER_ERRORS[category]
        elif category == 'too-dense' and value['step'] == 'composition':
            far = type(over) is int and 1 <= over <= 999
            value['message'] = 'This story is too long to fit one page at a readable size' + (
                f': about {over}% too long.' if far else '.')
            value['help'] = ('Shorten the story, then choose it and build the page again. Building again '
                             'without shortening it will stop here. Nothing was shrunk or left out.')
            value['fix'] = 'shorten'
            if far: value['over'] = over
        else:
            value.pop('message', None)
            value.pop('help', None)
        return value
    except (ValueError, OSError, TypeError, RecursionError): return None


def keep(store, ident, step, completed=(), *, state='working', error=None, values=None, revision=None):
    project = store.read(ident)
    action, label = ACTIONS[step]
    data = {'schema': 1, 'step': step, 'label': LABELS[step], 'state': state,
        'completed': list(completed), 'revision': project['revision'] if revision is None else revision,
        'next_action': action if state == 'failed' else None, 'next_label': label,
        'next_values': values or {}, 'category': step if state == 'failed' else None}
    if error:
        from .render import RenderError, RENDER_ERRORS
        import subprocess
        category = error.category if isinstance(error, RenderError) else (
            'timeout' if isinstance(error, subprocess.TimeoutExpired) else
            'renderer-unusable' if isinstance(error, (FileNotFoundError, PermissionError)) else 'unknown')
        if step in ('font-check', 'preview', 'export'):
            data['error_category'] = category
            data['message'], data['help'] = RENDER_ERRORS[category]
        from .contracts import TooDense
        if step == 'composition' and isinstance(error, TooDense):
            # A story too long for the page is the person's to shorten: a retry cannot help.
            data['error_category'] = 'too-dense'
            if type(error.over) is int: data['over'] = error.over
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
