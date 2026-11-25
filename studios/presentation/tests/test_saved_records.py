"""Decks the earlier step-by-step flow saved, as saved records (GitHub issue #542, the fix
rounds): an opening on the desk that was interrupted waits and is finished on the person's
word; a list says only what the small record proves, and an open record keeps what its check
found until the person acts or checks again; a list and a poll read no material file; a
read-only record's next step is true for its reason; a wait says only what is known;
start-up recovers a step a stopped runner left as it always did and continues nothing;
taking a saved deck is the team's take as it always was; and each state of the screen has
one filled action."""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import runner_support
import test_desk_page
from runner import decks, desk_chat, desk_migration
from runner import research as research_cli
from runner import engine as engines
from studio_core import sync_guard, work_summary
from studio_core.sync_guard import SYNC_WAIT
from workspace import WorkspaceError
from test_desk import ok

STUDIO = Path(__file__).resolve().parents[1]
CRASH = '''import os, sys
from pathlib import Path
from runner import engine, desk_chat, desk_migration, gitstate
e=engine.Engine(background=False)
if sys.argv[3] == 'receipt':
 original=desk_migration._write
 def die(path,data):
  original(path,data)
  if Path(path).name == 'migration-origin.json': os._exit(71)
 desk_migration._write=die
else:
 original=gitstate.commit
 def die(*args,**kwargs):
  original(*args,**kwargs)
  os._exit(71)
 gitstate.commit=die
desk_chat.migrate(e,Path(sys.argv[1]),sys.argv[2])
'''


def files_of(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob('*')) if path.is_file()}


class SavedRecordCase(runner_support.DeskCase):
    def interrupted(self, title: str, boundary: str = 'commit') -> Path:
        """A saved deck whose opening on the desk stopped in the middle, as a runner that
        ended there leaves it: after its receipt was written, or after its commit."""
        root = self.load_saved('build', title=title)
        token = desk_chat.migration_preview(self.engine, root)['expected']
        done = subprocess.run([sys.executable, '-c', CRASH, str(root), token, boundary],
                              cwd=STUDIO, env={**os.environ, 'PYTHONPATH': '.:tests'},
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 71, done.stderr)
        self.assertTrue((root / desk_migration.format.PENDING).exists())
        return root

    def listed(self) -> dict:
        found = self.engine.decks()
        return {brief['id']: (kind, brief) for kind, briefs in found.items() for brief in briefs}


class InterruptedOpeningTests(SavedRecordCase):
    def test_an_interrupted_opening_waits_says_so_and_is_finished_on_the_desk(self):
        for boundary, outcome in (('commit', 'opened'), ('receipt', 'put back')):
            with self.subTest(boundary):
                root = self.interrupted('Interrupted ' + boundary, boundary)
                raw = (root / 'run.json').read_bytes()
                beside = self.load_saved('outline', title='Beside ' + boundary)
                shown = self.engine.view(root)
                saved = shown['saved_record']
                self.assertEqual((shown['title'], shown['sentence'], saved['state'],
                                  saved['action'], saved['waiting']),
                                 ('Interrupted ' + boundary, engines.INTERRUPTED, 'interrupted',
                                  'finish', [engines.INTERRUPTED_CLEARS]))
                kind, brief = self.listed()[root.name]
                self.assertEqual((kind, brief['title'], brief['saved'], brief['sentence']),
                                 ('saved', 'Interrupted ' + boundary, 'interrupted',
                                  engines.SAVED_SAYS['interrupted']))
                # Another deck waits for it, says which, and goes there.
                other = self.engine.saved_check(beside)['saved_record']
                said = engines.HOLDER_SAYS['interrupted'].format(title='Interrupted ' + boundary)
                self.assertEqual((other['state'], other['action'], other['waiting'],
                                  other['holder']),
                                 ('waiting', 'open', [said],
                                  {'path': str(root), 'title': 'Interrupted ' + boundary}))
                # Nothing recovers it on its own: starting again leaves it as it is.
                before = files_of(root)
                self.engine.resume()
                self.assertEqual(files_of(root), before)
                # The person's word finishes it, as the migration's own recovery does.
                finished = self.engine.finish_opening(root)
                self.assertEqual(finished['opening'], outcome)
                self.assertFalse((root / desk_migration.format.PENDING).exists())
                self.assertEqual((root / 'run.json').read_bytes(), raw)
                if outcome == 'opened':
                    self.assertEqual(finished['execution'], 'conversation')
                    self.assertEqual(decks.read_run(root)['flow'], 'desk')
                else:
                    self.assertNotIn('flow', decks.read_run(root))
                    self.assertEqual(self.engine.saved_check(root)['saved_record']['state'],
                                     'migrates')
                self.assertEqual(self.engine.saved_check(beside)['saved_record']['state'],
                                 'migrates')


