"""Real native page, disposable saved scene and a single local preview failure."""
import contextlib
import json
from pathlib import Path
import signal
import sys
import threading
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from helpers import Isolated
import test_desk_engine as fixtures
from runner import server
from studio_core import preferences, studios_config


def main():
    case=Isolated();web=None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            case.setUp();fixtures.setup_desk(case)
            studios_config.update({'assistant':{'agent':'codex'},'local':{'root':str(case.workspace)},'person':{'name':'Synthetic author'}})
            preferences.finish(studios_config,lambda _:None)
            case.engine.assistant=mock.Mock()
            first=True
            def renderer(*args,**kwargs):
                nonlocal first
                if first:first=False;raise RuntimeError('Synthetic preview failure; private details stay local')
                return fixtures.fake_renderer(*args,**kwargs)
            case.engine.renderer=renderer
        web=server.desk(case.store,engine=case.engine);web.start()
        print(json.dumps({'url':web.url,'id':case.ident}),flush=True)
        done=threading.Event();signal.signal(signal.SIGTERM,lambda *_:done.set());signal.signal(signal.SIGINT,lambda *_:done.set());done.wait()
        assert case.engine.assistant.mock_calls==[],case.engine.assistant.mock_calls
        assert case.store.read(case.ident)['attempts']==[]
    finally:
        if web:web.stop()
        case.doCleanups()


if __name__=='__main__':main()
