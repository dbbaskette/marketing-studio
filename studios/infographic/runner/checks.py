"""Exact-basis factual, coverage, geometry and brand checks; visual review is distinct."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import re

from . import evidence, brand
from .contracts import Invalid, basis, digest
from .validation import REQUIRED_CHECKS, require, validate_project


def contrast(one, two):
    def luminance(color):
        values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(one), luminance(two)))
    return (b + .05) / (a + .05)


def evaluate(store, project, *, measurement=None, visual=None):
    scene = project['scene']
    require(scene is not None, 'Build a scene before checking the page.')
    results = {kind: {'status': 'passed', 'findings': []} for kind in REQUIRED_CHECKS}
    def flag(kind, message, *, incomplete=False):
        results[kind]['status'] = 'incomplete' if incomplete and results[kind]['status'] != 'failed' else 'failed'
        results[kind]['findings'].append(message)
    story = next((s for s in project['stories'] if s['id'] == project['selected_story']), None)
    visible = '\n'.join(e['text'] for e in scene['elements'] if e['kind'] == 'text')
    covered = set(key for block in (story or {}).get('blocks', []) for key in block['required_ids'])
    required = {item['id'] for item in project['brief']['must_show']}
    if not story or story.get('omissions') or required - covered:
        flag('coverage', 'Required ideas are missing from the selected story.')
    if any(words not in visible for words in project['brief']['locked_words']):
        flag('coverage', 'Locked wording is absent or changed in the page.')
    if any(words.casefold() in visible.casefold() for words in project['brief']['exclusions']):
        flag('coverage', 'The page contains excluded content.')
    try:
        evidence.verify(store, project, project['facts'])
    except (ValueError, OSError):
        flag('facts', 'The saved claims no longer match their captured source or calculation.')
    if any(f['kind'] == 'conflicting-values' for f in evidence.findings(project['facts'])):
        flag('facts', 'Resolve or qualify contradictory source values before approval.')
    try:
        validate_project(project)
    except ValueError:
        flag('facts', 'The scene or its evidence references are invalid.')
    digital = scene['unit'] == 'px'
    supplied_numbers = {Decimal(m.group()) for fact in project['facts']
                        for q in fact.get('evidence', []) for m in evidence.NUMBERS.finditer(q.get('quote', ''))}
    supplied_numbers.update(Decimal(str(f['value'])) for f in project['facts'] if evidence.number(f.get('value')))
    supplied_numbers.update(Decimal(m.group()) for f in project['facts'] for key in evidence.CONTEXT
                            for m in evidence.NUMBERS.finditer(f.get(key, '')))
    for element in scene['elements']:
        if element['kind'] == 'text':
            checked_text = element['text']
            for index, block in enumerate((story or {}).get('blocks', [])):
                prefix = str(index + 1) + '. '
                if block['kind'] == 'process' and element['id'] == block['id'] + '_heading' \
                        and checked_text.startswith(prefix):
                    checked_text = checked_text[len(prefix):]
                    break
            if element['role'] != 'source' and any(Decimal(m.group()) not in supplied_numbers
                    for m in evidence.NUMBERS.finditer(checked_text)):
                flag('facts', element['id'] + ': a displayed numeric assertion is not backed by the saved evidence.')
            body_floor, source_floor = brand.type_floors(project['brand'], digital)
            floor = source_floor if element['role'] == 'source' else body_floor
            if element['font_size'] < floor:
                flag('layout', element['id'] + ': text is below its readable size floor.')
            if element['font'] != project['brand']['font']:
                flag('brand-accessibility', element['id'] + ': font differs from the pinned brand.')
            if contrast(element['color'], scene['background']) < 4.5:
                flag('brand-accessibility', element['id'] + ': text contrast is below 4.5:1.')
        if element['kind'] == 'chart':
            used = [f for key in element['fact_ids'] for f in project['facts'] if f['id'] == key]
            try:
                evidence.comparable(used)
                require(element.get('baseline') == 0, 'Use a faithful zero baseline.')
            except ValueError as failure:
                flag('facts', str(failure))
        if element['kind'] == 'artwork':
            asset = next(a for a in project['assets'] if a['id'] == element['asset_id'])
            from .render import dimensions
            target = dimensions(project['brief']['preset'])
            minimum = .5 if digital else 1 / 3
            if asset['width'] < target['width_px'] * minimum or asset['height'] < target['height_px'] * minimum:
                flag('visual', element['id'] + ': artwork resolution is below the useful output floor; request a larger original.')
    if not measurement or not measurement.get('complete'):
        flag('layout', 'Actual font, asset decoding and one-page output measurements are required.', incomplete=True)
    elif measurement.get('overflow') or measurement.get('missing_fonts') or measurement.get('invalid_assets'):
        flag('layout', 'The rendered page has overflow, missing fonts or undecodable artwork.')
    if scene.get('art_regions') and not any(e['kind'] == 'artwork' for e in scene['elements']):
        flag('visual', 'The planned explanatory artwork has not been composed.')
    if not visual or visual.get('basis') != basis(project) or visual.get('scene_digest') != digest(scene) \
            or visual.get('status') != 'passed' or not visual.get('observations'):
        flag('visual', 'Inspect the actual composed page; generation or geometry success does not establish visual fidelity.', incomplete=True)
    else:
        for finding in visual.get('findings', []):
            if finding.get('blocking'):
                flag('visual', finding.get('message', 'An unresolved visual finding blocks approval.'))
    return [{'id': 'check_' + kind, 'kind': kind, 'scene_digest': digest(scene), 'basis': basis(project),
             'blocking': True, **results[kind]} for kind in sorted(REQUIRED_CHECKS)]
