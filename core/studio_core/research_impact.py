"""Reviewable research refresh scope; accepted evidence is never an approval receipt."""
import copy
import hashlib
import json
from pathlib import Path
import secrets
import time
from studio_core import research_contract as rc, research_session as session, research_sections as sections


def inventory(sources):
    return sorted([{'name': source['file'], 'origin': source.get('origin', source.get('url', '')),
        'permission': source.get('permission', 'selected'), 'title': source.get('title'), 'source_date': source.get('source_date'),
        'text': hashlib.sha256(source['text'].encode()).hexdigest(),
        'original': hashlib.sha256(Path(source['original_path']).read_bytes()).hexdigest()
            if source.get('original_path') else None} for source in sources], key=lambda row: row['name'])


def global_identity(record):
    return sections.fingerprint({key: record.get(key) for key in
        ('form', 'brief', 'research_from', 'research_contract', 'model_profiles', 'deck_content')})


def snapshot(root, record, sources, questions):
    return {'schema': 1, 'global': global_identity(record), 'sources': inventory(sources),
        'questions': copy.deepcopy(questions)}


def preview(root, record, sources, questions, outputs=()):
    """No writes, model jobs, or fetched sources. Unknown dependency changes stay broad."""
    if not sections.enabled(record): return None
    case = session.case_for(root)
    path = case / '.harness-research/studio-inputs.json'
    if not path.is_file(): return None
    prior = json.loads(path.read_bytes())
    current = snapshot(root, record, sources, questions)
    old, new = ({row['name']: row for row in value['sources']} for value in (prior, current))
    changed = [{'name': name, 'kind': 'added' if name not in old else 'removed' if name not in new else 'changed'}
        for name in sorted(old.keys() | new.keys()) if old.get(name) != new.get(name)]
    broad = prior.get('global') != current['global'] or any(row['kind'] != 'added' for row in changed)
    old_questions = {row['id']: row for row in prior['questions']}
    rows = [{'id': row['id'], 'title': row.get('question') or row.get('text') or row['id'],
        'required': broad or old_questions.get(row['id']) != row} for row in questions]
    # Explicit refresh without changed supplied inputs must revisit every area: web pages
    # may have changed, and no hidden source relevance guess can justify retaining them.
    if not changed: broad = True
    if broad:
        for row in rows: row['required'] = True
    basis = sections.fingerprint([current, prior, outputs])
    return {'schema': 1, 'expected': basis, 'sections': rows, 'changed_inputs': changed,
        'broad_required': broad, 'outputs': list(outputs),
        'final_check': 'The assembled research needs a fresh independent check. Changed claims update their dependent materials; slide pixels and neighbors remain subject to exact-revision review.',
        'reuse_note': 'Choose every section the added inputs or cross-section dependencies can affect. Unselected sections retain validated evidence and drafts, never user approval.'}


def confirm(root, record, sources, questions, supplied, outputs=()):
    plan = preview(root, record, sources, questions, outputs)
    if plan is None: return None
    if not isinstance(supplied, dict) or supplied.get('expected') != plan['expected']:
        raise ValueError('Review the current affected-work preview before refreshing research.')
    ids = supplied.get('sections')
    available = {row['id'] for row in plan['sections']}
    required = {row['id'] for row in plan['sections'] if row['required']}
    if not isinstance(ids, list) or not ids or not all(isinstance(ident, str) for ident in ids) or len(set(ids)) != len(ids) or not set(ids) <= available or not required <= set(ids):
        raise ValueError('Select the affected sections, including every required section.')
    case = session.case_for(root)
    return {'schema': 1, 'from': str(case.relative_to(root)), 'affected': [
        'area-' + session.digest(ident)[:40] for ident in ids],
        'input': snapshot(root, record, sources, questions), 'expected': plan['expected']}


