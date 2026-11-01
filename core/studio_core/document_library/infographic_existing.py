"""Infographic Studio's approved exports, read for Add existing work to library: never changed.

What is offered
---------------
Only an infographic whose current revision is approved and has its approved files prepared:
what Infographic Studio's Prepare approved files keeps in the library (`runner/library.py`).
The workspace is marked by `.infographic-studio/workspace.json` (its owner), and each
infographic is `projects/<id>/`, its current revision named by `current.json`.

- "Approved" is read as Infographic Studio reads it (`Engine.deliveries`): a final (not
  draft) export of the current revision, made from exactly its approval and its checks,
  while the latest visual review of that page passed and every source still matches the
  bytes it was captured as.
- It is added as an Infographic, Created here, under Infographic Studio's own key,
  `infographic:<owner[:12]>-<id>`, so an infographic already kept is that same library
  document. Its text is the export's accessible text (`page.txt`).
- Its PDF (`page.pdf`) comes along only when it matches the hash the export's manifest
  recorded, the manifest that binds it to that revision and approval; otherwise only the
  text is added, with why. Nothing is rendered or exported again.
- What Infographic Studio calls it travels with it, as `native`: the infographic's ID, its
  revision and the export's ID.

Left out: infographics not approved, approved files of an earlier revision, drafts, and an
infographic whose records do not match their hashes. No record is written, no lock is
taken, no Git, network, assistant, image provider or renderer is used, and every read is
bounded and refuses links.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import reading
from .store import LIMITS, TITLE, _plain

PRODUCT = 'Infographic Studio'
MARKER = '.infographic-studio/workspace.json'
IDENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')
SHA = re.compile(r'^[0-9a-f]{64}$')
BASIS = ('brief', 'sources', 'facts', 'stories', 'selected_story', 'brand', 'scene', 'assets')
FILES = {'png': 'page.png', 'pdf': 'page.pdf', 'svg': 'page.svg', 'text': 'page.txt'}
RECORD = 2_000_000
MANIFEST = 100_000
SOURCE = 16_000_000
EXPORT = 32_000_000
ENTRIES = 2_000
NO_PDF = 'Its PDF does not match the approved export it was prepared with, so only its text is added.'


def canonical(value) -> bytes:
    """Infographic Studio's canonical JSON, which its digests are of."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def basis(project: dict) -> dict:
    return {key: digest(project.get(key)) for key in BASIS}


def owner(root: Path) -> str | None:
    """The workspace's owner, from its marker, or None when it is not one."""
    marker = reading.record(root / MARKER, 10_000) if reading.unlinked(root, MARKER) else None
    if not isinstance(marker, dict) or set(marker) != {'schema', 'product', 'owner'} \
            or type(marker['schema']) is not int or marker['schema'] != 1 \
            or marker['product'] != PRODUCT or not isinstance(marker['owner'], str) \
            or not IDENT.match(marker['owner']):
        return None
    return marker['owner']


def _file(root: Path, relative: str, limit: int) -> bytes | None:
    if not isinstance(relative, str) or not relative or relative.startswith('/') \
            or any(part in ('', '.', '..') for part in relative.split('/')) \
            or '\\' in relative or not reading.unlinked(root, relative):
        return None
    return reading.bounded(root / relative, limit)


def _project(root: Path, ident: str, held_by: str) -> dict:
    """The infographic's current revision, read as `Store.read` reads it; ValueError when
    it cannot be."""
    folder = f'projects/{ident}'
    pointer = reading.record(root / folder / 'current.json', 10_000) \
        if reading.unlinked(root, f'{folder}/current.json') else None
    if not isinstance(pointer, dict) or pointer.get('schema') != 1 or pointer.get('id') != ident \
            or type(pointer.get('revision')) is not int or pointer['revision'] < 0 \
            or not isinstance(pointer.get('sha256'), str) or not SHA.match(pointer['sha256']):
        raise ValueError('its revision pointer is invalid')
    raw = _file(root, f"{folder}/versions/{pointer['revision']}-{pointer['sha256']}.json", RECORD)
    if raw is None or reading.sha(raw) != pointer['sha256']:
        raise ValueError('its saved revision changed')
    try:
        project = json.loads(raw)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ValueError('its saved revision cannot be read') from None
    if not isinstance(project, dict) or project.get('product') != PRODUCT \
            or project.get('id') != ident or project.get('owner') != held_by \
            or project.get('revision') != pointer['revision'] \
            or not isinstance(project.get('brief'), dict) \
            or not isinstance(project.get('sources'), list) \
            or not isinstance(project.get('checks'), list):
        raise ValueError('its identity or owner does not match')
    return project


