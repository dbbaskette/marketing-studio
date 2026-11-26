"""Every saved state a training made in a conversation with the helper `training.py` can be in
(GitHub issue #547), loaded from its stored copy (`saved_fixtures.conversation`). The stored
copies were captured by driving the helper's commands that continued such a training; those
commands are gone, so the copies cannot be captured again.

Such a training lives in a folder of its own, outside the workspace. Nothing continues it:
it is listed there with Bring in as its one way on, and Bring in copies it into the workspace
without touching the original. Brought in, it is a saved record like any the earlier flow
saved, and each state has one outcome, under the owner's rulings:

- with a plan, outline or draft it opens on the desk through the explicit, previewed
  migration, every original byte kept, nothing approved, marked Ready or delivered that was
  not, and what it holds but cannot open (an outline that cannot be read, a file written but
  never saved, a copy never made) said in History;
- finished, by the runner's own survey, it keeps the finished Open on the desk;
- with nothing made yet, or a record that cannot be read or understood, it is read-only:
  what it is, why, its files to read in place, and one next action that can be taken.
"""
import json

import saved_fixtures
from test_saved_states import SavedStopTests  # puts the helper and the runner on the path
import workspace
from runner import desk_chat, desk_migration, drafts, engine as engines, page

NOTHING_MADE = desk_migration.NOTHING_MADE
MISSING = desk_migration.MISSING

# Each stored state and its outcome once brought in: ('migrates', targets),
# ('finished',), ('read-only', why, next) or ('outside',) for one that cannot be brought in.
OUTCOMES = {
    'conversation-started': ('read-only', NOTHING_MADE, 'new'),
    'conversation-intake': ('read-only', NOTHING_MADE, 'copy'),
    'conversation-research-plan-gate': ('read-only', NOTHING_MADE, 'copy'),
    'conversation-research-gate': ('read-only', NOTHING_MADE, 'copy'),
    'conversation-research-imported': ('read-only', NOTHING_MADE, 'copy'),
    'conversation-unsaved-plan': ('read-only', MISSING + ' blueprint has no saved input record.',
                                  'copy'),
    'conversation-unreadable-plan': ('read-only', MISSING + ' The shared saved teaching plan '
                                     'cannot be read.', 'copy'),
    'conversation-blueprint-gate': ('migrates', ['blueprint']),
    'conversation-blueprint-on-the-page': ('migrates', ['blueprint']),
    'conversation-question-after-plan': ('migrates', ['blueprint']),
    'conversation-document-gate': ('migrates', ['blueprint', 'document']),
    'conversation-edited-after-save': ('migrates', ['blueprint', 'document']),
    'conversation-change-asked': ('migrates', ['blueprint', 'document']),
    'conversation-left-out': ('migrates', ['blueprint', 'document']),
    'conversation-out-of-date': ('migrates', ['blueprint', 'document', 'brief']),
    'conversation-deck-gate': ('migrates', ['blueprint', 'document', 'brief', 'deck']),
    'conversation-google-deck': ('migrates', ['blueprint', 'document', 'brief', 'deck']),
    'conversation-scenario-gate': ('migrates', ['blueprint', 'document', 'brief', 'deck',
                                                'scenario:main', 'yoodli:main']),
    'conversation-levels': ('migrates', ['blueprint@101', 'blueprint@301', 'document@101']),
    'conversation-ready-at-package': ('migrates', ['blueprint', 'document', 'brief', 'deck',
                                                   'scenario:main']),
    'conversation-unsaved-guide': ('migrates', ['blueprint']),
    'conversation-finished': ('migrates', ['blueprint', 'document', 'brief', 'deck',
                                           'scenario:main', 'yoodli:main']),
    'conversation-finished-complete': ('finished',),
    'conversation-unreadable-session': ('outside',),
}


