"""Bounded research coordination. Harness Research owns evidence and review semantics.

Investigators return evidence, one writer synthesizes immutable inputs, and a fresh
reviewer checks the final digest. Only the coordinator writes the shared case.
"""
import copy
import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import secrets
import threading

from studio_core import research_contract as rc

RECORD_SCHEMA = 5
PROTOCOL = {'schema': 1, 'mode': 'parallel', 'workers': 3}
EVIDENCE = ('Investigate only your assigned questions, using the full purpose and scope. '
            'Return schema 2 JSON with sources, facts, and gaps (an array of short strings). '
            'Do not write a report, findings or finished training material. Preserve '
            'qualifications, counterevidence and unavailable evidence. Set every fact author to this worker ID. ' + rc.CAPTURED + ' ' + rc.SOURCE_IDS)
COMPOSE = ('Write connected research findings, report sections and an authored brief from '
           'the immutable evidence provided. Return schema 2 JSON with findings, sections, '
           'brief and optional comparisons only. Do not return or change sources or facts; '
           'the coordinator includes them unchanged. References use the supplied fact IDs. '
           'Keep gaps honest; request missing evidence in gap blocks. Do not invent facts '
           'or produce finished training materials.')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def protocol(record):
    held = record.get('research_execution') or {}
    return isinstance(held, dict) and held.get('schema') == 1 and held.get('mode') == 'parallel' \
        and type(held.get('workers')) is int and 1 <= held['workers'] <= 3


def enabled(record, task):
    return protocol(record) and len(task.get('planning_questions') or []) > 1


def streams(task, limit=3):
    questions = task.get('planning_questions') or []
    if not isinstance(questions, list) or not questions:
        raise ValueError('Parallel research needs approved planning questions.')
    count = min(3, max(1, int(limit)), len(questions))
    return [{'id': f'area{i + 1}', 'questions': copy.deepcopy(questions[i::count])}
            for i in range(count)]


def identity(kind, stream, local):
    # Long model IDs never overrun the helper's 64-character identifier contract.
    return f'{kind}-{stream}-' + hashlib.sha256(str(local).encode()).hexdigest()[:24]


def preparation(value, spec):
    """Compose schema-2 helper input without letting the model alter frozen evidence."""
    mode = spec.get('research_mode')
    if mode == 'evidence':
        if set(value) - {'schema', 'sources', 'facts', 'gaps'}:
            raise ValueError('Return sources, facts and gaps only; the synthesis worker writes the report.')
        if not isinstance(value.get('sources'), list) or not isinstance(value.get('facts'), list):
            raise ValueError('Return sources and facts as arrays.')
        gaps = value.get('gaps', [])
        if not isinstance(gaps, list) or any(not isinstance(g, str) or not g.strip() for g in gaps):
            raise ValueError('Return gaps as an array of nonempty strings.')
        return {**{k: v for k, v in value.items() if k != 'gaps'}, **spec['task'], 'findings': [],
                'sections': [{'id': 'collection', 'title': 'Evidence collection', 'blocks': [
                    {'text': g, 'kind': 'gap', 'refs': []} for g in gaps
                ] or [{'text': 'Evidence collected; synthesis and independent review are pending.',
                       'kind': 'gap', 'refs': []}]}]}
    if mode == 'compose':
        if set(value) - {'schema', 'findings', 'sections', 'brief', 'comparisons'}:
            raise ValueError('Return findings, sections, brief and optional comparisons only. Evidence is kept unchanged.')
        for name in ('findings', 'sections', 'brief'):
            if not isinstance(value.get(name), list) or not value[name]:
                raise ValueError(f'Return {name} as a nonempty array for the connected report and authored brief.')
        return {**copy.deepcopy(spec['evidence_base']), **value}
    return value


def check_frozen(value, spec):
    base = spec.get('evidence_base')
    if not isinstance(base, dict):
        return None
    if value.get('facts') != base.get('facts') or value.get('sources') != base.get('sources'):
        return ['Synthesis must keep the registered evidence and its actual investigator authors unchanged.']
    return []


