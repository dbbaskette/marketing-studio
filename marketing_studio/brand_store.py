"""Brand packs and icon libraries in the studios' storage, and the working copies that make them.

What a caller needs to know
---------------------------
    place = brand_store.storage(shared, checkouts)    # where the brands folder is
    brand_store.listing(found, place)                 # packs, libraries, working copies
    work = brand_store.start(place, 'brand', 'tanzu', 'Tanzu Division', update=True)
    brand_store.add_source(work, 'template.pptx', data)   # or {'clash': name}
    brand_store.keep_source(work, name, 'there' | 'new' | 'both')
    brand_store.begin(work, 'extract', lambda line, stop: brand_store.extract(...))
    brand_store.view(work)                            # what the page shows
    brand_store.edit(work, 'guide', text); brand_store.accept(work, 'guide')
    saved = brand_store.save(found, place, work)      # check, seal, copy, commit
    brand_store.push(place)                           # only on the person's yes
    brand_store.discard(work)

- Storage: with local Git storage the brands folder is `<local.root>/brands`, a Git
  repository of its own, made on the first Save. With a team repository it is `brands/` in
  a studio's checkout of it (`studio_core.brand_data.unplaced`, or the first checkout when
  none has the folder yet), and a commit there takes only `brands/<id>` (or the library's
  folder) under the workspace write lock every studio takes.
- A working copy is in Marketing Studio's data folder, `brand-work/<kind>-<id>/`, laid out
  as the brands folder is, so that Harness Brand finds sources and icon libraries beside
  the pack. Sources added go into it, and storage changes only on Save. Its record,
  `work.json`, keeps the fingerprint of what storage held when it was made: Save refuses
  when storage changed since.
- One background task (Extract or the assistant's job) runs at a time per working copy.
  Its lines and how it ended are in the record; a task left running by a Marketing Studio
  that has closed is read as stopped. A task that fails or is stopped writes nothing into
  the pack: its work is written only once it has all succeeded.
- Parts are the pack's judgement files as the page shows them. A part is accepted for the
  content it had when it was accepted; on Update a part the same as the current pack's is
  unchanged. Save refuses while any part waits.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from studio_core import brand_data
from studio_core.process_lock import ProcessRLock, workspace_lock_path

from . import brand_skill, state
from .errors import WorkspaceError

SCHEMA = 1
LIBRARIES = brand_data.LIBRARIES
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
VARIANT = re.compile(r'^[a-z][a-z0-9-]{0,30}$')
FILE_NAME = re.compile(r'^[^/\\\x00-\x1f]{1,120}$')
KINDS = ('brand', 'library')
LIBRARY_KINDS = ('glyph', 'picture')
SOURCE_LIMIT = 40_000_000       # bytes in one source file
LINES = 200                     # task lines kept
SEALS = ('files', 'sources', 'brandSha256')
JUDGEMENT = ('relationship', 'contentRange', 'components', 'searchTerms', 'delivery',
             'searchable', 'notes')
PARTS = {'roles': ('brand.json', 'Colour roles and slide settings'),
         'layouts': ('layouts.json', 'What each layout is for'),
         'guide': ('guide.md', 'Brand rules, voice and slides'),
         'directions': ('directions.json', 'Deck directions'),
         'audit': ('audit.json', 'Audit limits')}
SEEN = ('.png', '.svg', '.jpg', '.jpeg')
MEDIA = {'.png': 'image/png', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
PREVIEW_HELP = ('Previews need LibreOffice and Poppler on this computer (brew install --cask '
                'libreoffice; brew install poppler). The layouts are measured all the same.')
LOCK = threading.RLock()        # every record read and write in this process
TASKS: dict[str, tuple[threading.Thread, threading.Event]] = {}


# --- storage ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Storage:
    folder: Path            # the brands folder
    team: bool              # a studio's checkout of the team repository
    repo: Path | None       # the repository the folder is committed in; None until made
    address: str | None     # the team repository

    @property
    def where(self) -> str:
        return (f'brands/ in {self.address}, through the copy at {self.repo}' if self.team
                else f'{self.folder}, kept with local Git')


def git(repo, *args, env=None, seconds=60):
    try:
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                              timeout=seconds, stdin=subprocess.DEVNULL,
                              env={**os.environ, 'GIT_TERMINAL_PROMPT': '0',
                                   'GIT_SSH_COMMAND': 'ssh -o BatchMode=yes', **(env or {})})
    except FileNotFoundError as failure:
        raise WorkspaceError('Saving a brand needs Git, which is not installed. Install it and '
                             'try again.') from failure
    except subprocess.TimeoutExpired as failure:
        raise WorkspaceError(f'Git did not answer in {seconds} seconds.') from failure


def reason(done) -> str:
    lines = [line.strip() for line in (done.stderr or done.stdout or '').splitlines() if line.strip()]
    return lines[-1] if lines else f'it ended with exit code {done.returncode}'


def storage(shared, checkouts=()) -> Storage:
    """The brands folder the shared settings say, for Marketing Studio, which has no
    workspace of its own."""
    shared = shared if isinstance(shared, dict) else {}
    section = shared.get('team') if isinstance(shared.get('team'), dict) else {}
    # A setting of the wrong kind is taken as not given, as studio_core.brand_data takes it.
    team = section.get('repository') if isinstance(section.get('repository'), str) else None
    if not team:
        folder = brand_data.folder(shared)
        return Storage(folder, False, folder if (folder / '.git').exists() else None, None)
    folder = brand_data.unplaced(shared, checkouts)
    if folder is None:
        folder = next((found for repository, address in checkouts
                       if (found := brand_data.folder(shared, repository, address)) is not None),
                      None)
    if folder is None:
        raise WorkspaceError(
            f'With a team repository, brand packs are kept in its brands folder, and no studio '
            f'on this computer has a copy of {team} yet. Open a studio once so it joins the '
            'repository, then open Brands again.')
    return Storage(folder, True, folder.parent, team)


def write_lock(place: Storage):
    """The workspace write lock every studio takes on the repository."""
    return ProcessRLock(lambda: workspace_lock_path(place.repo, state.data_root()),
                        refusal=WorkspaceError)


# --- small file helpers ----------------------------------------------------------------

def read_json(path: Path, default=None):
    try:
        found = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default
    return found


def write_json(path: Path, value) -> None:
    put(path, (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def put(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f'.{path.name}.pending')
    pending.write_bytes(data)
    os.replace(pending, path)


def fingerprint(folder: Path) -> str:
    """What a brand's or library's folder in storage holds, as one hash: 'none' when absent."""
    folder = Path(folder)
    if not folder.exists():
        return 'none'
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob('*') if p.is_file() and p.name != '.DS_Store'):
        digest.update(path.relative_to(folder).as_posix().encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def files_in(folder: Path) -> list[dict]:
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return [{'name': path.relative_to(folder).as_posix(), 'size': path.stat().st_size}
            for path in sorted(folder.rglob('*'))
            if path.is_file() and not any(part.startswith('.') for part in path.relative_to(folder).parts)]


def checked(found, folder, env=None) -> dict:
    """What `pack check` says of a pack or library folder: {'ok', 'problems'}."""
    try:
        _, said = brand_skill.answer(found, ['pack', 'check', str(folder), '--json'], env=env)
    except WorkspaceError as failure:
        return {'ok': False, 'problems': [str(failure)]}
    problems = [str(each) for each in (said.get('problems') or [])] if isinstance(said, dict) else []
    return {'ok': bool(isinstance(said, dict) and said.get('ok')) and not problems,
            'problems': problems or ([] if isinstance(said, dict) else ['pack check gave no answer.'])}


def library_summary(archive: Path) -> dict:
    try:
        with zipfile.ZipFile(archive) as opened:
            library = json.loads(opened.read('library.json'))
            icons = json.loads(opened.read('icons.json')).get('icons') or []
        return {'name': str(library.get('name') or archive.parent.name),
                'kind': library.get('kind'), 'count': len(icons)}
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, AttributeError):
        return {'name': archive.parent.name, 'kind': None, 'count': None}


# --- the listing -----------------------------------------------------------------------

def unshared(place: Storage, path: str) -> int:
    """Commits on this checkout touching `path` that the team repository does not have."""
    if not place.team or place.repo is None:
        return 0
    done = git(place.repo, 'rev-list', '--count', '@{u}..HEAD', '--', path)
    return int(done.stdout.strip() or 0) if done.returncode == 0 else 0


def listing(found, place: Storage) -> dict:
    folder = place.folder
    packs, libraries = [], []
    if folder.is_dir():
        for entry in sorted(folder.iterdir()):
            pack = entry / 'pack'
            if entry.name == LIBRARIES or entry.name.startswith('.') or not (pack / 'brand.json').is_file():
                continue
            brand = read_json(pack / 'brand.json', {}) or {}
            variants = brand.get('variants') if isinstance(brand.get('variants'), dict) else {}
            packs.append({
                'id': entry.name, 'name': str(brand.get('name') or entry.name),
                'variants': list(variants),
                'slides': any(isinstance(v, dict) and v.get('slides') for v in variants.values()),
                'libraries': [str(each.get('library')) for each in brand.get('icons') or []
                              if isinstance(each, dict)],
                'check': checked(found, pack), 'unshared': unshared(place, f'brands/{entry.name}')})
        shelf = folder / LIBRARIES
        for entry in sorted(shelf.iterdir()) if shelf.is_dir() else ():
            if entry.name.startswith('.') or not (entry / 'library.zip').is_file():
                continue
            libraries.append({'id': entry.name, **library_summary(entry / 'library.zip'),
                              'usedBy': [pack['name'] for pack in packs if entry.name in pack['libraries']],
                              'check': checked(found, entry),
                              'unshared': unshared(place, f'brands/{LIBRARIES}/{entry.name}')})
    return {'packs': packs, 'libraries': libraries, 'work': working_copies(),
            'where': place.where, 'team': place.team, 'skill': {'name': found.name, 'version': found.version}}


# --- working copies --------------------------------------------------------------------

def root() -> Path:
    return state.data_root() / 'brand-work'


def key_of(kind, ident) -> str:
    return f'{kind}-{ident}'


def folder_of(key: str) -> Path:
    if not isinstance(key, str) or not re.fullmatch(r'(brand|library)-[a-z0-9][a-z0-9-]{0,62}', key):
        raise WorkspaceError('Choose a brand or icon library from this page.')
    return root() / key


def inside(work: dict) -> Path:
    """The brand's or library's folder inside the working copy, as it will be in storage."""
    base = folder_of(work['key']) / 'brands'
    return base / work['id'] if work['kind'] == 'brand' else base / LIBRARIES / work['id']


def target(place: Storage, work: dict) -> Path:
    return place.folder / work['id'] if work['kind'] == 'brand' else place.folder / LIBRARIES / work['id']


def record(key: str) -> dict:
    with LOCK:
        work = read_json(folder_of(key) / 'work.json')
        if not isinstance(work, dict) or work.get('schema') != SCHEMA:
            raise WorkspaceError('That working copy is not there any more. Start it again from Brands.')
        task = work.get('task')
        alive = TASKS.get(key)
        if task and task.get('state') == 'running' and not (alive and alive[0].is_alive()):
            task.update(state='stopped', ended=time.time(),
                        detail='Marketing Studio was closed while this ran, so nothing was kept from it. Run it again.')
            keep(work)
        return work


def keep(work: dict) -> dict:
    with LOCK:
        write_json(folder_of(work['key']) / 'work.json', work)
    return work


def working_copies() -> list[dict]:
    found = []
    folder = root()
    for entry in sorted(folder.iterdir()) if folder.is_dir() else ():
        try:
            work = record(entry.name)
        except WorkspaceError:
            continue
        found.append({'key': work['key'], 'kind': work['kind'], 'id': work['id'],
                      'name': work['name'], 'update': work['update'],
                      'task': (work.get('task') or {}).get('state')})
    return found


def check_name(name) -> str:
    if not isinstance(name, str) or not name.strip() or len(name) > 80 \
            or any(ord(c) < 32 for c in name):
        raise WorkspaceError('Give a name of at most 80 characters, such as Tanzu Division.')
    return name.strip()


def start(place: Storage, kind, ident, name=None, library_kind=None, update=False) -> dict:
    """A working copy for a new brand or library, or for updating one in storage."""
    if kind not in KINDS:
        raise WorkspaceError('Choose a brand or an icon library.')
    if not isinstance(ident, str) or not SLUG.match(ident) or ident == LIBRARIES:
        raise WorkspaceError('Give an id of lower-case letters, digits and hyphens, such as '
                             'tanzu, starting with a letter or digit.')
    key = key_of(kind, ident)
    with LOCK:
        if (folder_of(key) / 'work.json').exists():
            raise WorkspaceError(f'{ident} already has a working copy here. Continue it, or '
                                 'discard it first.')
        work = {'schema': SCHEMA, 'key': key, 'kind': kind, 'id': ident, 'update': bool(update),
                'storage': str(place.folder), 'made': time.time(), 'task': None,
                'extracted': None, 'parts': {}, 'notes': [], 'clashes': [], 'checked': None}
        stored = target(place, work)
        here = inside(work)
        if update:
            marker = stored / ('pack/brand.json' if kind == 'brand' else 'library.zip')
            if not marker.is_file():
                raise WorkspaceError(f'There is no {ident} {"brand pack" if kind == "brand" else "icon library"} '
                                     'in storage to update.')
            if kind == 'brand':
                work['name'] = str((read_json(marker, {}) or {}).get('name') or ident)
            else:
                summary = library_summary(marker)
                work['name'], work['libraryKind'] = summary['name'], summary['kind'] or 'glyph'
        else:
            if stored.exists() and any(stored.iterdir()):
                raise WorkspaceError(f'{ident} is already in storage. Update it instead.')
            work['name'] = check_name(name)
            if kind == 'library':
                if library_kind not in LIBRARY_KINDS:
                    raise WorkspaceError('Choose the library\'s kind: glyph (one-colour shapes the brand '
                                         'colours) or picture (artwork kept in its own colours).')
                work['libraryKind'] = library_kind
        work['base'] = fingerprint(stored)
        base = folder_of(key)
        try:
            if update:
                shutil.copytree(stored, here, ignore=shutil.ignore_patterns('.DS_Store'))
                if kind == 'brand':
                    shutil.copytree(stored / 'pack', base / 'current')
                    # The old seal is made again at Save; it would only fail the checks.
                    brand = read_json(here / 'pack/brand.json', {})
                    if isinstance(brand, dict) and any(field in brand for field in SEALS):
                        write_json(here / 'pack/brand.json',
                                   {k: v for k, v in brand.items() if k not in SEALS})
            (here / 'sources').mkdir(parents=True, exist_ok=True)
            if kind == 'brand':
                (here / 'pack').mkdir(parents=True, exist_ok=True)
                shelf = place.folder / LIBRARIES
                for library in sorted(shelf.iterdir()) if shelf.is_dir() else ():
                    if (library / 'library.zip').is_file():
                        (base / 'brands' / LIBRARIES / library.name).mkdir(parents=True, exist_ok=True)
                        shutil.copy2(library / 'library.zip',
                                     base / 'brands' / LIBRARIES / library.name / 'library.zip')
            keep(work)
        except BaseException:
            shutil.rmtree(base, ignore_errors=True)
            raise
    return work


def discard(key: str) -> None:
    with LOCK:
        running = TASKS.get(key)
        if running and running[0].is_alive():
            raise WorkspaceError('Stop what is running first, then discard the working copy.')
        shutil.rmtree(folder_of(key), ignore_errors=True)


# --- sources ---------------------------------------------------------------------------

def source_name(name) -> str:
    if not isinstance(name, str) or not FILE_NAME.match(name) or name.startswith('.') \
            or name.strip() != name or name in ('.', '..'):
        raise WorkspaceError('Give the file a plain name that does not start with a dot.')
    return name


def idle(key: str) -> None:
    running = TASKS.get(key)
    if running and running[0].is_alive():
        raise WorkspaceError('Wait for what is running to finish, or stop it, first.')


def add_source(key: str, name, data: bytes) -> dict:
    """Copy one file into the working copy's sources. A taken name waits for the person."""
    with LOCK:
        work = record(key)
        idle(key)
        name = source_name(name)
        if len(data) > SOURCE_LIMIT:
            raise WorkspaceError(f'{name} is larger than {SOURCE_LIMIT // 1_000_000} MB.')
        if work['kind'] == 'library' and not name.lower().endswith(('.svg', '.json', '.zip')):
            raise WorkspaceError(f'{name} is not an icon source. Add SVG files, an icons.json, '
                                 'or a ZIP archive of them.')
        sources = inside(work) / 'sources'
        if (sources / name).exists():
            put(folder_of(key) / 'incoming' / name, data)
            if name not in work['clashes']:
                work['clashes'].append(name)
            keep(work)
            return {'clash': name}
        put(sources / name, data)
        return {'added': name}


