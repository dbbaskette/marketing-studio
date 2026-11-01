"""Training Studio and the shared Document Library (studio_core.document_library).

What a caller needs to know
---------------------------
    library.pin(engine, path, picks)       # Add from library: the training's root
    library.update(engine, path, ident)    # Use revision N of one pinned document, when asked
    library.upload(name, data)             # Keep in library, for an upload: never raises
    library.keep(root, name)               # a guide or brief marked ready: never raises
    library.again(engine, path, name)      # Keep in library (again), for a Ready one
    library.kept(root, cards)              # what the desk says of each guide and brief,
                                           # Ready or returned to draft
    library.upload_again(engine, path, name)   # Keep in library again, for an added document
    library.research_sources(store, sent)  # the shared source editor, with Keep in library

Context
-------
- A pinned revision becomes one of the training's own documents (`documents.add_snapshots`),
  read only by its research, within the research's own permissions. Pinning starts no
  research, grants no web access and sends nothing to an assistant.
- While the training waits for its documents, a pinned one is read once the person says
  that is all of them, as an uploaded one is. Once the research is planned it is kept as a
  document added after the research (`documents.later`): not read until the person
  updates the research, which is priced first. Use revision N works the same way.
- A saved training whose research does not read documents takes none: pinning does not
  widen where research looks there. A desk training researched from the public web takes
  them as Add a source does: its research reads documents from then on, and the pinned ones
  wait, unread, until the person updates the research (`drafts.widen`). A conversation's
  training never widens from the page.
- New training can pin documents too (`engine.start(..., library=picks)`): each chosen
  revision is read and checked before anything is made, and pinned before research starts.
- Both are refused while a job is running: a job keeps the documents it started with.

Finished material
-----------------
- Marking a learner guide or a brief ready keeps it in the library as Markdown, as
  learners read it: the coverage notes under its headings are left out. Each material is
  found again by the training's own library key (made once, kept in `sources/library.json`,
  which the workspace never shares), so marking it ready again adds a revision only when
  its words changed. Decks are not kept: Training Studio cannot export a PDF of one yet.
- Marking ready never waits on the library: what stops it is recorded, and the desk offers
  Keep in library again. Nothing kept is shared with the team or committed.
- Returning a material to draft (Return to draft, Undo, or an edit) never removes what the
  library keeps: the desk says the library keeps revision N until it is marked ready again,
  and marking the same words ready again adds no revision.

Keep in library
---------------
- An upload the person chose to keep is kept in the library too, after the training took
  it, as an uploaded document from Training Studio. The same file sent again is the same
  library document, so trying again after a failure never makes a second one. A training's
  own copy is unchanged either way, and sharing never is.
- The New training sheet's source editor (ui-kit/research.js) offers the same choice for a
  file it captures; the file is kept once the source draft accepted it as readable.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path

import gdocs
import home
import workspace
from workspace import WorkspaceError

import runner  # noqa: F401  puts the core on the import path
from runner import drafts
from studio_core import document_library
from studio_core import research_contract as rc
from studio_core.document_library import LibraryError
from studio_core.document_library import context as library_context

STATUS = Path('sources') / 'library.json'
# The learner's own reading: the guide and the brief, kept as Markdown.
KEPT = ('document', 'brief')
BUSY = ('A step is being worked on now. Add from the library, or take a newer revision, '
        'when it ends: a job that is running keeps the documents it started with.')
NO_DOCUMENTS = ("This training's research does not read documents, so it takes none. "
                'Add from library changes no research setting.')
ON_DESK_INSTEAD = (' On the desk, Add a source reads documents too, and says what that '
                   'changes first.')
NOT_READY = '{it} is not marked ready, so it is not kept in the library yet.'
NOT_KEPT = 'The library could not keep it. Try Keep in library again.'
KEY = re.compile(r'training:[a-z0-9-]{1,120}-[a-f0-9]{12}')


# --- context: documents pinned from the library ------------------------------------------

def _given(record: dict) -> dict:
    given = record.get('documents')
    if not given:
        raise WorkspaceError(NO_DOCUMENTS + (ON_DESK_INSTEAD if drafts.on_desk(record) else ''))
    return given


def _idle(engine, root: Path, record: dict) -> None:
    """Refuse a change to the training's documents while a job may be reading them. Call it
    holding `files`."""
    if drafts.on_desk(record):
        if engine._desk_change_busy(root, record):
            raise WorkspaceError(BUSY)
        return
    run = engine._run(root)
    if run.workers or run.busy:
        raise WorkspaceError(BUSY)


def _later(given: dict) -> list[dict]:
    return [entry for entry in given.get('later') or () if isinstance(entry, dict)]


def _plural(count: int) -> str:
    return '1 document' if count == 1 else f'{count} documents'


def pin(engine, path, picks) -> Path:
    """Add documents chosen from the Document Library to the training's documents: each
    chosen revision is checked first, and its text and file are copied into the training,
    which keeps them when the library changes. Returns the training's folder."""
    root = engine._held(path)
    with engine.files:
        record = engine._load(root)
        # A desk training researched from the public web takes them too, as Add a source
        # does: its research reads documents from now on, once the person updates it.
        widening = not record.get('documents') and drafts.on_desk(record) \
            and not drafts.in_conversation(record)
        given = record.get('documents') if widening else _given(record)
        _idle(engine, root, record)
        waiting = not widening and engine._survey(root, record).next.kind == 'documents'
        try:
            added = library_context.pin(engine.documents, root, picks)
        except LibraryError as refusal:
            raise WorkspaceError(str(refusal)) from None
        if not waiting:
            # Kept, and read only once the person updates the research.
            now = home.now()
            if widening:
                from runner import pipeline
                drafts.widen(record, now)
                given = record['documents']
                readable = [entry for entry in engine.documents.listed(root)
                            if entry.get('readable')]
                given.update(done=now, count=len(readable))
                # Its documents are all added, as Add a source says of its own.
                marker = root / pipeline.ADDED
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(now + '\n', encoding='utf-8')
            given['later'] = [*_later(given),
                              *({'name': entry['name'], 'added_at': now} for entry in added)]
            engine._store(root, record)
            engine._commit(root, f'add {_plural(len(added))} from the Document Library, '
                                 'not read until the research is updated')
    return root


