"""Historical team reference collections: explicit preview, bounded import, local catalog."""
import argparse
from contextlib import closing
from datetime import datetime
import http.client
from html.parser import HTMLParser
import io
import ipaddress
import json
import os
from pathlib import Path
import socket
import sqlite3
import ssl
import time
from types import SimpleNamespace
from urllib.parse import urlsplit, urljoin, urlunsplit
import uuid
import xml.etree.ElementTree as ET
import zipfile

import studio
from experience import page
from hub_store import HubError, MAX_TEXT, MAX_BINARY, encoded, sha, record_path

MAX_POSTS = 500
MAX_BATCH = 25
MAX_DISCOVERY = 1000
MAX_FETCH = 2 * 1024 * 1024
MAX_IMPORT_BYTES = 25 * 1024 * 1024


def canonical(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Use an HTTPS URL without credentials or a custom port.')
    if any(key in parsed.query.lower() for key in ('access_token', 'api_key', 'password', 'authorization')):
        raise ValueError('Do not put credentials in collection URLs.')
    return urlunsplit(('https', parsed.hostname.lower(), parsed.path or '/', parsed.query, ''))


def in_scope(url, scope):
    url = urlsplit(canonical(url));base = urlsplit(canonical(scope))
    prefix = base.path.rstrip('/')
    return url.hostname == base.hostname and (not prefix or url.path == prefix or url.path.startswith(prefix + '/'))


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=15, context=ssl.create_default_context());self.address = address
    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close();raise