def _manifest(root: Path, ident: str, export: str) -> dict | None:
    """An export's manifest, in the shape `exports.validate_manifest` accepts, or None."""
    value = _file(root, f'projects/{ident}/exports/{export}/manifest.json', MANIFEST)
    try:
        value = json.loads(value) if value is not None else None
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    if not isinstance(value, dict) or value.get('schema') != 1 or value.get('id') != export \
            or type(value.get('revision')) is not int or value['revision'] < 0 \
            or type(value.get('draft')) is not bool or not isinstance(value.get('files'), list) \
            or len(value['files']) != 4:
        return None
    if not all(isinstance(value.get(key), str) and SHA.match(value[key])
               for key in ('scene_digest', 'checks_digest', 'approval_digest', 'measurement_sha256')):
        return None
    seen = set()
    for item in value['files']:
        kind = item.get('format') if isinstance(item, dict) else None
        if kind not in FILES or kind in seen \
                or item.get('file') != f'exports/{export}/{FILES[kind]}' \
                or not isinstance(item.get('sha256'), str) or not SHA.match(item['sha256']) \
                or type(item.get('bytes')) is not int or not 0 < item['bytes'] <= (46_000_000 if kind == 'svg' else EXPORT):
            return None
        seen.add(kind)
    return value


def _reviewed(root: Path, project: dict) -> bool:
    """`visual_review.checked`: the latest review of exactly this page passed, and the
    project's visual check is of that review."""
    jobs = root / 'projects' / project['id'] / 'jobs'
    folders, _ = reading.folders(jobs, lambda name: name.startswith('visual_'), ENTRIES)
    wanted, scene, records = basis(project), digest(project.get('scene')), []
    for folder in folders:
        saved = reading.record(folder / 'review.json', 100_000)
        if saved and saved.get('basis') == wanted and saved.get('scene_digest') == scene:
            sequence = saved.get('sequence', 0)
            records.append((sequence if type(sequence) is int else 0, folder.name, saved))
    review = max(records, key=lambda item: item[:2])[2] if records else None
    visual = next((one for one in project['checks'] if isinstance(one, dict) and one.get('kind') == 'visual'), None)
    return bool(review and review.get('status') == 'passed' and review.get('observations')
                and not any(isinstance(one, dict) and one.get('blocking') for one in review.get('findings', []))
                and visual and visual.get('status') == 'passed'
                and visual.get('review_digest') == digest(review))


def _sources_intact(root: Path, project: dict) -> bool:
    """Every source still matches the bytes it was captured as (`sources.read`)."""
    for source in project['sources']:
        if not isinstance(source, dict):
            return False
        raw = _file(root, f"projects/{project['id']}/{source.get('file')}", SOURCE)
        if raw is None or len(raw) != source.get('bytes') or reading.sha(raw) != source.get('sha256'):
            return False
        if source.get('kind') == 'research' \
                and reading.sha(raw) != (source.get('provenance') or {}).get('verified_archive_sha256'):
            return False
        if 'normalized_file' in source:
            normalized = _file(root, f"projects/{project['id']}/{source['normalized_file']}", SOURCE)
            if normalized is None or reading.sha(normalized) != source.get('normalized_sha256'):
                return False
    return True


def _approved(root: Path, project: dict) -> dict | None:
    """The approved export of the current revision (`Engine.deliveries`' approved_current,
    as `library._approved` chooses it), or None."""
    if project.get('approval') is None:
        return None
    exports = root / 'projects' / project['id'] / 'exports'
    folders, _ = reading.folders(exports, lambda name: name.startswith('e_') and bool(IDENT.match(name)), ENTRIES)
    found = [one for one in (_manifest(root, project['id'], folder.name) for folder in folders) if one]
    found.sort(key=lambda one: (one['revision'], not one['draft']), reverse=True)
    approval, checks = digest(project['approval']), digest(project['checks'])
    candidates = [one for one in found if not one['draft'] and one['revision'] == project['revision']
                  and one['approval_digest'] == approval and one['checks_digest'] == checks]
    if not candidates or not _reviewed(root, project) or not _sources_intact(root, project):
        return None
    return candidates[0]


