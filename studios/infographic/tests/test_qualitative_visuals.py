from copy import deepcopy

from helpers import Isolated
from test_composition import contract
from runner import brand, evidence, scene, sources, stories
from runner.contracts import Invalid, PRESETS
from runner.workspace import Store
from runner.engine import Engine


class QualitativeVisualTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace, data=self.data)
        project = self.store.create('Synthetic architecture')
        source = 'A queue buffers messages. A router selects destinations.'
        project = sources.capture(self.store, project['id'], source.encode(), expected_revision=0)
        captured = project['sources'][0]['id']
        facts = [{'id': key, 'statement': label, 'value': quote, 'unit': '', 'status': 'supplied',
                  'evidence': [{'source_id': captured, 'quote': quote}]}
                 for key, label, quote in [('f1', 'Queue', 'A queue buffers messages.'),
                                           ('f2', 'Router', 'A router selects destinations.')]]
        project = evidence.adopt(self.store, project['id'], evidence.locate(self.store, project, facts), expected_revision=1)
        self.project = brand.adopt(self.store, project['id'], contract(), expected_revision=2)
        self.proposal = {'id': 's1', 'headline': 'Different jobs in the system',
                         'takeaway': 'Queues buffer messages; routers select destinations.',
                         'rationale': 'Explain the supplied roles.', 'qualifications': [], 'omissions': [],
                         'blocks': [{'id': 'b1', 'kind': 'comparison', 'title': 'Two roles',
                           'text': source, 'fact_ids': ['f1', 'f2'], 'required_ids': [],
                           'illustration': False, 'illustration_role': ''}]}

    def plan(self, proposal, preset='a4', project=None):
        p = deepcopy(project or self.project)
        p['brief']['preset'] = preset
        p['stories'] = stories.verify(p, [proposal])
        p['selected_story'] = proposal['id']
        return scene.plan(p)

    def measured(self, mixed=False):
        p = self.store.create('Synthetic measurements')
        raw = ('Baseline 12. Comparison 24. Unit requests. Period January. Denominator per second. '
               'Conditions same test. Uncertainty not reported. A router selects destinations.')
        p = sources.capture(self.store, p['id'], raw.encode(), expected_revision=0)
        facts = [{'id': key, 'statement': label, 'value': value, 'unit': 'requests', 'status': 'supplied',
                  'period': 'January', 'denominator': 'per second', 'conditions': 'same test',
                  'uncertainty': 'not reported', 'evidence': [{'source_id': p['sources'][0]['id'], 'quote': quote}]}
                 for key, label, value, quote in [('f1', 'Baseline', 12, 'Baseline 12'),
                                                 ('f2', 'Comparison', 24, 'Comparison 24')]]
        if mixed:
            facts[1].update(statement='Router', value='A router selects destinations.')
            facts[1]['evidence'][0]['quote'] = facts[1]['value']
        p = evidence.adopt(self.store, p['id'], evidence.locate(self.store, p, facts), expected_revision=1)
        return brand.adopt(self.store, p['id'], contract(), expected_revision=2)

    def test_descriptive_comparisons_and_components_need_no_numeric_measurements(self):
        for kind in ('comparison', 'parts'):
            for explicit in (False, None):
                for preset in PRESETS:
                    with self.subTest(kind=kind, explicit=explicit, preset=preset):
                        proposal = deepcopy(self.proposal)
                        block = proposal['blocks'][0]
                        block['kind'] = kind
                        if explicit is not None:
                            block['quantitative'] = explicit
                        result = self.plan(proposal, preset)
                        self.assertFalse(any(e['kind'] == 'chart' for e in result['elements']))
                        body = next(e for e in result['elements'] if e['id'] == 'b1_text')
                        self.assertEqual(body['text'], block['text'])
                        self.assertEqual(body['fact_ids'], ['f1', 'f2'])
        self.assertEqual(self.store.read(self.project['id']), self.project, 'Planning must not alter saved source facts.')

    def test_number_callouts_and_explicit_quantitative_layouts_still_reject_prose(self):
        for kind in ('numbers', 'comparison', 'parts'):
            with self.subTest(kind=kind):
                proposal = deepcopy(self.proposal)
                proposal['blocks'][0].update(kind=kind, quantitative=True)
                with self.assertRaisesRegex(Invalid, 'numeric source values'):
                    self.plan(proposal)
        proposal['blocks'][0].update(kind='numbers', quantitative=False)
        with self.assertRaisesRegex(Invalid, 'Number callouts'):
            self.plan(proposal)

    def test_mixed_values_need_explicit_qualitative_intent_and_never_gain_a_scale(self):
        p = self.measured(mixed=True)
        for explicit in (None, True):
            proposal = deepcopy(self.proposal)
            proposal['blocks'][0]['text'] = 'The source supplies a measurement and describes a routing function.'
            if explicit is not None:
                proposal['blocks'][0]['quantitative'] = explicit
            with self.assertRaisesRegex(Invalid, 'numeric source values'):
                self.plan(proposal, project=p)
        proposal['blocks'][0]['quantitative'] = False
        result = self.plan(proposal, project=p)
        self.assertFalse(any(e['kind'] == 'chart' for e in result['elements']))

    def test_bad_measurement_context_cannot_be_hidden_in_a_quantitative_layout(self):
        p = self.measured()
        p['facts'][1]['period'] = 'February'
        for kind in ('comparison', 'parts', 'numbers'):
            proposal = deepcopy(self.proposal)
            proposal['blocks'][0]['kind'] = kind
            proposal['blocks'][0]['text'] = 'Baseline and comparison under the supplied measurement context.'
            with self.assertRaisesRegex(Invalid, 'period differs'):
                self.plan(proposal, project=p)
            p['facts'][1]['period'] = 'January'
            self.assertTrue(any(e['kind'] == 'chart' for e in self.plan(proposal, project=p)['elements']))
            p['facts'][1]['period'] = 'February'

    def test_generated_alternatives_keep_valid_stories_without_rerunning_the_assistant(self):
        good = deepcopy(self.proposal)
        bad = deepcopy(self.proposal)
        bad.update(id='bad_numbers')
        bad['blocks'][0].update(kind='numbers', quantitative=True)
        calls = []
        reply = {'facts': self.project['facts'], 'stories': [bad, good]}
        class Assistant:
            def propose(self, *args):
                calls.append('propose')
                return deepcopy(reply)
        engine = Engine(self.store, assistant=Assistant())
        result = engine.propose(self.project['id'], expected_revision=self.project['revision'])
        self.assertEqual([s['id'] for s in result['stories']], ['s1'])
        self.assertEqual(result['facts'], self.project['facts'])
        self.assertIsNone(result['approval'])
        self.assertEqual(calls, ['propose'])
        with self.assertRaisesRegex(Invalid, 'numeric source values'):
            stories.verify(self.project, [bad, good])
        before = self.store.read(self.project['id'])
        reply['stories'] = [bad]
        with self.assertRaisesRegex(Invalid, 'numeric source values'):
            engine.propose(before['id'], expected_revision=before['revision'])
        self.assertEqual(self.store.read(before['id']), before)
        self.assertEqual(calls, ['propose', 'propose'])
