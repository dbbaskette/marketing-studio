"""Decks the earlier step-by-step flow saved, as saved records (GitHub issue #542, the fix
round): an opening on the desk that was interrupted waits and is finished on the person's
word; a list says only what a current check found; a list and a poll read no material file;
a read-only record's next step is true for its reason; starting changes nothing in a saved
deck, and a dead step's marker is cleared only on the person's word; taking a saved deck
changes only its driver; and each state of the screen has one filled action."""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import runner_support
import test_desk_page
from runner import decks, desk_chat, desk_migration
from runner import engine as engines
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
    def test_a_list_says_only_what_a_current_check_found(self):
        root = self.load_saved('build', title='Listed')
        kind, brief = self.listed()[root.name]
        self.assertEqual((kind, brief['saved'], brief['sentence'], brief['needs']),
                         ('saved', 'unchecked', engines.SAVED_SAYS['unchecked'], False))
        with mock.patch.object(desk_migration, 'worker_in_progress', return_value=True):
            self.engine.saved_check(root)
        kind, brief = self.listed()[root.name]
        self.assertEqual((brief['saved'], brief['sentence']),
                         ('waiting', engines.SAVED_SAYS['waiting']))
        self.engine.saved_check(root)
        self.assertEqual(self.listed()[root.name][1]['sentence'], engines.SAVED_SAYS['migrates'])
        # Its record changed since: the list no longer says what the check found.
        os.utime(root / 'run.json', ns=(1, 1))
        self.assertEqual(self.listed()[root.name][1]['saved'], 'unchecked')
        # Files that cannot be read whole wait, and the list never says it opens.
        (root / 'linked.md').symlink_to(root / 'outline.md')
        saved = self.engine.saved_check(root)['saved_record']
        self.assertEqual((saved['state'], saved['action']), ('waiting', 'copy'))
        self.assertEqual(self.listed()[root.name][1]['sentence'], engines.SAVED_SAYS['waiting'])

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

    def test_starting_changes_nothing_in_a_saved_deck_and_its_marker_is_cleared_on_request(self):
        root = self.load_saved('build', title='Left marked')
        (root / engines.IN_HAND).write_text('outline\n')
        with open(root / 'outline.md', 'a') as stream:
            stream.write('\nA line not committed.\n')
        before = files_of(root)
        self.engine.resume()
        self.assertEqual(files_of(root), before)
        saved = self.engine.saved_check(root)['saved_record']
        self.assertEqual((saved['state'], saved['action'], saved['waiting']),
                         ('waiting', 'clear-marker', [engines.LEFTOVER_HERE]))
        # Another saved deck goes there to clear it.
        beside = self.load_saved('outline', title='Beside it')
        other = self.engine.saved_check(beside)['saved_record']
        self.assertEqual((other['action'], other['holder']['path']), ('open', str(root)))
        shown = self.engine.clear_marker(root)
        self.assertFalse((root / engines.IN_HAND).exists())
        del before[engines.IN_HAND]
        self.assertEqual(files_of(root), before)
        self.assertEqual(shown['saved_record']['state'], 'migrates')


class SavedTakeTests(runner_support.DeskCase, runner_support.TeamCase):
    def test_taking_a_saved_deck_changes_only_its_driver_and_then_it_opens_on_the_desk(self):
        root = self.load_saved('build', title='Taken')
        self.engine.share()
        other = self.theirs(self.blake, root)
        with self.be(self.blake):
            self.blake.engine.fetch()
            saved = self.blake.engine.saved_check(other)['saved_record']
            self.assertEqual((saved['state'], saved['action']), ('waiting', 'take'))
            before, raw = files_of(other), json.loads((other / 'run.json').read_bytes())
            self.blake.engine.drive(other, 'take')
            after = json.loads((other / 'run.json').read_bytes())
            # The same keys in the same order, each the same but the driver.
            self.assertEqual(list(after), list(raw))
            for key in raw:
                if key != 'driver':
                    self.assertEqual(after[key], raw[key], key)
            self.assertEqual(after['driver']['name'], 'Blake')
            now = files_of(other)
            self.assertEqual({name: data for name, data in now.items() if name != 'run.json'},
                             {name: data for name, data in before.items() if name != 'run.json'})
            # Nothing continues it, so there is no run to hand over.
            with self.assertRaises(WorkspaceError) as refused:
                self.blake.engine.drive(other, 'hand-over')
            self.assertEqual(str(refused.exception), engines.SAVED_FLOW_ENDED)
            # Taken, it opens on the desk here.
            preview = desk_chat.migration_preview(self.blake.engine, other)
            self.assertEqual(preview['blockers'], [])
            opened = desk_chat.migrate(self.blake.engine, other, preview['expected'])
            self.assertEqual(opened['execution'], 'conversation')

    def test_a_read_only_saved_deck_is_not_taken(self):
        root = self.load_saved('research-plan', title='Nothing made')
        self.engine.share()
        other = self.theirs(self.blake, root)
        with self.be(self.blake):
            self.blake.engine.fetch()
            before = files_of(other)
            with self.assertRaises(WorkspaceError) as refused:
                self.blake.engine.drive(other, 'take')
            self.assertEqual(str(refused.exception), engines.SAVED_NOT_TAKEN)
            self.assertEqual(files_of(other), before)


class SavedScreenTests(test_desk_page.DeskPageCase):
    """Every state of a saved record's screen has exactly one filled action."""

    def checked(self, root) -> dict:
        return self.post('saved-check', {'path': str(root)})

    def shot(self, root, view, steps=(), **more) -> dict:
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
        (root / engines.IN_HAND).write_text('outline\n')
        cases.append(('Clear the step marker', self.checked(root)))
        (root / engines.IN_HAND).unlink()
        holder = self.load_saved('outline', title='Holder')
        (holder / engines.IN_HAND).write_text('outline\n')
        cases.append(('Open Holder', self.checked(root)))
        (holder / engines.IN_HAND).unlink()
        self.load_saved('unleveled', title='No review level')
        cases.append(('Start new work from this', self.checked(root)))
        for button, view in cases:
            with self.subTest(button):
                self.assertEqual(view['saved_record']['state'], 'waiting')
                _, shot = self.shot(root, view)
                self.assertEqual(shot['filled'], [button])
                self.assertIn('What it waits for', shot['text'])
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
