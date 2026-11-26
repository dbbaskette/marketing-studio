"""The studio's own equivalents of the pinned helper's rules: everything an evidence
packet, a synthesis or a review would be refused for, said at once, and the checks of
sources and citations against what a job captured.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
from collections import Counter
import copy
from pathlib import Path

from studio_core.research_schema import (
    HOST_FIELDS, ID_PATTERN, LIMITS, UNREADABLE, WHEN_PRESENT, conditions, identifier,
    permission_of, pinned, pinned_schema, wrong_text)


def capture_texts(sources, captures, folder):
    """{source ID: the capture text Harness Research will read for it}, for each source whose
    file this job saved: the exact bytes the helper's case is given, decoded as it decodes them."""
    saved = {entry['file']: entry for entry in captures if entry.get('file')}
    texts = {}
    for source in sources:
        file = source.get('file') if isinstance(source, dict) else None
        entry = saved.get(file) if isinstance(file, str) else None
        if not entry or not folder or not entry.get('local') or not isinstance(source.get('id'), str):
            continue
        try:
            text = (Path(folder) / entry['local']).read_bytes().decode('utf-8')
        except (OSError, UnicodeDecodeError):
            continue   # The helper says why it cannot read it.
        texts.setdefault(source['id'], text.removeprefix('\ufeff'))
    return texts


def clipped(quote, limit=80):
    line = ' '.join(str(quote).split())
    return line if len(line) <= limit else line[:limit - 1].rstrip() + '…'


