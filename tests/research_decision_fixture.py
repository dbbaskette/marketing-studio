"""Native Training Studio creator decisions using fictional evidence only."""
import json
from pathlib import Path
import signal
import sys
import threading

native = Path(__file__).resolve().parents[1] / 'studios/training'
sys.path.insert(0, str(native / 'tests'))
sys.path.insert(1, str(native))
from test_research_decision import CreatorDecisionTests
from runner import page
import desk

case = CreatorDecisionTests()
web = None
try:
    case.setUp()
    case.unread = True
    root = case.start()
    class Fixture(page.RunnerPage):
        reads = (*page.RunnerPage.reads, '/api/fixture-decision-state')
        def read(self, address, one):
            if address == '/api/fixture-decision-state':
                from studio_core import research_contract
                output = root / 'research'
                return desk.as_json(200, {'jobs': len(case.workers.jobs),
                    'report': (output/'report.md').read_text() if (output/'report.md').exists() else '',
                    'creator': (output/'creator.json').exists()})
            return super().read(address, one)
    web = desk.Desk(page=lambda port: Fixture(port, case.engine)); web.start()
    print(json.dumps({'url': web.url, 'path': str(root)}), flush=True)
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    done.wait()
finally:
    if web: web.stop()
    case.doCleanups()
