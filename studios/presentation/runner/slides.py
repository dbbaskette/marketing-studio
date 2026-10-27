"""The harness-slides command line, called from Python.

What a caller needs to know
---------------------------
    slides = Slides()                              # finds the installed tool, or refuses
    slides.version()
    slides.outline_contract(brand)                 # text a worker is told
    report = slides.outline_check(outline, brand)  # {'status', 'slides', 'delivery',
                                                   #  'wordBudget', 'words', 'findings'}
    slides.outline_start(outline, brand, folder)   # the tool splits the deck into sections
    slides.compose_contract(brand)                 # text a worker is told
    slides.layouts(brand)                          # {'default', 'layouts': [{'name', 'title',
                                                   #                           'subtitles', 'pictures'}]}
    report = slides.compile(composition, brand, folder=None, design=None, section=False)
                                                   # checks; with a folder, writes
    slides.merge(parts, composition)
    shown = slides.preview(compiled, folder, renderer, file_id=None, slide=None, design=None,
                           section=False)
    slides.critique(preview_folder, assessment)
    made = slides.render(compiled, deck)
    slides.cited(compiled)                         # {source: [slide numbers]}, from the scene
    slides.reading()                               # {name: text}: the tool's own guidance
    slides.drive_check()                           # whether Google access reaches Drive
    slides.drive_import(deck, name)                # {'id', 'name', 'url'}
    slides.drive_export(file_id, deck)             # a Google Slides file, as a new .pptx
    slides.outline_draft(outline, brand, output)   # an HTML page of the outline's wording
    slides.pptx_inspect(deck)                      # {'sha256', 'size', 'slides': [...]}
    slides.pptx_patch(deck, plan, output)          # a new deck with scoped text changes
    slides.pptx_compare(deck, after, allow)        # {'preserved', 'failures', ...}
    shown = slides.pictures_of(deck, folder, renderer, file_id=None)
    slides.designs()                               # whether it keeps a design session
    slides.sections()                              # whether it checks a section against it
    slides.design_propose(project, proposal, expected=None)   # with its question
    slides.design_status(project)
    slides.design_check(project)                   # {'plan', 'revision', 'buildAllowed'}
    slides.design_respond(project, reply)          # a person's answer to the question
    slides.capabilities()                          # what it says it has, or None
    slides.has(name), slides.knows()               # one capability; outline fields it keeps
    slides.assets()                                # whether it keeps an asset manifest
    slides.asset_status(project)                   # {'manifest', 'assets': [{..., 'state'}]}
    slides.asset_check(project, brand=None)        # {'status': 'ready', ...}, or Refused
    slides.asset_icon(project, icon, ident, alt=None, brand=None)
    slides.asset_supplied(project, file, ident, alt, source, kind='supplied',
                          restrictions=None)       # a person's picture, recorded
    slides.images_status()                         # whether an image provider is set up
    slides.generate_image(project, ident, prompt, output, slide, alt=None)
    slides.reviews()                               # whether it reviews a build against the design
    made = slides.review_prepare(compiled, output, design)   # renders output/deck.pptx
    slides.review_slide(output, slide)             # one slide's packet: criteria, prompts
    slides.review_mark(output, revision, numbers, note)       # its pictures were looked at
    slides.review_assess(output, revision, assessment)        # with what is unresolved

- `brand` is the path of an exported brand-contract.json. `outline`, `composition`, `parts`
  and `assessment` are paths of JSON files; `folder`, `compiled`, `preview_folder` and
  `deck` are paths. The tool refuses to write over anything, so every output path is new.
- Every call returns the tool's own JSON, or its text for a contract.
- When the tool says no, Refused is raised: a WorkspaceError that carries the lines it
  printed, one problem each, in `problems`. A compile that finds text that does not fit, or
  a check that fails, is a refusal with those lines; give them to the worker as they are.
- `preview` returns {'deck', 'deckSha256', 'contactSheet', 'renderer', 'fileId', 'url',
  'slides': [{'id', 'number', 'title', 'image', 'findings': [{'severity', 'code',
  'detail'}]}]}, where `image` is a PNG's path. `renderer` is 'drive' or 'local'. With
  'drive', pass the `file_id` an earlier preview returned so that one file is written again
  and no second one is made; a first preview makes the file.
- Previews through Drive must be taken one at a time: two at once cross their pictures.
  `preview` holds a lock of its own for that, so callers may call it from several threads.
- `critique` records one assessment for one preview and returns {'critical', 'major',
  'minor', 'status'}. The tool says 'clear' unless a finding is critical; the counts are
  what a caller should go by.
- `render` and `preview` never leave a deck behind that cannot be opened: when the tool
  fails after writing one, the file is removed before Refused is raised.
- `ready()` says, without starting anything that writes, what this computer has: the tool
  and its version, the programs it uses to turn a render into pictures, LibreOffice, and
  whether Google access reaches Drive. Each missing thing is a sentence for a person.
- The runtime is the folder named by HARNESS_SLIDES_RUNTIME when that is set, else the
  first usual install location that holds one. `Slides(run=...)` replaces how the command
  is run. The tests' stand-in, in tests/stand_ins/slides.py, behaves like the real command
  for every call above and needs neither Node nor an installed skill.

Added to the above
------------------
- `Slides()` asks the tool for its version and refuses one older than MINIMUM with
  TooOld, a WorkspaceError that keeps the `version` it found.
- Paths in what a call returns are text, as the tool printed them. Where the tool leaves
  something out, `preview` gives None: `contactSheet` for one slide, `fileId` and `url` for
  a local render. What else the tool said is still there, `critic` among them.
- `cited` leaves out the tool's own mark on a cover, section or closing slide ('outline').
- `drive_check` is True or False. It is False too when Drive would not turn a PowerPoint
  file into slides, since previews and the finished deck both need that.
- A refusal by `preview` that had already written its file in Drive says so in `left`:
  {'fileId', 'url'}. A tool with a Google preview pool (`google-preview-pool`) reuses its
  own few preview decks, and is never named a file; an older one is passed that `fileId`
  for the next preview, and one it says a newer preview replaced is previewed again.
- `ready()` returns {'tool', 'version', 'pictures', 'local', 'drive', 'missing'}: four
  yes-or-no answers, the version, and the sentences. `ready(slides, which=...)` asks a given
  Slides, and looks for programs some other way, which is how a test asks. With
  `drive=False` Drive is not asked at all, and `drive` is None.
- Every call that writes removes what it wrote when it fails, so the same path can be
  tried again. Nothing that was there before the call is ever removed.
- `reading()` returns the guidance the tool's own workers are sent to read, as
  {name: text}: 'design guidance', 'composition guidance', 'drafting guidance', 'gallery'
  (what its examples are for), and 'example order', 'example contrast' and so on, one drawn
  slide for each relation the tool has an example of. They are files of the installed
  tool, read and never run, each from inside its folder and cut off at READ_MOST
  characters. One the installed version does not have is left out. A caller chooses which
  a worker needs; `example(relation)` is the name of one relation's example.
- The design session is the tool's record of what a person approved of how each slide is
  drawn, kept in `project`, a folder of the deck's own. `designs()` asks the tool whether it
  has the session as a deck's outline gate needs it: a proposal of schema 2, one question
  for the whole plan (`--mode batch`), and refusals as JSON. 0.13.1 has none of the three.
  Every design call asks for JSON, so a refusal of one carries `found`, each problem as
  {'code', 'slide', 'asset', 'provider', 'detail', 'recoverable', 'next', 'fallback'?},
  with `codes` and the design `revision` it named. Its lines are the details.
- `design_respond` sends a person's answer, and nothing else may: no worker is given it.
  The reply names the question and revision that were put to the person, so an answer to
  anything older is refused as `design-revision-stale`.
- `sections()` asks the tool whether it checks a build against the approved design one
  section at a time (`--section`), with refusals as JSON. 0.13.1 does not know `--section`.
  The tool is asked, as for `designs()`: `--section` without a design project is refused as
  JSON `input-invalid` before any file is read, so nothing is read or written.
- `compile` and `preview` with `design`, the design project, check the slides against the
  design approved there now: every approved slide in order, or with `section` a run of
  neighbouring ones, each with its approved title and, where a slide gives one, its
  approved `intent`. They then ask for refusals as JSON, so a `design-mismatch` names its
  slide in `found`. Without `design` the command is as 0.13.1 takes it.
- `capabilities()` is the set of names `version` lists, which a tool after 0.13.1 gives,
  or None for one that lists none. `designs()`, `sections()` and `assets()` read it first
  and ask the tool by a refusal only when it lists nothing.
- The asset manifest is the tool's record of each picture and icon a deck may use, kept in
  `project`, the deck's design project. `assets()` says whether the tool keeps one: its
  capability `assets`, or for a tool that lists none, whether `assets status` of an empty
  folder that is thrown away answers as JSON. Every asset call asks for JSON, so a refusal
  carries `found` and `codes`, each problem with its `asset`, `provider` and `next`. The tool
  keeps the files, their hashes, alt text, sources and provenance; nothing here keeps a
  credential. `asset_supplied` is the person's alone: no worker is given it.
- `generate_image` asks the tool's own image provider, set up as the tool says, for the
  approved artwork of one slide drawn as generated art. The tool refuses any other slide.
- The design-bound review of a composition is `review --compiled` with `--design-project`:
  the tool renders the whole build itself into `output/deck.pptx`, which is the reviewed
  deck to deliver, and pictures each slide. `reviews()` is its capability `compose-review`;
  a tool that lists no capabilities has none, so nothing is asked by a refusal. Every review
  call asks for JSON. `review_prepare` returns the tool's summary: {'output', 'revision',
  'slides', 'pending', 'creativeReviewComplete', 'readyForUserReview', 'designReview',
  'qualityRevision', 'assessmentBinding', ...}; the record it wrote is `output/review.json`.
  `review_slide` returns {'revision', 'assessmentBinding', 'slide': the prompt, with its
  'criteria', 'objects', 'expectedText', 'sources' and any 'proseCards', 'findings'}, and
  checks the review's receipts first. `review_mark` records that the pictures were looked
  at, and `review_assess` records an assessment, a file of the shape the tool takes, and
  adds `unresolved`. A changed deck, picture, build or design revision is refused as
  `review-stale`, a changed asset copy as `asset-hash-changed`, and a computer without
  LibreOffice or Poppler as `renderer-unavailable`.
- An existing deck is read and changed through the tool's `pptx` commands. `pptx_inspect`
  returns {'sha256', 'size', 'slides': [{'number', 'id', 'title', 'hidden', 'objects':
  [{'id', 'type', 'text', 'runs', 'alt', 'title', 'box', 'contentHash', 'structureHash'}]}]}.
  `pptx_patch` takes a plan {'sourceSha256', 'operations': [{'slide', 'object',
  'expectedHash', 'text' | 'runs' | 'alt' | 'title'}]} and writes a new deck, which the
  tool compares with the original before it keeps it; an output that is there already is
  refused. `pptx_compare` says whether only what `allow` lists changed: {'preserved',
  'failures', 'changedParts'}.
- `pictures_of` draws every slide of a deck through `review --file`, in a new folder, with
  the renderer 'local' (LibreOffice) or 'google' (through Drive, reusing `file_id`). It
  returns {'slides': [{'number', 'image'}], 'contactSheet', 'fileId', 'url'}, `image` being
  a PNG's path, and is taken under the same lock as `preview`.
- `drive_export` writes a Google Slides file as a new .pptx and returns its path.
  `outline_draft` writes the tool's own page of an outline's wording and returns its path.
- `slides.runtime` is the folder the tool is installed in, with links followed. Give it to
  `Slides(runtime=...)` to use that same tool somewhere else, as the worker tools' server
  does. `Slides(read=...)` replaces how a guidance file is read.
"""
from __future__ import annotations

