"""Desk work on the single-worker tool job queue: queue it, then settle the result.

Each job carries the part it changes and that part's text fingerprint when it was asked
for. The worker settles a result as soon as it is ready (tool_jobs.once calls `ended`): it
lands only while that text is unchanged, with the text it replaces kept as a version first,
and in a team workspace it is then recorded as a decision (`share`). A result an older
process finished is settled by the next desk request. Like desk.py, every function except
`share` expects the caller to hold the studio lock.
"""

import json
import re
import secrets

import blog_runner
import desk
import studio
import tool_jobs

KINDS = ('desk-section', 'desk-revise-all', 'desk-selection', 'desk-first-pass')
ACTIVE = ('queued', 'working')
ACTIONS = {
    'rephrase': 'Rewrite the passage in fresh words with the same meaning.',
    'shorten': 'Tighten the passage; use noticeably fewer words.',
    'expand': 'Develop the passage further with one concrete detail, example or consequence '
    'from the sources.',
    'fix': 'Fix grammar, clarity and flow only.',
}
WRITE_AGAIN = (
    'Write this section again from its heading, its brief, the sections before it and the '
    'sources. Keep the kind of post and the tone. Return only the section text.'
)
WHOLE = (
    'Revise every section in sections for this pass, with the full draft as context. Return '
    'JSON in content: a list of {"id": ..., "text": ...} for every section in sections, in '
    'order, ids unchanged, each text without its heading. Return a section the pass does not '
    'touch exactly as it was.'
)
REVISE_ONE = (
    'The author left a note for the whole draft. The draft is revised one section at a time, '
    'in order: revise part.text, this section only, for the note. The whole draft is in '
    "sections for context; return only this section's text, without its heading."
)
FIRST_PASS_LIMIT = 180_000  # The whole draft as JSON must come back in one result.
TIGHTEN = (
    'Tighten and proofread the draft, section by section. Fix spelling, grammar, '
    'punctuation and consistency, and cut needless words; change nothing else.'
)
RESHAPE = (
    'Reshape each section to fit the selected kind of post in style.guide: its moves, the '
    'order of points within a section, its register and its length. Keep every fact, number, '
    'name, quotation and link, and the author’s stance. Add no claim the sources do not '
    'support.'
)
RETURN = (
    'Return the writing in content and your notes apart from it: in evidence, each material '
    'claim with its source ID and exact passage; in gaps, each thing the author must supply '
    'before publishing, such as a release date or a link. Source IDs and editorial '
    'placeholders go there, never in content.'
)
STALE = 'The draft changed while this was being written. Run it again.'
GAPS = 50


def _guide(name):
    return (blog_runner.REFERENCES / 'modules' / name).read_text().rstrip()


INDEXED = 60  # desk jobs a blog's index names, newest last


def _index(root, ident):
    """A small list of one blog's desk jobs, so a request reads only those."""
    return studio.inside(root, '.blog-runs', 'desk-jobs', studio.identifier(ident) + '.json')


def _indexed(root, ident):
    target = _index(root, ident)
    if not target.is_file() or target.is_symlink():
        return []
    try:
        found = studio.read_json(target).get('jobs')
    except (ValueError, OSError, AttributeError):
        return []
    return [name for name in found if isinstance(name, str)] if isinstance(found, list) else []


def _note(root, ident, job_id):
    studio.write_json(_index(root, ident), {'jobs': (_indexed(root, ident) + [job_id])[-INDEXED:]})


def _read_jobs(root, ident, names):
    found = []
    for name in names:
        try:
            value = tool_jobs.read(root, name)
        except (ValueError, OSError):
            continue  # Removed with a deleted blog, or never written.
        if value.get('kind') in KINDS and (value.get('metadata') or {}).get('article') == ident:
            found.append(value)
    return sorted(found, key=lambda value: value.get('created_at') or '')


def jobs(root, ident):
    """This blog's desk jobs, oldest first, from its index."""
    return _read_jobs(root, ident, _indexed(root, ident))


