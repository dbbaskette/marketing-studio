"""Bounded authoring outputs; native evidence and page checks remain authoritative."""
from copy import deepcopy
from .visuals import ICONS

TEXT = {'type': 'string', 'maxLength': 10000}
CONTEXT_TEXT = {'type': 'string', 'maxLength': 1000}
ID = {'type': 'string', 'pattern': '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$'}


def record(**properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


def array(items, **limits):
    return {'type': 'array', 'items': items, **limits}


VISUAL = record(
    nodes=array(record(id=ID, label={'type': 'string', 'maxLength': 150},
        caption={'type': 'string', 'maxLength': 300}, icon={'type': 'string', 'enum': list(ICONS)},
        fact_ids=array(ID, minItems=1)), minItems=1, maxItems=4),
    links=array(record(**{'from': ID, 'to': ID, 'label': {'type': 'string', 'maxLength': 100},
                         'fact_ids': array(ID, minItems=1)}), maxItems=6))


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
            illustration={'type': 'boolean'}, illustration_role=TEXT,
            visual={'anyOf': [VISUAL, {'type': 'null'}]}), minItems=1, maxItems=5)),
        minItems=1, maxItems=3))


def planning(brief, sources):
    shape = deepcopy(PLAN)
    story = shape['properties']['stories']
    if brief.get('direction') == 'direct':
        story['maxItems'] = 1
    requirements = [item['id'] for item in brief.get('must_show', [])]
    references = {'type': 'string', 'enum': requirements} if requirements else deepcopy(ID)
    for field in (story['items']['properties']['omissions'],
                  story['items']['properties']['blocks']['items']['properties']['required_ids']):
        field.update(items=deepcopy(references), maxItems=len(requirements))
    story['items']['properties']['omissions']['description'] = 'Only omitted brief.must_show IDs. If there are no must-show items return []. Put optional source exclusions in qualifications.'
    names = [source['id'] for source in sources]
    if names:
        shape['properties']['facts']['items']['properties']['evidence']['items']['properties']['source_id'] = {'type': 'string', 'enum': names}
    return shape


def art_direction(project):
    regions = [region['id'] for region in project['scene'].get('art_regions', [])]
    assets = [asset['id'] for asset in project['assets']]
    return record(style=TEXT, reading_order=TEXT, acceptance=TEXT,
        reference_assets=array({'type': 'string', 'enum': assets} if assets else ID, maxItems=len(assets)),
        objects=array(record(id=ID, region_id={'type': 'string', 'enum': regions},
            count={'type': 'integer', 'minimum': 1, 'maximum': 100},
            description=TEXT, relationships=TEXT, preserve=TEXT), minItems=1, maxItems=1000))


def inspection(context):
    scene = context.get('scene') if isinstance(context.get('scene'), dict) else {}
    regions = sorted({'page', *(e['id'] for e in scene.get('elements', [])),
                      *(r['id'] for r in scene.get('art_regions', []))})
    region = {'type': 'string', 'enum': regions}
    detail = {'type': 'string', 'maxLength': 2000}
    kinds = ['counts', 'relationships', 'crop', 'resolution', 'label_clearance', 'brand', 'factual_implications']
    return record(capability={'type': 'string', 'enum': ['inspected', 'unavailable']},
        observations=array(record(kind={'type': 'string', 'enum': kinds}, region_id=region, text=detail), maxItems=30),
        findings=array(record(region_id=region, blocking={'type': 'boolean'}, message=detail, correction=detail), maxItems=30))
