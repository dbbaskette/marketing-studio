"""Focused editorial records. No model, Google reads, or automatic publication."""
from datetime import date
import argparse
import json
import re
import studio
from experience import page
from hub_store import HubError

STAGES = ('idea', 'draft', 'review', 'ready', 'published')


def doc_link(record):
    documents = record.get('google', {}).get('documents', {})
    for kind in ('draft', 'outline'):
        entry = documents.get(kind, {})
        url = entry.get('url', '')
        if re.fullmatch(r'https://docs\.google\.com/document/d/[A-Za-z0-9_-]+/(?:edit)?', url):
            return {'url': url, 'observed_at': entry.get('observed_at'), 'observation': 'saved link; not a live Google status'}
    # Older records store the same verified link on the transfer baseline.
    for entry in record.get('google', {}).get('baselines', {}).values():
        document = entry.get('document', {})
        url = document.get('url', '')
        if re.fullmatch(r'https://docs\.google\.com/document/d/[A-Za-z0-9_-]+/(?:edit)?', url):
            return {'url': url, 'observed_at': document.get('observed_at'), 'observation': 'saved link; not a live Google status'}
    return None


def row(record, ident, location, revision=None, conflict=False):
    details = record.get('editorial', {})
    stage = details.get('stage') or ('idea' if record.get('stage') in ('intake', 'brief', 'outline') else 'draft')
    decision_stale = bool(stage in ('ready', 'published') and details.get('draft') != record.get('artifact_hashes', {}).get('draft'))
    if decision_stale:stage = 'review'
    due = details.get('due')
    return {'id': ident, 'title': record.get('title', 'Untitled'), 'author': record.get('author') or 'Unassigned',
            'owner': details.get('owner') or 'Unassigned', 'stage': stage, 'due': due,
            'overdue': bool(due and due < date.today().isoformat() and stage != 'published'),
            'updated_at': record.get('updated_at'), 'next_step': record.get('next_step'),
            'google': doc_link(record), 'location': location, 'revision': revision, 'conflict': conflict,
            'publication_url': details.get('publication_url'), 'decision_stale': decision_stale}


def board(root, query='', stage=None, owner=None, limit=20, offset=0):
    """Metadata only, merging local work with the cached shared graph without fetching."""
    rows, errors, mapped = [], [], set()
    from hub_workspace import active
    adapter = active(root)
    if adapter:
        mapped = {v['item'] for k, v in adapter.state['items'].items() if k.startswith('articles/')}
    folder = studio.inside(root, 'articles')
    if folder.exists():
        for directory in sorted(folder.iterdir()):
            if not directory.is_dir(): continue
            try:
                _, record = studio.item(root, 'articles', directory.name)
                binding = adapter.state['items'].get('articles/' + record['id'], {}) if adapter else {}
                rows.append(row(record, record['id'], 'local', binding.get('revision')))
            except (ValueError, OSError, KeyError, TypeError):
                errors.append({'id': directory.name, 'status': 'unreadable'})
    if adapter:
        graph = adapter.hub.graph()
        for item_id, heads in graph['heads'].items():
            saved = graph['revisions'][heads[-1]]
            if saved['kind'] != 'article' or saved['status'] == 'tombstone': continue
            if item_id in mapped:
                for entry in rows:
                    binding = adapter.state['items'].get('articles/' + entry['id'], {})
                    if binding.get('item') == item_id:
                        entry['conflict'] = len(heads) > 1
                        entry['shared_newer'] = binding.get('revision') not in heads
                continue
            data = dict(saved['data'].get('studio', {}), title=saved['title'])
            rows.append(row(data, item_id, 'hub', saved['revision'], len(heads) > 1))
    rows = [r for r in rows if (not stage or r['stage'] == stage) and (not owner or r['owner'] == owner)
            and all(w in ' '.join(str(r.get(k) or '') for k in ('title', 'author', 'owner')).casefold() for w in query.casefold().split())]
    rows.sort(key=lambda r: (r['updated_at'] or '', r['id']), reverse=True)
    return {**page(rows, limit, offset), 'problems': errors[:10], 'sharing': 'selected-team-hub' if adapter else 'local',
            'observation': 'saved local and cached Hub metadata; refresh the Hub to check remote changes',
            'access': 'Everyone with Hub write access has the same editing controls.'}


