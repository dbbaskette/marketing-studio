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

- Storage is exactly `brand.brands`, resolved through studio_core.brand_data.place.
  A remote copy must already exist after explicit Get brands. Local Git is initialized
  only by Save. Team storage and studio workspace settings never choose a brands folder.
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
import tempfile
import stat
import subprocess
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from studio_core import brand_data
from studio_core.process_lock import ProcessRLock

from . import brand_skill, state
from .errors import WorkspaceError

SCHEMA = 1
LIBRARIES = 'icon-libraries'
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
    team: bool              # a configured remote brands repository
    repo: Path | None       # the repository the folder is committed in; None until made
    address: str | None     # the configured remote brands repository

    @property
    def where(self) -> str:
        return (f'{self.address}, through the copy at {self.repo}' if self.team
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
    address = (shared.get('brand') or {}).get('brands')
    if not isinstance(address, str) or not address.strip():
        raise WorkspaceError('Choose the brands repository in Shared settings, Brand, then save settings.')
    address = address.strip()
    try:
        folder = brand_data.place(address).resolve()
    except ValueError as failure:
        raise WorkspaceError(str(failure)) from failure
    remote = not brand_data._local(address)
    if remote and not (folder / '.git').exists():
        raise WorkspaceError('The brands repository has no copy here yet. Use Get brands in Shared settings, Brand first.')
    repo = folder if (folder / '.git').exists() else None
    if repo is not None:
        top = git(repo, 'rev-parse', '--show-toplevel')
        if top.returncode or Path(top.stdout.strip()).resolve() != folder:
            raise WorkspaceError('Choose the root of the brands repository, not a folder inside another repository.')
        if remote:
            origin = git(repo, 'remote', 'get-url', 'origin')
            if origin.returncode or origin.stdout.strip() != address:
                raise WorkspaceError('This copy belongs to a different brands repository. Review Shared settings, Brand.')
    elif folder.exists():
        parent = git(folder, 'rev-parse', '--show-toplevel')
        if parent.returncode == 0:
            raise WorkspaceError('Choose a separate brands repository, outside any existing repository.')
    return Storage(folder, remote, repo, address if remote else None)


def write_lock(place: Storage):
    """The stable repository lock also held by Get brands."""
    return ProcessRLock(lambda: brand_data.lock_path(place.folder),
                        refusal=WorkspaceError)


# --- small file helpers ----------------------------------------------------------------

TREE_LIMIT = 250_000_000
FILE_LIMIT = 10_000


def no_links(path: Path) -> Path:
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise WorkspaceError('Brand files cannot use symbolic links. Copy the actual file into the brands folder.')
    return path


def tree_files(folder: Path):
    """Validate every copied path, including hidden entries, before following or writing it."""
    folder = no_links(folder)
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise WorkspaceError('A brand or library must be a folder.')
    files, total = [], 0
    for base, dirs, names in os.walk(folder, followlinks=False):
        for name in (*dirs, *names):
            path = no_links(Path(base) / name)
            mode = path.lstat().st_mode
            if name == '.git' or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise WorkspaceError('Brand folders cannot contain Git metadata or special files.')
            if stat.S_ISREG(mode):
                size = path.stat().st_size
                total += size
                files.append(path)
                if size > SOURCE_LIMIT or total > TREE_LIMIT or len(files) > FILE_LIMIT:
                    raise WorkspaceError('This brand exceeds the file or working-copy size limit.')
    return sorted(files)


def read_json(path: Path, default=None):
    try:
        path = no_links(path)
        if path.stat().st_size > 4_000_000:
            raise WorkspaceError('Brand metadata is too large to read.')
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(path: Path, value) -> None:
    put(path, (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def put(path: Path, data: bytes) -> None:
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def fingerprint(folder: Path) -> str:
    folder = no_links(folder)
    if not folder.exists():
        return 'none'
    digest = hashlib.sha256()
    for path in tree_files(folder):
        if path.name == '.DS_Store':
            continue
        digest.update(path.relative_to(folder).as_posix().encode('utf-8') + b'\0')
        with path.open('rb') as stream:
            file_hash = hashlib.file_digest(stream, 'sha256')
        digest.update(file_hash.digest())
    return digest.hexdigest()


def files_in(folder: Path) -> list[dict]:
    folder = Path(folder)
    return [{'name': path.relative_to(folder).as_posix(), 'size': path.stat().st_size}
            for path in tree_files(folder)
            if not any(part.startswith('.') for part in path.relative_to(folder).parts)]


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
        no_links(archive)
        with zipfile.ZipFile(archive) as opened:
            if any(opened.getinfo(name).file_size > 4_000_000 for name in ('library.json', 'icons.json')):
                raise WorkspaceError('Icon library metadata is too large to read.')
            library = json.loads(opened.read('library.json'))
            icons = json.loads(opened.read('icons.json')).get('icons') or []
        return {'name': str(library.get('name') or archive.parent.name),
                'kind': library.get('kind'), 'count': len(icons)}
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, AttributeError):
        return {'name': archive.parent.name, 'kind': None, 'count': None}


# --- the listing -----------------------------------------------------------------------

def unshared(place: Storage, path: str) -> int:
    """Commits on this checkout touching `path` not present on the configured remote branch."""
    if not place.team or place.repo is None:
        return 0
    done = git(place.repo, 'rev-list', '--count', '@{u}..HEAD', '--', path)
    return int(done.stdout.strip() or 0) if done.returncode == 0 else 0


def listing(found, place: Storage) -> dict:
    folder = place.folder
    packs, libraries = [], []
    if folder.is_dir():
        for entry in sorted(folder.iterdir()):
            no_links(entry)
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
                'check': {'ok': None, 'problems': []}, 'unshared': unshared(place, f'{entry.name}')})
        shelf = folder / LIBRARIES
        for entry in sorted(shelf.iterdir()) if shelf.is_dir() else ():
            if entry.name.startswith('.') or not (entry / 'library.zip').is_file():
                continue
            libraries.append({'id': entry.name, **library_summary(entry / 'library.zip'),
                              'usedBy': [pack['name'] for pack in packs if entry.name in pack['libraries']],
                              'check': {'ok': None, 'problems': []},
                              'unshared': unshared(place, f'{LIBRARIES}/{entry.name}')})
    return {'packs': packs, 'libraries': libraries, 'work': working_copies(),
            'where': place.where, 'team': place.team, 'push': outgoing_commits(place) if place.team else None, 'skill': {'name': found.name, 'version': found.version}}


