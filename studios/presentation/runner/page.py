"""The runner's server: the page, with the engine behind it.

What a caller needs to know
---------------------------
    server = page.Studio(engine, port)    # the page's server, answering for the runner
    server.url                            # the link, with its key; for a person only
    server.serve()                        # until interrupted; server.stop() ends the engine

- It keeps every rule of `server.Page`: it answers on the local machine only, checks the
  `Host` header, needs the key (X-Presentation-Studio-Token) for every call, and takes a
  change only as a POST with a JSON body from the page's own origin. `RunnerPage` adds
  addresses and never loosens a rule. Every answer is JSON, except a slide's picture
  (image/png) and the deck itself (the .pptx).
- Scratch forms accept optional `notes` (at most 4000 characters). Direction look picks bind to the shown samples; edited outlines stop for newly drawn looks. A finished team deck can have `mine: true` and no active driver when this computer delivered it; asking for changes reclaims it in that request.
- Reads (GET):
  - `/api/capabilities` {"runner": true, "version", "install"}, `install` the installed copy
    it runs from (None for a checkout), which the page waits for after a restart; `/api/setup`, what `setup.describe`
    says; `/api/agents` {"agents": [{"agent", "installed", "signed_in", "reachable",
    "version", "problem"}]}; `/api/models?agent=` what an agent offers to choose from
    ({"agent", "models", "levels", "source", "problem"}; a list that could not be made is
    answered with no models and `problem`, and listing holds up nothing else).
  - `/api/decks`, every deck in the engine's four lists {"needs", "working", "finished",
    "elsewhere"}; `/api/run?path=` one deck's view (`engine.view`); `/api/activity?path=`
    one deck's Activity log (`engine.activity`): each finished assistant job, newest first,
    without its lines; `&entry=` one finished job's lines, `&job=&since=` one running job's.
  - `/api/slide?path=&kind=build|look|original&number=` (or `&name=sample` for the cover
    drawn in the deck's brand, `&name=sheet` for the brand's looks on one sheet and
    `kind=look&number=` for one look, or `contact-sheet` for the build's sheet): one picture as
    image/png, only what `engine.picture` gives. Nothing is ever read from a place the
    request names.
  - `/api/download?path=`: the rendered deck, only what `engine.download` gives, as an
    attachment named for the deck; with `&revision=N`, that delivered revision's PowerPoint
    file while it is kept beside the deck (`deliver.receipt_file`).
  - `/api/file?path=&name=`: one of a deck's shared files, by name, only from FILES:
    {"name", "size", "text", "truncated"}. A file that leads out of the deck's folder is
    refused.
  - `/api/status` (`engine.standing`), `/api/published` {"published": [...]},
    `/api/delete?path=` what deleting would do (`engine.leaving`), and `/api/computer`, the
    last look at this computer with what a deck needs here.
- Changes (POST):
  - `/api/setup/check` and `/api/setup`: see `setup`. The values every studio shares are
    kept only in the studios config, so `/api/setup` and `/api/brand` write the ones they
    change there, and are 409 and 400, with a sentence, when one changes while that file
    cannot be read, or when the form was opened before another studio changed that same
    value: each takes `shared_seen`, the `shared` the form was shown, to tell what the
    person changed. `GET /api/setup` carries `shared`, what the file holds that
    Presentation Studio can use; `shared_problem`, a sentence when it could not be read;
    `team_moved`, {"repository", "branch", "says"} when it names a team repository this
    computer's workspace is not a copy of; and `shared_notice`, a sentence about the values
    the file already held when this computer's own moved there.
  - `/api/shared` {"seen": true}: the notice about the shared values has been read and is
    not shown again; answers the set-up.
  - `/api/decks` {"form", "uploads"?}: start a deck. `form` is what `decks.check_form`
    reads; `uploads` maps an uploaded file's name to its bytes in base64. Answers
    {"path", "id"}. It alone may carry up to DECKS_LIMIT bytes, and only with the key.
  - `/api/run` {"path", "action"}: pause, resume, stop, retry or undo; answers the view.
  - `/api/decide` {"path", "gate", "decision", "note"?, "extra"?}: the only way a gate
    moves; answers the view. `/api/answer` {"path", "id", "answer"}: a worker's question.
  - `/api/picture` {"path", "slide", "name", "content", "alt", "source", "expected"}: a
    picture of the person's own (PNG or JPEG, `content` in base64) for a cover, section or
    content slide while the outline waits; answers {"asset", "slide"}. It may carry up to
    PICTURE_LIMIT bytes, and only with the key.
  - `/api/picture-remove` {"path", "slide", "expected"}: take that picture off its slide
    while the outline waits; answers {"slide"}.
  - `/api/share` {}, `/api/fetch` {}, `/api/drive` {"path", "action": take|hand-over},
    `/api/publish` {"path"}, `/api/delete` {"path", "title"}, `/api/bring` {"path"}: a
    deck this computer knows from outside the workspace, copied in (`engine.bring`).
  - `/api/companions` {}, `/api/upgrade` {"version"} (main's label or commit, as shown),
    `/api/restart` {}, `/api/versions` {"dismiss"}: asked of `engine.upkeep`, each answering
    {"upkeep"}; 409 where nothing looks after the skills here, and while a deck is working
    (`upkeep` says so). Presentation Studio is updated from its repository's `main`.
  - `/api/brand` {"repository"} keeps the brand skill's repository once git can read its
    main branch as this person, and answers the set-up; it is 400, with a sentence, when it
    cannot be read. An empty repository forgets it. A `release` sent by an older page is
    not read. `/api/brand/install` {"commit"} installs the brand skill from main at that
    revision with its own installer, in the background, and answers {"upkeep"}; it is 409
    while a deck is working, while anything else is in hand, while a companion waits for
    Update, and when main is no longer at the revision shown in `upkeep.versions.brand`.
  - `/api/computer` {}: look at this computer again, and at the skills, and wake the decks
    that were waiting on what was missing.
  - The desk, for a deck started from the desk's start (`engine.desk_*`), each answering the
    deck's view: `/api/desk-note` {"path", "number", "note", "expected"} redraws one slide's
    section with the note; `/api/desk-deck-note` {"path", "note", "expected"} every section;
    `/api/desk-stop` {"path"} stops that redraw and keeps what was redrawn;
    `/api/desk-deliver` {"path", "expected", "blockers_seen"?} delivers the deck on screen;
    `/api/desk-draw-here` {"path"} draws a deck this computer has no drawing of;
    `/api/desk-upgrade` {"path", "expected"} upgrades a Selected changes deck to Redesign,
    keep content, one way, starting nothing, and `/api/desk-redesign-start` {"path"} starts
    its redesign from the priced step it then waits at;
    `/api/desk-open` {"path"} opens a deck delivered the gated way on the desk, still
    delivered, from this computer's drawing of it;
    `/api/desk-outline` {"path", "slides", "expected"} saves the Outline tab;
    `/api/desk-reread` {"path", "kind"} reads the document the other way; `/api/desk-look`
    {"path", "look", "note"?} picks the look at the deck's one pause; and
    `/api/desk-look-again` {"path"} draws the looks again for another pick. A slide's words:
    `/api/desk-words` {"path", "number", "field", "text", "seen", "session"?} and
    `/api/desk-notes` {"path", "number", "text", "seen", "session"?} save typed words with no
    composer where they fit (`field` is "title", "subtitle", "detail", "caveat", "source" or
    ["points", index, "label"|"text"], and on a Selected changes deck ["object", object ID,
    run index or null]; `seen` is the view's `desk.seen`);
    `/api/desk-selection` {"path", "number", "field", "start", "end", "action",
    "instruction"?, "seen"} has a words job rewrite a passage (rephrase, shorten, expand, fix
    or ask); `/api/desk-redraw-words` {"path", "number", "field", "text", "expected"} saves
    words that did not fit and redraws the slide's section; `/api/desk-discard` {"path",
    "number"} lets them go; and `/api/desk-restore` {"path", "slide", "index", "seen"} brings a
    kept version back. `GET /api/desk-versions?path=&slide=` answers {"versions"}, newest
    first. Sources, research and Finishing: `/api/desk-source` {"path", "name", "content",
    "library"?} adds a file (`content` in base64; it alone may carry up to SOURCE_LIMIT
    bytes, and only with the key; `library` true keeps it in the Document Library too, and
    the answer's `library_upload` says how that went) or {"path", "text", "title"} pasted
    text, and starts nothing;
    `/api/desk-research-again` {"path", "expected"} researches again with the sources as
    they are; `/api/desk-leave-out` {"path", "ids"} leaves those findings out;
    `/api/desk-finish` {"path", "tool", "expected"?, "again"?} runs one of Finishing's tools
    (brand, review, notes or rehearse; `again` checks the brand again); and
    `/api/desk-apply` {"path", "set", "ids", "seen"} and `/api/desk-skip` {"path", "set",
    "ids"} apply or skip proposals of one set, by their IDs (or {"id", "after"} with the
    person's own words). Both answer the view with `finished`, what was done.
    `/api/desk-outline-price` (GET ?path=, or POST {"path", "slides"} with the unsaved
    slides) answers {"says", "sections"}: what saving them redraws. `expected` is the view's
    `desk.expected` (the deck on screen) or `desk.outline.expected` (the outline read). A
    refusal is 400 with its sentence; a deck someone else drives is 409. A deck that is not on
    the desk is refused with `desk.NOT_ON_DESK`, except by `/api/desk-open`.
- A refusal is {"error": "<a sentence>"}. Something sent in the wrong shape is 400; a deck
  that is not one of this workspace's is 404; something that cannot be done as things
  stand, such as a change to a deck someone else drives, is 409.
- Every request that passes the rules tells the engine a page is open, which is how the
  runner knows not to notify through the computer instead. Reading never starts or wakes
  a run.
- Ported from Training Studio's runner/page.py. Its desk lists, gates, documents, copies,
  outline, assets and adopt are gone: a deck has one view, one decision address and its
  start form.
"""
from __future__ import annotations