def inputs(root, directory, record):
    sources = []
    for selected in record['sources']:
        if 'reference' not in selected['purposes']: continue
        folder, current = studio.item(root, 'sources', selected['source_id'])
        pinned = folder if current['revision'] == selected['revision'] else studio.inside(folder, 'revisions', str(selected['revision']))
        source = studio.read_json(pinned / 'record.json') if pinned != folder else current
        text = (pinned / 'content.md').read_bytes() if (pinned / 'content.md').is_file() else b''
        sources.append({'position': len(sources), 'sha256': studio.digest(text),
                        'origin': __import__('hub_workspace').portable_origin(source.get('origin', '')),
                        'name': source['name'], 'status': source['status']})
    return {'draft': studio.artifact_fingerprint(directory, 'DRAFT.md'), 'sources': sources}


def derived_status(root, directory, record):
    current = inputs(root, directory, record)
    return {name: {'status': 'current' if value.get('inputs') == current and studio.artifact_fingerprint(directory, value.get('path', 'missing')) == value.get('sha256') else 'stale',
                   'path': value.get('path'), 'created_at': value.get('created_at')}
            for name, value in record.get('editorial_assets', {}).items()}


def inbox(root, article_id=None, limit=20, offset=0, online=False, account=None, client=None):
    rows = []
    coverage = []
    if online and not article_id:raise ValueError('Choose a current blog before reading live Google feedback.')
    articles = [article_id] if article_id else [p.name for p in studio.inside(root, 'articles').iterdir() if p.is_dir()] if (root / 'articles').exists() else []
    for ident in articles:
        directory, record = studio.item(root, 'articles', ident)
        for check, review in studio.freshness(root, directory, record).items():
            coverage.append({'id': ident, 'check': check, 'status': review['status'], 'checked_at': review.get('checked_at')})
            if review['status'] in ('stale', 'unavailable'):
                rows.append({'id': ident, 'title': record['title'], 'kind': check, 'status': review['status'],
                             'action': 'Rerun this check against the current draft and selected sources.'})
            for number, finding in enumerate(review.get('result', {}).get('findings', [])[:100], 1):
                if isinstance(finding, dict) and finding.get('status') not in ('resolved', 'dismissed', 'applied'):
                    rows.append({'id': ident, 'title': record['title'], 'kind': check, 'status': review['status'], 'number': number,
                                 'finding': {k: str(finding[k])[:2000] for k in ('message', 'detail', 'original', 'replacement', 'severity') if k in finding},
                                 'action': 'Inspect the finding; applying an edit requires an explicit choice.'})
        for name, asset in derived_status(root, directory, record).items():
            if asset['status'] == 'stale':
                rows.append({'id': ident, 'title': record['title'], 'kind': name, 'status': 'stale', 'action': 'Regenerate this companion from the current inputs.'})
        from author_workflow import hub_state
        sharing = hub_state(root, record)
        if sharing['status'] not in ('shared', 'synchronized', 'local-only'):
            rows.append({'id': ident, 'title': record['title'], 'kind': 'Hub save', 'status': sharing['status'], 'action': 'Save and sync; inspect queued work or conflicts before continuing.'})
        evidence_path = directory / 'derived' / 'evidence.json'
        if evidence_path.is_file():
            for claim in studio.read_json(evidence_path).get('content', {}).get('claims', []):
                if claim['status'] in ('contradicted', 'insufficient'):
                    rows.append({'id': ident, 'title': record['title'], 'kind': 'claim evidence', 'status': claim['status'], 'blocking': True, 'finding': {'message': claim['claim']}, 'action': 'Inspect its exact cited passages before reusing the claim.'})
        if record.get('pending_question'):
            rows.append({'id': ident, 'title': record['title'], 'kind': 'question', 'status': 'waiting', 'action': record['pending_question']})
        if record.get('google'):
            rows.append({'id': ident, 'title': record['title'], 'kind': 'Google review', 'status': 'not-checked-live',
                         'action': 'Open the linked Doc or explicitly refresh Google review data.', 'google': doc_link(record)})
    from hub_workspace import active
    adapter = active(root)
    if adapter and not article_id:
        local_items = {v['item'] for k, v in adapter.state['items'].items() if k.startswith('articles/')}
        graph = adapter.hub.graph()
        for item_id, heads in graph['heads'].items():
            record = graph['revisions'][heads[-1]]
            if record['kind'] != 'article' or record['status'] == 'tombstone' or item_id in local_items:continue
            if len(heads) > 1:rows.append({'id': item_id, 'title': record['title'], 'kind': 'Hub conflict', 'status': 'conflict', 'blocking': True, 'action': 'Resolve competing revisions before resuming.'})
            for check, review in record['data'].get('studio', {}).get('reviews', {}).items():
                if review.get('status') in ('stale', 'unavailable') or review.get('result', {}).get('findings'):
                    rows.append({'id': item_id, 'title': record['title'], 'kind': check, 'status': review['status'], 'location': 'hub', 'action': 'Resume this blog to inspect its saved review findings.'})
    if online:
        _, record = studio.item(root, 'articles', article_id)
        rows = [r for r in rows if r['kind'] != 'Google review']
        link = doc_link(record)
        if link:
            from google_drive import Client, GoogleError
            import google_suggestions as gs
            selected_client = client or Client(account)
            document_id = link['url'].split('/d/', 1)[1].split('/', 1)[0]
            try:
                document = gs.review_read(selected_client, document_id)
                for thread in document.get('comments', [])[:100]:
                    if thread.get('status') == 'OPEN':rows.append({'id': article_id, 'title': record['title'], 'kind': 'Google comment', 'status': 'open', 'finding': {'message': str(thread.get('headPost', {}).get('content', ''))[:2000]}, 'action': 'Review in Google Docs.', 'google': link})
                pending = gs.summary(document)['pending']
                if pending:rows.append({'id': article_id, 'title': record['title'], 'kind': 'Google suggestions', 'status': 'open', 'count': pending, 'action': 'Review suggested edits in Google Docs.', 'google': link})
            except GoogleError:
                try:
                    for thread in selected_client.review_comments(document_id)[:100]:
                        if not thread.get('resolved') and not thread.get('deleted'):rows.append({'id': article_id, 'title': record['title'], 'kind': 'Google comment', 'status': 'open', 'finding': {'message': str(thread.get('content', ''))[:2000]}, 'action': 'Open Google Docs → All Comments.', 'google': link})
                    rows.append({'id': article_id, 'title': record['title'], 'kind': 'Google suggestions', 'status': 'unavailable', 'action': 'Native suggestion readback is unavailable; inspect Google Docs.'})
                except GoogleError:
                    rows.append({'id': article_id, 'title': record['title'], 'kind': 'Google review', 'status': 'unavailable', 'action': 'Check the Google connection; local findings remain available.'})
    for entry in rows:entry.setdefault('blocking', entry['status'] in ('stale', 'unavailable', 'conflict', 'contradicted') or entry.get('finding', {}).get('severity') in ('error', 'critical', 'blocking'))
    rows.sort(key=lambda r: (not r['blocking'], r['title'], r['kind']))
    return {**page(rows, limit, offset), 'coverage': coverage[:100], 'coverage_truncated': len(coverage) > 100,
            'google_observation': 'Read requested against the selected Doc at ' + studio.now() if online else 'No live Google request was made.'}



