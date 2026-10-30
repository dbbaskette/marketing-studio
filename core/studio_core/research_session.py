"""Shared host coordination over Harness Research's portable collection contract.

The helper owns packets, evidence assembly and digest validation. The host owns
isolated invocations, source access, capacity, allowance and terminal observation.
"""
from __future__ import annotations

import copy
import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

from studio_core import research_contract as rc, research_timing

PROTOCOL = 'harness-collection-v1'
RECORD_SCHEMA = 5  # Training Studio's new execution record; other adapters version their own.
PENDING = 'Synthesis and independent review are pending.'
EVIDENCE = ('Investigate only your assigned questions within the supplied task and source policy. '
            'Return schema 2 JSON containing only sources, facts and gaps (an array of strings). '
            'Each fact contains only id, statement, author and citations. Each citation contains '
            'source, quote and optional locator. kind belongs to synthesis prose, never a fact '
            'or citation. Put unsupported or inferred material in gaps; never upgrade it to a fact. '
            'Preserve counterevidence and limitations. Set every fact author to this worker ID. '
            'The host registers your actual invocation and capture receipts. You cannot register '
            'permissions or approve your own evidence. ' + rc.CAPTURED + ' ' + rc.SOURCE_IDS)
COMPOSE = ('Write connected findings, report sections and an authored brief from the immutable '
           'evidence. Return schema 2 JSON containing findings, sections, brief and optional '
           'comparisons only. The host includes the registered sources/facts unchanged. '
           'Preserve actual investigators and gaps; request registered investigation for new facts. ')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def capability(runtime):
    runtime = Path(runtime)
    needed = ['scripts/lib/collection.mjs', 'scripts/lib/topic-assets.mjs',
              'references/collection.schema.json', 'references/investigation-packet.md',
              'references/parallel-research.md']
    if not all((runtime / name).is_file() for name in needed):
        return None
    schema = json.loads((runtime / 'references/collection.schema.json').read_text())
    if schema.get('$schema') is None:
        return None
    paths = sorted([runtime / 'package.json', *runtime.glob('scripts/**/*.mjs'),
                    *(p for p in runtime.glob('references/**/*') if p.is_file())])
    return {'protocol': PROTOCOL, 'digest': digest([[str(p.relative_to(runtime)),
            hashlib.sha256(p.read_bytes()).hexdigest()] for p in paths])}


def execution(runtime, workers=3):
    supported = capability(runtime)
    return {'schema': 1, 'protocol': PROTOCOL, 'workers': min(3, max(1, int(workers))),
            'capability': supported} if supported else None


def protocol(record):
    held = record.get('research_execution') or {}
    return isinstance(held, dict) and held.get('schema') == 1 and held.get('protocol') == PROTOCOL \
        and type(held.get('workers')) is int and 1 <= held['workers'] <= 3 \
        and isinstance(held.get('capability'), dict) and held['capability'].get('protocol') == PROTOCOL


def enabled(record, task=None):
    return protocol(record)


def preparation(value, spec):
    if spec.get('research_mode') == 'evidence':
        if set(value) - {'schema', 'sources', 'facts', 'gaps'}:
            raise ValueError('Return sources, facts and gaps only; synthesis writes the report.')
        if not isinstance(value.get('sources'), list) or not isinstance(value.get('facts'), list):
            raise ValueError('Return sources and facts as arrays.')
        gaps = value.get('gaps', [])
        if not isinstance(gaps, list) or any(not isinstance(g, str) or not g.strip() for g in gaps):
            raise ValueError('Return gaps as an array of nonempty strings.')
        return {**{k: v for k, v in value.items() if k != 'gaps'}, **spec['task'], 'findings': [],
                'sections': [{'id': 'collection', 'title': 'Evidence collection', 'blocks': [
                    {'text': g, 'kind': 'gap', 'refs': []} for g in gaps] or [
                    {'text': PENDING, 'kind': 'gap', 'refs': []}]}]}
    if spec.get('research_mode') == 'compose':
        if set(value) - {'schema', 'findings', 'sections', 'brief', 'comparisons'}:
            raise ValueError('Return findings, sections, brief and optional comparisons only. Evidence is kept unchanged.')
        for name in ('findings', 'sections', 'brief'):
            if not isinstance(value.get(name), list) or not value[name]:
                raise ValueError(f'Return {name} as a nonempty array.')
        return {**copy.deepcopy(spec['evidence_base']), **value}
    return value