# ruff: noqa: F821  names bound from studio_core.shared_runner are unseen by a linter;
# test_shared_runner_use checks the bound parts, and the suites call the rest.

import base64
import binascii
import re
from http import HTTPStatus
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
import server
from workspace import WorkspaceError

from runner import decks, gitstate, marks, settings, setup
from runner import engine as engines

from studio_core import modules, polling
from studio_core.document_library import LibraryError
from studio_core.document_library import context as library_context
from studio_core.shared_runner import caller
from studio_core.shared_runner import page as _shared
modules.bind(globals(), _shared, _shared.NAMES)

READS = ('/api/research-note', '/api/updates', '/api/slide-text-draft', '/api/intake-draft', '/api/capabilities', '/api/setup', '/api/agents', '/api/models', '/api/decks',
         '/api/run', '/api/activity', '/api/slide', '/api/download', '/api/status', '/api/published',
         '/api/delete', '/api/file', '/api/known-decks',
         '/api/desk-outline-price', '/api/desk-versions', '/api/desk-migration-preview', '/api/desk-ready-context')
# The desk's changes: each is an engine method by the same name, with what it is sent.
DESK = {'/api/desk-note': ('desk_note', ('number', 'note', 'expected')),
        '/api/desk-deck-note': ('desk_deck_note', ('note', 'expected')),
        '/api/desk-stop': ('desk_stop', ()),
        '/api/desk-deliver': ('desk_deliver', ('expected', 'blockers_seen?')),
        '/api/desk-draw-here': ('desk_draw_here', ()),
        '/api/desk-upgrade': ('desk_upgrade', ('expected',)),
        '/api/desk-redesign-start': ('desk_redesign_start', ()),
        '/api/desk-outline': ('desk_outline', ('slides', 'expected')),
        '/api/desk-reread': ('desk_reread', ('kind',)),
        '/api/desk-look': ('desk_look', ('look', 'note?')),
        '/api/desk-look-again': ('desk_look_again', ()),
        '/api/desk-words': ('desk_words', ('number', 'field', 'text', 'seen', 'session?')),
        '/api/desk-notes': ('desk_notes', ('number', 'text', 'seen', 'session?')),
        '/api/desk-selection': ('desk_selection', ('number', 'field', 'start', 'end', 'action',
                                                   'instruction?', 'seen', 'passage?')),
        '/api/desk-redraw-words': ('desk_redraw_words', ('number', 'field', 'text',
                                                         'expected')),
        '/api/desk-discard': ('desk_discard', ('number',)),
        '/api/desk-restore': ('desk_restore', ('slide', 'index', 'seen', 'stamp?')),
        '/api/desk-research-again': ('desk_research_again', ('expected', 'impact?')),
        '/api/desk-leave-out': ('desk_leave_out', ('ids',)),
        '/api/desk-finish': ('desk_finish', ('tool', 'expected?', 'again?')),
        '/api/desk-apply': ('desk_apply', ('set', 'ids', 'seen')),
        '/api/desk-skip': ('desk_skip', ('set', 'ids')),
        '/api/desk-open': ('open_on_desk', ()),
        # Sources from the shared Document Library, and the delivered deck kept there.
        '/api/desk-library': ('desk_library', ('picks',)),
        '/api/desk-library-update': ('desk_library_update', ('document',)),
        '/api/desk-library-keep': ('desk_library_keep', ())}
