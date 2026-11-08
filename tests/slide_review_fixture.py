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
    parser.add_argument('--research-preview',action='store_true')
    parser.add_argument('--poll-files',type=int,default=0)
    parser.add_argument('--rendered',action='store_true')
    parser.add_argument('--review-fixes',action='store_true',help='Five synthetic suggestions on one Training Studio slide')
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
            case.setUp();case.engine.content_first=not args.rendered
            if args.review_fixes:
                if args.product!='training' or not args.rendered:
                    parser.error('--review-fixes requires training --rendered')
                from test_runner_deck import MAJOR
                case.workers.found=[[{**MAJOR,'slide':'check-yourself',
                    'note':f'Detail {number} needs attention.',
                    'fix':f'Make detail {number} easier to read.'} for number in range(1,6)],[]]
            from studio_core import preferences,studios_config
            studios_config.update({'local':{'root':str(case.space.root)}});preferences.finish(studios_config,lambda _:None)
            catalog=mock.patch('studio_core.model_catalog.Catalog.get',return_value={'agent':'codex','models':[],'problem':None});catalog.start();case.addCleanup(catalog.stop)
            root=case.begin(flow='desk') if args.product=='training' else case.start_desk(look='default')
            if args.rendered and args.product=='training':
                case.to_end(root)
            elif args.rendered:
                case.on_desk(root)
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
        if args.research_preview:
            record=case.engine._load(root)
            preview={'basis':'synthetic-section-basis','digest':'synthetic-display-digest','sections':[{'title':'Saved section','text':'Synthetic section prose is available before final checking.'}],'sources':[{'title':'Selected fixture source','permission':'selected'}]}
            record['research_execution']={'progress':{'phase':'review','first_readable_seconds':2,'combining':[{'id':'area1','questions':['Synthetic question'],'status':'kept','preview':preview},{'id':'area2','questions':['Sibling question'],'status':'failed'}]}}
            case.engine._store(root,record)
        if args.poll_files:
            assets=case.space.root/'synthetic-other-project-assets';assets.mkdir()
            for number in range(args.poll_files):
                (assets/f'asset-{number:06d}.txt').write_text('Synthetic metadata benchmark')
        reads_count={}
        class Fixture(page.RunnerPage):
            reads=(*page.RunnerPage.reads,'/api/fixture-review-state','/api/fixture-research-stage')
            def read(self,address,one):
                if address=='/api/fixture-research-stage':
                    record=case.engine._load(root);progress=record['research_execution']['progress'];phase=one('phase')
                    if phase=='complete':progress.update(phase='complete',checked_result_seconds=9)
                    elif phase=='changed':progress['combining'][0]['preview']['basis']='changed-section-basis'
                    case.engine._store(root,record)
                    return protocol.as_json(200,{'ok':True})
                if address=='/api/fixture-review-state':
                    return protocol.as_json(200,{'jobs':len(case.workers.jobs),'reads':dict(reads_count)})
                reads_count[address]=reads_count.get(address,0)+1
                return super().read(address,one)
        web=protocol.Desk(page=lambda port:Fixture(port,case.engine));web.start()
        print(json.dumps({'url':web.url,'path':str(root),'slides':args.slides}),flush=True)
        done=threading.Event();signal.signal(signal.SIGTERM,lambda *_:done.set());signal.signal(signal.SIGINT,lambda *_:done.set());done.wait()
    finally:
        if web:web.stop()
        case.doCleanups()


if __name__=='__main__':main()
