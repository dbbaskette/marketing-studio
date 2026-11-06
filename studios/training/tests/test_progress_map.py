"""Progress is a projection of saved scope/receipts, not a second scheduler."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest

import helpers  # noqa: F401
import runner_support  # noqa: F401  adds the native runner to the test import path
from runner import progress_map


def step(ident, stage, artifact=None):
    return NS(id=ident, stage=stage, artifact=artifact)


def card(name, kind='document', state='queued', seen=None):
    return {'name': name, 'kind': kind, 'state': state, 'seen': seen, 'level': '101'}


class ProgressMapTests(unittest.TestCase):
    def setUp(self):
        self.steps = [step('scan', 'research-plan'), step('review:training-plan', 'research-plan'),
                      step('research-plan', 'research-plan'), step('research', 'research'),
                      step('document@101', 'document', 'document@101'), step('package', 'package')]
        self.found = NS(steps=self.steps, done=set(), session={'settings': {'stages': ['document']}, 'unavailable': {}},
                        next=NS(step=self.steps[0], kind='work'))
        self.record = {}
        self.cards = [card('document@101')]

    def shown(self, state='working', **options):
        return progress_map.project(self.record, self.found, self.cards, state, 'Current operation.', **options)

    def by_id(self, result):
        return {item['id']: item for item in result['stages']}

    def test_outline_approval_precedes_research_and_a_read_changes_nothing(self):
        self.found.done = {'scan'}; self.found.next = NS(step=self.steps[1], kind='review')
        before = deepcopy((self.record, self.cards, vars(self.found)))
        result = self.shown('waiting'); stages = self.by_id(result)
        self.assertEqual(list(stages), ['outline', 'research', 'materials', 'review'])
        self.assertEqual(stages['outline']['state'], 'needs-you')
        self.assertEqual(stages['research']['state'], 'waiting')
        self.assertEqual((self.record, self.cards, vars(self.found)), before)

    def test_legacy_plan_is_after_research(self):
        self.found.steps = [self.steps[2], self.steps[3], step('blueprint@101', 'blueprint', 'blueprint@101'),
                            step('review:training-plan', 'blueprint'), *self.steps[4:]]
        self.found.done = {'research-plan', 'research'}
        self.found.next = NS(step=self.found.steps[3], kind='review')
        result = self.shown('waiting'); stages = self.by_id(result)
        self.assertEqual(list(stages), ['research', 'plan', 'materials', 'review'])
        self.assertEqual(stages['plan']['state'], 'needs-you')
        self.assertEqual(stages['research']['state'], 'complete')

    def test_slot_and_missing_sources_are_not_called_working(self):
        result = self.by_id(self.shown(queued=True))
        self.assertEqual(result['outline']['state'], 'waiting')
        self.assertIn('assistant slot', result['outline']['detail'])
        self.found.next = NS(step=None, kind='documents')
        self.assertEqual(self.by_id(self.shown('waiting'))['outline']['state'], 'needs-you')

    def test_research_has_real_counts_and_phase_then_marked_creator_acceptance(self):
        self.found.done = {'scan', 'review:training-plan', 'research-plan'}
        self.found.next = NS(step=self.steps[3], kind='work')
        self.record['research_execution'] = {'progress': {'phase': 'synthesize',
            'streams': [{'status': 'kept'}, {'status': 'failed'}],
            'combining': [{'status': 'kept'}, {'status': 'working'}]}}
        research = self.by_id(self.shown())['research']
        self.assertEqual(research['phase'], 'Writing research sections')
        self.assertEqual([(count['done'], count['total']) for count in research['counts']], [(1, 2), (1, 2)])
        self.record['research_execution']['progress']['phase'] = 'creator-approved'
        self.found.done.add('research'); self.found.next.step = self.steps[4]
        research = self.by_id(self.shown())['research']
        self.assertEqual(research['words'], 'Accepted with flags')
        self.assertIn('not independently verified', research['warning'])

    def test_only_selected_branches_appear_and_unknown_practice_scope_is_not_complete(self):
        stages = self.by_id(self.shown())
        self.assertEqual([branch['id'] for branch in stages['materials']['branches']], ['reading'])
        self.found.session['settings']['stages'].append('scenario')
        practice = self.by_id(self.shown())['materials']['branches'][1]
        self.assertEqual((practice['state'], practice['total']), ('waiting', 0))
        self.assertIn('level plans', practice['detail'])
        planned = step('blueprint@101', 'blueprint', 'blueprint@101')
        self.found.steps.append(planned); self.found.done.add(planned.id)
        practice = self.by_id(self.shown())['materials']['branches'][1]
        self.assertEqual(practice['state'], 'complete')
        self.assertIn('No practice items', practice['detail'])

    def test_stop_belongs_to_failed_branch_and_does_not_hide_saved_peers(self):
        deck = step('outline:101', 'deck', 'deck@101'); self.found.steps.append(deck)
        self.found.next = NS(step=deck, kind='outline')
        self.cards = [card('document@101', state='draft', seen='guide'), card('deck@101', 'deck', 'decide')]
        stages = self.by_id(self.shown('waiting'))
        self.assertEqual(stages['materials']['branches'][0]['state'], 'complete')
        self.assertEqual(stages['materials']['branches'][1]['state'], 'needs-you')
        self.record['problem'] = {'step': 'outline:101:section-1', 'what': 'Spending amount reached.'}
        stages = self.by_id(self.shown('failed'))
        self.assertEqual(stages['materials']['state'], 'stopped')
        self.assertEqual(stages['materials']['branches'][0]['available'], 1)
        self.assertEqual(stages['materials']['branches'][1]['state'], 'stopped')

    def test_prior_draft_during_update_is_available_not_complete_or_ready(self):
        self.found.next.step = self.steps[4]
        for state in ('queued', 'writing', 'held'):
            with self.subTest(state=state):
                self.cards = [card('document@101', state=state, seen='old')]
                stages = self.by_id(self.shown('waiting' if state == 'held' else 'working', queued=state == 'queued'))
                self.assertEqual(stages['materials']['available'], 1)
                self.assertNotEqual(stages['materials']['state'], 'complete')
                self.assertNotEqual(stages['review']['state'], 'complete')
                self.assertEqual(stages['review']['ready'], 0)

    def test_generation_is_not_creator_readiness(self):
        self.found.done = {s.id for s in self.steps}; self.found.next = NS(step=None, kind='done')
        self.cards = [card('document@101', state='draft', seen='draft')]
        stages = self.by_id(self.shown('done'))
        self.assertEqual(stages['materials']['state'], 'complete')
        self.assertEqual(stages['review']['state'], 'needs-you')
        self.cards[0]['state'] = 'ready'
        self.assertEqual(self.by_id(self.shown('done'))['review']['state'], 'complete')

    def test_review_can_start_while_another_material_is_still_working(self):
        self.cards = [card('document@101', state='draft', seen='draft'), card('brief@101', 'brief', 'writing')]
        self.assertEqual(self.by_id(self.shown())['review']['state'], 'available')

    def test_conversation_and_other_computers_do_not_claim_live_work(self):
        self.record['execution'] = 'conversation'; self.cards[0]['state'] = 'writing'
        result = self.shown()
        self.assertEqual([item['id'] for item in result['stages']], ['materials', 'review'])
        self.assertIsNone(result['current']); self.assertIn('no work is scheduled', result['note'])
        self.assertNotIn('working', [item['state'] for item in result['stages']])
        self.record.clear(); result = self.shown(mine=False)
        self.assertIsNone(result['current']); self.assertIn('another computer', result['note'])
