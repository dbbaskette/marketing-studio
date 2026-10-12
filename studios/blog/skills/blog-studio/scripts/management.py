"""A private local editorial desk. Standard library, loopback only, no hosted service."""
import argparse
import base64
from contextlib import contextmanager
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import re
import secrets
import shutil
import sys
import tempfile
import threading
import traceback
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs
import webbrowser

import studio
import editorial
import blog_library
import source_curator
from hub_store import HubError, TransportError, AuthenticationError, encoded, sha

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'management'
STATIC = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}
MAX_BODY = 15 * 1024 * 1024
HEADER_TIMEOUT = 3  # Seconds a new connection has to send its request line and headers.
BODY_TIMEOUT = 15   # Seconds for each read or write once a request is recognized.
API_WAIT = 30       # Seconds a request waits for another desk operation before reporting "busy".
UNCHANGED = {'status': 'unchanged', 'next_step': 'No changes to save.', 'receipts': []}


def checked_access(adapter):
    """Verify the same private repository before reporting read/write capability."""
    metadata = adapter.hub.registry.provider.lookup(adapter.hub.config['repository'])
    if not metadata:
        raise TransportError('The selected Hub is unavailable to this account. Check GitHub access.')
    if (metadata.get('private') is not True
            or metadata.get('id') != adapter.hub.config['provider_id']
            or metadata.get('repository') != adapter.hub.config['repository']):
        raise HubError('Hub identity or privacy changed. Editing and refresh are blocked; saved content is preserved.')
    return metadata


def capabilities(root):
    """A fresh permission observation, never a reusable authorization to mutate."""
    from hub_workspace import active
    adapter = active(root)
    status, edit, refresh, memory = 'local-only', True, False, False
    message = 'No Team Hub selected. Local blogs and references are editable; join a Hub for shared memory.'
    if adapter:
        edit = refresh = memory = False
        try:
            metadata = checked_access(adapter)
            refresh = True
            if metadata.get('write') is True:
                status, edit, memory = 'writable', True, True
                message = 'Hub access verified. You can refresh and edit shared work.'
            elif metadata.get('write') is False:
                status = 'read-only'
                message = 'Read-only Hub access. You can browse and refresh; shared edits need GitHub write access.'
            else:
                status = 'unverified'
                message = 'Hub read access verified; contribution permission is unavailable. You can refresh and browse.'
        except AuthenticationError:
            status = 'access-expired'
            message = 'GitHub sign-in expired or is missing. Sign in again, then check access. Saved content remains available.'
        except TransportError:
            status = 'unavailable'
            message = 'Hub access cannot be verified right now. Check connectivity and repository access, then check again. Saved content remains available.'
        except HubError:
            status = 'identity-mismatch'
            message = 'Hub identity or privacy could not be verified. Inspect the Hub in chat before refreshing or editing.'
    return {'status': status, 'message': message, 'checked_at': studio.now(),
            'actions': {'edit': edit, 'memory': memory, 'refresh': refresh},
            'google': 'not-checked', 'google_message': 'Google access is checked separately in chat.',
            'analysis': source_curator.disclosure(root), **identity(root, adapter)}


def identity(root, adapter):
    """Which workspace and Hub this desk reads and writes, so two desks cannot be confused."""
    try:
        shown = '~/' + root.relative_to(Path.home()).as_posix()
    except (ValueError, RuntimeError):
        shown = str(root)
    hub = None
    if adapter:
        hub = {'repository': adapter.hub.config.get('repository'), 'url': adapter.hub.config.get('url')}
    return {'workspace': shown, 'hub': hub}


def authorize_write(root):
    """One contributor level; reverify access for each actual mutation."""
    from hub_workspace import active
    adapter = active(root)
    if adapter and checked_access(adapter).get('write') is not True:
        raise ValueError('Hub write access could not be verified. Check GitHub access before editing shared work.')
    return adapter


def share(root, group, record):
    from hub_workspace import active
    adapter = active(root)
    if adapter:
        try:
            record['hub_sync'] = adapter.publish_mutation(group, record)
        except Exception as exc:
            # The local save already happened. Whatever stopped sharing, report it truthfully
            # as "saved locally" instead of failing the request and leaving the result unclear.
            if not isinstance(exc, (HubError, OSError)):note_unexpected(exc)
            record['hub_sync'] = {'status': 'local-saved-not-shared', 'next_step': 'Local work is saved. Retry Hub sync.'}
    return record


SHARING_MESSAGES = {
    'shared': 'Shared with the Team Hub.',
    'synchronized': 'Shared with the Team Hub.',
    'pending-review': 'Saved; waiting for contribution review.',
    'conflicting': 'Saved; competing Hub revisions need resolution in chat.',
    'newer-hub-revision': 'Saved here; the Team Hub has a newer version. Continue this one in chat to bring them together.',
    'review-closed': 'Saved; its contribution review was closed. Retry sync to open a new review.',
    'local-only': 'Saved in this workspace; no Team Hub selected.',
}


def receipt(root, label, result, group=None):
    """A durable local receipt, without manuscript content or provider credentials."""
    from hub_workspace import active
    adapter = active(root)
    sync = result.get('hub_sync', {}) if group else result
    sharing = sync.get('status', 'local-saved-not-shared' if adapter else 'local-only')
    reference = sync.get('item', {}) if group else sync
    value = {'label': label, 'local_saved': True, 'sharing': sharing,
             'hub': adapter.hub.id if adapter else None,
             'group': group, 'local_id': result.get('id') if group else None,
             'item': reference.get('item') if isinstance(reference, dict) else None,
             'revision': reference.get('revision') if isinstance(reference, dict) else None,
             'checked_at': studio.now()}
    if adapter and group:
        try:
            value['checkpoint'] = local_checkpoint(root, adapter, group, result['id'])
        except (HubError, OSError, ValueError):
            value['checkpoint'] = None
    ident = sha(encoded([value['hub'], group, value['local_id'] or value['item']]))
    value['id'] = ident
    studio.write_json(studio.inside(root, '.desk-receipts', ident + '.json'), value)
    return public_receipt(value)


def local_checkpoint(root, adapter, group, ident):
    directory, record = studio.item(root, {'source': 'sources', 'article': 'articles'}[group], ident)
    artifacts = adapter.read_artifacts(directory, {'source': 'sources', 'article': 'articles'}[group])
    inputs = studio.fingerprints(root, directory, record) if group == 'article' else {}
    return sha(encoded({'record': record, 'inputs': inputs, 'files': {n:sha(v[0]) for n,v in artifacts.items()}}))


def public_receipt(value):
    status = value['sharing']
    message = SHARING_MESSAGES.get(status, 'Saved locally; Hub sync needs attention.')
    # A held save needs the author's choice in chat; retrying the same push cannot succeed.
    retry = bool(value['hub'] and status not in ('shared', 'synchronized', 'conflicting', 'local-only', 'newer-hub-revision'))
    return {k: value[k] for k in ('id', 'label', 'local_saved', 'sharing', 'checked_at')} | {'message': message, 'retry': retry}


