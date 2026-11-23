"""A solution brief from a desk draft, laid out in the brand's template by Harness Brand.

The draft keeps a brief's page furniture in plain Markdown, so the person reads and edits it
on the desk like any other text: a blockquote is that page's sidebar, and a list whose items
start with `[icon: words]` is the icon row. `read` takes those out of the Markdown and returns
the main column's text and a layout. `make` looks each icon up in the brand's icon library,
has Harness Brand fill the brand's solution-brief template, and reports the pages.

Blog Studio writes no Word files itself: Harness Brand takes the Markdown and the layout."""

import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from studio_core import brand_skills
from studio_core.packaging import stable_place

import desk
import studio

TEMPLATE = 'solution-brief'
TIMEOUT = 300
MOST_ICONS = 4
PAGES = (4, 5)
# What a brief leaves out (see references/modules/solution-brief.md).
INTERNAL = re.compile(r'^(who (it|this) is for|audience|target audience|personas?)\b', re.I)
SOURCES = re.compile(r'^(sources|references|citations|footnotes|bibliography)\b', re.I)
ICON = re.compile(r'^[-*]\s+\[icon:\s*([^\]]+?)\s*\]\s*\*\*(.+?)\*\*\s*[:–—-]?\s*(.*)$')
HEADING = re.compile(r'^##\s+(.+?)\s*$')
PICTURE = re.compile(r'^!\[[^\]]*\]\([^)]*\)\s*$')
PULLED = re.compile(r'^(stat|quote):\s*(.+)$', re.I)
BOLD_LINE = re.compile(r'^\*\*(.+?)\*\*:?$')
NOT_INSTALLED = (
    'Harness Brand is not installed on this computer, so the brief cannot be laid out. Install '
    'Harness Brand 1.3.0 or newer, then make the brief again. The draft is kept.'
)
TOO_OLD = (
    'The Harness Brand on this computer cannot lay out sidebars and icons. Update it to 1.3.0 '
    'or newer, then make the brief again. The draft is kept.'
)
NOT_A_BRIEF = 'This is a blog, not a solution brief.'


def _check(label, passed, detail=''):
    return {'label': label, 'passed': bool(passed), 'detail': detail}


def _sidebar_block(line):
    """One line of a sidebar's blockquote as a layout block, and a problem when it has one."""
    pulled = PULLED.match(line)
    if pulled:
        kind = pulled.group(1).lower()
        words, dash, source = pulled.group(2).rpartition(' — ')
        if not dash:
            words, dash, source = pulled.group(2).rpartition(' -- ')
        if not dash or not source.strip():
            said = f'A {kind} in a sidebar has no source: “{pulled.group(2)[:60]}”.'
            return {'type': 'body', 'text': pulled.group(2).strip()}, said
        return {'type': kind, 'text': words.strip(), 'attribution': source.strip()}, None
    heading = BOLD_LINE.match(line)
    if heading:
        return {'type': 'heading', 'text': heading.group(1).strip()}, None
    if re.match(r'^[-*]\s+', line):
        return {'type': 'bullet', 'text': re.sub(r'^[-*]\s+', '', line).strip()}, None
    return {'type': 'body', 'text': line}, None


