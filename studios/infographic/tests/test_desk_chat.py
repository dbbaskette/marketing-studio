"""The companion conversation's checked, bounded desk operations (desk_chat.py)."""
from copy import deepcopy
import json
import threading
from unittest import mock

from helpers import Isolated
import test_desk_engine as fixtures
from runner import api, desk_chat, server
from runner.contracts import Invalid


class DeskChatTests(Isolated):
    def setUp(self):
        super().setUp()
        fixtures.setup_desk(self)
        self.engine.assistant = None     # a conversation writes its own work: no nested assistant

    def current(self):
        return self.store.read(self.ident)

    def test_show_names_what_can_be_written_and_starts_nothing(self):
        shown = desk_chat.show(self.store, self.ident)
        self.assertEqual(shown['targets'], ['facts', 'stories', 'story:story1'])
        self.assertEqual((shown['selected_story']['id'], shown['page']['elements'] > 0), ('story1', True))
        self.assertEqual(shown['submissions'], [])
        self.renderer.assert_not_called()

    def test_a_story_revision_lands_only_on_the_inputs_its_context_named(self):
        context = desk_chat.context(self.store, self.ident, 'story:story1')
        self.assertEqual(context['kind'], 'story')
        self.assertIn('story', context['inputs'])
        self.assertTrue(context['instructions'])
        revised = deepcopy(context['inputs']['story'])
        revised['takeaway'] = 'Keep the other instances serving while one restarts.'
        shown = desk_chat.submit(self.engine, self.ident, {'kind': 'story', 'target': 'story:story1',
                                                           'expected_basis': context['expected_basis'],
                                                           'payload': {'story': revised}})
        project = self.current()
        self.assertEqual(project['stories'][0]['takeaway'], revised['takeaway'])
        # Saving never chooses a story, approves, builds or renders.
        self.assertIsNone(project['selected_story'])
        self.assertIsNone(project['approval'])
        self.renderer.assert_not_called()
        self.assertEqual([(s['kind'], s['target'], s['by']) for s in shown['submissions']],
                         [('story', 'story:story1', 'conversation')])
        # The same context again is out of date: it is refused, and nothing changes.
        before = self.current()
        with self.assertRaisesRegex(Invalid, 'changed. Read desk context again'):
            desk_chat.submit(self.engine, self.ident, {'kind': 'stories', 'target': 'stories',
                                                       'expected_basis': context['expected_basis'],
                                                       'payload': {'stories': [revised]}})
        self.assertEqual(self.current(), before)

    def test_submissions_are_checked_by_the_native_rules(self):
        context = desk_chat.context(self.store, self.ident, 'story:story1')
        changed_id = dict(context['inputs']['story'], id='another')
        cases = [
            ({'kind': 'stories', 'target': 'story:story1', 'payload': {'story': changed_id}}, 'does not match its target'),
            ({'kind': 'story', 'target': 'story:story1', 'payload': {'story': changed_id}}, 'keeping its id'),
            ({'kind': 'story', 'target': 'story:missing', 'payload': {}}, 'existing story'),
            ({'kind': 'story', 'target': 'approve', 'payload': {}}, 'Choose facts, stories'),
            ({'kind': 'story', 'target': 'story:story1', 'payload': {'story': 'x' * 2_100_000}}, 'too large'),
        ]
        before = self.current()
        for sent, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(Invalid, message):
                desk_chat.submit(self.engine, self.ident, {**sent, 'expected_basis': context['expected_basis']})
        with self.assertRaisesRegex(Invalid, 'Submit kind, target'):
            desk_chat.submit(self.engine, self.ident, {'kind': 'story', 'target': 'story:story1', 'payload': {}})
        self.assertEqual(self.current(), before)

    def test_only_the_person_keeps_out_of_date_work_and_a_story_saved_again_stays_marked(self):
        project = self.current()
        self.store.edit_brief(self.ident, {**project['brief'], 'audience': 'Operators'}, expected_revision=project['revision'])
        shown = desk_chat.show(self.store, self.ident)
        self.assertEqual(set(shown['stale']), {'stories', 'page'})
        self.assertFalse(any(t.startswith('stale:') for t in shown['targets']))
        with self.assertRaisesRegex(Invalid, 'Only the person keeps out-of-date work'):
            desk_chat.context(self.store, self.ident, 'stale:page')
        # Saving the same story again is not making it again: its mark stays.
        context = desk_chat.context(self.store, self.ident, 'story:story1')
        desk_chat.submit(self.engine, self.ident, {'kind': 'story', 'target': 'story:story1',
                                                   'expected_basis': context['expected_basis'],
                                                   'payload': {'story': context['inputs']['story']}})
        self.assertEqual(set(self.current()['stale']), {'stories', 'page'})

    def test_submissions_listed_are_bounded(self):
        from runner.contracts import canonical
        with self.store.locked():
            for n in range(30):
                self.store.write_blob(self.ident, f'jobs/conversation_{n:04d}/submission.json',
                                      canonical({'schema': 1, 'kind': 'story', 'target': 'story:story1',
                                                 'by': 'conversation', 'basis': 'b', 'revision': 1,
                                                 'at': f'2026-11-24T00:{n:02d}:00Z'}))
        shown = desk_chat.show(self.store, self.ident)['submissions']
        self.assertEqual(len(shown), desk_chat.SHOWN)
        self.assertEqual(shown[0]['at'], '2026-11-24T00:29:00Z')

    def test_page_endpoints_and_no_saving_while_work_runs(self):
        page = server.Page(8000, self.store, self.engine)
        self.addCleanup(page.actions.shutdown)
        status, _, raw = page.write('/api/desk-context', {'id': self.ident, 'target': 'stories'})
        self.assertEqual(status, 200)
        context = json.loads(raw)
        shown = json.loads(page.read('/api/desk-show', lambda name: self.ident)[2])
        self.assertEqual(shown['revision'], self.current()['revision'])
        entered, release = threading.Event(), threading.Event()
        def slow(found, sent):
            entered.set(); release.wait(5); return {}
        with mock.patch.object(api, 'action', side_effect=slow):
            page.write('/api/action', {'action': 'suggest', 'id': self.ident, 'expected_revision': self.current()['revision']})
            self.assertTrue(entered.wait(3))
            with self.assertRaisesRegex(Invalid, 'still working'):
                page.write('/api/desk-submit', {'id': self.ident, 'kind': 'stories', 'target': 'stories',
                                                'expected_basis': context['expected_basis'],
                                                'payload': {'stories': context['inputs'].get('stories', [])}})
            release.set()
