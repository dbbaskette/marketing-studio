"""Readable-first scheduling preserves the existing dependencies and saved flows."""
import copy
import unittest

import runner_support  # noqa: F401  adds the native runner and core import paths
import workspace
from runner import material_flow, pipeline


def record():
    return {'schema': 7, 'flow': 'desk', 'outline_first': {'schema': 1},
            'material_flow': dict(material_flow.PIN), 'drafts': {}}


class MaterialOrderTests(unittest.TestCase):
    def test_readable_materials_precede_later_plans_and_every_deck_wait(self):
        levels = ['101', '201', '301', '401']
        listed = pipeline.steps(levels, stages=(*pipeline.STAGES, 'yoodli'),
                                practice={level: {'main': {}} for level in levels}, deck=True)
        ordered = material_flow.order(listed, {'levels': levels}, record())
        ids = [step.id for step in ordered]
        self.assertCountEqual(ordered, listed)
        self.assertEqual(ids[:7], [step.id for step in listed[:7]])
        self.assertEqual(ids[7:19], [
            'blueprint@101', 'gate:blueprint@101', 'document@101', 'gate:document@101',
            'brief@101', 'gate:brief@101', 'blueprint@201', 'gate:blueprint@201',
            'document@201', 'gate:document@201', 'brief@201', 'gate:brief@201'])
        self.assertLess(ids.index('brief@401'), ids.index('scenario:main@101'))
        self.assertLess(ids.index('yoodli:main@401'), ids.index('gate:deck-outline@101'))
        self.assertEqual(ids[-1], 'package')
        # Count material author calls, not an unsupported provider-time estimate.
        before = [step.id for step in listed if step.kind == 'agent' and step.stage != 'research']
        after = [step.id for step in ordered if step.kind == 'agent' and step.stage != 'research']
        self.assertEqual(before.index('document@101') - after.index('document@101'), 3)

    def test_optional_outputs_and_unavailable_decks_keep_their_steps_and_dependencies(self):
        for levels in ([], ['101'], ['101', '201']):
            for stages in ((), ('document',), ('brief',), ('deck',), ('scenario', 'yoodli'), pipeline.STAGES):
                for deck in (True, False):
                    with self.subTest(levels=levels, stages=stages, deck=deck):
                        listed = pipeline.steps(levels, stages, {at: {'main': {}} for at in levels or [None]},
                                                copies=['document', 'brief', 'yoodli:main'], deck=deck)
                        ordered = material_flow.order(listed, {'levels': levels}, record())
                        self.assertCountEqual(ordered, listed)
                        for at in levels or [None]:
                            # Stable grouping preserves each artifact's work/gate/copy order.
                            for stage in ('blueprint', 'document', 'brief', 'scenario', 'yoodli', 'deck'):
                                def own(step):
                                    return step.stage == stage and (not step.artifact or workspace.split(step.artifact)[1] == at)
                                self.assertEqual([step for step in ordered if own(step)], [step for step in listed if own(step)])

    def test_legacy_records_and_explicit_updates_keep_their_existing_order(self):
        listed = pipeline.steps(['101', '201'], deck=True)
        legacy = record(); legacy.pop('material_flow')
        update = record(); update['drafts']['updates'] = {'document@101': {'at': 'saved'}}
        for saved in (legacy, update, {}):
            self.assertEqual(material_flow.order(listed, {'levels': ['101', '201']}, saved), listed)

    def test_unknown_policy_never_enables_new_scheduling(self):
        for value in (None, {}, True, {'schema': True, 'order': 'readable-first'},
                      {'schema': 2, 'order': 'readable-first'}, {'schema': 1, 'order': 'anything'}):
            saved = record(); saved['material_flow'] = copy.deepcopy(value)
            self.assertFalse(material_flow.enabled(saved))
