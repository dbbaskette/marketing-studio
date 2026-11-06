"""Training Studio's explicit creator choice over a saved independent check."""
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
    case = research_session.case_for(root)
    output = rc.output_root(case)
    base, manifest = rc.read_bundle(output, complete=False)
    items = decisions.flags(base)
    if not items: raise WorkspaceError('There are no unresolved flags in this draft.')
    now = inputs(engine, root, record)
    saved = rc.inside(case, '.harness-research/studio-inputs.json')
    if saved.exists() and json.loads(saved.read_text()) != now:
        raise WorkspaceError('Research inputs changed. Update the research before deciding on this draft.')
    expected = decisions.digest([manifest, base['review'], now, identity(root, record), record.get('driver')])
    return {'expected': expected, 'items': items, 'inputs': now,
            'bundle_expected': decisions.digest([base, manifest]),
            'report': (output / 'report.md').read_text(), 'source': output}


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
            if verified.get('status') != 'needs-revision' or verified.get('artifact_integrity') == 'failed':
                raise WorkspaceError('Research integrity or source state changed. Recheck the draft before deciding.')
            base, _ = rc.read_bundle(shown['source'], complete=False)
            decisions.resolve(base, sent.get('choices'))
            _, manifest = decisions.publish(shown['source'], root / 'research', sent['choices'], shown['inputs'], shown['bundle_expected'])
            record['research'].update(reviewed=True, reviewed_request=None, digest=manifest['digest'],
                creator_decision={'digest': manifest['digest'], 'identity': identity(root, record)})
            record['research'].pop('again', None)
            workspace.write_atomic(root / pipeline.REPORT, (root / 'research/report.md').read_bytes())
            workspace.save(root, 'research', built=True)
            workspace.append_review(root, 'research', 'Creator decisions on independent research flags',
                'The creator explicitly included flagged material with warnings or excluded it. '
                'The original independent verdicts are retained in the research bundle. '
                'Creator approval does not claim independent verification.')
            record['problem'] = {'state': 'waiting', 'step': 'research', 'action': 'resume',
                'label': 'Continue', 'settings': True,
                'what': 'Your research choices are saved. Continue to review the report and create materials.',
                'kept': 'Included uncertainty is marked. Excluded claims and dependent passages are omitted.'}
            record['halt'] = 'paused'
            if record.get('research_execution', {}).get('progress'):
                record['research_execution']['progress']['phase'] = 'creator-approved'
            engine._store(root, record)
            engine._commit(root, 'save creator decisions on flagged research')
        except (ValueError, OSError, KeyError) as failure:
            raise WorkspaceError(str(failure)) from failure
    return engine.view(root)