class SavedListTests(SavedRecordCase):
    def test_a_list_says_only_what_the_small_record_proves(self):
        root = self.load_saved('build', title='Listed')
        unread = self.load_saved('outline', title='Unread')
        (unread / 'run.json').write_text('{not json')
        checks = (lambda: None, lambda: self.engine.saved_check(root))
        for check in checks:
            check()
            listed = self.listed()
            kind, brief = listed[root.name]
            self.assertEqual((kind, brief['saved'], brief['sentence'], brief['needs']),
                             ('saved', 'unchecked', engines.SAVED_SAYS['unchecked'], False))
            self.assertEqual(listed[unread.name][1]['saved'], 'read-only')
        # What a check found stays on the record's screen, never on a list.
        with mock.patch.object(desk_migration, 'worker_in_progress', return_value=True):
            self.assertEqual(self.engine.saved_check(root)['saved_record']['state'], 'waiting')
        self.assertEqual(self.listed()[root.name][1]['saved'], 'unchecked')

    def test_an_open_record_keeps_what_its_check_found_until_the_person_acts(self):
        root = self.load_saved('build', title='Kept')
        beside = self.load_saved('outline', title='Beside')
        found = self.engine.saved_check(root)
        self.assertEqual(found['saved_record']['state'], 'migrates')
        # A fetch, and a step's write in another deck, change nothing it shows.
        self.engine._fetched += 1
        os.utime(beside / 'run.json', ns=(1, 1))
        (beside / engines.IN_HAND).write_text('outline\n')
        shown = self.engine.view(root)
        self.assertEqual((shown['sentence'], shown['saved_record']['state'],
                          shown['saved_record']['checked_at']),
                         (engines.SAVED_OPENS, 'migrates', found['saved_record']['checked_at']))
        # Its action checks again for itself when it is pressed.
        self.assertIn(SYNC_WAIT, desk_chat.migration_preview(self.engine, root)['blockers'])
        # Check again finds it as it is now.
        again = self.engine.saved_check(root)['saved_record']
        self.assertEqual((again['state'], again['action']), ('waiting', 'check'))

    def test_a_list_and_a_poll_read_no_material_file(self):
        root = self.load_saved('build', title='Polled')
        refused = AssertionError('a material file was read')
        with mock.patch.object(desk_chat, '_files', side_effect=refused), \
                mock.patch.object(desk_migration, 'outcome', side_effect=refused), \
                mock.patch.object(desk_migration, 'migration_preview', side_effect=refused):
            self.engine.decks()
            self.assertEqual(self.engine.view(root)['saved_record']['state'], 'unchecked')
        self.engine.saved_check(root)
        with mock.patch.object(desk_chat, '_files', side_effect=refused), \
                mock.patch.object(desk_migration, 'outcome', side_effect=refused), \
                mock.patch.object(desk_migration, 'migration_preview', side_effect=refused):
            self.engine.decks()
            self.assertEqual(self.engine.view(root)['saved_record']['state'], 'migrates')