SOURCE = '/api/desk-source'   # a source added on the desk: a file in base64, or pasted text
SOURCE_LIMIT = 12_000_000     # bytes: a document of up to 8 MB, in base64, with its name
# What a desk change takes as it is sent, not as text.
RAW = ('slides', 'field', 'ids', 'again', 'picks')
WHOLE = ('seen', 'start', 'end', 'index')   # whole numbers, from zero
WRITES = ('/api/research-note', '/api/slide-text-draft', '/api/intake-draft', '/api/research-sources', '/api/setup/check', '/api/setup', '/api/decks', '/api/run', '/api/decide',
          '/api/answer', '/api/share', '/api/fetch', '/api/drive', '/api/publish',
          '/api/delete', '/api/bring', '/api/companions', '/api/upgrade', '/api/restart',
          '/api/versions', '/api/brand', '/api/brand/install', '/api/shared',
          '/api/deliver', '/api/build-feedback', '/api/progress-seen',
          '/api/research-site', '/api/picture',
          '/api/picture-remove', '/api/desk-outline-price', SOURCE, *DESK)
COPY = '/api/deck-copy'   # a deck's setup, for the start form to make a new one from
WRITES = (*WRITES, '/api/desk-migrate', '/api/desk-ready', COPY)
# Browsing the shared Document Library: it reads, and selects nothing for a deck.
WRITES = (*WRITES, *library_context.ROUTES)
# A folder on this computer, a Google Drive folder link, or a spreadsheet, read into the one
# document a deck from a document is made from (`studio_core.source_intake`).
DOCUMENT_INTAKE = '/api/document-intake'
WRITES = (*WRITES, DOCUMENT_INTAKE)
DOCUMENT_ENDINGS = ('.txt', '.md', '.html', '.htm', '.docx', '.pdf')   # the page's DOCUMENT_TYPES
DOCUMENT_MOST = 8_000_000    # bytes: the largest document the runner reads
INTAKE_LIMIT = 12_000_000    # bytes: a spreadsheet sent to be read, in base64
# Two are read at most: enough to tell one document from more than one, and no more.
ONE_DOCUMENT = ('This folder holds more than one document, among them {names}. A deck from a '
                'document is made from one. Choose one of them as a file, or start from an idea '
                'with research and add the folder to its sources.')
PPTX = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
DECKS = '/api/decks'
DECKS_LIMIT = 120_000_000    # bytes: a deck's form with its uploads, in base64
PICTURE = '/api/picture'
PICTURE_LIMIT = 28_000_000   # bytes: a picture of up to 20 MB for a slide, in base64
FILES = engines.FILES   # a read-only record lists the same files
PREVIEW_LIMIT = 1_000_000    # bytes of a file sent to the page
NO_DECK = 'There is no deck there.'
NO_KEEPER = ('This runner does not look after the skills on this computer. Run the installer '
             'to update them.')
NAMED = re.compile(r'[^A-Za-z0-9._-]')


def shaped(action, *args):
    """Run something that reads what was sent. Its refusal means the request was wrong."""
    try:
        return action(*args)
    except WorkspaceError as refusal:
        raise server.Refusal(HTTPStatus.BAD_REQUEST, str(refusal))


