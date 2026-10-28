"""Worker confinement and bounded shutdown, with local synthetic subprocesses only."""
import json
import sys
import time
from unittest import mock

from helpers import Isolated
from graphics_fixtures import png
from runner.author import Author
from runner.images.codex import execute


class WorkerTests(Isolated):
    def test_blocked_stdin_cannot_escape_the_owned_timeout(self):
        folder = self.temp / 'worker'; folder.mkdir()
        start = time.monotonic()
        answer = execute([sys.executable, '-c', 'import time; time.sleep(30)'], 'x' * 200_000, folder, 1)
        self.assertEqual(answer['state'], 'unknown')
        self.assertLess(time.monotonic() - start, 4)

    def test_planning_and_image_inspection_keep_distinct_tool_boundaries(self):
        calls = []
        def run(command, prompt, folder, timeout):
            calls.append((command, prompt))
            if command[0].endswith('codex'):
                event = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{"result":"fixture"}'}}
            else: event = {'type': 'result', 'result': '{"result":"fixture"}'}
            return {'state': 'complete', 'returncode': 0, 'events': json.dumps(event)}
        for agent in ('codex', 'claude'):
            author = Author({'agent': agent}, run=run)
            self.assertEqual(author._call('Synthetic text proposal'), {'result': 'fixture'})
            author.inspect_images({'scene': 'synthetic'}, [png()])
            command = calls[-1][0]
            if agent == 'codex':
                self.assertIn('--image', command)
                self.assertIn(['--disable', 'image_generation'], [command[i:i+2] for i in range(len(command)-1)])
            else:
                self.assertEqual(command[command.index('--tools') + 1], 'Read')
                self.assertEqual(command[command.index('--allowedTools') + 1], 'Read(./inspection-*.png)')
                self.assertEqual(command[command.index('--setting-sources') + 1], '')
                self.assertIn('--restricted', command)
