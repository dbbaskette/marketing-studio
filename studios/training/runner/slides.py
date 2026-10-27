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
    slides.cited(compiled)                         # {objective: [slide numbers]}, from the scene
    slides.reading()                               # {name: text}: the tool's own guidance
    slides.drive_check()                           # whether Google access reaches Drive
    slides.drive_import(deck, name)                # {'id', 'name', 'url'}
    slides.designs()                               # whether it keeps a design session
    slides.sections()                              # whether it checks a section against it
    slides.design_propose(project, proposal, expected=None, brand=None)   # with its question
    slides.design_status(project)
    slides.design_check(project)                   # {'plan', 'revision', 'buildAllowed'}
    slides.design_respond(project, reply)          # a person's answer to the question
    slides.capabilities()                          # what it says it has, or None
    slides.has('review-packets')                   # whether it says it has that one
    slides.lacks()                                 # what a new deck needs and it lacks
    slides.assets()                                # whether it keeps an asset manifest
    slides.asset_status(project, design=None)      # {'manifest', 'assets': [{..., 'state'}]}
    slides.asset_check(project, brand=None, design=None)   # {'status': 'ready', ...}, or
                                                   # Refused
    slides.asset_icon(project, icon, ident, alt=None, brand=None)
    slides.asset_supplied(project, file, ident, alt, source, kind='supplied',
                          restrictions=None)       # a person's picture, recorded
    slides.images_status()                         # whether an image provider is set up
    slides.generate_image(project, ident, prompt, output, slide, alt=None)
    slides.reviews()                               # whether it reviews a build against the design
    made = slides.review_prepare(compiled, output, design, renderer=None, file_id=None)
                                                   # renders output/deck.pptx
    slides.review_slide(output, slide)             # one slide's packet: criteria, prompts
    slides.review_packets(output)                  # every slide's packet, in one call
    slides.review_mark(output, revision, numbers, note)       # its pictures were looked at
    slides.review_assess(output, revision, assessment)        # with what is unresolved
    slides.design_present(project, output, revision)          # the deck put to the person

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
  TooOld, a WorkspaceError that keeps the `version` it found. What a new deck needs is said
  by capability and never by version: `lacks()` names each of NEEDED the tool lacks, in
  order, and NAMES says each as a person reads it. RELEASE is the release a person is told
  to update to, the one `pins/companions.json` pins.
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
  and ask the tool by a refusal only when it lists nothing; so does `lacks()`. `has(name)`
  is whether the list names it: a tool that lists nothing has none of them. A caller uses
  what a capability gives only where `has` says so, and does as before where it does not.
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
- Where the tool has them: `review_prepare` with `renderer` 'drive' renders through Google
  Drive (`review-google-renderer`), writing again the file `file_id` names, and returns
  its `fileId` and `url`; a refusal after the upload names that file in `left`.
  `review_packets` gives every slide's packet in one call (`review-packets`): {'revision',
  'assessmentBinding', 'designReview', 'slides': [{'number', 'id', 'planId', 'title',
  'image', 'imageSha256', 'mark', 'packet', 'findings'}]}, `packet` being what
  `review_slide` gives as `slide`. `design_present` puts a reviewed deck to the person in
  the design session, its unresolved findings listed (`design-present-findings`); only
  `design_respond` with the person's own answer approves it.
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

RELEASE = '0.16.0'      # what a person is told to update to, as the installer pins it
# What a new deck needs of the slides tool, by the names its `version` lists: NEEDED for a
# deck approved on its words and its look, as the brand's checkpoints are, and DESIGN_NEEDED
# besides for one whose slides' designs are walked through first, when the person asks.
NEEDED = ('json-refusals',)
DESIGN_NEEDED = ('design-schema-2', 'design-batch', 'compose-section', 'assets',
                 'compose-review')
ORDER = ('design-schema-2', 'design-batch', 'json-refusals', 'compose-section', 'assets',
         'compose-review')   # how what is lacking is said
