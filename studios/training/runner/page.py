"""The runner's server: the desk's page, with the runner behind it.

What a caller needs to know
---------------------------
    server = page.Studio(engine, port)    # the desk's server, answering for the runner too
    server.url                            # the link, with its key; for a person only
    server.serve()                        # until interrupted; server.stop() ends the engine

- It serves the same page as the desk and keeps every one of its rules: it answers on the
  local machine only, checks the `Host` header, needs the key for every call, and takes a
  change only as a POST with a JSON body from the page's own origin. Those rules live in
  the desk's `Page`; `RunnerPage` adds addresses and never loosens a rule.
- What it adds is the contract in the appendices of the milestone 2, 3, 4 and 5
  specifications: whether the runner is here, set-up, the agents, starting a training, a
  run, an answer to a worker's question, the person's documents, the copies, sharing,
  the decision about what a deck says, a slide's picture, who drives a training, the
  status of every run, publishing, and bringing a training in.
- A training in a shared workspace is run from one computer. List items and `GET /api/run`
  carry `driver`: null when nobody drives it, else {"name", "here", "since"}; `mine`,
  whether this computer may change it (null in a list for a training no run drives);
  `notice`, a sentence saying that it was taken from this computer and that what this
  computer had not shared is kept here, or that the training was changed on two computers
  at once; and `last_shared`, {"at", "by", "says"} for a training someone else drives,
  whose state is `elsewhere`: only what was last shared is known here. A run also carries
  `queue`, {"ahead": n} while it waits its turn; `taken`, {"by", "at", "kept"} for one
  that was taken from this computer, until it is taken back; `kept`, the names git
  keeps under, in this computer's copy, whatever this computer set aside of the
  training; and `clash`, true while it stands changed on two computers. Every address that changes a training someone else drives, or
  nobody does, answers 409 with who has it: a decision, a move of its decisions, a run's
  actions, an answer, its documents, its copies, and what its deck says. A training
  driven elsewhere never counts as needing the person here.
- `GET /api/download?path=&artifact=[&copy=word]` answers authenticated attachment bytes for a registered supported deliverable or the finished index; names are never filesystem paths.
- `POST /api/copies` with `pull: "<artifact>"` explicitly pulls its Google Doc. `choose: ours|theirs` resolves a confirmed conflict only while the local, remote and kept-text revisions still match. It answers the refreshed run and a sentence.
- The run adds `decided` while work continues after a decision and combined-review beads to its saved stage row. New runs use review layout 2; existing runs retain layout 1.
- `GET /api/models?agent=codex` answers what an agent offers to choose from: {"agent",
  "models": [{"name", "label", "family", "about", "levels", "default_level"}], "levels",
  "source", "problem"}. `levels` beside the models are those a model that is not listed may
  be given, and `source` where a list the runner keeps came from. A list that could
  not be made is still answered, with no models and `problem` saying why, so the page can
  say so and still take a name typed in. It is kept a while, and listing holds up nothing
  else the page asks.
- `POST /api/drive` with {"path", "action"} takes a training (`take`), which also takes
  one over, or hands it over (`hand-over`), and answers the run. `POST /api/fetch` brings
  in what teammates shared and sends nothing: {"reached", "received", "notice"}.
- `GET /api/status` answers {"limit", "runs", "elsewhere"}: each run on this computer as
  {"path", "id", "title", "state", "sentence", "driver", "needs", "queue", "spent",
  "notice"}, and each training a teammate drives as the first six of those with
  `last_shared` and `notice`. `limit` is how many trainings work at once.
- `POST /api/publish` with {"path"} answers {"revision", "ready", "shared", "notice"}.
  `GET /api/published` answers {"published": [{"path", "id", "title", "revision", "at",
  "by", "ready", "current"}]}, each training's latest revision; `current` is false when
  the training has changed here since. A training someone else drives is
  not published from here.
- `GET /api/delete?path=` answers what deleting a training would do: {"path", "title",
  "state", "may", "why", "stops", "share", "revisions", "documents", "drive"}, where
  `drive` lists each file it left in Google Drive as {"what", "name", "url"}. `POST
  /api/delete` with {"path", "title"} deletes it, stopping it first, and answers
  {"deleted", "title", "shared", "notice"}. The title must be the training's own. A
  training a conversation made is 404 here: the runner never deletes a folder it does
  not drive.
- `GET /api/setup` and `GET /api/status` carry `upkeep`: what `upkeep.Upkeep.report` says
  of Training Studio and its skills on this computer, or null where the runner does not
  look. `POST /api/companions`, with {}, brings each companion skill that is missing or
  older than its pin, in the background, through the installer's own checked install, and
  answers `upkeep`. It is 409 while a training here is working, while an update is in
  hand, and when there is nothing to bring. The page asks for it only after the person
  said yes in its confirmation.
- `upkeep.versions` has a row each for Training Studio and its companions, with what is
  installed, the newest, the pins and a state. `POST /api/upgrade` with {"version"}
  installs that newer Training Studio beside this one, in the background, and answers
  `upkeep`; it is 409 from a checkout, while a training is working, while anything else is
  in hand, and when `version` is not the newest known. Once it is installed, `POST
  /api/restart` with {} stops the runner, which then opens the newer version on the same
  port with the same key; it is 409 while a training is working. `POST /api/versions` with
  {"dismiss": key} stops Home showing the versions until a newer one is out. The page asks
  for each only after the person said yes.
- `POST /api/brand` with {"repository", "release"} keeps the brand skill's repository once
  git can read it as this person, and answers the set-up; it is 400, with a sentence, when
  it cannot be read or has no such release. An empty repository forgets it. `POST
  /api/brand/install` with {"release"} installs that release of the brand skill with its own
  installer, in the background, and answers `upkeep`; it is 409 while a training is working,
  while anything else is in hand, while a companion waits for Update, and when `release`
  is not the one shown in `upkeep.versions.brand`.
- The values every studio shares are kept only in the studios config, so `POST /api/setup`
  and `POST /api/brand` write the ones they change there, and are 409 and 400, with a
  sentence, when one changes while that file cannot be read, or when the form was opened
  before another studio changed that same value: each takes `shared_seen`, the `shared`
  the form was shown, to tell what the person changed. `GET /api/setup` carries
  `shared`, what the file holds that Training Studio can use; `shared_problem`, a sentence
  when it could not be read; `team_moved`, {"repository", "branch", "says"} when it names
  a team repository this computer's workspace is not a copy of; and `shared_notice`, a
  sentence about the values the file already held when this computer's own moved there.
  `POST /api/shared` with {"seen": true} stops it being shown and answers the set-up. See
  `setup` and `studios_config`.
- `POST /api/adopt` with {"path"} copies a training this computer knows, started in a
  conversation, into the workspace, and answers {"path", "id"} of the copy.
- Every request that passes the rules tells the engine a page is open, which is how the
  runner knows not to notify through the computer instead.
- `POST /api/documents` alone may carry up to DOCUMENT_LIMIT bytes, because it carries a
  document, and only when it is asked with the key. Every other address keeps the desk's
  limit, and every one of the desk's rules still applies to this one.
- `GET /api/gate` gains `whose` for a practice scenario: who wrote its file. For a Yoodli
  scenario it gains `beside`, the scenario it was laid out from. For a deck it gains
  `slides`, `review`, `audit` and `coverage`; `review` and `audit` are null, and the other
  two empty, for a deck the runner did not make.
- `GET /api/slide` answers one slide's picture as `image/png`, and nothing else: of a deck
  the runner rendered, named by `artifact`, or of a `section`'s latest preview while a
  deck is drawn, by `number`. It needs the key like every other read. What it sends is
  never read from an address the request gives: the place is worked out from the
  training, the deck or the section, and the number, and only a PNG found there, inside
  the training's own folder or the folder of the worker drawing that section, is sent.
- `POST /api/outline` records what the person decided about what a deck says, which is the
  runner's own gate, and answers the run.
- `GET /api/deck-draft-ticket` with `path` and `level` draws a deck's wireframe draft into
  its own work folder, once for each version of what it says, and answers {"src"}: the
  address a sandboxed frame opens it at, `/api/deck-draft?ticket=…`, good for that one page
  for two minutes. That address answers the page under its own policy (CSP sandbox,
  default-src 'none'), so the draft can run nothing and reach nothing of the page.
- `POST /api/look` with {"path", "level", "choice", "words"?} records the look the person
  chose for a deck from the brand's rendered samples, in their words, and answers the run.
  A run carries `look` while there are looks to show; `GET /api/slide` with the deck's
  `artifact`, `section` "look" and a look's `number` (0 for the sheet of them all) answers
  its picture.
- A run carries `redesign`: each of its decks drawn without a design, as {"level",
  "artifact", "label", "may", "why"}. `POST /api/redesign` with {"path", "level"} draws one
  again from a design, after the person said yes in the page's confirmation, and answers
  the run. It is 409 while the training works, for a deck that has its design already, and
  where this computer cannot make a deck from one, saying why.
- A decision at gate 6 about a deck the slides tool put to the person with its review is
  sent to that tool first, as their answer to its question; a refusal there is 409, and
  the core records nothing.
- `POST /api/asset` with {"path", "level", "asset", "content", "alt", "source",
  "restrictions"?} gives the slides tool a picture the person supplies for an asset of
  their deck's approved design, and answers the run. `content` is the picture in base64;
  like a document, it may be up to DOCUMENT_LIMIT bytes. A deck waiting for it carries on.
- The page's check of this computer gains what a deck needs here. Asking for a new look
  also lets the trainings that were waiting on what was missing carry on, and looks at the
  skills again, putting back a link the installer placed that has gone missing.
- `GET /api/download?path=&artifact=&copy=word` sends a managed deliverable or its Word
  copy as an attachment, with the same authenticated read rules. `README.md` names the index.
- `GET /api/file` also answers for `README.md`, the index at the top of a training this
  computer knows, once it is written. The index is derived and is not one of a training's
  own files, so the desk alone refuses it.
- A refusal is `{"error": "<a sentence for a person>"}`. Something sent in the wrong shape
  is 400, a training this computer does not know is 403, a training no run is driving is
  404, and something that cannot be done as things stand is 409.
- The desk's lists gain `run`, and a training whose run has a question or a problem
  counts as needing the person. One that someone else drives, or nobody does, never
  does: it is `in-progress` here, and keeps `waiting` only so that what was waiting when
  it was last shared can be read. A decision made through the desk's own `decide` is
  committed and wakes that training's run, and what the page is told then says what the
  runner does next, not what an assistant in a conversation would.
- Reading never starts or wakes a run: `GET /api/run` can be asked for as often as the
  page likes.
- A training started on the desk (`flow: 'desk'`) is shown and changed there: `GET
  /api/drafts?path=` answers `drafts.view`, and `POST /api/drafts/ready` {path, name,
  seen}, `/api/drafts/level-ready` {path, level, seen: {name: hash}}, `/api/drafts/update`
  {path, name}, `/api/drafts/keep` {path, name, reason, seen} and `/api/drafts/send` {path,
  name} each answer it after the change (`level-ready` adds `marked` and `stopped`, `send`
  adds `made` and `problems`). Each is 409 with `drafts.NOT_ON_DESK` for a saved training,
  and a desk training is 409 with `drafts.ON_DESK` at `/api/decide`, `/api/review`,
  `/api/outline`, `/api/look` and `GET /api/gate`. A teammate reads the desk with only
  Download on each card, and each change is refused with who runs the training.
- A guide, brief or plan is typed into part by part; scenarios and Yoodli layouts use one
  whole-file part (`opening`). `GET /api/drafts/card?path=&name=` answers
  the card's view (`drafts.card`: the card, its parts with their revision and version
  counts, and the whole desk as `desk`); `POST /api/drafts/save` {path, name, part, seen:
  the revision the form saw, text, session} and `/api/drafts/restore` {path, name, part,
  seen, index} answer it after the change, with `said` when the desk could not accept a
  save it made; `GET /api/drafts/versions?path=&name=&part=` answers the part's History
  with each version's `label` and the words of each kind of change as `sources`. Typing is
  committed together (`Engine.pending_commit`), and `POST /api/drafts/share` {path}, sent
  when the person leaves the desk, commits it and shares it under the team's setting:
  {"committed"}. A person-owned scenario uses `POST /api/drafts/layout` {path, name, seen:
  file digest, note} to request the existing keep-wording layout path; rewrite is refused.
- While a run is driving a training, its decisions cannot be moved back to a conversation:
  a gate the runner waits at would then be one an assistant could pass. They can be moved
  once the run is done as far as it goes, which is how a slide deck gets made. Moving them
  either way wakes the run, which then looks at the training's files again.
"""
from __future__ import annotations

