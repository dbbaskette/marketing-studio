"""One person decision on researched topics, then automatic material production.

Uses existing checked blueprints; no sample lesson, new research format or extra
author job. Only new schema-6 runner desks opt in. Older runs keep their gates.
"""
import re

import checks
import workspace
from workspace import WorkspaceError
from studio_core import review_policy

RECORD_SCHEMA = 6
STEP = 'review:training-plan'


def enabled(record):
    value = record.get('training_plan')
    if record.get('schema') != RECORD_SCHEMA or not isinstance(value, dict):
        return False
    if type(value.get('schema')) is not int or value['schema'] != 1:
        return False
    revision, approval = value.get('revision', 0), value.get('approved')
    return (type(revision) is int and revision >= 0 and (approval is None or
        isinstance(approval, dict) and isinstance(approval.get('signature'), str)
        and re.fullmatch(r'[0-9a-f]{64}', approval['signature']) is not None
        and approval.get('by') == 'page' and isinstance(approval.get('at'), str)))


def names(session):
    return [workspace.qualify('blueprint', level) for level in session['levels'] or [None]]


def file(root, relative):
    path = workspace.managed(root, relative)
    if path.is_symlink() or root.resolve() not in path.resolve().parents:
        raise WorkspaceError('The training plan must stay inside its training folder.')
    return path


def signature(root, session, record):
    files = {'intake': workspace.sha256_file(file(root, 'intake.md'))}
    files.update({name: workspace.sha256_file(file(root, workspace.artifact(root, session, name)['file']))
                  for name in names(session)})
    return review_policy.fingerprint({'levels': session['levels'], 'files': files,
        'revision': record['training_plan'].get('revision', 0)})


def group(root, session, record, listed, done):
    from runner import pipeline
    if not enabled(record):
        return listed, done
    positions = [i + 1 for i, step in enumerate(listed) if step.stage == 'blueprint']
    if not positions:
        return listed, done
    at = max(positions)
    step = pipeline.Step(STEP, 'review', 'Review what this training will cover',
                         'Waiting for you to review the training topics', 'blueprint')
    listed = (*listed[:at], step, *listed[at:])
    if (record['training_plan'].get('approved') or {}).get('signature') == signature(root, session, record):
        done = frozenset({*done, STEP})
    return listed, done


def clean(text):
    return re.sub(r'\s*\[(?:R:[^\]]+|unsupported)\]', '', text).strip()


def view(root, found, record):
    if found.next.kind != 'review' or found.next.step.id != STEP:
        return None
    levels = []
    for name in names(found.session):
        text = file(root, workspace.artifact(root, found.session, name)['file']).read_text()
        parsed = checks.parse_blueprint(text)
        blocks = re.split(r'(?m)^## (?=M\d)', text)[1:]
        modules = []
        for (_, module), block in zip(parsed['modules'].items(), blocks):
            items, example = [], ''
            for line in block.splitlines():
                point = re.match(r'^- K\d+\.\d+:\s*(.+)', line)
                if point and '[unsupported]' not in line:
                    items.append(clean(point.group(1)))
                if line.startswith('Example:'):
                    example = clean(line.removeprefix('Example:'))
            modules.append({'title': module['title'], 'minutes': module['minutes'],
                            'items': items, 'example': example,
                            'practice': [parsed['assessment'][ident] for ident in module['objectives']
                                         if ident in parsed['assessment']]})
        levels.append({'level': workspace.split(name)[1],
                       'objectives': [o['text'] for o in parsed['objectives'].values()],
                       'modules': modules, 'gaps': clean(parsed['open_gaps'])})
    return {'expected': signature(root, found.session, record), 'levels': levels}


def decide(engine, path, expected, decision, note=None):
    import home
    root = engine._held(path)
    if decision not in ('approve', 'changes'):
        raise WorkspaceError('Choose Build the training or Ask for changes.')
    note = (note or '').strip()
    if decision == 'changes' and (not note or len(note) > 4000):
        raise WorkspaceError('Say what should change in 4000 characters or fewer.')
    with engine.files:
        record = engine._load(root)
        found = engine._survey(root, record)
        if not enabled(record) or found.next.kind != 'review' or found.next.step.id != STEP:
            raise WorkspaceError('The training topics are not waiting for a decision.')
        if expected != signature(root, found.session, record):
            raise WorkspaceError('The training topics changed. Read the latest version before deciding.')
        if engine._run(root).workers:
            raise WorkspaceError('Wait for the work in progress to finish before deciding.')
        if record.get('problem') or record.get('question') or record.get('halt'):
            raise WorkspaceError('Resolve the stopped work before deciding on the training topics.')
        if decision == 'approve':
            record['training_plan']['approved'] = {'signature': expected, 'by': 'page', 'at': home.now()}
            said = 'approve the training topics and build the selected materials'
        else:
            for name in names(found.session):
                workspace.decide(root, name, 'revise', note, by='page')
                engine._fresh(record, name)
            record['training_plan'].pop('approved', None)
            record['training_plan']['revision'] = record['training_plan'].get('revision', 0) + 1
            said = 'revise the training topics: ' + workspace.shortened(note)
        engine._store(root, record)
        engine._commit(root, said)
    engine.carry_on(root)
    return engine.view(root)
