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
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED) as audit:
            root = self.deck()
            audited = audit.call_count
            self.engine.desk_finish(root, 'brand')
            items = self.finishing(root, 'brand')['items']
            self.assertEqual([item['says'] for item in items], ['Text runs off the slide.'])
            job = self.finishing(root, 'brand')['job']
            # Opened again, the same check keeps the same set.
            self.engine.desk_finish(root, 'brand')
            self.assertEqual(self.finishing(root, 'brand')['job'], job)
            self.assertEqual(audit.call_count, audited, 'the brand check is not run again')

    def test_a_check_again_that_fails_keeps_the_last_check(self):
        from runner import brand as brand_skill
        root = self.deck()
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            self.engine.desk_finish(root, 'brand', again=True)
        before = build.read_state(root)['audit']
        crashed = brand_skill.Refused(['The checker crashed.'])
        with mock.patch.object(self.brand, 'audit', side_effect=crashed), \
                self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_finish(root, 'brand', again=True)
        self.assertIn("The brand's check of this deck could not be run.", str(caught.exception))
        state = build.read_state(root)
        self.assertEqual(state['audit'], before)
        self.assertFalse(state.get('auditNote'))
        self.assertEqual(self.desk_view(root)['blockers'],
                         [{'number': 3, 'says': 'Text runs off the slide.'}])

    def test_again_is_true_or_false(self):
        root = self.deck()
        for given in (1, 0, 'yes'):
            with self.subTest(given=given):
                with self.assertRaises(WorkspaceError) as caught:
                    self.engine.desk_finish(root, 'brand', again=given)
                self.assertIn('true or false', str(caught.exception))

    def test_a_selected_changes_deck_has_no_finishing(self):
        from test_desk_words import planned
        self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
        root = self.existing_deck('automatic', 'selected', flow='desk',
                                  selected='Shorten the words on slide 2')
        self.on_desk(root)
        for name, given in (('desk_finish', ('brand',)), ('desk_finish', ('rehearse',)),
                            ('desk_apply', ('a' * 32, ['p1'], 1)),
                            ('desk_skip', ('a' * 32, ['p1']))):
            with self.subTest(route=name, given=given):
                with self.assertRaises(WorkspaceError) as caught:
                    getattr(self.engine, name)(root, *given)
                self.assertEqual(str(caught.exception), finishing.OWN_DECK)

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

    def test_a_finding_on_a_slide_redrawn_since_the_review_is_refused(self):
        root = self.deck()
        self.workers.found = [lambda slides: [*drawing_finding(3, self.NOTE, self.FIX)(slides),
                                              *drawing_finding(6, 'The rows crowd.', 'Space them.')(
                                                  slides)]]
        self.review(root)
        kept = self.finishing(root, 'review')
        self.assertEqual(kept['reviewed_deck'], build.read_state(root)['rounds'][-1]['deck'])
        self.engine.desk_note(root, 4, 'Shorter.', self.expected(root))   # section 1 again
        self.on_desk(root)
        items = {item['number']: item for item in self.finishing(root, 'review')['items']}
        self.assertFalse(items[3]['present'])
        self.assertTrue(items[6]['present'])
        drawn = self.sections()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_apply(root, kept['job'], [items[3]['id']], self.seen(root))
        self.assertEqual(str(caught.exception), 'This slide changed since this was found, so it '
                         'was not noted. Skip it.')
        self.assertEqual(self.sections(), drawn)
        self.engine.desk_apply(root, kept['job'], [items[6]['id']], self.seen(root))
        self.assertEqual(self.sections(), drawn + 1)

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

    def given_up(self, root: Path, steps: dict) -> None:
        """The review that stopped is given up: the desk rests as it did before it."""
        shown = self.view(root)
        self.assertTrue(shown['desk']['working']['halted'])
        self.assertFalse(shown['desk']['reviewing'])
        self.engine.desk_stop(root)
        record = self.record(root)
        self.assertNotIn('review_requested', record)
        self.assertIsNone(record['halted'])
        self.assertEqual({name: record['steps'][name]['done'] for name in steps}, steps)
        shown = self.on_desk(root)
        self.assertTrue(shown['desk']['deliverable'])
        self.assertIsNone(shown['desk']['working'])
        self.assertEqual(len(self.workers.of('review')), self.reviews)

    def test_a_review_that_fails_can_be_given_up(self):
        from runner_support import fails
        root = self.deck()
        self.workers.then('review', *[fails()] * 3)
        self.review(root)
        self.reviews = len(self.workers.of('review'))
        self.assertEqual(self.view(root)['problem']['state'], 'failed')
        self.given_up(root, {'build-review': True, 'build-repair': True, 'build-render': True})

    def test_a_review_that_is_stopped_can_be_given_up(self):
        root = self.deck()

        def stopping(tools, job):
            self.engine.act(root, 'stop')
            return self.workers.review(tools, job)

        self.workers.then('review', stopping)
        self.review(root)
        self.reviews = len(self.workers.of('review'))
        self.assertEqual(self.record(root)['halted']['state'], 'stopped')
        self.given_up(root, {'build-review': True, 'build-repair': True, 'build-render': True})

    def test_a_review_under_way_says_so(self):
        root = self.deck()
        seen = []

        def looking(tools, job):
            seen.append(self.desk_view(root))
            return self.workers.review(tools, job)

        self.workers.then('review', looking)
        self.review(root)
        self.assertTrue(seen[0]['reviewing'])
        self.assertEqual(seen[0]['working']['what'], desk.REVIEWING)

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


