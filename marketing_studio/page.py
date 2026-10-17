"""The home API: shared settings, first-run setup, inventory, and launch."""
import threading

from studio_core import preferences as shared_preferences
from studio_core.model_catalog import Catalog

from . import catalog, server, shared, state, validation
from .errors import WorkspaceError


class Home(server.Page):
    reads = ('/api/home', '/api/computer', '/api/models')
    writes = ('/api/shared', '/api/setup', '/api/open', '/api/computer', '/api/paths', '/api/models')

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

    def snapshot(self):
        preferences = state.read()
        values, problem = shared.read()
        return {'studios': catalog.describe(preferences.get('paths', {}), self.launcher.running),
                'shared': values, 'shared_problem': problem, 'setup': {**preferences, 'done': not problem and self.configured(values)},
                'computer': self.computer(False), 'efforts': validation.EFFORTS,
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
        if path == '/api/models':
            try:
                return server.as_json(200, self.models.get(sent.get('agent'), refresh=True))
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
        if path == '/api/computer':
            return server.as_json(200, {'computer': self.computer(True)})
        with self.changes:
            if path == '/api/shared':
                try:
                    shared_preferences.save(shared, sent.get('changes'), sent.get('seen'))
                except ValueError as failure:
                    raise WorkspaceError(str(failure)) from failure
            elif path == '/api/setup':
                if type(sent.get('done')) is not bool:
                    raise WorkspaceError('Choose whether setup is complete.')
                kept = state.read()
                try:
                    if sent['done']:
                        shared_preferences.finish(shared, lambda values: self.launcher.prepare(kept, values)
                                           if sent.get('prepare') is True else None)
                    else:
                        shared.update({'setup': {'version': 0}})
                except ValueError as failure:
                    raise WorkspaceError(str(failure)) from failure
                state.save({**kept, 'done': sent['done']})
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
            return server.as_json(200, self.snapshot())
