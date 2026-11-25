"""Nothing changes a saved record but what is named (GitHub issue #542).

A saved record (a training the earlier step-by-step flow saved) is refused by default at the
one place every changing route passes through (`RunnerPage.saved_gate`), at the desk
command line (`studio desk`) and at the helper's write guard (`training.py`). Only the
explicit opening on the desk, the finished Open on the desk, Take over, Delete, Start new
work from this, Publish and Bring in are allowed. Every changing route is walked here, for a
saved record that opens on the desk, one that is read-only and one that is finished: each is
allowed by name, or refuses with the sentence that names the two ways on, with the training's
folder byte for byte as it was and nothing committed. A route added without a decision here
fails this test.
"""
import contextlib
import io
import json

import helpers  # noqa: F401
import saved_fixtures
import training
from runner_support import StudioCase
from runner import engine as engines, page, studio

STATES = ('blueprint-gate', 'research-plan-gate', 'finished')
# Every changing route the page serves that is not allowed: each refuses a saved record.
REFUSED = (
    '/api/answer', '/api/approval', '/api/asset', '/api/brand', '/api/brand/install',
    '/api/companions', '/api/computer', '/api/copies', '/api/decide', '/api/documents',
    '/api/documents-library', '/api/documents-library-keep', '/api/documents-library-update',
    '/api/drafts/apply', '/api/drafts/deck-brand', '/api/drafts/deck-brand-copy',
    '/api/drafts/deck-note', '/api/drafts/deck-outline', '/api/drafts/deck-outline-price',
    '/api/drafts/deck-stop', '/api/drafts/doc', '/api/drafts/draft', '/api/drafts/draw-here',
    '/api/drafts/finding', '/api/drafts/finish', '/api/drafts/keep', '/api/drafts/layout',
    '/api/drafts/level-ready', '/api/drafts/library-keep', '/api/drafts/look',
    '/api/drafts/look-samples', '/api/drafts/note', '/api/drafts/ready', '/api/drafts/restore',
    '/api/drafts/retry', '/api/drafts/reviewed-ready', '/api/drafts/revise', '/api/drafts/save',
    '/api/drafts/selection', '/api/drafts/send', '/api/drafts/share', '/api/drafts/skip',
    '/api/drafts/slide-note', '/api/drafts/slide-restore', '/api/drafts/slide-selection',
    '/api/drafts/slide-selection-settle', '/api/drafts/slide-speaker-notes',
    '/api/drafts/slide-words', '/api/drafts/slide-words-decide', '/api/drafts/source',
    '/api/drafts/stop', '/api/drafts/stop-updates', '/api/drafts/update',
    '/api/drafts/update-all', '/api/drafts/write-whole', '/api/fetch', '/api/intake-draft',
    '/api/library', '/api/library-document', '/api/library-filters', '/api/library-matching',
    '/api/note', '/api/outline', '/api/outline-flow', '/api/redesign', '/api/research-decision',
    '/api/research-note', '/api/research-site', '/api/research-sources', '/api/restart',
    '/api/run', '/api/setup', '/api/setup/check', '/api/share', '/api/shared',
    '/api/slide-text-draft', '/api/training-models', '/api/training-plan',
    '/api/training-settings', '/api/training-settings/sources', '/api/trainings',
    '/api/upgrade', '/api/versions')
# Desk commands that change a training, and those that only read it or open it on the desk.
DESK_CHANGING = ('save', 'submit', 'scope', 'handoff', 'take', 'answer', 'ready',
                 'return-delivered')
DESK_OTHER = ('create', 'show', 'context', 'migration-preview', 'migrate')


