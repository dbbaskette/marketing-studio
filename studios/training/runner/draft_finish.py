"""Training Studio Finishing: local checks, explicit review jobs and proposal decisions.

Jobs read saved context only. Nothing changes until Apply; text and slide edits retain
their existing basis, History and approval rules.
"""
import json
import re
import secrets

import checks
import home
import workspace
from studio_core.drafting import basis, proofread as mechanical
from studio_core.drafting import proposals as shared
from studio_core.drafting import guards, parts, record
from studio_core import step_times

from runner import briefs, draft_jobs, drafts, pipeline

TOOLS = {f'finish-{key}': key for key in ('proofread', 'coverage', 'claims', 'practice', 'yoodli',
                                       'sources', 'time', 'answers', 'humanize', 'level')}
RULES = {'no_em_dashes': True, 'no_ascii_double_hyphen': True,
         'banished_words': ['delve', 'leverage'], 'banished_phrases': ["it's worth noting"]}
STARTERS = ('Furthermore', 'Moreover', 'Additionally')
KINDS = {'proofread': ('document', 'brief'), 'coverage': ('document',),
         'claims': ('document', 'brief'), 'practice': ('scenario',), 'yoodli': ('yoodli',),
         'sources': ('document', 'brief'), 'time': ('document', 'deck'),
         'answers': ('document',), 'humanize': ('document', 'brief'),
         'level': ('document', 'brief')}
UNREADABLE = 'The Finishing suggestions could not be read. Try this check again.'
VERDICTS = ('supported', 'not in the sources', 'contradicted')


def proposals(engine, root, name='document'):
    """Piece 3's proposal store, with Training Studio's exact-part basis rule."""
    store = drafts.TrainingStore(engine, root)
    desk = (DeckFinishDesk(engine, root) if workspace.split(name)[0] == 'deck'
            else drafts.TrainingDesk(store, drafts.codec_of(name)))

    def present(draft, item):
        try:
            if item['part'] not in desk.codec.fixed and (
                    desk.codec.section(draft, item['part']) or {}).get('locked'):
                return False
            return basis.fingerprint(desk.codec.text_of(draft, item['part'])) == item['basis']
        except (KeyError, ValueError):
            return False

    # Lock by part identity, as the selection job does. Another section can legitimately
    # contain the same words as Sources; the generic codec hook compares text instead.
    text_fit = shared.text_fit(desk.codec.replace(landed=lambda draft, before, text: text))

    def fit(draft, item, after, text):
        if not present(draft, item) or basis.fingerprint(text) != item['basis']:
            raise ValueError(shared.GONE)
        if 'start' not in item:
            return text_fit(draft, item, after, text)
        # Mechanical findings retain a Python character offset. Identical sentences
        # elsewhere in the part do not make the chosen occurrence ambiguous.
        start, before = item['start'], item['before']
        if (type(start) is not int or start < 0 or not before
                or text[start:start + len(before)] != before):
            raise ValueError(shared.GONE)
        return text[:start] + after + text[start + len(before):]

    return shared.Proposals(store, desk, TOOLS, owner='training', present=present, fit=fit)


def _read(engine, root, name):
    desk = (DeckFinishDesk(engine, root) if workspace.split(name)[0] == 'deck'
            else drafts.desk_of(engine, root, name))
    return desk, desk.read(name)


def _proof(desk, draft, name):
    # Core's offsets and default join share a normalized reading shape. Coverage notes
    # and locked Sources are metadata, not prose to rewrite.
    reading = {**draft, 'sections': [s for s in draft['sections'] if not s.get('locked')]}
    return mechanical.check(reading, RULES, STARTERS, name)


def proofread(engine, root, name):
    """Read-only GET: mechanical findings; no proposal files or jobs are created."""
    with engine.files:
        root = engine._desk_root(root)
        if workspace.split(name)[0].partition(':')[0] not in KINDS['proofread']:
            raise ValueError('Proofread a guide or brief.')
        desk, draft = _read(engine, root, name)
        return _proof(desk, draft, name)


