"""The parts of the runner's `upkeep` both deck studios share. A studio binds them
into its own module with `studio_core.modules.bind`; they read that module's names.

INSTALLER (built from the studio's own file), TOOLS (the studio's companion modules), the
messages that name the product or its items, and every definition that differs stay in
each studio.
"""
from __future__ import annotations

import re


SAVED = 'updates.json'    # in the data folder: the releases last found online, and when
DAY = 24 * 3600           # seconds between looks online
LOOK_SECONDS = 15         # for one repository to answer
UPDATE_SECONDS = 2400     # for the companions to be fetched, checked and installed
TAG = re.compile(r'^([0-9a-f]{40})\trefs/tags/(v?(\d+\.\d+\.\d+))(\^\{\})?$')
UPDATING = 'The companion skills are being updated already.'
NO_RESTART = 'There is no upgrade waiting for a restart.'
BRAND = 'brand skill'     # the brand skill's row, and its entry in what was found online
BRAND_SECONDS = 900       # for the brand skill's own installer to finish
BRAND_INSTALLING = 'The brand skill is being installed already.'


def _floor(pin: dict) -> str:
    """The oldest installed copy a pin accepts: its >= requirement, or the lock itself."""
    try:
        return minimum_version(pin)
    except (ValueError, TypeError):
        return pin['version']


def _now() -> str:
    return home.now()


def _age(stamp: str | None) -> float | None:
    """Seconds since a time this module wrote, or None when it cannot be read."""
    try:
        then = datetime.strptime(str(stamp), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - then).total_seconds()


def _version(text: str) -> tuple:
    try:
        return tuple(int(part) for part in text.split('.'))
    except (AttributeError, ValueError):
        return ()


def newest(listed: str) -> dict | None:
    """The newest release among the tags `git ls-remote --tags` printed, as {'version',
    'tag', 'commit'}, or None. An annotated tag's commit is the one it points at."""
    found = {}
    for line in listed.splitlines():
        match = TAG.match(line.strip())
        if match:
            commit, name, version, peeled = match.groups()
            entry = found.setdefault(name, {'version': version, 'tag': name, 'commit': commit})
            if peeled:
                entry['commit'] = commit
    return max(found.values(), key=lambda entry: _version(entry['version'])) if found \
        else None


def fetch_tree(repository: str, ref: str, into: Path) -> tuple[Path, str]:
    """One revision of a repository, fetched by the name of its ref with the guidance's own
    isolated git, written into `into` as plain files: (the folder, its commit). Links and
    anything else that is not a plain file are left out."""
    if str(repository).startswith('-') or not re.fullmatch(r'refs/(heads|tags)/[\w.\-/]+',
                                                          ref) or '..' in ref:
        raise sync_guidance.SyncError('That is not a revision this version can fetch.')
    bare, tree = into / 'fetched.git', into / 'tree'
    sync_guidance.git('init', '--quiet', '--bare', '--template=', str(bare))
    (bare / 'config').write_bytes(sync_guidance.CACHE_CONFIG)
    sync_guidance.git('fetch', '--quiet', '--no-tags', '--depth', '1', str(repository),
                      f'+{ref}:refs/fetched', repo=bare)
    commit = sync_guidance.git('rev-parse', '--verify', 'refs/fetched^{commit}',
                               repo=bare).decode().strip()
    files = {}
    for line in filter(None, sync_guidance.git('ls-tree', '-r', '-z', '--full-tree', commit,
                                               repo=bare).split(b'\0')):
        meta, _, name = line.partition(b'\t')
        mode, kind, ident = meta.split()
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            continue
        inside = PurePosixPath(name.decode('utf-8', 'replace'))
        if inside.is_absolute() or any(part in ('', '.', '..') for part in inside.parts):
            raise sync_guidance.SyncError('What was fetched has a file that cannot be placed.')
        files[inside.as_posix()] = (ident.decode(), mode == b'100755')
    content = sync_guidance.blobs(sorted({ident for ident, _ in files.values()}), bare)
    for name, (ident, runs) in files.items():
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content[ident])
        if runs:
            target.chmod(0o755)
    shutil.rmtree(bare, ignore_errors=True)
    return tree, commit


def install_root(runner_dir: Path | None = None) -> Path:
    """Where the installer keeps its record: the folder of `versions/` the runner was
    installed in, or else the data folder, where a linked checkout's record is."""
    here = (runner_dir or Path(__file__).resolve().parent).parent
    if here.parent.name == 'versions':
        return here.parent.parent
    return home.data_root()


