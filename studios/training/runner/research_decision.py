"""Training Studio's choice over a saved independent check: the creator's own, or, in a
training started with `research_flags: 'assistant'`, one an assistant makes so that the
training carries on (`automatic`). An automatic choice is recorded as the assistant's."""
import json
from pathlib import Path

from runner import pipeline
import home
import workspace
from workspace import WorkspaceError
from studio_core import research_contract as rc, research_decisions as decisions
from studio_core import research_session, research_impact


def inputs(engine, root, record):
    sources = engine._sources(root, record)[1] if record.get('documents') else []
    originals = {s['file']: s['original'] for s in engine.documents.listed(root)
                 if s.get('file') and s.get('original') and s.get('distinct', True)}
    sources = [{**s, **({'original_path': rc.inside(root, originals[s['file']])}
                if s.get('file') in originals else {})} for s in sources]
    questions = home.read_json(root / pipeline.PLAN, {}).get('items') or []
    return research_impact.snapshot(root, record, sources, questions)


def identity(root, record):
    return decisions.digest([research_impact.global_identity(record),
        record.get('outline_first'), record.get('research_inputs'), record.get('documents'),
        workspace.sha256_file(root / pipeline.PLAN), workspace.sha256_file(root / 'intake.md')])


def current(root, record):
    held = (record.get('research') or {}).get('creator_decision')
    if not held: return False
    facts, manifest = rc.read_bundle(root / 'research')
    return (manifest.get('owner') == decisions.OWNER and manifest['digest'] == held['digest']
            and held['identity'] == identity(root, record)
            and facts.get('creator_review') is not None)


def snapshot(engine, root, record):
    if engine._desk_change_busy(root, record) or research_session.unresolved(root):
        raise WorkspaceError('Wait for the active work to stop before deciding on this draft.')
    if (record.get('problem') or {}).get('step') != 'research' or (record.get('problem') or {}).get('settings'):
        raise WorkspaceError('This training is not waiting on its research check.')
    return _shown(engine, root, record)


def _shown(engine, root, record):
    case = research_session.case_for(root)
    output = rc.output_root(case)
    base, manifest = rc.read_bundle(output, complete=False)
    items = decisions.flags(base)
    if not items: raise WorkspaceError('There are no unresolved flags in this draft.')
    now = inputs(engine, root, record)
    saved = rc.inside(case, '.harness-research/studio-inputs.json')
    if saved.exists() and json.loads(saved.read_text()) != now:
        raise WorkspaceError('Research inputs changed. Update the research before deciding on this draft.')
    expected = decisions.digest([manifest, base.get('review'), now, identity(root, record), record.get('driver')])
    return {'expected': expected, 'items': items, 'inputs': now,
            'bundle_expected': decisions.digest([base, manifest]),
            'report': (output / 'report.md').read_text(), 'source': output}


def _keep(root, record, shown, choices, by=None, reasons=None):
    """Publish the research with these choices and record them in the run. Files held."""
    base, _ = rc.read_bundle(shown['source'], complete=False)
    decisions.resolve(base, choices, by=by, reasons=reasons)
    _, manifest = decisions.publish(shown['source'], root / 'research', choices, shown['inputs'],
                                    shown['bundle_expected'], by=by, reasons=reasons)
    record['research'].update(reviewed=True, reviewed_request=None, digest=manifest['digest'],
        creator_decision={'digest': manifest['digest'], 'identity': identity(root, record),
                          **({'by': by} if by else {})})
    record['research'].pop('again', None)
    workspace.write_atomic(root / pipeline.REPORT, (root / 'research/report.md').read_bytes())
    workspace.save(root, 'research', built=True)
    if by == decisions.ASSISTANT:
        workspace.append_review(root, 'research', 'Automatic decisions on independent research flags',
            'An assistant decided each flagged item for Training Studio: included, included with a '
            'warning, or excluded. The creator has not reviewed these choices. The original '
            'independent verdicts and the reason for each choice are retained in the research '
            'bundle. An automatic decision does not claim independent verification.')
    else:
        workspace.append_review(root, 'research', 'Creator decisions on independent research flags',
            'The creator explicitly included flagged material, optionally with warnings, or excluded it. '
            'The original independent verdicts are retained in the research bundle. '
            'Creator approval does not claim independent verification.')


