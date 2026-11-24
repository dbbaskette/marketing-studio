"""The pinned Harness Research synthesis schema, and the outlines said from it: what a
source, a synthesis and a review are to hold, and the text bounds the helper keeps.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
import json
from pathlib import Path
import re
import threading
import unicodedata


# The task's own fields. The caller owns them, so generated prose cannot change them.
TASK_FIELDS = ('topic', 'audience', 'purpose', 'scope', 'source_mode')


# What the pinned helper bounds that its schema does not state: the length of each text it
# reads, which Harness Research's text() caps at 4000 characters unless named here, and what
# JavaScript's trim() treats as blank (JS_SPACE). These come from the helper's code, not its
# schema, and were checked against Harness Research LIMITS_VERIFIED_WITH. A re-pin to another
# version fails tests/test_research_packet_problems.py until the gated parity tests
# (STUDIO_TEST_RESEARCH_RUNTIME) are run against it and this is updated.
LIMITS_VERIFIED_WITH = '1.5.1'
TEXT_LIMIT = 4000
LIMITS = {'statement': 10000, 'quote': 30000}
# Fields the studio knows and checks against its own captures: an investigator copies them.
HOST_FIELDS = ('id', 'file', 'origin', 'permission', 'original_file')
# Optional fields Harness Research checks whenever they are present, and only then.
WHEN_PRESENT = {'source': ('source_date', 'accessed_at', 'version'), 'citation': ('locator',)}
# What a field an investigator fills in means, in the studio's words. A field the pinned
# schema adds later is still listed, as required or optional, without them.
MEANING = {
    'title': "The source's own title. The outline gives one for each source the studio offered: "
             'keep it unless the source names itself otherwise.',
    'publisher': 'Who published the source, as the source itself shows it: an organisation, team '
                 'or author.',
    'context': 'full when the capture holds the whole source, or all of it that matters here; '
               'partial when part of it is missing or cut short.',
    'context_note': 'Say specifically what part of the source is missing.',
    'source_date': "The source's own publication or revision date, copied as the source states "
                   'it. Leave it out when the source states none: never guess a date.',
    'accessed_at': 'When the source was read, only when a tool told you. Leave it out otherwise: '
                   'never guess a date.',
    'version': 'A version the source itself names, such as a release number. Leave it out when it '
               'names none.',
}
UNREADABLE = 'The pinned Harness Research source metadata contract could not be read.'


OUTLINED = ('Build each source you return from its source_outline entry: copy id, file, origin '
            'and permission exactly, keep its title, and add the fields source_outline.fill_in '
            'names; use no other fields. Any source saved during this job is built the same way '
            'from what its tool returned (its ID, Capture file and Origin), with permission '
            'public. Copy every quote character for character from the capture it cites.')
GIVEN = 'These are all the sources the studio gave you.'
KEPT = ('These are the sources your previous draft cited, which this round is given: cite only '
        'these, or a source saved during this job.')
# What JavaScript's trim() removes: Harness Research refuses text that is only these.
JS_SPACE = frozenset('\t\n\v\f\r\ufeff\u2028\u2029')


_SCHEMAS: dict = {}            # (path, mtime_ns, size) -> the parsed schema; read-only
_SCHEMAS_HELD = threading.Lock()


def _schema(runtime):
    """The pinned Harness Research synthesis schema, parsed once for each version of its
    file: kept by its path and its (modification time, size), so a changed or replaced file
    is read again. What is returned is shared and never changed by its callers. A file that
    cannot be read or parsed raises as reading it always did."""
    path = Path(runtime) / 'references/synthesis.schema.json'
    found = path.stat()
    key = (str(path.resolve()), found.st_mtime_ns, found.st_size)
    with _SCHEMAS_HELD:
        kept = _SCHEMAS.get(key)
    if kept is None:
        kept = json.loads(path.read_text())
        with _SCHEMAS_HELD:
            if len(_SCHEMAS) >= 16:
                _SCHEMAS.clear()
            _SCHEMAS[key] = kept
    return kept


def pinned(runtime):
    """The definitions of the pinned Harness Research synthesis schema."""
    return _schema(runtime)['$defs']


def conditions(definition):
    """{field: [(other field, value), ...]}: what a schema definition requires only when another
    field has a value, from its allOf if/then rules."""
    found = {}
    for rule in definition.get('allOf') or ():
        if not isinstance(rule, dict):
            continue
        tests = (rule.get('if') or {}).get('properties') or {}
        for field in (rule.get('then') or {}).get('required') or ():
            for other, test in tests.items():
                if isinstance(test, dict) and 'const' in test:
                    found.setdefault(field, []).append((other, test['const']))
    return found


def permission_of(capture):
    """A capture's permission, as the studio's checks read it."""
    return capture.get('permission') or ('selected' if capture.get('offered', True) else 'public')


def js_blank(value):
    """Whether a text is empty once JavaScript's trim() has removed what it removes."""
    return all(c in JS_SPACE or unicodedata.category(c) == 'Zs' for c in value)


