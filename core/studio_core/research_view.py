"""What a research stop shows, from a published Harness Research bundle, and what a
change to the research costs. Shared by Blog Studio, Presentation Studio and Training
Studio so that all three say the same things in the same words."""
from pathlib import Path

from studio_core import research_contract

JOIN = '--'
CHECKED = ('The independent check accepted the report and the brief: it found their '
           'coverage honest and the brief fit for its use.')
UNCHECKED = 'The independent check has not accepted this research.'


def _line(text):
    return ' '.join(str(text or '').split())


def series(items):
    items = [str(item) for item in items if item]
    if len(items) < 2:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def answered_by(finding_id, question_ids):
    """The planning question a finding answers: the one whose ID the finding's ID is, or
    begins with followed by two hyphens. The longest such ID wins."""
    best = None
    for ident in question_ids:
        if finding_id == ident or str(finding_id).startswith(ident + JOIN):
            if best is None or len(ident) > len(best):
                best = ident
    return best


def _read_words(yours, public):
    total = yours + public
    parts = ([f'{yours} of yours'] if yours else []) + ([f'{public} public'] if public else [])
    return f"{total} source{'' if total == 1 else 's'}: " + ', '.join(parts) + '.'


def account(folder, questions=()):
    """Return no account when the saved bundle is unreadable or malformed."""
    try:
        return _account(folder, questions)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _account(folder, questions):
    facts, manifest = research_contract.read_bundle(folder)
    folder = Path(folder)
    review = facts.get('review') if isinstance(facts.get('review'), dict) else {}
    assessment = review.get('assessment') if isinstance(review.get('assessment'), dict) else {}
    accepted = manifest.get('status') == 'complete' and bool(review.get('accepted'))
    sources = [s for s in facts.get('sources') or () if isinstance(s, dict)]
    titles = {s.get('id'): s.get('title') or s.get('origin') or s.get('id') for s in sources}
    asked = [{'id': q['id'], 'question': _line(q.get('question'))} for q in questions
             if isinstance(q, dict) and isinstance(q.get('id'), str)]
    ids = [q['id'] for q in asked]
    gaps = []

    def gap(text):
        text = _line(text)
        if text and text not in gaps:
            gaps.append(text)

    findings = []
    for finding in facts.get('findings') or ():
        own = [_line(block.get('text')) for block in finding.get('gaps') or ()
               if isinstance(block, dict) and _line(block.get('text'))]
        for text in own:
            gap(text)
        findings.append({'id': finding['id'], 'title': finding.get('title') or finding['id'],
                         'summary': _line((finding.get('summary') or {}).get('text')),
                         'gaps': own, 'question': answered_by(finding['id'], ids)})
    for sections in (facts.get('sections') or (), facts.get('brief') or ()):
        for section in sections:
            for block in section.get('blocks') or ():
                if isinstance(block, dict) and block.get('kind') == 'gap':
                    gap(block.get('text'))
    yours = sum(s.get('permission') == 'selected' for s in sources)
    public = sum(s.get('permission') == 'public' for s in sources)
    return {
        'brief': (folder / 'brief.md').read_text(encoding='utf-8'),
        'report': (folder / 'report.md').read_text(encoding='utf-8'),
        'evidence': (folder / 'evidence.md').read_text(encoding='utf-8'),
        'check': {'accepted': accepted, 'said': CHECKED if accepted else UNCHECKED,
                  'coverage': assessment.get('coverage'),
                  'usefulness': assessment.get('usefulness'),
                  'note': _line(assessment.get('note')),
                  'unread': [{'source': item.get('source'), 'title': titles.get(item.get('source')),
                              'access_error': _line(item.get('access_error'))}
                             for item in review.get('originals') or ()
                             if isinstance(item, dict) and item.get('read_original') is False]},
        'read': _read_words(yours, public),
        'sources': {'yours': yours, 'public': public,
                    'partial': [{'title': titles.get(s.get('id')), 'note': _line(s.get('context_note'))}
                                for s in sources if s.get('context') == 'partial']},
        'findings': findings, 'gaps': gaps,
        'questions': [{**q, 'findings': [f['id'] for f in findings if f['question'] == q['id']]}
                      for q in asked],
        'unplanned': [f['id'] for f in findings if f['question'] is None],
    }


REFRESH = 'Bring the evidence up to date'


def refresh_words(tried) -> str:
    """What bringing the research up to date costs, as its control says it: what its last try
    took, where that was recorded."""
    cost = research_contract.took(tried['seconds'], tried['dollars']) if tried else ''
    return ('Re-reads the sources and checks the report again: '
            + (f'its last try took {cost}.' if cost
               else 'about as long and as costly as the research was.'))


def price(attempts_by_name, redone=(), drafted=True, *, recorded=None):
    tried = recorded if recorded is not None else research_contract.last_rounds(attempts_by_name or {})
    most = research_contract.ROUNDS
    words = ('Asking for changes runs the research again' + (' from its last report' if drafted else '')
             + f': up to {most} rounds of writing and checking.')
    cost = research_contract.took(tried['seconds'], tried['dollars']) if tried else ''
    words += f' Its last try took {cost}.' if cost else ' No time or money was recorded for its last try.'
    if redone:
        words += ' Then it makes again: ' + series(redone) + '.'
    return {**(tried or {'rounds': 0, 'jobs': 0, 'seconds': 0, 'dollars': None}),
            'most': most, 'drafted': drafted, 'redone': list(redone), 'words': words,
            'refresh': refresh_words(tried)}
