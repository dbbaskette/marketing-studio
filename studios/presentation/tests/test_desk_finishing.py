"""Finishing on the desk: the brand check, the deck's review, speaker notes and rehearse.
Every tool proposes, and nothing changes until Apply.

Every test runs the engine over the stand-ins, with scripted workers, a disposable data
folder, workspace and git identity. Nothing real is started.
"""
import json
import unittest
from pathlib import Path
from unittest import mock

from runner_support import LONG_OUTLINE, DeskCase
from workspace import WorkspaceError

from runner import desk, worker_tools
from runner.steps import build, finishing

MIXED = {'status': 'BLOCKED',
         'blockers': [{'slide': 6, 'says': 'A logo is missing.', 'code': 'LOGO'},
                      {'slide': 3, 'says': 'Text runs off the slide.', 'code': 'OUT_OF_BOUNDS'}],
         'warnings': [{'slide': 2, 'says': 'Text under 18 points.', 'code': 'SMALL_TEXT'},
                      {'says': 'The deck has no closing slide.', 'code': 'NO_CLOSING'}]}
BLOCKED = {'status': 'BLOCKED', 'warnings': [],
           'blockers': [{'slide': 3, 'says': 'Text runs off the slide.', 'code': 'OUT_OF_BOUNDS'}]}


def drawing_finding(number: int, note: str, fix: str):
    """A review that finds one major drawing problem on slide `number`."""
    def found(slides):
        slide = next(one for one in slides if one['number'] == number)
        return [{'slide': slide['id'], 'question': 6, 'severity': 'major', 'about': 'drawing',
                 'note': note, 'fix': fix}]
    return found


class FinishCase(DeskCase):
    def deck(self, **changes) -> Path:
        root = self.start_desk(look='default', **changes)
        self.on_desk(root)
        return root

    def seen(self, root: Path) -> int:
        return self.desk_view(root)['seen']

    def expected(self, root: Path) -> str:
        return self.desk_view(root)['expected']

    def finishing(self, root: Path, tool: str) -> dict:
        return self.desk_view(root)['finishing'][tool]

    def sections(self) -> int:
        return len(self.workers.of('section'))

    def kinds(self, since: int) -> list:
        return [kind for kind, _, _ in self.workers.jobs[since:]]