def receipts(root):
    from hub_workspace import active
    adapter = active(root)
    folder = studio.inside(root, '.desk-receipts')
    if not folder.exists():return {'items': []}
    remote = adapter.hub.graph(include_local=False) if adapter else None
    local = adapter.hub.graph() if adapter else None
    items = []
    for path in sorted(folder.glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)[:50]:
        value = studio.read_json(studio.inside(folder, path.name))
        if value['hub'] != (adapter.hub.id if adapter else None):continue
        if remote and value.get('revision') in remote['revisions']:
            value['sharing'] = 'conflicting' if len(local['heads'].get(value['item'], [])) > 1 else 'shared'
        items.append(public_receipt(value))
    return {'items': items, 'observation': 'Saved operation receipts; refresh the Hub to check remote changes.'}


def retry_receipt(root, adapter, data):
    if set(data) != {'id'} or not re.fullmatch(r'[a-f0-9]{64}', data.get('id', '')):
        raise ValueError('Choose a saved operation to retry.')
    path = studio.inside(root, '.desk-receipts', data['id'] + '.json')
    value = studio.read_json(path)
    if not adapter or value['hub'] != adapter.hub.id:raise ValueError('Select the original Team Hub before retrying.')
    if value.get('group') and not value.get('revision'):
        group = {'source': 'sources', 'article': 'articles'}[value['group']]
        if not value.get('checkpoint') or local_checkpoint(root, adapter, value['group'], value['local_id']) != value['checkpoint']:
            raise ValueError('This saved work changed. Inspect it in chat before sharing a new checkpoint.')
        reference = adapter._publish(group, value['local_id'])
        value.update(item=reference['item'], revision=reference['revision'])
        studio.write_json(path, value)  # Retain identity before a potentially uncertain transport.
    result = adapter.hub.sync()
    adapter.record_confirmed_saves(result)
    value.update(sharing=result['status'], checked_at=studio.now())
    remote = adapter.hub.graph(include_local=False)
    if value.get('revision') in remote['revisions']:
        value['sharing'] = 'conflicting' if len(adapter.hub.graph()['heads'].get(value['item'], [])) > 1 else 'shared'
    studio.write_json(path, value)
    return {'receipts': [public_receipt(value)]}


def upload(root, data):
    if set(data) - {'operation', 'filename', 'content', 'title', 'purpose', 'as_blog', 'author', 'analyze'}:raise ValueError('Unknown upload field.')
    if not isinstance(data.get('analyze', True), bool):raise ValueError('Choose whether to summarize and tag this upload.')
    operation = data.get('operation', '')
    if not re.fullmatch(r'[a-f0-9]{32}', operation):raise ValueError('An upload operation ID is required.')
    staging = studio.inside(root, '.uploads');staging.mkdir(mode=0o700, exist_ok=True);staging.chmod(0o700)
    ledger = studio.inside(staging, operation + '.json')
    fingerprint = sha(encoded(data))
    if ledger.exists():
        saved = studio.read_json(ledger)
        if saved['fingerprint'] != fingerprint:raise ValueError('This operation ID belongs to a different upload.')
        if saved.get('result'):return saved['result']
        raise ValueError('This upload has an uncertain result. Inspect retained work before retrying; do not create a duplicate.')
    filename = data.get('filename', '')
    if not isinstance(filename, str) or Path(filename).name != filename or len(filename) > 200 or filename.startswith('.'):
        raise ValueError('Use a simple upload filename.')
    suffix = Path(filename).suffix.lower()
    if suffix not in ('.md', '.txt', '.html', '.htm', '.docx', '.pdf'):raise ValueError('Upload Markdown, text, HTML, DOCX, or PDF.')
    content = base64.b64decode(data.get('content', ''), validate=True)
    if not content or len(content) > blog_library.MAX_BINARY:raise ValueError('Upload a nonempty file of at most 10 MiB.')
    text, status = blog_library.extract(root, content, suffix)
    if text is not None and len(text.encode()) > blog_library.MAX_TEXT:raise ValueError('Extracted text exceeds the shared file limit.')
    title = data.get('title') or Path(filename).stem
    if not isinstance(title, str) or not 1 <= len(title) <= 500:raise ValueError('Use a title under 500 characters.')
    purpose = data.get('purpose', 'reference')
    if purpose not in studio.PURPOSES:raise ValueError('Choose a source purpose.')
    if data.get('as_blog') and not (text and text.strip()):raise ValueError('This file needs text extraction before it can become an editable blog. Upload it as a pending reference first.')
    if data.get('author'):studio.checked_author(data['author'])
    studio.write_json(ledger, {'fingerprint': fingerprint, 'state': 'started'})
    # An unchecked "Summarize and tag" keeps this file's text away from the analysis CLI.
    with tempfile.TemporaryDirectory(dir=staging) as temp, source_curator.skipping(data.get('analyze') is False):
        path = Path(temp) / filename;path.write_bytes(content)
        source = studio.source_command(root, SimpleNamespace(action='add', name=title, file=str(path), content=text, text_file=None,
            origin=filename, purpose=[purpose], author=data.get('author') or None, note='Uploaded through the local editorial desk.', status=status))
    result = {'source': share(root, 'source', source), 'state': status, 'next_step': 'Source saved. Pending files need extraction before use.' if status != 'ready' else 'Source saved; attach it only to the blogs that need it.'}
    if data.get('as_blog'):
        args = SimpleNamespace(action='create', title=title, id=None, mode='existing', author=data.get('author'),
            profile=None, voice='preserve', tone=None, stop='review', research='supplied-only', audience=None, blog_type=None, review_folder=None)
        article = studio.article_command(root, args)
        directory, article = studio.item(root, 'articles', article['id'])
        studio.save_artifact(directory, 'original', text, article, 'uploaded original')
        studio.save_artifact(directory, 'draft', text, article, 'starting manuscript')
        article['sources'] = [{'source_id': source['id'], 'revision': source['revision'], 'purposes': ['manuscript']}]
        studio.persist(directory, 'articles', article)
        result['article'] = share(root, 'article', article)
    result['receipts'] = [receipt(root, 'Uploaded reference', result['source'], 'source')]
    if result.get('article'):result['receipts'].append(receipt(root, 'Uploaded blog', result['article'], 'article'))
    studio.write_json(ledger, {'fingerprint': fingerprint, 'state': 'saved', 'result': result})
    return result


def memories(root, limit=20, offset=0, query=''):
    from hub_workspace import active
    adapter = active(root)
    if not adapter:return {'items': [], 'total': 0, 'next_step': 'Join a Team Hub to curate shared memory.'}
    graph = adapter.hub.graph();rows = []
    for item_id, heads in graph['heads'].items():
        for revision in heads:
            record = graph['revisions'][revision]
            if record['kind'] not in ('rule', 'context', 'note', 'decision') or record['status'] == 'tombstone':continue
            rows.append({k: record[k] for k in ('item', 'revision', 'title', 'kind', 'scope', 'summary', 'status')} | {
                'conflict': len(heads) > 1, 'lesson': record['data'].get('lesson'),
                'focused_workflow': bool(record['data'].get('collection') or record['data'].get('lesson')),
                'lesson_status': blog_library.lesson_state(adapter, record) if record['data'].get('lesson') else None})
    rows = [r for r in rows if all(term in (r['title'] + ' ' + r['summary'] + ' ' + r['kind'] + ' ' + r['scope']['key']).casefold() for term in query.casefold().split())]
    return __import__('experience').page(rows, limit, offset)


