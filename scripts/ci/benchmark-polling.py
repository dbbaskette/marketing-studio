#!/usr/bin/env python3
"""Synthetic metadata benchmark; client read counts use the native 60-second policy."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'core'))
from studio_core import polling


def measure(module, root, files):
    engine=SimpleNamespace(workspace=SimpleNamespace(root=root/'workspace'),_lock=threading.RLock(),_runs={})
    samples=[];reads=0;revision=None;last_full=-60;signal_bytes=0
    # The synthetic body is encoded once; this models transfer counts, not native
    # HTTP latency. Native endpoint timings are recorded separately.
    payload=json.dumps({'slides':[{'id':n,'text':'Synthetic words. '*128} for n in range(30)]}).encode()
    for tick in range(30):
        began=time.perf_counter();signal=module.snapshot(engine,root/'private');samples.append((time.perf_counter()-began)*1000)
        signal_bytes+=len(json.dumps(signal).encode())
        now=tick*5
        if not (signal['revision']==revision and (signal['complete'] or signal.get('cached')) and not signal['active'] and now-last_full<60):
            reads+=1;last_full=now
        revision=signal['revision']
    target=files[-1];target.write_text(target.read_text()+' external edit')
    visible=None
    for attempt in range(1,16):
        signal=module.snapshot(engine,root/'private')
        if not (signal['revision']==revision and (signal['complete'] or signal.get('cached')) and not signal['active'] and 150+attempt*5-last_full<60):
            visible=attempt;break
    scan=getattr(engine,'_polling_scan',None)
    if scan:scan.close()
    return {'median_signal_ms':round(statistics.median(samples),3),'max_signal_ms':round(max(samples),3),
            'authoritative_reads':reads,'modeled_authoritative_bytes':reads*len(payload),
            'signal_bytes':signal_bytes,'edit_visible_after_authoritative_probe':visible}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True);args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('polling_before',args.baseline);before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    results=[]
    with tempfile.TemporaryDirectory(prefix='polling-benchmark-') as tmp:
        root=Path(tmp);(root/'private').mkdir();space=root/'workspace';space.mkdir()
        previous=os.environ.get('STUDIOS_CONFIG');os.environ['STUDIOS_CONFIG']=str(root/'settings.json')
        try:
            for count,projects in [(100,1),(6000,1),(20000,100)]:
                import shutil
                shutil.rmtree(space);space.mkdir();files=[]
                for n in range(count):
                    folder=space/f'project-{n%projects:03d}'/'assets';folder.mkdir(parents=True,exist_ok=True)
                    file=folder/f'asset-{n:06d}.txt';file.write_text('Synthetic asset');files.append(file)
                repeats=[]
                for _ in range(3):repeats.append({'before':measure(before,root,files),'after':measure(polling,root,files)})
                results.append({'files':count,'projects':projects,'repeats':repeats})
        finally:
            if previous is None:os.environ.pop('STUDIOS_CONFIG',None)
            else:os.environ['STUDIOS_CONFIG']=previous
    print(json.dumps({'scope':'Synthetic local metadata; 30 probes at modeled five-second intervals, three repetitions. Transfer counts are modeled using an encoded synthetic 30-slide payload, not measured production traffic.','results':results},indent=2))


if __name__=='__main__':main()