def active(root):
    """{blog id: desk jobs under way}, for the blog list. Only one runs per blog, so each
    blog's newest few jobs are read."""
    folder = studio.inside(root, '.blog-runs', 'desk-jobs')
    found = {}
    for target in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        try:
            ident = studio.identifier(target.stem)
        except ValueError:
            continue
        count = sum(1 for job in _read_jobs(root, ident, _indexed(root, ident)[-3:]) if busy(job))
        if count:
            found[ident] = count
    return found


def _guard(root, ident):
    """Refuse a blog another computer drives in a team workspace."""
    from team_workspace import guard

    guard(root, ident)


CHAIN = re.compile(r'[a-f0-9]{16}')


def _chain_path(root, chain):
    if not isinstance(chain, str) or not CHAIN.fullmatch(chain):
        raise ValueError('Choose a whole-draft note.')
    return studio.inside(root, '.blog-runs', 'desk-chains', chain + '.json')


def chain_record(root, chain):
    target = _chain_path(root, chain)
    if not target.is_file() or target.is_symlink():
        return None
    try:
        return studio.read_json(target)
    except (ValueError, OSError):
        return None


def _chain_note(root, job, applied=False, problem=None, ended=False):
    """Keep a whole-draft note's own tally: how many sections were revised, which were not
    and why, and whether it has ended. It does not depend on how many jobs are listed."""
    meta = job['metadata']['desk']
    record = chain_record(root, meta['chain']) or {
        'article': job['metadata']['article'],
        'total': len(meta['order']),
        'revised': 0,
        'problems': [],
        'ended': False,
    }
    if applied:
        record['revised'] += 1
    if problem:
        heading = ''
        try:
            found = desk._part(desk.read(root, job['metadata']['article']), meta['part'])
            heading = found['heading'] if found else ''
        except (ValueError, OSError):
            pass
        record['problems'] = (
            record['problems'] + [{'part': meta['part'], 'heading': heading, 'error': problem}]
        )[-200:]
    if ended:
        record['ended'] = True
    studio.write_json(_chain_path(root, meta['chain']), record)


def unsettled(job):
    """A ready result not yet landed in the draft: still the blog's job under way."""
    return job.get('status') == 'ready' and not job.get('settled_at')


def busy(job):
    return job.get('status') in ACTIVE or unsettled(job)


def _busy(root, ident):
    if any(busy(job) for job in jobs(root, ident)):
        raise ValueError('A desk job is already working on this blog. Wait or stop it.')


def fingerprint(value):
    return studio.digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def _sections_basis(draft):
    return fingerprint([[section['id'], section['text']] for section in draft['sections']])


def _context(root, draft, length=False):
    """The kind of post, sources with their stance, examples and gaps for a desk job, and
    the guidance runs share (blog_runner.shared_guidance). Tone only: no voice."""
    import styles

    style = styles.pinned(root, draft['style']) if draft.get('style') else None
    record = {
        'title': draft['title'],
        'sources': draft.get('sources', []),
        'material': [
            entry['source_id']
            for entry in draft.get('sources', [])
            if 'material' in entry['purposes']
        ],
        'voice': {'mode': 'tone', 'tone': draft.get('tone', '')},
        'research_policy': 'supplied-only',
    }
    found = blog_runner.inputs(root, record, {'brief': {}})
    extra = {
        'style': style,
        'tone': draft.get('tone', ''),
        'sources': found['sources'],
        'gaps': draft.get('gaps', []),
        'response_kind': 'writing-with-notes',
    }
    if found.get('examples'):
        extra['examples'] = found['examples']
    guidance = blog_runner.shared_guidance(
        style, draft.get('tone', ''), draft.get('length') if length else None
    )
    if found.get('examples'):
        guidance += (
            '\nThe documents in examples show the kind of post wanted; take their shape, '
            'not their facts.'
        )
    return extra, guidance