def packet_problems(value, texts, runtime, worker=None, mode=None):
    """What the pinned helper's common evidence rules would refuse, every one at once, as
    (problems, flawed source indexes, flawed fact indexes).

    These are the studio's equivalents of the rules Harness Research stops at the first of:
    each source's required and conditional fields, its choices and its text bounds; each fact's
    ID, statement, author and citations; and each quote, which must appear exactly in the
    capture it cites. The fields, choices and conditions come from the pinned schema; a rule
    the studio does not know here is still the helper's, which runs once these pass. Nothing
    is refused here that the helper would accept. File, origin, permission and citation IDs are
    checked against the job's own captures by uncaptured and citation_sources.
    """
    try:
        definitions = pinned(runtime)
        source_rule, fact_rule = definitions['source'], definitions['fact']
        source_fields = source_rule['properties']
        fact_fields = fact_rule['properties']
    except (OSError, ValueError, KeyError, TypeError):
        return [], set(), set()
    citation_rule = (fact_fields.get('citations') or {}).get('items') or {}
    citation_fields = citation_rule.get('properties') or {}
    required, when = set(source_rule.get('required') or ()), conditions(source_rule)
    problems, flawed_sources, flawed_facts = [], set(), set()
    rows = value.get('sources') if isinstance(value.get('sources'), list) else []
    ids = repeated([row.get('id') for row in rows if isinstance(row, dict)])
    for index, source in enumerate(rows):
        if not isinstance(source, dict):
            continue
        name = source['id'] if isinstance(source.get('id'), str) and source['id'] else f'number {index + 1}'
        said = []
        if 'id' in source_fields and not identifier(source.get('id'), source_fields['id']):
            said.append('id must be lowercase letters, digits and hyphens (at most 64), such as s1')
        elif ids(source.get('id')):
            said.append('another source has the same id')
        for field, rule in source_fields.items():
            rule = rule if isinstance(rule, dict) else {}
            if field in HOST_FIELDS:
                continue
            present = field in source
            needed = field in required or any(source.get(other) == wanted
                                              for other, wanted in when.get(field, ()))
            if isinstance(rule.get('enum'), list):
                if needed and source.get(field) not in rule['enum']:
                    choices = ', '.join(map(str, rule['enum']))
                    said.append(f'{field} must be one of {choices}, not {clipped(source[field], 40)!r}'
                                if source.get(field) is not None else f'{field} is missing: use one of {choices}')
            elif rule.get('type') == 'string' and (needed or present and field in WHEN_PRESENT['source']):
                wrong = 'is missing' if not present else wrong_text(source[field])
                if wrong:
                    said.append(f'{field} {wrong}' + (
                        ': leave it out when unknown, and never guess a date' if field in ('source_date', 'accessed_at')
                        else ': give who published it, as the source itself shows it' if field == 'publisher'
                        else ': say what part of the source is missing' if field == 'context_note' else ''))
        if said:
            flawed_sources.add(index)
            problems.append(f'Source {name}: ' + '; '.join(said) + '.')
    known = {row['id'] for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)}
    facts = value.get('facts') if isinstance(value.get('facts'), list) else []
    fact_ids = repeated([fact.get('id') for fact in facts if isinstance(fact, dict)])
    authored = False
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            flawed_facts.add(index)
            problems.append(f'Fact number {index + 1}: return each fact as an object.')
            continue
        name = fact['id'] if isinstance(fact.get('id'), str) and fact['id'] else f'number {index + 1}'
        said = []
        unknown = sorted(set(fact) - set(fact_fields)) if mode == 'evidence' else []
        if unknown:
            said.append('unknown field(s) ' + ', '.join(unknown))
        if 'id' in fact_fields and not identifier(fact.get('id'), fact_fields['id']):
            said.append('id must be lowercase letters, digits and hyphens (at most 64)')
        elif fact_ids(fact.get('id')):
            said.append('another fact has the same id')
        elif isinstance(fact.get('id'), str) and fact['id'] in known:
            said.append('its id is also a source id; give it its own')
        if 'statement' in fact_fields:
            wrong = wrong_text(fact.get('statement'), LIMITS['statement'])
            if wrong:
                said.append(f'statement {wrong}')
        if worker and fact.get('author') != worker:
            authored = True
            flawed_facts.add(index)
        citations = fact.get('citations')
        if not isinstance(citations, list):
            said.append('citations must be an array')
            citations = []
        elif not citations and 'citations' in fact_fields:
            said.append('it needs at least one citation with an exact quote')
        for number, citation in enumerate(citations, start=1):
            if not isinstance(citation, dict):
                said.append(f'citation {number} must be an object')
                continue
            unknown = sorted(set(citation) - set(citation_fields)) if mode == 'evidence' and citation_fields else []
            if unknown:
                said.append(f'citation {number} has unknown field(s) ' + ', '.join(unknown))
            ref = citation.get('source')
            if not isinstance(ref, str) or ref not in known:
                flawed_facts.add(index)   # citation_sources says which IDs it may use
                continue
            quote = citation.get('quote')
            wrong = wrong_text(quote, LIMITS['quote']) if 'quote' in citation_fields else None
            if wrong:
                said.append(f'citation {number} quote {wrong}')
            for field in WHEN_PRESENT['citation']:
                if field in citation and field in citation_fields and wrong_text(citation[field]):
                    said.append(f'citation {number} {field} {wrong_text(citation[field])}: '
                                'leave it out when there is none')
            if not wrong and isinstance(quote, str) and ref in texts and quote not in texts[ref]:
                from studio_core.shared_runner.worker_tools import place
                found = place(texts[ref], quote)
                said.append(f'the quote {clipped(quote)!r} is not in source {ref} exactly' + (
                    f'; the capture has it as {found[1]!r}: copy that' if found and len(found[1]) <= 400
                    else '; it differs from the capture in spacing or punctuation: copy it from '
                         'the capture as it stands' if found else
                    '; quote only words the capture holds, or cite another source'))
        if said:
            flawed_facts.add(index)
            problems.append(f'Fact {name}: ' + '; '.join(said) + '.')
    if authored:
        problems.append(f'Set every fact author to {worker}.')
    return problems, flawed_sources, flawed_facts


