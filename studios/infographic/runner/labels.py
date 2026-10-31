"""Human names for page elements and revisions. Read-only: nothing here saves or renders."""
from __future__ import annotations

from .contracts import digest


def _element_id(value):
    from .visual_scene import element_id
    return element_id(value)


def _nodes(block, project):
    """The diagram items as the visual layout composes them, planned or derived from facts."""
    planned = (block.get('visual') or {}).get('nodes')
    if planned:
        return planned
    from . import visuals
    try:
        return visuals.nodes(block, {f['id']: f for f in project['facts']}) or []
    except (ValueError, KeyError, TypeError):
        return []


def _names(project):
    """Element ID → (label, section) for the selected story, as both layouts compose them."""
    story = next((s for s in project['stories'] if s['id'] == project['selected_story']), None)
    names = {'headline': ('Page heading', None), 'takeaway': ('Page takeaway', None),
             'sources': ('Source note', None)}
    for index, block in enumerate((story or {}).get('blocks', []), 1):
        section = 'Section ' + str(index)
        for suffix, words in (('heading', 'heading'), ('text', 'text'), ('context', 'note')):
            names[_element_id(block['id'] + '_' + suffix)] = (section + ' ' + words, index)
        step = 'step' if block.get('kind') in ('process', 'timeline') else 'item'
        for number, node in enumerate(_nodes(block, project), 1):
            base = block['id'] + '_node_' + node['id']
            names[_element_id(base + '_label')] = (section + ', ' + step + ' ' + str(number) + ' label', index)
            names[_element_id(base + '_caption')] = (section + ', ' + step + ' ' + str(number) + ' caption', index)
    return names, len((story or {}).get('blocks', []))


def _place(bounds, width, height):
    x, y, w, h = bounds
    across = (x + w / 2) / width if width else .5
    down = (y + h / 2) / height if height else .5
    vertical = 'top' if down < 1 / 3 else 'middle' if down < 2 / 3 else 'bottom'
    horizontal = 'left' if across < 1 / 3 else 'centre' if across < 2 / 3 else 'right'
    return vertical + (' centre' if horizontal == 'centre' and vertical != 'middle' else
                       '' if horizontal == 'centre' else ' ' + horizontal)


def elements(project):
    """Editable words in reading order, each with a human label, its place and page bounds.

    Bounds are fractions of the page, so the page can mark an element on any rendering.
    Element IDs stay available for advanced detail and exact edits.
    """
    planned = project.get('scene')
    if not planned:
        return []
    names, sections = _names(project)
    width, height = planned.get('width') or 1, planned.get('height') or 1
    order = {ident: i for i, ident in enumerate(planned.get('reading_order') or [])}
    found, unnamed = [], 0
    texts = [e for e in planned['elements'] if e['kind'] == 'text']
    for element in sorted(texts, key=lambda e: order.get(e['id'], len(order))):
        label, section = names.get(element['id'], (None, None))
        if label is None:
            unnamed += 1
            label = 'Other text ' + str(unnamed)
        x, y, w, h = element['bounds']
        place = _place(element['bounds'], width, height)
        location = ('Section ' + str(section) + ' of ' + str(sections) + ', ' + place if section
                    else place[:1].upper() + place[1:]) + ' of the page'
        found.append({'id': element['id'], 'label': label, 'location': location, 'text': element['text'],
                      'bounds': [x / width, y / height, w / width, h / height]})
    return found


_FIELDS = (('brief', 'brief'), ('sources', 'sources'), ('facts', 'facts'), ('stories', 'story choices'),
           ('selected_story', 'chosen story'), ('brand', 'brand'), ('scene', 'page'),
           ('assets', 'artwork'), ('image_briefs', 'art direction'))
_CONTENT = tuple(key for key, _ in _FIELDS)


def _content(project):
    return digest({key: project[key] for key in _CONTENT})


_BRIEF = (('title', 'working title'), ('audience', 'audience'), ('purpose', 'desired takeaway'),
          ('must_show', 'must-show ideas'), ('locked_words', 'exact wording'),
          ('exclusions', 'leave out'), ('direction', 'story direction'), ('preset', 'page size'))


def joined(words):
    """'a', 'a and b', 'a, b and c'."""
    words = list(words)
    return ' and '.join(words) if len(words) < 3 else ', '.join(words[:-1]) + ' and ' + words[-1]


