"""The home API: shared settings, first-run setup, inventory, and launch."""
import threading

from . import catalog, server, shared, state, validation
from .errors import WorkspaceError


class Home(server.Page):
    reads = ('/api/home', '/api/computer')
    writes = ('/api/shared', '/api/setup', '/api/open', '/api/computer', '/api/paths')

    def __init__(self, port, launcher):
        super().__init__(port)
        self.launcher = launcher
        self.changes = threading.RLock()

    def uses_google(self):
        return shared.read()[0].get('output') == 'google'

    def snapshot(self):
        preferences = state.read()
        values, problem = shared.read()
        return {'studios': catalog.describe(preferences.get('paths', {}), self.launcher.running),
                'shared': values, 'shared_problem': problem, 'setup': preferences,
                'computer': self.computer(False), 'efforts': validation.EFFORTS}

    def read(self, path, one):
        with self.changes:
            return server.as_json(200, self.snapshot() if path == '/api/home'
                                  else {'computer': self.computer(False)})

    def write(self, path, sent):
        if path == '/api/computer':
            return server.as_json(200, {'computer': self.computer(True)})
        with self.changes:
            if path == '/api/shared':
                changes, seen = sent.get('changes'), sent.get('seen')
                if not isinstance(seen, dict):
                    raise WorkspaceError('Reload shared settings before saving changes.')
                validation.check(changes, shared.read()[0])

                def guard(current):
                    validation.check(changes, current)
                    for key, value in changes.items():
                        pairs = value.items() if isinstance(value, dict) else [(None, value)]
                        for member, wanted in pairs:
                            def leaf(obj):
                                group = obj.get(key)
                                return (group or {}).get(member) if member is not None else group
                            held, before = leaf(current), leaf(seen)
                            if held != before and held != wanted:
                                raise WorkspaceError('Another studio changed this setting. Reload the page and try again.')
                shared.update(changes, guard=guard)
            elif path == '/api/setup':
                if type(sent.get('done')) is not bool:
                    raise WorkspaceError('Choose whether setup is complete.')
                values, problem = shared.read()
                if problem:
                    raise WorkspaceError(problem)
                validation.check({}, values)
                if sent['done'] and not ((values.get('team') or {}).get('repository')
                                        or (values.get('local') or {}).get('root')):
                    raise WorkspaceError('Choose a local work folder or a repository before finishing setup.')
                preferences = state.read()
                if sent.get('prepare') is True and sent['done']:
                    self.launcher.prepare(preferences, values)
                state.save({**preferences, 'done': sent['done']})
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
                if not preferences.get('done'):
                    raise WorkspaceError('Finish shared setup before opening a studio.')
                values, problem = shared.read()
                if problem:
                    raise WorkspaceError(problem)
                return server.as_json(200, {'link': self.launcher.open(sent.get('studio'), preferences, values)})
            return server.as_json(200, self.snapshot())
