"""Mark reviewed materials ready on the Training Studio desk (issue #516): one confirmed
batch, for a level or for the whole training, that marks ready only what the person opened in
the version it is now and that is not held, and leaves the rest with why.

Row 244 of the state-transition matrix in
docs/archive/superpowers/plans/2026-10-12-training-studio-core-pipeline.md. Scripted workers, the
stand-in for harness-research and a studios config of the test's own; nothing real is
started."""
from unittest import mock

import helpers  # noqa: F401  puts the runner on the import path
import workspace
from test_drafts import edit
from test_runner_deck import DeckCase, PageCase
from workspace import WorkspaceError

from runner import drafts


class BatchCase(DeckCase):

    def seen(self, root, name: str) -> str:
        session = workspace.load(root)
        return workspace.sha256_file(root / workspace.artifact(root, session, name)['file'])

    def person(self, root) -> dict:
        return workspace.person_statuses(root, workspace.load(root))

    def drafted(self, root) -> list[str]:
        return [name for name, status in self.person(root).items() if status == 'draft']


class BatchReadyTests(BatchCase):

    def test_row_244_only_what_was_opened_as_it_is_now_is_marked(self):
        root = self.begin(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        # The guide is changed after the deck was made from it: the deck is held.
        edit(self, root, 'document@101', lambda text: text + '\nOne line more.\n')
        self.assertEqual(self.person(root)['deck@101'], 'stale')
        before = self.person(root)
        seen = {'blueprint@101': self.seen(root, 'blueprint@101'),
                'document@101': self.seen(root, 'document@101'),
                # Opened before it changed: refused as changed, never marked.
                'brief@101': '0' * 64,
                # Opened, but held: left as held whatever was seen.
                'deck@101': self.seen(root, 'deck@101')}
        commits = len(self.log())
        answer = self.engine.mark_reviewed_ready(root, '101', seen)
        self.assertEqual(answer['marked'], ['blueprint@101', 'document@101'])
        left = {one['name']: one['why'] for one in answer['left']}
        self.assertEqual(left['brief@101'], 'refused')
        self.assertEqual(left['deck@101'], 'held')
        # Every scenario was not opened, so none is marked.
        scenarios = [name for name in before if name.startswith('scenario:')]
        self.assertTrue(scenarios)
        for name in scenarios:
            self.assertEqual(left[name], 'unopened')
        said = {one['name']: one['said'] for one in answer['left']}
        self.assertTrue(said['brief@101'].endswith(
            'has changed since it was opened. Read the new version before deciding.'))
        self.assertEqual(said['deck@101'], drafts.left_said('deck@101', 'held'))
        self.assertIn('was not opened in the version it is now', said[scenarios[0]])
        person = self.person(root)
        self.assertEqual([person[name] for name in answer['marked']], ['approved'] * 2)
        for name in left:
            self.assertEqual(person[name], before[name], name)
        # One commit for the batch, saying what it marked.
        self.assertEqual(len(self.log()), commits + 1)
        self.assertEqual(self.log()[-1],
                         'Rolling restarts: mark 2 reviewed materials of level 101 ready')

    def test_row_244_drafts_marked_unopened_are_said_so_in_the_approval_record(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        plan, guide = 'blueprint@101', 'document@101'
        answer = self.engine.mark_reviewed_ready(
            root, '101', {plan: self.seen(root, plan), guide: self.seen(root, guide)},
            unopened=[guide])
        self.assertEqual(answer['marked'], [plan, guide])
        said = 'mark 2 materials (1 not opened) of level 101 ready'
        self.assertEqual(self.log()[-1], 'Rolling restarts: ' + said)
        self.assertEqual(self.record(root)['last_decision']['label'],
                         '2 materials (1 not opened) of level 101')

    def test_row_244_nothing_opened_marks_nothing_and_commits_nothing(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        commits, before = self.log(), self.person(root)
        answer = self.engine.mark_reviewed_ready(root, '101', {})
        self.assertEqual(answer['marked'], [])
        self.assertEqual({one['why'] for one in answer['left']}, {'unopened'})
        self.assertEqual(sorted(one['name'] for one in answer['left']), sorted(self.drafted(root)))
        self.assertEqual((self.log(), self.person(root)), (commits, before))

    def test_row_244_the_whole_training_marks_every_level_s_opened_drafts(self):
        root = self.start(flow='desk', levels=['101', '201'])
        self.assertEqual(self.to_end(root), [])
        plans = ['blueprint@101', 'blueprint@201']
        seen = {name: self.seen(root, name) for name in plans}
        answer = self.engine.mark_reviewed_ready(root, None, seen, every=True)
        self.assertEqual(answer['marked'], plans)
        # Level 101's materials come before level 201's, each in the desk's order.
        names = [one['name'] for one in answer['left']]
        self.assertEqual(names, sorted(names, key=lambda name: workspace.split(name)[1]))
        self.assertTrue(any(name.endswith('@201') for name in names))
        self.assertEqual(self.log()[-1],
                         'Rolling restarts: mark 2 reviewed materials of every level ready')
        # A level alone leaves the other level as it is.
        guide = 'document@201'
        answer = self.engine.mark_reviewed_ready(root, '101', {guide: self.seen(root, guide)})
        self.assertEqual(answer['marked'], [])
        self.assertNotIn(guide, [one['name'] for one in answer['left']])
        self.assertEqual(self.person(root)[guide], 'draft')

    def test_row_244_scenarios_alone_with_kind(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        everything = {name: self.seen(root, name) for name in self.drafted(root)}
        answer = self.engine.mark_reviewed_ready(root, '101', everything, kind='scenario')
        self.assertTrue(answer['marked'])
        self.assertTrue(all(name.startswith('scenario:') for name in answer['marked']))
        self.assertEqual(self.person(root)['document@101'], 'draft')

    def test_row_244_a_level_must_be_one_of_the_training_s(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        commits = self.log()
        with self.assertRaisesRegex(WorkspaceError, '^Choose a level.$'):
            self.engine.mark_reviewed_ready(root, None, {})
        with self.assertRaisesRegex(WorkspaceError, '^This training has no level 999.$'):
            self.engine.mark_reviewed_ready(root, '999', {})
        self.assertEqual(self.log(), commits)

    def test_row_244_what_is_still_being_written_is_left_as_such(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        session = workspace.load(root)
        seen = {name: self.seen(root, name) for name in self.drafted(root)}
        # A material being made again is still being written, whatever was seen of it.
        record = {'drafts': {'updates': {'document@101': {'chain': 'one'}}}}
        found = dict(drafts.reviewed_batch(root, session, record, ('101',), seen))
        self.assertEqual(found['document@101'], 'writing')
        self.assertIsNone(found['blueprint@101'])
        # One whose file is not there yet has not been written.
        (root / workspace.artifact(root, session, 'brief@101')['file']).unlink()
        found = dict(drafts.reviewed_batch(root, session, {}, ('101',), seen))
        self.assertEqual(found['brief@101'], 'writing')
        self.assertEqual(drafts.left_said('brief@101', 'writing'),
                         'The level 101 brief is still being written.')

    def test_row_244_a_training_worked_on_in_conversation_is_refused(self):
        root = self.start(flow='desk', levels=['101'])
        self.assertEqual(self.to_end(root), [])
        commits = self.log()
        with mock.patch.object(drafts, 'in_conversation', return_value=True), \
                self.assertRaisesRegex(WorkspaceError, 'worked on in conversation'):
            self.engine.mark_reviewed_ready(root, '101', {
                name: self.seen(root, name) for name in self.drafted(root)})
        self.assertEqual(self.log(), commits)

    def test_row_244_a_saved_training_is_refused(self):
        import saved_fixtures
        root = saved_fixtures.load(self, 'level-document-gate')
        with self.assertRaisesRegex(WorkspaceError, f'^{drafts.NOT_ON_DESK}$'):
            self.engine.mark_reviewed_ready(root, '101', {})


class BatchEndpointTests(PageCase):
    """POST /api/drafts/reviewed-ready, as the page sends it."""

    def setUp(self):
        super().setUp()
        self.root = self.start(materials=['document', 'brief'])
        self.assertEqual(self.to_end(self.root), [])
        self.path = str(self.root)

    def cards(self) -> dict:
        return {card['name']: card for card in self.get('drafts', path=self.path)['cards']}

    def test_row_244_the_endpoint_marks_what_was_opened_and_says_the_rest(self):
        cards = self.cards()
        plan = next(name for name in cards if name.startswith('blueprint'))
        answer = self.post('drafts/reviewed-ready', {
            'path': self.path, 'level': '', 'scope': 'level',
            'seen': {plan: cards[plan]['seen']}})
        self.assertEqual(answer['marked'], [plan])
        self.assertEqual({one['why'] for one in answer['left']}, {'unopened'})
        self.assertEqual({card['name']: card['state'] for card in answer['cards']}[plan], 'ready')

    def test_row_244_the_endpoint_refuses_what_it_cannot_read(self):
        commits = self.log()
        for sent in ({'level': 101, 'seen': {}}, {'level': '', 'scope': 'all', 'seen': {}},
                     {'level': '', 'kind': 'deck', 'seen': {}}, {'level': '', 'seen': []},
                     {'level': '', 'seen': {}, 'unopened': 'blueprint'},
                     {'level': '', 'seen': {}, 'unopened': [1]},
                     {'level': ''}, {'level': '', 'seen': {'blueprint': 7}}):
            with self.subTest(sent=sent):
                self.post('drafts/reviewed-ready', {'path': self.path, **sent}, expect=400)
        self.assertEqual(self.log(), commits)
        self.assertEqual({card['state'] for card in self.cards().values()}, {'draft'})