def source_metadata(value, runtime):
    """Match source metadata to the pinned helper before the collection boundary.

    The dossier saver permits extra metadata that the collection registry refuses.
    Preserve the common date spelling without guessing missing dates or resolving
    conflicts. Other unknown fields get feedback while the author can still correct
    its submission; evidence, permissions, captures and citations stay unchanged.
    """
    if not runtime:
        return value, []
    try:
        allowed = set(pinned(runtime)['source']['properties'])
    except (OSError, ValueError, KeyError, TypeError):
        return value, [UNREADABLE]
    result, problems = copy.deepcopy(value), []
    for source in result.get('sources') or []:
        if not isinstance(source, dict):
            problems.append('Return each source as an object.')
            continue
        name = source.get('id') or 'unnamed'
        if 'date' in source and 'source_date' in allowed:
            date = source['date']
            if isinstance(date, str) and date.strip() and ('source_date' not in source or source['source_date'] == date):
                source['source_date'] = source.pop('date')
            else:
                problems.append(f'Source {name}: date is empty, invalid or conflicts with source_date. '
                                'Use one supported source_date, or omit it when unknown; do not guess.')
        unknown = set(source) - allowed
        if unknown:
            problems.append(f'Source {name}: unknown source field(s): {", ".join(sorted(unknown))}. '
                            f'Use only the pinned fields: {", ".join(sorted(allowed))}. '
                            'Correct and resubmit within this job; keep captured evidence unchanged.')
    return result, problems


def repeated(values):
    """A test of whether a value is in `values` more than once, as `values.count(value) > 1`
    says, counted once for the whole list rather than once for each value asked about. A
    value that cannot be counted by hash (a list or an object) is counted as count() does."""
    counted = Counter()
    for value in values:
        try:
            counted[value] += 1
        except TypeError:
            pass

    def more_than_once(value):
        try:
            return counted[value] > 1
        except TypeError:
            return values.count(value) > 1
    return more_than_once


def within(values):
    """A test of whether a value is among `values`, as `value in values` says, without
    reading the list again for each value asked about."""
    hashed, rest = set(), []
    for value in values:
        try:
            hashed.add(value)
        except TypeError:
            rest.append(value)

    def contains(value):
        try:
            if value in hashed:
                return True
        except TypeError:
            pass
        return value in rest
    return contains


def distinct(values):
    """Whether values are all different, as JavaScript's Set counts strings."""
    texts = [value for value in values if isinstance(value, str)]
    return len(texts) == len(values) and len(set(texts)) == len(texts)


def block_problems(value, allowed, kinds, label):
    """Why Harness Research's block() would refuse a statement, as a list of words."""
    if not isinstance(value, dict):
        return [f'{label} must be an object with text, kind and refs']
    said = []
    wrong = wrong_text(value.get('text'), LIMITS['block'])
    if wrong:
        said.append(f'{label} text {wrong}')
    if kinds and value.get('kind') not in kinds:
        said.append(f'{label} kind must be one of ' + ', '.join(kinds))
    said += refs_problems(value.get('refs'), allowed, f'{label} refs', value.get('kind') != 'gap')
    return said


def refs_problems(refs, allowed, label, required=True):
    """Why Harness Research's refs() would refuse a list of references."""
    if not isinstance(refs, list):
        return [f'{label} must be an array']
    if required and not refs:
        return [f'{label} need at least one ID']
    unknown = [ref for ref in refs if not isinstance(ref, str) or ref not in allowed]
    if unknown or not distinct(refs):
        return [f'{label} ' + (f'name unknown ID(s): {", ".join(clipped(ref, 64) for ref in unknown[:5])}'
                               if unknown else 'repeat an ID')]
    return []


