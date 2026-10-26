"""Where each deck route stops at each review level: one table that the route walks
(test_flow_routes) and the form's "where it stops" line (test_desk) both read, so the
runner and the form cannot drift apart.

STOPS[case][level] is the gates the person decides, in order. Every other gate the deck
has is continued by the review policy, with a receipt saying so.
"""

LEVELS = ('step_by_step', 'balanced', 'automatic')
LEVEL_WORDS = {'step_by_step': 'Step by step', 'balanced': 'Balanced',
               'automatic': 'Automatic draft'}


def _gates(*names: str) -> list[str]:
    return [f'gate:{name}' for name in names]


STOPS = {
    'scratch': {'step_by_step': _gates('outline', 'look', 'build'),
                'balanced': _gates('outline', 'build'),
                'automatic': _gates('build')},
    'scratch-research': {'step_by_step': _gates('research-plan', 'research', 'outline',
                                                'look', 'build'),
                         'balanced': _gates('outline', 'build'),
                         'automatic': _gates('build')},
    'document-script': {'step_by_step': _gates('classify', 'outline', 'look', 'build'),
                        'balanced': _gates('outline', 'build'),
                        'automatic': _gates('build')},
    'brand-only': {'step_by_step': _gates('classify', 'build'),
                   'balanced': _gates('build'),
                   'automatic': _gates('build')},
    'polish': {'step_by_step': _gates('classify', 'build'),
               'balanced': _gates('build'),
               'automatic': _gates('build')},
    'redesign': {'step_by_step': _gates('classify', 'look', 'build'),
                 'balanced': _gates('look', 'build'),
                 'automatic': _gates('build')},
    'rework': {'step_by_step': _gates('classify', 'outline', 'look', 'build'),
               'balanced': _gates('outline', 'build'),
               'automatic': _gates('build')},
    'selected': {'step_by_step': _gates('classify', 'build'),
                 'balanced': _gates('build'),
                 'automatic': _gates('build')},
}

# The form's cases: what New deck is given for each, and the route table it follows. A
# document has research off here; with research on, it follows `document-script` once
# read as a script.
FORM = {
    'scratch': {'route': 'scratch', 'research': False, 'stops': 'scratch'},
    'scratch-research': {'route': 'scratch', 'research': True, 'stops': 'scratch-research'},
    'document': {'route': 'document', 'research': False, 'stops': 'document-script'},
    'brand-only': {'route': 'existing', 'level': 'brand-only', 'stops': 'brand-only'},
    'polish': {'route': 'existing', 'level': 'polish', 'stops': 'polish'},
    'redesign': {'route': 'existing', 'level': 'redesign', 'stops': 'redesign'},
    'rework': {'route': 'existing', 'level': 'rework', 'stops': 'rework'},
    'selected': {'route': 'existing', 'level': 'selected', 'stops': 'selected'},
}


def _series(items: list[str]) -> str:
    return items[0] if len(items) < 2 else ', '.join(items[:-1]) + ' and ' + items[-1]


def _words(case: str, level: str, gate: str) -> str:
    form = FORM[case]
    if gate == 'gate:classify':
        return 'the kind of document' if form['route'] == 'document' \
            else 'the slides read from your deck'
    if gate == 'gate:outline' and level == 'balanced':
        together = (['the research'] if form.get('research') else []) + ['the outline']
        if 'gate:look' in STOPS[form['stops']]['step_by_step']:
            together.append('the look')
        return f'the direction ({_series(together)} together)'
    return {'gate:research-plan': 'the research plan', 'gate:research': 'the research',
            'gate:outline': 'the outline', 'gate:look': 'the look',
            'gate:build': 'the deck'}[gate]


def line(case: str, level: str) -> str:
    """The form's line for a case at a level, as stopsFor says it: for example
    line('redesign', 'balanced') == 'Balanced: it stops for the look and the deck'."""
    gates = STOPS[FORM[case]['stops']][level]
    return (LEVEL_WORDS[level] + ': it stops for '
            + _series([_words(case, level, gate) for gate in gates]))