def _items(engine, root, name, tool, desk, draft):
    codec = desk.codec
    whole = codec.join(draft)
    base, level = workspace.split(name)
    kind = base.partition(':')[0]
    parts = [('opening', draft.get('opening', ''))] + [
        (s['id'], s['text']) for s in draft['sections'] if not s.get('locked')]

    def item(part, before, note, **extra):
        return {'part': part, 'before': before, 'note': note,
                'basis': basis.fingerprint(codec.text_of(draft, part)), **extra}

    if tool == 'proofread':
        return [item(f['part'], f['sentence'], f['label'], fix=f['fix'], start=f['start'])
                for f in _proof(desk, draft, name)['findings']]
    if tool == 'claims':
        found = []
        for part, text in parts:
            for start, end in mechanical.sentences(text):
                sentence = text[start:end]
                checked = checks.citations(whole, kind, added=[sentence],
                                            names=draft_jobs.intake_names(root))
                for problem in checked['problems']:
                    if problem.startswith('A claim with no reference:'):
                        found.append(item(part, sentence, problem,
                                          instruction='Add the reference for this, or cut it.'))
        return found
    if tool == 'coverage':
        plan = draft_jobs.file_text(root, workspace.qualify('blueprint', level))
        result = checks.document_coverage(checks.parse_blueprint(plan), whole)
        part = next((s['id'] for s in draft['sections'] if not s.get('locked')), 'opening')
        return [item(part, codec.text_of(draft, part),
                     problem.replace('is not covered by any section.', 'is not taught by any section.'),
                     instruction=(f'Teach {problem.split()[0]} here.' if 'not covered' in problem
                                  else problem)) for problem in result['problems']]
    if tool == 'practice':
        results = [checks.check_scenario(whole, base)]
    else:
        profile = home.read_json(workspace.profile_for(root), {})
        scenario_name = workspace.qualify('scenario:' + base.partition(':')[2], level)
        try:
            scenario = checks.parse_scenario(draft_jobs.file_text(root, scenario_name))
        except (ValueError, OSError):
            scenario = None
        results = checks.check_yoodli(whole, profile, scenario, None, base)
    found = []
    for result in results:
        if tool == 'yoodli' and not result['check'].endswith('.limits'):
            continue
        for problem in result['problems']:
            limit = re.search(r'characters; the limit is (\d+)\.', problem)
            instruction = f'Bring this field under {limit[1]} characters.' if limit else problem
            found.append(item('opening', whole, problem, instruction=instruction))
    return found


def finish(engine, root, name, tool, seen=None, level=None):
    if 'finish-' + tool in draft_jobs.FINISHING:
        draft_jobs.begin(engine, root, 'finish-' + tool, name, seen=seen, level=level)
        with engine.files:
            return drafts.card(engine, root, name)
    with engine.files:
        root, _ = engine._on_desk(root, decided=True)
        kind = workspace.split(name)[0].partition(':')[0]
        if tool not in KINDS or kind not in KINDS[tool]:
            raise ValueError('Choose a Finishing tool for this material.')
        desk, draft = _read(engine, root, name)
        if seen is not None:
            record.checked(draft, seen, thing='draft')
        proposals(engine, root, name).keep(name, secrets.token_hex(16), 'finish-' + tool,
            _items(engine, root, name, tool, desk, draft))
        return drafts.card(engine, root, name)


