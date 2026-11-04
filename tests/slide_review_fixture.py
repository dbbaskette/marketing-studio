"""Real slide-review pages, private state and fake native workers only."""
import argparse
import contextlib
from copy import deepcopy
import json
from pathlib import Path
import signal
import sys
import threading
from unittest import mock


def main():
    parser=argparse.ArgumentParser();parser.add_argument('product',choices=('training','presentation'));parser.add_argument('--slides',type=int,choices=(6,30),default=6)
    args=parser.parse_args();native=Path(__file__).resolve().parents[1]/'studios'/args.product
    sys.path.insert(0,str(native/'tests'));sys.path.insert(1,str(native))
    from runner import page
    if args.product=='training':
        from test_runner_deck import PageCase
        import desk as protocol
        case=PageCase()
    else:
        from runner_support import DeskCase
        import server as protocol
        case=DeskCase()
    web=None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            case.setUp();case.engine.content_first=True
            from studio_core import preferences,studios_config
            studios_config.update({'local':{'root':str(case.space.root)}});preferences.finish(studios_config,lambda _:None)
            catalog=mock.patch('studio_core.model_catalog.Catalog.get',return_value={'agent':'codex','models':[],'problem':None});catalog.start();case.addCleanup(catalog.stop)
            root=case.begin(flow='desk') if args.product=='training' else case.start_desk(look='default')
            if args.slides==30 or args.product=='presentation':
                if args.product=='training':
                    from runner import pipeline
                    import workspace
                    target=pipeline.place(root,None,pipeline.OUTLINE)
                else:target=root/'outline.json'
                value=json.loads(target.read_text());original=value['slides'];middle=[]
                for number in range(args.slides-2):
                    copy=deepcopy(original[1:-1][number%len(original[1:-1])]);copy['id']+='-copy-'+str(number);copy['title']+=' '+str(number+1);middle.append(copy)
                value['slides']=[original[0],*middle,original[-1]]
                if args.product=='training':
                    target.write_text(json.dumps(value));record=case.engine._load(root);checksum=workspace.sha256_file(target)
                    record['deck']['']['outline']['sha256']=checksum;record['deck']['']['waiting']['sha256']=checksum
                    case.engine._store(root,record)
                else:
                    record=case.engine._load(root);case.engine._edit_outline(root,record,value['slides']);case.engine._store(root,record)
        class Fixture(page.RunnerPage):
            reads=(*page.RunnerPage.reads,'/api/fixture-review-state')
            def read(self,address,one):
                if address=='/api/fixture-review-state':
                    return protocol.as_json(200,{'jobs':len(case.workers.jobs)})
                return super().read(address,one)
        web=protocol.Desk(page=lambda port:Fixture(port,case.engine));web.start()
        print(json.dumps({'url':web.url,'path':str(root),'slides':args.slides}),flush=True)
        done=threading.Event();signal.signal(signal.SIGTERM,lambda *_:done.set());signal.signal(signal.SIGINT,lambda *_:done.set());done.wait()
    finally:
        if web:web.stop()
        case.doCleanups()


if __name__=='__main__':main()
