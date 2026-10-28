"""Desk work on the single-worker tool job queue: queue it, then settle the result.

Each job carries the part it changes and that part's text fingerprint when it was asked
for. The worker settles a result as soon as it is ready (tool_jobs.once calls `ended`): it
lands only while that text is unchanged, with the text it replaces kept as a version first,
and in a team workspace it is then recorded as a decision (`share`). A result an older
process finished is settled by the next desk request. Like desk.py, every function except
`share` expects the caller to hold the studio lock. A job never carries image data: a part's
text holds only its image references (desk_images), every payload is scrubbed of any data a
source brings, and a result keeps the references the text had.
"""

import json
import re
import secrets
import shutil
import tempfile
from pathlib import Path

import blog_runner
import desk
import desk_images
import studio
import tool_jobs
from studio_core import step_times
from studio_core.drafting import basis, prompts

KINDS = (
    'desk-section',
    'desk-revise-all',
    'desk-selection',
    'desk-first-pass',
    'desk-research',
    'desk-outline',
    'desk-draft',
    # Finishing (desk_finish.py): each proposes changes the person applies, edits or skips.
    'finish-copyedit',
    'finish-humanize',
    'finish-facts',
    'finish-headline',
    'finish-feedback',
    'finish-voice',
    'finish-geo',
)  # A blog's own desk jobs; desk-angles runs before there is a blog.
FINISH = (
    'finish-copyedit',
    'finish-humanize',
    'finish-facts',
    'finish-headline',
    'finish-feedback',
    'finish-voice',
    'finish-geo',
)
# The basis rule and the words a desk job is asked with are the shared desk's
# (studio_core.drafting.basis and prompts).
ACTIVE = basis.ACTIVE
ACTIONS = prompts.ACTIONS
WRITE_AGAIN = (
    'Write this section again from its heading, its brief, the sections before it and the '
    'sources. Keep the kind of post and the tone. Return only the section text.'
)
WHOLE = prompts.WHOLE
REVISE_ONE = prompts.REVISE_ONE
FIRST_PASS_LIMIT = 180_000  # The whole draft as JSON must come back in one result.
OPENING = (
    'The opening, the text before the first section, is the item in sections with id '
    '"opening" and no heading; return it like the others.'
)
NO_HEADINGS = 'Add no ## heading anywhere: the sections stay as they are.'
DIVIDE = (
    'This draft has no sections yet: all of it is in the opening. You may divide it into '
    'sections with ## headings, as the kind of post’s shape asks, inside the opening’s text; '
    'keep its order and every fact.'
)
NO_TEXT = 'This draft has no text to work on yet. Write or paste some first.'
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
RETURN = blog_runner.WRITING_NOTES  # Evidence and gaps in notes, never in the prose.
STALE = basis.stale()
GAPS = basis.GAPS


def _guide(name):
    return (blog_runner.REFERENCES / 'modules' / name).read_text().rstrip()


def desk_check(name):
    """A manuscript editor check as a desk job reads it: the desk is tone-only, so there are
    house rules but no pinned author rules."""
    import manuscript_editor

    return manuscript_editor.CHECKS[name].replace(
        'the pinned author and house rules', 'the house rules'
    )


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
        heading = 'the opening' if meta['part'] == 'opening' else ''
        try:
            found = desk._part(desk.read(root, job['metadata']['article']), meta['part'])
            heading = found['heading'] if found else heading
        except (ValueError, OSError):
            pass
        record['problems'] = (
            record['problems'] + [{'part': meta['part'], 'heading': heading, 'error': problem}]
        )[-200:]
    if ended:
        record['ended'] = True
    studio.write_json(_chain_path(root, meta['chain']), record)


unsettled = basis.unsettled
busy = basis.busy


def _busy(root, ident):
    if any(busy(job) for job in jobs(root, ident)):
        raise ValueError('A desk job is already working on this blog. Wait or stop it.')


fingerprint = basis.fingerprint
_sections_basis = basis.sections_basis


def _pass_basis(draft):
    """What a first pass was asked about: the opening and every section."""
    return basis.pass_basis(draft, desk.CODEC)


def _opening_part(draft):
    """The opening as a part a whole-draft job works on, with no heading. A draft with no
    ## headings is all opening, so it is the one part such a job has."""
    return {'id': 'opening', 'heading': '', 'text': draft['opening']}