def synthesis_problems(value, runtime, shaped=False):
    """What the pinned helper's synthesis save would refuse in findings, sections, brief and
    comparisons, every one at once. The helper stops at the first; these are its rules
    (validateDossier), with the shapes and choices read from the pinned schema. `shaped` when
    the studio has already said which parts are missing or not arrays. Nothing when the pinned
    schema cannot be read."""
    try:
        definitions = pinned(runtime)
        finding_rule, section_rule = definitions['finding'], definitions['section']
        kinds = list((definitions['statement']['properties'].get('kind') or {}).get('enum') or [])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []
    finding_id = (finding_rule.get('properties') or {}).get('id')
    section_id = (section_rule.get('properties') or {}).get('id')
    problems = []
    rows = value.get('sources') if isinstance(value.get('sources'), list) else []
    facts = value.get('facts') if isinstance(value.get('facts'), list) else []
    source_ids = {row.get('id') for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)}
    fact_ids = {fact.get('id') for fact in facts if isinstance(fact, dict) and isinstance(fact.get('id'), str)}
    findings = value.get('findings')
    if not isinstance(findings, list):
        findings = []
        if not shaped:
            problems.append('findings must be an array.')
    named = [finding.get('id') if isinstance(finding, dict) else None for finding in findings]
    finding_ids = {ident for ident in named if isinstance(ident, str)}
    named_twice = repeated(named)
    for index, finding in enumerate(findings):
        ident = named[index]
        name = ident if isinstance(ident, str) and ident else f'number {index + 1}'
        if not isinstance(finding, dict):
            problems.append(f'Finding {name}: return it as an object.')
            continue
        said = []
        if not identifier(ident, finding_id or {'pattern': ID_PATTERN}):
            said.append('id must be lowercase letters, digits and hyphens (at most 64)')
        elif named_twice(ident):
            said.append('another finding has the same id')
        elif ident in source_ids or ident in fact_ids:
            said.append('its id is also a source or fact id; give it its own')
        wrong = wrong_text(finding.get('title'))
        if wrong:
            said.append(f'title {wrong}')
        said += block_problems(finding.get('summary'), fact_ids, kinds, 'summary')
        if isinstance(finding.get('summary'), dict) and finding['summary'].get('kind') == 'gap':
            said.append('its summary is a gap: a summary needs evidence; put unknowns in gaps')
        said += refs_problems(finding.get('support'), fact_ids, 'support')
        said += refs_problems(finding.get('counter'), fact_ids, 'counter', False)
        for group in ('implications', 'conditions', 'gaps'):
            blocks = finding.get(group)
            if not isinstance(blocks, list):
                said.append(f'{group} must be an array (it may be empty)')
                continue
            for number, block in enumerate(blocks, start=1):
                said += block_problems(block, fact_ids, kinds, f'{group} {number}')
        if said:
            problems.append(f'Finding {name}: ' + '; '.join(said) + '.')
    evidence = fact_ids | finding_ids
    parts = [('Report', 'sections', value.get('sections'), True)]
    if 'brief' in value:
        parts.append(('Brief', 'brief', value.get('brief'), True))
    for label, key, sections, needed in parts:
        if not isinstance(sections, list):
            if not shaped:
                problems.append(f'{key} must be an array.')
            continue
        if not sections:
            if not shaped:
                problems.append('At least one report section is required.' if key == 'sections'
                                else 'The brief needs at least one section.')
            continue
        ids = [section.get('id') if isinstance(section, dict) else None for section in sections]
        ids_twice = repeated(ids)
        for index, section in enumerate(sections):
            ident = ids[index]
            name = f'{label} section ' + (ident if isinstance(ident, str) and ident else f'number {index + 1}')
            if not isinstance(section, dict):
                problems.append(f'{name}: return it as an object.')
                continue
            said = []
            if not identifier(ident, section_id or {'pattern': ID_PATTERN}):
                said.append('id must be lowercase letters, digits and hyphens (at most 64)')
            elif ids_twice(ident):
                said.append(f'another {label.lower()} section has the same id')
            wrong = wrong_text(section.get('title'))
            if wrong:
                said.append(f'title {wrong}')
            blocks = section.get('blocks')
            if not isinstance(blocks, list) or not blocks:
                said.append('blocks must be a nonempty array')
            else:
                for number, block in enumerate(blocks, start=1):
                    said += block_problems(block, evidence, kinds, f'block {number}')
            if said:
                problems.append(f'{name}: ' + '; '.join(said) + '.')
    raw = value.get('comparisons')
    comparisons = [] if raw is None or raw is False or raw == '' or (
        isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw == 0) else raw
    if not isinstance(comparisons, list):
        problems.append('comparisons must be an array, or left out.')
        comparisons = []
    for index, comparison in enumerate(comparisons, start=1):
        name = f'Comparison {index}'
        if not isinstance(comparison, dict):
            problems.append(f'{name}: return it as an object.')
            continue
        said = []
        wrong = wrong_text(comparison.get('title'))
        if wrong:
            said.append(f'title {wrong}')
        subjects = comparison.get('subjects')
        if not isinstance(subjects, list):
            said.append('subjects must be an array')
            subjects = None
        elif len(subjects) < 2 or not distinct(subjects) or any(wrong_text(s) for s in subjects):
            said.append('subjects must be at least two distinct, nonempty names')
        among = within(subjects) if subjects is not None else None
        rows_ = comparison.get('rows')
        if not isinstance(rows_, list):
            said.append('rows must be an array')
            rows_ = []
        criteria = set()   # each criterion so far that is text: only text is asked about
        for number, row in enumerate(rows_, start=1):
            if not isinstance(row, dict):
                said.append(f'row {number} must be an object')
                continue
            criterion = row.get('criterion')
            wrong = wrong_text(criterion)
            if wrong:
                said.append(f'row {number} criterion {wrong}')
            elif criterion in criteria:   # text, as wrong_text said
                said.append(f'row {number} repeats the criterion {clipped(criterion, 60)!r}')
            if isinstance(criterion, str):
                criteria.add(criterion)
            cells = row.get('cells')
            if not isinstance(cells, list):
                said.append(f'row {number} cells must be an array')
                continue
            named_cells = [cell.get('subject') if isinstance(cell, dict) else None for cell in cells]
            if subjects is not None and (len(cells) != len(subjects) or not distinct(named_cells)
                                         or any(not among(subject) for subject in named_cells)):
                said.append(f'row {number} needs exactly one cell per subject, naming it')
            for place_, cell in enumerate(cells, start=1):
                if not isinstance(cell, dict):
                    said.append(f'row {number} cell {place_} must be an object')
                    continue
                wrong = wrong_text(cell.get('text'), LIMITS['cell'])
                if wrong:
                    said.append(f'row {number} cell {place_} text {wrong}')
                said += refs_problems(cell.get('refs'), fact_ids, f'row {number} cell {place_} refs')
        if said:
            problems.append(f'{name}: ' + '; '.join(said) + '.')
    return problems


