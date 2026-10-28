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
  - `/api/capabilities` {"runner": true, "version"}; `/api/setup`, what `setup.describe`
    says; `/api/agents` {"agents": [{"agent", "installed", "signed_in", "reachable",
    "version", "problem"}]}; `/api/models?agent=` what an agent offers to choose from
    ({"agent", "models", "levels", "source", "problem"}; a list that could not be made is
    answered with no models and `problem`, and listing holds up nothing else).
  - `/api/decks`, every deck in the engine's four lists {"needs", "working", "finished",
    "elsewhere"}; `/api/run?path=` one deck's view (`engine.view`).
  - `/api/slide?path=&kind=build|look|original&number=` (or `&name=sample` for the cover
    drawn in the deck's brand, `&name=sheet` for the brand's looks on one sheet and
    `kind=look&number=` for one look, or `contact-sheet` for the build's sheet): one picture as
    image/png, only what `engine.picture` gives. Nothing is ever read from a place the
    request names.
  - `/api/download?path=`: the rendered deck, only what `engine.download` gives, as an
    attachment named for the deck.
  - `/api/storyboard?path=&expected=` (and POST, with the unsaved `slides`): the outline
    drawn as a wireframe storyboard, kept in the deck's work/drafts/, answered as {"src",
    "expected", "milliseconds"}. `src` is `/api/deck-draft?ticket=`, which the page's
    sandboxed frame opens without the key, for that one file, for two minutes, as HTML under
    the framed page's own policy (`server.framed_html`).
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
  - `/api/note` {"path", "expected", "text"}: a note for the next step, which goes with
    the next job that starts and stops nothing; `expected` is the view's `note.expected`.
  - `/api/share` {}, `/api/fetch` {}, `/api/drive` {"path", "action": take|hand-over},
    `/api/publish` {"path"}, `/api/delete` {"path", "title"}, `/api/bring` {"path"}: a
    deck this computer knows from outside the workspace, copied in (`engine.bring`).
  - `/api/companions` {}, `/api/upgrade` {"version"}, `/api/restart` {}, `/api/versions`
    {"dismiss"}: asked of `engine.upkeep`, each answering {"upkeep"}; 409 where nothing
    looks after the skills here, and while a deck is working (`upkeep` says so).
  - `/api/brand` {"repository", "release"} keeps the brand skill's repository once git can
    read it as this person, and answers the set-up; it is 400, with a sentence, when it
    cannot be read or has no such release. An empty repository forgets it.
    `/api/brand/install` {"release"} installs that release of the brand skill with its own
    installer, in the background, and answers {"upkeep"}; it is 409 while a deck is
    working, while anything else is in hand, while a companion waits for Update, and when
    `release` is not the one shown in `upkeep.versions.brand`.
  - `/api/computer` {}: look at this computer again, and at the skills, and wake the decks
    that were waiting on what was missing.
  - The desk, for a deck started from the desk's start (`engine.desk_*`), each answering the
    deck's view: `/api/desk-note` {"path", "number", "note", "expected"} redraws one slide's
    section with the note; `/api/desk-deck-note` {"path", "note", "expected"} every section;
    `/api/desk-stop` {"path"} stops that redraw and keeps what was redrawn;
    `/api/desk-deliver` {"path", "expected", "blockers_seen"?} delivers the deck on screen;
    `/api/desk-draw-here` {"path"} draws a deck this computer has no drawing of;
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
    first. Sources, research and Finishing: `/api/desk-source` {"path", "name", "content"}
    adds a file (`content` in base64; it alone may carry up to SOURCE_LIMIT bytes, and only
    with the key) or {"path", "text", "title"} pasted text, and starts nothing;
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

from studio_core import modules
from studio_core.shared_runner import page as _shared
modules.bind(globals(), _shared, _shared.NAMES)

READS = ('/api/capabilities', '/api/setup', '/api/agents', '/api/models', '/api/decks',
         '/api/run', '/api/slide', '/api/download', '/api/status', '/api/published',
         '/api/delete', '/api/file', '/api/known-decks', '/api/storyboard',
         '/api/desk-outline-price', '/api/desk-versions', '/api/desk-migration-preview', '/api/desk-ready-context')
