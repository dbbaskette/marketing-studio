"""Verified Harness Research in the Document Library: kept once it passes, and given back.

What a caller needs to know
---------------------------
    from studio_core.document_library import research as library_research
    kept = library_research.keep_research(None, studio='training', project='restart-1a2b3c',
                                          case=root / 'research', title='Restart: research')
    # {'state': 'kept', 'key', 'document', 'revision', 'changed'}, or
    # {'state': 'refused' | 'failed', 'key', 'problem'}. It never raises.
    found = library_research.research_bundle(None, 'restart-research-0a1b2c3d4e', 2,
                                             root / 'imported-research')
    # {'id', 'revision', 'title', 'studio', 'folder', 'files', 'digest'}: the bundle written
    # whole into that folder and checked; LibraryError says why when it is refused.

What is kept
------------
A studio keeps research only once Harness Research verified it: `case` must pass
`research_contract.read_bundle` (every file's hash, the review of that exact digest). The
item's readable text is the bundle's `report.md`, so every studio's Add from library can
already take it as a source through `snapshot`, which gives a research item as that report
alone (`name` `<title>.md`, no original). Its bundle is kept beside it as one archive
(`original.zip`, at most LIMITS['research'], 16 MB zipped): `output.json` and every file its
manifest names (report, brief, evidence, facts and the source captures), each checked against
its manifest hash as it is archived, and nothing else. Keeping the same research again (the
same title, report and output.json) adds no revision.

Its key is `<studio>:<project>:research`. Finished work's key (`<studio>:<project>`) never has
a second colon, so a project's research and its finished work are two documents.

Given back (`Library.research_archive`, then `research_bundle`), the archive is written into a
folder the caller names, which must be empty, or not there yet inside a folder that is: only
output.json and the files its manifest names are written, each name is checked to stay inside
it, no link is written, and the folder is then read with `read_bundle` again, so a changed
bundle is refused and what was written is cleared.
Nothing here starts research, an assistant or a provider, or uses the network.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path

from studio_core import research_contract as contract

from .store import IDENT, LIMITS, Library, LibraryError, opened

PROJECT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$')
STUDIOS = ('blog', 'presentation', 'training', 'infographic')
FILES = 1_000                   # files one bundle may hold, as research_contract.case_files allows
UNPACKED = 64_000_000           # bytes one bundle may hold before it is archived, or once unpacked
STAMP = (1980, 1, 1, 0, 0, 0)   # every archived file's time: the same bundle, the same archive
REFUSED = ('This research was not kept in the Document Library because it has not passed '
           'verification: {why}')
NOT_KEPT = 'The Document Library could not keep this research. It is still saved in the project.'
UNREAD = ('The research files could not be read, so the Document Library did not keep them. '
          'The research is still saved in the project.')
NOT_RESEARCH = ('That document is not research the library kept, so it has no research bundle '
                'to import.')
CHANGED = 'The research bundle in the library changed after it was kept, so it was not imported.'


def research_key(studio, project) -> str:
    """The library key of a project's research: `<studio>:<project>:research`."""
    ident = project.get('id') if isinstance(project, dict) else project
    if studio not in STUDIOS or not isinstance(ident, str) or not PROJECT.match(ident):
        raise LibraryError('Name the research by its studio and project.')
    return f'{studio}:{ident}:research'


def _folder(case) -> Path:
    """The folder holding the bundle: `case` itself when it holds output.json (a published
    bundle, such as a project's `research/`), else its case's output root."""
    case = Path(case)
    if (case / 'output.json').is_file() and not (case / 'output.json').is_symlink():
        return case
    return contract.output_root(case)


def _title(given, report: str) -> str:
    if isinstance(given, str) and given.strip():
        return given
    for line in report.splitlines():
        if line.startswith('# ') and line[2:].strip():
            return line[2:].strip()
    return 'Research'


def _plain_file(folder: Path, name: str) -> bytes:
    path = contract.inside(folder, name)
    if path.is_symlink() or not path.is_file():
        raise ValueError('The research bundle is missing a file it names.')
    return path.read_bytes()


