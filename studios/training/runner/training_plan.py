"""One person decision on what a training covers, then automatic material production.

Schema-6 runner desks put it after research, on the checked blueprints. Schema-7 desks
(scan, outline, then fill in: `outline_first`) put it before research, on the training
outline drafted from a quick scan, and research each approved section afterwards. Older
runs keep their gates.
"""
import re

import checks
import workspace
from workspace import WorkspaceError
from studio_core import review_policy

RECORD_SCHEMA = 6
OUTLINE_SCHEMA = 7       # outline_first.RECORD_SCHEMA: the gate comes before research
STEP = 'review:training-plan'


def enabled(record):
    value = record.get('training_plan')
    if record.get('schema') not in (RECORD_SCHEMA, OUTLINE_SCHEMA) or not isinstance(value, dict):
        return False
    wanted = 1 if record['schema'] == RECORD_SCHEMA else 2
    if type(value.get('schema')) is not int or value['schema'] != wanted:
        return False
    revision, approval = value.get('revision', 0), value.get('approved')
    return (type(revision) is int and revision >= 0 and (approval is None or
        isinstance(approval, dict) and isinstance(approval.get('signature'), str)
        and re.fullmatch(r'[0-9a-f]{64}', approval['signature']) is not None
        and approval.get('by') == 'page' and isinstance(approval.get('at'), str)))


def outlined(record):
    """Whether the gate is on the training outline, before research (#297)."""
    return enabled(record) and record.get('schema') == OUTLINE_SCHEMA


def names(session):
    return [workspace.qualify('blueprint', level) for level in session['levels'] or [None]]


def revision_levels(session, note, selected=None):
    """Use explicit scope or named training levels; never broaden an invalid scope."""
    available = session['levels'] or [None]
    if selected is None:
        mentioned = list(dict.fromkeys(re.findall(r'\b(?:level\s+)?(101|201|301|401)\b', note, re.I)))
        selected = available if re.search(r'\b(?:all|both|every)\s+levels\b|\bwhole\s+training\b', note, re.I) else mentioned or available
    if not isinstance(selected, list) or not selected or any(level not in available for level in selected):
        raise WorkspaceError('Choose levels included in this training before requesting changes.')
    return [level for level in available if level in selected]


def file(root, relative):
    path = workspace.managed(root, relative)
    if path.is_symlink() or root.resolve() not in path.resolve().parents:
        raise WorkspaceError('The training plan must stay inside its training folder.')
    return path


def signature(root, session, record):
    if outlined(record):
        from runner import outline_first
        return review_policy.fingerprint({'outline': workspace.sha256_file(file(root, outline_first.OUTLINE)),
            'revision': record['training_plan'].get('revision', 0)})
    files = {'intake': workspace.sha256_file(file(root, 'intake.md'))}
    files.update({name: workspace.sha256_file(file(root, workspace.artifact(root, session, name)['file']))
                  for name in names(session)})
    return review_policy.fingerprint({'levels': session['levels'], 'files': files,
        'revision': record['training_plan'].get('revision', 0)})


def group(root, session, record, listed, done):
    from runner import pipeline
    if not enabled(record):
        return listed, done
    if outlined(record):
        positions = [i + 1 for i, step in enumerate(listed) if step.id == 'scan']
        step = pipeline.Step(STEP, 'review', 'Review the training outline',
                             'Waiting for you to review the training outline', 'research-plan')
    else:
        positions = [i + 1 for i, step in enumerate(listed) if step.stage == 'blueprint']
        step = pipeline.Step(STEP, 'review', 'Review what this training will cover',
                             'Waiting for you to review the training topics', 'blueprint')
    if not positions:
        return listed, done
    at = max(positions)
    listed = (*listed[:at], step, *listed[at:])
    if (record['training_plan'].get('approved') or {}).get('signature') == signature(root, session, record):
        done = frozenset({*done, STEP})
    return listed, done


def clean(text):
    return re.sub(r'\s*\[(?:R:[^\]]+|unsupported)\]', '', text).strip()


def view(root, found, record):
    if found.next.kind != 'review' or found.next.step.id != STEP:
        return None
    if outlined(record):
        from runner import outline_first
        return outline_first.view(root, found, record, signature(root, found.session, record))
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


def decide(engine, path, expected, decision, note=None, levels=None, outline=None):
    """Approve what the training covers, or ask for changes. On the training outline
    (`outlined`), approving carries the outline as the person edited it, kept before the
    approval is bound to it; nothing expensive has started before this."""
    import home
    root = engine._held(path)
    if outline is not None:
        from runner import outline_first
        with engine.files:
            if not outlined(engine._load(root)):
                raise WorkspaceError('This training has no outline to edit.')
        if decision != 'approve':
            raise WorkspaceError('Edit the outline, then approve it to start the research.')
        return _approve_outline(engine, root, expected, outline_first.edited(outline))
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
        if outlined(record) and decision != 'approve':
            raise WorkspaceError('Edit the outline, then approve it to start the research.')
        if decision == 'approve':
            record['training_plan']['approved'] = {'signature': expected, 'by': 'page', 'at': home.now()}
            said = 'approve the training topics and build the selected materials'
        else:
            selected = revision_levels(found.session, note, levels)
            for level in selected:
                name = workspace.qualify('blueprint', level)
                workspace.decide(root, name, 'revise', note, by='page')
                engine._fresh(record, name)
            record['training_plan'].pop('approved', None)
            record['training_plan']['revision'] = record['training_plan'].get('revision', 0) + 1
            said = 'revise the training topics: ' + workspace.shortened(note)
        engine._store(root, record)
        engine._commit(root, said)
    engine.carry_on(root)
    return engine.view(root)


def _waiting(engine, root, expected):
    """The run, its survey and its record, once the outline gate is the decision waiting
    and nothing is in hand. Call holding the files lock."""
    record = engine._load(root)
    found = engine._survey(root, record)
    if not outlined(record) or found.next.kind != 'review' or found.next.step.id != STEP:
        raise WorkspaceError('The training outline is not waiting for a decision.')
    if expected != signature(root, found.session, record):
        raise WorkspaceError('The training outline changed. Read the latest version before deciding.')
    if engine._run(root).workers:
        raise WorkspaceError('Wait for the work in progress to finish before deciding.')
    if record.get('problem') or record.get('question') or record.get('halt'):
        raise WorkspaceError('Resolve the stopped work before deciding on the training outline.')
    return record, found


def _approve_outline(engine, root, expected, edited):
    """Keep the outline as the person edited it and approve exactly that version."""
    import home
    from runner import outline_first
    with engine.files:
        record, found = _waiting(engine, root, expected)
        before = outline_first.read(root)
        changed = before is None or {key: before.get(key) for key in ('sections', 'separate')} \
            != {key: edited.get(key) for key in ('sections', 'separate')}
        if changed:
            outline_first.write(root, edited)
        record['training_plan']['approved'] = {'signature': signature(root, found.session, record),
                                               'by': 'page', 'at': home.now()}
        engine._store(root, record)
        count = len(edited['sections'])
        engine._commit(root, f'approve the training outline ({count} section'
                       + ('' if count == 1 else 's') + (', as edited' if changed else '')
                       + ') and research each section')
    engine.carry_on(root)
    return engine.view(root)
