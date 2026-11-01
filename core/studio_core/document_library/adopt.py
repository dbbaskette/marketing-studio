"""Add existing work to library: a preview of what the studios' known workspaces hold, then
an import only when the person confirms that preview.

What a caller needs to know
---------------------------
    adopt.preview(workspaces)              # nothing is written, and the library is not made
    adopt.confirm(workspaces, signature)   # adds what that preview offered, or refuses

- `workspaces` is {studio: {'root': folder} or None}: the workspace each studio remembers
  in its own records (Marketing Studio's `workspaces.remembered`). Only those folders are
  read: no home folder is searched, no studio is started or set up, and nothing in a
  workspace is moved, rewritten or regenerated.
- Each studio's existing work is read by its own adapter, which offers only finished work:
  Blog Studio's team library (blog_existing.py), Presentation Studio's delivered decks
  (presentation_existing.py), Training Studio's learner guides and briefs marked ready
  (training_existing.py) and Infographic Studio's approved exports
  (infographic_existing.py).
- The preview gives each workspace, each candidate with its formats and gaps, and whether
  it is new, a new revision of what the library has, or already there. Its `signature`
  binds the confirm to it: when anything the preview offered changed since, the confirm
  refuses and nothing is added, so the person previews again.
- Adding uses each studio's own library key (`blog:<blog id>`, `blog:reference.<source id>`,
  a deck's key in `sources/library.json`, `training:<folder>-<part>.<material>`,
  `infographic:<owner[:12]>-<id>`), so adding again adds nothing, and finishing, delivering
  or marking it ready later reuses the document it was added as. What the studio calls each
  item (its ID, revision, roles, voice and style) is recorded with the revision it became.
  A failure is reported per item and the rest are still added; trying again adds only what
  is missing.
- A PDF is added only when the adapter checked it against the exact revision it was made
  from (see `Library.adopt`); otherwise the item says why it has none. Work the library
  already keeps with a PDF is not added again without one.
- Nothing is shared with a team, sent to an assistant or read from the network.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from studio_core import studios_config

from . import blog_existing, infographic_existing, presentation_existing, training_existing
from .store import FORMATS, KINDS, ORIGINS, STUDIOS, LibraryError, opened

ADAPTERS = {'blog': blog_existing, 'presentation': presentation_existing,
            'training': training_existing, 'infographic': infographic_existing}
LIMIT = 500          # candidates one workspace offers in one preview
SHOWN = 200          # candidate rows a preview lists
FOUND = {            # what a workspace's candidates are, one and many
    'blog': ('item in its team library', 'items in its team library'),
    'presentation': ('delivered deck', 'delivered decks'),
    'training': ('learner guide or brief marked ready', 'learner guides and briefs marked ready'),
    'infographic': ('approved infographic', 'approved infographics'),
}
CHANGED = ('Something the preview offered changed since it was made, so nothing was added. '
           'Preview again, then add.')


def _studios(workspaces) -> dict:
    if not isinstance(workspaces, dict) or set(workspaces) - set(STUDIOS):
        raise LibraryError('Name each studio’s workspace.')
    return workspaces


def _scan(workspaces, content=False) -> tuple[list[dict], list[dict]]:
    """(each workspace's row, every candidate) for the known workspaces."""
    rows, candidates = [], []
    for studio in ('blog', 'presentation', 'training', 'infographic'):
        label = STUDIOS[studio]
        found = _studios(workspaces).get(studio)
        root = Path(found['root']) if isinstance(found, dict) and isinstance(found.get('root'), str) \
            and Path(found['root']).is_absolute() else None
        if root is None:
            rows.append({'studio': studio, 'label': label, 'state': 'none', 'shown': None,
                         'summary': f'{label} has no workspace on this computer yet.',
                         'gaps': [], 'count': 0})
            continue
        shown = studios_config.shown(root)
        adapter = ADAPTERS[studio]
        if not root.is_dir() or root.is_symlink():
            rows.append({'studio': studio, 'label': label, 'state': 'missing', 'shown': shown,
                         'summary': f'{label}’s workspace at {shown} is not there now, so '
                                    'nothing in it was offered.', 'gaps': [], 'count': 0})
            continue
        scanned = adapter.scan(root, content=content)
        offered = scanned['candidates'][:LIMIT]
        gaps = list(scanned['gaps'])
        if len(scanned['candidates']) > LIMIT:
            gaps.append(f'Only the first {LIMIT} items are offered at once. Add them, then '
                        'preview again for the rest.')
        for candidate in offered:
            candidate['root'] = root
            for part in ('pdf', 'pdf_sha', 'pdf_note'):
                candidate.setdefault(part, None)     # an adapter whose work has no PDF
        candidates.extend(offered)
        one, many = FOUND[studio]
        rows.append({'studio': studio, 'label': label,
                     'state': 'found' if scanned['readable'] else 'unreadable', 'shown': shown,
                     'summary': f'{len(offered)} {one if len(offered) == 1 else many}.'
                     if scanned['readable'] else gaps[0],
                     'gaps': gaps[:40] if scanned['readable'] else gaps[1:40],
                     'count': len(offered)})
    return rows, candidates


def _states(candidates) -> None:
    """Mark each candidate new, a new revision of a library document, or already kept."""
    library = opened()
    held = library.keyed([one['key'] for one in candidates]) if library else {}
    # A file the studio already kept as an upload (Keep in library) is the same file: it is
    # not offered again under the team library's key.
    uploads = {studio: library.uploaded(studio) for studio in {one['studio'] for one in candidates}} \
        if library else {}
    for one in candidates:
        found = held.get(one['key'])
        copy = uploads.get(one['studio'], {}).get(one['original_sha']) if one['original_sha'] else None
        if found is None and copy:
            one['state'], one['document'] = 'kept', None
            one['gaps'] = ['Kept in the library when it was uploaded.', *one['gaps']]
        elif found is None:
            one['state'] = 'new'
        elif found['whole'] and found['title'] == one['title'] \
                and found['markdown'] == one['markdown_sha'] \
                and found['original'] == one['original_sha'] \
                and one['pdf_sha'] in (None, found.get('pdf')):
            # No checked PDF here now (a deck's preview cleared away since, say) never takes
            # away the PDF the library already keeps of the same text: it is the same work.
            one['state'] = 'kept'
            if one['pdf_sha'] is None and found.get('pdf'):
                one['held_pdf'] = True
                one['gaps'] = [gap for gap in one['gaps'] if gap != one['pdf_note']]
        else:
            one['state'] = 'changed'
        if not copy or found is not None:
            one['document'] = found
        if found and found.get('hidden'):
            # Adding it again keeps it hidden: only Restore brings it back.
            one['gaps'] = ['Removed from the library. Restore it under Show hidden to use it again.',
                           *one['gaps']]


def _signature(candidates) -> str:
    wanted = sorted([one['key'], one['title'], one['markdown_sha'], one['original_sha'],
                     one['pdf_sha']] for one in candidates if one['state'] != 'kept')
    return hashlib.sha256(json.dumps(wanted).encode()).hexdigest()


def _shown(one) -> dict:
    formats = (['markdown'] if one['markdown_sha'] else []) \
        + (['pdf'] if one['pdf_sha'] or one.get('held_pdf') else []) \
        + (['original'] if one['original_sha'] else [])
    found = one.get('document')
    return {'title': one['title'], 'studio_label': STUDIOS[one['studio']],
            'kind_label': KINDS[one['kind']], 'origin_label': ORIGINS[one['origin']],
            'note': one['note'], 'author': one['author'],
            'formats': formats, 'format_labels': [FORMATS[name] for name in formats],
            'readable': bool(one['markdown_sha']), 'gaps': one['gaps'][:6], 'state': one['state'],
            'state_label': {'new': 'Will be added',
                            'changed': f'Adds revision {found["revision"] + 1}' if found else 'Will be added',
                            'kept': 'Already in the library'}[one['state']]}


def preview(workspaces) -> dict:
    """What Add existing work to library would add. Nothing is written."""
    rows, candidates = _scan(workspaces)
    _states(candidates)
    adding = [one for one in candidates if one['state'] != 'kept']
    listed = sorted(candidates, key=lambda one: (one['state'] == 'kept', one['title'].casefold()))
    return {'workspaces': rows, 'items': [_shown(one) for one in listed[:SHOWN]],
            'total': len(candidates), 'adding': len(adding),
            'new': sum(one['state'] == 'new' for one in candidates),
            'changed': sum(one['state'] == 'changed' for one in candidates),
            'kept': sum(one['state'] == 'kept' for one in candidates),
            'signature': _signature(candidates)}


def confirm(workspaces, signature) -> dict:
    """Add what the preview with this signature offered: {'added', 'revised', 'unchanged',
    'failed': [{'title', 'problem'}], 'location'}. Refused, adding nothing, when the
    workspaces no longer match that preview."""
    if not isinstance(signature, str) or len(signature) != 64:
        raise LibraryError('Preview what would be added first.')
    _, candidates = _scan(workspaces)
    _states(candidates)
    if _signature(candidates) != signature:
        raise LibraryError(CHANGED)
    adding = [one for one in candidates if one['state'] != 'kept']
    done = {'added': 0, 'revised': 0, 'unchanged': len(candidates) - len(adding), 'failed': []}
    if not adding:
        return {**done, 'location': None}
    library = opened(create=True)      # this confirm is an explicit use
    for one in adding:
        try:
            found = ADAPTERS[one['studio']].load(one['root'], one)
            # Only a PDF the adapter checked against the revision it was made from is saved.
            pdf = {'state': 'saved', 'data': found['pdf']} if found.get('pdf') is not None \
                else {'state': 'needs-export', 'reason': found['pdf_note']} \
                if isinstance(found.get('pdf_note'), str) else None
            kept = library.adopt(found['key'], found['studio'], found['kind'], found['origin'],
                                 found['title'], text=found['text'], original=found['original'],
                                 filename=found['filename'], project=found['project'],
                                 author=found['author'], native=found['native'],
                                 gaps=found['gaps'], pdf=pdf)
        except (LibraryError, ValueError, OSError) as failure:
            done['failed'].append({'title': one['title'],
                                   'problem': str(failure)[:300] or 'It could not be added.'})
            continue
        if not kept['changed']:
            done['unchanged'] += 1
        elif kept['revision'] == 1:
            done['added'] += 1
        else:
            done['revised'] += 1
    return {**done, 'location': studios_config.shown(library.root)}