def _piece(draft, part):
    """The section a whole-draft job works on, or the opening as one."""
    return _opening_part(draft) if part == 'opening' else desk._part(draft, part)


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
    pinned = studio.item(root, 'articles', draft['id'])[1] if draft.get('id') else {}
    brand = pinned.get('brand')
    if draft.get('from_run') and not brand:
        directory, _ = studio.item(root, 'articles', draft['id'])
        brand = studio.read_json(studio.inside(directory, blog_runner.STATE)).get('brand')
    record['author'] = pinned.get('author', '')
    found = blog_runner.inputs(root, record, {'brief': {}, 'brand': brand})
    extra = {
        'style': style,
        'author': pinned.get('author', ''),
        **({'brand': brand} if brand else {}),
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
    if draft.get('images'):
        guidance += '\n' + desk_images.GUIDANCE
    return extra, guidance


def _request(label, text, scope):
    """The author's words as an instruction from the author, not as document data."""
    return prompts.request(label, text, scope, 'Blog Studio')


def _create(root, ident, kind, payload, guidance, meta):
    result = tool_jobs.create(
        root,
        secrets.token_hex(16),
        kind,
        desk_images.scrubbed(payload),  # A source's image data never reaches a job.
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
    if edit:
        rule = prompts.edit_rule('blog draft')
    else:
        # Written from its brief: the desk's writing rule, then the article guide.
        rule = _guide('desk-write.md') + '\n\n' + WRITE_AGAIN
        if found.get('brief'):
            rule += ' part.brief says what this section must do.'
        rule += '\n\n' + _guide('blog-write.md')
        research, said = _research_extra(root, ident)
        payload.update(research)
        rule += said
    guidance = rule + '\n\n' + shared
    guidance += '\n' + RETURN
    if note:
        guidance += _request(
            'NOTE FOR THIS SECTION',
            note,
            prompts.SURGICAL if edit else prompts.FOLLOW,
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
    if action not in ACTIONS and action != 'ask':
        raise ValueError('Choose rephrase, shorten, expand, fix or ask.')
    if not isinstance(instruction, str) or len(instruction) > 2000:
        raise ValueError('Keep the instruction to 2,000 characters.')
    instruction = instruction.strip() if action in ('ask', 'fix') else ''
    if action == 'ask':
        if not instruction:
            raise ValueError('Say what to do with the passage.')
        line = prompts.ASK
    else:
        line = ACTIONS[action]
    extra, shared = _context(root, draft)
    payload = {'passage': text[:12_000], 'around': whole[:20_000], 'action': line, **extra}
    guidance = prompts.edit_rule('blog draft') + prompts.passage_task(line) + shared + '\n' + RETURN
    if action == 'ask':
        guidance += _request('INSTRUCTION FOR THE PASSAGE', instruction, prompts.ONLY_PASSAGE)
    elif instruction:  # Fix from a proofread finding: the finding, as the author chose it.
        guidance += _request(
            'PROOFREAD FINDING TO FIX',
            instruction,
            prompts.ALSO_FIX,
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
    guidance = (
        prompts.edit_rule('blog draft') + '\n\n' + REVISE_ONE + '\n\n' + shared + '\n' + RETURN
    )
    guidance += _request(
        'NOTE FOR THE WHOLE DRAFT',
        note,
        prompts.SURGICAL_PART,
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
    if not order and draft['opening'].strip():
        order = ['opening']  # A draft with no ## headings is revised as its one part.
    if not order:
        raise ValueError('This draft has no written sections to revise.')
    first = _piece(draft, order[0])
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
            section = _piece(draft, part)
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


# Angles: three ways into a topic, suggested before the blog exists, keyed by the page's
# operation so the same request returns the same job.
ANGLES = (
    'Propose three distinct angles for this blog that the supplied sources can support. Each '
    'angle is a headline, the point it makes (what the reader should understand or do '
    'afterward) and who it is for. Where brief gives a point or an audience, stay close to '
    'it; the three still differ. Return JSON in content: a list of exactly three objects, each '
    '{"headline": ..., "point": ..., "audience": ...}, in plain words, with no source IDs. '
    'Do not outline or draft the blog.'
)
UNREADABLE_ANGLES = 'The angles came back in a shape Blog Studio cannot read. Ask again.'
ANGLE_FIELDS = (('headline', 300), ('point', 2000), ('audience', 500))
OPERATION = re.compile(r'[a-f0-9]{32}')


def _angles_path(root, operation):
    if not isinstance(operation, str) or not OPERATION.fullmatch(operation):
        raise ValueError('Angles need their page operation ID. Reload and ask again.')
    return studio.inside(root, '.blog-runs', 'desk-angles', operation + '.json')


def _words(data, key, limit, label):
    value = data.get(key) or ''
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('Keep ' + label + ' to ' + format(limit, ',') + ' characters.')
    return value.strip()


DAY = 86_400


def forget_angles(root, operation):
    """Remove one request's angles and their job: their payload holds source text."""
    target = _angles_path(root, operation)
    if not target.is_file() or target.is_symlink():
        return
    try:
        ident = studio.read_json(target).get('job')
        job = tool_jobs.read(root, ident)
        if job['status'] in ACTIVE:
            tool_jobs.control(root, ident, 'cancel', blog_runner.engine(root))
        tool_jobs.path(root, ident).unlink(missing_ok=True)
    except (ValueError, OSError, AttributeError):
        pass
    target.unlink(missing_ok=True)


def prune_angles(root):
    """Angles left more than a day are let go, with their jobs."""
    import time

    folder = studio.inside(root, '.blog-runs', 'desk-angles')
    for target in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        try:
            if time.time() - target.stat().st_mtime > DAY and OPERATION.fullmatch(target.stem):
                forget_angles(root, target.stem)
        except OSError:
            continue


def angles(root, data):
    """Queue three angles for a blog not yet made, from its title, point, audience, kind of
    post, tone and the sources chosen so far. Nothing is written to the library."""
    prune_angles(root)
    if data.get('replaces'):
        forget_angles(root, data['replaces'])  # The page asked again: the earlier ones go.
    target = _angles_path(root, data.get('operation'))
    title = _words(data, 'title', 500, 'the title')
    brief = {
        'point': _words(data, 'point', 2000, 'the point'),
        'audience': _words(data, 'audience', 500, 'who it is for'),
    }
    tone = _words(data, 'tone', 2000, 'the tone')
    style = data.get('style') or None
    if style is not None and not isinstance(style, str):
        raise ValueError('Choose a listed kind of post.')
    record = {'sources': []}
    desk._attach(root, data, record)
    chosen = {
        'title': title or 'A new blog',
        'sources': desk._citable(record['sources']),
        'style': studio.style_check(root, style) if style else None,
        'tone': tone,
        'gaps': [],
    }
    extra, shared = _context(root, chosen)
    extra.pop('gaps', None)
    extra.pop('response_kind', None)  # Content and notes: the angles are JSON in content.
    payload = {'title': title, 'brief': brief, **extra}
    guidance = ANGLES + '\n\n' + _guide('blog-argument-outline.md') + '\n\n' + shared
    if extra['sources']:
        guidance += '\nThe sources are in sources, with their names and stance.'
    asked = fingerprint([payload, guidance])
    if target.exists():
        prior = studio.read_json(target)
        if prior.get('fingerprint') != asked:
            raise ValueError('This request changed. Ask for angles again.')
        return angles_view(root, data['operation'])
    job = tool_jobs.create(
        root,
        secrets.token_hex(16),
        'desk-angles',
        desk_images.scrubbed(payload),
        guidance,
        basis=None,
        metadata={'article': None, 'desk': {'operation': data['operation']}},
    )
    studio.write_json(target, {'job': job['id'], 'fingerprint': asked})
    blog_runner.engine(root).wake.set()
    return angles_view(root, data['operation'])


def _unfenced(content):
    text = content.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*)\n```', text, re.S)
    return fenced.group(1) if fenced else text


def _read_angles(content):
    try:
        found = json.loads(_unfenced(content))
    except ValueError:
        raise ValueError(UNREADABLE_ANGLES) from None
    if not isinstance(found, list) or len(found) != 3:
        raise ValueError(UNREADABLE_ANGLES)
    angles = []
    for item in found:
        if not isinstance(item, dict):
            raise ValueError(UNREADABLE_ANGLES)
        angle = {}
        for key, limit in ANGLE_FIELDS:
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(UNREADABLE_ANGLES)
            angle[key] = ' '.join(value.split())[:limit]
        angles.append(angle)
    return angles


def _settle_angles(root, job):
    try:
        job['angles'] = _read_angles((job.get('result') or {}).get('content') or '')
        job.update(applied=True, error='')
    except ValueError as error:
        job.update(angles=[], applied=False, error=str(error))
    job['settled_at'] = studio.now()
    tool_jobs.write(root, job)
    return None  # No blog yet: nothing to record for the team.


def angles_view(root, operation):
    """Three angles as the page shows them, once the job has them."""
    target = _angles_path(root, operation)
    try:
        job = tool_jobs.read(root, studio.read_json(target)['job'])
    except (ValueError, OSError, KeyError, TypeError):
        raise ValueError('These angles are no longer here. Ask for angles again.') from None
    return {
        'operation': operation,
        'job': job['id'],
        'status': job['status'],
        'busy': busy(job),
        'angles': job.get('angles') or [],
        'error': job.get('error') or '',
    }


# A start's outline and draft, written from the brief, the sources and any research.
OUTLINE_JSON = (
    'Return JSON in content: {"title": ..., "opening_brief": ..., "sections": [{"heading": '
    '..., "brief": ...}]}, with at most 60 sections, each heading one line.'
)
SHAPE = (
    'Shape an outline with the author from their notes in notes: propose the sections the '
    'post needs, keeping their points, and their order where it works.'
)
DRAFT_TASK = (
    'Write the whole draft from outline: the opening, then a `## ` heading for each outline '
    'section, in order, each followed by its text. Return the Markdown in content.'
)
UNREADABLE_OUTLINE = 'The outline came back in a shape Blog Studio cannot read. Run it again.'


def _research_extra(root, ident):
    """What research before the writing found, for the payload, and a line saying so: the
    reviewed bundle as runs read it, or a plain research report."""
    from studio_core import research_contract

    directory, _ = studio.item(root, 'articles', ident)
    if (directory / 'research' / 'output.json').is_file():
        facts, manifest = research_contract.read_bundle(directory / 'research')
        return (
            {
                'research_bundle': {
                    'digest': manifest['digest'],
                    'brief': (directory / 'research' / 'brief.md').read_text(),
                    'findings': facts['findings'],
                    'facts': facts['facts'],
                    'sources': facts['sources'],
                }
            },
            '\nThe reviewed research for this post is in research_bundle. '
            + research_contract.HANDOFF,
        )
    report = studio.inside(directory, 'derived', 'blog-research.md')
    if report.is_file():
        return {'research': report.read_text()}, (
            '\nThe research findings are in research: use them as they cite their sources.'
        )
    return {}, ''


def _outline_basis(draft):
    """The sections an outline or a draft is written over. The title and the opening are
    not in it: typing there while the draft is written keeps what was typed (see
    _apply_draft), so the draft is never thrown away for it."""
    return fingerprint(
        [[s['id'], s['heading'], s.get('brief', ''), s['text']] for s in draft['sections']]
    )


def outline_job(root, ident, start=False):
    """Plan the post: a title, an opening brief and sections with briefs, from the point,
    the sources, any research, and the author's own outline or notes."""
    draft = desk.read(root, ident)
    begun = desk.read_start(root, ident) or {}
    notes = begun.get('notes') or ''
    extra, shared = _context(root, draft, length=True)
    research, said = _research_extra(root, ident)
    payload = {
        'title': draft['title'],
        'brief': draft.get('brief') or {'point': '', 'audience': ''},
        'notes': notes,
        **extra,
        **research,
    }
    task = ''
    if notes and begun.get('way') == 'shape':
        task = SHAPE
    elif notes:
        task = 'The author’s own outline or notes are in notes. ' + blog_runner.FROM_OUTLINE
    guidance = _guide('desk-write.md') + ('\n\n' + task if task else '') + '\n\n'
    guidance += _guide('blog-argument-outline.md') + '\n\n' + shared + said
    guidance += '\n' + RETURN + '\n' + OUTLINE_JSON
    return _queue(
        root,
        ident,
        draft,
        draft['revision'],
        'desk-outline',
        payload,
        guidance,
        {'part': 'sections', 'action': 'outline', 'basis': _outline_basis(draft), 'start': start},
        parts=[],
    )


def draft_job(root, ident, seen, start=False):
    """Write the whole draft from the outline: the opening and every section."""
    draft = desk.read(root, ident)
    if not draft['sections']:
        raise ValueError('Make the outline first: add its sections on the Outline tab.')
    extra, shared = _context(root, draft, length=True)
    research, said = _research_extra(root, ident)
    payload = {
        'title': draft['title'],
        'brief': draft.get('brief') or {'point': '', 'audience': ''},
        'opening_brief': draft.get('opening_brief', ''),
        'outline': [
            {'heading': s['heading'], 'brief': s.get('brief', '')} for s in draft['sections']
        ],
        **extra,
        **research,
    }
    guidance = _guide('desk-write.md') + '\n\n' + DRAFT_TASK + '\n\n'
    guidance += _guide('blog-write.md') + '\n\n' + shared + said
    guidance += '\n' + RETURN + '\n' + blog_runner.GAPS_OPEN
    return _queue(
        root,
        ident,
        draft,
        seen,
        'desk-draft',
        payload,
        guidance,
        {
            'part': 'sections',
            'action': 'draft',
            'basis': _outline_basis(draft),
            'opening': fingerprint(draft['opening']),
            'start': start,
        },
    )


def _read_outline(content):
    try:
        found = json.loads(_unfenced(content))
    except ValueError:
        raise ValueError(UNREADABLE_OUTLINE) from None
    sections = found.get('sections') if isinstance(found, dict) else None
    if not isinstance(sections, list) or not 1 <= len(sections) <= desk.SECTIONS:
        raise ValueError(UNREADABLE_OUTLINE)
    title, opening = found.get('title') or '', found.get('opening_brief') or ''
    if not isinstance(title, str) or not isinstance(opening, str):
        raise ValueError(UNREADABLE_OUTLINE)
    rows = []
    for item in sections:
        heading = item.get('heading') if isinstance(item, dict) else None
        brief = item.get('brief') or '' if isinstance(item, dict) else ''
        if not isinstance(heading, str) or not heading.strip() or not isinstance(brief, str):
            raise ValueError(UNREADABLE_OUTLINE)
        rows.append(
            {'heading': ' '.join(heading.split())[:200], 'brief': brief.strip()[: desk.BRIEF]}
        )
    return {
        'title': ' '.join(title.split())[:500],
        'opening_brief': opening.strip()[: desk.BRIEF],
        'sections': rows,
    }


def _apply_outline(root, ident, draft, job, result):
    if _outline_basis(draft) != job['metadata']['desk'].get('basis'):
        raise ValueError('The draft changed while the outline was being made. Run it again.')
    found = _read_outline(result.get('content') or '')
    taken = {s['id'] for s in draft['sections']}
    draft['sections'] = [{'id': desk._id(taken), **row, 'text': ''} for row in found['sections']]
    draft['opening_brief'] = found['opening_brief']
    draft['title'] = draft['title'] or found['title'] or 'Untitled'
    _merge_gaps(draft, result)
    return desk._write(root, ident, draft, [s['id'] for s in draft['sections']] + ['outline'])


def _same_heading(one, other):
    def plain(text):
        return ' '.join(re.sub(r'[^\w\s]', ' ', text.lower()).split())

    return plain(one) == plain(other)


def _apply_draft(root, ident, draft, job, result):
    if _outline_basis(draft) != job['metadata']['desk'].get('basis'):
        raise ValueError(
            'The outline or draft changed while the draft was being written. Write it again.'
        )
    text = (result.get('content') or '').replace('\r\n', '\n').strip()
    found = desk.split(text)
    if not found['sections']:
        raise ValueError('The draft came back without its ## sections. Write it again.')
    images = {**(draft.get('images') or {}), **found['images']}
    outline, taken = draft['sections'], {s['id'] for s in draft['sections']}
    # Each written section goes with the outline section of the same heading, then with the
    # one in its place, so its id, brief and History follow the right text.
    planned, used = [None] * len(found['sections']), set()
    for at, written in enumerate(found['sections']):
        for section in outline:
            if section['id'] not in used and _same_heading(section['heading'], written['heading']):
                planned[at] = section
                used.add(section['id'])
                break
    for at in range(len(found['sections'])):
        if planned[at] is None and at < len(outline) and outline[at]['id'] not in used:
            planned[at] = outline[at]
            used.add(outline[at]['id'])
    merged = []
    for at, written in enumerate(found['sections']):
        was = planned[at]['text'] if planned[at] else ''
        # Image data the text kept as text must come back; a part with none may be new text.
        text = desk_images.restored(was, written['text'], strict=desk_images.holds(was))
        text = desk_images.kept(was, text, images)
        desk.checked_text('opening', text, desk.limit(found))
        merged.append(
            {
                'id': planned[at]['id'] if planned[at] else desk._id(taken),
                'heading': written['heading'][:200],
                'brief': planned[at].get('brief', '') if planned[at] else '',
                **({'level': written['level']} if written.get('level') else {}),
                'text': text,
            }
        )
    merged += [s for s in outline if s['id'] not in used]  # Left out: they stay as they were.
    before = {s['id']: s['text'] for s in outline}
    for section in merged:
        if before.get(section['id']) and before[section['id']] != section['text']:
            desk.keep(root, ident, section['id'], before[section['id']], 'draft')
    typed = fingerprint(draft['opening']) != job['metadata']['desk'].get('opening')
    if found['opening'] and not typed:  # An opening typed meanwhile is the person's.
        opening = desk_images.restored(
            draft['opening'], found['opening'], strict=desk_images.holds(draft['opening'])
        )
        opening = desk_images.kept(draft['opening'], opening, images)
        desk.checked_text('opening', opening, desk.limit(found))
        if draft['opening'] and draft['opening'] != opening:
            desk.keep(root, ident, 'opening', draft['opening'], 'draft')
        draft['opening'] = opening
    draft['sections'] = merged
    draft['images'] = images
    _merge_gaps(draft, result)
    return desk._write(root, ident, draft, [s['id'] for s in merged] + ['opening', 'outline'])


# A start: its steps run one after another with no stops; a problem stops it for Retry.
STEP_WORDS = {'research': 'Researching', 'outline': 'Outlining', 'draft': 'Drafting'}
STOPPED_START = 'Stopped. Choose Retry to start this step again.'


def research_job(root, ident):
    """The research before the writing, as a run researches with no gate: the plan of
    research questions, then the research itself (research_run), in one job."""
    draft = desk.read(root, ident)
    start = desk.read_start(root, ident) or {}
    _, record = studio.item(root, 'articles', ident)
    brief = draft.get('brief') or {}
    run = {
        'brief': {
            'goal': brief.get('point') or draft['title'],
            'audience': brief.get('audience') or 'Blog readers',
        }
    }
    payload = {**blog_runner.inputs(root, record, run), 'documents': {}, 'changes': ''}
    payload['refresh'] = False
    stage = blog_runner.STAGES['research-plan']
    guidance = (
        stage[2]
        + '\n\n'
        + (blog_runner.REFERENCES / blog_runner.GUIDES['research-plan']).read_text()
        + '\n\n'
        + blog_runner.house_guide()
    )
    return _queue(
        root,
        ident,
        draft,
        draft['revision'],
        'desk-research',
        payload,
        guidance,
        {
            'part': 'research',
            'action': 'research',
            'start': True,
            'contract': start.get('contract'),
        },
        parts=[],
    )


def _transient_path(root, ident):
    """What a start is doing now and why it stopped: kept on this computer, beside its jobs,
    never in the blog's shared folder, so a phase note or a failure leaves nothing for the
    team to record."""
    return studio.inside(root, '.blog-runs', 'desk-starts', studio.identifier(ident) + '.json')


def transient(root, ident):
    target = _transient_path(root, ident)
    try:
        found = studio.read_json(target) if target.is_file() else {}
    except (ValueError, OSError):
        found = {}
    return found if isinstance(found, dict) else {}


def _keep_transient(root, ident, **values):
    studio.write_json(_transient_path(root, ident), {**transient(root, ident), **values})


def _note_phase(root, job, words):
    """Say what research is doing on the start. Best effort: a busy workspace skips it."""
    try:
        with studio.locked(root):
            ident = job['metadata']['article']
            start = desk.read_start(root, ident)
            if start and start.get('job') == job['id']:
                _keep_transient(root, ident, phase=words[:200])
    except (ValueError, OSError):
        pass


def _round_words(event):
    from studio_core import research_contract

    if 'round' not in event:
        return None
    if not event['round']:
        return 'Finding public sources'
    phase = {'author': 'writing the report', 'review': 'the independent check'}
    return (
        'Round '
        + str(event['round'])
        + ' of '
        + str(research_contract.ROUNDS)
        + (', ' + phase[event.get('phase')] if event.get('phase') in phase else '')
    )


def staging(root, ident):
    """Where a start's reviewed research waits on this computer while its job works: never in
    the blog's folder, which a team workspace would see as changed outside a decision."""
    return studio.inside(root, '.blog-runs', 'desk-starts', studio.identifier(ident))


def research_run(engine, job):
    """Run a start's research job outside the lock: the plan, then reviewed research through
    Harness Research when the start pinned it, or one research job with the assistant's web
    search. Nothing is written into the blog while it works: the plan and report go back with
    the result, a reviewed case waits in `staging`, and all of it lands when the job settles
    (`_land_research`), under the lock, as one team decision."""
    from studio_core import model_profiles, research_contract

    import time

    import blog_worker

    root, stop = engine.root, engine.stop
    deadline = time.monotonic() + job['seconds']  # One limit for the plan and the research.
    ident = job['metadata']['article']
    studio.item(root, 'articles', ident)

    def left():
        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            raise blog_worker.WorkerFailure(
                'Research ran out of the time a step may take.', 'time-limit'
            )
        return remaining

    def ask(data, guidance, step, web=False):
        if stop.is_set():
            raise ValueError('Research stopped.')
        selection = model_profiles.route(job, 'Blog Studio', step, purpose='research')
        return engine.worker(
            job['engine'],
            data,
            guidance,
            seconds=left(),
            web=web,
            stop=stop,
            model_selection=selection,
        )

    _note_phase(root, job, 'Planning the research')
    plan = ask(job['payload'], job['guidance'], 'research-plan')['content']
    if not isinstance(plan, str) or len(plan) > 200_000:
        raise ValueError('The research questions came back unreadable. Retry it.')
    payload = {**job['payload'], 'documents': {'research-plan': plan}}
    contract = job['metadata']['desk'].get('contract')
    if contract:
        import synthesis_research

        run = {
            'engine': job['engine'],
            'brief': payload['brief'],
            'research_contract': contract,
            'model_profiles': job.get('model_profiles'),
        }
        with tempfile.TemporaryDirectory(prefix='blog-desk-research-') as scratch:
            target = Path(scratch)
            result = synthesis_research.generate(
                target,
                run,
                payload,
                engine.worker,
                seconds=left(),
                stop=stop,
                progress=lambda event: (
                    _note_phase(root, job, _round_words(event)) if _round_words(event) else None
                ),
            )
            with studio.locked(root):
                if tool_jobs._working(root, job['id']) is not None and not stop.is_set():
                    kept = staging(root, ident)
                    shutil.rmtree(kept, ignore_errors=True)
                    kept.mkdir(parents=True)
                    research_contract.copy_case(
                        target / research_contract.CASE, kept / research_contract.CASE
                    )
        return {
            'content': result['content'][:200_000],
            'notes': result['notes'][:10_000],
            'plan': plan,
        }
    _note_phase(root, job, 'Researching')
    stage = blog_runner.STAGES['research']
    guidance = (
        stage[2]
        + '\n\n'
        + (blog_runner.REFERENCES / blog_runner.GUIDES['research']).read_text()
        + '\n\n'
        + blog_runner.house_guide()
    )
    result = ask(payload, guidance, 'research', web=blog_runner.searches_web(payload))
    content = result.get('content') if isinstance(result, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError('The research came back empty. Retry it.')
    if len(content) > 200_000:
        raise ValueError(
            'The research report came back longer than 200,000 characters, more than the '
            'draft can read. Nothing was saved; retry it.'
        )
    return {**result, 'plan': plan}


def _land_research(root, ident, job, result):
    """A start's research, settled: its plan, then its reviewed case published into the blog's
    research folder, or its report as derived/blog-research.md. The staged case goes."""
    from studio_core import research_contract

    directory, _ = studio.item(root, 'articles', ident)
    kept = staging(root, ident)
    case = kept / research_contract.CASE
    plan = result.get('plan')
    contract = (job['metadata'].get('desk') or {}).get('contract')
    if contract and not case.is_dir() and not (directory / 'research').is_dir():
        raise ValueError('The reviewed research was not kept on this computer. Retry it.')
    try:
        if contract and case.is_dir():
            research_contract.copy_case(case, directory / research_contract.CASE)
            research_contract.publish(case, directory / 'research')
        elif not contract:
            studio.atomic(
                studio.inside(directory, blog_runner.STAGES['research'][1]),
                result['content'].encode(),
            )
        if isinstance(plan, str) and plan.strip():
            studio.atomic(
                studio.inside(directory, blog_runner.STAGES['research-plan'][1]), plan.encode()
            )
    except Exception as error:  # noqa: BLE001 - part of it may be in the blog already.
        raise ValueError(
            'The research could not be saved in full (' + str(error)[:300] + '). Retry saves '
            'it again.'
        ) from None
    shutil.rmtree(kept, ignore_errors=True)
    return None


def conversation_owned(root, ident):
    return studio.item(root, 'articles', ident)[1].get('execution') == 'conversation'


def _queue_step(root, ident, step):
    """Queue one step of a start and say so on it."""
    if conversation_owned(root, ident):
        raise ValueError(
            'This work belongs to the conversation. Use desk handoff to request runner continuation.'
        )
    if step == 'research':
        job = research_job(root, ident)
    elif step == 'outline':
        job = outline_job(root, ident, start=True)
    else:
        job = draft_job(root, ident, desk.read(root, ident)['revision'], start=True)
    start = desk.read_start(root, ident)
    start['job'] = job['id']
    desk.write_start(root, ident, start)
    _keep_transient(root, ident, phase='', problem='')
    return job


def _start_problem(root, ident, problem):
    start = desk.read_start(root, ident)
    if start and not start.get('ended_at'):
        _keep_transient(root, ident, problem=(problem or 'This step did not finish.')[:1000])


def begin(root, ident):
    """Queue a new start's first step. A problem queuing it is kept on the start, where the
    page shows it with Retry; the blog is made either way."""
    if conversation_owned(root, ident):
        return None
    start = desk.read_start(root, ident)
    if not start or start.get('ended_at') or start.get('job'):
        return None
    try:
        _queue_step(root, ident, start['step'])
    except ValueError as error:
        _start_problem(root, ident, str(error))
        return str(error)
    return None


def stalled(root, ident, start):
    """Why a start that has not ended is not moving, or '' while its step is under way. A
    step interrupted when Blog Studio closed, or whose job is gone, stops it too."""
    return stalled_detail(root, ident, start)['problem']


LONGEST_STEP = 3600


def _longest(root):
    """The most time Try again with more time may give a start's step: twice the step time
    limit in Settings, and never more than an hour, as a run's retry allows."""
    return min(LONGEST_STEP, 2 * blog_runner.settings(root)['defaults']['seconds'])


def stalled_detail(root, ident, start):
    """Why a start stopped, and what the page may offer for it: {'problem', 'reason',
    'said', 'step', 'seconds', 'more'}. `reason` is 'cli' or 'time-limit' as the assistant's
    job ended, else 'research' when the research step stopped, else None. `said` holds the
    last lines a failed assistant printed (kept on this computer). `seconds` is the limit
    the stopped step had, and `more` the limit Try again with more time gives it, or None.
    Every value is empty while the step is under way or the start is done."""
    found = dict.fromkeys(('reason', 'said', 'step', 'seconds', 'more'), None)
    found['problem'] = ''
    if not start or start.get('ended_at') or conversation_owned(root, ident):
        return found
    job = None
    if start.get('job'):
        try:
            job = tool_jobs.read(root, start['job'])
        except (ValueError, OSError):
            job = None
    if job is not None and busy(job):
        return found
    job = job or {}
    reason = job.get('reason') if job.get('reason') in ('cli', 'time-limit') else None
    if reason is None and start.get('step') == 'research':
        reason = 'research'
    seconds = job.get('seconds') if isinstance(job.get('seconds'), int) else None
    # Settings are read only for a step out of time: the blog list asks this of every start.
    longest = _longest(root) if reason == 'time-limit' and seconds else 0
    return {
        'problem': (
            transient(root, ident).get('problem')
            or job.get('error')
            or 'This step stopped. Choose Retry to start it again.'
        ),
        'reason': reason,
        'said': (job.get('said') or None) if reason == 'cli' else None,
        'step': start.get('step'),
        'seconds': seconds,
        'more': min(longest, 2 * seconds)
        if reason == 'time-limit' and seconds and seconds < longest
        else None,
    }


def retry(root, ident, seconds=None, skip_research=False):
    """Run the step a start stopped at again, in a new job. With `seconds`, the step runs
    with that time limit, at most twice the setting. With `skip_research`, a start stopped
    at its research goes on without it: the step leaves the start, the start records that
    it has no research, and the next step is queued."""
    if conversation_owned(root, ident):
        raise ValueError(
            'This work belongs to the conversation. Use desk handoff to request continuation.'
        )
    start = desk.read_start(root, ident)
    if not stalled(root, ident, start):
        raise ValueError('Nothing to retry: this start is under way or done.')
    if seconds is not None:
        longest = _longest(root)
        if type(seconds) is not int or not 30 <= seconds <= longest:
            raise ValueError(
                'Choose a step time limit from 30 seconds to '
                + str(longest)
                + ' seconds, at most twice the step time limit in Settings.'
            )
    if skip_research is not False:
        if skip_research is not True:
            raise ValueError('Say whether to continue without research.')
        if start.get('step') != 'research':
            raise ValueError('Continue without research is for a start stopped at its research.')
    _busy(root, ident)
    if skip_research:
        steps = [step for step in start['steps'] if step != 'research']
        start.update(
            steps=steps,
            step=steps[0],
            research_from=None,
            contract=None,
            research_skipped={'at': studio.now()},
        )
        desk.write_start(root, ident, start)
        shutil.rmtree(staging(root, ident), ignore_errors=True)
    job = _queue_step(root, ident, start['step'])
    if seconds is not None:
        saved = tool_jobs.read(root, job['id'])
        saved['seconds'] = seconds
        tool_jobs.write(root, saved)


TIMES = step_times.TIMES  # step durations kept per step, for the estimate


def _times_path(root):
    return studio.inside(root, '.blog-runs', 'desk-step-times.json')


def _step_key(step, length):
    return 'draft:' + (length or 'style') if step == 'draft' else step


_seconds = step_times.seconds


def _note_time(root, key, seconds):
    """Keep how long a step took on this computer; best effort."""
    step_times.note(desk.BlogStore(root), _times_path(root), key, seconds)


def expected_minutes(root, step, length):
    """How long a step usually takes: the median of its recent runs here, else a guess."""
    return step_times.expected(
        desk.BlogStore(root),
        _times_path(root),
        _step_key(step, length),
        lambda: desk.estimate([step], length),
    )


def _advance(root, job):
    """After a start's step settles: the next step, or the end of the start."""
    ident = job['metadata']['article']
    if conversation_owned(root, ident):
        return
    start = desk.read_start(root, ident)
    if not start or start.get('job') != job['id'] or start.get('ended_at'):
        return
    if not job.get('applied'):
        _start_problem(root, ident, job.get('error'))
        return
    took = _seconds(job)
    if took is not None and took >= 0:
        draft = desk.read(root, ident)
        _note_time(root, _step_key(start['step'], draft.get('length')), took)
    at = start['steps'].index(start['step'])
    if at + 1 >= len(start['steps']):
        start.update(step=None, ended_at=studio.now())
        desk.write_start(root, ident, start)
        _keep_transient(root, ident, phase='', problem='')
        return
    start['step'] = start['steps'][at + 1]
    desk.write_start(root, ident, start)
    try:
        _queue_step(root, ident, start['step'])
    except Exception as error:  # noqa: BLE001 - the start stops readably, never silently.
        _start_problem(root, ident, str(error)[:1000] or type(error).__name__)


def _timing(root, ident, start, job):
    """About how many minutes are left, and whether the step under way has overrun."""
    if start.get('ended_at') or not start.get('step'):
        return {'minutes_left': 0, 'over': False}
    length = desk.read(root, ident).get('length')
    steps = start['steps'][start['steps'].index(start['step']) :]
    return step_times.left([expected_minutes(root, step, length) for step in steps], job)


def _start_view(root, ident, rows):
    start = desk.read_start(root, ident)
    if not start or conversation_owned(root, ident):
        return None
    job = next((row for row in rows if row['id'] == start.get('job')), None)
    timing = _timing(root, ident, start, job)
    detail = stalled_detail(root, ident, start)
    return {
        **timing,
        **{key: value for key, value in start.items() if key not in ('notes', 'contract')},
        'phase': transient(root, ident).get('phase') or '',
        'problem': detail['problem'],
        # Why it stopped and what the page offers: more time, no research, or Status.
        'reason': detail['reason'],
        'said': detail['said'],
        'seconds': detail['seconds'],
        'more': detail['more'],
        'busy': bool(job and job['busy']),
        'status': job['status'] if job else None,
        'doing': STEP_WORDS.get(start.get('step') or '', ''),
    }


def finish(root, ident, seen, tool, level=None, guide=None, chain=None):
    """Queue a finishing tool. It writes no part, so no card waits for it and no form is
    refused for it; its proposals are read against the draft when they come back. `chain`
    is Review mode's: what to queue once this one settles."""
    import desk_finish

    draft = desk.read(root, ident)
    kind, payload, guidance, meta = desk_finish.request(root, ident, draft, tool, level, guide)
    return _queue(
        root,
        ident,
        draft,
        seen,
        kind,
        payload,
        guidance,
        {'part': 'finishing', 'action': tool, **meta, **(chain or {})},
        parts=[],
    )


# Review mode ("Check spelling and grammar"): Copy edit, and when the person asked for it,
# Humanize at the strength they chose, queued once Copy edit settles. The choice is pinned
# on this computer beside the blog's waiting suggestions, so Check again asks for the same.
REVIEW = 'review.json'
PINNED = object()  # Check again: the strength pinned for this blog.
HUMANIZE_LEVELS = ('light', 'medium', 'strong')
NO_LEVEL = 'Choose light, medium or strong for the human-sounding suggestions, or leave them off.'


def _review_path(root, ident):
    return studio.inside(root, '.blog-runs', 'desk-proposals', studio.identifier(ident), REVIEW)


def review_record(root, ident):
    """{humanize, chain, copyedit, next, ended, problem} for this blog's latest check."""
    target = _review_path(root, ident)
    if not target.is_file() or target.is_symlink():
        return {}
    try:
        found = studio.read_json(target)
    except (ValueError, OSError):
        return {}
    return found if isinstance(found, dict) else {}


def humanize_level(value):
    """A start's or Check again's strength for the human-sounding suggestions, or None."""
    if value is not None and value not in HUMANIZE_LEVELS:
        raise ValueError(NO_LEVEL)
    return value


def review(root, ident, seen, humanize=PINNED):
    """Queue Check spelling and grammar: Copy edit, then Humanize at the pinned strength.
    One job runs at a time per blog; the second is queued when the first settles."""
    record = review_record(root, ident)
    level = record.get('humanize') if humanize is PINNED else humanize_level(humanize)
    if level not in HUMANIZE_LEVELS:
        level = None
    _busy(root, ident)  # A check under way keeps its own record.
    record = {'humanize': level}
    studio.write_json(_review_path(root, ident), record)  # The choice stays either way.
    chain = secrets.token_hex(8)
    job = finish(
        root, ident, seen, 'copyedit', chain={'review': chain, **({'then': level} if level else {})}
    )
    record.update(chain=chain, copyedit=job['id'], next=None, ended=not level, problem='')
    studio.write_json(_review_path(root, ident), record)
    return job


def _review_next(root, job):
    """After Copy edit settles, ready or not, queue Humanize for the same check, once. A
    problem queuing it is kept on the check's record for the page to say."""
    import desk_finish

    meta, ident = job['metadata']['desk'], job['metadata']['article']
    record = review_record(root, ident)
    if record.get('chain') != meta.get('review') or record.get('ended'):
        return None
    record['ended'] = True  # Whatever happens next, this step is taken once.
    try:
        if any(busy(other) for other in jobs(root, ident) if other['id'] != job['id']):
            raise ValueError('Another desk job started first, so the wording check did not.')
        draft = desk.read(root, ident)
        kind, payload, guidance, extra = desk_finish.request(
            root, ident, draft, 'humanize', meta['then']
        )
        made = _create(
            root,
            ident,
            kind,
            payload,
            guidance,
            {
                'part': 'finishing',
                'action': 'humanize',
                **extra,
                'review': meta['review'],
                'seen': draft['revision'],
            },
        )
        record['next'] = made['id']
    except Exception as error:  # noqa: BLE001 - said on the page, never silently stuck.
        record['problem'] = (str(error) or type(error).__name__)[:1000]
    studio.write_json(_review_path(root, ident), record)
    return record.get('next')


def interrupted(root, job):
    """A desk job Blog Studio found working when it started again (tool_jobs.recover), now
    failed: a check's Copy edit still lets its Humanize go ahead, once. Nothing else
    continues by itself."""
    if not (job.get('metadata', {}).get('desk') or {}).get('then'):
        return
    try:
        _guard(root, job['metadata']['article'])
        _review_next(root, job)
    except Exception:  # noqa: BLE001 - recovery never stops for one blog.
        return


def _review_end(root, ident):
    """Stop ends the check: nothing more is queued for it."""
    record = review_record(root, ident)
    if record.get('chain') and not record.get('ended'):
        record['ended'] = True
        studio.write_json(_review_path(root, ident), record)


def review_view(root, ident):
    """What Review mode needs of the check: the pinned strength and any problem queuing
    its second step."""
    record = review_record(root, ident)
    level = record.get('humanize')
    return {
        'humanize': level if level in HUMANIZE_LEVELS else None,
        'problem': str(record.get('problem') or '')[:1000],
    }


FIRST_PASSES = ('tighten', 'reshape', 'leave')


def first_pass(root, ident, seen, choice):
    """Tighten and proofread, or reshape to the kind of post; leave queues nothing."""
    if choice not in FIRST_PASSES:
        raise ValueError('Choose tighten, reshape or leave it as it is.')
    if choice == 'leave':
        return None
    draft = desk.read(root, ident)
    # The opening and each written section are the parts; a draft with no ## headings is
    # all opening, and is worked on as that one part.
    parts = [_opening_part(draft)] if draft['opening'].strip() else []
    parts += [
        {'id': s['id'], 'heading': s['heading'], 'text': s['text']}
        for s in draft['sections']
        if s['text']
    ]
    if not parts:
        raise ValueError(NO_TEXT)
    if choice == 'reshape' and not draft.get('style'):
        raise ValueError('Choose a kind of post to reshape the draft to.')
    written = [{'id': s['id'], 'text': s['text']} for s in parts]
    if len(json.dumps(written, ensure_ascii=False)) > FIRST_PASS_LIMIT:
        raise ValueError(
            'This draft is too long for one first pass. Edit it section by section: a note '
            'on each section, or a note for the whole draft.'
        )

    extra, shared = _context(root, draft, length=choice == 'reshape')
    rule = (
        TIGHTEN + ' ' + desk_check('copyedit') + '\n\n' + prompts.edit_rule('blog draft')
        if choice == 'tighten'
        else RESHAPE
    )
    # Only Reshape, and only on a draft with no sections, may add ## headings.
    divide = choice == 'reshape' and not draft['sections']
    guidance = (
        rule + '\n\n' + WHOLE + ' ' + OPENING + ' ' + (DIVIDE if divide else _no_headings(draft))
    )
    guidance += '\n\n' + shared + '\n' + RETURN
    payload = {**_whole_payload(draft, extra), 'sections': parts}
    payload.pop('opening')  # Sent once, as the first part.
    return _queue(
        root,
        ident,
        draft,
        seen,
        'desk-first-pass',
        payload,
        guidance,
        {'part': 'sections', 'action': choice, 'basis': _pass_basis(draft)},
        ['opening'] + [section['id'] for section in draft['sections']],
    )


# Settling: a ready result lands in the draft, once, with the replaced text kept first.


def _merge_gaps(draft, result):
    basis.merge_gaps(draft, result)


_clean = basis.clean
_opening_text = basis.opening_text
_landed = desk._landed  # A returned text as it lands, its images kept (desk_images).


def _no_heading(text, deepest=2):
    """A result that would add a section is refused readably; the person adds sections.
    `deepest` is the draft's `desk.limit`."""
    basis.no_heading(text, desk.CODEC, deepest)


def _no_headings(draft):
    """The rule that keeps a whole-draft job from adding a section, at the draft's level."""
    if desk.level(draft) == 2:
        return NO_HEADINGS
    mark = '#' * desk.level(draft)
    return 'Add no ' + mark + ' or ## heading anywhere: the sections stay as they are.'


_section_texts = basis.section_texts


def _put(draft, part, text):
    """A part's text set as it landed (desk._write tidies it when the draft is written)."""
    section = desk.CODEC.section(draft, part)
    if section is None:
        draft[part] = text
    else:
        section['text'] = text


def _apply(root, ident, draft, job):
    """Land a ready result through the shared basis rule (studio_core.drafting.basis): only
    while its part is unchanged, with the text it replaces kept as a version first. Each
    part whose rewrite changes a fact or its structure is noted in the job's `checks`; the
    rewrite lands either way."""
    meta, result = job['metadata']['desk'], job.get('result') or {}
    content = result.get('content')
    if not isinstance(content, str) or not content.strip():
        raise ValueError(basis.EMPTY_RESULT)
    kind = job['kind']
    if kind in FINISH:
        import desk_finish

        desk_finish.settle(root, ident, draft, job)
        return None  # Proposals only: nothing changes until the person applies them.
    if kind == 'desk-research':
        return _land_research(root, ident, job, result)
    if kind == 'desk-outline':
        return _apply_outline(root, ident, draft, job, result)
    if kind == 'desk-draft':
        return _apply_draft(root, ident, draft, job, result)
    if kind in ('desk-section', 'desk-revise-all', 'desk-selection'):
        if kind == 'desk-selection':
            part, before, text, flag = basis.land_selection(draft, meta, content, desk.CODEC)
            source = 'selection'
        else:
            part, before, text, flag = basis.land_part(draft, meta, content, desk.CODEC)
            source = 'rewrite' if kind == 'desk-section' else 'revise-all'
        desk.keep(root, ident, part, before, source)
        if kind == 'desk-selection':
            desk._set(draft, part, text)
        else:
            _put(draft, part, text)
        _merge_gaps(draft, result)
        written = desk._write(root, ident, draft, [part])
        _checked(job, {part: flag})
        return written
    # The first pass: the opening and every section as they were asked about, and every
    # returned id known. Reshaping a draft with no headings may divide it into sections.
    sections = {section['id']: section for section in draft['sections']}

    def divide(part, text):
        if part == 'opening' and meta.get('action') == 'reshape' and not sections:
            return _divided(text)
        return None

    changes, added = basis.land_sections(draft, meta, content, desk.CODEC, divide)
    for part, (before, text, _) in changes.items():
        if part == 'opening':
            # A division is undone as a whole: restoring this version takes out the sections
            # it added (desk.restore).
            divided = {'divided': [s['id'] for s in added]} if added else None
            desk.keep(root, ident, part, before, 'first-pass', extra=divided)
            draft['opening'] = text
        else:
            desk.keep(root, ident, part, before, 'first-pass')
            sections[part]['text'] = text
    draft['sections'] = draft['sections'] + added
    _merge_gaps(draft, result)
    written = desk._write(root, ident, draft, list(changes) + [s['id'] for s in added])
    _checked(job, {part: flag for part, (_, _, flag) in changes.items()})
    return written


def _checked(job, flags):
    """Keep each part's fact or structure check on the job, for the desk view to carry."""
    flags = {part: flag for part, flag in flags.items() if flag}
    if flags:
        job['checks'] = flags


def _divided(text):
    """A reshaped draft's text as its opening and the sections its ## headings start. A
    leading # title line is left out: the title is its own part."""
    found = desk.split(text)
    if len(found['sections']) > desk.SECTIONS:
        raise ValueError('The reshaped draft had too many sections, so it was not applied.')
    for section in found['sections']:
        if len(section['heading']) > 300:
            raise ValueError('The reshaped draft had a heading too long to use. Run it again.')
        desk.checked_text(section['id'], section['text'], desk.limit(found))
    return found['opening'], found['sections']


def _settle(root, job):
    """Land one ready job; the blog it changed, or None when it is left for later. Whatever
    goes wrong, the job is settled with a readable problem, so it never holds up the desk."""
    ident = (job.get('metadata') or {}).get('article')
    try:
        _guard(root, ident)  # A blog another computer drives settles there, not here.
        if (job.get('metadata', {}).get('desk') or {}).get('start') and conversation_owned(
            root, ident
        ):
            return None
        draft = desk.read(root, ident)
    except ValueError:
        return None
    basis.settle(job, lambda: _apply(root, ident, draft, job), studio.now)
    tool_jobs.write(root, job)
    if job['kind'] == 'desk-revise-all':
        _chain_note(root, job, applied=job['applied'], problem=job['error'] or None)
        _next(root, job)
    if (job['metadata'].get('desk') or {}).get('start'):
        _advance(root, job)
    if job['kind'] in FINISH:
        if (job['metadata'].get('desk') or {}).get('then'):
            _review_next(root, job)  # Review mode's Humanize, after its Copy edit.
        return None  # Its proposals wait on this computer: nothing for the team to record.
    return ident


def ended(root, job):
    """The worker's hook when a desk job ends, under the studio lock: settle a ready one.
    Returns the blog to record as a team decision once the lock is released, or None."""
    if job['kind'] == 'desk-angles':
        return _settle_angles(root, job) if unsettled(job) else None
    if unsettled(job):
        return _settle(root, job)
    if job.get('status') == 'failed' and (job['metadata'].get('desk') or {}).get('start'):
        try:
            _guard(root, job['metadata']['article'])
            _start_problem(root, job['metadata']['article'], job.get('error'))
        except ValueError:
            return None
        return job['metadata']['article']  # Shared, so nothing it touched is left behind.
    if job.get('status') == 'failed' and (job['metadata'].get('desk') or {}).get('then'):
        try:
            _guard(root, job['metadata']['article'])
        except ValueError:
            return None
        _review_next(root, job)  # A Copy edit that failed still lets its Humanize go ahead.
        return None
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
    start = desk.read_start(root, ident)
    _review_end(root, ident)  # A check's Humanize is not queued after Stop.
    for job in found:
        if job['status'] in ACTIVE or unsettled(job):
            if job['kind'] == 'desk-revise-all':
                _chain_note(root, job, ended=True)
            if start and start.get('job') == job['id']:
                _start_problem(root, ident, STOPPED_START)
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
        # A rewrite that changed a fact or its part's structure: {part: what to check}.
        'checks': job.get('checks') or {},
        'created_at': job.get('created_at'),
        'started_at': job.get('started_at'),
        'finished_at': job.get('finished_at'),
    }


def images_view(root, ident):
    """The data of a desk blog's images, which the page reads once and keeps; the desk view
    lists them by key only, so a poll never carries them."""
    desk.read(root, ident)
    # A record cleaned here but not written (another computer drives it) is served as cleaned.
    data = {**desk.cleaned_data(root, ident), **desk._data(root, ident)}
    return {'id': ident, 'images': desk_images.served(data)}


def _doc_suggestions(root, ident, draft):
    import google_pending

    return {
        'count': len(google_pending.read(root, ident)),
        'marks': google_pending.on_desk(root, ident, draft),
    }


def view(root, ident):
    """The desk as the page reads it: the draft, its Markdown, its jobs and version counts."""
    import desk_finish
    import editorial
    import styles

    draft = desk.read(root, ident)
    directory, record = studio.item(root, 'articles', ident)
    sendable = desk_finish.google_ready(record)
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
        tally = chain_record(root, last['chain']) or {}  # Not the blog's record, used below.
        chain = {
            'total': tally.get('total', last['total']),
            'revised': tally.get('revised', 0),
            'ended': bool(tally.get('ended')),
            'working': bool(last['busy']),
            'problems': tally.get('problems', []),
        }
    return {
        # The images are listed without their data, read once from `images_view`.
        **{key: value for key, value in draft.items() if key != 'images'},
        'images': desk_images.shown(draft),
        # Images the text names that are kept nowhere: the page says each is missing.
        'missing_images': desk_images.missing(
            draft,
            set(desk._held(root, ident)) | set(desk.cleaned_data(root, ident))
            if draft.get('images')
            else None,
        ),
        # Images too large for the blog's shared files, kept in its Google Doc: shown as such.
        'kept_images': desk_images.kept_in_doc(draft),
        'markdown': desk.join(draft, images=False),
        'jobs': rows,
        'chain': chain,
        'working': next((row for row in reversed(rows) if row['busy']), None),
        'versions': desk.counts(root, ident),
        'run': studio.inside(directory, blog_runner.STATE).is_file(),
        'google': editorial.doc_link(record),
        'publication': (record.get('editorial') or {}).get('publication_url') or None,
        'style_name': style_name,
        'source_names': names,
        # Sections taken out on the Outline tab, to bring back.
        'removed': [
            {
                'heading': item.get('heading') or '',
                'words': len(str(item.get('text') or '').split()),
                'at': item.get('at'),
            }
            for item in desk.removed(root, ident)
        ],
        # A start under way: the page shows its progress until the draft (or outline) opens.
        'start': _start_view(root, ident, rows),
        'execution': record.get('execution', 'runner'),
        'conversation_scope': record.get('conversation_scope'),
        # Finishing: the newest suggestions from each tool, waiting on this computer.
        'finishing': desk_finish.summary(root, ident, draft),
        # Review mode's check: whether it also suggests human-sounding wording, and how much.
        'review': review_view(root, ident),
        # Whether research was read for this draft, and how many sources it drew on.
        'research': _research_read(directory),
        # Whether the blog's Google Doc can take the desk's wording as suggestions.
        'google_suggestions': sendable,
        # Other people's suggestions pending in the blog's Google Doc, shown, never ours.
        'doc_suggestions': _doc_suggestions(root, ident, draft)
        if sendable
        else {'count': 0, 'marks': []},
        # The blog record's version, for Mark as published, Delete and changing its driver.
        'expected': expected(root, ident),
        # In a team workspace, who drives the blog, as a run says it (blog_runner.describe).
        # While another computer drives it, or nobody does, the desk is read only.
        **_team(root, ident),
    }


LINK = re.compile(r'https?://[^\s)<>\]"\']+')


def _research_read(directory):
    """{'sources': n} when research was read for this draft: the reviewed bundle's sources,
    or the distinct links in a plain research report. None when no research ran."""
    from studio_core import research_contract

    if (directory / 'research' / 'output.json').is_file():
        try:
            facts, _ = research_contract.read_bundle(directory / 'research')
            return {'sources': len(facts.get('sources') or [])}
        except (ValueError, OSError, KeyError, TypeError):
            return {'sources': None}
    report = directory / 'derived' / 'blog-research.md'
    if report.is_file():
        try:
            links = {link.rstrip('.,;:') for link in LINK.findall(report.read_text())}
        except (ValueError, OSError):
            return {'sources': None}
        return {'sources': len(links) or None}
    return None


def expected(root, ident):
    """The version of a desk blog's record the page last read: a change of driver, Mark as
    published and Delete each refuse a view whose blog has changed since."""
    directory, _ = studio.item(root, 'articles', ident)
    return studio.digest((directory / 'session.json').read_bytes())


def _team(root, ident):
    from studio_sync import team as drivers
    from team_workspace import driver, record, space

    found = space(root)
    if not found or not found.address:
        return {'team': False, 'driver': None, 'elsewhere': None}
    return {
        'team': True,
        'driver': driver(root, ident),
        'elsewhere': drivers.elsewhere(found, record(root, ident)),
    }