def read(markdown):
    """(the main column's Markdown, the layout, checks) from a brief's draft.

    The layout's icons are still the words the draft names; `make` turns each into an icon ID."""
    title, body, sidebars, icons, headings, unsourced = '', [], {}, [], [], []
    current, pictures, fenced = None, 0, False
    for raw in markdown.replace('\r\n', '\n').split('\n'):
        line = raw.rstrip()
        if line.lstrip().startswith('```'):
            fenced = not fenced
        if fenced:
            body.append(line)
            continue
        if line.startswith('# ') and not title and not headings:
            title = line[2:].strip()
            continue
        found = HEADING.match(line)
        if found:
            current = ' '.join(found.group(1).split())
            headings.append(current)
            body.append('## ' + current)
            continue
        if line.startswith('>'):
            words = line[1:].strip()
            if words:
                block, problem = _sidebar_block(words)
                sidebars.setdefault(current, []).append(block)
                if problem:
                    unsourced.append(problem)
            continue
        icon = ICON.match(line.strip())
        if icon:
            icons.append(
                {
                    'words': ' '.join(icon.group(1).split()),
                    'label': icon.group(2).strip(),
                    'detail': icon.group(3).strip().rstrip('.'),
                }
            )
            continue
        if PICTURE.match(line.strip()):
            pictures += 1
            continue
        body.append(line)
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(body)).strip()
    source = ('# ' + title + '\n\n' if title else '') + text + '\n'
    layout = {'template': TEMPLATE}
    if icons and headings:
        layout['icon_row'] = {'before': headings[0], 'items': icons[:MOST_ICONS]}
    if sidebars:
        layout['sidebars'] = [
            {'page_of': heading, 'blocks': blocks}
            for heading, blocks in sidebars.items()
            if heading is None or heading in headings
        ]
    if len(headings) >= 3 and headings[-1].lower() == 'summary':
        layout['closing_from'] = headings[
            -2
        ]  # Summary shares the final page with what is before it.
    repeated = sorted({h for h in headings if headings.count(h) > 1})
    internal = [h for h in headings if INTERNAL.match(h)] + [
        block['text']
        for blocks in sidebars.values()
        for block in blocks
        if block['type'] == 'heading' and INTERNAL.match(block['text'])
    ]
    listed = [h for h in headings if SOURCES.match(h)]
    checks = [
        _check(
            'One row of four icons',
            len(icons) == MOST_ICONS,
            ''
            if len(icons) == MOST_ICONS
            else f'The draft names {len(icons)} icons. Write four lines in the form '
            '“- [icon: words] **Label**: detail” after the intro.',
        ),
        _check(
            'A sidebar for the opening page',
            None in sidebars,
            '' if None in sidebars else 'Add a blockquote to the opening for page 1’s sidebar.',
        ),
        _check(
            'Each section heading is used once',
            not repeated,
            'Used more than once: ' + ', '.join(repeated) + '.' if repeated else '',
        ),
        _check(
            'Nothing internal',
            not internal,
            'Leave out: ' + ', '.join(internal) + '.' if internal else '',
        ),
        _check(
            'No list of sources',
            not listed,
            'A brief names a source where its figure appears. Remove: ' + ', '.join(listed) + '.'
            if listed
            else '',
        ),
        _check(
            'Every pulled figure and quote names its source', not unsourced, ' '.join(unsourced)
        ),
        _check(
            'No pictures to carry',
            not pictures,
            f'{pictures} picture(s) in the draft are not carried into the brief in this version.'
            if pictures
            else '',
        ),
    ]
    return source, layout, checks


def runtime():
    """Harness Brand's folder on this computer, with the layout option; else a refusal.

    It is looked for where every studio looks for a brand skill (studio_core.brand_skills).
    BRAND_SKILL_RUNTIME, then HARNESS_BRAND_RUNTIME (the name an older Blog Studio read),
    are the only places looked when either is set. Otherwise the `brand.skill` shared
    setting comes first, then every usual place. The first that holds Harness Brand's
    rebranding command is used."""
    given = [os.environ.get(name) for name in (brand_skills.VARIABLE, 'HARNESS_BRAND_RUNTIME')]
    given = [one for one in given if one]
    if given:
        places = [place for one in given for place in brand_skills.locations(one)]
    else:
        chosen = brand_skills.setting('skill')
        places = (brand_skills.locations(chosen) if chosen else []) + brand_skills.installed()
    found = next((p for p in places if (p / 'rebrand/scripts/brand.py').is_file()), None)
    if found is None:
        raise ValueError(NOT_INSTALLED)
    if "'--layout'" not in (found / 'rebrand/scripts/brand.py').read_text(errors='replace'):
        raise ValueError(TOO_OLD)
    # Its stable address, through `current`: the next update removes the version folder.
    return stable_place(found)


def _python(folder):
    own = folder / 'rebrand/.venv/bin/python3'
    return str(own) if own.exists() else sys.executable


