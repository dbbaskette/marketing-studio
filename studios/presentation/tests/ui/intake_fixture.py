"""Real native page over isolated settings, documents, slides and scripted authors."""
import contextlib
import json
import os
from pathlib import Path
import signal
import sys
import threading
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT)]
from runner_support import DeskCase
from runner import page
import server


def main():
    case, web = DeskCase(), None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            case.setUp()
            catalog = mock.patch('studio_core.model_catalog.Catalog.get', return_value={
                'agent': 'codex', 'models': [], 'problem': None})
            catalog.start()
            case.addCleanup(catalog.stop)
            from studio_core import document_library, preferences, studios_config
            os.environ['STUDIOS_LIBRARY'] = str(case.base / 'library')
            studios_config.update({'local': {'root': str(case.space.root)}})
            preferences.finish(studios_config, lambda _: None)
            document_library.opened(create=True).add_upload('capacity-notes.md',
                b'# Capacity notes\n\nKeep more than one instance running.\n')
            root = case.space.root
            if '--desk' in sys.argv:
                root = case.start_desk(look='default')
                case.waiting(root)
        web = server.Desk(page=lambda port: page.RunnerPage(port, case.engine))
        web.start()
        print(json.dumps({'url': web.url, 'path': str(root)}), flush=True)
        done = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: done.set())
        signal.signal(signal.SIGINT, lambda *_: done.set())
        done.wait()
    finally:
        if web:
            web.stop()
        case.doCleanups()


if __name__ == '__main__':
    main()
