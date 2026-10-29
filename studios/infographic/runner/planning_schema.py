"""Bounded story-planning output; native evidence and story checks remain authoritative."""

TEXT = {'type': 'string', 'maxLength': 10000}
CONTEXT_TEXT = {'type': 'string', 'maxLength': 1000}
ID = {'type': 'string', 'pattern': '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}


def record(**properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


def array(items, **limits):
    return {'type': 'array', 'items': items, **limits}


PLAN = record(
    facts=array(record(
        id=ID, statement=TEXT, value={'anyOf': [
            {'type': 'string', 'description': 'For qualitative facts copy an exact substring of an evidence quote. Put the paraphrase in statement.'},
            {'type': 'number', 'description': 'A literal numeric source quantity, not a formatted string.'}]},
        unit=TEXT, period=CONTEXT_TEXT, denominator=CONTEXT_TEXT, conditions=CONTEXT_TEXT, uncertainty=CONTEXT_TEXT,
        status={'type': 'string', 'enum': ['supplied']},
        calculation={'anyOf': [{'type': 'null'}, record(
            operator={'type': 'string', 'enum': ['sum', 'difference', 'ratio', 'percent_change']},
            operands=array(ID, minItems=2))]},
        evidence=array(record(source_id=ID, quote=TEXT))), minItems=1, maxItems=12),
    stories=array(record(
        id=ID, headline=TEXT, takeaway=TEXT, rationale=TEXT,
        qualifications=array(TEXT), omissions=array(ID),
        blocks=array(record(
            id=ID, kind={'type': 'string', 'enum': ['comparison', 'process', 'timeline', 'numbers', 'parts', 'concept']},
            title=TEXT, text=TEXT, fact_ids=array(ID, minItems=1), required_ids=array(ID),
            quantitative={'type': 'boolean', 'description': 'True for measured numeric charts; false for descriptive comparisons and component explanations.'},
            illustration={'type': 'boolean'}, illustration_role=TEXT), minItems=1, maxItems=5)),
        minItems=1, maxItems=3))
