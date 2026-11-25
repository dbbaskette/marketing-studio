"""Nothing changes a deck the earlier step-by-step flow saved except a short list of actions
(GitHub issue #542, fix round 3): one gate (`runner.saved_gate`) that every changing page
route and desk command passes refuses such a deck by default. These tests walk every route
of `RunnerPage.writes` and every desk command against stored saved decks in four states,
and pin the round's defects: Take of a deck with nothing to take it for, publishing a deck
not delivered, start-up leaving lock files, the migration's raw refusal of an unreadable
record, and start-up's handling of a deck whose record cannot be read."""
import io
import json
import re
from pathlib import Path

import runner_support
import test_runner_page
from runner import decks, desk_chat, page as pages, saved_gate, studio
from runner import engine as engines
from studio_core import sync_guard
from workspace import WorkspaceError

# What a route takes besides the deck's path, where a value of its own shape is needed.
GENERIC = {'number': 1, 'note': 'x', 'expected': 'x', 'slides': [], 'kind': 'research',
           'look': 'default', 'field': 'title', 'text': 'x', 'seen': 0, 'start': 0, 'end': 1,
           'action': 'rewrite', 'slide': 'slide-1', 'index': 0, 'ids': ['a'], 'tool': 'brand',
           'set': 'x', 'picks': [], 'document': 'x', 'title': 'Not its title'}
BODIES = {'/api/run': {'action': 'resume'}, '/api/drive': {'action': 'take'},
          '/api/decide': {'gate': 'gate:outline', 'decision': 'approve'},
          '/api/answer': {'id': 'q1', 'answer': 'An answer.'},
          '/api/desk-migrate': {'expected': 'bogus'},
          '/api/research-note': {'action': 'save', 'text': 'x'},
          '/api/slide-text-draft': {'action': 'save', 'expected': 0, 'patch': {}},
          '/api/build-feedback': {'ref': '0' * 32, 'note': 'x', 'number': 1},
          '/api/progress-seen': {'ref': '0' * 32},
          pages.SOURCE: {'text': 'A pasted source.', 'title': 'Pasted'},
          '/api/desk-outline-price': {'slides': []}}
# A server error, or an exception's own text, is never how a refusal is said.
RAW = re.compile(r'Traceback|\b\w+(Error|Exception)\b|Expecting |line \d+ column \d+')


def plain(said) -> bool:
    return isinstance(said, str) and bool(said.strip()) and not RAW.search(said)


def body(path: str) -> dict:
    sent = dict(GENERIC)
    for key in (pages.DESK.get(path) or (None, ()))[1]:
        sent.setdefault(key.rstrip('?'), 'x')
    return {**sent, **BODIES.get(path, {})}


class SavedDecks(test_runner_page.PageCase):
    """Stored saved decks in the four states the gate tells apart, beside nothing else."""

    def decks(self) -> dict:
        found = {'opens': self.load_saved('build', title='Opens'),
                 'read-only': self.load_saved('research-plan', title='Nothing made'),
                 'delivered': self.load_saved('delivered', title='Delivered earlier')}
        bad = self.load_saved('outline', title='Unreadable')
        (bad / 'run.json').write_text('{not json')
        self.git('commit', '-qam', 'A record that cannot be read')
        found['unreadable'] = bad
        return found

    def snap(self):
        repo = self.space.repo
        files = {path.relative_to(repo).as_posix(): path.read_bytes()
                 for path in sorted(repo.rglob('*'))
                 if path.is_file() and '.git' not in path.relative_to(repo).parts}
        return files, self.git('log', '--all', '--format=%H %s'), self.git('tag', '--list')

    def restore(self, before) -> None:
        """Put the workspace back as `before` had it, after an allowed change."""
        repo = self.space.repo
        head = before[1].splitlines()[0].split()[0]
        self.git('reset', '-q', '--hard', head)
        for tag in set(self.git('tag', '--list').split()) - set(before[2].split()):
            self.git('tag', '-d', tag)
        files = before[0]
        for path in sorted(repo.rglob('*')):
            relative = path.relative_to(repo)
            if path.is_file() and '.git' not in relative.parts \
                    and relative.as_posix() not in files:
                path.unlink()
        for name, data in files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_bytes(data)
        self.engine._checks.clear()

    def call(self, path: str, sent: dict):
        """(status, what it said). An exception the page does not answer is a server
        error."""
        try:
            status, _, data, _ = self.raw('POST', path, json.dumps(sent).encode(),
                                          origin=self.origin, kind='application/json')
        except Exception as failure:   # the real page would answer 500
            return 500, f'{type(failure).__name__}: {failure}'
        said = json.loads(data).get('error') if status >= 300 else None
        return status, said


