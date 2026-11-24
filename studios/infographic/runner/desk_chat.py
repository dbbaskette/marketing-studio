"""Checked, bounded conversation operations on Infographic Studio's desk.

The companion conversation (the Infographic Studio skill) works on an infographic the way
Presentation Studio's does on a deck: it reads the desk (`show`), asks for the exact inputs and
instructions of one target (`context`, with an `expected_basis`), and saves what it wrote
(`submit`). A submission is checked by the same native rules as the page's own actions
(evidence.adopt, stories.adopt, image_brief.make) and lands only on the exact inputs its
context named; anything changed since is refused, saying so. Nothing here approves, chooses a
story, builds, renders, delivers, starts research or calls an assistant or image provider.

Targets: 'facts', 'stories', 'story:<id>' (one story revised) and 'art-direction'. Work held
out of date is shown (`stale`) but only the person keeps it as it is, on the page; the
conversation can make a part again, never clear its mark. Each submission is recorded beside
the infographic (jobs/conversation_*/submission.json, immutable) and the newest are listed by
`show`.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import secrets

from studio_core.activity_log import now

from . import evidence, progress, sources, stories
from .contracts import Invalid, basis, canonical, digest, stale_parts
from .validation import require
from .workspace import _read

KINDS = {'facts': 'facts', 'stories': 'stories', 'story': 'story', 'art-direction': 'art-direction'}
SHOWN = 20          # conversation submissions `show` lists, newest first
READ = 200          # folders read to find them, newest first
CHANGED = 'The infographic or its inputs changed. Read desk context again before saving.'
MAX_PAYLOAD = 2_000_000
MAX_SOURCE_TEXT = 120_000
PROMPTS = Path(__file__).parent / 'prompts'


def _target(project, target):
    """The target's kind and its subject: a story ID or an out-of-date part."""
    require(isinstance(target, str) and 0 < len(target) <= 100, 'Name one desk target.')
    head, _, subject = target.partition(':')
    require(head in KINDS and bool(subject) == (head == 'story'),
            'Choose facts, stories, story:<id> or art-direction. Only the person keeps out-of-date work as it is, on the page.')
    if head == 'story':
        require(any(s['id'] == subject for s in project['stories']), 'Choose an existing story.')
    if head == 'art-direction':
        require(project['scene'] is not None and bool(project['scene'].get('art_regions')),
                'Build a page that plans artwork before writing its art direction.')
    return head, subject


def _basis(project, target):
    return digest({'target': target, 'revision': project['revision'], 'basis': basis(project),
                   'stale': stale_parts(project)})


def _submissions(store, ident):
    root = store._project(ident) / 'jobs'
    found = []
    folders = []
    if root.is_dir() and not root.is_symlink():
        for folder in root.glob('conversation_*'):
            try:
                folders.append((folder.stat().st_mtime, folder))
            except OSError:
                continue
    for _, folder in sorted(folders, reverse=True)[:READ]:
        try:
            found.append(json.loads(_read(store.root, f'projects/{ident}/jobs/{folder.name}/submission.json', 20_000)))
        except (Invalid, ValueError):
            continue
    return sorted(found, key=lambda one: one.get('at') or '', reverse=True)[:SHOWN]


def show(store, ident):
    """The desk as the conversation reads it: what the page shows, with nothing started."""
    project = store.read(ident)
    selected = next((s for s in project['stories'] if s['id'] == project['selected_story']), None)
    return {'id': ident, 'revision': project['revision'], 'brief': project['brief'],
            'sources': [{'id': s['id'], 'name': s.get('name'), 'kind': s['kind'], 'characters': s['characters']}
                        for s in project['sources']],
            'facts': project['facts'], 'stories': project['stories'], 'selected_story': selected,
            'brand': (project['brand'] or {}).get('identity'),
            'page': None if project['scene'] is None else {
                'elements': len(project['scene']['elements']),
                'art_regions': [r['id'] for r in project['scene'].get('art_regions', [])]},
            'image_briefs': len(project['image_briefs']), 'stale': stale_parts(project),
            'approved': project['approval'] is not None, 'readiness': progress.readiness(project),
            'targets': _targets(project), 'submissions': _submissions(store, ident)}


