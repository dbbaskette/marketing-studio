"""Read-only status polling cannot compete for optional index refresh locks."""
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock
import helpers
import hub


class GitPollingTests(unittest.TestCase):
    def test_status_disables_optional_index_refresh_and_writers_keep_their_environment(self):
        with mock.patch.dict(os.environ, {'GIT_OPTIONAL_LOCKS': '1'}), mock.patch.object(hub.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            hub.run(Path('/tmp/disposable-git-polling'), '-c', 'core.autocrlf=false', 'status', '--porcelain')
            self.assertEqual(run.call_args.kwargs['env']['GIT_OPTIONAL_LOCKS'], '0')
            hub.run(Path('/tmp/disposable-git-polling'), 'add', '-A')
            self.assertEqual(run.call_args.kwargs['env']['GIT_OPTIONAL_LOCKS'], '1')