class RouteWalkTests(SavedDecks):
    STATES = {'opens': 'saved', 'read-only': 'saved', 'delivered': 'finished',
              'unreadable': 'unreadable'}

    def test_every_changing_route_has_a_decision(self):
        # A route added without a decision fails here.
        self.assertEqual(set(pages.RunnerPage.writes), set(pages.SAVED_ROUTES))

    def test_every_route_is_allowed_for_the_state_or_refused_in_plain_words_changing_nothing(self):
        found = self.decks()
        for name, root in found.items():
            self.assertEqual(saved_gate.standing(self.engine, root), self.STATES[name], name)
        cases = [(path, body(path)) for path in pages.RunnerPage.writes]
        cases.append(('/api/drive', {**body('/api/drive'), 'action': 'hand-over'}))
        for name, root in found.items():
            state = self.STATES[name]
            for path, sent in cases:
                with self.subTest(deck=name, route=path, action=sent.get('action')):
                    decision = pages.SAVED_ROUTES[path]
                    if decision == saved_gate.WORKSPACE:
                        # About no deck, decided so in SAVED_ROUTES: such a route reads
                        # `path`, where it reads it at all, as something else (the
                        # workspace's own folder for /api/setup, a folder to bring in for
                        # /api/bring), so it is not sent a deck's.
                        self.assertNotIn(path, [*pages.DESK, '/api/run', '/api/drive'])
                        continue
                    sent = {**sent, 'path': str(root)}
                    prefix = root.relative_to(self.space.repo).as_posix() + '/'

                    def folder(snapshot):
                        return {key: value for key, value in snapshot[0].items()
                                if key.startswith(prefix)}
                    before = self.snap()
                    status, said = self.call(path, sent)
                    after = self.snap()
                    self.assertLess(status, 500, said)
                    if status >= 300:
                        self.assertTrue(plain(said), said)
                    if saved_gate.allowed(decision, state, sent):
                        pass    # on the allow-list for this state
                    else:
                        self.assertGreaterEqual(status, 400, said)
                        self.assertEqual(after, before)
                    if after != before:
                        self.restore(before)


class CommandWalkTests(SavedDecks):
    STATES = RouteWalkTests.STATES

    def commands(self) -> list[str]:
        """Every desk command the command line has, read from its parser."""
        desk = studio.parser()._subparsers._group_actions[0].choices['desk']
        return list(desk._subparsers._group_actions[0].choices)

    def test_every_desk_command_has_a_decision(self):
        self.assertEqual(set(self.commands()), set(studio.SAVED_COMMANDS))

    def test_every_command_is_allowed_for_the_state_or_refused_in_plain_words_changing_nothing(self):
        found = self.decks()
        given = self.base / 'given.json'
        given.write_text(json.dumps({'expected_basis': 'x', 'scope': ['outline']}))
        for name, root in found.items():
            state = self.STATES[name]
            for action in self.commands():
                if action == 'create':
                    continue    # about no deck
                with self.subTest(deck=name, command=action):
                    argv = ['desk', action, '--folder', str(root)]
                    if action not in ('show', 'context', 'migration-preview', 'migrate'):
                        argv += ['--input', str(given)]
                    if action == 'context':
                        argv += ['--target', 'outline']
                    if action == 'migrate':
                        argv += ['--expected', 'bogus']
                    args = studio.parser().parse_args(argv)
                    before = self.snap()
                    said = None
                    try:
                        studio.desk_command(args, make=lambda: self.engine, out=io.StringIO())
                    except WorkspaceError as refusal:
                        said = str(refusal)
                    after = self.snap()
                    if said is not None:
                        self.assertTrue(plain(said), said)
                    if not saved_gate.allowed(studio.SAVED_COMMANDS[action], state, {}):
                        self.assertIsNotNone(said)
                        self.assertEqual(after, before)
                    if after != before:
                        self.restore(before)