class CurationConflict(ValueError):
    """An inspected source changed; the proposal must not be applied implicitly."""


def source_detail(root, ident, location='local'):
    if location not in ('local', 'hub'):raise ValueError('Choose a local or shared source.')
    from hub_workspace import active
    adapter = active(root)
    rows = blog_library.source_rows(root)
    selected = next((r for r in rows if r['id'] == ident and r['location'] == location), None)
    # A refreshed shared head can replace the local catalog row. Reload shows
    # that head for comparison; the changed selection invalidates the old form.
    if not selected and location == 'local' and adapter:
        binding = adapter.state['items'].get('sources/' + ident, {})
        selected = next((r for r in rows if r['id'] == binding.get('item') and r['location'] == 'hub'), None)
    if not selected and location == 'hub' and adapter:
        # The catalog suppresses a shared row when a local checkout represents
        # it. Explicit shared-form inspection still reads that exact shared head.
        try:
            saved = adapter.hub.read(ident)
        except HubError as exc:
            raise CurationConflict('This shared reference changed or has competing revisions. Compare them in chat before editing.') from exc
        shared = saved['record']
        if shared['kind'] == 'source' and shared['status'] != 'tombstone':
            selected = {'id': ident, 'location': 'hub',
                        'record': dict(shared['data'].get('studio', {}), name=shared['title'], revision=shared['revision']),
                        'body': Path(saved['paths']['BODY.md']).read_bytes(),
                        'binding': {'item': ident, 'revision': shared['revision']}}
    if not selected:raise CurationConflict('This reference changed or is no longer available. Reload the library before editing it.')
    binding = selected.get('binding', {})
    local_versions = []
    if adapter and binding:
        for key, saved in sorted(adapter.state['items'].items()):
            if key.startswith('sources/') and saved['item'] == binding['item']:
                _, local = studio.item(root, 'sources', key.split('/', 1)[1])
                local_versions.append({'key': key, 'record': local, 'binding': saved})
    expected = sha(encoded({'id': selected['id'], 'location': selected['location'],
                            'record': selected['record'], 'binding': binding,
                            'hub': adapter.hub.id if adapter else None, 'local_versions': local_versions}))
    location = selected['location']
    record = selected['record']
    text = selected.get('body', b'').decode() if location == 'hub' else selected['path'].read_text() if selected['path'].is_file() else ''
    return {'record': record, 'id': selected['id'], 'expected': expected,
            'excerpt': text[:8000], 'truncated': len(text) > 8000, 'location': location,
            'limitation': 'Pending extraction; no source text was read.' if record['status'] != 'ready' else 'Selected saved source; historical facts need current verification.'}


def manuscript_preview(paths):
    for name in ('DRAFT.md', 'OUTLINE.md', 'BRIEF.md', 'ORIGINAL.md'):
        path = paths.get(name)
        if path and Path(path).is_file():
            with Path(path).open('rb') as stream:text = stream.read(16001)
            return {'kind': name.removesuffix('.md').lower(),
                    'text': text[:16000].decode('utf-8', errors='replace'), 'truncated': len(text) > 16000}
    return {'kind': None, 'text': '', 'truncated': False}


def article_view(ident, record, location, preview, reviews, conflict=False, shared_newer=False):
    stage = editorial.row(record, ident, location, conflict=conflict)
    stop = record.get('stop_point', 'draft')
    question = record.get('pending_question')
    stale = [name for name, review in reviews.items() if review['status'] == 'stale']
    unavailable = [name for name, review in reviews.items() if review['status'] in ('unavailable', 'failed')]
    reached = stop in ('brief', 'outline', 'draft') and preview['kind'] == stop
    state, blocker, label, request = stage['stage'], '', 'Continue in chat', 'Show the saved work and help me choose the next step.'
    if conflict:
        state, blocker, label = 'conflict', 'Competing shared revisions need comparison before resuming or editing.', 'Compare revisions in chat'
        request = 'Compare competing Hub revisions before resuming or editing this blog.'
    elif shared_newer:
        state, blocker, label = 'shared-newer', 'A newer shared revision exists. Compare it with local work before continuing.', 'Compare shared changes in chat'
        request = 'Compare the newer shared revision with my local work before making changes.'
    elif stage['decision_stale']:
        state, blocker, label = 'review', 'The manuscript changed after the recorded ready or published decision. That decision is no longer current.', 'Inspect changed draft in chat'
        request = 'Show what needs a new review after the manuscript changed; do not renew readiness or publication automatically.'
    elif question:
        state, blocker, label = 'waiting', str(question)[:2000], 'Answer the waiting question in chat'
        request = 'Show the waiting question and help me answer it.'
    elif reached:
        state, label = 'stop-reached', 'Inspect saved ' + stop + ' in chat'
        request = 'Show the saved ' + stop + ' and its available follow-ups; do not advance beyond my requested stop.'
    elif stale:
        blocker, label = 'Saved reviews are stale: ' + ', '.join(stale) + '.', 'Inspect stale reviews in chat'
        request = 'Show the stale reviews and their affected inputs before rerunning any checks.'
    elif unavailable:
        blocker, label = 'Some checks need attention: ' + ', '.join(unavailable) + '.', 'Inspect review coverage in chat'
        request = 'Show unavailable or failed checks and the missing evidence or access.'
    elif not preview['text']:
        state, label = 'empty', 'Plan this blog in chat'
        request = 'Help me gather the missing material for the requested writing step.'
    elif stage['stage'] == 'ready':
        label = 'Inspect ready blog in chat'
        request = 'Show the saved draft and review coverage; publication remains a separate explicit choice.'
    elif preview['kind'] == 'draft':
        label = 'Review draft in chat'
        request = 'Show the current draft and review coverage, then help me choose the next review.'
    elif preview['kind'] == 'outline':
        label = 'Continue outline in chat'
        request = 'Show this outline and help me choose the next step.'
    command = 'Use Blog Studio. ' + ('Inspect shared blog ' if location == 'hub' else 'Continue blog ') + ident + '. ' + request
    command += ' Keep the requested stopping point (' + stop + ') unless I explicitly change it.'
    return {'id': ident, 'location': location, 'state': state, 'stage': stage['stage'], 'stop_point': stop,
            'stop_reached': reached, 'blocker': blocker, 'decision_stale': stage['decision_stale'],
            'conflict': conflict, 'shared_newer': shared_newer, 'google': editorial.doc_link(record),
            'google_observation': 'Saved link only; Google access and document freshness are checked in chat.' if editorial.doc_link(record) else 'No saved Google Doc link. Keep writing in chat; Google access can be checked there.',
            'reviews': [{'check': name, 'status': review['status'], 'checked_at': review.get('checked_at'),
                         'detail': review.get('detail') or ('Inputs changed since this review.' if review['status'] == 'stale' else '')}
                        for name, review in reviews.items()],
            'next_action': {'label': label, 'command': command}, 'preview': preview}


