"""Real story page over isolated settings and scripted workers, never live providers."""
import contextlib
import json
from pathlib import Path
import signal
import sys
import threading
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_slide_story import SlideStoryTests
from runner import agents, page
import server


def main():
    case, web = SlideStoryTests(), None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            case.setUp()
            catalog = mock.patch('studio_core.model_catalog.Catalog.get', return_value={
                'agent': 'codex', 'models': [], 'problem': None})
            catalog.start(); case.addCleanup(catalog.stop)
            from studio_core import preferences, studios_config
            studios_config.update({'local': {'root': str(case.space.root)}})
            preferences.finish(studios_config, lambda _: None)
            if '--timeout' in sys.argv:
                case.workers.queued['scan'] = [lambda tools, job: agents.Outcome(False, 'timeout', seconds=270)]
            root = case.start(research=True, research_questions=['Which failure modes remain?'])
        web=server.Desk(page=lambda port:page.RunnerPage(port,case.engine));web.start()
        print(json.dumps({'url': web.url, 'path': str(root)}), flush=True)
        done = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: done.set()); signal.signal(signal.SIGINT, lambda *_: done.set())
        done.wait()
    finally:
        if web: web.stop()
        case.doCleanups()


if __name__ == '__main__': main()
