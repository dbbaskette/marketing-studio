"""Bounded, resumable blog research records. No network, models, or generated code."""
import json
import re
import uuid
from pathlib import Path
import studio

VERDICTS = ('supported', 'contradicted', 'insufficient', 'unavailable')


def nonempty(value, label, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label} needs nonempty text (max {limit} characters).')
    return value


def basis(directory):
    return {name: studio.artifact_fingerprint(directory, name) for name in ('DRAFT.md', 'OUTLINE.md', 'BRIEF.md')}


def locations(directory):
    return studio.inside(directory, 'derived', 'research.json'), studio.inside(directory, 'derived', 'research-report.md')


def literal(text):
    return re.sub(r'([\\`*_{}\[\]<>!#|])', r'\\\1', text)


def save(directory, record, value):
    path, report = locations(directory)
    if path.exists():
        studio.atomic(studio.inside(directory, 'history', 'editorial-research-' + uuid.uuid4().hex + '.json'), path.read_bytes())
    if report.exists():
        studio.atomic(studio.inside(directory, 'history', 'derived-research-report-' + uuid.uuid4().hex + '.md'), report.read_bytes())
    studio.write_json(path, value)
    pending = [i['id'] for i in value['items'] if i['id'] not in value['results']]
    unresolved = [i for i, r in value['results'].items() if r['status'] in ('insufficient', 'unavailable')]
    lines = ['# Research brief', '', f"Completed: {len(value['results'])}/{len(value['items'])}.",
             'Pending: ' + (', '.join(pending) or 'none') + '.',
             'Unresolved: ' + (', '.join(unresolved) or 'none') + '.', '',
             'Research gathers evidence; the factual-support review evaluates the blog.', '']
    for item in value['items']:
        result = value['results'].get(item['id'])
        lines += ['## ' + item['id'], '', literal(item['question']), '', 'Status: ' + (result['status'] if result else 'pending'), '']
        if result:
            lines += [literal(result['summary']), '', 'Limits: ' + literal(result['limits']), '']
            for evidence in result['evidence']:
                lines += ['Source: ' + literal(evidence['name']) + ' (' + evidence['source_id'] + ', revision ' + str(evidence['revision']) + ')',
                          'Origin: ' + evidence['origin'], 'Location: ' + literal(evidence['locator']), '', '> ' + literal(evidence['quote']).replace('\n', '\n> '), '']
    studio.atomic(report, ('\n'.join(lines) + '\n').encode())
    record['research'] = {'run': value['run'], 'path': 'derived/research.json', 'report': 'derived/research-report.md',
                          'sha256': studio.digest(path.read_bytes()), 'updated_at': studio.now()}
    studio.persist(directory, 'articles', record)
    return record


