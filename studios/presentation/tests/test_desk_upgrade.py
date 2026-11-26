"""Upgrading a Selected changes deck to Redesign, keep content in place (issue #538).

The stand-in reads the deck given as three slides: a cover, slide 2 with its words in two
runs ("Ship apps " and "in minutes, not weeks.") and a hidden slide 3. The person named
slide 2 at the start, and its plan shortened the second run to "in minutes.". Upgrading
spends nothing: the deck waits for Start on its own priced step, and only then is the deck,
as it is now, read again and redrawn."""
import hashlib
import json
import unittest
from pathlib import Path

import helpers  # noqa: F401  sets PRESENTATION_STUDIO_DATA to a temporary folder

import runner_support
from runner_support import DeskCase
from test_desk_words import planned
from workspace import WorkspaceError

from runner import desk, stages
from runner.jobs import spent
from runner.steps import existing
from runner.steps import outline as outlines
from studio_core import presentation_migration, stops


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Upgrading(DeskCase):
    """A Selected changes deck on the desk, and its upgrade."""

    def deck(self, engine=None, **more) -> Path:
        self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
        root = self.existing_deck('automatic', 'selected', flow='desk',
                                  selected='Shorten the words on slide 2', **more)
        self.on_desk(root)
        return root

    def expected(self, root: Path) -> str:
        return self.desk_view(root)['expected']

    def upgrade(self, root: Path) -> dict:
        return self.engine.desk_upgrade(root, self.expected(root))

    def read_whole(self, root: Path):
        """An extract job that reads the deck word for word, as `read_word_for_word` does,
        into an outline with every field a saved outline carries (its delivery and each
        slide's speaker notes), so a conversation can read it."""
        from test_flow_routes import read_in

        def extract(tools, job):
            said = read_in(json.loads((root / outlines.INVENTORY).read_text(encoding='utf-8')))
            said['delivery'] = 'reading'
            for slide in said['slides']:
                slide.setdefault('notes', 'Say what this slide shows.')
            self.workers.outline_said = said
            self.workers._ok(tools.submit_outline(json.dumps(said)))
        return extract

    def redrawn(self, whole=False) -> Path:
        """Upgraded, started, its look picked, and back on the desk. `whole` reads it into an
        outline a conversation can read."""
        root = self.deck()
        self.upgrade(root)
        if whole:
            self.workers.queued['outline'] = [self.read_whole(root)]
        self.engine.desk_redesign_start(root)
        self.pick_look(root)
        self.on_desk(root)
        return root


