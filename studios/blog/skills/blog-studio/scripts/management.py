"""A private local editorial desk. Standard library, loopback only, no hosted service."""
import argparse
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs
import uuid
import webbrowser

import studio
import editorial
import blog_library
from hub_store import HubError, encoded, sha

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'management'
MAX_BODY = 15 * 1024 * 1024


def authorize_write(root):
    """One contributor level; validate existing GitHub write access, not a new role DB."""
    from hub_workspace import active
    adapter = active(root)
    if adapter:
        metadata = adapter.hub.registry.provider.lookup(adapter.hub.config['repository'])
        if not metadata or metadata.get('private') is not True or metadata.get('write') is not True or metadata.get('id') != adapter.hub.config['provider_id']:
            raise ValueError('Hub write access could not be verified. Check GitHub access before editing shared work.')
    return adapter


def share(root, group, record):
    from hub_workspace import active
    adapter = active(root)
    if adapter:
        try:record['hub_sync'] = adapter.publish_mutation(group, record)
        except (HubError, OSError):record['hub_sync'] = {'status': 'local-saved-not-shared', 'next_step': 'Local work is saved. Retry Hub sync.'}
    return record


SHARING_MESSAGES = {
    'shared': 'Shared with the Team Hub.',
    'synchronized': 'Shared with the Team Hub.',
    'pending-review': 'Saved; waiting for contribution review.',
    'conflicting': 'Saved; competing Hub revisions need resolution in chat.',
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
    retry = bool(value['hub'] and status not in ('shared', 'synchronized', 'conflicting', 'local-only'))
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
    if set(data) != {'id'} or not __import__('re').fullmatch(r'[a-f0-9]{64}', data.get('id', '')):
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
    if set(data) - {'operation', 'filename', 'content', 'title', 'purpose', 'as_blog', 'author'}:raise ValueError('Unknown upload field.')
    operation = data.get('operation', '')
    if not __import__('re').fullmatch(r'[a-f0-9]{32}', operation):raise ValueError('An upload operation ID is required.')
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
    with tempfile.TemporaryDirectory(dir=staging) as temp:
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
                'lesson_status': blog_library.lesson_state(adapter, record) if record['data'].get('lesson') else None})
    rows = [r for r in rows if all(term in (r['title'] + ' ' + r['summary'] + ' ' + r['kind'] + ' ' + r['scope']['key']).casefold() for term in query.casefold().split())]
    return __import__('experience').page(rows, limit, offset)


def source_detail(root, ident, location='local'):
    selected = next((r for r in blog_library.source_rows(root) if r['id'] == ident and r['location'] == location), None)
    if not selected:raise ValueError('Choose a catalog source.')
    record = selected['record']
    text = selected.get('body', b'').decode() if location == 'hub' else selected['path'].read_text() if selected['path'].is_file() else ''
    return {'record': record, 'excerpt': text[:8000], 'truncated': len(text) > 8000, 'location': location,
            'limitation': 'Pending extraction; no source text was read.' if record['status'] != 'ready' else 'Selected saved source; historical facts need current verification.'}


def detail(root, ident, location='local'):

    if location == 'hub':
        from hub_workspace import active
        adapter = active(root)
        if not adapter:raise ValueError('Select a Hub.')
        saved = adapter.hub.read(ident)
        record = saved['record']
        if record['kind'] != 'article':raise ValueError('Choose a shared blog.')
        return {'record': record['data'].get('studio', {}), 'title': record['title'], 'location': 'hub',
                'next_step': 'Choose Resume to check out this saved revision; existing local work is protected.'}
    directory, record = studio.item(root, 'articles', ident)
    return {'record': record, 'title': record['title'], 'expected': sha((directory / 'session.json').read_bytes()),
            'assets': editorial.derived_status(root, directory, record), 'location': 'local'}