def schedule(root, ident, data):
    directory, record = studio.item(root, 'articles', ident)
    if set(data) - {'stage', 'owner', 'due', 'publication_url', 'expected'}: raise ValueError('Unknown editorial field.')
    if data.get('expected') and studio.digest((directory / 'session.json').read_bytes()) != data['expected']:
        raise ValueError('This blog changed. Reload before saving your decision.')
    details = dict(record.get('editorial', {}))
    if 'stage' in data:
        if data['stage'] not in STAGES: raise ValueError('Choose an editorial stage.')
        details['stage'] = data['stage']
    if 'owner' in data:
        if not isinstance(data['owner'], str) or len(data['owner']) > 200: raise ValueError('Owner is limited to 200 characters.')
        details['owner'] = data['owner'].strip()
    if 'due' in data:
        if data['due']: date.fromisoformat(data['due'])
        details['due'] = data['due'] or None
    if 'publication_url' in data:
        url = data['publication_url'] or ''
        if url and (not re.fullmatch(r'https://[^\s<>]+', url) or len(url) > 2000): raise ValueError('Use a public HTTPS publication URL.')
        details['publication_url'] = url
    if details.get('stage') == 'published' and not details.get('publication_url'):
        raise ValueError('Published needs the actual publication URL. This operation does not publish a blog.')
    details['decided_at'] = studio.now()
    if 'stage' in data:details['draft'] = studio.artifact_fingerprint(directory, 'DRAFT.md')
    if details.get('stage') in ('ready', 'published') and not details.get('draft'):raise ValueError('Save a draft before recording readiness or publication.')
    record['editorial'] = details
    studio.persist(directory, 'articles', record)
    return record