# ruff: noqa: F821  names bound from studio_core.shared_runner are unseen by a linter;
# test_shared_runner_use checks the bound parts, and the suites call the rest.

import base64
import binascii
import re
from http import HTTPStatus
from urllib.parse import urlencode
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import desk
import home
import workspace
from workspace import WorkspaceError
from studio_core import research_sites

from runner import engine as engines
from runner import drafts, gitstate, pipeline, setup

from studio_core import modules
from studio_core.shared_runner import page as _shared
modules.bind(globals(), _shared, _shared.NAMES)

DRAFTS = '/api/drafts'
# The desk's decisions, each under DRAFTS: Mark ready, Mark this level ready, Update, Keep as
# it is, and Send to its copies.
DECIDED = tuple(f'{DRAFTS}/{action}' for action in ('ready', 'level-ready', 'update', 'keep',
                                                     'send'))
# Typing into a part, bringing back one of its versions, and committing what was typed.
TYPED = tuple(f'{DRAFTS}/{action}' for action in ('save', 'restore', 'share'))
JOBS = tuple(f'{DRAFTS}/{action}' for action in ('note', 'revise', 'selection', 'stop', 'retry', 'layout', 'write-whole'))
VERSIONS = f'{DRAFTS}/versions'
CARD = f'{DRAFTS}/card'   # one card with its parts, as the shared kit reads it
PART_LIMIT = 1_000_000   # bytes: one part of the largest size, as JSON
READS = ('/api/capabilities', '/api/setup', '/api/agents', '/api/models', '/api/run',
         '/api/download', '/api/slide', '/api/status', '/api/published', '/api/delete', '/api/deck-draft-ticket',
         DRAFTS, CARD, VERSIONS, f'{DRAFTS}/update-preview')
