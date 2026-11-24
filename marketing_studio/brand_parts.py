"""Parts: the pack's judgement files as the page shows them, edited, accepted and
compared with the current pack, and the page's view of a working copy.
marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .errors import WorkspaceError

from .brand_files import files_in, library_summary, no_links, put, read_json, same
from .brand_tasks import guess_variant
from .brand_terms import JUDGEMENT, LIBRARIES, MEDIA, PARTS, SEALS, SEEN
from .brand_work import _record, folder_of, idle, inside, keep, record


def _store():
    """marketing_studio.brand_store, read when called. Callers and tests replace names on it
    (LOCK, git, walk, write_json and others), and a call made here reaches what they put there."""
    from . import brand_store
    return brand_store


def judgement(layouts) -> dict:
    """The layouts' judgement fields, by variant and layout id, with each layout's name."""
    shown = {}
    for variant, measured in ((layouts or {}).get('variants') or {}).items():
        shown[variant] = {}
        for layout in measured.get('layouts') or []:
            if isinstance(layout, dict) and isinstance(layout.get('id'), str):
                shown[variant][layout['id']] = {'name': layout.get('name'),
                                                **{k: layout[k] for k in JUDGEMENT if k in layout}}
    return shown


def part_content(pack: Path, part: str):
    """A part as the page shows it and the person edits it: text, or None when absent."""
    file = pack / PARTS[part][0]
    if not file.is_file():
        return None
    if part == 'guide':
        return file.read_text(encoding='utf-8')
    value = read_json(file)
    if value is None:
        return file.read_text(encoding='utf-8', errors='replace')
    if part == 'roles' and isinstance(value, dict):
        value = {k: v for k, v in value.items() if k not in SEALS}
    if part == 'layouts':
        value = judgement(value)
    return json.dumps(value, indent=2, ensure_ascii=False)


def digest(text) -> str | None:
    return None if text is None else hashlib.sha256(text.encode('utf-8')).hexdigest()


def parts(work: dict) -> list[dict]:
    if work['kind'] != 'brand':
        return []
    pack = inside(work) / 'pack'
    current = folder_of(work['key']) / 'current'
    shown = []
    for part, (file, title) in PARTS.items():
        content = part_content(pack, part)
        if content is None:
            continue
        kept = work['parts'].get(part) or {}
        before = part_content(current, part) if work['update'] else None
        if kept.get('accepted') == _store().digest(content):
            status = 'accepted'
        elif work['update'] and same(part, content, before):
            status = 'unchanged'
        else:
            status = 'review'
        shown.append({'id': part, 'file': file, 'title': title, 'state': status,
                      'by': kept.get('by') or ('current pack' if work['update'] else 'draft'),
                      'quotes': kept.get('quotes') or [], 'note': kept.get('note'),
                      'content': content, 'current': before if work['update'] else None})
    return shown


def apply_part(work: dict, part: str, value, by: str, quotes=(), pack=None) -> None:
    """Write one judgement file from a value the person or the assistant gave, into the
    working pack or the copy of it `pack` names."""
    if part not in PARTS:
        raise WorkspaceError('Choose a part of the pack from this page.')
    pack = Path(pack) if pack is not None else inside(work) / 'pack'
    file = pack / PARTS[part][0]
    if part == 'guide':
        if not isinstance(value, str) or not value.strip() or len(value) > 400_000:
            raise WorkspaceError('guide.md must be Markdown text, under the headings the format names.')
        put(file, (value.rstrip() + '\n').encode('utf-8'))
    elif part == 'layouts':
        if not isinstance(value, dict):
            raise WorkspaceError('Give the layouts as {variant: {layout id: {fields}}}.')
        layouts = read_json(file, {}) or {}
        variants = layouts.get('variants') or {}
        for variant, given in value.items():
            if variant not in variants or not isinstance(given, dict):
                raise WorkspaceError(f'layouts.json has no variant {variant}.')
            by_id = {layout.get('id'): layout for layout in variants[variant].get('layouts') or []}
            by_name = {layout.get('name'): layout for layout in variants[variant].get('layouts') or []}
            for named, fields in given.items():
                layout = by_id.get(named) or by_name.get(named)
                if layout is None or not isinstance(fields, dict):
                    raise WorkspaceError(f'{variant} has no layout {named}.')
                for field in JUDGEMENT:
                    if field in fields and fields[field] is not None:
                        layout[field] = fields[field]
                    else:
                        layout.pop(field, None)
        _store().write_json(file, layouts)
    else:
        if not isinstance(value, dict):
            raise WorkspaceError(f'{PARTS[part][0]} must be one JSON object.')
        if part == 'roles':
            value = {k: v for k, v in value.items() if k not in SEALS}
            value['schema'], value['id'] = 1, work['id']
        _store().write_json(file, value)
    kept = work['parts'].setdefault(part, {})
    kept.update(by=by, quotes=[q for q in quotes if isinstance(q, dict)][:200], note=None,
                accepted=None)


def parse_part(part: str, text):
    if not isinstance(text, str):
        raise WorkspaceError('Give the part as text.')
    if part == 'guide':
        return text
    try:
        return json.loads(text)
    except ValueError as failure:
        raise WorkspaceError(f'That is not JSON the pack can keep ({failure}). Correct it and save '
                             'again.') from failure


def edit(key: str, part: str, text) -> dict:
    """The person's own version of a part, accepted as it is."""
    with _store().LOCK:
        work = record(key)
        idle(key)
        apply_part(work, part, parse_part(part, text), 'you')
        work['parts'][part]['accepted'] = _store().digest(part_content(inside(work) / 'pack', part))
        return keep(work)


