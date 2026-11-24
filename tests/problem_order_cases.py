"""Synthetic dossiers with repeated, missing and odd IDs, criteria and subjects, and a
small synthetic synthesis schema, for checking that the problems found in them are said in
the same words and order however they are counted (#513). Never evidence about anything."""
import copy
import json
from pathlib import Path

from synthesis_fixture import TEXT, dossier

ID = {'type': 'string', 'pattern': '^[a-z0-9][a-z0-9-]{0,63}$'}
SCHEMA = {'$defs': {
    'source': {'type': 'object', 'required': ['id', 'file', 'title', 'publisher', 'context'],
               'properties': {'id': ID, 'file': {'type': 'string'}, 'origin': {'type': 'string'},
                              'title': {'type': 'string'}, 'publisher': {'type': 'string'},
                              'permission': {'enum': ['public', 'selected']},
                              'context': {'enum': ['full', 'partial']}}},
    'fact': {'type': 'object', 'required': ['id', 'statement', 'citations'],
             'properties': {'id': ID, 'statement': {'type': 'string'},
                            'author': {'type': 'string'},
                            'citations': {'type': 'array', 'items': {
                                'type': 'object', 'properties': {
                                    'source': {'type': 'string'},
                                    'quote': {'type': 'string'}}}}}},
    'finding': {'type': 'object', 'properties': {'id': ID}},
    'section': {'type': 'object', 'properties': {'id': ID}},
    'statement': {'type': 'object', 'properties': {
        'kind': {'enum': ['summary', 'inference', 'recommendation', 'gap']}}}}}


def runtime(folder: Path) -> Path:
    """A folder holding SCHEMA where Harness Research keeps its synthesis schema."""
    (folder / 'references').mkdir(parents=True, exist_ok=True)
    (folder / 'references' / 'synthesis.schema.json').write_text(json.dumps(SCHEMA))
    return folder


def _findings(v):
    v['findings'] += [copy.deepcopy(v['findings'][0]), {'id': ['not', 'text'], 'title': ''},
                      {'id': {'x': 1}}, 'not an object', {'id': 'fact-a', 'title': 'Clash'}]


def _sections(v):
    v['sections'] += [copy.deepcopy(v['sections'][0]), {'id': ['x']}, {'id': None, 'blocks': []}]
    v['brief'] += [copy.deepcopy(v['brief'][0]), copy.deepcopy(v['brief'][0])]


def _comparisons(v):
    cell = lambda subject, text, refs=('fact-a',): {'subject': subject, 'text': text,  # noqa: E731
                                                     'refs': list(refs)}
    v['comparisons'] = [
        {'title': 'A', 'subjects': ['one', 'two'], 'rows': [
            {'criterion': 'Cost', 'cells': [cell('one', 'Low'), cell('two', 'High')]},
            {'criterion': 'Cost', 'cells': [cell('one', 'x'), cell('three', 'y')]},
            {'criterion': ['odd'], 'cells': []},
            {'criterion': 'Speed', 'cells': [cell(['one'], 'z', ()), cell('two', 'w', ['fact-b'])]},
            {'criterion': 'Speed', 'cells': 'none'}]},
        {'title': 'B', 'subjects': [['one'], {'a': 1}, 'two'], 'rows': [
            {'criterion': 'Fit', 'cells': [cell(['one'], 'a'), cell({'a': 1}, 'b'),
                                           cell('two', 'c')]},
            {'criterion': 'Fit', 'cells': [cell('one', 'a')]}]},
        {'title': 'C', 'subjects': 'one, two', 'rows': []},
        'not an object']


def _sources_facts(v):
    v['sources'] += [copy.deepcopy(v['sources'][0]), {'id': ['s'], 'file': 'x'}, {'id': None}]
    v['facts'] += [copy.deepcopy(v['facts'][0]),
                   {'id': 'source-a', 'statement': 'Clash', 'citations': []},
                   {'id': {'f': 1}, 'citations': 'none'}, 'not an object']


def cases() -> dict:
    """{name: a dossier}: the fixture as it is, and with each kind of repeat, and all."""
    base = dossier('synthesizer-1')
    changes = {'findings': [_findings], 'sections': [_sections],
               'comparisons': [_comparisons], 'sources-facts': [_sources_facts],
               'everything': [_findings, _sections, _comparisons, _sources_facts]}
    found = {'fixture': copy.deepcopy(base)}
    for name, steps in changes.items():
        value = copy.deepcopy(base)
        for step in steps:
            step(value)
        found[name] = value
    return found


def said(contract, folder) -> dict:
    """Every problem `contract` finds in each case, keyed as the expected values are."""
    texts = {'sources/source.txt': TEXT}
    found = {}
    for name, value in cases().items():
        for shaped in (False, True):
            found[f'synthesis {name} shaped={shaped}'] = contract.synthesis_problems(
                value, folder, shaped)
        for mode in (None, 'evidence'):
            problems, sources, facts = contract.packet_problems(value, texts, folder,
                                                                'synthesizer-1', mode)
            found[f'packet {name} mode={mode}'] = [problems, sorted(sources), sorted(facts)]
    return found
