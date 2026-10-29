"""Durable image intent and exact-basis adoption; unknown work is never replayed."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from .contracts import MAX_ASSET_BYTES, basis, canonical, digest
from .validation import identifier, require, validate_image_result
from .workspace import _read


class Jobs:
    def __init__(self, store, adapters):
        self.store, self.adapters = store, adapters

    def intent(self, ident, *, expected_revision, brief_id, provider, request_id,
               operation='generate', parent=None, automatic=False):
        require(identifier(request_id) and provider in ('codex', 'gemini')
                and operation in ('generate', 'edit') and type(automatic) is bool,
                'Choose an owned image request, provider and operation.')
        payload = {'expected_revision': expected_revision, 'brief_id': brief_id, 'provider': provider,
                   'request_id': request_id, 'operation': operation, 'parent': parent, 'automatic': automatic}
        fingerprint = digest(payload)
        with self.store.locked():
            project = self.store.read(ident)
            relative = f'jobs/{request_id}/intent.json'
            folder = self.store._project(ident) / 'jobs' / request_id
            if folder.exists() or folder.is_symlink():
                saved = json.loads(_read(self.store.root, f'projects/{ident}/{relative}', 100_000))
                require(saved['fingerprint'] == fingerprint, 'This request ID was already used for different image work.')
                return deepcopy(saved)  # Idempotent lookup, never an execution/retry.
            self.store.expect(project, expected_revision)
            brief = next((b for b in project['image_briefs'] if b['id'] == brief_id), None)
            require(brief is not None and brief['basis'] == basis(project), 'Refresh the image brief for the current scene and inputs.')
            require(not any(a['state'] in ('queued', 'running', 'unknown') for a in self.recovery(ident)),
                    'An image request is pending or uncertain. Cancel it explicitly before starting new work.')
            if operation == 'edit':
                require(parent in {a['id'] for a in project['assets']} and parent in brief['reference_assets'],
                        'Editing must reference the original owned image in its saved brief.')
            record = {**payload, 'schema': 1, 'fingerprint': fingerprint, 'project_id': ident,
                      'owner': self.store.owner, 'basis': basis(project), 'brief': brief,
                      'assistant_configuration': getattr(self.adapters.get(provider), 'configuration', {})}
            require(len(canonical(record)) <= 100_000, 'The saved image intent exceeds its bounded size.')
            if automatic:
                from .visual_review import consume_repair_locked
                consume_repair_locked(self.store, project, kind='image')
            self.store.write_blob(ident, relative, canonical(record))
            candidate = deepcopy(project)
            candidate['revision'] += 1
            candidate['approval'] = None
            candidate['checks'] = []
            candidate['attempts'].append({'id': request_id, 'provider': provider, 'state': 'queued',
                                         'revision': candidate['revision'], 'basis': basis(candidate),
                                         'image_brief_id': brief_id, 'asset_ids': [], 'cost': None,
                                         'operation': operation, 'parent': parent, 'automatic': automatic})
            self.store.commit_locked(project, candidate)
            return record

    def execute(self, ident, request_id):
        """Execute a saved queued intent once. Reopening/status never calls this."""
        with self.store.locked():
            project = self.store.read(ident)
            attempt = next((a for a in project['attempts'] if a['id'] == request_id), None)
            require(attempt is not None and attempt['state'] == 'queued',
                    'Only a queued owned intent can execute. Interrupted/unknown work needs explicit recovery.')
            require(attempt['basis'] == basis(project), 'The image inputs changed before execution.')
            record = json.loads(_read(self.store.root, f'projects/{ident}/jobs/{request_id}/intent.json', 100_000))
            require(record['owner'] == self.store.owner and record['project_id'] == ident, 'Image intent ownership changed.')
            candidate = deepcopy(project)
            candidate['revision'] += 1
            running = next(a for a in candidate['attempts'] if a['id'] == request_id)
            running.update(state='running', revision=candidate['revision'], basis=basis(candidate))
            self.store.commit_locked(project, candidate)
            revision, expected_basis = candidate['revision'], basis(candidate)
            references = []
            for asset_id in record['brief']['reference_assets']:
                mime, raw = self.store.read_asset(ident, asset_id)
                references.append({'mime': mime, 'data': raw})
        folder = self.store._project(ident) / 'jobs' / request_id
        # Factory owns configuration and the private attempt folder, never model-selected paths.
        factory = self.adapters.get(record['provider'])
        try:
            require(factory is not None, 'The selected image adapter is unavailable; recover this request explicitly.')
            adapter = factory(folder)
            if record['operation'] == 'edit':
                answer = adapter.edit(attempt_id=request_id, brief=record['brief'], reference_assets=references)
            else:
                answer = adapter.generate(attempt_id=request_id, brief=record['brief'])
            validate_image_result(answer)
            require(answer['provider'] == record['provider'] and answer['attempt_id'] == request_id
                    and answer['operation'] == record['operation'], 'The image result belongs to another request.')
        except Exception:
            # The remote outcome may be unknown. Do not leak exception text or retry.
            from .images.base import result
            answer = result(record['provider'], record['operation'], request_id, state='unknown', reason='provider-refusal')
        return self._adopt(ident, request_id, answer, revision, expected_basis)

    def recover(self, ident, request_id, *, expected_revision):
        """Recover completed owned Codex output locally, with no provider execution."""
        with self.store.locked():
            current = self.store.read(ident)
            self.store.expect(current, expected_revision)
            details = self._details(ident, request_id)
            attempt = next((a for a in current['attempts'] if a['id'] == request_id), None)
            require(details['provider'] == 'codex' and not details['cancelled_locally'] and attempt is not None
                    and attempt['state'] in ('failed', 'unknown') and attempt['basis'] == basis(current),
                    'Only completed saved artwork for the unchanged current page can be recovered. Cancelled work stays cancelled.')
            state, expected_basis = attempt['state'], basis(current)
        from .images.codex import Codex
        folder = self.store._project(ident) / 'jobs' / request_id
        answer = Codex(folder).recover(attempt_id=request_id, operation=details['operation'])
        require(answer['state'] == 'complete', 'No usable completed artwork was found. No image request was repeated.')
        return self._adopt(ident, request_id, answer, expected_revision, expected_basis, state=state)

    def _adopt(self, ident, request_id, answer, revision, expected_basis, *, state='running'):
        folder = self.store._project(ident) / 'jobs' / request_id
        with self.store.locked():
            current = self.store.read(ident)
            if state != 'running':
                require(current['revision'] == revision and basis(current) == expected_basis,
                        'The page changed during recovery. Its newer work is kept.')
            # The original outcome is immutable. Recovery has its own receipt.
            result_name = 'recovered-result.json' if state != 'running' else 'result.json'
            self.store.write_blob(ident, f'jobs/{request_id}/{result_name}', canonical(answer))
            found = next((a for a in current['attempts'] if a['id'] == request_id), None)
            if found is None or found['state'] != state or current['revision'] != revision or basis(current) != expected_basis:
                return {'adopted': False, 'state': 'outdated', 'attempt_id': request_id}
            updated = deepcopy(current)
            updated['revision'] += 1
            landed = next(a for a in updated['attempts'] if a['id'] == request_id)
            landed.update(state=answer['state'] if answer['state'] in ('complete', 'failed', 'cancelled', 'unknown') else 'failed',
                          cost=answer['usage']['cost'], usage=answer['usage'], request_id=answer['request_id'], reason=answer['reason'])
            for asset in answer['assets'] if answer['state'] == 'complete' else []:
                raw = _read(folder, asset['file'], MAX_ASSET_BYTES)
                from .images.base import validate_png
                from .validation import image_size
                validate_png(raw, asset['mime'])
                require(image_size(raw, asset['mime']) == (asset['width'], asset['height']),
                        'The returned dimensions do not match the decoded artwork.')
                require(len(raw) == asset['bytes'] and hashlib.sha256(raw).hexdigest() == asset['sha256'],
                        'Returned asset bytes do not match the owned image result.')
                file = 'assets/' + asset['sha256'] + ('.png' if asset['mime'] == 'image/png' else '.jpg')
                self.store.write_blob(ident, file, raw)
                if asset['id'] not in {a['id'] for a in updated['assets']}:
                    updated['assets'].append({**asset, 'file': file})
                landed['asset_ids'].append(asset['id'])
            updated['checks'] = []
            updated['approval'] = None
            self.store.commit_locked(current, updated)
            return {'adopted': True, 'state': landed['state'], 'attempt_id': request_id, 'reason': landed['reason'], 'provider': landed['provider']}

    def cancel(self, ident, request_id, *, expected_revision):
        with self.store.locked():
            current = self.store.read(ident)
            self.store.expect(current, expected_revision)
            require(identifier(request_id), 'Choose an owned request identity.')
            folder = self.store._project(ident) / 'jobs' / request_id
            record = json.loads(_read(self.store.root, f'projects/{ident}/jobs/{request_id}/intent.json', 100_000))
            require(record['owner'] == self.store.owner and record['project_id'] == ident, 'The image request belongs to another owner.')
            if (folder / 'cancelled.json').exists():
                return current
            updated = deepcopy(current)
            attempt = next((a for a in updated['attempts'] if a['id'] == request_id), None)
            require(any(r['attempt_id'] == request_id and r['state'] in ('queued', 'running', 'unknown')
                        for r in self.recovery(ident)), 'Choose a pending owned image request.')
            if attempt is not None:
                attempt['state'] = 'cancelled'
                attempt['remote_cancellation'] = 'unknown'
            self.store.write_blob(ident, f'jobs/{request_id}/cancelled.json', canonical({'remote_cancellation': 'unknown', 'owner': self.store.owner}))
            updated['revision'] += 1
            updated['approval'] = None
            saved = self.store.commit_locked(current, updated)
        from .images.codex import stop_owned
        stop_owned(self.store._project(ident) / 'jobs' / request_id)
        return saved

    def recovery(self, ident):
        project = self.store.read(ident)
        found = {a['id']: a['state'] for a in project['attempts']}
        root = self.store._project(ident) / 'jobs'
        require(not root.is_symlink(), 'Image history cannot traverse links.')
        result = []
        for folder in root.iterdir() if root.exists() else ():
            if not identifier(folder.name) or not (folder / 'intent.json').exists(): continue
            record = json.loads(_read(self.store.root, f'projects/{ident}/jobs/{folder.name}/intent.json', 100_000))
            require(record['owner'] == self.store.owner and record['project_id'] == ident, 'Image intent ownership changed.')
            if (folder / 'cancelled.json').exists() or found.get(folder.name) == 'cancelled': continue
            state = found.get(folder.name)
            if state is None:
                result_name = 'recovered-result.json' if (folder / 'recovered-result.json').exists() else 'result.json'
                if (folder / result_name).exists():
                    answer = json.loads(_read(self.store.root, f'projects/{ident}/jobs/{folder.name}/{result_name}', 100_000))
                    state = answer['state']
                else: state = 'unknown'
            local = False
            if state in ('failed', 'unknown') and record['provider'] == 'codex':
                from .images.codex import saved_output
                try:
                    saved_output(folder)
                    attempt = next((a for a in project['attempts'] if a['id'] == folder.name), None)
                    local = bool(attempt and attempt['basis'] == basis(project))
                except (ValueError, OSError):
                    pass
            if state in ('queued', 'running', 'unknown') or local:
                result.append({'attempt_id': folder.name, 'state': state, 'automatic_retry': False,
                     'local_artwork_available': local,
                     'message': 'Completed artwork was found. Recover it locally without another image request.' if local else
                         'No request was resubmitted. Pending or interrupted work requires explicit cancellation and new intent.'})
        return result

    def details(self, ident, request_id):
        self.store.read(ident)
        return self._details(ident, request_id)

    def _details(self, ident, request_id):
        require(identifier(request_id), 'Choose an owned image request identity.')
        prefix = f'projects/{ident}/jobs/{request_id}/'
        record = json.loads(_read(self.store.root, prefix + 'intent.json', 100_000))
        require(record['owner'] == self.store.owner and record['project_id'] == ident, 'Image request ownership changed.')
        folder = self.store._project(ident) / 'jobs' / request_id
        result_name = 'recovered-result.json' if (folder / 'recovered-result.json').exists() else 'result.json'
        answer = json.loads(_read(self.store.root, prefix + result_name, 100_000)) if (folder / result_name).exists() else None
        return {'id': request_id, 'provider': record['provider'], 'operation': record['operation'],
                'configuration': record['assistant_configuration'],
                'revision': record['expected_revision'], 'brief': record['brief'],
                'result': answer, 'cancelled_locally': (folder / 'cancelled.json').exists(),
                'automatic_retry': False}

    def history(self, ident):
        self.store.read(ident)
        root = self.store._project(ident) / 'jobs'
        require(not root.is_symlink(), 'Image request history cannot traverse links.')
        found = []
        for folder in root.iterdir() if root.exists() else ():
            if identifier(folder.name) and (folder / 'intent.json').exists():
                item = self._details(ident, folder.name)
                found.append({'id': item['id'], 'provider': item['provider'], 'operation': item['operation'],
                              'revision': item['revision'], 'state': 'cancelled locally' if item['cancelled_locally'] else
                              (item['result'] or {}).get('state', 'pending or interrupted'),
                              'usage': (item['result'] or {}).get('usage')})
        return sorted(found, key=lambda item: (item['revision'], item['id']), reverse=True)