class RunnerPage(server.Page):
    """What the page may ask the runner."""
    reads = (*server.READS, *READS)
    writes = (*server.WRITES, *WRITES)

    # Each request is answered knowing whether the network bridge carried it
    # (`studio_core.shared_runner.caller`): a phone may not read this computer's folders.
    def answer(self, target, headers, method='GET', body=None):
        with caller.answering(headers):
            return super().answer(target, headers, method, body)

    # --- reads ---------------------------------------------------------------------------

    def read(self, path: str, one):
        if path == '/api/research-note':
            return self.apply(path, {'path':one('path'), 'id':one('id'), 'action':'read'})

        if path == '/api/updates':
            from studio_core import polling
            return server.as_json(HTTPStatus.OK, polling.snapshot(self.engine, home.data_root()))

        if path == '/api/slide-text-draft':
            try: level = one('level')
            except server.Refusal: level = None
            return self.apply(path, {'path': one('path'), 'level': level or None, 'action': 'read'})

        if path == '/api/intake-draft':
            from studio_core import intake_drafts
            try:
                return server.as_json(HTTPStatus.OK, intake_drafts.dispatch(home.data_root(),
                    gitstate.workspace_identity(self.engine.workspace), {'action':'read'}))
            except ValueError as error:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, str(error)) from None
        if path in ('/api/desk-migration-preview', '/api/desk-ready-context'):
            from runner import desk_chat
            folder = self.deck(one('path'))
            value = desk_chat.migration_preview(self.engine, folder) if path.endswith('migration-preview') \
                else desk_chat.context(self.engine, folder, 'ready')
            return server.as_json(HTTPStatus.OK, value)
        self.engine.seen()
        if path == '/api/capabilities':
            return server.as_json(HTTPStatus.OK, {'runner': True,
                                                  'version': gitstate.installed(),
                                                  'install': gitstate.installed_copy()})
        if path == '/api/setup':
            return server.as_json(HTTPStatus.OK, setup.describe(self.engine))
        if path == '/api/agents':
            return server.as_json(HTTPStatus.OK, {'agents': self.agents()})
        if path == '/api/models':
            return server.as_json(HTTPStatus.OK, shaped(self.engine.models, one('agent')))
        if path == '/api/decks':
            return server.as_json(HTTPStatus.OK, self.engine.decks())
        if path == '/api/known-decks':
            return server.as_json(HTTPStatus.OK, {'decks': [entry for entry in home.decks()
                if self.engine.driven(entry['path']) is None]})
        if path == '/api/run':
            return server.as_json(HTTPStatus.OK, self.run(one('path')))
        if path == '/api/activity':
            def given(name):
                try:
                    return one(name)
                except server.Refusal:
                    return None
            since = given('since') or '0'
            if not (since.isascii() and since.isdigit()) or len(since) > 9:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Give since as a whole number.')
            return server.as_json(HTTPStatus.OK, self.engine.activity(
                self.deck(one('path')), entry=given('entry'), job=given('job'),
                since=int(since)))
        if path == '/api/slide':
            return HTTPStatus.OK, PNG, self.slide(one)
        if path == '/api/download':
            try:
                revision = one('revision')
            except server.Refusal:
                revision = None
            if revision is not None and not re.fullmatch(r'[0-9]+', revision):
                raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A revision is a whole number.')
            return self.download(one('path'), int(revision) if revision else None)
        if path == '/api/file':
            return server.as_json(HTTPStatus.OK, self.file(one('path'), one('name')))
        if path == '/api/desk-versions':
            deck = self.deck(one('path'))
            return server.as_json(HTTPStatus.OK, {'versions': self.desk(
                lambda: self.engine.desk_versions(deck, one('slide')))})
        if path == '/api/desk-outline-price':
            path = self.deck(one('path'))
            return server.as_json(HTTPStatus.OK, self.desk(
                lambda: self.engine.desk_outline_price(path, None)))
        if path == '/api/status':
            return server.as_json(HTTPStatus.OK, self.engine.standing())
        if path == '/api/published':
            return server.as_json(HTTPStatus.OK, {'published': self.engine.published()})
        if path == '/api/delete':
            return server.as_json(HTTPStatus.OK, self.engine.leaving(self.deck(one('path'))))
        return super().read(path, one)

    def deck(self, path: str) -> str:
        """A deck of this workspace, or 404 for any other folder, whatever it holds."""
        if self.engine.driven(path) is None:
            raise server.Refusal(HTTPStatus.NOT_FOUND, NO_DECK)
        return path

    def run(self, path: str) -> dict:
        found = self.engine.view(self.deck(path))
        if found is None:
            raise server.Refusal(HTTPStatus.NOT_FOUND, NO_DECK)
        return found

    def slide(self, one) -> bytes:
        """One picture of a deck. The request names the deck, the kind of picture and a
        slide's number or a name, and nothing else: where it is kept is the engine's."""
        def given(name: str) -> str | None:
            try:
                return one(name)
            except server.Refusal:
                return None

        path, kind = self.deck(one('path')), one('kind')
        number, name = given('number'), given('name')
        if kind not in engines.PICTURE_KINDS:
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A picture is of the build, the brand '
                                 'or the original deck: ' + ', '.join(engines.PICTURE_KINDS)
                                 + '.')
        if (number is None) == (name is None):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Name the slide by its number, or by '
                                 'a name, and not both.')
        if number is not None and not (number.isascii() and number.isdigit()):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Give number as a whole number.')
        try:
            return shaped(self.engine.picture, path, kind,
                          int(number) if number is not None else name)
        except OSError:
            raise server.Refusal(HTTPStatus.NOT_FOUND, engines.NO_PICTURE)

    def download(self, path: str, revision: int | None = None) -> tuple:
        """The rendered deck, or one delivered revision's PowerPoint file, as a file to keep."""
        name, data = self.engine.download(self.deck(path), revision)
        name = NAMED.sub('-', name) or 'deck.pptx'
        return HTTPStatus.OK, PPTX, data, {
            'Content-Disposition': f'attachment; filename="{name}"'}

    def file(self, path: str, name: str) -> dict:
        """One of a deck's shared files, by its name: only those in FILES."""
        root = Path(self.deck(path))
        if name not in FILES:
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A file is one of: '
                                 + ', '.join(FILES) + '.')
        file = (root / name).resolve()
        if root.resolve() not in file.parents:
            raise server.Refusal(HTTPStatus.FORBIDDEN, f'{name} leads outside the deck folder.')
        if not file.is_file():
            raise server.Refusal(HTTPStatus.NOT_FOUND, f'{name} has not been written yet.')
        with open(file, 'rb') as stream:
            data = stream.read(PREVIEW_LIMIT)
        truncated = file.stat().st_size > len(data)
        return {'name': name, 'size': file.stat().st_size,
                'text': data.decode('utf-8', 'replace'), 'truncated': truncated}

    def uses_google(self) -> bool:
        """Whether a new deck is made in Google Slides, or a deck here was."""
        if settings.load().output == 'google':
            return True
        for root in self.engine.every():
            try:
                if (decks.read_run(root).get('form') or {}).get('output') == 'google':
                    return True
            except (OSError, ValueError, AttributeError):
                continue
        return False

    def computer(self, look: bool) -> dict | None:
        """The last look at this computer, with what a deck needs here. A new look is a new
        look at those too and at the skills, and wakes the decks waiting on them."""
        seen = super().computer(look)
        if seen is None:
            return None
        keep = getattr(self.engine, 'upkeep', None)
        if look and keep is not None:
            keep.again()
        needs = self.engine.look_again() if look else self.engine.deck_needs()
        items = [{**item, 'optional': False} for item in needs['items']]
        wrong = [*seen['wrong'], *(item['name'] for item in items if item['state'] != 'ok')]
        return {**seen, 'items': [*seen['items'], *items], 'wrong': wrong,
                'ready': seen['ready'] and not wrong}

    def body_limit(self, target: str, headers) -> int:
        """A deck's form may carry its uploads whole, to its own address, from whoever holds
        the key. Anyone else's request there is held to the usual limit, so it is refused
        unread."""
        address = target.partition('?')[0]
        if address in ('/api/intake-draft', '/api/decide', '/api/slide-text-draft'):
            try:
                self.check_token(headers)
            except server.Refusal:
                return super().body_limit(target, headers)
            from studio_core.intake_drafts import LIMIT
            return LIMIT if address == '/api/intake-draft' else 512_000
        if address in (DECKS, PICTURE, SOURCE, '/api/research-sources', DOCUMENT_INTAKE):
            try:
                self.check_token(headers)
            except server.Refusal:
                return super().body_limit(target, headers)
            return {DECKS: DECKS_LIMIT, PICTURE: PICTURE_LIMIT, SOURCE: SOURCE_LIMIT, '/api/research-sources': 12_000_000,
                    DOCUMENT_INTAKE: INTAKE_LIMIT}[address]
        return super().body_limit(target, headers)

    # --- changes -------------------------------------------------------------------------

    def write(self, path: str, sent: dict):
        """Every POST the page answers. Once it has run, even when it failed partway, the
        next poll walks the workspace again instead of reusing the last walk, so the
        change shows at once in every open tab. A read sent as a POST changes nothing."""
        try:
            return self.apply(path, sent)
        finally:
            if sent.get('action') != 'read':
                polling.invalidate(self.engine)

    def apply(self, path: str, sent: dict):
        if path == '/api/research-note':
            from studio_core import intake_drafts, research_notes
            try:
                if not isinstance(sent.get('path'), str): raise ValueError('Choose saved work for this note.')
                root = self.engine.driven(sent['path'])
                if root is None: raise ValueError('Choose saved work in this workspace.')
                values = {key:value for key,value in sent.items() if key not in ('path','id')}
                return server.as_json(HTTPStatus.OK, research_notes.dispatch(home.data_root(), root, sent.get('id'), values))
            except intake_drafts.Conflict:
                raise server.Refusal(HTTPStatus.CONFLICT, 'This queued note changed in another tab. Copy your text before reloading. Evidence is unchanged.') from None
            except ValueError as failure:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, str(failure)) from None

        if path == '/api/slide-text-draft':
            from studio_core import intake_drafts
            try:
                if not isinstance(sent.get('path'), str):
                    raise ValueError('Choose a saved project for these corrections.')
                root = self.engine.driven(sent['path'])
                if root is None: raise ValueError('Choose saved work in this workspace.')
                level = sent.get('level')
                if level is not None and (not isinstance(level, str) or len(level) > 80):
                    raise ValueError('Choose a level from this review.')
                scope = {'workspace': gitstate.workspace_identity(self.engine.workspace),
                         'project': str(root), 'level': level or None}
                values = {key: value for key, value in sent.items() if key not in ('path', 'level')}
                return server.as_json(HTTPStatus.OK, intake_drafts.slide_review(home.data_root(), scope, values))
            except intake_drafts.Conflict as failure:
                raise server.Refusal(HTTPStatus.CONFLICT, str(failure)) from None
            except ValueError as failure:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, str(failure)) from None

        if path == '/api/intake-draft':
            from studio_core import intake_drafts
            try:
                value = intake_drafts.dispatch(home.data_root(),
                    gitstate.workspace_identity(self.engine.workspace), sent)
                return server.as_json(HTTPStatus.OK, value)
            except intake_drafts.Conflict as error:
                raise server.Refusal(HTTPStatus.CONFLICT, str(error)) from None
            except ValueError as error:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, str(error)) from None
        if path in library_context.ROUTES:
            try:
                return server.as_json(HTTPStatus.OK, library_context.answer(path, sent, 'presentation'))
            except ValueError as error:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, str(error)) from None
        if path == DOCUMENT_INTAKE:
            return server.as_json(HTTPStatus.OK, self.document_intake(sent))
        if path == '/api/research-sources':
            from studio_core.research_sources import Sources
            from runner import source_keep
            # A phone through the network bridge may not read this computer's folders.
            refused = caller.folder_refused(sent)
            if refused:
                raise server.Refusal(HTTPStatus.FORBIDDEN, refused)
            try:
                return server.as_json(HTTPStatus.OK, source_keep.research_sources(
                    Sources(self.engine.space().root / '.research-sources'), sent))
            except ValueError as error:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, str(error)) from None
        self.engine.seen()
        if path == COPY:
            deck = self.deck(server.text(sent, 'path'))
            try:
                return server.as_json(HTTPStatus.OK, self.engine.copy_setup(deck))
            except WorkspaceError as refusal:
                raise server.Refusal(HTTPStatus.CONFLICT, str(refusal)) from None
        if path in ('/api/desk-migrate', '/api/desk-ready'):
            from runner import desk_chat
            root = self.deck(server.text(sent, 'path'))
            value = desk_chat.migrate(self.engine, root, server.text(sent, 'expected')) \
                if path.endswith('migrate') else desk_chat.ready(
                    self.engine, root, {key: value for key, value in sent.items() if key != 'path'})
            return server.as_json(HTTPStatus.OK, value)
        if path == '/api/setup/check':
            return server.as_json(HTTPStatus.OK, shaped(setup.check, sent))
        if path == '/api/setup':
            return server.as_json(HTTPStatus.OK,
                                  setup.apply(self.engine, shaped(setup.read, sent)))
        if path == DECKS:
            return server.as_json(HTTPStatus.OK, self.start(sent))
        if path == '/api/run':
            return server.as_json(HTTPStatus.OK, self.act(sent))
        if path == '/api/progress-seen':
            return server.as_json(HTTPStatus.OK, self.engine.progress_seen(
                self.deck(server.text(sent, 'path')), server.text(sent, 'ref')))
        if path == '/api/build-feedback':
            number = sent.get('number')
            if number is not None and (type(number) is not int or number < 1):
                raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Name the slide by its number.')
            return server.as_json(HTTPStatus.OK, self.engine.build_feedback(
                self.deck(server.text(sent, 'path')), server.text(sent, 'ref'),
                server.text(sent, 'note'), number))
        if path == '/api/decide':
            return server.as_json(HTTPStatus.OK, self.decide(sent))
        if path == PICTURE:
            return server.as_json(HTTPStatus.OK, self.picture_given(sent))
        if path == '/api/picture-remove':
            return server.as_json(HTTPStatus.OK, self.engine.remove_picture(
                self.deck(server.text(sent, 'path')), server.text(sent, 'slide'),
                server.text(sent, 'expected', needed=False)))
        if path == '/api/answer':
            return server.as_json(HTTPStatus.OK, self.answered(sent))
        if path in DESK:
            return server.as_json(HTTPStatus.OK, self.desk_change(path, sent))
        if path == SOURCE:
            return server.as_json(HTTPStatus.OK, self.source_given(sent))
        if path == '/api/desk-outline-price':
            deck = self.deck(server.text(sent, 'path'))
            return server.as_json(HTTPStatus.OK, self.desk(
                lambda: self.engine.desk_outline_price(deck, sent.get('slides'))))
        if path == '/api/research-site':
            # A site for one deck's research, checked here as the deck's form will be.
            return server.as_json(HTTPStatus.OK, shaped(setup.research_site, sent))
        if path == '/api/share':
            return server.as_json(HTTPStatus.OK, self.engine.share())
        if path == '/api/fetch':
            return server.as_json(HTTPStatus.OK, self.engine.fetch())
        if path == '/api/drive':
            return server.as_json(HTTPStatus.OK, self.drive(sent))
        if path == '/api/deliver':
            return server.as_json(HTTPStatus.OK, self.engine.deliver_again(
                self.deck(server.text(sent, 'path'))))
        if path == '/api/publish':
            return server.as_json(HTTPStatus.OK, self.engine.publish(
                self.deck(server.text(sent, 'path'))))
        if path == '/api/delete':
            title = server.text(sent, 'title')
            return server.as_json(HTTPStatus.OK, self.engine.delete(
                self.deck(server.text(sent, 'path')), title))
        if path == '/api/bring':
            return server.as_json(HTTPStatus.OK, self.bring(sent))
        if path == '/api/companions':
            return server.as_json(HTTPStatus.OK, {'upkeep': self.keeper().update(
                self.working())})
        if path == '/api/upgrade':
            version = server.text(sent, 'version')
            return server.as_json(HTTPStatus.OK, {'upkeep': self.keeper().upgrade(
                self.working(), version)})
        if path == '/api/restart':
            return server.as_json(HTTPStatus.OK, {'upkeep': self.keeper().restart(
                self.working())})
        if path == '/api/versions':
            dismissed = server.text(sent, 'dismiss')
            return server.as_json(HTTPStatus.OK, {'upkeep': self.keeper().dismiss(dismissed)})
        if path == '/api/brand':
            return server.as_json(HTTPStatus.OK, shaped(setup.save_brand, self.engine, sent))
        if path == '/api/shared':
            if sent.get('seen') is not True:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Send {"seen": true} once the '
                                     'notice about the shared values has been read.')
            setup.notice_read()
            return server.as_json(HTTPStatus.OK, setup.describe(self.engine))
        if path == '/api/brand/install':
            commit = server.text(sent, 'commit')
            return server.as_json(HTTPStatus.OK, {'upkeep': self.keeper().install_brand(
                self.working(), commit)})
        return super().write(path, sent)

    def keeper(self):
        """What looks after the skills here, or a refusal where nothing does."""
        keep = getattr(self.engine, 'upkeep', None)
        if keep is None:
            raise server.Refusal(HTTPStatus.CONFLICT, NO_KEEPER)
        return keep

    def working(self) -> bool:
        return setup.working(self.engine)

    def start(self, sent: dict) -> dict:
        """Start a deck from its form and what was uploaded with it."""
        form, given = sent.get('form'), sent.get('uploads') or {}
        if not isinstance(form, dict):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Send the form as one JSON object.')
        if not isinstance(given, dict) or not all(isinstance(name, str) and name.strip()
                                                  for name in given):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Send the uploads by their names.')
        uploads = {}
        for name, content in given.items():
            if not isinstance(content, str) or not content:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, f'"{name}" arrived empty. Choose '
                                     'the file again.')
            try:
                uploads[name] = base64.b64decode(content, validate=True)
            except (binascii.Error, ValueError):
                raise server.Refusal(HTTPStatus.BAD_REQUEST, f'"{name}" did not arrive whole. '
                                     'Choose the file again.')
        brands = self.engine.brands() if self.engine.workspace is not None else None
        if brands is not None and not sent.get('research_inputs'):   # source-backed forms are checked with their trusted references by the engine
            shaped(decks.check_form, form, brands)
        # A malformed pick is the request's fault, refused before anything is read.
        if sent.get('library') is not None:
            try:
                library_context.picks(sent['library'])
            except LibraryError as refusal:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, str(refusal)) from None
        return self.engine.start(form, uploads, research_inputs=sent.get('research_inputs'),
                                 library=sent.get('library'))

    @staticmethod
    def document_intake(sent: dict) -> dict:
        """The New deck form's folder or spreadsheet, for a deck from a document: {location}
        (a folder on this computer or a Google Drive folder link) or {file: {name, data}} (a
        spreadsheet, in base64), read with `source_intake.take`. A folder on this computer is
        refused to a caller the network bridge carried. Answers the one document it holds,
        {name, content (base64), bytes, said}; a folder with none or with more is refused,
        saying what it held. Nothing is kept: the form sends the document when it starts."""
        from studio_core import source_intake
        if set(sent) not in ({'location'}, {'file'}):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Give a folder, or one spreadsheet.')
        given = sent.get('location')
        if 'file' in sent:
            file = sent['file']
            if not isinstance(file, dict) or not isinstance(file.get('name'), str) \
                    or not isinstance(file.get('data'), str):
                raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Send the spreadsheet with its '
                                     'name and its contents.')
            try:
                given = {'name': file['name'], 'data': base64.b64decode(file['data'],
                                                                        validate=True)}
            except (binascii.Error, ValueError):
                raise server.Refusal(HTTPStatus.BAD_REQUEST, f'"{file["name"]}" did not arrive '
                                     'whole. Choose the file again.') from None
        elif not isinstance(given, str):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Give the folder as text.')
        # The same refusal, in the same status, as the source editor's folder add.
        if caller.remote() and caller.on_this_computer(given):
            raise server.Refusal(HTTPStatus.FORBIDDEN, source_intake.REMOTE)
        try:
            found = source_intake.take(given, local=not caller.remote(),
                                       accepts=DOCUMENT_ENDINGS, room=2,
                                       spare=2 * DOCUMENT_MOST)
        except ValueError as refusal:
            raise server.Refusal(HTTPStatus.CONFLICT, str(refusal)) from None
        documents = list(found['uploads'].items())
        if not documents:
            raise server.Refusal(HTTPStatus.CONFLICT, found['said'] or 'Nothing there can be '
                                 'read as a document.')
        if len(documents) > 1:
            names = [name for name, _ in documents]
            raise server.Refusal(HTTPStatus.CONFLICT, ONE_DOCUMENT.format(
                names=' and '.join(names)))
        name, data = documents[0]
        if len(data) > DOCUMENT_MOST:
            raise server.Refusal(HTTPStatus.CONFLICT, f'{name} is larger than a document can '
                                 'be. Save a smaller copy.')
        return {'name': name, 'content': base64.b64encode(data).decode('ascii'),
                'bytes': len(data), 'said': found['said']}

    def picture_given(self, sent: dict) -> dict:
        """A picture the person gives one slide at the outline stop: {"path", "slide",
        "name", "content" (the file in base64), "alt", "source", "expected"}."""
        data = sent.get('content')
        try:
            if not isinstance(data, str) or not data:
                raise ValueError
            picture = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'The picture did not arrive whole. '
                                 'Choose the file again.')
        return self.engine.add_picture(
            self.deck(server.text(sent, 'path')), server.text(sent, 'slide'),
            server.text(sent, 'name', needed=False) or '', picture,
            server.text(sent, 'alt', needed=False) or '',
            server.text(sent, 'source', needed=False) or '',
            server.text(sent, 'expected', needed=False))

    def source_given(self, sent: dict) -> dict:
        """A source the person adds on the desk: {"path", "name", "content", "library"?} with
        the file in base64, and `library` true to keep it in the Document Library as well
        (Keep in library) or false for this deck only, or {"path", "text", "title",
        "library"?} with text they pasted, kept in the library the same way."""
        deck = self.deck(server.text(sent, 'path'))
        keep = sent.get('library', False)
        if not isinstance(keep, bool):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Choose Keep in library or Only this '
                                 'project.')
        if sent.get('content') is None:
            text = sent.get('text')
            if not isinstance(text, str) or len(text) > SOURCE_LIMIT:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Paste the text of the source, or '
                                     'choose its file.')
            title = server.text(sent, 'title', needed=False)
            return self.desk(lambda: self.engine.desk_source(deck, None, text=text,
                                                             title=title, keep=keep))
        data = sent.get('content')
        try:
            if not isinstance(data, str) or not data:
                raise ValueError
            given = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'The file did not arrive whole. '
                                 'Choose it again.')
        return self.desk(lambda: self.engine.desk_source(
            deck, server.text(sent, 'name'), given, title=server.text(sent, 'title',
                                                                       needed=False),
            keep=keep))

    def act(self, sent: dict) -> dict:
        path, action = server.text(sent, 'path'), server.text(sent, 'action')
        if action not in engines.ACTIONS:
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A run can be asked to: '
                                 + ', '.join(engines.ACTIONS) + '.')
        return self.engine.act(self.deck(path), action)

    def decide(self, sent: dict) -> dict:
        """A person's decision at a gate: approve, or ask for changes with a note, marks, or
        both. At the brand's gate the change is another brand, and needs no note."""
        path, gate = server.text(sent, 'path'), server.text(sent, 'gate')
        decision, note = server.text(sent, 'decision'), server.text(sent, 'note', False)
        extra = sent.get('extra')
        if gate not in engines.WORDS:
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A decision is made at one of the '
                                 'gates: ' + ', '.join(engines.WORDS) + '.')
        if decision not in engines.DECISIONS and not (gate == 'gate:story' and decision == 'save'):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A decision is to approve, or to ask '
                                 'for changes: ' + ', '.join(engines.DECISIONS) + '.')
        if extra is not None and not isinstance(extra, dict):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Send what comes with a decision as '
                                 'one JSON object.')
        if decision == 'changes' and not (note or '').strip() \
                and not (gate in marks.REVIEWED and marks.asks(extra or {})):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, engines.NO_NOTE)
        return self.engine.decide(self.deck(path), gate, decision, note, extra,
                                  server.text(sent, 'expected', False))

    def desk(self, action):
        """A desk call: what it refuses is 400 with its sentence, except a deck someone else
        drives, which is 409 as it is everywhere."""
        try:
            return action()
        except engines.Elsewhere:
            raise
        except WorkspaceError as refusal:
            raise server.Refusal(HTTPStatus.BAD_REQUEST, str(refusal))

    def desk_change(self, path: str, sent: dict) -> dict:
        """One of the desk's changes, with what it takes beside the deck's path."""
        name, takes = DESK[path]
        deck = self.deck(server.text(sent, 'path'))
        given = []
        for key in takes:
            optional = key.endswith('?')
            key = key.rstrip('?')
            if key in ('number',):
                value = sent.get(key)
                if type(value) is not int or value < 1:
                    raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Name the slide by its number.')
            elif key in RAW:
                value = sent.get(key)
            elif key in WHOLE:
                value = sent.get(key)
                if type(value) is not int or value < 0:
                    raise server.Refusal(HTTPStatus.BAD_REQUEST, f'Give {key} as a whole number.')
            elif key == 'text':
                value = sent.get(key)
                if not isinstance(value, str) or len(value) > server.NOTE_LIMIT:
                    raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Give text as text.')
            else:
                value = server.text(sent, key, not optional)
            given.append(value)
        return self.desk(lambda: getattr(self.engine, name)(deck, *given))

    def answered(self, sent: dict) -> dict:
        path, ident = server.text(sent, 'path'), server.text(sent, 'id')
        answer = server.text(sent, 'answer')
        if not answer.strip():
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Write an answer first.')
        return self.engine.answer(self.deck(path), ident, answer)

    def drive(self, sent: dict) -> dict:
        """Take a deck, which takes over one someone else drives, or hand it over."""
        path, action = server.text(sent, 'path'), server.text(sent, 'action')
        if action not in engines.DRIVING:
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A deck can be asked to: '
                                 + ', '.join(engines.DRIVING) + '.')
        return self.engine.drive(self.deck(path), action)

    def bring(self, sent: dict) -> dict:
        """Copy a deck this computer knows, made outside the workspace, into it. Any other
        folder is refused, whatever it holds; the folder it came from is only read."""
        path = server.text(sent, 'path')
        if path not in [entry['path'] for entry in home.decks()]:
            raise server.Refusal(HTTPStatus.FORBIDDEN, 'That folder is not a deck this '
                                 'computer knows.')
        return self.engine.bring(path)


modules.bind(globals(), _shared, methods={'RunnerPage': _shared.METHODS['RunnerPage']})


class Studio(server.Desk):
    """The runner's server: the page, answering for the engine."""


modules.bind(globals(), _shared, methods={'Studio': _shared.METHODS['Studio']})
