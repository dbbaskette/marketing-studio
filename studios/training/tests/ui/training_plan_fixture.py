"""Disposable real-page fixture. All authors, research, slides and settings are synthetic."""
import contextlib
import json
import signal
import sys
import threading
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_runner_deck import PageCase
from runner import page
import desk

def main():
    case = PageCase()
    server = None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            case.setUp()
            catalog = mock.patch('studio_core.model_catalog.Catalog.get', return_value={'agent':'codex','models':[],'problem':None})
            catalog.start(); case.addCleanup(catalog.stop)
            from studio_core import preferences, studios_config
            studios_config.update({'local': {'root': str(case.space.root)}})
            preferences.finish(studios_config, lambda _: None)
            case.engine.plan_first = True
            root = case.begin(flow='desk', deck_target=None, brand=None)
        server = desk.Desk(page=lambda port: page.RunnerPage(port, case.engine))
        server.start()
        print(json.dumps({'url': server.url, 'path': str(root)}), flush=True)
        done = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: done.set())
        signal.signal(signal.SIGINT, lambda *_: done.set())
        done.wait()
    finally:
        if server: server.stop()
        case.doCleanups()

if __name__ == '__main__': main()