class SpeakerNotesTests(FinishCase):
    """Task 4.4: speaker notes proposed by a job, applied through the notes edit."""

    def propose(self, root: Path) -> dict:
        self.engine.desk_finish(root, 'notes')
        self.on_desk(root)
        return self.finishing(root, 'notes')

    def test_speaker_notes_are_proposed_per_slide(self):
        root = self.deck()
        before = (root / 'outline.json').read_bytes()
        kept = self.propose(root)
        self.assertEqual(len(self.workers.of('speaker-notes')), 1)
        content = [(number, slide) for number, slide in enumerate(LONG_OUTLINE['slides'], 1)
                   if slide.get('kind') not in build.LEADS]
        self.assertEqual([(item['number'], item['part']) for item in kept['items']],
                         [(number, slide['id']) for number, slide in content])
        first = kept['items'][0]
        self.assertEqual(first['before'], content[0][1].get('notes') or '')
        self.assertEqual(first['after'], f"Say why {content[0][1]['id']} matters, then lead on.")
        self.assertEqual((root / 'outline.json').read_bytes(), before)
        self.assertEqual(self.desk_view(root)['finish_prices']['notes'].split('.')[0],
                         finishing.NOTES_SAYS.split('.')[0])

    def test_apply_writes_notes_with_no_section_job(self):
        root = self.deck()
        kept = self.propose(root)
        drawn = self.sections()
        first, second = kept['items'][:2]
        self.engine.desk_apply(root, kept['job'], [first['id'], second['id']], self.seen(root))
        self.on_desk(root)
        self.assertEqual(self.sections(), drawn)
        slides = {slide['id']: slide for slide in
                  json.loads((root / 'outline.json').read_text())['slides']}
        self.assertEqual(slides[first['part']]['notes'], first['after'])
        self.assertEqual(slides[second['part']]['notes'], second['after'])
        states = [item['state'] for item in self.finishing(root, 'notes')['items']]
        self.assertEqual(states[:2], ['applied', 'applied'])
        self.assertEqual(desk.versions_of(root, first['part'])[0]['source'], 'finishing')

    def test_an_edited_proposal_writes_the_person_s_words(self):
        root = self.deck()
        kept = self.propose(root)
        first = kept['items'][0]
        self.engine.desk_apply(root, kept['job'], [{'id': first['id'], 'after': 'My own words.'}],
                               self.seen(root))
        self.on_desk(root)
        slide = next(one for one in json.loads((root / 'outline.json').read_text())['slides']
                     if one['id'] == first['part'])
        self.assertEqual(slide['notes'], 'My own words.')

    def test_notes_typed_since_are_not_overwritten(self):
        root = self.deck()
        kept = self.propose(root)
        first = kept['items'][0]
        self.engine.desk_notes(root, first['number'], 'Typed since.', self.seen(root), 'b' * 16)
        self.on_desk(root)
        self.assertFalse(self.finishing(root, 'notes')['items'][0]['present'])
        with self.assertRaises(WorkspaceError):
            self.engine.desk_apply(root, kept['job'], [first['id']], self.seen(root))

    def test_a_proposal_naming_a_slide_the_deck_lacks_is_refused_by_the_check(self):
        tools = []

        def lacking(given, job):
            made = [{'slide': 's9', 'notes': 'Notes for a slide that is not there.'}]
            tools.append(given.submit_artifact('speaker-notes', json.dumps(made)))
            return self.workers.speaker_notes(given, job)

        self.workers.then('speaker-notes', lacking)
        root = self.deck()
        self.propose(root)
        (said,) = tools
        self.assertFalse(said[0])
        self.assertIn('s9 is not a slide of this deck.', said[1])
        problems = finishing.check_speaker_notes(json.dumps([
            {'slide': LONG_OUTLINE['slides'][1]['id'], 'notes': 'x' * 4001}]),
            {'slides': [LONG_OUTLINE['slides'][1]['id']]})[0]
        ident = LONG_OUTLINE['slides'][1]['id']
        self.assertEqual(problems, [f'Keep the notes of {ident} to 4,000 characters.'])
        self.assertIs(worker_tools.validator('speaker-notes'), finishing.check_speaker_notes)

    def test_the_job_reads_the_outline_and_the_sources(self):
        root = self.deck()
        self.engine.desk_source(root, None, text='Each batch waits for its health checks.',
                                title='Runbook')
        read = {}

        def reading(tools, job):
            for name in ('outline', 'sources', 'slides'):
                read[name] = tools.read_input(name)[1]
            return self.workers.speaker_notes(tools, job)

        self.workers.then('speaker-notes', reading)
        self.propose(root)
        self.assertEqual(json.loads(read['outline'])['slides'][1]['id'],
                         LONG_OUTLINE['slides'][1]['id'])
        self.assertIn('Each batch waits for its health checks.', read['sources'])
        self.assertEqual(len(json.loads(read['slides'])), len(LONG_OUTLINE['slides']))
        job = self.workers.of('speaker-notes')[0]
        self.assertTrue(self.workers.jobs[-1][1].guidance.startswith('# Proposing speaker notes'))
        self.assertIn('20 minutes', job.task)

    def test_one_change_at_a_time(self):
        root = self.deck()
        refused = []

        def again(tools, job):
            with self.assertRaises(WorkspaceError) as caught:
                self.engine.desk_finish(root, 'notes')
            refused.append(str(caught.exception))
            return self.workers.speaker_notes(tools, job)

        self.workers.then('speaker-notes', again)
        self.propose(root)
        self.assertEqual(refused, [desk.ONE_CHANGE])

    def stopped_job(self, root: Path, kind: str) -> None:
        """The job of `kind` that was stopped is given up with Stop, and the desk takes the
        next change."""
        record = self.record(root)
        self.assertEqual(record['halted']['state'], 'stopped')
        self.assertTrue(record['desk_jobs'])
        self.assertTrue(self.desk_view(root)['working']['halted'])
        self.engine.desk_stop(root)
        record = self.record(root)
        self.assertEqual((record.get('desk_jobs'), record['halted']), ([], None))
        self.on_desk(root)
        self.engine.desk_note(root, 6, 'Give the rollback its own row.', self.expected(root))
        self.assertEqual(self.record(root)['desk_notes'][-1]['status'], 'done')

    def stopping(self, root: Path, kind: str):
        def act(tools, job):
            self.engine.act(root, 'stop')
            return getattr(self.workers, kind.replace('-', '_'))(tools, job)
        return act

    def test_a_stopped_speaker_notes_job_is_given_up(self):
        root = self.deck()
        self.workers.then('speaker-notes', self.stopping(root, 'speaker-notes'))
        self.engine.desk_finish(root, 'notes')
        self.stopped_job(root, 'speaker-notes')
        self.assertNotIn('notes', self.desk_view(root)['finishing'])

    def test_a_stopped_words_job_is_given_up(self):
        root = self.deck()
        self.workers.then('words', self.stopping(root, 'words'))
        self.engine.desk_selection(root, 3, ('points', 0, 'text'), 0, 3, 'rephrase', None,
                                   self.seen(root))
        self.stopped_job(root, 'words')