def detail(root, ident, location='local', revision=None):
    if location not in ('local', 'hub'):raise ValueError('Choose a local or shared blog.')
    from hub_workspace import active
    adapter = active(root)
    if location == 'hub':
        if not adapter:raise ValueError('Select a Hub.')
        graph = adapter.hub.graph();heads = graph['heads'].get(ident, [])
        if not heads:raise ValueError('Choose an available shared blog.')
        selected = revision or heads[-1]
        if selected not in heads:raise ValueError('This shared blog changed. Reload before inspecting its current revision.')
        saved = adapter.hub.read(ident, selected);shared = saved['record']
        if shared['kind'] != 'article' or shared['status'] == 'tombstone':raise ValueError('Choose a shared blog.')
        record = dict(shared['data'].get('studio', {}), title=shared['title'])
        paths = {name.removeprefix('artifacts/'):path for name,path in saved['paths'].items() if name.startswith('artifacts/')}
        preview = manuscript_preview(paths)
        reviews = {name:{'status':'needs-local-check' if value['status'] == 'current' else value['status'],
                          'checked_at':value.get('checked_at'), 'detail':'Shared review snapshot; resume in chat to verify current local inputs.'}
                   for name,value in record.get('reviews', {}).items()}
        return {'record': record, 'title': record['title'], 'location': 'hub', 'revision': selected,
                'assets': {}, 'history': [], 'sources': shared.get('dependencies', [])[:20],
                'view': article_view(ident, record, location, preview, reviews, conflict=len(heads)>1)}
    directory, record = studio.item(root, 'articles', ident)
    paths = {name:studio.inside(directory, name) for name in ('DRAFT.md','OUTLINE.md','BRIEF.md','ORIGINAL.md')}
    preview = manuscript_preview(paths)
    current = dict(record, artifact_hashes={**record.get('artifact_hashes', {}), 'draft':studio.artifact_fingerprint(directory, 'DRAFT.md')})
    binding = adapter.state['items'].get('articles/' + ident, {}) if adapter else {}
    heads = adapter.hub.graph()['heads'].get(binding.get('item'), []) if binding else []
    history = studio.inside(directory, 'history')
    return {'record': record, 'title': record['title'], 'expected': sha((directory / 'session.json').read_bytes()),
            'assets': editorial.derived_status(root, directory, record), 'location': 'local',
            'sources': record.get('sources', [])[:20],
            'history': [p.name for p in sorted(history.iterdir(), key=lambda p:p.name, reverse=True)[:10]] if history.is_dir() else [],
            'view': article_view(ident, current, location, preview, studio.freshness(root, directory, record),
                                 conflict=len(heads)>1, shared_newer=bool(binding and binding.get('revision') not in heads))}


def finding_detail(root, ident, key, location='local'):
    if location not in ('local','hub'):raise ValueError('Choose a local or shared finding.')
    result = editorial.inbox(root, article_id=ident if location=='local' else None,
                             shared_id=ident if location=='hub' else None, query=key)
    finding = next((entry for entry in result['items'] if entry['id']==ident and entry['key']==key), None)
    if not finding:raise ValueError('This finding changed or is no longer available. Reload the inbox.')
    article = detail(root, ident, location)
    evidence = []
    if location == 'local' and finding['kind'] == 'claim evidence':
        directory, _ = studio.item(root, 'articles', ident)
        saved = studio.read_json(studio.inside(directory, 'derived/evidence.json'))
        claim = next((entry for entry in saved.get('content', {}).get('claims', [])
                      if entry['claim']==finding['finding']['message'] and entry['start']==finding.get('claim_start')), None)
        if claim:evidence = claim.get('citations', [])[:10]
    command = ('Use Blog Studio. ' + ('Inspect shared blog ' if location=='hub' else 'Continue blog ') + ident
               + '. Show the ' + finding['kind'] + ' finding ' + key + ' and its evidence before making changes. Keep the requested stopping point (' + article['view']['stop_point'] + ').')
    return {'article':article, 'finding':finding, 'evidence':evidence, 'command':command}

def memory_detail(root, ident, revision=None):
    from hub_workspace import active
    adapter = active(root)
    if not adapter:raise ValueError('Select a Hub.')
    saved = adapter.hub.read(ident, revision)
    record = saved['record']
    if record['kind'] not in ('note', 'context', 'rule', 'decision'):raise ValueError('Choose a memory.')
    heads = adapter.hub.graph()['heads'].get(ident, [])
    focused = bool(record['data'].get('collection') or record['data'].get('lesson'))
    reason = ''
    command = 'Use Blog Studio. Inspect team memory ' + ident + '.'
    if record['data'].get('collection'):
        reason = 'Collection settings are read-only here. Manage this collection in chat.'
        command = 'Use Blog Studio. Show collection ' + ident + ' and help me manage its settings.'
    elif record['data'].get('lesson'):
        reason = 'Candidate lessons are read-only here. Review or promote this lesson in chat.'
        command = 'Use Blog Studio. Review candidate lesson ' + ident + ' before changing team guidance.'
    elif record['kind'] == 'decision':
        reason = 'Decisions are read-only here. Inspect the decision and discuss a follow-up in chat.'
    elif heads != [record['revision']]:
        reason = 'This memory has changed or has competing revisions. Compare them in chat before editing.'
    body = Path(saved['paths']['BODY.md']).read_text()
    return {'record': {k: record[k] for k in ('item', 'revision', 'kind', 'title', 'scope')},
            'focused_workflow': focused, 'editable': not bool(reason), 'read_only_reason': reason,
            'continuation': command, 'body': body[:16000], 'truncated': len(body) > 16000}


def import_operation(root, data):
    operation = data.get('operation', '')
    if not isinstance(operation, str) or not re.fullmatch(r'[a-f0-9]{32}', operation):
        raise ValueError('An import operation ID is required.')
    ledger = studio.inside(root, '.desk-imports', operation + '.json')
    fingerprint = sha(encoded(data))
    saved = studio.read_json(ledger) if ledger.exists() else None
    if saved and saved['fingerprint'] != fingerprint:
        raise ValueError('This operation belongs to a different import request.')
    return ledger, fingerprint, saved


IMPORT_SUFFIXES = ('.md', '.txt', '.html', '.htm', '.docx', '.pdf')


