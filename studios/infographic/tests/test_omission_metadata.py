"""Optional source scope is distinct from required brief coverage; no providers."""
from copy import deepcopy

from helpers import Isolated
import test_workflow_contracts as workflows
from runner import evidence, planning_responses, sources, stories
from runner.contracts import Invalid
from runner.engine import Engine
from runner.planning_schema import PLAN, planning


class OmissionMetadataTests(Isolated):
    start = workflows.WorkflowContractTests.start

    def test_saved_optional_source_omissions_recover_locally_without_new_planning(self):
        example, p, reply = self.start('omission_notes')
        original = deepcopy(reply)
        planning_responses.save(self.store, p, reply)
        with self.store.locked():
            planning_responses.rejected(self.store, p['id'], 'List every omitted required idea before building.')
        result = Engine(self.store).propose(p['id'], expected_revision=p['revision'])
        self.assertEqual(len(result['facts']), 2)
        chosen = result['stories'][0]
        self.assertEqual(chosen['omissions'], [])
        self.assertEqual(chosen['qualifications'], [
            'Not included in this story: load test numbers',
            'Not included in this story: vendor screenshots',
            'Not included in this story: licensing details'])
        self.assertIsNone(result['approval'])
        self.assertEqual(reply, original)
        self.assertEqual(len(list((self.store._project(p['id']) / 'jobs/planning').glob('*.json'))), 1)
        self.assertEqual(sources.read(self.store, result, p['sources'][0]), example['source'])

    def test_required_ideas_still_cannot_be_dropped_or_claimed_as_covered(self):
        example, p, reply = self.start('omission_notes')
        facts = evidence.validated_proposal(self.store, p, reply)
        for direction in ('suggest', 'hybrid'):
            candidate = {**p, 'facts': facts, 'brief': {**p['brief'], 'direction': direction,
                'must_show': [{'id': 'r_core', 'text': 'Keep the core idea.'}]}}
            with self.assertRaises(Invalid): stories.usable_proposals(candidate, reply['stories'])
            stated = deepcopy(reply['stories'])
            stated[0]['omissions'].append('r_core')
            if direction == 'hybrid':
                with self.assertRaises(Invalid): stories.usable_proposals(candidate, stated)
            else:
                checked = stories.usable_proposals(candidate, stated)
                self.assertEqual(checked[0]['omissions'], ['r_core'])
            stated[0]['blocks'][0]['required_ids'] = ['r_core']
            with self.assertRaises(Invalid): stories.usable_proposals(candidate, stated)

    def test_manual_adoption_remains_strict_and_malformed_notes_are_not_guessed(self):
        example, p, reply = self.start('omission_notes')
        candidate = {**p, 'facts': evidence.validated_proposal(self.store, p, reply)}
        with self.assertRaises(Invalid): stories.verify(candidate, reply['stories'])
        for value in (None, {}, [None], ['']):
            malformed = deepcopy(reply['stories']); malformed[0]['omissions'] = value
            with self.assertRaises(Invalid): stories.usable_proposals(candidate, malformed)

    def test_schema_binds_only_actual_requirements_and_source_ids_without_mutating_template(self):
        original = deepcopy(PLAN)
        empty = planning({'direction': 'direct', 'must_show': []}, [{'id': 'captured_one'}])
        story = empty['properties']['stories']
        self.assertEqual(story['maxItems'], 1)
        self.assertEqual(story['items']['properties']['omissions']['maxItems'], 0)
        self.assertEqual(story['items']['properties']['blocks']['items']['properties']['required_ids']['maxItems'], 0)
        shape = planning({'must_show': [{'id': 'r_core'}]}, [{'id': 'captured_one'}])
        self.assertEqual(shape['properties']['stories']['items']['properties']['omissions']['items']['enum'], ['r_core'])
        self.assertEqual(shape['properties']['facts']['items']['properties']['evidence']['items']['properties']['source_id']['enum'], ['captured_one'])
        self.assertEqual(PLAN, original)