def plan(root, ident, supplied):
    directory, record = studio.item(root, 'articles', ident)
    if not isinstance(supplied, dict) or set(supplied) != {'purpose', 'scope', 'items'}:
        raise ValueError('Research plan needs purpose, scope and items.')
    if supplied['purpose'] not in ('planning', 'fact-check') or supplied['scope'] not in ('supplied-only', 'public-web'):
        raise ValueError('Choose planning/fact-check and supplied-only/public-web.')
    if supplied['scope'] == 'public-web' and record.get('research_policy') == 'supplied-only':
        raise ValueError('This article is limited to supplied sources. Keep that scope or obtain an explicit policy change.')
    items = supplied['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        raise ValueError('Plan 1–30 focused research questions.')
    seen = set()
    draft = (directory / 'DRAFT.md').read_text() if (directory / 'DRAFT.md').is_file() else ''
    for item in items:
        if not isinstance(item, dict) or set(item) != {'id', 'question', 'public_query', 'claim'}:
            raise ValueError('Each item needs id, question, public_query (text or null) and claim (quote/start or null).')
        key = studio.identifier(item['id'])
        if key in seen: raise ValueError('Research item IDs must be unique.')
        seen.add(key);nonempty(item['question'], 'Question')
        query = item['public_query']
        if query is not None:
            nonempty(query, 'Public query', 500)
            if supplied['scope'] != 'public-web':raise ValueError('Supplied-only research cannot contain public queries.')
            if re.search(r'https?://|[/\\]|@', query):raise ValueError('Public queries cannot contain URLs, file paths or email addresses.')
        claim = item['claim']
        if claim is not None:
            if not isinstance(claim, dict) or set(claim) != {'quote', 'start'} or type(claim['start']) is not int or claim['start'] < 0:
                raise ValueError('Claim needs an exact manuscript quote and nonnegative character start.')
            quote = nonempty(claim['quote'], 'Claim')
            if draft[claim['start']:claim['start'] + len(quote)] != quote:
                raise ValueError('Claim does not match this draft. Refresh its wording and location.')
        if supplied['purpose'] == 'fact-check' and claim is None:
            raise ValueError('Fact-check questions must map to an exact draft claim.')
    pin = basis(directory)
    run = studio.digest(json.dumps([supplied, pin], sort_keys=True, ensure_ascii=False).encode())[:24]
    path, _ = locations(directory)
    if path.exists():
        old = studio.read_json(path)
        if old['run'] == run:
            return record  # Resume without losing completed or unresolved results.
    value = {'schema': 1, 'run': run, **supplied, 'inputs': pin, 'results': {}, 'created_at': studio.now()}
    return save(directory, record, value)


def evidence(root, record, citation):
    required = {'source_id', 'revision', 'quote', 'start', 'locator'}
    if not isinstance(citation, dict) or set(citation) != required:
        raise ValueError('Evidence needs source_id, revision, exact quote/start and locator.')
    attached = next((s for s in record['sources'] if s['source_id'] == citation['source_id'] and 'reference' in s['purposes']), None)
    if not attached or attached['revision'] != citation['revision']:
        raise ValueError('Attach this exact source revision as a factual reference first.')
    folder, source = studio.item(root, 'sources', citation['source_id'])
    if source['revision'] != citation['revision']:
        folder = studio.inside(folder, 'revisions', str(citation['revision']))
        source = studio.read_json(folder / 'record.json')
    content = studio.inside(folder, 'content.md').read_text()
    quote = nonempty(citation['quote'], 'Evidence quote', 12000)
    start = citation['start']
    if type(start) is not int or start < 0 or content[start:start + len(quote)] != quote or source['status'] != 'ready':
        raise ValueError('Evidence must quote an available, pinned reference passage exactly.')
    nonempty(citation['locator'], 'Evidence location', 1000)
    from hub_workspace import portable_origin
    return {**citation, 'name': source['name'], 'origin': portable_origin(source['origin']),
            'content_sha256': studio.digest(content.encode())}


def record_result(root, ident, run, item_id, supplied):
    directory, record = studio.item(root, 'articles', ident)
    path, _ = locations(directory);value = studio.read_json(path)
    if value['run'] != run or basis(directory) != value['inputs']:
        raise ValueError('Research plan changed or manuscript is stale. Refresh the plan before recording results.')
    if item_id not in {i['id'] for i in value['items']}:
        raise ValueError('Unknown research item.')
    if not isinstance(supplied, dict) or set(supplied) != {'status', 'summary', 'limits', 'evidence'} or supplied['status'] not in VERDICTS:
        raise ValueError('Result needs status, summary, limits and evidence.')
    nonempty(supplied['summary'], 'Research summary', 12000);nonempty(supplied['limits'], 'Coverage limits', 4000)
    if not isinstance(supplied['evidence'], list) or len(supplied['evidence']) > 20:
        raise ValueError('Use at most 20 exact passages per item.')
    citations = [evidence(root, record, c) for c in supplied['evidence']]
    if supplied['status'] in ('supported', 'contradicted') and not citations:
        raise ValueError('Supported/contradicted research requires a traceable passage; missing evidence stays unresolved.')
    value['results'][item_id] = {**supplied, 'evidence': citations, 'checked_at': studio.now()}
    return save(directory, record, value)


def status(root, ident):
    directory, record = studio.item(root, 'articles', ident);path, report = locations(directory)
    if not path.exists():return {'id': ident, 'status': 'not-started'}
    value = studio.read_json(path)
    stale = basis(directory) != value['inputs'] or studio.digest(path.read_bytes()) != record.get('research', {}).get('sha256')
    for result in value['results'].values():
        for selected in result['evidence']:
            try:
                # Clone projections use different local IDs/revision numbers. Match the
                # inspected content + origin against selected pins, never a newer body.
                references = [v for v in record['sources'] if 'reference' in v['purposes']]
                exact = [v for v in references if v['source_id'] == selected['source_id']]
                candidates = exact or references
                matched = []
                from hub_workspace import portable_origin
                for pin in candidates:
                    folder, current = studio.item(root, 'sources', pin['source_id'])
                    if current['revision'] != pin['revision']:continue
                    if exact and pin['revision'] != selected['revision']:continue
                    if (portable_origin(current['origin']) == selected['origin']
                            and studio.digest(studio.inside(folder, 'content.md').read_bytes()) == selected['content_sha256']):
                        matched.append(pin)
                stale |= len(matched) != 1
            except (ValueError, OSError):stale = True
    pending = [i['id'] for i in value['items'] if i['id'] not in value['results']]
    unresolved = [i for i, r in value['results'].items() if r['status'] in ('insufficient', 'unavailable')]
    return {'id': ident, 'run': value['run'], 'status': 'stale' if stale else 'in-progress' if pending else 'complete',
            'purpose': value['purpose'], 'scope': value['scope'], 'pending': pending, 'unresolved': unresolved,
            'completed': len(value['results']), 'report': str(report), 'file': str(path),
            'assessment': 'Research coverage only; does not mark the factual-support review current.'}


def add_parser(groups):
    actions = groups.add_parser('research').add_subparsers(dest='action', required=True)
    for action in ('plan', 'record', 'status'):
        p = actions.add_parser(action);p.add_argument('--id', required=True)
        if action != 'status':p.add_argument('--file', required=True)
        if action == 'record':p.add_argument('--run', required=True);p.add_argument('--item', required=True)


def command(root, args):
    if args.action == 'status':return status(root, args.id)
    value = studio.read_json(Path(args.file))
    if args.action == 'plan':return plan(root, args.id, value)
    return record_result(root, args.id, args.run, args.item, value)
