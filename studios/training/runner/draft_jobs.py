"""Training Studio's serial desk queue and the context for one checked text change."""
from __future__ import annotations

import copy
import json
import re
import secrets

import checks
import home
import workspace
from studio_core import step_times
from studio_core.drafting import basis, prompts, record

from runner import briefs, drafts, pipeline

KINDS = ('section', 'write-again', 'revise-all', 'selection', 'update', 'layout', 'write-whole')
BUSY = drafts.BUSY
NEXT = 'Next, after {doing}.'
SOURCES = 'Leave Sources as it is: the studio adds the references you use.'
WHOLE = ('blueprint', 'scenario', 'yoodli')


def file_text(root, name):
    spec = workspace.artifact(root, workspace.load(root), name)
    return workspace.managed(root, spec['file']).read_text(encoding='utf-8')


def readonly(engine, root, name):
    """A start owns both its output and the materials it is reading until that step ends."""
    run = engine._run(root)
    live = [key for key in run.workers if not key.startswith('draft:')]
    if not live:
        return None
    session = workspace.load(root)
    for key in live:
        step = next((s for s in engine._survey(root, engine._load(root)).steps if s.id == key or key.startswith(s.id + ':')), None)
        if step is None or not step.artifact:
            continue
        spec = workspace.artifact(root, session, step.artifact)
        if name == step.artifact or name in spec['upstream']:
            verb, _, rest = step.doing.partition(' ')
            infinitive = {'Writing': 'write', 'Drawing': 'draw', 'Planning': 'plan',
                          'Checking': 'check', 'Preparing': 'prepare', 'Building': 'build',
                          'Laying': 'lay', 'Rewriting': 'rewrite'}.get(verb)
            use = f'to {infinitive} {rest}' if infinitive else ': ' + step.doing.lower()
            return f'Being used {use}. You can edit it when that is done.'
    return None


def browser_offset(text, offset):
    """Translate a UTF-16 selection offset to a Python index, only at character boundaries."""
    if type(offset) is not int or offset < 0:
        return None
    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        units += 2 if ord(char) > 0xffff else 1
        if units > offset:
            return None
    return len(text) if units == offset else None


def begin(engine, root, kind, name, part=None, note=None, seen=None, action=None,
          passage=None, start=None):
    """Validate and persist a request. Waking schedules work; the caller never calls a provider."""
    with engine.files:
        root, run = engine._on_desk(root, decided=True)
        if drafts.busy(run):
            raise workspace.WorkspaceError(BUSY)
        if kind not in KINDS:
            raise workspace.WorkspaceError('Choose a listed kind of change.')
        session = workspace.load(root)
        if not isinstance(name, str) or name not in workspace.artifact_names(root, session):
            raise workspace.WorkspaceError('Choose a material of this training.')
        locked = readonly(engine, root, name)
        if locked:
            raise workspace.WorkspaceError(locked)
        base = workspace.split(name)[0].partition(':')[0]
        try:
            drafts._vet('whole', file_text(root, name))
        except ValueError as error:
            raise workspace.WorkspaceError(str(error)) from None
        if kind == 'write-whole' and base != 'document':
            raise workspace.WorkspaceError('Choose a guide to write again as a whole.')
        if base in WHOLE or kind == 'write-whole':
            if part is not None or kind == 'selection':
                raise workspace.WorkspaceError('Change this material with a whole note.')
            if kind == 'layout' and (base != 'scenario' or name not in engine._survey(root, run).own):
                raise workspace.WorkspaceError('Only your own scenario can be laid out in your words.')
            if kind != 'layout' and name in engine._survey(root, run).own:
                raise workspace.WorkspaceError('This scenario is your own. Change its words yourself; ask to lay it out from its practice card.')
            text, sections = file_text(root, name), None
            if (base == 'blueprint' or kind == 'write-whole') and type(seen) is int:
                try:
                    record.checked(drafts.desk_of(engine, root, name).read(name), seen, thing='draft')
                except ValueError as error:
                    raise workspace.WorkspaceError(str(error)) from None
            elif seen != workspace.sha256_file(root / workspace.artifact(root, session, name)['file']):
                raise workspace.WorkspaceError('This draft changed since you opened it. Reload to see the latest.')
            part = 'whole'
        else:
            if kind == 'layout':
                raise workspace.WorkspaceError('Only your own scenario can be laid out in your words.')
            try:
                codec = drafts.codec_of(name)
                draft = drafts.desk_of(engine, root, name).read(name)
                if kind == 'revise-all':
                    record.checked(draft, seen, thing='draft')
                    sections = [s['id'] for s in draft['sections'] if not s.get('locked')]
                    if not sections:
                        raise ValueError('There are no sections to revise.')
                    part = sections[0]
                else:
                    sections = None
                    record.checked(draft, seen, [part], thing='draft')
                if part not in codec.fixed and codec.section(draft, part).get('locked'):
                    raise ValueError(SOURCES)
                text = codec.text_of(draft, part)
            except ValueError as error:
                raise workspace.WorkspaceError(str(error)) from None
        if note is not None and (not isinstance(note, str) or len(note) > 4000):
            raise workspace.WorkspaceError('Keep the note under 4,000 characters.')
        if kind == 'selection':
            if action not in (*prompts.ACTIONS, 'ask') or not isinstance(passage, str) or not passage:
                raise workspace.WorkspaceError('Choose a passage and a listed change.')
            start = browser_offset(text, start)
            if start is None or text[start:start + len(passage)] != passage:
                raise workspace.WorkspaceError('Select the passage again in the current text.')
        job = {'id': secrets.token_hex(6), 'kind': kind, 'name': name, 'part': part,
               'note': note or '', 'action': action, 'passage': passage, 'selection': passage,
               'start': start, 'basis': basis.fingerprint(text), 'status': 'queued', 'at': home.now()}
        if sections is not None:
            job.update(sections=sections, done=[], bases={s: basis.fingerprint(
                codec.text_of(draft, s)) for s in sections}, total=len(sections), index=0, chain=True)
        guess = len(sections) if sections is not None else 2 if kind == 'write-again' else 1
        job['minutes'] = step_times.expected(drafts.Times(), drafts.times(), f'draft:{kind}', guess)
        live = engine._run(root).workers
        doing = next((v['label'] for k, v in live.items() if not k.startswith('draft:')), None)
        job['says'] = NEXT.format(doing=doing.rstrip('.').lower()) if doing else 'Waiting to start.'
        run.setdefault('drafts', {}).setdefault('jobs', []).append(job)
        run['drafts']['jobs'] = run['drafts']['jobs'][-20:]
        engine._store(root, run)
        engine._commit(root, f'ask for a change to {workspace.label(name)}')
    engine.wake(root)
    return dict(job)


