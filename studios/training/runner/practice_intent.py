"""Short creator intent for practice; the author supplies the scenario detail."""
import re

from workspace import WorkspaceError


def check(value=None):
    if value is None:
        return {'mode': 'ai', 'scenarios': []}
    if not isinstance(value, dict) or value.get('mode') not in ('ai', 'custom'):
        raise WorkspaceError('Choose Let AI choose or Define scenarios.')
    if value['mode'] == 'ai':
        return {'mode': 'ai', 'scenarios': []}
    rows = value.get('scenarios')
    if not isinstance(rows, list) or not rows:
        raise WorkspaceError('Add a short scenario description, or let AI choose.')
    kept, ids = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise WorkspaceError('Give each scenario a short description.')
        ident, text = row.get('id'), row.get('description')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', ident) or ident in ids:
            raise WorkspaceError('Each scenario needs a distinct identifier. Reopen the form and try again.')
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > 300:
            raise WorkspaceError('Describe each scenario in 300 characters or fewer. AI fills in the details.')
        ids.add(ident)
        kept.append({'id': ident, 'description': text.strip()})
    return {'mode': 'custom', 'scenarios': kept}


def of(session):
    return check(session['settings'].get('scenario_plan'))


def descriptions(session, ident=None):
    rows = of(session)['scenarios']
    if ident is not None:
        rows = [row for row in rows if row['id'] == ident]
    if not rows:
        return None
    return ('# Creator scenario descriptions\n\n'
            + '\n'.join(row['id'] + ': ' + row['description'] for row in rows)
            + '\n\nUse these short descriptions as the scope. AI supplies appropriate personas, '
              'dialogue, goals and observable evaluation criteria. Adapt to this level and '
              'audience; use the supplied training references for facts. Do not ask the '
              'creator to write a full script. Invented situations are hypothetical.\n')