def _targets(project):
    found = []
    if project['sources']:
        found.append('facts')
    if project['facts']:
        found.append('stories')
    found += ['story:' + s['id'] for s in project['stories']]
    if project['scene'] is not None and project['scene'].get('art_regions'):
        found.append('art-direction')
    return found


def context(store, ident, target):
    """The exact inputs and native instructions for one target, with the basis to save against."""
    project = store.read(ident)
    head, subject = _target(project, target)
    inputs = {'brief': project['brief']}
    instructions = []
    if head == 'facts':
        captured = [{'id': s['id'], 'name': s.get('name'), 'text': sources.read(store, project, s)}
                    for s in project['sources']]
        require(sum(len(one['text']) for one in captured) <= MAX_SOURCE_TEXT,
                'The captured sources exceed one planning step. Choose a smaller explicit source scope.')
        inputs['sources'] = captured
        instructions.append((PROMPTS / 'evidence.md').read_text())
        returns = 'payload {"facts": [...]}: located facts, each quoting its source exactly.'
    elif head in ('stories', 'story'):
        inputs['facts'] = project['facts']
        instructions.append((PROMPTS / 'stories.md').read_text())
        if head == 'story':
            inputs['story'] = next(s for s in project['stories'] if s['id'] == subject)
            returns = 'payload {"story": {...}}: the whole revised story, with the same id.'
        else:
            returns = 'payload {"stories": [...]}: one to three distinct stories.'
    else:
        story = next((s for s in project['stories'] if s['id'] == project['selected_story']), None)
        inputs.update(story=story, brand=project['brand'], scene=project['scene'], facts=project['facts'])
        instructions.append((PROMPTS / 'image-brief.md').read_text())
        returns = 'payload {"direction": {...}}: the art direction, as the image-brief instructions describe it.'
    return {'id': ident, 'target': target, 'kind': KINDS[head], 'inputs': inputs,
            'instructions': '\n\n'.join(instructions), 'returns': returns,
            'expected_basis': _basis(project, target),
            'never': 'Saving never approves, chooses a story, builds, delivers or starts an assistant or image provider.'}


def submit(engine, ident, request):
    """Save what the conversation wrote for one target, on exactly the inputs its context named."""
    require(isinstance(request, dict) and set(request) == {'kind', 'target', 'expected_basis', 'payload'}
            and isinstance(request['payload'], dict),
            'Submit kind, target, expected_basis and payload together.')
    require(len(canonical(request['payload'])) <= MAX_PAYLOAD, 'The submission is too large.')
    store = engine.store
    project = store.read(ident)
    head, subject = _target(project, request['target'])
    require(request['kind'] == KINDS[head], 'The submission kind does not match its target.')
    if request['expected_basis'] != _basis(project, request['target']):
        raise Invalid(CHANGED)
    payload, revision = request['payload'], project['revision']
    if head == 'facts':
        require(set(payload) == {'facts'}, 'Submit {"facts": [...]}.')
        saved = evidence.adopt(store, ident, payload['facts'], expected_revision=revision, remade=False)
    elif head == 'stories':
        require(set(payload) == {'stories'}, 'Submit {"stories": [...]}.')
        saved = stories.adopt(store, ident, payload['stories'], expected_revision=revision, remade=False)
    elif head == 'story':
        require(set(payload) == {'story'} and isinstance(payload['story'], dict)
                and payload['story'].get('id') == subject, 'Submit {"story": {...}} keeping its id.')
        with store.locked():
            current = store.read(ident)
            store.expect(current, revision)
            proposals = [deepcopy(payload['story']) if s['id'] == subject else s for s in current['stories']]
            verified = stories.verify(current, proposals)
            # A revised story is chosen again by the person; the same story saved again changes
            # nothing (and makes nothing current).
            saved = current if verified == current['stories'] else store.change_locked(
                current, {'stories': verified, 'selected_story': None})
    else:
        require(set(payload) == {'direction'} and isinstance(payload['direction'], dict),
                'Submit {"direction": {...}}.')
        saved = engine.image_direction(ident, payload['direction'], expected_revision=revision)
    record = {'schema': 1, 'kind': request['kind'], 'target': request['target'], 'by': 'conversation',
              'basis': request['expected_basis'], 'revision': saved['revision'], 'at': now()}
    with store.locked():
        store.write_blob(ident, 'jobs/conversation_' + secrets.token_hex(8) + '/submission.json', canonical(record))
    return show(store, ident)