# --- working copies --------------------------------------------------------------------

def root() -> Path:
    return state.data_root() / 'brand-work'


def key_of(kind, ident) -> str:
    return f'{kind}-{ident}'


def folder_of(key: str) -> Path:
    if not isinstance(key, str) or not re.fullmatch(r'(brand|library)-[a-z0-9][a-z0-9-]{0,62}', key):
        raise WorkspaceError('Choose a brand or icon library from this page.')
    return no_links(root() / key)


def inside(work: dict) -> Path:
    """The brand's or library's folder inside the working copy, as it will be in storage."""
    base = folder_of(work['key']) / 'brands'
    return base / work['id'] if work['kind'] == 'brand' else base / LIBRARIES / work['id']


def target(place: Storage, work: dict) -> Path:
    return no_links(place.folder / work['id'] if work['kind'] == 'brand' else place.folder / LIBRARIES / work['id'])


def record(key: str) -> dict:
    with LOCK:
        work = read_json(folder_of(key) / 'work.json')
        if not isinstance(work, dict) or work.get('schema') != SCHEMA:
            raise WorkspaceError('That working copy is not there any more. Start it again from Brands.')
        if work.get('key') != key or work.get('kind') not in KINDS or not isinstance(work.get('id'), str) or not SLUG.fullmatch(work['id']) or key_of(work['kind'], work['id']) != key:
            raise WorkspaceError('That working copy has an invalid identity. Start it again from Brands.')
        tree_files(folder_of(key))
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
                    tree_files(library)
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
                code, said = brand_skill.answer(found, list(args), env=brand_skill.environment(folder_of(key) / 'brands'), stop=stop, seconds=900)
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
    found = no_links(here / path).resolve()
    if here.resolve() not in found.parents or not found.is_file():
        raise WorkspaceError('That picture is not in this working copy.')
    if found.stat().st_size > 10_000_000:
        raise WorkspaceError('This preview is too large to show.')
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
        result = checked(found, folder, env=brand_skill.environment(folder_of(key) / 'brands'))
        work['checked'] = result
        keep(work)
        if not result['ok']:
            refused = WorkspaceError('pack check does not pass yet, so nothing was saved: '
                                     + ' '.join(result['problems'][:3]))
            refused.details = {'problems': result['problems']}
            raise refused
        if work['kind'] == 'brand':
            code, sealed = brand_skill.answer(found, ['pack', 'seal', str(folder), '--json'], env=brand_skill.environment(folder_of(key) / 'brands'))
            if code != 0:
                raise WorkspaceError('pack seal did not seal the pack: ' + brand_skill.said(json.dumps(sealed), code))
            again = checked(found, folder, env=brand_skill.environment(folder_of(key) / 'brands'))
            if not again['ok']:
                raise WorkspaceError('The sealed pack does not pass pack check: ' + ' '.join(again['problems'][:3]))
    # The entire Save owns the repository lock; task files remain available after a failure.
        verified = fingerprint(here)
    repo = place.folder
    with write_lock(Storage(place.folder, place.team, repo, place.address)), LOCK:
        work = record(key)
        idle(key)
        if fingerprint(here) != verified:
            raise WorkspaceError('The working copy changed during validation. Review it and save again.')
        stored = target(place, work)
        if fingerprint(stored) != work['base']:
            raise WorkspaceError('The brand in storage changed after this working copy was made. Discard it and start an update from the newer version.')
        if place.repo is None:
            place.folder.mkdir(parents=True, exist_ok=True)
            parent = git(repo, 'rev-parse', '--show-toplevel')
            if parent.returncode == 0:
                raise WorkspaceError('The brands folder is now inside another repository. Review Shared settings, Brand.')
            made = git(repo, 'init', '--quiet', '-b', 'main')
            if made.returncode:
                raise WorkspaceError(f'Could not initialize the brands repository ({reason(made)}).')
            place = Storage(repo, False, repo, None)
        identity(repo)
        scope = [stored.relative_to(repo).as_posix()]
        dirty = git(repo, 'status', '--porcelain', '--untracked-files=all', '--', *scope)
        if dirty.returncode or dirty.stdout.strip():
            raise WorkspaceError('This brand has uncommitted files in the repository. Commit or set them aside before saving this working copy.')
        attributes = no_links(repo / '.gitattributes')
        new_attributes = not attributes.exists()
        if new_attributes:
            scope.append('.gitattributes')
        staged = Path(tempfile.mkdtemp(prefix='.brand-save-', dir=repo))
        incoming, backup = staged / 'incoming', staged / 'before'
        index = staged / 'index'
        index_env = {'GIT_INDEX_FILE': str(index)}
        moved = False
        committed = False
        head = git(repo, 'rev-parse', '--verify', 'HEAD')
        try:
            shutil.copytree(here, incoming, ignore=shutil.ignore_patterns('.*'))
            stored.parent.mkdir(parents=True, exist_ok=True)
            if stored.exists():
                os.replace(stored, backup)
            moved = True
            os.replace(incoming, stored)
            if new_attributes:
                put(attributes, GITATTRIBUTES.encode())
            ready = git(repo, 'read-tree', head.stdout.strip() if head.returncode == 0 else '--empty', env=index_env)
            if ready.returncode:
                raise WorkspaceError(f'Could not prepare the brand commit ({reason(ready)}).')
            added = git(repo, 'add', '-A', '--', *scope, env=index_env)
            if added.returncode:
                raise WorkspaceError(f'Could not prepare the brand commit ({reason(added)}).')
            what = 'brand pack' if work['kind'] == 'brand' else 'icon library'
            message = f"{'Update' if work['update'] else 'Add'} the {work['name']} {what}"
            changed = git(repo, 'diff', '--cached', '--quiet', env=index_env)
            if changed.returncode not in (0, 1):
                raise WorkspaceError('Git could not compare the prepared brand commit.')
            if changed.returncode == 1:
                done = git(repo, '-c', 'core.hooksPath=/dev/null', 'commit', '--quiet', '-m', message, env=index_env)
                if done.returncode:
                    raise WorkspaceError(f'Git did not record the brand ({reason(done)}). Nothing was saved; retry this working copy.')
                committed = True
                # Selected paths were clean before Save; refresh only those index entries.
                refreshed = git(repo, 'reset', '--quiet', 'HEAD', '--', *scope)
                if refreshed.returncode:
                    raise WorkspaceError('The brand was committed, but Git could not refresh its index. Review the repository before continuing.')
            shutil.rmtree(folder_of(key))
        except BaseException:
            if not committed and moved:
                shutil.rmtree(stored, ignore_errors=True)
                if backup.exists():
                    os.replace(backup, stored)
                if new_attributes:
                    attributes.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(staged, ignore_errors=True)
    answer = {'saved': work['id'], 'kind': work['kind'], 'name': work['name'],
              'committed': committed, 'message': message, 'where': place.where}
    if place.team:
        answer['push'] = outgoing_commits(place)
    return answer


