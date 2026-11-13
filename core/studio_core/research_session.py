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

from studio_core import research_contract as rc, research_timing, research_sections, research_preview, research_quality
from studio_core import research_reading
from studio_core.shared_runner.worker_tools import tidy

PROTOCOL = 'harness-collection-v1'
RECORD_SCHEMA = 5  # Training Studio's new execution record; other adapters version their own.
PENDING = 'Synthesis and independent review are pending.'
EVIDENCE = ('Investigate only your assigned questions within the supplied task and source policy. '
            'Return one JSON object holding only "schema": 2, sources, facts and gaps (an array of '
            'strings). '
            'Each fact contains only id, statement, author and citations. Each citation contains '
            'source, quote and optional locator. kind belongs to synthesis prose, never a fact '
            'or citation. Put unsupported or inferred material in gaps; never upgrade it to a fact. '
            'Preserve counterevidence and limitations. Set every fact author to this worker ID. '
            'The host registers your actual invocation and capture receipts. You cannot register '
            'permissions or approve your own evidence. ' + rc.CAPTURED + ' ' + rc.SOURCE_IDS + ' '
            + rc.OUTLINED)
COMPOSE = ('Write connected findings, report sections and an authored brief from the immutable '
           'evidence. Return schema 2 JSON containing findings, sections, brief and optional '
           'comparisons only. The host includes the registered sources/facts unchanged. '
           'Preserve actual investigators and gaps; request registered investigation for new facts. '
           + rc.SYNTHESIZED + ' ')
# What a synthesis returns, and which of its parts must hold at least one item.
COMPOSED = ('schema', 'findings', 'sections', 'brief', 'comparisons')


TOO_MANY = ('This research has {count} documents, and one research agent reads at most {most}. '
            'Remove or exclude some, then start again.')


INTAKE = {'entries': 200}
INTAKE_FILE = 'references/intake-limits.json'
OVER_INTAKE = ('The installed Harness Research takes at most {most} entries in one research run, and a link '
               'counts as two. This run has {count}. Update Harness Research to read more, or remove some sources.')


def intake_limits(runtime):
    """What the installed Harness Research says one run may take in; an older one says nothing
    and has the limits it always had."""
    try:
        value = json.loads((Path(runtime) / INTAKE_FILE).read_text(encoding='utf-8'))
        entries = value['entries']
    except (OSError, ValueError, KeyError, TypeError):
        return dict(INTAKE)
    return {'entries': entries} if type(entries) is int and entries >= INTAKE['entries'] else dict(INTAKE)


def intake_entries(sources):
    """How many entries these sources register as: a chosen link is two, anything else one."""
    count = 0
    for source in sources:
        if source.get('permission', 'selected' if source.get('offered', True) else 'public') != 'selected':
            continue
        linked = urlsplit(source.get('origin', source.get('url', '')) or '').scheme in ('http', 'https')
        count += 2 if linked else 1
    return count


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
        research_quality.evidence(value, spec.get('research_policy'))
        if set(value) - {'schema', 'sources', 'facts', 'gaps'}:
            raise ValueError('Return sources, facts and gaps only; synthesis writes the report.')
        if not isinstance(value.get('sources'), list) or not isinstance(value.get('facts'), list):
            raise ValueError('Return sources and facts as arrays.')
        gaps = value.get('gaps', [])
        # Blank as Harness Research's text() reads it, with JavaScript's trim().
        if not isinstance(gaps, list) or any(not isinstance(g, str) or rc.js_blank(g) for g in gaps):
            raise ValueError('Return gaps as an array of nonempty strings.')
        return {**{k: v for k, v in value.items() if k != 'gaps'}, **spec['task'], 'findings': [],
                'sections': [{'id': 'collection', 'title': 'Evidence collection', 'blocks': [
                    {'text': g, 'kind': 'gap', 'refs': []} for g in gaps] or [
                    {'text': PENDING, 'kind': 'gap', 'refs': []}]}]}
    if spec.get('research_mode') in ('compose-section', 'compose-final'):
        return research_sections.prepared(value, spec)
    if spec.get('research_mode') == 'compose':
        problems = compose_shape(value)
        if problems:
            raise ValueError(' '.join(problems))
        research_quality.prose(value)
        return {**copy.deepcopy(spec['evidence_base']), **value}
    return value