def library_preview_state(root, ident):
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('Choose a saved import preview.')
    path = studio.inside(root, '.library', ident + '.json')
    if not path.is_file():
        raise ValueError('This saved preview is no longer available. Preview the source again.')
    manifest = studio.read_json(path)
    # A new collection stays a draft inside its preview until the first import saves it.
    draft = manifest.get('pending_collection')
    config = draft or blog_library.collections(root).get(manifest['collection'])
    if not config:
        raise ValueError('This preview belongs to a collection that is no longer available. Preview it again.')
    results = manifest['results']
    counts = {key: sum(v['status'] == key for v in results.values()) for key in ('imported', 'updated', 'unchanged', 'failed')}
    counts['pending_extraction'] = sum(v.get('extraction') == 'pending' for v in results.values())
    return {'preview': ident, 'collection': config['name'], 'type': config['type'], 'scope': config.get('scope'),
            'saved_collection': not draft,
            'coverage_note': {'archive': 'Links from this page only. Other archive pages have not been followed.',
                              'feed': 'Posts listed in this feed only. Older posts may be missing.',
                              'sitemap': 'URLs in this sitemap only. Nested sitemap indexes are not expanded.',
                              'urls': 'The post links you supplied.',
                              'folder': 'The supported files in the selected folder.',
                              'export': 'The posts in the selected JSON export.'}[config['type']],
            'expected': sha(encoded([manifest, config])), 'candidates': len(manifest['candidates']),
            'completed': len(results), 'remaining': len(manifest['candidates']) - len(results), 'counts': counts,
            'expected_bytes': sum(v.get('expected_bytes', 0) for v in manifest['candidates']),
            'network_bytes': 'unknown until fetched' if config['type'] not in ('folder', 'export') else None,
            'excluded': manifest['excluded'][:20], 'discovery_limited': manifest['discovery_limited'],
            'posts': [{'key': sha(entry['identity'].encode())[:32],
                       'title': entry.get('title') or entry.get('label') or entry.get('url') or Path(entry.get('file', '')).name or 'Untitled post',
                       'url': entry.get('url'), 'author': entry.get('author'),
                       'status': results.get(entry['identity'], {}).get('status', 'pending')} for entry in manifest['candidates']],
            'selected': manifest.get('desk_selected', []),
            'failures': [v['reason'] for v in results.values() if v['status'] == 'failed'][:20]}


def stage_selection(root, operation, kind, data):
    """Copy the files chosen in the browser into this operation's private staging folder."""
    files = data.get('files') if kind == 'folder' else [{'path': 'export.json', 'content': data.get('export')}]
    if not isinstance(files, list) or not 1 <= len(files) <= blog_library.MAX_POSTS:
        raise ValueError('Select 1–500 supported files.')
    allowed = ('.json',) if kind == 'export' else IMPORT_SUFFIXES
    decoded, paths, size = [], set(), 0
    for file in files:
        if not isinstance(file, dict) or set(file) != {'path', 'content'}:
            raise ValueError('Choose files with a relative path and content.')
        name = file['path']
        if (not isinstance(name, str) or len(name) > 500 or '\\' in name or '\x00' in name
                or name.startswith('/') or any(p.startswith('.') or not p for p in name.split('/'))
                or len(name.split('/')) > 12 or name in paths):
            raise ValueError('Selected files need unique relative paths without hidden or parent folders.')
        if Path(name).suffix.lower() not in allowed:
            raise ValueError('Choose Markdown, text, HTML, DOCX or PDF files; exports must be JSON.')
        content = base64.b64decode(file['content'], validate=True)
        size += len(content)
        if not content or size > blog_library.MAX_BINARY:
            raise ValueError('Select nonempty files totaling at most 10 MiB. Use a smaller folder or import a larger local folder in chat.')
        paths.add(name);decoded.append((name, content))
    base = studio.inside(root, '.library', 'desk-inputs', operation)
    if base.is_dir() and not base.is_symlink():
        shutil.rmtree(base)  # A repeated request restages the same selection.
    for name, content in decoded:
        studio.atomic(studio.inside(base, *name.split('/')), content)
    return base if kind == 'folder' else base / 'export.json'


def desk_staged(root, path):
    """True for a copy this desk staged itself; only such a copy may be replaced by a new selection."""
    if not path:
        return False
    staging = studio.inside(root, '.library', 'desk-inputs').resolve()
    resolved = Path(path).resolve()
    return resolved != staging and resolved.is_relative_to(staging)


def discard_staged(root, path, keep):
    """Remove a superseded staged copy. Never touches anything outside the desk's staging folder."""
    if not desk_staged(root, path):
        return
    staging = studio.inside(root, '.library', 'desk-inputs').resolve()
    top = staging / Path(path).resolve().relative_to(staging).parts[0]
    if top != keep.resolve() and top.is_dir() and not top.is_symlink():
        shutil.rmtree(top)


def name_owner(root, name):
    """(key, free) for a collection name.

    A name is free when no collection uses it, or when the collection that uses it was set
    up in this workspace and has no saved posts; that empty collection's key is then reused
    instead of adding a duplicate. A teammate's shared collection keeps its name even while
    it looks empty here: this workspace may simply not have refreshed their posts yet.
    """
    wanted = str(name).strip().casefold()
    matches = [c for c in blog_library.collections(root).values() if str(c['name']).strip().casefold() == wanted]
    if not matches:
        return None, True
    mine = blog_library.local_config(root)['collections']
    empty_here = all(c['key'] in mine and not blog_library.imported_count(root, c['key']) for c in matches)
    return matches[0]['key'], empty_here


def refresh_selection(root, operation, collection, data):
    """Give a folder/export collection chosen in the desk a new selection under the same collection."""
    config = blog_library.collections(root)[collection]
    kind = config['type']
    if kind not in ('folder', 'export') or ('files' in data) != (kind == 'folder'):
        raise ValueError('Choose a folder for a folder collection, or a JSON file for an export collection.')
    previous = config.get('local_path')
    if previous and not desk_staged(root, previous):
        raise ValueError('This collection reads a folder on this computer directly. Refresh it without choosing files.')
    staged = stage_selection(root, operation, kind, data)
    blog_library.locate(root, collection, str(staged))
    return previous


def collection_rows(root):
    rows = []
    for config in blog_library.collections(root).values():
        local = config.get('local_path')
        row = {k: v for k, v in config.items() if k != 'local_path'}
        # A desk-staged or not-yet-located folder/export can be refreshed with a new selection.
        row['refresh_files'] = config['type'] in ('folder', 'export') and (not local or desk_staged(root, local))
        rows.append(row)
    return {'items': rows}