# The desk's changes: each is an engine method by the same name, with what it is sent.
DESK = {'/api/desk-note': ('desk_note', ('number', 'note', 'expected')),
        '/api/desk-deck-note': ('desk_deck_note', ('note', 'expected')),
        '/api/desk-stop': ('desk_stop', ()),
        '/api/desk-deliver': ('desk_deliver', ('expected', 'blockers_seen?')),
        '/api/desk-draw-here': ('desk_draw_here', ()),
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
        '/api/desk-research-again': ('desk_research_again', ('expected',)),
        '/api/desk-leave-out': ('desk_leave_out', ('ids',)),
        '/api/desk-finish': ('desk_finish', ('tool', 'expected?', 'again?')),
        '/api/desk-apply': ('desk_apply', ('set', 'ids', 'seen')),
        '/api/desk-skip': ('desk_skip', ('set', 'ids')),
        '/api/desk-open': ('open_on_desk', ())}
SOURCE = '/api/desk-source'   # a source added on the desk: a file in base64, or pasted text
SOURCE_LIMIT = 12_000_000     # bytes: a document of up to 8 MB, in base64, with its name
# What a desk change takes as it is sent, not as text.
RAW = ('slides', 'field', 'ids', 'again')
WHOLE = ('seen', 'start', 'end', 'index')   # whole numbers, from zero
WRITES = ('/api/setup/check', '/api/setup', '/api/decks', '/api/run', '/api/decide',
          '/api/answer', '/api/share', '/api/fetch', '/api/drive', '/api/publish',
          '/api/delete', '/api/bring', '/api/companions', '/api/upgrade', '/api/restart',
          '/api/versions', '/api/brand', '/api/brand/install', '/api/shared',
          '/api/deliver', '/api/storyboard', '/api/review-draft', '/api/build-feedback', '/api/progress-seen',
          '/api/note', '/api/review-level', '/api/research-site', '/api/picture',
          '/api/picture-remove', '/api/desk-outline-price', SOURCE, *DESK)