def compose_shape(value):
    """Every way a synthesis's parts differ from what the studio asks for: only its own parts,
    and findings, sections and brief each a nonempty array (#303: all of them at once)."""
    problems = []
    if set(value) - set(COMPOSED):
        problems.append('Return findings, sections, brief and optional comparisons only. Evidence is kept unchanged.')
    for name in ('findings', 'sections', 'brief'):
        if not isinstance(value.get(name), list) or not value[name]:
            problems.append(f'Return {name} as a nonempty array.')
    return problems


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


def section_streams(task):
    questions = task.get('planning_questions')
    if not isinstance(questions, list) or not 1 <= len(questions) <= 64:
        raise ValueError('Section research needs one to 64 approved questions.')
    ids = [item.get('id') for item in questions if isinstance(item, dict)]
    if len(ids) != len(questions) or any(not isinstance(ident, str) or not ident for ident in ids) or len(set(ids)) != len(ids):
        raise ValueError('Every approved section needs its own question ID.')
    return [{'id': 'area-' + digest(item['id'])[:40], 'questions': [copy.deepcopy(item)]} for item in questions]


def bytes_of(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Research captures must be ordinary files, not links.')
    return path.read_bytes()


def kept_copies(target, file):
    """The hashes of the copies kept investigations hold of one registered capture.

    An investigation keeps each source it cites at sources/collection/<area>/<attempt>/
    followed by the source's registered capture file, which rc.uncaptured enforces.
    """
    folder = target / 'sources/collection'
    if not folder.is_dir() or folder.is_symlink():
        return set()
    return {hashlib.sha256(path.read_bytes()).hexdigest() for path in folder.glob('*/*/' + file)
            if path.is_file() and not path.is_symlink()}


def capture_text(text, kept):
    """The text a source is registered with, which is the text investigators are given.

    The text is tidied the way the studios' worker tools tidy what an assistant reads, so
    the copy a kept investigation holds is byte-identical to the registered capture that
    Harness Research checks it against. Earlier Blog Studio and Infographic Studio runs
    gave investigators the text as it came; when a kept investigation already holds that
    untidied text, and not the tidied text, it stays registered so that evidence stays valid.
    `kept` holds the hashes of this one source's kept copies, from kept_copies.
    """
    tidied = tidy(text)
    if tidied != text and hashlib.sha256(text.encode()).hexdigest() in kept \
            and hashlib.sha256(tidied.encode()).hexdigest() not in kept:
        return text
    return tidied


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


def corrections(review, registry, *, sectioned=False):
    owners = {global_id: mapping['workstream'] for mapping in registry['mappings']
              for global_id in mapping['facts'].values()}
    selected = {owners[f['id']] for f in review.get('facts', [])
                if f.get('id') in owners and f.get('verdict') not in ('supported', 'pending')}
    prose_only = sectioned and any(row.get('verdict') not in ('supported', 'pending')
        for key in ('findings', 'prose') for row in review.get(key, []))
    if not selected and not prose_only and (review.get('assessment') or {}).get('coverage') == 'needs-revision':
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
        # Registering again updates capture_sha256, so a capture registered untidied by an
        # earlier version is corrected here on Try again (#295).
        offered = []
        for source, filename, linked in selected:
            origin = source.get('origin', source.get('url', ''))
            original = next(e for e in inventory if e.get('filename') == filename)
            entry = next(e for e in inventory if e.get('type') == 'url' and e['origin'] == origin) if linked else original
            file = 'sources/selected/' + filename + '.txt'
            text = capture_text(source['text'], kept_copies(target, file))
            rc.write(target, file, text)
            self.command(target, 'asset', 'source', {'id': entry['id'], 'outcome': 'captured',
                'capture_file': file, 'accessed_at': source.get('accessed_at') or now(),
                'note': 'Selected studio capture; the remote original was not automatically refreshed.'})
            offered.append({**source, 'text': text, 'file': file, 'origin': entry['origin'], 'url': entry['origin'],
                'permission': 'selected', 'path': rc.inside(target, file),
                'original': original['original_file'], 'original_path': rc.inside(target, original['original_file'])})
        for source in public:
            if task['source_mode'] == 'selected':
                raise ValueError('Public captures need explicit external-search permission.')
            # Names stay those of the text as it came, so an earlier capture is replaced.
            file = 'sources/public/' + digest([source['origin'], source['text']]) + '.txt'
            text = capture_text(source['text'], kept_copies(target, file))
            rc.write(target, file, text)
            self.command(target, 'asset', 'source', {'id': 'public-' + digest([source['origin'], source['text']])[:32],
                'role': 'discovered', 'origin': source['origin'], 'permission': 'public', 'outcome': 'captured',
                'capture_file': file, 'accessed_at': source.get('accessed_at') or now()})
            offered.append({**source, 'text': text, 'file': file, 'path': rc.inside(target, file), 'permission': 'public'})
        rc.write(base, 'current.json', json.dumps({'schema': 1, 'basis': basis}))
        return target, offered

    def run(self, root, task, invoke, sources=(), *, limit=3, progress=lambda state: None,
            allowed=lambda: True, cancelled=lambda: False, readable=None, restart_stopped=False,
            section_policy=None, section_context=None, impact=None, input_snapshot=None,
            creator_review=False, reading=False, **_):
        if capability(self.runtime) is None:
            raise ValueError('This workflow needs the complete Harness Research 1.1 collection runtime.')
        if task.get('research_policy') and not research_quality.valid_policy(task['research_policy']):
            raise ValueError('Restore the saved focused research policy before continuing.')
        if unresolved(root):
            raise ValueError('An earlier research invocation has no confirmed terminal observation. Confirm it ended before retrying; saved evidence is kept.')
        if section_policy and impact:
            from studio_core import research_impact
            research_impact.context_current(root, task, impact)
        areas = section_streams(task) if section_policy else streams(task, limit)
        basis = digest([task, [[s.get('file'), s.get('origin'), s.get('permission'),
            hashlib.sha256(s['text'].encode()).hexdigest(),
            hashlib.sha256(bytes_of(s['original_path'])).hexdigest() if s.get('original_path') else None]
            for s in sources], capability(self.runtime), areas])
        # Said here, before anything is registered, and never after the work has begun.
        chosen_count = sum(source.get('permission', 'selected' if source.get('offered', True) else 'public') == 'selected'
                           for source in sources)
        if not reading and chosen_count > research_reading.GROUP:
            raise ValueError(TOO_MANY.format(count=chosen_count, most=research_reading.GROUP))
        most, count = intake_limits(self.runtime)['entries'], intake_entries(sources)
        if count > most:
            raise ValueError(OVER_INTAKE.format(most=most, count=count))
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
                       'stream': payload['_execution'].get('stream'),
                       'section': payload['_execution'].get('section'), 'started_at': now(), 'status': 'working'}
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
                    if area['id'] == stream:
                        area['status'] = state
                        if state != 'kept': area.pop('evidence', None)
                with host_lock:
                    timing = research_timing.account(host['started'], host['attempts'])
                    active = [{'id': a['worker'], 'phase': a['phase'], 'stream': a.get('stream'),
                               'section': a.get('section'),
                               'status': a.get('status', 'working')}
                              for a in host['attempts'] if not a.get('ended_at')]
                unconfirmed = sum(a['status'] == 'termination-unconfirmed' for a in active)
                tracked['agents'] = {'count': None if unconfirmed else len(active),
                                     'unconfirmed': unconfirmed, 'active': active}
                if timing['incomplete']:
                    timing.update(active_seconds=None, assistant_seconds=None)
                tracked['timing'] = timing
                if phase in ('stopped', 'paused', 'invalidated') or cancelled():
                    for area in tracked['streams']: area.pop('evidence', None)
                if phase == 'complete': tracked['checked_result_seconds'] = timing.get('elapsed_seconds')
                progress(copy.deepcopy(tracked))

        original_hashes = [(s['original_path'], hashlib.sha256(bytes_of(s['original_path'])).hexdigest())
                           for s in sources if s.get('original_path')]

        def require():
            if any(hashlib.sha256(bytes_of(path)).hexdigest() != expected for path, expected in original_hashes):
                self.command(case, 'collection', 'stop')
                report('invalidated')
                raise ValueError('A selected original changed during research. Earlier evidence is kept; capture and approve its new revision.')
            if cancelled():
                self.command(case, 'collection', 'stop')
                report('stopped')
                raise InterruptedError('Research stopped; accepted evidence is kept.')
            if not allowed():
                self.command(case, 'collection', 'pause')
                report('paused')
                raise InterruptedError('Research paused; accepted evidence is kept.')

        reuse_context = None
        context_unchanged = True
        if section_policy and section_policy.get('reuse'):
            if research_sections.reuse_capability(self.runtime) != section_policy['reuse']:
                raise ValueError('Restore the saved unchanged-save capability before continuing.')
            reuse_context = '.harness-research/studio-review-context.json'
            context = {'schema': 1, 'protocol': research_sections.fingerprint([capability(self.runtime), section_policy['reuse']]),
                'guidance': research_sections.fingerprint([research_sections.PROTOCOL, section_context]),
                'independence': research_sections.fingerprint((section_context or {}).get('checking'))}
            context_file = rc.inside(case, reuse_context)
            context_unchanged = context_file.exists() and json.loads(context_file.read_bytes()) == context
            rc.write(case, reuse_context, json.dumps(context))
        if section_policy:
            from studio_core import research_impact
            research_impact.reuse(self, root, case, task, areas, impact, section_context, require)
            if input_snapshot:
                rc.write(case, '.harness-research/studio-inputs.json', json.dumps(input_snapshot))
                rc.write(case, '.harness-research/studio-task-context.json', json.dumps({key: task[key] for key in rc.TASK_FIELDS if key != 'planning_questions'}))
            rc.write(case, '.harness-research/studio-section-context.json', json.dumps(section_context))
        previous = case / '.harness-research/synthesis.json'
        prior = json.loads(bytes_of(previous)) if previous.exists() else {}
        if context_unchanged and (prior.get('review') or {}).get('accepted'):
            verified = self.helper.command(case, 'verify')
            if verified.get('status') == 'complete':
                report('complete')
                return rc.read_bundle(rc.output_root(case))
        review, dossier = (prior.get('review') or {}), prior.get('dossier')
        # A user-triggered retry repairs a previous rejected draft once. Merely
        # opening the creator decision form never invalidates kept contributions.
        if (creator_review and review and not review.get('accepted')
                and not research_quality.coverage(review)['unread']
                and all(row['status'] == 'accepted' for row in self.command(case, 'collection', 'status')['workstreams'])):
            registry = self.command(case, 'collection', 'assemble')
            affected = sorted(corrections(review, registry, sectioned=bool(section_policy)))
            if section_policy: research_sections.invalidate(case, review, affected)
            for stream in affected:
                self.command(case, 'collection', 'retry', {'workstream': stream, 'reason': 'The creator explicitly requested another correction attempt.'})
        # More than fifty documents are read in groups first, one agent to a group, and each
        # area's investigator is then offered only the documents its notes rank highest.
        given = {area['id']: offered for area in areas}
        cited_most = None
        if research_reading.needed(offered):
            if not reading:
                raise ValueError(TOO_MANY.format(count=len(research_reading.selected(offered)), most=research_reading.GROUP))
            chosen = research_reading.selected(offered)
            every = research_reading.groups(chosen)
            place = {source['file']: n for n, source in enumerate(sorted(chosen, key=lambda one: one['file']), start=1)}
            waiting = research_reading.waiting(root, offered, areas)
            todo = {tuple(source['file'] for source in group) for group in waiting}
            spans = [{'from': place[group[0]['file']], 'to': place[group[-1]['file']], 'status': 'waiting'} for group in waiting]
            with state_lock:
                tracked['reading'] = {'total': len(chosen), 'read': len(chosen) - sum(len(g) for g in waiting),
                                      'groups': spans, 'of': len(every)}
            if waiting:
                report('read')

            def note(number, group):
                require()
                worker = 'reader-' + secrets.token_hex(12)
                span = spans[number]
                with state_lock: span['status'] = 'working'
                report()
                wanted = research_reading.spec(group, areas)
                payload = {'task': task, 'worker': worker, 'areas': research_reading.labels(areas),
                    'documents': wanted['documents'], 'return': research_reading.GUIDANCE,
                    '_execution': {'phase': 'read', 'round': 1, 'stream': f'group-{number + 1:02d}',
                        'workers': len(waiting), 'mode': 'reading', 'invocation': 'research-invocation-' + secrets.token_hex(16),
                        'span': [span['from'], span['to'], len(chosen)], 'reading': wanted}}
                try:
                    text, _ = invoke('read', research_reading.GUIDANCE, payload, group, False)
                    problems = research_reading.check(text, wanted)[0]
                    if problems: raise ValueError(' '.join(problems))
                    require()
                    research_reading.keep(root, group, areas, json.loads(text), worker)
                except BaseException:
                    with state_lock: span['status'] = 'failed'
                    report()
                    raise
                with state_lock:
                    span['status'] = 'read'
                    tracked['reading']['read'] += len(group)
                report()

            missed = []
            with ThreadPoolExecutor(max_workers=min(3, max(1, limit))) as pool:
                futures = [pool.submit(contextvars.copy_context().run, note, number, group) for number, group in enumerate(waiting)]
                for future in as_completed(futures):
                    try: future.result()
                    except BaseException as error: missed.append(error)
            if missed:
                # Groups that finished keep their notes; a retry reads only the rest.
                report('needs-attention')
                raise missed[0]
            require()
            plan = research_reading.assign(root, offered, areas)
            rc.write(case, '.harness-research/studio-reading.json', json.dumps(plan))
            found = [source for source in offered if source not in chosen]
            by_file = {source['file']: source for source in chosen}
            given = {area['id']: [by_file[file] for file in plan['assignment'][area['id']]] + found for area in areas}
            # The independent check reads every cited original, so what all areas cite together
            # stays within one agent's fifty too.
            cited_most = max(1, research_reading.GROUP // len(areas))
            with state_lock:
                tracked['reading'].update(unused=len(plan['unused']), dropped=sum(plan['dropped'].values()))
            report('investigate')
        # Every source each investigator is given, with each field it must return (#303).
        outlines = {area['id']: rc.source_outline(given[area['id']], self.runtime) for area in areas}
        # And the exact shape the synthesis and the review return.
        synthesis_outline = rc.synthesis_outline(self.runtime)
        review_outline = rc.review_outline(self.runtime)
        for number in range(1, rc.ROUNDS + 1):
            require()
            tracked['round'] = number
            status = self.command(case, 'collection', 'status')
            accepted = research_preview.restored(case, json.loads(bytes_of(state_file)), basis)
            with state_lock:
                for row in tracked['streams']:
                    row.pop('evidence', None)
                    if row['id'] in accepted: row['evidence'] = accepted[row['id']]
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
                    'return': EVIDENCE + (' ' + research_quality.FOCUSED_GUIDANCE +
                        f' Return at most {task["research_policy"]["facts_per_area"]} essential facts '
                        f'and {task["research_policy"]["sources_per_area"]} cited sources for this area.'
                        if task.get('research_policy') else '') + (
                        f' Cite at most {cited_most} sources for this area: the ones that carry the most.'
                        if cited_most else ''), 'source_outline': outlines[area['id']],
                    'previous_review': review, 'previous_dossier': dossier,
                    '_execution': {'phase': 'investigate', 'round': number, 'stream': area['id'],
                        'workers': len(pending), 'mode': 'evidence', 'invocation': invocation,
                        'research_policy': task.get('research_policy')}}
                terminal = {'workstream': area['id'], 'investigator': worker, 'attempt': registration['number']}
                try:
                    text, captures = invoke('investigate', (self.runtime / 'references/investigate.md').read_text(),
                                            payload, given[area['id']], task['source_mode'] != 'selected')
                    require_cancelled = cancelled()
                    self.command(case, 'collection', 'finish', {**terminal, 'outcome': 'completed',
                        'note': 'The host transport returned from this isolated invocation.'})
                    if require_cancelled:
                        self.command(case, 'collection', 'stop')
                        raise InterruptedError('Stopped research cannot adopt a late response.')
                    value = json.loads(text)
                    research_quality.evidence(value, task.get('research_policy'))
                    if not isinstance(value.get('sources'), list) or not isinstance(value.get('facts'), list):
                        raise ValueError('Return captured sources and facts as arrays.')
                    if cited_most and len(value['sources']) > cited_most:
                        raise ValueError(f'Cite at most {cited_most} sources for this area; {len(value["sources"])} were returned. '
                                         'Keep the ones that carry the most.')
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
                    require()
                    self.command(case, 'collection', 'accept', packet)
                    with state_lock:
                        for row in tracked['streams']:
                            if row['id'] == area['id']: row['evidence'] = research_preview.evidence(packet, basis)
                        if 'first_finding_seconds' not in tracked:
                            tracked['first_finding_seconds'] = research_timing.account(host['started'], host['attempts']).get('elapsed_seconds')
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
            if section_policy:
                def section_progress(values):
                    with state_lock:
                        tracked['combining'] = values
                        if any(row.get('preview') for row in values) and 'first_readable_seconds' not in tracked:
                            tracked['first_readable_seconds'] = research_timing.account(host['started'], host['attempts']).get('elapsed_seconds')
                    report('synthesize')
                dossier, worker = research_sections.combine(case, task, areas, registry, base,
                    offered_final, invoke, round=number,
                    guidance=(self.runtime / 'references/synthesize.md').read_text(),
                    policy={**section_policy, 'workers': limit}, require=require,
                    notify=section_progress, context=section_context)
                require()
            elif (number == 1 and not pending and context_unchanged
                  and research_quality.coverage(review)['unread']
                  and isinstance(dossier, dict) and prior.get('author')
                  and not check_frozen(dossier, {'evidence_base': base})):
                # Saved non-sectioned runs also resume an unfinished check without
                # paying a synthesizer to rewrite the same validated dossier.
                worker = prior['author']
            else:
                worker = 'synthesizer-' + secrets.token_hex(12)
                report('synthesize')
                payload = {'task': task, 'worker': worker, 'evidence': base, 'gaps': registry['gaps'],
                    'synthesis_outline': synthesis_outline,
                    'previous_dossier': dossier, 'previous_review': review, 'return': COMPOSE + rc.IDS_FOR_QUESTIONS,
                    '_execution': {'phase': 'synthesize', 'round': number, 'mode': 'compose', 'evidence_base': base}}
                text, _ = invoke('synthesize', (self.runtime / 'references/synthesize.md').read_text(), payload, offered_final, False)
                require()
                dossier = json.loads(text)
            if check_frozen(dossier, {'evidence_base': base}):
                raise ValueError('Synthesis changed registered evidence; investigator work is kept.')
            research_quality.prose(dossier)
            dossier.update({k: task[k] for k in rc.TASK_FIELDS})
            rc.write(case, 'dossier.json', json.dumps(dossier))
            status = self.helper.command(case, 'save', 'dossier.json', worker, **(
                {'reuse_context': reuse_context} if reuse_context else {}))
            if status.get('save_result') == 'no-change' and status.get('status') == 'complete':
                verified = self.helper.command(case, 'verify')
                if verified.get('status') == 'complete':
                    report('complete')
                    return rc.read_bundle(rc.output_root(case))
            report('review')
            reviewer = 'reviewer-' + secrets.token_hex(12)
            output = rc.output_root(case)
            payload = {'task': task, 'worker': reviewer, 'dossier': dossier, 'review_template': status['review_template'],
                **{key: (output / (key + '.md')).read_text() for key in ('report', 'brief', 'evidence')},
                'review_outline': review_outline,
                'return': 'Independently inspect the exact saved evidence and prose. Return complete review JSON. Read each capture and supplied original; report access gaps honestly. ' + rc.REVIEWED,
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
            if creator_review:
                from studio_core import research_decisions
                flags = research_decisions.flags(rc.read_bundle(output, complete=False)[0])
                if flags:
                    tracked['review_coverage'] = research_quality.coverage(review)
                    tracked['review_flags'] = len(flags)
                    tracked.pop('correction', None)
                    report('creator-review')
                    raise research_decisions.CreatorReview(len(flags))
            cause = rc.unreadable_originals(review, dossier)
            said = (readable(cause) if readable else '') if cause else None
            if cause and said is not None:
                raise rc.CheckCouldNotFinish(rc.objections(case), number - 1, cause, said or None)
            coverage = research_quality.coverage(review)
            if coverage['unread']:
                # Unread evidence is not a failed claim. Preserve the exact dossier:
                # the legacy single-reviewer contract cannot reuse partial attestations.
                tracked['review_coverage'] = coverage
                tracked.pop('correction', None)
                report('check-incomplete')
                raise research_quality.IncompleteCheck(coverage)
            affected = sorted(corrections(review, registry, sectioned=bool(section_policy)))
            if section_policy: research_sections.invalidate(case, review, affected)
            for stream in affected:
                self.command(case, 'collection', 'retry', {'workstream': stream, 'reason': 'The independent review requested evidence correction.'})
                report(stream=stream, state='waiting')
            notes = [item['note'] for item in review.get('facts', [])
                     if item.get('verdict') not in ('supported', 'pending') and item.get('note')]
            assessment = review.get('assessment') or {}
            if assessment.get('note'): notes.append(assessment['note'])
            with state_lock:
                tracked['correction'] = {'areas': affected, 'notes': notes}
            report('needs-revision')
        raise rc.ReviewRefused(rc.objections(case), rc.ROUNDS, rc.grouped(case))
