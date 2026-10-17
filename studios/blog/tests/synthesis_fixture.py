"""Synthetic dossier and review; never evidence about real products."""

import copy

TEXT = 'Complete synthetic source context. More than one instance keeps capacity. Health checks start the next batch. This is a fictional test, not a product claim.'


def dossier(
    worker, file='sources/source.txt', origin='https://example.invalid/docs', permission='public'
):
    return {
        'schema': 2,
        'topic': 'Synthetic restart',
        'audience': 'Operators',
        'purpose': 'Teach a fictional example',
        'scope': 'Synthetic only',
        'source_mode': permission,
        'sources': [
            {
                'id': 'source-a',
                'file': file,
                'origin': origin,
                'title': 'Synthetic source',
                'publisher': 'Synthetic publisher',
                'permission': permission,
                'context': 'full',
            }
        ],
        'facts': [
            {
                'id': 'fact-a',
                'statement': 'More than one instance keeps capacity.',
                'author': worker,
                'citations': [
                    {'source': 'source-a', 'quote': 'More than one instance keeps capacity.'}
                ],
            }
        ],
        'findings': [
            {
                'id': name,
                'title': 'A conditional choice',
                'summary': {
                    'text': 'More than one instance keeps capacity.',
                    'refs': ['fact-a'],
                    'kind': 'summary',
                },
                'support': ['fact-a'],
                'counter': [],
                'implications': [],
                'conditions': [
                    {
                        'text': 'Only within this synthetic example.',
                        'refs': ['fact-a'],
                        'kind': 'inference',
                    }
                ],
                'gaps': [],
            }
            for name in ('instance-min', 'health-checks')
        ],
        'sections': [
            {
                'id': 'explain',
                'title': 'Explanation',
                'blocks': [
                    {
                        'text': 'More than one instance keeps capacity.',
                        'refs': ['fact-a'],
                        'kind': 'summary',
                    }
                ],
            }
        ],
        'brief': [
            {
                'id': 'teaching',
                'title': 'What to explain first',
                'blocks': [
                    {
                        'text': 'Use the synthetic example within its stated bounds.',
                        'refs': ['instance-min'],
                        'kind': 'recommendation',
                    }
                ],
            }
        ],
    }


def review(template, accepted=True):
    result = copy.deepcopy(template)
    for source in result['originals']:
        source['read_original'] = True
    for group in ('facts', 'findings', 'prose'):
        for item in result[group]:
            item.update(
                verdict='supported' if accepted else 'narrow',
                note='Synthetic independent invocation inspected the saved context and scope.',
            )
    result['assessment'] = {
        'coverage': 'accurate',
        'usefulness': 'adequate',
        'note': 'Explicit synthetic scope and usable brief.',
    }
    return result
