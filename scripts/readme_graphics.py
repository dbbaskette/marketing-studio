#!/usr/bin/env python3
"""Rebuild the five README illustrations with Python's standard library.

Run from any directory: python3 scripts/readme_graphics.py [--check]
These are workflow illustrations, not screenshots or generated project content.
"""
import argparse
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = (
    ('marketing', 'Marketing Studio', 'One home. Four ways to make something.',
     '#2463c4', ('Shared settings', 'Your sources', 'Choose a studio', 'Your decisions')),
    ('blog', 'Blog Studio', 'From a rough idea to words worth sharing.',
     '#2463c4', ('Bring your material', 'Write on the desk', 'Review suggestions', 'Send when ready')),
    ('presentation', 'Presentation Studio', 'Your story. Your brand. Every slide considered.',
     '#a64b12', ('Idea, document or deck', 'Approve slide text', 'Refine the design', 'Choose Deliver')),
    ('training', 'Training Studio', 'A clear path from subject to learning.',
     '#7442b4', ('Audience and sources', 'Review the plan', 'Build your materials', 'Mark ready')),
    ('infographic', 'Infographic Studio', 'Make the important idea visible.',
     '#087b7b', ('Sources and facts', 'Choose a story', 'Refine the page', 'Approve and export')),
)


def text(x, y, value, size=18, fill='#263449', weight=400):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}">{escape(value)}</text>')


