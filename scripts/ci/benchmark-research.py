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
    from test_research_session import SessionTests
    case = SessionTests()
    case.setUp()
    case.task['planning_questions'] = [{'id': f'q{i}', 'question': f'Synthetic question {i}'} for i in range(9)]
    case.barrier = None
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
        facts, _ = case.workflow.run(case.root, case.task, case.invoke, limit=workers)
        elapsed = time.monotonic() - start
        collection = [row for row in intervals if row[0] == 'investigate']
        return {'workers': workers, 'questions': 9, 'facts': len(facts['facts']),
                'whole_seconds': round(elapsed, 4),
                'collection_seconds': round(max(r[2] for r in collection) - min(r[1] for r in collection), 4),
                'synthesis_review_seconds': round(sum(end - began for phase, began, end in intervals if phase != 'investigate'), 4),
                'tokens': None, 'dollars': None, 'failures': 0}
    finally:
        case.doCleanups()


UNIT_SECONDS = .5   # the synthetic work of checking one unit's items, the same in every mode


def measure_check(runtime, mode):
    """The independent check of six approved sections (six content units and the final unit)
    with equivalent synthetic work: `single` is one reviewer doing every unit's work, `1` and
    `3` are review units one or three at a time (issue #378)."""
    os.environ['STUDIO_TEST_RESEARCH_RUNTIME'] = str(runtime)
    from test_research_units import UnitCheckTests
    from synthesis_fixture import review
    case = UnitCheckTests()
    case.setUp()
    case.task['planning_questions'] = [{'id': f'question-{i}', 'question': f'Synthetic question {i}'} for i in range(6)]
    case.pause = UNIT_SECONDS
    original = case.invoke
    intervals, read = [], []

    def invoke(phase, guidance, payload, sources, fetch):
        if phase != 'review':
            return original(phase, guidance, payload, sources, fetch)
        start = time.monotonic()
        if 'assignment' in payload:
            result = original(phase, guidance, payload, sources, fetch)
            read.append((payload['_execution']['unit'], sorted(source['file'] for source in sources)))
        else:   # one reviewer: every content unit's work and the final's, one after another
            time.sleep(UNIT_SECONDS * (len(case.task['planning_questions']) + 1))
            result = json.dumps(review(payload['review_template'])), []
            read.append(('single', sorted(source['file'] for source in sources)))
        intervals.append((start, time.monotonic()))
        return result

    case.invoke = invoke
    if mode == 'single':
        case.units = None
    try:
        facts, _ = case.run_units(limit=1 if mode == '1' else 3)
        content = [files for unit, files in read if unit not in ('final', 'single')]
        counted = {}
        for files in content:
            for file in files:
                counted[file] = counted.get(file, 0) + 1
        everything = {}
        for _, files in read:
            for file in files:
                everything[file] = everything.get(file, 0) + 1
        return {'mode': mode, 'accepted': facts['review']['accepted'], 'review_jobs': len(read),
                'check_seconds': round(max(end for _, end in intervals) - min(start for start, _ in intervals), 4),
                'sources': len(facts['sources']),
                'sources_read_by_more_than_one_content_unit': sum(count > 1 for count in counted.values()),
                'sources_read_by_more_than_one_job': sum(count > 1 for count in everything.values()),
                'source_reads': sum(everything.values()), 'tokens': None, 'dollars': None}
    finally:
        case.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True, help='Exactly pinned disposable test helper')
    parser.add_argument('--check-only', action='store_true', help='Measure only the independent check')
    args = parser.parse_args()
    if not (args.runtime / 'scripts/harness-research.mjs').is_file():
        parser.error('Prepare a disposable pinned test helper first.')
    result = {'kind': 'synthetic-only', 'provider_jobs': 0}
    if not args.check_only:
        runs = [measure(args.runtime, workers) for _ in range(3) for workers in (1, 3)]
        result.update(runs=runs, medians={str(workers): {key: round(statistics.median(r[key] for r in runs if r['workers'] == workers), 4)
                    for key in ('collection_seconds', 'synthesis_review_seconds', 'whole_seconds')}
                   for workers in (1, 3)})
    import marketing_studio  # noqa: F401  (puts studio_core on the path)
    from studio_core import research_units
    if research_units.capability(args.runtime):
        checks = [measure_check(args.runtime, mode) for _ in range(3) for mode in ('single', '1', '3')]
        result.update(checks=checks, check_medians={mode: {key: statistics.median(r[key] for r in checks if r['mode'] == mode)
                      for key in ('check_seconds', 'review_jobs', 'source_reads', 'sources_read_by_more_than_one_content_unit',
                                  'sources_read_by_more_than_one_job')}
                     for mode in ('single', '1', '3')})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
