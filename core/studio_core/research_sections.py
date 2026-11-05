"""Durable section authoring over the existing immutable collection registry.

These are validated draft contributions, never reusable semantic-review receipts.
The supported whole-dossier independent review remains the final boundary.
"""
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextvars
import hashlib
import json
import secrets
import threading
from pathlib import Path

from studio_core import research_contract as rc, stops

PROTOCOL = 'studio-section-combining-v1'
TRAINING_SCHEMA, PRESENTATION_SCHEMA = 8, 6
SECONDS = 300
FINAL_GUIDANCE = '''Assemble the final brief from completed section contributions.
The section authors have already written the findings and report sections. Do not
rewrite them, repeat their research, or perform the independent source check here.
Use only completed_sections as the basis for a short connected brief, at most two
introductory report sections, and comparisons only when they help answer the task.
Preserve uncertainty, limitations and gaps. Reference the supplied finding IDs;
do not introduce facts or unsupported conclusions. Return schema 2 with sections,
brief and optional comparisons. Sources remain available for structural validation;
independent reviewers check the exact evidence and prose in the next stage.'''


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def reuse_capability(runtime):
    path = Path(runtime) / 'references/synthesis-reuse-capability.json'
    if not path.is_file() or path.is_symlink(): return None
    value = json.loads(path.read_bytes())
    if value.get('schema') != 1 or value.get('protocol') != 'harness-synthesis-reuse-v1' \
            or value.get('state_schema') != 3 or value.get('output_schema') != 2:
        return None
    return {'protocol': value['protocol'], 'digest': fingerprint(value)}


def pin(runtime=None):
    return {'schema': 1, 'protocol': PROTOCOL, 'seconds': SECONDS, 'more_time': {},
        'reuse': reuse_capability(runtime) if runtime else None}


def enabled(record):
    value = record.get('section_synthesis')
    return (isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1
        and (value.get('reuse') is None or isinstance(value.get('reuse'), dict)
            and value['reuse'].get('protocol') == 'harness-synthesis-reuse-v1'
            and isinstance(value['reuse'].get('digest'), str) and len(value['reuse']['digest']) == 64)
        and value.get('protocol') == PROTOCOL and type(value.get('seconds')) is int
        and 1 <= value['seconds'] <= 3600 and isinstance(value.get('more_time'), dict)
        and all(isinstance(key, str) and type(seconds) is int and 1 <= seconds <= 86_400
                for key, seconds in value['more_time'].items()))


def grant(record, problem):
    section = problem.get('section')
    if not section or not enabled(record):
        return False
    record['section_synthesis']['more_time'][section] = min(86_400, stops.more_time(problem['seconds']))
    return True


def timeout(engine, root, error, product):
    section = getattr(error, 'section', None)
    if not section:
        return False
    seconds = error.section_seconds
    current = engine._load(root)['section_synthesis']
    own = section in current['more_time']
    engine._problem(root, 'research', 'failed', stops.timed_out(
        'Assembling the final brief' if section == 'final' else 'Combining this section',
        seconds, 1, 'training' if product == 'training' else 'deck', own),
        'Completed research areas and section contributions are kept. Retry works only on unfinished contributions.',
        stops.MORE_TIME, detail={'seconds': seconds, 'section': section})
    return True


def deduplicate(facts):
    """Collapse exact claims with identical source/quotation context; retain distinctions."""
    seen, kept = set(), []
    for fact in facts:
        citations = sorted((item['source'], ' '.join(item['quote'].split()), item.get('locator') or '')
                           for item in fact['citations'])
        identity = fingerprint([' '.join(fact['statement'].split()), citations])
        if identity not in seen:
            kept.append(copy.deepcopy(fact)); seen.add(identity)
    return kept


def prepared(value, spec):
    mode = spec['research_mode']
    if mode == 'compose-section':
        if set(value) - {'schema', 'findings', 'sections'} or not isinstance(value.get('findings'), list) \
                or not isinstance(value.get('sections'), list) or not value['sections']:
            raise ValueError('Return schema 2, findings and nonempty report sections only. Evidence is fixed; the final author writes the brief.')
        if spec['evidence_base']['facts'] and not value['findings']:
            raise ValueError('Return at least one finding from this section’s evidence.')
        return {**copy.deepcopy(spec['evidence_base']), **value}
    if mode == 'compose-final':
        if set(value) - {'schema', 'sections', 'brief', 'comparisons'} \
                or not isinstance(value.get('brief'), list) or not value['brief'] \
                or not isinstance(value.get('sections', []), list) or len(value.get('sections', [])) > 2:
            raise ValueError('Return schema 2, an authored brief, up to two introduction sections and optional comparisons. Completed findings/sections stay fixed.')
        parts = spec['contributions']
        return {**copy.deepcopy(spec['evidence_base']), 'findings': copy.deepcopy(parts['findings']),
            **value, 'sections': [*value.get('sections', []), *copy.deepcopy(parts['sections'])]}
    raise ValueError('Unknown section authoring mode.')