class SavedActionTests(SavedRecordCase):
    def test_a_read_only_reason_names_a_next_step_true_for_it(self):
        nothing = self.engine.saved_check(self.load_saved('research-plan'))['saved_record']
        self.assertEqual(nothing['why'], desk_migration.NOTHING_MADE)
        self.assertNotIn('Restore', nothing['remedy'])
        self.assertIn('Start new work from it', nothing['remedy'])
        refused = self.engine.view(self.load_saved('unleveled'))['saved_record']
        self.assertIn('Restore its saved record', refused['remedy'])

    def test_what_a_wait_says_is_only_what_is_known(self):
        root = self.load_saved('build', title='Waits')
        other = self.load_saved('outline', title='Other deck')
        # A step this Presentation Studio runs is named, and is waited for.
        (other / engines.IN_HAND).write_text('outline\n')
        self.engine._active_steps.add(str(other))
        try:
            saved = self.engine.saved_check(root)['saved_record']
        finally:
            self.engine._active_steps.discard(str(other))
        self.assertEqual((saved['waiting'], saved['action']),
                         ([engines.HOLDER_SAYS['working'].format(title='Other deck')], 'check'))
        # A marker of a step it does not run: never said to end by itself.
        saved = self.engine.saved_check(root)['saved_record']
        self.assertEqual((saved['waiting'], saved['action']),
                         ([engines.HOLDER_SAYS['marked'].format(title='Other deck')], 'check'))
        (other / engines.IN_HAND).unlink()
        # Something it cannot see: another Studio in the workspace, say.
        with mock.patch.object(desk_migration, 'worker_in_progress', return_value=True):
            saved = self.engine.saved_check(root)['saved_record']
        self.assertEqual((saved['waiting'], saved['action']), ([engines.ELSEWHERE_WAITS], 'check'))
        for said in (engines.HOLDER_SAYS['marked'], engines.ELSEWHERE_WAITS):
            self.assertNotIn('by itself', said)
            self.assertNotIn('Wait for it to end', said)
        # The shared check could not look: its folder and reason are said as it gives them.
        unchecked = sync_guard.unchecked('team-work/x', 'its Presentation Studio run record '
                                         'cannot be understood')
        with mock.patch.object(desk_migration, 'worker_in_progress',
                               side_effect=WorkspaceError(unchecked)):
            saved = self.engine.saved_check(root)['saved_record']
        self.assertEqual((saved['waiting'], saved['action']), ([unchecked], 'copy'))

    def test_finishing_an_interrupted_opening_says_what_it_waits_for(self):
        root = self.interrupted('Interrupted')
        other = self.load_saved('outline', title='Marked deck')
        (other / engines.IN_HAND).write_text('outline\n')
        with self.assertRaises(WorkspaceError) as refused:
            self.engine.finish_opening(root)
        self.assertEqual(str(refused.exception),
                         engines.HOLDER_SAYS['marked'].format(title='Marked deck'))
        self.assertNotIn(SYNC_WAIT, str(refused.exception))
        self.assertTrue((root / desk_migration.format.PENDING).exists())
        (other / engines.IN_HAND).unlink()
        self.assertEqual(self.engine.finish_opening(root)['opening'], 'opened')


class StartUpRecoveryTests(SavedRecordCase):
    """Start-up recovers a step a stopped runner left in a saved deck as it always did, and
    continues nothing (fix round 2: the replaced marker ruling)."""

    def test_a_saved_deck_this_computer_runs_is_recovered_as_before_and_not_continued(self):
        root = self.load_saved('build', title='Left marked')
        (root / engines.IN_HAND).write_text('outline\n')
        (root / research_cli.LOCK).parent.mkdir(parents=True, exist_ok=True)
        (root / research_cli.LOCK).write_text('')
        committed = (root / 'outline.md').read_bytes()
        with open(root / 'outline.md', 'a') as stream:
            stream.write('\nA line a stopped step left.\n')
        raw, log, jobs = (root / 'run.json').read_bytes(), self.log(), list(self.workers.jobs)
        self.engine.resume()
        # What the stopped step half-made is put back, and its markers go: as before.
        self.assertFalse((root / engines.IN_HAND).exists())
        self.assertFalse((root / research_cli.LOCK).exists())
        self.assertEqual((root / 'outline.md').read_bytes(), committed)
        # Nothing continues it: no job, no commit, its record as it was.
        self.assertEqual(((root / 'run.json').read_bytes(), self.log(), self.workers.jobs),
                         (raw, log, jobs))
        self.assertEqual(self.engine.saved_check(root)['saved_record']['state'], 'migrates')

    def test_a_read_only_or_unreadable_deck_loses_only_its_markers(self):
        # The reviewer's probes: neither deck holds the workspace after start-up.
        nothing = self.load_saved('research-plan', title='Nothing made')
        bad = self.load_saved('outline', title='Bad')
        (bad / 'run.json').write_text('{not json')
        beside = self.load_saved('outline', title='Has outline')
        for root in (nothing, bad):
            (root / engines.IN_HAND).parent.mkdir(parents=True, exist_ok=True)
            (root / engines.IN_HAND).write_text('research-plan\n')
        unreadable = files_of(bad)
        self.engine.resume()
        for root in (nothing, bad):
            self.assertFalse((root / engines.IN_HAND).exists(), root.name)
        del unreadable[engines.IN_HAND]
        self.assertEqual(files_of(bad), unreadable)
        other = self.engine.saved_check(beside)['saved_record']
        self.assertEqual((other['state'], other['waiting']), ('migrates', []))
        preview = desk_chat.migration_preview(self.engine, beside)
        self.assertEqual(preview['blockers'], [])
        self.assertEqual(desk_chat.migrate(self.engine, beside, preview['expected'])['execution'],
                         'conversation')

    def test_a_step_running_in_this_process_is_never_touched(self):
        root = self.load_saved('build', title='Running')
        (root / engines.IN_HAND).write_text('outline\n')
        self.engine._active_steps.add(str(root))
        try:
            self.engine.resume()
            self.assertTrue((root / engines.IN_HAND).exists())
        finally:
            self.engine._active_steps.discard(str(root))