def reuse(workflow, root, case, task, areas, intent, context, require):
    """Import unchanged accepted packets through the supported host protocol, checking bytes."""
    if not intent or intent.get('schema') != 1: return
    previous = rc.inside(root, intent['from'])
    if previous == case: return
    old_path = previous / '.harness-research/studio-inputs.json'
    if not old_path.is_file(): return
    old = json.loads(old_path.read_bytes())
    current = intent['input']
    if old.get('global') != current['global']: return
    old_inputs, new_inputs = ({row['name']: row for row in value['sources']} for value in (old, current))
    if any(new_inputs.get(name) != row for name, row in old_inputs.items()): return
    context_current(root, task, intent)
    old_context = previous / '.harness-research/studio-section-context.json'
    if not old_context.is_file() or json.loads(old_context.read_bytes()) != context: return
    old_status = workflow.command(previous, 'collection', 'status')
    if old_status.get('status') == 'stale': return
    state = json.loads((previous / '.harness-research/collection.json').read_bytes())
    accepted = {row['id']: row for row in state['workstreams'] if row['attempts'] and row['attempts'][-1]['status'] == 'accepted'}
    old_questions = {row['id']: row for row in old['questions']}
    old_inventory = json.loads((previous / 'sources.json').read_bytes())['entries']
    new_inventory = json.loads((case / 'sources.json').read_bytes())['entries']
    reused = []
    for area in areas:
        require()
        ident = area['id']
        if ident in intent['affected'] or ident not in accepted or any(old_questions.get(q['id']) != q for q in area['questions']): continue
        current_status = workflow.command(case, 'collection', 'status')
        if any(row['id'] == ident and row['status'] == 'accepted' for row in current_status['workstreams']): continue
        attempt = accepted[ident]['attempts'][-1]
        packet_path = rc.inside(previous, attempt['packet']['file'])
        raw = packet_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != attempt['packet']['sha256']: raise ValueError('An earlier accepted research packet changed; preserve it for inspection.')
        packet = json.loads(raw)
        registration = workflow.command(case, 'collection', 'register', {'workstream': ident,
            'investigator': packet['investigator'], 'invocation': 'retained-evidence-' + secrets.token_hex(16)})
        terminal = {'workstream': ident, 'investigator': packet['investigator'], 'attempt': registration['registration']['number']}
        try:
            for source in packet['sources']:
                before = copy.deepcopy(source)
                if source['permission'] == 'selected':
                    entry = next((row for row in old_inventory if row['origin'] == source['origin'] and row.get('original_file')), None)
                    current_entry = next((row for row in new_inventory if entry and row.get('filename') == entry.get('filename')
                        and row.get('original_sha256') == entry.get('original_sha256')), None)
                    if entry and current_entry:
                        # File origins name this case's retained immutable input directory.
                        # The original hash and logical filename, not a mutable alias, bind relocation.
                        source['origin'] = current_entry['origin']
                for key in ('file', 'original_file'):
                    if before.get(key): rc.write(case, source[key], rc.inside(previous, before[key]).read_bytes())
                if source['permission'] == 'public':
                    workflow.command(case, 'asset', 'source', {'id': 'source-' + secrets.token_hex(12), 'role': 'discovered',
                        'origin': source['origin'], 'permission': 'public', 'outcome': 'captured', 'capture_file': source['file'], 'accessed_at': session.now()})
                workflow.command(case, 'collection', 'capture', {**terminal, 'source': source})
            workflow.command(case, 'collection', 'finish', {**terminal, 'outcome': 'completed', 'note': 'Host revalidated retained immutable evidence; no provider invocation.'})
            workflow.command(case, 'collection', 'accept', {**packet, **terminal,
                'request_digest': registration['request_digest'], 'generation': registration['generation']})
        except BaseException:
            try: workflow.command(case, 'collection', 'finish', {**terminal, 'outcome': 'failed', 'note': 'Retained-evidence validation ended without a provider invocation.'})
            except ValueError: pass
            raise
        reused.append(ident)
    # Contributions are draft cache entries. Their checked basis still decides reuse.
    drafts = previous / '.harness-research/studio-combining.json'
    target = case / '.harness-research/studio-combining.json'
    if drafts.is_file() and not target.exists():
        saved = json.loads(drafts.read_bytes())
        saved['sections'] = {key: value for key, value in saved['sections'].items() if key in reused}
        saved['final'] = None
        rc.write(case, str(target.relative_to(case)), json.dumps(saved))


def native_sources(engine, root, record, product):
    from runner import documents
    sources = engine._sources(root, {**record, 'documents': {**(record.get('documents') or {}), 'later': []}})[1] if product == 'training' else engine._offered(root, engine._research_from(root, record))
    kept = getattr(engine, 'documents', None) or documents
    originals = {row['file']: row['original'] for row in kept.listed(root)
        if row.get('file') and row.get('original') and row.get('distinct', True)}
    return [{**source, **({'original_path': rc.inside(root, originals[source['file']])}
        if source.get('file') in originals else {})} for source in sources]


def native(engine, root, record, product, supplied=None):
    if not sections.enabled(record): return None
    case = session.case_for(root)
    marker = case / '.harness-research/studio-inputs.json'
    if not marker.is_file(): return None  # No capture reads before the approved scan/research.
    run = engine._run(root)
    if getattr(run, 'busy', False) or getattr(run, 'workers', None):
        if supplied is not None: raise ValueError('Wait for the current work to finish before changing research.')
        return None
    if product == 'training':
        from runner import pipeline
        import workspace
        plan = Path(root) / pipeline.PLAN
        questions = json.loads(plan.read_bytes()).get('items') or [] if plan.is_file() else []
        outputs = [{'name': name, 'depends_on': [q['id'] for q in questions], 'scope': 'Dependent sections after changed findings are checked'} for name in workspace.artifact_names(Path(root), workspace.load(root))]
    else:
        plan = Path(root) / 'research/plan.json'
        questions = json.loads(plan.read_bytes()).get('items') or [] if plan.is_file() else []
        outputs = [{'name': 'Slide text and dependent slide sections', 'depends_on': [q['id'] for q in questions], 'scope': 'Changed content and adjacent inspection scope'}, {'name': 'Exact final deck consistency', 'depends_on': [q['id'] for q in questions], 'scope': 'Required for every new delivered revision'}]
    from runner import documents
    kept = getattr(engine, 'documents', None) or documents
    key = sections.fingerprint([str(case), marker.stat().st_mtime_ns, global_identity(record),
        record.get('documents'), record.get('research_inputs'), kept.listed(root), questions, outputs])
    cache = getattr(engine, '_research_impact_cache', {})
    found = cache.get(str(root))
    if supplied is None and found and found['key'] == key and time.monotonic() < found['until']:
        return copy.deepcopy(found['value'])
    sources = native_sources(engine, root, record, product)
    if supplied is not None:
        cache.pop(str(root), None)  # Confirmation always hashes actual bytes again.
        return confirm(root, record, sources, questions, supplied, outputs)
    value = preview(root, record, sources, questions, outputs)
    if len(cache) >= 16 and str(root) not in cache: cache.pop(next(iter(cache)))
    cache[str(root)] = {'key': key, 'until': time.monotonic() + 30, 'value': copy.deepcopy(value)}
    engine._research_impact_cache = cache
    return value


def context_current(root, task, intent):
    if not intent: return
    previous = rc.inside(root, intent['from'])
    task_context = previous / '.harness-research/studio-task-context.json'
    if not task_context.is_file() or json.loads(task_context.read_bytes()) != {key: task[key] for key in rc.TASK_FIELDS if key != 'planning_questions'}:
        raise ValueError('The research scope or audience changed after the preview. Review the broad affected scope before continuing.')