class BrandCheckTests(FinishCase):
    """Task 4.2: the brand check, in process, and the proposals it keeps."""

    def test_the_brand_check_lists_blockers_first_with_no_job(self):
        root = self.deck()
        jobs = len(self.workers.jobs)
        with mock.patch.object(self.brand, 'audit', return_value=MIXED):
            self.engine.desk_finish(root, 'brand', again=True)
        listed = finishing.brand(root, self.record(root))
        self.assertEqual([(one['kind'], one['number'], one['says']) for one in listed], [
            ('blocker', 3, 'Text runs off the slide.'), ('blocker', 6, 'A logo is missing.'),
            ('warning', 2, 'Text under 18 points.'),
            ('warning', None, 'The deck has no closing slide.')])
        ids = {slide['number']: slide['id'] for slide in LONG_OUTLINE['slides']
               for slide in [{**slide, 'number': LONG_OUTLINE['slides'].index(slide) + 1}]}
        self.assertEqual(listed[0]['slide'], ids[3])
        self.assertIsNone(listed[3]['slide'])
        self.assertEqual(self.kinds(jobs), [])
        shown = self.desk_view(root)
        self.assertEqual(shown['brand_check'], listed)
        self.assertTrue(shown['brand_current'])
        items = shown['finishing']['brand']['items']
        self.assertEqual([item.get('after') for item in items[:3]],
                         ["The brand's check: Text runs off the slide.",
                          "The brand's check: A logo is missing.",
                          "The brand's check: Text under 18 points."])
        self.assertEqual(items[3]['comment'], 'The deck has no closing slide.')
        # Each finding says what applying it redraws: its slide's section.
        card = next(card for part in shown['sections'] for card in part['slides']
                    if card['number'] == 3)
        self.assertEqual(items[0]['price'], card['price'])

    def test_the_last_render_s_check_is_kept_without_running_it_again(self):
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            root = self.deck()
        audited = len(self.brand.audited) if hasattr(self.brand, 'audited') else None
        self.engine.desk_finish(root, 'brand')
        items = self.finishing(root, 'brand')['items']
        self.assertEqual([item['says'] for item in items], ['Text runs off the slide.'])
        job = self.finishing(root, 'brand')['job']
        # Opened again, the same check keeps the same set.
        self.engine.desk_finish(root, 'brand')
        self.assertEqual(self.finishing(root, 'brand')['job'], job)
        if audited is not None:
            self.assertEqual(len(self.brand.audited), audited)

    def test_check_again_runs_the_audit_on_the_current_deck(self):
        root = self.deck()
        audit = mock.Mock(return_value=BLOCKED)
        with mock.patch.object(self.brand, 'audit', audit):
            self.engine.desk_finish(root, 'brand', again=True)
        (called,) = audit.call_args_list
        self.assertEqual(Path(called.args[0]), root / 'work' / 'deck.pptx')
        state = build.read_state(root)
        self.assertEqual(state['audit']['messages'], ['Slide 3: Text runs off the slide. (error)'])
        self.assertEqual(self.desk_view(root)['blockers'],
                         [{'number': 3, 'says': 'Text runs off the slide.'}])

    def test_apply_on_a_blocker_redraws_its_section_with_the_check_s_words(self):
        root = self.deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            self.engine.desk_finish(root, 'brand', again=True)
        kept = self.finishing(root, 'brand')
        jobs = len(self.workers.jobs)
        done = self.engine.desk_apply(root, kept['job'], ['p1'], self.seen(root))
        self.assertEqual(done['finished'], {'applied': 1, 'left': []})
        again = self.workers.jobs[jobs:]
        self.assertEqual([kind for kind, _, _ in again if kind == 'section'], ['section'])
        task = next(job.task for kind, job, _ in again if kind == 'section')
        self.assertIn('Draw section 1 of', task)
        self.assertIn("Slide 3: The brand's check: Text runs off the slide.", task)
        self.on_desk(root)
        self.assertEqual(self.finishing(root, 'brand')['items'][0]['state'], 'applied')
        # The slide's words before the note are kept, as Finishing's version.
        ident = LONG_OUTLINE['slides'][2]['id']
        self.assertEqual(desk.versions_of(root, ident)[0]['source'], 'finishing')

    def test_skip_changes_nothing(self):
        root = self.deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            self.engine.desk_finish(root, 'brand', again=True)
        kept = self.finishing(root, 'brand')
        before = {name: (root / name).read_bytes() for name in ('run.json', 'outline.json')}
        jobs, log = len(self.workers.jobs), self.log()
        done = self.engine.desk_skip(root, kept['job'], ['p1'])
        self.assertEqual(done['finished'], {'skipped': 1})
        self.assertEqual({name: (root / name).read_bytes() for name in before}, before)
        self.assertEqual((len(self.workers.jobs), self.log()), (jobs, log))
        self.assertEqual(self.finishing(root, 'brand')['items'][0]['state'], 'skipped')

    def test_the_proposals_wait_on_this_computer_only(self):
        root = self.deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            self.engine.desk_finish(root, 'brand', again=True)
        job = self.finishing(root, 'brand')['job']
        self.assertTrue((root / desk.PROPOSALS / f'{job}.json').is_file())
        self.assertNotIn(f'{job}.json', self.git('ls-files'))

    def test_an_apply_from_an_old_form_is_refused(self):
        root = self.deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            self.engine.desk_finish(root, 'brand', again=True)
        kept, seen = self.finishing(root, 'brand'), self.seen(root)
        self.engine.desk_words(root, 3, 'title', 'Batches restart in turn', seen, 'a' * 16)
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_apply(root, kept['job'], ['p1'], seen)
        self.assertEqual(str(caught.exception),
                         'This deck changed since you opened it. Reload to see the latest.')

    def test_a_gated_deck_has_no_finishing(self):
        root = self.gated()
        for name, given in (('desk_finish', ('brand',)), ('desk_apply', ('a' * 32, ['p1'], 1)),
                            ('desk_skip', ('a' * 32, ['p1']))):
            with self.subTest(route=name):
                with self.assertRaises(WorkspaceError) as caught:
                    getattr(self.engine, name)(root, *given)
                self.assertEqual(str(caught.exception), desk.NOT_ON_DESK)