class StartUpTeamTests(runner_support.DeskCase, runner_support.TeamCase):
    def test_after_start_up_a_desk_deck_shares_starts_and_edits_in_conversation(self):
        # The reviewer's probe: a saved deck left with a marker held the whole workspace.
        nothing = self.load_saved('research-plan', title='Nothing made')
        form = {**runner_support.FORM, 'flow': 'desk', 'scope': ['outline']}
        desk_deck = Path(desk_chat.create(self.engine, form)['path'])
        self.engine.share()
        (nothing / engines.IN_HAND).parent.mkdir(parents=True, exist_ok=True)
        (nothing / engines.IN_HAND).write_text('research-plan\n')
        self.engine.resume()
        self.assertFalse((nothing / engines.IN_HAND).exists())
        self.assertTrue(self.engine.share()['shared'])
        started = Path(desk_chat.create(self.engine, form)['path'])
        self.assertTrue(started.is_dir())
        self.assertEqual(desk_chat._root(self.engine, desk_deck, change=True)[0], desk_deck)


class SavedTakeTests(runner_support.DeskCase, runner_support.TeamCase):
    def test_taking_a_saved_deck_is_the_teams_take_as_before_and_continues_nothing(self):
        root = self.load_saved('build', title='Taken')
        self.engine.share()
        other = self.theirs(self.blake, root)
        with self.be(self.blake):
            self.blake.engine.fetch()
            saved = self.blake.engine.saved_check(other)['saved_record']
            self.assertEqual((saved['state'], saved['action']), ('waiting', 'take'))
            # The reviewer's probe: a change not shared yet goes with the take, as it always
            # did (the confirmation says so).
            with open(other / 'outline.md', 'a') as stream:
                stream.write('\nHand edit not committed.\n')
            expected = self.blake.engine._load(other)
            jobs = list(self.workers.jobs)
            self.assertFalse((other / work_summary.FILE).exists())
            self.blake.engine.drive(other, 'take')
            # As any deck's record is stored: its summary for the studio's lists is kept too.
            self.assertTrue((other / work_summary.FILE).is_file())
            space = self.blake.engine.space()
            subject = self.git('log', '-1', '--format=%s', repo=space.repo)
            self.assertEqual(subject, 'Taken: Blake takes this deck over from Alex')
            changed = self.git('show', '--name-only', '--format=', 'HEAD', repo=space.repo)
            self.assertIn((other / 'outline.md').relative_to(space.repo).as_posix(),
                          changed.splitlines())
            # Its record is written as the team's take writes any deck's: the record as the
            # runner reads it, with this computer as its driver.
            after = json.loads((other / 'run.json').read_bytes())
            expected['driver'] = after['driver']
            self.assertEqual(after, expected)
            self.assertEqual((other / 'run.json').read_text(),
                             json.dumps(expected, indent=2, ensure_ascii=False) + '\n')
            self.assertEqual(after['driver']['name'], 'Blake')
            self.assertEqual(self.workers.jobs, jobs)
            # Nothing continues it, so there is no run to hand over.
            with self.assertRaises(WorkspaceError) as refused:
                self.blake.engine.drive(other, 'hand-over')
            self.assertEqual(str(refused.exception), engines.SAVED_FLOW_ENDED)
            # Taken, it opens on the desk here.
            preview = desk_chat.migration_preview(self.blake.engine, other)
            self.assertEqual(preview['blockers'], [])
            opened = desk_chat.migrate(self.blake.engine, other, preview['expected'])
            self.assertEqual(opened['execution'], 'conversation')