def free_name(folder: Path, name: str) -> str:
    stem, dot, ending = name.rpartition('.') if '.' in name.strip('.') else (name, '', '')
    for number in range(2, 1000):
        candidate = f'{stem} ({number}){dot}{ending}'
        if not (folder / candidate).exists():
            return candidate
    raise WorkspaceError(f'There are too many sources named like {name}.')


def keep_source(key: str, name, which) -> dict:
    """Settle a taken name: keep the one there, the new one, or both (the new one renamed)."""
    with LOCK:
        work = record(key)
        idle(key)
        if name not in work['clashes'] or which not in ('there', 'new', 'both'):
            raise WorkspaceError('Choose which file to keep from this page.')
        incoming = folder_of(key) / 'incoming' / name
        sources = inside(work) / 'sources'
        kept = name
        if which == 'new':
            os.replace(incoming, sources / name)
        elif which == 'both':
            kept = free_name(sources, name)
            os.replace(incoming, sources / kept)
        else:
            incoming.unlink(missing_ok=True)
        work['clashes'].remove(name)
        keep(work)
        return {'kept': kept, 'which': which}


# --- background tasks ------------------------------------------------------------------

def begin(key: str, kind: str, job, part=None) -> dict:
    """Run `job(line, stop)` in the background as this working copy's one task."""
    with LOCK:
        work = record(key)
        idle(key)
        stop = threading.Event()
        work['task'] = {'kind': kind, 'part': part, 'state': 'running', 'lines': [],
                        'detail': '', 'started': time.time(), 'ended': None}
        keep(work)

        def line(text):
            text = ' '.join(str(text).split())[:300]
            if not text:
                return
            with LOCK:
                current = record(key)
                lines = current['task']['lines']
                if not lines or lines[-1] != text:
                    lines.append(text)
                    del lines[:-LINES]
                    keep(current)

        def run():
            ending, detail = 'done', ''
            try:
                job(line, stop)
            except brand_skill.Stopped:
                ending, detail = 'stopped', 'It was stopped before it finished, so nothing was kept from it.'
            except WorkspaceError as failure:
                ending, detail = 'failed', str(failure)
            except Exception as failure:   # reported to the person, never lost
                ending, detail = 'failed', f'{type(failure).__name__}: {failure}'
            if stop.is_set() and ending == 'done':
                ending, detail = 'stopped', 'It was stopped before it finished, so nothing was kept from it.'
            with LOCK:
                try:
                    current = record(key)
                except WorkspaceError:
                    return   # discarded meanwhile
                current['task'].update(state=ending, detail=detail, ended=time.time())
                keep(current)

        thread = threading.Thread(target=run, daemon=True, name=f'brands-{key}')
        TASKS[key] = (thread, stop)
        thread.start()
        return work