# ruff: noqa: F821  names bound from studio_core.shared_runner are unseen by a linter;
# test_shared_runner_use checks the bound parts, and the suites call the rest.

import contextlib
import json
import os  # noqa: F401  read by the shared parts
import re
import shutil
import tempfile  # noqa: F401  read by the shared parts
import threading  # noqa: F401  read by the shared parts
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
from workspace import WorkspaceError

from runner import companion  # noqa: F401  read by the shared parts

from studio_core import modules
from studio_core.shared_runner import slides as _shared
modules.bind(globals(), _shared, _shared.NAMES)

DRAWERS = ('local', 'google')   # how `review --file` draws a deck's pictures
LEFT = re.compile(r'The preview deck is in Drive \((\S+)\); retry with --file-id (\S+?)\.$')


class TooOld(WorkspaceError):
    """The slides tool here is older than MINIMUM. `version` is the version it said."""


modules.bind(globals(), _shared, methods={'TooOld': _shared.METHODS['TooOld']})


class Refused(WorkspaceError):
    """The slides tool said no. `problems` holds the lines it gave, one problem each. When it
    was asked for its refusal as JSON, `found` holds each problem as the tool gave it and
    `revision` the design revision it named; otherwise `found` is empty."""


modules.bind(globals(), _shared, methods={'Refused': _shared.METHODS['Refused']})