class ConversationStateCase(SavedStopTests):
    def outside(self, state):
        """The stored training in its own folder, as the helper left it: listed on the page
        with Bring in as its way on, and refused by the preview until it is brought in."""
        top = saved_fixtures.conversation(self, state)
        before = self.snapshot(top)
        found = desk_migration.outcome(self.engine, top)
        self.assertEqual(found, {'outcome': 'bring', 'said': 'There is no saved training there.',
                                 'reason': desk_migration.BRING})
        shown = desk_chat.migration_preview(self.engine, top)
        self.assertEqual((shown['blockers'], shown['writes']),
                         (['There is no saved training there.'], []))
        if OUTCOMES[state] != ('outside',):
            item = page.RunnerPage(8765, self.engine).detail(str(top))
            # Bring in is offered: a training the page knows, not run here, readable.
            self.assertNotIn('error', item)
            self.assertIsNone(item['run'])
        self.assertEqual(self.snapshot(top), before)
        return top, before

    def brought(self, state):
        top, before = self.outside(state)
        jobs = len(self.workers.jobs)
        root = self.engine.driven(self.engine.bring(top)['path'])
        # The original is only read; the copy is a saved record that runs nothing.
        self.assertEqual(self.snapshot(top), before)
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertIsNone(self.view(root)['flow'])
        return root

    def never_says_finish_later(self, root):
        shown = self.record_of(root)
        self.assertNotEqual(shown['saved_record']['why'], drafts.NOT_FINISHED)
        return shown

    def proves(self, state):
        outcome = OUTCOMES[state]
        if outcome == ('outside',):
            return self.proves_outside(state)
        root = self.brought(state)
        shown = self.never_says_finish_later(root)
        if outcome[0] == 'migrates':
            self.assert_migrates(root, outcome[1])
            # Its one next action was taken: it is desk work now.
            self.assertEqual(self.engine.view(root)['flow'], 'desk')
        elif outcome[0] == 'finished':
            self.assertEqual(shown['saved_record']['outcome'], 'finished')
            self.assertTrue(shown['can_open_desk'])
            self.assert_refused(root, desk_migration.FINISHED)
            self.engine.open_on_desk(root)
            self.assertEqual(self.engine.view(root)['flow'], 'desk')
        else:
            _, why, next_action = outcome
            before = self.workspace_state(root)
            self.assert_read_only(root, why, next_action)
            self.assertTrue(self.preview(root)['blockers'])
            if next_action == 'copy':
                # Its start form is among its files, to read in place.
                self.assertIn('intake.md', shown['saved_record']['files'])
                # Start new work from this: its start form is read, and nothing is written.
                values = self.engine.copy_setup(root)
                self.assertEqual(values['title'], workspace.load(root)['title'] + ' copy')
            self.assertEqual(self.workspace_state(root), before)
        return root

    def proves_outside(self, state):
        """A record the runner cannot read is not brought in: it is a read-only record where
        it is, said plainly, with its files to read in place and a new training as its one
        way on. Nothing in its folder changes."""
        top, before = self.outside(state)
        with self.assertRaises(workspace.WorkspaceError) as refused:
            self.engine.bring(top)
        self.assertIn('cannot be brought into the workspace', str(refused.exception))
        native = page.RunnerPage(8765, self.engine)
        item = native.detail(str(top))
        self.assertEqual((item['error'], item['sentence']),
                         (engines.CONVERSATION_UNREAD_BRIEF, engines.CONVERSATION_UNREAD))
        record = item['saved_record']
        self.assertEqual((record['outcome'], record['why'], record['next'], record['outside']),
                         ('read-only', engines.CONVERSATION_UNREAD_WHY, 'new', True))
        for said in (item['error'], item['sentence'], record['why']):
            self.assertNotIn('JSON', said)
            self.assertNotIn(str(self.base), said)
        self.assertIn('blueprint.md', record['files'])
        listed = {entry['path']: entry for entry in native.trainings()}[str(top)]
        self.assertEqual(listed['saved_record'], record)
        read = native.saved_file(str(top), 'blueprint.md')
        self.assertEqual(read['text'], (top / 'blueprint.md').read_text())
        with self.assertRaises(Exception):
            native.saved_file(str(top), '.training-studio/session.json')
        self.assertEqual(self.snapshot(top), before)
        self.assertFalse(any(path.parent == self.space.root for path in
                             self.space.root.glob('*/.training-studio')))
        return top


class EveryStateTests(ConversationStateCase):
    def test_every_stored_state_has_an_outcome_here(self):
        self.assertEqual(set(OUTCOMES), set(saved_fixtures.conversation_names()))


for _state in OUTCOMES:
    def _test(self, state=_state):
        self.proves(state)
    _test.__doc__ = f'{_state}: {OUTCOMES[_state][0]}'
    setattr(EveryStateTests, 'test_' + _state.replace('-', '_'), _test)


