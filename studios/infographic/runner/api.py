"""One bounded action dispatcher for native commands and authenticated HTTP."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import stat

from . import brand, computer, evidence, history, scene, settings, sources, stories
from .author import Author
from .contracts import Invalid, MAX_RECORD_BYTES
from .engine import Engine
from .image_jobs import Jobs
from .images.codex import Codex
from .images.gemini import Gemini
from .validation import require


def source_bytes(value):
    require(isinstance(value, str) and len(value) <= 22_000_000, 'Supply bounded base64 source bytes.')
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as failure:
        raise Invalid('The source bytes are not valid base64.') from failure


def load_json(path, *, limit=MAX_RECORD_BYTES):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'JSON input files cannot traverse links.')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Choose a regular JSON file.')
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'The JSON input exceeds its size limit.')
    return json.loads(raw)


def engine(store):
    chosen = settings.snapshot()
    assistant = chosen['assistant']
    def codex_adapter(folder):
        return Codex(folder, model=assistant['model'], effort=assistant['effort'])
    codex_adapter.configuration = dict(assistant)
    from studio_core.runtime import assistant_command
    codex_adapter.preflight = lambda: require(assistant_command('codex') is not None, 'Install or select an available Codex CLI before starting image work.')
    adapters = {'codex': codex_adapter}
    if chosen['native'].get('gemini_model'):
        def gemini_adapter(folder):
            return Gemini(folder, model=chosen['native']['gemini_model'])
        gemini_adapter.configuration = {'model': chosen['native']['gemini_model'], 'api': 'interactions', 'image_size': '2K'}
        gemini_adapter.preflight = lambda: require(bool(os.environ.get('GEMINI_API_KEY')), 'Set GEMINI_API_KEY in the server launch environment before starting image work. Do not paste it into this page.')
        adapters['gemini'] = gemini_adapter
    found = Engine(store, executable=chosen['renderer'], adapters=adapters, assistant=Author(assistant))
    found.configuration = chosen
    return found


# Unknown fields are refused rather than silently influencing a stage worker.
FIELDS = {
    'source': {'data', 'kind', 'name', 'selection', 'replace_id', 'acknowledge_warnings'},
    'source-import': {'capture_id', 'replace_id', 'acknowledge_warnings'},
    'team-preview': {'export_id', 'include_editable', 'source_ids', 'asset_ids'},
    'team-share': {'export_id', 'include_editable', 'source_ids', 'asset_ids','inventory_digest','expected_head','expected_claim','expected_connection','confirm_private'},
    'google-deliver': {'export_id', 'request_id', 'account', 'folder', 'reconcile'},
    'facts': {'data'}, 'stories': {'data'}, 'select': {'story_id'}, 'brand': {'data'},
    'layout': {'arrangement'}, 'image-brief': {'data', 'edit'},
    'image-start': {'brief_id', 'provider', 'request_id', 'operation', 'parent'},
    'image-cancel': {'request_id'}, 'art-direct': set(), 'build': {'request_id'}, 'compose-image': {'asset_id'},
    'suggest': {'automatic', 'fresh'}, 'edit-text': {'element_id', 'text'},
    'preview': set(), 'check': set(), 'review': {'export_id', 'observations'}, 'approve': set(),
    'export': {'draft'}, 'restore': {'revision', 'sha256'},
    'inspect-images': set(), 'revise-art': {'change', 'preserve', 'request_id'},
    'compare': {'before', 'after'}, 'repair': {'request_id'}, 'revise-story': {'story_id', 'block_id', 'instruction'},
}


def action(found, sent):
    require(isinstance(sent, dict), 'Supply one Infographic Studio action.')
    verb, ident, revision = sent.get('action'), sent.get('id'), sent.get('expected_revision')
    require(isinstance(verb, str) and verb in FIELDS
            and set(sent) <= {'action', 'id', 'expected_revision'} | FIELDS[verb],
            'Choose a supported action and only its listed fields.')
    require(isinstance(ident, str) and type(revision) is int, 'Every action needs an infographic ID and expected revision.')
    store = found.store
    # Validate the shared revision before costly or filesystem work.
    if verb == 'image-start':
        from .validation import identifier
        require(identifier(sent.get('request_id')), 'Choose an owned image request identity.')
        if (store._project(ident) / 'jobs' / sent['request_id'] / 'intent.json').exists():
            jobs = Jobs(store, found.adapters)
            jobs.intent(ident, expected_revision=revision, brief_id=sent.get('brief_id'), provider=sent.get('provider'),
                        request_id=sent['request_id'], operation=sent.get('operation', 'generate'), parent=sent.get('parent'))
            return {'state': 'existing', 'attempt_id': sent['request_id'], 'automatic_retry': False, 'recovery': jobs.recovery(ident)}
    if verb == 'google-deliver':
        from . import google_delivery
        return google_delivery.execute(store, ident, expected_revision=revision, **{k: sent[k] for k in FIELDS[verb] if k in sent})
    store.expect(store.read(ident), revision)
    if verb in ('team-preview','team-share'):
        from . import team
        method=team.preview if verb=='team-preview' else team.share
        return method(store,ident,expected_revision=revision,**{k:sent[k] for k in FIELDS[verb] if k in sent})
    if verb == 'source':
        raw = source_bytes(sent.get('data'))
        return sources.capture(store, ident, raw, kind=sent.get('kind', 'text'), name=sent.get('name', 'Pasted information'),
                               selection=sent.get('selection'), replace_id=sent.get('replace_id'), expected_revision=revision,
                               acknowledge_warnings=sent.get('acknowledge_warnings', False))
    if verb == 'source-import':
        from . import intake
        return intake.adopt(store, ident, sent.get('capture_id'), replace_id=sent.get('replace_id'),
                            expected_revision=revision, acknowledge_warnings=sent.get('acknowledge_warnings', False))
    if verb == 'facts': return evidence.adopt(store, ident, sent.get('data'), expected_revision=revision)
    if verb == 'stories': return stories.adopt(store, ident, sent.get('data'), expected_revision=revision)
    if verb == 'select': return stories.select(store, ident, sent.get('story_id'), expected_revision=revision)
    if verb == 'brand': return brand.adopt(store, ident, sent.get('data'), expected_revision=revision)
    if verb == 'layout': return scene.adopt(store, ident, expected_revision=revision, arrangement=sent.get('arrangement', 'stack'))
    if verb == 'art-direct': return found.prepare_art(ident, expected_revision=revision)
    if verb == 'inspect-images': return found.inspect_images(ident, expected_revision=revision)
    if verb == 'repair': return found.repair(ident, expected_revision=revision, request_id=sent.get('request_id'))
    if verb == 'revise-story': return found.revise_story(ident, sent.get('story_id'), sent.get('block_id'), sent.get('instruction'), expected_revision=revision)
    if verb == 'revise-art': return found.revise_art(ident, sent.get('change'), sent.get('preserve'),
                            expected_revision=revision, request_id=sent.get('request_id'))
    if verb == 'compare': return history.compare(store, ident, sent.get('before'), sent.get('after'))
    if verb == 'build': return found.build(ident, expected_revision=revision, request_id=sent.get('request_id'))
    if verb == 'image-brief': return found.image_direction(ident, sent.get('data'), edit=sent.get('edit'), expected_revision=revision)
    if verb == 'image-start':
        config = getattr(found, 'configuration', None)
        if config:
            require(sent.get('provider') == config['image_provider'], 'Change the shared assistant explicitly before selecting another image provider.')
        require(sent.get('provider') in found.adapters, 'Configure the selected image adapter and model before starting image work.')
        preflight = getattr(found.adapters[sent['provider']], 'preflight', None)
        if preflight: preflight()
        jobs = Jobs(store, found.adapters)
        jobs.intent(ident, expected_revision=revision, brief_id=sent.get('brief_id'), provider=sent.get('provider'),
                    request_id=sent.get('request_id'), operation=sent.get('operation', 'generate'), parent=sent.get('parent'))
        return jobs.execute(ident, sent['request_id'])
    if verb == 'image-cancel': return Jobs(store, found.adapters).cancel(ident, sent.get('request_id'), expected_revision=revision)
    if verb == 'compose-image': return found.compose_asset(ident, sent.get('asset_id'), expected_revision=revision)
    if verb == 'suggest':
        require(type(sent.get('automatic', False)) is bool, 'Automatic draft must be an explicit boolean choice.')
        return found.propose(ident, expected_revision=revision, automatic=sent.get('automatic', False), fresh=sent.get('fresh', False))
    if verb == 'edit-text': return found.edit_text(ident, sent.get('element_id'), sent.get('text'), expected_revision=revision)
    if verb == 'preview': return found.preview(ident, expected_revision=revision)
    if verb == 'check': return found.check(ident, expected_revision=revision)
    if verb == 'review': return found.manual_review(ident, sent.get('export_id'), sent.get('observations'), expected_revision=revision)
    if verb == 'approve': return found.approve(ident, expected_revision=revision)
    if verb == 'export':
        require(type(sent.get('draft', False)) is bool, 'Draft delivery must be an explicit boolean choice.')
        return found.preview(ident, expected_revision=revision, draft=sent.get('draft', False))
    if verb == 'restore': return history.restore(store, ident, sent.get('revision'), expected_revision=revision, fingerprint=sent.get('sha256'))
    raise Invalid('Unsupported Infographic Studio action.')