def review_problems(review, template, runtime=None):
    """What the pinned helper's validateReview would refuse in an independent review, every
    one at once, checked against the review_template the reviewer was given. The helper stops
    at the first; these are all of its rules except the reviewer's identity and stale evidence,
    which the studio controls, with the choices read from the pinned schema."""
    try:
        definition = pinned_schema(runtime)['$defs']['review']['properties'] if runtime else {}
    except (OSError, ValueError, KeyError, TypeError):
        definition = {}

    def choices(group, field, fallback):
        rule = definition.get(group) or {}
        rule = (rule.get('items') or rule) if group != 'assessment' else rule
        found = ((rule.get('properties') or {}).get(field) or {}).get('enum')
        return list(found) if isinstance(found, list) else list(fallback)

    if not isinstance(review, dict):
        return ['Return the review as one JSON object, filled in from review_template.']
    problems = []
    if review.get('schema') != 2:
        problems.append('Set "schema": 2.')
    if review.get('digest') != template.get('digest'):
        problems.append(f"Set digest to {template.get('digest')!r}, exactly as review_template gives it.")
    expected = [item for item in template.get('originals') or () if isinstance(item, dict)]
    originals = review.get('originals')
    if not isinstance(originals, list):
        problems.append('originals must be an array, one entry for each source in review_template.')
    else:
        given = [item.get('source') if isinstance(item, dict) else None for item in originals]
        wanted = [item.get('source') for item in expected]
        if len(originals) != len(wanted) or not distinct(given) or set(given) != set(wanted):
            problems.append(f'originals must hold exactly one entry for each of the {len(wanted)} '
                            'source(s) in review_template: ' + ', '.join(map(str, wanted[:40])) + '.')
        for item in expected:
            found = next((entry for entry in originals if isinstance(entry, dict)
                          and entry.get('source') == item.get('source')), None)
            if found is None:
                continue
            name = item.get('source')
            if found.get('sha256') != item.get('sha256') or (
                    'original_sha256' in item and found.get('original_sha256') != item['original_sha256']):
                problems.append(f'Original {name}: copy sha256' + (' and original_sha256' if 'original_sha256' in item
                                                                    else '') + ' exactly from review_template.')
            if not isinstance(found.get('read_original'), bool):
                problems.append(f'Original {name}: set read_original to true or false.')
            elif found['read_original'] is False and wrong_text(found.get('access_error')):
                problems.append(f'Original {name}: read_original is false, so give access_error: what '
                                'the tool answered.')
    for group in ('facts', 'findings', 'prose'):
        items, wanted = review.get(group), [item.get('id') for item in template.get(group) or ()
                                            if isinstance(item, dict)]
        if not isinstance(items, list):
            problems.append(f'{group} must be an array, one entry for each in review_template.')
            continue
        given = [item.get('id') if isinstance(item, dict) else None for item in items]
        if len(items) != len(wanted) or not distinct(given) or set(given) != set(wanted):
            missing = [ident for ident in wanted if ident not in given]
            problems.append(f'{group} must hold exactly one entry for each of the {len(wanted)} in '
                            'review_template' + (', and is missing ' + ', '.join(map(str, missing[:10]))
                                                 if missing else '') + '.')
        verdicts = choices(group, 'verdict', ('supported', 'unsupported', 'narrow'))
        unjudged, unexplained = [], []
        for ident in wanted:
            found = next((item for item in items if isinstance(item, dict) and item.get('id') == ident), None)
            if found is None:
                continue
            if found.get('verdict') not in verdicts:
                unjudged.append(ident)
            if wrong_text(found.get('note'), LIMITS['note']):
                unexplained.append(ident)
        if unjudged:
            problems.append(f'{group}: set verdict to one of {", ".join(verdicts)} for '
                            f'{len(unjudged)} item(s), such as ' + ', '.join(map(str, unjudged[:5])) + '.')
        if unexplained:
            problems.append(f'{group}: give a note explaining the verdict for {len(unexplained)} '
                            'item(s), such as ' + ', '.join(map(str, unexplained[:5])) + '.')
    assessment = review.get('assessment') if isinstance(review.get('assessment'), dict) else {}
    for field, fallback in (('coverage', ('accurate', 'needs-revision')),
                            ('usefulness', ('adequate', 'needs-revision'))):
        allowed = choices('assessment', field, fallback)
        if assessment.get(field) not in allowed:
            problems.append(f'assessment.{field} must be one of {", ".join(allowed)}.')
    if wrong_text(assessment.get('note'), LIMITS['note']):
        problems.append('assessment.note must explain the assessment.')
    return problems


