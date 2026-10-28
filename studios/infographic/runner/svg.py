"""Compose safe editable SVG. Generated artwork remains explicitly raster."""
from __future__ import annotations

import base64
import xml.etree.ElementTree as ET

from . import render, sources
from .validation import require

NS = render.SVG
ET.register_namespace('', NS)


def compose(store, project: dict, *, draft=False) -> str:
    scene = project['scene']
    require(scene is not None, 'Plan the scene before rendering it.')
    root = ET.Element('{' + NS + '}svg', {'viewBox': f'0 0 {scene["width"]} {scene["height"]}',
                      'role': 'img', 'aria-label': project['brief']['title']})
    ET.SubElement(root, 'title').text = project['brief']['title']
    ET.SubElement(root, 'desc').text = 'Single-page infographic. Text and chart marks are editable; embedded artwork is raster.'
    ET.SubElement(root, 'rect', {'width': str(scene['width']), 'height': str(scene['height']), 'fill': scene['background']})
    for element in scene['elements']:
        x, y, width, height = element['bounds']
        common = {'id': element['id'], 'data-id': element['id'],
                  'data-box': ' '.join(str(v) for v in element['bounds'])}
        if element['kind'] == 'text':
            attrs = {**common, 'x': str(x), 'y': str(y + element['font_size']),
                     'font-family': element['font'], 'font-size': str(element['font_size']), 'fill': element['color']}
            node = ET.SubElement(root, 'text', attrs)
            for index, line in enumerate(element['lines']):
                ET.SubElement(node, 'tspan', {'x': str(x), 'y': str(y + element['font_size'] * (1 + 1.4 * index))}).text = line
        elif element['kind'] == 'chart':
            group = ET.SubElement(root, 'g', common)
            values, size = element['values'], element['font_size']
            maximum = 1 if element['form'] == 'numbers' else sum(values) if element['form'] == 'parts' else max(values)
            require(maximum > 0, 'A numeric chart needs a positive scale; show zero values as text instead.')
            row_height = height / len(values)
            offset = 0
            for i, (label, value) in enumerate(zip(element['labels'], values)):
                literal = element.get('display_values', [str(v) for v in values])[i]
                wording = f'{label}: {literal} {element["unit"]}'
                require(len(wording) * size * .58 <= width, 'A numeric label will not fit legibly. Edit the label or widen its region.')
                if element['form'] == 'parts':
                    # Shared whole, labeled segments, exact values. Never infer a
                    # percentage or a source total from the width of an image.
                    length = width * value / maximum
                    roles = ['headingPrimary', 'inkDeep', 'accentAqua', 'accentPurple', 'accentAzure']
                    colors = project['brand']['colors']
                    fill = colors.get(roles[i % len(roles)], element['color'])
                    ET.SubElement(group, 'rect', {'x': str(x + offset), 'y': str(y + size * .2),
                        'width': str(length), 'height': str(size * .6), 'fill': fill,
                        'stroke': scene['background'], 'stroke-width': '1'})
                    offset += length
                    label_y = y + size * 2 + i * (height - size * 2) / len(values)
                else:
                    label_y = y + row_height * i + size
                text = ET.SubElement(group, 'text', {'x': str(x), 'y': str(label_y),
                         'font-family': element['font'], 'font-size': str(size), 'fill': project['brand']['colors']['inkPrimary']})
                text.text = label if element['form'] == 'numbers' else wording
                if element['form'] == 'numbers':
                    # The exact value is a callout, rather than a length-encoded bar.
                    ET.SubElement(group, 'text', {'x': str(x), 'y': str(label_y + size * 1.45),
                        'font-family': element['font'], 'font-size': str(size * 1.2),
                        'fill': element['color']}).text = literal + ' ' + element['unit']
                    continue
                if element['form'] == 'parts':
                    continue
                ET.SubElement(group, 'rect', {'x': str(x), 'y': str(y + row_height * i + size * 1.35),
                              'width': str(width * value / maximum), 'height': str(size * .5), 'fill': element['color']})
        elif element['kind'] == 'artwork':
            mime, raw = store.read_asset(project['id'], element['asset_id'])
            ET.SubElement(root, 'image', {**common, 'x': str(x), 'y': str(y), 'width': str(width), 'height': str(height),
                          'href': 'data:' + mime + ';base64,' + base64.b64encode(raw).decode(),
                          'preserveAspectRatio': 'xMidYMid meet', 'aria-label': element.get('alt', 'Illustrative artwork')})
        elif element['kind'] == 'connector':
            ET.SubElement(root, 'line', {**common, 'x1': str(x), 'y1': str(y), 'x2': str(x + width),
                          'y2': str(y + height), 'stroke': element['color'], 'stroke-width': '1'})
        elif element['kind'] == 'shape':
            ET.SubElement(root, 'rect', {**common, 'x': str(x), 'y': str(y), 'width': str(width),
                          'height': str(height), 'fill': element['color']})
    if draft:
        ET.SubElement(root, 'text', {'x': '8', 'y': str(scene['height'] - 8),
                      'font-family': project['brand']['font'], 'font-size': '18' if scene['unit'] == 'px' else '9',
                      'fill': project['brand']['colors']['inkPrimary']}).text = 'DRAFT — not approved'
    return render.safe_svg(ET.tostring(root, encoding='unicode'))


def accessible_text(project: dict, *, draft=False) -> str:
    scene = project['scene']
    require(scene is not None, 'There is no scene to describe.')
    elements = {element['id']: element for element in scene['elements']}
    regions = {region['id']: region for region in scene.get('art_regions', [])}
    output = [project['brief']['title'], 'DRAFT — not approved' if draft else 'Approved infographic', '']
    for key in scene['reading_order']:
        item = elements.get(key)
        if item is None:
            if key in regions:
                output.append('Illustration: ' + regions[key]['role'])
            continue
        if item['kind'] == 'text':
            output.append(item['text'])
        elif item['kind'] == 'chart':
            output.append('Exact numeric callouts' if item['form'] == 'numbers' else 'Chart: zero baseline; ' + item['form'])
            output.extend(f'{label}: {value} {item["unit"]}' for label, value in zip(item['labels'], item.get('display_values', item['values'])))
        elif item['kind'] == 'artwork':
            output.append('Raster illustration: ' + item.get('alt', 'Artwork'))
        elif item['kind'] == 'connector':
            output.append('Relationship: ' + item.get('meaning', 'Conceptual connection, not a measured quantity.'))
        output.append('')
    output.extend(['Source identities (supplied, not independently corroborated):',
                   *[s.get('name', s['id']) + ' — SHA256 ' + s['sha256'] for s in project['sources']]])
    return '\n'.join(output) + '\n'