def outgoing_commits(place: Storage) -> dict:
    """Read-only disclosure, bound to the exact head and configured destination."""
    branch = git(place.repo, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip()
    head = git(place.repo, 'rev-parse', '--verify', 'HEAD').stdout.strip()
    base = git(place.repo, 'rev-parse', '--verify', f'refs/remotes/origin/{branch}')
    preview = {'branch': branch, 'address': place.address, 'head': head, 'commits': 0,
               'brands': 0, 'items': [], 'blocked': None}
    if not branch or base.returncode:
        preview['blocked'] = 'The saved branch has no matching origin branch. Review its upstream with Git first.'
    else:
        commits = git(place.repo, 'rev-list', f'{base.stdout.strip()}..{head}')
        if commits.returncode:
            preview['blocked'] = 'Git could not read the outgoing commits.'
        else:
            ids = commits.stdout.splitlines()
            preview['commits'] = len(ids)
            items = set()
            for commit in ids:
                changed = git(place.repo, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', commit)
                paths = changed.stdout.splitlines()
                owned = set()
                for path in paths:
                    bits = path.split('/')
                    if path == '.gitattributes':
                        continue
                    if bits[0] == LIBRARIES and len(bits) >= 3 and SLUG.fullmatch(bits[1]):
                        owned.add('/'.join(bits[:2]))
                    elif len(bits) >= 2 and SLUG.fullmatch(bits[0]) and bits[0] != LIBRARIES:
                        owned.add(bits[0])
                    else:
                        preview['blocked'] = 'An outgoing commit includes files outside a brand or icon library. Review and push it with Git.'
                if changed.returncode or len(owned) != 1:
                    preview['blocked'] = 'Each outgoing commit must contain exactly one brand or icon library. Review and push it with Git.'
                items.update(owned)
            preview['brands'] = len(ids)
            preview['items'] = sorted(items)
    preview['expected'] = hashlib.sha256(canonical({**preview, 'base': base.stdout.strip()}).encode()).hexdigest()
    return preview


def push(place: Storage, expected=None) -> dict:
    if not place.team:
        raise WorkspaceError('This local brands repository has no configured remote push. The commit is the save.')
    with write_lock(place):
        preview = outgoing_commits(place)
        if not isinstance(expected, str) or expected != preview['expected']:
            raise WorkspaceError('The push preview changed. Review the saved commits and say yes again.')
        if preview['blocked']:
            raise WorkspaceError(preview['blocked'])
        if not preview['commits']:
            raise WorkspaceError('There are no saved commits to push.')
        # An exact SHA and the configured address cannot follow a changed branch or pushurl.
        done = git(place.repo, 'push', '--quiet', place.address,
                   f"{preview['head']}:refs/heads/{preview['branch']}", seconds=120)
        if done.returncode:
            raise WorkspaceError(f'The brands repository did not take the push ({reason(done)}). The brand stays committed on this computer. Review and update the repository before retrying.')
        # Keep the local tracking reference in step with the exact head just sent.
        git(place.repo, 'update-ref', f"refs/remotes/origin/{preview['branch']}", preview['head'])
        return {'pushed': True, 'branch': preview['branch'], 'address': place.address}


def decode(content) -> bytes:
    try:
        if not isinstance(content, str) or not content:
            raise ValueError
        return base64.b64decode(content, validate=True)
    except ValueError:
        raise WorkspaceError('The file did not arrive whole. Choose it again.') from None
