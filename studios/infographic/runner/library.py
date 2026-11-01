"""Infographic Studio and the shared Document Library (studio_core.document_library).

What a caller needs to know
---------------------------
    library.choose(store, ident, picks, expected_revision=n, acknowledge_warnings=False)
    library.update(store, ident, document, revision, expected_revision=n)  # exactly revision N
    library.marked(store, project)    # {source id: {'id', 'revision', 'head', 'update', 'state'}}
    library.idle(store, project, research=None, activity=None)   # refuses while work runs
    library.keep(store, ident, export_id)    # an approved export's text and PDF; never raises
    library.status(store, ident)             # what was kept last, or None
    library.own(store, ident)                # the library document holding its export, or None

Context
- Chosen revisions are checked by the library (they exist, are readable and match their
  hashes) before the infographic changes, and are then captured as ordinary `handoff`
  sources through the same capture boundary as selected studio material
  (`sources.captured`): the readable Markdown is the source text and an upload's original
  bytes are kept beside it. The infographic keeps them when the library changes or is gone.
  All chosen documents land in one new revision, or none do. A revision with extraction
  gaps is refused unless the person confirms using only its readable text
  (`acknowledge_warnings`), as an intake preview with gaps is; the gaps stay on the source.
- A source records where it came from in `provenance.library`; a newer revision in the
  library is offered as Update available and only the revision the person chose is taken. Choosing documents
  starts no research, grants no web access, sends nothing to an assistant and changes no
  research setting; like any source change it clears the facts, story and page that were
  built from the earlier sources, under the existing input rules.
- This infographic's own kept export (the document under `key()`, see `own()`) is refused
  as a source for itself; the page shows it as unavailable.
- Refused while the infographic is working: an action under way on the page, an image
  request pending or uncertain, or research running.

Approved exports
- After the approved files are prepared, the export's accessible text (`page.txt`) and its
  PDF (`page.pdf`) are kept in the library as an Infographic, found again by this
  workspace's infographic key: preparing the same files again reuses the document and adds
  a revision only when they changed. Only an export that is the approved, visually checked
  current revision is kept (the check Google delivery uses), and its bytes are read through
  `exports.read`, against their recorded hashes. Keeping never renders, uploads or runs an
  assistant or image provider.
- The approval and the files stand whatever the library does: a failure is recorded in
  `jobs/library.json`, which team sharing never reads, and Keep in library again retries it
  from the saved files alone.
"""
from __future__ import annotations

from datetime import datetime, timezone

from studio_core import document_library
from studio_core.document_library import LibraryError
from studio_core.document_library import context as library_context

from . import exports, sources
from .contracts import Invalid, canonical
from .validation import identifier, require
from .workspace import _atomic, _json

STATUS = 'jobs/library.json'
EXTRACTOR = 'document-library-markdown-v1'
BUSY = ('This infographic is working now. Add from the library, or take a newer revision, '
        'once its story, artwork or research has finished, or once Image work needs '
        'attention is resolved.')
NOT_APPROVED = ('Only the approved files of the current revision are kept in the Document '
                'Library. Approve this revision and prepare its files first.')


def key(store, ident) -> str:
    """This infographic's library key. The workspace owner keeps two workspaces apart."""
    return f'infographic:{store.owner[:12]}-{ident}'


SELF = ('This is this infographic’s own approved page, kept in the Document Library. It '
        'cannot be a source for itself. Choose another document.')


def own(store, ident) -> str | None:
    """The library document that keeps this infographic's approved files, or None."""
    try:
        found = document_library.opened()
        held = found.keyed([key(store, ident)]).get(key(store, ident)) if found else None
    except (LibraryError, OSError):
        return None
    return held['id'] if held else None


def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# --- context ---------------------------------------------------------------------------------

def pinned(source: dict) -> dict | None:
    """{'id', 'revision', ...} of the library revision a source was chosen from, or None."""
    held = (source.get('provenance') or {}).get('library') if source.get('kind') == 'handoff' else None
    if isinstance(held, dict) and isinstance(held.get('id'), str) and type(held.get('revision')) is int:
        return held
    return None


def idle(store, project, *, research=None, activity=None) -> None:
    """Refuse a change to the infographic's context while work may be reading it."""
    if isinstance(activity, dict) and activity.get('state') == 'running':
        raise Invalid(BUSY)
    from .image_jobs import Jobs as Images
    if any(item['state'] in ('queued', 'running', 'unknown')
           for item in Images(store, {}).recovery(project['id'])):
        raise Invalid(BUSY)
    from .research_jobs import Jobs as Research
    found = (research or Research(store)).read(project['id'])
    if found and found.get('state') in ('working', 'pausing', 'stopping'):
        raise Invalid(BUSY)


def _name(title: str) -> str:
    plain = ''.join(c if c.isprintable() and c not in '/\\' else '-' for c in title).strip()
    return plain[:200] or 'Library document'