def apply(engine, root, name, job, items, seen):
    with engine.files:
        root, run = engine._on_desk(root, decided=True)
        if drafts.busy(run):
            raise ValueError(shared.WORKING)
        locked = draft_jobs.readonly(engine, root, name)
        if locked:
            raise ValueError(locked)
        sets = proposals(engine, root, name)
        found = sets.read(name, job)
        if (not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict)
                or set(items[0]) - {'id', 'after'}):
            raise ValueError('Choose one suggestion to apply.')
        chosen = items[0]
        item = next((p for p in found['items'] if p['id'] == chosen.get('id')), None)
        if item is None or item['state'] != 'open':
            raise ValueError('Choose an open suggestion from this set.')
        draft = sets.desk.read(name)
        if not sets.present(draft, item):
            raise ValueError(shared.GONE)
        sets.desk.checked(draft, seen, [item['part']])
        if workspace.split(name)[0] == 'deck':
            return apply_deck(engine, root, name, sets, found, item, chosen, draft)
        if 'instruction' in item:
            return {**drafts.card(engine, root, name),
                    'note': {'part': item['part'], 'text': item['instruction']}}
        if 'after' in chosen or 'after' in item:
            engine._edits_first(root)
            with sets.store.making('finishing', None):
                done = sets.apply(name, seen, job, items)
            # The private typing index excludes output another start worker may still
            # be writing. An edited proposal is the person's saved text, too.
            engine._edited(root, name)
            engine._edits_first(root)
            return {**drafts.card(engine, root, name), 'finished': done}
        # Queue without waking until the proposal identity is durably attached. The
        # engine may run synchronously in tests, and another worker can acquire files.
        queued = draft_jobs.begin(engine, root, 'selection', name, part=item['part'],
            seen=seen, action='fix', passage=item['before'], note=item['fix'],
            start=len(sets.codec.text_of(draft, item['part'])[:item['start']].encode('utf-16-le')) // 2,
            finishing={'job': job, 'item': item['id']}, wake=False)
    engine.wake(root)
    with engine.files:
        return {**drafts.card(engine, root, name), 'queued': queued['id']}


def landed(engine, root, job):
    """Called under files only after the selection was written successfully."""
    if not job.get('finishing'):
        return
    sets = proposals(engine, root, job['name'])
    try:
        found = sets.read(job['name'], job['finishing']['job'])
    except (ValueError, OSError):
        return  # A newer check can prune an old set; the applied text still has History.
    for item in found['items']:
        if item['id'] == job['finishing']['item']:
            item['state'] = 'applied'
    sets.store.write_json(sets.path(job['name'], found['job']), found)


def skip(engine, root, name, job, ids):
    with engine.files:
        root, run = engine._on_desk(root, decided=True)
        for pending in (run.get('drafts') or {}).get('jobs', []):
            link = pending.get('finishing') or {}
            if (pending.get('name') == name and pending.get('status') in ('queued', 'working')
                    and link.get('job') == job and isinstance(ids, list) and link.get('item') in ids):
                raise ValueError(shared.WORKING)
        proposals(engine, root, name).skip(name, job, ids)
        return drafts.card(engine, root, name)


def validate(name, tool, level=None):
    kind = workspace.split(name)[0].partition(':')[0]
    if tool not in KINDS or kind not in KINDS[tool]:
        raise ValueError('Choose a Finishing tool for this material.')
    if tool == 'humanize' and level not in (None, 'light', 'medium', 'strong'):
        raise ValueError('Choose light, medium or strong for Humanize.')


def prices(name):
    kind = workspace.split(name)[0].partition(':')[0]
    return {tool: {'minutes': step_times.expected(drafts.Times(), drafts.times(),
                  'draft:finish-' + tool, 2)} for tool in KINDS
            if 'finish-' + tool in draft_jobs.FINISHING and kind in KINDS[tool]}