def stop(key: str) -> None:
    running = TASKS.get(key)
    if running and running[0].is_alive():
        running[1].set()


def wait(key: str, seconds: float = 30) -> None:
    """For tests and for Save: until this working copy's task has ended."""
    running = TASKS.get(key)
    if running:
        running[0].join(seconds)


# --- Extract ---------------------------------------------------------------------------

def guess_variant(name: str) -> str:
    return 'dark' if 'dark' in name.lower() else 'light'


def extract_brand(found, key: str, tokens=None, templates=(), icons=()):
    """The job that runs Harness Brand's pack commands into a copy of the working pack and
    puts it in place only when every command has finished."""
    work = record(key)
    if work['kind'] != 'brand':
        raise WorkspaceError('That is an icon library: extract it as one.')
    here = inside(work)
    sources = here / 'sources'
    names = {item['name'] for item in files_in(sources)}
    if tokens is not None and tokens not in names:
        raise WorkspaceError('Choose the design-system export from the sources.')
    variants = []
    for item in templates:
        if not isinstance(item, dict) or item.get('source') not in names \
                or not str(item.get('source')).lower().endswith('.pptx'):
            raise WorkspaceError('Choose each template from the sources: a PowerPoint (.pptx) file.')
        if not isinstance(item.get('variant'), str) or not VARIANT.match(item['variant']):
            raise WorkspaceError('Name each variant in lower-case letters, digits and hyphens, '
                                 'starting with a letter, such as light or dark.')
        variants.append(item['variant'])
    if len(set(variants)) != len(variants):
        raise WorkspaceError('Give each template a variant of its own.')
    shelf = folder_of(key) / 'brands' / LIBRARIES
    for library in icons:
        if not isinstance(library, str) or not (shelf / library / 'library.zip').is_file():
            raise WorkspaceError(f'There is no icon library {library} to use.')
    pack = here / 'pack'
    if tokens is None and not (pack / 'tokens.json').is_file():
        raise WorkspaceError('Choose the design-system export: a pack is drafted from its tokens.')

    def job(line, stop):
        trial = folder_of(key) / 'brands' / work['id'] / '.pack-extracting'
        shutil.rmtree(trial, ignore_errors=True)
        shutil.copytree(pack, trial)
        outcome = {'tokens': tokens, 'templates': list(templates), 'icons': list(icons),
                   'previews': {}, 'draft': []}
        try:
            def command(*args):
                code, said = brand_skill.answer(found, list(args), stop=stop, seconds=900)
                if code != 0:
                    raise WorkspaceError(brand_skill.said(json.dumps(said), code))
                return said
            if tokens is not None:
                line(f'Reading the tokens in {tokens}')
                made = command('pack', 'tokens', str(sources / tokens), '--into', str(trial),
                               '--replace', '--json')
                line(f"Found {made.get('colors')} colours ({made.get('dark')} with a dark value) and "
                     f"{made.get('styles')} type styles")
            for item in templates:
                line(f"Measuring {item['source']} as {item['variant']}")
                made = command('pack', 'measure', str(sources / item['source']), '--variant',
                               item['variant'], '--into', str(trial), '--replace', '--json')
                line(f"Measured {made.get('measured')} layouts, {made.get('used')} with an example slide")
            measured = read_json(trial / 'layouts.json', {}) or {}
            for variant in (measured.get('variants') or {}):
                line(f'Drawing the {variant} previews')
                try:
                    made = command('pack', 'previews', str(trial), '--variant', variant, '--json')
                    line(f"Drew {made.get('drawn')} previews for {variant}")
                    outcome['previews'][variant] = None
                except WorkspaceError as failure:
                    outcome['previews'][variant] = f'{failure} {PREVIEW_HELP}'
                    line(f'No previews for {variant}: {failure}')
            if not (trial / 'brand.json').is_file():
                line('Drafting brand.json, guide.md, the directions and the audit limits')
                args = ['pack', 'scaffold', str(trial), '--id', work['id'], '--name', work['name'],
                        '--json']
                if icons:
                    args[-1:-1] = ['--icons', ','.join(icons)]
                made = command(*args)
                outcome['draft'] = [str(each) for each in made.get('draft') or []]
            if stop.is_set():
                raise brand_skill.Stopped()
            with LOCK:
                shutil.rmtree(pack)
                os.replace(trial, pack)
                current = record(key)
                current['extracted'] = {**outcome, 'at': time.time()}
                keep(current)
            line('Extracted. Review what came out below.')
        finally:
            shutil.rmtree(trial, ignore_errors=True)
    return job