# Harness Research 1.6.0's review units (studio_core.research_units): one reviewer answers for
# one unit of a saved dossier, in the answer its template gives.
REVIEW_UNITS = 'harness-review-units-v1'
UNIT_FIELDS = ('schema', 'protocol', 'plan', 'digest', 'unit', 'attempt', 'reviewer',
               'originals', 'facts', 'findings', 'prose', 'assessment')


def unit_review(template):
    """Whether a review template is one review unit's, not the whole dossier's."""
    return isinstance(template, dict) and template.get('protocol') == REVIEW_UNITS


def unit_problems(answer, template, runtime=None):
    """What Harness Research would refuse in one review unit's answer, every one at once,
    checked against the unit's template: the fields that bind it to its plan, digest, unit,
    attempt and reviewer, exactly what the unit owns, each once, and the whole-dossier
    assessment on the final unit only. The per-item rules are review_problems'."""
    if not isinstance(answer, dict):
        return ['Return the unit answer as one JSON object, filled in from review_template.']
    problems = []
    for key in UNIT_FIELDS[:7]:
        if answer.get(key) != template.get(key):
            problems.append(f'Set {key} to {template.get(key)!r}, exactly as review_template gives it.')
    extra = sorted(str(key) for key in answer if key not in UNIT_FIELDS)
    if extra:
        problems.append('Leave out ' + ', '.join(extra[:10]) + ': a unit answer holds only what '
                        'review_template holds.')
    final = 'assessment' in template
    if not final and 'assessment' in answer:
        problems.append('Leave out assessment: only the final unit answers the whole-dossier assessment.')
    # The items, as a single review's are checked; a content unit has no assessment to check.
    stand_in = {'coverage': 'accurate', 'usefulness': 'adequate', 'note': 'Not part of this unit.'}
    problems += review_problems({**answer, 'schema': 2, 'digest': template.get('digest'),
                                 'assessment': answer.get('assessment') if final else stand_in},
                                {**template, 'schema': 2}, runtime)
    return problems


