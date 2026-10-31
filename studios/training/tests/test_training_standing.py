"""One standing for a desk training on every screen (issue #220): Home, Trainings, Status
and the desk read the same `drafts.standing`, so a finished writing job with a major review
finding needs the person everywhere, drafts that exist are never "still to make", and a deck
waiting for its slide text says so instead of "Writing". Scripted workers and the stand-ins
of the deck tests; nothing real is started and nothing leaves this computer. Tests named
row_194 to row_196 cover those rows of the state-transition matrix in
docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md."""
import json  # noqa: I001  the path-setting imports must come before runner

import helpers  # noqa: F401
import desk
import workspace
from test_runner_deck import DeckCase, MAJOR

from runner import drafts, page, pipeline

STANDING_FIELDS = {'state', 'phase', 'words', 'sentence', 'level', 'counts', 'levels', 'next',
                   'kinds'}
COUNT_FIELDS = {'materials', 'to_write', 'updating', 'drafts', 'attention', 'decision', 'ready'}


class StandingTests(DeckCase):

    def listed(self, root):
        """What Home and Trainings read of the training, as the runner's page lists it."""
        listing = page.RunnerPage(8765, self.engine).trainings()
        return next(item for item in listing if item['path'] == str(root)), listing

    def seen(self, root, name):
        session = workspace.load(root)
        return workspace.sha256_file(root / workspace.artifact(root, session, name)['file'])

    def two_levels_with_a_major_finding(self):
        """The audited sequence: two levels, every draft written, and a major review finding
        kept on the level 101 deck."""
        self.workers.found = [[MAJOR], [], [], []]
        root = self.begin(levels=['101', '201'])
        self.assertEqual(self.to_end(root), [])
        return root

    def test_row_194_every_screen_agrees_on_a_finished_job_that_needs_attention(self):
        root = self.two_levels_with_a_major_finding()
        jobs, commits = len(self.workers.jobs), self.log()
        item, listing = self.listed(root)
        detail = page.RunnerPage(8765, self.engine).detail(str(root))
        shown = drafts.view(self.engine, root)
        told = shown['standing']
        self.assertEqual(set(told), STANDING_FIELDS)
        self.assertEqual(set(told['counts']), COUNT_FIELDS)
        # Home, Trainings, the training's own screen and the desk say one thing.
        for where in (item, detail):
            with self.subTest(where='detail' if where is detail else 'list'):
                self.assertEqual(where['standing'], told)
                self.assertEqual(where['state'], 'needs-you')
                self.assertEqual(where['sentence'], told['sentence'])
                self.assertFalse(where['ready'])
        self.assertEqual((told['phase'], told['words']), ('attention', 'Needs attention'))
        self.assertEqual(told['next'], {'kind': 'material', 'label': 'Review the level 101 '
                                        'slide deck', 'material': 'deck@101', 'level': '101',
                                        'slide': MAJOR['slide']})
        self.assertTrue(told['sentence'].startswith(
            'The level 101 slide deck needs attention before it can be marked ready.'))
        self.assertIn('9 drafts to mark ready', told['sentence'])
        self.assertEqual(shown['needs'], ['the level 101 slide deck'])
        # Still to write counts drafts that do not exist yet: all ten do.
        self.assertEqual(told['counts'], {'materials': 10, 'to_write': 0, 'updating': 0,
                                          'drafts': 9, 'attention': 1, 'decision': 0,
                                          'ready': 0})
        self.assertEqual((item['to_make'], item['to_write'], item['to_review'],
                          item['attention']), (0, 0, 9, 1))
        self.assertEqual(told['levels']['101']['attention'], 1)
        self.assertEqual(told['levels']['201'], {**told['levels']['201'], 'attention': 0,
                                                 'drafts': 5})
        # The row of stages never calls a stage done that is not Ready, nor the index begun.
        stages = {stage['stage']: stage['state'] for stage in item['stages']}
        self.assertEqual(stages['deck'], 'review')
        self.assertEqual(stages['package'], 'not-started')
        self.assertEqual({stages[name] for name in drafts.ORDER if name in stages}, {'review'})
        # The next thing that needs the person, after any decision, is this training.
        self.assertEqual(desk.next_up(listing)['path'], str(root))
        # Reading every screen started nothing and changed nothing.
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.log(), commits)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_row_195_marking_one_material_ready_changes_only_its_own_standing(self):
        root = self.two_levels_with_a_major_finding()
        before = {card['name']: card['state'] for card in drafts.view(self.engine, root)['cards']}
        self.engine.mark_ready(root, 'document@201', seen=self.seen(root, 'document@201'))
        after = drafts.view(self.engine, root)
        now = {card['name']: card['state'] for card in after['cards']}
        self.assertEqual({name for name in now if now[name] != before[name]}, {'document@201'})
        self.assertEqual(now['document@201'], 'ready')
        counts = after['standing']['counts']
        self.assertEqual((counts['drafts'], counts['ready'], counts['attention']), (8, 1, 1))
        self.assertEqual(after['standing']['levels']['201']['ready'], 1)
        self.assertEqual(after['standing']['next']['material'], 'deck@101')

    def test_drafts_with_nothing_to_settle_wait_for_mark_ready_and_then_are_ready(self):
        root = self.begin(levels=['101'])
        self.assertEqual(self.to_end(root), [])
        item = self.listed(root)[0]
        told = item['standing']
        self.assertEqual((item['state'], told['phase'], told['words']),
                         ('needs-you', 'drafts', 'Drafts to mark ready'))
        drafted = told['counts']['drafts']
        self.assertEqual(told['sentence'], f'{drafted} drafts to read and mark ready.')
        self.assertEqual(told['next']['material'], 'blueprint@101')
        self.assertNotEqual(item['state'], 'finished')
        session = workspace.load(root)
        seen = {name: self.seen(root, name) for name in drafts.level_ready(root, session, '101')}
        self.engine.mark_level_ready(root, '101', seen)
        self.assertEqual(self.to_end(root), [])
        self.assertTrue((root / pipeline.INDEX).is_file())
        item = self.listed(root)[0]
        self.assertEqual((item['state'], item['standing']['phase'], item['standing']['words']),
                         ('finished', 'ready', 'Ready'))
        self.assertIsNone(item['standing']['next'])
        self.assertTrue(item['ready'])
        stages = {stage['stage']: stage['state'] for stage in item['stages']}
        self.assertEqual(stages['package'], 'done')

    def test_row_196_a_deck_waiting_for_its_slide_text_says_so_and_nothing_writes(self):
        self.engine.content_first = True
        root = self.begin(levels=['101', '201'])
        shown = drafts.view(self.engine, root)
        cards = {card['name']: card for card in shown['cards']}
        self.assertEqual((cards['deck@101']['state'], cards['deck@101']['says']),
                         ('decide', drafts.TEXT_APPROVAL))
        self.assertEqual(cards['deck@101']['actions'], [])
        # The run waits for the person: what is not written yet is not said to be writing.
        unwritten = [card for card in shown['cards'] if not card['seen']]
        self.assertTrue(unwritten)
        self.assertNotIn('writing', {card['state'] for card in unwritten})
        told = shown['standing']
        self.assertEqual((told['state'], told['phase'], told['words']),
                         ('needs-you', 'decision', 'Needs your text approval'))
        self.assertEqual((told['next']['kind'], told['next']['material'], told['next']['level'],
                          told['next']['label']),
                         ('text', 'deck@101', '101', 'Review the slide text for level 101'))
        self.assertEqual(told['counts']['decision'], 1)
        item = self.listed(root)[0]
        self.assertEqual((item['state'], item['standing']), ('needs-you', told))
        self.assertFalse(self.workers.of('section'), 'nothing is drawn before the decision')

    def test_a_saved_run_keeps_its_own_words(self):
        root = self.saved_begin(levels=['101'])
        self.to_end(root)
        item = self.listed(root)[0]
        self.assertNotIn('standing', item)
        self.assertIsNone(drafts.standing(self.engine, root))

    def test_the_standing_is_plain_json(self):
        root = self.two_levels_with_a_major_finding()
        told = drafts.standing(self.engine, root)
        self.assertEqual(json.loads(json.dumps(told)), told)
