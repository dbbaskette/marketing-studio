"""Styles: the shape of a kind of writing, apart from who writes it.

A style lives under styles/<id>/ as record.json, STYLE.md and revisions/<n>/ copies, the
way a voice profile lives under profiles/. Starter styles ship with the skill under
assets/styles/. Reading never writes: a starter that is not in the workspace is shown as a
virtual entry built from the packaged file. A starter is copied into styles/ only when
someone changes or uses it (save, retire, pin), and from then on the copy is the style:
an edited or retired starter is never copied back over.
"""

import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from types import SimpleNamespace
import uuid

import studio

SEEDS = Path(__file__).resolve().parents[1] / 'assets' / 'styles'
# A starter carries no wall-clock time, so two computers that each copy the same untouched
# starter write identical files and merge without a conflict.
SEED_TIME = '2026-10-21T00:00:00+00:00'


def parse_seed(text):
    """(name, summary, body) from a starter file's front matter."""
    text = text.removeprefix('﻿').replace('\r\n', '\n')
    match = re.match(r'---\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)', text, re.S)
    if not match:
        raise ValueError('A starter style needs front matter with name and summary.')
    fields = dict(line.split(':', 1) for line in match.group(1).splitlines() if ':' in line)
    name, summary = fields.get('name', '').strip(), fields.get('summary', '').strip()
    if not name or not summary:
        raise ValueError('A starter style needs a name and a summary.')
    return name, summary, match.group(2).strip() + '\n'


def starters():
    """{id: (record, guide)} for every packaged starter, as revision 1 of a confirmed style."""
    found = {}
    for path in sorted(SEEDS.glob('*.md')):
        ident = studio.identifier(path.stem)
        name, summary, body = parse_seed(path.read_text(encoding='utf-8'))
        record = {
            'id': ident,
            'name': name,
            'summary': summary,
            'kind': 'seed',
            'revision': 1,
            'status': 'confirmed',
            'sample_ids': [],
            'created_at': SEED_TIME,
        }
        found[ident] = (record, body)
    return found