def _request(label, text, scope):
    """The author's words as an instruction from the author, not as document data."""
    return (
        '\n\nAUTHOR’S '
        + label
        + ', from the author through Blog Studio. '
        + scope
        + '\n"""\n'
        + text
        + '\n"""'
    )


def _create(root, ident, kind, payload, guidance, meta):
    result = tool_jobs.create(
        root,
        secrets.token_hex(16),
        kind,
        payload,
        guidance,
        basis=None,
        metadata={'article': ident, 'desk': meta},
    )
    _note(root, ident, result['id'])
    blog_runner.engine(root).wake.set()
    return result


def _queue(root, ident, draft, seen, kind, payload, guidance, meta, parts=None):
    if parts is None:
        parts = (
            [section['id'] for section in draft['sections']]
            if meta['part'] == 'sections'
            else [meta['part']]
        )
    desk.checked(draft, seen, parts)
    _busy(root, ident)
    return _create(root, ident, kind, payload, guidance, {**meta, 'seen': seen})


def section(root, ident, seen, part, note):
    """Rewrite one section for the author's note, or write it again without one."""
    draft = desk.read(root, ident)
    found = desk._part(draft, part)
    if found is None:
        raise ValueError('Rewrite a section; edit the title and opening directly.')
    if not isinstance(note, str) or len(note) > 4000:
        raise ValueError('Keep the note to 4,000 characters.')
    note = note.strip()
    index = draft['sections'].index(found)
    extra, shared = _context(root, draft, length=not (note and found['text']))
    payload = {
        'title': draft['title'],
        'outline': [{'heading': s['heading'], 'brief': s['brief']} for s in draft['sections']],
        'before': [s['text'] for s in draft['sections'][:index]][-2:],
        'after': [s['text'] for s in draft['sections'][index + 1 :]][:1],
        'part': found,
        'note': note,
        **extra,
    }
    edit = bool(note and found['text'])
    guidance = (_guide('desk-edit.md') if edit else WRITE_AGAIN) + '\n\n' + shared
    guidance += '\n' + RETURN
    if note:
        guidance += _request(
            'NOTE FOR THIS SECTION',
            note,
            'Apply it as a surgical edit of part.text and change nothing it does not require.'
            if edit
            else 'Follow it as you write the section.',
        )
    return _queue(
        root,
        ident,
        draft,
        seen,
        'desk-section',
        payload,
        guidance,
        {'part': part, 'action': 'note' if note else 'again', 'basis': fingerprint(found['text'])},
    )


def selection(root, ident, seen, part, text, action, instruction='', start=None):
    """Rephrase, shorten, expand, fix or do as asked with one selected passage.

    `start` is where the selection begins in the part, so a word that occurs more than once
    is still the one the person selected; without it the passage must occur once."""
    draft = desk.read(root, ident)
    whole = desk.text_of(draft, part)
    if not isinstance(text, str) or not text.strip():
        raise ValueError('That passage is no longer in this part. Select it again.')
    if start is not None:
        if type(start) is not int or whole[start : start + len(text)] != text:
            raise ValueError('That passage is no longer in this part. Select it again.')
    elif text not in whole:
        raise ValueError('That passage is no longer in this part. Select it again.')
    elif whole.count(text) > 1:
        raise ValueError('That passage appears more than once here. Select a longer passage.')
    if action == 'ask':
        if not isinstance(instruction, str) or len(instruction) > 2000:
            raise ValueError('Keep the instruction to 2,000 characters.')
        instruction = instruction.strip()
        if not instruction:
            raise ValueError('Say what to do with the passage.')
        line = 'Do what the author asks below with the passage.'
    elif action in ACTIONS:
        line = ACTIONS[action]
    else:
        raise ValueError('Choose rephrase, shorten, expand, fix or ask.')
    extra, shared = _context(root, draft)
    payload = {'passage': text[:12_000], 'around': whole[:20_000], 'action': line, **extra}
    guidance = (
        _guide('desk-edit.md')
        + '\n\nAct on the passage only: '
        + line
        + ' Return only the replacement for passage in content; around is its context and '
        'is not returned.\n\n' + shared + '\n' + RETURN
    )
    if action == 'ask':
        guidance += _request(
            'INSTRUCTION FOR THE PASSAGE', instruction, 'Apply it to the passage only.'
        )
    return _queue(
        root,
        ident,
        draft,
        seen,
        'desk-selection',
        payload,
        guidance,
        {
            'part': part,
            'action': action,
            'selection': text,
            'start': start,
            'basis': fingerprint(whole),
        },
    )


