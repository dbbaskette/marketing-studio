"""Presentation Studio's parameters for the shared engine-lock contract."""
import sys
import unittest

import helpers
import runner_support
from runner import engine as engines, gitstate

# Shared test resources live outside the independently runnable product packages.
shared_tests = str(helpers.REPO.parents[1] / 'tests')
if shared_tests not in sys.path:
    sys.path.append(shared_tests)
from deck_process_lock_cases import EngineProcessLockCases, ChangedWorkspaceStartCases


class EngineProcessLockTests(EngineProcessLockCases, unittest.TestCase):
    helpers = helpers
    engines = engines
    gitstate = gitstate
    record_path = 'run.json'
    marker_path = 'work/step.lock'


class ChangedWorkspaceStartTests(ChangedWorkspaceStartCases, runner_support.StudioCase):
    gitstate = gitstate