def references(root, session, draft, section, blueprint):
    """Supported findings behind the section, numbered beyond the existing Sources list."""
    whole = drafts.codec_of('brief' if 'kind' in draft else 'document').join(draft)
    _, listed = checks._sources(whole)
    next_number = max(listed, default=0) + 1
    selected = set(section.get('findings') or ())
    covers = set(section.get('covers') or ())
    parsed = checks.parse_blueprint(blueprint)
    modules = [m for m in parsed['modules'].values() if covers.intersection(
        [*m['objectives'], *m['key_points']])]
    for module in modules:
        for point in module['key_points'].values():
            selected.update(point['findings'])
    research = workspace.research_record(root) or {}
    items = research.get('findings') if research.get('schema') == 2 else research.get('items')
    if isinstance(items, dict):
        items = [{'id': key, **value} for key, value in items.items()]
    results, found = research.get('results') or {}, []
    reviewed = {one['id']: one.get('verdict') for one in (research.get('review') or {}).get('findings', [])}
    facts = {one['id']: one for one in research.get('facts') or ()}
    sources = {one['id']: one for one in research.get('sources') or ()}
    source = next((s['text'] for s in draft['sections'] if s.get('locked')), '')
    cited = set(checks.REFERENCE.findall(section['text']))
    for item in items or ():
        ident = item.get('id')
        result = results.get(ident) or item
        verdict = (reviewed.get(ident, 'supported') if research.get('schema') == 2 else
                   result.get('status', result.get('verdict')))
        if verdict != 'supported':
            continue
        citations = [citation for fact in item.get('support') or ()
                     for citation in (facts.get(fact) or {}).get('citations') or ()]
        evidence = result.get('evidence') or []
        source_meta = (sources.get(citations[0].get('source'), {}) if citations else
                       evidence[0] if evidence else {})
        summary = result.get('summary') or item.get('summary') or ''
        if isinstance(summary, dict):
            summary = summary.get('text') or ''
        detail = {'id': ident, 'title': item.get('title') or item.get('question') or ident,
                  'summary': summary, 'conditions': item.get('conditions') or [],
                  'counter': item.get('counter') or [], 'gaps': item.get('gaps') or [],
                  'date': item.get('date') or source_meta.get('date') or '',
                  'origin': item.get('url') or item.get('document') or source_meta.get('origin') or 'research'}
        entry = next((line for line in source.splitlines() if f'`{ident}`' in line), None)
        if entry is None:
            # Guide entries have no finding ID. Match the exact runner-written entry,
            # including its date/origin, so later section jobs reuse its assigned number.
            same = [line for line in source.splitlines() if checks.SOURCES_ENTRY.match(line)
                    and checks.SOURCES_ENTRY.sub('', line, count=1) == source_entry(detail, 'document')]
            entry = same[0] if len(same) == 1 else None
        match = checks.SOURCES_ENTRY.match(entry or '')
        number = int(match.group(1)) if match else None
        if ident not in selected and str(number) not in cited:
            continue
        if number is None:
            number, next_number = next_number, next_number + 1
        found.append({'number': number, **detail})
    return found, modules