def extract_library(found, key: str):
    work = record(key)
    if work['kind'] != 'library':
        raise WorkspaceError('That is a brand: extract it as one.')
    here = inside(work)
    sources = sorted(path for path in (here / 'sources').iterdir()
                     if not path.name.startswith('.')) if (here / 'sources').is_dir() else []
    if not sources:
        raise WorkspaceError('Add the icons first: SVG files, an icons.json or a ZIP archive of them.')

    def job(line, stop):
        trial = folder_of(key) / 'trial' / work['id']
        shutil.rmtree(trial.parent, ignore_errors=True)
        trial.mkdir(parents=True)
        try:
            line(f"Making the {work['name']} library from {len(sources)} source{'s' if len(sources) != 1 else ''}")
            code, made = brand_skill.answer(
                found, ['pack', 'icons', *map(str, sources), '--library', work['id'], '--name',
                        work['name'], '--kind', work['libraryKind'], '--into', str(trial),
                        '--replace', '--json'], stop=stop, seconds=900)
            if code != 0 or not isinstance(made, dict):
                raise WorkspaceError('pack icons did not make the library.')
            line(f"Made {made.get('icons')} {made.get('kind')} icons; left out {len(made.get('skipped') or [])}")
            if stop.is_set():
                raise brand_skill.Stopped()
            with LOCK:
                for name in ('library.zip', 'contact-sheet.svg'):
                    if (trial / name).is_file():
                        os.replace(trial / name, here / name)
                current = record(key)
                current['extracted'] = {'icons': made.get('icons'), 'kind': made.get('kind'),
                                        'sources': made.get('sources') or [],
                                        'skipped': made.get('skipped') or [], 'at': time.time()}
                keep(current)
        finally:
            shutil.rmtree(trial.parent, ignore_errors=True)
    return job


