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
from pathlib import Path

import helpers  # noqa: F401
import saved_fixtures
import training
import workspace
from runner_support import StudioCase
from runner import engine as engines, page, studio

STATES = ('blueprint-gate', 'research-plan-gate', 'finished')
# Every changing route the page serves that is not allowed: each refuses a saved record.
REFUSED = (
    '/api/answer', '/api/asset', '/api/brand', '/api/brand/install',
    '/api/companions', '/api/computer', '/api/copies', '/api/documents',
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
                        # Two allowed routes depend on what the record holds: Take over only
                        # where it would open on the desk, publish only a finished one.
                        refused = {'/api/drive': engines.NOTHING_TO_TAKE
                                   if state == 'research-plan-gate' else None,
                                   '/api/publish': engines.SAVED_ONLY
                                   if state != 'finished' else None}.get(route)
                        before, head = self.folder(root), self.git('rev-parse', 'HEAD')
                        if refused is None:
                            native.saved_gate(route, {**body, 'action': 'take'})
                        else:
                            with self.assertRaises(page.desk.Refusal) as caught:
                                native.write(route, {**body, 'action': 'take'})
                            self.assertEqual((caught.exception.status, str(caught.exception)),
                                             (409, refused))
                        self.assert_untouched(root, before, head, route)
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
        # The gate's decisions that once reached such a folder are gone (GitHub issue
        # #547); every changing route that names it still refuses it.
        for route in ('/api/copies', '/api/documents', '/api/note'):
            with self.subTest(route=route), self.assertRaises(page.desk.Refusal) as caught:
                native.write(route, {'path': str(outside), 'action': 'done'})
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

    def helper(self, root, argv) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = training.main(['--dir', str(root), *argv])
        self.assertEqual(code, 2, out.getvalue())
        return json.loads(out.getvalue())['error']

    def test_the_helper_never_writes_a_training_a_runner_made(self):
        import write_guard
        for state in STATES:
            root = saved_fixtures.load(self, state)
            # Nothing continues a saved record (GitHub issue #547): every helper command
            # that writes answers that its saved flow no longer continues.
            for argv in (['approve', 'blueprint'], ['skip', 'deck', '--reason', 'Not needed.'],
                         ['checkpoint', '--next', 'Something else'],
                         ['save', 'blueprint', '--built'],
                         ['pin', 'harness-research', '--task', 'x'],
                         ['google', 'push', 'document', '--prepare',
                          str(self.base / 'send.md')]):
                with self.subTest(state=state, argv=argv):
                    before, head = self.folder(root), self.git('rev-parse', 'HEAD')
                    said = self.helper(root, argv)
                    self.assertEqual(said, write_guard.SAVED_RUNNER)
                    self.assert_untouched(root, before, head, ' '.join(argv))

    def test_the_helper_never_writes_a_training_a_conversation_made(self):
        """GitHub issue #547: a conversation's training is a saved record too; the helper
        changes nothing in it."""
        import write_guard
        for state in ('conversation-blueprint-gate', 'conversation-finished'):
            top = saved_fixtures.conversation(self, state)
            for argv in (['approve', 'blueprint'], ['save', 'blueprint', '--built'],
                         ['checkpoint', '--next', 'Something else'],
                         ['export', 'document'], ['pin', 'harness-research', '--task', 'x'],
                         ['google', 'push', 'document', '--prepare',
                          str(self.base / 'send.md')]):
                with self.subTest(state=state, argv=argv):
                    before = self.folder(top)
                    said = self.helper(top, argv)
                    self.assertEqual(said, write_guard.SAVED_CONVERSATION
                                     if argv[0] == 'google' else training.ENDED)
                    self.assertEqual(self.folder(top), before)
        # ENDED is one plain sentence, said only for a training a conversation made.
        self.assertEqual(training.ENDED.count('. '), 0)
        self.assertTrue(training.ENDED.endswith('.'))

    def desk_training(self, **changes):
        """A desk training this computer drives, finished by the runner."""
        root = self.start(materials=['document', 'brief', 'scenario'], **changes)
        self.to_end(root)
        return root

    def run_helper(self, root, argv) -> tuple[int, dict]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = training.main(['--dir', str(root), *argv])
        return code, json.loads(out.getvalue())

    def test_a_desk_training_keeps_the_helper_commands_desk_work_used(self):
        """GitHub issue #547, ruling 2(a): `save` (a hand edit; the Google conflict and
        unplaced-comment recovery), `checkpoint` (copies, levels) and `export` work on a desk
        training this computer drives exactly as before the conversation's way of working
        went. The others never changed a desk training: they say the desk's own way, and
        change nothing."""
        root = self.desk_training(copies=['word'])
        guide = root / 'document.md'
        guide.write_text(guide.read_text() + '\nA comment put back by hand.\n')
        code, said = self.run_helper(root, ['save', 'document'])
        self.assertEqual((code, said['artifact']), (0, 'document'))
        self.assertEqual(said['sha256'], workspace.sha256_file(guide))
        scratch = self.base / 'rebuilt.md'
        scratch.write_text('# Learner guide\n\nRebuilt.\n')
        self.assertEqual(self.run_helper(root, ['save', 'document', '--from', str(scratch)])[0], 0)
        self.assertEqual(guide.read_text(), scratch.read_text())
        code, said = self.run_helper(root, ['checkpoint', '--copies', 'word', 'google'])
        self.assertEqual((code, sorted(said['settings']['copies'])), (0, ['google', 'word']))
        code, said = self.run_helper(root, ['export', 'document', '--unavailable',
                                            '--reason', 'No pandoc here'])
        self.assertEqual(code, 0, said)
        for argv in (['approve', 'document'], ['skip', 'yoodli', '--clear'],
                     ['skip', 'deck', '--unavailable', '--reason', 'No slides'],
                     ['pin', 'harness-slides', '--task', 't-1'],
                     ['research-import', '--case', str(self.base)]):
            with self.subTest(argv=argv):
                before = self.folder(root)
                self.assertEqual(self.helper(root, argv), training.DESK_WAY[argv[0]])
                self.assertEqual(self.folder(root), before)
        levelled = self.desk_training(levels=['101'], title='Two levels')
        code, said = self.run_helper(levelled, ['checkpoint', '--add-level', '301'])
        self.assertEqual((code, said['levels']), (0, ['101', '301']))

    def test_the_guidance_names_no_helper_command_desk_work_is_refused(self):
        """GitHub issue #547, ruling 2(b): every helper command SKILL.md and the references
        tell a reader to run is one that works for desk work. The removed ones, which answer
        a desk training with the desk's own way, and the retired `init` are never named; and
        each one named is a command the helper has."""
        import re
        skill = Path(training.__file__).resolve().parents[1]
        named = {}
        for path in [skill / 'SKILL.md', *sorted((skill / 'references').rglob('*.md'))]:
            for found in re.finditer(r'training\.py\s+([a-z][a-z-]*)', path.read_text()):
                named.setdefault(found.group(1), set()).add(path.name)
        known = set(training.parser()._subparsers._group_actions[0].choices)
        self.assertTrue(named)
        for command, files in sorted(named.items()):
            with self.subTest(command=command, files=sorted(files)):
                self.assertIn(command, known)
                self.assertNotIn(command, (*training.ENDED_COMMANDS, 'init'))
        # What desk work keeps is what the desk test above runs.
        self.assertLessEqual(set(named) & {'save', 'checkpoint', 'export'},
                             set(training.DESK_COMMANDS))

    def test_desk_work_owned_by_a_conversation_keeps_its_own_way(self):
        """As before: a desk training a conversation works on is changed only through the
        checked desk operations; the helper says so."""
        root = self.desk_training()
        record = workspace.read_run(root)
        record['execution'] = 'conversation'
        workspace.write_run(root, record)
        before = self.folder(root)
        for argv in (['save', 'document'], ['checkpoint', '--next', 'x'],
                     ['export', 'document']):
            with self.subTest(argv=argv):
                self.assertIn('being worked on in conversation', self.helper(root, argv))
        self.assertEqual(self.helper(root, ['approve', 'document']),
                         training.DESK_WAY['approve'])
        self.assertEqual(self.folder(root), before)


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
