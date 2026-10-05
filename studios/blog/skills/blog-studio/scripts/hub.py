#!/usr/bin/env python3
"""Team Hub lifecycle, progressive memory lookup, and durable Git synchronization."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

from hub_store import (VERSION, KINDS, HubError, TransportError, GitHub, uid, now, encoded,
                       sha, atomic, write_json, read_json, contained, locked, canonical_repository,
                       git, manifest, validate_files, artifact_name, tree_files, commit_files)


def default_registry():
    return Path.home() / '.local/share/blog-studio/hubs'


def check_root(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise HubError('Choose an absolute real hub storage location.')
    path = path.resolve()
    installed = Path(__file__).resolve().parents[1]
    if path == installed or path.is_relative_to(installed):
        raise HubError('Store team data outside the installed skill.')
    return path


class Registry:
    def __init__(self, root=None, provider=None):
        self.root = check_root(root or default_registry())
        self.provider = provider or GitHub()

    def state(self):
        path = contained(self.root, 'registry.json')
        value = read_json(path) if path.exists() else {'schema': 1, 'hubs': {}}
        if not isinstance(value, dict) or value.get('schema') != 1 or not isinstance(value.get('hubs'), dict):
            raise HubError('The local hub registry is invalid.')
        return value

    def list(self):
        return [{'hub': key, **value} for key, value in self.state()['hubs'].items()]

    def hub(self, hub_id):
        entry = self.state()['hubs'].get(uid(hub_id))
        if not entry:
            raise HubError('This hub is not joined on this computer.')
        return Hub(self, hub_id, entry)

    def selected(self, workspace):
        workspace = check_root(workspace)
        path = contained(workspace, '.team-hub.json')
        if not path.exists():
            return None
        value = read_json(path)
        if value.get('schema') != 1 or Path(value['registry']).resolve() != self.root:
            raise HubError('The project selects a different hub registry. Use its recorded registry path.')
        return self.hub(value['hub'])

    def select(self, hub_id, workspace):
        hub = self.hub(hub_id)
        workspace = check_root(workspace)
        write_json(contained(workspace, '.team-hub.json'), {'schema': 1, 'hub': hub.id, 'registry': str(self.root)})
        return {'status': 'selected', 'hub': hub.id, 'workspace': str(workspace), 'shared_work': True}

    def leave(self, hub_id, workspace):
        selected = self.selected(workspace)
        if selected and selected.id == hub_id:
            contained(workspace, '.team-hub.json').unlink()
        return {'status': 'left-project', 'retained': 'Clone, queued work, and shared remote data.'}

    def join(self, repository, destination=None, workspace=None):
        repository = canonical_repository(repository)
        with locked(self.root, '.registry.lock'):
            metadata = self.provider.lookup(repository)
            if not metadata:
                raise HubError('The private repository is unavailable to your account.')
            hub = self._join(metadata, destination)
        if workspace:
            self.select(hub.id, workspace)
        return hub.status()

    def _join(self, metadata, destination=None):
        repository = canonical_repository(metadata['repository'])
        if metadata.get('private') is not True:
            raise HubError('Team Hubs must be private repositories.')
        state = self.state()
        for hub_id, entry in state['hubs'].items():
            if entry['repository'] == repository:
                if entry['provider_id'] != metadata['id']:
                    raise HubError('This repository identity changed. The existing clone was preserved.')
                if destination and check_root(destination) != Path(entry['path']):
                    raise HubError('This hub already has a managed local clone; reuse its recorded location.')
                hub = Hub(self, hub_id, entry)
                with locked(hub.root):
                    hub._refresh(metadata)
                return hub
        stage = self.root / ('.join-' + uuid.uuid4().hex)
        stage.mkdir(mode=0o700)
        try:
            repository_path = stage / 'repository.git'
            git(repository_path, 'init', '--bare', '--quiet', '--initial-branch=main')
            source = self.provider.transport(metadata)
            git(repository_path, 'remote', 'add', 'origin', source)
            git(repository_path, 'fetch', '--quiet', '--no-tags', source, 'refs/heads/main')
            commit = git(repository_path, 'rev-parse', 'FETCH_HEAD^{commit}').decode().strip()
            files = tree_files(repository_path, commit)
            graph = validate_files(files, repository)
            hub_id = graph['manifest']['hub']
            if hub_id in state['hubs']:
                raise HubError('The hub UUID is already registered to another repository.')
            target = check_root(destination) if destination else self.root / 'clones' / hub_id
            if target.exists() or target.is_symlink():
                raise HubError('The chosen local hub location already exists; it was preserved.')
            entry = {'repository': repository, 'provider_id': metadata['id'],
                     'path': str(target), 'name': graph['manifest']['name'], 'url': metadata['url']}
            write_json(stage / 'config.json', {'schema': 1, 'hub': hub_id, 'actor': self.provider.actor(), **entry})
            write_json(stage / 'state.json', {'revision': commit, 'verified_at': now(),
                'fresh': True, 'write': metadata.get('write'), 'review_branch': None})
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.move(str(stage), str(target))
            # Record activation atomically. A failed record write leaves an owned recoverable clone.
            state['hubs'][hub_id] = entry
            try:
                write_json(self.root / 'registry.json', state)
            except Exception:
                shutil.move(str(target), str(stage))
                raise
            hub = Hub(self, hub_id, entry)
            hub._materialize(commit, files)
            return hub
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def create(self, repository, name, destination=None, workspace=None, mode='auto'):
        repository = canonical_repository(repository)
        if not name.strip() or mode not in ('auto', 'direct', 'review'):
            raise HubError('Supply a hub name and a supported contribution mode.')
        intent_path = self.root / 'creation' / (sha(repository.encode()) + '.json')
        with locked(self.root, '.registry.lock'):
            intent = read_json(intent_path) if intent_path.exists() else None
            if intent and (intent['name'] != name or intent['mode'] != mode):
                raise HubError('A prior creation intent uses different settings. Resume it without changing the request.')
            metadata = self.provider.lookup(repository)
            if not intent:
                if metadata:
                    raise HubError('That repository already exists. Join it explicitly; no remote data was changed.')
                intent = {'repository': repository, 'name': name, 'mode': mode,
                          'hub': uuid.uuid4().hex, 'status': 'prepared', 'provider_id': None}
                write_json(intent_path, intent)
            seed_files = {'hub.json': encoded(manifest(intent['hub'], name, repository, mode)),
                          'README.md': ('# ' + name + '\n\nShared Blog Studio working memory. Use the installed skill to create revisions.\n').encode()}
            from hub_browse import changes
            seed_files.update(changes(seed_files, validate_files(seed_files, repository)))
            marker = 'Blog Studio Team Hub ' + intent['hub']
            if metadata is None:
                intent['status'] = 'creating';write_json(intent_path, intent)
                try:
                    self.provider.create(repository, intent['hub'])
                except TransportError:
                    metadata = self.provider.lookup(repository)
                    if not metadata:
                        raise HubError('Remote creation outcome is unverified. The intent was retained; retry the same owner/name.')
                metadata = metadata or self.provider.lookup(repository)
            if (not metadata or not metadata['private'] or metadata.get('description') != marker
                    or (intent['provider_id'] is not None and metadata['id'] != intent['provider_id'])):
                raise HubError('An existing repository does not match this hub creation intent; it was preserved.')
            intent['provider_id'] = metadata['id'];intent['status'] = 'remote-created';write_json(intent_path, intent)
            seed_dir = contained(self.root, 'creation', intent['hub'])
            seed_dir.mkdir(parents=True, exist_ok=True)
            repo = seed_dir / 'repository.git'
            if not repo.exists():
                git(repo, 'init', '--bare', '--quiet', '--initial-branch=main')
            source = self.provider.transport(metadata)
            fetched = git(repo, 'fetch', '--quiet', '--no-tags', source, 'refs/heads/main', allow_failure=True)
            if fetched.returncode == 0:
                commit = git(repo, 'rev-parse', 'FETCH_HEAD^{commit}').decode().strip()
                graph = validate_files(tree_files(repo, commit), repository)
                if graph['manifest']['hub'] != intent['hub']:
                    raise HubError('Remote initialization belongs to another hub. No seed was pushed.')
            else:
                advertised = git(repo, 'ls-remote', '--exit-code', source, 'refs/heads/main', allow_failure=True)
                if advertised.returncode != 2:
                    raise TransportError('Remote initialization could not be verified. Retry the same create request; no seed was pushed.')
                actor = self.provider.actor()
                commit = commit_files(repo, None, seed_files, 'Initialize Team Hub', actor)
                git(repo, 'push', '--quiet', source, commit + ':refs/heads/main')
            intent['status'] = 'seeded';write_json(intent_path, intent)
            hub = self._join(metadata, destination)
            intent['status'] = 'joined';write_json(intent_path, intent)
        if workspace:
            self.select(hub.id, workspace)
        return {'status': 'created', **hub.status(), 'creation': 'verified'}


class Hub:
    def __init__(self, registry, hub_id, entry):
        self.registry = registry
        self.id = uid(hub_id)
        self.root = check_root(entry['path'])
        self.repository = contained(self.root, 'repository.git')
        self.config = read_json(contained(self.root, 'config.json'))
        if (self.config.get('hub') != self.id or self.config.get('repository') != entry['repository']
                or self.config.get('provider_id') != entry['provider_id']):
            raise HubError('The clone ownership record does not match the registry.')

    def _state(self):
        value = read_json(contained(self.root, 'state.json'))
        if not isinstance(value, dict) or not isinstance(value.get('revision'), str):
            raise HubError('Local hub state is invalid.')
        return value

    def _write_state(self, state):
        write_json(contained(self.root, 'state.json'), state)

    def _remote_files(self):
        files = tree_files(self.repository, self._state()['revision'])
        graph = validate_files(files, self.config['repository'])
        if graph['manifest']['hub'] != self.id:
            raise HubError('The repository now contains a different hub UUID.')
        return files

    def _materialize(self, commit, files):
        root = contained(self.root, 'snapshots', commit)
        for name, content in files.items():
            target = contained(root, *name.split('/'))
            if target.exists():
                if sha(target.read_bytes()) != sha(content):
                    raise HubError('A validated local hub snapshot changed. Restore it before reading that revision.')
            else:
                atomic(target, content);target.chmod(0o400)
        return root

    def _refresh(self, metadata=None):
        metadata = metadata or self.registry.provider.lookup(self.config['repository'])
        if not metadata:
            raise TransportError('Hub repository is unavailable to this account.')
        if (metadata['id'] != self.config['provider_id'] or not metadata['private']
                or metadata['repository'] != self.config['repository']):
            raise HubError('The remote identity or visibility changed; the existing clone was preserved.')
        state = self._state()
        git(self.repository, 'fetch', '--quiet', '--no-tags', self.registry.provider.transport(metadata), 'refs/heads/main')
        commit = git(self.repository, 'rev-parse', 'FETCH_HEAD^{commit}').decode().strip()
        files = tree_files(self.repository, commit)
        graph = validate_files(files, self.config['repository'])
        if graph['manifest']['hub'] != self.id:
            raise HubError('Remote hub UUID changed.')
        previous = self._remote_files()
        for name, content in previous.items():
            if name.startswith('memory/') and files.get(name) != content:
                raise HubError('A published memory revision was modified or removed. Existing data was preserved.')
        published = []
        for intent in self._intents():
            additions = self._intent_files(intent)
            if all(name in files for name in additions):
                if any(files[name] != data for name, data in additions.items()):
                    raise HubError('Remote operation ID was reused with different content.')
                published.append(intent)
        self._materialize(commit, files)
        state.update(revision=commit, fresh=True, verified_at=now(), write=metadata.get('write'))
        state.pop('error', None)
        self._write_state(state)
        for intent in published:
            intent['state'] = 'published';intent['published_commit'] = commit
            self._write_intent(intent)
        if state.get('library_review') and graph['manifest'].get('browse_schema') in (1, 2):
            state.pop('library_review', None)
        if not state.get('library_review') and not any(i['state'] == 'pending-review' for i in self._intents()):
            state['review_branch'] = None;state.pop('pull_request', None);self._write_state(state)
        return graph

    def refresh(self, offline=False):
        with locked(self.root):
            if offline:
                state = self._state();state['fresh'] = False;self._write_state(state)
            else:
                try:
                    self._refresh()
                except TransportError as exc:
                    state = self._state();state.update(fresh=False, error=str(exc));self._write_state(state)
                except HubError as exc:
                    state = self._state();state.update(fresh=False, error=str(exc));self._write_state(state)
                    raise
            return self.status()

    def _intents(self):
        folder = contained(self.root, 'outbox')
        values = []
        if folder.exists():
            for path in folder.iterdir():
                if path.name.startswith('.'):
                    continue
                uid(path.name)
                intent = read_json(contained(folder, path.name, 'intent.json'))
                if intent['operation'] != path.name or intent['hub'] != self.id:
                    raise HubError('The saved operation belongs to another hub.')
                values.append(intent)
        return sorted(values, key=lambda i: (i['created_at'], i['operation']))

    def _write_intent(self, intent):
        write_json(contained(self.root, 'outbox', uid(intent['operation']), 'intent.json'), intent)

    def _intent_files(self, intent):
        root = contained(self.root, 'outbox', uid(intent['operation']), 'payload')
        result = {}
        for name, digest in intent['files'].items():
            path = contained(root, *name.split('/'))
            content = path.read_bytes()
            if sha(content) != digest:
                raise HubError('Queued operation content changed; the original operation was preserved.')
            result[name] = content
        if sha(encoded(intent['files'])) != intent['payload_hash']:
            raise HubError('Queued operation manifest changed.')
        return result

    def files(self, include_local=True):
        files = self._remote_files()
        if include_local:
            for intent in self._intents():
                if intent['state'] != 'published':
                    for name, data in self._intent_files(intent).items():
                        if name in files and files[name] != data:
                            raise HubError('An operation ID has conflicting payloads.')
                        files[name] = data
        return files

    def view(self):
        """One local Git tree observation for a read-only card; never remote freshness."""
        remote = self._remote_files()
        files = dict(remote)
        intents = self._intents()
        for intent in intents:
            if intent['state'] != 'published':
                for name, data in self._intent_files(intent).items():
                    if name in files and files[name] != data:
                        raise HubError('An operation ID has conflicting payloads.')
                    files[name] = data
        return validate_files(files, self.config['repository']), remote, intents

    def graph(self, include_local=True):
        return validate_files(self.files(include_local), self.config['repository'])

    def status(self):
        state = self._state()
        graph = self.graph()
        intents = self._intents()
        return {'hub': self.id, 'name': graph['manifest']['name'], 'url': self.config['url'],
                'revision': state['revision'], 'fresh': state.get('fresh', False),
                'contribution_mode': graph['manifest']['contribution_mode'],
                'contribution': 'write' if state.get('write') is True else 'read-only' if state.get('write') is False else 'unverified',
                'queued': sum(i['state'] == 'queued' for i in intents),
                'pending_review': sum(i['state'] == 'pending-review' for i in intents),
                'conflicts': sum(len(v) > 1 for v in graph['heads'].values()),
                'clone': str(self.repository), 'error': state.get('error'),
                'pull_request': state.get('pull_request'),
                'blog_library': 'pending-review' if state.get('library_review') else 'available' if graph['manifest'].get('browse_schema') in (1, 2) else 'upgrade-on-next-sync',
                'blog_library_url': self.config['url'] + '/tree/main/blogs' if graph['manifest'].get('browse_schema') in (1, 2) else None}

    def save(self, kind, title, body='', *, item=None, parents=None, operation=None, data=None,
             dependencies=None, artifacts=None, scope=None, tags=None, summary='', status='active',
             offline=False, sync=True, actor=None):
        if kind not in KINDS:
            raise HubError('Unsupported memory kind.')
        operation = uid(operation) if operation else uuid.uuid4().hex
        item = uid(item) if item else operation
        with locked(self.root):
            existing_path = contained(self.root, 'outbox', operation, 'intent.json')
            existing = read_json(existing_path) if existing_path.exists() else None
            graph = self.graph()
            remote_record = graph['revisions'].get(operation)
            if parents is None:
                parents = existing['request']['parents'] if existing else remote_record['parents'] if remote_record else graph['heads'].get(item, [])
                if len(parents) > 1:
                    raise HubError('This item has competing revisions. Resolve them explicitly with all selected parents.')
            parents = sorted(uid(p) for p in parents)
            files = {'BODY.md': (body.encode('utf-8'), 'text')}
            for name, (content, media) in (artifacts or {}).items():
                files['artifacts/' + artifact_name(name)] = (content, media)
            request = {'item': item, 'kind': kind, 'title': title, 'parents': parents, 'data': data or {},
                       'dependencies': dependencies or [], 'scope': scope or {'level': 'team', 'key': ''},
                       'tags': tags or [], 'summary': summary, 'status': status,
                       'files': {name: {'sha256': sha(content), 'media': media} for name, (content, media) in files.items()}}
            request_hash = sha(encoded(request))
            if existing:
                if existing['request_hash'] != request_hash:
                    raise HubError('An operation ID cannot be reused with different content.')
                result = self._sync(offline) if sync else self.status()
                return {**result, 'hub_commit': result['revision'], 'item': item, 'revision': operation, 'operation': operation}
            if remote_record:
                remote_request = {key: remote_record[key] for key in request}
                if sha(encoded(remote_request)) != request_hash:
                    raise HubError('An operation ID cannot be reused with different content.')
                result = self._sync(offline) if sync else self.status()
                return {**result, 'hub_commit': result['revision'], 'item': item, 'revision': operation, 'operation': operation}
            record = {'schema': 1, 'operation': operation, 'revision': operation, **request,
                      'actor': actor or self.config.get('actor') or 'Blog Studio member', 'created_at': now()}
            prefix = 'memory/items/' + item + '/revisions/' + operation + '/'
            additions = {prefix + name: content for name, (content, _) in files.items()}
            additions[prefix + 'record.json'] = encoded(record)
            combined = dict(self.files());combined.update(additions)
            validate_files(combined, self.config['repository'])
            folder = contained(self.root, 'outbox', operation)
            stage = contained(self.root, 'outbox', '.' + operation)
            if stage.exists():
                raise HubError('A previous staging operation needs inspection; it was preserved.')
            stage.mkdir(parents=True, mode=0o700)
            try:
                for name, content in additions.items():
                    atomic(contained(stage, 'payload', *name.split('/')), content)
                hashes = {name: sha(content) for name, content in additions.items()}
                intent = {'hub': self.id, 'operation': operation, 'state': 'queued',
                          'created_at': record['created_at'], 'request': request, 'request_hash': request_hash,
                          'files': hashes, 'payload_hash': sha(encoded(hashes))}
                write_json(stage / 'intent.json', intent)
                os.replace(stage, folder)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
            result = self._sync(offline) if sync else {'status': 'local-saved', **self.status()}
            return {**result, 'hub_commit': result['revision'], 'item': item, 'revision': operation, 'operation': operation}

    def _sync(self, offline=False):
        if offline:
            state = self._state();state['fresh'] = False;self._write_state(state)
            return {'status': 'queued-offline', **self.status()}
        try:
            self._refresh()
            for attempt in range(3):
                intents = [i for i in self._intents() if i['state'] != 'published']
                from hub_browse import changes, verify
                original = self._remote_files()
                original_graph = validate_files(original, self.config['repository'])
                verify(original, original_graph)
                if not intents and not changes(original, original_graph):
                    return {'status': 'synchronized', **self.status()}
                state = self._state()
                if state.get('write') is False:
                    return {'status': 'queued-read-only', **self.status()}
                base = state['revision']
                original = self._remote_files()
                additions = {}
                for intent in intents:
                    additions.update(self._intent_files(intent))
                policy_review = self.registry.provider.review_required(self.config['repository'])
                mode = validate_files(original)['manifest']['contribution_mode']
                review = policy_review or mode == 'review' or bool(state.get('review_branch'))
                branch = state.get('review_branch') or 'codex/hub-' + (intents[0]['operation'] if intents else base[:32])
                extra_parents = []
                if review:
                    state['review_branch'] = branch
                    if not intents:state['library_review'] = True
                    self._write_state(state)
                    prior = git(self.repository, 'fetch', '--quiet', self.registry.provider.transport(self.config),
                                'refs/heads/' + branch, allow_failure=True)
                    if prior.returncode == 0:
                        prior_commit = git(self.repository, 'rev-parse', 'FETCH_HEAD^{commit}').decode().strip()
                        branch_files = tree_files(self.repository, prior_commit)
                        verify(branch_files, validate_files(branch_files, self.config['repository']))
                        for name, content in branch_files.items():
                            if name.startswith('memory/'):
                                if name in original and original[name] != content:
                                    raise HubError('A contribution branch changed an immutable memory revision.')
                                if name in additions and additions[name] != content:
                                    raise HubError('A contribution branch reused an operation ID with different content.')
                                additions.setdefault(name, content)
                        extra_parents.append(prior_commit)
                combined = dict(original);combined.update(additions)
                additions.update(changes(combined, validate_files(combined, self.config['repository'])))
                for name, content in additions.items():
                    if content is None:combined.pop(name, None)
                    else:combined[name] = content
                validate_files(combined, self.config['repository'])
                commit = commit_files(self.repository, base, additions, 'Save Team Hub memory',
                                      self.config.get('actor', 'Blog Studio member'), extra_parents)
                target = branch if review else 'main'
                pushed = git(self.repository, 'push', '--quiet', self.registry.provider.transport(self.config),
                             commit + ':refs/heads/' + target, allow_failure=True)
                if pushed.returncode == 0:
                    if review:
                        for intent in intents:
                            intent['state'] = 'pending-review';self._write_intent(intent)
                        url = self.registry.provider.ensure_pr(self.config['repository'], branch, 'Update Team Hub memory')
                        state = self._state();state['pull_request'] = url;self._write_state(state)
                        return {'status': 'pending-review', **self.status()}
                    self._refresh()
                    return {'status': 'shared', **self.status()}
                # Reconcile even after uncertain/rejected delivery before retrying the same IDs.
                self._refresh()
            return {'status': 'queued-contention', **self.status()}
        except TransportError as exc:
            state = self._state();state.update(fresh=False, error=str(exc));self._write_state(state)
            return {'status': 'queued-unavailable', **self.status()}

    def sync(self, offline=False):
        with locked(self.root):
            return self._sync(offline)

    def read(self, item, revision=None):
        item = uid(item)
        with locked(self.root):
            files = self.files()
            graph = validate_files(files, self.config['repository'])
            heads = graph['heads'].get(item, [])
            if revision is None:
                if len(heads) != 1:
                    raise HubError('Select a revision explicitly; this item is missing or conflicted.')
                revision = heads[0]
            record = graph['revisions'].get(uid(revision))
            if not record or record['item'] != item:
                raise HubError('Unknown memory item/revision.')
            prefix = 'memory/items/' + item + '/revisions/' + revision + '/'
            contents = {name: content for name, content in files.items() if name.startswith(prefix)}
            cache = contained(self.root, 'reads', revision)
            paths = {}
            for relative in record['files']:
                path = contained(cache, *relative.split('/'))
                content = contents[prefix + relative]
                if path.exists() and path.read_bytes() != content:
                    raise HubError('The local read artifact changed. Restore it before using this revision.')
                if not path.exists():
                    atomic(path, content);path.chmod(0o400)
                paths[relative] = str(path)
            visibility = 'shared'
            for intent in self._intents():
                if intent['operation'] == revision and intent['state'] != 'published':
                    visibility = intent['state']
            return {'record': record, 'paths': paths, 'heads': heads, 'conflicted': len(heads) > 1,
                    'visibility': visibility, 'hub': self.id, 'hub_commit': self._state()['revision']}

    def find(self, query='', kind=None, scope=None, tag=None, limit=10, offset=0):
        if not 1 <= limit <= 50:
            raise HubError('Choose a result limit between 1 and 50.')
        if offset < 0:
            raise HubError('A result offset must be nonnegative.')
        with locked(self.root):
            files = self.files();graph = validate_files(files, self.config['repository'])
            terms = query.casefold().split()
            items = []
            for item, heads in graph['heads'].items():
                for revision in sorted(heads):
                    record = graph['revisions'][revision]
                    if (record['status'] == 'tombstone' or (kind and record['kind'] != kind)
                            or (scope and record['scope'] != scope) or (tag and tag not in record['tags'])):
                        continue
                    prefix = 'memory/items/' + item + '/revisions/' + revision + '/'
                    text = (record['title'] + ' ' + record['summary'] + ' ' + ' '.join(record['tags'])
                            + ' ' + files[prefix + 'BODY.md'].decode()).casefold()
                    if any(term not in text for term in terms):
                        continue
                    items.append({'item': item, 'revision': revision, 'kind': record['kind'],
                                  'title': record['title'], 'summary': record['summary'][:300],
                                  'scope': record['scope'], 'status': record['status'],
                                  'conflicted': len(heads) > 1})
            items.sort(key=lambda row: (row['title'], row['item'], row['revision']))
            return {'items': items[offset:offset+limit], 'total': len(items), 'offset': offset, 'truncated': len(items) > offset+limit,
                    'hub': self.id, 'revision': self._state()['revision'], 'fresh': self._state().get('fresh', False)}

    def context(self, project=None, author=None, article=None, limit=50):
        if not 1 <= limit <= 200:
            raise HubError('Choose a context limit between 1 and 200.')
        selected = [{'level': 'team', 'key': ''}]
        for level, key in (('project', project), ('author', author), ('article', article)):
            if key:
                selected.append({'level': level, 'key': key})
        graph = self.graph()
        result = []
        conflicts = []
        for item, heads in graph['heads'].items():
            for revision in heads:
                record = graph['revisions'][revision]
                if record['data'].get('collection'):continue
                if record['kind'] in ('rule', 'context') and record['scope'] in selected and record['status'] != 'tombstone':
                    row = {'item': item, 'revision': revision, 'scope': record['scope'], 'title': record['title'],
                           'conflicted': len(heads) > 1, 'key': record['data'].get('key')}
                    (conflicts if len(heads) > 1 else result).append(row)
        keys = {}
        for row in result:
            if row['key']:
                grouping = (row['scope']['level'], row['scope']['key'], row['key'])
                keys.setdefault(grouping, []).append(row)
        for rows in keys.values():
            if len(rows) > 1:
                for row in rows:
                    row['conflicted'] = True
                    if row not in conflicts:
                        conflicts.append(row)
        usable = [r for r in result if not r['conflicted']]
        usable.sort(key=lambda r: selected.index(r['scope']), reverse=True)
        return {'selected': usable[:limit], 'conflicts': conflicts[:limit], 'total': len(usable),
                'truncated': len(usable) > limit or len(conflicts) > limit,
                'precedence': 'Current request, explicit article/author/project selections, then team defaults.',
                'hub': self.id, 'revision': self._state()['revision'], 'fresh': self._state().get('fresh', False)}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry', type=Path, default=default_registry())
    p.add_argument('--hub')
    p.add_argument('--workspace', type=Path)
    actions = p.add_subparsers(dest='action', required=True)
    actions.add_parser('list')
    for name in ('create', 'join'):
        sub = actions.add_parser(name);sub.add_argument('--repo', required=True);sub.add_argument('--destination', type=Path)
        if name == 'create':
            sub.add_argument('--name', required=True);sub.add_argument('--mode', choices=('auto', 'direct', 'review'), default='auto')
    for name in ('select', 'leave', 'status'):
        actions.add_parser(name)
    for name in ('refresh', 'sync'):
        sub = actions.add_parser(name);sub.add_argument('--offline', action='store_true')
    for name in ('save', 'remember', 'resolve', 'remove'):
        sub = actions.add_parser(name);sub.add_argument('--item');sub.add_argument('--parent', action='append')
        sub.add_argument('--operation');sub.add_argument('--kind', choices=KINDS, default='note')
        sub.add_argument('--title', required=True);sub.add_argument('--file', type=Path)
        sub.add_argument('--data-file', type=Path);sub.add_argument('--dependencies-file', type=Path)
        sub.add_argument('--scope', choices=('team', 'project', 'author', 'article'), default='team')
        sub.add_argument('--scope-key', default='');sub.add_argument('--tag', action='append', default=[])
        sub.add_argument('--summary', default='');sub.add_argument('--artifact', action='append', default=[])
        sub.add_argument('--offline', action='store_true');sub.add_argument('--no-sync', action='store_true')
        sub.add_argument('--status', choices=('active', 'provisional', 'confirmed'), default='active')
    sub = actions.add_parser('read');sub.add_argument('--item', required=True);sub.add_argument('--revision')
    sub = actions.add_parser('history');sub.add_argument('--item', required=True);sub.add_argument('--limit', type=int, default=20);sub.add_argument('--offset', type=int, default=0)
    sub = actions.add_parser('find');sub.add_argument('--query', default='');sub.add_argument('--kind', choices=KINDS)
    sub.add_argument('--tag');sub.add_argument('--limit', type=int, default=10);sub.add_argument('--offset', type=int, default=0)
    sub = actions.add_parser('context');sub.add_argument('--project');sub.add_argument('--author');sub.add_argument('--article');sub.add_argument('--limit', type=int, default=50)
    sub = actions.add_parser('import-workspace');sub.add_argument('--article', action='append', default=[])
    sub.add_argument('--source', action='append', default=[]);sub.add_argument('--profile', action='append', default=[])
    sub.add_argument('--offline', action='store_true')
    sub = actions.add_parser('checkout-workspace');sub.add_argument('--article', action='append', default=[])
    sub.add_argument('--source', action='append', default=[]);sub.add_argument('--profile', action='append', default=[])
    sub.add_argument('--offline', action='store_true')
    return p


def main():
    args = parser().parse_args()
    try:
        registry = Registry(args.registry)
        if args.action == 'list':
            result = registry.list()
        elif args.action in ('create', 'join'):
            if args.action == 'create':
                result = registry.create(args.repo, args.name, args.destination, args.workspace, args.mode)
            else:
                result = registry.join(args.repo, args.destination, args.workspace)
        else:
            hub = registry.hub(args.hub) if args.hub else registry.selected(args.workspace) if args.workspace else None
            if not hub:
                raise HubError('Select a joined hub or provide --hub and its registry.')
            if args.action in ('select', 'leave'):
                if not args.workspace:
                    raise HubError('A project workspace is required.')
                result = getattr(registry, args.action)(hub.id, args.workspace)
            elif args.action == 'status':result = hub.status()
            elif args.action in ('sync', 'refresh'):result = getattr(hub, args.action)(args.offline)
            elif args.action == 'read':result = hub.read(args.item, args.revision)
            elif args.action == 'history':
                if not 1 <= args.limit <= 50 or args.offset < 0:
                    raise HubError('Choose a history limit from 1 to 50 and a nonnegative offset.')
                graph = hub.graph()
                records = sorted((r for r in graph['revisions'].values() if r['item'] == uid(args.item)), key=lambda r: r['created_at'], reverse=True)
                result = {'revisions': [{k: r[k] for k in ('item','revision','parents','title','status','created_at','actor')} for r in records[args.offset:args.offset+args.limit]],
                          'total': len(records), 'truncated': len(records) > args.offset+args.limit, 'heads': graph['heads'].get(args.item, [])[:50]}
            elif args.action == 'find':result = hub.find(args.query, args.kind, tag=args.tag, limit=args.limit, offset=args.offset)
            elif args.action == 'context':result = hub.context(args.project, args.author, args.article, limit=args.limit)
            elif args.action in ('import-workspace', 'checkout-workspace'):
                if not args.workspace:
                    raise HubError('An explicit writing workspace is required.')
                from hub_workspace import Workspace
                adapter = Workspace(args.workspace, hub)
                selections = {'articles': args.article, 'sources': args.source, 'profiles': args.profile}
                if args.action == 'import-workspace':result = adapter.publish_selected(selections, offline=args.offline)
                else:result = adapter.checkout_selected(selections, offline=args.offline)
            else:
                parents = args.parent
                if args.action in ('resolve', 'remove') and not args.item:
                    raise HubError('Choose the item to resolve or remove.')
                if args.action == 'resolve':
                    heads = hub.graph()['heads'].get(uid(args.item), [])
                    if len(heads) < 2 or set(parents or []) != set(heads):
                        raise HubError('Resolution must name all current competing parent revisions.')
                body = args.file.read_text(encoding='utf-8') if args.file else ''
                artifacts = {}
                for entry in args.artifact:
                    if '=' not in entry:
                        raise HubError('Use --artifact name=absolute-file.')
                    name, value = entry.split('=', 1);path = Path(value)
                    if not path.is_absolute() or path.is_symlink():raise HubError('Select an absolute regular artifact file.')
                    content = path.read_bytes()
                    try:content.decode('utf-8');media = 'text'
                    except UnicodeError:media = 'binary'
                    artifacts[name] = (content, media)
                if args.scope != 'team' and not args.scope_key:
                    raise HubError('A project, author, or article rule needs its scope key.')
                result = hub.save(args.kind, args.title, body, item=args.item, parents=parents,
                    operation=args.operation, data=read_json(args.data_file) if args.data_file else None,
                    dependencies=read_json(args.dependencies_file) if args.dependencies_file else None,
                    artifacts=artifacts, scope={'level': args.scope, 'key': args.scope_key}, tags=args.tag,
                    summary=args.summary, status='tombstone' if args.action == 'remove' else args.status,
                    offline=args.offline, sync=not args.no_sync)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (HubError, OSError, ValueError, KeyError, TypeError) as exc:
        message = str(exc) if isinstance(exc, HubError) else 'Hub operation could not finish. Check selected paths and input records; saved work is retained.'
        print(json.dumps({'status': 'error', 'error': message}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
