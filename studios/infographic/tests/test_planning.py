import json
from pathlib import Path

from helpers import Isolated
from runner import sources
from runner.activity import Activity
from runner.assistant_failure import AssistantFailure, MESSAGES, classify
from runner.author import Author
from runner.engine import Engine
from runner.planning_schema import PLAN, planning
from runner.workspace import Store


class PlanningTests(Isolated):
    def test_bounded_schema_and_unique_quotes_feed_the_native_checks(self):
        store = Store.setup(self.workspace)
        project = store.create('Synthetic long source')
        quote = 'One instance restarts while the other instances serve.'
        source = 'Background context. ' * 1700 + quote
        project = sources.capture(store, project['id'], source.encode(), kind='text',
                                  name='synthetic.txt', expected_revision=0)
        captured = project['sources'][0]
        reply = {'facts': [{'id': 'f1', 'statement': quote, 'value': quote, 'unit': 'unknown',
                  'status': 'supplied', 'period': '', 'denominator': '', 'conditions': '',
                  'uncertainty': '', 'calculation': None,
                  'evidence': [{'source_id': captured['id'], 'quote': quote}]}],
                 'stories': [{'id': 's1', 'headline': 'Keep serving', 'takeaway': quote,
                  'rationale': 'Explain only the supplied relationship.', 'qualifications': [], 'omissions': [],
                  'blocks': [{'id': 'b1', 'kind': 'concept', 'title': 'One at a time', 'text': quote,
                   'fact_ids': ['f1'], 'required_ids': [], 'quantitative': False,
                   'illustration': False, 'illustration_role': ''}]}]}
        calls = []

        def run(command, prompt, folder, timeout):
            calls.append(command)
            self.assertEqual(timeout, 300)
            self.assertIn('omit start/end', prompt)
            self.assertIn('at most 12 facts', prompt)
            path = Path(command[command.index('--output-schema') + 1])
            self.assertEqual(path.parent, folder)
            self.assertEqual(json.loads(path.read_text()), planning(project['brief'], [{'id': captured['id']}]))
            self.assertEqual(command[command.index('-m') + 1], 'synthetic-model')
            self.assertIn('model_reasoning_effort="high"', command)
            events = [None, {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Working.'}},
                      {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(reply)}}]
            return {'state': 'complete', 'returncode': 0, 'events': '\n'.join(map(json.dumps, events))}

        author = Author({'agent': 'codex', 'model': 'synthetic-model', 'effort': 'high'}, run=run)
        result = Engine(store, assistant=author).propose(project['id'], expected_revision=project['revision'])
        point = result['facts'][0]['evidence'][0]
        self.assertEqual((point['start'], point['end']), (source.index(quote), len(source)))
        self.assertEqual(len(result['stories']), 1)
        self.assertIsNone(result['approval'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(list((self.data / 'jobs').iterdir()), [])

    def test_failed_workers_report_safe_specific_causes_without_retrying(self):
        cases = [
            ('unknown', -9, '', 'timeout'),
            ('cancelled', -9, '', 'cancelled'),
            ('complete', 1, 'Unauthorized: private provider detail', 'sign-in'),
            ('unknown', -9, 'Rate limit exceeded: private provider detail', 'quota'),
            ('complete', 1, 'model_not_found: private provider detail', 'model'),
            ('complete', 2, 'unexpected argument --output-schema', 'incompatible'),
            ('complete', 1, 'stream disconnected: private provider detail', 'connection'),
            ('complete', 1, 'private provider detail', 'worker'),
        ]
        for state, code, detail, reason in cases:
            with self.subTest(reason=reason):
                calls = []
                def run(command, prompt, folder, timeout):
                    calls.append(command)
                    (folder / 'stderr.txt').write_text(detail)
                    return {'state': state, 'returncode': code, 'events': ''}
                author = Author({'agent': 'codex'}, run=run)
                activity = Activity()
                with self.assertRaises(AssistantFailure) as raised:
                    with activity.track('owned', 'suggest'):
                        author._call('Synthetic source')
                self.assertEqual(raised.exception.reason, reason)
                self.assertEqual(str(raised.exception), MESSAGES[reason])
                observed = activity.snapshot('owned')
                self.assertEqual(observed['reason'], reason)
                self.assertEqual(observed['problem'], MESSAGES[reason])
                self.assertNotIn('private provider detail', json.dumps(observed))
                self.assertEqual(observed['state'], 'failed')
                self.assertEqual(len(calls), 1)
                self.assertEqual(list((self.data / 'jobs').iterdir()), [])

    def test_terminal_error_events_and_missing_or_malformed_output_are_not_proposals(self):
        cases = [({'type': 'turn.failed', 'error': {'message': 'rate_limit_exceeded'}}, 'quota'),
                 ({'type': 'result', 'is_error': True, 'result': 'Unauthorized'}, 'sign-in'),
                 ({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Not JSON'}}, 'invalid-output'),
                 ({'type': 'turn.completed'}, 'invalid-output')]
        for event, reason in cases:
            with self.subTest(reason=reason):
                def run(*args):
                    return {'state': 'complete', 'returncode': 0, 'events': json.dumps(event)}
                with self.assertRaises(AssistantFailure) as raised:
                    Author({'agent': 'codex'}, run=run)._call('Synthetic source')
                self.assertEqual(raised.exception.reason, reason)
        quoted = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'A source discusses quota and sign-in.'}}
        self.assertEqual(classify({'state': 'unknown', 'events': json.dumps(quoted)}), 'timeout')

    def test_schema_keeps_calculations_and_never_requires_manual_offsets(self):
        fact = PLAN['properties']['facts']
        self.assertEqual(fact['maxItems'], 12)
        point = fact['items']['properties']['evidence']['items']
        self.assertEqual(set(point['required']), {'source_id', 'quote'})
        self.assertFalse(point['additionalProperties'])
        self.assertIn('calculation', fact['items']['properties'])
        self.assertEqual(PLAN['properties']['stories']['maxItems'], 3)
