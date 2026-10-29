#!/usr/bin/env python3
"""Equivalent synthetic collection load, never a live provider speed estimate."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]


def measure(runtime, workers):
    os.environ['STUDIO_TEST_RESEARCH_RUNTIME'] = str(runtime)
    from test_research_parallel import ParallelWorkflowTests
    case = ParallelWorkflowTests()
    case.setUp()
    case.task['planning_questions'] = [{'id': f'q{i}', 'question': f'Synthetic question {i}'} for i in range(9)]
    original = case.invoke
    intervals = []

    def invoke(phase, guidance, payload, sources, fetch):
        start = time.monotonic()
        if phase == 'investigate':
            time.sleep(.08 * len(payload['questions']))
        result, captures = original(phase, guidance, payload, sources, fetch)
        if phase == 'investigate':
            # Equal numbers of questions, facts and captured source bytes in both modes.
            dossier = json.loads(result)
            template = dossier['facts'][0]
            dossier['facts'] = [{**template, 'id': question['id']} for question in payload['questions']]
            result = json.dumps(dossier)
        else:
            time.sleep(.06)  # Equal synthetic composition/check delay in both modes.
        intervals.append((phase, start, time.monotonic()))
        return result, captures

    case.invoke = invoke
    start = time.monotonic()
    try:
        facts, _ = case.run_workflow(limit=workers)
        elapsed = time.monotonic() - start
        collection = [row for row in intervals if row[0] == 'investigate']
        return {'workers': workers, 'questions': 9, 'facts': len(facts['facts']),
                'whole_seconds': round(elapsed, 4),
                'collection_seconds': round(max(r[2] for r in collection) - min(r[1] for r in collection), 4),
                'synthesis_review_seconds': round(sum(end - began for phase, began, end in intervals if phase != 'investigate'), 4),
                'tokens': None, 'dollars': None, 'failures': 0}
    finally:
        case.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True, help='Exactly pinned disposable test helper')
    args = parser.parse_args()
    if not (args.runtime / 'scripts/harness-research.mjs').is_file():
        parser.error('Prepare a disposable pinned test helper first.')
    runs = [measure(args.runtime, workers) for _ in range(3) for workers in (1, 3)]
    medians = {str(workers): {key: round(statistics.median(r[key] for r in runs if r['workers'] == workers), 4)
                for key in ('collection_seconds', 'synthesis_review_seconds', 'whole_seconds')}
               for workers in (1, 3)}
    print(json.dumps({'kind': 'synthetic-only', 'provider_jobs': 0, 'runs': runs, 'medians': medians}, indent=2))


if __name__ == '__main__':
    main()