def update(engine, path, ident) -> Path:
    """Take the newest library revision of one pinned document, because the person asked.
    Once the research is planned, the new revision waits, unread, for the research to be
    updated. Returns the training's folder."""
    root = engine._held(path)
    with engine.files:
        record = engine._load(root)
        given = _given(record)
        _idle(engine, root, record)
        waiting = engine._survey(root, record).next.kind == 'documents'
        before = next((entry for entry in engine.documents.listed(root)
                       if (entry.get('library') or {}).get('id') == ident), None)
        try:
            entry = library_context.update(engine.documents, root, ident)
        except LibraryError as refusal:
            raise WorkspaceError(str(refusal)) from None
        if not waiting:
            gone = before['name'] if before else None
            given['later'] = [*(one for one in _later(given) if one.get('name') != gone),
                              {'name': entry['name'], 'added_at': home.now()}]
            engine._store(root, record)
            engine._commit(root, f"take revision {entry['library']['revision']} of "
                                 f"{entry.get('title') or entry['name']} from the Document "
                                 'Library, not read until the research is updated')
    return root


def shown(entry: dict) -> dict:
    """What the page is told of one pinned document, beside its name: its title, the
    revision it uses, and the newer one available."""
    if not entry.get('library'):
        return {}
    return {'title': entry.get('title'),
            'library': {key: entry['library'].get(key) for key in ('id', 'revision')},
            'library_head': entry.get('library_head'), 'update': bool(entry.get('update'))}


# --- Keep in library, for an upload -------------------------------------------------------

def upload(name, data) -> dict:
    """Keep an upload the training took in the library too: {'state': 'kept', 'document',
    'revision', 'readable'} or {'state': 'failed', 'problem'}. Never raises: the training
    has its document either way. The same file sent again is the same library document."""
    try:
        if not isinstance(name, str) or type(data) is not bytes:
            raise LibraryError('There was no document to keep.')
        operation = hashlib.sha256(b'training-upload\0' + name.encode('utf-8') + b'\0'
                                   + hashlib.sha256(data).digest()).hexdigest()[:32]
        row = document_library.opened(create=True).add_upload(
            name, data, operation=operation, studio='training')
        return {'state': 'kept', 'document': row['id'], 'revision': row['revision'],
                'readable': bool(row.get('readable'))}
    except Exception as failure:     # the training's own copy stands whatever happens here
        known = isinstance(failure, (LibraryError, OSError))
        return {'state': 'failed', 'problem': (str(failure)[:300] if known else '')
                or 'The library could not keep it.'}