def canonical(value, area):
    """Namespace local prose IDs, preserving primary approved question IDs and all words."""
    primary = area['questions'][0]['id']
    mapping = {finding['id']: finding['id'] if finding['id'] == primary
               else 'finding-' + fingerprint([area['id'], finding['id']])[:40]
               for finding in value['findings']}
    def refs(item):
        if isinstance(item, dict):
            return {key: [mapping.get(ref, ref) for ref in part]
                    if key in ('refs', 'support', 'counter') and isinstance(part, list)
                    else refs(part) for key, part in item.items()}
        return [refs(part) for part in item] if isinstance(item, list) else item
    found = refs(copy.deepcopy(value))
    for finding in found['findings']: finding['id'] = mapping[finding['id']]
    for index, section in enumerate(found['sections']):
        section['id'] = primary if index == 0 else 'report-' + fingerprint([area['id'], section['id']])[:40]
    return {key: found[key] for key in ('findings', 'sections')}


def combine(case, task, areas, registry, base, offered, invoke, *, round, guidance, policy,
            require, notify, context=None):
    """Keep completed units; a failed peer never causes their author to run again."""
    path = rc.inside(case, '.harness-research/studio-combining.json')
    saved = json.loads(path.read_bytes()) if path.exists() else {'schema': 1, 'sections': {}, 'final': None}
    if not isinstance(saved, dict) or saved.get('schema') != 1 or not isinstance(saved.get('sections'), dict):
        raise ValueError('Saved section combining cannot be read; preserve it for inspection.')
    lock = threading.RLock()
    progress = [{'id': area['id'], 'questions': copy.deepcopy(area['questions']), 'status': 'waiting'} for area in areas]
    def publish(ident=None, state=None):
        with lock:
            for row in progress:
                if row['id'] == ident: row['status'] = state
                receipt = saved['sections'].get(row['id']) or {}
                if row['status'] == 'kept' and receipt.get('digest') == fingerprint(receipt.get('content')):
                    content = receipt['content']
                    left = 24000
                    excerpts = []
                    for section in content.get('sections', [])[:12]:
                        words = '\n\n'.join(str(block.get('text', '')) for block in section.get('blocks', []))
                        excerpts.append({'title': str(section.get('title', ''))[:500], 'text': words[:left]})
                        left -= min(left, len(words))
                        if left <= 0: break
                    row['preview'] = {'basis': receipt['basis'], 'digest': receipt['digest'],
                        'sections': excerpts, 'truncated': left <= 0,
                        'sources': [{'title': source.get('title', source.get('id', 'Source')),
                                     'permission': source.get('permission', 'unknown')}
                                    for source in evidence(next(area for area in areas if area['id'] == row['id']))['sources'][:40]]}
                else: row.pop('preview', None)
            notify(copy.deepcopy(progress))
    def store():
        rc.write(case, str(path.relative_to(case)), json.dumps(saved))
    def kept(value, key):
        if not value or value.get('basis') != key: return False
        if value.get('digest') != fingerprint(value.get('content')):
            raise ValueError('A saved section contribution changed. Preserve and inspect the checkpoint.')
        return not value.get('needs_revision')
    owners = {row['workstream']: set(row['facts'].values()) for row in registry['mappings']}
    def evidence(area):
        facts = [fact for fact in base['facts'] if fact['id'] in owners[area['id']]]
        cited = {citation['source'] for fact in facts for citation in fact['citations']}
        return {**{key: base[key] for key in ('schema', *rc.TASK_FIELDS)},
            'sources': [source for source in base['sources'] if source['id'] in cited], 'facts': facts}
    def one(area):
        require()
        selected = evidence(area)
        source_files = {source['file'] for source in selected['sources']}
        captures = [source for source in offered if source['file'] in source_files]
        bound = copy.deepcopy(selected)
        for source in bound['sources']:
            if source['permission'] == 'selected' and source.get('original_file') and not source['origin'].startswith(('https://', 'http://')):
                source['origin'] = 'retained-original:' + source['original_file']
        identity = fingerprint([PROTOCOL, {key: (area['questions'] if key == 'planning_questions' else (context or {}).get('scope_identity', task[key]) if key == 'scope' else task[key]) for key in rc.TASK_FIELDS}, area,
            bound, [[source['file'], hashlib.sha256(rc.inside(case, source['file']).read_bytes()).hexdigest(),
                hashlib.sha256(rc.inside(case, source['original']).read_bytes()).hexdigest() if source.get('original') else None]
                for source in captures], context])
        with lock:
            receipt = saved['sections'].get(area['id'])
            if kept(receipt, identity):
                publish(area['id'], 'kept'); return
        publish(area['id'], 'working')
        worker = 'section-writer-' + secrets.token_hex(12)
        view = {**selected, 'facts': deduplicate(selected['facts'])}
        payload = {'task': {key: task[key] for key in rc.TASK_FIELDS}, 'worker': worker,
            'section': area, 'evidence': view, 'gaps': [gap for gap in registry['gaps'] if gap['workstream'] == area['id']],
            'return': 'Write only this approved section’s findings and report sections. Return schema 2 with findings and sections. No sources, facts, brief or comparisons. Use the approved question ID as the primary finding ID. Preserve qualifications; unsupported material is a gap.',
            '_execution': {'phase': 'synthesize', 'round': round, 'stream': area['id'], 'workers': min(3, len(areas)),
                'mode': 'compose-section', 'evidence_base': selected,
                'seconds': policy['more_time'].get(area['id'], policy['seconds']), 'section': area['id']}}
        if receipt and receipt.get('basis') == identity and receipt.get('needs_revision'):
            payload.update(previous_contribution=receipt['content'], previous_review=receipt.get('review'))
        try:
            text, _ = invoke('synthesize', guidance, payload, captures, False)
            require()
            value = json.loads(text)
            if any(value.get(key) != selected[key] for key in ('sources', 'facts')):
                raise ValueError('A section changed registered evidence; accepted investigator work is kept.')
            content = canonical(value, area)
            with lock:
                saved['sections'][area['id']] = {'basis': identity, 'worker': worker,
                    'content': content, 'digest': fingerprint(content)}
                saved['final'] = None; store()
            publish(area['id'], 'kept')
        except BaseException:
            publish(area['id'], 'failed'); raise
    publish()
    failures = []
    with ThreadPoolExecutor(max_workers=min(3, max(1, policy.get('workers', 3)))) as pool:
        futures = [pool.submit(contextvars.copy_context().run, one, area) for area in areas]
        for future in as_completed(futures):
            try: future.result()
            except BaseException as error: failures.append(error)
    if failures: raise failures[0]
    require()
    contributions = {key: [part for area in areas for part in saved['sections'][area['id']]['content'][key]]
                     for key in ('findings', 'sections')}
    key = fingerprint([PROTOCOL, task, contributions, base, context])
    if kept(saved.get('final'), key):
        return copy.deepcopy(saved['final']['content']), saved['final']['worker']
    worker = 'final-writer-' + secrets.token_hex(12)
    payload = {'task': {key: task[key] for key in rc.TASK_FIELDS}, 'worker': worker,
        'completed_sections': copy.deepcopy(contributions),
        'return': 'Write a short introduction (up to two sections), cross-section comparisons if useful, and an authored brief from the completed contributions. Return schema 2, sections, brief and optional comparisons only. Do not repeat findings or invent facts. Cite the completed finding IDs.',
        '_execution': {'phase': 'synthesize', 'round': round, 'stream': 'final', 'mode': 'compose-final', 'section': 'final',
            'evidence_base': base, 'contributions': contributions, 'seconds': policy['more_time'].get('final', policy['seconds'])}}
    if (saved.get('final') or {}).get('basis') == key and saved['final'].get('needs_revision'):
        prior = saved['final']['content']
        payload['previous_final'] = {name: prior.get(name) for name in ('brief', 'comparisons')}
        payload['previous_review'] = saved['final'].get('review')
    text, _ = invoke('synthesize', FINAL_GUIDANCE, payload, offered, False)
    require()
    value = json.loads(text)
    with lock:
        saved['final'] = {'basis': key, 'content': value, 'worker': worker, 'digest': fingerprint(value)}; store()
    return value, worker