# --- parts -----------------------------------------------------------------------------

def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def judgement(layouts) -> dict:
    """The layouts' judgement fields, by variant and layout id, with each layout's name."""
    shown = {}
    for variant, measured in ((layouts or {}).get('variants') or {}).items():
        shown[variant] = {}
        for layout in measured.get('layouts') or []:
            if isinstance(layout, dict) and isinstance(layout.get('id'), str):
                shown[variant][layout['id']] = {'name': layout.get('name'),
                                                **{k: layout[k] for k in JUDGEMENT if k in layout}}
    return shown


def part_content(pack: Path, part: str):
    """A part as the page shows it and the person edits it: text, or None when absent."""
    file = pack / PARTS[part][0]
    if not file.is_file():
        return None
    if part == 'guide':
        return file.read_text(encoding='utf-8')
    value = read_json(file)
    if value is None:
        return file.read_text(encoding='utf-8', errors='replace')
    if part == 'roles' and isinstance(value, dict):
        value = {k: v for k, v in value.items() if k not in SEALS}
    if part == 'layouts':
        value = judgement(value)
    return json.dumps(value, indent=2, ensure_ascii=False)


def same(part, one, other) -> bool:
    if one is None or other is None:
        return one is other
    if part == 'guide':
        return one.strip() == other.strip()
    try:
        return canonical(json.loads(one)) == canonical(json.loads(other))
    except ValueError:
        return one == other


