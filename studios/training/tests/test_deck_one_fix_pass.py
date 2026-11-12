"""A desk deck checks its own slide text, gets one pass of fixes after its review, and waits
on the person only for a question that is theirs to answer."""
import copy
import json
from unittest import mock

from test_runner_deck import DeckCase, MAJOR, SAID, SMALL, with_slide
from runner_support import OUTLINE
import workspace
from runner import deck, drafts, pipeline

ASK = 'Should this slide promise zero downtime, or only fewer interruptions?'


def outline_jobs(workers) -> list[dict]:
    return [spec for kind, _, spec in workers.jobs if kind == 'outline']


class TextCheckTests(DeckCase):
    def says(self, said):
        """A worker that hands in `said` as what the deck says."""
        def act(tools, job):
            self.workers.outline_said = said
            return self.workers.outline(tools, job)
        return act

    def test_the_slide_text_is_checked_once_and_only_the_corrected_text_is_shown(self):
        self.engine.content_first = True
        written = with_slide(4, title='Chek what you can explain')
        corrected = with_slide(4, title='Check what you can explain')
        self.workers.then('outline', self.says(written), self.says(corrected))
        root = self.begin(flow='desk', slide_text_review=True)
        jobs = self.workers.of('outline')
        self.assertEqual(len(jobs), 2)
        self.assertIn('Write what', jobs[0].task)
        self.assertIn('Check the slide text', jobs[1].task)
        self.assertIn('Chek what you can explain', jobs[1].task,
                      'the checker is given the text as it was written')
        self.assertIn('Do not ask the person about anything you can look up', jobs[1].task)
        shown = self.view(root)['outline']
        self.assertTrue(shown['waiting'])
        self.assertEqual([slide['title'] for slide in shown['slides']],
                         [slide['title'] for slide in corrected['slides']])
        self.assertNotIn('findings', shown)
        kept = self.engine._load(root)['deck']['']['outline']
        self.assertEqual(kept['check'], pipeline.CHECKED_TEXT)
        # Checked text is not checked again: not by carrying on, and not for the words the
        # person asks for.
        self.engine.carry_on(root)
        self.assertEqual(len(self.workers.of('outline')), 2)
        self.engine.outline(root, None, 'revise', 'Shorten the first title.',
                            seen=shown['sha256'])
        self.assertEqual(len(self.workers.of('outline')), 3)
        self.assertTrue(self.view(root)['outline']['waiting'])
        self.assertFalse(self.workers.of('section'))

    def test_a_check_still_due_after_a_restart_runs_once_and_nothing_unchecked_is_shown(self):
        self.engine.content_first = True
        root = self.begin(flow='desk', slide_text_review=True)
        seen = self.view(root)['outline']['sha256']
        self.engine.outline(root, None, 'revise', 'Start again.', seen=seen)
        count = len(self.workers.of('outline'))
        # The run record as it stood when the engine went away between the two jobs.
        record = self.engine._load(root)
        record['deck']['']['outline']['check'] = pipeline.CHECK_DUE
        record['deck']['']['waiting'] = None
        self.engine._store(root, record)
        # As a restart reads it: from the files and the run record alone.
        found = self.engine._survey(root, record)
        self.assertTrue(found.decks[None].checking)
        self.assertNotIn('deck-outline', found.decks[None].done)
        self.assertEqual(found.next.step.doing, 'Checking the slide text of the slide deck')
        self.assertIsNone(self.view(root)['outline'])
        self.engine.carry_on(root)
        self.assertEqual(len(self.workers.of('outline')), count + 1)
        self.assertIn('Check the slide text', self.workers.of('outline')[-1].task)
        self.assertTrue(self.view(root)['outline']['waiting'])
        self.assertEqual(self.engine._load(root)['deck']['']['outline']['check'],
                         pipeline.CHECKED_TEXT)
        self.engine.carry_on(root)
        self.assertEqual(len(self.workers.of('outline')), count + 1)

    def test_a_check_that_never_finishes_keeps_the_text_and_stops_nothing(self):
        self.engine.content_first = True
        nothing = lambda tools, job: None
        self.workers.then('outline', self.says(OUTLINE), *[nothing] * pipeline.ATTEMPTS)
        root = self.begin(flow='desk', slide_text_review=True)
        view = self.view(root)
        self.assertIsNone(view['problem'])
        self.assertTrue(view['outline']['waiting'])
        self.assertEqual(self.engine._load(root)['deck']['']['outline']['check'],
                         pipeline.CHECK_LEFT)
        self.assertIn(pipeline.UNCHECKED, view['outline']['worth'])

    def test_with_text_approval_off_the_text_is_checked_before_anything_is_drawn(self):
        self.engine.content_first = True
        root = self.begin(flow='desk', slide_text_review=False)
        kinds = self.kinds()
        outlines = [index for index, kind in enumerate(kinds) if kind == 'outline']
        self.assertEqual(len(outlines), 2)
        self.assertLess(outlines[1], kinds.index('section'))
        self.assertEqual(self.engine._load(root)['deck']['']['outline']['check'],
                         pipeline.CHECKED_TEXT)


