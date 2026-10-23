"""Desk work on the single-worker tool job queue: queue it, then settle the result.

Each job carries the part it changes and that part's text fingerprint when it was asked
for. A ready result lands only while that text is unchanged, with the text it replaces
kept as a version first. Like desk.py, every function expects the caller to hold the
studio lock.
"""

import json
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
    'Revise every section in sections for this note, with the full draft as context. Return '
    'JSON in content: a list of {"id": ..., "text": ...} for every section in sections, in '
    'order, ids unchanged, each text without its heading. Return a section the note does not '
    'touch exactly as it was.'
)
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


def jobs(root, ident):
    """Every desk job saved for one blog, oldest first."""
    folder = studio.inside(root, '.blog-runs', 'tools')
    found = []
    for target in folder.glob('*.json') if folder.is_dir() else []:
        try:
            value = tool_jobs.read(root, target.stem)
        except (ValueError, OSError):
            continue
        if value.get('kind') in KINDS and (value.get('metadata') or {}).get('article') == ident:
            found.append(value)
    return sorted(found, key=lambda value: value.get('created_at') or '')


def _busy(root, ident):
    if any(job['status'] in ACTIVE for job in jobs(root, ident)):
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


def _queue(root, ident, draft, seen, kind, payload, guidance, meta):
    desk.checked(draft, seen)
    _busy(root, ident)
    meta = {**meta, 'seen': seen}
    result = tool_jobs.create(
        root,
        secrets.token_hex(16),
        kind,
        payload,
        guidance,
        basis={'desk': seen},
        metadata={'article': ident, 'desk': meta},
    )
    blog_runner.engine(root).wake.set()
    return result


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


def selection(root, ident, seen, part, text, action, instruction=''):
    """Rephrase, shorten, expand, fix or do as asked with one selected passage."""
    draft = desk.read(root, ident)
    whole = desk.text_of(draft, part)
    if not isinstance(text, str) or not text.strip() or text not in whole:
        raise ValueError('That passage is no longer in this part. Select it again.')
    if whole.count(text) > 1:
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
            'basis': fingerprint(whole),
        },
    )
