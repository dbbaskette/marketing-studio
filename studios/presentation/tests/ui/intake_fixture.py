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
            if '--saved' in sys.argv:
                # A deck the earlier gated flow saved, waiting at its deck: it opens on the desk.
                root = case.gated(title='Saved gated deck')
            if '--saved-read-only' in sys.argv:
                # A deck the earlier gated flow saved whose record the runner cannot read (its
                # review level is missing), shown as a read-only record. It is served on its
                # own: an unreadable record stops the shared worker scan, and with it the
                # opening of every other deck in the workspace on the desk.
                unread = root = case.saved_start(title='Unreadable saved deck')
                from runner import decks
                record = decks.read_run(unread)
                record['schema'] = 2
                record.pop('review_policy', None)
                decks.write_run(unread, record)
                print(json.dumps({'read_only': str(unread)}), file=sys.stderr, flush=True)
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