def fetch(url, scope, redirects=3):
    """Reject private addresses and pin the actual socket, including every redirect."""
    if not in_scope(url, scope): raise ValueError('URL is outside the approved collection scope.')
    parsed = urlsplit(canonical(url))
    addresses = list(dict.fromkeys(v[4][0] for v in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('Collection URLs must resolve only to public addresses.')
    connection = PinnedHTTPS(parsed.hostname, addresses[0])
    try:
        connection.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers={'User-Agent': 'BlogStudio/1.12 (explicit team collection import)', 'Accept': 'text/html,application/xml,text/plain'})
        response = connection.getresponse()
        if response.status in (301, 302, 303, 307, 308):
            if redirects <= 0: raise ValueError('Too many collection redirects.')
            destination = canonical(urljoin(url, response.getheader('Location', '')))
            connection.close()
            return fetch(destination, scope, redirects - 1)
        if response.status != 200: raise ValueError('Source returned HTTP ' + str(response.status) + '; historical snapshots were retained.')
        length = response.getheader('Content-Length')
        if length and int(length) > MAX_FETCH: raise ValueError('Source exceeds the bounded fetch limit.')
        content = response.read(MAX_FETCH + 1)
        if len(content) > MAX_FETCH: raise ValueError('Source exceeds the bounded fetch limit.')
        return content, canonical(url), response.getheader('Content-Type', '')
    finally:connection.close()


def folder(root):
    directory = studio.inside(root, '.library');directory.mkdir(mode=0o700, exist_ok=True);directory.chmod(0o700)
    return directory


def local_config(root):
    path = studio.inside(root, '.library', 'collections.json')
    return studio.read_json(path) if path.exists() else {'schema': 1, 'collections': {}}


def collections(root):
    result = local_config(root)['collections']
    from hub_workspace import active
    adapter = active(root)
    if adapter:
        graph = adapter.hub.graph()
        for heads in graph['heads'].values():
            if len(heads) != 1: continue
            record = graph['revisions'][heads[0]]
            config = record['data'].get('collection')
            if record['kind'] == 'context' and record['status'] != 'tombstone' and isinstance(config, dict):
                result.setdefault(config['key'], {**config, 'hub_item': record['item']})
    return result


def setup(root, data):
    name = data.get('name', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200: raise ValueError('Give this collection a short name.')
    key = studio.identifier(data.get('key') or studio.new_id(name))
    kind = data.get('type')
    if kind not in ('folder', 'export', 'urls', 'feed', 'sitemap', 'archive'): raise ValueError('Choose folder, export, urls, feed, sitemap, or archive.')
    scope = canonical(data['scope']) if data.get('scope') else None
    discovery_scope = canonical(data.get('discovery_scope') or scope) if scope else None
    if kind in ('urls', 'feed', 'sitemap', 'archive') and not scope: raise ValueError('Choose the permitted website/path scope first.')
    config = {'key': key, 'name': name.strip(), 'type': kind, 'scope': scope, 'discovery_scope': discovery_scope, 'created_at': studio.now()}
    if kind in ('feed', 'sitemap', 'archive'):
        config['url'] = canonical(data['url'])
        if not in_scope(config['url'], discovery_scope): raise ValueError('Discovery URL is outside the chosen scope.')
    if kind == 'urls':
        if not isinstance(data.get('urls'), list) or len(data['urls']) > MAX_POSTS:raise ValueError('Provide 1–500 URLs per collection.')
        config['urls'] = [canonical(u) for u in data.get('urls', [])[:MAX_POSTS]]
        if not config['urls'] or any(not in_scope(u, scope) for u in config['urls']): raise ValueError('Choose a bounded list of URLs within the collection scope.')
    if kind in ('folder', 'export'):
        path = Path(data.get('path', '')).expanduser()
        if not path.is_absolute() or not path.exists() or path.is_symlink(): raise ValueError('Choose an existing local folder or export file.')
        if (kind == 'folder' and not path.is_dir()) or (kind == 'export' and not path.is_file()):raise ValueError('Choose a folder for folder imports or a JSON file for exports.')
        config['local_path'] = str(path.resolve())
    state = local_config(root)
    if key in state['collections']: raise ValueError('This collection already exists. Refresh it instead of creating a duplicate.')
    state['collections'][key] = config
    studio.write_json(folder(root) / 'collections.json', state)
    publish_config(root, config)
    from hub_workspace import active
    adapter = active(root)
    if adapter:
        try:adapter.hub.sync()
        except (HubError, OSError):config['sharing'] = 'queued; retry Hub sync'
    return {k: v for k, v in config.items() if k != 'local_path'}


def publish_config(root, config, coverage=None):
    from hub_workspace import active
    adapter = active(root)
    if not adapter: return None
    portable = {k: v for k, v in config.items() if k not in ('local_path', 'hub_item')}
    state = local_config(root);local = state['collections'].setdefault(config['key'], config)
    existing = collections(root).get(config['key'], {}).get('hub_item') or sha(encoded(['library-collection', adapter.hub.id, config['key']]))[:32]
    result = adapter.hub.save('context', 'Blog collection: ' + config['name'],
        'Historical references. Read only selected passages. Reverify dated software claims before reuse.',
        item=existing, data={'collection': portable, 'coverage': coverage or {}},
        operation=sha(encoded([adapter.hub.id, portable, coverage]))[:32], sync=False)
    local['hub_item'] = result['item'];studio.write_json(folder(root) / 'collections.json', state)
    return result


class ArchiveLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.links = [];self.labels = [];self.anchor = None;self.title = '';self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag == 'title':self.in_title = True
        if tag == 'a':
            url = dict(attrs).get('href')
            self.anchor = None
            if url and len(self.links) < MAX_DISCOVERY:
                self.links.append(url);self.labels.append('');self.anchor = len(self.labels) - 1
    def handle_endtag(self, tag):
        if tag == 'title':self.in_title = False
        if tag == 'a':self.anchor = None
    def handle_data(self, text):
        if self.in_title:self.title += text
        if self.anchor is not None:self.labels[self.anchor] = (self.labels[self.anchor] + text)[:500]


def parse_discovery(content, kind, url, scope):
    candidates = []
    if kind == 'archive':
        parser = ArchiveLinks();parser.feed(content.decode('utf-8'))
        candidates = [{'url': urljoin(url, link), 'label': ' '.join(label.split())} for link, label in zip(parser.links, parser.labels)]
    else:
        try:tree = ET.fromstring(content)
        except ET.ParseError as exc:raise ValueError('Malformed discovery XML; no posts were imported.') from exc
        if sum(1 for _ in tree.iter()) > 20000: raise ValueError('Discovery XML is too large.')
        local = lambda t:t.rsplit('}', 1)[-1]
        if kind == 'sitemap':
            if local(tree.tag) == 'sitemapindex':raise ValueError('Choose a post sitemap; nested sitemap indexes need separately previewed collections.')
            candidates = [{'url': node.text} for node in tree.iter() if local(node.tag) == 'loc' and node.text]
        else:
            for entry in tree.iter():
                if local(entry.tag) not in ('item', 'entry'):continue
                values = {local(node.tag): node for node in entry}
                link = values.get('link')
                if local(entry.tag) == 'entry':
                    links = [node for node in entry if local(node.tag) == 'link'
                             and node.get('rel', 'alternate') in ('alternate', 'http://www.iana.org/assignments/relation/alternate')]
                    link = min(links, key=lambda node: 0 if node.get('type', '').split(';', 1)[0].strip().lower()
                               in ('text/html', 'application/xhtml+xml') else 1, default=None)
                if link is None:continue
                uri = urljoin(url, link.get('href') or link.text or '')
                if not uri:continue
                def text(*keys):
                    for key in keys:
                        node = values.get(key)
                        if node is not None:return ''.join(node.itertext()).strip()
                    return None
                author = text('creator', 'author')
                if local(entry.tag) == 'entry' and values.get('author') is not None:
                    author = next((''.join(node.itertext()).strip() for node in values['author']
                                   if local(node.tag) == 'name'), None)
                candidates.append({'url': uri, 'title': text('title'), 'author': author,
                    'published': text('pubDate', 'published'), 'updated': text('updated'), 'external_id': text('guid', 'id')})
    accepted, excluded, seen = [], [], set()
    for entry in candidates[:MAX_DISCOVERY]:
        try:
            uri = canonical(entry['url'])
            if not in_scope(uri, scope): raise ValueError('outside scope')
            identity = entry.get('external_id') or uri
            if identity in seen:
                if entry.get('label'):
                    prior = next(v for v in accepted if v['identity'] == identity)
                    if not prior.get('label'):prior['label'] = entry['label']
                continue
            seen.add(identity);accepted.append({**entry, 'url': uri, 'identity': identity})
        except (ValueError, TypeError): excluded.append({'reason': 'invalid URL or outside permitted scope'})
    return accepted[:MAX_POSTS], excluded, len(candidates) >= MAX_POSTS


def preview(root, key, reader=fetch):
    config = collections(root).get(studio.identifier(key))
    if not config: raise ValueError('Choose a configured collection.')
    candidates, excluded, limited = [], [], False
    kind = config['type']
    if kind in ('folder', 'export'):
        if not config.get('local_path'): raise ValueError('Choose this member’s local folder/export path; machine paths are not shared.')
        path = Path(config['local_path'])
        if kind == 'export':
            payload = studio.read_json(path)
            if not isinstance(payload, list) or len(payload) > MAX_DISCOVERY: raise ValueError('Export must be a bounded JSON list of posts.')
            for entry in payload[:MAX_POSTS]:
                if not isinstance(entry, dict):raise ValueError('Each export post must be an object.')
                identity = entry.get('external_id') or entry.get('url')
                if not isinstance(identity, str) or not 1 <= len(identity) <= 2000: raise ValueError('Each post needs its canonical URL or external_id.')
                if entry.get('url'):entry['url'] = canonical(entry['url'])
                candidates.append({**entry, 'identity': identity})
            limited = len(payload) > MAX_POSTS
        else:
            count = 0
            def candidate_files():
                for current, dirs, names in os.walk(path, followlinks=False):
                    dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(current) / d).is_symlink())
                    for name in sorted(names):
                        if not name.startswith('.'):yield Path(current) / name
            for source in candidate_files():
                if not source.is_file():continue
                count += 1
                if count > MAX_DISCOVERY:limited = True;break
                if source.is_symlink() or not source.resolve().is_relative_to(path.resolve()):
                    excluded.append({'reason': 'symlink or escaping file'});continue
                if source.suffix.lower() not in ('.md', '.txt', '.html', '.htm', '.docx', '.pdf'):
                    excluded.append({'reason': 'unsupported file type'});continue
                if len(candidates) >= MAX_POSTS:limited = True;break
                candidates.append({'identity': config['key'] + ':' + source.relative_to(path).as_posix(), 'file': str(source), 'title': source.stem,
                                   'expected_bytes': source.stat().st_size})
    elif kind == 'urls':
        candidates = [{'url': u, 'identity': u} for u in config['urls']]
    else:
        content, final, _ = reader(config['url'], config.get('discovery_scope') or config['scope'])
        candidates, excluded, limited = parse_discovery(content, kind, final, config['scope'])
    unique = {v['identity']: v for v in candidates}
    ident = uuid.uuid4().hex
    manifest = {'schema': 1, 'id': ident, 'collection': key, 'created_at': studio.now(), 'candidates': list(unique.values()),
                'excluded': excluded[:100], 'discovery_limited': limited, 'results': {}, 'processed_bytes': 0}
    studio.write_json(folder(root) / (ident + '.json'), manifest)
    return {'preview': ident, 'collection': config['name'], 'candidates': len(unique), 'duplicates': len(candidates) - len(unique),
            'expected_bytes': sum(v.get('expected_bytes', 0) for v in unique.values()), 'network_bytes': 'unknown until fetched' if kind not in ('folder', 'export') else None,
            'discovery_limited': limited, 'excluded': excluded[:20], 'sample': [{k: v for k, v in entry.items() if k in ('identity', 'title', 'url', 'author')} for entry in list(unique.values())[:20]],
            'next_step': 'Review the scope and preview, then explicitly import this batch as historical references.'}


