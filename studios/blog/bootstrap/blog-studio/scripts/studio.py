#!/usr/bin/env python3
"""Portable Blog Studio artifacts. Standard library; no model/network access."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid

PURPOSES = ('manuscript', 'outline', 'reference', 'inspiration', 'voice-sample', 'author-background')
MODES = ('existing', 'first-draft', 'outline-only', 'from-outline', 'interview', 'discover')
CHECKS = ('proofread', 'factual-support', 'shape', 'humanization', 'geo')
SOURCE_CHECKS = ('factual-support', 'geo')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identifier(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', value):
        raise ValueError('ID must contain lowercase letters, digits, and hyphens (max 80).')
    return value


def new_id(name):
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:60] or 'item'
    return slug + '-' + uuid.uuid4().hex[:8]


def inside(root, *parts):
    path = root.joinpath(*parts)
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('Path escapes workspace.')
    return path


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def write_json(path, value):
    atomic(path, (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode())


def read_json(path):
    from local_reads import read
    return json.loads(read(path).decode('utf-8'))


def read_text(path):
    return Path(path).read_text(encoding='utf-8')


def item(root, kind, value):
    directory = inside(root, kind, identifier(value))
    metadata = directory / ('session.json' if kind == 'articles' else 'record.json')
    if not metadata.is_file():
        raise ValueError(f'Unknown {kind} ID: {value}')
    return directory, read_json(metadata)


def metadata_path(directory, kind):
    return directory / ('session.json' if kind == 'articles' else 'record.json')


def persist(directory, kind, record):
    record['updated_at'] = now()
    write_json(metadata_path(directory, kind), record)


@contextmanager
def locked(root):
    lock = inside(root, '.studio.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Workspace is busy. If a previous process crashed, inspect its .studio.lock before removing it.')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def initialize(root):
    package = Path(__file__).resolve().parents[1]
    if root == package or root.is_relative_to(package):
        raise ValueError('Save author/article data outside the installed skill folder.')
    root.mkdir(parents=True, exist_ok=True)
    manifest = inside(root, 'studio.json')
    if not manifest.exists():
        write_json(manifest, {'schema_version': 1, 'created_at': now()})
    elif read_json(manifest).get('schema_version') != 1:
        raise ValueError('Unsupported workspace version.')
    for kind in ('profiles', 'sources', 'articles'):
        inside(root, kind).mkdir(exist_ok=True)
    return {'root': str(root), 'schema_version': 1}


def snapshot_profile(directory, record):
    rev = inside(directory, 'revisions', str(record['revision']))
    rev.mkdir(parents=True, exist_ok=True)
    write_json(rev / 'record.json', record)
    for name in ('VOICE.md', 'BACKGROUND.md', 'rules.json'):
        p = inside(directory, name)
        if p.exists():
            atomic(rev / name, p.read_bytes())


def voice_pin(root, profile_id, revision=None):
    directory, record = item(root, 'profiles', profile_id)
    version = revision or record['revision']
    version_dir = inside(directory, 'revisions', str(version))
    if not (version_dir / 'record.json').is_file():
        raise ValueError('Unknown profile revision.')
    return {'profile_id': profile_id, 'revision': version}


def validate_samples(root, values):
    for value in values:
        _, source = item(root, 'sources', value)
        if 'voice-sample' not in source['purposes']:
            raise ValueError('Profile samples must be classified as authored voice-sample material.')
        if source['status'] != 'ready':
            raise ValueError('Profile samples must have readable content.')


def profile_command(root, args):
    if args.action == 'create':
        value = identifier(args.id) if args.id else new_id(args.name)
        directory = inside(root, 'profiles', value)
        if directory.exists():
            raise ValueError('Profile already exists; use save to create a revision.')
        validate_samples(root, args.sample)
        record = {'id': value, 'name': args.name, 'revision': 1, 'status': args.status,
                  'sample_ids': args.sample, 'created_at': now()}
        guide = read_text(args.guide_file) if args.guide_file else ''
        if args.status == 'confirmed' and not guide.strip():
            raise ValueError('A confirmed profile needs a readable voice guide.')
        background = read_text(args.background_file) if args.background_file else ''
        rules = read_json(Path(args.rules_file)) if args.rules_file else {}
        validate_rules(rules)
        directory.mkdir()
        atomic(directory / 'VOICE.md', guide.encode())
        atomic(directory / 'BACKGROUND.md', background.encode())
        write_json(directory / 'rules.json', rules)
        persist(directory, 'profiles', record)
        snapshot_profile(directory, record)
        return record
    directory, record = item(root, 'profiles', args.id)
    if args.action == 'show':
        revision = args.revision or record['revision']
        saved = inside(directory, 'revisions', str(revision))
        if not (saved / 'record.json').exists():
            raise ValueError('Unknown profile revision.')
        return {**read_json(saved / 'record.json'), 'guide': str(saved / 'VOICE.md'),
                'background': str(saved / 'BACKGROUND.md'), 'rules': str(saved / 'rules.json')}
    guide = read_text(args.guide_file)
    if not guide.strip():
        raise ValueError('Voice guide cannot be empty.')
    samples = args.sample if args.sample is not None else record['sample_ids']
    validate_samples(root, samples)
    rules = read_json(Path(args.rules_file)) if args.rules_file else read_json(directory / 'rules.json')
    validate_rules(rules)
    record['revision'] += 1
    record['sample_ids'] = samples
    record['status'] = args.status or record['status']
    atomic(directory / 'VOICE.md', guide.encode())
    if args.background_file:
        atomic(directory / 'BACKGROUND.md', read_text(args.background_file).encode())
    write_json(directory / 'rules.json', rules)
    persist(directory, 'profiles', record)
    snapshot_profile(directory, record)
    return record


def validate_rules(rules):
    if not isinstance(rules, dict):
        raise ValueError('Rules must be a JSON object.')
    for name in ('banished_words', 'banished_phrases'):
        if name in rules and (not isinstance(rules[name], list) or not all(isinstance(x, str) for x in rules[name])):
            raise ValueError(f'{name} must be a list of strings.')
    for name in ('no_em_dashes', 'no_ascii_double_hyphen'):
        if name in rules and not isinstance(rules[name], bool):
            raise ValueError(f'{name} must be true or false.')


def source_command(root, args):
    if args.action == 'add':
        original = Path(args.file).read_bytes() if args.file else None
        text = getattr(args, 'content', None)
        if text is None:
            text = read_text(args.text_file) if args.text_file else None
        extraction = None
        if text is None and args.file and Path(args.file).suffix.lower() in ('.md', '.txt'):
            text = original.decode('utf-8')
        if text is None and args.file and Path(args.file).suffix.lower() in ('.html', '.htm'):
            from performance import extract
            extraction, _ = extract(root, original, Path(args.file).suffix)
            text = extraction['text']
        status = args.status or ('ready' if text and text.strip() else 'pending')
        if status == 'ready' and not (text and text.strip()):
            raise ValueError('Ready source needs nonempty extracted text; use pending/unavailable otherwise.')
        value = new_id(args.name)
        directory = inside(root, 'sources', value)
        directory.mkdir()
        extension = Path(args.file).suffix.lower() if args.file else ''
        original_path = 'original' + extension if original is not None else None
        if original is not None:
            atomic(directory / original_path, original)
        if text is not None:
            atomic(directory / 'content.md', text.encode())
        record = {'id': value, 'name': args.name, 'origin': args.origin or (str(Path(args.file).resolve()) if args.file else ''),
                  'original_filename': Path(args.file).name if args.file else None,
                  'original_path': original_path, 'original_sha256': digest(original) if original is not None else None,
                  'content_sha256': digest(text.encode()) if text is not None else None,
                  'purposes': args.purpose, 'author': args.author, 'status': status,
                  'note': args.note, 'revision': 1, 'created_at': now(), 'retrieved_at': now() if text else None}
        if extraction:
            record['extraction'] = {k:v for k,v in extraction.items() if k != 'text'}
        persist(directory, 'sources', record)  # Recoverable intake before a potentially slow CLI call.
        from source_curator import enrich
        enrich(root, record, text)
        persist(directory, 'sources', record)
        return record
    directory, record = item(root, 'sources', args.id)
    if args.action == 'show':
        return {**record, 'content_path': str(inside(directory, 'content.md')) if (directory / 'content.md').exists() else None,
                'original_file': str(inside(directory, record['original_path'])) if record['original_path'] else None}
    text = read_text(args.text_file) if args.text_file else ((directory / 'content.md').read_text() if (directory / 'content.md').exists() else None)
    status = args.status or record['status']
    if status == 'ready' and not (text and text.strip()):
        raise ValueError('Ready source needs extracted text.')
    history = inside(directory, 'revisions', str(record['revision']))
    history.mkdir(parents=True, exist_ok=True)
    write_json(history / 'record.json', record)
    if (directory / 'content.md').exists():
        atomic(history / 'content.md', (directory / 'content.md').read_bytes())
    if args.text_file:
        atomic(directory / 'content.md', text.encode())
        record['content_sha256'] = digest(text.encode())
        record['retrieved_at'] = now()
    record['revision'] += 1
    record['status'] = status
    if record.get('analysis',{}).get('sha256') != record.get('content_sha256') and record.get('analysis'):
        record['analysis']['status']='needs-analysis'
    if args.note is not None:
        record['note'] = args.note
    persist(directory, 'sources', record)
    from source_curator import enrich
    enrich(root, record, text)
    persist(directory, 'sources', record)
    return record


def artifact_fingerprint(directory, filename):
    p = inside(directory, filename)
    from local_reads import read
    return digest(read(p)) if p.exists() else None


def evidence_state(root, record):
    evidence = []
    for attached in record['sources']:
        if 'reference' not in attached['purposes']:
            continue
        directory, source = item(root, 'sources', attached['source_id'])
        from local_reads import read
        path = inside(directory, 'content.md')
        content = read(path) if path.is_file() else None
        evidence.append({'id': source['id'], 'revision': source['revision'], 'status': source['status'],
                         'hash': digest(content) if content is not None else None, 'origin': source['origin'],
                         'readable': bool(content and content.decode('utf-8').strip())})
    return evidence


def fingerprints(root, directory, record, evidence=None):
    evidence = evidence_state(root, record) if evidence is None else evidence
    return {'draft': artifact_fingerprint(directory, 'DRAFT.md'), 'voice': record['voice'],
            'evidence': digest(json.dumps(evidence, sort_keys=True).encode()),
            'guidance': (record.get('guidance') or {}).get('revision'),
            'memory': digest(json.dumps(record['memory'], sort_keys=True).encode()) if record.get('memory') else None,
            'hub_context': digest(json.dumps(record['hub_context']['selected'], sort_keys=True).encode()) if record.get('hub_context') else None}


def ready_evidence(root, record):
    for entry in evidence_state(root, record):
        if entry['status'] == 'ready' and entry['readable']:
            return True
    return False


def freshness(root, directory, record):
    evidence = evidence_state(root, record)
    current = fingerprints(root, directory, record, evidence)
    reviews = {}
    for check in CHECKS:
        saved = record['reviews'].get(check)
        if saved is None:
            reviews[check] = {'status': 'not-run'}
            continue
        shown = dict(saved)
        keys = ('draft', 'voice', 'guidance', 'hub_context', 'memory', 'evidence') if check in SOURCE_CHECKS else ('draft', 'voice', 'guidance', 'hub_context', 'memory')
        if any(saved['inputs'].get(key) != current[key] for key in keys):
            shown['status'] = 'stale'
            shown['previous_status'] = saved['status']
        if check == 'factual-support' and not any(e['status'] == 'ready' and e['readable'] for e in evidence):
            shown['status'] = 'unavailable'
            shown['detail'] = 'No readable factual references are selected.'
        reviews[check] = shown
    return reviews


def save_artifact(directory, kind, body, record, label="save"):
    previous = None
    target = inside(directory, kind.upper() + '.md')
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '-' + uuid.uuid4().hex[:8]
        previous = kind + '-' + stamp + '.md'
        atomic(inside(directory, 'history', previous), target.read_bytes())
    atomic(target, body.encode())
    if target.read_bytes() != body.encode():
        raise OSError('Saved artifact readback did not match; inspect the retained file before continuing.')
    record['stage'] = 'draft' if kind == 'draft' else 'outline' if kind == 'outline' else record['stage']
    record['artifact_hashes'][kind] = digest(body.encode())
    record.setdefault('artifact_events', []).append({'kind': kind, 'before': previous,
        'after_sha256': record['artifact_hashes'][kind], 'label': label[:200], 'at': now()})
    record['artifact_events'] = record['artifact_events'][-100:]
    return {'path': str(target), 'sha256': record['artifact_hashes'][kind], 'reopened': True}


def checked_author(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ValueError('Use an author name between 1 and 200 characters.')
    return value.strip()


def article_record(root, args, value):
    """Build new-article metadata without publishing a partially initialized article."""
    from writing_defaults import for_create
    default_voice = for_create(root, args)
    if default_voice:
        voice = {'mode': 'profile', **default_voice}
    elif args.profile:
        voice = {'mode': 'profile', **voice_pin(root, args.profile)}
    else:
        voice = {'mode': args.voice or 'preserve', 'tone': args.tone or ''}
    stops = {'existing': 'review', 'first-draft': 'draft', 'outline-only': 'outline',
             'from-outline': 'draft', 'interview': 'outline', 'discover': 'brief'}
    record = {'id': value, 'title': args.title, 'mode': args.mode, 'stage': 'intake',
              'author': checked_author(args.author) if args.author else '',
              'stop_point': args.stop or stops[args.mode], 'research_policy': args.research,
              'voice': voice, 'sources': [], 'reviews': {}, 'artifact_hashes': {},
              'next_step': 'Gather missing material and relevant context.', 'pending_question': None,
              'created_at': now()}
    record['writing_preferences'] = {key: getattr(args, key) for key in ('audience', 'blog_type', 'review_folder') if getattr(args, key, None) is not None}
    return record


def article_command(root, args):
    if args.action == 'create':
        value = identifier(args.id) if args.id else new_id(args.title)
        directory = inside(root, 'articles', value)
        if directory.exists():
            raise ValueError('Article already exists.')
        record = article_record(root, args, value)
        directory.mkdir()
        persist(directory, 'articles', record)
        write_json(inside(root, '.active-article.json'), {'id': value})
        return record
    directory, record = item(root, 'articles', args.id)
    if args.action == 'show':
        sources = []
        for attached in record['sources']:
            source_directory, source = item(root, 'sources', attached['source_id'])
            sources.append({**attached, 'name': source['name'], 'status': source['status'],
                            'current_revision': source['revision'], 'changed_since_attach': source['revision'] != attached['revision'],
                            'content_path': str(inside(source_directory, 'content.md')) if (source_directory / 'content.md').exists() else None})
        return {**record, 'directory': str(directory), 'selected_sources': sources,
                'reviews': freshness(root, directory, record)}
    if args.action == 'restore':
        from author_workflow import restore
        return restore(root, args)
    if args.action in ('remember', 'forget', 'detach-context'):
        from experience import change_context
        change_context(record, args)
    elif args.action == 'rename':
        if not args.title.strip() or len(args.title.strip()) > 500:
            raise ValueError('Use a blog title between 1 and 500 characters.')
        record['title'] = args.title.strip()
    elif args.action == 'author':
        record['author'] = checked_author(args.name)
    elif args.action == 'attach':
        _, source = item(root, 'sources', args.source)
        roles = args.purpose or source['purposes']
        entry = {'source_id': args.source, 'purposes': roles, 'revision': source['revision']}
        record['sources'] = [s for s in record['sources'] if s['source_id'] != args.source] + [entry]
    elif args.action == 'save':
        body = read_text(args.file)
        if not body.strip():
            raise ValueError('Cannot save an empty artifact.')
        if args.kind == 'draft' and record['stop_point'] in ('outline', 'brief'):
            raise ValueError('This task stops before drafting. Update its stop point only when the author requests a draft.')
        if args.kind == 'draft' and 'original' not in record['artifact_hashes'] and record['mode'] == 'existing':
            raise ValueError('Save the imported original before saving an edited draft.')
        if args.kind == 'original' and (directory / 'ORIGINAL.md').exists():
            raise ValueError('Imported original is immutable; revisions belong in DRAFT.md.')
        saved_artifact = save_artifact(directory, args.kind, body, record, label=args.label)
    elif args.action == 'progress':
        record['stage'] = args.stage
        record['next_step'] = args.next_step
        record['pending_question'] = args.pending_question
        if args.stop:
            record['stop_point'] = args.stop
    elif args.action == 'context':
        from hub_workspace import active
        adapter = active(root)
        if adapter is None:
            raise ValueError('Select a Team Hub before attaching shared context.')
        context = read_json(Path(args.file))
        if context.get('hub') != adapter.hub.id or context.get('conflicts') or context.get('truncated'):
            raise ValueError('Choose context from this hub and resolve applicable rule conflicts first.')
        graph = adapter.hub.graph()
        selected = []
        for reference in context.get('selected', []):
            shared = graph['revisions'].get(reference.get('revision'))
            if not shared or shared['item'] != reference.get('item') or shared['kind'] not in ('rule', 'context'):
                raise ValueError('A selected shared context revision is unavailable.')
            selected.append({'item': shared['item'], 'revision': shared['revision']})
        record['hub_context'] = {'hub': adapter.hub.id, 'revision': context['revision'], 'selected': selected}
    elif args.action == 'guidance':
        if not re.fullmatch(r'[0-9a-f]{32}', args.task):
            raise ValueError('Invalid guidance task ID.')
        pin = read_json(inside(root, 'task-context', 'tasks', args.task, 'pin.json'))
        if pin.get('task') != args.task or not re.fullmatch(r'[0-9a-f]{40,64}', pin.get('revision', '')):
            raise ValueError('Invalid saved guidance pin.')
        selected = {'task': args.task, 'revision': pin['revision'],
                    'runtime': str(Path(__file__).resolve().parent),
                    'freshness': 'cached' if args.cached else 'pinned'}
        previous = record.get('guidance')
        if previous and previous['task'] != args.task:
            if previous['revision'] != pin['revision'] and not args.adopt:
                raise ValueError('This article already has a guidance pin. Use --adopt only for an author-requested refresh.')
            if previous['revision'] != pin['revision']:
                record.setdefault('guidance_history', []).append(previous)
        record['guidance'] = selected
    elif args.action == 'note':
        target = inside(directory, 'INTERVIEW.md' if args.kind == 'interview' else 'DECISIONS.md')
        old = target.read_text() if target.exists() else ''
        atomic(target, (old + '\n\n' + args.text.strip()).strip().encode() + b'\n')
    elif args.action == 'voice':
        if args.profile:
            record['voice'] = {'mode': 'profile', **voice_pin(root, args.profile, args.revision)}
        else:
            record['voice'] = {'mode': args.voice, 'tone': args.tone or ''}
    elif args.action == 'review':
        data = read_json(Path(args.file)) if args.file else {}
        if not isinstance(data, dict):
            raise ValueError('Review result must be a JSON object.')
        if args.status == 'current' and not artifact_fingerprint(directory, 'DRAFT.md'):
            raise ValueError('A current review requires a saved manuscript.')
        if args.status == 'current' and (not isinstance(data.get('findings'), list)):
            raise ValueError('Current review needs a findings list and actual completed-check evidence.')
        status = args.status
        if args.check == 'factual-support' and not ready_evidence(root, record):
            status = 'unavailable'
            data = {'findings': [], 'detail': 'No readable factual references are selected.'}
        if args.check in record['reviews']:
            previous = record['reviews'][args.check]
            write_json(inside(directory, 'history', 'review-' + args.check + '-' + uuid.uuid4().hex + '.json'), previous)
        record['reviews'][args.check] = {'status': status, 'result': data,
                                        'inputs': fingerprints(root, directory, record), 'checked_at': now()}
    elif args.action == 'derive':
        body = read_text(args.file)
        name = identifier(args.name)
        target = inside(directory, 'derived', name + '.md')
        if target.exists():
            atomic(inside(directory, 'history', 'derived-' + name + '-' + uuid.uuid4().hex + '.md'), target.read_bytes())
        atomic(target, body.encode())
    persist(directory, 'articles', record)
    return {**record, 'directory': str(directory), 'reviews': freshness(root, directory, record),
            **({'saved_artifact': saved_artifact} if args.action == 'save' else {})}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, help='Absolute path to an author-chosen data workspace')
    groups = p.add_subparsers(dest='group', required=True)
    groups.add_parser('init')
    listing = groups.add_parser('list')
    listing.add_argument('kind', choices=('profiles', 'sources', 'articles'))
    from blog_library import add_parser as library_parser
    library_parser(groups)
    manage = groups.add_parser("manage");manage.add_argument("--port", type=int, default=0);manage.add_argument("--open", action="store_true");manage.add_argument("--harness", choices=("codex","claude"))
    from editorial import add_parser as editorial_parser
    editorial_parser(groups)
    from experience import add_parser as experience_parser
    experience_parser(groups)
    from performance import add_parser as performance_parser
    performance_parser(groups)
    from author_workflow import add_parser as author_parser
    author_parser(groups)
    profiles = groups.add_parser('profile').add_subparsers(dest='action', required=True)
    create = profiles.add_parser('create')
    create.add_argument('--name', required=True); create.add_argument('--id')
    create.add_argument('--guide-file'); create.add_argument('--background-file'); create.add_argument('--rules-file')
    create.add_argument('--status', choices=('provisional', 'confirmed'), default='provisional')
    create.add_argument('--sample', action='append', default=[])
    save = profiles.add_parser('save')
    save.add_argument('--id', required=True);save.add_argument('--guide-file', required=True)
    save.add_argument('--background-file');save.add_argument('--rules-file')
    save.add_argument('--status', choices=('provisional', 'confirmed'));save.add_argument('--sample', action='append')
    show = profiles.add_parser('show');show.add_argument('--id', required=True);show.add_argument('--revision', type=int)
    sources = groups.add_parser('source').add_subparsers(dest='action', required=True)
    add = sources.add_parser('add')
    add.add_argument('--name', required=True);add.add_argument('--file');add.add_argument('--text-file');add.add_argument('--origin')
    add.add_argument('--purpose', action='append', choices=PURPOSES, required=True)
    add.add_argument('--author', default='');add.add_argument('--note', default='')
    add.add_argument('--status', choices=('ready', 'pending', 'unavailable'))
    show = sources.add_parser('show');show.add_argument('--id', required=True)
    update = sources.add_parser('update');update.add_argument('--id', required=True);update.add_argument('--text-file')
    update.add_argument('--status', choices=('ready', 'pending', 'unavailable'));update.add_argument('--note')
    articles = groups.add_parser('article').add_subparsers(dest='action', required=True)
    create = articles.add_parser('create');create.add_argument('--title', required=True);create.add_argument('--id')
    create.add_argument('--mode', choices=MODES, required=True);create.add_argument('--profile');create.add_argument('--author')
    create.add_argument('--voice', choices=('preserve', 'tone'));create.add_argument('--tone')
    create.add_argument('--audience');create.add_argument('--blog-type');create.add_argument('--review-folder')
    create.add_argument('--research', choices=('supplied-only', 'web-allowed', 'unspecified'), default='unspecified')
    create.add_argument('--stop', choices=('draft', 'outline', 'review', 'brief'))
    show = articles.add_parser('show');show.add_argument('--id', required=True)
    rename = articles.add_parser('rename');rename.add_argument('--id', required=True);rename.add_argument('--title', required=True)
    author = articles.add_parser('author');author.add_argument('--id', required=True);author.add_argument('--name', required=True)
    for operation in ('remember', 'forget'):
        memory = articles.add_parser(operation); memory.add_argument('--id', required=True)
        memory.add_argument('--key', required=True)
        if operation == 'remember':
            memory.add_argument('--file', required=True)
    detach = articles.add_parser('detach-context');detach.add_argument('--id', required=True)
    detach.add_argument('--item', required=True)
    attach = articles.add_parser('attach');attach.add_argument('--id', required=True);attach.add_argument('--source', required=True)
    attach.add_argument('--purpose', action='append', choices=PURPOSES)
    save = articles.add_parser('save');save.add_argument('--id', required=True)
    save.add_argument('--kind', choices=('brief', 'original', 'draft', 'outline'), required=True);save.add_argument('--file', required=True)
    save.add_argument('--label', default='save', help='Operation name, such as proofread, for recovery')
    restore = articles.add_parser('restore');restore.add_argument('--id', required=True)
    restore.add_argument('--kind', choices=('draft', 'outline'), default='draft')
    restore.add_argument('--revision', required=True);restore.add_argument('--expected')
    restore.add_argument('--apply', action='store_true')
    progress = articles.add_parser('progress');progress.add_argument('--id', required=True)
    progress.add_argument('--stage', choices=('intake', 'interview', 'brief', 'outline', 'draft', 'review', 'complete'), required=True)
    progress.add_argument('--next-step', required=True);progress.add_argument('--pending-question')
    progress.add_argument('--stop', choices=('draft', 'outline', 'review', 'brief'))
    context = articles.add_parser('context');context.add_argument('--id', required=True);context.add_argument('--file', required=True)
    guidance = articles.add_parser('guidance');guidance.add_argument('--id', required=True);guidance.add_argument('--task', required=True)
    guidance.add_argument('--adopt', action='store_true');guidance.add_argument('--cached', action='store_true')
    note = articles.add_parser('note');note.add_argument('--id', required=True);note.add_argument('--kind', choices=('interview', 'decision'), required=True);note.add_argument('--text', required=True)
    voice = articles.add_parser('voice');voice.add_argument('--id', required=True);voice.add_argument('--profile');voice.add_argument('--revision', type=int)
    voice.add_argument('--voice', choices=('preserve', 'tone'), default='preserve');voice.add_argument('--tone')
    review = articles.add_parser('review');review.add_argument('--id', required=True);review.add_argument('--check', choices=CHECKS, required=True)
    review.add_argument('--status', choices=('current', 'unavailable', 'failed'), required=True);review.add_argument('--file')
    derive = articles.add_parser('derive');derive.add_argument('--id', required=True);derive.add_argument('--name', required=True);derive.add_argument('--file', required=True)
    from google_workflow import add_parser
    add_parser(groups)
    return p


def main():
    p = parser();args = p.parse_args()
    root = Path(args.root).expanduser()
    if not root.is_absolute():
        p.error('--root must be absolute')
    root = root.resolve()
    from hub_store import HubError
    try:
        if args.group == 'manage':
            from management import main as manage
            return manage(root, args.port, args.open, args.harness)
        if args.group == 'library' and args.action in ('collections', 'find', 'read'):
            from blog_library import command
            result = command(root, args)
        elif args.group in ('resume', 'passages', 'check', 'cache'):
            from performance import command
            result = command(root, args)
        elif args.group in ('home', 'context', 'readiness'):
            from experience import command
            result = command(root, args)
        elif args.group in ('status', 'route', 'changes') or (args.group == 'defaults' and args.action == 'show'):
            from author_workflow import command
            result = command(root, args)
        elif args.group == 'editorial' and args.action in ('board', 'inbox', 'assets'):
            from editorial import command
            result = command(root, args)
        elif args.group == 'init':
            result = initialize(root)
        else:
            if not (root / 'studio.json').is_file():
                raise ValueError('Initialize this workspace first.')
            with locked(root):
                if args.group == 'list':
                    result = []
                    for folder in sorted(inside(root, args.kind).iterdir()):
                        if folder.is_dir():
                            _, record = item(root, args.kind, folder.name)
                            result.append(record)
                elif args.group in ('select', 'defaults'):
                    from author_workflow import command
                    result = command(root, args)
                elif args.group == 'library':
                    from blog_library import command
                    result = command(root, args)
                elif args.group == 'editorial':
                    from editorial import command
                    result = command(root, args)
                elif args.group == 'profile': result = profile_command(root, args)
                elif args.group == 'source': result = source_command(root, args)
                elif args.group == 'google':
                    from google_workflow import command
                    result = command(root, args)
                else: result = article_command(root, args)
                mutation_group = 'article' if args.group == 'editorial' else 'source' if args.group == 'library' and args.action == 'curate' else args.group
                if args.group == 'google':
                    mutation_group = 'source' if args.action == 'source' else 'article' if args.action not in ('compare', 'capabilities', 'status') else None
                if mutation_group in ('profile', 'source', 'article') and args.action != 'show' and not (args.action == 'restore' and not args.apply):
                    from hub_workspace import active
                    from hub_store import HubError
                    try:
                        adapter = active(root)
                        if adapter:
                            result['hub_sync'] = adapter.publish_mutation(mutation_group, result)
                    except OSError as exc:
                        result['hub_sync'] = {'status': 'local-saved-not-shared',
                            'error': 'Hub filesystem access failed (' + type(exc).__name__ + ').',
                            'next_step': 'Local work is saved. Check sandbox/filesystem access to the selected Hub clone, then retry Hub sync; do not repeat the local operation.'}
                    except HubError as exc:
                        result['hub_sync'] = {'status': 'local-saved-not-shared', 'error': str(exc),
                            'next_step': 'Retry the selected workspace import after resolving the hub issue.'}
        if getattr(args, 'format', None) == 'markdown' and 'card' in result:
            print(result['card'])
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except (HubError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Blog Studio: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