def materialize(root, ident):
    """Copy a starter into the workspace if it is not there. Returns whether it wrote.

    The copy is built beside its destination and moved into place whole, so a copy that
    stopped half way is never mistaken for a style, and one that another command wrote
    meanwhile is left as it is.
    """
    ident = studio.identifier(ident)
    found = starters().get(ident)
    directory = studio.inside(root, 'styles', ident)
    if found is None or (directory / 'record.json').is_file():
        return False
    record, guide = found
    if directory.exists():  # left by a copy that stopped before it was finished
        shutil.rmtree(directory)
    temporary = studio.inside(root, 'styles', '.' + ident + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.mkdir(parents=True)
        studio.atomic(temporary / 'STYLE.md', guide.encode('utf-8'))
        studio.write_json(temporary / 'record.json', record)
        snapshot(temporary, record)
        try:
            os.replace(temporary, directory)
        except OSError:
            if (directory / 'record.json').is_file():
                return False  # another command copied it first
            raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    return True


def _read(root, ident):
    """(record, guide) of a style as it is now: the saved one, else the starter, else an error."""
    ident = studio.identifier(ident)
    directory = studio.inside(root, 'styles', ident)
    if (directory / 'record.json').is_file():
        _, record = studio.item(root, 'styles', ident)
        return record, (directory / 'STYLE.md').read_text(encoding='utf-8')
    if ident in starters():
        return starters()[ident]
    raise ValueError(f'Unknown styles ID: {ident}')


def name_of(root, ident):
    """A style's current name, a starter's even before it is copied; None if it is gone."""
    try:
        return _read(root, ident)[0]['name']
    except (ValueError, KeyError, OSError):
        return None


def validate_samples(root, values):
    for value in values:
        _, source = studio.item(root, 'sources', value)
        if 'style-sample' not in source['purposes']:
            raise ValueError('Style samples must be classified as style-sample material.')
        if source['status'] != 'ready':
            raise ValueError('Style samples must have readable content.')


def snapshot(directory, record):
    rev = studio.inside(directory, 'revisions', str(record['revision']))
    rev.mkdir(parents=True, exist_ok=True)
    studio.write_json(rev / 'record.json', record)
    studio.atomic(rev / 'STYLE.md', (directory / 'STYLE.md').read_bytes())


def _create(root, ident, name, guide, status, samples):
    directory = studio.inside(root, 'styles', ident)
    if directory.exists() or ident in starters():
        raise ValueError('Style already exists; use save to create a revision.')
    validate_samples(root, samples)
    if status == 'confirmed' and not guide.strip():
        raise ValueError('A confirmed style needs a readable guide.')
    record = {
        'id': ident,
        'name': name,
        'summary': '',
        'kind': 'learned',
        'revision': 1,
        'status': status,
        'sample_ids': list(samples),
        'created_at': studio.now(),
    }
    directory.mkdir(parents=True)
    studio.atomic(directory / 'STYLE.md', guide.encode('utf-8'))
    studio.persist(directory, 'styles', record)
    snapshot(directory, record)
    return record


def check(root, ident, revision=None):
    """{style_id, revision} that pin would return, without writing anything.

    A retired style is refused unless a revision is named. A starter not yet in the
    workspace has only revision 1.
    """
    record, _ = _read(root, ident)
    if revision is None and record['status'] == 'retired':
        raise ValueError('This style is retired. Choose an active style for new work.')
    version = revision or record['revision']
    if not 1 <= version <= record['revision']:
        raise ValueError('Unknown style revision.')
    directory = studio.inside(root, 'styles', record['id'])
    if (directory / 'record.json').is_file() and not (
        studio.inside(directory, 'revisions', str(version)) / 'record.json'
    ).is_file():
        raise ValueError('Unknown style revision.')
    return {'style_id': record['id'], 'revision': version}


def pin(root, ident, revision=None):
    """{style_id, revision} for new work, checked as check() does.

    Using a starter copies it into the workspace, so the pinned revision is always there.
    """
    selection = check(root, ident, revision)
    materialize(root, selection['style_id'])
    return check(root, selection['style_id'], selection['revision'])


def pinned(root, selection):
    """The name and guide of a pinned revision, exactly as saved, for a writing job.

    A starter not yet copied into the workspace reads as its packaged revision 1, so a new
    run can check its whole context before pin copies the starter.
    """
    ident = studio.identifier(selection['style_id'])
    if not (studio.inside(root, 'styles', ident) / 'record.json').is_file():
        found = starters().get(ident)
        if found is not None and selection['revision'] == 1:
            return {'name': found[0]['name'], 'guide': found[1]}
    directory, _ = studio.item(root, 'styles', ident)
    rev = studio.inside(directory, 'revisions', str(selection['revision']))
    return {
        'name': studio.read_json(rev / 'record.json')['name'],
        'guide': (rev / 'STYLE.md').read_text(encoding='utf-8'),
    }


def command(root, args):
    """The style CLI: create, save, show, retire. Mirrors studio.profile_command.

    show writes nothing. For a starter that is not in the workspace yet it returns
    `guide: None` and the starter's text as `guide_text`; for a saved style, `guide` is the
    path of the revision's STYLE.md as before.
    """
    if args.action == 'create':
        ident = studio.identifier(args.id) if args.id else studio.new_id(args.name)
        guide = studio.read_text(args.guide_file) if args.guide_file else ''
        return _create(root, ident, args.name, guide, args.status, args.sample)
    record, guide = _read(root, args.id)
    if args.action == 'show':
        revision = args.revision or record['revision']
        directory = studio.inside(root, 'styles', record['id'])
        if not (directory / 'record.json').is_file():
            if revision != 1:
                raise ValueError('Unknown style revision.')
            return {**record, 'guide': None, 'guide_text': guide}
        saved = studio.inside(directory, 'revisions', str(revision))
        if not (saved / 'record.json').exists():
            raise ValueError('Unknown style revision.')
        return {**studio.read_json(saved / 'record.json'), 'guide': str(saved / 'STYLE.md')}
    if args.action == 'retire':
        if args.confirmed is not True or args.expected_revision != record['revision']:
            raise ValueError('Confirm the current style revision before retiring it.')
        if record['status'] != 'retired':
            materialize(root, record['id'])
            directory, record = studio.item(root, 'styles', record['id'])
            record.update(status='retired', revision=record['revision'] + 1)
            studio.persist(directory, 'styles', record)
            snapshot(directory, record)
        return record
    guide = studio.read_text(args.guide_file)
    if not guide.strip():
        raise ValueError('Style guide cannot be empty.')
    samples = args.sample if args.sample is not None else record['sample_ids']
    validate_samples(root, samples)
    materialize(root, record['id'])
    directory, record = studio.item(root, 'styles', record['id'])
    record['revision'] += 1
    if getattr(args, 'name', None):
        record['name'] = args.name
    record['sample_ids'] = samples
    record['status'] = args.status or record['status']
    studio.atomic(directory / 'STYLE.md', guide.encode('utf-8'))
    studio.persist(directory, 'styles', record)
    snapshot(directory, record)
    return record


def detail(root, ident):
    """One style for the page, with the version token its edits are checked against.

    A starter not yet in the workspace has the token it keeps once copied unchanged.
    """
    record, guide = _read(root, ident)
    return {
        **record,
        'guide': guide,
        'expected': studio.digest(json.dumps([record, guide], sort_keys=True).encode()),
    }


def catalog(root):
    """Every style, starters first, and the ready style samples. Writes nothing."""
    found, samples = {}, []
    for file in sorted(studio.inside(root, 'styles').glob('*/record.json')):
        if file.parent.name.startswith('.'):
            continue
        try:
            found[file.parent.name] = studio.read_json(file)
        except (ValueError, OSError):
            continue
    for ident, (record, _) in starters().items():
        found.setdefault(ident, record)
    rows = [
        {key: record.get(key) for key in ('id', 'name', 'summary', 'kind', 'revision', 'status')}
        for record in found.values()
    ]
    rows.sort(key=lambda row: (row['kind'] != 'seed', (row['name'] or '').lower()))
    for file in sorted(studio.inside(root, 'sources').glob('*/record.json')):
        try:
            record = studio.read_json(file)
        except (ValueError, OSError):
            continue
        if 'style-sample' in record.get('purposes', []) and record.get('status') == 'ready':
            samples.append({key: record.get(key) for key in ('id', 'name', 'author', 'revision')})
    return {'styles': rows, 'samples': samples, **studio.sample_choices(root, 'style-sample')}


def save(root, data):
    """The page's style-save: a new style, or a revision of one shown at `expected`."""
    selected = data.get('style')
    current = detail(root, selected) if selected else None
    if current and current['status'] == 'retired':
        raise ValueError('This style is retired. Restore it in chat, or write a new style.')
    if current and data.get('expected') != current['expected']:
        raise ValueError('This style changed. Reload before saving a revision.')
    status = data.get('status', 'provisional')
    if (
        status not in ('provisional', 'confirmed')
        or status == 'confirmed'
        and data.get('confirmed') is not True
    ):
        raise ValueError('Confirm the reviewed style guide, or save it as provisional.')
    guide = data.get('guide')
    if not isinstance(guide, str) or not guide.strip() or len(guide) > 40_000:
        raise ValueError('Give a style guide up to 40,000 characters.')
    name = data.get('name', (current or {}).get('name'))
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError('Give a style name up to 200 characters.')
    chosen = data.get('samples', (current or {}).get('sample_ids', []))
    if not isinstance(chosen, list) or len(chosen) > 10:
        raise ValueError('Choose up to ten examples.')
    with tempfile.TemporaryDirectory(prefix='blog-style-') as scratch:
        file = Path(scratch) / 'STYLE.md'
        file.write_text(guide, encoding='utf-8')
        result = command(
            root,
            SimpleNamespace(
                action='save' if current else 'create',
                id=selected,
                name=name.strip(),
                guide_file=str(file),
                status=status,
                sample=chosen,
            ),
        )
    return {'style': result['id'], 'revision': result['revision'], 'status': result['status']}


def retire(root, data):
    """The page's style-retire, against the version shown."""
    current = detail(root, data.get('style'))
    if current['expected'] != data.get('expected') or data.get('confirmed') is not True:
        raise ValueError('Confirm the current style before retiring it.')
    record = command(
        root,
        SimpleNamespace(
            action='retire', id=current['id'], expected_revision=current['revision'], confirmed=True
        ),
    )
    return {'style': record['id'], 'revision': record['revision'], 'status': 'retired'}
