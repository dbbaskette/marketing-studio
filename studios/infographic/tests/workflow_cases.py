"""Synthetic provider-shaped replies, deliberately not pre-normalized native records."""
from copy import deepcopy


def fact(ident, statement, value, quote, **fields):
    return {'id': ident, 'statement': statement, 'value': value, 'unit': '',
            'period': '', 'denominator': '', 'conditions': '', 'uncertainty': '',
            'status': 'supplied', 'calculation': None,
            'evidence': [{'source_id': 'captured', 'quote': quote}], **fields}


def block(kind='concept', refs=None, **fields):
    return {'id': 'b1', 'kind': kind, 'title': 'Supplied explanation',
            'text': 'The queue buffers messages while the router selects destinations.',
            'fact_ids': refs or ['f1', 'f2'], 'required_ids': [], 'quantitative': False,
            'illustration': False, 'illustration_role': '', **fields}


def story(blocks=None, **fields):
    return {'id': 's1', 'headline': 'Different roles in a system',
            'takeaway': 'Buffer messages and select destinations.',
            'rationale': 'Explain only the supplied relationships.',
            'qualifications': [], 'omissions': [], 'blocks': blocks or [block()], **fields}


def case(name):
    source = 'A queue buffers messages. A router selects destinations.'
    facts = [fact('f1', 'Queues decouple senders.', 'Queue-based decoupling', 'A queue buffers messages.'),
             fact('f2', 'Routing directs messages.', 'Destination-based routing', 'A router selects destinations.')]
    proposals = [story()]
    if name in ('comparison', 'components'):
        proposals = [story([block('comparison' if name == 'comparison' else 'parts')])]
    elif name == 'process':
        proposals = [story([block('process', ['f1'], title='1. Buffer', text='The queue buffers messages.'),
                            block('process', ['f2'], id='b2', title='Route', text='The router selects destinations.')])]
    elif name == 'whitespace':
        source = 'A\u00a0queue\nbuffers   messages. A router selects destinations.'
    elif name == 'typography':
        source = '“Queues” buffer messages. A router selects destinations.'
        facts[0]['evidence'][0]['quote'] = '"Queues" buffer messages.'
    elif name == 'timeline':
        source = 'In March, the queue was introduced. In April, routing was added.'
        facts = [fact('f1', 'Queue introduction.', 'Queue launch', 'In March, the queue was introduced.', period='March'),
                 fact('f2', 'Routing introduction.', 'Routing launch', 'In April, routing was added.', period='April')]
        proposals = [story([block('timeline', ['f1'], title='Queue', text='The queue was introduced.'),
                            block('timeline', ['f2'], id='b2', title='Routing', text='Routing was added.')])]
    elif name in ('numeric_strings', 'zeros', 'calculation', 'negative', 'attached_units'):
        one, two = ('0.00', '0.0') if name == 'zeros' else ('12.30', '24.60')
        if name == 'negative': one = '-12'
        unit = 'ms' if name == 'attached_units' else 'requests'
        gap = '' if name == 'attached_units' else ' '
        source = (f'Baseline {one}{gap}{unit}. Comparison {two}{gap}{unit}. Period January. '
                  'Denominator per second. Conditions same benchmark. Uncertainty not reported.')
        context = {'unit': unit, 'period': 'January', 'denominator': 'per second',
                   'conditions': 'same benchmark', 'uncertainty': 'not reported'}
        facts = [fact('f1', 'Baseline', one, f'Baseline {one}{gap}{unit}.', **context),
                 fact('f2', 'Comparison', two, f'Comparison {two}{gap}{unit}.', **context)]
        proposals = [story([block('comparison', quantitative=True, title='Supplied counts',
                                  text='Compare the supplied observations under the same conditions.')],
                          headline='Supplied measurements', takeaway='Keep the measurement context visible.')]
        if name == 'calculation':
            facts[0]['value'], facts[1]['value'] = 12.3, 24.6
            derived = fact('f3', 'Ratio', '2.00', '', unit='unknown',
                           calculation={'operator': 'ratio', 'operands': ['f2', 'f1']})
            derived['evidence'] = []
            facts.append(derived)
            proposals[0]['blocks'] = [block('numbers', ['f3'], quantitative=True, title='Derived ratio',
                                           text='Divide the comparison by the baseline under their shared context.')]
        if name == 'negative':
            proposals[0]['blocks'] = [block('numbers', ['f1'], quantitative=True, title='Supplied balance',
                                           text='Show the supplied balance directly without a proportional bar.')]
    elif name == 'partial':
        facts.append(fact('bad', 'An unsupported claim.', 'Invented wording', 'This sentence is absent.'))
        bad = story([block(refs=['bad'])], id='unsupported')
        proposals.insert(0, bad)
    elif name != 'paraphrase':
        raise ValueError('Unknown synthetic workflow case: ' + name)
    return {'name': name, 'source': source, 'answer': {'facts': facts, 'stories': proposals}}


NAMES = ('paraphrase', 'comparison', 'components', 'process', 'whitespace', 'typography',
         'timeline', 'numeric_strings', 'zeros', 'calculation', 'negative', 'attached_units', 'partial')


def captured_answer(example, ident):
    answer = deepcopy(example['answer'])
    for item in answer['facts']:
        for point in item['evidence']:
            point['source_id'] = ident
    return answer
