import copy
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
            for gate in ('review:direction', 'review:final', 'documents', 'intake', 'deck'):
                self.assertFalse(review.automatic(run, 'training', gate), (mode, gate))
        run = {'review_policy': {'schema': 1, 'level': 'balanced'}}
        review.receipt(run, 'research', {'hash': 'exact'}, 'today')
        self.assertEqual(run['review_events'][0]['by'], 'review-policy')
        self.assertEqual(run['review_events'][0]['decision'], 'continued-automatically')