# Each capability, as a person reads it.
NAMES = {'assets': 'an asset manifest for the pictures and icons a deck uses',
         'assets-approved-candidates': 'checking every asset an approved design names',
         'canonical-digests': 'designs compared whatever order their keys are in',
         'compose-code-spans': 'names and commands set as code',
         'compose-icon-assets': 'icons placed by the asset they are recorded as',
         'compose-projects': 'a deck kept as a project',
         'compose-provenance': "where each slide's words came from",
         'compose-review': 'a whole deck reviewed against its approved design',
         'compose-section': 'a section checked against the approved design',
         'compose-split-point': 'a sentence split across shapes found in a preview',
         'compose-verified-critique': 'a review checked against the deck it reviewed',
         'compose-visual-vocabulary': 'the drawing words a composition may use',
         'design-batch': 'one question for a whole design',
         'design-icon-ids': 'an exact icon named in a design',
         'design-present-findings': 'a reviewed deck put to you with its findings',
         'design-schema-2': 'a design proposed with its words and its assets',
         'google-preview-pool': 'a few reusable preview decks in Google Drive',
         'json-refusals': 'refusals a program can read',
         'native-charts': 'charts drawn as charts',
         'neutral-native-composition': 'slides drawn as editable shapes',
         'owned-google-previews': 'preview decks kept as your own',
         'preview-repair-clusters': 'preview problems grouped for repair',
         'relative-records': 'records that move with the deck',
         'render-bundles': 'a render kept with what it was made from',
         'review-google-renderer': 'a review rendered through Google Drive',
         'review-input-refusals': 'a review asked wrongly refused plainly',
         'review-packets': "every slide's review given in one call",
         'review-sources-from-slide': 'an assessment that takes its sources from the slide'}