CHOICES = ('include-plain', 'include', 'exclude')
GUIDANCE = (
    'An independent check flagged items in a research draft that training materials will be '
    'written from. Decide each flagged item so that the training carries on without a person. '
    'Read flagged-items with list_inputs/read_input. Each item has an id, its kind, the text, '
    'the checker\'s verdict and note, and its sources with any dates known.\n\n'
    'Choose one of three for every id:\n'
    '- "include-plain": keep it as written. This is the default. Use it whenever the flag is '
    'minor, about wording, narrowness or emphasis, or would not change what a learner is taught.\n'
    '- "include": keep it with a visible warning that it is not independently verified. Use it '
    'when the doubt is real and a learner should know, but nothing directly contradicts it.\n'
    '- "exclude": leave it out, with everything that depends on it. Use it only when BOTH hold: '
    'a source directly contradicts the item, and the item is very important to what the training '
    'teaches, so that being wrong would mislead learners.\n\n'
    'When sources disagree, the newer document wins most of the time: keep the item when the '
    'newer source supports it and an older one contradicts it, and exclude it when the newer '
    'source contradicts it. Go against the newer source only with a clear reason, such as the '
    'older one being the authoritative specification. An item whose kind is "assessment" '
    'describes the whole draft and cannot be excluded.\n\n'
    'Hand back one JSON object with submit_artifact("flag-decisions", JSON): '
    '{"choices": {id: choice}, "reasons": {id: one plain sentence}}. Decide every id, add none, '
    'and stop after that.')


def validate(text_value, spec):
    """The worker tools' check of the decisions an assistant hands back."""
    try:
        value = json.loads(text_value)
        choices, reasons = value.get('choices'), value.get('reasons') or {}
        wanted = spec['ids']
        if not isinstance(choices, dict) or not isinstance(reasons, dict) or set(choices) != set(wanted):
            raise ValueError('Give one choice for every flagged id, and no other: ' + ', '.join(wanted) + '.')
        for ident, choice in choices.items():
            if choice not in CHOICES:
                raise ValueError(f'{ident}: choose one of ' + ', '.join(CHOICES) + '.')
            if choice == 'exclude' and ident in spec.get('whole', ()):
                raise ValueError(f'{ident} describes the whole draft and cannot be excluded.')
        kept = {'choices': choices, 'reasons': {ident: str(reasons.get(ident) or '')[:400] for ident in choices}}
        return [], [], [], json.dumps(kept, ensure_ascii=False, indent=2) + '\n'
    except (ValueError, AttributeError, KeyError) as error:
        return [str(error)], [], [], text_value


def enabled(record):
    return record.get('research_flags') == decisions.ASSISTANT