class SavedScreenTests(test_desk_page.DeskPageCase):
    """Every state of a saved record's screen has exactly one filled action."""

    def checked(self, root) -> dict:
        return self.post('saved-check', {'path': str(root)})

    def shot(self, root, view, steps=(), **more) -> dict:
        """The screen as it opens on `view`: it checks the deck as it opens, and the check
        answers what `view` says."""
        more = {'POST /api/saved-check': [ok(view)], 'GET /api/run': [ok(view)] * 6, **more}
        result = self.open_deck(str(root), view, [{'snapshot': 'saved'}, *steps], **more)
        shot = result['snapshots']['saved']
        self.assertLayout(shot)
        return result, shot

    def test_a_saved_record_is_checked_once_when_it_opens(self):
        root = self.load_saved('build', title='Opened')
        unchecked, checked = self.run_of(str(root)), self.checked(root)
        self.assertEqual(unchecked['saved_record']['state'], 'unchecked')
        result = self.open_deck(str(root), unchecked, [{'snapshot': 'opened'}],
                                **{'POST /api/saved-check': [ok(checked)],
                                   # Once checked, its view says what the check found.
                                   'GET /api/run': [ok(unchecked), ok(checked)]})
        self.assertEqual(self.posts(result), [('/api/saved-check', {'path': str(root)})])
        self.assertEqual(result['snapshots']['opened']['filled'], ['Open on the desk'])

    def test_a_finished_saved_deck_offers_open_on_the_desk_filled(self):
        root = self.load_saved('delivered', title='Delivered earlier')
        _, shot = self.shot(root, self.checked(root))
        self.assertEqual(shot['filled'], ['Open on the desk'])
        self.assertNotIn('Hand over', shot['buttons'])

    def test_an_interrupted_opening_offers_to_finish_it(self):
        root = self.load_saved('build', title='Interrupted')
        pending = root / desk_migration.format.PENDING
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text('{}')
        view = self.run_of(str(root))
        result, shot = self.shot(root, view, [{'click': 'Finish opening on the desk'}],
                                 **{'POST /api/saved-finish': [ok(view)]})
        self.assertEqual(shot['filled'], ['Finish opening on the desk'])
        self.assertIn(engines.INTERRUPTED, shot['text'])
        self.assertIn(engines.INTERRUPTED_CLEARS, shot['text'])
        self.assertEqual(self.posts(result), [('/api/saved-finish', {'path': str(root)})])

    def test_a_waiting_record_fills_the_action_that_clears_it(self):
        root = self.load_saved('build', title='Waits')
        cases = []
        with mock.patch.object(desk_migration, 'worker_in_progress', return_value=True):
            cases.append(('Check again', self.checked(root)))
        holder = self.load_saved('outline', title='Holder')
        (holder / engines.IN_HAND).write_text('outline\n')
        cases.append(('Check again', self.checked(root)))
        (holder / engines.IN_HAND).unlink()
        pending = holder / desk_migration.format.PENDING
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text('{}')
        cases.append(('Open Holder', self.checked(root)))
        pending.unlink()
        self.load_saved('unleveled', title='No review level')
        cases.append(('Start new work from this', self.checked(root)))
        for button, view in cases:
            with self.subTest(button):
                self.assertEqual(view['saved_record']['state'], 'waiting')
                _, shot = self.shot(root, view)
                self.assertEqual(shot['filled'], [button])
                self.assertIn('What it waits for', shot['text'])
                # Nothing is said to end by itself unless a step is known to run.
                self.assertNotIn('ends by itself', shot['text'])
                self.assertNotIn('Clear the step marker', shot['buttons'])
        # Someone else's: take it, to open it here.
        taken = {**cases[0][1], 'mine': False, 'driver': {'name': 'Alex', 'here': False},
                 'saved_record': {**cases[0][1]['saved_record'], 'action': 'take'}}
        _, shot = self.shot(root, taken)
        self.assertEqual(shot['filled'], ['Take it over'])

    def test_a_read_only_record_says_a_next_step_true_for_it(self):
        root = self.load_saved('research-plan', title='Nothing made')
        _, shot = self.shot(root, self.checked(root))
        self.assertEqual(shot['filled'], ['Start new work from this'])
        self.assertNotIn('Restore', shot['text'])
        self.assertIn('Its folder, with every saved file listed above'.lower(),
                      shot['text'].lower())

    def test_a_saved_deck_run_here_offers_no_hand_over(self):
        root = self.load_saved('build', title='Mine')
        view = self.checked(root)
        view = {**view, 'mine': True, 'driver': {'name': 'Alex', 'here': True, 'computer': 'x'}}
        _, shot = self.shot(root, view)
        self.assertNotIn('Hand over', shot['buttons'])

    def test_a_check_made_before_it_opened_is_made_again_and_then_kept(self):
        root = self.load_saved('build', title='Checked before')
        with mock.patch.object(desk_migration, 'worker_in_progress', return_value=True):
            before = self.checked(root)
        now = self.checked(root)
        self.assertEqual((before['saved_record']['state'], now['saved_record']['state']),
                         ('waiting', 'migrates'))
        # What the earlier check found is not shown as the screen opens: it checks again, and
        # while that has not answered the screen says only that it checks.
        refused = {'status': 409, 'body': {'error': 'The deck could not be read completely.'}}
        result = self.open_deck(str(root), before, [{'snapshot': 'opening'}],
                                **{'POST /api/saved-check': [refused],
                                   'GET /api/run': [ok(before)] * 4})
        opening = result['snapshots']['opening']
        self.assertEqual(self.posts(result), [('/api/saved-check', {'path': str(root)})])
        self.assertNotIn('What it waits for', opening['text'])
        self.assertIn(engines.SAVED_UNCHECKED, opening['text'])
        self.assertEqual(opening['filled'], ['Check how it goes on'])
        # Once it answers, the screen keeps what that check found, polls and all.
        result = self.open_deck(str(root), before, [{'poll': True}, {'poll': True},
                                                    {'snapshot': 'opened'}],
                                **{'POST /api/saved-check': [ok(now)],
                                   'GET /api/run': [ok(before)] + [ok(now)] * 6})
        opened = result['snapshots']['opened']
        self.assertEqual(self.posts(result), [('/api/saved-check', {'path': str(root)})])
        self.assertEqual(opened['filled'], ['Open on the desk'])
        self.assertNotIn('Checking how it goes on', opened['text'])

    def test_taking_a_saved_deck_says_what_taking_does(self):
        root = self.load_saved('build', title='Theirs')
        view = self.checked(root)
        view = {**view, 'mine': False, 'driver': {'name': 'Alex', 'here': False},
                'saved_record': {**view['saved_record'], 'state': 'waiting', 'action': 'take',
                                 'waiting': [desk_migration.NOT_OURS]}}
        result, _ = self.shot(root, view, [{'click': 'Take it over'}, {'snapshot': 'asked'}])
        shot = result['snapshots']['asked']
        self.assertIn('Take Theirs over from Alex?', shot['text'])
        self.assertIn('committed and shared as it is on this computer', shot['text'])
        self.assertIn('Nothing continues it until you open it there', shot['text'])
        self.assertNotIn('only its driver changes', shot['text'])
        self.assertNotIn('runs from this computer', shot['text'])

    def test_an_interrupted_opening_is_not_offered_for_deletion_on_a_list(self):
        root = self.load_saved('build', title='Interrupted listed')
        pending = root / desk_migration.format.PENDING
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text('{}')
        self.load_saved('outline', title='Deletable')
        result = self.run_page(self.answers(), [{'snapshot': 'home'}])
        shot = result['snapshots']['home']
        self.assertIn('Open Interrupted listed', shot['buttons'])
        self.assertNotIn('Delete Interrupted listed', shot['buttons'])
        self.assertIn('Delete Deletable', shot['buttons'])

    def test_saved_records_have_their_own_list_with_open(self):
        self.load_saved('build', title='Listed earlier')
        result = self.run_page(self.answers(), [{'snapshot': 'home'}])
        shot = result['snapshots']['home']
        self.assertIn('Saved by the earlier flow', shot['text'])
        self.assertIn('Open Listed earlier', shot['buttons'])
        self.assertNotIn('Review Listed earlier', shot['buttons'])
        self.assertNotIn('Needs you', shot['text'])