class FixPassTests(DeckCase):
    def card(self, root):
        return next(card for card in drafts.view(self.engine, root)['cards']
                    if card['kind'] == 'deck')

    def seen(self, root):
        return self.engine._load(root)['deck']['']['saved']['sha256']

    def test_one_pass_of_fixes_then_what_is_left_is_notes_that_wait_on_nobody(self):
        # A small thing about the drawing is fixed too; the review still finds a major
        # thing afterwards, and nothing is drawn a third time.
        again = {**MAJOR, 'slide': 'check-yourself'}
        self.workers.found = [[SMALL], [again], [again]]
        root = self.begin(flow='desk')
        self.to_end(root)
        built = self.built(root)
        self.assertEqual(len(built['rounds']), 2, 'one pass of fixes, and no second')
        self.assertEqual(len(self.workers.of('review')), 2)
        sections = [spec for kind, _, spec in self.workers.jobs if kind == 'section']
        self.assertEqual(len(sections), len(built['start']['sections']) + 1)
        fixed = sections[-1]
        self.assertIn('what the review found', [entry['name'] for entry in fixed['inputs']])
        self.assertNotIn('what the person asked', [entry['name'] for entry in fixed['inputs']])
        record = self.engine._load(root)
        self.assertEqual(record['deck']['']['fix_pass']['slides'], ['check-yourself'])
        self.assertEqual([note['status'] for note in record['deck']['']['notes']], ['done'])
        self.assertIsNone(record.get('question'))
        # What is left is kept to read, does not need the person and does not block Ready.
        card = self.card(root)
        self.assertEqual(card['state'], 'draft')
        self.assertEqual(card['needs'], [])
        self.assertEqual(len(card['notes']), 1)
        self.assertIn('Nothing there waits on you', card['says'])
        items = self.engine.deck_proposals(root, None)['review']['items']
        self.assertEqual([item['part'] for item in items], ['check-yourself'])
        told = drafts.standing(self.engine, root)
        self.assertEqual(told['phase'], 'drafts')
        self.assertEqual(told['counts']['attention'], 0)
        self.engine.mark_ready(root, 'deck', self.seen(root))
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'],
                         'approved')

    def test_a_clean_review_draws_nothing_again(self):
        self.workers.found = [[]]
        root = self.begin(flow='desk')
        self.to_end(root)
        self.assertEqual(len(self.built(root)['rounds']), 1)
        self.assertEqual(len(self.workers.of('review')), 1)
        self.assertEqual(self.card(root)['notes'], [])
        self.assertEqual(self.card(root)['says'], drafts.DRAFT)

    def test_a_later_change_by_the_person_gets_no_pass_of_fixes_of_its_own(self):
        self.workers.found = [[], [SMALL]]
        root = self.begin(flow='desk')
        self.to_end(root)
        count = len(self.workers.of('section'))
        self.engine.slide_note(root, None, 'check-yourself', 'Make the diagram larger.',
                               self.seen(root))
        self.to_end(root)
        self.assertEqual(len(self.workers.of('section')), count + 1)
        self.assertEqual(len(self.built(root)['rounds']), 2)
        self.assertEqual(len(self.card(root)['notes']), 1)

    def reworded(self, slide='the-objection', **changes):
        """A worker that corrects the words of one slide and copies the rest."""
        def act(tools, job):
            spec = tools.job['artifacts']['outline']
            made = copy.deepcopy(spec['previous'])
            next(one for one in made['slides'] if one['id'] == slide).update(changes)
            accepted = tools.submit_outline(json.dumps(made))
            assert accepted[0], accepted[1]
        return act

    def test_a_wording_finding_is_corrected_in_the_words_and_its_slide_drawn_again(self):
        self.workers.found = [[SAID], []]
        caveat = 'A restart still needs more than one instance.'
        self.workers.then('outline', self.workers.outline, self.workers.outline,
                          self.reworded(caveat=caveat))
        root = self.begin(flow='desk')
        self.to_end(root)
        fixer = outline_jobs(self.workers)[-1]
        self.assertEqual(len(outline_jobs(self.workers)), 3)
        self.assertFalse(fixer['ask'])
        self.assertIn('what the review found', [entry['name'] for entry in fixer['inputs']])
        self.assertNotIn('the-objection', fixer['artifacts']['outline']['frozen'])
        said = pipeline.outline_of(root, None)
        self.assertEqual(next(slide for slide in said['slides']
                              if slide['id'] == 'the-objection')['caveat'], caveat)
        record = self.engine._load(root)
        kept, built = record['deck'][''], self.built(root)
        digest = workspace.sha256_file(pipeline.place(root, None, pipeline.OUTLINE))
        self.assertEqual(kept['outline']['sha256'], digest)
        self.assertEqual(kept['approved']['sha256'], digest)
        self.assertEqual(built['start']['outline'], digest)
        self.assertEqual(kept['fix_pass']['words']['state'], pipeline.FIX_DONE)
        self.assertEqual(kept['fix_pass']['words']['slides'], ['the-objection'])
        # Its section is drawn again with the new words, and the review looks once more.
        sections = [spec for kind, _, spec in self.workers.jobs if kind == 'section']
        self.assertEqual(len(sections), len(built['start']['sections']) + 1)
        again = sections[-1]
        self.assertIn('what the review found', [entry['name'] for entry in again['inputs']])
        self.assertIn('Use the exact updated words', kept['notes'][-1]['note'])
        self.assertEqual(kept['notes'][-1]['by'], 'review')
        drawn = next(slide for slide in again['artifacts']['section']['slides']
                     if slide['id'] == 'the-objection')
        self.assertEqual(drawn['caveat'], caveat)
        self.assertEqual(len(built['rounds']), 2)
        self.assertEqual(len(self.workers.of('review')), 2)
        # The slide as it was is in its history, and nothing waits on the person.
        versions = drafts.slide_history(self.engine, root).kept('deck', 'the-objection')
        self.assertEqual(versions[0]['source'], 'review')
        card = self.card(root)
        self.assertEqual((card['state'], card['needs'], card['notes']), ('draft', [], []))
        self.assertIsNone(self.view(root)['problem'])

    def test_a_wording_fix_that_cannot_be_made_is_kept_as_a_note_and_stops_nothing(self):
        self.workers.found = [[SAID]]
        self.workers.then('outline', self.workers.outline, self.workers.outline,
                          lambda tools, job: None)
        root = self.begin(flow='desk')
        self.to_end(root)
        kept = self.engine._load(root)['deck']['']
        self.assertEqual(kept['fix_pass']['words']['state'], pipeline.FIX_LEFT)
        self.assertEqual(len(outline_jobs(self.workers)), 3, 'tried once, not again')
        self.assertEqual(len(self.built(root)['rounds']), 1)
        view, card = self.view(root), self.card(root)
        self.assertIsNone(view['problem'])
        self.assertEqual((card['state'], card['needs']), ('draft', []))
        self.assertEqual(len(card['notes']), 1)
        self.engine.mark_ready(root, 'deck', self.seen(root))

    def test_only_a_question_from_the_review_waits_on_the_person(self):
        asking = {**SAID, 'ask': ASK}
        self.workers.found = [[asking]]
        root = self.begin(flow='desk')
        self.to_end(root)
        # A finding that asks is not fixed without them: nothing reworded, nothing redrawn.
        self.assertEqual(len(outline_jobs(self.workers)), 2)
        self.assertEqual(len(self.built(root)['rounds']), 1)
        asked = self.engine._load(root)['question']
        self.assertIn(ASK, asked['text'])
        self.assertEqual(asked['deck']['level'], None)
        card = self.card(root)
        self.assertEqual(card['state'], 'needs')
        self.assertEqual(card['needs'], [drafts.ASKED])
        told = drafts.standing(self.engine, root)
        self.assertEqual((told['phase'], told['next']['kind']), ('decision', 'question'))
        with self.assertRaisesRegex(Exception, 'Settle what needs you'):
            self.engine.mark_ready(root, 'deck', self.seen(root))
        self.engine.answer(root, asked['id'], 'Only fewer interruptions.')
        record = self.engine._load(root)
        self.assertIsNone(record['question'])
        self.assertEqual(record['deck']['']['review_answers'][0]['answer'],
                         'Only fewer interruptions.')
        card = self.card(root)
        self.assertEqual((card['state'], card['needs']), ('draft', []))
        # Asked once: carrying on does not put it to them again.
        self.engine.carry_on(root)
        self.assertIsNone(self.engine._load(root)['question'])
        self.engine.mark_ready(root, 'deck', self.seen(root))

    def test_several_questions_are_put_as_one_numbered_question(self):
        first = {**SAID, 'ask': ASK}
        second = {**SMALL, 'ask': 'Is the footer line wanted on this slide at all?'}
        self.workers.found = [[first, second]]
        root = self.begin(flow='desk')
        self.to_end(root)
        text = self.engine._load(root)['question']['text']
        self.assertIn('2 questions', text)
        self.assertIn('1. Slide', text)
        self.assertIn('2. Slide', text)
        self.assertIn(ASK, text)

    def test_what_to_fix_is_chosen_by_what_a_finding_is_about(self):
        sections = [{'id': 'section-1', 'slides': ['what-it-does', 'the-objection']},
                    {'id': 'section-2', 'slides': ['check-yourself']}]
        numbered = [{**MAJOR, 'number': 2}, {**SAID, 'number': 3}, {**SMALL, 'number': 5},
                    {**SMALL, 'number': 5, 'ask': ASK, 'note': 'Another thing entirely.'},
                    {**SAID, 'number': 3, 'about': 'concept'},
                    {**SAID, 'number': 3, 'ask': ASK}]
        self.assertEqual([(note['slide'], note['section'])
                          for note in deck.to_fix(numbered, sections)],
                         [('what-it-does', 'section-1'), ('check-yourself', 'section-2')])
        self.assertEqual([(found['slide'], found['note'])
                          for found in deck.to_reword(numbered, sections)],
                         [('the-objection', SAID['note'])])
        self.assertEqual(len(deck.questions(numbered)), 2)


