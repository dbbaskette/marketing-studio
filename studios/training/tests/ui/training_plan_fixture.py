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
            # --desk: straight to the desk, with no teaching plan to check first.
            case.engine.plan_first = '--desk' not in sys.argv
            workspace_mode = '--workspace' in sys.argv
            case.engine.content_first = workspace_mode
            if workspace_mode:
                from test_runner_deck import MAJOR
                case.workers.found = [[MAJOR]]
            root = case.space.root if '--new' in sys.argv else case.begin(flow='desk', **({} if workspace_mode else {'deck_target': None, 'brand': None}),
                **({'levels':['101','201']} if '--two-levels' in sys.argv else {}),
                **({'yoodli': True} if '--yoodli' in sys.argv else {}))
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
