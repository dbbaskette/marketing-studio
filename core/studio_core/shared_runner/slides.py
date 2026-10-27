"""The parts of the runner's `slides` both deck studios share. A studio binds them
into its own module with `studio_core.modules.bind`; they read that module's names.

`_new` and `Slides.turn` stay in each studio: a context manager is not a function bind
can rebuild. TooOld and Refused name their class in `super()`.
"""
from __future__ import annotations

# ruff: noqa: F821  these definitions read the names of the studio module they are
# bound into; each studio's test_shared_runner_use checks every one resolves there.

import contextlib
import json
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path


VARIABLE = 'HARNESS_SLIDES_RUNTIME'
MINIMUM = '0.16.0'      # the oldest runtime taken: the one the installer pins
RENDERERS = ('drive', 'local')
SCRIPT = Path('scripts') / 'harness-slides.mjs'
TIMEOUT = 300    # a local preview may wait two minutes for LibreOffice, then draw each slide
LEAD = 'outline'  # what the tool cites on a cover, section or closing slide
PROGRAMS = {'soffice': 'HARNESS_SOFFICE', 'pdftoppm': 'HARNESS_PDFTOPPM',
            'pdfinfo': 'HARNESS_PDFINFO'}   # the variables the tool reads for each program
COUNTED = re.compile(r'^\d+ problems to fix:$')
NOISE = re.compile(r'^\((?:node:\d+\)|Use `node )')   # Node's own warnings, not the tool's
PREVIEWING = threading.Lock()   # one LibreOffice render at a time, whoever asks
GUIDES = {'design guidance': 'design.md', 'composition guidance': 'compositions.md',
          'drafting guidance': 'draft.md', 'gallery': 'gallery.md',
          'review guidance': 'review.md'}   # under REFERENCES
REFERENCES = Path('references')
GALLERY = REFERENCES / 'gallery'    # one drawn slide for each relation, as JSON
READ_MOST = 60_000      # characters of one guidance file that are handed on
RELATIONS = ('order', 'dependency', 'hierarchy', 'membership', 'contrast', 'parallel',
             'overlap', 'quantity', 'none')   # what a slide can show, as the tool names them
POOL = 4   # the Google preview decks Harness Slides keeps, unless HARNESS_PREVIEW_POOL_SIZE says
_POOLS: dict = {}
_POOLS_HELD = threading.Lock()


def pool_size() -> int:
    """How many Google previews the slides tool's pool takes at once: its own
    HARNESS_PREVIEW_POOL_SIZE when that is a whole number of 1 or more, else POOL."""
    try:
        size = int(os.environ.get('HARNESS_PREVIEW_POOL_SIZE') or POOL)
    except ValueError:
        return POOL
    return size if size >= 1 else POOL


def _pooled(size: int) -> threading.BoundedSemaphore:
    with _POOLS_HELD:
        return _POOLS.setdefault(size, threading.BoundedSemaphore(size))


def locations() -> list[Path]:
    """Where an installed harness-slides may be. The override, when set, is the only place
    looked."""
    return companion.locations(VARIABLE, 'harness-slides', 'Harness Slides')


def find_runtime() -> Path:
    """The installed harness-slides, with links followed so one version is used throughout.
    Refuses when there is none."""
    return companion.find_runtime(locations(), SCRIPT, VARIABLE, 'harness-slides',
                                  'a deck cannot be made')


