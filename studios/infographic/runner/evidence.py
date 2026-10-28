"""Located supplied assertions and reproducible calculations, without invented evidence."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import re

from .contracts import Invalid
from .sources import read
from .validation import number, records, require, text, validate_project

CONTEXT = ('period', 'denominator', 'conditions', 'uncertainty')
UNKNOWN = {'', 'unknown', 'not reported', 'unspecified'}
NUMBERS = re.compile(r'(?<![\w.])[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?![\w.])')


def locate(store, project, proposed):
    """Resolve an assistant's exact unique quotation; never guess ambiguous evidence."""
    records(proposed, 'Facts')
    located = deepcopy(proposed)
    captured = {source['id']: read(store, project, source) for source in project['sources']}
    for fact in located:
        points = fact.get('evidence', [])
        require(isinstance(points, list), 'Evidence locations must be a list.')
        for point in points:
            require(isinstance(point, dict), 'Locate the assertion in a captured source.')
            source, quote = captured.get(point.get('source_id')), point.get('quote')
            require(source is not None and text(quote, limit=120_000), 'Use a verbatim quotation in its named captured source.')
            start, end = point.get('start'), point.get('end')
            if type(start) is int and type(end) is int and 0 <= start < end <= len(source) and source[start:end] == quote:
                continue
            position = source.find(quote)
            require(position >= 0 and source.find(quote, position + 1) < 0,
                    'The quotation is absent or ambiguous. Choose a longer exact quote or a valid captured location; no evidence was guessed.')
            point.update(start=position, end=position + len(quote))
        if number(fact.get('value')) and not fact.get('calculation') and 'literal' not in fact:
            literals = {m.group() for p in points for m in NUMBERS.finditer(p['quote'])
                        if Decimal(m.group()) == Decimal(str(fact['value']))}
            if len(literals) == 1:
                fact['literal'] = literals.pop()
    return located


def verify(store, project: dict, proposed: list[dict]) -> list[dict]:
    facts = records(proposed, 'Facts')
    source_text = {source['id']: read(store, project, source) for source in project['sources']}
    for fact in facts.values():
        require(fact.get('status') == 'supplied', 'Supplied-only work cannot claim independent corroboration.')
        require(text(fact.get('statement')), 'Describe the supplied assertion.')
        if 'literal' in fact:
            require(number(fact.get('value')) and text(fact['literal'], limit=100)
                    and NUMBERS.fullmatch(fact['literal']) is not None
                    and Decimal(fact['literal']) == Decimal(str(fact['value'])),
                    'A numeric display literal must equal its exact saved value.')
        if fact.get('calculation') is not None:
            continue  # The project validator checks operands, units, cycles and exact arithmetic.
        points = fact.get('evidence')
        require(isinstance(points, list) and bool(points), 'Locate every assertion in a captured source.')
        quotes = []
        for point in points:
            require(isinstance(point, dict) and point.get('source_id') in source_text,
                    'The assertion names a missing captured source.')
            value = source_text[point['source_id']]
            start, end, quote = point.get('start'), point.get('end'), point.get('quote')
            require(type(start) is int and type(end) is int and 0 <= start < end <= len(value)
                    and isinstance(quote, str) and value[start:end] == quote,
                    'The quoted evidence does not match its exact captured source location.')
            quotes.append(quote)
        if number(fact.get('value')):
            require(all(text(fact.get(key), empty=True, limit=1000) for key in CONTEXT),
                    'Record numeric period, denominator, conditions and uncertainty; leave unknown context empty.')
            require(any(Decimal(match.group()) == Decimal(str(fact['value']))
                        for quote in quotes for match in NUMBERS.finditer(quote)),
                    'The numeric literal is absent from the captured evidence. Record an explicit calculation instead.')
            if 'literal' in fact:
                require(text(fact['literal'], limit=100) and any(m.group() == fact['literal']
                    and Decimal(m.group()) == Decimal(str(fact['value'])) for quote in quotes for m in NUMBERS.finditer(quote)),
                    'Preserve an exact numeric source literal for display; do not reformat or round it.')
            related = '\n'.join(source_text[p['source_id']] for p in points).casefold()
            for key in ('unit', *CONTEXT):
                value = fact[key].strip().casefold()
                require(value in UNKNOWN or value in related,
                        'Numeric ' + key + ' is not present in the selected source. Keep its literal wording or mark it unknown; do not infer measurement context.')
        else:
            require(text(fact.get('value')) and any(fact['value'] in quote for quote in quotes),
                    'Keep a literal source value or a reproducible calculation for each assertion.')
    candidate = deepcopy(project)
    candidate.update(facts=deepcopy(proposed), stories=[], selected_story=None, scene=None,
                     image_briefs=[], attempts=[], checks=[], approval=None)
    validate_project(candidate)
    return deepcopy(proposed)


def findings(facts: list[dict]) -> list[dict]:
    result, groups = [], {}
    for fact in facts:
        if not number(fact.get('value')):
            continue
        missing = [key for key in ('unit', 'period', 'denominator', 'conditions')
                   if fact.get(key, '').strip().casefold() in UNKNOWN]
        if not fact.get('uncertainty', '').strip(): missing.append('uncertainty')
        if missing:
            result.append({'fact_ids': [fact['id']], 'kind': 'missing-context',
                           'message': 'Clarify ' + ', '.join(missing) + ' before a numeric comparison.'})
        key = (fact.get('metric', fact['statement']), fact.get('unit'),
               fact.get('period'), fact.get('denominator'), fact.get('conditions'))
        groups.setdefault(key, []).append(fact)
    for group in groups.values():
        if len({str(f['value']) for f in group}) > 1:
            result.append({'fact_ids': [f['id'] for f in group], 'kind': 'conflicting-values',
                           'message': 'Different values describe the same measurement context. Resolve or qualify them.'})
    return result


def comparable(facts: list[dict]):
    require(bool(facts) and all(number(f.get('value')) for f in facts), 'A quantitative visual needs numeric source values.')
    require(all(f.get('unit', '').strip().casefold() not in UNKNOWN for f in facts), 'Clarify numeric units before comparison.')
    require(len({f['unit'] for f in facts}) == 1, 'Do not compare different units.')
    for key in CONTEXT:
        require(all(f.get(key, '').strip() and (key == 'uncertainty' or f[key].strip().casefold() not in UNKNOWN)
                    for f in facts), 'Clarify numeric ' + key + ' before comparison.')
        require(len({f[key] for f in facts}) == 1, 'Numeric ' + key + ' differs; use separate qualified explanations.')
    require(not any(f['kind'] == 'conflicting-values' for f in findings(facts)),
            'Resolve conflicting measurements before charting them.')


def adopt(store, ident: str, facts: list[dict], *, expected_revision: int) -> dict:
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        return store.change_locked(project, {'facts': verify(store, project, facts)})
