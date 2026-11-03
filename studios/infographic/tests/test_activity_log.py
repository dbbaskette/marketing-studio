"""What the assistant is doing while it works, and each infographic's Activity log (#294).

Synthetic events and local stand-in processes only: no assistant is started."""
import json
import sys
import threading

from helpers import Isolated
from runner import activity as activities
from runner.activity import Activity
from runner.assistant_failure import AssistantFailure
from runner.author import Author, watching
from runner.images.codex import execute
from runner.workspace import Store
from studio_core import activity_log

CLAUDE = [{'type': 'system', 'subtype': 'init', 'model': 'synthetic-model'},
          {'type': 'assistant', 'message': {'content': [
              {'type': 'tool_use', 'id': 't1', 'name': 'WebSearch',
               'input': {'query': 'synthetic capacity statistics'}}]}},
          {'type': 'result', 'subtype': 'success', 'result': '{"result": "fixture"}'}]
CODEX = [{'type': 'thread.started'}, {'type': 'item.completed', 'item': {'type': 'reasoning'}},
         {'type': 'item.completed', 'item': {'type': 'web_search', 'query': 'synthetic counts'}},
         {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{"result": "fixture"}'}},
         {'type': 'turn.completed', 'usage': {}}]
TASK = 'Synthetic private task text that must never be kept'


def answered(events):
    def run(command, prompt, folder, seconds, stop=None):
        return {'state': 'complete', 'returncode': 0,
                'events': '\n'.join(json.dumps(event) for event in events)}
    return run


class AuthorLinesTests(Isolated):
    def test_each_assistant_says_what_it_does_in_plain_lines(self):
        for agent, events, expected in (
                ('claude', CLAUDE, ['Started on synthetic-model',
                                    'Searching the web: synthetic capacity statistics']),
                ('codex', CODEX, ['Started', 'Thinking', 'Searching the web: synthetic counts'])):
            lines = activity_log.Lines()
            with watching(lines.append):
                self.assertEqual(Author({'agent': agent}, run=answered(events))._call(TASK),
                                 {'result': 'fixture'})
            self.assertEqual([line['text'] for line in lines.items()], expected, agent)
        # Research names its own listener, as its jobs run on threads of their own.
        lines = activity_log.Lines()
        Author({'agent': 'codex'}, run=answered(CODEX)).research(
            'investigate', {'q': 1}, 'Guide.', activity=lines.append)
        self.assertEqual(lines.items()[-1]['text'], 'Searching the web: synthetic counts')

    def test_lines_arrive_while_the_assistant_is_still_running(self):
        folder = self.temp / 'worker'
        folder.mkdir()
        released, seen = threading.Event(), []
        script = ('import json, sys, time\n'
                  'print(json.dumps({"type": "thread.started"}), flush=True)\n'
                  'while not __import__("os").path.exists(sys.argv[1]): time.sleep(0.05)\n'
                  'print(json.dumps({"type": "item.completed", "item": {"type": "reasoning"}}))\n')
        gate = folder / 'go'

        def watch(event):
            seen.append(event['type'])
            if event['type'] == 'thread.started':
                released.set()
                gate.write_text('go')       # the assistant carries on only once this is seen

        answer = execute([sys.executable, '-c', script, str(gate)], '', folder, 20, watch=watch)
        self.assertEqual(answer['state'], 'complete')
        self.assertTrue(released.is_set())
        self.assertEqual(seen, ['thread.started', 'item.completed'])


    def test_every_last_event_is_read_however_much_arrives_at_the_end(self):
        folder = self.temp / 'burst'
        folder.mkdir()
        script = ('import json, sys\n'
                  'line = json.dumps({"type": "item.completed", "item": {"type": "reasoning"}, '
                  '"pad": "x" * 60})\n'
                  'sys.stdout.write((line + "\\n") * 20000)\n')
        seen = []
        execute([sys.executable, '-c', script], '', folder, 20, watch=seen.append)
        self.assertEqual(len(seen), 20000)


class ActivityEntryTests(Isolated):
    def setUp(self):
        super().setUp()
        self.kept = []
        self.activity = Activity(keep=lambda ident, entry: self.kept.append((ident, entry)))

    def test_a_running_operation_shows_its_latest_line_and_is_logged_when_it_ends(self):
        with self.activity.track('p1', 'suggest') as report:
            report.said('Started')
            report.said('Searching the web: synthetic counts')
            worker = self.activity.snapshot('p1')['worker']
            self.assertEqual(worker['label'], 'Finding the story')
            self.assertEqual(worker['now']['text'], 'Searching the web: synthetic counts')
            self.assertEqual(worker['count'], 2)
            self.assertNotIn('lines', worker, 'a poll stays small')
            (ident, job), = self.activity.running('p1')
            self.assertEqual(ident, worker['id'])
            self.assertEqual(job['lines'].count, 2)
            self.assertEqual(self.kept, [], 'nothing is logged while it runs')
        self.assertNotIn('worker', self.activity.snapshot('p1'))
        (ident, entry), = self.kept
        self.assertEqual((ident, entry['label'], entry['step'], entry['outcome']),
                         ('p1', 'Finding the story', 'suggest', 'finished'))
        self.assertEqual([line['text'] for line in entry['lines']],
                         ['Started', 'Searching the web: synthetic counts'])

    def test_every_ending_is_logged_as_such(self):
        for failure, ended in ((AssistantFailure('timeout'), 'timeout'),
                               (AssistantFailure('cancelled'), 'stopped'),
                               (AssistantFailure('quota'), 'limit'),
                               (AssistantFailure('connection'), 'failed')):
            with self.assertRaises(AssistantFailure):
                with self.activity.track('p1', 'art-direct'):
                    raise failure
            self.assertEqual(self.kept[-1][1]['outcome'], ended)
            self.assertEqual(self.kept[-1][1]['detail'], str(failure))
        with self.activity.track('p1', 'image-start') as report:
            report.said('Started')
            self.activity.outcome('p1', {'state': 'cancelled'})
        self.assertEqual(self.kept[-1][1]['outcome'], 'stopped')
        # An outcome that could not be confirmed is not called out of time.
        with self.activity.track('p1', 'image-start') as report:
            report.said('Started')
            self.activity.outcome('p1', {'state': 'unknown'})
        self.assertEqual(self.kept[-1][1]['outcome'], 'failed')
        self.assertIn('without a confirmed result', self.kept[-1][1]['detail'])
        with self.assertRaises(RuntimeError):
            with self.activity.track('p1', 'suggest') as report:
                report.said('Started')
                raise RuntimeError('private failure')
        self.assertEqual(self.kept[-1][1]['outcome'], 'failed')
        self.assertNotIn('private failure', json.dumps(self.kept[-1][1]))

    def test_an_operation_no_assistant_worked_in_is_not_logged(self):
        with self.activity.track('p1', 'preview'):
            pass
        self.assertEqual(self.kept, [])
        self.assertEqual(activities.ending({'state': 'outdated'}), 'failed')


class StoreLogTests(Isolated):
    def test_the_log_is_kept_in_the_infographic_and_read_newest_first(self):
        store = Store.setup(self.workspace)
        ident = store.create('Synthetic activity')['id']
        found = store.activity_log(ident)
        self.assertEqual((found['jobs'], found['empty']), ([], 'No activity recorded yet.'))
        activity = Activity(keep=store.keep_activity)
        for agent, events in (('claude', CLAUDE), ('codex', CODEX)):
            with activity.track(ident, 'suggest') as report, watching(report.said):
                Author({'agent': agent}, run=answered(events))._call(TASK)
        jobs = store.activity_log(ident)['jobs']
        self.assertEqual([store.activity_log(ident, entry=job['id'])['lines'][0]['text'] for job in jobs],
                         ['Started', 'Started on synthetic-model'])
        written = (self.workspace / 'projects' / ident / activity_log.FILE).read_text()
        self.assertNotIn(TASK, written)
        self.assertNotIn('"type"', written)
        # The log is no revision of the infographic: its history and listing are unchanged.
        self.assertEqual(store.read(ident)['revision'], 0)
        self.assertEqual([item['id'] for item in store.listing()], [ident])


if __name__ == '__main__':
    import unittest
    unittest.main()