class SavedDeckDefectTests(SavedDecks):
    def test_a_saved_deck_not_delivered_is_not_published(self):
        found = self.decks()
        for name in ('opens', 'read-only'):
            before = self.snap()
            with self.assertRaises(WorkspaceError) as refused:
                self.engine.publish(found[name])
            self.assertEqual(str(refused.exception), engines.SAVED_FLOW_ENDED)
            self.assertEqual(self.snap(), before)
        # A delivered one is published as before.
        made = self.engine.publish(found['delivered'])
        self.assertEqual(made['revision'], 1)
        self.assertTrue(self.git('tag', '--list'))

    def test_an_unreadable_record_is_refused_by_the_migration_in_plain_words(self):
        bad = self.decks()['unreadable']
        before = self.snap()
        # The engine's own refusal (the route and the command reach it when the gate lets
        # them through).
        with self.assertRaises(WorkspaceError) as refused:
            desk_chat.migrate(self.engine, bad, 'bogus')
        self.assertTrue(plain(str(refused.exception)), str(refused.exception))
        self.assertIn('cannot be read', str(refused.exception))
        status, said = self.call('/api/desk-migrate', {'path': str(bad), 'expected': 'bogus'})
        self.assertEqual(status, 409, said)
        self.assertTrue(plain(said), said)
        args = studio.parser().parse_args(['desk', 'migrate', '--folder', str(bad),
                                           '--expected', 'bogus'])
        with self.assertRaises(WorkspaceError) as refused:
            studio.desk_command(args, make=lambda: self.engine, out=io.StringIO())
        self.assertTrue(plain(str(refused.exception)), str(refused.exception))
        self.assertEqual(self.snap(), before)


class SavedLockTests(runner_support.DeskCase):
    LOCKS = (engines.IN_HAND, 'work/.harness-slides/design/.lock', '.studio-research/lock',
             '.training-studio/step.lock', 'work/renders/x/.studio-research/lock',
             'sources/y/.harness-slides/design/.lock')

    def test_start_up_removes_each_lock_a_saved_deck_was_left_with(self):
        for locks in [(name,) for name in self.LOCKS] + [self.LOCKS]:
            with self.subTest(locks=locks):
                root = self.load_saved('research-plan', title='Locked ' + str(len(locks)))
                kept = {path.relative_to(root).as_posix(): path.read_bytes()
                        for path in root.rglob('*') if path.is_file()}
                for name in locks:
                    (root / name).parent.mkdir(parents=True, exist_ok=True)
                    (root / name).write_text('x\n')
                self.assertTrue(sync_guard.worker_in_progress(self.space.repo))
                self.engine.resume()
                self.assertFalse(sync_guard.worker_in_progress(self.space.repo))
                # Lock files only: everything else in the folder is as it was.
                self.assertEqual({path.relative_to(root).as_posix(): path.read_bytes()
                                  for path in root.rglob('*') if path.is_file()}, kept)

    def test_a_lock_of_a_step_this_process_runs_is_kept(self):
        root = self.load_saved('build', title='Running')
        lock = root / 'work/.harness-slides/design/.lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text('x\n')
        self.engine._active_steps.add(str(root))
        try:
            self.engine.resume()
            self.assertTrue(lock.exists())
        finally:
            self.engine._active_steps.discard(str(root))

    def test_a_desk_deck_whose_record_cannot_be_read_loses_only_its_markers(self):
        # Beyond 8c5e4524, as ruled and documented: a leftover marker on a deck nobody can
        # load would hold the whole workspace for good.
        root = self.start_desk(look='default')
        self.waiting(root)
        (root / 'run.json').write_text('{not json')
        (root / engines.IN_HAND).write_text('outline\n')
        (root / 'work/.harness-slides/design').mkdir(parents=True, exist_ok=True)
        (root / 'work/.harness-slides/design/.lock').write_text('x\n')
        kept = {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}
        self.engine.resume()
        del kept[engines.IN_HAND], kept['work/.harness-slides/design/.lock']
        self.assertEqual({path.relative_to(root).as_posix(): path.read_bytes()
                          for path in root.rglob('*') if path.is_file()}, kept)

    def test_a_desk_deck_keeps_what_start_up_did_for_it_before(self):
        root = self.start_desk(look='default')
        self.waiting(root)
        lock = root / 'work/.harness-slides/design/.lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text('x\n')
        self.engine.resume()
        self.assertTrue(lock.exists())     # as 8c5e4524 left it: the desk settles it