def _whole_payload(draft, extra, note=''):
    return {
        'title': draft['title'],
        'opening': draft['opening'],
        'sections': [
            {'id': s['id'], 'heading': s['heading'], 'text': s['text']}
            for s in draft['sections']
            if s['text']
        ],
        'note': note,
        **extra,
    }


def _revise_one(root, ident, draft, section, note, chain, order):
    """Queue the whole-draft note's job for one section, with the whole draft as context."""
    extra, shared = _context(root, draft)
    payload = {**_whole_payload(draft, extra, note), 'part': section}
    guidance = _guide('desk-edit.md') + '\n\n' + REVISE_ONE + '\n\n' + shared + '\n' + RETURN
    guidance += _request(
        'NOTE FOR THE WHOLE DRAFT',
        note,
        'Apply it to part.text as a surgical edit and change nothing it does not require.',
    )
    meta = {
        'part': section['id'],
        'action': 'revise',
        'basis': fingerprint(section['text']),
        'chain': chain,
        'order': order,
        'index': order.index(section['id']),
    }
    return draft, payload, guidance, meta


def revise_all(root, ident, seen, note):
    """A note for the whole draft: each written section revised in order, one job each, with
    the whole draft as context. The next is queued when one settles; a section that fails is
    reported and the rest still go ahead; Stop ends it."""
    if not isinstance(note, str) or len(note) > 4000:
        raise ValueError('Keep the note to 4,000 characters.')
    note = note.strip()
    if not note:
        raise ValueError('Write the note for the whole draft.')
    draft = desk.read(root, ident)
    order = [s['id'] for s in draft['sections'] if s['text']]
    if not order:
        raise ValueError('This draft has no written sections to revise.')
    first = desk._part(draft, order[0])
    _, payload, guidance, meta = _revise_one(
        root, ident, draft, first, note, secrets.token_hex(8), order
    )
    return _queue(root, ident, draft, seen, 'desk-revise-all', payload, guidance, meta, order)


def _next(root, job):
    """After one section of a whole-draft note, queue the next written section, if any. A
    problem queuing it ends the note, said on the note's own record."""
    try:
        if not _queue_next(root, job):
            _chain_note(root, job, ended=True)
    except Exception as error:  # noqa: BLE001 - the note ends readably, never silently.
        message = str(error)[:1000] or type(error).__name__
        _chain_note(root, job, problem='The rest of the note stopped: ' + message, ended=True)


def _queue_next(root, job):
    meta = job['metadata']['desk']
    ident = job['metadata']['article']
    _guard(root, ident)  # Another computer may have taken the blog meanwhile.
    draft = desk.read(root, ident)
    if any(busy(other) for other in jobs(root, ident) if other['id'] != job['id']):
        return False  # Something else is under way; the note ends here.
    for part in meta['order'][meta['index'] + 1 :]:
        try:
            section = desk._part(draft, part)
        except ValueError:
            continue  # A section removed meanwhile is skipped.
        if section['text']:
            _, payload, guidance, step = _revise_one(
                root, ident, draft, section, job['payload']['note'], meta['chain'], meta['order']
            )
            _create(
                root,
                ident,
                'desk-revise-all',
                payload,
                guidance,
                {**step, 'seen': draft['revision']},
            )
            return True
    return False


FIRST_PASSES = ('tighten', 'reshape', 'leave')