class SavedGuardTests(StudioCase):
    def folder(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob('*')) if path.is_file()}

    def assert_untouched(self, root, before, head, said):
        self.assertEqual(self.folder(root), before, said)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head, said)

    def test_every_changing_route_is_decided(self):
        writes = set(page.RunnerPage.writes)
        self.assertEqual(writes - set(page.SAVED_ALLOWED) - set(REFUSED), set(),
                         'a changing route has no decision for a saved record')
        self.assertEqual(set(REFUSED) & set(page.SAVED_ALLOWED), set())

    def test_each_route_refuses_a_saved_record_unless_it_is_allowed(self):
        native = page.RunnerPage(8765, self.engine)
        for state in STATES:
            root = saved_fixtures.load(self, state)
            path = str(root)
            for route in sorted(page.RunnerPage.writes):
                with self.subTest(state=state, route=route):
                    body = {'path': path, 'action': 'change', 'name': 'blueprint',
                            'level': '', 'expected': 'x'}
                    if route in page.SAVED_ALLOWED:
                        native.saved_gate(route, {**body, 'action': 'take'})
                        continue
                    before, head = self.folder(root), self.git('rev-parse', 'HEAD')
                    with self.assertRaises(page.desk.Refusal) as caught:
                        native.write(route, body)
                    self.assertEqual((caught.exception.status, str(caught.exception)),
                                     (409, engines.SAVED_ONLY))
                    self.assert_untouched(root, before, head, route)
            # Hand over is never allowed on a saved record, though Take over is.
            before, head = self.folder(root), self.git('rev-parse', 'HEAD')
            with self.assertRaises(page.desk.Refusal) as caught:
                native.write('/api/drive', {'path': path, 'action': 'hand-over'})
            self.assertEqual(str(caught.exception), engines.SAVED_ONLY)
            self.assert_untouched(root, before, head, 'hand-over')

    def test_a_folder_a_runner_made_outside_the_workspace_is_not_a_conversation_training(self):
        root = saved_fixtures.load(self, 'blueprint-gate')
        outside = self.base / 'outside' / root.name
        import shutil
        shutil.copytree(root, outside)
        native = page.RunnerPage(8765, self.engine)
        before = self.folder(outside)
        for route in ('/api/decide', '/api/approval'):
            with self.subTest(route=route), self.assertRaises(page.desk.Refusal) as caught:
                native.write(route, {'path': str(outside), 'artifact': 'blueprint',
                                     'decision': 'approve', 'mode': 'chat'})
            self.assertEqual(str(caught.exception), engines.SAVED_ONLY)
        self.assertEqual(self.folder(outside), before)

    def test_desk_commands_that_change_a_training_refuse_a_saved_record(self):
        listed = studio.parser()._subparsers._group_actions[0].choices['desk']
        actions = set(listed._subparsers._group_actions[0].choices)
        self.assertEqual(actions, set(DESK_CHANGING) | set(DESK_OTHER),
                         'a desk command has no decision for a saved record')
        given = self.base / 'input.json'
        given.write_text(json.dumps({'expected_basis': 'x', 'scope': ['part']}))
        for state in STATES:
            root = saved_fixtures.load(self, state)
            for action in DESK_CHANGING:
                with self.subTest(state=state, action=action):
                    before, head = self.folder(root), self.git('rev-parse', 'HEAD')
                    args = studio.parser().parse_args(['desk', action, '--folder', str(root),
                                                       '--input', str(given)])
                    with self.assertRaises(page.WorkspaceError) as caught:
                        studio.desk_command(args, make=self.make, out=io.StringIO())
                    self.assertEqual(str(caught.exception), engines.SAVED_ONLY)
                    self.assert_untouched(root, before, head, action)

    def test_the_helper_never_writes_a_training_a_runner_made(self):
        for state in STATES:
            root = saved_fixtures.load(self, state)
            for argv in (['approve', 'blueprint'], ['skip', 'deck', '--reason', 'Not needed.'],
                         ['checkpoint', '--next', 'Something else'],
                         ['save', 'blueprint', '--built'],
                         ['pin', 'harness-research', '--task', 'x']):
                with self.subTest(state=state, argv=argv):
                    before, head = self.folder(root), self.git('rev-parse', 'HEAD')
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        code = training.main(['--dir', str(root), *argv])
                    self.assertEqual(code, 2, out.getvalue())
                    self.assertIn('earlier step-by-step flow', json.loads(out.getvalue())['error'])
                    self.assert_untouched(root, before, head, ' '.join(argv))


from test_runner_deck import DeckCase  # noqa: E402


class SavedDeckGuardTests(DeckCase):
    """The reviewer's probes: drawing a saved deck again from a design, adding a picture to
    it, and handing it over each refuse it, and change nothing in its folder."""

    folder = SavedGuardTests.folder

    def test_a_saved_deck_is_never_drawn_again_given_a_picture_or_handed_over(self):
        self.slides.design = True
        native = page.RunnerPage(8765, self.engine)
        for state in ('deck-gate-waiting', 'deck-outline-waiting', 'deck-look-waiting',
                      'google-deck-drawn'):
            root = saved_fixtures.load(self, state)
            for route, body in (
                    ('/api/redesign', {'path': str(root), 'level': ''}),
                    ('/api/asset', {'path': str(root), 'asset': 'console_view',
                                    'content': 'iVBORw0KGgo=', 'alt': 'A console',
                                    'source': 'Course author'}),
                    ('/api/drive', {'path': str(root), 'action': 'hand-over'})):
                with self.subTest(state=state, route=route):
                    before, head = self.folder(root), self.git('rev-parse', 'HEAD')
                    with self.assertRaises(page.desk.Refusal) as caught:
                        native.write(route, body)
                    self.assertEqual(str(caught.exception), engines.SAVED_ONLY)
                    self.assertEqual(self.folder(root), before)
                    self.assertEqual(self.git('rev-parse', 'HEAD'), head)
