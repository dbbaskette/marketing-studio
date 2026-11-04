"""Private unfinished forms: disposable workspaces, no assistant or team operations."""

import isolation  # noqa: F401
from unittest.mock import patch

import management
from studio_core.intake_drafts import Conflict
from test_desk import DRAFT, RouteCase


class IntakeTests(RouteCase):
    def test_restore_step_sources_and_preferences_without_creating_a_blog(self):
        before = list(self.root.rglob('*'))
        self.assertEqual(self.get('intake-draft'), {'revision': 0, 'draft': None})
        self.assertEqual(list(self.root.rglob('*')), before)
        value = {
            'title': 'Synthetic brief',
            'step': 1,
            'audience': 'Operators',
            'point': 'Keep unfinished work',
            'operation': 'a' * 32,
            'files': [{'id': 'selected', 'library': True}],
            'sourceDraft': {'id': 'capture', 'expected': 2},
            'tone': 'Plain',
        }
        with patch.object(
            management, 'authorize_write', side_effect=AssertionError('No team access check')
        ):
            saved = self.post('intake-draft', {'action': 'save', 'expected': 0, 'patch': value})
        self.assertEqual(self.get('intake-draft')['draft'], value)
        self.assertEqual(list(self.root.rglob('*')), before)
        with self.assertRaises(Conflict):
            self.post(
                'intake-draft', {'action': 'save', 'expected': 0, 'patch': {'title': 'Stale'}}
            )
        with self.assertRaises(ValueError):
            self.post(
                'intake-draft',
                {'action': 'save', 'expected': saved['revision'], 'patch': {'token': 'excluded'}},
            )
        self.post('intake-draft', {'action': 'discard', 'expected': saved['revision']})
        self.assertIsNone(self.get('intake-draft')['draft'])

    def test_stale_start_is_refused_and_repeated_current_start_is_idempotent(self):
        operation = 'b' * 32
        saved = self.post(
            'intake-draft',
            {
                'action': 'save',
                'expected': 0,
                'patch': {'title': 'Synthetic', 'operation': operation, 'step': 1},
            },
        )
        start = {'operation': operation, 'title': 'Synthetic', 'manuscript': DRAFT}
        for revision in (None, 0):
            with self.assertRaises(Conflict):
                self.post('desk-create', {**start, 'intake_revision': revision})
        first = self.post('desk-create', {**start, 'intake_revision': saved['revision']})
        again = self.post('desk-create', {**start, 'intake_revision': saved['revision']})
        self.assertEqual(first['id'], again['id'])
        self.assertEqual(first['markdown'], DRAFT)
        self.assertEqual(management.failure(Conflict('Changed'), writing=True)[0], 409)