def accept(key: str, part: str) -> dict:
    with _store().LOCK:
        work = record(key)
        idle(key)
        if part not in PARTS or part_content(inside(work) / 'pack', part) is None:
            raise WorkspaceError('Choose a part of the pack from this page.')
        work['parts'].setdefault(part, {})['accepted'] = _store().digest(part_content(inside(work) / 'pack', part))
        return keep(work)



def view(key: str) -> dict:
    """What the page shows of a working copy: its files walked once, and each part read
    and hashed once."""
    work, walked = _record(key)
    here = inside(work)
    shown = {k: work.get(k) for k in ('key', 'kind', 'id', 'name', 'update', 'libraryKind',
                                      'task', 'extracted', 'notes', 'clashes', 'checked')}
    sources = files_in(here / 'sources', walked)
    shown['sources'] = sources
    if work['kind'] == 'library':
        sheet = here / 'contact-sheet.svg'
        shown['library'] = {**library_summary(here / 'library.zip'),
                            'sheet': 'contact-sheet.svg' if sheet.is_file() else None} \
            if (here / 'library.zip').is_file() else None
        shown['ready'] = save_ready(work)
        return shown
    pack = here / 'pack'
    tokens = read_json(pack / 'tokens.json', {}) or {}
    shown['tokens'] = {
        'colors': [{k: c.get(k) for k in ('name', 'light', 'dark', 'usage')}
                   for c in tokens.get('colors') or [] if isinstance(c, dict)],
        'styles': [{k: s.get(k) for k in ('name', 'group', 'fontSize', 'lineHeight', 'fontWeight')}
                   for s in (tokens.get('type') or {}).get('styles') or [] if isinstance(s, dict)],
        'families': (tokens.get('type') or {}).get('families') or {}} if tokens else None
    layouts = read_json(pack / 'layouts.json', {}) or {}
    shown['layouts'] = {variant: [{'id': l.get('id'), 'name': l.get('name'), 'used': l.get('used'),
                                   'preview': f"pack/{l['preview']}" if l.get('preview') else None,
                                   'relationship': l.get('relationship')}
                                  for l in measured.get('layouts') or [] if isinstance(l, dict)]
                        for variant, measured in (layouts.get('variants') or {}).items()}
    brand = read_json(pack / 'brand.json', {}) or {}
    shown['roles'] = roles(brand, tokens)
    shown['parts'] = parts(work)
    shown['choices'] = {
        'exports': [s['name'] for s in sources if '/' not in s['name']
                    and s['name'].lower().endswith(('.zip', 'tokens.json'))],
        'templates': [{'source': s['name'], 'variant': guess_variant(s['name'])}
                      for s in sources if s['name'].lower().endswith('.pptx')],
        'libraries': sorted(path.name for path in (folder_of(key) / 'brands' / LIBRARIES).glob('*')
                            if (path / 'library.zip').is_file())}
    shown['ready'] = save_ready(work, shown['parts'])
    return shown


def roles(brand: dict, tokens: dict) -> dict:
    """Each variant's colour roles with the colour each one names, for swatches."""
    colours = {c.get('name'): c for c in tokens.get('colors') or [] if isinstance(c, dict)}
    shown = {}
    for variant, values in (brand.get('variants') or {}).items():
        if not isinstance(values, dict):
            continue
        theme = values.get('theme') if values.get('theme') in ('light', 'dark') else 'light'
        shown[variant] = []
        for role, colour in (values.get('colors') or {}).items():
            found = colours.get(colour) or {}
            value = (found.get('dark') or found.get('light')) if theme == 'dark' else found.get('light')
            shown[variant].append({'role': role, 'color': colour,
                                   'value': value if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) else None})
    return shown


def save_ready(work: dict, shown_parts: list[dict] | None = None) -> str | None:
    """Why Save cannot run yet, or None. `shown_parts` is parts(work) when the caller has
    just read them."""
    task = work.get('task') or {}
    if task.get('state') == 'running':
        return 'Wait for what is running to finish.'
    if work.get('clashes'):
        return 'Choose which file to keep for each source whose name was taken.'
    if not work.get('extracted') and (work['kind'] == 'library' or not work['update']):
        return 'Extract first.'
    if work['kind'] == 'brand':
        waiting = [p['title'] for p in (parts(work) if shown_parts is None else shown_parts)
                   if p['state'] == 'review']
        if waiting:
            return 'Accept or edit each part first: ' + ', '.join(waiting) + '.'
    return None


def file(key: str, path) -> tuple[str, bytes]:
    """A picture in the working copy, for the page: a preview or the contact sheet."""
    work = record(key)
    here = inside(work)
    if not isinstance(path, str) or not path.lower().endswith(SEEN):
        raise WorkspaceError('Only previews and contact sheets are shown.')
    found = no_links(here / path).resolve()
    if here.resolve() not in found.parents or not found.is_file():
        raise WorkspaceError('That picture is not in this working copy.')
    if found.stat().st_size > 10_000_000:
        raise WorkspaceError('This preview is too large to show.')
    return MEDIA[found.suffix.lower()], found.read_bytes()
