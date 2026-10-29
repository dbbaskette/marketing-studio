from copy import deepcopy
import json
import random
import stat
from unittest import mock

from helpers import Isolated
from test_composition import contract
from test_desk_engine import fake_renderer
from workflow_cases import NAMES, case, captured_answer
from runner import api, brand, checks, evidence, planning_responses, sources, stories, svg, team
from runner.assistant_failure import AssistantFailure
from runner.author import Author
from runner.contracts import Invalid, canonical
from runner.engine import Engine
from runner.workspace import Store


class WorkflowContractTests(Isolated):
    def start(self, name):
        example = case(name)
        store = Store.setup(self.workspace, data=self.data) if not hasattr(self, 'store') else self.store
        self.store = store
        p = store.create('Synthetic ' + name, preset='digital')
        p = sources.capture(store, p['id'], example['source'].encode(), expected_revision=0)
        p = brand.adopt(store, p['id'], contract(), expected_revision=1)
        return example, p, captured_answer(example, p['sources'][0]['id'])

    def test_provider_shaped_replies_complete_the_whole_native_workflow(self):
        for name in NAMES:
            with self.subTest(case=name):
                example, p, reply = self.start(name)
                calls = []
                def run(command, prompt, folder, timeout):
                    calls.append('planning')
                    self.assertIn('--output-schema', command)
                    events = [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Working on the supplied material.'}},
                              {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(reply)}},
                              {'type': 'turn.completed'}]
                    return {'state': 'complete', 'returncode': 0, 'events': '\n'.join(map(json.dumps, events))}
                engine = Engine(self.store, renderer=fake_renderer, assistant=Author({'agent': 'codex'}, run=run))
                planned = engine.propose(p['id'], expected_revision=p['revision'])
                self.assertEqual(calls, ['planning'])
                self.assertFalse(engine.inspect(p['id'])['planning_response']['available'])
                chosen = stories.select(self.store, p['id'], planned['stories'][0]['id'], expected_revision=planned['revision'])
                delivery = engine.build(p['id'], expected_revision=chosen['revision'], request_id='owned_build_' + name)
                current = self.store.read(p['id'])
                if name == 'process':
                    headings = [e['text'] for e in current['scene']['elements'] if e['role'] == 'heading']
                    self.assertIn('1. Buffer', headings); self.assertNotIn('1. 1. Buffer', headings)
                    forged = deepcopy(current)
                    next(e for e in forged['scene']['elements'] if e['id'] == 'b1_heading')['text'] = '1. 99 requests'
                    self.assertEqual(next(c['status'] for c in checks.evaluate(self.store, forged) if c['id'] == 'check_facts'), 'failed')
                rendered = svg.compose(self.store, current)
                self.assertNotIn('NaN', rendered)
                if name == 'numeric_strings':
                    self.assertIn('12.30', rendered); self.assertIn('24.60', rendered)
                if name == 'zeros':
                    self.assertEqual(next(e['values'] for e in current['scene']['elements'] if e['kind'] == 'chart'), [0, 0])
                engine.manual_review(p['id'], delivery['id'], ['Synthetic workflow fixture review; real rendering is verified separately.'], expected_revision=current['revision'])
                engine.check(p['id'], expected_revision=self.store.read(p['id'])['revision'])
                checked = self.store.read(p['id'])
                self.assertTrue(all(c['status'] == 'passed' for c in checked['checks']), checked['checks'])
                approved = engine.approve(p['id'], expected_revision=checked['revision'])
                final = engine.preview(p['id'], expected_revision=approved['revision'], draft=False)
                self.assertEqual({f['format'] for f in final['files']}, {'png', 'pdf', 'svg', 'text'})
                self.assertEqual(calls, ['planning'])
                public, files = team.inventory(self.store, p['id'], expected_revision=approved['revision'],
                                               export_id=final['id'], include_editable=True)
                self.assertFalse(any('planning' in name or 'jobs/' in name for name in files))
                self.assertEqual(sources.read(self.store, self.store.read(p['id']), p['sources'][0]), example['source'])

    def test_validation_failure_is_retained_and_rechecked_without_an_assistant(self):
        example, p, reply = self.start('paraphrase')
        reply['facts'][0]['evidence'][0]['quote'] = 'This quotation is not in the source.'
        reply['stories'] = [reply['stories'][0]]
        calls = []
        class Assistant:
            def propose(self, *args): calls.append('planning'); return deepcopy(reply)
        engine = Engine(self.store, assistant=Assistant())
        with self.assertRaises(AssistantFailure): engine.propose(p['id'], expected_revision=p['revision'])
        self.assertEqual(self.store.read(p['id']), p)
        self.assertTrue(Engine(self.store).inspect(p['id'])['planning_response']['available'])
        with self.assertRaises(AssistantFailure): Engine(self.store).propose(p['id'], expected_revision=p['revision'])
        self.assertEqual(calls, ['planning'])
        self.assertEqual(planning_responses.load(self.store, p), reply)
        path = planning_responses.pointer(self.store, p['id'])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        with self.assertRaises(Invalid):
            api.action(engine, {'action': 'suggest', 'id': p['id'], 'expected_revision': p['revision'], 'fresh': 'yes'})
        self.assertEqual(calls, ['planning'])
        with self.assertRaises(AssistantFailure): engine.propose(p['id'], expected_revision=p['revision'], fresh=True)
        self.assertEqual(calls, ['planning', 'planning'])
        edited = self.store.edit_brief(p['id'], {**p['brief'], 'audience': 'A changed audience'}, expected_revision=p['revision'])
        self.assertIsNone(planning_responses.load(self.store, edited))

    def test_literal_manual_input_and_ambiguous_quotations_remain_strict(self):
        example, p, reply = self.start('paraphrase')
        located = evidence.locate(self.store, p, reply['facts'])
        with self.assertRaises(Invalid): evidence.verify(self.store, p, located)
        self.assertIsNone(evidence.quoted_span('Same phrase. Same phrase.', 'Same phrase.'))
        self.assertIsNone(evidence.quoted_span('A queue. Another queue.', 'queue'))
        source = '“Cafe\u0301”\u00a0queues\n   buffer messages.'
        span = evidence.quoted_span(source, '"Café" queues buffer messages.')
        self.assertEqual(source[slice(*span)], source)

    def test_response_storage_does_not_publish_a_partial_pointer(self):
        example, p, reply = self.start('paraphrase')
        with mock.patch.object(self.store, 'write_blob', side_effect=OSError('Synthetic interrupted write')):
            with self.assertRaises(OSError): planning_responses.save(self.store, p, reply)
        self.assertIsNone(planning_responses.load(self.store, p))
        self.assertEqual(self.store.read(p['id']), p)

    def test_saved_response_integrity_owner_and_links_are_checked_before_provider_work(self):
        example, p, reply = self.start('paraphrase')
        planning_responses.save(self.store, p, reply)
        pointer = planning_responses.pointer(self.store, p['id'])
        ref = json.loads(pointer.read_text())
        record_path = pointer.parent / 'planning' / (ref['response'] + '.json')
        record_path.write_text('{}')
        run = mock.Mock()
        with self.assertRaises(Invalid): Engine(self.store, assistant=run).propose(p['id'], expected_revision=p['revision'], fresh=True)
        run.propose.assert_not_called()
        self.assertEqual(self.store.read(p['id']), p)
        pointer.unlink(); pointer.symlink_to(self.settings)
        with self.assertRaises(Invalid): Engine(self.store, assistant=run).propose(p['id'], expected_revision=p['revision'])
        run.propose.assert_not_called()

    def test_wrong_quantities_and_invented_dates_remain_blocked(self):
        for name in ('numeric_strings', 'timeline'):
            with self.subTest(case=name):
                example, p, reply = self.start(name)
                if name == 'numeric_strings': reply['facts'][0]['value'] = 999
                else: reply['facts'][0]['period'] = '2099'
                # Remove the second supported fact/story route so the bad claim cannot be adopted.
                reply['facts'] = [reply['facts'][0]]
                reply['stories'][0]['blocks'] = [reply['stories'][0]['blocks'][0]]
                reply['stories'][0]['blocks'][0]['fact_ids'] = ['f1']
                with self.assertRaises(Invalid): evidence.validated_proposal(self.store, p, reply)
                self.assertEqual(self.store.read(p['id']), p)
        self.assertFalse(any(evidence.NUMBERS.finditer('1,200')))
        for unsupported in ('1e3', '1.2e-3', '1.2E+3'):
            self.assertFalse(any(evidence.NUMBERS.finditer(unsupported)), unsupported)

    def test_malformed_model_fields_never_become_uncaught_type_errors(self):
        example, p, baseline = self.start('paraphrase')
        rng = random.Random(811)
        fields = ('statement', 'value', 'unit', 'period', 'evidence', 'calculation')
        for index in range(60):
            reply = deepcopy(baseline)
            reply['facts'] = [reply['facts'][0]]
            reply['stories'][0]['blocks'][0]['fact_ids'] = ['f1']
            reply['facts'][0][rng.choice(fields)] = rng.choice([None, [], {}, True, 0, ''])
            try:
                facts = evidence.validated_proposal(self.store, p, reply)
                candidate = {**p, 'facts': facts}
                stories.usable_proposals(candidate, reply['stories'])
            except Invalid:
                pass
            self.assertEqual(self.store.read(p['id']), p)
        checked = evidence.validated_proposal(self.store, p, baseline)
        candidate = {**p, 'facts': checked}
        for field in ('headline', 'qualifications', 'omissions', 'blocks'):
            for value in (None, [], {}, True, 0, ''):
                proposals = deepcopy(baseline['stories'])
                proposals[0][field] = value
                try: stories.usable_proposals(candidate, proposals)
                except Invalid: pass
        for field in ('kind', 'title', 'text', 'fact_ids', 'required_ids', 'illustration', 'quantitative'):
            for value in (None, [], {}, True, 0, ''):
                proposals = deepcopy(baseline['stories'])
                proposals[0]['blocks'][0][field] = value
                try: stories.usable_proposals(candidate, proposals)
                except Invalid: pass
