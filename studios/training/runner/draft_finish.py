"""Training Studio's local Finishing checks and explicit proposal decisions.

Checks never schedule work. A proofread Apply requests the normal protected selection
job; other findings open an author's note, which still needs an explicit rewrite.
"""
import re
import secrets

import checks
import home
import workspace
from studio_core.drafting import basis, proofread as mechanical
from studio_core.drafting import proposals as shared
from studio_core.drafting import record

from runner import draft_jobs, drafts

TOOLS = {f'finish-{key}': key for key in ('proofread', 'coverage', 'claims', 'practice', 'yoodli')}
RULES = {'no_em_dashes': True, 'no_ascii_double_hyphen': True,
         'banished_words': ['delve', 'leverage'], 'banished_phrases': ["it's worth noting"]}
STARTERS = ('Furthermore', 'Moreover', 'Additionally')
KINDS = {'proofread': ('document', 'brief'), 'coverage': ('document',),
         'claims': ('document', 'brief'), 'practice': ('scenario',), 'yoodli': ('yoodli',)}


def proposals(engine, root, name='document'):
    """Piece 3's proposal store, with Training Studio's exact-part basis rule."""
    store = drafts.TrainingStore(engine, root)
    desk = drafts.TrainingDesk(store, drafts.codec_of(name))

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
    desk = drafts.desk_of(engine, root, name)
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


def finish(engine, root, name, tool, seen=None):
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
        record.checked(draft, seen, [item['part']], thing='draft')
        if 'instruction' in item:
            return {**drafts.card(engine, root, name),
                    'note': {'part': item['part'], 'text': item['instruction']}}
        if 'after' in chosen:
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