def run_command(command: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run the command line once: (exit code, standard output, standard error)."""
    return companion.run_command(command, cwd, TIMEOUT, 'The slides tool')


def _numbers(version: str) -> tuple:
    return tuple(int(part) for part in re.findall(r'\d+', version)[:3])


def _blocked(out: str) -> dict | None:
    """A refusal the tool printed as JSON on its standard output, or None when it printed
    none."""
    try:
        found = json.loads(out)
    except ValueError:
        return None
    if not isinstance(found, dict) or found.get('status') != 'blocked' \
            or not isinstance(found.get('problems'), list) or not found['problems'] \
            or not all(isinstance(problem, dict) for problem in found['problems']):
        return None
    return found


def _bound(design, section: bool) -> list[str]:
    """What compile and preview add to be checked against an approved design."""
    if design is None:
        if section:
            raise WorkspaceError('A section is checked against the approved design, so it '
                                 'needs the design project.')
        return []
    return ['--design-project', str(design), *(['--section'] if section else []), '--json']


def example(relation: str) -> str:
    """What `reading()` calls the drawn example of one relation."""
    return f'example {relation}'


def read_guidance(runtime: Path, relative: Path) -> str | None:
    """One guidance file of an installed tool, as text, or None when it has no such file.
    Only a file inside the tool's own folder is read, links followed, and no more of it
    than READ_MOST characters. Nothing is run."""
    try:
        inside, file = Path(runtime).resolve(), (Path(runtime) / relative).resolve()
        if inside not in file.parents or not file.is_file():
            return None
        with file.open(encoding='utf-8', errors='replace') as handle:
            return handle.read(READ_MOST)
    except (OSError, RuntimeError):
        return None


def ready(slides: Slides | None = None, which=shutil.which, drive: bool = True) -> dict:
    """What this computer has for a deck. Nothing is written; Drive is asked one question,
    unless `drive` is False: then it is not asked, and `drive` is None."""
    asking = drive
    version, missing = None, []
    try:
        slides = slides or Slides()
        version = slides.version()
        if which('python3') is None:
            raise WorkspaceError('harness-slides writes a deck with python3, which was not '
                                 'found on this computer. Install Python 3, then try again.')
    except WorkspaceError as problem:
        slides = None
        missing.append(str(problem))

    def has(program: str) -> bool:
        return which(os.environ.get(PROGRAMS[program]) or program) is not None

    pictures, local = has('pdftoppm') and has('pdfinfo'), has('soffice')
    drive = False if asking else None
    if slides is not None and asking:
        try:
            drive = slides.drive_check()
        except WorkspaceError:
            drive = False
    if not pictures:
        missing.append('Poppler (pdftoppm and pdfinfo) was not found, so a render cannot be '
                       'turned into pictures. Install Poppler, then try again.')
    if not local:
        missing.append('LibreOffice was not found, so previews cannot be rendered on this '
                       'computer. Install it, or render previews through Google Drive.')
    if slides is not None and drive is False:
        missing.append('Google access does not reach Drive, so previews cannot be rendered '
                       'there. Run `gcloud auth login --enable-gdrive-access`, or render '
                       'previews with LibreOffice.')
    return {'tool': slides is not None, 'version': version, 'pictures': pictures,
            'local': local, 'drive': drive, 'missing': missing}


class TooOld:
    """The shared methods of the studio's TooOld."""

    def __init__(self, version: str):
        super(TooOld, self).__init__(f'harness-slides {version} is installed, and a deck needs '
                         f'{MINIMUM} or newer. Update Harness Slides, then try again.')
        self.version = version


class Refused:
    """The shared methods of the studio's Refused."""

    def __init__(self, problems: list[str], refusal: dict | None = None):
        super(Refused, self).__init__('The slides tool refused: ' + ' '.join(problems))
        self.problems = problems
        self.found = list((refusal or {}).get('problems') or ())
        self.revision = (refusal or {}).get('designRevision')

    @property
    def codes(self) -> list[str]:
        """The code of each problem, in order, when the refusal came as JSON."""
        return [str(problem.get('code')) for problem in self.found]

    @property
    def left(self) -> dict | None:
        """The file a failed preview had already written in Drive, or None."""
        for line in self.problems:
            found = LEFT.search(line)
            if found:
                return {'fileId': found[2], 'url': found[1]}
        return None


class Slides:
    """The shared methods of the studio's Slides."""

    def __init__(self, runtime: Path | None = None, run=None, read=None):
        self.run = run or run_command
        self.read = read or read_guidance
        self.runtime = Path(runtime) if runtime else find_runtime()
        self.node = 'node' if run else shutil.which('node')
        self._designs: bool | None = None
        self._sections: bool | None = None
        self._assets: bool | None = None
        self._reviews: bool | None = None
        self._capabilities: frozenset | None = None
        self._asked_capabilities = False
        if self.node is None:
            raise WorkspaceError('harness-slides needs Node.js 20 or newer, which was not '
                                 'found on this computer. Install it, then try again.')
        found = self.version()
        if not _numbers(found):
            raise WorkspaceError('harness-slides did not say which version it is. Check '
                                 'that it is installed whole.')
        if _numbers(found) < _numbers(MINIMUM):
            raise TooOld(found)

    def _call(self, *args: str) -> str:
        code, out, err = self.run([self.node, str(self.runtime / SCRIPT), *args])
        if code != 0:
            found = _blocked(out) if '--json' in args else None
            if found:
                raise Refused([str(problem.get('detail') or problem.get('code'))
                               for problem in found['problems']], found)
            raise Refused(_problems(err, code))
        return out

    def _json(self, *args: str) -> dict:
        try:
            found = json.loads(self._call(*args))
        except ValueError:
            found = None
        if not isinstance(found, dict):
            raise WorkspaceError('The slides tool answered with something other than the '
                                 'JSON it should. Check that it is installed whole.')
        return found

    def version(self) -> str:
        """The runtime's version, as it states it."""
        return self._call('--version').strip().rpartition(' ')[2]

    def outline_contract(self, brand: Path) -> str:
        """What an outline holds and how much a slide of this brand carries, as text."""
        return self._call('outline', 'contract', '--brand', str(brand)).strip()

    def outline_check(self, outline: Path, brand: Path) -> dict:
        """Check an outline. An outline that is not one is refused; one whose words need
        work comes back with `findings`, each {'slide', 'code', 'detail'}."""
        return self._json('outline', 'check', '--file', str(outline), '--brand', str(brand))

    def outline_start(self, outline: Path, brand: Path, folder: Path) -> dict:
        """Split an approved outline into its parts, in a new folder: a lead file for each
        run of cover, section and closing slides, a brief for each section of content
        slides, and parts.json, which lists them all in order."""
        with _new(folder):
            return self._json('outline', 'start', '--file', str(outline), '--brand',
                              str(brand), '--output', str(folder))

    def compose_contract(self, brand: Path) -> str:
        """How a slide is drawn and the sizes this brand gives, as text."""
        return self._call('compose', 'contract', '--brand', str(brand)).strip()

    def layouts(self, brand: Path) -> dict:
        """The layouts of the brand's template. One with `title` false shows no title."""
        return self._json('compose', 'layouts', '--brand', str(brand))

    def merge(self, parts: Path, composition: Path) -> dict:
        """Join the files parts.json lists, which sit beside it, into one composition."""
        with _new(composition):
            return self._json('compose', 'merge', '--file', str(parts), '--output',
                              str(composition))

    def preview(self, compiled: Path, folder: Path, renderer: str,
                file_id: str | None = None, slide: str | None = None,
                design: Path | None = None, section: bool = False) -> dict:
        """Render what was compiled and return each slide as a picture, in a new folder.
        `slide` names one slide to draw; the whole deck is still rendered. With `design`,
        the build is checked first against the design approved there now, as `compile`
        checks it."""
        if renderer not in RENDERERS:
            raise WorkspaceError(f'A preview is rendered through {RENDERERS[0]} or '
                                 f'{RENDERERS[1]}, not {renderer}.')
        args = ['compose', 'preview', '--file', str(compiled), '--output', str(folder),
                '--renderer', 'google' if renderer == 'drive' else 'local']
        # A tool with a preview pool reuses its own few preview decks: no file is named.
        named = bool(file_id) and renderer == 'drive' and not self.has('google-preview-pool')
        rest = [*(['--slide', slide] if slide else []), *_bound(design, section)]
        with self.turn(renderer), _new(folder):
            try:
                shown = self._json(*args, *(['--file-id', file_id] if named else []), *rest)
            except Refused as refusal:
                # The file named was taken over by a newer preview: preview again, unnamed.
                if not named or not ('preview-replaced' in refusal.codes or any(
                        'replaced by a newer one' in line for line in refusal.problems)):
                    raise
                shown = self._json(*args, *rest)
            if not shown.get('deck') or not isinstance(shown.get('slides'), list):
                raise WorkspaceError('The slides tool rendered a preview and did not say '
                                     'where its slides are. Check that it is installed '
                                     'whole.')
        return {**shown, 'renderer': renderer, 'contactSheet': shown.get('contactSheet'),
                'fileId': shown.get('fileId'), 'url': shown.get('url')}

    def critique(self, preview_folder: Path, assessment: Path) -> dict:
        """Record a reviewer's findings against the render they looked at. One preview
        takes one critique; a second is refused."""
        return self._json('compose', 'critique', '--file', str(preview_folder),
                          '--assessment', str(assessment))

    def render(self, compiled: Path, deck: Path) -> dict:
        """Write the deck as a new PowerPoint file. Its hash differs from a preview's deck
        of the same slides, so deliver the deck that was looked at."""
        with _new(deck):
            return self._json('compose', 'render', '--file', str(compiled), '--output',
                              str(deck))

    def designs(self) -> bool:
        """Whether this tool keeps the design session a deck's outline is approved through:
        a proposal of schema 2, one question for the whole plan, and refusals as JSON. The
        tool is asked, not its version: a proposal from a file that is not there, in an empty
        folder that is thrown away, is refused as JSON by a tool that has all three, and
        nothing is written. The answer is kept."""
        listed = self.capabilities()
        if self._designs is None and listed is not None:
            self._designs = {'design-batch', 'design-schema-2', 'json-refusals'} <= listed
        if self._designs is None:
            try:
                with tempfile.TemporaryDirectory() as folder:
                    code, out, _ = self.run([
                        self.node, str(self.runtime / SCRIPT), 'design', 'propose',
                        '--project', str(Path(folder) / 'project'), '--file',
                        str(Path(folder) / 'none.json'), '--mode', 'batch', '--json'])
            except (WorkspaceError, OSError):
                code, out = 0, ''
            self._designs = code != 0 and _blocked(out) is not None
        return self._designs

    def sections(self) -> bool:
        """Whether this tool checks a section against the approved design, as a deck drawn
        from one needs: `--section` beside `--design-project` on compile and preview, with
        refusals as JSON. Asked as `designs` asks, and kept: `--section` alone is refused as
        JSON `input-invalid` by a tool that has it, before the file it names is read."""
        listed = self.capabilities()
        if self._sections is None and listed is not None:
            self._sections = {'compose-section', 'json-refusals'} <= listed
        if self._sections is None:
            try:
                with tempfile.TemporaryDirectory() as folder:
                    code, out, _ = self.run([
                        self.node, str(self.runtime / SCRIPT), 'compose', 'compile', '--file',
                        str(Path(folder) / 'none.json'), '--section', '--json'])
            except (WorkspaceError, OSError):
                code, out = 0, ''
            found = _blocked(out) if code != 0 else None
            self._sections = bool(found) and [problem.get('code') for problem
                                              in found['problems']] == ['input-invalid']
        return self._sections

    def has(self, name: str) -> bool:
        """Whether the tool's `version` lists this capability. A tool that lists none has
        none of them."""
        return name in (self.capabilities() or ())

    def capabilities(self) -> frozenset | None:
        """What the tool says it has, as `version` lists it, or None when it lists nothing,
        as 0.13.1 and the builds before the list do not. Asked once."""
        if not self._asked_capabilities:
            self._asked_capabilities = True
            try:
                found = json.loads(self._call('version'))
            except (WorkspaceError, OSError, ValueError):
                found = None
            listed = found.get('capabilities') if isinstance(found, dict) else None
            self._capabilities = frozenset(str(name) for name in listed) \
                if isinstance(listed, list) else None
        return self._capabilities

    def assets(self) -> bool:
        """Whether this tool keeps an asset manifest a deck's pictures and icons are recorded
        in: its capability `assets`, or for a tool that lists none, whether `assets status` of
        an empty folder, thrown away after, answers as JSON. Nothing is written. Kept."""
        if self._assets is None:
            listed = self.capabilities()
            if listed is not None:
                self._assets = 'assets' in listed
            else:
                try:
                    with tempfile.TemporaryDirectory() as folder:
                        code, out, _ = self.run([
                            self.node, str(self.runtime / SCRIPT), 'assets', 'status',
                            '--project', folder, '--json'])
                    found = json.loads(out) if code == 0 else None
                except (WorkspaceError, OSError, ValueError):
                    found = None
                self._assets = isinstance(found, dict) and isinstance(found.get('assets'),
                                                                      list)
        return self._assets

    def design_status(self, project: Path) -> dict:
        """Where the design of `project` stands, with the question waiting now."""
        return self._json('design', 'status', '--project', str(project), '--json')

    def design_check(self, project: Path) -> dict:
        """The approved design, which may be built. Refused until every slide is approved."""
        return self._json('design', 'check', '--project', str(project), '--json')

    def design_respond(self, project: Path, reply: dict) -> dict:
        """Record a person's answer: {'questionId', 'planRevision', 'decision',
        'feedback'}. Only what the person decided is ever sent."""
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'reply.json'
            file.write_text(json.dumps(reply, ensure_ascii=False), encoding='utf-8')
            return self._json('design', 'respond', '--project', str(project), '--file',
                              str(file), '--json')

    def asset_icon(self, project: Path, icon: str, ident: str, alt: str | None = None,
                   brand: Path | None = None) -> dict:
        """Record the brand icon `icon`, a library ID, as the asset `ident`. With `brand` the
        ID is checked against the brand's hashed icon index."""
        return self._json('assets', 'icon', icon, '--project', str(project), '--id', ident,
                          *([f'--alt={alt}'] if alt else []),
                          *(['--brand', str(brand)] if brand else []), '--json')

    def images_status(self) -> dict:
        """Whether the tool's image provider is set up: {'status', 'provider', 'steps'?}.
        It reads its own setup and asks nobody."""
        return self._json('images', 'status', '--json')

    def generate_image(self, project: Path, ident: str, prompt: str, output: str, slide: str,
                       alt: str | None = None) -> dict:
        """Have the tool's image provider make the approved artwork of `slide` from the
        brief `prompt`, at `output` inside the project's assets folder, and record it as the
        asset `ident`. A request made again with the same brief costs nothing more."""
        with tempfile.TemporaryDirectory() as folder:
            brief = Path(folder) / 'brief.txt'
            brief.write_text(prompt, encoding='utf-8')
            return self._json('images', 'generate', '--project', str(project), '--id', ident,
                              '--prompt-file', str(brief), '--output', output,
                              '--design-project', str(project), '--slide', slide,
                              *([f'--alt={alt}'] if alt else []), '--json')

    def reviews(self) -> bool:
        """Whether this tool reviews a whole compiled deck against its approved design and
        renders the deck it reviews: its capability `compose-review`. A tool that lists no
        capabilities has none, so it is not asked by a refusal."""
        if self._reviews is None:
            self._reviews = 'compose-review' in (self.capabilities() or ())
        return self._reviews

    def review_slide(self, output: Path, slide: str) -> dict:
        """One slide's part of a prepared review, by its ID, once its receipts are checked."""
        return self._json('review', '--output', str(output), '--slide', slide, '--json')

    def review_mark(self, output: Path, revision: str, numbers: list[int], note: str) -> dict:
        """Record that the pictures of these slides were looked at, for this revision."""
        return self._json('review', '--output', str(output), '--mark',
                          ','.join(str(number) for number in numbers), '--revision', revision,
                          '--note', note, '--json')

    def review_assess(self, output: Path, revision: str, assessment: dict) -> dict:
        """Record a creative assessment of this revision: every criterion of every slide."""
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'assessment.json'
            file.write_text(json.dumps(assessment, ensure_ascii=False), encoding='utf-8')
            return self._json('review', '--output', str(output), '--assessment', str(file),
                              '--revision', revision, '--json')

    def reading(self, brand: Path | None = None) -> dict:
        """The tool's guidance for whoever writes an outline or draws a slide, as
        {name: text}. It is the same for every brand, so `brand` changes nothing."""
        wanted = {name: REFERENCES / file for name, file in GUIDES.items()}
        wanted.update({example(relation): GALLERY / f'{relation}.json'
                       for relation in RELATIONS})
        found = {name: self.read(self.runtime, relative) for name, relative in wanted.items()}
        return {name: text for name, text in found.items()
                if isinstance(text, str) and text.strip()}

    def drive_check(self) -> bool:
        """Whether Google access reaches Drive and Drive turns PowerPoint into slides. It
        reads one fact about the account and changes nothing."""
        try:
            found = self._json('drive', 'check')
        except Refused:
            return False
        return bool(found.get('account')) and found.get('pptxImportAdvertised') is not False

    def drive_import(self, deck: Path, name: str) -> dict:
        """Put a deck in Drive as Google Slides. It is not tried twice: an upload that
        failed may still have made a file."""
        return self._json('drive', 'import', '--file', str(deck), '--name', name)


NAMES = ('VARIABLE', 'MINIMUM', 'RENDERERS', 'SCRIPT', 'TIMEOUT', 'LEAD', 'PROGRAMS', 'COUNTED',
         'NOISE', 'PREVIEWING', 'GUIDES', 'REFERENCES', 'GALLERY', 'READ_MOST', 'RELATIONS',
         'POOL', '_POOLS', '_POOLS_HELD', 'pool_size', '_pooled', 'locations', 'find_runtime',
         'run_command', '_numbers', '_blocked', '_bound', 'example', 'read_guidance', 'ready')
METHODS = {'TooOld': ('__init__',), 'Refused': ('__init__', 'codes', 'left'), 'Slides':
           ('__init__', '_call', '_json', 'version', 'outline_contract', 'outline_check',
           'outline_start', 'compose_contract', 'layouts', 'merge', 'preview', 'critique',
           'render', 'designs', 'sections', 'has', 'capabilities', 'assets', 'design_status',
           'design_check', 'design_respond', 'asset_icon', 'images_status', 'generate_image',
           'reviews', 'review_slide', 'review_mark', 'review_assess', 'reading', 'drive_check',
           'drive_import')}