def _run(folder, arguments, brand, home=None):
    # The brands the shared settings name (`brand.brands`), not a folder recorded earlier.
    env = brand_skills.environment({**os.environ, 'HARNESS_REBRAND_BRAND': brand})
    try:
        return subprocess.run(
            [_python(folder), *arguments],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
            cwd=home,
        )
    except subprocess.TimeoutExpired:
        raise ValueError('Harness Brand took too long to lay out the brief. Try again.') from None


def icon_id(folder, brand, words):
    """The brand library's icon for these words: the whole phrase first, then each word."""
    tries = [words] + [word for word in words.split() if word != words]
    for query in tries:
        done = _run(
            folder,
            [str(folder / 'rebrand/scripts/brand_icons.py'), 'search', query, '--limit', '1'],
            brand,
        )
        try:
            hits = json.loads(done.stdout or '[]')
        except ValueError:
            hits = []
        if done.returncode == 0 and hits:
            return hits[0]['id']
    raise ValueError(
        f'The brand’s icon library has no icon for “{words}”. Change that icon’s words in the '
        'draft to a plainer concept, such as database, identity, cloud or security lock.'
    )


def _lay_out(folder, brand, source, layout, work, attempt):
    run = work / f'run-{attempt}'
    (work / 'brief-layout.json').write_text(json.dumps(layout, indent=2, ensure_ascii=False) + '\n')
    done = _run(
        folder,
        [
            str(folder / 'rebrand/scripts/brand.py'),
            str(source),
            '--brand',
            brand,
            '--document',
            TEMPLATE,
            '--layout',
            str(work / 'brief-layout.json'),
            '--output',
            'word',
            '--run-dir',
            str(run),
        ],
        brand,
    )
    saved = run / 'result.json'
    try:
        result = json.loads(done.stdout) if done.stdout.strip() else json.loads(saved.read_text())
    except (ValueError, OSError):
        lines = [line for line in (done.stderr or '').strip().splitlines() if line.strip()]
        raise ValueError(
            'Harness Brand could not lay out the brief' + (': ' + lines[-1][:300] if lines else '.')
        ) from None
    if result.get('status') != 'branded':
        raise ValueError(result.get('error') or 'Harness Brand could not lay out the brief.')
    return result


def _rendered(placed, layout):
    """Checks from Harness Brand's page report."""
    if not placed.get('rendered'):
        return [
            _check(
                'Pages checked',
                False,
                'LibreOffice or poppler is missing, so the pages were not rendered. Open the '
                'Word file and look at each page.',
            )
        ]
    pages, sharing = placed.get('pages') or 0, placed.get('sidebars_sharing_a_page') or []
    row = (layout.get('icon_row') or {}).get('before')
    # The row sits above its heading, so a page break before that heading leaves it on page 1.
    on_first = (
        not row
        or (placed.get('headings') or {}).get(row) == 1
        or row in (layout.get('page_break_before') or [])
    )
    return [
        _check(
            'Four or five pages',
            PAGES[0] <= pages <= PAGES[1],
            ''
            if PAGES[0] <= pages <= PAGES[1]
            else f'It is {pages} pages. '
            + ('Cut text to bring it to five.' if pages > PAGES[1] else 'It has room for more.'),
        ),
        _check(
            'One sidebar on a page',
            not sharing,
            'Two sidebars overlap on page ' + ', '.join(map(str, sharing)) + '. Remove one.'
            if sharing
            else '',
        ),
        _check(
            'The subtitle fits one line',
            placed.get('subtitle_on_one_line') is not False,
            '' if placed.get('subtitle_on_one_line') is not False else 'Shorten the subtitle.',
        ),
        _check(
            'The icon row is on page 1',
            on_first,
            '' if on_first else 'Shorten the intro so the icon row stays on the first page.',
        ),
    ]


