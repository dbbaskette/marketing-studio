"""The parts of the runner's `page` both deck studios share. A studio binds them
into its own module with `studio_core.modules.bind`; they read that module's names.

Each method names its class in `super()`: the class is the studio's, found in its module.
"""
from __future__ import annotations

# ruff: noqa: F821  these definitions read the names of the studio module they are
# bound into; each studio's test_shared_runner_use checks every one resolves there.

import concurrent.futures
import threading

PNG = 'image/png'


class RunnerPage:
    """The shared methods of the studio's RunnerPage."""

    def __init__(self, port: int, engine):
        super(RunnerPage, self).__init__(port)
        self.engine = engine

    def agents(self) -> list[dict]:
        """Each agent: installed, signed in and reachable now. Looked at when asked, both
        at once, and each look is reused for a minute."""
        names = list(self.engine.adapters)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(names) or 1) as pool:
            found = list(pool.map(self.engine.ready, names))
        return [{'agent': name, 'installed': ready.installed, 'signed_in': ready.signed_in,
                 'reachable': ready.reachable, 'version': ready.version,
                 'problem': ready.problem} for name, ready in zip(names, found)]


class Studio:
    """The shared methods of the studio's Studio."""

    def __init__(self, engine, port: int = 0, token: str | None = None):
        super(Studio, self).__init__(port, page=lambda chosen: RunnerPage(chosen, engine))
        self.engine = engine
        if token:   # a runner opened again in its own place keeps the key its page holds
            self.page.token = self.token = token

    def serve(self) -> None:
        self.engine.serving()
        super(Studio, self).serve()

    def leave(self, after: float = 0.5) -> None:
        """Stop serving shortly, once what is being answered has gone out."""
        threading.Timer(after, self.server.shutdown).start()

    def start(self) -> None:
        self.engine.serving()
        super(Studio, self).start()

    def stop(self) -> None:
        super(Studio, self).stop()
        self.engine.close()


NAMES = ('PNG',)
METHODS = {'RunnerPage': ('__init__', 'agents'), 'Studio': ('__init__', 'serve', 'leave', 'start',
           'stop')}