def digest(text) -> str | None:
    return None if text is None else hashlib.sha256(text.encode('utf-8')).hexdigest()


def parts(work: dict) -> list[dict]:
    if work['kind'] != 'brand':
        return []
    pack = inside(work) / 'pack'
    current = folder_of(work['key']) / 'current'
    shown = []
    for part, (file, title) in PARTS.items():
        content = part_content(pack, part)
        if content is None:
            continue
        kept = work['parts'].get(part) or {}
        before = part_content(current, part) if work['update'] else None
        if kept.get('accepted') == digest(content):
            status = 'accepted'
        elif work['update'] and same(part, content, before):
            status = 'unchanged'
        else:
            status = 'review'
        shown.append({'id': part, 'file': file, 'title': title, 'state': status,
                      'by': kept.get('by') or ('current pack' if work['update'] else 'draft'),
                      'quotes': kept.get('quotes') or [], 'note': kept.get('note'),
                      'content': content, 'current': before if work['update'] else None})
    return shown


def apply_part(work: dict, part: str, value, by: str, quotes=(), pack=None) -> None:
    """Write one judgement file from a value the person or the assistant gave, into the
    working pack or the copy of it `pack` names."""
    if part not in PARTS:
        raise WorkspaceError('Choose a part of the pack from this page.')
    pack = Path(pack) if pack is not None else inside(work) / 'pack'
    file = pack / PARTS[part][0]
    if part == 'guide':
        if not isinstance(value, str) or not value.strip() or len(value) > 400_000:
            raise WorkspaceError('guide.md must be Markdown text, under the headings the format names.')
        put(file, (value.rstrip() + '\n').encode('utf-8'))
    elif part == 'layouts':
        if not isinstance(value, dict):
            raise WorkspaceError('Give the layouts as {variant: {layout id: {fields}}}.')
        layouts = read_json(file, {}) or {}
        variants = layouts.get('variants') or {}
        for variant, given in value.items():
            if variant not in variants or not isinstance(given, dict):
                raise WorkspaceError(f'layouts.json has no variant {variant}.')
            by_id = {layout.get('id'): layout for layout in variants[variant].get('layouts') or []}
            by_name = {layout.get('name'): layout for layout in variants[variant].get('layouts') or []}
            for named, fields in given.items():
                layout = by_id.get(named) or by_name.get(named)
                if layout is None or not isinstance(fields, dict):
                    raise WorkspaceError(f'{variant} has no layout {named}.')
                for field in JUDGEMENT:
                    if field in fields and fields[field] is not None:
                        layout[field] = fields[field]
                    else:
                        layout.pop(field, None)
        write_json(file, layouts)
    else:
        if not isinstance(value, dict):
            raise WorkspaceError(f'{PARTS[part][0]} must be one JSON object.')
        if part == 'roles':
            value = {k: v for k, v in value.items() if k not in SEALS}
            value['schema'], value['id'] = 1, work['id']
        write_json(file, value)
    kept = work['parts'].setdefault(part, {})
    kept.update(by=by, quotes=[q for q in quotes if isinstance(q, dict)][:200], note=None,
                accepted=None)


def parse_part(part: str, text):
    if not isinstance(text, str):
        raise WorkspaceError('Give the part as text.')
    if part == 'guide':
        return text
    try:
        return json.loads(text)
    except ValueError as failure:
        raise WorkspaceError(f'That is not JSON the pack can keep ({failure}). Correct it and save '
                             'again.') from failure


def edit(key: str, part: str, text) -> dict:
    """The person's own version of a part, accepted as it is."""
    with LOCK:
        work = record(key)
        idle(key)
        apply_part(work, part, parse_part(part, text), 'you')
        work['parts'][part]['accepted'] = digest(part_content(inside(work) / 'pack', part))
        return keep(work)


def accept(key: str, part: str) -> dict:
    with LOCK:
        work = record(key)
        idle(key)
        if part not in PARTS or part_content(inside(work) / 'pack', part) is None:
            raise WorkspaceError('Choose a part of the pack from this page.')
        work['parts'].setdefault(part, {})['accepted'] = digest(part_content(inside(work) / 'pack', part))
        return keep(work)


# --- what the page shows ---------------------------------------------------------------