def invalidate(case, review, evidence_areas=()):
    """Keep valid drafts; rerun only contributions named by a rejected check."""
    path = rc.inside(case, '.harness-research/studio-combining.json')
    if not path.exists(): return
    saved = json.loads(path.read_bytes())
    bad_findings = {row['id'] for row in review.get('findings', []) if row.get('verdict') not in ('supported', 'pending')}
    bad_prose = [row for row in review.get('prose', []) if row.get('verdict') not in ('supported', 'pending')]
    any_named = bool(bad_findings or bad_prose or evidence_areas)
    assessment = review.get('assessment') or {}
    broad = not any_named and assessment.get('coverage') == 'needs-revision'
    for ident, receipt in saved['sections'].items():
        content = receipt['content']
        names = {finding['id'] for finding in content['findings']}
        prose = [row for row in bad_prose if any(row['id'].startswith(section['id'] + ':') for section in content['sections'])]
        if ident in evidence_areas or bad_findings & names or prose or broad:
            receipt.update(needs_revision=True, review={'findings': [row for row in review.get('findings', []) if row['id'] in names and row['id'] in bad_findings],
                'prose': prose, 'assessment': assessment})
    if saved.get('final'):
        saved['final'].update(needs_revision=True, review={'prose': bad_prose, 'assessment': assessment})
    rc.write(case, str(path.relative_to(case)), json.dumps(saved))