def extract(root, content, suffix):
    if suffix == '.docx':
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > MAX_FETCH or sum(v.file_size for v in archive.infolist()) > MAX_IMPORT_BYTES: raise ValueError('DOCX expands beyond the extraction limit.')
            tree = ET.fromstring(archive.read(info))
            namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            text = '\n\n'.join(''.join(node.text or '' if node.tag == namespace + 't' else '\t' if node.tag == namespace + 'tab' else '\n' if node.tag == namespace + 'br' else '' for node in p.iter()) for p in tree.iter(namespace + 'p'))
            return text, 'ready' if text.strip() else 'pending'
    if suffix not in ('.md', '.txt', '.html', '.htm'):return None, 'pending'
    from performance import extract as cached_extract
    result, _ = cached_extract(root, content, suffix)
    return result['text'], 'ready' if result['text'].strip() else 'pending'


def source_rows(root):
    """Canonical records, not machine indexes; includes cached Hub-only sources."""
    from hub_workspace import active
    adapter = active(root);seen = set();rows = []
    files = adapter.hub.files() if adapter else {}
    graph = __import__('hub_store').validate_files(files, adapter.hub.config['repository']) if adapter else None
    if (root / 'sources').exists():
        for directory in sorted(studio.inside(root, 'sources').iterdir()):
            if not directory.is_dir():continue
            _, record = studio.item(root, 'sources', directory.name)
            if record.get('pinned_reference'):continue
            binding = adapter.state['items'].get('sources/' + record['id'], {}) if adapter else {}
            if binding and graph['heads'].get(binding['item']) != [binding['revision']]:continue
            if binding:seen.add(binding['item'])
            rows.append({'id': record['id'], 'location': 'local', 'record': record,
                         'path': studio.inside(directory, 'content.md'), 'binding': binding})
    if adapter:
        for item_id, heads in graph['heads'].items():
            if item_id in seen or len(heads) != 1:continue
            saved = graph['revisions'][heads[0]]
            if saved['kind'] != 'source' or saved['status'] == 'tombstone':continue
            data = saved['data'].get('studio', {})
            if data.get('pinned_reference'):continue
            rows.append({'id': item_id, 'location': 'hub', 'record': dict(data, name=saved['title'], revision=saved['revision']),
                         'body': files[saved['base'] + '/BODY.md'] if 'base' in saved else files[record_path(saved, 'BODY.md')],
                         'binding': {'item': item_id, 'revision': saved['revision']}})
    return rows