def _captured(snapshot: dict, acknowledged: bool) -> tuple[dict, bytes, bytes]:
    """A library revision as a source record, its kept bytes and its normalized text."""
    found = document_library.opened()
    gaps = found.describe(snapshot['id'], snapshot['revision'])['gaps'] if found else []
    gaps = [gap for gap in gaps if isinstance(gap, str) and gap.strip()][:20]
    if gaps and acknowledged is not True:
        raise Invalid(f'"{snapshot["title"]}" has extraction gaps. Review them and confirm '
                      'using only its readable text before adding it.')
    text = snapshot['text']
    raw = snapshot['original'] if snapshot['original'] is not None else text.encode('utf-8')
    studio = document_library.STUDIOS.get(snapshot.get('studio'), 'Marketing Studio')
    provenance = {'studio': studio, 'library': {
        'id': snapshot['id'], 'revision': snapshot['revision'], 'kind': snapshot['kind'],
        'title': snapshot['title'][:200], 'content_sha256': snapshot['content_sha256'],
        'original_sha256': snapshot['original_sha256']}}
    # The gaps stay recorded with the source, and on its card, as the person confirmed them.
    extracted = {'text': text, 'extractor': EXTRACTOR, 'locations': [], 'warnings': gaps,
                 'readable': True}
    record, normalized = sources.captured(raw, extracted, kind='handoff', name=_name(snapshot['title']),
                                          provenance=provenance, acknowledge_warnings=bool(gaps))
    return record, raw, normalized


class _Sources:
    """The documents adapter `context.pin` and `context.update` take, for one infographic."""

    def __init__(self, store, ident, expected_revision, research=None, activity=None,
                 acknowledged=False):
        require(type(acknowledged) is bool, 'Confirm readable-only coverage explicitly.')
        self.store, self.ident, self.expected = store, ident, expected_revision
        self.research, self.activity, self.acknowledged = research, activity, acknowledged
        self.own = own(store, ident)

    def _not_own(self, snapshot):
        # Its own approved page is not a source for its facts: that would be circular.
        if self.own is not None and snapshot['id'] == self.own:
            raise Invalid(SELF)

    def _current(self):
        project = self.store.read(self.ident)
        self.store.expect(project, self.expected)
        idle(self.store, project, research=self.research, activity=self.activity)
        return project

    def listed(self, _root) -> list[dict]:
        return [{'source': source['id'], 'title': source['name'], 'library': held}
                for source in self._current()['sources'] if (held := pinned(source))]

    def _save(self, project, sources_now, captured):
        for record, raw, normalized in captured:
            self.store.write_blob(self.ident, record['file'], raw)
            self.store.write_blob(self.ident, record['normalized_file'], normalized)
        return self.store.change_locked(project, {'sources': sources_now})

    def add_snapshots(self, _root, snapshots) -> dict:
        for snapshot in snapshots:
            self._not_own(snapshot)
        captured = [_captured(snapshot, self.acknowledged) for snapshot in snapshots]
        with self.store.locked():
            project = self._current()
            held = {one['id'] for one in map(pinned, project['sources']) if one}
            for snapshot in snapshots:
                if snapshot['id'] in held:
                    raise Invalid(f'"{snapshot["title"]}" is already in this infographic. '
                                  'Use its newer revision instead, when one is offered.')
            known = {source['id'] for source in project['sources']}
            added = [record for record, _, _ in captured if record['id'] not in known]
            return self._save(project, project['sources'] + added, captured)

    def replace_snapshot(self, _root, snapshot) -> dict:
        self._not_own(snapshot)
        record, raw, normalized = _captured(snapshot, self.acknowledged)
        with self.store.locked():
            project = self._current()
            place = next((n for n, source in enumerate(project['sources'])
                          if (pinned(source) or {}).get('id') == snapshot['id']), None)
            require(place is not None, 'That library document is not in this infographic.')
            sources_now = list(project['sources'])
            sources_now[place] = record     # it keeps its place among the sources
            return self._save(project, sources_now, [(record, raw, normalized)])


def choose(store, ident, picks, *, expected_revision, research=None, activity=None,
           acknowledge_warnings=False) -> dict:
    """Add the chosen library revisions as sources, all or none. Returns the infographic."""
    adapter = _Sources(store, ident, expected_revision, research, activity, acknowledge_warnings)
    adapter._current()      # refused before the library is read when the work moved on
    try:
        return library_context.pin(adapter, ident, picks)
    except LibraryError as refusal:
        raise Invalid(str(refusal)) from None


