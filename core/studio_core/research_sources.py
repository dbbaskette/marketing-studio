"""One private source-draft API for every studio, with no provider or Google writes."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit

from studio_core import google_reference, public_fetch, source_documents, research_sites
from studio_core.process_lock import ProcessRLock
from studio_core import research_contract as rc

LIMIT = 8_000_000
MOST = 40
TYPES = {'.txt': 'text', '.md': 'text', '.markdown': 'text', '.pdf': 'pdf', '.docx': 'docx', '.html': 'html', '.htm': 'html'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


class Sources:
    def __init__(self, root, *, google=None, fetch=None, account=None, extract=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not (self.root / '.gitignore').exists():
            rc.write(self.root, '.gitignore', '*\n')
        self.google = google or google_reference.capture
        self.fetch = fetch or public_fetch.fetch
        self.account = account
        self.extract = extract or source_documents.extract
        self.lock = ProcessRLock(lambda: self.root / 'sources.lock', refusal=ValueError)

    def folder(self, ident):
        require(isinstance(ident, str) and re.fullmatch('[a-f0-9]{32}', ident), 'Choose a source draft from this studio.')
        return rc.inside(self.root, ident)

    def load(self, ident):
        try:
            value = json.loads(rc.inside(self.folder(ident), 'draft.json').read_text())
        except (OSError, ValueError) as error:
            raise ValueError('This source draft is unavailable. Create a new one; your saved studio work is kept.') from error
        require(value.get('owner') == 'studio-research-sources' and value.get('schema') == 1,
                'This source draft is not owned by the shared research component.')
        return value

    def save(self, value):
        value['revision'] = secrets.token_hex(16)
        rc.write(self.folder(value['id']), 'draft.json', json.dumps(value))

    @staticmethod
    def shown(value):
        keys = ('id', 'revision', 'external', 'restricted', 'sites', 'workers', 'focus')
        return {**{k: value[k] for k in keys}, 'sources': [{k: s[k] for k in (
            'id', 'name', 'kind', 'origin', 'status', 'warnings', 'problem', 'tabs', 'selected_tabs', 'captured_at', 'sha256')
            if k in s} for s in value['sources']], 'formats': list(TYPES)}

    def create(self, *, sites=()):
        with self.lock:
            ident = secrets.token_hex(16)
            self.folder(ident).mkdir(mode=0o700)
            value = {'schema': 1, 'owner': 'studio-research-sources', 'id': ident,
                'revision': '', 'external': False, 'restricted': False,
                'sites': research_sites.sites(list(sites)), 'workers': 3, 'focus': '', 'sources': []}
            self.save(value)
            return self.shown(value)

    def read(self, ident):
        with self.lock:
            return self.shown(self.load(ident))

    def check(self, ident, expected):
        value = self.load(ident)
        require(value['revision'] == expected, 'These sources changed in another view. Reload; your entered links and text are kept.')
        return value

    def mutate(self, ident, expected, operation, **data):
        require(operation in ('configure', 'remove', 'exclude', 'capture', 'tabs'), 'Choose a supported source action.')
        # Network/extraction happens outside the draft lock; adoption rechecks the same revision.
        if operation in ('capture', 'tabs'):
            with self.lock:
                current = self.check(ident, expected)
                old = next((s for s in current['sources'] if s['id'] == data.get('source')), None)
                require(len(current['sources']) < MOST or old is not None, 'Use at most 40 sources in one request.')
                if operation == 'capture' and data.get('source') and data.get('kind') != 'saved':
                    require(old is not None and old.get('requested_url'), 'Choose a saved URL to retry.')
                    data = {'kind': 'url', 'url': old['requested_url']}
                if operation == 'tabs':
                    require(old is not None and old['kind'] in ('google-doc', 'google-slides'), 'Choose a Google source from this draft.')
                    data = {'kind': 'url', 'url': old['requested_url'], 'selected': data.get('selected')}
            captured = self.capture(data)
            with self.lock:
                current = self.check(ident, expected)
                captured['id'] = old['id'] if old else secrets.token_hex(16)
                current['sources'] = [s for s in current['sources'] if s['id'] != captured['id']]
                if captured.get('raw') is not None:
                    raw, text = captured.pop('raw'), captured.pop('text')
                    raw_name = 'captures/' + hashlib.sha256(raw).hexdigest() + '.raw'
                    text_name = 'captures/' + hashlib.sha256(text.encode()).hexdigest() + '.txt'
                    rc.write(self.folder(ident), raw_name, raw)
                    rc.write(self.folder(ident), text_name, text)
                    captured.update(original=raw_name, file=text_name,
                                    original_sha256=hashlib.sha256(raw).hexdigest(), sha256=hashlib.sha256(text.encode()).hexdigest())
                current['sources'].append(captured)
                self.save(current)
                return self.shown(current)
        with self.lock:
            current = self.check(ident, expected)
            if operation == 'configure':
                require(not set(data) - {'external', 'restricted', 'workers', 'focus'}, 'Keep supported research options only.')
                for key in ('external', 'restricted'):
                    if key in data: require(type(data[key]) is bool, 'Choose search permission explicitly.')
                if 'workers' in data: require(type(data['workers']) is int and 1 <= data['workers'] <= 3, 'Choose 1–3 research workers.')
                if 'focus' in data: require(isinstance(data['focus'], str) and len(data['focus']) <= 4000, 'Keep the research focus within 4,000 characters.')
                current.update(data)
                require(not current['restricted'] or current['sites'], 'Add approved sites in shared settings before restricting searches to them.')
            else:
                source = next((s for s in current['sources'] if s['id'] == data.get('source')), None)
                require(source is not None, 'Choose a source in this draft.')
                if operation == 'remove': current['sources'].remove(source)
                else: source['status'] = 'excluded'
            self.save(current)
            return self.shown(current)

    def saved(self):
        """Bounded inventory of verified local results; no personal folder picker or network scan."""
        workspace = self.root.parent
        rows = []
        for category in ('blogs', 'articles', 'presentations', 'trainings', 'projects'):
            parent = workspace / category
            if not parent.is_dir() or parent.is_symlink(): continue
            for item in sorted(parent.iterdir())[:500]:
                if not item.is_dir() or item.is_symlink(): continue
                bundle = item / 'research'
                if not (bundle / 'output.json').is_file(): continue
                try:
                    facts, manifest = rc.read_bundle(bundle)
                    relative = str(bundle.relative_to(workspace))
                    rows.append({'id': digest(relative), 'revision': digest(manifest),
                        'name': facts.get('topic') or item.name, 'purpose': facts.get('purpose') or '',
                        'audience': facts.get('audience') or '', 'scope': facts.get('scope') or '', 'folder': relative})
                except (OSError, ValueError, KeyError): continue
        return rows

    def capture(self, data):
        kind = data.get('kind')
        name = data.get('name') or 'Pasted notes'
        source = {'name': name, 'kind': kind, 'origin': name, 'status': 'ready', 'warnings': [],
                  'tabs': [], 'selected_tabs': [], 'problem': None,
                  'captured_at': datetime.now(timezone.utc).isoformat()}
        try:
            if kind == 'saved':
                selected = next((s for s in self.saved() if s['id'] == data.get('source') and s['revision'] == data.get('revision')), None)
                require(selected is not None, 'This saved research changed or is unavailable. Choose its current reviewed revision.')
                bundle = rc.inside(self.root.parent, selected['folder'])
                facts, manifest = rc.read_bundle(bundle)
                body = {key: rc.inside(bundle, key + '.md').read_text() for key in ('brief', 'evidence', 'report')}
                raw = json.dumps({'research': facts, 'manifest': manifest, **body}, ensure_ascii=False).encode()
                extracted = {'text': '\n\n'.join(body.values()), 'warnings': [
                    'Previously reviewed for: ' + selected['purpose'] + '. Reused as selected reference material; new claims and purpose still need their own check.']}
                source.update(name=selected['name'], origin='Saved local research: ' + selected['folder'])
            elif kind == 'url':
                url = data.get('url')
                require(isinstance(url, str) and len(url) <= 4096, 'Give a document or public page link.')
                source['requested_url'] = url
                source['origin'] = url
                if urlsplit(url).hostname == 'docs.google.com':
                    found = self.google(url, account=self.account() if callable(self.account) else self.account,
                                        selected=data.get('selected'))
                    source.update({k: found[k] for k in ('name', 'kind', 'origin', 'tabs', 'selected_tabs')})
                    raw, extracted = found['raw'], found['extracted']
                else:
                    found = self.fetch(url)
                    raw = found['raw']
                    source.update(kind='url', name=found['url'], origin=found['url'])
                    mime = found['mime'].split(';', 1)[0]
                    require(mime in ('text/plain', 'text/html', 'application/pdf'), 'Use a readable text, HTML or PDF reference.')
                    extracted = self.extract(raw, {'text/plain': 'text', 'text/html': 'html', 'application/pdf': 'pdf'}[mime])
            elif kind == 'text':
                require(isinstance(data.get('text'), str), 'Paste readable source text.')
                raw = data['text'].encode('utf-8')
                extracted = self.extract(raw, 'text')
            elif kind == 'file':
                require(isinstance(name, str) and Path(name).name == name and '/' not in name and '\\' not in name,
                        'Choose a plain filename.')
                suffix = Path(name).suffix.lower()
                require(suffix in TYPES, 'Choose PDF, DOCX, text, Markdown or HTML.')
                encoded = data.get('content')
                require(isinstance(encoded, str) and len(encoded) <= 4 * ((LIMIT + 2) // 3), 'Choose a source within 8 MB.')
                try: raw = base64.b64decode(encoded, validate=True)
                except ValueError: raise ValueError('The uploaded file is not valid base64.') from None
                extracted = self.extract(raw, TYPES[suffix])
            else:
                raise ValueError('Add a link, file or pasted text.')
            require(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'Choose nonempty source material within 8 MB.')
            text = extracted.get('text', '')
            require(isinstance(text, str) and 0 < len(text.encode()) <= LIMIT and text.strip(),
                    'This source contains no readable text. Use a text copy or exclude it.')
            source.update(raw=raw, text=text, warnings=extracted.get('warnings', []))
        except (ValueError, OSError) as error:
            source.update(status='needs-attention', problem=str(error))
        return source

    def preview(self, ident, source_id):
        with self.lock:
            value = self.load(ident)
            source = next((s for s in value['sources'] if s['id'] == source_id), None)
            require(source is not None and source['status'] == 'ready', 'Choose a readable source to preview.')
            text = rc.inside(self.folder(ident), source['file']).read_text()
            require(hashlib.sha256(text.encode()).hexdigest() == source['sha256'], 'This source capture changed. Read it again.')
            return {'source': source_id, 'text': text[:20_000], 'total': len(text), 'warnings': source['warnings']}

    def prepared(self, ident, expected, *, primary=False):
        """Trusted server-side start handoff; paths/bytes never come from browser IDs."""
        with self.lock:
            value = self.check(ident, expected)
            require(all(s['status'] in ('ready', 'excluded') for s in value['sources']),
                    'Retry, remove or explicitly exclude unreadable sources before starting.')
            ready = [s for s in value['sources'] if s['status'] == 'ready']
            require(primary or ready or value['external'], 'Add a source or allow additional external search.')
            offered = []
            for source in ready:
                folder = self.folder(ident)
                text = rc.inside(folder, source['file']).read_text()
                raw = rc.inside(folder, source['original']).read_bytes()
                require(hashlib.sha256(text.encode()).hexdigest() == source['sha256']
                        and hashlib.sha256(raw).hexdigest() == source['original_sha256'],
                        'A selected source changed. Read it again before starting.')
                offered.append({**source, 'title': source['name'], 'text': text, 'permission': 'selected',
                    'path': rc.inside(folder, source['file']), 'original_path': rc.inside(folder, source['original'])})
            choice = {'documents': bool(ready) or primary, 'sites': value['sites'] if value['external'] and value['restricted'] else [],
                      'web': value['external'] and not value['restricted']}
            return {'id': ident, 'revision': expected, 'sources': offered, 'research_from': choice,
                    'workers': value['workers'], 'focus': value['focus']}

    def dispatch(self, sent):
        require(isinstance(sent, dict), 'Send one source request.')
        sent = dict(sent)
        action = sent.pop('action', None)
        if action == 'saved':
            require(not sent, 'List the reviewed local research only.')
            return {'items': [{k:v for k,v in item.items() if k != 'folder'} for item in self.saved()]}
        if action == 'create':
            require(not sent, 'Create the source draft before adding material.')
            from studio_core import studios_config
            shared, _ = studios_config.read()
            return self.create(sites=research_sites.defaults(shared))
        ident = sent.pop('id', None)
        if action == 'read':
            require(not sent, 'Read one source draft.')
            return self.read(ident)
        if action == 'preview':
            require(set(sent) == {'source'}, 'Choose one source to preview.')
            return self.preview(ident, sent['source'])
        expected = sent.pop('expected', None)
        return self.mutate(ident, expected, action, **sent)


def install(prepared, root):
    """Keep an exact private input snapshot with the new studio item, before dispatch."""
    root = Path(root)
    rc.write(root, 'sources/research-inputs/.gitignore', '*\n')
    rows = []
    for source in prepared['sources']:
        ident = source['id']
        suffix = Path(source['name']).suffix.lower() if source['kind'] == 'file' else '.raw'
        suffix = suffix if re.fullmatch(r'\.[a-z0-9]{1,10}', suffix) else '.raw'
        original = 'sources/research-inputs/' + ident + '.original' + suffix
        file = 'sources/research-inputs/' + ident + '.txt'
        raw = Path(source['original_path']).read_bytes()
        text = source['text']
        require(hashlib.sha256(raw).hexdigest() == source['original_sha256']
                and hashlib.sha256(text.encode()).hexdigest() == source['sha256'],
                'The source changed while starting; reload the source preview.')
        rc.write(root, original, raw)
        rc.write(root, file, text)
        rows.append({k: source[k] for k in ('id', 'name', 'kind', 'origin', 'warnings', 'tabs', 'selected_tabs',
            'captured_at', 'sha256', 'original_sha256') if k in source})
        rows[-1].update(file=file, original=original)
    value = {'schema': 1, 'owner': 'studio-research-inputs', 'sources': rows,
             'research_from': prepared['research_from'], 'workers': prepared['workers'], 'focus': prepared['focus']}
    rc.write(root, 'sources/research-inputs/manifest.json', json.dumps(value))
    return {'schema': 1, 'digest': digest(value), 'count': len(rows),
            'workers': prepared['workers'], 'focus': prepared['focus']}


def sources(root, saved=None):
    root = Path(root)
    file = root / 'sources/research-inputs/manifest.json'
    if not file.exists():
        require(not saved, 'This computer does not have the selected research inputs. Add their permitted copies before resuming.')
        return [], []
    value = json.loads(rc.inside(root, 'sources/research-inputs/manifest.json').read_text())
    require(value.get('schema') == 1 and value.get('owner') == 'studio-research-inputs'
            and (not saved or saved.get('digest') == digest(value)), 'The saved research inputs changed; reload them before starting.')
    plan, offered = [], []
    for source in value['sources']:
        text = rc.inside(root, source['file']).read_text()
        original = rc.inside(root, source['original']).read_bytes()
        require(hashlib.sha256(text.encode()).hexdigest() == source['sha256']
                and hashlib.sha256(original).hexdigest() == source['original_sha256'], 'A saved source capture changed; read it again.')
        plan.append({'id': source['id'], 'title': source['name'], 'origin': source['origin'],
            'original_file': source['original'], 'file': source['file'],
            'limits': '; '.join(source['warnings']) or 'none'})
        offered.append({'title': source['name'], 'origin': source['origin'], 'permission': 'selected',
            'text': text, 'file': source['file'], 'original': source['original'],
            'original_path': rc.inside(root, source['original']), 'supplied': source['id'],
            'accessed_at': source['captured_at']})
    return plan, offered


def prepare_start(workspace, reference, *, primary=False):
    require(isinstance(reference, dict) and set(reference) == {'id', 'expected'}, 'Choose this source draft and its current revision.')
    return Sources(Path(workspace) / '.research-sources').prepared(reference['id'], reference['expected'], primary=primary)