def archive(folder) -> tuple[bytes, str, dict, dict, str]:
    """(the bundle as one archive, its report's text, facts, manifest, the SHA-256 of its
    output.json) of a verified bundle. read_bundle checks it first; then the exact
    output.json bytes archived are the ones parsed here, and every file archived is checked
    against its manifest entry as it is read, so nothing that changed in between is kept.
    Refused with ValueError when it does not pass, or is too large."""
    folder = Path(folder)
    facts, verified = contract.read_bundle(folder)
    raw = _plain_file(folder, 'output.json')
    manifest = json.loads(raw.decode('utf-8'))
    if manifest != verified:
        raise ValueError('Research evidence or output changed. Revise and review it again.')
    wanted = {entry['file']: entry['sha256'] for entry in manifest['artifacts']}
    if len(wanted) + 1 > FILES:
        raise ValueError('The research bundle has more files than the library keeps.')
    buffer, total, report = io.BytesIO(), len(raw), None
    with zipfile.ZipFile(buffer, 'w') as packed:
        for name in sorted({'output.json', *wanted}):
            data = raw if name == 'output.json' else _plain_file(folder, name)
            if name != 'output.json' and hashlib.sha256(data).hexdigest() != wanted[name]:
                raise ValueError('Research evidence or output changed. Revise and review it again.')
            total += len(data) if name != 'output.json' else 0
            if total > UNPACKED:
                raise ValueError('The research bundle is larger than the library keeps.')
            if name == 'report.md':
                report = data.decode('utf-8')
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            packed.writestr(info, data)
    if report is None:
        raise ValueError('The research bundle is incomplete.')
    return buffer.getvalue(), report, facts, manifest, hashlib.sha256(raw).hexdigest()


def keep_research(library=None, *, studio, project, case, title=None, author=None) -> dict:
    """Keep a project's verified research in the Document Library. Never raises.

    `library` is an opened Library, or None to open (and, on first use, make) the shared one.
    `studio` is the studio that ran it (blog, presentation, training or infographic).
    `project` is the project's ID, the text after `<studio>:` in its finished-work key, or
    {'id', 'title', 'revision'}. `case` is the folder holding the published bundle (whose
    output.json read_bundle reads, such as the project's `research/`), or its research case
    folder. `title` defaults to the report's first heading.

    Returns {'state': 'kept', 'key', 'document', 'revision', 'changed'}; {'state':
    'refused', 'key', 'problem'} when the bundle does not pass verification (nothing is kept);
    or {'state': 'failed', 'key', 'problem'} when its files could not be read or the library
    could not keep it."""
    done = {'key': None}
    try:
        done['key'] = research_key(studio, project)
    except LibraryError as failure:
        return {**done, 'state': 'failed', 'problem': str(failure)}
    try:
        bundle, report, _facts, manifest, manifest_sha = archive(_folder(case))
    except OSError as failure:
        # The files could not be read (missing, permissions, a disk error): not a verdict on
        # the research, so it is a failure to keep, not a refusal.
        said = str(failure.strerror or failure).lower() if failure.strerror or str(failure) else ''
        return {**done, 'state': 'failed', 'problem': UNREAD + (f' ({said})' if said else '')}
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError) as failure:
        why = str(failure)[:300] if isinstance(failure, ValueError) and str(failure) else 'it could not be read.'
        return {**done, 'state': 'refused', 'problem': REFUSED.format(why=why)}
    except Exception:       # research stands whatever happens here
        return {**done, 'state': 'refused', 'problem': REFUSED.format(why='it could not be read.')}
    try:
        library = library if library is not None else opened(create=True)
        held = project if isinstance(project, dict) else {'id': project}
        kept = library.retain_research(
            key=done['key'], studio=studio, title=_title(title, report), text=report, bundle=bundle,
            project=held, author=author,
            research={'owner': manifest.get('owner'), 'digest': manifest.get('digest'),
                      'status': manifest.get('status'), 'files': 1 + len(manifest['artifacts']),
                      'manifest_sha256': manifest_sha})
        return {**done, 'state': 'kept', 'document': kept['document'], 'revision': kept['revision'],
                'changed': kept['changed']}
    except Exception as failure:     # research stands whatever the library does
        known = isinstance(failure, (LibraryError, OSError))
        return {**done, 'state': 'failed', 'problem': (str(failure)[:300] if known else '') or NOT_KEPT}


