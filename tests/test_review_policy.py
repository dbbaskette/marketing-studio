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
        # Balanced stops at the first writing stage a blog has: the outline when there is
        # one, else the draft, so a blog from an outline is read before its package.
        self.assertFalse(review.automatic(run, 'blog', 'draft', 'package', first='draft'))
        self.assertTrue(review.automatic(run, 'blog', 'draft', 'package', first='outline'))
        self.assertTrue(review.automatic(run, 'blog', 'review', 'package', first='draft'))
        automatic_run = {'review_policy': {'schema': 1, 'level': 'automatic'}}
        self.assertTrue(review.automatic(automatic_run, 'blog', 'draft', 'package', first='draft'))
        self.assertFalse(review.automatic(automatic_run, 'blog', 'package', 'package', first='draft'))
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

    def test_effective_reads_balanced_when_absent_and_step_by_step_when_invalid(self):
        self.assertEqual(review.effective({}), 'balanced')
        self.assertEqual(review.effective({'review': {'level': 'automatic'}}), 'automatic')
        self.assertEqual(review.effective({'review': {'level': 'fast'}}), 'step_by_step')
        # A file that cannot be read never gives more autonomy than Step by step.
        self.assertEqual(review.effective({}, 'Unreadable'), 'step_by_step')

    def test_change_writes_the_level_under_the_lock_and_keeps_other_values(self):
        shared.path().write_text('{"schema": 1, "share": "asked"}')
        review.change(shared.update, 'automatic', 'balanced')
        values = shared.read()[0]
        self.assertEqual(values['share'], 'asked')
        self.assertEqual(values['review'], {'level': 'automatic'})

    def test_change_refuses_a_level_another_studio_changed(self):
        shared.path().write_text('{"schema": 1, "review": {"level": "step_by_step"}}')
        before = shared.path().read_bytes()
        with self.assertRaises(ValueError) as caught:
            review.change(shared.update, 'automatic', 'balanced')
        self.assertEqual(str(caught.exception), review.STALE)
        self.assertEqual(review.STALE, 'Another studio changed where new work stops. '
                                       'Reload the page and try again.')
        self.assertEqual(shared.path().read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'Choose Balanced'):
            review.change(shared.update, 'fast', 'step_by_step')

    def test_change_takes_a_level_the_file_already_holds(self):
        # A start that wrote the level and then failed is tried again from the same form:
        # the file holds what it asks for, so there is nothing stale to refuse.
        shared.path().write_text('{"schema": 1, "review": {"level": "automatic"}}')
        before = shared.path().read_bytes()
        review.change(shared.update, 'automatic', 'balanced')
        self.assertEqual(shared.path().read_bytes(), before)

    def test_change_refuses_an_unreadable_file(self):
        from marketing_studio.errors import WorkspaceError
        shared.path().write_text('{')
        with self.assertRaises(WorkspaceError) as caught:
            review.change(shared.update, 'automatic', 'balanced')
        self.assertTrue(str(caught.exception).endswith(shared.REFUSED), str(caught.exception))
        self.assertEqual(shared.path().read_text(), '{')

    def test_ahead_agrees_with_automatic_for_every_product_and_level(self):
        products = [
            ('blog', ['outline', 'draft', 'review', 'package'], 'package'),
            ('presentation', ['gate:classify', 'gate:research', 'gate:outline', 'gate:look',
                              'gate:build'], None),
            ('training', ['gate:research-plan', 'review:direction', 'gate:deck-outline@101',
                          'gate:deck-look@101', 'gate:deck@101', 'review:final'], None)]
        for level in review.LEVELS:
            run = {'review_policy': {'schema': 1, 'level': level}}
            for product, gates, last in products:
                with self.subTest(level=level, product=product):
                    self.assertEqual(review.ahead(run, product, gates, last=last),
                                     [g for g in gates
                                      if not review.automatic(run, product, g, last=last)])
        run = {'review_policy': {'schema': 1, 'level': 'balanced'}}
        self.assertEqual(review.ahead(run, 'blog', ['draft', 'review', 'package'],
                                      last='package', first='draft'), ['draft', 'package'])

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
    TRAINING = {'balanced': {'documents', 'intake', 'deck', 'gate:deck',
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


class SameDeckPausesTests(unittest.TestCase):
    """Both studios make a deck the same way: at each level, the brand's checkpoints pause in
    the same places, whichever studio's own gate or combined stop hosts them."""

    def paused(self, product, level, gates):
        from studio_core import deck_flow
        found = set()
        hosts = deck_flow.HOSTS.get(product, {}).get(level, {})
        run = {'review_policy': {'schema': 1, 'level': level}}
        for gate in gates:
            checkpoint = deck_flow.canonical(product, gate)
            if checkpoint is None:
                continue
            if not review.automatic(run, product, gate, 'package'):
                hosted = next((stop for stop, host in hosts.items() if host == gate), None)
                found.add(hosted or checkpoint)
        found.update(stop for stop, host in hosts.items() if host not in gates or host.startswith('review:'))
        return found

    def test_each_level_pauses_both_studios_at_the_same_checkpoints(self):
        from studio_core import deck_flow
        for level in ('step_by_step', 'balanced', 'automatic'):
            with self.subTest(level=level):
                training = self.paused('training', level, training_gates())
                presentation = self.paused('presentation', level, presentation_gates())
                self.assertEqual(training, presentation)
                self.assertEqual(training, set(deck_flow.pauses(level)))

    def test_the_canonical_table(self):
        from studio_core import deck_flow
        self.assertEqual(deck_flow.PAUSES, {'step_by_step': ('draft', 'look', 'final'),
                                            'balanced': ('direction', 'final'),
                                            'automatic': ('final',)})
        self.assertIs(deck_flow.stops('training', 'balanced', 'gate:deck-look@101'), False)
        self.assertIs(deck_flow.stops('training', 'automatic', 'gate:deck'), True)
        self.assertIs(deck_flow.stops('presentation', 'balanced', 'gate:outline'), True)
        self.assertIs(deck_flow.stops('presentation', 'balanced', 'gate:look'), False)
        self.assertIsNone(deck_flow.stops('training', 'balanced', 'gate:brief'))
