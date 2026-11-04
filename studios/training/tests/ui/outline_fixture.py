"""Native outline review with a disposable workspace and scripted authors only."""
import contextlib
import json
from pathlib import Path
import signal
import sys
import threading
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_outline_integration import OutlineIntegrationTests
from runner import agents, page
import desk


def main():
    case,web=OutlineIntegrationTests(),None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            case.setUp()
            patcher=mock.patch('studio_core.model_catalog.Catalog.get',return_value={'agent':'codex','models':[],'problem':None})
            patcher.start();case.addCleanup(patcher.stop)
            from studio_core import preferences,studios_config
            studios_config.update({'local':{'root':str(case.space.root)}})
            preferences.finish(studios_config,lambda _:None)
            if '--timeout' in sys.argv:
                case.workers.queued['scan']=[lambda tools,job:agents.Outcome(False,'timeout','Synthetic scan time cap',seconds=180,cost=0.03)]
            if '--adopt' in sys.argv:
                case.engine.outline_first=False
                with mock.patch.object(case.engine,'wake'):
                    root=case.begin_outline()
                case.engine.act(root,'stop')
            else:
                root=case.begin_outline(research_questions=['Which failure modes remain?'])
        class SpendingPage(page.RunnerPage):
            writes = (*page.RunnerPage.writes, '/api/fixture-spend')
            def write(self, path, sent):
                if path == '/api/fixture-spend' and '--spending-test' in sys.argv:
                    import home
                    with case.engine.files:
                        record=case.engine._load(root)
                        case.engine._tried(record,'budget-fixture',home.now(),1,'kept',dollars=21)
                        case.engine._store(root,record)
                    return desk.as_json(200,case.engine.view(root))
                return super().write(path,sent)
        web=desk.Desk(page=lambda port:SpendingPage(port,case.engine));web.start()
        print(json.dumps({'url':web.url,'path':str(root)}),flush=True)
        done=threading.Event()
        signal.signal(signal.SIGTERM,lambda *_:done.set());signal.signal(signal.SIGINT,lambda *_:done.set())
        done.wait()
    finally:
        if web:web.stop()
        case.doCleanups()


if __name__=='__main__':main()