class ReviewTests(FinishCase):
    """Task 4.3: Review the deck, with what it finds as proposals."""

    NOTE, FIX = 'The steps read right to left.', 'Draw them left to right.'

    def review(self, root: Path) -> dict:
        return self.engine.desk_finish(root, 'review', self.expected(root))

    def test_review_findings_arrive_as_proposals_and_nothing_is_redrawn(self):
        root = self.deck()
        self.workers.found = [drawing_finding(3, self.NOTE, self.FIX)]
        drawn = self.sections()
        self.review(root)
        self.assertEqual(len(self.workers.of('review')), 1)
        self.assertEqual(self.sections(), drawn)
        self.on_desk(root)
        items = self.finishing(root, 'review')['items']
        self.assertEqual([(item['number'], item['severity'], item['after']) for item in items],
                         [(3, 'major', f'{self.NOTE} {self.FIX}')])
        self.assertEqual(build.read_state(root)['repair'], [])
        record = self.record(root)
        self.assertNotIn('review_requested', record)
        self.assertTrue(self.desk_view(root)['reviewed'])

    def test_apply_on_a_finding_is_a_slide_note(self):
        root = self.deck()
        self.workers.found = [drawing_finding(3, self.NOTE, self.FIX)]
        self.review(root)
        kept = self.finishing(root, 'review')
        drawn = self.sections()
        self.engine.desk_apply(root, kept['job'], ['p1'], self.seen(root))
        tasks = [job.task for job in self.workers.of('section')[drawn:]]
        self.assertEqual(len(tasks), 1)
        self.assertIn(f'Slide 3: {self.NOTE} {self.FIX}', tasks[0])
        self.on_desk(root)
        notes = self.record(root)['desk_notes']
        self.assertEqual([(item['number'], item['note'], item['status']) for item in notes],
                         [(3, f'{self.NOTE} {self.FIX}', 'done')])

    def test_a_slide_note_after_a_review_is_not_reviewed_again(self):
        root = self.deck()
        self.workers.found = [drawing_finding(3, self.NOTE, self.FIX)]
        self.review(root)
        self.engine.desk_note(root, 6, 'Give the rollback its own row.', self.expected(root))
        self.on_desk(root)
        self.assertEqual(len(self.workers.of('review')), 1)

    def test_review_is_priced_from_its_last_try(self):
        root = self.deck()
        said = self.desk_view(root)['finish_prices']['review']
        self.assertTrue(said.endswith(desk.NO_RECORD), said)
        self.workers.cost = 0.42
        self.review(root)
        tried = self.record(root)['steps']['build-review']['tries'][-1]
        from studio_core import stops
        said = self.desk_view(root)['finish_prices']['review']
        self.assertIn(desk.LAST_TOOK.format(cost=stops.cost(tried['seconds'], tried['dollars'])),
                      said)

    def test_a_review_of_another_deck_is_refused(self):
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_finish(root, 'review', 'x')
        self.assertEqual(str(caught.exception), desk.CHANGED)
        self.assertEqual(self.workers.of('review'), [])

    def test_the_same_deck_is_not_reviewed_twice(self):
        root = self.deck()
        self.review(root)
        with self.assertRaises(WorkspaceError) as caught:
            self.review(root)
        self.assertEqual(str(caught.exception), finishing.REVIEWED)
        self.assertEqual(len(self.workers.of('review')), 1)

    def test_a_gated_deck_still_repairs_after_its_check(self):
        self.workers.found = [drawing_finding(5, self.NOTE, self.FIX)]
        root = self.gated(initial_review='user-first')
        drawn = self.sections()
        expected = self.view(root)['gate']['expected_deck']
        self.engine.review_draft(root, expected)
        tasks = [job.task for job in self.workers.of('section')[drawn:]]
        self.assertTrue(tasks)
        self.assertIn('Draw section 2 of', tasks[0])
        self.assertTrue(self.record(root).get('review_requested'))
        self.assertEqual(self.waiting(root), 'gate:build')


if __name__ == '__main__':
    unittest.main()