def library_preview(root, data):
    """Explicit source selection; stage only browser-selected files, then reuse CLI discovery.

    A new collection is validated and discovered first. It is saved and shared only when
    its first posts are imported, so a failed or abandoned preview leaves no collection.
    """
    if set(data) - {'operation', 'collection', 'name', 'type', 'files', 'export', 'url', 'scope', 'discovery_scope'}:
        raise ValueError('Unknown import preview field.')
    ledger, fingerprint, saved = import_operation(root, data)
    if saved and saved.get('preview'):return library_preview_state(root, saved['preview'])
    operation = data['operation']
    staging = studio.inside(root, '.library', 'desk-inputs', operation)
    collection, draft, superseded = data.get('collection'), None, None
    try:
        if collection:
            if set(data) - {'operation', 'collection', 'files', 'export'}:raise ValueError('Choose an existing collection or a new source.')
            if collection not in blog_library.collections(root):raise ValueError('Choose a configured collection.')
            if 'files' in data or 'export' in data:
                superseded = refresh_selection(root, operation, collection, data)
        else:
            kind = data.get('type')
            if kind not in ('folder', 'export', 'archive', 'feed', 'sitemap', 'urls'):
                raise ValueError('Choose a folder, website, feed, sitemap, links, or JSON export.')
            owner, free = name_owner(root, data.get('name'))
            if not free:
                raise ValueError('A collection already has that name. Choose Refresh an existing collection or use a different name.')
            collection = owner or 'desk-' + operation
            config = {'key': collection, 'name': data.get('name'), 'type': kind}
            if kind in ('folder', 'export'):
                config['path'] = str(stage_selection(root, operation, kind, data))
            else:
                config.update(url=data.get('url'), scope=data.get('scope'), discovery_scope=data.get('discovery_scope'))
                if kind == 'urls':
                    config['urls'] = [u.strip() for u in str(data.get('url') or '').splitlines() if u.strip()]
            draft = blog_library.normalize(root, config)
        studio.write_json(ledger, {'fingerprint': fingerprint, 'collection': collection})
        result = blog_library.preview(root, collection, reader=blog_library.fetch, config=draft)
    except Exception:
        # No collection was saved. Drop this operation's staged copy unless a saved collection now reads it.
        if not data.get('collection') and staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    studio.write_json(ledger, {'fingerprint': fingerprint, 'collection': collection, 'preview': result['preview']})
    studio.write_json(studio.inside(root, '.desk-imports', 'current.json'), {'preview': result['preview']})
    if superseded:
        discard_staged(root, superseded, keep=staging)
    return library_preview_state(root, result['preview'])


def library_import(root, data):
    required = {'operation', 'preview', 'expected', 'confirm', 'retry', 'selected'}
    if (set(data) - {'analyze'} != required or data['confirm'] is not True or not isinstance(data['retry'], bool)
            or not isinstance(data.get('analyze', True), bool)):
        raise ValueError('Review the preview, then explicitly choose Import or Retry failed posts.')
    ledger, fingerprint, saved = import_operation(root, data)
    if saved and saved.get('result'):return saved['result']
    current = library_preview_state(root, data['preview'])
    if current['expected'] != data['expected']:
        raise ValueError('This preview changed. Reload the saved preview before continuing; retained posts are safe.')
    chosen = data['selected']
    known = {post['key']: post['status'] for post in current['posts']}
    if (not isinstance(chosen, list) or not chosen or len(chosen) > blog_library.MAX_POSTS
            or any(not isinstance(key, str) or key not in known for key in chosen) or len(set(chosen)) != len(chosen)):
        raise ValueError('Check the posts you want to import from this preview.')
    eligible = 'failed' if data['retry'] else 'pending'
    if not any(known[key] == eligible for key in chosen):
        raise ValueError('Select failed posts to retry.' if data['retry'] else 'Select posts that have not been imported yet.')
    path = studio.inside(root, '.library', data['preview'] + '.json')
    manifest = studio.read_json(path)
    manifest['desk_selected'] = chosen
    studio.write_json(ledger, {'fingerprint': fingerprint, 'state': 'started'})
    studio.write_json(path, manifest)
    identities = [entry['identity'] for entry in manifest['candidates'] if sha(entry['identity'].encode())[:32] in chosen]
    # analyze=False is the author's unchecked "Summarize and tag" for this batch.
    result = blog_library.import_batch(root, data['preview'], limit=25, retry=data['retry'], reader=blog_library.fetch,
                                       selected=identities, analyze=data.get('analyze', True))
    state = library_preview_state(root, data['preview'])
    sync = result.get('hub_sync', {'status': 'local-only'})
    state['sharing'] = sync.get('status', 'local-saved-not-shared')
    state['sharing_message'] = SHARING_MESSAGES.get(state['sharing'], 'Saved locally; Hub sync needs attention. Retry Hub sync in chat.')
    studio.write_json(ledger, {'fingerprint': fingerprint, 'state': 'saved', 'result': state})
    return state


def curation_changes(record, values):
    """The posted curation fields whose value differs from the inspected reference."""
    library = record.get('library') or {}
    current = {'curation': library.get('curation', 'active'), 'topics': library.get('topics', []),
               'products': library.get('products', []), 'note': record.get('note') or ''}
    return {key: value for key, value in values.items() if key not in current or value != current[key]}


