"""One checked native desk workflow, shared by conversation commands and the page."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets

from . import brand, checks, evidence, exports, history, image_brief, scene, sources, stories, visual_review
from .contracts import Invalid, basis, canonical, digest
from .validation import REQUIRED_CHECKS, require, text
from .workspace import _read, file_lock


class Engine:
    def __init__(self, store, *, executable=None, renderer=None, adapters=None, assistant=None):
        self.store = store
        self.executable = executable or os.environ.get('INFOGRAPHIC_STUDIO_RENDERER')
        self.renderer = renderer
        self.adapters = adapters or {}
        self.assistant = assistant

    def inspect(self, ident):
        project = self.store.read(ident)
        from .image_jobs import Jobs
        return {'project': project, 'history': history.entries(self.store, ident),
                'source_findings': evidence.findings(project['facts']),
                'recovery': Jobs(self.store, self.adapters).recovery(ident),
                'image_history': Jobs(self.store, self.adapters).history(ident),
                'visual_review': visual_review.latest(self.store, project),
                'review_checked': visual_review.checked(self.store, project),
                'deliveries': self.deliveries(ident)}

    def deliveries(self, ident):
        project = self.store.read(ident)
        root = self.store._project(ident) / 'exports'
        require(not root.is_symlink(), 'The export directory cannot be a link.')
        if not root.exists():
            return []
        found = []
        review_checked = visual_review.checked(self.store, project)
        for folder in root.iterdir():
            if folder.name.startswith('e_') and not folder.is_symlink() and folder.is_dir():
                try:
                    manifest = json.loads(_read(self.store.root,
                        f'projects/{ident}/exports/{folder.name}/manifest.json', 100_000))
                    exports.validate_manifest(manifest, folder.name)
                except (OSError, ValueError):
                    continue  # Incomplete delivery is never advertised as downloadable.
                found.append({**manifest, 'current': manifest['basis'] == basis(project)
                              and manifest['scene_digest'] == digest(project['scene']),
                              'approved_current': not manifest['draft'] and project['approval'] is not None
                              and manifest['revision'] == project['revision']
                              and manifest['approval_digest'] == digest(project['approval'])
                              and manifest['checks_digest'] == digest(project['checks'])
                              and review_checked})
        return sorted(found, key=lambda item: (item['revision'], not item['draft']), reverse=True)

    def propose(self, ident, *, expected_revision, automatic=False):
        with file_lock(self.store._project(ident) / 'jobs/author.lock'):
            return self._propose(ident, expected_revision=expected_revision, automatic=automatic)

    def _propose(self, ident, *, expected_revision, automatic=False):
        """The page may request a confined author; a conversation supplies its own data."""
        project = self.store.read(ident)
        self.store.expect(project, expected_revision)
        require(bool(project['sources']), 'Add supplied information before asking for story suggestions.')
        require(self.assistant is not None, 'No planning assistant is configured. Use the conversation commands to author facts and stories.')
        captured = [{'id': source['id'], 'text': sources.read(self.store, project, source)}
                    for source in project['sources']]
        require(sum(len(item['text']) for item in captured) <= 120_000,
                'The selected material exceeds one planning job. Select a smaller explicit source scope.')
        answer = self.assistant.propose(project['brief'], captured)
        require(isinstance(answer, dict) and set(answer) == {'facts', 'stories'},
                'The assistant did not return a facts-and-stories proposal. Existing work is kept.')
        with self.store.locked():
            current = self.store.read(ident)
            self.store.expect(current, expected_revision)
            facts = evidence.verify(self.store, current, evidence.locate(self.store, current, answer['facts']))
            candidate = deepcopy(current)
            candidate['facts'] = facts
            proposals = stories.verify(candidate, answer['stories'])
            changes = {'facts': facts, 'stories': proposals}
            if automatic:
                require(not proposals[0].get('omissions'), 'The recommended story omits required content. Choose a direction explicitly.')
                changes['selected_story'] = proposals[0]['id']
            return self.store.change_locked(current, changes)

    def prepare_art(self, ident, *, expected_revision):
        with file_lock(self.store._project(ident) / 'jobs/author.lock'):
            return self._prepare_art(ident, expected_revision=expected_revision)

    def _prepare_art(self, ident, *, expected_revision):
        project = self.store.read(ident)
        self.store.expect(project, expected_revision)
        require(self.assistant is not None and project['scene'] is not None,
                'Compose the page and configure an assistant before asking for art direction.')
        direction = self.assistant.art_direction(project)
        return self.image_direction(ident, direction, expected_revision=expected_revision)

    def build(self, ident, *, expected_revision, request_id):
        with file_lock(self.store._project(ident) / 'jobs/build.lock'):
            return self._build(ident, expected_revision=expected_revision, request_id=request_id)

    def _build(self, ident, *, expected_revision, request_id):
        """Explicit page build: plan, author art direction, generate if needed, compose, preview."""
        from .image_jobs import Jobs
        from .validation import identifier
        require(identifier(request_id), 'Give this build an owned request identity.')
        project = self.store.read(ident)
        self.store.expect(project, expected_revision)
        require(project['selected_story'] is not None, 'Choose the story before building its page.')
        require(self.renderer is not None or self.executable and Path(self.executable).is_file()
                and os.access(self.executable, os.X_OK), 'Configure the installed renderer before starting a page build.')
        if project['scene'] is None:
            project = scene.adopt(self.store, ident, expected_revision=project['revision'])
        # Establish actual font/layout capability before spending image-provider usage.
        self.preview(ident, expected_revision=project['revision'])
        if project['scene'].get('art_regions') and not any(e['kind'] == 'artwork' for e in project['scene']['elements']):
            active = Jobs(self.store, self.adapters).recovery(ident)
            require(not active, 'An earlier image request is pending or uncertain. Recover it explicitly; this build did not resubmit it.')
            completed = next((a for a in reversed(project['attempts']) if a['state'] == 'complete' and a['asset_ids']
                              and all(a['basis'][key] == basis(project)[key] for key in a['basis'] if key != 'assets')), None)
            if completed:
                asset_id = completed['asset_ids'][0]
            else:
                selected = getattr(self, 'configuration', {}).get('image_provider')
                require(selected in self.adapters, 'Configure the selected image adapter and model before building artwork.')
                preflight = getattr(self.adapters[selected], 'preflight', None)
                if preflight: preflight()
                if not project['image_briefs'] or project['image_briefs'][-1]['basis'] != basis(project):
                    project = self.prepare_art(ident, expected_revision=project['revision'])
                jobs = Jobs(self.store, self.adapters)
                jobs.intent(ident, expected_revision=project['revision'], brief_id=project['image_briefs'][-1]['id'],
                            provider=selected, request_id=request_id)
                answer = jobs.execute(ident, request_id)
                if answer['state'] != 'complete' or not answer['adopted']:
                    return answer
                project = self.store.read(ident)
                asset_id = next(a for a in project['attempts'] if a['id'] == request_id)['asset_ids'][0]
            project = self.compose_asset(ident, asset_id, expected_revision=project['revision'])
            return self.preview(ident, expected_revision=project['revision'])
        return self.preview(ident, expected_revision=project['revision'])

    def image_direction(self, ident, direction, *, expected_revision, edit=None):
        with self.store.locked():
            project = self.store.read(ident)
            self.store.expect(project, expected_revision)
            brief = image_brief.make(project, direction, edit=edit)
            return self.store.change_locked(project, {'image_briefs': [brief]})

    def inspect_images(self, ident, *, expected_revision):
        from .visual_review import inspect
        return inspect(self, ident, expected_revision=expected_revision)

    def revise_story(self, ident, story_id, block_id, instruction, *, expected_revision):
        require(text(instruction, limit=4000) and self.assistant is not None, 'Describe the revision and configure an assistant first.')
        with file_lock(self.store._project(ident) / 'jobs/author.lock'):
            project = self.store.read(ident)
            self.store.expect(project, expected_revision)
            story = next((s for s in project['stories'] if s['id'] == story_id), None)
            require(story is not None, 'Choose an existing story.')
            if block_id is not None:
                require(block_id in {b['id'] for b in story['blocks']}, 'Choose an existing named story block.')
            revised = self.assistant.revise_story(project, story, block_id, instruction)
            require(isinstance(revised, dict) and revised.get('id') == story_id, 'The revision must retain the story identity.')
            if block_id is not None:
                require({k: v for k, v in revised.items() if k != 'blocks'} == {k: v for k, v in story.items() if k != 'blocks'}
                        and [b for b in revised.get('blocks', []) if b['id'] != block_id] == [b for b in story['blocks'] if b['id'] != block_id]
                        and [b['id'] for b in revised.get('blocks', [])] == [b['id'] for b in story['blocks']],
                        'The assistant changed content outside the requested block. No revision was adopted.')
            proposals = [revised if s['id'] == story_id else s for s in project['stories']]
            with self.store.locked():
                current = self.store.read(ident)
                self.store.expect(current, expected_revision)
                verified = stories.verify(current, proposals)
                return self.store.change_locked(current, {'stories': verified, 'selected_story': None})

    def repair(self, ident, *, expected_revision, request_id):
        project = self.store.read(ident)
        self.store.expect(project, expected_revision)
        review = visual_review.latest(self.store, project)
        defects = [f for f in (review or {}).get('findings', []) if f['blocking']]
        if defects and any(e['kind'] == 'artwork' for e in project['scene']['elements']):
            return self.revise_art(ident, '\n'.join(f['region_id'] + ': ' + f['correction'] for f in defects),
                'Preserve all other subjects, relationships, empty label regions, brand and composition.',
                expected_revision=expected_revision, request_id=request_id, automatic=True)
        require(project['scene'] is not None, 'Build a scene before requesting repair.')
        visual_review.consume_repair(self.store, ident, expected_revision=expected_revision, kind='layout')
        arrangement = 'columns' if project['scene'].get('arrangement') != 'columns' else 'stack'
        changed = scene.adopt(self.store, ident, expected_revision=expected_revision, arrangement=arrangement)
        return self.preview(ident, expected_revision=changed['revision'])

    def revise_art(self, ident, change, preserve, *, expected_revision, request_id, automatic=False):
        from .image_jobs import Jobs
        from .visual_review import consume_repair
        project = self.store.read(ident)
        self.store.expect(project, expected_revision)
        asset = next((e['asset_id'] for e in (project['scene'] or {}).get('elements', []) if e['kind'] == 'artwork'), None)
        require(asset is not None and text(change, limit=4000) and text(preserve, limit=4000),
                'Choose composed artwork and describe the exact change and what to preserve.')
        provider = getattr(self, 'configuration', {}).get('image_provider')
        require(provider in self.adapters, 'Configure the selected image provider before requesting edits.')
        preflight = getattr(self.adapters[provider], 'preflight', None)
        if preflight: preflight()
        if automatic:
            consume_repair(self.store, ident, expected_revision=expected_revision, kind='image')
        require(self.assistant is not None, 'Configure the art-direction assistant before requesting an image revision.')
        direction = self.assistant.art_direction(project)
        direction['reference_assets'] = [asset]
        project = self.image_direction(ident, direction, expected_revision=expected_revision,
                    edit={'asset_id': asset, 'change': change, 'preserve': preserve})
        jobs = Jobs(self.store, self.adapters)
        jobs.intent(ident, expected_revision=project['revision'], brief_id=project['image_briefs'][-1]['id'],
                    provider=provider, request_id=request_id, operation='edit', parent=asset)
        answer = jobs.execute(ident, request_id)
        if answer['state'] != 'complete' or not answer['adopted']:
            return answer
        current = self.store.read(ident)
        attempt = next(a for a in current['attempts'] if a['id'] == request_id)
        current = self.compose_asset(ident, attempt['asset_ids'][0], expected_revision=current['revision'])
        return self.preview(ident, expected_revision=current['revision'])

    def compose_asset(self, ident, asset_id, *, expected_revision):
        with self.store.locked():
            project = self.store.read(ident)
            self.store.expect(project, expected_revision)
            require(project['scene'] is not None and project['scene'].get('art_regions'), 'This scene has no planned artwork regions.')
            asset = next((a for a in project['assets'] if a['id'] == asset_id), None)
            require(asset is not None, 'Choose an owned returned image.')
            self.store.read_asset(ident, asset_id)
            planned = deepcopy(project['scene'])
            layer = {'id': 'artwork_layer', 'kind': 'artwork', 'bounds': [0, 0, planned['width'], planned['height']],
                     'asset_id': asset_id, 'fact_ids': [], 'fit': 'contain',
                     'alt': '; '.join(region['role'] for region in planned['art_regions'])}
            planned['elements'] = [layer] + [e for e in planned['elements'] if e['id'] != 'artwork_layer']
            for region in planned['art_regions']:
                region['asset_id'] = asset_id
            return self.store.change_locked(project, {'scene': planned})

    def edit_text(self, ident, element_id, value, *, expected_revision):
        require(text(value, limit=10_000), 'Supply the replacement text for one named element.')
        with self.store.locked():
            project = self.store.read(ident)
            self.store.expect(project, expected_revision)
            require(project['scene'] is not None, 'Build a page before editing an element.')
            planned = deepcopy(project['scene'])
            element = next((e for e in planned['elements'] if e['id'] == element_id and e['kind'] == 'text'), None)
            require(element is not None, 'Choose one existing text element.')
            lines = scene.wrapped(value, element['bounds'][2], element['font_size'])
            require(len(lines) * element['font_size'] * 1.4 <= element['bounds'][3] + .01,
                    'The replacement does not fit its readable region. Revise the layout or shorten the text.')
            element.update(text=value, lines=lines)
            visible = '\n'.join(e['text'] for e in planned['elements'] if e['kind'] == 'text')
            require(all(exact in visible for exact in project['brief']['locked_words']),
                    'Change locked wording in the brief explicitly before editing it here.')
            return self.store.change_locked(project, {'scene': planned})

    def preview(self, ident, *, expected_revision, draft=True):
        require(self.executable is not None or self.renderer is not None,
                'Configure an installed pinned renderer before preview or export. Nothing is downloaded automatically.')
        kwargs = {'renderer': self.renderer} if self.renderer else {}
        return exports.build(self.store, ident, expected_revision=expected_revision,
                             executable=self.executable, draft=draft, **kwargs)

    def manual_review(self, ident, export_id, observations, *, expected_revision):
        require(isinstance(observations, list) and bool(observations)
                and all(text(v, limit=2000) for v in observations), 'Record what you inspected on the actual page.')
        with self.store.locked():
            project = self.store.read(ident)
            self.store.expect(project, expected_revision)
            found = next((d for d in self.deliveries(ident) if d['id'] == export_id), None)
            require(found is not None and found['basis'] == basis(project)
                    and found['scene_digest'] == digest(project['scene']), 'Inspect the current rendered page before recording visual review.')
            exports.read(self.store, ident, export_id, 'png')
            review = {'schema': 1, 'by': 'user', 'status': 'passed', 'basis': basis(project),
                      'scene_digest': digest(project['scene']), 'export_id': export_id,
                      'inspected_png_sha256': next(f['sha256'] for f in found['files'] if f['format'] == 'png'),
                      'observations': observations, 'findings': []}
            from .visual_review import latest
            review['sequence'] = (latest(self.store, project) or {}).get('sequence', 0) + 1
            self.store.write_blob(ident, 'jobs/visual_' + secrets.token_hex(12) + '/review.json', canonical(review))
            return review

    def check(self, ident, *, expected_revision):
        with self.store.locked():
            project = self.store.read(ident)
            self.store.expect(project, expected_revision)
            found = next((d for d in self.deliveries(ident) if d['basis'] == basis(project)
                          and d['scene_digest'] == digest(project['scene'])), None)
            measurement = None
            if found is not None:
                raw = _read(self.store.root,
                    f'projects/{ident}/exports/{found["id"]}/measurements.json', 100_000)
                require(hashlib.sha256(raw).hexdigest() == found['measurement_sha256'],
                        'The saved renderer measurements no longer match their captured identity.')
                measurement = json.loads(raw)
            from .visual_review import latest
            visual = latest(self.store, project)
            result = deepcopy(project)
            result.update(revision=project['revision'] + 1, approval=None,
                          checks=checks.evaluate(self.store, project, measurement=measurement, visual=visual))
            next(c for c in result['checks'] if c['kind'] == 'visual')['review_digest'] = digest(visual)
            return self.store.commit_locked(project, result)

    def approve(self, ident, *, expected_revision):
        with self.store.locked():
            project = self.store.read(ident)
            self.store.expect(project, expected_revision)
            require(visual_review.checked(self.store, project),
                    'The visual review changed or is incomplete. Run checks against the latest review before approval.')
            require(REQUIRED_CHECKS <= {c['kind'] for c in project['checks']}
                    and all(c['status'] == 'passed' and c['basis'] == basis(project)
                            and c['scene_digest'] == digest(project['scene']) for c in project['checks']
                            if c['blocking'] or c['kind'] in REQUIRED_CHECKS),
                    'Resolve current blocking/incomplete findings and inspect the actual page before approval.')
            approved = deepcopy(project)
            approved['revision'] += 1
            approved['approval'] = {'revision': approved['revision'], 'owner': self.store.owner,
                                    'basis': basis(approved), 'scene_digest': digest(approved['scene']), 'by': 'user'}
            return self.store.commit_locked(project, approved)
