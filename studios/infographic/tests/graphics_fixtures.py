"""Synthetic graphics authored in code; generated files stay outside the repository."""
import base64
import struct
import zlib
import xml.etree.ElementTree as ET


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    row = b'\x00' + b'\x0b\x7b\x79\xff' * 4
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * 4)) + chunk(b'IEND', b''))


def scene(kind, preset):
    from runner.contracts import PRESETS
    size = PRESETS[preset]
    height = 600 * size['height'] / size['width']
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    root = ET.Element('{http://www.w3.org/2000/svg}svg', viewBox=f'0 0 600 {height}')

    def element(tag, **attributes):
        return ET.SubElement(root, '{http://www.w3.org/2000/svg}' + tag,
                             {key.replace('_', '-'): str(value) for key, value in attributes.items()})

    def words(value, x, y, *, size=24, width=510, anchor='start', ident=''):
        e = element('text', x=x, y=y, fill='#172b3a', font_family='Arial', font_size=size,
                    text_anchor=anchor)
        e.text = value
        e.set('data-id', ident or value.lower().replace(' ', '-')[:40])
        left = x - width / 2 if anchor == 'middle' else x - width if anchor == 'end' else x
        e.set('data-box', f'{left} {y - size * 1.4} {width} {size * 1.9}')

    element('rect', x=0, y=0, width=600, height=height, fill='#ffffff')
    words('Synthetic ' + kind, 40, 82, size=32, width=520, ident='title')
    words('Renderer test · no AI image generation', 40, 122, size=18, width=520)
    element('image', x=536, y=38, width=24, height=24,
            href='data:image/png;base64,' + base64.b64encode(png()).decode())
    if kind == 'comparison':
        for label, value, y in [('A', 12, 260), ('B', 24, 380)]:
            words(label, 55, y + 39, size=26, width=40)
            element('rect', x=120, y=y, width=value * 15, height=60, rx=5, fill='#0b7b79')
            words(str(value), 535, y + 39, size=26, width=48, anchor='end')
        element('line', x1=120, y1=240, x2=120, y2=470, stroke='#758591', stroke_width=1)
        for value in (0, 12, 24):
            words(str(value), 120 + value * 15, 505, size=18, width=46, anchor='middle')
        words('Count (synthetic)', 300, 554, size=20, width=350, anchor='middle')
        words('B has twice the count of A.', 40, 635, size=24, width=520)
    elif kind == 'process':
        for i, label in enumerate(('Capture', 'Review', 'Export')):
            y = 190 + i * 180
            element('rect', x=80, y=y, width=440, height=100, rx=12, fill='#edf6f5',
                    stroke='#0b7b79', stroke_width=1)
            words(str(i + 1), 112, y + 61, size=22, width=35)
            words(label, 310, y + 61, size=28, width=330, anchor='middle')
            if i < 2:
                element('line', x1=300, y1=y + 108, x2=300, y2=y + 157,
                        stroke='#0b7b79', stroke_width=2)
                element('polygon', points=f'293,{y + 154} 307,{y + 154} 300,{y + 164}', fill='#0b7b79')
    elif kind == 'concept':
        for x in (150, 450):
            element('line', x1=x, y1=340, x2=300, y2=490, stroke='#758591', stroke_width=2)
        for x, y, label in [(40, 220, 'Input A'), (340, 220, 'Input B'), (190, 490, 'Shared idea')]:
            element('rect', x=x, y=y, width=220, height=120, rx=15, fill='#edf6f5',
                    stroke='#0b7b79', stroke_width=1)
            words(label, x + 110, y + 70, size=26, width=205, anchor='middle')
        words('Relationships without invented metrics.', 300, 665, size=20, width=540, anchor='middle')
    else:
        raise ValueError('Choose a synthetic comparison, process, or concept.')
    words('Source: disposable synthetic fixture · embedded PNG marker at top right',
          40, height - 25, size=12, width=520, ident='source-note')
    return ET.tostring(root, encoding='unicode')