def dispatch(root, route, data):
    if route == 'refresh':
        if data:raise ValueError('Refresh takes no fields.')
        from hub_workspace import active
        adapter = active(root)
        if not adapter:raise ValueError('Select a Team Hub to refresh shared work.')
        result = adapter.hub.refresh()  # Existing read, identity, privacy and immutable-history checks.
        if not result.get('fresh'):
            raise TransportError('Hub refresh could not verify current shared work. Check connectivity and GitHub access; saved content is preserved.')
        return result
    with studio.locked(root):
        adapter = authorize_write(root)
        if route == 'library-preview':return library_preview(root, data)
        if route == 'library-import':return library_import(root, data)
        if route == 'retry-sync':return retry_receipt(root, adapter, data)
        if route == 'upload':return upload(root, data)
        if route == 'schedule':
            if not data.get('expected'):raise ValueError('Reload this blog before changing its editorial decision.')
            ident = data.get('id');values = {k: v for k, v in data.items() if k != 'id'}
            directory, _ = studio.item(root, 'articles', ident)
            before = (directory / 'session.json').read_bytes()
            record = editorial.schedule(root, ident, values, desk=True)
            if (directory / 'session.json').read_bytes() == before:
                return dict(UNCHANGED, id=ident)
            result = share(root, 'article', record)
            return {**result, 'receipts': [receipt(root, 'Editorial decision', result, 'article')]}
        if route == 'resume':
            if set(data) != {'item'} or not adapter:raise ValueError('Choose a shared blog.')
            graph = adapter.hub.graph();heads = graph['heads'].get(data['item'], [])
            if len(heads) != 1 or graph['revisions'][heads[0]]['kind'] != 'article':raise ValueError('Resolve competing revisions before resuming.')
            ident = adapter._checkout(data['item']);studio.write_json(studio.inside(root, '.active-article.json'), {'id': ident})
            return {'id': ident, 'status': 'resumed'}
        if route in ('curate','analyze'):
            allowed = {'id','location','expected'} if route=='analyze' else {'id', 'location', 'expected', 'confirmed', 'curation', 'topics', 'products', 'note'}
            if set(data) - allowed:
                raise ValueError('Unknown curation field.')
            if not isinstance(data.get('expected'), str) or not re.fullmatch(r'[a-f0-9]{64}', data['expected']):
                raise CurationConflict('Reload this reference before saving curation.')
            if adapter:
                adapter = authorize_write(root)  # Resolve current selection under the workspace lock.
                if not adapter or not adapter.hub.refresh().get('fresh'):
                    raise HubError('Current Hub state could not be verified. Your proposed curation is retained; check access before retrying.')
            current = source_detail(root, data['id'], data.get('location', 'local'))
            if current['expected'] != data['expected']:
                raise CurationConflict('This reference changed. Reload and compare before explicitly resubmitting your proposed curation.')
            values = {k: v for k, v in data.items() if k not in ('id', 'confirmed', 'location', 'expected')}
            if route == 'curate':
                values = curation_changes(current['record'], values)
                if not values:
                    return dict(UNCHANGED, id=current['id'])  # Before any checkout, revision or share.
            if values.get('curation') == 'retired' and data.get('confirmed') is not True:raise ValueError('Confirm retirement; earlier snapshots remain in Git history.')
            ident = current['id']
            if current['location'] == 'hub':
                if not adapter:raise ValueError('Select a Hub.')
                # Existing unshared local edits must be reconciled in chat, not
                # overwritten by a form displaying the shared version.
                for key, saved in adapter.state['items'].items():
                    if key.startswith('sources/') and saved['item'] == ident:
                        payload = adapter._payload('sources', key.split('/', 1)[1], read_only=True)[0]
                        if sha(encoded(payload)) != saved['fingerprint']:
                            raise CurationConflict('This reference has unshared local edits. Compare them in chat before changing the shared reference.')
                ident = adapter._checkout(ident)
            if route=='analyze':return source_curator.retry(root, [ident])
            result = share(root, 'source', blog_library.curate(root, ident, values))
            return {**result, 'receipts': [receipt(root, 'Reference curation', result, 'source')]}
        if route == 'memory':
            if not adapter:raise ValueError('Select a Team Hub to save shared memory.')
            if set(data) - {'kind', 'title', 'body', 'item', 'revision', 'scope', 'scope_key', 'operation'}:raise ValueError('Unknown memory field.')
            values = {'kind': data.get('kind'), 'title': data.get('title'), 'body': data.get('body'),
                      'scope': data.get('scope', 'team'), 'scope_key': data.get('scope_key', '')}
            if data.get('item'):
                graph = adapter.hub.graph();heads = graph['heads'].get(data['item'])
                if heads != [data.get('revision')]:raise ValueError('This memory changed. Reload before editing.')
                previous = graph['revisions'][heads[0]]
                if previous['kind'] not in ('note', 'context', 'rule'):
                    raise ValueError('This memory kind is read-only here. Inspect it in chat; it cannot be converted into a note.')
                if previous['data'].get('collection') or previous['data'].get('lesson'):
                    raise ValueError('Use the focused collection or lesson workflow to change this record.')
                saved = adapter.hub.read(data['item'], data['revision'])
                current = {'kind': previous['kind'], 'title': previous['title'], 'body': Path(saved['paths']['BODY.md']).read_text(),
                           'scope': previous['scope']['level'], 'scope_key': previous['scope']['key']}
                values = {**current, **{key: data[key] for key in current if key in data}}
                if values == current:
                    return dict(UNCHANGED, item=data['item'], revision=data['revision'])
            if values['kind'] not in ('note', 'context', 'rule'):raise ValueError('Choose note, context, or rule.')
            # A body the form did not send is the saved one, which may be longer than the form shows.
            if not isinstance(values['body'], str) or not values['body'] or ('body' in data and len(values['body']) > 16000):
                raise ValueError('Provide a memory under 16000 characters.')
            if not isinstance(values['title'], str) or not 1 <= len(values['title']) <= 200:raise ValueError('Provide a short memory title.')
            if values['scope'] not in ('team', 'project', 'author', 'article'):raise ValueError('Choose a memory scope.')
            result = adapter.hub.save(values['kind'], values['title'], values['body'], item=data.get('item'),
                parents=[data['revision']] if data.get('item') else None, operation=data.get('operation'),
                scope={'level': values['scope'], 'key': values['scope_key']}, sync=True)
            return {**result, 'receipts': [receipt(root, 'Shared memory', result)]}
    raise ValueError('Unknown management action.')


class Busy(Exception):
    """Another desk request still holds the workspace."""


PROTOCOL_ERRORS = {
    405: 'The editorial desk answers GET and POST requests only.',
    408: 'The request took too long to arrive.',
    414: 'The request address is too long.',
    431: 'The request headers are too large.',
    501: 'The editorial desk answers GET and POST requests only.',
}


def note_unexpected(exc):
    """One stderr line with the exception type and code location; never its message or any content."""
    frames = traceback.extract_tb(exc.__traceback__)
    where = (Path(frames[-1].filename).name + ':' + str(frames[-1].lineno)) if frames else 'unknown location'
    print('Blog Studio desk: unexpected ' + type(exc).__name__ + ' at ' + where, file=sys.stderr, flush=True)


def failure(exc, writing=False):
    """(HTTP status, JSON body) for any exception. Authored messages pass through; internals never do."""
    if isinstance(exc, CurationConflict):
        # A refused save is a conflict; a read of a reference that went away is an ordinary 400, as before.
        return (409 if writing else 400), {'error': str(exc)[:500], 'code': 'source-conflict'}
    if isinstance(exc, Busy):
        return 503, {'error': 'Another desk operation is still running. This request changed nothing; try again when it finishes.', 'code': 'busy'}
    if isinstance(exc, json.JSONDecodeError):
        return 400, {'error': 'A saved Blog Studio file is damaged and could not be read. Ask Blog Studio in chat to inspect this workspace.'}
    if isinstance(exc, UnicodeError):
        return 400, {'error': 'This text is not UTF-8. Save the file as UTF-8 text, then retry.'}
    if isinstance(exc, (KeyError, TypeError)):
        return 400, {'error': 'This request was missing expected information. Reload the desk and try again, or continue in chat.'}
    if isinstance(exc, (ValueError, HubError)):
        return 400, {'error': str(exc)[:500]}
    if isinstance(exc, OSError):
        after = 'Inspect retained work before retrying.' if writing else 'Saved work is preserved.'
        return 503, {'error': 'Workspace access failed. ' + after}
    return 500, {'error': 'The desk helper hit an unexpected problem. Reload the desk; saved work is kept, and you can continue in chat.',
                 'code': 'unexpected'}