LEFT = re.compile(r'The (?:preview|review) deck is in Drive \((\S+)\); retry with '
                  r'(?:--renderer google )?--file-id (\S+?)\.$')


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

    def outline_draft(self, outline: Path, brand: Path, output: Path) -> Path:
        """Write the tool's page of an outline's wording and structure: a wireframe draft,
        which is no design."""
        with _new(output):
            self._json('outline', 'draft', '--file', str(outline), '--brand', str(brand),
                       '--output', str(output))
        return Path(output)

    def compile(self, composition: Path, brand: Path, folder: Path | None = None,
                design: Path | None = None, section: bool = False,
                outline: Path | None = None) -> dict:
        """Check a composition, a whole deck or one section. With a new folder, write what
        a preview and a render are made from. With `design`, it is checked against the
        design approved in that project: as the whole deck, or as one `section`. With the
        approved `outline`, on a tool that can, its preview finds a point's sentence split
        across shapes."""
        args = ['compose', 'compile', '--file', str(composition), '--brand', str(brand),
                *_bound(design, section),
                *(['--outline', str(outline)] if outline and self.has('compose-split-point')
                  else [])]
        if folder is None:
            return self._json(*args)
        with _new(folder):
            return self._json(*args, '--output', str(folder))

    def cited(self, compiled: Path) -> dict:
        """Which slides cite each objective, by number, read from the compiled scene."""
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
        """What this tool knows of an outline beyond its words, by the names deck.KNOWS
        gives: a point's `parts`, a slide's `provenance`."""
        from runner import deck
        return frozenset(name for capability, name in deck.KNOWS.items()
                         if self.has(capability))

    def lacks(self, design: bool = False) -> list[str]:
        """Each capability a new deck needs that this tool lacks: those of NEEDED, and with
        `design`, for a deck whose slides' designs are walked through, those of DESIGN_NEEDED,
        in ORDER. Read from what `version` lists; for a tool that lists nothing, the design
        session, the section check and the asset manifest are asked as `designs`,
        `sections` and `assets` ask, and a review against the design is lacking, since no
        such tool has it."""
        wanted = (*NEEDED, *(DESIGN_NEEDED if design else ()))
        listed = self.capabilities()
        if listed is not None:
            return [name for name in ORDER if name in wanted and name not in listed]
        found = {'compose-review'}
        if not self.designs():
            found |= {'design-schema-2', 'design-batch', 'json-refusals'}
        if not self.sections():
            found.add('compose-section')
        if not self.assets():
            found.add('assets')
        return [name for name in ORDER if name in wanted and name in found]

    def design_propose(self, project: Path, proposal: Path, expected: str | None = None,
                       brand: Path | None = None) -> dict:
        """Propose a design in `project`, a folder that exists, as one question for the
        whole plan. A changed proposal names the revision it replaces in `expected`. Slides
        whose approved design is unchanged keep their approval. With `brand`, each icon the
        proposal names by its library ID is checked against the brand's library, which a
        tool with `design-icon-ids` does."""
        args = ['design', 'propose', '--project', str(project), '--file', str(proposal),
                '--mode', 'batch', '--json']
        return self._json(*args, *(['--expected', expected] if expected else []),
                          *(['--brand', str(brand)] if brand else []))

    # --- the asset manifest ---

    def asset_status(self, project: Path, design: Path | None = None) -> dict:
        """Each asset recorded in `project`, as {'manifest', 'assets'}: each with its
        `assetId`, `kind`, `path` (none for an icon), `sha256`, `alt`, `source`,
        `restrictions`, `ref` (an icon's library ID), `provenance` and `state`: 'ok',
        'file-missing', 'hash-changed' or 'invalid'. With `design`, the design project, it
        adds `candidates`: {'resolved', 'pending'}, each {'slide', 'assetId', 'kind',
        'concept', 'ref'?}."""
        return self._json('assets', 'status', '--project', str(project),
                          *(['--design-project', str(design)] if design else []), '--json')

    def asset_check(self, project: Path, brand: Path | None = None,
                    design: Path | None = None) -> dict:
        """Refuse a recorded file that is missing or changed, and with `brand` an icon the
        brand's library no longer has as it was recorded. With `design`, also each asset the
        design names that is not recorded: on a tool with `assets-approved-candidates`,
        every one of the stored plan, approved or not."""
        return self._json('assets', 'check', '--project', str(project),
                          *(['--design-project', str(design)] if design else []),
                          *(['--brand', str(brand)] if brand else []), '--json')

    def asset_supplied(self, project: Path, file: Path, ident: str, alt: str, source: str,
                       kind: str = 'supplied', restrictions: str | None = None) -> dict:
        """Record a picture the person gave as the asset `ident`. A file from outside the
        project is copied into it; one inside is recorded as it is now. The words go
        joined to their option (`--alt=…`), so words that begin with "-" stay words."""
        return self._json('assets', 'add-supplied', str(file), '--project', str(project),
                          '--id', ident, f'--alt={alt}', f'--source={source}', '--kind', kind,
                          *([f'--restrictions={restrictions}'] if restrictions else []),
                          '--json')

    # --- the design-bound review of a composition ---


    def review_prepare(self, compiled: Path, output: Path, design: Path,
                       renderer: str | None = None, file_id: str | None = None) -> dict:
        """Render a whole deck compiled against the design approved in `design` into
        `output/deck.pptx`, picture each slide, and prepare its creative review. An unchanged
        build keeps its deck and its receipts. Renders are taken one at a time. With
        `renderer` 'drive' it is rendered through Google Drive, writing again the file
        `file_id` names when one is given; otherwise with LibreOffice."""
        args = ['review', '--compiled', str(compiled), '--output', str(output),
                '--design-project', str(design)]
        if renderer == 'drive':
            args += ['--renderer', 'google', *(['--file-id', file_id] if file_id else [])]
        with PREVIEWING:   # a review renders into the deck's one remembered file
            made = self._json(*args, '--json')
        return {**made, 'fileId': made.get('fileId'), 'url': made.get('url')}

    def review_packets(self, output: Path) -> dict:
        """Every slide's part of a prepared review, in deck order, once its receipts are
        checked: one call in place of one for each slide."""
        found = self._json('review', '--output', str(output), '--packets', '--json')
        if not isinstance(found.get('slides'), list):
            raise WorkspaceError('The slides tool gave a review without its slides. Check '
                                 'that it is installed whole.')
        return found

    def design_present(self, project: Path, output: Path, revision: str) -> dict:
        """Put the deck a review in `output` rendered, of this review revision, to the person
        as the design session's rendered question, with what its assessment leaves unresolved
        listed. Returns the design's status, with that question."""
        return self._json('design', 'present', '--project', str(project), '--output',
                          str(output), '--revision', revision, '--accept-findings', '--json')


modules.bind(globals(), _shared, methods={'Slides': _shared.METHODS['Slides']})

    # --- what the tool's own workers read ---

    # --- Google Drive ---