class HistoryTests(ConversationStateCase):
    """What a state holds but cannot open on the desk is kept as it is and said in History."""

    def opened(self, state):
        root = self.brought(state)
        shown = self.preview(root)
        desk_chat.migrate(self.engine, root, shown['expected'])
        return root, shown, drafts.view(self.engine, root)

    def test_finished_in_a_conversation_with_a_copy_never_made_opens_on_the_desk(self):
        stored = saved_fixtures.conversation_tree('conversation-finished')
        self.assertEqual(json.loads(stored[saved_fixtures.SESSION])['stage'], 'done')
        root, shown, desk = self.opened('conversation-finished')
        said = [desk_migration.DONE_ELSEWHERE, desk_migration.ACCEPTED.format(
            said='The Yoodli scenario has no Word copy')]
        self.assertEqual(shown['notes'], said)
        self.assertLessEqual(set(said), set(shown['retained']))
        self.assertEqual(desk['saved_status'], {'notes': said})
        # The copy never made is not made, and no export is invented.
        session = workspace.load(root)
        self.assertNotIn('yoodli:main', session['exports'])
        self.assertFalse((root / 'yoodli' / 'main.docx').exists())
        self.assertEqual(session['stage'], 'done')

    def test_a_file_written_and_never_saved_is_kept_and_not_made_on_the_desk(self):
        stored = saved_fixtures.conversation_tree('conversation-unsaved-guide')
        root, shown, desk = self.opened('conversation-unsaved-guide')
        said = desk_migration.UNSAVED.format(what='The learner guide', file='document.md')
        self.assertEqual(shown['notes'], [said])
        self.assertEqual(desk['saved_status'], {'notes': [said]})
        self.assertEqual((root / 'document.md').read_bytes(), stored['document.md'])
        session = workspace.load(root)
        self.assertNotIn('document', session['artifacts'])
        self.assertEqual(workspace.statuses(root, session)['document'], 'not-started')
        cards = {card['name']: card['state'] for card in desk['cards']}
        self.assertEqual(cards['document'], 'needs')
        # Once the desk makes the guide, it is the guide: the mark is for those bytes only.
        (root / 'document.md').write_text('# A guide the desk wrote\n')
        self.assertEqual(workspace.statuses(root, workspace.load(root))['document'], 'draft')

    def test_saved_material_moves_as_it_would_without_the_unsaved_file(self):
        root = self.brought('conversation-unsaved-guide')
        (root / 'document.md').unlink()
        self.gitstate.commit(self.space, 'without the unsaved guide', [root])
        shown = self.preview(root)
        self.assertEqual((shown['targets'], shown['notes']), (['blueprint'], []))


class WhereTests(ConversationStateCase):
    """Where a conversation's folder is, as its saved record says it: compared as folders,
    as Bring in compares them."""

    def test_where_a_folder_lies(self):
        repo, root = self.space.repo, self.space.root
        self.assertEqual(self.engine.where(self.base / 'conversation' / 'kept'), 'outside')
        self.assertEqual(self.engine.where(root / 'kept'), 'in-workspace')
        if repo != root:
            self.assertEqual(self.engine.where(repo / 'notes' / 'kept'), 'in-repository')
        self.assertEqual(self.engine.where(repo.parent), 'holds-workspace')

    def test_an_unreadable_record_inside_the_repository_is_not_said_to_be_outside_it(self):
        """A conversation's unreadable record kept in the workspace's repository: its saved
        record says where it is, never that it is outside the workspace."""
        import home
        top = self.space.repo / 'notes' / 'kept-here'
        saved_fixtures.place('conversation-unreadable-session', top)
        home.remember(top, top.name, [])
        record = page.RunnerPage(8765, self.engine).detail(str(top))['saved_record']
        where = 'in-repository' if self.space.repo != self.space.root else 'in-workspace'
        self.assertEqual((record['where'], record['outside']), (where, False))
        outside = saved_fixtures.conversation(self, 'conversation-unreadable-session')
        record = page.RunnerPage(8765, self.engine).detail(str(outside))['saved_record']
        self.assertEqual((record['where'], record['outside']), ('outside', True))


# Where a stored conversation's folder is, or what it holds, when Bring in cannot take it: the
# same check decides its record and Bring in (`Engine.bring_refusal`). Each row: the stored
# state, where its folder is, and the sentence both say. Outside the workspace, every state
# above is brought in.
WHERE_OUTCOMES = {
    ('conversation-blueprint-gate', 'in-repository'): engines.IN_REPOSITORY,
    ('conversation-blueprint-gate', 'in-workspace'): engines.ALREADY_IN,
    ('conversation-blueprint-gate', 'holds-workspace'): engines.HOLDS_WORKSPACE,
    ('conversation-blueprint-gate', 'a linked file'): (
        'This training cannot be brought into the workspace. linked.md is a symbolic link, '
        'which a workspace does not take.'),
    ('conversation-blueprint-gate', 'a name already taken'): engines.NAME_TAKEN.format(
        where='trainings/blueprint-in-conversation'),
}