def work_for(root, found, job):
    name, part = job['name'], job['part']
    base, level = workspace.split(name)
    if part == 'whole':
        spec = workspace.artifact(root, found.session, name)
        step = pipeline.Step(name, 'agent', workspace.label(name),
                             'Rewriting ' + workspace.label(name), spec['stage'], name)
        return pipeline.work(root, found, step, {'note': job['note']}, None, [])
    codec = drafts.codec_of(name)
    draft = codec.split(file_text(root, name))
    # IDs live in the local record, while the file is the authority for its words.
    saved = home.read_json(pipeline.place(root, level, 'work/drafts') / drafts._folder_name(name) / 'draft.json', None)
    draft = drafts.follow(saved, draft)
    section = codec.section(draft, part) if part not in codec.fixed else {
        'text': draft[part], 'heading': '', 'covers': [], 'findings': []}
    blueprint = pipeline._text(root, found.session, workspace.qualify('blueprint', level)) or ''
    handed, modules = references(root, found.session, draft, section, blueprint)
    inputs = {'section': section['text'], 'heading': section['heading'],
              'covers': json.dumps(section.get('covers') or []),
              'plan module': json.dumps(modules), 'findings': json.dumps(handed),
              'whole material': codec.join(draft)}
    index = next((i for i, s in enumerate(draft['sections']) if s['id'] == part), -1)
    inputs['neighbours'] = json.dumps(draft['sections'][max(0, index - 1):index] + draft['sections'][index + 1:index + 2])
    earlier = pipeline._earlier(root, found.session, level)
    if earlier:
        inputs['earlier levels'] = earlier
    task = prompts.request('NOTE FOR THIS SECTION', job.get('note') or 'Write this section again from its plan and findings.', prompts.SURGICAL_PART, 'Training Studio')
    if job['kind'] == 'selection':
        task = prompts.passage_task(prompts.ACTIONS.get(job['action'], prompts.ASK))
        if job.get('note'):
            task += prompts.request('NOTE FOR THIS PASSAGE', job['note'], prompts.ONLY_PASSAGE, 'Training Studio')
        inputs.update(passage=job['passage'], around=section['text'])
    elif job['kind'] == 'revise-all':
        task += '\n\n' + prompts.REVISE_ONE
    spec = {'kind': 'part', 'name': name, 'part': part,
            'file': workspace.artifact(root, found.session, name)['file'],
            'heading': section['heading'], 'findings': handed,
            'material': codec.join(draft), 'draft': draft, 'before': section['text'],
            'blueprint': blueprint, 'brief_kind': found.session['settings']['brief_kind'],
            'finding_statuses': found.session.get('findings'),
            'names': intake_names(root), 'selection': job.get('passage') if job['kind'] == 'selection' else None,
            'start': job.get('start')}
    return pipeline.Work(briefs.guidance('part') + '\n\n' + prompts.edit_rule('training material'),
                         task + '\n\nHand back only the requested words with submit_part.',
                         'write', {'inputs': inputs, 'artifacts': {'part': spec}, 'ask': False}, 'part')


def intake_names(root):
    """Product names explicitly supplied in intake, rather than arbitrary capitalised words."""
    text = (root / 'intake.md').read_text(encoding='utf-8')
    named = [value.strip() for value in re.findall(r'(?im)^[-* ]*(?:products?|product names?):\s*(.+)$', text) if value.strip()]
    answers = pipeline.answers(root)
    for key in ('product', 'products', 'product names'):
        named.extend(v.strip() for v in re.split(r'[,;\n]', answers.get(key) or '') if v.strip())
    named.extend(re.findall(r'\b[A-Z][\w-]*(?: +[A-Z][\w-]*)+', answers.get('topic') or ''))
    return list(dict.fromkeys(named))


def spliced(spec, content):
    """A validated part in a copy of the complete material, with runner-owned references."""
    codec = drafts.codec_of(spec['name'])
    draft = copy.deepcopy(spec['draft'])
    before = spec['before']
    if spec.get('selection'):
        at, passage = spec['start'], spec['selection']
        content = before[:at] + content.strip() + before[at + len(passage):]
    codec.set_text(draft, spec['part'], content)
    append_sources(draft, spec['findings'], content, workspace.split(spec['name'])[0])
    return codec.join(draft), content


def append_sources(draft, findings, text, kind):
    source = next((s for s in draft['sections'] if s.get('locked')), None)
    if source is None:
        return
    listed = {int(m.group(1)) for line in source['text'].splitlines() if (m := checks.SOURCES_ENTRY.match(line))}
    cited = {int(n) for n in checks.REFERENCE.findall(text)}
    for item in findings:
        n = item['number']
        if n in cited and n not in listed:
            source['text'] += f"\n{n}. {source_entry(item, kind)}"
            listed.add(n)


def source_entry(item, kind):
    title = f"Finding `{item['id']}`: {item['title']}" if kind == 'brief' else item['title']
    return f"{title}, {item['date']}, {item['origin']}"