def _apart(layout, placed, sections):
    """Change the layout so two sidebars no longer share a page; False when nothing here helps.

    On page 1, which is the opening sidebar's, the later sidebar moves to the section straight
    after its own when that one has none. Otherwise a page break goes before the later one's
    section. The last section is left alone when it shares the final page by design: there the
    person removes a sidebar."""
    pages = placed.get('sidebars_sharing_a_page') or []
    if not pages:
        return False
    here = [bar['page_of'] for bar in placed.get('sidebars') or [] if bar.get('page') == pages[0]]
    later = next((heading for heading in reversed(here) if heading), None)
    if later is None or later not in sections:
        return False
    closing = sections[-1] if layout.get('closing_from') else None
    if later == closing:
        return False
    bars = layout.get('sidebars') or []
    taken = {bar['page_of'] for bar in bars}
    after = sections[sections.index(later) + 1 :][:1]
    if pages[0] == 1 and after and after[0] not in taken and after[0] != closing:
        next(bar for bar in bars if bar['page_of'] == later)['page_of'] = after[0]
        return True
    breaks = layout.setdefault('page_break_before', [])
    if later in breaks:
        return False
    breaks.append(later)
    return True


def make(root, ident):
    """Lay the brief out and keep the Word file and the PDF with the blog's derived files."""
    directory, record = studio.item(root, 'articles', ident)
    if not record.get('brief'):
        raise ValueError(NOT_A_BRIEF)
    brand = (record.get('brand') or {}).get('brand')
    if not brand:
        raise ValueError(desk.BRIEF_NEEDS_BRAND)
    draft = desk.read(root, ident)
    if not draft['sections'] or not any(section['text'].strip() for section in draft['sections']):
        raise ValueError('Write the draft first. The brief is made from it.')
    folder = runtime()
    text, layout, checks = read(desk.join(draft, images=False))
    row = layout.get('icon_row')
    if row:  # Icons come from the brand's own library, never from anywhere else.
        row['items'] = [
            {
                'icon': icon_id(folder, brand, item['words']),
                'label': item['label'],
                'detail': item['detail'],
            }
            for item in row['items']
        ]
    work = studio.inside(directory, 'derived', 'brief')
    work.mkdir(parents=True, exist_ok=True)
    stamp, again = time.strftime('%Y%m%dT%H%M%S'), 0
    while (work / (stamp + ('-' + str(again) if again else ''))).exists():
        again += 1
    work = work / (stamp + ('-' + str(again) if again else ''))
    work.mkdir()
    source = work / 'brief.md'
    source.write_text(text)
    sections = [' '.join(section['heading'].split()) for section in draft['sections']]
    result = None
    for attempt in range(1, 7):
        result = _lay_out(folder, brand, source, layout, work, attempt)
        if not _apart(layout, result.get('layout') or {}, sections):
            break
    placed = result.get('layout') or {}
    files = {}
    for kind, name in (('word', 'solution-brief.docx'), ('pdf', 'solution-brief.pdf')):
        made = (result.get('outputs') or {}).get(kind)
        if made and Path(made).is_file():
            kept = work / name
            kept.write_bytes(Path(made).read_bytes())
            files[kind] = {
                'name': name,
                'path': str(kept),
                'content': base64.b64encode(kept.read_bytes()).decode(),
            }
    if 'word' not in files:
        raise ValueError('Harness Brand returned no Word file for the brief.')
    return {
        'files': files,
        'pages': placed.get('pages'),
        'icons': [item['icon'] for item in (layout.get('icon_row') or {}).get('items', [])],
        'checks': checks + _rendered(placed, layout),
        'warnings': result.get('warnings') or [],
        'page_breaks': layout.get('page_break_before') or [],
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Lay a solution brief out with Harness Brand.')
    parser.add_argument('--root', required=True, help='The Blog Studio workspace')
    parser.add_argument('--id', required=True, help='The brief’s ID on the desk')
    given = parser.parse_args()
    try:
        made = make(Path(given.root), given.id)
    except ValueError as error:
        sys.exit(str(error))
    for file in made['files'].values():
        del file['content']  # The files are on this computer; their bytes are for the page.
    print(json.dumps(made, indent=2, ensure_ascii=False))
