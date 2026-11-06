"""A real native desk with a controllable scripted guide worker; no user state."""
import json
from pathlib import Path
import signal
import sys
import threading
from unittest import mock

native = Path(__file__).resolve().parents[1] / 'studios/training'
sys.path[:0] = [str(native / 'tests'), str(native)]
from runner_support import StudioCase
from runner import page
from studio_core import preferences, studios_config
import desk

case = StudioCase()
web = None
release, entered = threading.Event(), threading.Event()
try:
    case.setUp()
    studios_config.update({'local': {'root': str(case.space.root)}})
    preferences.finish(studios_config, lambda _: None)
    catalog = mock.patch('studio_core.model_catalog.Catalog.get', return_value={'agent': 'codex', 'models': [], 'problem': None})
    catalog.start(); case.addCleanup(catalog.stop)

    def guide(tools, job):
        root = case.engine.trainings()[0]
        with case.engine.files:
            record = case.engine._load(root)
            # This fixture isolates the UI handoff. Creator receipt semantics have
            # separate native coverage; no synthetic choice is presented as checked.
            record['research_execution'] = {'progress': {
                'phase': 'creator-approved', 'agents': {'count': 0, 'active': []}}}
            case.engine._store(root, record)
        entered.set()
        while not release.wait(0.05):
            if case.engine._run(root).stop.is_set():
                return
        return case.workers.document(tools, job)

    case.workers.then('document', guide)
    case.engine.background = True
    root = case.start(levels=['101', '201'], materials=['document', 'brief'])
    if not entered.wait(30):
        raise RuntimeError('The scripted guide worker did not start')

    class Fixture(page.RunnerPage):
        reads = (*page.RunnerPage.reads, '/api/fixture-progress-state')
        def read(self, address, one):
            if address == '/api/fixture-progress-state':
                return desk.as_json(200, {'jobs': len(case.workers.jobs)})
            return super().read(address, one)

    web = desk.Desk(page=lambda port: Fixture(port, case.engine)); web.start()
    print(json.dumps({'url': web.url, 'path': str(root)}), flush=True)
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    done.wait()
finally:
    release.set()
    if web: web.stop()
    case.doCleanups()