def upload_again(engine, path, name) -> dict:
    """Keep in library again, for a document the training already took: its file as it was
    sent, read from the training's own copy. Starts nothing and changes no document."""
    root = engine._held(path)
    with engine.files:
        entry = next((one for one in engine.documents.listed(root) if one.get('name') == name
                      and not one.get('library')), None)
        if entry is None or not entry.get('original'):
            raise WorkspaceError('That is not a document added to this training.')
        data = (root / entry['original']).read_bytes()
    return upload(entry['name'], data)


def _kept_capture(store, ident, source) -> dict:
    """Keep one file the source editor captured: its bytes as the draft holds them, checked
    against their hash. Never raises."""
    try:
        with store.lock:
            value = store.load(ident)
            found = next((one for one in value['sources'] if one.get('id') == source), None)
            if found is None or found.get('kind') != 'file' or found.get('status') != 'ready':
                raise LibraryError('Only a readable uploaded file is kept in the library.')
            data = rc.inside(store.folder(ident), found['original']).read_bytes()
            if hashlib.sha256(data).hexdigest() != found.get('original_sha256'):
                raise LibraryError('This file changed after it was read. Add it again.')
        return {**upload(found['name'], data), 'source': source}
    except (LibraryError, ValueError, OSError, KeyError) as failure:
        return {'state': 'failed', 'problem': str(failure)[:300] or 'The library could not keep it.',
                'source': source}


def research_sources(store, sent):
    """The shared source editor's request, with Training Studio's Keep in library: `keep`
    on a file capture keeps the file once the draft accepted it as readable, and
    `library-keep` tries again for one source. The answer then carries `library_kept`."""
    if not isinstance(sent, dict):
        return store.dispatch(sent)
    sent = dict(sent)
    if sent.get('action') == 'library-keep':
        if set(sent) - {'action', 'id', 'expected', 'source'}:
            raise ValueError('Choose one source to keep in the library.')
        return {**store.read(sent.get('id')), 'library_kept': _kept_capture(
            store, sent.get('id'), sent.get('source'))}
    if 'keep' not in sent:
        return store.dispatch(sent)
    keep = sent.pop('keep')
    if type(keep) is not bool or sent.get('action') != 'capture' or sent.get('kind') != 'file':
        raise ValueError('Say whether to keep an uploaded file in the library.')
    before = {one['id'] for one in store.read(sent.get('id'))['sources']}
    answer = store.dispatch(sent)
    added = next((one for one in answer['sources'] if one['id'] not in before), None)
    if not keep or added is None or added.get('status') != 'ready':
        return answer       # Only this project, or not accepted: nothing is kept
    return {**answer, 'library_kept': _kept_capture(store, answer['id'], added['id'])}


# --- finished material: a guide or brief marked ready -----------------------------------