def view(key: str) -> dict:
    work = record(key)
    here = inside(work)
    shown = {k: work.get(k) for k in ('key', 'kind', 'id', 'name', 'update', 'libraryKind',
                                      'task', 'extracted', 'notes', 'clashes', 'checked')}
    sources = files_in(here / 'sources')
    shown['sources'] = sources
    if work['kind'] == 'library':
        sheet = here / 'contact-sheet.svg'
        shown['library'] = {**library_summary(here / 'library.zip'),
                            'sheet': 'contact-sheet.svg' if sheet.is_file() else None} \
            if (here / 'library.zip').is_file() else None
        shown['ready'] = save_ready(work)
        return shown
    pack = here / 'pack'
    tokens = read_json(pack / 'tokens.json', {}) or {}
    shown['tokens'] = {
        'colors': [{k: c.get(k) for k in ('name', 'light', 'dark', 'usage')}
                   for c in tokens.get('colors') or [] if isinstance(c, dict)],
        'styles': [{k: s.get(k) for k in ('name', 'group', 'fontSize', 'lineHeight', 'fontWeight')}
                   for s in (tokens.get('type') or {}).get('styles') or [] if isinstance(s, dict)],
        'families': (tokens.get('type') or {}).get('families') or {}} if tokens else None
    layouts = read_json(pack / 'layouts.json', {}) or {}
    shown['layouts'] = {variant: [{'id': l.get('id'), 'name': l.get('name'), 'used': l.get('used'),
                                   'preview': f"pack/{l['preview']}" if l.get('preview') else None,
                                   'relationship': l.get('relationship')}
                                  for l in measured.get('layouts') or [] if isinstance(l, dict)]
                        for variant, measured in (layouts.get('variants') or {}).items()}
    brand = read_json(pack / 'brand.json', {}) or {}
    shown['roles'] = roles(brand, tokens)
    shown['parts'] = parts(work)
    shown['choices'] = {
        'exports': [s['name'] for s in sources if '/' not in s['name']
                    and s['name'].lower().endswith(('.zip', 'tokens.json'))],
        'templates': [{'source': s['name'], 'variant': guess_variant(s['name'])}
                      for s in sources if s['name'].lower().endswith('.pptx')],
        'libraries': sorted(path.name for path in (folder_of(key) / 'brands' / LIBRARIES).glob('*')
                            if (path / 'library.zip').is_file())}
    shown['ready'] = save_ready(work)
    return shown


def roles(brand: dict, tokens: dict) -> dict:
    """Each variant's colour roles with the colour each one names, for swatches."""
    colours = {c.get('name'): c for c in tokens.get('colors') or [] if isinstance(c, dict)}
    shown = {}
    for variant, values in (brand.get('variants') or {}).items():
        if not isinstance(values, dict):
            continue
        theme = values.get('theme') if values.get('theme') in ('light', 'dark') else 'light'
        shown[variant] = []
        for role, colour in (values.get('colors') or {}).items():
            found = colours.get(colour) or {}
            value = (found.get('dark') or found.get('light')) if theme == 'dark' else found.get('light')
            shown[variant].append({'role': role, 'color': colour,
                                   'value': value if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) else None})
    return shown


def save_ready(work: dict) -> str | None:
    """Why Save cannot run yet, or None."""
    task = work.get('task') or {}
    if task.get('state') == 'running':
        return 'Wait for what is running to finish.'
    if work.get('clashes'):
        return 'Choose which file to keep for each source whose name was taken.'
    if not work.get('extracted') and (work['kind'] == 'library' or not work['update']):
        return 'Extract first.'
    if work['kind'] == 'brand':
        waiting = [p['title'] for p in parts(work) if p['state'] == 'review']
        if waiting:
            return 'Accept or edit each part first: ' + ', '.join(waiting) + '.'
    return None


def file(key: str, path) -> tuple[str, bytes]:
    """A picture in the working copy, for the page: a preview or the contact sheet."""
    work = record(key)
    here = inside(work)
    if not isinstance(path, str) or not path.lower().endswith(SEEN):
        raise WorkspaceError('Only previews and contact sheets are shown.')
    found = (here / path).resolve()
    if here.resolve() not in found.parents or not found.is_file():
        raise WorkspaceError('That picture is not in this working copy.')
    return MEDIA[found.suffix.lower()], found.read_bytes()


# --- Save and Push ---------------------------------------------------------------------

GITATTRIBUTES = '* -text\n'


def identity(repo: Path) -> None:
    done = git(repo, 'var', 'GIT_AUTHOR_IDENT')
    if done.returncode != 0 or not done.stdout.rpartition(' <')[0].strip():
        raise WorkspaceError(
            'Git does not know who you are, so the brand cannot be recorded. Tell it once with '
            'git config --global user.name "Your Name" and git config --global user.email '
            '"you@example.com", then save again.')