class RehearseTests(FinishCase):
    """Task 4.5: rehearse, counted in process."""

    @staticmethod
    def outline(*notes, kinds=None) -> dict:
        kinds = kinds or ['content'] * len(notes)
        return {'slides': [{'id': f'slide-{at}', 'kind': kind, 'title': 'A slide',
                            **({'notes': said} if said else {})}
                           for at, (said, kind) in enumerate(zip(notes, kinds), 1)]}

    @staticmethod
    def words(count: int) -> str:
        return ' '.join(['word'] * count)

    def test_rehearse_counts_notes_at_150_words_a_minute(self):
        self.assertEqual(finishing.WPM, 150)
        shown = finishing.rehearse(self.outline(self.words(300), self.words(150), None), 20)
        self.assertEqual([one['minutes'] for one in shown['slides']], [2, 1, 0])
        self.assertEqual(shown['total'], 3)
        self.assertEqual(shown['says'], "Slide 1's notes take about 2 minutes; the deck's notes "
                         'take about 3 of your 20 minutes.')

    def test_rehearse_names_the_slides_that_run_long(self):
        # 25 minutes over 5 content slides: a slide is long past 10 minutes. Counted over all
        # 7 slides, it would be long past 7 minutes, and slide 2 would be named too; the lead
        # slides' notes are counted in the time but never named.
        notes = [self.words(150 * 8), *[self.words(150 * 7)] * 3, self.words(150 * 11)]
        shown = finishing.rehearse(self.outline(self.words(150 * 12), *notes, None,
                                                kinds=['cover', *['content'] * 5, 'closing']), 25)
        self.assertEqual(shown['long'], [6])
        self.assertEqual(shown['total'], 52)
        self.assertEqual(shown['says'], "Slide 1's notes take about 12 minutes; the deck's notes "
                         'take about 52 of your 25 minutes.')

    def test_rehearse_says_a_short_time_as_under_a_minute(self):
        shown = finishing.rehearse(self.outline(self.words(30), self.words(20)), 20)
        self.assertEqual(shown['says'], "Slide 1's notes take under a minute; the deck's notes "
                         'take under a minute of your 20 minutes.')
        shown = finishing.rehearse(self.outline(self.words(30)), None)
        self.assertEqual(shown['says'], "The deck's notes take under a minute.")

    def test_rehearse_with_no_minutes_says_the_time_alone(self):
        shown = finishing.rehearse(self.outline(self.words(450), self.words(150)), None)
        self.assertEqual(shown['says'], "The deck's notes take about 4 minutes.")
        self.assertEqual(shown['long'], [])

    def test_rehearse_starts_no_job(self):
        root = self.deck()
        jobs, log = len(self.workers.jobs), self.log()
        shown = self.engine.desk_finish(root, 'rehearse')['desk']['rehearse']
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.log(), log)
        outline = json.loads((root / 'outline.json').read_text())
        self.assertEqual(shown, finishing.rehearse(outline, 20))


if __name__ == '__main__':
    unittest.main()