class StandingTests(DeckCase):
    def test_drafts_can_be_marked_ready_while_work_continues(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        with mock.patch.object(self.engine, '_state',
                               return_value=('working', 'Writing the brief.')):
            told = drafts.standing(self.engine, root)
        self.assertEqual((told['phase'], told['state']), ('working', 'in-progress'))
        self.assertIsNone(told['next'], 'nothing waits on the person')
        self.assertEqual(told['offer']['kind'], 'material')
        self.assertTrue(told['offer']['material'])
        self.assertTrue(told['offer']['label'].startswith('Review '))
        self.assertIn('ready to read and mark ready now, while the rest is made',
                      told['offer']['says'])

    def test_a_stopped_run_offers_resume(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        record = self.engine._load(root)
        record['halt'] = 'paused'
        self.engine._store(root, record)
        told = drafts.standing(self.engine, root)
        self.assertEqual(told['phase'], 'stopped')
        self.assertIsNone(told['next'])
        self.assertEqual(told['offer']['kind'], 'resume')
        self.assertEqual(told['offer']['label'], 'Resume training')
        self.assertIn('until you resume', told['offer']['says'])


WORDS = {'slide': 'the-objection', 'criterion': 'technical-fit', 'severity': 'major',
         'about': 'content', 'reason': 'The caveat pulls away from what the title claims.'}


class DesignedFixPassTests(DeckCase):
    """The same pass of fixes on a deck drawn from an approved design, which the slides tool
    reviews: corrected words become a design of their own that the sections are bound to."""
    WALKTHROUGH = True   # its decks walk through each slide's design

    def setUp(self):
        super().setUp()
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True    # the tool renders what it reviews with LibreOffice

    def test_corrected_words_are_bound_to_a_design_of_their_own_and_drawn_again(self):
        self.workers.found = [[WORDS], []]
        caveat = 'A restart still needs more than one instance.'
        self.workers.then('outline', self.workers.outline, self.workers.outline,
                          FixPassTests.reworded(self, caveat=caveat))
        root = self.begin(flow='desk')
        self.to_end(root)
        view = self.view(root)
        self.assertIsNone(view['problem'], view['problem'])
        record = self.engine._load(root)
        kept, built = record['deck'][''], self.built(root)
        self.assertEqual(kept['fix_pass']['words']['state'], pipeline.FIX_DONE,
                         kept['fix_pass']['words'])
        said = pipeline.outline_of(root, None)
        self.assertEqual(next(slide for slide in said['slides']
                              if slide['id'] == 'the-objection')['caveat'], caveat)
        # The words and the design they were put to the tool as are what everything is
        # bound to: the approval, the start and the design file.
        design = kept['approved']['design']
        self.assertRegex(design['project'], r'^deck/design-edits/[a-f0-9]{24}$')
        self.assertEqual(built['start']['design'], design)
        self.assertEqual(design['sha256'], workspace.sha256_file(
            pipeline.place(root, None, pipeline.DESIGN)))
        plan = json.loads(pipeline.place(root, None, pipeline.DESIGN).read_text())
        target = next(slide for slide in plan['slides'] if slide['id'] == 'the-objection')
        self.assertEqual(target['copy']['caveat'], caveat)
        self.assertEqual(self.slides.replies[-1]['decision'], 'approve')
        self.assertEqual(len(built['rounds']), 2)
        sections = [spec for kind, _, spec in self.workers.jobs if kind == 'section']
        self.assertEqual(len(sections), len(built['start']['sections']) + 1)
        drawn = next(slide for slide in sections[-1]['artifacts']['section']['slides']
                     if slide['id'] == 'the-objection')
        self.assertEqual(drawn['caveat'], caveat)
        card = next(card for card in drafts.view(self.engine, root)['cards']
                    if card['kind'] == 'deck')
        self.assertEqual((card['state'], card['needs']), ('draft', []))