def automatic(engine, root, run):
    """Have an assistant decide the flags the independent check left, publish the research
    with its choices and let the training carry on. Returns False when there is nothing it
    can decide here, and the creator's stop stands. A job that hands nothing back, or
    exclusions that would leave no evidence, fall back to including every item with a
    warning: the training carries on and each item says it is unverified."""
    with engine.files:
        record = engine._load(root)
        try:
            shown = _shown(engine, root, record)
        except (WorkspaceError, ValueError, OSError, KeyError):
            return False
    base, _ = rc.read_bundle(shown['source'], complete=False)
    dated = {s['title']: {key: s[key] for key in ('published', 'date', 'updated', 'captured_at', 'retrieved_at')
                          if s.get(key)} for s in base.get('sources', [])}
    items = [{**item, 'sources': [{**source, **dated.get(source['title'], {})} for source in item['sources']]}
             for item in shown['items']]
    ids = [item['id'] for item in items]
    whole = [item['id'] for item in items if item['kind'] == 'assessment']
    work = pipeline.Work(GUIDANCE, 'Decide the flagged research items for this training.\n'
        + pipeline._about(root, workspace.load(root)), 'write',
        {'inputs': {'flagged-items': json.dumps(items, ensure_ascii=False, indent=2)},
         'artifacts': {'flag-decisions': {'kind': 'flag-decisions', 'ids': ids, 'whole': whole}},
         'ask': False, 'fetch': False}, 'flag-decisions')
    step = pipeline.Step('research-flags', 'agent', 'Decide on flagged research',
                         'Deciding on flagged research', 'research')
    outcome, handed, started, folder = engine._job(root, run, step, work)
    if outcome.reason == 'stopped' or run.stop.is_set():
        return False
    accepted = (handed.get('artifacts') or {}).get('flag-decisions')
    fallback = {ident: 'include' for ident in ids}
    why = {ident: 'No automatic decision was returned, so this is included with a warning.' for ident in ids}
    decided = json.loads(accepted['text']) if accepted else {'choices': fallback, 'reasons': why}
    with engine.files:
        record = engine._load(root)
        try:
            try:
                _keep(root, record, shown, decided['choices'], decisions.ASSISTANT, decided['reasons'])
            except ValueError:
                # the exclusions leave nothing to teach from: keep everything, with warnings
                _keep(root, record, shown, fallback, decisions.ASSISTANT, {
                    ident: 'Excluding what was chosen left no usable evidence, so this is '
                           'included with a warning.' for ident in ids})
        except (ValueError, OSError, KeyError):
            return False
        if record.get('research_execution', {}).get('progress'):
            record['research_execution']['progress']['phase'] = 'assistant-decided'
        engine._tried(record, step.id, started, outcome.seconds, 'kept', **engine._cost(outcome))
        engine._store(root, record)
        engine._commit(root, 'keep an assistant\'s decisions on flagged research')
    return True


def dispatch(engine, path, sent):
    if not isinstance(path, (str, Path)) or not isinstance(sent, dict):
        raise WorkspaceError('Choose a saved training for this decision.')
    root = engine._held(path)
    with engine.files:
        record = engine._load(root)
        try:
            shown = snapshot(engine, root, record)
            if sent.get('action') == 'read':
                return {key: shown[key] for key in ('expected', 'items', 'report')}
            if sent.get('action') != 'save' or sent.get('expected') != shown['expected']:
                raise WorkspaceError('This draft or its inputs changed. Reopen the current flags before saving.')
            tool = rc.matching(engine.research(), record.get('research_contract'))
            if tool is None: raise WorkspaceError('Restore the saved research helper before continuing.')
            verified = tool._json('synthesis', 'verify', '--project', str(research_session.case_for(root)))
            if verified.get('status') not in ('needs-revision', 'draft') or verified.get('artifact_integrity') == 'failed':
                raise WorkspaceError('Research integrity or source state changed. Recheck the draft before deciding.')
            base, _ = rc.read_bundle(shown['source'], complete=False)
            _keep(root, record, shown, sent.get('choices'))
            record['problem'] = {'state': 'waiting', 'step': 'research', 'action': 'resume',
                'label': 'Continue', 'settings': True, 'creator_saved': True,
                'what': 'Your research choices are saved. Continue to review the report and create materials.',
                'kept': 'Your inclusion and warning choices are applied. Excluded claims and dependent passages are omitted. Independent-check notes are kept in the evidence.'}
            record['halt'] = 'paused'
            if record.get('research_execution', {}).get('progress'):
                record['research_execution']['progress']['phase'] = 'creator-approved'
            engine._store(root, record)
            engine._commit(root, 'save creator decisions on flagged research')
        except (ValueError, OSError, KeyError) as failure:
            raise WorkspaceError(str(failure)) from failure
    return engine.view(root)