def evidence(root, ident, claims):
    directory, record = studio.item(root, 'articles', ident)
    draft = (directory / 'DRAFT.md').read_text()
    if not isinstance(claims, list) or not 1 <= len(claims) <= 100: raise ValueError('Supply 1–100 claim records.')
    provenance = inputs(root, directory, record)
    references = [s for s in record['sources'] if 'reference' in s['purposes']]
    checked = []
    for claim in claims:
        if not isinstance(claim, dict) or claim.get('status') not in ('supported', 'contradicted', 'insufficient', 'not-checked'):
            raise ValueError('Use an explicit evidence status.')
        quote = claim.get('claim', '')
        start = claim.get('start')
        if not isinstance(start, int) or not quote or len(quote) > 4000 or draft[start:start + len(quote)] != quote or start < 0:
            raise ValueError('Claim must match an exact current manuscript span.')
        citations = []
        for citation in claim.get('citations', []):
            index = citation.get('source')
            if not isinstance(index, int) or index < 0 or index >= len(references): raise ValueError('Choose a selected reference by position.')
            selected = references[index]
            folder, source = studio.item(root, 'sources', selected['source_id'])
            if source['revision'] != selected['revision']: folder = studio.inside(folder, 'revisions', str(selected['revision']))
            text = (folder / 'content.md').read_text()
            excerpt, offset = citation.get('quote', ''), citation.get('start')
            if not isinstance(offset, int) or offset < 0 or not excerpt or len(excerpt) > 4000 or text[offset:offset + len(excerpt)] != excerpt:
                raise ValueError('Evidence must match an exact pinned source passage.')
            citations.append({**provenance['sources'][index], 'quote': excerpt, 'start': offset})
        if claim['status'] in ('supported', 'contradicted') and not citations: raise ValueError('An evidence judgment requires cited source passages.')
        checked.append({'claim': quote, 'start': start, 'status': claim['status'], 'citations': citations,
                        'reason': str(claim.get('reason', ''))[:2000]})
    return save_asset(root, ident, 'evidence', {'claims': checked, 'coverage': 'Only explicitly selected claims have been checked; no quality score is inferred.'})


def save_asset(root, ident, name, payload):
    directory, record = studio.item(root, 'articles', ident)
    provenance = inputs(root, directory, record)
    if not provenance['draft']: raise ValueError('Save a manuscript before preparing companions.')
    name = studio.identifier(name)
    content = {'schema': 1, 'kind': name, 'inputs': provenance, 'created_at': studio.now(), 'content': payload}
    path = 'derived/' + name + '.json'
    target = studio.inside(directory, path)
    if target.exists():
        studio.atomic(studio.inside(directory, 'history', 'editorial-' + name + '-' + __import__('uuid').uuid4().hex + '.json'), target.read_bytes())
    studio.write_json(target, content)
    record.setdefault('editorial_assets', {})[name] = {k: content[k] for k in ('inputs', 'created_at')}
    record['editorial_assets'][name]['path'] = path
    record['editorial_assets'][name]['sha256'] = studio.digest(target.read_bytes())
    studio.persist(directory, 'articles', record)
    return record


def package(root, ident, data):
    if not isinstance(data, dict) or set(data) - {'channels', 'publication_url', 'notes'}: raise ValueError('Supply channels, publication_url, and optional notes.')
    channels = data.get('channels', [])
    if not isinstance(channels, list) or not 1 <= len(channels) <= 12: raise ValueError('Choose 1–12 channel drafts.')
    directory, record = studio.item(root, 'articles', ident)
    draft = (directory / 'DRAFT.md').read_text()
    saved = []
    for channel in channels:
        name, text = channel.get('name'), channel.get('text')
        if not isinstance(name, str) or not 1 <= len(name) <= 80 or not isinstance(text, str) or not 1 <= len(text) <= 12000: raise ValueError('Provide a named, bounded channel draft.')
        # Exact manuscript passages bind the author's choice of claims; no claim is silently fabricated.
        passages = channel.get('manuscript_quotes', [])
        if not passages or any(not isinstance(q, str) or not q or q not in draft for q in passages): raise ValueError('Each channel draft needs supporting manuscript passages.')
        maximum = channel.get('max_characters')
        if maximum is not None and (not isinstance(maximum, int) or maximum < 1): raise ValueError('Character limit must be positive.')
        saved.append({'name': name, 'text': text, 'characters': len(text), 'max_characters': maximum,
                      'over_limit': bool(maximum and len(text) > maximum), 'manuscript_quotes': passages})
    copy_path = studio.inside(directory, 'derived', 'publication-copy.md')
    if copy_path.exists():studio.atomic(studio.inside(directory, 'history', 'derived-publication-copy-' + __import__('uuid').uuid4().hex + '.md'), copy_path.read_bytes())
    studio.atomic(copy_path, draft.encode())
    return save_asset(root, ident, 'publication-package', {'channels': saved, 'publication_url': data.get('publication_url'),
        'missing_publication_url': not bool(data.get('publication_url')), 'notes': str(data.get('notes', ''))[:4000],
        'working_document': doc_link(record), 'final_copy': {'path': 'derived/publication-copy.md', 'sha256': studio.digest(draft.encode())},
        'factual_validation': 'Selected excerpts establish provenance; check each channel draft for unsupported additions before release.',
        'state': 'prepared only; sending or publishing requires a separate request'})


