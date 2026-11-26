"""A real native desk with a controllable scripted guide worker; no user state.

`--research STATE` shows a synthetic research progress snapshot instead of the creator's
saved choices, to look at the units doing the work (#379): `check` (the check in parts, one
working), `brief` (the final brief being written), `failed` (a part of the check failed),
`stopped` (a stopped check), `correction` (a correction round gathering again: what it redoes
is not called kept) or `legacy` (a snapshot saved before units)."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import signal
import sys
import threading
from unittest import mock

native = Path(__file__).resolve().parents[1] / 'studios/training'
sys.path[:0] = [str(native / 'tests'), str(native)]
from runner_support import StudioCase
from runner import page
from studio_core import preferences, studios_config
import desk
from studio_core import research_transport

asked = argparse.ArgumentParser()
asked.add_argument('--research', choices=('check', 'brief', 'failed', 'stopped', 'correction', 'legacy'))
chosen = asked.parse_args().research


def snapshot(state):
    """A synthetic progress snapshot as research_run.Run reports it; no real research."""
    ago = lambda seconds: (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat().replace('+00:00', 'Z')
    questions = ['Which synthetic deployment pattern keeps every instance reachable while one of them restarts?',
                 'What starts the next synthetic batch?', 'How are synthetic retries counted?',
                 'Which synthetic settings change the result?']
    streams = [{'id': f'area-{n}', 'questions': [q], 'status': 'kept', 'attempts': 1, 'seconds': 40 + 9 * n}
               for n, q in enumerate(questions)]
    combining = [{'id': f'area-{n}', 'questions': [{'id': f'q{n}', 'question': q}], 'status': 'kept',
                  'attempts': 2 if n == 1 else 1, 'seconds': 70 + 11 * n} for n, q in enumerate(questions)]
    timing = {'elapsed_seconds': 840, 'active_seconds': 700, 'assistant_seconds': 1500, 'incomplete': False}
    if state == 'legacy':
        return {'phase': 'review', 'round': 1, 'workstreams': [{'id': s['id'], 'questions': s['questions'],
                'status': 'accepted'} for s in streams], 'combining': [{k: row[k] for k in ('id', 'questions', 'status')}
                for row in combining]}
    if state == 'brief':
        return {'schema': 1, 'phase': 'synthesize', 'round': 1, 'round_limit': 3, 'streams': streams,
                'combining': combining, 'final_brief': {'status': 'working', 'attempts': 1, 'seconds': 35, 'started_at': ago(35)},
                'agents': {'count': 1, 'unconfirmed': 0, 'active': [{'id': 'final-writer-x', 'phase': 'synthesize',
                           'stream': 'final', 'section': 'final', 'status': 'working'}]},
                'counts': {'gather': {'working': 0, 'waiting': 0, 'kept': 4, 'failed': 0, 'stopped': 0, 'total': 4},
                           'combine': {'working': 1, 'waiting': 0, 'kept': 4, 'failed': 0, 'stopped': 0, 'total': 5}},
                'timing': timing}
    units = [{'id': f'unit-{n:016x}', 'kind': 'content', 'label': q if len(q) <= 80 else q[:79].rstrip() + '…',
              'status': 'kept', 'attempts': 1, 'seconds': 50 + 7 * n} for n, q in enumerate(questions)]
    units.append({'id': 'final', 'kind': 'final', 'label': 'the whole research', 'status': 'waiting'})
    agents = {'count': 0, 'unconfirmed': 0, 'active': []}
    if state == 'check':
        units[1].update(status='working', seconds=75, started_at=ago(75))
        units[2].update(status='kept', attempts=2)
        units[3].update(status='waiting'); units[3].pop('seconds')
        agents = {'count': 1, 'unconfirmed': 0, 'active': [{'id': 'reviewer-x', 'phase': 'review', 'stream': None,
                  'section': units[1]['id'], 'unit': units[1]['id'], 'status': 'working'}]}
    if state == 'failed':
        units[2].update(status='failed', attempts=1, seconds=95)
    if state == 'correction':
        streams[1].update(status='working', attempts=2, seconds=12, started_at=ago(12))
        combining[1].update(status='waiting', again=True)
        for unit in units:
            unit.update(status='waiting', again=True); unit.pop('seconds', None)
        return {'schema': 1, 'phase': 'investigate', 'round': 2, 'round_limit': 3, 'streams': streams,
                'combining': combining, 'final_brief': {'status': 'waiting', 'again': True, 'attempts': 1, 'seconds': 52},
                'review_units': units, 'timing': timing,
                'agents': {'count': 1, 'unconfirmed': 0, 'active': [{'id': 'investigator-x', 'phase': 'investigate',
                           'stream': 'area-1', 'section': None, 'status': 'working'}]},
                'correction': {'areas': ['area-1'], 'notes': ['Synthetic: one fact needs a narrower claim.']},
                'counts': {'gather': {'working': 1, 'waiting': 0, 'kept': 3, 'failed': 0, 'stopped': 0, 'total': 4},
                           'combine': {'working': 0, 'waiting': 2, 'kept': 3, 'failed': 0, 'stopped': 0, 'total': 5},
                           'check': {'working': 0, 'waiting': 5, 'kept': 0, 'failed': 0, 'stopped': 0, 'total': 5}}}
    if state == 'stopped':
        units[2].update(status='stopped', seconds=30); units[3].update(status='waiting'); units[3].pop('seconds')
    tally = {key: sum(u['status'] == key for u in units) for key in ('waiting', 'kept', 'failed', 'stopped')}
    shown = {'schema': 1, 'phase': 'stopped' if state == 'stopped' else 'review', 'round': 1, 'round_limit': 3,
             'streams': streams, 'combining': combining, 'final_brief': {'status': 'kept', 'attempts': 1, 'seconds': 52},
             'review_units': units, 'agents': agents, 'timing': timing,
             'counts': {'gather': {'working': 0, 'waiting': 0, 'kept': 4, 'failed': 0, 'stopped': 0, 'total': 4},
                        'combine': {'working': 0, 'waiting': 0, 'kept': 5, 'failed': 0, 'stopped': 0, 'total': 5},
                        'check': {'working': len(agents['active']), **tally, 'total': len(units)}}}
    if state in ('failed', 'stopped'):
        how = 'failed' if state == 'failed' else 'stopped'
        kept = sum(u['status'] == 'kept' for u in units)
        shown['ended_in'] = {'part': 'review-unit', 'how': how, 'label': units[2]['label'], 'kept': kept,
                             'total': len(units), 'said': research_transport.ended_words(
                                 'review-unit', how, label=units[2]['label'], kept=kept, total=len(units),
                                 detail='' if state == 'stopped' else 'Synthetic unit check failed.')}
    return shown


case = StudioCase()
web = None
release, entered = threading.Event(), threading.Event()
try:
    case.setUp()
    studios_config.update({'local': {'root': str(case.space.root)}})
    preferences.finish(studios_config, lambda _: None)
    catalog = mock.patch('studio_core.model_catalog.Catalog.get', return_value={'agent': 'codex', 'models': [], 'problem': None})
    catalog.start(); case.addCleanup(catalog.stop)

    def guide(tools, job):
        root = case.engine.trainings()[0]
        with case.engine.files:
            record = case.engine._load(root)
            # This fixture isolates the UI handoff. Creator receipt semantics have
            # separate native coverage; no synthetic choice is presented as checked.
            record['research_execution'] = {'progress': snapshot(chosen) if chosen else {
                'phase': 'creator-approved', 'agents': {'count': 0, 'active': []}}}
            case.engine._store(root, record)
        entered.set()
        while not release.wait(0.05):
            if case.engine._run(root).stop.is_set():
                return
        return case.workers.document(tools, job)

    case.workers.then('document', guide)
    case.engine.background = True
    root = case.start(levels=['101', '201'], materials=['document', 'brief'])
    if not entered.wait(30):
        raise RuntimeError('The scripted guide worker did not start')

    class Fixture(page.RunnerPage):
        reads = (*page.RunnerPage.reads, '/api/fixture-progress-state')
        def read(self, address, one):
            if address == '/api/fixture-progress-state':
                return desk.as_json(200, {'jobs': len(case.workers.jobs)})
            return super().read(address, one)

    web = desk.Desk(page=lambda port: Fixture(port, case.engine)); web.start()
    print(json.dumps({'url': web.url, 'path': str(root)}), flush=True)
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    done.wait()
finally:
    release.set()
    if web: web.stop()
    case.doCleanups()
