"""The home API: shared settings, first-run setup, inventory, launch, and the Document
Library screen (browsing, preview, download, upload, Add existing work to library, and
Remove from library or Restore; it selects nothing for a project)."""
import base64
import binascii
import threading
import shutil
from pathlib import Path

from studio_core import preferences as shared_preferences
from studio_core import brand_catalog, brand_data, graphics, research_sites, runtime
from studio_core.model_catalog import Catalog
from studio_core import document_library
from studio_core.document_library import adopt as library_adopt
from studio_core.document_library import context as library_context

from . import brand_job, brand_skill, brand_store, catalog, server, shared, state, validation, workspaces, work_overview
from .errors import WorkspaceError
from .network import VIA_HEADER


# The Brands section's routes, each /api/brand-<name>.
BRAND_ROUTES = ('list', 'start', 'work', 'source', 'keep', 'extract', 'interpret', 'stop', 'part',
                'save', 'push', 'discard', 'file')
REMOTE_BRANDS = ('Brands are made on the computer Marketing Studio runs on, where the sources, '
                 'your assistant and Git are. Open Marketing Studio there.')


class Home(server.Page):
    reads = ('/api/home', '/api/computer', '/api/models')
    writes = ('/api/shared', '/api/setup', '/api/open', '/api/connect', '/api/computer', '/api/paths', '/api/models', '/api/graphics', '/api/brands', '/api/brands-repository', '/api/research-site',
              *library_context.ROUTES, '/api/library-upload', '/api/library-download',
              '/api/library-existing', '/api/library-adopt', '/api/library-hide',
              *(f'/api/brand-{name}' for name in BRAND_ROUTES))
    BRAND_UPLOAD = '/api/brand-source'
    BRAND_UPLOAD_LIMIT = 56_000_000
    UPLOAD = '/api/library-upload'
    EXISTING = ('/api/library-existing', '/api/library-adopt')
    HIDE = '/api/library-hide'
    UPLOAD_LIMIT = 12_000_000   # bytes: a document of up to 8 MB, in base64, with its name

    def __init__(self, port, launcher):
        super().__init__(port)
        self.launcher = launcher
        self.models = Catalog()
        self.changes = threading.RLock()
        # Each request is answered on its own thread: whether this one came over the bridge.
        self.caller = threading.local()
        # Upgrade a completed pre-shared setup on opening Marketing Studio.
        values, problem = shared.read()
        if state.read().get('done') and not problem and 'setup' not in values:
            try:
                shared_preferences.finish(shared, lambda _: None)
            except ValueError:
                pass

    @staticmethod
    def configured(values):
        return shared_preferences.ready(values)

    def uses_google(self):
        return shared.read()[0].get('output') == 'google'

    @staticmethod
    def storage(values):
        """The shared choices that say where every studio's work lives."""
        return {'team': {key: (values.get('team') or {}).get(key) for key in ('repository', 'branch')},
                'local': (values.get('local') or {}).get('root'), 'share': values.get('share')}

    @staticmethod
    def readiness(row, problem, done, agent):
        """What a launch card can honestly say before the studio opens, and how to recover.

        Only local launch prerequisites are looked at: shared setup, the chosen assistant's
        command and Git on PATH. Nothing is run, signed in to, installed or started; account
        sign-in and task tools are each studio's to check when a task needs them."""
        if not row['installed']:
            return {'state': 'off', 'label': 'Not installed',
                    'detail': 'Install it yourself to open it here. Marketing Studio never installs or updates studios.',
                    'action': None}
        if problem:
            return {'state': 'none', 'label': 'Not checked',
                    'detail': 'The shared settings file could not be read, so what this studio needs was not checked.',
                    'action': {'view': 'settings', 'label': 'Review shared settings'}}
        if not done:
            return {'state': 'review', 'label': 'Needs setup',
                    'detail': 'Finish shared setup once for all studios.',
                    'action': {'view': 'settings', 'label': 'Finish shared setup'}}
        missing = [name for name, found in ((runtime.ASSISTANTS.get(agent, 'The assistant'),
                                             runtime.assistant_command(agent)),
                                            ('Git', shutil.which('git'))) if not found]
        if missing:
            return {'state': 'review', 'label': 'Needs setup',
                    'detail': f"{' and '.join(missing)} {'was' if len(missing) == 1 else 'were'} not found on this computer.",
                    'action': {'view': 'computer', 'label': 'Check this computer'}}
        return {'state': 'done', 'label': 'Can open',
                'detail': f'Setup, {runtime.ASSISTANTS.get(agent, "the assistant")} and Git found. '
                          'Sign-in is checked when a task needs it.',
                'action': None}

    def snapshot(self):
        preferences = state.read()
        values, problem = shared.read()
        studios = catalog.describe(preferences.get('paths', {}), self.launcher.running)
        done = not problem and self.configured(values)
        agent=(values.get('assistant') or {}).get('agent') or runtime.assistant_default(state.data_root())
        for row in studios:
            row['readiness'] = self.readiness(row, problem, done, agent)
            # Read from each studio's own records: never started, never guessed from a folder's name.
            row['workspace'] = workspaces.connection(row['id'], values) if done and row['installed'] else None
        return {'studios': studios, 'work_overview': work_overview.snapshot(studios),
                'shared': values, 'shared_problem': problem, 'setup': {**preferences, 'done': not problem and self.configured(values)},
                # Each kind of work as the form fills it in, with the kinds not yet saved.
                'models_shown': None if problem else shared_preferences.model_profiles.shown(values),
                'computer': self.computer(False), 'efforts': validation.EFFORTS,
                # Whether a Gemini key is here and where from; never the key.
                'graphics': graphics.snapshot(values, runtime.assistant_default(state.data_root())),
                'assistant_default': runtime.assistant_default(state.data_root()),
                # The private link is this computer's to show; the phone already holds it.
                'network': self.launcher.network.snapshot(private=not getattr(self.caller, 'remote', False))
                if self.launcher.network else None}

    def read(self, path, one):
        if path == '/api/models':
            try:
                return server.as_json(200, self.models.get(one('agent')))
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        with self.changes:
            return server.as_json(200, self.snapshot() if path == '/api/home'
                                  else {'computer': self.computer(False)})

    def answer(self, target, headers, method='GET', body=None):
        """A request, remembering whether the network bridge carried it. Only the bridge adds
        its header, and a loopback caller that sends it only gets the network's answers: the
        studio's bridge link, and the home snapshot without the private link."""
        self.caller.remote = headers.get(VIA_HEADER) == 'network'
        try:
            return super().answer(target, headers, method, body)
        finally:
            self.caller.remote = False

    def body_limit(self, target, headers):
        if target.partition('?')[0] == self.UPLOAD:
            return self.UPLOAD_LIMIT
        if target.partition('?')[0] == self.BRAND_UPLOAD:
            return self.BRAND_UPLOAD_LIMIT
        return super().body_limit(target, headers)

    def library(self, path, sent):
        """The Document Library screen: what every studio page answers, and here also an
        upload, a download, and Remove from library or Restore. Nothing selects context for
        a project, and no studio's workspace is read or changed by a removal."""
        try:
            if path in library_context.ROUTES:
                return library_context.answer(path, sent, 'marketing')
            if path in self.EXISTING:
                # Only the workspace each studio remembers in its own records is read: no
                # folder is searched, and no studio is started or set up.
                known = {identifier: workspaces.remembered(identifier)
                         for identifier in catalog.STUDIOS}
                if path == '/api/library-existing':
                    return library_adopt.preview(known)
                with self.changes:
                    return library_adopt.confirm(known, sent.get('signature'))
            if path == self.HIDE:
                # Hides the document from browsing and Add from library, or shows it again.
                # No revision is deleted; projects that pinned it keep their own copies.
                found = document_library.opened()
                if found is None:
                    raise document_library.LibraryError(library_context.NOT_MADE)
                with self.changes:
                    return {'document': found.hide(sent.get('id'), sent.get('hidden'))}
            if path == '/api/library-download':
                found = document_library.opened()
                if found is None:
                    raise document_library.LibraryError(library_context.NOT_MADE)
                revision = sent.get('revision')
                name, media, data = found.download(sent.get('id'), revision, sent.get('format'))
                return {'name': name, 'media': media, 'content': base64.b64encode(data).decode('ascii')}
            content = sent.get('content')
            try:
                if not isinstance(content, str) or not content:
                    raise ValueError
                data = base64.b64decode(content, validate=True)
            except (binascii.Error, ValueError):
                raise WorkspaceError('The file did not arrive whole. Choose it again.')
            with self.changes:
                made = document_library.opened(create=True)   # an upload is an explicit use
                row = made.add_upload(sent.get('name'), data, title=sent.get('title') or None,
                                      operation=sent.get('operation'), studio='marketing')
            return {'document': row, 'location': document_library.location()['shown']}
        except document_library.LibraryError as error:
            raise WorkspaceError(str(error)) from error

    def brands(self, path, sent):
        """The Brands section: a front for Harness Brand's pack commands and the person's
        assistant, on working copies kept outside the brands folder until Save."""
        if getattr(self.caller, 'remote', False):
            raise WorkspaceError(REMOTE_BRANDS)
        name = path.removeprefix('/api/brand-')
        key = sent.get('key')
        if name == 'work':
            return server.as_json(200, brand_store.view(key))
        if name == 'file':
            media, data = brand_store.file(key, sent.get('path'))
            return 200, media, data
        if name == 'stop':
            brand_store.stop(key)
            return server.as_json(200, brand_store.view(key))
        if name == 'discard':
            brand_store.discard(key)
            return server.as_json(200, {'discarded': key})
        if name == 'source':
            added = brand_store.add_source(key, sent.get('name'),
                                           brand_store.decode(sent.get('content')))
            return server.as_json(200, {**added, 'work': brand_store.view(key)})
        if name == 'keep':
            kept = brand_store.keep_source(key, sent.get('name'), sent.get('which'))
            return server.as_json(200, {**kept, 'work': brand_store.view(key)})
        if name == 'part':
            if sent.get('action') == 'accept':
                brand_store.accept(key, sent.get('part'))
            elif sent.get('action') == 'edit':
                brand_store.edit(key, sent.get('part'), sent.get('content'))
            else:
                raise WorkspaceError('Accept the part, or save your edit of it.')
            return server.as_json(200, brand_store.view(key))
        values, problem = shared.read()
        if problem:
            raise WorkspaceError(problem)
        try:
            place = brand_store.storage(values)
        except WorkspaceError as failure:
            if name == 'list':
                return server.as_json(200, {'unavailable': str(failure), 'where': 'Shared settings, Brand'})
            raise
        if name == 'push':
            if sent.get('confirm') is not True:
                raise WorkspaceError('Say yes to the push first.')
            return server.as_json(200, brand_store.push(place, sent.get('expected')))
        brand = values.get('brand') if isinstance(values.get('brand'), dict) else {}
        chosen = brand.get('skill') if isinstance(brand.get('skill'), str) and brand.get('skill') else None
        try:
            found = brand_skill.find(chosen, place.folder)
        except WorkspaceError as failure:
            if name == 'list':
                return server.as_json(200, {'unavailable': str(failure), 'where': place.where})
            raise
        if name == 'list':
            return server.as_json(200, brand_store.listing(found, place))
        if name == 'start':
            work = brand_store.start(place, sent.get('kind'), sent.get('id'), sent.get('name'),
                                     sent.get('libraryKind'), sent.get('update') is True)
            return server.as_json(200, brand_store.view(work['key']))
        if name == 'extract':
            work = brand_store.record(key)
            if work['kind'] == 'library':
                job = brand_store.extract_library(found, key)
            else:
                templates, icons = sent.get('templates') or [], sent.get('icons') or []
                if not isinstance(templates, list) or not isinstance(icons, list):
                    raise WorkspaceError('Choose the templates and icon libraries from this page.')
                job = brand_store.extract_brand(found, key, sent.get('tokens'), templates, icons)
            brand_store.begin(key, 'extract', job)
            return server.as_json(200, brand_store.view(key))
        if name == 'interpret':
            job = brand_job.interpret(found, key, values, sent.get('part'), sent.get('note'))
            brand_store.begin(key, 'interpret', job, sent.get('part'))
            return server.as_json(200, brand_store.view(key))
        if name == 'save':
            return server.as_json(200, brand_store.save(found, place, key))
        raise WorkspaceError('That is not something Brands does.')

    def write(self, path, sent):
        if path.startswith('/api/brand-'):
            return self.brands(path, sent)
        if path in library_context.ROUTES or path in (self.UPLOAD, self.HIDE, '/api/library-download',
                                                      *self.EXISTING):
            return server.as_json(200, self.library(path, sent))
        if path == '/api/research-site':
            # One site checked as a save would check it; nothing is saved.
            try:
                return server.as_json(200, {'site': research_sites.site(sent.get('site'))})
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        if path == '/api/brands-repository':
            # Only the saved setting is fetched, so a form never fetches an address it did not save.
            values, problem = shared.read()
            if problem:
                raise WorkspaceError(problem)
            try:
                return server.as_json(200, brand_data.bring((values.get('brand') or {}).get('brands')))
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        if path == '/api/brands':
            skill = sent.get('skill')
            if skill is not None and (not isinstance(skill, str) or len(skill) > 2000
                                     or not Path(skill).expanduser().is_absolute()):
                raise WorkspaceError('Choose an absolute installed brand skill folder, or leave it blank.')
            return server.as_json(200, brand_catalog.choices(skill))
        if path == '/api/graphics':
            try:
                return server.as_json(200, graphics.act(
                    sent, remote=getattr(self.caller, 'remote', False)))
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        if path == '/api/models':
            try:
                return server.as_json(200, self.models.get(sent.get('agent'), refresh=True))
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        if path == '/api/computer':
            return server.as_json(200, {'computer': self.computer(True)})
        # Opening or connecting a studio can take a minute or more. The settings are read under
        # the lock; the launch itself is not, so Home, a phone and every other button keep
        # answering meanwhile. The launcher has its own lock for the studios it starts.
        if path == '/api/open':
            with self.changes:
                preferences = state.read()
                if not self.configured(shared.read()[0]):
                    raise WorkspaceError('Finish shared setup before opening a studio.')
                values, problem = shared.read()
                if problem:
                    raise WorkspaceError(problem)
                # This computer keeps the loopback link; only a phone is given a studio's bridge.
                remote = getattr(self.caller, 'remote', False)
                resume = sent.get('resume')
                if resume is not None:
                    try: work_overview.check(sent.get('studio'), resume)
                    except (ValueError, KeyError) as error: raise WorkspaceError(str(error)) from None
            link = self.launcher.open(sent.get('studio'), preferences, values, remote=remote)
            if resume is not None: link = work_overview.link(sent.get('studio'), resume, link)
            return server.as_json(200, {'link': link})
        if path == '/api/connect':
            with self.changes:
                preferences = state.read()
                values, problem = shared.read()
                if problem:
                    raise WorkspaceError(problem)
                if not self.configured(values):
                    raise WorkspaceError('Finish shared setup before connecting a studio.')
            result = self.launcher.connect(sent.get('studio'), preferences, values)
            with self.changes:
                return server.as_json(200, {**self.snapshot(), 'connected': result})
        with self.changes:
            if path == '/api/shared':
                before = shared.read()[0]
                try:
                    shared_preferences.save(shared, sent.get('changes'), sent.get('seen'))
                except shared_preferences.Conflict as failure:
                    # Nothing was written. The page names the field and offers the newer values.
                    refused = WorkspaceError(str(failure))
                    refused.details = {'conflict': {'fields': failure.fields}}
                    raise refused from failure
                except ValueError as failure:
                    raise WorkspaceError(str(failure)) from failure
                values, problem = shared.read()
                kept = state.read()
                if kept.get('done') and not problem and self.configured(values) \
                        and self.storage(values) != self.storage(before):
                    # The storage changed after setup: studios without a workspace get one
                    # there now, and the cards say which ones keep a different workspace.
                    outcome = {}
                    try:
                        outcome['prepared'] = self.launcher.prepare(kept, values)
                    except WorkspaceError as failure:
                        outcome['prepare_problem'] = str(failure)
                    return server.as_json(200, {**self.snapshot(), **outcome})
            elif path == '/api/setup':
                if type(sent.get('done')) is not bool:
                    raise WorkspaceError('Choose whether setup is complete.')
                kept, outcome = state.read(), {}
                try:
                    if sent['done']:
                        shared_preferences.finish(shared, lambda values: outcome.update(
                            prepared=self.launcher.prepare(kept, values)) if sent.get('prepare') is True else None)
                    else:
                        shared.update({'setup': {'version': 0}})
                except ValueError as failure:
                    raise WorkspaceError(str(failure)) from failure
                state.save({**kept, 'done': sent['done']})
                return server.as_json(200, {**self.snapshot(), **outcome})
            elif path == '/api/paths':
                paths = sent.get('paths')
                if not isinstance(paths, dict) or set(paths) - catalog.STUDIOS.keys():
                    raise WorkspaceError('Choose studio installation folders from this page.')
                for identifier, value in paths.items():
                    if not isinstance(value, str) or len(value) > 4000:
                        raise WorkspaceError('Give a studio installation folder as text.')
                    if value and catalog.locate(identifier, {identifier: value}) is None:
                        raise WorkspaceError('That folder does not contain the studio launcher.')
                kept = state.read()
                state.save({**kept, 'paths': {**kept.get('paths', {}), **paths}})
            return server.as_json(200, self.snapshot())