def first_pass(root, ident, seen, choice):
    """Tighten and proofread, or reshape to the kind of post; leave queues nothing."""
    if choice not in FIRST_PASSES:
        raise ValueError('Choose tighten, reshape or leave it as it is.')
    if choice == 'leave':
        return None
    draft = desk.read(root, ident)
    if not any(s['text'] for s in draft['sections']):
        raise ValueError(
            'A first pass works section by section. Give the draft ## headings, or edit it '
            'as it is.'
        )
    if choice == 'reshape' and not draft.get('style'):
        raise ValueError('Choose a kind of post to reshape the draft to.')
    written = [{'id': s['id'], 'text': s['text']} for s in draft['sections'] if s['text']]
    if len(json.dumps(written, ensure_ascii=False)) > FIRST_PASS_LIMIT:
        raise ValueError(
            'This draft is too long for one first pass. Edit it section by section: a note '
            'on each section, or a note for the whole draft.'
        )
    import manuscript_editor

    extra, shared = _context(root, draft, length=choice == 'reshape')
    rule = (
        TIGHTEN + ' ' + manuscript_editor.CHECKS['copyedit'] + '\n\n' + _guide('desk-edit.md')
        if choice == 'tighten'
        else RESHAPE
    )
    guidance = rule + '\n\n' + WHOLE + '\n\n'
    guidance += shared + '\n' + RETURN
    return _queue(
        root,
        ident,
        draft,
        seen,
        'desk-first-pass',
        _whole_payload(draft, extra),
        guidance,
        {'part': 'sections', 'action': choice, 'basis': _sections_basis(draft)},
    )


# Settling: a ready result lands in the draft, once, with the replaced text kept first.


def _merge_gaps(draft, result):
    found = result.get('gaps')
    if not isinstance(found, list):
        return
    gaps = list(draft.get('gaps') or [])
    for gap in found:
        if isinstance(gap, str) and gap.strip() and gap.strip()[:1000] not in gaps:
            gaps.append(gap.strip()[:1000])
    draft['gaps'] = gaps[-GAPS:]


def _clean(text, heading=None):
    """The returned writing without a repeated heading or wrapping blank lines."""
    text = text.replace('\r\n', '\n').strip()
    if heading is not None:
        first, _, rest = text.partition('\n')
        if re.fullmatch(r'#{1,6}\s+' + re.escape(heading) + r'\s*', first.strip()):
            text = rest.strip()
    return text


def _no_heading(text):
    """A result that would add a section is refused readably; the person adds sections."""
    if desk.has_heading(text):
        raise ValueError(
            'The rewrite added a ## section heading, so it was not applied. Run it again.'
        )


