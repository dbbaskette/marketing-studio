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
    if '--saved-taken' in sys.argv:
        # Two people sharing one team repository: the page is Blake's, over a deck Alex runs.
        from runner_support import TeamCase

        class Team(DeskCase, TeamCase):
            pass
        case = Team()
    else:
        case = DeskCase()
    web, engine = None, None
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
            if '--selected' in sys.argv or '--selected-again' in sys.argv:
                # A deck started at Selected changes, on the desk with slide 2 changed: it offers
                # Upgrade to Redesign, keep content. Upgrading it, then Start on its priced step,
                # runs the redesign with the stand-in assistant jobs. With --selected-again, a
                # first such deck is upgraded and redrawn before it, so this computer has a
                # record of how long a redesign's steps take, which the priced step says.
                from runner_support import read_word_for_word
                from test_desk_words import planned
                for again in range(2 if '--selected-again' in sys.argv else 1):
                    case.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
                    root = case.existing_deck('automatic', 'selected', flow='desk',
                                              selected='Shorten the words on slide 2')
                    case.on_desk(root)
                    if again == 0 and '--selected-again' in sys.argv:
                        case.engine.desk_upgrade(root, case.desk_view(root)['expected'])
                        case.engine.desk_redesign_start(root)
                        case.pick_look(root)
                        case.on_desk(root)
                        case.workers.queued['outline'] = [read_word_for_word(case)] * 4
            if '--saved' in sys.argv:
                # A deck the earlier gated flow saved, waiting at its deck: it opens on the desk.
                root = case.load_saved('build', title='Saved gated deck')
            if '--saved-question' in sys.argv:
                # A deck the earlier gated flow saved with a worker's question unanswered after
                # its outline was drafted: it opens on the desk with the question kept in its
                # saved runner history.
                root = case.load_saved('question', title='Saved deck with a question')
            if '--saved-read-only' in sys.argv:
                # A deck the earlier gated flow saved whose record the runner cannot read (its
                # review level is missing), shown as a read-only record. It is served on its
                # own: an unreadable record stops the shared worker scan, and with it the
                # opening of every other deck in the workspace on the desk.
                unread = root = case.load_saved('unleveled', title='Unreadable saved deck')
                print(json.dumps({'read_only': str(unread)}), file=sys.stderr, flush=True)
            if '--saved-delivered' in sys.argv:
                # Delivered by the earlier flow: the finished Open on the desk opens it.
                root = case.load_saved('delivered', title='Delivered earlier')
            if '--saved-nothing' in sys.argv:
                # Stopped at its research plan, before anything was made: read-only.
                root = case.load_saved('research-plan', title='Stopped before its outline')
            if '--saved-interrupted' in sys.argv:
                # Its opening on the desk stopped in the middle, after the commit, as a runner
                # that ended there leaves it; and another saved deck that waits for it.
                import subprocess
                from runner import desk_chat
                from test_saved_records import CRASH, STUDIO
                beside = case.load_saved('outline', title='Waiting beside it')
                root = case.load_saved('build', title='Interrupted opening')
                token = desk_chat.migration_preview(case.engine, root)['expected']
                subprocess.run([sys.executable, '-c', CRASH, str(root), token, 'commit'],
                               cwd=STUDIO, env={**os.environ, 'PYTHONPATH': '.:tests'},
                               capture_output=True, text=True, timeout=30)
                print(json.dumps({'beside': str(beside)}), file=sys.stderr, flush=True)
            if '--saved-taken' in sys.argv:
                # Alex runs a saved deck; the page is Blake's, who takes it over to open it.
                taken = case.load_saved('build', title='Run by Alex')
                case.engine.share()
                blake = mock.patch.dict(os.environ, case.blake.env)
                blake.start()
                case.addCleanup(blake.stop)
                studios_config.update({'local': {'root': str(case.blake.space.root)}})
                preferences.finish(studios_config, lambda _: None)
                case.blake.engine.fetch()
                engine, root = case.blake.engine, case.theirs(case.blake, taken)
        served = engine or case.engine
        web = server.Desk(page=lambda port: page.RunnerPage(port, served))
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