def _candidate(root: Path, held_by: str, ident: str, content: bool
               ) -> tuple[dict | None, str | None, bool]:
    """(One approved infographic, None, True), (None, why it is left out, True), or (None,
    None, False) for one that is not approved."""
    try:
        project = _project(root, ident, held_by)
    except (ValueError, KeyError, TypeError, RecursionError) as refusal:
        return None, f'“{ident}” was left out: {str(refusal).rstrip(".")}.', True
    title = _plain(project['brief'].get('title'), TITLE) or 'Untitled'
    export = _approved(root, project)
    if export is None:
        return None, None, False
    items = {item['format']: item for item in export['files']}
    folder = f"projects/{ident}/"
    text_bytes = _file(root, folder + items['text']['file'], EXPORT)
    if text_bytes is None or reading.sha(text_bytes) != items['text']['sha256']:
        return None, (f'“{title[:120]}” was left out: its approved files no longer match '
                      'their export. Prepare approved files again in Infographic Studio.'), True
    try:
        text = text_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return None, f'“{title[:120]}” was left out: its text could not be read.', True
    if not text.strip() or len(text_bytes) > LIMITS['text']:
        return None, f'“{title[:120]}” was left out: it has no text the library can keep.', True
    pdf, pdf_sha, why = None, None, NO_PDF
    path = root / (folder + items['pdf']['file'])
    if items['pdf']['bytes'] <= LIMITS['pdf'] and reading.unlinked(root, folder + items['pdf']['file']):
        if content:
            data = reading.bounded(path, LIMITS['pdf'])
            sha = reading.sha(data) if data is not None else None
        else:
            data, sha = None, reading.digest(path, LIMITS['pdf'])
        if sha == items['pdf']['sha256']:
            pdf, pdf_sha, why = data, sha, None
    native = {'studio': 'infographic', 'record': 'approved-export', 'infographic': ident,
              'revision': export['revision'], 'export': export['id']}
    return {'key': f'infographic:{held_by[:12]}-{ident}', 'studio': 'infographic',
            'kind': 'infographic', 'origin': 'created', 'title': title, 'author': None,
            'text': text if content else None, 'original': None,
            'markdown_sha': reading.sha(text.encode('utf-8')), 'original_sha': None,
            'pdf': pdf, 'pdf_sha': pdf_sha, 'pdf_note': why, 'filename': None,
            'project': {'id': ident, 'title': project['brief'].get('title'),
                        'revision': export['revision']},
            'native': native, 'gaps': [why] if why else [], 'note': 'Approved infographic',
            'folder': root / 'projects' / ident, 'ident': ident}, None, True


def _checked(root: Path, held_by: str, ident: str, content: bool):
    try:
        return _candidate(root, held_by, ident, content)
    except (TypeError, ValueError, AttributeError, KeyError, OSError, RecursionError):
        return None, (f'“{ident}” was left out: its record is not in a shape Infographic '
                      'Studio saves.'), True


def load(root, candidate: dict) -> dict:
    """The candidate read again with its text and PDF, refused when either is no longer
    what the preview read."""
    root = Path(root)
    held_by = owner(root)
    found = _checked(root, held_by, candidate['ident'], True)[0] if held_by else None
    if not found or any(found[name] != candidate[name] for name in
                        ('key', 'title', 'markdown_sha', 'original_sha', 'pdf_sha')):
        raise ValueError(f'“{candidate["title"][:120]}” changed in Infographic Studio after '
                         'the preview.')
    return found


def scan(root, content: bool = False) -> dict:
    """{'candidates', 'gaps', 'more', 'readable'}: the workspace's approved infographics,
    with the hashes of their text and PDF as read now, and what was left out and why."""
    root = Path(root)
    held_by = owner(root)
    if held_by is None:
        return {'candidates': [], 'gaps': ['This folder is not an Infographic Studio workspace '
                                           'this computer can read, so nothing in it was offered.'],
                'more': False, 'readable': False}
    folders, more = reading.folders(root / 'projects', IDENT.match, ENTRIES)
    candidates, gaps, waiting = [], [], 0
    for folder in folders:
        found, why, finished = _checked(root, held_by, folder.name, content)
        if found:
            candidates.append(found)
        elif why:
            gaps.append(why)
        elif not finished:
            waiting += 1
    if waiting:
        gaps.append(f'{waiting} infographic{" is" if waiting == 1 else "s are"} not approved '
                    f'with {"its" if waiting == 1 else "their"} files prepared, so '
                    f'{"it is" if waiting == 1 else "they are"} not offered.')
    if more:
        gaps.append(f'Only the first {ENTRIES} infographics were looked at.')
    return {'candidates': candidates, 'gaps': gaps, 'more': more, 'readable': True}
