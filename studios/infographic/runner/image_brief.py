"""Self-contained artwork direction, separate from exact compositor content."""
from copy import deepcopy

from .contracts import basis, canonical, digest
from .validation import records, require, text, validate_project


def make(project: dict, direction: dict, *, edit=None) -> dict:
    scene = project['scene']
    require(scene is not None and project['brand'] is not None, 'Plan a branded scene before describing artwork.')
    planned = scene.get('art_regions', [])
    require(bool(planned), 'This story needs no artwork; do not start decorative image generation.')
    require(isinstance(direction, dict) and all(text(direction.get(k)) for k in ('style', 'acceptance', 'reading_order')),
            'Describe a coherent style, actual reading order and observable artwork acceptance criteria.')
    require(isinstance(direction.get('objects'), list) and bool(direction['objects']),
            'Describe the required subjects and relationships precisely before submitting.')
    regions = []
    width, height = scene['width'], scene['height']
    for region in planned:
        x, y, w, h = region['bounds']
        regions.append({'id': region['id'], 'bounds': [x / width, y / height, w / width, h / height],
                        'owner': 'image', 'purpose': region['role']})
    for element in scene['elements']:
        if element['kind'] in ('text', 'chart'):
            x, y, w, h = element['bounds']
            regions.append({'id': element['id'], 'bounds': [x / width, y / height, w / width, h / height],
                            'owner': 'compositor'})
    names = {region['id'] for region in planned}
    objects = records(direction['objects'], 'Image objects')
    for item in objects.values():
        require(isinstance(item.get('region_id'), str) and item['region_id'] in names and text(item.get('description'))
                and type(item.get('count')) is int and 0 < item['count'] <= 100,
                'Describe each subject, explicit count and its planned artwork region.')
        require(text(item.get('relationships')) and text(item.get('preserve')),
                'Specify relationships and elements that must be preserved, not a generic image prompt.')
    require(names <= {item['region_id'] for item in objects.values()}, 'Describe every planned artwork region.')
    references = direction.get('reference_assets', [])
    require(isinstance(references, list) and all(isinstance(ref, str) for ref in references)
            and set(references) <= {a['id'] for a in project['assets']},
            'Reference actual owned permitted assets, not inaccessible paths.')
    if edit is not None:
        require(isinstance(edit, dict) and text(edit.get('change')) and text(edit.get('preserve'))
                and edit.get('asset_id') in references, 'An edit needs a staged original asset, exact change and preservation instructions.')
    story = next(s for s in project['stories'] if s['id'] == project['selected_story'])
    info = {'audience': project['brief']['audience'], 'takeaway': story['takeaway'],
            'canvas': {k: scene[k] for k in ('width', 'height', 'unit')},
            'regions': regions, 'objects': list(objects.values()), 'style': direction['style'],
            'brand': {k: project['brand'][k] for k in ('identity', 'colors', 'imagery', 'geometry')},
            'reading_order': direction['reading_order'], 'acceptance': direction['acceptance'],
            'edit': edit, 'reference_assets': references}
    from .render import dimensions
    output = dimensions(project['brief']['preset'])
    info['target_output_pixels'] = [output['width_px'], output['height_px']]
    compositor = [e['text'] for e in scene['elements'] if e['kind'] == 'text']
    prompt = ('Create explanatory artwork for this one-page composition. Return a high-resolution portrait PNG, artwork only. '
              'Keep every compositor-owned region empty. Do not draw words, numbers, chart marks, '
              'logos or identity artwork. Counts indicate illustrative composition, not measured '
              'product or customer evidence. Do not fetch references, search, or use outside sources. '
              'Use only the attached reference images identified below.\n' + canonical(info).decode())
    require(len(prompt) <= 60_000, 'Art direction is too large; reduce the requested image scope.')
    image = {'id': 'image_' + digest(info)[:20], 'story_id': story['id'], 'scene_id': scene['id'],
             'basis': basis(project), 'prompt': prompt, 'goal': story['takeaway'],
             'reading_order': direction['reading_order'], 'style': direction['style'],
             'exclusions': 'No compositor text, numbers, chart marks, logos, unsupported facts or external resources.',
             'acceptance': direction['acceptance'], 'canvas': info['canvas'], 'regions': regions,
             'objects': info['objects'], 'reference_assets': references,
             'fact_ids': list(dict.fromkeys(key for block in story['blocks'] for key in block['fact_ids'])),
             'compositor_text': compositor, 'edit': edit}
    candidate = deepcopy(project)
    candidate.update(image_briefs=[image], attempts=[], checks=[], approval=None)
    validate_project(candidate)
    return image