def save(found, place: Storage, key: str) -> dict:
    """Check and seal the working copy, put it in storage and commit it there. Nothing in
    storage changes unless every check passed; the working copy is removed after."""
    with LOCK:
        work = record(key)
        idle(key)
        why = save_ready(work)
        if why:
            raise WorkspaceError(why)
        if Path(work['storage']) != place.folder:
            raise WorkspaceError(f"This working copy was made for {work['storage']}, but storage is "
                                 f'now {place.folder}. Discard it and start again.')
        here = inside(work)
        folder = here / 'pack' if work['kind'] == 'brand' else here
        if work['kind'] == 'brand':
            brand = read_json(folder / 'brand.json', {})
            if isinstance(brand, dict) and any(field in brand for field in SEALS):
                write_json(folder / 'brand.json', {k: v for k, v in brand.items() if k not in SEALS})
        result = checked(found, folder)
        work['checked'] = result
        keep(work)
        if not result['ok']:
            refused = WorkspaceError('pack check does not pass yet, so nothing was saved: '
                                     + ' '.join(result['problems'][:3]))
            refused.details = {'problems': result['problems']}
            raise refused
        if work['kind'] == 'brand':
            code, sealed = brand_skill.answer(found, ['pack', 'seal', str(folder), '--json'])
            if code != 0:
                raise WorkspaceError('pack seal did not seal the pack: ' + brand_skill.said(json.dumps(sealed), code))
            again = checked(found, folder)
            if not again['ok']:
                raise WorkspaceError('The sealed pack does not pass pack check: ' + ' '.join(again['problems'][:3]))
    repo = place.repo
    if repo is None:
        place.folder.mkdir(parents=True, exist_ok=True)
        done = git(place.folder, 'init', '--quiet', '-b', 'main')
        if done.returncode != 0:
            raise WorkspaceError(f'A Git repository could not be made at {place.folder} ({reason(done)}).')
        repo = place.folder
        place = Storage(place.folder, False, repo, None)
    identity(repo)
    with write_lock(place), LOCK:
        stored = target(place, work)
        if fingerprint(stored) != work['base']:
            raise WorkspaceError(
                f"The {work['name']} {'brand pack' if work['kind'] == 'brand' else 'icon library'} in "
                'storage changed after this working copy was made, so it was not saved over. '
                'Discard this working copy and start the update again from what is there now.')
        if place.team:
            from studio_core.sync_guard import worker_in_progress
            if worker_in_progress(repo, WorkspaceError):
                raise WorkspaceError('A studio step is running in that copy of the team repository. '
                                     'Wait for it to finish, then save again.')
        incoming = stored.with_name(f'.{stored.name}.saving')
        outgoing = stored.with_name(f'.{stored.name}.replaced')
        shutil.rmtree(incoming, ignore_errors=True)
        shutil.rmtree(outgoing, ignore_errors=True)
        shutil.copytree(here, incoming, ignore=shutil.ignore_patterns('.*'))
        if stored.exists():
            os.replace(stored, outgoing)
        os.replace(incoming, stored)
        shutil.rmtree(outgoing, ignore_errors=True)
        scope = [stored.relative_to(repo).as_posix()]
        attributes = place.folder / '.gitattributes'
        if not attributes.exists():
            attributes.write_text(GITATTRIBUTES, encoding='utf-8')
            scope.append(attributes.relative_to(repo).as_posix())
        what = 'brand pack' if work['kind'] == 'brand' else 'icon library'
        message = f"{'Update' if work['update'] else 'Add'} the {work['name']} {what}"
        git(repo, 'add', '-A', '--', *scope)
        done = git(repo, 'commit', '--quiet', '--only', '-m', message, '--', *scope)
        committed = done.returncode == 0
        if not committed and git(repo, 'diff', '--cached', '--quiet', '--', *scope).returncode != 0:
            raise WorkspaceError(f'The {what} was copied into storage but Git did not record it '
                                 f'({reason(done)}). Commit it there with Git.')
        shutil.rmtree(folder_of(key), ignore_errors=True)
    answer = {'saved': work['id'], 'kind': work['kind'], 'name': work['name'],
              'committed': committed, 'message': message, 'where': place.where}
    if place.team:
        answer['push'] = outgoing_commits(place)
    return answer


def outgoing_commits(place: Storage) -> dict:
    branch = git(place.repo, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip()
    ahead = git(place.repo, 'rev-list', '--count', '@{u}..HEAD')
    brands = git(place.repo, 'rev-list', '--count', '@{u}..HEAD', '--', 'brands')
    count = lambda done: int(done.stdout.strip() or 0) if done.returncode == 0 else None
    return {'branch': branch, 'address': place.address, 'commits': count(ahead),
            'brands': count(brands)}


def push(place: Storage) -> dict:
    """Send the checkout's branch to the team repository: only on the person's yes, never
    forced. A refusal leaves every commit on this computer."""
    if not place.team:
        raise WorkspaceError('Local Git storage has nowhere to push to: the commit is the save.')
    branch = git(place.repo, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip()
    if not branch:
        raise WorkspaceError(f'The copy at {place.repo} is not on a branch.')
    done = git(place.repo, 'push', '--quiet', 'origin', f'refs/heads/{branch}:refs/heads/{branch}',
               seconds=120)
    if done.returncode != 0:
        raise WorkspaceError(
            f'{place.address} did not take the push ({reason(done)}). The brand stays committed on '
            'this computer. If the team repository has changes this copy lacks, open the studio '
            'that uses this copy so it brings them in, then push again from Brands.')
    return {'pushed': True, 'branch': branch, 'address': place.address}


def decode(content) -> bytes:
    try:
        if not isinstance(content, str) or not content:
            raise ValueError
        return base64.b64decode(content, validate=True)
    except ValueError:
        raise WorkspaceError('The file did not arrive whole. Choose it again.') from None
