"""Styles: the shape of a kind of writing, apart from who writes it.

A style lives under styles/<id>/ as record.json, STYLE.md and revisions/<n>/ copies, the
way a voice profile lives under profiles/. Starter styles ship with the skill under
assets/styles/ and are copied into a workspace the first time its styles are read or
pinned. A copied starter that was edited or retired is left alone: a seed is copied only
when its id is absent.
"""

import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace

import studio

SEEDS = Path(__file__).resolve().parents[1] / 'assets' / 'styles'


def parse_seed(text):
    """(name, summary, body) from a starter file's front matter."""
    match = re.match(r'---\n(.*?)\n---\n(.*)', text, re.S)
    if not match:
        raise ValueError('A starter style needs front matter with name and summary.')
    fields = dict(line.split(':', 1) for line in match.group(1).splitlines() if ':' in line)
    name, summary = fields.get('name', '').strip(), fields.get('summary', '').strip()
    if not name or not summary:
        raise ValueError('A starter style needs a name and a summary.')
    return name, summary, match.group(2).strip() + '\n'


def seed(root):
    """Copy every starter whose id is absent. Returns the ids copied."""
    copied = []
    for path in sorted(SEEDS.glob('*.md')):
        ident = studio.identifier(path.stem)
        if studio.inside(root, 'styles', ident).exists():
            continue
        name, summary, body = parse_seed(path.read_text(encoding='utf-8'))
        _create(root, ident, name, body, 'confirmed', [], kind='seed', summary=summary)
        copied.append(ident)
    return copied


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


def _create(root, ident, name, guide, status, samples, kind='learned', summary=''):
    directory = studio.inside(root, 'styles', ident)
    if directory.exists():
        raise ValueError('Style already exists; use save to create a revision.')
    validate_samples(root, samples)
    if status == 'confirmed' and not guide.strip():
        raise ValueError('A confirmed style needs a readable guide.')
    record = {
        'id': ident,
        'name': name,
        'summary': summary,
        'kind': kind,
        'revision': 1,
        'status': status,
        'sample_ids': list(samples),
        'created_at': studio.now(),
    }
    directory.mkdir(parents=True)
    studio.atomic(directory / 'STYLE.md', guide.encode())
    studio.persist(directory, 'styles', record)
    snapshot(directory, record)
    return record


def pin(root, ident, revision=None):
    """{style_id, revision} for new work; a retired style is refused unless a revision is named."""
    seed(root)
    directory, record = studio.item(root, 'styles', ident)
    if revision is None and record['status'] == 'retired':
        raise ValueError('This style is retired. Choose an active style for new work.')
    version = revision or record['revision']
    if not (studio.inside(directory, 'revisions', str(version)) / 'record.json').is_file():
        raise ValueError('Unknown style revision.')
    return {'style_id': ident, 'revision': version}


def pinned(root, selection):
    """The name and guide of a pinned revision, exactly as saved, for a writing job."""
    directory, _ = studio.item(root, 'styles', selection['style_id'])
    rev = studio.inside(directory, 'revisions', str(selection['revision']))
    return {
        'name': studio.read_json(rev / 'record.json')['name'],
        'guide': (rev / 'STYLE.md').read_text(),
    }


def command(root, args):
    """The style CLI: create, save, show, retire. Mirrors studio.profile_command."""
    seed(root)
    if args.action == 'create':
        ident = studio.identifier(args.id) if args.id else studio.new_id(args.name)
        guide = studio.read_text(args.guide_file) if args.guide_file else ''
        return _create(root, ident, args.name, guide, args.status, args.sample)
    directory, record = studio.item(root, 'styles', args.id)
    if args.action == 'show':
        revision = args.revision or record['revision']
        saved = studio.inside(directory, 'revisions', str(revision))
        if not (saved / 'record.json').exists():
            raise ValueError('Unknown style revision.')
        return {**studio.read_json(saved / 'record.json'), 'guide': str(saved / 'STYLE.md')}
    if args.action == 'retire':
        if args.confirmed is not True or args.expected_revision != record['revision']:
            raise ValueError('Confirm the current style revision before retiring it.')
        if record['status'] != 'retired':
            record.update(status='retired', revision=record['revision'] + 1)
            studio.persist(directory, 'styles', record)
            snapshot(directory, record)
        return record
    guide = studio.read_text(args.guide_file)
    if not guide.strip():
        raise ValueError('Style guide cannot be empty.')
    samples = args.sample if args.sample is not None else record['sample_ids']
    validate_samples(root, samples)
    record['revision'] += 1
    if getattr(args, 'name', None):
        record['name'] = args.name
    record['sample_ids'] = samples
    record['status'] = args.status or record['status']
    studio.atomic(directory / 'STYLE.md', guide.encode())
    studio.persist(directory, 'styles', record)
    snapshot(directory, record)
    return record


def detail(root, ident):
    """One style for the page, with the version token its edits are checked against."""
    seed(root)
    directory, record = studio.item(root, 'styles', ident)
    guide = (directory / 'STYLE.md').read_text()
    return {
        **record,
        'guide': guide,
        'expected': studio.digest(json.dumps([record, guide], sort_keys=True).encode()),
    }


def catalog(root):
    """Every style, starters first, and the ready style samples."""
    seed(root)
    found, samples = [], []
    for file in sorted(studio.inside(root, 'styles').glob('*/record.json')):
        try:
            record = studio.read_json(file)
        except (ValueError, OSError):
            continue
        found.append(
            {
                key: record.get(key)
                for key in ('id', 'name', 'summary', 'kind', 'revision', 'status')
            }
        )
    found.sort(key=lambda row: (row['kind'] != 'seed', (row['name'] or '').lower()))
    for file in sorted(studio.inside(root, 'sources').glob('*/record.json')):
        record = studio.read_json(file)
        if 'style-sample' in record.get('purposes', []) and record.get('status') == 'ready':
            samples.append({key: record.get(key) for key in ('id', 'name', 'author', 'revision')})
    return {'styles': found, 'samples': samples}


def save(root, data):
    """The page's style-save: a new style, or a revision of one shown at `expected`."""
    selected = data.get('style')
    current = detail(root, selected) if selected else None
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
        file.write_text(guide)
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
    return {'style': record['id'], 'status': 'retired', 'revision': record['revision']}