class UpgradeTests(Upgrading):

    def test_a_selected_changes_deck_offers_the_upgrade_with_what_it_locks(self):
        root = self.deck()
        offered = self.desk_view(root)['upgrade']
        self.assertEqual(offered['action'], 'Upgrade to Redesign, keep content')
        self.assertEqual(offered['locked'], desk.UPGRADE_LOCKED)
        self.assertIn('nothing is spent until you press Start there', offered['confirm'])
        self.assertIn('This cannot be undone.', offered['confirm'])
        self.assertIsNone(offered['refused'])
        self.assertIsNone(self.desk_view(root)['upgraded'])

    def test_upgrading_spends_nothing_and_waits_on_a_priced_step(self):
        root = self.deck()
        record = self.record(root)
        jobs, cost = len(self.workers.jobs), spent(record)
        original = digest(root / existing.SOURCE)
        copy = digest(root / existing.PATCHED)
        inventory = (root / existing.INVENTORY).read_bytes()
        view = self.upgrade(root)
        # Nothing started, nothing spent, and nothing given was changed.
        self.assertEqual(len(self.workers.jobs), jobs)
        after = self.record(root)
        self.assertEqual(spent(after), cost)
        self.assertFalse((after['steps'].get('extract') or {}).get('tries'))
        self.assertEqual(digest(root / existing.SOURCE), original)
        self.assertEqual((root / existing.INVENTORY).read_bytes(), inventory)
        # The deck as it is now is kept as the redesign's own input.
        self.assertEqual(digest(root / existing.UPGRADED), copy)
        self.assertEqual(after['form']['level'], 'redesign')
        self.assertEqual(after['form']['selected'], 'Shorten the words on slide 2')
        made = after['upgraded']
        self.assertEqual((made['from'], made['to'], made['revision'], made['input'],
                          made['sha256'], made['by']),
                         ('selected', 'redesign', 0, existing.UPGRADED, copy, 'Alex'))
        self.assertTrue(made['at'] and made['arrived_at'])
        self.assertIn('## Change level\nredesign', (root / 'intake.md').read_text())
        # It waits for Start on a step that states the price, before the deck is read again.
        self.assertEqual(view['state'], 'waiting')
        self.assertEqual(view['sentence'], 'Waiting for you to start the redesign.')
        gate = view['gate']
        self.assertEqual(gate['name'], 'gate:redesign')
        self.assertIn('Your assistant reads your deck as it is now (3 slides)',
                      gate['price']['says'])
        # No redesign has run on this computer yet: it says so, and no cost it lacks.
        self.assertTrue(gate['price']['says'].endswith(desk.REDESIGN_NO_RECORD),
                        gate['price']['says'])
        self.assertIsNone(gate['elsewhere'])
        self.assertEqual(gate['upgraded']['says'], desk.UPGRADED_SAYS + desk.UPGRADED_BEFORE)
        names = [step.name for step in stages.steps(after)]
        self.assertEqual(names[names.index('gate:classify') + 1:names.index('extract') + 1],
                         ['gate:redesign', 'reinventory', 'extract'])
        # It is not on the desk until it is redrawn, and is not offered the upgrade again.
        self.assertFalse(view['desk']['arrived'])
        self.assertIsNone(view['desk']['upgrade'])
        self.assertEqual(view['desk']['upgraded']['revision'], 0)
        self.assertEqual(self.log()[-1].split(': ', 1)[-1],
                         'upgrade to Redesign, keep content: nothing is spent until the '
                         'redesign is started')
        # Waiting there, the runner starts nothing on its own.
        self.engine.wake(root)
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.waiting(root), 'gate:redesign')

    def test_start_reads_the_deck_as_it_is_now_and_keeps_every_change(self):
        root = self.deck()
        self.upgrade(root)
        original = digest(root / existing.SOURCE)
        view = self.engine.desk_redesign_start(root)
        # The inventory and the Before pictures are taken again from the deck as it was.
        found = json.loads((root / existing.INVENTORY).read_text())
        self.assertEqual(found['sha256'], digest(root / existing.UPGRADED))
        slide = next(one for one in found['slides'] if one['number'] == 2)
        words = [item['text'] for item in slide['objects']]
        self.assertIn('Ship apps in minutes.', words)
        self.assertNotIn('Ship apps in minutes, not weeks.', words)
        self.assertTrue((root / existing.ORIGINAL_SHOTS / existing.SHOTS).is_file())
        self.assertEqual(digest(root / existing.SOURCE), original)
        # The outline is read from it, every selected change in it.
        outline = json.loads((root / outlines.OUTLINE).read_text())
        said = json.dumps(outline)
        self.assertIn('in minutes.', said)
        self.assertNotIn('not weeks', said)
        record = self.record(root)
        self.assertEqual(record['gates']['gate:redesign']['state'], 'approved')
        self.assertEqual(record['gates']['gate:redesign']['by'], 'Alex')
        self.assertTrue(record['upgraded']['started_at'])
        self.assertEqual(view['gate']['name'], 'gate:look')
        self.pick_look(root)
        shown = self.on_desk(root)
        self.assertEqual(shown['desk']['level'], 'redesign')
        self.assertTrue(shown['desk']['arrived'])
        # Before is the deck as it was when it was upgraded.
        cards = [card for part in shown['desk']['sections'] for card in part['slides']]
        self.assertTrue(any(card['before'] for card in cards))
        self.assertIsNone(shown['desk']['notes_locked'])
        # It never waits on the priced step again.
        self.assertNotIn('gate:redesign', [step.name for step in stages.steps(record)
                                          if not stages._is_done(record, step)])

    def test_copy_as_new_brings_the_deck_it_is_redesigned_from(self):
        # GitHub issue #544: not the deck first given, which lacks the selected changes.
        import base64
        root = self.deck()
        self.upgrade(root)
        for upgraded in (self.engine.copy_setup(root),
                         (self.engine.desk_redesign_start(root), self.engine.copy_setup(root))[1]):
            brought = base64.b64decode(upgraded['upload']['encoded'])
            self.assertEqual(hashlib.sha256(brought).hexdigest(), digest(root / existing.UPGRADED))
            self.assertNotEqual(brought, (root / existing.SOURCE).read_bytes())
            self.assertEqual((upgraded['form']['level'], upgraded['upload']['name'],
                              upgraded['left']), ('redesign', 'old.pptx', []))
        # Where the copy kept at the upgrade is not on this computer, it is asked for again.
        (root / existing.UPGRADED).unlink()
        found = self.engine.copy_setup(root)
        self.assertIsNone(found['upload'])
        self.assertIn('old.pptx', found['left'][0])

    def test_a_delivered_revision_stays_delivered_and_the_redesign_is_the_next(self):
        root = self.deck()
        view = self.engine.desk_deliver(root, self.expected(root))
        self.assertEqual(view['state'], 'finished')
        before = self.record(root)
        receipts = view['desk']['receipts']
        shared = {path.name: path.read_bytes() for path in (root / 'deck.pptx',)
                  if path.is_file()}
        offered = view['desk']['upgrade']
        self.assertIn('Revision 1 stays delivered as it is; the redesign is delivered as '
                      'revision 2.', offered['confirm'])
        view = self.upgrade(root)
        after = self.record(root)
        self.assertEqual(after['revisions'], before['revisions'])
        self.assertEqual(view['desk']['receipts'], receipts)
        self.assertEqual({name: (root / name).read_bytes() for name in shared}, shared)
        self.assertIsNone(view['desk']['delivered'])
        self.assertEqual(after['upgraded']['revision'], 1)
        self.assertEqual(view['desk']['upgraded']['says'], desk.UPGRADED_SAYS
                         + desk.UPGRADED_AFTER.format(revision=1))
        self.engine.desk_redesign_start(root)
        self.pick_look(root)
        shown = self.on_desk(root)
        self.engine.desk_deliver(root, shown['desk']['expected'],
                                 shown['desk']['blockers_seen'])
        done = self.record(root)
        self.assertEqual(done['revisions'][0], before['revisions'][0])
        self.assertEqual([entry['revision'] for entry in done['revisions']], [1, 2])
        self.assertEqual(self.view(root)['desk']['receipts'][0], receipts[0])

    def test_the_upgrade_is_refused_while_a_job_runs_and_changes_nothing(self):
        root = self.deck()
        expected = self.expected(root)
        run = self.engine._run(root)
        run.busy = True
        try:
            self.assertEqual(self.desk_view(root)['upgrade']['refused'], desk.UPGRADE_BUSY)
            with self.assertRaisesRegex(WorkspaceError, desk.UPGRADE_BUSY):
                self.engine.desk_upgrade(root, expected)
        finally:
            run.busy = False
        record = self.record(root)
        # Each refusal says the one thing to do first.
        for change, said in (
                ({'desk_jobs': [{'kind': 'speaker-notes'}]}, desk.UPGRADE_BUSY),
                ({'halted': {'state': 'stopped', 'step': None, 'action': 'resume',
                             'why': 'Stopped on the page.'}}, desk.UPGRADE_HALTED),
                ({'question': {'id': 'q', 'text': 'Which slide?', 'from': 'patch'}},
                 desk.UPGRADE_QUESTION),
                ({'desk_notes': [{'id': 'n', 'number': 2, 'note': 'Shorter',
                                  'status': 'waiting'}]}, desk.UPGRADE_WAITING),
                ({'desk': {**record['desk'], 'edits': ['an edit']}}, desk.UPGRADE_WAITING)):
            with self.subTest(said=said):
                (root / 'run.json').write_text(json.dumps({**record, **change}))
                self.assertEqual(self.desk_view(root)['upgrade']['refused'], said)
                with self.assertRaisesRegex(WorkspaceError, said):
                    self.engine.desk_upgrade(root, expected)
        (root / 'run.json').write_text(json.dumps(record))
        self.assertEqual(self.record(root)['form']['level'], 'selected')
        self.assertFalse((root / existing.UPGRADED).exists())

    def test_an_outdated_page_is_refused(self):
        root = self.deck()
        with self.assertRaisesRegex(WorkspaceError, desk.CHANGED):
            self.engine.desk_upgrade(root, 'not-the-deck-on-screen')
        self.assertEqual(self.record(root)['form']['level'], 'selected')

    def test_one_way_only(self):
        root = self.deck()
        self.upgrade(root)
        with self.assertRaisesRegex(WorkspaceError, desk.UPGRADE_DONE):
            self.engine.desk_upgrade(root, 'anything')
        self.assertFalse(self.view(root)['undo'])
        with self.assertRaisesRegex(WorkspaceError, desk.UPGRADE_FINAL):
            self.engine.act(root, 'undo')
        # The priced step is the desk's own: no gate decision moves it.
        with self.assertRaises(WorkspaceError):
            self.engine.decide(root, 'gate:redesign', 'approve')
        self.engine.desk_redesign_start(root)
        with self.assertRaisesRegex(WorkspaceError, desk.REDESIGN_NOT_WAITING):
            self.engine.desk_redesign_start(root)

    def test_another_level_is_not_offered_the_upgrade(self):
        root = self.existing_deck('automatic', 'polish', flow='desk', look='default')
        self.on_desk(root)
        self.assertIsNone(self.desk_view(root)['upgrade'])
        with self.assertRaisesRegex(WorkspaceError, desk.UPGRADE_LEVEL):
            self.engine.desk_upgrade(root, self.expected(root))

    def test_a_deck_started_at_redesign_has_no_priced_step(self):
        root = self.existing_deck('automatic', 'redesign', flow='desk', look='default')
        self.on_desk(root)
        record = self.record(root)
        names = [step.name for step in stages.steps(record)]
        self.assertNotIn('gate:redesign', names)
        self.assertNotIn('reinventory', names)
        self.assertNotIn('gate:redesign', record['gates'])
        self.assertNotIn('upgraded', record)
        self.assertIsNone(self.desk_view(root)['upgraded'])
        # The pipeline of an ordinary redesign is as it was.
        self.assertEqual(names, ['intake-source', 'inventory', 'gate:classify', 'extract',
                                 'brand', 'look-preview', 'gate:look', 'build-start',
                                 'build-sections', 'build-whole', 'build-review',
                                 'build-repair', 'build-render', 'gate:build', 'deliver'])

    def test_the_record_keeps_a_schema_the_shared_check_accepts(self):
        # The tests' engine, and the engine as the page builds it, start a Selected changes
        # deck with no research: its schema is one the shared worker check accepts, and the
        # upgrade does not change that. Decks started with research (schemas 4 to 6) are
        # known to the check too since GitHub issue #541 was fixed; test_running_check_records
        # covers them.
        for engine in (self.engine, self.make(parallel_research=True, content_first=True,
                                              story_first=True, section_synthesis=True)):
            with self.subTest(production=engine is not self.engine):
                self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
                root = self.existing_deck('automatic', 'selected', flow='desk',
                                          selected='Shorten the words on slide 2',
                                          engine=engine)
                self.on_desk(root)
                before = self.record(root)
                self.assertTrue(presentation_migration.supported(before), before['schema'])
                engine.desk_upgrade(root, self.expected(root))
                after = self.record(root)
                self.assertEqual(after['schema'], before['schema'])
                self.assertTrue(presentation_migration.supported(after))


