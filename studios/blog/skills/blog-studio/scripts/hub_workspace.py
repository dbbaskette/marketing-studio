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
from hub_store import (HubError, NewerRevision, uid, sha, encoded, atomic, write_json, read_json,
                       contained, size_problem)
from hub import Registry, check_root, HELD

GROUP_KIND = {'articles': 'article', 'sources': 'source', 'profiles': 'voice'}
KIND_GROUP = {value: key for key, value in GROUP_KIND.items()}
# Local article history that is shared once. A later revision does not repeat a
# history file an ancestor revision already holds, and a checkout rebuilds the
# whole folder from those ancestors. Google transfer snapshots are not covered.
LOCAL_HISTORY = re.compile(
    r'history/(?:(?:draft|outline|brief|original|derived-[A-Za-z0-9_.-]+)-[A-Za-z0-9_.-]+\.md'
    r'|(?:review|editorial)-[A-Za-z0-9_.-]+\.json)')
SOURCE_ORIGINAL = re.compile(r'original(?:\.[A-Za-z0-9]+)?')
HISTORY_FOLDERS = ('history/', 'revisions/', 'imported-history/')
IMPORTED_PROFILE_RECORD = re.compile(r'(?:imported-history/)+revisions/[0-9]+/record\.json')


def inherited_history(name):
    """Record file names whose bytes a revision may inherit from its ancestors."""
    return name.startswith('artifacts/') and bool(LOCAL_HISTORY.fullmatch(name[len('artifacts/'):]))
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
        # Files kept on this computer because they exceed a sharing limit.
        self.notices = []

    def persist(self):
        write_json(self.path, self.state)

    def reload(self):
        """Read the binding map again. Call this after taking the workspace lock.

        The map is loaded when the adapter is built, which can be seconds before
        the lock is held (a checkout refreshes the hub first). Another command
        may have saved a newer binding in that window; writing the older copy
        back would make the next save build on a superseded revision.
        """
        if not self.path.exists():
            return
        state = read_json(self.path)
        if state.get('schema') != 1 or state.get('hub') != self.hub.id:
            raise HubError('This workspace is bound to a different hub; select a separate workspace or migrate explicitly.')
        self.state = state

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
                allowed = name in ('DRAFT.md','OUTLINE.md','BRIEF.md','ORIGINAL.md','INTERVIEW.md','DECISIONS.md') or bool(re.fullmatch(r'(?:derived/[A-Za-z0-9_.-]+\.(?:md|json)|history/(?:draft|outline|brief|original|derived-[A-Za-z0-9_.-]+)-[A-Za-z0-9_.-]+\.md|history/(?:review|editorial)-[A-Za-z0-9_.-]+\.json)', name))
                allowed = allowed or bool(re.fullmatch(r'history/google-[a-f0-9]{32}-(?:document\.md|document\.docx|snapshot\.json)', name))
            elif group == 'profiles':
                allowed = name in ('VOICE.md','BACKGROUND.md','rules.json') or bool(re.fullmatch(r'(?:imported-history/)*revisions/[0-9]+/(?:record\.json|VOICE\.md|BACKGROUND\.md|rules\.json)', name))
            else:
                allowed = name == 'content.md' or bool(re.fullmatch(r'original(?:\.[A-Za-z0-9]+)?|(?:imported-history/)*revisions/[0-9]+/(?:record\.json|content\.md|original(?:\.[A-Za-z0-9]+)?)', name))
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

    def _payload(self, group, local_id, visiting=None, read_only=False, projection=None, fork=False):
        visiting = visiting or set()
        key = self.key(group, local_id)
        if key in visiting:
            raise HubError('Workspace references form a cycle.')
        visiting.add(key)
        if read_only:
            reference_for = lambda group, ident, unused=None: self._bound_ref(group, ident)
        else:
            reference_for = lambda group, ident, seen=None: self._publish(group, ident, seen, fork=fork)
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
                source_id = selected['source_id']
                _, source_record = self.local_item('sources', source_id)
                if selected['revision'] != source_record['revision']:
                    pin_key = source_id + '/' + str(selected['revision'])
                    if read_only:
                        reference = self._bound_ref('source-pins', pin_key)
                    else:
                        reference = self._publish_source_pin(source_id, selected['revision'], article=local_id)
                else:
                    reference = reference_for('sources', source_id, visiting)
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
                data['guidance'] = {'repository': GUIDANCE_REPOSITORY, 'revision': guidance['revision']}
                # Pins written before 2.0 carried a freshness label; keep it so unchanged articles do not churn.
                legacy = guidance.get('shared_freshness', guidance.get('freshness'))
                if legacy:
                    data['guidance']['freshness'] = legacy
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

    def _shareable(self, group, local_id, title, artifacts, data):
        """Apply the hub's size limits before a save is queued.

        The current working files must fit: one over the limit stops the save
        here, naming the file and the limit, instead of failing with a generic
        message on every later sync. An oversized original file, or an
        oversized file in the local history folders, is not needed to continue
        the work elsewhere, so it stays on this computer and the rest is shared
        with a note saying so.
        """
        shipped, kept_local = {}, []
        for name, (content, media) in artifacts.items():
            problem = size_problem(name, content, media)
            if problem is None:
                shipped[name] = (content, media)
            elif name.startswith(HISTORY_FOLDERS) or (group == 'sources' and SOURCE_ORIGINAL.fullmatch(name)):
                kept_local.append({'file': name, 'bytes': len(content), 'reason': problem})
            else:
                raise HubError("'" + title + "' (" + local_id + ') cannot be shared: ' + problem
                               + ' Shorten or split that file and save again; for a source, replace its text'
                               + ' with an excerpt (studio.py source update --id ' + local_id + ' --text-file …).')
        if kept_local:
            data = dict(data, files_kept_local=[{'file': entry['file'], 'bytes': entry['bytes']}
                                                for entry in kept_local])
            if data.get('original_path') in {entry['file'] for entry in kept_local}:
                data['original_path'] = None
            notice = {'local_id': local_id, 'title': title,
                      'kept_on_this_computer': [entry['reason'] for entry in kept_local]}
            if notice not in self.notices:
                self.notices.append(notice)
        return shipped, data

    def _publish(self, group, local_id, visiting=None, fork=False):
        """Queue the current state of one local item as a new shared revision.

        fork: the author explicitly accepts creating a competing version when a
        newer shared one exists. Without it the save is guarded: a sync keeps it
        on this computer rather than push a second head.
        """
        key = self.key(group, local_id)
        request, artifacts, body = self._payload(group, local_id, visiting, fork=fork)
        title, data, dependencies = request['title'], request['data'], request['dependencies']
        fingerprint = sha(encoded(request))
        saved = self.state['items'].get(key)
        if saved and fork:
            chain = self.hub.unshared_chain(saved['revision'], dependencies=True)
            self.hub.release({intent['operation'] for intent in chain})
        held = bool(saved) and self.hub.intent_state(saved['revision']) == HELD
        unchanged = bool(saved) and saved['fingerprint'] == fingerprint
        if held and (visiting or not unchanged):
            # Nothing may build on, or pin, a save that is waiting for a decision.
            raise NewerRevision(self._newer_message(group, local_id, saved['item']))
        if unchanged:
            return {'item': saved['item'], 'revision': saved['revision'], 'kind': GROUP_KIND[group]}
        shipped, data = self._shareable(group, local_id, title, artifacts, data)
        # Parent is the version this local projection actually edited, not a newly fetched head.
        operation = sha(encoded([self.hub.id, key, saved['revision'] if saved else None, fingerprint]))[:32]
        shared_item = saved['item'] if saved else None
        if shared_item is None and group == 'sources' and data.get('library', {}).get('identity'):
            shared_item = sha(encoded(['library-source', self.hub.id, data['library']['identity']]))[:32]
        result = self.hub.save(GROUP_KIND[group], title, body, operation=operation, item=shared_item,
            parents=[saved['revision']] if saved else [], data={'studio': data}, dependencies=dependencies,
            artifacts=shipped, sync=False, hold_if_stale=not fork,
            inherited=inherited_history if group == 'articles' else None,
            scope={'level': 'author' if group == 'profiles' else 'team', 'key': title if group == 'profiles' else ''})
        self.state['items'][key] = {**(saved or {}), 'item': result['item'], 'revision': result['revision'], 'fingerprint': fingerprint}
        # A crash after enqueue but before this map write is recoverable by matching the operation payload.
        self.persist()
        return {'item': result['item'], 'revision': result['revision'], 'kind': GROUP_KIND[group]}

    def _choices(self, group, local_id, item):
        """What the author can do when a newer shared version exists."""
        flag = {'articles': '--article', 'sources': '--source', 'profiles': '--profile'}[group]
        fork = ('share yours as a competing version (hub.py import-workspace ' + flag + ' ' + local_id
                + ' --fork) and resolve the conflict, ')
        if group == 'articles':
            return ('Compare first (studio.py changes --id ' + local_id + ' --against hub). Then either ' + fork
                    + 'or continue from the shared version and keep a local backup (hub.py checkout-workspace '
                    + flag + ' ' + str(item) + ' --set-aside-local).')
        # Each shared source or voice revision is checked out as its own local copy.
        return ('Either ' + fork + 'or check out the shared version (hub.py checkout-workspace ' + flag + ' '
                + str(item) + ') and use that copy instead; this one stays on this computer.')

    def _newer_message(self, group, local_id, item):
        return ('A newer shared version of ' + local_id + ' exists, so this save stays on this computer and was '
                'not pushed. ' + self._choices(group, local_id, item))

    def _report(self, outcome, keys, blocked=()):
        """Make a save that was kept back the headline of a publish result."""
        waiting = list(blocked)
        for key in keys:
            saved = self.state['items'].get(key)
            if saved and self.hub.intent_state(saved['revision']) == HELD:
                group, local_id = key.split('/', 1)
                entry = {'local_id': local_id, 'item': saved['item'],
                         'next_step': self._newer_message(group, local_id, saved['item'])}
                if entry not in waiting:
                    waiting.append(entry)
        if waiting:
            outcome.setdefault('sync_status', outcome.get('status'))
            outcome.update(status=HELD, newer_revision=waiting, next_step=waiting[0]['next_step'])
        if self.notices:
            outcome['kept_on_this_computer'] = self.notices
        return outcome

    def _publish_source_pin(self, local_id, revision, article=None):
        key = 'source-pins/' + studio.identifier(local_id) + '/' + str(revision)
        if key in self.state['items']:
            saved = self.state['items'][key]
            return {'item': saved['item'], 'revision': saved['revision'], 'kind': 'source'}
        directory, _ = self.local_item('sources', local_id)
        pinned = studio.inside(directory, 'revisions', str(revision))
        record = studio.read_json(pinned / 'record.json')
        data = {k: v for k, v in record.items() if k not in ('id', 'revision')}
        data['origin'] = portable_origin(data.get('origin', ''))
        data['pinned_reference'] = True
        artifacts = {'content.md': ((pinned / 'content.md').read_bytes(), 'text')} if (pinned / 'content.md').exists() else {}
        original = record.get('original_path')
        if original and studio.inside(pinned, original).is_file():
            content = studio.inside(pinned, original).read_bytes()
            try: content.decode('utf-8'); media = 'text'
            except UnicodeError: media = 'binary'
            artifacts[original] = (content, media)
        else:
            data['original_path'] = None
            data['original_sha256'] = None
        operation = sha(encoded([self.hub.id, key, data, {n: sha(v[0]) for n, v in artifacts.items()}]))[:32]
        pinned_text = artifacts.get('content.md')
        problem = size_problem('content.md', *pinned_text) if pinned_text else None
        if problem:
            # The blog still pins this earlier revision, so shortening the source is not enough.
            raise HubError("'" + record['name'] + "' (" + local_id + ') revision ' + str(revision)
                           + ', which this blog pins, cannot be shared: ' + problem + ' Attach the source again to '
                           + 'use its current text (studio.py article attach --id ' + str(article or '<blog id>')
                           + ' --source ' + local_id + '), then save.')
        artifacts, data = self._shareable('sources', local_id, record['name'], artifacts, data)
        result = self.hub.save('source', record['name'], artifacts.get('content.md', (b'', 'text'))[0].decode(),
            operation=operation, data={'studio': data}, artifacts=artifacts, sync=False)
        self.state['items'][key] = {'item': result['item'], 'revision': result['revision'], 'fingerprint': 'pinned'}
        self.persist()
        return {'item': result['item'], 'revision': result['revision'], 'kind': 'source'}

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

    def record_confirmed_saves(self, result):
        # A queued/review/offline result is not a save to remote main. When a save
        # was kept back, sync_status still says what happened to everything else.
        if result.get('sync_status', result.get('status')) not in ('shared', 'synchronized'):
            return
        self.state = read_json(self.path) if self.path.exists() else self.state
        remote = self.hub.graph(include_local=False)['revisions']
        changed = False
        for saved in self.state['items'].values():
            revision = saved['revision']
            if revision in remote and saved.get('last_saved_revision') != revision:
                saved.update(last_saved_to_hub=studio.now(), last_saved_revision=revision)
                changed = True
        if changed:
            self.persist()

    def publish_selected(self, selections, offline=False, fork=False):
        if not (self.root / 'studio.json').exists():
            raise HubError('Initialize the selected local writing workspace first.')
        if not any(selections.values()):
            raise HubError('Select the articles, sources, or profiles to import; no workspace sweep is performed.')
        references, keys, blocked = [], [], []
        self.notices = []
        with studio.locked(self.root):
            self.reload()
            for group in ('sources', 'profiles', 'articles'):
                for local_id in selections.get(group, []):
                    keys.append(self.key(group, local_id))
                    try:
                        references.append(self._publish(group, local_id, fork=fork))
                    except NewerRevision as exc:
                        saved = self.state['items'].get(keys[-1], {})
                        blocked.append({'local_id': local_id, 'item': saved.get('item'), 'next_step': str(exc)})
        result = self.hub.sync(offline)
        with studio.locked(self.root):
            self.record_confirmed_saves(result)
        return self._report({'items': references, **result}, keys, blocked)

    def publish_mutation(self, group, result, offline=False):
        # Called while studio owns its workspace lock; only the concrete changed item/dependencies.
        mapped = {'article': 'articles', 'source': 'sources', 'profile': 'profiles'}[group]
        self.reload()
        self.notices = []
        key = self.key(mapped, result['id'])
        blocked = []
        try:
            reference = self._publish(mapped, result['id'])
        except NewerRevision as exc:
            saved = self.state['items'].get(key, {})
            reference = {'item': saved.get('item'), 'revision': saved.get('revision'), 'kind': GROUP_KIND[mapped]}
            blocked.append({'local_id': result['id'], 'item': saved.get('item'), 'next_step': str(exc)})
        sync = self.hub.sync(offline)
        self.record_confirmed_saves(sync)
        return self._report({'item': reference, **sync}, [key], blocked)

    def _place(self, target, content):
        """Write one projected file; two shared files must never land on one path."""
        if target.exists():
            raise HubError('Two shared files map to the same local file (' + target.name
                           + '); nothing was replaced. Report this hub revision.')
        atomic(target, content)

    def _checkout(self, item, revision=None, stack=None, set_aside=False):
        """Project one shared revision into this workspace and return its local ID.

        set_aside: the author chose to continue from the shared version. Local
        work that was never shared is then moved to .hub-history as a backup
        instead of stopping the checkout; it is not deleted and not pushed.
        """
        stack = stack or set()
        shared = self.hub.read(item, revision, inherit=inherited_history)
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
        if group == 'articles':
            existing = [key.split('/', 1)[1] for key, value in self.state['items'].items()
                        if key.startswith('articles/') and value['item'] == record['item']
                        and studio.inside(self.root, 'articles', key.split('/', 1)[1]).is_dir()]
            if len(existing) > 1:
                raise HubError('Multiple local copies refer to this shared blog. Preserve and reconcile them before resuming.')
            if existing:
                local_id = existing[0]
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
            kept_back = self.hub.intent_state(saved['revision']) == HELD
            edited = sha(encoded(request)) != saved['fingerprint']
            if kept_back and not set_aside:
                raise HubError('This projection has unshared local edits that were kept back because a newer shared '
                               'version exists. ' + self._choices(group, local_id, record['item']))
            if edited and not set_aside:
                raise HubError('This projection has unshared local edits. Save them to the hub or use a separate '
                               'workspace before resuming, or rerun the checkout with --set-aside-local to keep '
                               'them as a backup under .hub-history and continue from the shared version.')
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
            # A shared pin is a record of which guidance the article used; helpers always run from this installation.
            if data.get('guidance'):
                pinned = data['guidance']
                data['guidance'] = {'revision': pinned['revision'], 'source': 'shared',
                                    **({'shared_freshness': pinned['freshness']} if pinned.get('freshness') else {})}
            data['guidance_history'] = [{'revision': g['revision'], 'source': 'shared'} for g in data.get('guidance_history', [])]
        data['hub_projection'] = {'hub': self.hub.id, 'item': record['item'], 'revision': record['revision']}
        stage = Path(tempfile.mkdtemp(prefix='.hub-projection-', dir=self.root))
        try:
            for relative, path in shared['paths'].items():
                if relative.startswith('artifacts/'):
                    name = relative[10:]
                    if group in ('profiles', 'sources') and name.startswith(('revisions/', 'imported-history/')):
                        # Every handoff nests earlier history one level deeper, so the
                        # sender's own revisions never land on history it had imported.
                        name = 'imported-history/' + name
                    if name in ('record.json', 'session.json'):
                        raise HubError('Artifact may not replace the projection metadata.')
                    content = Path(path).read_bytes()
                    if group == 'profiles' and IMPORTED_PROFILE_RECORD.fullmatch(name):
                        history = json.loads(content);history['id'] = local_id;history['revision'] = 1;history['sample_ids'] = data['sample_ids']
                        content = encoded(history)
                    self._place(studio.inside(stage, *name.split('/')), content)
            # Earlier revisions hold the history this one does not repeat.
            for relative, path in shared.get('inherited', {}).items():
                self._place(studio.inside(stage, *relative[10:].split('/')), Path(path).read_bytes())
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
        if set_aside and saved:
            # The backup in .hub-history holds the local files; the queue entries
            # move out of the outbox intact so they can never be pushed later.
            chain = self.hub.unshared_chain(saved['revision'])
            self.hub.withdraw({intent['operation'] for intent in chain})
        stack.remove(pair)
        return local_id

    def _set_projection_fingerprint(self, group, local_id):
        request, _, _ = self._payload(group, local_id, read_only=True)
        self.state['items'][self.key(group, local_id)]['fingerprint'] = sha(encoded(request))
        self.persist()

    def _bound_ref(self, group, local_id, **extra):
        value = self.state['items'][(group + '/' + local_id) if group in ('profile-pins', 'source-pins') else self.key(group, local_id)]
        return {'item': value['item'], 'revision': value['revision'], 'kind': GROUP_KIND.get(group, 'source' if group == 'source-pins' else 'voice'), **extra}

    def checkout_selected(self, selections, offline=False, set_aside=False):
        if not any(selections.values()):
            raise HubError('Select the shared item IDs to resume or import.')
        self.hub.refresh(offline)
        studio.initialize(self.root)
        results = []
        with studio.locked(self.root):
            self.reload()
            for group in ('sources', 'profiles', 'articles'):
                for item in selections.get(group, []):
                    graph = self.hub.graph()
                    heads = graph['heads'].get(uid(item), [])
                    if len(heads) != 1 or graph['revisions'][heads[0]]['kind'] != GROUP_KIND[group]:
                        raise HubError('Select an unambiguous item of the requested kind.')
                    local_id = self._checkout(item, set_aside=set_aside)
                    results.append({'kind': GROUP_KIND[group], 'item': item, 'local_id': local_id})
            if self.hub.status()['fresh']:
                self.record_confirmed_saves({'status': 'synchronized'})
        self.hub.registry.select(self.hub.id, self.root)
        return {'status': 'checked-out', 'items': results, 'hub': self.hub.id, 'fresh': self.hub.status()['fresh']}
