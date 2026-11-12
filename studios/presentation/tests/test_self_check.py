"""A deck checks itself: its slide text before the person reads it, and the built deck in one
review with one pass of fixes before it reaches the desk.

Every test runs the engine over the stand-ins, with scripted workers, a disposable data
folder, workspace and git identity. Nothing real is started.
"""
import json
import unittest

from runner_support import LONG_OUTLINE, DeskCase, fails

from runner import stages
from runner.steps import build
from runner.steps import outline as outlines

CORRECTED = 'A rolling restart replaces instances in batches'


def corrected() -> dict:
    """The outline as the check hands it back: slide 2's title corrected."""
    said = json.loads(json.dumps(LONG_OUTLINE))
    said['slides'][1]['title'] = CORRECTED
    return said


class TextCheckTests(DeskCase):
    """The slide text is checked by a second assistant, once, before it is shown."""

    def setUp(self):
        super().setUp()
        self.engine.content_first = True

    def kinds(self) -> list:
        return [kind for kind, _, _ in self.workers.jobs]

    def test_the_text_is_checked_once_and_only_the_corrected_text_is_shown(self):
        self.workers.checked_said = corrected()
        root = self.start_desk(look='default')
        shown = self.view(root)
        gate = shown['gate']
        self.assertEqual(gate['name'], 'gate:outline')
        self.assertEqual(gate['slides'][1]['title'], CORRECTED)
        self.assertIn(CORRECTED, gate['text'])
        # The writer, then one check: and no list of what the check found.
        self.assertEqual(self.kinds(), ['outline', 'text-check'])
        self.assertNotIn('findings', gate)
        kind, job, spec = self.workers.jobs[-1]
        self.assertIn('Correct it yourself', job.guidance)
        self.assertFalse(spec['ask'])
        self.assertIn('The current outline', [one['name'] for one in spec['inputs']])
        record = self.record(root)
        self.assertTrue(outlines.text_checked(root, record))
        self.assertTrue(record['steps']['outline-check']['done'])
        self.assertEqual(shown['sentence'], 'Waiting for you to approve the slide text.')

    def test_the_page_says_the_text_is_being_checked(self):
        said = []

        def looking(tools, job):
            said.append(self.engine.view(self.root)['sentence'])
            return self.workers.text_check(tools, job)

        def writing(tools, job):
            # The deck's folder, read from the job that runs before the check.
            self.root = next(self.space.repo.rglob('run.json')).parent
            return self.workers.outline(tools, job)

        self.workers.then('outline', writing)
        self.workers.then('text-check', looking)
        self.start_desk(look='default')
        self.assertEqual(said, ['Checking the slide text.'])

    def test_a_rewrite_is_checked_once_and_never_loops(self):
        root = self.start_desk(look='default')
        gate = self.view(root)['gate']
        self.workers.outline_said = corrected()     # the writer's second draft says more
        self.engine.decide(root, 'gate:outline', 'changes', 'Clarify the first title.',
                           expected=gate['expected'])
        self.assertEqual(self.kinds(), ['outline', 'text-check', 'outline', 'text-check'])
        again = self.view(root)['gate']
        self.assertEqual(again['name'], 'gate:outline')
        check = self.workers.of('text-check')[-1]
        self.assertIn('Clarify the first title.', check.task)
        self.assertIn('Keep what the note asked for', check.task)
        self.assertNotIn("Read a person's note at a gate", check.guidance)
        self.engine.decide(root, 'gate:outline', 'approve', expected=again['expected'])
        self.assertEqual(self.waiting(root), 'gate:build')
        self.assertEqual(len(self.workers.of('text-check')), 2)

    def test_text_already_checked_is_not_checked_again(self):
        root = self.start_desk(look='default')
        with self.engine.files:
            record = self.engine._load(root)
            # As a runner stopped between keeping the check and noting its step.
            record['steps']['outline-check']['done'] = False
            record['gates']['gate:outline']['state'] = 'absent'
            self.engine._store(root, record)
            self.engine._commit(root, 'as a runner that stopped mid-way left it')
        self.engine.wake(root)
        self.assertEqual(self.kinds(), ['outline', 'text-check'])
        self.assertEqual(self.view(root)['gate']['name'], 'gate:outline')
        self.assertTrue(self.record(root)['steps']['outline-check']['done'])

    def test_a_check_that_does_not_finish_shows_the_text_as_written(self):
        self.workers.then('text-check', fails(), fails())
        root = self.start_desk(look='default')
        shown = self.view(root)
        self.assertIsNone(shown['problem'])
        self.assertEqual(shown['gate']['name'], 'gate:outline')
        self.assertEqual(len(self.workers.of('text-check')), 2)
        self.assertEqual(shown['gate']['slides'][1]['title'], LONG_OUTLINE['slides'][1]['title'])

    def test_a_deck_saved_before_keeps_the_steps_it_began_with(self):
        root = self.gated()
        self.assertNotIn('outline-check', [step.name for step in stages.steps(self.record(root))])
        self.assertEqual(self.workers.of('text-check'), [])