def _bytes(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Research captures must be ordinary files, not links.')
    return path.read_bytes()


class PacketCache:
    """Private, input-bound checkpoints. Each packet has its own helper-validated case."""
    def __init__(self, root, basis, helper):
        root = Path(root)
        if root.is_symlink():
            raise ValueError('Research checkpoints cannot traverse links.')
        self.root, self.basis, self.helper = root / basis, basis, helper
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def keep(self, stream, task, worker, text, captures, cancelled=lambda: False):
        value = json.loads(text)
        for key in rc.TASK_FIELDS:
            value[key] = task[key]
        if any(f.get('author') != worker for f in value.get('facts', [])):
            raise ValueError('Evidence must identify its actual investigator invocation.')
        value, problems, _ = rc.citation_sources(value, captures)
        if problems:
            raise ValueError(' '.join(problems))
        problems = rc.uncaptured(value['sources'], captures)
        if problems:
            raise ValueError(' '.join(problems))
        # Keep a prior valid packet until a complete replacement passes validation.
        folder = rc.inside(self.root, stream + '-' + secrets.token_hex(8))
        folder.mkdir(mode=0o700)
        files = {}
        by_file = {s['file']: s for s in captures}
        for source in value['sources']:
            captured = by_file[source['file']]
            for key, path_key in (('file', 'path'), ('original', 'original_path')):
                if captured.get(key) and captured.get(path_key):
                    data = _bytes(captured[path_key])
                    rc.write(folder, captured[key], data)
                    files[captured[key]] = hashlib.sha256(data).hexdigest()
            if captured.get('original') and source['permission'] == 'selected':
                source['original_file'] = captured['original']
            else:
                source.pop('original_file', None)
        rc.write(folder, 'dossier.json', json.dumps(value))
        self.helper.command(folder, 'save', 'dossier.json', worker)
        files['dossier.json'] = hashlib.sha256((folder / 'dossier.json').read_bytes()).hexdigest()
        receipt = {'schema': 1, 'basis': self.basis, 'stream': stream, 'worker': worker,
                   'files': files}
        rc.write(folder, 'receipt.json', json.dumps(receipt))
        if cancelled():
            raise InterruptedError('Stopped research cannot adopt a late response.')
        # A pointer is replaced atomically; packet directories are never partly adopted.
        rc.write(self.root, stream + '.json', json.dumps({'folder': folder.name}))
        return {'folder': folder, 'dossier': value, 'worker': worker, 'stream': stream, 'hashes': files}

    def invalidate(self, stream):
        rc.write(self.root, stream + '.json', json.dumps({'invalidated': True}))

    def get(self, stream):
        try:
            pointer = json.loads(rc.inside(self.root, stream + '.json').read_text())
            if pointer.get('invalidated'):
                return None
            folder = rc.inside(self.root, pointer['folder'])
            if not folder.name.startswith(stream + '-'):
                return None
            # load uses the path's receipt identity, not the directory's revision suffix.
            receipt = json.loads(rc.inside(folder, 'receipt.json').read_text())
            if receipt.get('basis') != self.basis or receipt.get('stream') != stream:
                return None
            blobs = {}
            for name, expected in receipt['files'].items():
                blobs[name] = _bytes(rc.inside(folder, name))
                if hashlib.sha256(blobs[name]).hexdigest() != expected:
                    return None
            value = json.loads(blobs['dossier.json'])
            if any(f.get('author') != receipt['worker'] for f in value['facts']):
                return None
            return {'folder': folder, 'dossier': value, 'worker': receipt['worker'], 'stream': stream,
                    'hashes': receipt['files']}
        except (OSError, ValueError, KeyError, TypeError):
            return None


def assemble(case, task, packets):
    sources, facts, owners, gaps = [], [], {}, []
    equivalent = {}
    for packet in sorted(packets, key=lambda p: p['stream']):
        stream, folder, dossier = packet['stream'], packet['folder'], packet['dossier']

        def read(name):
            data = _bytes(rc.inside(folder, name))
            if hashlib.sha256(data).hexdigest() != packet['hashes'].get(name):
                raise ValueError('A checkpoint source changed; research must read it again.')
            return data

        source_ids = {}
        for row in dossier['sources']:
            source = copy.deepcopy(row)
            data = read(source['file'])
            original = read(source['original_file']) if source.get('original_file') else None
            same = digest([source.get(k) for k in ('origin', 'permission', 'context', 'context_note',
                                                  'publisher', 'source_date', 'accessed_at', 'version')]
                          + [hashlib.sha256(data).hexdigest(),
                             hashlib.sha256(original).hexdigest() if original is not None else None])
            if same in equivalent:
                source_ids[source['id']] = equivalent[same]
                continue
            global_id = identity('s', stream, source['id'])
            source_ids[source['id']] = global_id
            source['id'] = global_id
            for key in ('file', 'original_file'):
                if source.get(key):
                    name = 'sources/parallel/' + stream + '/' + source[key]
                    rc.write(case, name, read(source[key]))
                    source[key] = name
            sources.append(source)
            equivalent[same] = global_id
        for row in dossier['facts']:
            fact = copy.deepcopy(row)
            fact['id'] = identity('f', stream, fact['id'])
            if fact['id'] in owners:
                raise ValueError('Research fact IDs collided; no evidence was merged.')
            owners[fact['id']] = stream
            for citation in fact['citations']:
                citation['source'] = source_ids[citation['source']]
            facts.append(fact)
        for section in dossier.get('sections', []):
            gaps += [b['text'] for b in section.get('blocks', []) if b.get('kind') == 'gap']
    return {'schema': 2, **{k: task[k] for k in rc.TASK_FIELDS}, 'sources': sources,
            'facts': facts, 'findings': [], 'sections': [{'id': 'pending', 'title': 'Synthesis pending',
            'blocks': [{'text': 'Synthesis and independent review are pending.', 'kind': 'gap', 'refs': []}]}]}, owners, gaps


def corrections(review, owners):
    selected = {owners[f['id']] for f in review.get('facts', [])
                if f.get('id') in owners and f.get('verdict') not in ('supported', 'pending')}
    # Prose/findings can be repaired from frozen evidence. Broad missing coverage
    # with no located fact objection needs the whole approved scope investigated.
    if not selected and (review.get('assessment') or {}).get('coverage') == 'needs-revision':
        selected = set(owners.values())
    return selected


class Workflow:
    def __init__(self, runtime, call=None):
        self.helper = rc.Workflow(runtime, call)
        self.runtime = Path(runtime)

    def run(self, root, task, invoke, sources=(), *, cache_root, limit=3,
            progress=lambda value: None, allowed=lambda: True, cancelled=lambda: False,
            readable=None):
        limit = max(1, min(3, int(limit)))
        case = rc.inside(root, str(rc.CASE))
        case.mkdir(parents=True, exist_ok=True)
        source_basis = []
        for source in sources:
            source_basis.append([source.get('file'), source.get('origin'), source.get('permission'),
                                 hashlib.sha256(source.get('text', '').encode()).hexdigest(),
                                 hashlib.sha256(_bytes(source['original_path'])).hexdigest()
                                 if source.get('original_path') else None])
        basis_task = copy.deepcopy(task)
        areas = streams(task, limit)
        basis = digest([basis_task, source_basis, areas, rc.capability(self.runtime)])
        cache = PacketCache(cache_root, basis, self.helper)
        packets = {area['id']: cache.get(area['id']) for area in areas}
        state = {'schema': 1, 'phase': 'investigate', 'round': 1,
                 'streams': [{'id': a['id'], 'questions': [q.get('question') or q.get('text') or q.get('id') or 'Approved question' if isinstance(q, dict) else str(q) for q in a['questions']], 'status': 'kept' if packets[a['id']] else 'waiting'} for a in areas]}
        state_lock = threading.RLock()

        def report(phase=None, stream=None, status=None):
            with state_lock:
                if phase:
                    state['phase'] = phase
                for item in state['streams']:
                    if item['id'] == stream:
                        item['status'] = status
                progress(copy.deepcopy(state))

        def require():
            if not allowed():
                raise InterruptedError('Research is paused or stopped; verified evidence is kept.')

        try:
            previous = json.loads(rc.inside(cache.root, 'previous.json').read_text())
            review, dossier = previous.get('review'), previous.get('dossier')
        except (OSError, ValueError, TypeError):
            review, dossier = None, None
        for number in range(1, rc.ROUNDS + 1):
            state['round'] = number
            require()
            pending = [a for a in areas if not packets.get(a['id'])]
            report('investigate')

            def collect(area):
                require()
                report(stream=area['id'], status='working')
                worker = 'investigator-' + secrets.token_hex(12)
                payload = {'task': task, 'worker': worker, 'questions': area['questions'],
                           'return': EVIDENCE, 'previous_review': review,
                           '_execution': {'phase': 'investigate', 'round': number, 'stream': area['id'],
                                          'workers': len(pending), 'mode': 'evidence'}}
                guide = (self.runtime / 'references/investigate.md').read_text()
                try:
                    text, captured = invoke('investigate', guide, payload, sources,
                                            task['source_mode'] != 'selected')
                    # Stop cannot adopt a late completion; Pause may checkpoint finished work.
                    packet = cache.keep(area['id'], task, worker, text, captured, cancelled)
                    report(stream=area['id'], status='kept')
                    return area['id'], packet
                except Exception:
                    report(stream=area['id'], status='failed')
                    raise

            failures = []
            with ThreadPoolExecutor(max_workers=min(limit, len(pending) or 1)) as pool:
                futures = [pool.submit(contextvars.copy_context().run, collect, area) for area in pending]
                for future in as_completed(futures):
                    try:
                        stream, packet = future.result()
                        packets[stream] = packet
                    except Exception as error:
                        failures.append(error)
            if failures:
                raise failures[0]
            require()
            base, owners, gaps = assemble(case, task, list(packets.values()))
            if not base['facts']:
                for area in areas:
                    cache.invalidate(area['id'])
                raise ValueError('The investigators found no cited facts. Their captured work is kept; review the approved questions and source access before retrying.')
            worker = 'synthesizer-' + secrets.token_hex(12)
            report('synthesize')
            payload = {'task': task, 'worker': worker, 'evidence': base, 'gaps': gaps,
                       'previous_dossier': dossier, 'previous_review': review,
                       'return': COMPOSE + ' ' + rc.IDS_FOR_QUESTIONS,
                       '_execution': {'phase': 'synthesize', 'round': number, 'mode': 'compose',
                                      'evidence_base': base}}
            guide = (self.runtime / 'references/synthesize.md').read_text()
            text, _ = invoke('synthesize', guide, payload, [
                {'title': s['title'], 'origin': s['origin'], 'file': s['file'], 'permission': s['permission'],
                 'text': rc.inside(case, s['file']).read_text(),
                 **({'original': s['original_file'], 'original_path': rc.inside(case, s['original_file'])}
                    if s.get('original_file') else {})} for s in base['sources']], False)
            require()
            dossier = json.loads(text)
            if dossier.get('sources') != base['sources'] or dossier.get('facts') != base['facts']:
                raise ValueError('Synthesis changed frozen evidence; verified investigator work is kept.')
            for key in rc.TASK_FIELDS:
                dossier[key] = task[key]
            rc.write(case, 'dossier.json', json.dumps(dossier))
            status = self.helper.command(case, 'save', 'dossier.json', worker)
            report('review')
            reviewer = 'reviewer-' + secrets.token_hex(12)
            payload = {'task': task, 'worker': reviewer, 'dossier': dossier,
                       'review_template': status['review_template'],
                       'report': (case / 'research/report.md').read_text(),
                       'brief': (case / 'research/brief.md').read_text(),
                       'evidence': (case / 'research/evidence.md').read_text(),
                       'return': 'Independently inspect the exact evidence and prose. Return complete review JSON. '
                                 'Read every source and supplied original; report unavailable context honestly.',
                       '_execution': {'phase': 'review', 'round': number}}
            text, _ = invoke('review', (self.runtime / 'references/review-synthesis.md').read_text(),
                             payload, [{'title': s['title'], 'origin': s['origin'], 'file': s['file'],
                                        'permission': s['permission'], 'text': rc.inside(case, s['file']).read_text(),
                                        **({'original': s['original_file'], 'original_path': rc.inside(case, s['original_file'])}
                                           if s.get('original_file') else {})} for s in dossier['sources']], False)
            require()
            review = json.loads(text)
            rc.write(case, 'review.json', text)
            status = self.helper.command(case, 'review', 'review.json', reviewer)
            if status.get('status') == 'complete':
                verified = self.helper.command(case, 'verify')
                if verified.get('status') != 'complete' or verified.get('artifact_integrity') == 'failed':
                    raise ValueError('The reviewed research changed before handoff.')
                report('complete')
                return rc.read_bundle(case / 'research')
            cause = rc.unreadable_originals(review, dossier)
            said = (readable(cause) if readable else '') if cause else None
            if cause and said is not None:
                raise rc.CheckCouldNotFinish(rc.objections(case), number - 1, cause, said or None)
            rc.write(cache.root, 'previous.json', json.dumps({'review': review, 'dossier': dossier}))
            for stream in corrections(review, owners):
                packets[stream] = None
                cache.invalidate(stream)
                report(stream=stream, status='waiting')
        raise rc.ReviewRefused(rc.objections(case), rc.ROUNDS, rc.grouped(case))