class CannotBeBroughtInTests(ConversationStateCase):
    """GitHub issue #547: a record never offers an action that cannot be taken. A
    conversation's training that Bring in would refuse is a read-only record where it is: why,
    in Bring in's own sentence and with no path of this computer, and a new training as its
    way on. `studio saved-work` says the same. Nothing in its folder changes."""

    def placed(self, state, where):
        import home
        import shutil
        if where == 'in-repository':
            top = self.space.repo / 'notes' / 'kept-here'
        elif where == 'in-workspace':
            top = self.space.root / 'kept-here'
        elif where == 'holds-workspace':
            # The workspace's repository lies inside this folder: the stored files beside it.
            top = self.space.repo.parent
            shutil.copytree(saved_fixtures.CONVERSATION / state, top, dirs_exist_ok=True)
            home.remember(top, *saved_fixtures.conversation_title(state))
            return top
        else:
            if where == 'a name already taken':
                self.engine.bring(saved_fixtures.conversation(self, state))
                top = self.base / 'another-conversation' / 'kept'
            else:
                top = self.base / 'elsewhere' / 'kept'
            saved_fixtures.place(state, top)
            if where == 'a linked file':
                (top / 'linked.md').symlink_to(top / 'blueprint.md')
            return top
        return saved_fixtures.place(state, top)

    def proves_kept(self, state, where, said):
        top = self.placed(state, where)
        before = self.snapshot(top)
        self.assertEqual(self.engine.bring_refusal(top), said)
        native = page.RunnerPage(8765, self.engine)
        item = native.detail(str(top))
        record = item['saved_record']
        self.assertEqual((record['outcome'], record['why'], record['next']),
                         ('read-only', said, 'new'))
        self.assertEqual(item['sentence'], engines.CONVERSATION_KEPT)
        for text in (said, item['sentence']):
            self.assertNotIn(str(self.base), text)
        self.assertEqual(record['outside'], where not in ('in-repository', 'in-workspace',
                                                          'holds-workspace'))
        # Bring in refuses it with the very sentence its record says.
        with self.assertRaises(workspace.WorkspaceError) as refused:
            self.engine.bring(top)
        self.assertEqual(str(refused.exception), said)
        found = self.engine.saved_work()
        listed = {entry['path']: entry['why'] for entry in next(
            paths for paths in found['paths'] if paths['id'] == 'read-only-record')['needed_by']}
        if where == 'a linked file':
            # saved-work never reads through a link: the folder is reported as one it could
            # not look at, naming the link, and never as one to bring in.
            self.assertTrue(any(entry['path'] == str(top) and 'Symbolic link excluded' in
                                entry['why'] for entry in found['issues']))
            self.assertFalse(found['complete'])
        else:
            self.assertEqual(listed.get(str(top)), said)
        brought = {entry['path'] for entry in next(
            paths for paths in found['paths'] if paths['id'] == 'bring-in-first')['needed_by']}
        self.assertNotIn(str(top), brought)
        self.assertEqual(self.snapshot(top), before)

    def test_every_stored_state_outside_the_workspace_can_be_brought_in(self):
        for state, outcome in OUTCOMES.items():
            if outcome == ('outside',):
                continue
            with self.subTest(state=state):
                top = saved_fixtures.conversation(self, state)
                self.assertIsNone(self.engine.bring_refusal(top))
                record = page.RunnerPage(8765, self.engine).detail(str(top))['saved_record']
                self.assertEqual((record['outcome'], record['next'], record['where']),
                                 ('bring', 'bring', 'outside'))

    def test_on_a_phone_nothing_is_offered_that_would_be_refused(self):
        """Through the private link, nothing of this computer's folders is read: the record
        says bringing a training in is done on the computer, and offers no action."""
        from studio_core.shared_runner import caller
        top = saved_fixtures.conversation(self, 'conversation-blueprint-gate')
        native = page.RunnerPage(8765, self.engine)
        with caller.answering({caller.VIA_HEADER: caller.NETWORK}):
            record = native.detail(str(top))['saved_record']
            self.assertEqual(caller.bring_refused(str(top)), caller.BRING_HERE)
        self.assertEqual((record['outcome'], record['next'], record['elsewhere']),
                         ('bring', None, engines.BRING_ON_COMPUTER))
        # On this computer it is still brought in.
        self.assertEqual(native.detail(str(top))['saved_record']['next'], 'bring')


for (_state, _where), _said in WHERE_OUTCOMES.items():
    def _kept(self, state=_state, where=_where, said=_said):
        self.proves_kept(state, where, said)
    _kept.__doc__ = f'{_state}, {_where}: read-only where it is'
    setattr(CannotBeBroughtInTests, 'test_' + (_state + ' ' + _where).replace('-', '_')
            .replace(' ', '_'), _kept)