def import_batch(root, preview_id, limit=MAX_BATCH, retry=False, reader=fetch, delay=.25, selected=None):
    if not __import__('re').fullmatch(r'[a-f0-9]{32}', preview_id) or not 1 <= limit <= MAX_BATCH: raise ValueError('Choose a valid preview and batch size 1–25.')
    path = folder(root) / (preview_id + '.json');manifest = studio.read_json(path)
    config = collections(root)[manifest['collection']]
    def normalized_date(value):
        if not value:return None
        try:return datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()
        except (ValueError, AttributeError):
            try:return __import__('email.utils', fromlist=['parsedate_to_datetime']).parsedate_to_datetime(value).date().isoformat()
            except (ValueError, TypeError, AttributeError):return None
    existing = {r['record'].get('library', {}).get('identity'): r for r in source_rows(root) if r['record'].get('library')}
    if selected is not None:
        known = {entry['identity'] for entry in manifest['candidates']}
        if not isinstance(selected, list) or not selected or any(not isinstance(v, str) or v not in known for v in selected) or len(set(selected)) != len(selected):
            raise ValueError('Select valid posts from this preview.')
    chosen = set(selected) if selected is not None else None
    batch = [entry for entry in manifest['candidates'] if (chosen is None or entry['identity'] in chosen)
             and ((entry['identity'] not in manifest['results'] or manifest['results'][entry['identity']]['status'] == 'failed') if retry and chosen is None
                  else manifest['results'].get(entry['identity'], {}).get('status') == 'failed' if retry
                  else entry['identity'] not in manifest['results'])][:limit]
    from hub_workspace import active
    adapter = active(root)
    for entry in batch:
        identity = entry['identity'];result = {'status': 'failed'}
        try:
            if entry.get('file'):
                path_source = Path(entry['file'])
                base = Path(config['local_path'])
                if path_source.is_symlink() or not path_source.resolve().is_relative_to(base.resolve()): raise ValueError('Import file changed or escaped its configured folder.')
                if path_source.stat().st_size > MAX_BINARY: raise ValueError('Original exceeds Hub file size limit.')
                content = path_source.read_bytes();suffix = path_source.suffix.lower();origin = path_source.name
            elif 'text' in entry:
                if not isinstance(entry['text'], str): raise ValueError('Export text must be a string.')
                content = entry['text'].encode();suffix = '.md';origin = entry.get('url') or identity
            else:
                time.sleep(delay)
                content, origin, media = reader(entry['url'], config['scope'])
                suffix = '.html' if 'html' in media else '.txt'
            if len(content) > MAX_BINARY or manifest['processed_bytes'] + len(content) > MAX_IMPORT_BYTES: raise ValueError('This preview reached its byte limit. Create a smaller scoped preview.')
            manifest['processed_bytes'] += len(content)
            text, status = extract(root, content, suffix)
            if text is not None and len(text.encode()) > MAX_TEXT: raise ValueError('Extracted post exceeds Hub text size limit.')
            title = entry.get('title') or identity
            if suffix in ('.html', '.htm') and not entry.get('title'):
                parser = ArchiveLinks();parser.feed(content.decode());title = parser.title.strip() or title
            from performance import passage_index
            metadata = {'identity': identity, 'collections': [config['key']], 'canonical_url': entry.get('url'),
                'external_id': entry.get('external_id'), 'author': entry.get('author'), 'published': normalized_date(entry.get('published')), 'published_supplied': entry.get('published'),
                'updated': normalized_date(entry.get('updated')), 'topics': entry.get('topics', []), 'products': entry.get('products', []),
                'sections': passage_index(text) if text else [], 'historical': True, 'curation': 'active', 'extraction': 'text' if status == 'ready' else 'pending-host-extraction'}
            for key in ('topics', 'products'):
                if not isinstance(metadata[key], list) or len(metadata[key]) > 30 or any(not isinstance(v, str) or len(v) > 100 for v in metadata[key]):raise ValueError('Use up to 30 short topic/product tags.')
            if metadata['author'] is not None:metadata['author'] = studio.checked_author(metadata['author'])
            old = existing.get(identity) or next((r for r in existing.values() if r['record'].get('library', {}).get('canonical_url') == origin and origin.startswith('https://')), None)
            if old:metadata['identity'] = old['record']['library']['identity']
            if origin.startswith('https://'):metadata['canonical_url'] = origin
            if old and old['location'] == 'hub':
                local_id = adapter._checkout(old['id'])
                directory, record = studio.item(root, 'sources', local_id)
            elif old:
                directory, record = studio.item(root, 'sources', old['id'])
            else:
                local_id = 'post-' + sha(identity.encode())[:32]
                directory = studio.inside(root, 'sources', local_id)
                if directory.exists():raise ValueError('A source identity collision needs inspection; existing work was preserved.')
                directory.mkdir();record = {'id': local_id, 'name': title, 'purposes': ['reference'], 'revision': 0, 'created_at': studio.now()}
            prior_metadata = record.get('library', {})
            metadata['curation'] = prior_metadata.get('curation', 'active')
            for field in ('topics', 'products'):
                if field not in entry:metadata[field] = prior_metadata.get(field, [])
            metadata['collections'] = sorted(set(prior_metadata.get('collections', []) + metadata['collections']))
            original_hash = sha(content)
            unchanged = record.get('original_sha256') == original_hash and prior_metadata == metadata
            if unchanged:
                result = {'status': 'unchanged', 'id': record['id']}
            else:
                previous_revision = record['revision']
                if previous_revision:
                    history = studio.inside(directory, 'revisions', str(previous_revision));history.mkdir(parents=True, exist_ok=True)
                    studio.write_json(history / 'record.json', record)
                    for name in ('content.md', record.get('original_path')):
                        if name and (directory / name).exists():studio.atomic(history / name, (directory / name).read_bytes())
                name = 'original' + suffix
                studio.atomic(directory / name, content)
                if text is not None:studio.atomic(directory / 'content.md', text.encode())
                else:(directory / 'content.md').unlink(missing_ok=True)
                record.update(name=title, origin=origin, library=metadata, original_filename=Path(entry.get('file', identity)).name,
                    original_path=name, original_sha256=original_hash, content_sha256=sha(text.encode()) if text is not None else None,
                    author=entry.get('author'), status=status, retrieved_at=studio.now(), note='Historical team reference; reverify dated software claims.', revision=previous_revision + 1)
                studio.persist(directory, 'sources', record)
                result = {'status': 'updated' if previous_revision else 'imported', 'id': record['id'], 'extraction': status}
            if adapter:adapter._publish('sources', record['id'])
            existing[identity] = {'id': record['id'], 'location': 'local', 'record': record}
        except (OSError, ValueError, KeyError, TypeError, ET.ParseError, zipfile.BadZipFile, HubError) as exc:
            result = {'status': 'failed', 'reason': str(exc)[:400]}
        manifest['results'][identity] = result
        studio.write_json(path, manifest)
    counts = {name: sum(r['status'] == name for r in manifest['results'].values()) for name in ('imported', 'updated', 'unchanged', 'failed')}
    counts['pending_extraction'] = sum(r.get('extraction') == 'pending' for r in manifest['results'].values())
    coverage = {'preview': preview_id, 'discovered': len(manifest['candidates']), 'completed': len(manifest['results']),
                'remaining': len(manifest['candidates']) - len(manifest['results']), 'discovery_limited': manifest['discovery_limited'],
                'excluded': len(manifest['excluded']), 'bytes': manifest['processed_bytes'], 'counts': counts, 'last_refresh': studio.now()}
    publish_config(root, config, coverage)
    result = {**coverage, 'results': [{k: v for k, v in r.items()} for r in manifest['results'].values()][-limit:],
              'next_step': 'Retry failed items explicitly, continue this preview, or preview a refresh. Nothing missing was deleted.'}
    if adapter:
        try:result['hub_sync'] = adapter.hub.sync()
        except (HubError, OSError):result['hub_sync'] = {'status': 'local-saved-not-shared', 'next_step': 'Retry Hub sync; do not repeat the import.'}
    return result