def evidence_gaps(value):
    """The exact gap strings sent in a collection packet, including prepared evidence."""
    return value.get('gaps') or [block['text'] for section in value.get('sections', [])
        for block in section.get('blocks', []) if block.get('kind') == 'gap'
        and not (section.get('id') == 'collection' and block.get('text') == PENDING)]


def check_frozen(value, spec):
    base = spec.get('evidence_base')
    if not isinstance(base, dict):
        return None
    return [] if all(value.get(k) == base.get(k) for k in ('sources', 'facts')) else [
        'Synthesis must preserve the registered evidence and its actual investigators.']


def streams(task, limit=3):
    questions = task.get('planning_questions') or [{'id': 'scope', 'question': task['scope']}]
    if isinstance(questions, dict):
        questions = [{'id': k, 'question': v} for k, v in questions.items()]
    if not isinstance(questions, list) or not questions:
        raise ValueError('Research needs an approved scope or questions.')
    count = min(3, max(1, int(limit)), len(questions))
    return [{'id': f'area{i + 1}', 'questions': copy.deepcopy(questions[i::count])} for i in range(count)]


def bytes_of(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Research captures must be ordinary files, not links.')
    return path.read_bytes()


def case_for(root):
    """A confined owned pointer, never a user-supplied absolute handoff path."""
    base = rc.inside(root, str(rc.CASE))
    pointer = base / 'current.json'
    if not pointer.is_file():
        return base
    value = json.loads(bytes_of(pointer))
    if not re.fullmatch('[a-f0-9]{64}', str(value.get('basis', ''))):
        raise ValueError('The saved research location changed; preserve and inspect it.')
    return rc.inside(base, value['basis'] + '/topic')


def unresolved(root):
    """Capacity remains occupied across changed inputs until host termination is confirmed."""
    base = rc.inside(root, str(rc.CASE))
    if not base.exists(): return False
    for folder in base.iterdir():
        if not folder.is_dir() or folder.is_symlink() or not re.fullmatch('[a-f0-9]{64}', folder.name):
            continue
        path = rc.inside(base, folder.name + '/topic/.harness-research/studio-execution.json')
        if path.exists():
            host = json.loads(bytes_of(path))
            if host.get('schema') != 1 or not isinstance(host.get('attempts'), list):
                raise ValueError('The research host record is unreadable. Preserve it before retrying.')
            if any(not attempt.get('ended_at') for attempt in host['attempts']): return True
    return False


def corrections(review, registry):
    owners = {global_id: mapping['workstream'] for mapping in registry['mappings']
              for global_id in mapping['facts'].values()}
    selected = {owners[f['id']] for f in review.get('facts', [])
                if f.get('id') in owners and f.get('verdict') not in ('supported', 'pending')}
    if not selected and (review.get('assessment') or {}).get('coverage') == 'needs-revision':
        selected = set(owners.values())
    return selected


class Workflow:
    def __init__(self, runtime, call=None):
        self.runtime, self.call = Path(runtime), call
        self.lock = threading.RLock()
        self.helper = rc.Workflow(runtime, call)

    def command(self, root, group, action, value=None, **flags):
        with self.lock:
            args = [group, action, '--project', str(root)]
            if value is not None:
                name = '.harness-research/host-inputs/' + secrets.token_hex(12) + '.json'
                rc.write(root, name, json.dumps(value))
                args += ['--file', name]
            for key, val in flags.items():
                args += ['--' + key.replace('_', '-'), str(val)]
            if self.call:
                return self.call(*args)
            result = subprocess.run([shutil.which('node') or 'node',
                str(self.runtime / 'scripts/harness-research.mjs'), *args],
                capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
            if result.returncode:
                raise ValueError((result.stderr.strip().splitlines() or ['Harness Research did not finish.'])[-1])
            return json.loads(result.stdout)

    def asset(self, root, task, sources, basis):
        base = rc.inside(root, str(rc.CASE))
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Intermediate originals, receipts and host state never enter studio Git sharing.
        rc.write(base, '.gitignore', '*\n')
        area = rc.inside(base, basis)
        area.mkdir(exist_ok=True, mode=0o700)
        target, inputs = area / 'topic', area / 'inputs'
        inputs.mkdir(exist_ok=True, mode=0o700)
        selected, public, urls = [], [], []
        for source in sources:
            if source.get('permission', 'selected' if source.get('offered', True) else 'public') != 'selected':
                public.append(source)
                continue
            key = digest([source['file'], source.get('origin'), source['text']])[:32]
            suffix = Path(source.get('original', '')).suffix.lower() if source.get('original_path') else '.txt'
            suffix = suffix if re.fullmatch(r'\.[a-z0-9]{1,8}', suffix) else '.txt'
            filename = key + suffix
            data = bytes_of(source['original_path']) if source.get('original_path') else source['text'].encode()
            path = inputs / filename
            if path.exists() and bytes_of(path) != data:
                raise ValueError('The selected research input changed during capture.')
            if not path.exists(): rc.write(inputs, filename, data)
            origin = source.get('origin', source.get('url', ''))
            linked = urlsplit(origin).scheme in ('http', 'https')
            if linked: urls.append(origin)
            selected.append((source, filename, linked))
        if urls: rc.write(inputs, 'urls.txt', '\n'.join(urls) + '\n')
        if not target.exists():
            arguments = {'topic': task['topic'], 'audience': task['audience'], 'purpose': task['purpose'],
                         'destination': 'topic', 'source_mode': task['source_mode']}
            if selected: arguments['directory'] = str(inputs)
            self.command(area, 'asset', 'init', **arguments)
        inventory = json.loads((target / 'sources.json').read_text())['entries']
        offered = []
        for source, filename, linked in selected:
            origin = source.get('origin', source.get('url', ''))
            original = next(e for e in inventory if e.get('filename') == filename)
            entry = next(e for e in inventory if e.get('type') == 'url' and e['origin'] == origin) if linked else original
            file = 'sources/selected/' + filename + '.txt'
            rc.write(target, file, source['text'])
            self.command(target, 'asset', 'source', {'id': entry['id'], 'outcome': 'captured',
                'capture_file': file, 'accessed_at': source.get('accessed_at') or now(),
                'note': 'Selected studio capture; the remote original was not automatically refreshed.'})
            offered.append({**source, 'file': file, 'origin': entry['origin'], 'url': entry['origin'],
                'permission': 'selected', 'path': rc.inside(target, file),
                'original': original['original_file'], 'original_path': rc.inside(target, original['original_file'])})
        for source in public:
            if task['source_mode'] == 'selected':
                raise ValueError('Public captures need explicit external-search permission.')
            file = 'sources/public/' + digest([source['origin'], source['text']]) + '.txt'
            rc.write(target, file, source['text'])
            self.command(target, 'asset', 'source', {'id': 'public-' + digest([source['origin'], source['text']])[:32],
                'role': 'discovered', 'origin': source['origin'], 'permission': 'public', 'outcome': 'captured',
                'capture_file': file, 'accessed_at': source.get('accessed_at') or now()})
            offered.append({**source, 'file': file, 'path': rc.inside(target, file), 'permission': 'public'})
        rc.write(base, 'current.json', json.dumps({'schema': 1, 'basis': basis}))
        return target, offered

    def run(self, root, task, invoke, sources=(), *, limit=3, progress=lambda state: None,
            allowed=lambda: True, cancelled=lambda: False, readable=None, restart_stopped=False, **_):
        if capability(self.runtime) is None:
            raise ValueError('This workflow needs the complete Harness Research 1.1 collection runtime.')
        if unresolved(root):
            raise ValueError('An earlier research invocation has no confirmed terminal observation. Confirm it ended before retrying; saved evidence is kept.')
        areas = streams(task, limit)
        basis = digest([task, [[s.get('file'), s.get('origin'), s.get('permission'),
            hashlib.sha256(s['text'].encode()).hexdigest(),
            hashlib.sha256(bytes_of(s['original_path'])).hexdigest() if s.get('original_path') else None]
            for s in sources], capability(self.runtime), areas])
        case, offered = self.asset(root, task, sources, basis)
        host_file = '.harness-research/studio-execution.json'
        host_path = rc.inside(case, host_file)
        host = json.loads(bytes_of(host_path)) if host_path.exists() else {'schema': 1, 'started': now(), 'attempts': []}
        if any(not attempt.get('ended_at') for attempt in host['attempts']):
            raise ValueError('An earlier research invocation has no confirmed terminal observation. Confirm it ended before retrying; saved evidence is kept.')
        host_lock = threading.RLock()
        original_invoke = invoke
        def execute(phase, guidance, payload, offered, fetch):
            payload = copy.deepcopy(payload)
            payload.setdefault('_execution', {}).setdefault('invocation', 'research-invocation-' + secrets.token_hex(16))
            invocation = payload['_execution']['invocation']
            attempt = {'phase': phase, 'invocation': invocation, 'worker': payload['worker'],
                       'stream': payload['_execution'].get('stream'), 'started_at': now(), 'status': 'working'}
            with host_lock:
                host['attempts'].append(attempt)
                rc.write(case, host_file, json.dumps(host))
            confirmed = True
            try:
                report()
                return original_invoke(phase, guidance, payload, offered, fetch)
            except BaseException as error:
                confirmed = getattr(error, 'terminal_confirmed', True)
                raise
            finally:
                with host_lock:
                    attempt['status'] = 'finished' if confirmed else 'termination-unconfirmed'
                    if confirmed:
                        attempt['ended_at'] = now()
                        attempt['seconds'] = max(0, research_timing.stamp(attempt['ended_at']) - research_timing.stamp(attempt['started_at']))
                    rc.write(case, host_file, json.dumps(host))
                report()
        invoke = execute
        request = {'schema': 1, **{k: task[k] for k in rc.TASK_FIELDS},
                   'execution_mode': 'parallel' if limit > 1 else 'sequential',
                   'max_investigators': min(3, max(1, limit)),
                   'workstreams': [{'id': a['id'], 'questions': [q.get('question') or q.get('text') or q.get('id')
                        if isinstance(q, dict) else str(q) for q in a['questions']]} for a in areas]}
        state_file = case / '.harness-research/collection.json'
        if not state_file.exists():
            status = self.command(case, 'collection', 'init', request)
        else:
            status = self.command(case, 'collection', 'status')
            if status['status'] == 'stale':
                raise ValueError('Saved research inputs changed. Refresh sources explicitly; earlier work is kept.')
            if status['status'] == 'paused' and allowed():
                status = self.command(case, 'collection', 'resume')
            if status['status'] == 'stopped':
                if not restart_stopped:
                    raise ValueError('This collection was stopped. Its checked work is kept; explicitly retry research to start a new generation.')
                status = self.command(case, 'collection', 'invalidate', request)
        held = json.loads(bytes_of(state_file))
        if any(a.get('started_at') and not a.get('ended_at') for s in held['workstreams'] for a in s['attempts']):
            raise ValueError('An earlier research invocation has no confirmed terminal observation. Confirm it ended before retrying; saved evidence is kept.')
        kept = {s['id'] for s in status['workstreams'] if s['status'] == 'accepted'}
        tracked = {'schema': 1, 'phase': 'investigate', 'round': 1, 'round_limit': rc.ROUNDS, 'streams': [
            {'id': a['id'], 'questions': request['workstreams'][i]['questions'],
             'status': 'kept' if a['id'] in kept else 'waiting'} for i, a in enumerate(areas)]}
        state_lock = threading.RLock()

        def report(phase=None, stream=None, state=None):
            with state_lock:
                if phase: tracked['phase'] = phase
                for area in tracked['streams']:
                    if area['id'] == stream: area['status'] = state
                with host_lock:
                    timing = research_timing.account(host['started'], host['attempts'])
                    active = [{'id': a['worker'], 'phase': a['phase'], 'stream': a.get('stream'),
                               'status': a.get('status', 'working')}
                              for a in host['attempts'] if not a.get('ended_at')]
                unconfirmed = sum(a['status'] == 'termination-unconfirmed' for a in active)
                tracked['agents'] = {'count': None if unconfirmed else len(active),
                                     'unconfirmed': unconfirmed, 'active': active}
                if timing['incomplete']:
                    timing.update(active_seconds=None, assistant_seconds=None)
                tracked['timing'] = timing
                progress(copy.deepcopy(tracked))

        original_hashes = [(s['original_path'], hashlib.sha256(bytes_of(s['original_path'])).hexdigest())
                           for s in sources if s.get('original_path')]

        def require():
            if any(hashlib.sha256(bytes_of(path)).hexdigest() != expected for path, expected in original_hashes):
                self.command(case, 'collection', 'stop')
                raise ValueError('A selected original changed during research. Earlier evidence is kept; capture and approve its new revision.')
            if cancelled():
                self.command(case, 'collection', 'stop')
                raise InterruptedError('Research stopped; accepted evidence is kept.')
            if not allowed():
                self.command(case, 'collection', 'pause')
                raise InterruptedError('Research paused; accepted evidence is kept.')

        previous = case / '.harness-research/synthesis.json'
        prior = json.loads(bytes_of(previous)) if previous.exists() else {}
        if (prior.get('review') or {}).get('accepted'):
            verified = self.helper.command(case, 'verify')
            if verified.get('status') == 'complete':
                report('complete')
                return rc.read_bundle(rc.output_root(case))
        review, dossier = (prior.get('review') or {}), prior.get('dossier')
        for number in range(1, rc.ROUNDS + 1):
            require()
            tracked['round'] = number
            status = self.command(case, 'collection', 'status')
            pending = []
            for area in areas:
                saved = next(s for s in status['workstreams'] if s['id'] == area['id'])
                if saved['status'] == 'accepted': report(stream=area['id'], state='kept')
                else: pending.append((area, saved))
            # Do not paint a fresh investigation when only synthesis prose needs repair.
            if pending: report('investigate')

            def collect(area, saved):
                require()
                report(stream=area['id'], state='working')
                worker = 'investigator-' + secrets.token_hex(12)
                invocation = 'research-invocation-' + secrets.token_hex(16)
                if saved['status'] not in ('pending', 'reserved'):
                    self.command(case, 'collection', 'retry', {'workstream': area['id'], 'reason': 'Retry this unaccepted area.'})
                registered = self.command(case, 'collection', 'register',
                    {'workstream': area['id'], 'investigator': worker, 'invocation': invocation})
                registration = registered['registration']
                payload = {'task': task, 'worker': worker, 'questions': area['questions'],
                    'return': EVIDENCE, 'previous_review': review, 'previous_dossier': dossier,
                    '_execution': {'phase': 'investigate', 'round': number, 'stream': area['id'],
                        'workers': len(pending), 'mode': 'evidence', 'invocation': invocation}}
                terminal = {'workstream': area['id'], 'investigator': worker, 'attempt': registration['number']}
                try:
                    text, captures = invoke('investigate', (self.runtime / 'references/investigate.md').read_text(),
                                            payload, offered, task['source_mode'] != 'selected')
                    require_cancelled = cancelled()
                    self.command(case, 'collection', 'finish', {**terminal, 'outcome': 'completed',
                        'note': 'The host transport returned from this isolated invocation.'})
                    if require_cancelled:
                        self.command(case, 'collection', 'stop')
                        raise InterruptedError('Stopped research cannot adopt a late response.')
                    value = json.loads(text)
                    if not isinstance(value.get('sources'), list) or not isinstance(value.get('facts'), list):
                        raise ValueError('Return captured sources and facts as arrays.')
                    value, problems = rc.source_metadata(value, self.runtime)
                    if problems: raise ValueError(' '.join(problems))
                    value, problems, _ = rc.citation_sources(value, captures)
                    problems += rc.uncaptured(value['sources'], captures)
                    if problems: raise ValueError(' '.join(problems))
                    captured = {s['file']: s for s in captures}
                    for source in value['sources']:
                        original = captured[source['file']]
                        with self.lock:
                            for key, path_key in (('file', 'path'), ('original_file', 'original_path')):
                                if original.get(path_key):
                                    old = source.get(key) or original.get('original')
                                    if old:
                                        file = 'sources/collection/' + area['id'] + '/' + str(registration['number']) + '/' + old
                                        rc.write(case, file, bytes_of(original[path_key]))
                                        source[key] = file
                            if source['permission'] == 'public':
                                self.command(case, 'asset', 'source', {'id': 'source-' + secrets.token_hex(12),
                                    'role': 'discovered', 'origin': source['origin'], 'permission': 'public',
                                    'outcome': 'captured', 'capture_file': source['file'], 'accessed_at': now()})
                            self.command(case, 'collection', 'capture', {**terminal, 'source': source})
                    gaps = evidence_gaps(value)
                    packet = {'schema': 1, 'request_digest': registered['request_digest'],
                        'generation': registered['generation'], **terminal, 'sources': value['sources'],
                        'facts': value['facts'], 'limitations': [], 'gaps': gaps}
                    self.command(case, 'collection', 'accept', packet)
                    report(stream=area['id'], state='kept')
                except BaseException as error:
                    # invoke returns/raises only after the transport confirms termination.
                    # Completed observations must not be overwritten by a conflicting outcome.
                    state = json.loads(bytes_of(state_file))
                    attempt = next(s for s in state['workstreams'] if s['id'] == area['id'])['attempts'][-1]
                    if not attempt.get('ended_at') and getattr(error, 'terminal_confirmed', True):
                        self.command(case, 'collection', 'finish', {**terminal,
                            'outcome': 'cancelled' if cancelled() else 'failed',
                            'note': 'The host transport ended before a checked packet was accepted.'})
                    report(stream=area['id'], state='failed' if getattr(error, 'terminal_confirmed', True) else 'termination-unconfirmed')
                    raise

            failures = []
            with ThreadPoolExecutor(max_workers=min(3, max(1, limit))) as pool:
                futures = [pool.submit(contextvars.copy_context().run, collect, area, saved) for area, saved in pending]
                for future in as_completed(futures):
                    try: future.result()
                    except BaseException as error: failures.append(error)
            if failures:
                report('needs-attention')
                raise failures[0]
            require()
            registry = self.command(case, 'collection', 'assemble')
            if not registry['facts']:
                for area in areas:
                    self.command(case, 'collection', 'retry', {'workstream': area['id'], 'reason': 'No cited facts were collected; review source access before retrying.'})
                report('needs-attention')
                raise ValueError('The investigators found no cited facts. Captured work and gaps are kept; review source access and the approved scope.')
            base = {'schema': 2, **{k: task[k] for k in rc.TASK_FIELDS}, 'sources': registry['sources'], 'facts': registry['facts']}
            offered_final = [{'title': s['title'], 'origin': s['origin'], 'file': s['file'],
                'permission': s['permission'], 'text': rc.inside(case, s['file']).read_text(),
                'path': rc.inside(case, s['file']),
                **({'original': s['original_file'], 'original_path': rc.inside(case, s['original_file'])}
                   if s.get('original_file') else {})} for s in base['sources']]
            worker = 'synthesizer-' + secrets.token_hex(12)
            report('synthesize')
            payload = {'task': task, 'worker': worker, 'evidence': base, 'gaps': registry['gaps'],
                'previous_dossier': dossier, 'previous_review': review, 'return': COMPOSE + rc.IDS_FOR_QUESTIONS,
                '_execution': {'phase': 'synthesize', 'round': number, 'mode': 'compose', 'evidence_base': base}}
            text, _ = invoke('synthesize', (self.runtime / 'references/synthesize.md').read_text(), payload, offered_final, False)
            require()
            dossier = json.loads(text)
            if check_frozen(dossier, {'evidence_base': base}):
                raise ValueError('Synthesis changed registered evidence; investigator work is kept.')
            dossier.update({k: task[k] for k in rc.TASK_FIELDS})
            rc.write(case, 'dossier.json', json.dumps(dossier))
            status = self.helper.command(case, 'save', 'dossier.json', worker)
            report('review')
            reviewer = 'reviewer-' + secrets.token_hex(12)
            output = rc.output_root(case)
            payload = {'task': task, 'worker': reviewer, 'dossier': dossier, 'review_template': status['review_template'],
                **{key: (output / (key + '.md')).read_text() for key in ('report', 'brief', 'evidence')},
                'return': 'Independently inspect the exact saved evidence and prose. Return complete review JSON. Read each capture and supplied original; report access gaps honestly.',
                '_execution': {'phase': 'review', 'round': number}}
            text, _ = invoke('review', (self.runtime / 'references/review-synthesis.md').read_text(), payload, offered_final, False)
            require()
            review = json.loads(text)
            rc.write(case, 'review.json', text)
            status = self.helper.command(case, 'review', 'review.json', reviewer)
            if status.get('status') == 'complete':
                verified = self.helper.command(case, 'verify')
                if verified.get('status') != 'complete' or verified.get('artifact_integrity') == 'failed':
                    raise ValueError('The checked research changed before handoff.')
                report('complete')
                return rc.read_bundle(output)
            cause = rc.unreadable_originals(review, dossier)
            said = (readable(cause) if readable else '') if cause else None
            if cause and said is not None:
                raise rc.CheckCouldNotFinish(rc.objections(case), number - 1, cause, said or None)
            for stream in corrections(review, registry):
                self.command(case, 'collection', 'retry', {'workstream': stream, 'reason': 'The independent review requested evidence correction.'})
                report(stream=stream, state='waiting')
            affected = sorted(corrections(review, registry))
            notes = [item['note'] for item in review.get('facts', [])
                     if item.get('verdict') not in ('supported', 'pending') and item.get('note')]
            assessment = review.get('assessment') or {}
            if assessment.get('note'): notes.append(assessment['note'])
            with state_lock:
                tracked['correction'] = {'areas': affected, 'notes': notes}
            report('needs-revision')
        raise rc.ReviewRefused(rc.objections(case), rc.ROUNDS, rc.grouped(case))
