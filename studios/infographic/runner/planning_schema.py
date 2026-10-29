"""Bounded story-planning output; native evidence and story checks remain authoritative."""

TEXT = {'type': 'string'}


def record(**properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


def array(items, **limits):
    return {'type': 'array', 'items': items, **limits}


PLAN = record(
    facts=array(record(
        id=TEXT, statement=TEXT, value={'anyOf': [TEXT, {'type': 'number'}]},
        unit=TEXT, period=TEXT, denominator=TEXT, conditions=TEXT, uncertainty=TEXT,
        status={'type': 'string', 'enum': ['supplied']},
        calculation={'anyOf': [{'type': 'null'}, record(
            operator={'type': 'string', 'enum': ['sum', 'difference', 'ratio', 'percent_change']},
            operands=array(TEXT, minItems=2))]},
        evidence=array(record(source_id=TEXT, quote=TEXT))), maxItems=12),
    stories=array(record(
        id=TEXT, headline=TEXT, takeaway=TEXT, rationale=TEXT,
        qualifications=array(TEXT), omissions=array(TEXT),
        blocks=array(record(
            id=TEXT, kind={'type': 'string', 'enum': ['comparison', 'process', 'timeline', 'numbers', 'parts', 'concept']},
            title=TEXT, text=TEXT, fact_ids=array(TEXT, minItems=1), required_ids=array(TEXT),
            illustration={'type': 'boolean'}, illustration_role=TEXT), minItems=1, maxItems=5)),
        minItems=1, maxItems=3))