class SavedLockTeamTests(runner_support.DeskCase, runner_support.TeamCase):
    def test_after_start_up_a_desk_deck_shares_starts_and_edits_beside_a_locked_saved_deck(self):
        locked = self.load_saved('research-plan', title='Locked')
        form = {**runner_support.FORM, 'flow': 'desk', 'scope': ['outline']}
        desk_deck = Path(desk_chat.create(self.engine, form)['path'])
        self.engine.share()
        for name in SavedLockTests.LOCKS:
            (locked / name).parent.mkdir(parents=True, exist_ok=True)
            (locked / name).write_text('x\n')
        self.engine.resume()
        self.assertFalse(sync_guard.worker_in_progress(self.space.repo))
        self.assertTrue(self.engine.share()['shared'])
        self.assertTrue(Path(desk_chat.create(self.engine, form)['path']).is_dir())
        self.assertEqual(desk_chat._root(self.engine, desk_deck, change=True)[0], desk_deck)
        # Another saved deck beside it opens on the desk: nothing holds the workspace.
        beside = self.load_saved('build', title='Beside')
        self.assertEqual(self.engine.saved_check(beside)['saved_record']['waiting'], [])


class SavedTakeGuardTests(runner_support.DeskCase, runner_support.TeamCase):
    def snap(self, repo: Path):
        files = {path.relative_to(repo).as_posix(): path.read_bytes()
                 for path in sorted(repo.rglob('*'))
                 if path.is_file() and '.git' not in path.relative_to(repo).parts}
        return files, self.git('log', '--all', '--format=%H %s', repo=repo)

    def test_a_deck_with_nothing_to_take_it_for_is_not_taken(self):
        # The reviewer's probe: a read-only deck was taken, rewritten, committed and pushed.
        root = self.load_saved('research-plan', title='Nothing made')
        self.engine.share()
        other = self.theirs(self.blake, root)
        with self.be(self.blake):
            self.blake.engine.fetch()
            before, sent = self.snap(self.blake.space.repo), self.shared()
            with self.assertRaises(WorkspaceError) as refused:
                self.blake.engine.drive(other, 'take')
            self.assertEqual(str(refused.exception), engines.NOTHING_TO_TAKE)
            self.assertEqual(self.snap(self.blake.space.repo), before)
            self.assertEqual(self.shared(), sent)

    def test_a_delivered_deck_is_taken_to_open_it_on_the_desk(self):
        root = self.load_saved('delivered', title='Delivered earlier')
        self.engine.share()
        other = self.theirs(self.blake, root)
        with self.be(self.blake):
            self.blake.engine.fetch()
            self.blake.engine.drive(other, 'take')
            self.assertEqual(decks.read_run(other)['driver']['name'], 'Blake')