def _problems(err: str, code: int) -> list[str]:
    """The tool's own lines: one problem alone, or each one listed under a count."""
    lines = [line.strip() for line in err.splitlines() if line.strip()]
    def event(line):
        try:
            found = json.loads(line)
        except ValueError:
            return False
        return isinstance(found, dict) and found.get('schema') == 1 \
            and found.get('type') in ('slide-ready', 'preview-ready', 'compiled',
                                      'storyboard-ready', 'failed') \
            and isinstance(found.get('runId'), str) and type(found.get('sequence')) is int
    lines = [line for line in lines if not event(line)]
    lines = [line for line in lines if not NOISE.match(line)]
    for index, line in enumerate(lines):
        if COUNTED.match(line):
            lines = lines[index + 1:]
            break
    return lines or [f'it ended with exit code {code}']


@contextlib.contextmanager
def _new(path):
    """A file or folder a call is about to make. When the call fails, what it wrote is
    removed; what was already there is never touched."""
    path = Path(path)
    there = path.exists() or path.is_symlink()
    try:
        yield
    except BaseException:
        if not there and path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        elif not there:
            path.unlink(missing_ok=True)
        raise


class Slides:
    """The outline, compose and drive commands of one installed harness-slides. `runtime`
    is the folder it is installed in."""

    @contextlib.contextmanager
    def turn(self, renderer: str):
        """This process's turn at a renderer: LibreOffice renders one at a time under one
        profile, and so does Google Drive for a tool without a preview pool; one with
        `google-preview-pool` renders up to `pool_size()` at once, each in a deck of its
        pool."""
        held = _pooled(pool_size()) if renderer == 'drive' \
            and self.has('google-preview-pool') else PREVIEWING
        with held:
            yield

    # --- the outline ---


    # --- the composition ---

    def compile(self, composition: Path, brand: Path, folder: Path | None = None,
                design: Path | None = None, section: bool = False,
                outline: Path | None = None, assets: Path | None = None) -> dict:
        """Check a composition, a whole deck or one section. With a new folder, write what
        a preview and a render are made from. With `design`, it is checked against the
        design approved in that project: as the whole deck, or as one `section`. With the
        approved `outline`, on a tool that can (compose-split-point), its preview finds a
        point's sentence split across shapes. With `assets`, the deck's asset project, an
        image named by its asset ID is resolved from that project's manifest."""
        args = ['compose', 'compile', '--file', str(composition), '--brand', str(brand),
                *_bound(design, section),
                *(['--asset-project', str(assets)] if assets else []),
                *(['--outline', str(outline)] if outline and self.has('compose-split-point')
                  else [])]
        if folder is None:
            return self._json(*args)
        with _new(folder):
            return self._json(*args, '--output', str(folder))

    def cited(self, compiled: Path) -> dict:
        """Which slides cite each source, by number, read from the compiled scene."""
        try:
            scene = json.loads((Path(compiled) / 'scene.json').read_text(encoding='utf-8'))
            found: dict = {}
            for number, slide in enumerate(scene['slides'], 1):
                for source in slide.get('sources') or []:
                    if source != LEAD and number not in found.setdefault(source, []):
                        found[source].append(number)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise WorkspaceError(f'{compiled} does not hold a compiled deck, so what its '
                                 'slides cite cannot be read. Compile the deck again.')
        return found

    # --- the design session ---

    def knows(self) -> frozenset:
        """What this tool knows of an outline beyond its words, by the names build.KNOWS
        gives: a point's `parts`, a slide's `provenance`."""
        from runner.steps import build
        return frozenset(name for capability, name in build.KNOWS.items()
                         if self.has(capability))

    def design_propose(self, project: Path, proposal: Path,
                       expected: str | None = None) -> dict:
        """Propose a design in `project`, a folder that exists, as one question for the
        whole plan. A changed proposal names the revision it replaces in `expected`. Slides
        whose approved design is unchanged keep their approval."""
        args = ['design', 'propose', '--project', str(project), '--file', str(proposal),
                '--mode', 'batch', '--json']
        return self._json(*args, *(['--expected', expected] if expected else []))

    # --- the asset manifest ---

    def asset_status(self, project: Path) -> dict:
        """Each asset recorded in `project`, as {'manifest', 'assets'}: each with its
        `assetId`, `kind`, `path` (none for an icon), `sha256`, `alt`, `source`,
        `restrictions`, `ref` (an icon's library ID), `provenance` and `state`: 'ok',
        'file-missing', 'hash-changed' or 'invalid'."""
        return self._json('assets', 'status', '--project', str(project), '--json')

    def asset_check(self, project: Path, brand: Path | None = None) -> dict:
        """Refuse a recorded file that is missing or changed, and with `brand` an icon the
        brand's library no longer has as it was recorded."""
        return self._json('assets', 'check', '--project', str(project),
                          *(['--brand', str(brand)] if brand else []), '--json')

    def asset_supplied(self, project: Path, file: Path, ident: str, alt: str, source: str,
                       kind: str = 'supplied', restrictions: str | None = None) -> dict:
        """Record a picture the person gave as the asset `ident`. A file from outside the
        project is copied into it; one inside is recorded as it is now. The person's words
        go joined to their option (`--alt=…`), so words that begin with "-" stay words."""
        return self._json('assets', 'add-supplied', str(file), '--project', str(project),
                          '--id', ident, f'--alt={alt}', f'--source={source}', '--kind', kind,
                          *([f'--restrictions={restrictions}'] if restrictions else []),
                          '--json')

    # --- the design-bound review of a composition ---


    def review_prepare(self, compiled: Path, output: Path, design: Path) -> dict:
        """Render a whole deck compiled against the design approved in `design` into
        `output/deck.pptx`, picture each slide, and prepare its creative review. An unchanged
        build keeps its deck and its receipts. It renders with LibreOffice, one at a time."""
        with self.turn('local'):
            return self._json('review', '--compiled', str(compiled), '--output', str(output),
                              '--design-project', str(design), '--json')

    # --- what the tool's own workers read ---


    # --- Google Drive ---

    def drive_export(self, file_id: str, deck: Path) -> Path:
        """Write a Google Slides file as a new PowerPoint file at `deck`."""
        with _new(deck):
            self._json('drive', 'export', '--file-id', file_id, '--output', str(deck))
        return Path(deck)

    # --- an existing deck ---

    def pptx_inspect(self, deck: Path) -> dict:
        """Every slide of a deck and every object on it, with the hashes a patch names."""
        found = self._json('pptx', 'inspect', '--file', str(deck), '--json')
        if not isinstance(found.get('slides'), list):
            raise WorkspaceError('The slides tool read the deck and did not say what is on '
                                 'its slides. Check that it is installed whole.')
        return found

    def pptx_patch(self, deck: Path, plan: Path, output: Path) -> dict:
        """Write a new deck with the plan's changes made, and nothing else changed."""
        with _new(output):
            return self._json('pptx', 'patch', '--file', str(deck), '--plan', str(plan),
                              '--output', str(output))

    def pptx_compare(self, deck: Path, after: Path, allow: Path) -> dict:
        """Whether `after` differs from `deck` only where `allow` says it may. A change it
        does not allow is an answer, not a refusal: `preserved` is false, with `failures`."""
        code, out, err = self.run([self.node, str(self.runtime / SCRIPT), 'pptx', 'compare',
                                   '--file', str(deck), '--after', str(after),
                                   '--allow', str(allow)])
        try:
            found = json.loads(out)
        except ValueError:
            found = None
        if isinstance(found, dict) and isinstance(found.get('preserved'), bool):
            return found
        if code != 0:
            raise Refused(_problems(err, code))
        raise WorkspaceError('The slides tool answered with something other than the '
                             'JSON it should. Check that it is installed whole.')

    def pictures_of(self, deck: Path, folder: Path, renderer: str,
                    file_id: str | None = None) -> dict:
        """A picture of every slide of a deck, drawn into a new folder."""
        if renderer not in DRAWERS:
            raise WorkspaceError(f'A deck is drawn through {DRAWERS[0]} or {DRAWERS[1]}, '
                                 f'not {renderer}.')
        args = ['review', '--file', str(deck), '--output', str(folder), '--renderer', renderer]
        args += ['--file-id', file_id] if file_id and renderer == 'google' else []
        with self.turn('drive' if renderer == 'google' else 'local'), _new(folder):
            made = self._json(*args)
            try:
                record = json.loads((Path(folder) / 'review.json').read_text(encoding='utf-8'))
                slides = [{'number': slide['number'], 'image': str(Path(folder) / slide['image'])}
                          for slide in record['slides']]
            except (OSError, ValueError, KeyError, TypeError):
                raise WorkspaceError('The slides tool drew the deck and did not say where its '
                                     'pictures are. Check that it is installed whole.') from None
        return {'slides': slides, 'contactSheet': made.get('contactSheet'),
                'fileId': made.get('fileId'), 'url': made.get('url'),
                # Under the slides tool's preview pool: the receipt of the preview its deck
                # holds, and whether a newer preview has replaced it since.
                **{key: made[key] for key in ('pool', 'remoteReplaced') if key in made}}

    def outline_draft(self, outline: Path, brand: Path, output: Path) -> Path:
        """Write the tool's page of an outline's wording and structure, which is no design."""
        with _new(output):
            self._json('outline', 'draft', '--file', str(outline), '--brand', str(brand),
                       '--output', str(output))
        return Path(output)


modules.bind(globals(), _shared, methods={'Slides': _shared.METHODS['Slides']})