def catalog(root, query='', collection=None, author=None, topic=None, product=None, since=None, until=None, limit=20, offset=0, include_retired=False):
    if not 1 <= limit <= 50 or offset < 0:raise ValueError('Choose limit 1–50 and nonnegative offset.')
    rows = source_rows(root)
    signature = sha(encoded([{'metadata': {k: v for k, v in r['record'].items() if k in ('id', 'revision', 'name', 'library', 'content_sha256', 'updated_at', 'status', 'author', 'origin')}, 'body_stat': [r['path'].stat().st_size, r['path'].stat().st_mtime_ns] if r['location'] == 'local' and r['path'].exists() else None} for r in rows]))
    cache = studio.inside(root, '.derived-cache');cache.mkdir(mode=0o700, exist_ok=True)
    database = studio.inside(cache, 'library.sqlite3')
    if database.is_symlink():raise ValueError('Library index must not be a symlink.')
    with closing(sqlite3.connect(database)) as db, db:
        database.chmod(0o600)
        db.execute('CREATE TABLE IF NOT EXISTS state (signature TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS posts (id TEXT, title TEXT, body TEXT, author TEXT, published TEXT, collections TEXT, topics TEXT, products TEXT, retired INTEGER, data TEXT)')
        prior = db.execute('SELECT signature FROM state').fetchone()
        if not prior or prior[0] != signature:
            db.execute('DELETE FROM posts');db.execute('DELETE FROM state');db.execute('INSERT INTO state VALUES (?)', (signature,))
            for source in rows:
                record = source['record'];metadata = record.get('library', {})
                body = source.get('body', b'').decode() if source['location'] == 'hub' else source['path'].read_text() if source['path'].exists() else ''
                data = {'id': source['id'], 'location': source['location'], 'title': record['name'], 'author': record.get('author'),
                        'origin': __import__('hub_workspace').portable_origin(record.get('origin', '')), 'status': record['status'],
                        'revision': record['revision'], 'sha256': record.get('content_sha256'), 'library': {k: v for k, v in metadata.items() if k in ('identity', 'collections', 'canonical_url', 'author', 'published', 'updated', 'topics', 'products', 'historical', 'curation', 'extraction')},
                        'historical': metadata.get('historical') is True, 'warning': 'Historical claims require current verification.' if metadata.get('historical') else None}
                db.execute('INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?,?)', (source['id'], record['name'], body, record.get('author') or '', metadata.get('published') or '',
                    json.dumps(metadata.get('collections', [])), json.dumps(metadata.get('topics', [])), json.dumps(metadata.get('products', [])),
                    int(metadata.get('curation') == 'retired'), json.dumps(data)))
        clauses, params = [], []
        for word in query.casefold().split()[:20]:
            clauses.append('lower(title || " " || body) LIKE ? ESCAPE "!"');params.append('%' + word.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%')
        if not include_retired:clauses.append('retired = 0')
        for column, value in (('collections', collection), ('author', author), ('topics', topic), ('products', product)):
            if value:clauses.append(column + ' LIKE ?');params.append('%' + value + '%')
        if since:clauses.append('published >= ?');params.append(since)
        if until:clauses.append('published <= ? AND published != ""');params.append(until)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        total = db.execute('SELECT count(*) FROM posts' + where, params).fetchone()[0]
        found = [json.loads(v[0]) for v in db.execute('SELECT data FROM posts' + where + ' ORDER BY title, id LIMIT ? OFFSET ?', params + [limit, offset])]
    names = {key: value['name'] for key, value in collections(root).items()}
    for entry in found:entry['collection_names'] = [names.get(key, key) for key in entry['library'].get('collections', [])]
    return {'items': found, 'total': total, 'truncated': total > offset + limit, 'offset': offset, 'index': 'rebuildable local catalog',
            'cache_rebuilt': not prior or prior[0] != signature, 'source_count': len(rows), 'index_bytes': database.stat().st_size}


def curate(root, ident, data):
    directory, record = studio.item(root, 'sources', ident)
    if set(data) - {'curation', 'topics', 'products', 'note'}:raise ValueError('Unknown curation field.')
    metadata = dict(record.get('library', {}))
    if 'curation' in data:
        if data['curation'] not in ('active', 'retired', 'pending'):raise ValueError('Choose active, retired, or pending.')
        metadata['curation'] = data['curation']
    for key in ('topics', 'products'):
        if key in data:
            if not isinstance(data[key], list) or len(data[key]) > 30 or any(not isinstance(v, str) or len(v) > 100 for v in data[key]):raise ValueError('Use up to 30 short tags.')
            metadata[key] = data[key]
    history = studio.inside(directory, 'revisions', str(record['revision']));history.mkdir(parents=True, exist_ok=True)
    studio.write_json(history / 'record.json', record)
    if (directory / 'content.md').exists():studio.atomic(history / 'content.md', (directory / 'content.md').read_bytes())
    original = record.get('original_path')
    if original and studio.inside(directory, original).is_file():studio.atomic(studio.inside(history, original), studio.inside(directory, original).read_bytes())
    record['library'] = metadata;record['revision'] += 1
    if 'note' in data:
        if not isinstance(data['note'], str) or len(data['note']) > 4000:raise ValueError('Keep the source note under 4000 characters.')
        record['note'] = data['note']
    studio.persist(directory, 'sources', record)
    return record


def lesson(root, data, promote=False):
    from hub_workspace import active
    adapter = active(root)
    if not adapter:raise ValueError('Select a Team Hub to save shared candidate lessons.')
    if promote:
        graph = adapter.hub.graph();item_id = data['item'];heads = graph['heads'].get(item_id, [])
        if len(heads) != 1:raise ValueError('Choose one unambiguous candidate lesson.')
        saved = graph['revisions'][heads[0]]
        if not saved['data'].get('lesson') or lesson_state(adapter, saved) != 'current':raise ValueError('Choose a current candidate lesson before promotion.')
        body = adapter.hub.files()[record_path(saved, 'BODY.md')].decode()
        return adapter.hub.save('rule', saved['title'], body, operation=sha(encoded(['promote', item_id, saved['revision']]))[:32], dependencies=saved['dependencies'], data={'approved_from': {'item': item_id, 'revision': saved['revision']}}, sync=True)
    if data.get('type') not in ('observed-pattern', 'recommendation') or not isinstance(data.get('text'), str) or not 1 <= len(data['text']) <= 4000:
        raise ValueError('Provide a short observed pattern or editorial recommendation.')
    references = data.get('references', [])
    if not isinstance(references, list) or not 1 <= len(references) <= 20:raise ValueError('Link 1–20 supporting source passages.')
    graph = adapter.hub.graph();dependencies, excerpts = [], []
    for ref in references:
        source = graph['revisions'].get(ref.get('revision'))
        if not source or source['kind'] != 'source' or source['item'] != ref.get('item'):raise ValueError('Choose saved source revisions.')
        body = adapter.hub.files()[record_path(source, 'BODY.md')].decode()
        quote = ref.get('quote', '')
        if not quote or len(quote) > 2000 or quote not in body:raise ValueError('Each lesson citation needs an exact retained passage.')
        dependencies.append({'item': source['item'], 'revision': source['revision'], 'kind': 'source', 'role': 'lesson-source'})
        excerpts.append({'item': source['item'], 'revision': source['revision'], 'quote': quote})
    return adapter.hub.save('note', str(data.get('title', 'Candidate writing lesson'))[:200], data['text'], operation=sha(encoded([data, dependencies]))[:32],
        dependencies=dependencies, data={'lesson': {'type': data['type'], 'state': 'candidate', 'excerpts': excerpts,
        'limits': 'Frequency does not prove quality or performance. Author voice and team rules remain separate.'}}, sync=True)


def lesson_state(adapter, record):
    graph = adapter.hub.graph()
    return 'current' if all(graph['heads'].get(d['item']) == [d['revision']] for d in record['dependencies']) else 'stale'


def read_source(root, ident, query='', limit=3, max_chars=4000):
    if not 1 <= limit <= 20 or not 100 <= max_chars <= 16000:raise ValueError('Use 1–20 passages and 100–16000 characters.')
    selected = next((r for r in source_rows(root) if r['id'] == ident), None)
    if not selected:raise ValueError('Choose a catalog source.')
    record = selected['record']
    if record['status'] != 'ready':raise ValueError('This source still needs extraction; it was not read.')
    content = selected.get('body', b'').decode() if selected['location'] == 'hub' else selected['path'].read_text()
    from performance import passage_index
    from local_cache import reuse
    sections, hit = reuse(root, 'library-passages', {'sha256': sha(content.encode())}, lambda:passage_index(content))
    terms = query.casefold().split()
    matching = [s for s in sections if all(t in content[s['start']:s['end']].casefold() for t in terms)]
    result, remaining = [], max_chars
    for span in matching[:limit]:
        excerpt = content[span['start']:span['end']][:remaining]
        if not excerpt:break
        result.append({'start': span['start'], 'end': span['start'] + len(excerpt), 'quote': excerpt});remaining -= len(excerpt)
    return {'id': ident, 'title': record['name'], 'revision': record['revision'], 'sha256': sha(content.encode()),
        'origin': __import__('hub_workspace').portable_origin(record.get('origin', '')), 'passages': result,
        'truncated': len(matching) > len(result) or any(len(content[s['start']:s['end']]) > len(r['quote']) for s, r in zip(matching, result)),
        'historical': record.get('library', {}).get('historical') is True, 'warning': 'Reverify dated software claims before reuse.', 'cache_hit': hit}


def add_parser(groups):
    commands = groups.add_parser('library').add_subparsers(dest='action', required=True)
    p = commands.add_parser('read');p.add_argument('--id', required=True);p.add_argument('--query', default='');p.add_argument('--limit', type=int, default=3);p.add_argument('--max-chars', type=int, default=4000)
    p = commands.add_parser('locate');p.add_argument('--collection', required=True);p.add_argument('--path', required=True)
    p = commands.add_parser('setup');p.add_argument('--file', required=True)
    p = commands.add_parser('collections')
    p = commands.add_parser('preview');p.add_argument('--collection', required=True)
    p = commands.add_parser('import');p.add_argument('--preview', required=True);p.add_argument('--limit', type=int, default=25);p.add_argument('--retry', action='store_true')
    p = commands.add_parser('find');p.add_argument('--query', default='');p.add_argument('--collection');p.add_argument('--author');p.add_argument('--topic');p.add_argument('--product');p.add_argument('--since');p.add_argument('--until');p.add_argument('--limit', type=int, default=20);p.add_argument('--offset', type=int, default=0)
    p = commands.add_parser('curate');p.add_argument('--id', required=True);p.add_argument('--file', required=True)
    p = commands.add_parser('lesson');p.add_argument('--file', required=True)
    p = commands.add_parser('promote');p.add_argument('--item', required=True);p.add_argument('--confirm', action='store_true', required=True)


def command(root, args):
    if args.action == 'read':return read_source(root, args.id, args.query, args.limit, args.max_chars)
    if args.action == 'locate':
        config = collections(root).get(args.collection)
        if not config or config['type'] not in ('folder', 'export'):raise ValueError('Choose a local file collection.')
        path = Path(args.path).expanduser()
        if not path.is_absolute() or not path.exists() or path.is_symlink():raise ValueError('Choose an existing local folder/export path.')
        state = local_config(root);state['collections'][args.collection] = dict(config, local_path=str(path.resolve()))
        studio.write_json(folder(root) / 'collections.json', state)
        return {'status': 'local-source-selected', 'collection': config['name']}
    if args.action == 'collections':return {'items': [{k: v for k, v in r.items() if k not in ('local_path', 'urls')} for r in collections(root).values()]}
    if args.action == 'find':return catalog(root, args.query, args.collection, args.author, args.topic, args.product, args.since, args.until, args.limit, args.offset)
    if args.action == 'preview':return preview(root, args.collection)
    if args.action == 'import':return import_batch(root, args.preview, args.limit, args.retry)
    if args.action == 'promote':return lesson(root, {'item': args.item}, True)
    data = studio.read_json(Path(args.file))
    if args.action == 'setup':return setup(root, data)
    if args.action == 'lesson':return lesson(root, data)
    return curate(root, args.id, data)
