import ast
import copy
import unittest
from pathlib import Path
from unittest import mock
from test_home import IsolatedHome
from marketing_studio import shared
from studio_core import review_policy as review, preferences


class ReviewPolicyTests(IsolatedHome):
    def test_defaults_legacy_invalid_and_unreadable(self):
        self.assertEqual(review.capture(), {'schema': 1, 'level': 'balanced'})
        self.assertEqual(review.level({}), 'step_by_step')
        for value in ({}, {'schema': True, 'level': 'automatic'}, {'schema': 2, 'level': 'balanced'}, {'schema': 1, 'level': 'all'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review.level({'review_policy': value})
        with mock.patch('studio_core.studios_config.read', return_value=({}, 'Unreadable')):
            self.assertEqual(review.capture()['level'], 'step_by_step')

    def test_save_roundtrip_preserves_other_values_and_rejects_conflicts(self):
        shared.update({'private': {'keep': 7}, 'review': {'level': 'balanced'}})
        before = preferences.visible(shared.read()[0])
        preferences.save(shared, {'review': {'level': 'automatic'}}, before)
        self.assertEqual(shared.read()[0]['private'], {'keep': 7})
        with self.assertRaisesRegex(ValueError, 'Another studio'):
            preferences.save(shared, {'review': {'level': 'step_by_step'}}, before)
        saved = review.capture()
        shared.update({'review': {'level': 'step_by_step'}})
        self.assertEqual(saved['level'], 'automatic')
        for value in (None, {}, {'level': 'all'}, {'level': 'automatic', 'publish': True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                preferences.check({'review': value}, {})

    def test_gate_contract_and_receipt(self):
        for mode, stops in [('balanced', {'gate:outline', 'gate:build'}),
                            ('automatic', {'gate:build'}),
                            ('step_by_step', {'gate:classify', 'gate:research-plan', 'gate:research', 'gate:outline', 'gate:look', 'gate:build'})]:
            run = {'review_policy': {'schema': 1, 'level': mode}}
            for gate in ('gate:classify', 'gate:research-plan', 'gate:research', 'gate:outline', 'gate:look', 'gate:build'):
                self.assertEqual(review.automatic(run, 'presentation', gate), gate not in stops)
        run = {'review_policy': {'schema': 1, 'level': 'balanced'}}
        for gate in ('research-plan', 'research', 'draft', 'review'):
            self.assertTrue(review.automatic(run, 'blog', gate, 'package'))
        self.assertFalse(review.automatic(run, 'blog', 'outline', 'package'))
        self.assertFalse(review.automatic(run, 'blog', 'package', 'package'))
        # Training Studio: Balanced reads the research plan, then the direction and the
        # finished materials together. Automatic draft reads only the finished materials.
        for mode, stops in [('balanced', {'gate:research-plan'}), ('automatic', set())]:
            run = {'review_policy': {'schema': 1, 'level': mode}}
            for gate in ('gate:research-plan', 'gate:research', 'gate:blueprint', 'gate:document'):
                self.assertEqual(review.automatic(run, 'training', gate), gate not in stops, (mode, gate))
            for gate in ('review:direction', 'review:final', 'documents', 'intake', 'deck',
                         'gate:deck', 'gate:deck@101', 'gate:deck@301'):
                self.assertFalse(review.automatic(run, 'training', gate), (mode, gate))
            # A gate that carries its level is read without it.
            self.assertTrue(review.automatic(run, 'training', 'gate:deck-outline@201'))
            self.assertTrue(review.automatic(run, 'training', 'gate:scenario:main@101'))
        run = {'review_policy': {'schema': 1, 'level': 'balanced'}}
        review.receipt(run, 'research', {'hash': 'exact'}, 'today')
        self.assertEqual(run['review_events'][0]['by'], 'review-policy')
        self.assertEqual(run['review_events'][0]['decision'], 'continued-automatically')

    def test_grave_findings_and_audit_blockers_keep_any_gate_for_the_person(self):
        held = review.held([{'severity': 'major', 'slide': 'close01', 'note': 'Too high.'},
                            {'severity': 'minor', 'slide': 'goals01', 'note': 'Small.'},
                            {'severity': 'critical', 'number': 3, 'detail': 'Misleads.'}],
                           [{'code': 'LOGO', 'says': 'Restore the logo.'}])
        self.assertEqual(held, ['Major on close01: Too high.', 'Critical on 3: Misleads.',
                                'Audit blocker: Restore the logo.'])
        self.assertEqual(review.held([{'severity': 'minor', 'note': 'x'}], []), [])
        self.assertEqual(review.held(None, None), [])
        for mode in ('balanced', 'automatic'):
            run = {'review_policy': {'schema': 1, 'level': mode}}
            for product, gate in (('training', 'gate:deck-outline'), ('training', 'gate:brief'),
                                  ('presentation', 'gate:look'), ('blog', 'draft')):
                self.assertTrue(review.automatic(run, product, gate, 'package'))
                self.assertFalse(review.automatic(run, product, gate, 'package', holding=held),
                                 (mode, product, gate))


ROOT = Path(__file__).resolve().parents[1]


def _source(relative):
    return ast.parse((ROOT / relative).read_text(encoding='utf-8'))


def _assigned(tree, name):
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] \
            if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return node.value
    raise AssertionError(f'{name} is not assigned where the policy test looks for it.')


def training_gates():
    """Every gate Training Studio's pipeline lays out, read from its step table, with the
    forms they take: once per level, once per practice scenario, and the two combined
    reviews."""
    rows = [(row.elts[0].value, row.elts[1].value, row.elts[2].value)
            for row in _assigned(_source('studios/training/runner/pipeline.py'), 'TRAINING').elts]
    each = ('document', 'brief', 'deck', 'scenario', 'yoodli')
    gates = {'review:direction', 'review:final'}
    for stage, ident, kind in rows:
        if kind != 'gate':
            continue
        named = [f'{ident}:main'] if stage in ('scenario', 'yoodli') else [ident]
        for one in named:
            gates.add(one)
            if stage in each and ident != 'deck':
                gates.update({f'{one}@101', f'{one}@401'})
    return gates


def presentation_gates():
    tree = _source('studios/presentation/runner/stages.py')
    return {call.args[0].value for call in ast.walk(_assigned(tree, 'PIPELINE'))
            if isinstance(call, ast.Call) and getattr(call.func, 'id', '') == '_s'
            and call.args[2].value == 'gate'}


def blog_stages():
    tree = _source('studios/blog/skills/blog-studio/scripts/blog_runner.py')
    return {key.value for key in _assigned(tree, 'STAGES').keys} - {'angles'}


class EveryRealGateTests(unittest.TestCase):
    """The policy against every gate ID each studio really lays out, so a renamed or new
    gate is decided here rather than slipping past by its name."""
    # Where each level stops: a gate's ID without its level or scenario.
    TRAINING = {'balanced': {'documents', 'intake', 'deck', 'gate:deck', 'gate:deck-look',
                             'gate:research-plan', 'review:direction', 'review:final'},
                'automatic': {'documents', 'intake', 'deck', 'gate:deck',
                              'review:direction', 'review:final'}}
    PRESENTATION = {'balanced': {'gate:outline', 'gate:build', 'rehearse'},
                    'automatic': {'gate:build', 'rehearse'}}
    BLOG = {'balanced': {'outline', 'package'}, 'automatic': {'package'}}

    def test_every_training_gate(self):
        gates = training_gates()
        self.assertIn('gate:deck@101', gates)
        self.assertIn('gate:deck-outline@401', gates)
        self.assertIn('gate:deck-look@101', gates)
        self.assertIn('gate:scenario:main@101', gates)
        for mode, stops in self.TRAINING.items():
            run = {'review_policy': {'schema': 1, 'level': mode}}
            for gate in sorted(gates):
                base = gate.partition('@')[0]
                base = base if base.count(':') < 2 else base.rpartition(':')[0]
                self.assertEqual(review.automatic(run, 'training', gate), base not in stops,
                                 (mode, gate))
        for gate in gates:
            self.assertFalse(review.automatic({'review_policy': {'schema': 1, 'level': 'step_by_step'}},
                                              'training', gate))

    def test_every_presentation_gate(self):
        gates = presentation_gates()
        self.assertEqual(gates, {'gate:classify', 'gate:research-plan', 'gate:research',
                                 'gate:outline', 'gate:look', 'gate:build', 'rehearse'})
        for mode, stops in self.PRESENTATION.items():
            run = {'review_policy': {'schema': 1, 'level': mode}}
            for gate in gates:
                self.assertEqual(review.automatic(run, 'presentation', gate),
                                 gate not in stops, (mode, gate))

    def test_every_blog_stage(self):
        stages = blog_stages()
        self.assertTrue({'research-plan', 'research', 'outline', 'draft', 'review',
                         'package'} <= stages, stages)
        for mode, stops in self.BLOG.items():
            run = {'review_policy': {'schema': 1, 'level': mode}}
            for stage in stages:
                self.assertEqual(review.automatic(run, 'blog', stage, 'package'),
                                 stage not in stops, (mode, stage))
