"""Shared host coordination over Harness Research's portable collection contract.

The helper owns packets, evidence assembly and digest validation. The host owns
isolated invocations, source access, capacity, allowance and terminal observation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from studio_core import research_contract as rc, research_sections, research_quality
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
REGISTER = 100
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
    """The execution record a new case starts with. When the installed Harness Research
    offers review units, the case keeps that as its own entry, `review`, and its independent
    check is done in units for as long as it lives (studio_core.research_units); a case
    without the entry keeps the single review whatever is installed later."""
    supported = capability(runtime)
    if not supported:
        return None
    from studio_core import research_units
    units = research_units.entry(runtime)
    return {'schema': 1, 'protocol': PROTOCOL, 'workers': min(3, max(1, int(workers))),
            'capability': supported, **({'review': units} if units else {})}


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


# A file whose modification or change time is this close to when it was hashed may still
# change within the same tick of a coarse file system clock without its times moving, so it
# is hashed again at the next check ("racy" in Git's sense). Two seconds covers the coarsest.
RACY_NS = 2_000_000_000


def _mark(path):
    """What changes whenever a file's bytes do: its modification and change times, size,
    inode and device, from lstat. None when it is not an ordinary file, or is gone."""
    try:
        found = os.lstat(path)
    except OSError:
        return None
    if not stat.S_ISREG(found.st_mode):
        return None
    return (found.st_mtime_ns, found.st_ctime_ns, found.st_size, found.st_ino, found.st_dev)


class Originals:
    """The selected originals of one research run, each with the SHA-256 it had when the
    run began, so that a check before each worker call can say whether any changed.

    An original is hashed again whenever its mark (_mark) differs from the mark it had when
    it was last hashed in this process, and whenever that hash was taken within RACY_NS of
    its last change. Otherwise it is unchanged since: a write moves its change time, which
    nothing but the system clock can set back, so its bytes are not read again. A changed,
    replaced, linked or missing original is read, and refused, exactly as before."""

    def __init__(self, paths):
        self.held = []           # [path, its hash when the run began, mark of that hash]
        for path in paths:
            mark, sha = self._read(path)
            self.held.append([path, sha, mark])

    @staticmethod
    def _read(path):
        """(mark, SHA-256) of the original now; the mark is None when the hash may not be
        trusted to stand for the file later."""
        began = time.time_ns()
        before = _mark(path)
        sha = hashlib.sha256(bytes_of(path)).hexdigest()
        if before is None or before[0] >= began - RACY_NS or before[1] >= began - RACY_NS:
            return None, sha
        return before, sha

    def changed(self) -> bool:
        """Whether any original differs from what it was when the run began."""
        for entry in self.held:
            path, expected, mark = entry
            if mark is not None and _mark(path) == mark:
                continue
            mark, sha = self._read(path)
            if sha != expected:
                return True
            entry[2] = mark
        return False


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


def case_basis(root, task, inputs, helper, areas, earlier=None):
    """The name of the case research is kept in: what it is made from and the helper's
    protocol, never the helper's version or digest, so an update of Harness Research goes on
    with the same case. A case an older Marketing Studio saved was named with the capability
    it ran on, digest and all: `earlier` is that capability, and its case is used when it is
    there and the stable one is not."""
    basis = digest([task, inputs, rc.stable(helper), areas])
    if not isinstance(earlier, dict):
        return basis
    older = digest([task, inputs, earlier, areas])
    base = rc.inside(root, str(rc.CASE))
    if not (base / basis / 'topic').exists() and (base / older / 'topic').is_dir():
        return older
    return basis


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
        self.cancelled = None   # the run's Stop, for helper commands run here (rc.run_helper)

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
            # Without a studio's call, Stop ends a command still running (rc.run_helper).
            result = rc.run_helper([shutil.which('node') or 'node',
                str(self.runtime / 'scripts/harness-research.mjs'), *args],
                rc.HELPER_SECONDS, self.cancelled)
            if result.returncode and not rc.answered(args, result.returncode, result.stdout):
                raise ValueError((result.stderr.strip().splitlines() or ['Harness Research did not finish.'])[-1])
            return json.loads(result.stdout)

    def capture_sources(self, case, terminal, sources, registration):
        if sources and registration.get('batch_capture'):
            self.command(case, 'collection', 'capture', {**terminal, 'sources': sources})
        else:
            for source in sources:
                self.command(case, 'collection', 'capture', {**terminal, 'source': source})

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
        offered, updates = [], []
        for source, filename, linked in selected:
            origin = source.get('origin', source.get('url', ''))
            original = next(e for e in inventory if e.get('filename') == filename)
            entry = next(e for e in inventory if e.get('type') == 'url' and e['origin'] == origin) if linked else original
            file = 'sources/selected/' + filename + '.txt'
            text = capture_text(source['text'], kept_copies(target, file))
            rc.write(target, file, text)
            updates.append({'id': entry['id'], 'outcome': 'captured',
                'capture_file': file, 'accessed_at': source.get('accessed_at') or now(),
                'note': 'Selected studio capture; the remote original was not automatically refreshed.'})
            offered.append({**source, 'text': text, 'file': file, 'origin': entry['origin'], 'url': entry['origin'],
                'permission': 'selected', 'path': rc.inside(target, file),
                'original': original['original_file'], 'original_path': rc.inside(target, original['original_file'])})
        # Registered a hundred at a time: one helper call for each source made a long list slow.
        for start in range(0, len(updates), REGISTER):
            self.command(target, 'asset', 'source', {'entries': updates[start:start + REGISTER]})
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
            creator_review=False, reading=False, earlier=None, review_units=None, **_):
        """`earlier` is what the run's record held of the helper before it moved to the
        installed one ({'capability', 'reuse', 'section_context'}). A case an older Marketing
        Studio saved is named and checked by those; it goes on as the same research.
        `review_units` is the case's `review` entry (research_units.of): with it, the
        independent check is done in review units; without it, by the single review. The run's
        steps, and what they share, are studio_core.research_run.Run."""
        from studio_core.research_run import Run
        return Run(self, root, task, invoke, sources, limit=limit, progress=progress,
                   allowed=allowed, cancelled=cancelled, readable=readable,
                   restart_stopped=restart_stopped, section_policy=section_policy,
                   section_context=section_context, impact=impact, input_snapshot=input_snapshot,
                   creator_review=creator_review, reading=reading, earlier=earlier,
                   review_units=review_units).go()
