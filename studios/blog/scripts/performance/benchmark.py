#!/usr/bin/env python3
"""Synthetic local workflow benchmark. No accounts, network providers, or model calls."""
import argparse
import cProfile
import json
from pathlib import Path
import platform
import pstats
import statistics
import sys
import time
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'tests'), str(REPO / 'skills/blog-studio/scripts')]
from test_google_workflow import GoogleWorkflowTests
from hub_fixtures import FakeProvider
from hub import Registry
from hub_workspace import Workspace
import studio
import experience
import author_workflow
import text_checks


def measure(operation):
    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    result = operation()
    profiler.disable()
    elapsed = time.perf_counter() - start
    stats = pstats.Stats(profiler)
    calls = {'read_text': 0, 'read_bytes': 0, 'subprocess_run': 0}
    for (filename, _, name), (_, count, _, _, _) in stats.stats.items():
        if name in ('read_text', 'read_bytes'): calls[name] += count
        if name == 'run' and Path(filename).name == 'subprocess.py': calls['subprocess_run'] += count
    phases = sorted(({'function': key[2], 'self_seconds': round(value[2], 6), 'calls': value[1]}
                     for key, value in stats.stats.items()), key=lambda v: v['self_seconds'], reverse=True)[:8]
    return {'elapsed_seconds': round(elapsed, 6), 'local_phases': phases, 'calls': calls,
            'response_characters': len(json.dumps(result, default=str)),
            'measured_model_tokens': None, 'provider_seconds': None, 'model_seconds': None,
            'harness_tool_calls': None}


def run(repeats=3, optimized=False):
    fixture = GoogleWorkflowTests();fixture.setUp()
    try:
        words = [f'word{n}' for n in range(400)]
        text = '# Synthetic technical blog\n\n' + '\n\n'.join(
            f'## Section {n}\n\n' + ' '.join(words[n:n+90]) + '.' for n in range(24))
        fixture.save('draft', text)
        for n in range(40):
            source = fixture.run_command('source','add','--name',f'Synthetic source {n}',
                '--file',fixture.file(text), '--purpose','reference')
            fixture.run_command('article','attach','--id',fixture.aid,'--source',source['id'])
        fixture.run_command('article','review','--id',fixture.aid,'--check','factual-support',
            '--status','current','--file',fixture.file({'findings':[]},'.json'))
        fixture.handoff()
        provider = FakeProvider(fixture.base/'remotes')
        registry = Registry(fixture.base/'hubs', provider)
        hid = registry.create('fixture/performance','Synthetic performance')['hub']
        adapter = Workspace(fixture.root, registry.hub(hid))
        adapter.publish_selected({'articles':[fixture.aid]})
        def resume():
            if optimized:
                import performance
                return performance.resume(fixture.root, fixture.aid)
            return {'context': experience.context(fixture.root,fixture.aid),
                    'status': author_workflow.status(fixture.root,fixture.aid)}
        def proofread():
            if optimized:
                import performance
                return performance.check(fixture.root, fixture.aid, {'no_em_dashes':True})
            return text_checks.lint(text, {'no_em_dashes':True})
        def push():
            prepared = fixture.run_command('google','prepare','--id',fixture.aid,*fixture.obs())
            return fixture.run_command('google','confirm','--id',fixture.aid,'--transfer',prepared['transfer'],*fixture.obs())
        def pull():
            inputs = fixture.obs()
            compared = fixture.run_command('google','compare','--id',fixture.aid,*inputs)
            return fixture.run_command('google','accept','--id',fixture.aid,*inputs,'--expected-comparison',compared['comparison'])
        def sync(): return adapter.publish_selected({'articles':[fixture.aid]})
        rows = {}
        with patch('hub_workspace.active',return_value=adapter):
            for name, operation in [('resume',resume),('proofread-mechanical',proofread),('push-checkpoint',push),('pull-checkpoint',pull),('hub-sync',sync)]:
                samples = [measure(operation) for _ in range(repeats+1)]
                rows[name] = {'cold':samples[0], 'warm':samples[1:],
                              'warm_median_seconds':statistics.median(x['elapsed_seconds'] for x in samples[1:])}
        refs = ('references/workspace/resume.md','references/modules/copy-editing.md',
                'references/modules/blog-google-handoff.md','references/modules/blog-google-return.md','references/hub/sync.md')
        guidance = sum(len((REPO/'skills/blog-studio'/p).read_text()) for p in refs)
        return {'schema':1, 'environment':{'python':platform.python_version(),'os':platform.system(),
                'release':platform.release(),'machine':platform.machine()},'optimized':optimized,
                'workload':{'sections':24,'sources':40,'draft_characters':len(text),'warm_repeats':repeats},
                'runtime_source_sha256':studio.digest(b''.join(p.read_bytes() for p in sorted((REPO/'skills/blog-studio/scripts').glob('*.py')))),
                'selected_guidance_characters':guidance,'selected_guidance_character_token_estimate':round(guidance/4),
                'notes':['Synthetic local fixtures only; Google operations measure checkpoint logic, not live transfers.',
                         'Hub uses local bare Git repositories. Timings include profiler overhead.',
                         'Cold is first operation in a prepared process, not a flushed OS cache.',
                         'Missing model/provider metrics are unavailable, not zero. Character estimates are not billing.',
                         'No manuscript, identity, credential, provider output, or absolute workspace paths recorded.'],
                'operations':rows}
    finally: fixture.doCleanups()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--optimized',action='store_true')
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if not 2 <= args.repeats <= 10: parser.error('Use 2–10 warm repetitions.')
    result=run(args.repeats,args.optimized)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n');args.output.chmod(0o600)
    print(json.dumps({k:round(v['warm_median_seconds'],4) for k,v in result['operations'].items()}))