def visual(root, ident, data):
    if not isinstance(data, dict) or data.get('type') not in ('diagram', 'table', 'screenshot-plan'): raise ValueError('Choose diagram, table, or screenshot-plan.')
    for key in ('caption', 'alt', 'content'):
        if not isinstance(data.get(key), str) or not 1 <= len(data[key]) <= 16000: raise ValueError('Provide content, caption, and alt text.')
    directory, record = studio.item(root, 'articles', ident)
    draft = (directory / 'DRAFT.md').read_text()
    passages = data.get('manuscript_quotes', [])
    if not passages or any(not isinstance(q, str) or not q or q not in draft for q in passages): raise ValueError('Ground the visual in exact manuscript passages.')
    if data['type'] == 'diagram' and re.search(r'<\s*[a-z/]|click\s|https?://|init:|%%\{|javascript:', data['content'], re.I):
        raise ValueError('Use a plain diagram without links, HTML, or executable directives.')
    payload = {k: data[k] for k in ('type', 'content', 'caption', 'alt', 'manuscript_quotes')}
    payload['placement'] = str(data.get('placement', 'Choose a placement next to the explanation it supports.'))[:1000]
    payload['illustrative'] = data.get('illustrative', True) is True
    markdown = '# Visual companion\n\n' + ('Illustrative example.\n\n' if payload['illustrative'] else '')
    markdown += 'Placement: ' + payload['placement'] + '\n\n'
    markdown += ('```mermaid\n' + data['content'] + '\n```' if data['type'] == 'diagram' else data['content']) + '\n\nCaption: ' + data['caption'] + '\n\nAlternative text: ' + data['alt'] + '\n'
    target = studio.inside(directory, 'derived', 'visual-companion.md')
    if target.exists():studio.atomic(studio.inside(directory, 'history', 'derived-visual-companion-' + __import__('uuid').uuid4().hex + '.md'), target.read_bytes())
    studio.atomic(target, markdown.encode())
    payload['portable_output'] = {'path': 'derived/visual-companion.md', 'sha256': studio.digest(markdown.encode())}
    return save_asset(root, ident, 'visual-companion', payload)


def add_parser(groups):
    commands = groups.add_parser('editorial').add_subparsers(dest='action', required=True)
    for name in ('board', 'inbox'):
        p = commands.add_parser(name);p.add_argument('--id');p.add_argument('--limit', type=int, default=20);p.add_argument('--offset', type=int, default=0)
        if name == 'inbox':p.add_argument('--online', action='store_true');p.add_argument('--account')
        if name == 'board':
            p.add_argument('--query', default='');p.add_argument('--stage', choices=STAGES);p.add_argument('--owner')
    for name in ('schedule', 'evidence', 'package', 'visual'):
        p = commands.add_parser(name);p.add_argument('--id', required=True);p.add_argument('--file', required=True)
    p = commands.add_parser('assets');p.add_argument('--id', required=True)


def command(root, args):
    if args.action == 'board': return board(root, args.query, args.stage, args.owner, args.limit, args.offset)
    if args.action == 'inbox': return inbox(root, args.id, args.limit, args.offset, args.online, args.account)
    if args.action == 'assets':
        directory, record = studio.item(root, 'articles', args.id)
        return {'items': derived_status(root, directory, record)}
    data = studio.read_json(__import__('pathlib').Path(args.file))
    return {'schedule': schedule, 'evidence': evidence, 'package': package, 'visual': visual}[args.action](root, args.id, data)