WRITES = (*WRITES, '/api/desk-migrate', '/api/desk-ready')
PPTX = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
DECKS = '/api/decks'
DRAFT = '/api/deck-draft'   # a deck's storyboard, framed by the page and opened with a ticket
DECKS_LIMIT = 120_000_000    # bytes: a deck's form with its uploads, in base64
PICTURE = '/api/picture'
PICTURE_LIMIT = 28_000_000   # bytes: a picture of up to 20 MB for a slide, in base64
FILES = ('README.md', 'intake.md', 'classify.md', 'outline.md', 'look.md',
         'research/plan.md', 'research/report.md', 'research/review.md')
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
    framed = (DRAFT,)   # opened by the storyboard's frame, with a ticket

    # --- reads ---------------------------------------------------------------------------

    def read(self, path: str, one):
        if path in ('/api/desk-migration-preview', '/api/desk-ready-context'):
            from runner import desk_chat
            folder = self.deck(one('path'))
            value = desk_chat.migration_preview(self.engine, folder) if path.endswith('migration-preview') \
                else desk_chat.context(self.engine, folder, 'ready')
            return server.as_json(HTTPStatus.OK, value)
        self.engine.seen()
        if path == '/api/capabilities':
            return server.as_json(HTTPStatus.OK, {'runner': True,
                                                  'version': gitstate.installed()})
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
        if path == '/api/slide':
            return HTTPStatus.OK, PNG, self.slide(one)
        if path == '/api/download':
            return self.download(one('path'))
        if path == '/api/storyboard':
            return server.as_json(HTTPStatus.OK, self.framing(one('path'), self.engine.storyboard(
                self.deck(one('path')), None, one('expected'))))
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

    def framing(self, path: str, drawn: dict) -> dict:
        """A storyboard the runner drew, as the page frames it: the address of DRAFT with a
        ticket for that one file of that one deck. Called only for a request that sent the
        key."""
        ticket = self.ticket(DRAFT, {'path': path, 'draft': drawn['draft']})
        return {'src': f'{DRAFT}?ticket={ticket}', 'expected': drawn['expected'],
                'milliseconds': drawn['milliseconds']}

    def read_framed(self, path: str, scope) -> tuple:
        """A framed page whose ticket held: the storyboard it was issued for, served under its
        own sandboxed policy. Only the file the runner wrote in that deck's work/drafts/ is
        read; nothing the request names is."""
        if path != DRAFT or not isinstance(scope, dict):
            return super().read_framed(path, scope)
        try:
            body = self.engine.storyboard_page(scope.get('path'), scope.get('draft'))
        except (OSError, WorkspaceError):
            raise server.Refusal(HTTPStatus.NOT_FOUND, 'That draft is not here any more. '
                                                       'Show it again from the page.')
        return server.framed_html(body)

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

    def download(self, path: str) -> tuple:
        """The rendered deck, as a file to keep."""
        name, data = self.engine.download(self.deck(path))
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
        if address in (DECKS, PICTURE, SOURCE):
            try:
                self.check_token(headers)
            except server.Refusal:
                return super().body_limit(target, headers)
            return {DECKS: DECKS_LIMIT, PICTURE: PICTURE_LIMIT, SOURCE: SOURCE_LIMIT}[address]
        return super().body_limit(target, headers)

    # --- changes -------------------------------------------------------------------------

    def write(self, path: str, sent: dict):
        self.engine.seen()
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
        if path == '/api/storyboard':
            return server.as_json(HTTPStatus.OK, self.framing(
                server.text(sent, 'path'), self.engine.storyboard(
                    self.deck(server.text(sent, 'path')), sent.get('slides'),
                    server.text(sent, 'expected'))))
        if path == '/api/review-draft':
            return server.as_json(HTTPStatus.OK, self.engine.review_draft(
                self.deck(server.text(sent, 'path')), server.text(sent, 'expected')))
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
        if path == '/api/note':
            return server.as_json(HTTPStatus.OK, self.engine.note(
                self.deck(server.text(sent, 'path')), server.text(sent, 'text'),
                server.text(sent, 'expected')))
        if path == '/api/research-site':
            # A site for one deck's research, checked here as the deck's form will be.
            return server.as_json(HTTPStatus.OK, shaped(setup.research_site, sent))
        if path == '/api/review-level':
            level, seen = shaped(setup.review_choice, sent)
            return server.as_json(HTTPStatus.OK, setup.save_review_level(self.engine, level,
                                                                         seen))
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
            release = server.text(sent, 'release')
            return server.as_json(HTTPStatus.OK, {'upkeep': self.keeper().install_brand(
                self.working(), release)})
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
        if brands is not None:   # what makes no sense is said as such; the rest is the engine's
            shaped(decks.check_form, form, brands)
        return self.engine.start(form, uploads)

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
        """A source the person adds on the desk: {"path", "name", "content"} with the file in
        base64, or {"path", "text", "title"} with text they pasted."""
        deck = self.deck(server.text(sent, 'path'))
        if sent.get('content') is None:
            text = sent.get('text')
            if not isinstance(text, str) or len(text) > SOURCE_LIMIT:
                raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Paste the text of the source, or '
                                     'choose its file.')
            title = server.text(sent, 'title', needed=False)
            return self.desk(lambda: self.engine.desk_source(deck, None, text=text,
                                                             title=title))
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
                                                                       needed=False)))

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
        if decision not in engines.DECISIONS:
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'A decision is to approve, or to ask '
                                 'for changes: ' + ', '.join(engines.DECISIONS) + '.')
        if extra is not None and not isinstance(extra, dict):
            raise server.Refusal(HTTPStatus.BAD_REQUEST, 'Send what comes with a decision as '
                                 'one JSON object.')
        # Another brand, a slide whose words go back to the outline, a corrected reading
        # of the document, or a line against a slide: each says what should change itself.
        noted, target = (extra or {}).get('slide_notes'), (extra or {}).get('direction_target')
        wordless = gate == 'gate:look' \
            or (gate == 'gate:outline' and target in ('gate:look', 'gate:classify')) \
            or (gate == 'gate:build' and target == 'gate:outline') \
            or (gate == 'gate:build' and isinstance(noted, dict)
                and any(str(line or '').strip() for line in noted.values()))
        if decision == 'changes' and not wordless and not (note or '').strip() \
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