def _members(packed: zipfile.ZipFile) -> list:
    """The archive's files, each a plain file with a confined name, and only output.json and
    the files its manifest names: anything else in the archive refuses the whole of it."""
    infos, seen, total = packed.infolist(), set(), 0
    if len(infos) > FILES + 1:
        raise LibraryError(CHANGED)
    for info in infos:
        name = info.filename
        parts = name.split('/')
        kind = (info.external_attr >> 16) & 0o170000
        if (not name or '\\' in name or name.startswith('/') or info.is_dir()
                or any(part in ('', '.', '..') for part in parts) or name in seen
                or (kind and kind != stat.S_IFREG)):
            raise LibraryError(CHANGED)
        seen.add(name)
        total += info.file_size
        if total > UNPACKED:
            raise LibraryError(CHANGED)
    if 'output.json' not in seen or 'report.md' not in seen:
        raise LibraryError(CHANGED)
    try:
        manifest = json.loads(packed.read('output.json').decode('utf-8'))
        listed = {'output.json', *(entry['file'] for entry in manifest['artifacts'])}
    except (ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile):
        raise LibraryError(CHANGED) from None
    if seen != listed:
        raise LibraryError(CHANGED)
    return infos


def research_bundle(library, ident, revision, destination) -> dict:
    """Write one research revision's bundle into `destination` and check it, for a studio
    importing it. `library` is an opened Library, or None for the shared one. `ident` is a
    library document ID and `revision` a whole number. `destination` is an absolute folder
    that is empty, or not there yet in a folder that is: only `destination` itself is made.

    The kept archive and report are checked against their hashes first
    (`Library.research_archive`), then every name in the archive (only output.json and the
    files its manifest names), and then the written folder passes read_bundle, so every file
    matches its manifest hash and its review. On any refusal, what was written is removed and
    LibraryError says why. Returns {'id', 'revision', 'title', 'studio', 'folder', 'files',
    'digest'}."""
    if not isinstance(ident, str) or not IDENT.match(ident) or type(revision) is not int \
            or not 1 <= revision <= LIMITS['revisions']:
        raise LibraryError('Choose a research document in the library by its ID and revision.')
    if library is None:
        library = opened()
        if library is None:
            raise LibraryError('The Document Library has not been made on this computer yet.')
    if not isinstance(library, Library):
        raise LibraryError('Open the Document Library first.')
    target = Path(destination) if isinstance(destination, (str, Path)) else None
    if target is None or not target.is_absolute():
        raise LibraryError('Name an absolute folder to import the research into.')
    found = library.research_archive(ident, revision)
    if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise LibraryError('Import research into a new or empty folder; nothing was written.')
    if not target.exists() and (target.parent.is_symlink() or not target.parent.is_dir()):
        raise LibraryError('Import research into a folder whose parent folder is already there; '
                           'nothing was written.')
    made = not target.exists()
    try:
        with zipfile.ZipFile(io.BytesIO(found['archive'])) as packed:
            infos = _members(packed)
            if made:
                target.mkdir(mode=0o700)
            for info in infos:
                data = packed.read(info)     # its CRC is checked as it is read
                if len(data) != info.file_size:
                    raise LibraryError(CHANGED)
                contract.write(target, info.filename, data)
        report = contract.inside(target, 'report.md').read_bytes()
        if hashlib.sha256(report).hexdigest() != found['content_sha256']:
            raise LibraryError(CHANGED)
        _facts, manifest = contract.read_bundle(target)
    except LibraryError:
        _clear(target, made)
        raise
    except (zipfile.BadZipFile, ValueError, OSError, KeyError, TypeError, AttributeError) as failure:
        _clear(target, made)
        said = str(failure) if isinstance(failure, ValueError) and not isinstance(failure, zipfile.BadZipFile) else ''
        raise LibraryError(f'{CHANGED} {said}'.strip()[:400]) from None
    return {'id': found['id'], 'revision': found['revision'], 'title': found['title'],
            'studio': found['studio'], 'folder': str(target),
            'files': sorted(info.filename for info in infos), 'digest': manifest.get('digest')}


def _clear(target: Path, made: bool) -> None:
    """Take away what an import wrote: the folder it made, or what it put in an empty one."""
    if not target.is_dir() or target.is_symlink():
        return
    if made:
        shutil.rmtree(target, ignore_errors=True)
        return
    for child in target.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


__all__ = ['FILES', 'UNPACKED', 'archive', 'keep_research', 'research_bundle', 'research_key']