def cleared(previous, current):
    """The finished work that existed before a change and is gone after it, in words."""
    return [words for words, gone in (
        ('facts', previous['facts'] and not current['facts']),
        ('story', previous['stories'] and not current['stories']),
        ('page', previous['scene'] is not None and current['scene'] is None),
        ('approval', previous['approval'] is not None and current['approval'] is None)) if gone]


def _renamed(previous, current):
    """Only the working title changed, and nothing was cleared."""
    rest = lambda brief: {k: v for k, v in brief.items() if k != 'title'}
    return (previous['brief']['title'] != current['brief']['title']
            and rest(previous['brief']) == rest(current['brief'])
            and all(previous[key] == current[key] for key in _CONTENT if key != 'brief'))


def change(previous, current, earlier=(), fingerprint=None):
    """What one saved revision did, in words, with the content it affected.

    `earlier` holds content fingerprints of older revisions to recognise a restore;
    `fingerprint` is this revision's own, when the caller already has it.
    """
    if previous is None:
        return {'summary': 'Created the infographic', 'affected': []}
    changed = [key for key in _CONTENT if previous[key] != current[key]]
    affected = [words for key, words in _FIELDS if key in changed]
    lost = previous['approval'] is not None and current['approval'] is None
    if current['approval'] is not None and previous['approval'] is None:
        summary = 'Approved this exact revision'
    elif _renamed(previous, current):
        summary = 'Renamed to “' + current['brief']['title'] + '”'
    elif changed and (fingerprint or _content(current)) in earlier:
        # Content equal to an older revision: a restore, or words typed back exactly.
        summary = 'Restored an earlier revision as new work'
    elif changed == ['scene'] and previous['scene'] and current['scene']:
        summary, affected = _scene_change(previous, current)
    elif changed and changed[0] in ('brief', 'sources'):
        # Which brief fields changed, and what the change cleared that existed before it.
        summary = 'Added or updated sources' if changed[0] == 'sources' else (
            'Edited the brief: ' + joined([words for key, words in _BRIEF
                                           if previous['brief'].get(key) != current['brief'].get(key)]
                                          or ['its details']))
        gone = cleared(previous, current)
        if gone:
            summary += '; cleared the ' + joined(gone)
            lost = False
    elif changed:
        summary = {'brief': 'Edited the brief', 'sources': 'Added or updated sources', 'facts': 'Captured facts',
                   'stories': 'Proposed or revised stories', 'selected_story': 'Chose a story',
                   'brand': 'Pinned the brand', 'scene': 'Built the page', 'assets': 'Added artwork',
                   'image_briefs': 'Saved the art direction'}[changed[0]]
    elif previous['checks'] != current['checks'] and current['checks']:
        open_findings = [c for c in current['checks'] if c['status'] != 'passed']
        summary = 'Ran checks: all passed' if not open_findings else (
            'Ran checks: ' + str(len(open_findings)) + ' need attention')
        affected = ['checks']
    elif previous['attempts'] != current['attempts']:
        states = {a['id']: a['state'] for a in previous['attempts']}
        moved = [a for a in current['attempts'] if states.get(a['id']) != a['state']]
        word = {'queued': 'Saved an image request', 'running': 'Started an image request',
                'complete': 'Received artwork', 'failed': 'An image request failed',
                'cancelled': 'Cancelled an image request', 'unknown': 'An image request needs checking'}
        summary = word.get(moved[-1]['state'], 'Updated an image request') if moved else 'Updated image requests'
        affected = ['image requests']
    elif lost:
        summary = 'Cleared the approval'
    else:
        summary = 'Saved without content changes'
    if lost and not summary.startswith('Cleared'):
        summary += '; approval cleared'
    return {'summary': summary, 'affected': affected}


def _scene_change(previous, current):
    before = {e['id']: e for e in previous['scene']['elements']}
    after = {e['id']: e for e in current['scene']['elements']}
    if set(before) == set(after):
        edited = [i for i in after if after[i] != before[i]]
        if edited and all(after[i]['kind'] == 'text' and {k: v for k, v in after[i].items() if k not in ('text', 'lines')}
                          == {k: v for k, v in before[i].items() if k not in ('text', 'lines')} for i in edited):
            names = {e['id']: e['label'] for e in elements(current)}
            return 'Edited words', [names.get(i, 'text') for i in edited]
    if any(e['kind'] == 'artwork' for e in after.values()) and not any(e['kind'] == 'artwork' for e in before.values()):
        return 'Placed artwork on the page', ['page']
    return 'Changed the page layout', ['page']