def dispatch(root, route, data):
    adapter = authorize_write(root)
    if route == 'refresh':
        if not adapter:raise ValueError('Select a Team Hub to refresh shared work.')
        return adapter.hub.refresh()
    with studio.locked(root):
        if route == 'retry-sync':return retry_receipt(root, adapter, data)
        if route == 'upload':return upload(root, data)
        if route == 'schedule':
            if not data.get('expected'):raise ValueError('Reload this blog before changing its editorial decision.')
            ident = data.get('id');values = {k: v for k, v in data.items() if k != 'id'}
            result = share(root, 'article', editorial.schedule(root, ident, values))
            return {**result, 'receipts': [receipt(root, 'Editorial decision', result, 'article')]}
        if route == 'resume':
            if set(data) != {'item'} or not adapter:raise ValueError('Choose a shared blog.')
            graph = adapter.hub.graph();heads = graph['heads'].get(data['item'], [])
            if len(heads) != 1 or graph['revisions'][heads[0]]['kind'] != 'article':raise ValueError('Resolve competing revisions before resuming.')
            ident = adapter._checkout(data['item']);studio.write_json(studio.inside(root, '.active-article.json'), {'id': ident})
            return {'id': ident, 'status': 'resumed'}
        if route == 'curate':
            values = {k: v for k, v in data.items() if k not in ('id', 'confirmed', 'location')}
            if values.get('curation') == 'retired' and data.get('confirmed') is not True:raise ValueError('Confirm retirement; earlier snapshots remain in Git history.')
            ident = data['id']
            if data.get('location') == 'hub':
                if not adapter:raise ValueError('Select a Hub.')
                ident = adapter._checkout(ident)
            result = share(root, 'source', blog_library.curate(root, ident, values))
            return {**result, 'receipts': [receipt(root, 'Reference curation', result, 'source')]}
        if route == 'memory':
            if not adapter:raise ValueError('Select a Team Hub to save shared memory.')
            if set(data) - {'kind', 'title', 'body', 'item', 'revision', 'scope', 'scope_key', 'operation'}:raise ValueError('Unknown memory field.')
            if data.get('kind') not in ('note', 'context', 'rule'):raise ValueError('Choose note, context, or rule.')
            if not isinstance(data.get('body'), str) or not 1 <= len(data['body']) <= 16000:raise ValueError('Provide a memory under 16000 characters.')
            if not isinstance(data.get('title'), str) or not 1 <= len(data['title']) <= 200:raise ValueError('Provide a short memory title.')
            if data.get('item'):
                graph = adapter.hub.graph();heads = graph['heads'].get(data['item'])
                if heads != [data.get('revision')]:raise ValueError('This memory changed. Reload before editing.')
                if graph['revisions'][heads[0]]['data'].get('collection') or graph['revisions'][heads[0]]['data'].get('lesson'):
                    raise ValueError('Use the focused collection or lesson workflow to change this record.')
            scope = data.get('scope', 'team')
            if scope not in ('team', 'project', 'author', 'article'):raise ValueError('Choose a memory scope.')
            result = adapter.hub.save(data['kind'], data['title'], data['body'], item=data.get('item'),
                parents=[data['revision']] if data.get('item') else None, operation=data.get('operation'),
                scope={'level': scope, 'key': data.get('scope_key', '')}, sync=True)
            return {**result, 'receipts': [receipt(root, 'Shared memory', result)]}
    raise ValueError('Unknown management action.')