class DeskSteeringPageTests(test_desk_page.DeskPageCase):
    """The desk's Pause, Resume and Stop go through `steer` to /api/run, and a refusal changes
    nothing (fix round, ruling 6)."""

    working = test_desk_page.ProgressTests.working

    def test_pause_then_resume_post_to_the_run(self):
        path = self.desk_deck()
        working = self.working(path)
        paused = {**working, 'state': 'paused'}
        result = self.open_deck(path, working, [{'snapshot': 'working'}, {'click': 'Pause'}],
                                **{'POST /api/run': [ok(paused)]})
        self.assertIn('Stop', result['snapshots']['working']['buttons'])
        self.assertEqual(self.posts(result), [('/api/run', {'path': path, 'action': 'pause'})])
        result = self.open_deck(path, paused, [{'snapshot': 'paused'}, {'click': 'Resume'}],
                                **{'POST /api/run': [ok(working)]})
        self.assertNotIn('Pause', result['snapshots']['paused']['buttons'])
        self.assertEqual(self.posts(result), [('/api/run', {'path': path, 'action': 'resume'})])

    def test_a_refused_stop_changes_nothing_and_says_why(self):
        path = self.desk_deck()
        working = self.working(path)
        refused = {'status': 409, 'body': {'error': 'This deck is finished, so there is nothing '
                                                    'to stop.'}}
        result = self.open_deck(path, working, [{'click': 'Stop'}, {'snapshot': 'refused'}],
                                **{'POST /api/run': [refused]})
        shot = result['snapshots']['refused']
        self.assertEqual(self.posts(result), [('/api/run', {'path': path, 'action': 'stop'})])
        self.assertIn('This deck is finished, so there is nothing to stop. Nothing was changed.',
                      shot['toasts'])
        self.assertIn('Pause', shot['buttons'])
        self.assertIn('Stop', shot['buttons'])


