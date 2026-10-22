"""Synthetic dossier and review; never evidence about real products."""
import copy

TEXT = 'Complete synthetic source context. More than one instance keeps capacity. Health checks start the next batch. This is a fictional test, not a product claim.'

def dossier(worker, file='sources/source.txt', origin='https://example.invalid/docs', permission='public'):
    return {'schema': 2, 'topic': 'Synthetic restart', 'audience': 'Operators',
            'purpose': 'Teach a fictional example', 'scope': 'Synthetic only', 'source_mode': permission,
            'sources': [{'id': 'source-a', 'file': file, 'origin': origin, 'title': 'Synthetic source',
                         'publisher': 'Synthetic publisher', 'permission': permission, 'context': 'full'}],
            'facts': [{'id': 'fact-a', 'statement': 'More than one instance keeps capacity.',
                       'author': worker, 'citations': [{'source': 'source-a', 'quote': 'More than one instance keeps capacity.'}]}],
            'findings': [{'id': name, 'title': 'A conditional choice',
                          'summary': {'text': 'More than one instance keeps capacity.', 'refs': ['fact-a'], 'kind': 'summary'},
                          'support': ['fact-a'], 'counter': [], 'implications': [],
                          'conditions': [{'text': 'Only within this synthetic example.', 'refs': ['fact-a'], 'kind': 'inference'}],
                          'gaps': []} for name in ('instance-min', 'health-checks')],
            'sections': [{'id': 'explain', 'title': 'Explanation', 'blocks': [
                {'text': 'More than one instance keeps capacity.', 'refs': ['fact-a'], 'kind': 'summary'}]}],
            'brief': [{'id': 'teaching', 'title': 'What to explain first', 'blocks': [
                {'text': 'Use the synthetic example within its stated bounds.', 'refs': ['instance-min'], 'kind': 'recommendation'}]}]}

def review(template, accepted=True):
    result = copy.deepcopy(template)
    for source in result['originals']:
        source['read_original'] = True
    for group in ('facts', 'findings', 'prose'):
        for item in result[group]:
            item.update(verdict='supported' if accepted else 'narrow', note='Synthetic independent invocation inspected the saved context and scope.')
    result['assessment'] = {'coverage': 'accurate', 'usefulness': 'adequate', 'note': 'Explicit synthetic scope and usable brief.'}
    return result


import hashlib
import json
from studio_core import research_contract as contract


def published_bundle(folder, findings=(), review=None, sources=(), sections=(), brief=(), evidence=()):
    folder.mkdir(parents=True, exist_ok=True)
    facts = dict(owner=contract.OWNER, schema=2, digest='synthetic-digest', status='complete',
                 review=review or dict(accepted=True, digest='synthetic-digest', originals=[],
                                      assessment=dict(coverage='accurate', usefulness='adequate', note=' An honest\n account. ')),
                 facts=list(evidence), findings=list(findings), sources=list(sources), sections=list(sections), brief=list(brief))
    for name, text in [('brief.md', '# Prioritized handoff\n'), ('report.md', '# Report\n'),
                       ('evidence.md', '# Evidence\n'), ('facts.json', json.dumps(facts))]:
        (folder / name).write_text(text)
    manifest = {key: facts[key] for key in ('owner', 'schema', 'digest', 'status')}
    manifest['artifacts'] = [dict(file=name, sha256=hashlib.sha256((folder / name).read_bytes()).hexdigest())
                             for name in sorted(contract.ARTIFACTS)]
    (folder / 'output.json').write_text(json.dumps(manifest))
    return facts, manifest



def research_stop(folder):
    """A complete accepted bundle for the research-stop journeys."""
    value = dossier('synthetic-author')
    value['findings'][0].update(id='instance-min--capacity', title='Capacity condition', gaps=[dict(text='Unknown range.')])
    value['findings'][1].update(id='other', title='Another condition')
    sources = [*value['sources'], dict(id='mine-a', permission='selected'), dict(id='mine-b', permission='selected')]
    sources[0].update(context='partial', context_note='Pages 1 to 4 only.')
    return published_bundle(folder, findings=value['findings'], sources=sources, evidence=value['facts'])