def whole(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError('Use whole numbers for limit and offset.') from None


def view(root, name, query):
    """Read-only desk views by name. Returns None for an unknown view."""
    arg = lambda key, default=None: query.get(key, [default])[0]
    limit, offset = whole(arg('limit', 20)), whole(arg('offset', 0))
    if name == 'board':
        return editorial.board(root, arg('query', ''), arg('stage'), arg('owner'), limit, offset)
    if name == 'inbox':
        return editorial.inbox(root, arg('id'), limit, offset, query=arg('query', ''))
    if name == 'library':
        return blog_library.catalog(root, arg('query', ''), arg('collection'), arg('author'), arg('topic'), arg('product'),
                                    arg('since'), arg('until'), limit, offset, arg('retired') == 'true')
    if name == 'memory':
        return memories(root, limit, offset, arg('query', ''))
    if name == 'receipts':
        return receipts(root)
    if name == 'capabilities':
        return capabilities(root)
    if name == 'collections':
        return collection_rows(root)
    if name == 'library-preview':
        current = studio.inside(root, '.desk-imports', 'current.json')
        ident = arg('preview') or (studio.read_json(current)['preview'] if current.exists() else None)
        return library_preview_state(root, ident) if ident else {'available': False}
    if name == 'source':
        return source_detail(root, arg('id'), arg('location', 'local'))
    if name == 'article':
        return detail(root, arg('id'), arg('location', 'local'), arg('revision'))
    if name == 'finding':
        return finding_detail(root, arg('id'), arg('key'), arg('location', 'local'))
    if name == 'memory-detail':
        return memory_detail(root, arg('id'), arg('revision'))
    return None


def server(root, port=0, bind=True):
    """The local desk server and its session URL.

    Connections are handled on daemon threads, so a silent or slow connection never holds
    up another one. Workspace access stays serialized: one process-level lock covers every
    API handler. bind=False builds the same server without opening a port (for checks that
    drive the handler directly).
    """
    token = secrets.token_urlsafe(32)
    api_lock = threading.Lock()

    @contextmanager
    def serialized():
        if not api_lock.acquire(timeout=API_WAIT):
            raise Busy()
        try:
            yield
        finally:
            api_lock.release()

    class Handler(BaseHTTPRequestHandler):
        timeout = HEADER_TIMEOUT  # Applied to each new connection until its headers are read.
        server_version = 'BlogStudio'
        sys_version = ''
        responded = False

        def version_string(self):
            return 'Blog Studio desk'  # No Python or http.server version.

        def log_message(self, *args):pass  # Do not log content, document links, or session tokens.

        def reply(self, status, value, media='application/json', allow=None):
            body = encoded(value) if media == 'application/json' else value
            self.responded = True
            self.send_response(status)
            self.send_header('Content-Type', media)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            if allow:
                self.send_header('Allow', allow)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def fail(self, exc, writing=False):
            """Every failure ends in one JSON reply; the connection is never simply dropped."""
            status, body = failure(exc, writing)
            if status == 500:
                note_unexpected(exc)
            if self.responded:
                return  # A reply was already started; a second one would corrupt it.
            try:
                self.reply(status, body)
            except OSError:
                pass  # The browser went away.

        def send_error(self, code, message=None, explain=None):
            """Malformed or unsupported requests get the same JSON reply and headers as the rest."""
            self.close_connection = True
            try:
                self.reply(code, {'error': PROTOCOL_ERRORS.get(code, 'This request could not be handled.')})
            except OSError:
                pass

        def check(self, api=False):
            expected = '127.0.0.1:' + str(self.server.server_port)
            if self.headers.get('Host') != expected:raise ValueError('Invalid local host.')
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + expected:raise ValueError('Cross-origin access is unavailable.')
            site = (self.headers.get('Sec-Fetch-Site') or '').lower()
            if site and site not in ('same-origin', 'none') and not self.opening_page():
                raise ValueError('Cross-site access is unavailable.')
            if api and not secrets.compare_digest(self.headers.get('X-Blog-Studio-Token', ''), token):raise ValueError('Open the current editorial desk link to reconnect.')

        def opening_page(self):
            """A person following the desk link from another page: a top-level visit to the page shell.

            The shell holds no workspace data and cannot be framed, so this one cross-site
            request stays allowed; scripts, styles and every API call from another site do not.
            """
            return (self.command == 'GET' and urlsplit(self.path).path == '/'
                    and self.headers.get('Sec-Fetch-Mode') == 'navigate' and self.headers.get('Sec-Fetch-Dest') == 'document')

        def do_GET(self):
            try:
                self.check(self.path.startswith('/api/'))
                self.connection.settimeout(BODY_TIMEOUT)
                parsed = urlsplit(self.path)
                if parsed.path in STATIC:
                    name, media = STATIC[parsed.path]
                    return self.reply(200, (ASSETS / name).read_bytes(), media)
                result = None
                if parsed.path.startswith('/api/'):
                    with serialized():
                        result = view(root, parsed.path[5:], parse_qs(parsed.query))
                if result is None:
                    return self.reply(404, {'error': 'Unknown view.'})
                self.reply(200, result)
            except Exception as exc:
                self.fail(exc)

        def do_POST(self):
            try:
                self.check(True)
                if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type') != 'application/json':raise ValueError('Use a bounded JSON request.')
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    raise ValueError('Use a bounded JSON request.') from None
                if not 0 < size <= MAX_BODY:raise ValueError('Request exceeds the management limit.')
                if not self.path.startswith('/api/'):raise ValueError('Unknown management action.')
                self.connection.settimeout(BODY_TIMEOUT)
                try:
                    content = self.rfile.read(size)
                except OSError:
                    raise ValueError('Incomplete request.') from None
                if len(content) != size:raise ValueError('Incomplete request.')
                try:
                    data = json.loads(content)
                except ValueError:
                    raise ValueError('Supply a JSON object.') from None
                if not isinstance(data, dict):raise ValueError('Supply a JSON object.')
                with serialized():
                    result = dispatch(root, self.path[5:], data)
                self.reply(200, result)
            except Exception as exc:
                self.fail(exc, writing=True)

        def unsupported(self):
            self.reply(405, {'error': PROTOCOL_ERRORS[405]}, allow='GET, POST')

        do_HEAD = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = unsupported

    class LocalServer(ThreadingHTTPServer):
        daemon_threads = True  # A stuck connection never keeps the helper alive.
        request_queue_size = 32

        def handle_error(self, request, client_address):
            note_unexpected(sys.exc_info()[1])  # Never a traceback with content.

    httpd = LocalServer(('127.0.0.1', port), Handler, bind_and_activate=bind)
    if not bind:
        httpd.server_port = port
    return httpd, 'http://127.0.0.1:' + str(httpd.server_port) + '/#' + token


def launch_note(root, harness):
    """What this launch did about reference analysis, for the launch output and the author."""
    analysis = source_curator.disclosure(root)
    if harness:
        note = 'Saved ' + analysis['label'] + ' as this workspace’s analysis CLI because --harness was passed. ' + analysis['message']
    elif analysis['harness']:
        note = 'No --harness was passed, so the analysis CLI saved earlier for this workspace was left as it is. ' + analysis['message']
    else:
        note = ('No --harness was passed and none is saved, so opening the desk did not turn on reference analysis. '
                'Pass --harness codex or --harness claude only when the author wants summaries and tags from that CLI.')
    return {'harness': analysis['harness'], 'saved_by_this_launch': bool(harness), 'note': note}


def main(root, port=0, open_browser=False, harness=None):
    studio.initialize(root)
    # Only an explicit --harness changes the saved analysis choice; opening the desk alone never does.
    if harness:source_curator.configure(root, harness)
    analysis = launch_note(root, harness)
    httpd, url = server(root, port)
    print(json.dumps({'url': url, 'access': 'local session only', 'stop': 'Press Ctrl+C to close the desk.',
                      'analysis': analysis}), flush=True)
    if open_browser:webbrowser.open(url)
    try:httpd.serve_forever()
    except KeyboardInterrupt:pass
    finally:httpd.server_close()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--harness', choices=('codex', 'claude'), help='Save this CLI for reference analysis (explicit opt-in).')
    args = parser.parse_args();root = Path(args.root).expanduser()
    if not root.is_absolute():parser.error('Use an absolute workspace path.')
    raise SystemExit(main(root.resolve(), args.port, args.open, args.harness))