def citation_sources(value, captures):
    """Resolve only exact job handles to a unique, verified dossier source identity.

    The worker's s1 handle and its own source-a ID may describe the same saved file.
    This bridge changes IDs only, never quotations or evidence. Unknown, ambiguous,
    unsaved or mismatched sources must be corrected by the author; the pinned helper
    still validates every quote and the independent reviewer still checks support.
    """
    result = copy.deepcopy(value)
    rows = result.get('sources')
    sources = [s for s in rows if isinstance(s, dict)] if isinstance(rows, list) else []
    ids = {s['id'] for s in sources if isinstance(s.get('id'), str) and s['id']}
    known = ', '.join(repr(name[:64]) for name in sorted(ids)[:40]) or 'none'
    handles = {}
    for capture in captures:
        handle = capture.get('id')
        if isinstance(handle, str) and handle:
            handles.setdefault(handle, []).append(capture)
    problems, matched = [], 0
    facts = result.get('facts')
    for fact in facts if isinstance(facts, list) else []:
        if not isinstance(fact, dict) or not isinstance(fact.get('citations'), list):
            continue  # The helper diagnoses schema errors, rather than this ID bridge.
        for index, citation in enumerate(fact['citations']):
            if not isinstance(citation, dict):
                continue
            ref = citation.get('source')
            if isinstance(ref, str) and ref in ids:
                continue
            found = handles.get(ref, []) if isinstance(ref, str) else []
            candidates = []
            if len(found) == 1:
                capture = found[0]
                permission = capture.get('permission') or (
                    'selected' if capture.get('offered', True) else 'public')
                candidates = [s for s in sources if isinstance(s.get('id'), str)
                              and s['id'] in ids
                              and s.get('file') == capture.get('file')
                              and s.get('file')
                              and s.get('origin') == capture.get('origin', capture.get('url'))
                              and s.get('permission') == permission]
            if len(candidates) == 1:
                citation['source'] = candidates[0]['id']
                matched += 1
            elif len(problems) < 20:
                label = repr(str(fact.get('id', '?'))[:64])
                missing = repr(ref[:100]) if isinstance(ref, str) else repr(ref)[:100]
                problems.append(f'facts[{label}].citations[{index}].source {missing} does not '
                                f'identify one dossier source. Use sources[].id exactly. '
                                f'Available source IDs: {known}. Do not guess from a quote '
                                'or invent a source; correct the citation and resubmit the dossier.')
    return result, problems, matched


def uncaptured(sources, captures):
    """Why sources a dossier cites differ from what its job saved. The parent refuses the same
    after the job; saying it while the author can still correct it keeps the research step."""
    saved = {entry['file']: entry for entry in captures if entry.get('file')}
    listed = ', '.join(sorted(saved)[:40]) or 'none yet'
    problems = []
    for source in sources:
        name = source.get('file') if isinstance(source, dict) else None
        entry = saved.get(name) if isinstance(name, str) else None
        if entry is None:
            problems.append(f'Source file {name!r} is not one this job saved. Save a page with '
                            'save_source first, then copy its "Capture file" exactly. Saved '
                            f'files: {listed}.')
            continue
        origin = entry.get('origin', entry.get('url'))
        ident = source.get('id')
        label = f'{ident} ({name})' if isinstance(ident, str) and ident and ident != name else name
        if source.get('origin') != origin:
            problems.append(f'Source {label}: copy its origin exactly as {origin!r}.')
        permission = permission_of(entry)
        if source.get('permission') != permission:
            problems.append(f'Source {label}: its permission is {permission!r}.')
    return problems
