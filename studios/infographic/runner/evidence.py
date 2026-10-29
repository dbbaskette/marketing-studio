"""Located supplied assertions and reproducible calculations, without invented evidence."""
from __future__ import annotations

from copy import deepcopy
from bisect import bisect_right
from decimal import Decimal
import re
import unicodedata

from .contracts import Invalid
from .sources import read
from .validation import number, records, require, text, validate_project

CONTEXT = ('period', 'denominator', 'conditions', 'uncertainty')
UNKNOWN = {'', 'unknown', 'not reported', 'unspecified'}
NUMBERS = re.compile(r'(?<![\w.,+-])[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?![\d.]|,\d|[eE][+-]?\d)')


def spaced(value):
    return ' '.join(value.split())


def typography(value):
    return unicodedata.normalize('NFC', value).translate(str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'"}))


def quoted_span(source, quote):
    """Match only unique literal/typographic spans, retaining original source bytes."""
    start = source.find(quote)
    if start >= 0 and source.find(quote, start + 1) < 0:
        return start, start + len(quote)
    if start >= 0:
        return None
    tokens = list(re.finditer(r'\S+', source))
    normalized = ' '.join(typography(m.group()) for m in tokens)
    wanted = typography(spaced(quote))
    matches, at = [], normalized.find(wanted)
    while wanted and at >= 0:
        end = at + len(wanted)
        if (at == 0 or normalized[at - 1] == ' ') and (end == len(normalized) or normalized[end] == ' '):
            matches.append(at)
            if len(matches) > 1:
                return None
        at = normalized.find(wanted, at + 1)
    if len(matches) != 1:
        return None
    at = matches[0]
    starts, offset = [], 0
    for token in tokens:
        starts.append(offset)
        offset += len(typography(token.group())) + 1
    first, last = bisect_right(starts, at) - 1, bisect_right(starts, at + len(wanted) - 1) - 1
    return tokens[first].start(), tokens[last].end()


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
            source_id = point.get('source_id')
            source, quote = captured.get(source_id) if isinstance(source_id, str) else None, point.get('quote')
            require(source is not None and text(quote, limit=120_000), 'Use a verbatim quotation in its named captured source.')
            start, end = point.get('start'), point.get('end')
            if type(start) is int and type(end) is int and 0 <= start < end <= len(source) and source[start:end] == quote:
                continue
            span = quoted_span(source, quote)
            require(span is not None,
                    'The quotation is absent or ambiguous. Choose a longer exact quote or a valid captured location; no evidence was guessed.')
            start, end = span
            point.update(start=start, end=end, quote=source[start:end])
        if number(fact.get('value')) and not fact.get('calculation') and 'literal' not in fact:
            literals = {m.group() for p in points for m in NUMBERS.finditer(p['quote'])
                        if Decimal(m.group()) == Decimal(str(fact['value']))}
            if len(literals) == 1:
                fact['literal'] = literals.pop()
    return located


def prepare_proposal(store, project, answer):
    """Canonicalize generated fields against located evidence, without changing claims."""
    facts = locate(store, project, answer['facts'])
    records(answer['stories'], 'Stories')
    uses = {}
    for story in answer['stories']:
        for block in story.get('blocks', []) if isinstance(story.get('blocks'), list) else ():
            if not isinstance(block, dict) or not isinstance(block.get('fact_ids'), list):
                continue
            for key in block['fact_ids']:
                if isinstance(key, str):
                    uses.setdefault(key, []).append(block.get('kind') == 'numbers' or block.get('quantitative') is True)
    quantitative_ids = {key for key, choices in uses.items() if all(choices)}
    for fact in facts:
        require(text(fact.get('statement')), 'Describe the supplied assertion.')
        fact['status'] = 'supplied'  # This pipeline has performed no independent corroboration.
        for key in CONTEXT:
            if key not in fact and not (number(fact.get('value')) or fact['id'] in quantitative_ids or fact.get('calculation') is not None):
                continue
            if fact.get(key) is None:
                fact[key] = ''
            require(text(fact[key], empty=True, limit=1000), 'Record measurement context as source text or leave it unknown.')
        if fact.get('unit') is None:
            fact['unit'] = 'unknown' if number(fact.get('value')) else ''
        require(text(fact['unit'], empty=True), 'Record units as source text or mark them unknown.')
        value = fact.get('value')
        quotes = [point['quote'] for point in fact.get('evidence', [])]
        calculation = fact.get('calculation')
        if not isinstance(value, str):
            continue
        if (fact['id'] in quantitative_ids or isinstance(calculation, dict)) and len(value) <= 100 and NUMBERS.fullmatch(value):
            exact = Decimal(value)
            converted = int(exact) if exact == exact.to_integral_value() else float(exact)
            if number(converted) and Decimal(str(converted)) == exact and (isinstance(calculation, dict) or any(
                    Decimal(m.group()) == exact for quote in quotes for m in NUMBERS.finditer(quote))):
                fact['value'] = converted
                if calculation is None:
                    fact['literal'] = value
        elif calculation is None and quotes and not NUMBERS.search(value) and not NUMBERS.search(fact['statement']) \
                and (not text(value) or not any(value and value in quote for quote in quotes)):
            fact['value'] = quotes[0][:1000]
    for fact in facts:
        if number(fact.get('value')) and not text(fact.get('unit')):
            fact['unit'] = 'unknown'
        if number(fact.get('value')) and fact.get('calculation') is None:
            literals = {m.group() for point in fact.get('evidence', []) for m in NUMBERS.finditer(point['quote'])
                        if Decimal(m.group()) == Decimal(str(fact['value']))}
            if len(literals) == 1:
                fact['literal'] = literals.pop()
    return locate(store, project, facts)


def validated_proposal(store, project, answer):
    """Only checked facts and reproducible dependent calculations reach story selection."""
    raw = records(answer['facts'], 'Facts')
    require(1 <= len(raw) <= 12, 'Select one to twelve relevant source-backed assertions for this page.')
    prepared, valid, problems = {}, {}, []
    for key, fact in raw.items():
        try:
            prepared[key] = prepare_proposal(store, project, {'facts': [fact], 'stories': answer['stories']})[0]
        except Invalid as failure:
            problems.append(str(failure))
    for key, fact in prepared.items():
        if fact.get('calculation') is not None:
            continue
        try:
            valid[key] = verify(store, project, [fact])[0]
        except Invalid as failure:
            problems.append(str(failure))
    pending = {key: fact for key, fact in prepared.items() if fact.get('calculation') is not None}
    while pending:
        progressed = False
        for key, fact in list(pending.items()):
            calc = fact['calculation']
            operands = calc.get('operands') if isinstance(calc, dict) else None
            if not isinstance(operands, list) or not all(isinstance(ref, str) for ref in operands):
                problems.append('A calculation needs named numeric operands.')
                del pending[key]; progressed = True; continue
            if not all(ref in valid for ref in operands):
                continue
            used = [valid[ref] for ref in operands]
            if fact.get('unit', '') in UNKNOWN:
                units = {f.get('unit') for f in used}
                if calc.get('operator') in ('ratio', 'percent_change'):
                    fact['unit'] = 'ratio' if calc['operator'] == 'ratio' else '%'
                elif len(units) == 1:
                    fact['unit'] = next(iter(units))
            for field in CONTEXT:
                contexts = {f.get(field, '') for f in used}
                if fact.get(field, '') in UNKNOWN and len(contexts) == 1:
                    fact[field] = next(iter(contexts))
            try:
                verify(store, project, [*valid.values(), fact])
            except Invalid as failure:
                problems.append(str(failure))
            else:
                valid[key] = fact
            del pending[key]; progressed = True
        if not progressed:
            problems.append('Calculations refer to unsupported or circular operands.')
            break
    require(bool(valid), problems[0] if problems else 'No source-backed assertions were returned.')
    return verify(store, project, [valid[key] for key in raw if key in valid])


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
            require(isinstance(point, dict) and isinstance(point.get('source_id'), str) and point['source_id'] in source_text,
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
            related = spaced('\n'.join(source_text[p['source_id']] for p in points)).casefold()
            for key in ('unit', *CONTEXT):
                value = spaced(fact[key]).casefold()
                require(value in UNKNOWN or value in related,
                        'Numeric ' + key + ' is not present in the selected source. Keep its literal wording or mark it unknown; do not infer measurement context.')
        else:
            require(text(fact.get('value')) and any(fact['value'] in quote for quote in quotes),
                    'Keep a literal source value or a reproducible calculation for each assertion.')
            period = fact.get('period', '')
            if text(period) and period.strip().casefold() not in UNKNOWN:
                related = spaced('\n'.join(source_text[p['source_id']] for p in points)).casefold()
                require(spaced(period).casefold() in related,
                        'A timeline period must be present in the captured source; do not invent a date.')
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


def quantitative(block: dict, facts: list[dict]) -> bool:
    """Descriptions can be compared or decomposed without a numeric scale.

    Legacy numeric comparisons still request charts. Mixed data needs an explicit
    qualitative choice; it must never silently pass the quantitative checks.
    """
    if 'quantitative' in block:
        require(type(block['quantitative']) is bool, 'Say explicitly whether this visual uses a numeric scale.')
    if block['kind'] not in ('comparison', 'numbers', 'parts'):
        return False
    require(bool(facts), 'A visual needs supplied facts.')
    if block['kind'] == 'numbers':
        require(block.get('quantitative', True), 'Number callouts need numeric source measurements; use a conceptual explanation for descriptions.')
        return True
    return block.get('quantitative', not all(text(f.get('value')) for f in facts))


def comparable(facts: list[dict]):
    require(bool(facts) and all(number(f.get('value')) for f in facts),
            'A quantitative visual needs numeric source values. Use a qualitative comparison or conceptual explanation for descriptions.')
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