def finding(number: int, about: str = 'drawing', severity: str = 'major'):
    def found(slides):
        slide = next(one for one in slides if one['number'] == number)
        return [{'slide': slide['id'], 'question': 6, 'severity': severity, 'about': about,
                 'note': 'The steps read right to left.', 'fix': 'Draw them left to right.'}]
    return found


class FirstReviewTests(DeskCase):
    """The built deck is reviewed by itself, fixed in one pass and looked at again, before
    it reaches the desk."""

    def kinds(self) -> list:
        return [kind for kind, _, _ in self.workers.jobs]

    def test_the_review_runs_after_the_build_and_one_pass_of_fixes_then_stops(self):
        # Both reviews find it: the second sends nothing back.
        self.workers.found = [finding(3)] * 2
        root = self.start_desk(look='default')
        shown = self.on_desk(root)
        built = self.kinds()[self.kinds().index('review'):]
        self.assertEqual(built, ['review', 'section', 'review'])
        state = build.read_state(root)
        self.assertEqual(len(state['rounds']), 2)
        self.assertEqual(state['repair'], [])
        self.assertTrue(state['fix']['closed_at'])
        found = shown['desk']
        self.assertTrue(found['reviewed'])
        self.assertEqual(found['review_pass'],
                         {'found': 1, 'done': True, 'left': 1, 'rechecked': True})
        # What is left is a note: nothing but Deliver waits on the person.
        self.assertEqual([item['state'] for item in found['finishing']['review']['items']],
                         ['open'])
        self.assertTrue(found['deliverable'])
        self.assertIsNone(shown['question'])
        self.assertEqual(shown['sentence'], 'Ready to deliver.')
        self.assertTrue(self.engine._needs(self.record(root)).startswith('gate:gate:build'))

    def test_a_clean_review_draws_nothing_again(self):
        root = self.start_desk(look='default')
        shown = self.on_desk(root)
        self.assertEqual(self.kinds().count('review'), 1)
        self.assertEqual(len(build.read_state(root)['rounds']), 1)
        self.assertTrue(shown['desk']['reviewed'])
        self.assertIsNone(shown['desk']['review_pass'])

    def test_the_page_says_what_the_pass_is_doing(self):
        said = []

        def drawing(tools, job):
            said.append(self.engine.view(self.root)['sentence'])
            return self.workers.section(tools, job)

        def looking(tools, job):
            self.root = next(self.space.repo.rglob('run.json')).parent
            self.workers.then('section', drawing)
            if len(self.workers.of('review')) > 1:
                said.append(self.engine.view(self.root)['sentence'])
            return self.workers.review(tools, job)

        self.workers.then('review', looking, looking)
        self.workers.found = [finding(3)]
        root = self.start_desk(look='default')
        self.on_desk(root)
        self.assertEqual(said, ['Fixing what the review found: drawing 1 section again.',
                                'Checking the fixes.'])

    def test_a_review_that_does_not_finish_never_keeps_the_deck_from_the_desk(self):
        self.workers.then('review', fails(), fails())
        root = self.start_desk(look='default')
        shown = self.on_desk(root)
        self.assertIsNone(shown['problem'])
        self.assertFalse(shown['desk']['reviewed'])
        self.assertTrue(shown['desk']['deliverable'])

    def test_a_note_after_the_desk_runs_no_review(self):
        root = self.start_desk(look='default')
        self.on_desk(root)
        reviews = self.kinds().count('review')
        self.engine.desk_note(root, 4, 'Shorter.', self.view(root)['desk']['expected'])
        self.on_desk(root)
        self.assertEqual(self.kinds().count('review'), reviews)


if __name__ == '__main__':
    unittest.main()