def source_outline(sources, runtime, given=GIVEN):
    """Every source a job is given, as the investigator should return it: the fields the studio
    knows, filled in, and the fields it must add, each said from the pinned schema so the list
    cannot drift from Harness Research. Sources are numbered s1, s2 … in the order given, as the
    studio's tools number them. None when the pinned schema cannot be read."""
    try:
        definition = pinned(runtime)['source']
        rules = definition['properties']
        fields = list(rules)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    required, when = set(definition.get('required') or ()), conditions(definition)
    entries = []
    for number, source in enumerate(sources, start=1):
        known = {'id': f's{number}', 'file': source.get('file'),
                 'origin': source.get('origin', source.get('url')),
                 'permission': permission_of(source), 'title': source.get('title')}
        entries.append({key: known[key] for key in [*fields, *known]
                        if key in known and known[key] and key in rules})
    fill = {}
    for field in fields:
        if field in HOST_FIELDS:
            continue
        rule = rules[field] if isinstance(rules[field], dict) else {}
        said = ('Required.' if field in required else
                ' '.join(f'Required when {other} is {value}.' for other, value in when[field])
                if field in when else 'Optional.')
        if isinstance(rule.get('enum'), list):
            said += ' One of ' + ', '.join(map(str, rule['enum'])) + '.'
        if field in MEANING:
            said += ' ' + MEANING[field]
        fill[field] = said
    note = given + ' ' + OUTLINED + f' Each text field holds 1 to {TEXT_LIMIT:,} characters.'
    if 'original_file' in rules:
        note += ' The studio sets original_file; leave it out.'
    return {'note': note, 'fields': fields, 'fill_in': fill, 'sources': entries}


def js_length(value):
    """A text's length as JavaScript counts it, in UTF-16 code units."""
    return len(value.encode('utf-16-le', 'surrogatepass')) // 2


def wrong_text(value, limit=TEXT_LIMIT):
    """Why Harness Research's text() would refuse a value, or None when it would accept it."""
    if not isinstance(value, str):
        return 'is missing' if value is None else 'must be text'
    if js_blank(value):
        return 'is empty'
    if js_length(value) > limit:
        return f'is longer than {limit:,} characters'
    return None


def identifier(value, rule):
    """Whether a value matches the pattern a schema rule gives an ID, as the helper checks it."""
    pattern = (rule or {}).get('pattern') if isinstance(rule, dict) else None
    if not pattern:
        return True
    try:
        return isinstance(value, str) and re.fullmatch(pattern.removeprefix('^').removesuffix('$'),
                                                       value) is not None
    except re.error:
        return True


# The synthesis and review rules Harness Research enforces beyond its schema, in the studio's
# words, beside the shapes read from that schema. synthesis_problems and review_problems check
# each of them.
SYNTHESIS_RULES = (
    'A block of kind gap may have empty refs; every other block needs at least one ref. A '
    "finding's summary is never a gap.",
    "A finding's support, counter, and the refs of its summary, implications, conditions and gaps "
    'name fact IDs from the evidence; so do comparison cell refs. Report and brief block refs '
    'name fact or finding IDs. No refs list repeats an ID.',
    'Finding IDs are distinct from each other and from every source and fact ID. Section IDs are '
    'distinct within sections, and brief section IDs within the brief.',
    'Each comparison has at least two distinct subjects. Each row has a distinct criterion and '
    'exactly one cell per subject, naming it.',
    'Text holds at most 4,000 characters for a title, subject or criterion, 30,000 for a block '
    'and 10,000 for a comparison cell.',
)
SYNTHESIZED = ('synthesis_outline gives the exact shape of what you return, from the pinned '
               'Harness Research schema: build it from that outline and its rules, and check '
               'every reference against the evidence IDs before you hand it back.')
