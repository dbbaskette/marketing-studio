"""The home API: shared settings, first-run setup, inventory, and launch."""
import threading
from pathlib import Path

from studio_core import preferences as shared_preferences
from studio_core import brand_catalog, research_sites, runtime
from studio_core.model_catalog import Catalog

from . import catalog, server, shared, state, validation, workspaces
from .errors import WorkspaceError


class Home(server.Page):
    reads = ('/api/home', '/api/computer', '/api/models')
    writes = ('/api/shared', '/api/setup', '/api/open', '/api/connect', '/api/computer', '/api/paths', '/api/models', '/api/brands', '/api/research-site')

    def __init__(self, port, launcher):
        super().__init__(port)
        self.launcher = launcher
        self.models = Catalog()
        self.changes = threading.RLock()
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

    def snapshot(self):
        preferences = state.read()
        values, problem = shared.read()
        studios = catalog.describe(preferences.get('paths', {}), self.launcher.running)
        done = not problem and self.configured(values)
        for row in studios:
            # Read from each studio's own records: never started, never guessed from a folder's name.
            row['workspace'] = workspaces.connection(row['id'], values) if done and row['installed'] else None
        return {'studios': studios,
                'shared': values, 'shared_problem': problem, 'setup': {**preferences, 'done': not problem and self.configured(values)},
                'computer': self.computer(False), 'efforts': validation.EFFORTS,
                'assistant_default': runtime.assistant_default(state.data_root()),
                'network': self.launcher.network.snapshot() if self.launcher.network else None}

    def read(self, path, one):
        if path == '/api/models':
            try:
                return server.as_json(200, self.models.get(one('agent')))
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        with self.changes:
            return server.as_json(200, self.snapshot() if path == '/api/home'
                                  else {'computer': self.computer(False)})

    def write(self, path, sent):
        if path == '/api/research-site':
            # One site checked as a save would check it; nothing is saved.
            try:
                return server.as_json(200, {'site': research_sites.site(sent.get('site'))})
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        if path == '/api/brands':
            skill = sent.get('skill')
            if skill is not None and (not isinstance(skill, str) or len(skill) > 2000
                                     or not Path(skill).expanduser().is_absolute()):
                raise WorkspaceError('Choose an absolute installed brand skill folder, or leave it blank.')
            return server.as_json(200, brand_catalog.choices(skill))
        if path == '/api/models':
            try:
                return server.as_json(200, self.models.get(sent.get('agent'), refresh=True))
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        if path == '/api/computer':
            return server.as_json(200, {'computer': self.computer(True)})
        with self.changes:
            if path == '/api/shared':
                before = shared.read()[0]
                try:
                    shared_preferences.save(shared, sent.get('changes'), sent.get('seen'))
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
            elif path == '/api/open':
                preferences = state.read()
                if not self.configured(shared.read()[0]):
                    raise WorkspaceError('Finish shared setup before opening a studio.')
                values, problem = shared.read()
                if problem:
                    raise WorkspaceError(problem)
                return server.as_json(200, {'link': self.launcher.open(sent.get('studio'), preferences, values)})
            elif path == '/api/connect':
                preferences = state.read()
                values, problem = shared.read()
                if problem:
                    raise WorkspaceError(problem)
                if not self.configured(values):
                    raise WorkspaceError('Finish shared setup before connecting a studio.')
                result = self.launcher.connect(sent.get('studio'), preferences, values)
                return server.as_json(200, {**self.snapshot(), 'connected': result})
            return server.as_json(200, self.snapshot())