def update(store, ident, document, revision, *, expected_revision, research=None,
           activity=None, acknowledge_warnings=False) -> dict:
    """Take exactly the library revision the person chose for one source: refused unless it
    is newer than the one pinned. Returns the infographic."""
    require(isinstance(document, str) and type(revision) is int,
            'Choose a document from the Document Library and the revision to take.')
    adapter = _Sources(store, ident, expected_revision, research, activity, acknowledge_warnings)
    entry = next((one for one in adapter.listed(ident) if one['library']['id'] == document), None)
    require(entry is not None, 'That library document is not in this infographic.')
    require(revision > entry['library']['revision'],
            f'This infographic already uses revision {entry["library"]["revision"]} or newer.')
    found = document_library.opened()
    require(found is not None, NO_LIBRARY)
    try:
        return adapter.replace_snapshot(ident, found.snapshot(document, revision))
    except LibraryError as refusal:
        raise Invalid(str(refusal)) from None


NO_LIBRARY = ('There is no Document Library on this computer, or its folder is not '
              'connected. This infographic keeps its own copy.')
STATES = {
    'current': None,
    'update': None,
    'unreadable': 'Its newest library revision cannot be read now. This infographic keeps its own copy.',
    'removed': ('It was removed from the Document Library, so no newer revision is offered. '
                'This infographic keeps its own copy.'),
    'not-here': ("It is not in this computer's Document Library, so it was probably added on a "
                 "teammate's computer. This infographic keeps its own copy."),
    'no-library': NO_LIBRARY,
}


def marked(store, project) -> dict:
    """{source id: {'id', 'revision', 'head', 'update', 'state', 'note'}} for sources chosen
    from the library. `head` is the library's newest revision on this computer (None when
    it cannot be found); `state` and `note` say why. The infographic's own copy is read
    either way."""
    chosen = [(source['id'], held) for source in project['sources'] if (held := pinned(source))]
    if not chosen:
        return {}
    try:
        found = document_library.opened()
    except (LibraryError, OSError):
        found = None
    shown = {}
    for source, held in chosen:
        head, state = None, 'no-library'
        if found is not None:
            try:
                row = found.describe(held['id'])
                head = row['revision']
                # Remove from library hides it: Use revision N would be refused, so none is offered.
                state = ('removed' if row.get('hidden') else 'unreadable' if not row['readable']
                         else 'update' if head > held['revision'] else 'current')
            except (LibraryError, OSError):
                state = 'not-here'
        shown[source] = {'id': held['id'], 'revision': held['revision'], 'head': head,
                         'update': state == 'update', 'state': state, 'note': STATES[state]}
    return shown


# --- approved exports --------------------------------------------------------------------

def _approved(store, ident, export_id):
    from .engine import Engine
    project = store.read(ident)
    delivery = next((d for d in Engine(store).deliveries(ident)
                     if d['id'] == export_id or export_id is None and d['approved_current']), None)
    require(delivery is not None and not delivery['draft'] and delivery['approved_current'],
            NOT_APPROVED)
    return project, delivery


def keep(store, ident, export_id=None) -> dict:
    """Keep an approved export's text and PDF in the library, and record how that went.
    Never raises for the library: the approval and the files stand either way."""
    require(export_id is None or identifier(export_id), 'Choose a saved approved export.')
    done = {'schema': 1, 'at': _now(), 'key': key(store, ident), 'export': export_id}
    try:
        project, delivery = _approved(store, ident, export_id)
        # `revision` stays the saved revision, as the shared Document Library contract has it
        # (other studios' adapters read it). `page_revision` is what the person is told.
        from .history import Pages
        done.update(export=delivery['id'], revision=delivery['revision'],
                    page_revision=Pages(store, ident).of(delivery['revision']))
        text = exports.read(store, ident, delivery['id'], 'text')[1].decode('utf-8')
        pdf = exports.read(store, ident, delivery['id'], 'pdf')[1]
        title = project['brief']['title']
        kept = document_library.opened(create=True).retain(
            key=done['key'], studio='infographic', kind='infographic', title=title, text=text,
            project={'id': ident, 'title': title, 'revision': done['revision']},
            pdf={'state': 'saved', 'data': pdf})
        done.update(state='kept', document=kept['document'], library_revision=kept['revision'],
                    pdf='saved')
    except Exception as failure:     # the approved files stand whatever the library does
        known = isinstance(failure, (LibraryError, Invalid, OSError, UnicodeDecodeError))
        done.update(state='failed', problem=(str(failure)[:300] if known else '')
                    or 'The library could not keep it. Try Keep in library again.')
    try:
        _atomic(store._project(ident) / STATUS, canonical(done))
    except (OSError, ValueError):
        pass    # the files are approved either way; the desk then says nothing was recorded
    return done


def status(store, ident) -> dict | None:
    """What was last kept in the library for this infographic, or None."""
    try:
        found = _json(store.root, f'projects/{ident}/{STATUS}', 20_000)
    except (OSError, ValueError):
        return None
    if not isinstance(found, dict) or found.get('state') not in ('kept', 'failed'):
        return None
    return {k: found.get(k) for k in ('state', 'at', 'export', 'revision', 'document',
                                       'library_revision', 'pdf', 'problem', 'page_revision') if k in found}