REVIEW_RULES = (
    'Start from review_template and keep its digest, each original\'s sha256 (and '
    'original_sha256 when it has one), and every fact, finding and prose ID, exactly once each.',
    'Give every item a verdict and a note that explains it, including supported ones: an empty '
    'note is refused.',
    'Set read_original true only when you read that source (and its original, when it has one); '
    'when false, give access_error: what the tool answered.',
)
REVIEWED = ('review_outline says what each field of the review takes, from the pinned Harness '
            'Research schema. A refusal lists everything to correct at once.')


LIMITS.update(block=30000, cell=10000, note=20000)
ID_PATTERN = '^[a-z0-9][a-z0-9-]{0,63}$'


def pinned_schema(runtime):
    """The whole pinned Harness Research synthesis schema."""
    return _schema(runtime)


def described(rule):
    """What a schema rule asks for, in words, or a mapping of an inline object's fields."""
    if not isinstance(rule, dict):
        return 'any value'
    if '$ref' in rule:
        name = str(rule['$ref']).rsplit('/', 1)[-1]
        return f'a {name}, shaped as shapes.{name}'
    if 'const' in rule:
        return 'exactly ' + json.dumps(rule['const'])
    if isinstance(rule.get('enum'), list):
        return 'one of ' + ', '.join(map(str, rule['enum']))
    kind = rule.get('type')
    if kind == 'string':
        pattern = rule.get('pattern')
        if pattern == ID_PATTERN:
            return 'an ID: lowercase letters, digits and hyphens, at most 64'
        if pattern == '^[a-f0-9]{64}$':
            return 'a SHA-256 digest, copied exactly'
        return 'nonempty text' if rule.get('minLength') else 'text'
    if kind == 'boolean':
        return 'true or false'
    if kind == 'array':
        least = rule.get('minItems')
        items = described(rule.get('items'))
        said = 'an array' + (f' of at least {least}' if least else '')
        if isinstance(items, dict):
            return {'is': said + ' objects, each:' if least else said + ' of objects, each:',
                    'each': items}
        return said + ', each ' + items + (', with no repeats' if rule.get('uniqueItems') else '')
    if kind == 'object' and isinstance(rule.get('properties'), dict):
        return fields(rule)
    return 'any value'


def fields(definition):
    """{field: what it takes}, for each field of a schema definition, required ones first said."""
    required, when = set(definition.get('required') or ()), conditions(definition)
    shaped = {}
    for name, rule in (definition.get('properties') or {}).items():
        said = described(rule)
        said = said[:1].upper() + said[1:] if isinstance(said, str) else said
        lead = ('Required.' if name in required else
                ' '.join(f'Required when {other} is {json.dumps(value)}.' for other, value in when[name])
                if name in when else 'Optional.')
        shaped[name] = {'is': lead + ' ' + said['is'][:1].upper() + said['is'][1:], 'each': said['each']} \
            if isinstance(said, dict) and 'each' in said else \
            {'is': lead + ' An object:', 'fields': said} if isinstance(said, dict) else lead + ' ' + said
    return shaped


def synthesis_outline(runtime, keys=('findings', 'sections', 'brief', 'comparisons'),
                      required=('findings', 'sections', 'brief')):
    """The exact shape of a synthesis: each part it returns, the shape of a finding, a section,
    a statement (a block) and a comparison, read from the pinned schema, and the rules
    Harness Research enforces beyond it. `required` names the parts the studio requires to be
    nonempty. None when the pinned schema cannot be read."""
    try:
        schema = pinned_schema(runtime)
        top, definitions = schema['properties'], schema['$defs']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    parts, needed = {}, set(schema.get('required') or ())
    for key in keys:
        if key in top:
            said = described(top[key])
            said = said if isinstance(said, str) else said.get('is', '')
            parts[key] = ('Required, with at least one item. ' if key in required else
                          'Required. ' if key in needed else 'Optional. ') + said[:1].upper() + said[1:]
    shapes = {name: fields(definitions[name]) for name in ('finding', 'section', 'statement', 'comparison')
              if isinstance(definitions.get(name), dict)}
    return {'note': SYNTHESIZED, 'return': parts, 'shapes': shapes, 'rules': list(SYNTHESIS_RULES)}


def review_outline(runtime):
    """What each field of an independent review takes, from the pinned schema, and the rules
    Harness Research enforces beyond it. None when the pinned schema cannot be read."""
    try:
        definition = pinned_schema(runtime)['$defs']['review']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {'note': REVIEWED, 'fields': fields(definition), 'rules': list(REVIEW_RULES)}
