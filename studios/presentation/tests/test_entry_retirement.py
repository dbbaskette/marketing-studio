"""Public retirement is checked before workspace or provider access."""
import unittest
from unittest import mock
import runner_support  # noqa: F401
from runner.engine import Engine
from workspace import WorkspaceError


class EntryRetirementTests(unittest.TestCase):
    def test_obsolete_starts_refuse_before_any_workspace_access(self):
        engine = object.__new__(Engine)
        for form in ({}, {'flow': None}, {'flow': ''}, {'flow': 'guided'},
                     *({'flow': 'desk', key: value} for key, value in
                       [('review_level', 'automatic'), ('review_seen', None),
                        ('review_default', False)])):
            with self.subTest(form=form), mock.patch.object(Engine, 'space') as space:
                with self.assertRaisesRegex(WorkspaceError, 'desk|review'):
                    engine.start(form)
                space.assert_not_called()

    def test_conversation_refuses_explicit_retired_preferences(self):
        engine = object.__new__(Engine)
        with mock.patch('runner.desk_chat._start') as start:
            for key in ('review_level', 'review_seen', 'review_default'):
                with self.subTest(key=key), self.assertRaisesRegex(WorkspaceError, 'review'):
                    engine.start({key: None}, execution='conversation')
            start.assert_not_called()
