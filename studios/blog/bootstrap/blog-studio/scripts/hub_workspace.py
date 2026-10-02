#!/usr/bin/env python3
"""Portable shared artifacts around the existing local Blog Studio workspace."""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import studio
from hub_store import HubError, uid, sha, encoded, atomic, write_json, read_json, contained
from hub import Registry, check_root

GROUP_KIND = {'articles': 'article', 'sources': 'source', 'profiles': 'voice'}
KIND_GROUP = {value: key for key, value in GROUP_KIND.items()}
GUIDANCE_REPOSITORY = 'https://github.com/dbbaskette/blog-studio.git'


def active(workspace):
    workspace = check_root(workspace)
    selection = contained(workspace, '.team-hub.json')
    if not selection.exists():
        return None
    value = read_json(selection)
    registry = Registry(value['registry'])
    return Workspace(workspace, registry.hub(value['hub']))


def portable_origin(value):
    if not isinstance(value, str):
        return ''
    if value.startswith('/'):
        return Path(value).name
    url = urlsplit(value)
    if url.username or url.password:
        raise HubError('A source URL contains credentials; provide a portable URL before sharing it.')
    return value


def portable_review(value):
    result = {k: v for k, v in value.items() if k not in ('inputs', 'previous_status')}
    if 'inputs' in value:
        inputs = value['inputs']
        result['portable_inputs'] = {k: inputs.get(k) for k in ('draft', 'guidance')}
    return result