def status(root) -> dict:
    try:
        found = json.loads((Path(root) / STATUS).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _key(root: Path, held: dict) -> str:
    """This training's library key: the one recorded for it, else one made from the
    training's own identity, its folder and the moment its run started (kept in its
    committed run record). A training's folder name is a slug of its title, so the start
    keeps two trainings of one title apart, in two workspaces or made again after one was
    deleted, while the same training finds its documents again if `sources/library.json`
    is lost. A run with no start recorded gets a random part instead."""
    if isinstance(held.get('key'), str) and KEY.fullmatch(held['key']):
        return held['key']
    plain = re.sub(r'[^a-z0-9-]+', '-', root.name.lower()).strip('-')[:120] or 'training'
    started = (drafts.run_of(root) or {}).get('started_at')
    if isinstance(started, str) and started:
        return f"training:{plain}-{hashlib.sha256(f'{root.name}{chr(0)}{started}'.encode()).hexdigest()[:12]}"
    return f'training:{plain}-{secrets.token_hex(6)}'


def kept_by(base: str) -> bool:
    return base.partition(':')[0] in KEPT


def _approved(root: Path, session: dict, name: str) -> str | None:
    """The hash of the version of `name` the person marked ready, while it is the one on
    disk; None otherwise."""
    file = root / workspace.artifact(root, session, name)['file']
    digest = workspace.sha256_file(file)
    if digest is None or workspace.person_statuses(root, session).get(name) != 'approved':
        return None
    return digest


def keep(root, name: str) -> dict:
    """Keep one guide or brief the person marked ready in the library, as learners read it,
    and record how that went. Never raises: marking ready stands whatever the library does."""
    root = Path(root)
    held = status(root)
    materials = held.get('materials') if isinstance(held.get('materials'), dict) else {}
    done = {'at': home.now()}
    key = _key(root, held)
    try:
        session = workspace.load(root)
        digest = _approved(root, session, name)
        if digest is None:
            raise WorkspaceError(NOT_READY.format(it=workspace.sentence(workspace.label(name))))
        done['sha256'] = digest
        file = root / workspace.artifact(root, session, name)['file']
        text = gdocs.strip_comments(file.read_text(encoding='utf-8'))[0]
        base, level = workspace.split(name)
        title = session.get('title') or root.name
        words = workspace.label(name).removeprefix('the ')
        library = document_library.opened(create=True)
        found = library.retain(
            key=f"{key}.{re.sub(r'[^A-Za-z0-9._-]+', '-', base)}" + (f'-{level}' if level else ''),
            studio='training', kind='training', title=f'{title}: {words}', text=text,
            project={'id': root.name, 'title': title, 'revision': digest[:12]})
        done.update(state='kept', document=found['document'], revision=found['revision'])
    except Exception as failure:     # the person's decision stands whatever happens here
        known = isinstance(failure, (LibraryError, WorkspaceError, OSError, UnicodeDecodeError))
        done.update(state='failed', problem=(str(failure)[:300] if known else '') or NOT_KEPT)
    try:
        workspace.write_atomic(root / STATUS, (json.dumps(
            {'key': key, 'materials': {**materials, name: done}}, indent=2) + '\n').encode('utf-8'))
    except (OSError, WorkspaceError):
        pass    # marked ready either way; the desk then offers Keep in library again
    return done


def keep_marked(root, names) -> None:
    for name in names:
        if kept_by(workspace.split(name)[0]):
            keep(root, name)


def again(engine, path, name) -> Path:
    """Keep a Ready guide or brief in the library now, as the person asked: after a failure,
    or for one marked ready before the library kept anything. Starts no job and changes no
    material, so, like Mark ready, the person who runs a training worked on in a
    conversation may ask for it on the page too; nobody else may."""
    with engine.files:
        root = engine.driven(path)
        if root is None:
            raise WorkspaceError('No run is driving this training.')
        engine.hold(root, conversation=True)
        if not drafts.on_desk(engine._load(root)):
            raise WorkspaceError(drafts.NOT_ON_DESK)
        if not isinstance(name, str) or not kept_by(workspace.split(name)[0]):
            raise WorkspaceError('Only a learner guide or a brief is kept in the library.')
        session = workspace.load(root)
        if name not in workspace.artifact_names(root, session) or _approved(root, session, name) is None:
            raise WorkspaceError(NOT_READY.format(it=workspace.sentence(workspace.label(name))))
        done = keep(root, name)
    if done['state'] != 'kept':
        raise WorkspaceError(done['problem'])
    return root


def kept(root, cards) -> dict:
    """For each Ready guide or brief on the desk: {'state': 'kept', 'revision'} when the
    version marked ready is the one kept, {'state': 'failed', 'problem'} when keeping it
    failed, else {'state': 'not-kept'}. For one that is not Ready now (edited, or returned to
    draft) but was kept before: {'state': 'earlier', 'revision'}, the revision the library
    still holds until it is marked ready again. Nothing kept is ever removed here."""
    materials = status(root).get('materials') or {}
    shown_ = {}
    for card in cards:
        if card.get('kind') not in KEPT:
            continue
        held = materials.get(card['name']) if isinstance(materials, dict) else None
        held = held if isinstance(held, dict) else {}
        if card.get('state') != 'ready':
            if held.get('state') == 'kept' and held.get('revision'):
                shown_[card['name']] = {'state': 'earlier', 'revision': held['revision']}
            continue
        if held.get('sha256') and held.get('sha256') != card.get('seen'):
            shown_[card['name']] = {'state': 'not-kept'}
        elif held.get('state') == 'kept':
            shown_[card['name']] = {'state': 'kept', 'revision': held.get('revision')}
        elif held.get('state') == 'failed':
            shown_[card['name']] = {'state': 'failed', 'problem': held.get('problem') or NOT_KEPT}
        else:
            shown_[card['name']] = {'state': 'not-kept'}
    return shown_