class UnrenderedLookTests(runner_support.DeskCase):
    """Looks that cannot be rendered, on a desk deck (fix round, ruling 7)."""

    def test_a_deck_whose_looks_cannot_be_rendered_carries_on_in_the_default_look(self):
        from runner.steps import look as looks
        self.brand.run.unrenderable = 'No renderer here.'
        root = self.start_desk(look='pick')
        gate = self.view(root)['gate']
        self.assertEqual(gate['name'], 'gate:look')
        self.assertTrue(gate['offered']['failed'])
        # Drawn again, they still cannot be rendered, and the deck still waits for the pick.
        self.engine.desk_look_again(root)
        self.assertTrue(self.view(root)['gate']['offered']['failed'])
        self.engine.desk_look(root, looks.DEFAULT)
        self.on_desk(root)
        self.assertEqual(self.record(root)['gates']['gate:look']['state'], 'approved')
        self.assertEqual(looks.chosen(root)['shown'], 'unrendered')


class UnrenderedLookPageTests(test_desk_page.DeskPageCase):
    def test_the_look_pause_offers_the_default_look_and_drawing_again(self):
        self.brand.run.unrenderable = 'No renderer here.'
        path = self.started(flow='desk', look='pick')
        view = self.run_of(path)
        self.assertTrue(view['gate']['offered']['failed'])
        picked = self.post('desk-look', {'path': path, 'look': 'default'})
        result = self.open_deck(path, view, [{'snapshot': 'pause'},
                                             {'click': 'Use the brand’s default look'}],
                                **{'POST /api/desk-look': [ok(picked)]})
        shot = result['snapshots']['pause']
        self.assertEqual(shot['filled'], ['Use the brand’s default look'])
        self.assertIn('Draw the looks again', shot['buttons'])
        self.assertEqual(self.posts(result), [('/api/desk-look', {'path': path,
                                                                  'look': 'default'})])