class UpgradeFixTests(Upgrading):
    """Start only where the deck kept at the upgrade is; a deck stopped at the priced step; an
    upgrade cut short; the price once this computer has a record; and an upgraded deck
    continued in conversation."""

    def test_start_is_refused_where_the_deck_kept_at_the_upgrade_is_not(self):
        # A teammate's computer that took the deck over has no sources/, which is never
        # shared. Standing in for it, the kept deck is moved away here, then brought back.
        root = self.deck()
        self.upgrade(root)
        kept = root / existing.UPGRADED
        away = root.parent / 'kept-elsewhere.pptx'
        kept.rename(away)
        jobs, record = len(self.workers.jobs), self.record(root)
        self.assertEqual(self.view(root)['gate']['elsewhere'], desk.REDESIGN_ELSEWHERE)
        with self.assertRaisesRegex(WorkspaceError, desk.REDESIGN_ELSEWHERE):
            self.engine.desk_redesign_start(root)
        # Nothing approved, written or started.
        self.assertEqual(self.record(root), record)
        self.assertEqual(self.waiting(root), 'gate:redesign')
        self.assertEqual(len(self.workers.jobs), jobs)
        # Back on the computer that upgraded it, Start works.
        away.rename(kept)
        self.assertIsNone(self.view(root)['gate']['elsewhere'])
        self.assertEqual(self.engine.desk_redesign_start(root)['gate']['name'], 'gate:look')

    def test_a_deck_stopped_at_the_priced_step_says_to_resume_it_first(self):
        root = self.deck()
        self.upgrade(root)
        self.engine.act(root, 'stop')
        self.assertEqual(self.desk_view(root)['redesign_stopped'], desk.REDESIGN_STOPPED)
        with self.assertRaisesRegex(WorkspaceError, desk.REDESIGN_STOPPED):
            self.engine.desk_redesign_start(root)
        self.engine.act(root, 'resume')
        self.assertIsNone(self.desk_view(root)['redesign_stopped'])
        self.assertEqual(self.waiting(root), 'gate:redesign')
        self.assertEqual(self.engine.desk_redesign_start(root)['gate']['name'], 'gate:look')

    def test_an_upgrade_cut_short_leaves_the_deck_as_it_was(self):
        from unittest import mock

        from runner.steps import build
        root = self.deck()
        self.engine.desk_deliver(root, self.expected(root))
        expected = self.expected(root)
        names = ('run.json', 'intake.md', 'deliver.json', 'README.md', str(build.STATE))
        before = {name: (root / name).read_bytes() for name in names}
        with mock.patch.object(self.engine, '_store', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.engine.desk_upgrade(root, expected)
        self.assertEqual({name: (root / name).read_bytes() for name in names}, before)
        self.assertFalse((root / existing.UPGRADED).exists())
        view = self.view(root)
        self.assertEqual(view['desk']['level'], 'selected')
        self.assertTrue(view['desk']['drawn_here'])
        self.assertIsNone(view['desk']['upgrade']['refused'])

    def test_the_price_says_how_long_the_steps_took_here_once_they_have(self):
        self.redrawn()
        self.workers.queued['outline'] = [runner_support.read_word_for_word(self)] * 4
        root = self.deck()
        says = self.upgrade(root)['gate']['price']['says']
        minutes = desk.estimate(self.record(root))
        self.assertTrue(minutes)
        self.assertTrue(says.endswith(desk.REDESIGN_TOOK.format(
            minutes=stops.lasted(minutes * 60))), says)
        # No cost is said that this deck has no record of, and no minutes are called a cost.
        self.assertNotIn('$', says)
        self.assertIn('no record yet of what a redesign costs', says)

    def test_an_upgraded_deck_continued_in_conversation_can_be_marked_ready(self):
        from runner import desk_chat
        root = self.redrawn(whole=True)
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['part'])
        shown = self.desk_view(root)
        self.assertTrue(shown['can_mark_ready'], shown['ready_problem'])
        context = desk_chat.context(self.engine, root, 'ready')
        request = {'expected_basis': context['expected_basis'],
                   'seen': context['requirements']['seen'],
                   'response': 'I looked at the redrawn deck and it is ready.'}
        self.assertTrue(desk_chat.ready(self.engine, root, request)['desk']['ready'])

    def test_conversation_checks_the_deck_kept_and_the_deck_given(self):
        from runner import desk_chat, desk_migration
        root = self.redrawn(whole=True)
        record = self.record(root)
        desk_migration.materials(record, desk_chat._files(root))
        for name in (existing.UPGRADED, existing.SOURCE):
            with self.subTest(name=name):
                kept = (root / name).read_bytes()
                (root / name).write_bytes(kept + b'changed')
                with self.assertRaises(ValueError):
                    desk_migration.materials(record, desk_chat._files(root))
                (root / name).write_bytes(kept)

    def test_a_deck_not_upgraded_is_checked_as_before(self):
        from runner import desk_chat, desk_migration
        root = self.existing_deck('automatic', 'redesign', flow='desk', look='default')
        self.on_desk(root)
        # The stand-in's outline as a saved one carries it, so the inventory check is reached.
        outline = json.loads((root / outlines.OUTLINE).read_text())
        outline['delivery'] = 'reading'
        for slide in outline['slides']:
            slide.setdefault('notes', 'Say what this slide shows.')
        (root / outlines.OUTLINE).write_text(json.dumps(outline))
        record = self.record(root)
        self.assertEqual(existing.given_name(record), existing.SOURCE)
        desk_migration.materials(record, desk_chat._files(root))
        # A file at the upgrade's name is never read for a deck that was not upgraded.
        (root / existing.UPGRADED).write_bytes(b'PK\x03\x04 not read')
        desk_migration.materials(record, desk_chat._files(root))
        (root / existing.SOURCE).write_bytes((root / existing.SOURCE).read_bytes() + b'x')
        with self.assertRaisesRegex(ValueError, 'The original deck differs from its saved '
                                                'inventory.'):
            desk_migration.materials(record, desk_chat._files(root))


class StagesTests(unittest.TestCase):

    def run_of(self, level: str, upgraded: bool) -> dict:
        return {'route': 'existing', 'flow': 'desk', 'form': {'route': 'existing', 'level': level},
                **({'upgraded': {'from': 'selected'}} if upgraded else {})}

    def test_only_an_upgraded_redesign_has_the_priced_step(self):
        for level, upgraded, has in (('redesign', True, True), ('redesign', False, False),
                                     ('selected', True, False), ('polish', True, False)):
            names = [step.name for step in stages.steps(self.run_of(level, upgraded))]
            with self.subTest(level=level, upgraded=upgraded):
                self.assertEqual('gate:redesign' in names, has)
                self.assertEqual('reinventory' in names, has)

    def test_the_priced_step_says_no_forbidden_word(self):
        for name in ('gate:redesign', 'reinventory'):
            step = stages.BY_NAME[name]
            for word in ('artifact', 'stale', 'lineage', '{'):
                self.assertNotIn(word, (step.label + step.doing).lower())


if __name__ == '__main__':
    unittest.main()