def server(root, port=0):
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):pass  # Do not log content, document links, or session tokens.
        def reply(self, status, value, media='application/json'):
            body = encoded(value) if media == 'application/json' else value
            self.send_response(status);self.send_header('Content-Type', media);self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store');self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers();self.wfile.write(body)
        def check(self, api=False):
            expected = '127.0.0.1:' + str(self.server.server_port)
            if self.headers.get('Host') != expected:raise ValueError('Invalid local host.')
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + expected:raise ValueError('Cross-origin access is unavailable.')
            if api and not secrets.compare_digest(self.headers.get('X-Blog-Studio-Token', ''), token):raise ValueError('Open the current editorial desk link to reconnect.')
        def do_GET(self):
            try:
                self.check(self.path.startswith('/api/'))
                parsed = urlsplit(self.path);query = parse_qs(parsed.query)
                arg = lambda key, default=None:query.get(key, [default])[0]
                limit, offset = int(arg('limit', 20)), int(arg('offset', 0))
                if parsed.path == '/api/board':result = editorial.board(root, arg('query', ''), arg('stage'), arg('owner'), limit, offset)
                elif parsed.path == '/api/inbox':result = editorial.inbox(root, arg('id'), limit, offset)
                elif parsed.path == '/api/library':result = blog_library.catalog(root, arg('query', ''), arg('collection'), arg('author'), arg('topic'), arg('product'), arg('since'), arg('until'), limit, offset, arg('retired') == 'true')
                elif parsed.path == '/api/memory':result = memories(root, limit, offset, arg('query', ''))
                elif parsed.path == '/api/receipts':result = receipts(root)
                elif parsed.path == '/api/collections':result = {'items': [{k: v for k, v in c.items() if k != 'local_path'} for c in blog_library.collections(root).values()]}
                elif parsed.path == '/api/source':result = source_detail(root, arg('id'), arg('location', 'local'))
                elif parsed.path == '/api/article':result = detail(root, arg('id'), arg('location', 'local'))
                elif parsed.path == '/api/memory-detail':
                    from hub_workspace import active
                    adapter = active(root)
                    if not adapter:raise ValueError('Select a Hub.')
                    saved = adapter.hub.read(arg('id'));record = saved['record']
                    if record['kind'] not in ('note', 'context', 'rule', 'decision'):raise ValueError('Choose a memory.')
                    result = {'record': {k: record[k] for k in ('item', 'revision', 'kind', 'title', 'scope')}, 'focused_workflow': bool(record['data'].get('collection') or record['data'].get('lesson')), 'body': Path(saved['paths']['BODY.md']).read_text()[:16000]}
                elif parsed.path in ('/', '/app.js', '/style.css'):
                    file = ASSETS / {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[parsed.path]
                    return self.reply(200, file.read_bytes(), {'/': 'text/html; charset=utf-8', '/app.js': 'text/javascript; charset=utf-8', '/style.css': 'text/css; charset=utf-8'}[parsed.path])
                else:return self.reply(404, {'error': 'Unknown view.'})
                self.reply(200, result)
            except (ValueError, TypeError, KeyError, HubError) as exc:self.reply(400, {'error': str(exc)[:500]})
            except OSError:self.reply(503, {'error': 'Workspace access failed. Saved work is preserved.'})
        def do_POST(self):
            try:
                self.check(True)
                if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type') != 'application/json':raise ValueError('Use a bounded JSON request.')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_BODY:raise ValueError('Request exceeds the management limit.')
                if not self.path.startswith('/api/'):raise ValueError('Unknown management action.')
                self.connection.settimeout(15)
                content = self.rfile.read(size)
                if len(content) != size:raise ValueError('Incomplete request.')
                data = json.loads(content)
                if not isinstance(data, dict):raise ValueError('Supply a JSON object.')
                self.reply(200, dispatch(root, self.path[5:], data))
            except (ValueError, TypeError, KeyError, HubError) as exc:self.reply(400, {'error': str(exc)[:500]})
            except OSError:self.reply(503, {'error': 'Workspace access failed. Inspect retained work before retrying.'})
    class LocalServer(HTTPServer):
        def get_request(self):
            connection, address = super().get_request();connection.settimeout(15);return connection, address
    httpd = LocalServer(('127.0.0.1', port), Handler)
    return httpd, 'http://127.0.0.1:' + str(httpd.server_port) + '/#' + token


def main(root, port=0, open_browser=False):
    studio.initialize(root)
    httpd, url = server(root, port)
    print(json.dumps({'url': url, 'access': 'local session only', 'stop': 'Press Ctrl+C to close the desk.'}), flush=True)
    if open_browser:webbrowser.open(url)
    try:httpd.serve_forever()
    except KeyboardInterrupt:pass
    finally:httpd.server_close()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--root', required=True);parser.add_argument('--port', type=int, default=0);parser.add_argument('--open', action='store_true')
    args = parser.parse_args();root = Path(args.root).expanduser()
    if not root.is_absolute():parser.error('Use an absolute workspace path.')
    raise SystemExit(main(root.resolve(), args.port, args.open))