WRITES = ('/api/setup/check', '/api/setup', '/api/trainings', '/api/run', '/api/answer',
          '/api/documents', '/api/copies', '/api/share', '/api/outline', '/api/review', '/api/drive',
          '/api/publish', '/api/adopt', '/api/fetch', '/api/delete', '/api/companions',
          '/api/asset', '/api/upgrade', '/api/restart', '/api/versions', '/api/redesign',
          '/api/brand', '/api/brand/install', '/api/shared', '/api/note', '/api/look',
          '/api/review-level', '/api/research-site', f'{DRAFTS}/open',
          f'{DRAFTS}/slide-note', f'{DRAFTS}/slide-words', f'{DRAFTS}/slide-speaker-notes', f'{DRAFTS}/slide-words-decide',
          f'{DRAFTS}/finding', *DECIDED, *TYPED, *JOBS)
KINDS = {
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.pdf': 'application/pdf', '.md': 'text/markdown; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
}
NAMED = re.compile(r'[^A-Za-z0-9._-]+')
DOCUMENTS = '/api/documents'
ASSET = '/api/asset'
DOCUMENT_LIMIT = 12_000_000     # bytes: one document of the largest size, in base64
CLOSE = 'You can close this page; it says when it needs you again.'
HALTED = ('This training is not running, so nothing more happens until you resume it or '
          'try again.')
RUNNER_DECIDES = ('The runner is driving this training, so its decisions are made on the '
                  'page.')


def shaped(action, *args):
    """Run something that reads what was sent. Its refusal means the request was wrong."""
    try:
        return action(*args)
    except WorkspaceError as refusal:
        raise desk.Refusal(HTTPStatus.BAD_REQUEST, str(refusal))


def research_site(sent: dict) -> dict:
    """One site as research keeps it, {'site', 'shown'}, or a sentence naming it."""
    if not isinstance(sent, dict) or set(sent) != {'site'}:
        raise WorkspaceError('Give one site to check.')
    try:
        found = research_sites.site(sent['site'])
    except ValueError as error:
        raise WorkspaceError(str(error)) from None
    return {'site': found, 'shown': research_sites.shown(found)}