def _section_texts(content):
    """[{id, text}] from a whole-draft result, refused readably when malformed."""
    text = content.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*)\n```', text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        found = json.loads(text)
    except ValueError:
        raise ValueError(
            'The result was not the list of sections asked for. Run it again.'
        ) from None
    if (
        not isinstance(found, list)
        or len(found) > 500
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get('id'), str)
            or not isinstance(item.get('text'), str)
            for item in found
        )
    ):
        raise ValueError('The result was not the list of sections asked for. Run it again.')
    return found


def _apply(root, ident, draft, job):
    meta, result = job['metadata']['desk'], job.get('result') or {}
    content = result.get('content')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('The result was empty. Run it again.')
    kind = job['kind']
    if kind in ('desk-section', 'desk-revise-all'):
        part = meta['part']
        try:
            section = desk._part(draft, part)
        except ValueError:
            raise ValueError(STALE) from None
        if fingerprint(section['text']) != meta.get('basis'):
            raise ValueError(STALE)
        text = _clean(content, section['heading'])
        _no_heading(text)
        desk.checked_text(part, text)
        desk.keep(
            root,
            ident,
            part,
            section['text'],
            'rewrite' if kind == 'desk-section' else 'revise-all',
        )
        section['text'] = text
        _merge_gaps(draft, result)
        return desk._write(root, ident, draft, [part])
    if kind == 'desk-selection':
        part, passage, start = meta['part'], meta.get('selection') or '', meta.get('start')
        try:
            whole = desk.text_of(draft, part)
        except ValueError:
            raise ValueError(STALE) from None
        unchanged = fingerprint(whole) == meta.get('basis')
        if not passage:
            raise ValueError(STALE)
        if unchanged and type(start) is int and whole[start : start + len(passage)] == passage:
            at = start
        elif whole.count(passage) == 1:
            at = whole.index(passage)
        else:
            raise ValueError(
                'The selected passage changed while this was being written. Select it again.'
            )
        # The passage's own spaces and line breaks stay around its replacement.
        lead = passage[: len(passage) - len(passage.lstrip())]
        trail = passage[len(passage.rstrip()) :]
        replacement = _clean(content)
        if part == 'title':
            replacement = ' '.join(replacement.split())
        updated = whole[:at] + lead + replacement + trail + whole[at + len(passage) :]
        _no_heading(replacement)
        desk.checked_text(part, updated)
        desk.keep(root, ident, part, whole, 'selection')
        desk._set(draft, part, updated)
        _merge_gaps(draft, result)
        return desk._write(root, ident, draft, [part])
    # The first pass: every section as it was asked about, and every returned id known.
    if _sections_basis(draft) != meta.get('basis'):
        raise ValueError(STALE)
    found = _section_texts(content)
    sections = {section['id']: section for section in draft['sections']}
    ids = [item['id'] for item in found]
    if len(set(ids)) != len(ids) or any(name not in sections for name in ids):
        raise ValueError('The result named sections this draft does not have. Run it again.')
    changes = {}
    for item in found:
        section = sections[item['id']]
        text = _clean(item['text'], section['heading'])
        if not text or text == section['text']:
            continue
        _no_heading(text)
        desk.checked_text(item['id'], text)
        changes[item['id']] = text
    for part, text in changes.items():
        desk.keep(root, ident, part, sections[part]['text'], 'first-pass')
        sections[part]['text'] = text
    _merge_gaps(draft, result)
    return desk._write(root, ident, draft, list(changes))


def _settle(root, job):
    """Land one ready job; the blog it changed, or None when it is left for later. Whatever
    goes wrong, the job is settled with a readable problem, so it never holds up the desk."""
    ident = (job.get('metadata') or {}).get('article')
    try:
        _guard(root, ident)  # A blog another computer drives settles there, not here.
        draft = desk.read(root, ident)
    except ValueError:
        return None
    try:
        _apply(root, ident, draft, job)
        job.update(applied=True, error='')
    except ValueError as error:
        job.update(applied=False, error=str(error)[:1000])
    except Exception as error:  # noqa: BLE001 - e.g. a full disk: said, never stuck.
        job.update(
            applied=False,
            error=('This result could not be saved: ' + str(error))[:1000]
            + ' Nothing was changed; run it again.',
        )
    job['settled_at'] = studio.now()
    tool_jobs.write(root, job)
    if job['kind'] == 'desk-revise-all':
        _chain_note(root, job, applied=job['applied'], problem=job['error'] or None)
        _next(root, job)
    return ident


def ended(root, job):
    """The worker's hook when a desk job ends, under the studio lock: settle a ready one.
    Returns the blog to record as a team decision once the lock is released, or None."""
    if unsettled(job):
        return _settle(root, job)
    if job.get('status') == 'failed' and job['kind'] == 'desk-revise-all':
        try:
            _guard(root, job['metadata']['article'])
        except ValueError:
            return None
        _chain_note(root, job, problem=job.get('error') or 'This section could not be revised.')
        _next(root, job)  # A section that failed is reported; the others still go ahead.
    return None


def share(root, ident):
    """Record a settled desk change as a team decision. Runs outside the studio lock, which
    is not reentrant. Best effort: when it cannot, the next desk request first commits what
    was left under the blog (team_workspace.keep_desk), so nothing jams."""
    from team_workspace import saved, space

    if not ident or not space(root):
        return
    try:
        saved(root, ident, 'Keep a desk change')
    except Exception:  # noqa: BLE001 - a sharing problem never takes the worker down.
        pass


def settle(root, ident):
    """Land each ready desk job of this blog that an older process left unsettled. A result
    whose part changed meanwhile, or that cannot be read, is kept unapplied with a readable
    problem."""
    landed = []
    for job in jobs(root, ident):
        if unsettled(job) and _settle(root, job) and job.get('applied'):
            landed.append(job['id'])
    return landed


def stop(root, ident, job_id):
    """Stop this blog's desk work: a job under way is cancelled, and a result that is ready
    but not yet landed is set aside."""
    found = jobs(root, ident)
    if not any(job['id'] == job_id for job in found):
        raise ValueError('Choose a job on this blog.')
    for job in found:
        if job['status'] in ACTIVE or unsettled(job):
            if job['kind'] == 'desk-revise-all':
                _chain_note(root, job, ended=True)
        if job['status'] in ACTIVE:
            tool_jobs.control(root, job['id'], 'cancel', blog_runner.engine(root))
        elif unsettled(job):
            job.update(applied=False, error='Stopped. Its result was set aside.')
            job['settled_at'] = studio.now()
            tool_jobs.write(root, job)


def _row(job):
    """A desk job as the page shows it: what it works on and how it went."""
    meta = (job.get('metadata') or {}).get('desk') or {}
    return {
        'id': job['id'],
        'kind': job['kind'],
        'status': job['status'],
        'busy': busy(job),
        'part': meta.get('part'),
        'action': meta.get('action'),
        # A whole-draft note: which section of how many, and the run of jobs it belongs to.
        'chain': meta.get('chain'),
        'index': meta.get('index'),
        'total': len(meta['order']) if meta.get('order') else None,
        # The person's own note, shown on the card while the job works on it.
        'note': (job.get('payload') or {}).get('note') or '',
        'applied': job.get('applied'),
        'error': job.get('error') or '',
        'created_at': job.get('created_at'),
        'started_at': job.get('started_at'),
        'finished_at': job.get('finished_at'),
    }


def view(root, ident):
    """The desk as the page reads it: the draft, its Markdown, its jobs and version counts."""
    import editorial
    import styles

    draft = desk.read(root, ident)
    directory, record = studio.item(root, 'articles', ident)
    rows = [_row(job) for job in jobs(root, ident)][-60:]
    style_name = None
    if draft.get('style'):
        try:
            style_name = styles.pinned(root, draft['style'])['name']
        except (ValueError, OSError, KeyError):
            style_name = None
    names = []
    for entry in draft.get('sources', []):
        try:
            names.append(
                {
                    'id': entry['source_id'],
                    'name': studio.item(root, 'sources', entry['source_id'])[1]['name'],
                    'purposes': entry['purposes'],
                }
            )
        except (ValueError, OSError, KeyError):
            names.append({'id': entry['source_id'], 'name': 'Unavailable source', 'purposes': []})
    last = rows[-1] if rows else None
    chain = None
    if last and last['chain']:
        record = chain_record(root, last['chain']) or {}
        chain = {
            'total': record.get('total', last['total']),
            'revised': record.get('revised', 0),
            'ended': bool(record.get('ended')),
            'working': bool(last['busy']),
            'problems': record.get('problems', []),
        }
    return {
        **draft,
        'markdown': desk.join(draft),
        'jobs': rows,
        'chain': chain,
        'working': next((row for row in reversed(rows) if row['busy']), None),
        'versions': desk.counts(root, ident),
        'run': studio.inside(directory, blog_runner.STATE).is_file(),
        'google': editorial.doc_link(record),
        'publication': (record.get('editorial') or {}).get('publication_url') or None,
        'style_name': style_name,
        'source_names': names,
        # The blog record's version, for Mark as published and Delete.
        'expected': studio.digest((directory / 'session.json').read_bytes()),
    }