def work_for(root, found, job):
    name, kind = job['name'], job['kind']
    codec = drafts.codec_of(name) if workspace.split(name)[0] != 'deck' else DeckFinishDesk.codec
    saved = home.read_json(pipeline.place(root, workspace.split(name)[1], 'work/drafts')
                           / drafts._folder_name(name) / 'draft.json', None)
    draft = (DeckFinishDesk(None, root).read(name) if workspace.split(name)[0] == 'deck' else
             drafts.follow(saved, codec.split(draft_jobs.file_text(root, name))))
    parts = [{'part': part, 'text': codec.text_of(draft, part)} for part in
             [*codec.fixed, *(s['id'] for s in draft['sections'] if not s.get('locked'))]]
    inputs = {'parts': json.dumps(parts), 'whole material': codec.join(draft)}
    research = workspace.research_record(root) or {}
    findings = research.get('findings') if research.get('schema') == 2 else research.get('items')
    findings = findings or []
    if isinstance(findings, dict):
        findings = [{'id': key, **value} for key, value in findings.items()]
    if kind == 'finish-sources':
        inputs['research record'] = pipeline.findings_text(root)
    if kind == 'finish-time':
        inputs['learner time'] = pipeline.answers(root).get('time limit') or 'No time supplied.'
    if kind == 'finish-humanize':
        inputs['humanize level'] = job['level']
    if kind == 'finish-level':
        inputs['earlier levels'] = pipeline._earlier(root, found.session, workspace.split(name)[1]) or 'No earlier levels.'
    findings = [{**item, 'summary': (research.get('results') or {}).get(item['id'], {}).get(
        'summary', item.get('summary', ''))} for item in findings]
    spec = {'kind': 'finishing', 'finish_kind': kind, 'name': name, 'parts': parts,
            'findings': findings, 'draft': draft}
    return pipeline.Work(briefs.guidance(kind),
        f'Read every supplied input. Hand back the proposals with submit_artifact under the name "{kind}".',
        'write', {'inputs': inputs, 'artifacts': {kind: spec}, 'ask': False}, kind)


def result(content, spec):
    found = shared.read_result(content, UNREADABLE)
    if not isinstance(found, list) or len(found) > 60:
        raise ValueError(UNREADABLE)
    texts = {p['part']: p['text'] for p in spec['parts']}
    findings = {item['id']: item for item in spec['findings']}
    items = []
    for row in found:
        if (not isinstance(row, dict) or any(not isinstance(row.get(key), str)
                for key in ('part', 'quote', 'replacement', 'reason'))):
            raise ValueError(UNREADABLE)
        part, before, after = row['part'], row['quote'], row['replacement']
        text = texts.get(part)
        if text is None or not shared.once(text, before):
            raise ValueError('Each suggestion must quote one passage in a supplied part. Leave Sources alone.')
        item = {'part': part, 'before': before, 'after': after, 'note': row['reason'],
                'basis': basis.fingerprint(text), 'flag': guards.flags(before, after),
                'dropped': checks.dropped(before, after)}
        if spec['finish_kind'] == 'finish-sources':
            verdict, ident = row.get('verdict'), row.get('finding')
            if verdict not in VERDICTS or not isinstance(ident, str) or (ident not in findings
                    and not (verdict == 'not in the sources' and not ident)):
                raise ValueError('Name a supplied finding and a listed verdict for each claim.')
            finding = findings.get(ident) or {}
            item.update(verdict=verdict, finding=ident,
                        source=finding.get('title') or finding.get('question') or ident)
            summary = finding.get('summary') or ''
            item['passage'] = summary.get('text', '') if isinstance(summary, dict) else summary
            if item['source']:
                item['note'] += ' Finding: ' + item['source']
        items.append(item)
    return items


def check_result(content, spec):
    try:
        result(content, spec)
    except ValueError as error:
        return [str(error)], [], [], content
    return [], [], [], content


def receive(engine, root, job, content, spec):
    # The submitted snapshot supplies every basis, so typing during the check makes
    # its proposals unavailable instead of relocating them into newer prose.
    proposals(engine, root, job['name']).keep(job['name'], job['id'], job['kind'],
        result(content, spec), **({'level': job['level']} if job['kind'] == 'finish-humanize' else {}))
    job.update(status='done', applied=False, proposed=True, settled_at=home.now(),
               says='Suggestions are ready to review.')


