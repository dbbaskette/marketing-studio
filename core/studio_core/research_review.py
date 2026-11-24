"""What an independent check of research objected to, and what the work took, in words.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
import json
from pathlib import Path


class ReviewRefused(ValueError):
    """The independent check still objected after every round of correction. The message
    says what it objected to; `objections` holds every objection for the studio's review,
    and `groups`, when given, the same objections counted by cause (see `grouped`)."""

    def __init__(self, objections, rounds, groups=None):
        self.objections = list(objections)
        self.rounds = rounds
        self.groups = list(groups or ())
        count = len(self.objections)
        said = ('The independent check of the research still needs changes after '
                f'{rounds} rounds of correction')
        if self.groups:
            total = sum(group['count'] for group in self.groups)
            said += (f': {total} objection' + ('' if total == 1 else 's')
                     + f' in {len(self.groups)} group' + ('' if len(self.groups) == 1 else 's')
                     + ': ' + ', '.join(f"{group['title']} ({group['note']})"
                                        for group in self.groups) + '.')
        elif count:
            said += f': {count} objection' + ('' if count == 1 else 's') + ', such as '
            said += ' '.join(shortened(note) for note in self.objections[:2])
        else:
            said += ', and did not say what: read the saved check.'
        super().__init__(said + ' The draft report and the check’s notes are saved for correction.')


class CheckCouldNotFinish(ReviewRefused):
    """The independent check could not read the original of a source the studio offered,
    that is all it objected to, and the studio cannot serve that original either. No
    correction can change that: it is the studio's problem, not the research's. `cause`
    holds each such source as {'source', 'title', 'file', 'original', 'access_error'};
    `said` is the studio's own answer, when it was asked; `rounds` counts only the rounds of
    correction before it, so this one is not counted."""

    def __init__(self, objections, rounds, cause, said=None):
        self.objections = list(objections)
        self.rounds = rounds
        self.cause = list(cause)
        self.said = said
        first = self.cause[0] if self.cause else {}
        named = f'the original of "{first.get("title") or first.get("source") or "a source"}"'
        why = said or first.get('access_error')
        if why:
            named += f' ({shortened(why).rstrip(".")}.)'
        more = len(self.cause) - 1
        if more:
            named += f' and of {more} more source' + ('' if more == 1 else 's')
        ValueError.__init__(self, (
            f'The research check could not read {named}. That is a studio problem, not a '
            'research problem: nothing was found wrong with the report, but the check could '
            'not finish. Nothing to correct until the original is readable.'))


def unreadable_originals(review, dossier):
    """The sources with an original of their own that a review says it could not read,
    when they are all it objected to; else []. That is: every verdict it did not support
    rests only on such sources, and its assessment asks for no revision. A verdict rests on
    the sources its fact cites, its finding's facts cite, or its passage's facts and
    findings cite. A source with no original (its capture is the document) is never the
    cause: the check has only to read its capture. Each is {'source', 'title', 'file',
    'original', 'access_error'}."""
    if not isinstance(review, dict) or not isinstance(dossier, dict):
        return []
    named = {source.get('id'): source for source in dossier.get('sources') or ()
             if isinstance(source, dict)}
    unread = {item.get('source'): item.get('access_error') or 'it gave no reason'
              for item in review.get('originals') or ()
              if isinstance(item, dict) and item.get('read_original') is False
              and (named.get(item.get('source')) or {}).get('original_file')}
    if not unread:
        return []
    assessment = review.get('assessment') or {}
    if isinstance(assessment, dict) and 'needs-revision' in (assessment.get('coverage'),
                                                            assessment.get('usefulness')):
        return []
    cited = {fact.get('id'): {citation.get('source') for citation in fact.get('citations') or ()
                              if isinstance(citation, dict)}
             for fact in dossier.get('facts') or () if isinstance(fact, dict)}
    found = {finding.get('id'): set().union(*(cited.get(ident, set()) for ident in
                                            (finding.get('support') or []) + (finding.get('counter') or [])))
             for finding in dossier.get('findings') or () if isinstance(finding, dict)}
    rests = {**cited, **found}
    passages = {}
    for prefix, sections in (('', dossier.get('sections')), ('brief:', dossier.get('brief'))):
        for section in sections or ():
            for number, block in enumerate(section.get('blocks') or ()):
                passages[f"{prefix}{section.get('id')}:{number}"] = block.get('refs') or []
    for number, comparison in enumerate(dossier.get('comparisons') or ()):
        for row_number, row in enumerate(comparison.get('rows') or ()):
            for cell_number, cell in enumerate(row.get('cells') or ()):
                passages[f'comparison:{number}:{row_number}:{cell_number}'] = cell.get('refs') or []
    for group in ('facts', 'findings', 'prose'):
        for item in review.get(group) or ():
            if not isinstance(item, dict) or item.get('verdict') in (None, 'supported', 'pending'):
                continue
            ident = item.get('id')
            sources = (set().union(*(rests.get(ref, set()) for ref in passages.get(ident, ())))
                       if group == 'prose' else rests.get(ident, set()))
            if not sources or not sources <= unread.keys():
                return []
    return [{'source': ident, 'title': (named.get(ident) or {}).get('title') or ident,
             'file': (named.get(ident) or {}).get('file'),
             'original': (named.get(ident) or {}).get('original_file'), 'access_error': said}
            for ident, said in unread.items()]


def shortened(note, limit=160):
    line = ' '.join(str(note).split())
    return line if len(line) <= limit else line[:limit - 1].rstrip() + '…'


def objections(case):
    """What the last saved review objected to, one sentence each: every verdict that is
    not supported, with its note, then an assessment that asks for revision."""
    path = case / 'review.json'
    try:
        review = json.loads(path.read_text()) if path.is_file() else {}
    except ValueError:
        return []
    if not isinstance(review, dict):
        return []
    found = []
    for group in ('facts', 'findings', 'prose'):
        for item in review.get(group) or ():
            if isinstance(item, dict) and item.get('verdict') not in (None, 'supported'):
                note = ' '.join(str(item.get('note') or '').split())
                found.append(f"{item.get('id')} ({item.get('verdict')}): {note or 'no note'}")
    assessment = review.get('assessment') or {}
    if isinstance(assessment, dict):
        asked = [name for name in ('coverage', 'usefulness') if assessment.get(name) == 'needs-revision']
        if asked:
            note = ' '.join(str(assessment.get('note') or '').split())
            found.append(' and '.join(asked).capitalize() + ' need' + ('s' if len(asked) == 1 else '')
                         + ' revision: ' + (note or 'no note'))
    return found[:40]


NOUNS = {'facts': ('fact', 'facts'), 'findings': ('finding', 'findings'),
         'prose': ('passage of the report or brief', 'passages of the report or brief')}


def grouped(case):
    """What the last saved review objected to, by cause: one group for each kind of item
    (facts, findings, passages) and verdict, then one for an assessment that asks for
    revision. Each group is {'title', 'count', 'note', 'items'}: 'title' such as "12 facts
    the check calls narrow", 'note' the first item's, and 'items' every one, as `objections`
    words them."""
    path = Path(case) / 'review.json'
    try:
        review = json.loads(path.read_text()) if path.is_file() else {}
    except ValueError:
        return []
    if not isinstance(review, dict):
        return []
    groups = []
    for kind in ('facts', 'findings', 'prose'):
        found = {}
        for item in review.get(kind) or ():
            if isinstance(item, dict) and item.get('verdict') not in (None, 'supported', 'pending'):
                note = ' '.join(str(item.get('note') or '').split()) or 'no note'
                found.setdefault(str(item['verdict']), []).append(f"{item.get('id')}: {note}")
        for verdict in sorted(found, key=lambda name: (name != 'unsupported', name)):
            items = found[verdict]
            noun = NOUNS[kind][len(items) != 1]
            said = 'unsupported' if verdict == 'unsupported' else f'the check calls {verdict}'
            groups.append({'title': f'{len(items)} {noun} {said}', 'count': len(items),
                           'note': shortened(items[0], 100), 'items': items})
    assessment = review.get('assessment') or {}
    if isinstance(assessment, dict):
        asked = [name for name in ('coverage', 'usefulness') if assessment.get(name) == 'needs-revision']
        if asked:
            note = ' '.join(str(assessment.get('note') or '').split()) or 'no note'
            groups.append({'title': ' and '.join(asked) + (' needs' if len(asked) == 1 else ' need')
                           + ' revision', 'count': 1, 'note': shortened(note, 100), 'items': [note]})
    return groups


def took(seconds, dollars):
    """What some work took, in words: "48 minutes and $9.80". Empty when nothing was
    recorded."""
    said = []
    seconds = round(seconds or 0)
    if seconds >= 90 * 60:
        hours, minutes = divmod(round(seconds / 60), 60)
        said.append(f"{hours} hour{'' if hours == 1 else 's'}"
                    + (f" {minutes} minute{'' if minutes == 1 else 's'}" if minutes else ''))
    elif seconds >= 60:
        minutes = round(seconds / 60)
        said.append(f"{minutes} minute{'' if minutes == 1 else 's'}")
    elif seconds >= 1:
        said.append(f"{seconds} second{'' if seconds == 1 else 's'}")
    if dollars is not None:
        said.append(f'${dollars:,.2f}')
    return ' and '.join(said)
