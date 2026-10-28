"""Deterministic one-page planning with explicit readable bounds and artwork reservations."""
from __future__ import annotations

from copy import deepcopy
import math
import textwrap

from . import evidence, brand
from .contracts import PRESETS, Invalid, digest
from .validation import require, text, validate_project


def wrapped(value: str, width: float, size: float) -> list[str]:
    # Conservative initial wrapping; actual font bounds are verified by the renderer.
    limit = max(1, math.floor(width / (size * .58)))
    require(all(len(word) <= limit for word in value.split()),
            'A word or link will not fit at the readable type size. Edit the wording or reserve more space.')
    return textwrap.wrap(value, width=limit, break_long_words=False, break_on_hyphens=False) or ['']


def plan(project: dict, *, arrangement='stack') -> dict:
    require(project['brand'] is not None, 'Select a pinned brand before composing the page.')
    story = next((s for s in project['stories'] if s['id'] == project['selected_story']), None)
    require(story is not None and not story.get('omissions'), 'Choose a story with all required content first.')
    require(arrangement in ('stack', 'columns'), 'Choose stacked blocks or two columns.')
    p = PRESETS[project['brief']['preset']]
    width, height, digital = p['width'], p['height'], p['unit'] == 'px'
    body, foot = brand.type_floors(project['brand'], digital)
    visible_words = len((' '.join([story['headline'], story['takeaway'],
                                  *(b['title'] + ' ' + b['text'] for b in story['blocks'])])).split())
    density = visible_words + len(story['blocks']) * 25 + sum(b['illustration'] for b in story['blocks']) * 30
    preferred = (40 if density < 110 else 32 if density < 220 else 24) if digital else (
                 16 if density < 110 else 14 if density < 220 else 12)
    body = max(body, preferred)
    title_size = max(body * 2, 48 if digital else 25)
    font, colors = project['brand']['font'], project['brand']['colors']
    margin = width * .06
    gap = body * 1.2
    usable = width - 2 * margin
    elements, regions, reading_order = [], [], []

    def words(ident, value, x, y, box_width, size, *, fact_ids=(), role='body', block_id=None):
        lines = wrapped(value, box_width, size)
        box_height = len(lines) * size * 1.4
        require(y + box_height <= height - margin, 'Required text cannot fit. Shorten or prioritize content instead of shrinking it.')
        element = {'id': ident, 'kind': 'text', 'text': value, 'lines': lines,
                   'font': font, 'font_size': size, 'bounds': [x, y, box_width, box_height],
                   'fact_ids': list(fact_ids), 'color': colors['headingPrimary'] if role == 'heading' else colors['inkPrimary'],
                   'role': role, 'block_id': block_id}
        elements.append(element)
        reading_order.append(ident)
        return box_height

    y = margin
    y += words('headline', story['headline'], margin, y, usable, title_size, role='heading') + gap * .5
    y += words('takeaway', story['takeaway'], margin, y, usable, body * 1.15) + gap
    facts = {f['id']: f for f in project['facts']}
    blocks = story['blocks']
    footer = 'Supplied sources: ' + '; '.join(s.get('name', 'Source ' + str(i + 1))
                                                    for i, s in enumerate(project['sources']))
    if story.get('qualifications'):
        footer += '. ' + ' '.join(story['qualifications'])
    footer_lines = wrapped(footer, usable, foot)
    footer_height = len(footer_lines) * foot * 1.4
    bottom = height - margin - footer_height - gap
    columns = 2 if arrangement == 'columns' and len(blocks) > 1 else 1
    rows = math.ceil(len(blocks) / columns)
    block_width = (usable - gap * (columns - 1)) / columns
    block_height = (bottom - y - gap * (rows - 1)) / rows
    require(block_height > body * 4, 'Too many blocks for a legible page. Combine or prioritize the story.')
    for index, block in enumerate(blocks):
        x = margin + (index % columns) * (block_width + gap)
        top = y + (index // columns) * (block_height + gap)
        cursor = top
        prefix = str(index + 1) + '. ' if block['kind'] == 'process' else ''
        if block['kind'] == 'timeline':
            prefix = ' / '.join(dict.fromkeys(facts[key]['period'] for key in block['fact_ids'])) + ' · '
        cursor += words(block['id'] + '_heading', prefix + block['title'], x, cursor, block_width,
                        body * 1.2, fact_ids=block['fact_ids'], role='heading', block_id=block['id']) + body * .35
        cursor += words(block['id'] + '_text', block['text'], x, cursor, block_width, body,
                        fact_ids=block['fact_ids'], block_id=block['id']) + body * .5
        if block['kind'] in ('comparison', 'numbers', 'parts'):
            used = [facts[key] for key in block['fact_ids']]
            evidence.comparable(used)
            context = '; '.join(used[0][key] for key in evidence.CONTEXT)
            cursor += words(block['id'] + '_context', context, x, cursor, block_width, body,
                            fact_ids=block['fact_ids'], block_id=block['id']) + body * .35
            values = [fact['value'] for fact in used]
            require(all(v >= 0 for v in values), 'This layout supports nonnegative values only; choose another explanation for signed data.')
            available = top + block_height - cursor
            chart_height = min(body * (3.3 if block['kind'] == 'numbers' else 2.7) * len(used), available * (.45 if block['illustration'] else 1))
            require(chart_height >= body * (3 if block['kind'] == 'numbers' else 2) * len(used), 'There is not enough room for readable numeric labels.')
            elements.append({'id': block['id'] + '_chart', 'kind': 'chart', 'bounds': [x, cursor, block_width, chart_height],
                             'values': values, 'fact_ids': block['fact_ids'], 'unit': used[0]['unit'],
                             'display_values': [f.get('literal', str(f['value'])) for f in used],
                             'labels': [fact['statement'] for fact in used], 'baseline': 0,
                             'form': block['kind'], 'color': colors['headingPrimary'], 'font': font,
                             'font_size': body, 'block_id': block['id']})
            reading_order.append(block['id'] + '_chart')
            cursor += chart_height + body * .4
        if block['illustration']:
            art_height = top + block_height - cursor
            require(art_height >= body * 3, 'The planned illustration has no useful readable region. Reduce content or choose another layout.')
            regions.append({'id': block['id'] + '_art', 'block_id': block['id'],
                            'bounds': [x, cursor, block_width, art_height],
                            'role': block['illustration_role'], 'fit': 'contain', 'asset_id': None})
            reading_order.append(block['id'] + '_art')
        else:
            require(cursor <= top + block_height + .01, 'A block is overfull. Prioritize the story or change the layout.')
    words('sources', footer, margin, height - margin - footer_height, usable, foot, role='source')
    scene = {'id': 'scene_' + digest({'story': story, 'brand': project['brand']['sha256'],
                                     'preset': project['brief']['preset'], 'arrangement': arrangement})[:20],
             **{key: p[key] for key in ('width', 'height', 'unit')}, 'elements': elements,
             'art_regions': regions, 'reading_order': reading_order, 'arrangement': arrangement,
             'background': colors['canvasPrimary']}
    candidate = deepcopy(project)
    candidate.update(scene=scene, image_briefs=[], attempts=[], checks=[], approval=None)
    validate_project(candidate)
    return scene


def adopt(store, ident, *, expected_revision, arrangement='stack'):
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        return store.change_locked(project, {'scene': plan(project, arrangement=arrangement)})