def rect(x, y, width, height, fill, radius=12, stroke='none'):
    return (f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>')


def icon(kind, x, y, color):
    paths = {
        'marketing': '<rect x="2" y="2" width="12" height="12" rx="3"/>'
                     '<rect x="22" y="2" width="12" height="12" rx="3"/>'
                     '<rect x="2" y="22" width="12" height="12" rx="3"/>'
                     '<rect x="22" y="22" width="12" height="12" rx="3"/>',
        'blog': '<path d="M7 2h17l7 7v26H7z M23 2v9h8 M12 17h14 M12 23h14 M12 29h9"/>',
        'presentation': '<rect x="2" y="3" width="33" height="23" rx="3"/>'
                        '<path d="M18 26v9 M10 35h16 M9 19l6-7 6 3 7-6"/>',
        'training': '<path d="m1 11 17-8 18 8-18 8z M7 15v12q11 9 23 0V15 M35 12v15"/>',
        'infographic': '<rect x="3" y="2" width="29" height="34" rx="4"/>'
                       '<path d="M9 10h17 M9 17h7 M9 23h12 M9 29h17"/>',
    }
    return (f'<g transform="translate({x} {y})" fill="none" stroke="{color}" '
            f'stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">'
            f'{paths[kind]}</g>')


def illustration(kind, color):
    bits = [rect(804, 66, 412, 228, '#ffffff', 16, '#d8e0ea'),
            rect(805, 67, 410, 38, '#edf2f8', 15),
            text(824, 92, 'THE WORKBENCH', 12, '#526176', 650)]
    if kind == 'marketing':
        for n, (key, title, _, accent, _) in enumerate(PRODUCTS[1:]):
            x, y = 822 + (n % 2) * 194, 121 + (n // 2) * 77
            bits += [rect(x, y, 182, 64, '#f8fafc', 9, '#e1e7ef'),
                     icon(key, x + 10, y + 14, accent),
                     text(x + 54, y + 29, title.split()[0], 14, '#263449', 650),
                     text(x + 54, y + 48, 'Studio', 12, '#526176')]
    elif kind == 'presentation':
        for n in range(3):
            bits += [rect(822, 120 + n * 50, 46, 38, '#edf2f8', 5),
                     text(839, 145 + n * 50, str(n + 1), 13, '#526176')]
        bits += [rect(884, 120, 312, 148, '#f8fafc', 8, '#e1e7ef'),
                 rect(903, 139, 130, 8, color, 3), rect(903, 159, 106, 5, '#c4cedb', 2),
                 rect(903, 172, 90, 5, '#c4cedb', 2)]
        for n, height in enumerate((32, 54, 78)):
            bits += [rect(1060 + n * 36, 244 - height, 23, height, color, 3)]
    elif kind == 'training':
        for n, label in enumerate(('101', '201', '301', '401')):
            bits += [rect(822 + n * 94, 120, 82, 27,
                          color if n == 0 else '#edf2f8', 6),
                     text(850 + n * 94, 139, label, 12,
                          '#ffffff' if n == 0 else '#526176', 650)]
        for n, label in enumerate(('Guide', 'Slides', 'Practice')):
            x = 822 + n * 128
            bits += [rect(x, 161, 118, 108, '#f8fafc', 8, '#e1e7ef'),
                     rect(x + 14, 179, 62, 6, color, 2),
                     rect(x + 14, 195, 87, 4, '#c4cedb', 2),
                     rect(x + 14, 206, 72, 4, '#c4cedb', 2),
                     text(x + 14, 249, label, 13, '#263449', 600)]
    elif kind == 'infographic':
        bits += [rect(826, 119, 117, 155, '#f8fafc', 7, '#e1e7ef'),
                 rect(841, 136, 75, 6, color, 2)]
        for n in range(3):
            bits += [f'<circle cx="853" cy="{166+n*34}" r="9" fill="{color}"/>',
                     rect(871, 162 + n * 34, 57, 4, '#c4cedb', 2)]
        bits += [text(967, 145, 'Words', 15, '#263449', 650),
                 rect(967, 159, 220, 28, '#edf2f8', 6),
                 text(967, 214, 'Preview', 15, '#263449', 650),
                 rect(967, 228, 220, 28, '#edf2f8', 6)]
    else:
        bits += [rect(824, 120, 237, 153, '#f8fafc', 8, '#e1e7ef'),
                 rect(1080, 120, 116, 153, '#f8fafc', 8, '#e1e7ef'),
                 text(1093, 144, 'Finishing', 13, '#263449', 600)]
        for n, width in enumerate((170, 198, 185, 198, 160, 191, 180)):
            bits += [rect(841, 140 + n * 16, width, 5,
                          color if n == 0 else '#c4cedb', 2)]
        for n in range(3):
            bits += [rect(1093, 161 + n * 28, 89, 17, '#e5ecf5', 4)]
    return ''.join(bits)


def render(product):
    kind, title, tagline, color, steps = product
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="440" '
           'viewBox="0 0 1280 440" role="img" aria-labelledby="title desc">',
           f'<title id="title">{escape(title)}</title>',
           f'<desc id="desc">Workflow illustration: {escape(". ".join(steps))}. '
           'Illustrated interface, not a screenshot.</desc>',
           '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">',
           rect(0, 0, 1280, 440, '#f3f6fa', 20),
           rect(0, 0, 1280, 12, color, 0),
           icon(kind, 48, 49, color),
           text(101, 76, title, 28, '#17243a', 700),
           text(48, 149, tagline, 28, '#17243a', 650),
           text(48, 191, 'Local work. Your assistant. Your decisions.', 19, '#526176'),
           text(48, 260, 'A DESK FOR THE WORK, FROM START TO FINISH', 13, color, 650),
           illustration(kind, color)]
    for n, label in enumerate(steps):
        x = 48 + n * 304
        out += [rect(x, 331, 280, 62, '#ffffff', 10, '#d8e0ea'),
                f'<circle cx="{x+25}" cy="362" r="13" fill="{color}"/>',
                text(x + 21, 367, str(n + 1), 13, '#ffffff', 700),
                text(x + 49, 367, label, 16, '#263449', 600)]
    out += ['</g></svg>\n']
    return ''.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check without changing files')
    args = parser.parse_args()
    outdated = []
    for product in PRODUCTS:
        kind = product[0]
        folder = ROOT if kind == 'marketing' else ROOT / 'studios' / kind
        path = folder / 'docs/assets' / f'{kind}-studio-header.svg'
        content = render(product)
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8') != content:
                outdated.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    if outdated:
        parser.exit(1, 'Rebuild README graphics: ' + ', '.join(outdated) + '\n')
    print('Five README graphics are current.' if args.check else 'Built five README graphics.')


if __name__ == '__main__':
    main()