def _who(names: list[str]) -> str:
    return ' and '.join(names)


def _load(path: Path):
    """The installer at `path`, as a module, or None when it is not there or cannot load."""
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location(SELF.replace('-', '_') + '_installer', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:  # an installer that cannot be loaded is said, not raised
        return None
    return module


class Upkeep:
    """The shared methods of the studio's Upkeep."""

    def __init__(self, home_dir: Path | None = None, root: Path | None = None,
                 installer: Path | None = None, after=None):
        self.home = Path(home_dir or Path.home())
        self.root = Path(root or install_root())
        self.installer = Path(installer or INSTALLER)
        self.after = after
        self._module = None
        self._lock = threading.Lock()
        self._found: dict | None = None      # the last look on this computer
        self._update: dict | None = None     # the update in hand, or the last one
        self._upgrade: dict | None = None    # the upgrade in hand, or the one installed
        self._brand: dict | None = None      # the brand skill's install in hand, or the last
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self.restarting: list[str] | None = None   # what `studio serve` runs once it stops
        self.leave = None                    # stops the runner; `studio serve` sets it

    @property
    def folder(self) -> Path:
        """The copy this runner and its installer belong to: a version folder, or a checkout."""
        return self.installer.resolve().parent.parent

    def checkout(self) -> bool:
        """Whether this runner runs from a copy of the repository, upgraded with git pull."""
        return self.folder.parent.name != 'versions'

    def version(self) -> str:
        """The version of the copy this runner belongs to."""
        for path in (self.folder / 'VERSION', self.folder / 'skills' / SELF / 'VERSION'):
            try:
                found = path.read_text(encoding='utf-8').strip()
            except OSError:
                continue
            if _version(found):
                return found
        return sync_guidance.runtime_version()

    def start(self) -> None:
        """Look on this computer, putting back what is safe, then online when that is due.
        All of it in the background: the page answers meanwhile."""
        self._background(self._first, 'looking at the skills')

    def again(self) -> None:
        """The page's "Check again": the part on this computer now, online in the
        background when that is due."""
        self.check(repair=True)
        self._background(self.look, 'looking for releases')

    def _first(self) -> None:
        self.check(repair=True)
        self.look()

    def _background(self, work, name: str) -> None:
        thread = threading.Thread(target=work, daemon=True, name=name)
        self._threads.append(thread)
        thread.start()

    def close(self) -> None:
        """End an update in hand. What was looked at is kept."""
        self._stop.set()
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(timeout=10)

    def module(self):
        if self._module is None:
            self._module = _load(self.installer)
        return self._module

    def check(self, repair: bool = True) -> dict:
        """Look at the links, the commands and the companions on this computer, putting back
        what is safe when `repair`. Never raises: what went wrong is said in the report."""
        try:
            found = self._local(repair)
        except Exception as failure:  # the runner keeps serving, and says so
            found = self._blank(f'Looking at the skills on this computer did not work '
                                f'({type(failure).__name__}: {failure}).')
        with self._lock:
            self._found = found
        return found

    def _blank(self, problem: str | None) -> dict:
        return {'at': _now(), 'installer': False, 'mode': None, 'links': [], 'repaired': [],
                'companions': [], 'problem': problem, 'main': None, 'newest': None,
                'tools': {}, 'brands': []}

    def _brands(self) -> list[dict]:
        """Each brand skill in this home, installed from here or by hand: {'name',
        'version', 'runtime'}. Asked on this computer only."""
        try:
            return [{key: entry.get(key) for key in ('name', 'version', 'runtime')}
                    for entry in brand_skill.found(home=self.home)]
        except (WorkspaceError, OSError):
            return []

    def _tools(self) -> dict:
        """What each companion's own tool says of itself, where one is found in this home:
        {name: a sentence}. Asked on this computer only."""
        said = {}
        for name, (module, title) in TOOLS.items():
            places = companion.locations(module.VARIABLE, name, title, home=self.home)
            if not any((place / module.SCRIPT).is_file() for place in places):
                continue
            try:
                runtime = companion.find_runtime(places, module.SCRIPT, module.VARIABLE, name,
                                                 'it cannot be asked')
                if module is slides_tool:
                    tool = slides_tool.Slides(runtime)
                    listed = tool.capabilities()
                    said[name] = f'The tool in use says it is {tool.version()}' + (
                        f", and that it can do: {', '.join(sorted(listed))}." if listed
                        else '.')
                else:
                    said[name] = (f'The tool in use says it is '
                                  f'{research_tool.Research(runtime).version()}.')
            except (WorkspaceError, OSError) as refusal:
                said[name] = str(refusal)
        return said

    def _current(self, install, state: dict) -> list[str]:
        """Put back the link to the installed version when it is missing or points nowhere."""
        current = self.root / 'current'
        kept = state.get('current')
        staged = self.root / 'versions' / str(kept)
        if state.get('mode') != 'managed' or not kept or current.exists() \
                or not staged.is_dir():
            return []
        install.replace_link(current, staged)
        return [f'The link to the installed version was missing, and was put back: {current}.']

    def _commands(self, install, state: dict) -> list[str]:
        """Write again the commands the installer wrote, where one is missing. A file of
        someone's own in their place is left alone by the installer itself."""
        kept = state.get('launchers', {})
        missing = tuple(kind for kind in COMMANDS if kind in kept
                        and not os.path.lexists(kept[kind]))
        studio = Path(str(state.get('runner', '')))
        scripts = (Path(str(state.get('source', ''))) if state.get('mode') == 'link'
                   else self.root / 'current') / 'scripts'
        if not missing or not studio.is_file() or not scripts.is_dir():
            return []
        written = install.write_launchers(self.home, self.root, studio, scripts, missing)
        return [f'{COMMANDS[kind]} was missing, and was written again: {path}.'
                for kind, path in written.items()]

    @classmethod
    def _main_version(cls) -> str | None:
        main = cls._main()
        return main and main['version']

    @staticmethod
    def saved_path() -> Path:
        return home.data_root() / SAVED

    @classmethod
    def _saved(cls) -> dict:
        """What was last found online, as `look` keeps it; empty when nothing was."""
        kept = home.read_json(cls.saved_path(), None)
        return kept if isinstance(kept, dict) and isinstance(kept.get('found', {}), dict) \
            else {}

    def due(self) -> bool:
        """Whether looking online is on, and a day has passed since it last looked."""
        if not settings.load().look_for_updates:
            return False
        kept = home.read_json(self.saved_path(), None)
        age = _age(kept.get('at')) if isinstance(kept, dict) else None
        return age is None or age >= DAY or age < 0

    @staticmethod
    def _brand_entry(listed: dict) -> dict:
        """What is kept of the brand skill's releases: the newest, and every release with
        its commit, so that one chosen in Settings can be shown."""
        latest = brand_source.newest(listed) or {}
        return {'latest': latest.get('version'), 'tag': latest.get('tag'),
                'commit': latest.get('commit'),
                'releases': {tag: entry['commit'] for tag, entry in listed.items()}}

    def remember_brand(self, repository: str, listed: dict) -> None:
        """Keep the brand skill's releases, as Settings' check of its repository found them,
        so its row is shown at once. When the next look is due does not change."""
        kept = self._saved()
        found = dict(kept.get('found') or {})
        found[BRAND] = {'repository': repository, 'problem': None, 'known_at': _now(),
                        **self._brand_entry(listed)}
        home.data_root().mkdir(parents=True, exist_ok=True)
        home.write_json(self.saved_path(), {'schema': 1, **kept, 'found': found})

    def look(self) -> bool:
        """Ask each repository which releases it has, when that is due. Only the tags are
        read: nothing is downloaded or run. True when it looked."""
        if not self.due():
            return False
        place = home.data_root()
        place.mkdir(parents=True, exist_ok=True)
        found, before = {}, self._saved().get('found') or {}
        for name, repository in self.repositories().items():
            # What was known last is kept when it cannot be asked now, with when it was.
            known = before.get(name) if isinstance(before.get(name), dict) \
                and before[name].get('repository') == repository else {}
            entry = {'repository': repository, 'problem': None,
                     **{key: known.get(key) for key in ('latest', 'tag', 'commit', 'known_at',
                                                        *(('releases',) if name == BRAND
                                                          else ()))}}
            try:
                done = hub.run(place, 'ls-remote', '--tags', '--', repository,
                               timeout=LOOK_SECONDS)
            except WorkspaceError as refusal:
                entry['problem'] = str(refusal).rstrip('.')
            else:
                if done.returncode == 0 and name == BRAND:
                    entry.update(**self._brand_entry(brand_source.listed(done.stdout)),
                                 known_at=_now())
                elif done.returncode == 0:
                    latest = newest(done.stdout) or {}
                    entry.update(latest=latest.get('version'), tag=latest.get('tag'),
                                 commit=latest.get('commit'), known_at=_now())
                else:
                    entry['problem'] = hub.reason(done)
            found[name] = entry
        home.write_json(self.saved_path(), {'schema': 1, 'at': _now(), 'found': found,
                                            'dismissed': self._saved().get('dismissed')})
        fresh = self._newest(self.module())
        with self._lock:
            if self._found is not None:
                self._found = {**self._found, 'newest': fresh}
        return True

    def _bring(self, names: list[str]) -> None:
        command = [sys.executable, '-B', str(self.installer), 'companions', '--companions',
                   'install', '--while-open', '--json', '--home', str(self.home), '--root',
                   str(self.root)]
        printed: list[bytes] = []
        state, says = 'failed', None
        try:
            with tempfile.TemporaryFile() as errors:
                code, late = companion.supervise(command, None, None, '', UPDATE_SECONDS,
                                                 errors, printed.append, self._stop)
                errors.seek(0)
                complaint = errors.read().decode('utf-8', 'replace').strip()
            if self._stop.is_set():
                says = STOPPED
            elif late:
                says = (f'The update did not finish in {UPDATE_SECONDS // 60} minutes, so it '
                        'was ended. Try again, or run the installer.')
            else:
                state, says = self._said(code, b''.join(printed), complaint)
        except Exception as failure:  # said on the page; the runner keeps serving
            says = f'The update could not be run ({type(failure).__name__}: {failure}).'
        with self._lock:
            self._update = {**(self._update or {}), 'state': state, 'says': says,
                            'ended': _now()}
        self.check(repair=False)
        if self.after is not None:
            try:
                self.after()
            except Exception:  # a look that fails is the next look's to say
                pass

    @staticmethod
    def _said(code: int, printed: bytes, complaint: str) -> tuple[str, str]:
        """What the installer said it did, in sentences: ('done' or 'failed', says)."""
        try:
            result = json.loads(printed.decode('utf-8', 'replace'))
        except ValueError:
            result = None
        if not isinstance(result, dict):
            line = (complaint.splitlines() or ['it said nothing'])[-1][:300]
            return 'failed', f'The installer did not answer as expected: {line}'
        if 'error' in result or code != 0:
            return 'failed', f"Nothing was updated: {result.get('error', 'the installer failed')}"
        lines, whole = [], True
        for name, outcome in (result.get('companions') or {}).items():
            if outcome.get('state') == 'installed':
                lines.append(f"{name} {outcome.get('wanted')} was installed by its own "
                             'installer.')
            elif outcome.get('state') in ('failed', 'refused'):
                whole = False
                lines.append(f"{name} {outcome.get('wanted')} was not installed: "
                             f"{outcome.get('detail')}")
        return ('done' if whole else 'failed'), ' '.join(lines) or 'Nothing needed bringing.'

    @staticmethod
    def _the_brand(brands: list[dict]) -> dict | None:
        """The brand skill decks use: the one chosen in Settings, else the first found."""
        named = settings.load().brand_skill
        return next((entry for entry in brands if entry.get('runtime') == named),
                    brands[0] if brands else None)

    def _brand_installed(self, repository: str, target: dict,
                         before: dict | None) -> tuple[str, str]:
        """Whether the release is now the brand skill found here. A brand skill chosen in
        Settings that was the one upgraded is moved to the new version."""
        tag, version = target['tag'], target['version']
        now = [entry for entry in self._brands() if entry.get('version') == version]
        if not now:
            return 'failed', (f'Its installer finished, but no brand skill {version} is found '
                              'on this computer. Check this computer again, or run its '
                              'installer by hand.')
        chosen = settings.load()
        if before and chosen.brand_skill and chosen.brand_skill == before.get('runtime') \
                and now[0]['runtime'] != before.get('runtime'):
            settings.save(dataclasses.replace(chosen, brand_skill=now[0]['runtime']))
        return 'done', (f"{now[0]['name']} {version} is installed, from {repository} at "
                        f"{tag} (revision {target['commit'][:12]}). New decks can use it.")

    @staticmethod
    def _moved(before: dict, after: dict) -> list[str]:
        """What changed between two looks at the companions, one line each."""
        lines = []
        for place, (name, was, version) in before.items():
            _, now, then = after.get(place, (name, None, None))
            if (was, version) != (now, then):
                lines.append(f"{name} at {place}, from {version or 'nothing'} to "
                             f"{then or 'nothing'}" if version != then else
                             f'{name} at {place}, which now leads to {now or "nothing"}')
        return lines

    def dismiss(self, key: str) -> dict:
        """Stop showing the versions on Home until a newer one is out than `key` names."""
        if not isinstance(key, str) or not key or len(key) > 500:
            raise WorkspaceError('Name what is dismissed as the key the page was given.')
        kept = self._saved()
        home.write_json(self.saved_path(), {'schema': 1, **kept, 'dismissed': key})
        return self.report()

    def releases(self) -> dict:
        """Whether looking online is on, when it last looked, and what it did not reach."""
        kept = self._saved()
        online = kept.get('found') or {}
        missed = [name for name, entry in online.items()
                  if isinstance(entry, dict) and entry.get('problem')]
        problem = None
        if missed:
            first = online[missed[0]]['problem']
            named = ["the brand skill's repository" if name == BRAND else name
                     for name in missed]
            problem = (f'The last look for newer releases did not reach {_who(named)} '
                       f'({first}). It is tried again in a day.')
        return {'on': settings.load().look_for_updates, 'at': kept.get('at'),
                'problem': problem}

    @staticmethod
    def _target(state: dict | None) -> str | None:
        """The assistants the studio was installed for, as the installer names them."""
        chosen = sorted((state or {}).get('links', {}))
        return 'both' if len(chosen) > 1 else chosen[0] if chosen else None

    def _link(self, install, state: dict | None, harness: str, repair: bool) -> dict:
        """The studio's link for one assistant: as it is, or put back."""
        name = install.HARNESS[harness]
        entry = (state or {}).get('links', {}).get(harness)
        shown = {'assistant': name, 'name': install.NAME}
        if entry is None:   # not installed for it, as with a checkout that was never linked
            link = install.skill_link(self.home, harness)
            here = (link / 'SKILL.md').is_file()
            return {**shown, 'path': str(link), 'state': 'ok' if here else 'missing',
                    'says': None if here else f'{PRODUCT} is not installed for {name}. '
                    'Run the installer to install it.'}
        link, target = Path(entry['path']), str(entry['target'])
        shown['path'] = str(link)
        if link.is_symlink() and os.readlink(link) == target:
            if (link / 'SKILL.md').is_file():
                return {**shown, 'state': 'ok', 'says': None}
            return {**shown, 'state': 'missing', 'says': f'The link for {name} points at '
                    f'{target}, which is not there any more. Run the installer again.'}
        if link.exists() or link.is_symlink():
            return {**shown, 'state': 'left alone', 'says': f'{link} is not the link the '
                    'installer placed, so it was left alone. Run the installer again to '
                    f'link {PRODUCT} there.'}
        if not link.parent.is_dir():
            return {**shown, 'state': 'left alone', 'says': f"{name}'s skill folder, "
                    f'{link.parent}, is gone, so {PRODUCT} was not linked into it again.'}
        if not (Path(target) / 'SKILL.md').is_file():
            return {**shown, 'state': 'missing', 'says': f'The link for {name} is missing, and '
                    f'the copy it pointed at, {target}, is not there either. Run the installer '
                    'again.'}
        if not repair:
            return {**shown, 'state': 'missing', 'says': f'The link for {name} is missing. It '
                    f'is put back when {PRODUCT} starts.'}
        install.replace_link(link, Path(target))
        return {**shown, 'state': 'repaired', 'says': f'The link for {name} was missing, and '
                f'was put back: {link}.'}

    @staticmethod
    def _main() -> dict | None:
        """The studio's version on the source branch when guidance was last fetched,
        with its commit, read from the helper's guidance cache with its own isolated git.
        Nothing is fetched, and a cache the helper would not use is not read: it is the
        helper's to rebuild."""
        cache = sync_guidance.guidance_root() / 'cache.git'
        if not sync_guidance.ours(cache):
            return None
        try:
            commit = sync_guidance.git('rev-parse', '--verify',
                                       f'{sync_guidance.MAIN}^{{commit}}',
                                       repo=cache).decode().strip()
            # Not `manifest()`: that refuses guidance a newer version needs, which is just
            # what is looked for here.
            kept = json.loads(sync_guidance.git(
                'cat-file', 'blob', f"{commit}:{sync_guidance.source().get('manifest', 'guidance/manifest.json')}", repo=cache))
            root = str(kept['content_root']).strip('/')
            found = sync_guidance.git('cat-file', 'blob', f'{commit}:{root}/VERSION',
                                      repo=cache).decode().strip()
        except (sync_guidance.SyncError, ValueError, KeyError, TypeError, AttributeError,
                UnicodeDecodeError):
            return None
        return {'version': found, 'commit': commit} if _version(found) else None

    def _newest(self, install) -> dict | None:
        """The newest release of the studio known here, as {'version', 'ref', 'from', 'pins'}: its
        newest release tag once it has one, else the version on the source branch when
        guidance was last fetched. `pins` are the companion versions it is pinned to, or
        None when they cannot be read here."""
        online = (self._saved().get('found') or {}).get(SELF) or {}
        branch = str(sync_guidance.source().get('branch', 'main'))
        if online.get('latest'):
            found = {'version': online['latest'], 'from': 'tag',
                     'ref': f"refs/tags/{online.get('tag') or 'v' + online['latest']}",
                     'commit': online.get('commit')}
        elif (main := self._main()) is not None:
            found = {'version': main['version'], 'from': branch,
                     'ref': f'refs/heads/{branch}', 'commit': main['commit']}
        else:
            return None
        found['pins'] = self._pins_at(install, found.pop('commit'))
        return found

    def _refuse_busy(self) -> None:
        """Refuse a change while another is in hand, or while a newer release of the studio waits
        for a restart: that one brings the companions it was made with. Under the lock."""
        if self._update and self._update['state'] == 'running':
            raise WorkspaceError(UPDATING)
        if self._upgrade and self._upgrade['state'] == 'running':
            raise WorkspaceError(UPGRADING)
        if self._brand and self._brand['state'] == 'running':
            raise WorkspaceError(BRAND_INSTALLING)
        if self._upgrade and self._upgrade['state'] in ('restart', 'restarting'):
            raise WorkspaceError(f"{PRODUCT} {self._upgrade['version']} is installed "
                                 'and waits for a restart. Restart first: it brings the '
                                 'companion skills it was made with.')

    def suite_managed(self) -> bool:
        path = self.home / '.local/share/marketing-studio/installation.json'
        try:
            if SELF.removesuffix('-studio') in json.loads(path.read_text()).get('studios', []):
                return True
            raise ValueError('Not installed by this suite record')
        except (OSError, ValueError, TypeError):
            try:
                source = json.loads((self.folder / 'source.json').read_text())
                repository = os.environ.get(SOURCE_VARIABLE) or source.get('repository', '')
                return repository.removesuffix('.git') == 'https://github.com/dbbaskette/marketing-studio'
            except (OSError, ValueError, TypeError, AttributeError):
                return False

    def upgrade(self, working: bool, version: str) -> dict:
        """Install the newest release of the studio, `version`, beside this one, in the background.
        Refused, in a sentence, from a checkout, while an item is working, while anything
        else is in hand, and when the newest known is not `version` or not newer."""
        if self.suite_managed():
            raise WorkspaceError('Update this studio with the Marketing Studio installer.')
        with self._lock:
            found = self._found
            self._refuse_busy()
        if found is None:
            found = self.check(repair=False)
        if not found['installer']:
            raise WorkspaceError(NO_INSTALLER)
        if self.checkout() or found['mode'] != 'managed':
            raise WorkspaceError(FROM_CHECKOUT)
        newest, have = found.get('newest'), self.version()
        if not newest or _version(newest['version']) <= _version(have):
            raise WorkspaceError(NOTHING_NEWER)
        if newest['version'] != str(version):
            raise WorkspaceError(f"The newest {PRODUCT} is now {newest['version']}, not "
                                 f'{version}. Look at it again before you upgrade.')
        if working:
            raise WorkspaceError(UPGRADE_WORKING)
        with self._lock:
            self._refuse_busy()
            self._upgrade = {'state': 'running', 'since': _now(), 'version': newest['version'],
                             'says': f"Fetching {PRODUCT} {newest['version']}, checking "
                                     'it and installing it beside this one. This can take a '
                                     'few minutes.'}
        target = found.get('target')
        self._background(lambda: self._install(newest, target), f'upgrading {PRODUCT}')
        return self.report()

    def _run_installer(self, tree: Path, version: str, target: str | None) -> tuple[str, str]:
        """Run the fetched version's own installer, which checks it, lays it beside this one
        and moves `current`: ('restart' or 'failed', what is said)."""
        command = [sys.executable, '-B', str(tree / 'installer' / 'install.py'), 'install',
                   '--yes', '--json', '--companions', 'skip', '--while-open',
                   '--home', str(self.home), '--root', str(self.root),
                   *(['--target', target] if target else [])]
        printed: list[bytes] = []
        with tempfile.TemporaryFile() as errors:
            code, late = companion.supervise(command, None, None, '', UPGRADE_SECONDS, errors,
                                             printed.append, self._stop)
            errors.seek(0)
            complaint = errors.read().decode('utf-8', 'replace').strip()
        if self._stop.is_set():
            return 'failed', UPGRADE_STOPPED
        if late:
            return 'failed', (f'The upgrade did not finish in {UPGRADE_SECONDS // 60} minutes, '
                              'so it was ended. The version you have is still the one in use.')
        try:
            result = json.loads(b''.join(printed).decode('utf-8', 'replace'))
        except ValueError:
            result = None
        if not isinstance(result, dict):
            line = (complaint.splitlines() or ['it said nothing'])[-1][:300]
            return 'failed', f'Its installer did not answer as expected: {line}'
        if 'error' in result or code != 0:
            return 'failed', (f'{PRODUCT} {version} was not installed: '
                              f"{result.get('error', 'its installer failed')}")
        key = str(result.get('version', ''))
        current = self.root / 'current'
        if result.get('mode') != 'managed' or not key.startswith(f'{version}-') \
                or not os.path.islink(current) \
                or Path(os.readlink(current)) != self.root / 'versions' / key:
            return 'failed', (f'Its installer finished, but {PRODUCT} {version} is not '
                              'the version in use. Run the installer again.')
        return 'restart', (f'{PRODUCT} {version} is installed, checked and in place. '
                           'Restart to use it. This page comes back by itself.'
                           if self._opener() else
                           f'{PRODUCT} {version} is installed, checked and in place. '
                           f'Close {PRODUCT} and open it again to use it.')

    def _opener(self) -> Path | None:
        """The command the installer wrote that opens the studio, when it is there."""
        install = self.module()
        try:
            state = install.read_state(self.root) if install else None
        except install.InstallError:
            state = None
        kept = (state or {}).get('launchers', {}).get('command')
        return Path(kept) if kept and install.ours(Path(kept)) else None

    def restart(self, working: bool) -> dict:
        """Once a newer version is installed: stop, so that `studio serve` runs the command
        that opens the studio, which opens the newer one. Refused while an item
        works, and when there is no such command: then the person opens it again."""
        with self._lock:
            upgrade = dict(self._upgrade) if self._upgrade else None
        if not upgrade or upgrade['state'] != 'restart':
            raise WorkspaceError(NO_RESTART)
        if working:
            raise WorkspaceError(RESTART_WORKING)
        opener = self._opener()
        if opener is None:
            raise WorkspaceError(f'{PRODUCT} cannot open itself again here. Close it and '
                                 'open it again.')
        with self._lock:
            self._upgrade = {**self._upgrade, 'state': 'restarting',
                             'says': f"Restarting with {PRODUCT} {upgrade['version']}."}
            self.restarting = ['/bin/sh', str(opener), 'serve']
        if self.leave is not None:
            self.leave()
        return self.report()

    def command(self) -> str | None:
        """The command that brings a newer release of the studio to a checkout this runner runs
        from, when it is a git checkout: the studio is then upgraded there."""
        if not self.checkout() or not any((folder / '.git').exists()
                                          for folder in (self.folder, *self.folder.parents)):
            return None
        return f'cd {shlex.quote(str(self.folder))} && git pull'

    def versions(self, found: dict | None, upgrade: dict | None, busy: bool,
                 brand: dict | None = None) -> dict:
        """A row each for the studio, its companions and the brand skill, what an
        upgrade or a brand install would do, and the key Home is dismissed with. Worked out
        from what was last found; asks nothing."""
        kept = self._saved()
        online = kept.get('found') or {}
        have, newest = self.version(), (found or {}).get('newest')
        checkout = self.checkout() or (found or {}).get('mode') == 'link'
        ahead = bool(newest and _version(newest['version']) > _version(have))
        waiting = bool(upgrade and upgrade['state'] in ('restart', 'restarting'))
        rows = [{**self._own_row(have, newest, ahead, checkout, upgrade),
                 'known_at': (online.get(SELF) or {}).get('known_at')}]
        pins = (newest or {}).get('pins') if ahead else None
        for entry in (found or {}).get('companions', []):
            rows.append(self._companion_row(entry, online.get(entry['name']) or {},
                                            newest if ahead else None, pins,
                                            (found.get('tools') or {}).get(entry['name'])))
        rows.append(self._brand_row(found, online.get(BRAND) or {}))
        wanted = [row for row in rows if row['state'] in ('update', 'missing')]
        key = ', '.join(f"{row['name']} {row['target'] or row['state']}" for row in wanted)
        offered = bool(not self.suite_managed() and ahead and not checkout and found and found['installer']
                       and found['mode'] == 'managed' and not busy and not waiting)
        return {'rows': rows, 'at': kept.get('at'), 'checkout': checkout,
                'command': self.command(),
                'suite': 'marketing-studio' if self.suite_managed() else None,
                'key': key or None, 'dismissed': bool(key) and kept.get('dismissed') == key,
                'upgrade': {'offered': offered, 'version': newest['version'] if ahead else None,
                            'from': newest['from'] if ahead else None,
                            'state': upgrade and upgrade['state'],
                            'since': upgrade and upgrade['since'],
                            'says': upgrade and upgrade['says'],
                            'restart': bool(upgrade and upgrade['state'] == 'restart'
                                            and self._opener())},
                'brand': self._brand_offer(rows[-1], busy or waiting, brand)}

    def _own_row(self, have: str, newest: dict | None, ahead: bool, checkout: bool,
                 upgrade: dict | None) -> dict:
        """The studio's own row."""
        row = {'name': SELF, 'installed': have, 'newest': newest and newest['version'],
               'pinned': None, 'next': None, 'target': None, 'beyond': None, 'reports': None}
        if self.suite_managed():
            return {**row, 'newest': have, 'state': 'current', 'says': 'Updates are delivered by the Marketing Studio installer.'}
        if newest is None:
            return {**row, 'state': 'unknown', 'says': (
                f'Whether a newer {PRODUCT} is out is not known yet. It is looked for '
                'once a day, and when you check this computer again.')}
        if not ahead:
            return {**row, 'state': 'current', 'says': f'{PRODUCT} {have} is the newest.'}
        version = newest['version']
        if upgrade and upgrade['state'] in ('restart', 'restarting') \
                and upgrade.get('version') == version:
            says = f'{PRODUCT} {version} is installed. Restart to use it.'
        elif checkout:
            says = (f'{PRODUCT} {version} is out, and this is {have}. This one runs '
                    'from a copy of its repository, so it is upgraded there with git pull, '
                    'not from here.')
        else:
            says = f'{PRODUCT} {version} is out, and this is {have}.'
        return {**row, 'state': 'update', 'target': version, 'says': says}

    @staticmethod
    def guidance() -> dict:
        """Which guidance a new item is given."""
        path = sync_guidance.guidance_root() / 'last.json'
        last = home.read_json(path, None)
        commit = last.get('commit') if isinstance(last, dict) else None
        have = sync_guidance.runtime_version()
        try:
            at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime(
                '%Y-%m-%dT%H:%M:%SZ') if last is not None else None
        except OSError:
            at = None
        # The guidance `adopt` pins a new item to: a whole commit whose folder is there.
        if isinstance(commit, str) and sync_guidance.COMMIT.fullmatch(commit) \
                and (sync_guidance.folder_for(commit) / 'SKILL.md').is_file():
            branch = sync_guidance.source().get('branch', 'main')
            return {'commit': commit[:12], 'at': at, 'says': (
                f'New {ITEMS} follow the guidance from revision {commit[:12]} of {branch}, '
                'the newest when guidance was last fetched.')}
        return {'commit': None, 'at': at, 'says': (
            f'New {ITEMS} follow the guidance installed with {PRODUCT} {have}. '
            + ('The newest could not be fetched when it was last asked for.'
               if last is not None else 'None has been fetched on this computer yet.'))}


NAMES = ('SAVED', 'DAY', 'LOOK_SECONDS', 'UPDATE_SECONDS', 'TAG', 'UPDATING', 'NO_RESTART',
         'BRAND', 'BRAND_SECONDS', 'BRAND_INSTALLING', '_floor', '_now', '_age', '_version',
         'newest', 'fetch_tree', 'install_root', '_who', '_load')
METHODS = {'Upkeep': ('__init__', 'folder', 'checkout', 'version', 'start', 'again', '_first',
           '_background', 'close', 'module', 'check', '_blank', '_brands', '_tools', '_current',
           '_commands', '_main_version', 'saved_path', '_saved', 'due', '_brand_entry',
           'remember_brand', 'look', '_bring', '_said', '_the_brand', '_brand_installed', '_moved',
           'dismiss', 'releases', '_target', '_link', '_main', '_newest', '_refuse_busy',
           'suite_managed', 'upgrade', '_run_installer', '_opener', 'restart', 'command',
           'versions', '_own_row', 'guidance')}