class Workspace:
    def __init__(self, root, hub):
        self.root = check_root(root)
        self.hub = hub
        self.path = contained(self.root, '.hub-workspace.json')
        self.state = read_json(self.path) if self.path.exists() else {'schema': 1, 'hub': hub.id, 'items': {}}
        if self.state.get('schema') != 1 or self.state.get('hub') != hub.id:
            raise HubError('This workspace is bound to a different hub; select a separate workspace or migrate explicitly.')

    def persist(self):
        write_json(self.path, self.state)

    def local_item(self, group, local_id):
        return studio.item(self.root, group, studio.identifier(local_id))

    def key(self, group, local_id):
        return group + '/' + studio.identifier(local_id)

    def read_artifacts(self, directory, group):
        artifacts = {}
        for path in sorted(directory.rglob('*')):
            if not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                raise HubError('Workspace artifacts must be regular contained files.')
            name = path.relative_to(directory).as_posix()
            if name in ('record.json', 'session.json') or any(part.startswith('.') for part in path.relative_to(directory).parts):
                continue
            # Share concrete writing artifacts, never incidental configuration or arbitrary local files.
            if group == 'articles':
                allowed = name in ('DRAFT.md','OUTLINE.md','BRIEF.md','ORIGINAL.md','INTERVIEW.md','DECISIONS.md') or bool(re.fullmatch(r'(?:derived/[A-Za-z0-9_.-]+\.md|history/(?:draft|outline|brief|original|derived-[A-Za-z0-9_.-]+)-[A-Za-z0-9_.-]+\.md|history/review-[A-Za-z0-9_.-]+\.json)', name))
            elif group == 'profiles':
                allowed = name in ('VOICE.md','BACKGROUND.md','rules.json') or bool(re.fullmatch(r'(?:imported-history/)*revisions/[0-9]+/(?:record\.json|VOICE\.md|BACKGROUND\.md|rules\.json)', name))
            else:
                allowed = name == 'content.md' or bool(re.fullmatch(r'original(?:\.[A-Za-z0-9]+)?|(?:imported-history/)*revisions/[0-9]+/(?:record\.json|content\.md)', name))
            if not allowed:
                continue
            content = path.read_bytes()
            # Only helper-generated metadata needs conversion; original uploaded JSON stays intact.
            if group in ('sources', 'profiles') and path.name == 'record.json':
                record = json.loads(content)
                record = {k: v for k, v in record.items() if k not in ('id', 'revision', 'sample_ids')}
                if 'origin' in record:record['origin'] = portable_origin(record['origin'])
                content = encoded(record)
            elif group == 'articles' and name.startswith('history/review-') and path.suffix == '.json':
                content = encoded(portable_review(json.loads(content)))
            try:content.decode('utf-8');media = 'text'
            except UnicodeError:media = 'binary'
            artifacts[name] = (content, media)
        return artifacts

    def _payload(self, group, local_id, visiting=None, read_only=False, projection=None):
        visiting = visiting or set()
        key = self.key(group, local_id)
        if key in visiting:
            raise HubError('Workspace references form a cycle.')
        visiting.add(key)
        reference_for = (lambda group, ident, unused=None: self._bound_ref(group, ident)) if read_only else self._publish
        directory, record = projection or self.local_item(group, local_id)
        dependencies = []
        data = {k: v for k, v in record.items() if k not in ('id', 'revision', 'guidance', 'guidance_history', 'hub_context', 'hub_projection')}
        title = record.get('title') or record.get('name') or local_id
        if group == 'sources':
            data['origin'] = portable_origin(record.get('origin', ''))
        elif group == 'profiles':
            dependencies = [reference_for('sources', source, visiting) for source in record['sample_ids']]
            for dependency in dependencies:dependency['role'] = 'voice-sample'
            data.pop('sample_ids', None)
        else:
            sources = []
            for selected in record['sources']:
                reference = reference_for('sources', selected['source_id'], visiting)
                reference['role'] = 'source'
                reference['purposes'] = selected['purposes']
                dependencies.append(reference);sources.append(reference)
            data['sources'] = sources
            voice = dict(record['voice'])
            if voice.get('mode') == 'profile':
                # A selected profile revision is projected independently of its newer local head.
                profile_id = voice['profile_id']
                profile_dir, profile_record = self.local_item('profiles', profile_id)
                if voice['revision'] != profile_record['revision']:
                    reference = (self._bound_ref('profile-pins', profile_id + '/' + str(voice['revision'])) if read_only else self._publish_profile_pin(profile_id, voice['revision']))
                else:
                    reference = reference_for('profiles', profile_id, visiting)
                reference['role'] = 'voice';dependencies.append(reference)
                data['voice'] = {'mode': 'profile', 'ref': reference}
            guidance = record.get('guidance')
            if guidance:
                data['guidance'] = {'repository': GUIDANCE_REPOSITORY, 'revision': guidance['revision'],
                                    'freshness': guidance.get('shared_freshness', guidance.get('freshness', 'pinned'))}
            history = record.get('guidance_history', [])
            if history:
                data['guidance_history'] = [{'repository': GUIDANCE_REPOSITORY, 'revision': p['revision']} for p in history]
            context = record.get('hub_context')
            if context:
                if context['hub'] != self.hub.id:
                    raise HubError('Selected article context belongs to another hub.')
                data['hub_context'] = {'hub': context['hub'], 'revision': context['revision'], 'selected': context['selected']}
                graph = self.hub.graph()
                for selection in context['selected']:
                    shared = graph['revisions'].get(selection['revision'])
                    if not shared or shared['item'] != selection['item'] or shared['kind'] not in ('rule', 'context'):
                        raise HubError('Selected team context revision is missing.')
                    dependencies.append({'item': shared['item'], 'revision': shared['revision'], 'kind': shared['kind'], 'role': 'context'})
            data['reviews'] = {check: portable_review(review) for check, review in studio.freshness(self.root, directory, record).items() if review['status'] != 'not-run'}
        artifacts = self.read_artifacts(directory, group)
        body_name = 'DRAFT.md' if group == 'articles' else 'VOICE.md' if group == 'profiles' else 'content.md'
        body = artifacts.get(body_name, (b'', 'text'))[0].decode('utf-8')
        request = {'kind': GROUP_KIND[group], 'title': title, 'data': data, 'dependencies': dependencies,
                   'files': {name: {'sha256': sha(content), 'media': media} for name, (content, media) in artifacts.items()}, 'body': sha(body.encode())}
        visiting.remove(key)
        return request, artifacts, body

    def _publish(self, group, local_id, visiting=None):
        key = self.key(group, local_id)
        request, artifacts, body = self._payload(group, local_id, visiting)
        title, data, dependencies = request['title'], request['data'], request['dependencies']
        fingerprint = sha(encoded(request))
        saved = self.state['items'].get(key)
        if saved and saved['fingerprint'] == fingerprint:
            return {'item': saved['item'], 'revision': saved['revision'], 'kind': GROUP_KIND[group]}
        # Parent is the version this local projection actually edited, not a newly fetched head.
        operation = sha(encoded([self.hub.id, key, saved['revision'] if saved else None, fingerprint]))[:32]
        result = self.hub.save(GROUP_KIND[group], title, body, operation=operation, item=saved['item'] if saved else None,
            parents=[saved['revision']] if saved else [], data={'studio': data}, dependencies=dependencies,
            artifacts=artifacts, sync=False,
            scope={'level': 'author' if group == 'profiles' else 'team', 'key': title if group == 'profiles' else ''})
        self.state['items'][key] = {'item': result['item'], 'revision': result['revision'], 'fingerprint': fingerprint}
        # A crash after enqueue but before this map write is recoverable by matching the operation payload.
        self.persist()
        return {'item': result['item'], 'revision': result['revision'], 'kind': GROUP_KIND[group]}

    def _publish_profile_pin(self, local_id, revision):
        key = 'profile-pins/' + studio.identifier(local_id) + '/' + str(revision)
        if key in self.state['items']:
            saved = self.state['items'][key]
            return {'item': saved['item'], 'revision': saved['revision'], 'kind': 'voice'}
        directory, _ = self.local_item('profiles', local_id)
        pinned = studio.inside(directory, 'revisions', str(revision))
        record = studio.read_json(pinned / 'record.json')
        dependencies = [self._publish('sources', value) for value in record['sample_ids']]
        for ref in dependencies:ref['role'] = 'voice-sample'
        data = {k: v for k, v in record.items() if k not in ('id', 'revision', 'sample_ids')}
        artifacts = {name: ((pinned / name).read_bytes(), 'text') for name in ('VOICE.md', 'BACKGROUND.md', 'rules.json') if (pinned / name).exists()}
        operation = sha(encoded([self.hub.id, key, data, dependencies, {n: sha(v[0]) for n,v in artifacts.items()}]))[:32]
        result = self.hub.save('voice', record['name'], artifacts['VOICE.md'][0].decode(), operation=operation,
                               data={'studio': data}, dependencies=dependencies, artifacts=artifacts, sync=False)
        self.state['items'][key] = {'item': result['item'], 'revision': result['revision'], 'fingerprint': 'pinned'}
        self.persist()
        return {'item': result['item'], 'revision': result['revision'], 'kind': 'voice'}

    def publish_selected(self, selections, offline=False):
        if not (self.root / 'studio.json').exists():
            raise HubError('Initialize the selected local writing workspace first.')
        if not any(selections.values()):
            raise HubError('Select the articles, sources, or profiles to import; no workspace sweep is performed.')
        references = []
        with studio.locked(self.root):
            for group in ('sources', 'profiles', 'articles'):
                for local_id in selections.get(group, []):
                    references.append(self._publish(group, local_id))
        result = self.hub.sync(offline)
        return {'items': references, **result}

    def publish_mutation(self, group, result, offline=False):
        # Called while studio owns its workspace lock; only the concrete changed item/dependencies.
        mapped = {'article': 'articles', 'source': 'sources', 'profile': 'profiles'}[group]
        reference = self._publish(mapped, result['id'])
        return {'item': reference, **self.hub.sync(offline)}

    def _checkout(self, item, revision=None, stack=None):
        stack = stack or set()
        shared = self.hub.read(item, revision)
        record = shared['record']
        pair = (record['item'], record['revision'])
        if pair in stack:
            raise HubError('Pinned shared dependencies contain a cycle.')
        if record['kind'] not in KIND_GROUP:
            raise HubError('Only shared articles, sources, and voices project into this workspace.')
        if record['status'] == 'tombstone':
            raise HubError('This shared item is removed; select a historical revision explicitly for recovery.')
        group = KIND_GROUP[record['kind']]
        local_id = 'hub-' + record['item'] if group == 'articles' else 'hub-' + record['item'] + '-' + record['revision']
        key = self.key(group, local_id)
        saved = self.state['items'].get(key)
        directory = studio.inside(self.root, group, local_id)
        if saved and saved['revision'] == record['revision']:
            # Never discard unshared edits just because a cached shared revision matches.
            return local_id
        if directory.exists():
            metadata_path = directory / ('session.json' if group == 'articles' else 'record.json')
            owned = read_json(metadata_path).get('hub_projection') if metadata_path.exists() else None
            expected = {'hub': self.hub.id, 'item': record['item'], 'revision': record['revision']}
            if owned and all(owned.get(k) == v for k,v in expected.items()) and owned.get('fingerprint'):
                self.state['items'][key] = {'item': record['item'], 'revision': record['revision'], 'fingerprint': owned['fingerprint']}
                self.persist()
                return local_id
            if not saved:
                raise HubError('An unrelated local projection already exists; its files were preserved.')
            request, _, _ = self._payload(group, local_id, read_only=True)
            if sha(encoded(request)) != saved['fingerprint']:
                raise HubError('This projection has unshared local edits. Save them to the hub or use a separate workspace before resuming.')
        stack.add(pair)
        resolved = {}
        for dependency in record['dependencies']:
            if dependency['kind'] in KIND_GROUP:
                resolved[(dependency['item'], dependency['revision'])] = self._checkout(dependency['item'], dependency['revision'], stack)
        data = dict(record['data'].get('studio', {}))
        if not data:
            raise HubError('This record is not a portable Blog Studio checkpoint. Read its body directly instead.')
        data['id'] = local_id
        if group == 'articles':
            if data.get('mode') not in studio.MODES or data.get('stop_point') not in ('draft','outline','review','brief'):
                raise HubError('The portable article has an invalid writing mode or stop point.')
            draft_path = shared['paths'].get('artifacts/DRAFT.md')
            body = Path(shared['paths']['BODY.md']).read_bytes()
            if body != (Path(draft_path).read_bytes() if draft_path else b''):
                raise HubError('The portable article body and draft disagree. Resolve its complete checkpoint before checkout.')
        if group == 'sources':
            data['revision'] = 1
        elif group == 'profiles':
            data['revision'] = 1
            data['sample_ids'] = [resolved[(d['item'], d['revision'])] for d in record['dependencies'] if d.get('role') == 'voice-sample']
        else:
            data['sources'] = [{'source_id': resolved[(r['item'], r['revision'])], 'purposes': r['purposes'], 'revision': 1} for r in data['sources']]
            if data['voice'].get('mode') == 'profile':
                ref = data['voice']['ref'];data['voice'] = {'mode': 'profile', 'profile_id': resolved[(ref['item'], ref['revision'])], 'revision': 1}
            if data.get('guidance'):
                data['guidance'] = {**data['guidance'], 'task': None, 'runtime': str(Path(__file__).resolve().parent), 'shared_freshness': data['guidance'].get('freshness', 'pinned'), 'freshness': 'unrestored'}
            data['guidance_history'] = [{**g, 'task': None, 'runtime': str(Path(__file__).resolve().parent)} for g in data.get('guidance_history', [])]
        data['hub_projection'] = {'hub': self.hub.id, 'item': record['item'], 'revision': record['revision']}
        stage = Path(tempfile.mkdtemp(prefix='.hub-projection-', dir=self.root))
        try:
            for relative, path in shared['paths'].items():
                if relative.startswith('artifacts/'):
                    name = relative[10:]
                    if group in ('profiles', 'sources') and name.startswith('revisions/'):
                        name = 'imported-history/' + name
                    if name in ('record.json', 'session.json'):
                        raise HubError('Artifact may not replace the projection metadata.')
                    content = Path(path).read_bytes()
                    if group == 'profiles' and name.startswith('imported-history/revisions/') and name.endswith('record.json'):
                        history = json.loads(content);history['id'] = local_id;history['revision'] = 1;history['sample_ids'] = data['sample_ids']
                        content = encoded(history)
                    atomic(studio.inside(stage, *name.split('/')), content)
            if group == 'profiles':
                studio.write_json(stage / 'record.json', data)
                studio.snapshot_profile(stage, data)
            elif group == 'articles':
                # A verified shared current review keeps its meaning across machine-local IDs.
                current = studio.fingerprints(self.root, stage, data)
                for review in data['reviews'].values():
                    provenance = review.pop('portable_inputs', {})
                    if review['status'] == 'current' and any(provenance.get(k) != current[k] for k in ('draft','guidance')):
                        review['status'] = 'stale'
                    review['inputs'] = current
                studio.write_json(stage / 'session.json', data)
            else:
                studio.write_json(stage / 'record.json', data)
            request, _, _ = self._payload(group, local_id, read_only=True, projection=(stage, data))
            data['hub_projection']['fingerprint'] = sha(encoded(request))
            studio.write_json(stage / ('session.json' if group == 'articles' else 'record.json'), data)
            if directory.exists():
                backup = studio.inside(self.root, '.hub-history', local_id, saved['revision'])
                backup.parent.mkdir(parents=True, exist_ok=True)
                if backup.exists():
                    raise HubError('A prior projection backup already exists; preserve it before replacing this projection.')
                os.replace(directory, backup)
                try:
                    os.replace(stage, directory)
                except BaseException:
                    os.replace(backup, directory)
                    raise
            else:
                os.replace(stage, directory)
        finally:
            if stage.exists():shutil.rmtree(stage)
        self.state['items'][key] = {'item': record['item'], 'revision': record['revision'], 'fingerprint': data['hub_projection']['fingerprint']}
        self.persist()
        stack.remove(pair)
        return local_id

    def _set_projection_fingerprint(self, group, local_id):
        request, _, _ = self._payload(group, local_id, read_only=True)
        self.state['items'][self.key(group, local_id)]['fingerprint'] = sha(encoded(request))
        self.persist()

    def _bound_ref(self, group, local_id, **extra):
        value = self.state['items'][(group + '/' + local_id) if group == 'profile-pins' else self.key(group, local_id)]
        return {'item': value['item'], 'revision': value['revision'], 'kind': GROUP_KIND.get(group, 'voice'), **extra}

    def checkout_selected(self, selections, offline=False):
        if not any(selections.values()):
            raise HubError('Select the shared item IDs to resume or import.')
        self.hub.refresh(offline)
        studio.initialize(self.root)
        results = []
        with studio.locked(self.root):
            for group in ('sources', 'profiles', 'articles'):
                for item in selections.get(group, []):
                    graph = self.hub.graph()
                    heads = graph['heads'].get(uid(item), [])
                    if len(heads) != 1 or graph['revisions'][heads[0]]['kind'] != GROUP_KIND[group]:
                        raise HubError('Select an unambiguous item of the requested kind.')
                    results.append({'kind': GROUP_KIND[group], 'item': item, 'local_id': self._checkout(item)})
        self.hub.registry.select(self.hub.id, self.root)
        return {'status': 'checked-out', 'items': results, 'hub': self.hub.id, 'fresh': self.hub.status()['fresh']}