class DeckFinishDesk:
    """Text proposals for individual slide fields; Apply uses the existing deck editor."""
    codec = parts.Codec(fixed=(), single=(), part=re.compile(r'[A-Za-z0-9_:.-]+'),
        join=lambda draft: '\n\n'.join(p['heading'] + '\n' + p['text'] for p in draft['sections']))

    def __init__(self, engine, root):
        self.engine, self.root = engine, root

    def read(self, name):
        level = workspace.split(name)[1]
        session = workspace.load(self.root)
        spec = workspace.artifact(self.root, session, name)
        outline_path = pipeline.place(self.root, level, pipeline.OUTLINE)
        outline = home.read_json(outline_path, {})
        fields = []
        for slide in outline.get('slides') or []:
            names = ['title', 'subtitle', 'caveat', 'source', 'notes']
            names += [f'points[{i}].{key}' for i in range(len(slide.get('points') or []))
                      for key in ('label', 'text')]
            for index, field in enumerate(names):
                _, text = drafts.slide_words(outline, slide['id'], field, '')
                if text:
                    fields.append({'id': f"{slide['id']}:{index}", 'slide': slide['id'],
                        'field': field, 'heading': slide['title'] + ' · ' + field, 'text': text})
        # A stable, JavaScript-safe revision for this read-only parts adapter. The
        # normal deck digest still guards the actual edit through slide_words.
        revision = int(workspace.sha256_file(outline_path)[:12], 16) + 1
        return {'revision': revision, 'sections': fields,
                'seen': workspace.sha256_file(self.root / spec['file'])}

    def checked(self, draft, seen, parts=None):
        if type(seen) is not int or seen != draft['revision']:
            raise ValueError('This deck changed since you opened it. Read it again before deciding.')


def deck_card(engine, root, name):
    desk, draft = _read(engine, root, name)
    whole = drafts.view(engine, root)
    found = next(card for card in whole['cards'] if card['name'] == name)
    run = engine._load(root)
    job = whole['job']
    return {**found, **draft, 'finishing': proposals(engine, root, name).summary(name, draft),
            'finish_prices': prices(name), 'desk': whole,
            'readonly': draft_jobs.readonly(engine, root, name),
            'working': job if job and job.get('name') == name else None,
            'jobs': [dict(j) for j in (run.get('drafts') or {}).get('jobs', []) if j.get('name') == name]}


def mark_deck(engine, root, name, job, ident):
    sets = proposals(engine, root, name)
    try:
        found = sets.read(name, job)
        item = next(p for p in found['items'] if p['id'] == ident)
    except (ValueError, OSError, StopIteration):
        return  # A newer check may prune this set; the saved words retain History.
    item['state'] = 'applied'
    sets.store.write_json(sets.path(name, job), found)


def apply_deck(engine, root, name, sets, found, item, chosen, draft):
    part = sets.codec.section(draft, item['part'])
    after = chosen.get('after', item['after'])
    if not isinstance(after, str):
        raise ValueError('Write the wording to use, then apply it.')
    text = sets.fit(draft, item, after, part['text'])
    link = {'name': name, 'job': found['job'], 'ident': item['id']}
    level = workspace.split(name)[1]
    result = engine.slide_words(root, level, part['slide'], part['field'], text,
                               draft['seen'], _source='finishing', _finishing=link)
    return {**deck_card(engine, root, name), 'slide_result': result,
            'slide_edit': {'level': level, 'slide': part['slide'], 'field': part['field'],
                           'text': text, 'seen': draft['seen'], 'finishing': link}}


def deck_link(engine, root, level, sent):
    """Validate the proposal retained by an explicit slide redraw request."""
    link = sent.get('finishing')
    if link is None:
        return None
    with engine.files:
        if (not isinstance(link, dict) or set(link) != {'name', 'job', 'ident'}
                or link['name'] != workspace.qualify('deck', level)):
            raise workspace.WorkspaceError('Choose a Finishing suggestion for this deck.')
        sets = proposals(engine, root, link['name'])
        try:
            found = sets.read(link['name'], link['job'])
            item = next(p for p in found['items'] if p['id'] == link['ident'])
            draft = sets.desk.read(link['name'])
            part = sets.codec.section(draft, item['part'])
            if (item['state'] != 'open' or not sets.present(draft, item)
                    or part['slide'] != sent.get('slide') or part['field'] != sent.get('field')):
                raise ValueError(shared.GONE)
        except (ValueError, StopIteration, KeyError) as error:
            raise workspace.WorkspaceError(shared.GONE) from error
        return link