class RunnerPage(desk.Page):
    """What the page may ask the runner, on top of what it may ask the desk."""
    reads = (*desk.READS, *READS)
    writes = (*desk.WRITES, *WRITES)
    framed = ('/api/deck-draft',)   # a deck's wireframe draft, opened by its frame

    # --- reads ---------------------------------------------------------------------------

    def read(self, path: str, one):
        self.engine.seen()
        if path == '/api/download':
            def given(name):
                try:
                    return one(name)
                except desk.Refusal:
                    return None
            return self.download(one('path'), one('artifact'), given('copy'))
        if path == '/api/status':
            return desk.as_json(HTTPStatus.OK, self.engine.standing())
        if path == '/api/published':
            return desk.as_json(HTTPStatus.OK, {'published': self.engine.published()})
        if path == '/api/capabilities':
            return desk.as_json(HTTPStatus.OK, {'runner': True,
                                                'version': gitstate.installed()})
        if path == '/api/setup':
            return desk.as_json(HTTPStatus.OK, setup.describe(self.engine))
        if path == '/api/agents':
            return desk.as_json(HTTPStatus.OK, {'agents': self.agents()})
        if path == '/api/models':
            return desk.as_json(HTTPStatus.OK, shaped(self.engine.models, one('agent')))
        if path == '/api/run':
            return desk.as_json(HTTPStatus.OK, self.run(one('path')))
        if path == '/api/delete':
            return desk.as_json(HTTPStatus.OK, self.engine.leaving(self.driving(one('path'))))
        if path == DRAFTS:
            return desk.as_json(HTTPStatus.OK, drafts.view(self.engine,
                                                           self.on_desk(one('path'))))
        if path == CARD:
            root = self.on_desk(one('path'))
            name = one('name')
            return desk.as_json(HTTPStatus.OK, self.typed(lambda: self.engine.draft_card(
                root, name)))
        if path == f'{DRAFTS}/update-preview':
            root = self.on_desk(one('path'))
            with self.engine.files:
                return desk.as_json(HTTPStatus.OK, drafts.update_preview(root, one('name')))
        if path == VERSIONS:
            root = self.on_desk(one('path'))
            name, part = one('name'), one('part')
            return desk.as_json(HTTPStatus.OK, self.typed(lambda: self.engine.draft_versions(
                root, name, part)))
        if path == '/api/gate':
            self.not_on_desk(one('path'))
            return desk.as_json(HTTPStatus.OK, self.gate(one('path'), one('artifact')))
        if path == '/api/slide':
            return HTTPStatus.OK, PNG, self.slide(one)
        if path == '/api/deck-draft-ticket':
            def given(name):
                try:
                    return one(name)
                except desk.Refusal:
                    return None
            return desk.as_json(HTTPStatus.OK, self.deck_draft(
                {'path': one('path'), 'level': given('level')}))
        if path == '/api/file' and one('artifact') in (pipeline.INDEX, 'reviews/research.md'):
            return desk.as_json(HTTPStatus.OK, self.index(one('path'), one('artifact')))
        return super().read(path, one)

    def download(self, path: str, artifact: str, copy: str | None = None) -> tuple:
        """Send only a managed deliverable, as an attachment under the page's read rules."""
        desk.registered(path)
        if copy is not None and copy != 'word':
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give copy as word.')
        root, level = Path(path), None
        if artifact == pipeline.INDEX and copy is None:
            relative = pipeline.INDEX
        else:
            root, session = desk.artifact_of(path, artifact)
            level = workspace.split(artifact)[1]
            relative = workspace.artifact(root, session, artifact)['file']
            if copy == 'word':
                relative = (session['exports'].get(artifact) or {}).get('file')
                if not relative:
                    raise desk.Refusal(HTTPStatus.NOT_FOUND,
                                       f'There is no Word copy of {desk.named(artifact)} yet.')
        file = desk.inside(root, relative)
        if not file.is_file():
            raise desk.Refusal(HTTPStatus.NOT_FOUND, f'{relative} has not been made yet.')
        name = NAMED.sub('-', '-'.join(filter(None, [root.name, level, Path(relative).name])))
        return (HTTPStatus.OK, KINDS.get(file.suffix.lower(), 'application/octet-stream'),
                file.read_bytes(), {'Content-Disposition': f'attachment; filename="{name}"'})

    def index(self, path: str, relative=pipeline.INDEX) -> dict:
        """A training's index, in the shape the desk gives any of its files."""
        desk.registered(path)
        file = desk.inside(Path(path), relative)
        if not file.is_file():
            raise desk.Refusal(HTTPStatus.NOT_FOUND, 'The index has not been written yet.'
                               if relative == pipeline.INDEX else 'The research check has not been saved yet.')
        shown = {'artifact': relative, 'file': relative,
                 'size': file.stat().st_size, 'binary': True}
        found = desk.text_of(file)
        if found is None:
            return shown
        return {**shown, 'binary': False, 'text': found[0], 'truncated': found[1]}

    def gate(self, path: str, name: str) -> dict:
        """The desk's gate. A practice scenario's also says whose file it is, and a Yoodli
        scenario's names the scenario it was laid out from, to show beside it."""
        shown = desk.gate(path, name)
        shown['combined'] = self.engine.reviewing(path)
        # What Ask for changes writes again, and what that took, said before it is asked for.
        shown['redo'] = self.engine.redo(path, name)
        if name == 'research':
            shown['research_price'] = self.engine.research_price(path)
            # Pages refused for being outside your sites, said with the sites named.
            looks = self.engine.research_from(path)
            shown['outside'] = looks['outside'] if looks else None
            if shown.get('research') and shown['outside']:
                shown['research'] = {**shown['research'], 'outside': shown['outside']}
        kind = workspace.split(name)[0].partition(':')[0]
        if kind == 'scenario':
            shown['whose'] = self.engine.whose(path, name)
        elif kind == 'yoodli':
            source = name.replace('yoodli:', 'scenario:', 1)
            shown['beside'] = {'artifact': source, 'label': desk.named(source)}
        elif kind == 'deck':
            shown.update(self.engine.deck_gate(path, name))
        return shown

    def slide(self, one) -> bytes:
        """One slide's picture. The request names a training this computer knows, a deck
        of it or a section of the deck being drawn, and a number, and nothing else."""
        def given(name: str) -> str | None:
            try:
                return one(name)
            except desk.Refusal:
                return None

        path, artifact, section = one('path'), given('artifact'), given('section')
        if (artifact is None) == (section is None):
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Name the deck as artifact, or the '
                               'section, and not both.')
        if not one('number').isascii() or not one('number').isdigit():
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give number as a whole number.')
        desk.registered(path)
        if self.engine.driven(path) is None:
            raise desk.Refusal(HTTPStatus.NOT_FOUND, 'No run is driving this training.')
        try:
            return shaped(self.engine.picture, path, int(one('number')), artifact, section)
        except OSError:
            raise desk.Refusal(HTTPStatus.NOT_FOUND, engines.NO_PICTURE)

    def computer(self, look: bool) -> dict | None:
        """The desk's look at this computer, with what a deck needs here. A new look is a
        new look at those too, and wakes the trainings that were waiting on them."""
        seen = super().computer(look)
        if seen is None:
            return None
        keep = getattr(self.engine, 'upkeep', None)
        if look and keep is not None:
            keep.again()
        needs = self.engine.look_again() if look else self.engine.deck_needs()
        wanted = self.uses_deck()
        items = [{**item, 'optional': not wanted} for item in needs['items']]
        wrong = [*seen['wrong'], *(item['name'] for item in items
                                   if item['state'] != 'ok' and wanted)]
        return {**seen, 'items': [*seen['items'], *items], 'wrong': wrong,
                'ready': seen['ready'] and not wrong}

    @staticmethod
    def uses_deck() -> bool:
        """Whether any training on this computer wants a deck."""
        for entry in home.trainings():
            try:
                if 'deck' in pipeline.wanted(workspace.load(Path(entry['path']))):
                    return True
            except (WorkspaceError, OSError):
                continue
        return False

    def body_limit(self, target: str, headers) -> int:
        """A document may be sent whole, to its own address, and so may a part typed on the
        desk, by whoever holds the key. Anyone else's request there is held to the desk's
        limit, so it is refused unread."""
        address = target.partition('?')[0]
        if address in (DOCUMENTS, ASSET, f'{DRAFTS}/save'):
            try:
                self.check_token(headers)
            except desk.Refusal:
                return super().body_limit(target, headers)
            return PART_LIMIT if address == f'{DRAFTS}/save' else DOCUMENT_LIMIT
        return super().body_limit(target, headers)

    def driving(self, path: str) -> str:
        """A training this computer knows, once a run drives it. Any other folder, such as
        one a conversation made, is never the runner's to change."""
        desk.registered(path)
        if self.engine.driven(path) is None:
            raise desk.Refusal(HTTPStatus.NOT_FOUND, 'No run is driving this training.')
        return path

    def on_desk(self, path: str) -> Path:
        """A desk training's folder, once this computer knows it and a run drives it. A
        saved training is refused: the desk's routes are not its own."""
        desk.registered(path)
        root = self.engine.driven(path)
        if root is None:
            raise desk.Refusal(HTTPStatus.NOT_FOUND, 'No run is driving this training.')
        if not drafts.on_desk(drafts.run_of(root)):
            raise desk.Refusal(HTTPStatus.CONFLICT, drafts.NOT_ON_DESK)
        return root

    def not_on_desk(self, path: str) -> None:
        """Refuse a review screen's route for a desk training, which has none: it is
        changed on the desk. Any other training is answered as it always was."""
        root = self.engine.driven(path)
        if root is not None and drafts.on_desk(drafts.run_of(root)):
            raise desk.Refusal(HTTPStatus.CONFLICT, drafts.ON_DESK)

    def drafted(self, path: str, sent: dict) -> dict:
        """One of the desk's decisions, as the person made it on a card, answered with the
        desk's view: Mark ready {name, seen}, Mark this level ready {level, seen: {name:
        hash}}, which adds `marked` and `stopped`, Update {name}, Keep as it is {name,
        reason, seen}, and Send to its copies {name}, which adds `made` and `problems`."""
        root = self.on_desk(desk.text(sent, 'path'))
        name = None if path == f'{DRAFTS}/level-ready' else desk.text(sent, 'name')
        added = {}
        try:
            if path == f'{DRAFTS}/ready':
                self.engine.mark_ready(root, name, desk.text(sent, 'seen', False))
            elif path == f'{DRAFTS}/level-ready':
                level, seen = sent.get('level'), sent.get('seen')
                if level is not None and not isinstance(level, str) \
                        or seen is not None and not isinstance(seen, dict):
                    raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give the level as text and '
                                       'what was shown of each card by its name.')
                added = self.engine.mark_level_ready(root, level or None, seen or {})
            elif path == f'{DRAFTS}/update':
                self.engine.update(root, name)
            elif path == f'{DRAFTS}/keep':
                self.engine.keep(root, name, desk.text(sent, 'reason', False),
                                 desk.text(sent, 'seen', False))
            else:
                added = self.engine.send_copy(root, name)
        except WorkspaceError as refusal:
            raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))
        return {**drafts.view(self.engine, root), **added}

    def part(self, path: str, sent: dict) -> dict:
        """Typing on the desk: save {name, part, seen: the revision the form saw, text,
        session} and restore {name, part, seen, index}, each answered with the card's new
        view, and share {}, which commits what was typed and answers {'committed'}."""
        root = self.on_desk(desk.text(sent, 'path'))
        if path == f'{DRAFTS}/share':
            return self.typed(lambda: self.engine.draft_share(root))
        name, part = desk.text(sent, 'name'), desk.text(sent, 'part')
        if path == f'{DRAFTS}/restore':
            return self.typed(lambda: self.engine.draft_restore(
                root, name, part, sent.get('seen'), sent.get('index')))
        text = sent.get('text')
        if not isinstance(text, str):
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give text as text.')
        return self.typed(lambda: self.engine.draft_save(
            root, name, part, sent.get('seen'), text, desk.text(sent, 'session', False)))

    @staticmethod
    def typed(action):
        """A desk change to one part, or a read of one: its refusal says why, as the
        desk's decisions do."""
        try:
            return action()
        except WorkspaceError as refusal:
            raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))

    def run(self, path: str) -> dict:
        """One training's run, for a training this computer knows."""
        desk.registered(path)
        found = self.engine.view(path)
        if found is None:
            raise desk.Refusal(HTTPStatus.NOT_FOUND, 'No run is driving this training.')
        return found

    # --- the desk's lists ----------------------------------------------------------------

    def trainings(self) -> list[dict]:
        return [self.with_run(item) for item in super().trainings()]

    def detail(self, path: str) -> dict:
        return self.with_run(super().detail(path))

    def with_run(self, item: dict) -> dict:
        """Add a training's run to what the desk says about it. A run with a question or
        a problem makes the training one that needs the person."""
        found = self.engine.brief(item['path'])
        item['run'] = found and {'state': found['state'], 'sentence': found['sentence']}
        if found and (found.get('flow') == 'desk' or found['state'] == 'done'):
            item['run'].update(flow=found.get('flow'),
                               can_open_desk=found.get('can_open_desk', False))
        item['driver'] = found and found['driver']
        item['mine'] = None if found is None else found['mine']
        item['notice'] = found and found['notice']
        item['last_shared'] = found and found['last_shared']
        if found is None or 'error' in item:
            return item
        item['stages'] = self.engine.review_beads(item['path'], item['stages'])
        # A worker in hand is activity too, from the moment it began.
        if found.get('busy_since') and item.get('activity_at'):
            item['activity_at'] = max(item['activity_at'], found['busy_since'])
        session = workspace.load(Path(item['path']))
        # On the desk a material the desk accepted is a draft until the person marks it
        # ready.
        person = (workspace.person_statuses(Path(item['path']), session)
                  if workspace.on_desk(session) else {})
        for file in (item.get('view') or {}).get('files') or ():
            accepted = (session['artifacts'].get(file['artifact']) or {}).get('approved') or {}
            if file['status'] == 'approved' and person.get(file['artifact']) == 'draft':
                file.update(status='draft', words=drafts.DRAFT_WORDS)
            elif file['status'] == 'approved' and accepted.get('by') == 'review-policy':
                file['words'] = 'Continued automatically'
        if not found['mine']:   # it waits for whoever drives it, not for the person here
            if item.get('state') == 'needs-you' or (item.get('state') == 'in-progress'
                                                    and found['state'] != 'done'):
                # What was waiting when it was last shared is kept, to be read.
                item.update(state='in-progress', sentence=found['sentence'])
        elif found['needs'] and item.get('state') != 'needs-you':
            item.update(state='needs-you', sentence=found['sentence'],
                        waiting={'artifact': None, 'label': None,
                                 'question': found['question'], 'recorded': False})
        elif item.get('state') == 'in-progress' and found['state'] != 'done':
            item['sentence'] = found['sentence']
        return item

    # --- the desk's changes --------------------------------------------------------------

    def decide(self, path: str, target: str, decision: str, note: str | None,
               seen: str | None, refresh: bool = False) -> dict:
        """Record a decision as the desk does. For a training a run is driving it is then
        committed, shared if that is wanted, and the run is woken. A desk training has no
        gates: it is refused, and changed on the desk."""
        self.not_on_desk(path)
        with self.engine.files:
            self.engine.hold(path)
            try:   # a deck the slides tool presented has the approval sent to it first
                self.engine.refuse_while_reviewing(path, decision)
                self.engine.deck_decided(path, target, decision, note, seen)
            except WorkspaceError as refusal:
                raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))
            reply = super().decide(path, target, decision, note, seen, refresh)
            driven = self.engine.decided(path, reply['decided'], checked=True)
        if not driven:
            return reply
        self.engine.carry_on(path)
        state, coming = self.engine.ahead(path)
        if state in ('paused', 'stopped', 'failed'):
            coming = HALTED
        elif state == 'working':
            coming = f'{coming} {CLOSE}'
        reply['said'] = f'{desk.SAID[decision]} {coming}'
        reply['next'] = desk.next_up(self.trainings())
        return reply

    def move_approval(self, path: str, mode: str) -> dict:
        """Move a training's decisions as the desk does, except away from the page while a
        run is driving the training. The change is committed for a training a run drove."""
        desk.registered(path)
        self.engine.hold(path)
        found = self.engine.brief(path)
        if found is not None and mode == 'chat' and found['state'] != 'done':
            raise desk.Refusal(HTTPStatus.CONFLICT, RUNNER_DECIDES)
        with self.engine.files:
            self.engine.hold(path)
            reply = super().move_approval(path, mode)
            driven = self.engine.changed(path, f'decisions are now made '
                                         f'{workspace.WHERE[mode]}')
        if driven:
            self.engine.wake(path)
        return reply

    # --- writes --------------------------------------------------------------------------

    def write(self, path: str, sent: dict):
        self.engine.seen()
        if path == '/api/drive':
            return desk.as_json(HTTPStatus.OK, self.drive(sent))
        if path == '/api/publish':
            return desk.as_json(HTTPStatus.OK, self.engine.publish(self.known(sent)))
        if path == '/api/adopt':
            return desk.as_json(HTTPStatus.OK, self.adopt(sent))
        if path == '/api/fetch':
            return desk.as_json(HTTPStatus.OK, self.engine.fetch())
        if path == '/api/companions':
            return desk.as_json(HTTPStatus.OK, {'upkeep': self.update()})
        if path == '/api/upgrade':
            version = desk.text(sent, 'version')
            return desk.as_json(HTTPStatus.OK, {'upkeep': self.keeper().upgrade(
                self.working(), version)})
        if path == '/api/restart':
            return desk.as_json(HTTPStatus.OK, {'upkeep': self.keeper().restart(
                self.working())})
        if path == '/api/versions':
            return desk.as_json(HTTPStatus.OK, {'upkeep': self.keeper().dismiss(
                desk.text(sent, 'dismiss'))})
        if path == '/api/brand':
            return desk.as_json(HTTPStatus.OK, shaped(setup.save_brand, self.engine, sent))
        if path == '/api/review-level':
            level, seen = shaped(setup.review_choice, sent)
            return desk.as_json(HTTPStatus.OK, setup.save_review_level(self.engine, level,
                                                                       seen))
        if path == '/api/research-site':
            # A site added on the start form for one training only: checked here, the one
            # check every studio uses, and saved nowhere. The shared list is changed in
            # Shared settings.
            return desk.as_json(HTTPStatus.OK, shaped(research_site, sent))
        if path == '/api/shared':
            if sent.get('seen') is not True:
                raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Send {"seen": true} once the '
                                   'notice about the shared values has been read.')
            setup.notice_read()
            return desk.as_json(HTTPStatus.OK, setup.describe(self.engine))
        if path == '/api/brand/install':
            release = desk.text(sent, 'release')
            return desk.as_json(HTTPStatus.OK, {'upkeep': self.keeper().install_brand(
                self.working(), release)})
        if path == '/api/delete':
            title = desk.text(sent, 'title')
            return desk.as_json(HTTPStatus.OK, self.engine.delete(
                self.driving(desk.text(sent, 'path')), title))
        if path == '/api/setup/check':
            return desk.as_json(HTTPStatus.OK, shaped(setup.check, sent))
        if path == '/api/setup':
            return desk.as_json(HTTPStatus.OK,
                                setup.apply(self.engine, shaped(setup.read, sent)))
        if path == '/api/trainings':
            form = shaped(pipeline.check_form, sent, self.engine.brands())
            return desk.as_json(HTTPStatus.OK, self.engine.start(form))
        if path == '/api/run':
            return desk.as_json(HTTPStatus.OK, self.act(sent))
        if path == '/api/answer':
            return desk.as_json(HTTPStatus.OK, self.answered(sent))
        if path == '/api/note':
            path = desk.text(sent, 'path')
            self.run(path)
            return desk.as_json(HTTPStatus.OK, self.engine.note(
                path, desk.text(sent, 'text'), desk.text(sent, 'expected')))
        if path == DOCUMENTS:
            return desk.as_json(HTTPStatus.OK, self.supplied(sent))
        if path == '/api/copies':
            return desk.as_json(HTTPStatus.OK, self.copied(sent))
        if path == '/api/share':
            return desk.as_json(HTTPStatus.OK, self.engine.share())
        if path == ASSET:
            return desk.as_json(HTTPStatus.OK, self.asset(sent))
        if path == f'{DRAFTS}/open':
            training = desk.text(sent, 'path')
            desk.registered(training)
            try:
                return desk.as_json(HTTPStatus.OK, self.engine.open_on_desk(training))
            except WorkspaceError as refusal:
                raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))
        if path == f'{DRAFTS}/finding':
            root = self.on_desk(desk.text(sent, 'path'))
            level = desk.text(sent, 'level', False) or None
            ids = sent.get('ids')
            if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
                raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Choose the suggestions to change.')
            try:
                result = self.engine.deck_finding(root, level, desk.text(sent, 'seen'),
                                                  desk.text(sent, 'job'),
                                                  desk.text(sent, 'action'), ids)
            except WorkspaceError as refusal:
                raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))
            return desk.as_json(HTTPStatus.OK, {**drafts.view(self.engine, root), **result})
        if path in (f'{DRAFTS}/slide-words', f'{DRAFTS}/slide-speaker-notes'):
            root = self.on_desk(desk.text(sent, 'path'))
            level = desk.text(sent, 'level', False) or None
            try:
                if path.endswith('slide-words'):
                    result = self.engine.slide_words(root, level, desk.text(sent, 'slide'),
                        desk.text(sent, 'field'), desk.text(sent, 'text', False), desk.text(sent, 'seen'))
                else:
                    result = self.engine.slide_speaker_notes(root, level, desk.text(sent, 'slide'),
                        desk.text(sent, 'text', False), desk.text(sent, 'seen'))
            except WorkspaceError as refusal:
                raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))
            return desk.as_json(HTTPStatus.OK, {**drafts.view(self.engine, root), **result})
        if path == f'{DRAFTS}/slide-words-decide':
            root = self.on_desk(desk.text(sent, 'path'))
            try:
                result = self.engine.slide_words_decide(root, desk.text(sent, 'proposal'),
                    desk.text(sent, 'decision'), desk.text(sent, 'seen', False),
                    question=desk.text(sent, 'question', False), revision=desk.text(sent, 'revision', False),
                    response=desk.text(sent, 'response', False))
            except WorkspaceError as refusal:
                raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))
            return desk.as_json(HTTPStatus.OK, {**drafts.view(self.engine, root), **result})
        if path == f'{DRAFTS}/slide-note':
            root = self.on_desk(desk.text(sent, 'path'))
            level = desk.text(sent, 'level', False)
            try:
                self.engine.slide_note(root, level or None, desk.text(sent, 'slide'),
                                       desk.text(sent, 'note'), desk.text(sent, 'seen'))
            except WorkspaceError as refusal:
                raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))
            return desk.as_json(HTTPStatus.OK, drafts.view(self.engine, root))
        if path in DECIDED:
            return desk.as_json(HTTPStatus.OK, self.drafted(path, sent))
        if path in JOBS:
            root = self.known(sent)
            action = path.rsplit('/', 1)[-1]
            if action in ('stop', 'retry'):
                method = self.engine.stop_draft if action == 'stop' else self.engine.retry_draft
                reply = method(root, desk.text(sent, 'job'))
            else:
                note = desk.text(sent, 'note', False) or desk.text(sent, 'instruction', False)
                kind = ('write-whole' if action == 'write-whole' else 'layout' if action == 'layout' else 'selection' if action == 'selection' else 'revise-all' if action == 'revise'
                        else 'section' if note else 'write-again')
                reply = self.engine.draft_begin(root, kind, desk.text(sent, 'name'),
                    part=desk.text(sent, 'part', False), seen=sent.get('seen'), note=note,
                    action=desk.text(sent, 'action', False),
                    passage=desk.text(sent, 'passage', False) or desk.text(sent, 'text', False),
                    start=sent.get('start'))
            return desk.as_json(HTTPStatus.OK, reply)
        if path in TYPED:
            return desk.as_json(HTTPStatus.OK, self.part(path, sent))
        if path == '/api/review':
            self.not_on_desk(desk.text(sent, 'path'))
            self.run(desk.text(sent, 'path'))
            looks = sent.get('looks')
            if looks is not None and not isinstance(looks, dict):
                raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give the looks picked as an object.')
            return desk.as_json(HTTPStatus.OK, self.engine.review_decide(
                desk.text(sent, 'path'), desk.text(sent, 'expected'),
                desk.text(sent, 'decision'), desk.text(sent, 'target', False),
                desk.text(sent, 'note', False), self.requests(sent), looks))
        if path == '/api/outline':
            return desk.as_json(HTTPStatus.OK, self.outline(sent))
        if path == '/api/look':
            return desk.as_json(HTTPStatus.OK, self.look(sent))
        if path == '/api/redesign':
            return desk.as_json(HTTPStatus.OK, self.redesign(sent))
        return super().write(path, sent)

    def update(self) -> dict:
        """Bring the companion skills that are missing or older, unless a training here is
        working: a step in hand keeps using the skill it started with."""
        return self.keeper().update(self.working())

    def keeper(self):
        """What looks after the skills here, or a refusal where nothing does."""
        keep = getattr(self.engine, 'upkeep', None)
        if keep is None:
            raise desk.Refusal(HTTPStatus.CONFLICT, 'This runner does not look after the '
                               'skills on this computer. Run the installer to update them.')
        return keep

    def working(self) -> bool:
        """Whether any training on this computer is working now."""
        return any((self.engine.brief(root) or {}).get('state') == 'working'
                   for root in self.engine.trainings())

    def known(self, sent: dict) -> str:
        """The training a change names, once this computer knows it and a run drives it."""
        path = desk.text(sent, 'path')
        self.run(path)
        return path

    def drive(self, sent: dict) -> dict:
        """Take a training, which takes over one someone else drives, or hand it over."""
        action = desk.text(sent, 'action')
        if action not in engines.DRIVING:
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'A training can be asked to: '
                               + ', '.join(engines.DRIVING) + '.')
        return self.engine.drive(self.known(sent), action)

    def adopt(self, sent: dict) -> dict:
        """Bring a training this computer knows, started in a conversation, into the
        workspace. The copy is the one to work on; the folder it came from is left as it
        was."""
        path = desk.text(sent, 'path')
        desk.registered(path)
        return self.engine.bring(path)

    def outline(self, sent: dict) -> dict:
        """Record what the person decided about what a deck says: approve it, or say
        what should change. It is theirs alone to decide, and decided here."""
        self.not_on_desk(desk.text(sent, 'path'))
        path, decision = desk.text(sent, 'path'), desk.text(sent, 'decision')
        level, note = desk.text(sent, 'level', False), desk.text(sent, 'note', False)
        if decision not in engines.DECIDING:
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'What a deck says can be decided '
                               'as: ' + ', '.join(engines.DECIDING) + '.')
        if decision == 'revise' and not (note or '').strip():
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Say what should change.')
        self.run(path)
        return self.engine.outline(path, level or None, decision, note,
                                   desk.text(sent, 'seen', False),
                                   desk.text(sent, 'design', False))

    def look(self, sent: dict) -> dict:
        """Record the look the person chose for a deck from the brand's samples, with their
        words. It is theirs alone to choose, and chosen here."""
        self.not_on_desk(desk.text(sent, 'path'))
        path, choice = desk.text(sent, 'path'), desk.text(sent, 'choice')
        level, words = desk.text(sent, 'level', False), desk.text(sent, 'words', False)
        self.run(path)
        try:
            return self.engine.look(path, level or None, choice, words)
        except WorkspaceError as refusal:
            raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))

    def deck_draft(self, sent: dict) -> dict:
        """Draw a deck's wireframe draft, and give the page the address its frame opens it
        at: with a ticket for that one page, since a frame cannot send the key. It is read
        with the key, as a picture is: drawing it changes nothing of the training."""
        path, level = sent['path'], sent.get('level')
        desk.registered(path)
        root = self.engine.driven(path)
        if root is None:
            raise desk.Refusal(HTTPStatus.NOT_FOUND, 'No run is driving this training.')
        page = shaped(self.engine.deck_draft, path, level or None)
        ticket = self.ticket('/api/deck-draft', (str(root), str(page)))
        return {'src': '/api/deck-draft?' + urlencode({'ticket': ticket})}

    def read_framed(self, path: str, scope) -> tuple:
        """A deck's wireframe draft, for its frame: only a page the runner drew in that
        deck's own work folder, sandboxed by its own policy."""
        root, page = scope
        try:
            return desk.framed_html(self.engine.draft_page(root, page))
        except OSError:
            raise desk.Refusal(HTTPStatus.NOT_FOUND, 'That draft is not here any more. Show '
                                                     'it again from the page.')

    def redesign(self, sent: dict) -> dict:
        """Draw a deck that was drawn without a design again from one, as the person asked,
        after they said yes in the page's confirmation. It is theirs alone to ask for."""
        path, level = desk.text(sent, 'path'), desk.text(sent, 'level', False)
        self.run(path)
        try:
            return self.engine.redesign(path, level or None)
        except WorkspaceError as refusal:
            raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))

    def asset(self, sent: dict) -> dict:
        """A picture the person supplies for their deck: it is theirs alone to give."""
        path, asset = desk.text(sent, 'path'), desk.text(sent, 'asset')
        alt, source = desk.text(sent, 'alt'), desk.text(sent, 'source')
        level = desk.text(sent, 'level', False)
        restrictions = desk.text(sent, 'restrictions', False)
        content = sent.get('content')
        if not isinstance(content, str) or not content:
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give the picture as text.')
        if not alt.strip() or not source.strip():
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Say what the picture shows and where '
                               'it came from.')
        try:
            data = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError):
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'That picture did not arrive whole. '
                               'Add it again.')
        self.run(path)
        try:
            return self.engine.supply_asset(path, level or None, asset, data, alt, source,
                                            restrictions or None)
        except WorkspaceError as refusal:
            raise desk.Refusal(HTTPStatus.CONFLICT, str(refusal))

    @staticmethod
    def requests(sent: dict) -> list | None:
        """The change requests a combined review sends together, each a target and a
        note, or None when it sends one the old way or none at all."""
        asked = sent.get('requests')
        if asked is None:
            return None
        if not isinstance(asked, list) or not all(
                isinstance(ask, dict) and isinstance(ask.get('target'), str)
                and isinstance(ask.get('note'), str) for ask in asked):
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give requests as a list, each with a '
                               'target and a note.')
        return [{'target': ask['target'], 'note': ask['note']} for ask in asked]

    def act(self, sent: dict) -> dict:
        path, action = desk.text(sent, 'path'), desk.text(sent, 'action')
        if action not in engines.ACTIONS:
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'A run can be asked to: '
                               + ', '.join(engines.ACTIONS) + '.')
        self.run(path)
        return self.engine.act(path, action)

    def answered(self, sent: dict) -> dict:
        path, ident = desk.text(sent, 'path'), desk.text(sent, 'id')
        answer = desk.text(sent, 'answer')
        if not answer.strip():
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Write an answer first.')
        self.run(path)
        return self.engine.answer(path, ident, answer)

    def supplied(self, sent: dict) -> dict:
        """Add one of the person's documents, remove one, or hear that they are all added."""
        path, action = desk.text(sent, 'path'), desk.text(sent, 'action')
        if action not in engines.SUPPLYING:
            raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'A document can be: '
                               + ', '.join(engines.SUPPLYING) + '.')
        name, data = desk.text(sent, 'name', action not in ('done', 'update')), None
        if action == 'add':
            content = sent.get('content')
            if not isinstance(content, str) or not content:
                raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Give content as text.')
            try:
                data = base64.b64decode(content, validate=True)
            except (binascii.Error, ValueError):
                raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'That document did not arrive '
                                   'whole. Add it again.')
        self.run(path)
        return self.engine.supply(path, action, name, data)

    def copied(self, sent: dict) -> dict:
        path = desk.text(sent, 'path')
        self.run(path)
        if 'pull' in sent:
            artifact = desk.text(sent, 'pull')
            desk.artifact_of(path, artifact)
            choose = sent.get('choose')
            if choose not in (None, 'ours', 'theirs'):
                raise desk.Refusal(HTTPStatus.BAD_REQUEST, 'Choose the Doc’s version or this version.')
            return self.engine.pull_copy(path, artifact, choose)
        action = sent.get('action')
        if action == 'check':
            return self.engine.check_copies(path)
        if action == 'remake':
            artifact = desk.text(sent, 'artifact')
            desk.artifact_of(path, artifact)
            return self.engine.remake_copy(path, artifact)
        if action is not None:
            raise desk.Refusal(HTTPStatus.BAD_REQUEST,
                               'Ask to check the copies, make a Doc again, or make them '
                               'again.')
        return self.engine.copies_again(path)


modules.bind(globals(), _shared, methods={'RunnerPage': _shared.METHODS['RunnerPage']})


class Studio(desk.Desk):
    """The runner's server: the desk's, with a page that also answers for the runner."""


modules.bind(globals(), _shared, methods={'Studio': _shared.METHODS['Studio']})
