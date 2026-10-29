"""Words on the desk: a slide's words patched into its drawn section when they still fit,
typed and selection edits, speaker notes as their own edit, and History per slide.

Every test runs the engine over the stand-ins, with scripted workers, a disposable data
folder, workspace and git identity. Nothing real is started.
"""
import json
import secrets
import unittest
from pathlib import Path

from runner_support import LONG_OUTLINE, DeskCase
from workspace import WorkspaceError

from runner import desk
from runner.steps import build, words

SLIDE = LONG_OUTLINE['slides'][2]           # slide 3, in section 1
TOO_LONG = 's3/title: needs 40pt of height but has 30pt; shorten the title'


class PatchTests(DeskCase):
    """A slide's new words put into its drawn section, and the tool's word on whether they
    still fit."""

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def drawn(self, root: Path, section: str = 'section-1') -> dict:
        state = build.read_state(root)
        return json.loads((root / state['sections'][section]['file']).read_text())

    def slide(self, section: dict, ident: str = SLIDE['id']) -> dict:
        return next(one for one in section['slides'] if one['id'] == ident)

    def test_a_title_is_set_on_the_slide_field(self):
        root = self.deck()
        patched = words.patch_section(self.drawn(root), SLIDE['id'], 'title', SLIDE['title'],
                                      'Capacity holds with two or more')
        self.assertEqual(self.slide(patched)['title'], 'Capacity holds with two or more')
        self.assertEqual(self.slide(self.drawn(root))['title'], SLIDE['title'])

    def test_a_point_s_text_is_replaced_in_its_one_text_node(self):
        root = self.deck()
        old = SLIDE['points'][0]['text']
        patched = words.patch_section(self.drawn(root), SLIDE['id'], ('points', 0, 'text'),
                                      old, 'The others carry the load between them.')
        shown = json.dumps(self.slide(patched))
        self.assertIn('The others carry the load between them.', shown)
        self.assertNotIn(json.dumps(old)[1:-1] + '"', shown)

    def test_a_point_found_twice_is_refused(self):
        root = self.deck()
        drawn = self.drawn(root)
        slide = self.slide(drawn)
        slide['canvas']['children'].append({'type': 'text', 'id': 's1_again',
                                            'text': SLIDE['points'][0]['text']})
        with self.assertRaises(WorkspaceError) as caught:
            words.patch_section(drawn, SLIDE['id'], ('points', 0, 'text'),
                                SLIDE['points'][0]['text'], 'Shorter.')
        self.assertEqual(str(caught.exception), words.NOT_FOUND)

    def test_words_that_fit_land_as_a_new_drawn_file(self):
        root = self.deck()
        record = self.record(root)
        outline = words.retext(json.loads((root / 'outline.json').read_text()), SLIDE['id'],
                               'title', 'Capacity holds with two or more')
        whole = words.with_words(words.given(root), outline, SLIDE['id'])
        patched = words.patch_section(self.drawn(root), SLIDE['id'], 'title', SLIDE['title'],
                                      'Capacity holds with two or more')
        self.assertEqual(words.fits(root, record, 'section-1', patched, self.slides, whole), [])
        self.assertFalse(self.engines.Engine._needs_whole(root))
        before = build.read_state(root)['sections']['section-1']['file']
        made = words.land(root, record, 'section-1', patched)
        self.assertNotEqual(made.relative_to(root).as_posix(), before)
        self.assertTrue(self.engines.Engine._needs_whole(root))
        self.assertEqual(build.to_draw(root), [])

    def test_words_that_do_not_fit_come_back_as_the_tool_s_lines(self):
        root = self.deck()
        record = self.record(root)
        outline = words.retext(json.loads((root / 'outline.json').read_text()), SLIDE['id'],
                               'title', 'A much longer title')
        whole = words.with_words(words.given(root), outline, SLIDE['id'])
        patched = words.patch_section(self.drawn(root), SLIDE['id'], 'title', SLIDE['title'],
                                      'A much longer title')
        self.slides.run.fails['compose compile'] = TOO_LONG
        self.assertEqual(words.fits(root, record, 'section-1', patched, self.slides, whole),
                         [TOO_LONG])

    def test_section_spec_is_what_section_work_hands_its_composer(self):
        root = self.deck()
        record = self.record(root)
        work = build.section_work(root, record, 'section-2', None, None)
        handed = dict(work.prepared['artifacts']['section'])
        handed.pop('progress')
        self.assertEqual(handed, build.section_spec(root, record, 'section-2'))

    def test_the_start_s_outline_is_told_the_new_words(self):
        root = self.deck()
        outline = words.retext(json.loads((root / 'outline.json').read_text()), SLIDE['id'],
                               'title', 'Capacity holds with two or more')
        whole = words.with_words(words.given(root), outline, SLIDE['id'])
        words.retold(root, whole)
        told = words.given(root)
        self.assertEqual(next(one for one in build.slides_of(told)
                              if one['id'] == SLIDE['id'])['title'],
                         'Capacity holds with two or more')


class TypedWordsTests(DeskCase):
    """A slide's words and speaker notes typed on its card: saved with no composer when they
    still fit the drawing, and nothing saved when they do not."""

    SESSION = 'a' * 16

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def seen(self, root: Path) -> int:
        return self.desk_view(root)['seen']

    def card(self, root: Path, number: int) -> dict:
        return next(card for part in self.desk_view(root)['sections'] for card in part['slides']
                    if card['number'] == number)

    def outline_slide(self, root: Path, number: int) -> dict:
        return json.loads((root / 'outline.json').read_text())['slides'][number - 1]

    def put_together(self) -> int:
        return self.log().count('Rolling restarts: the deck is put together')

    def test_a_title_that_fits_lands_with_no_section_job(self):
        root = self.deck()
        jobs, rounds = len(self.workers.of('section')), len(build.read_state(root)['rounds'])
        self.engine.desk_words(root, 3, 'title', 'Batches restart in turn', self.seen(root),
                               self.SESSION)
        self.assertEqual(len(self.workers.of('section')), jobs)
        self.assertEqual(self.outline_slide(root, 3)['title'], 'Batches restart in turn')
        self.on_desk(root)
        self.assertEqual(len(build.read_state(root)['rounds']), rounds + 1)
        state = build.read_state(root)
        drawn = json.loads((root / state['sections']['section-1']['file']).read_text())
        self.assertEqual(next(one for one in drawn['slides'] if one['id'] == SLIDE['id'])['title'],
                         'Batches restart in turn')

    def test_a_title_that_does_not_fit_saves_nothing(self):
        root = self.deck()
        before = (root / 'outline.json').read_bytes()
        self.slides.run.fails['compose compile'] = TOO_LONG
        shown = self.engine.desk_words(root, 3, 'title', 'A much longer title', self.seen(root),
                                       self.SESSION)
        self.slides.run.fails.pop('compose compile')
        card = next(card for part in shown['desk']['sections'] for card in part['slides']
                    if card['number'] == 3)
        self.assertEqual(card['unfit']['text'], 'A much longer title')
        self.assertIn(TOO_LONG, card['unfit']['lines'])
        self.assertEqual(card['unfit']['says'], words.NO_FIT)
        self.assertEqual((root / 'outline.json').read_bytes(), before)
        self.assertEqual(self.waiting(root), 'gate:build')

    def test_redraw_with_these_words_saves_them_and_redraws_the_section(self):
        root = self.deck()
        edited = json.loads(json.dumps(LONG_OUTLINE))
        edited['slides'][2]['title'] = 'A much longer title'
        self.workers.outline_said = edited
        jobs = len(self.workers.of('section'))
        self.engine.desk_redraw_words(root, 3, 'title', 'A much longer title',
                                      self.desk_view(root)['expected'])
        again = self.workers.of('section')[jobs:]
        self.assertEqual(len(again), 1)
        self.assertIn('changed since your brief was written', again[0].task)
        self.assertIn('Fit the new words of slide 3.', again[0].task)
        self.assertEqual(self.outline_slide(root, 3)['title'], 'A much longer title')
        told = words.given(root)
        self.assertEqual(build.slides_of(told)[2]['title'], 'A much longer title')
        self.on_desk(root)
        self.assertIsNone(self.card(root, 3)['unfit'])

    def test_speaker_notes_save_with_no_section_job(self):
        root = self.deck()
        jobs, put = len(self.workers.of('section')), self.put_together()
        self.engine.desk_notes(root, 3, 'Two minutes. Ask who runs one instance.',
                               self.seen(root), self.SESSION)
        self.assertEqual(len(self.workers.of('section')), jobs)
        self.assertEqual(self.put_together(), put + 1)
        self.assertEqual(self.outline_slide(root, 3)['notes'],
                         'Two minutes. Ask who runs one instance.')
        self.assertEqual(self.card(root, 3)['notes'], 'Two minutes. Ask who runs one instance.')

    def test_two_notes_saves_while_the_deck_is_put_together_make_one_more_pass(self):
        from unittest import mock
        root = self.deck()
        real, saved, wholes = build.draw_whole, [], []

        def drawing(*given, **named):
            wholes.append(True)
            made = real(*given, **named)
            if not saved:
                for number, text in ((5, 'Show the check in the log.'), (6, 'One example.')):
                    saved.append(self.engine.desk_notes(root, number, text, self.seen(root),
                                                        self.SESSION))
            return made

        with mock.patch.object(build, 'draw_whole', drawing):
            self.engine.desk_notes(root, 3, 'Two minutes.', self.seen(root), self.SESSION)
        self.assertEqual(len(saved), 2)
        # The first save's pass, and one more for the two saved while it ran.
        self.assertEqual(len(wholes), 2)
        self.on_desk(root)
        self.assertEqual(self.outline_slide(root, 6)['notes'], 'One example.')
        state = build.read_state(root)
        drawn = json.loads((root / state['sections']['section-2']['file']).read_text())
        self.assertEqual([one['notes'] for one in drawn['slides']][:2],
                         ['Show the check in the log.', 'One example.'])

    def test_an_old_form_is_refused_for_its_slide_only(self):
        root = self.deck()
        seen = self.seen(root)
        self.engine.desk_words(root, 3, 'title', 'Batches restart in turn', seen, 'b' * 16)
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_words(root, 3, 'title', 'Another title', seen, 'c' * 16)
        self.assertIn('changed since', str(caught.exception))
        self.engine.desk_words(root, 5, 'title', 'Health first', seen, 'c' * 16)
        self.assertEqual(self.outline_slide(root, 5)['title'], 'Health first')

    def test_a_lead_slide_s_title_is_checked_on_its_own_and_has_no_points(self):
        root = self.deck()
        self.engine.desk_words(root, 1, 'title', 'Rolling restarts, plainly', self.seen(root),
                               self.SESSION)
        self.assertEqual(self.outline_slide(root, 1)['title'], 'Rolling restarts, plainly')
        with self.assertRaises(WorkspaceError):
            self.engine.desk_words(root, 1, ['points', 0, 'text'], 'x', self.seen(root),
                                   self.SESSION)

    def test_a_gated_deck_s_outline_is_never_patched(self):
        from runner import desk
        root = self.gated()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_words(root, 3, 'title', 'Batches restart in turn', 1, self.SESSION)
        self.assertEqual(str(caught.exception), desk.NOT_ON_DESK)


class SelectionTests(DeskCase):
    """Rephrase, Shorten, Expand, Fix or Ask… on a selection of a slide's words: a small
    words job rewrites the passage, and its words are saved as a typed edit is."""

    POINT = ('points', 0, 'text')     # slide 3's first point: 'The others carry the load.'

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def seen(self, root: Path) -> int:
        return self.desk_view(root)['seen']

    def point(self, root: Path) -> str:
        return json.loads((root / 'outline.json').read_text())['slides'][2]['points'][0]['text']

    def select(self, root: Path, words_of: str, action: str = 'rephrase', instruction=None):
        text = self.point(root)
        start = text.index(words_of)
        return self.engine.desk_selection(root, 3, self.POINT, start, start + len(words_of),
                                          action, instruction, self.seen(root))

    def test_rephrase_replaces_only_the_selected_passage(self):
        root = self.deck()
        self.select(root, 'the load')
        self.assertEqual(self.point(root), 'The others carry the load (fresh).')
        (job,) = self.workers.of('words')
        self.assertIn('the load', job.task)
        self.assertIn('The others carry the load.', job.task)
        self.on_desk(root)
        self.assertEqual(self.record(root).get('desk_jobs') or [], [])

    def test_a_result_after_the_field_changed_is_not_kept(self):
        root = self.deck()

        def typing(tools, job):
            self.engine.desk_words(root, 3, self.POINT, 'The rest carry the load.',
                                   self.seen(root), 'd' * 16)
            return self.workers.words(tools, job)

        self.workers.then('words', typing)
        self.select(root, 'the load')
        self.assertEqual(self.point(root), 'The rest carry the load.')
        tries = [attempt['outcome'] for name, entry in self.record(root)['steps'].items()
                 if name.startswith('desk-words') for attempt in entry['tries']]
        self.assertEqual(tries, ['superseded'])

    def test_a_selection_that_no_longer_fits_offers_the_redraw(self):
        root = self.deck()
        before = (root / 'outline.json').read_bytes()
        self.slides.run.fails['compose compile'] = TOO_LONG
        self.select(root, 'the load', 'expand')
        self.slides.run.fails.pop('compose compile')
        card = next(card for part in self.desk_view(root)['sections'] for card in part['slides']
                    if card['number'] == 3)
        self.assertEqual(card['unfit']['text'], 'The others carry the load (fresh).')
        self.assertEqual((root / 'outline.json').read_bytes(), before)

    def test_one_change_at_a_time(self):
        root = self.deck()
        queued = []

        def again(tools, job):
            with self.assertRaises(WorkspaceError) as caught:
                self.select(root, 'carry')
            queued.append(str(caught.exception))
            return self.workers.words(tools, job)

        self.workers.then('words', again)
        self.select(root, 'the load')
        self.assertEqual(queued, [desk.ONE_CHANGE])

    def test_the_words_job_has_its_brief(self):
        from runner import briefs
        root = self.deck()
        self.select(root, 'the load', 'ask', 'Say it as a promise.')
        (job,) = self.workers.of('words')
        guidance = self.workers.jobs[-1][1].guidance
        self.assertTrue(guidance.startswith(briefs.read('words').splitlines()[0]), guidance[:80])
        self.assertIn('Say it as a promise.', job.task)


class HistoryTests(DeskCase):
    """Each slide's earlier words are kept for the team, and its drawings on this computer."""

    SESSION = 'e' * 16

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def seen(self, root: Path) -> int:
        return self.desk_view(root)['seen']

    def retitle(self, root: Path, title: str, session=None) -> dict:
        return self.engine.desk_words(root, 3, 'title', title, self.seen(root),
                                      session or secrets.token_hex(8))

    def test_a_word_edit_keeps_the_words_before_it_in_the_shared_folder(self):
        root = self.deck()
        self.retitle(root, 'Batches restart in turn')
        relative = root.relative_to(self.space.repo).as_posix()
        tracked = self.git('ls-files', relative).splitlines()
        self.assertIn(f"{relative}/desk/versions/{SLIDE['id']}.jsonl", tracked)
        drawings = root / 'work' / 'desk' / 'versions' / SLIDE['id']
        self.assertTrue(list(drawings.glob('*.json')))
        self.assertTrue(list(drawings.glob('*.png')))
        self.assertFalse([name for name in tracked if '/work/' in name])
        (kept,) = self.engine.desk_versions(root, SLIDE['id'])
        self.assertEqual((kept['source'], kept['words']['title']), ('save', SLIDE['title']))
        self.assertEqual(kept['picture']['kind'], 'version')

    def test_saves_in_one_editing_session_keep_one_version(self):
        root = self.deck()
        self.retitle(root, 'Batches restart', self.SESSION)
        self.retitle(root, 'Batches restart in turn', self.SESSION)
        self.assertEqual(len(self.engine.desk_versions(root, SLIDE['id'])), 1)

    def test_twenty_versions_are_kept(self):
        root = self.deck()
        for number in range(22):
            self.retitle(root, f'Capacity holds, take {number}')
        self.assertEqual(len(self.engine.desk_versions(root, SLIDE['id'])), 20)

    def test_restore_with_the_drawing_needs_no_job(self):
        root = self.deck()
        self.retitle(root, 'Batches restart in turn')
        kept = json.loads(next((root / 'work/desk/versions' / SLIDE['id']).glob('*.json'))
                          .read_text())
        jobs = len(self.workers.jobs)
        self.engine.desk_restore(root, SLIDE['id'], 0, self.seen(root))
        self.assertEqual(len(self.workers.jobs), jobs)
        state = build.read_state(root)
        drawn = json.loads((root / state['sections']['section-1']['file']).read_text())
        self.assertEqual(next(one for one in drawn['slides'] if one['id'] == SLIDE['id']), kept)
        outline = json.loads((root / 'outline.json').read_text())
        self.assertEqual(outline['slides'][2]['title'], SLIDE['title'])
        self.on_desk(root)

    def test_restore_without_the_drawing_uses_the_word_chain(self):
        import shutil
        root = self.deck()
        self.retitle(root, 'Batches restart in turn')
        shutil.rmtree(root / 'work/desk/versions')
        self.engine.desk_restore(root, SLIDE['id'], 0, self.seen(root))
        outline = json.loads((root / 'outline.json').read_text())
        self.assertEqual(outline['slides'][2]['title'], SLIDE['title'])
        self.retitle(root, 'Batches restart in turn')
        shutil.rmtree(root / 'work/desk/versions')
        self.slides.run.fails['compose compile'] = TOO_LONG
        shown = self.engine.desk_restore(root, SLIDE['id'], 0, self.seen(root))
        self.slides.run.fails.pop('compose compile')
        card = next(card for part in shown['desk']['sections'] for card in part['slides']
                    if card['number'] == 3)
        self.assertIn(TOO_LONG, card['unfit']['lines'])

    def test_a_restore_is_itself_a_version(self):
        root = self.deck()
        self.retitle(root, 'Batches restart in turn')
        self.engine.desk_restore(root, SLIDE['id'], 0, self.seen(root))
        found = self.engine.desk_versions(root, SLIDE['id'])
        self.assertEqual([one['source'] for one in found], ['restore', 'save'])
        self.assertEqual(found[0]['words']['title'], 'Batches restart in turn')

    def test_a_version_picture_is_served_only_by_its_kind(self):
        root = self.deck()
        self.retitle(root, 'Batches restart in turn')
        (kept,) = self.engine.desk_versions(root, SLIDE['id'])
        self.assertTrue(self.engine.picture(root, 'version', kept['picture']['ref'])
                        .startswith(b'\x89PNG'))
        for wrong in ('../x', f"{SLIDE['id']}/../../deck", 'x'):
            with self.assertRaises(OSError) as caught:
                self.engine.picture(root, 'version', wrong)
            self.assertEqual(str(caught.exception), 'There is no picture of that slide on this '
                                                    'computer.')


class ChainEditTests(DeskCase):
    """Words saved while the deck is put together: what the review of words on the desk
    found, each held to here."""

    POINT = ('points', 0, 'text')

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def seen(self, root: Path) -> int:
        return self.desk_view(root)['seen']

    def outline(self, root: Path) -> dict:
        return json.loads((root / 'outline.json').read_text())

    def drawn_slide(self, root: Path) -> dict:
        state = build.read_state(root)
        made = json.loads((root / state['sections']['section-1']['file']).read_text())
        return next(one for one in made['slides'] if one['id'] == SLIDE['id'])

    def during(self, name: str, *edits):
        """Patch one step of the build to save `edits` (number, field, text) while it runs."""
        from unittest import mock
        real, done = getattr(build, name), []

        def running(*given, **named):
            made = real(*given, **named)
            if not done:
                done.append(True)
                root = self.engine.every()[0]
                for number, field, text in edits:
                    self.engine.desk_words(root, number, field, text, self.seen(root),
                                           secrets.token_hex(8))
            return made

        return mock.patch.object(build, name, running)

    def test_two_edits_to_one_field_end_on_the_second(self):
        root = self.deck()
        with self.during('draw_whole', (3, self.POINT, 'The others carry the load at once.'),
                         (3, self.POINT, 'The others carry the load in turn.')):
            self.engine.desk_words(root, 5, 'title', 'Check it aloud', self.seen(root), 'f' * 16)
        self.on_desk(root)
        self.assertEqual(self.outline(root)['slides'][2]['points'][0]['text'],
                         'The others carry the load in turn.')
        self.assertIn('The others carry the load in turn.', json.dumps(self.drawn_slide(root)))
        self.assertNotIn('at once', json.dumps(self.drawn_slide(root)))

    def test_an_edit_that_grows_the_one_before_it_is_drawn_once(self):
        root = self.deck()
        with self.during('draw_whole', (3, self.POINT, 'The others carry the load. Then'),
                         (3, self.POINT, 'The others carry the load. Then more')):
            self.engine.desk_words(root, 5, 'title', 'Check it aloud', self.seen(root), 'f' * 16)
        self.on_desk(root)
        shown = json.dumps(self.drawn_slide(root))
        self.assertIn('The others carry the load. Then more', shown)
        self.assertNotIn('Then more Then', shown)

    def test_words_typed_back_to_what_they_were_land_as_typed(self):
        root = self.deck()
        with self.during('draw_whole', (3, 'title', 'Changed title'), (3, 'title', SLIDE['title'])):
            self.engine.desk_words(root, 5, 'title', 'Check it aloud', self.seen(root), 'f' * 16)
        self.on_desk(root)
        self.assertEqual(self.outline(root)['slides'][2]['title'], SLIDE['title'])
        self.assertEqual(self.drawn_slide(root)['title'], SLIDE['title'])

    def test_words_saved_after_the_last_put_together_are_put_together_before_the_rest(self):
        root = self.deck()
        with self.during('render', (3, 'title', 'Batches restart in turn')):
            self.engine.desk_words(root, 5, 'title', 'Check it aloud', self.seen(root), 'f' * 16)
        shown = self.on_desk(root)['desk']
        self.assertFalse(self.engines.Engine._needs_whole(root))
        self.assertTrue(shown['deliverable'])
        state = build.read_state(root)
        self.assertEqual(state['rounds'][-1]['made_from']['section-1'],
                         state['sections']['section-1']['file'])
        self.assertEqual(self.drawn_slide(root)['title'], 'Batches restart in turn')

    def test_deliver_waits_for_a_words_job(self):
        from runner import desk
        root = self.deck()
        refused = []

        def delivering(tools, job):
            with self.assertRaises(WorkspaceError) as caught:
                self.engine.desk_deliver(root, self.desk_view(root)['expected'])
            refused.append(str(caught.exception))
            self.assertFalse(self.desk_view(root)['deliverable'])
            return self.workers.words(tools, job)

        self.workers.then('words', delivering)
        text = self.outline(root)['slides'][2]['points'][0]['text']
        start = text.index('the load')
        self.engine.desk_selection(root, 3, self.POINT, start, start + len('the load'),
                                   'rephrase', None, self.seen(root))
        self.assertEqual(refused, [desk.STILL])

    def test_a_words_job_that_cannot_be_saved_does_not_stop_the_deck(self):
        root = self.deck()

        def noting(tools, job):
            self.engine.desk_note(root, 2, 'Fewer words.', self.desk_view(root)['expected'])
            return self.workers.words(tools, job)

        self.workers.then('words', noting)
        text = self.outline(root)['slides'][2]['points'][0]['text']
        start = text.index('the load')
        self.engine.desk_selection(root, 3, self.POINT, start, start + len('the load'),
                                   'rephrase', None, self.seen(root))
        record = self.record(root)
        self.assertIsNone(record['halted'])
        self.assertEqual(record.get('desk_jobs') or [], [])
        self.on_desk(root)

    def test_the_outline_tab_changes_a_slide_for_its_card(self):
        root = self.deck()
        seen = self.seen(root)
        slides = self.desk_view(root)['outline']['slides']
        slides[2] = {**slides[2], 'title': 'Capacity holds with two or more'}
        self.workers.outline_said = {**LONG_OUTLINE, 'slides': slides}
        self.engine.desk_outline(root, slides, self.desk_view(root)['outline']['expected'])
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_words(root, 3, 'title', 'An older form', seen, 'g' * 16)
        self.assertIn('changed since', str(caught.exception))
        self.assertEqual(self.engine.desk_versions(root, SLIDE['id'])[0]['source'], 'outline')

    def test_words_are_refused_while_the_deck_is_being_delivered(self):
        from unittest import mock

        from runner import desk
        root = self.deck()
        with mock.patch.object(self.engine, 'wake'):
            self.engine.desk_deliver(root, self.desk_view(root)['expected'])
            for change in (lambda: self.engine.desk_words(root, 3, 'title', 'Typed after Deliver',
                                                          self.seen(root), 'l' * 16),
                           lambda: self.engine.desk_notes(root, 3, 'Later notes.',
                                                          self.seen(root), 'l' * 16),
                           lambda: self.engine.desk_selection(root, 3, self.POINT, 0, 3,
                                                              'rephrase', None,
                                                              self.seen(root))):
                with self.assertRaises(WorkspaceError) as caught:
                    change()
                self.assertEqual(str(caught.exception), desk.DELIVERING)
        self.engine.wake(root)
        self.assertEqual(self.outline(root)['slides'][2]['title'], SLIDE['title'])
        self.assertTrue((root / 'deliver.json').is_file())

    def test_a_restore_is_bound_to_its_version(self):
        root = self.deck()
        self.engine.desk_words(root, 3, 'title', 'First change', self.seen(root), 'h' * 16)
        self.engine.desk_words(root, 3, 'title', 'Second change', self.seen(root), 'i' * 16)
        first = self.engine.desk_versions(root, SLIDE['id'])[-1]
        self.engine.desk_restore(root, SLIDE['id'], 0, self.seen(root), stamp=first['stamp'])
        self.assertEqual(self.outline(root)['slides'][2]['title'], SLIDE['title'])

    def test_a_selection_of_words_that_changed_is_refused(self):
        from runner import desk
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_selection(root, 3, self.POINT, 0, 6, 'rephrase', None,
                                       self.seen(root), passage='Others')
        self.assertEqual(str(caught.exception), desk.SELECTION_CHANGED)

    def test_a_restore_that_does_not_fit_is_redrawn_with_all_its_words(self):
        import shutil
        root = self.deck()
        self.engine.desk_words(root, 3, 'title', 'Batches restart in turn', self.seen(root),
                               'j' * 16)
        self.engine.desk_notes(root, 3, 'New notes.', self.seen(root), 'k' * 16)
        shutil.rmtree(root / 'work/desk/versions')
        oldest = self.engine.desk_versions(root, SLIDE['id'])[-1]
        self.slides.run.fails['compose compile'] = TOO_LONG
        self.engine.desk_restore(root, SLIDE['id'], 0, self.seen(root), stamp=oldest['stamp'])
        self.slides.run.fails.pop('compose compile')
        card = next(card for part in self.desk_view(root)['sections'] for card in part['slides']
                    if card['number'] == 3)
        self.assertEqual(card['unfit']['field'], 'restore')
        self.engine.desk_redraw_words(root, 3, 'restore', '', self.desk_view(root)['expected'])
        outline = self.outline(root)['slides'][2]
        self.assertEqual((outline['title'], outline['notes']), (SLIDE['title'], SLIDE['notes']))


def planned(number: int, object_id: str, runs: list, read: list | None = None):
    """A scripted plan job for a Selected changes deck: one operation, on the runs given.
    What it read of the deck's inventory is added to `read`."""
    def act(tools, job):
        if read is not None:
            read.append(tools.read_input('Inventory')[1])
        spec = tools.job['artifacts']['patch']
        plan = {'sourceSha256': spec['sha256'], 'operations': [
            {'slide': number, 'object': object_id,
             'expectedHash': spec['objects'][f'{number}:{object_id}'],
             'runs': [{'index': index, 'text': text} for index, text in runs]}]}
        made = tools.submit_artifact('patch', json.dumps(plan))
        assert made[0], made[1]
    return act


class SelectedTests(DeskCase):
    """Selected changes on the desk: your own deck's words changed only through `pptx patch`
    to a copy, and `pptx compare`. The stand-in reads the deck given as three slides: a cover
    (its title, object 2, and its subtitle, object 3, each one run), slide 2 with its title
    (object 2) and words in two runs (object 3, "Ship apps " and "in minutes, not weeks."),
    and a hidden slide 3. The person named slide 2."""

    SESSION = 'f' * 16

    def deck(self) -> Path:
        self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
        root = self.existing_deck('automatic', 'selected', flow='desk',
                                  selected='Shorten the words on slide 2')
        self.on_desk(root)
        return root

    def seen(self, root: Path) -> int:
        return self.desk_view(root)['seen']

    def shown(self, root: Path, number: int, object_id: str) -> list:
        """An object's runs in the patched copy, as the slides tool reads it."""
        from runner.steps import existing
        found = self.slides.pptx_inspect(root / existing.PATCHED)
        slide = next(one for one in found['slides'] if one['number'] == number)
        return next(one for one in slide['objects'] if one['id'] == object_id)['runs']

    def plan(self, root: Path) -> list:
        from runner.steps import existing
        return json.loads((root / existing.PATCH).read_text())['operations']

    def test_a_typed_edit_is_one_patch_operation_and_no_job(self):
        from unittest import mock

        from runner.steps import existing
        root = self.deck()
        jobs, allowed = len(self.workers.of('patch')), []
        real = self.slides.pptx_compare

        def comparing(before, after, allow):
            allowed.append(json.loads(Path(allow).read_text()))
            return real(before, after, allow)

        with mock.patch.object(self.slides, 'pptx_compare', comparing):
            self.engine.desk_words(root, 2, ['object', '3', 0], 'Ship fast', self.seen(root),
                                   self.SESSION)
        self.assertEqual(len(self.workers.of('patch')), jobs)
        self.on_desk(root)
        # The plan's own change to the second run is kept beside the typed one.
        self.assertEqual(self.shown(root, 2, '3'), ['Ship fast ', 'in minutes.'])
        self.assertEqual(allowed, [[{'slide': '257', 'object': '3', 'fields': ['text']}]])
        (op,) = self.plan(root)
        self.assertEqual(op['runs'], [{'index': 0, 'text': 'Ship fast '},
                                      {'index': 1, 'text': 'in minutes.'}])
        shared = json.loads((root / words.SHARED_OPS).read_text())
        self.assertEqual(shared['operations'], [{
            'slide': 2, 'object': '3', 'expectedHash': op['expectedHash'],
            'runs': [{'index': 0, 'text': 'Ship fast '}]}])
        tracked = self.git('ls-files', root.relative_to(self.space.repo).as_posix())
        self.assertIn('desk/patch-ops.json', tracked)
        card = next(card for card in self.desk_view(root)['sections'][0]['slides']
                    if card['number'] == 2)
        self.assertEqual(card['objects'][1]['runs'], ['Ship fast ', 'in minutes.'])
        self.assertEqual(self.desk_view(root)['expected'],
                         self.engines.sha256_of(root / existing.PATCHED))

    def test_a_second_edit_to_the_same_object_replaces_the_first(self):
        root = self.deck()
        self.engine.desk_words(root, 1, ['object', '3', None], 'A deck to start from',
                               self.seen(root), self.SESSION)
        self.engine.desk_words(root, 1, ['object', '3', None], 'A deck to keep',
                               self.seen(root), self.SESSION)
        self.on_desk(root)
        ops = [op for op in self.plan(root) if op['slide'] == 1]
        self.assertEqual([op.get('text') for op in ops], ['A deck to keep'])
        shared = json.loads((root / words.SHARED_OPS).read_text())['operations']
        self.assertEqual([op.get('text') for op in shared], ['A deck to keep'])
        self.assertEqual(self.shown(root, 1, '3'), ['A deck to keep'])

    def test_a_note_on_an_unnamed_slide_runs_the_plan_with_it(self):
        root = self.deck()
        self.engine.desk_words(root, 2, ['object', '3', 0], 'Ship fast', self.seen(root),
                               self.SESSION)
        jobs, read = len(self.workers.of('patch')), []
        self.workers.then('patch', planned(1, '3', [(0, 'Who runs a deck like this?')], read))
        self.engine.desk_note(root, 1, 'Make the subtitle a question.',
                              self.desk_view(root)['expected'])
        again = self.workers.of('patch')[jobs:]
        self.assertEqual(len(again), 1)
        self.assertEqual(self.record(root)['desk_patch_slides'], [1])
        spec = self.workers.jobs[-1][2]['artifacts']['patch']
        self.assertEqual(spec['named'], [2, 1])
        self.assertIn('## Slide 1:', read[0])
        self.assertIn('Slide 1: Make the subtitle a question.', again[0].task)
        self.assertIn('The person also changed these words themselves', again[0].task)
        self.on_desk(root)
        # The plan made again for slide 1 changes slide 1 only: the earlier plan's change to
        # slide 2 is kept, and so is what was typed there.
        self.assertEqual(self.shown(root, 1, '3'), ['Who runs a deck like this?'])
        self.assertEqual(self.shown(root, 2, '3'), ['Ship fast ', 'in minutes.'])
        card = next(card for card in self.desk_view(root)['sections'][0]['slides']
                    if card['number'] == 1)
        self.assertEqual(card['note']['status'], 'done')
        self.assertTrue(self.desk_view(root)['deliverable'])

    def test_a_typed_word_stays_when_its_object_is_planned_again(self):
        root = self.deck()
        self.engine.desk_words(root, 2, ['object', '3', 0], 'Ship fast', self.seen(root),
                               self.SESSION)
        self.workers.then('patch', planned(2, '3', [(0, 'Ship apps '), (1, 'in seconds.')]))
        jobs = len(self.workers.of('patch'))
        self.engine.desk_note(root, 2, 'Say how fast in seconds.',
                              self.desk_view(root)['expected'])
        (job,) = self.workers.of('patch')[jobs:]
        self.assertIn('They stay as they are', job.task)
        self.on_desk(root)
        # The plan's new words for run 1, and the words typed into run 0.
        self.assertEqual(self.shown(root, 2, '3'), ['Ship fast ', 'in seconds.'])
        shared = json.loads((root / words.SHARED_OPS).read_text())['operations']
        self.assertEqual([op['runs'] for op in shared], [[{'index': 0, 'text': 'Ship fast '}]])

    def test_an_earlier_note_s_change_stays_when_a_later_note_is_planned(self):
        root = self.deck()
        self.workers.then('patch', planned(1, '3', [(0, 'Who runs a deck like this?')]))
        self.engine.desk_note(root, 1, 'Make the subtitle a question.',
                              self.desk_view(root)['expected'])
        self.on_desk(root)
        self.workers.then('patch', planned(3, '2', [(0, 'More, if you ask')]))
        jobs = len(self.workers.of('patch'))
        self.engine.desk_note(root, 3, 'Name it for the questions.',
                              self.desk_view(root)['expected'])
        (job,) = self.workers.of('patch')[jobs:]
        # Every note made on the desk is handed to the plan, by its slide.
        self.assertIn('Slide 1: Make the subtitle a question.', job.task)
        self.assertIn('Slide 3: Name it for the questions.', job.task)
        self.on_desk(root)
        self.assertEqual(self.shown(root, 1, '3'), ['Who runs a deck like this?'])
        self.assertEqual(self.shown(root, 2, '3'), ['Ship apps ', 'in minutes.'])
        self.assertEqual(self.shown(root, 3, '2'), ['More, if you ask'])

    def refusing(self, failure: dict):
        """pptx compare refusing the next copy it is shown with `failure`, then as it is."""
        from unittest import mock
        real, refused = self.slides.pptx_compare, []

        def comparing(before, after, allow):
            if not refused:
                refused.append(True)
                return {'preserved': False, 'failures': [failure], 'changedParts': []}
            return real(before, after, allow)
        return mock.patch.object(self.slides, 'pptx_compare', comparing)

    def test_a_change_the_compare_refuses_is_put_back_and_kept_on_its_card(self):
        from runner.steps import existing
        root = self.deck()
        plan = (root / existing.PATCH).read_bytes()
        shared = (root / words.SHARED_OPS).read_bytes() \
            if (root / words.SHARED_OPS).exists() else None
        with self.refusing({'slide': '257', 'object': '3',
                            'code': 'geometry-style-or-relationships-changed'}):
            self.engine.desk_words(root, 2, ['object', '3', 0], 'Ship fast', self.seen(root),
                                   self.SESSION)
        self.on_desk(root)
        self.assertIsNone(self.record(root).get('halted'))
        self.assertEqual((root / existing.PATCH).read_bytes(), plan)
        self.assertEqual((root / words.SHARED_OPS).read_bytes()
                         if (root / words.SHARED_OPS).exists() else None, shared)
        self.assertEqual(self.shown(root, 2, '3'), ['Ship apps ', 'in minutes.'])
        shown = self.desk_view(root)
        card = next(card for card in shown['sections'][0]['slides'] if card['number'] == 2)
        self.assertEqual((card['unfit']['text'], card['unfit']['field']),
                         ('Ship fast', ['object', '3', 0]))
        self.assertEqual(card['unfit']['says'], desk.PATCH_REFUSED)
        self.assertTrue(card['unfit']['lines'])
        self.assertTrue(shown['deliverable'])
        self.engine.desk_discard(root, 2)
        card = next(card for card in self.desk_view(root)['sections'][0]['slides']
                    if card['number'] == 2)
        self.assertIsNone(card['unfit'])

    def test_a_note_whose_copy_is_refused_is_set_aside_with_the_plan_put_back(self):
        from runner.steps import existing
        root = self.deck()
        plan = (root / existing.PATCH).read_bytes()
        self.workers.then('patch', planned(1, '3', [(0, 'Who runs a deck like this?')]))
        with self.refusing({'slide': '256', 'object': '3', 'code': 'alt-changed'}):
            self.engine.desk_note(root, 1, 'Make the subtitle a question.',
                                  self.desk_view(root)['expected'])
        self.on_desk(root)
        self.assertEqual((root / existing.PATCH).read_bytes(), plan)
        card = next(card for card in self.desk_view(root)['sections'][0]['slides']
                    if card['number'] == 1)
        self.assertEqual(card['note']['status'], 'set aside')
        self.assertTrue(card['note']['says'].startswith(desk.PATCH_REFUSED))
        self.assertTrue(self.desk_view(root)['deliverable'])

    def test_a_copy_that_cannot_be_made_again_stops_and_stop_puts_it_back(self):
        root = self.deck()
        self.slides.run.fails['review'] = 'LibreOffice could not open the deck'
        self.engine.desk_words(root, 2, ['object', '3', 0], 'Ship fast', self.seen(root),
                               self.SESSION)
        self.assertEqual(self.record(root)['halted']['state'], 'failed')
        working = self.desk_view(root)['working']
        self.assertTrue(working and working['halted'], working)
        self.slides.run.fails.pop('review')
        self.engine.desk_stop(root)
        self.on_desk(root)
        self.assertEqual(self.shown(root, 2, '3'), ['Ship apps ', 'in minutes.'])
        self.assertTrue(self.desk_view(root)['deliverable'])

    def test_without_the_plan_here_it_is_drawn_here_only_when_asked(self):
        import shutil
        root = self.deck()
        self.engine.desk_words(root, 2, ['object', '3', 0], 'Ship fast', self.seen(root),
                               self.SESSION)
        self.on_desk(root)
        shutil.rmtree(root / 'work')   # as on a computer that took the deck over
        jobs = len(self.workers.of('patch'))
        self.engine.wake(root)
        self.assertEqual(len(self.workers.of('patch')), jobs)
        shown = self.desk_view(root)
        self.assertFalse(shown['drawn_here'])
        self.assertTrue(shown['draw_here_price'].startswith(desk.DRAW_HERE_PATCH))
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_words(root, 2, ['object', '3', 1], 'in seconds.',
                                   self.seen(root), self.SESSION)
        self.assertEqual(str(caught.exception), desk.NO_DRAWING + ' Draw it here first.')
        self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
        self.engine.desk_draw_here(root)
        self.assertEqual(len(self.workers.of('patch')), jobs + 1)
        self.on_desk(root)
        self.assertTrue(self.desk_view(root)['drawn_here'])
        self.assertEqual(self.shown(root, 2, '3'), ['Ship fast ', 'in minutes.'])

    def test_delivering_is_not_said_as_making_the_copy(self):
        from runner import stages
        root = self.deck()
        record = self.record(root)
        record['gates']['gate:build']['state'] = 'approved'
        self.assertEqual(desk.working(root, record)['what'], stages.BY_NAME['deliver'].doing)
        record['steps']['build-render']['done'] = False
        self.assertEqual(desk.working(root, record)['what'], desk.PATCHING)

    def test_words_redrawn_or_restored_are_refused_on_your_own_deck(self):
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_redraw_words(root, 2, ['object', '3', 0], 'Ship fast',
                                          self.desk_view(root)['expected'])
        self.assertEqual(str(caught.exception), desk.OWN_REDRAW)
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_restore(root, 'slide-02-read', 0, self.seen(root))
        self.assertEqual(str(caught.exception), desk.OWN_RESTORE)

    def test_a_selection_inside_one_run_is_one_operation(self):
        root = self.deck()
        jobs = len(self.workers.of('patch'))
        text = 'in minutes.'
        start = text.index('minutes')
        self.engine.desk_selection(root, 2, ['object', '3', 1], start, start + len('minutes'),
                                   'rephrase', None, self.seen(root))
        (job,) = self.workers.of('words')
        self.assertIn('minutes', job.task)
        self.assertEqual(len(self.workers.of('patch')), jobs)
        self.on_desk(root)
        self.assertEqual(self.shown(root, 2, '3'), ['Ship apps ', 'in minutes (fresh).'])
        (op,) = self.plan(root)
        self.assertEqual(op['runs'], [{'index': 1, 'text': 'in minutes (fresh).'}])

    def test_stop_keeps_the_plan_made_before_the_note(self):
        import threading
        import time
        root = self.deck()
        stopped = []

        def stopping(tools, job):
            thread = threading.Thread(target=lambda: stopped.append(self.engine.desk_stop(root)))
            thread.start()
            for _ in range(300):
                if (self.engine._load(root).get('halted') or {}).get('state') == 'stopped':
                    break
                time.sleep(0.05)
            stopped.append(thread)

        self.workers.then('patch', stopping)
        jobs = len(self.workers.of('patch'))
        self.engine.desk_note(root, 1, 'Make the subtitle a question.',
                              self.desk_view(root)['expected'])
        stopped[0].join(30)
        self.on_desk(root)
        self.assertEqual(len(self.workers.of('patch')), jobs + 1)
        self.assertEqual(self.shown(root, 2, '3'), ['Ship apps ', 'in minutes.'])
        card = next(card for card in self.desk_view(root)['sections'][0]['slides']
                    if card['number'] == 1)
        self.assertEqual((card['note']['status'], card['note']['says']),
                         ('set aside', desk.PATCH_NOTE_SAYS['set aside']))
        self.assertTrue(self.desk_view(root)['deliverable'])

    def test_speaker_notes_are_refused_on_your_own_deck(self):
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_notes(root, 2, 'Two minutes.', self.seen(root), self.SESSION)
        self.assertEqual(str(caught.exception), desk.OWN_NOTES)

    def test_the_original_is_never_changed(self):
        import hashlib

        from runner.steps import existing
        root = self.deck()
        before = hashlib.sha256((root / existing.SOURCE).read_bytes()).hexdigest()
        self.engine.desk_words(root, 2, ['object', '2', None], 'Run it fast', self.seen(root),
                               self.SESSION)
        self.workers.then('patch', planned(1, '3', [(0, 'Who runs a deck like this?')]))
        self.engine.desk_note(root, 1, 'Make the subtitle a question.',
                              self.desk_view(root)['expected'])
        self.on_desk(root)
        self.assertEqual(hashlib.sha256((root / existing.SOURCE).read_bytes()).hexdigest(),
                         before)
        shown = self.view(root)['desk']
        self.engine.desk_deliver(root, shown['expected'], shown['blockers_seen'])
        self.assertEqual(hashlib.sha256((root / existing.SOURCE).read_bytes()).hexdigest(),
                         before)
        self.assertIsNotNone(json.loads((root / 'deliver.json').read_text())['url'])

    def test_a_gated_selected_deck_keeps_its_plan_as_its_worker_wrote_it(self):
        self.workers.then('patch', planned(2, '3', [(1, 'in minutes.')]))
        root = self.saved_existing_deck('automatic', 'selected',
                                  selected='Shorten the words on slide 2')
        self.assertEqual(self.waiting(root), 'gate:build')
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_words(root, 2, ['object', '3', 0], 'Ship fast', 1, self.SESSION)
        self.assertEqual(str(caught.exception), desk.NOT_ON_DESK)
        self.assertFalse((root / words.SHARED_OPS).exists())
        self.assertEqual(self.plan(root)[0]['runs'], [{'index': 1, 'text': 'in minutes.'}])


class StrictWordsTests(DeskCase):
    """Brand only and Polish keep your own deck's words exactly: a word edit, a selection and
    words redrawn are refused, and say so; speaker notes and a note on a slide still work."""

    SESSION = 'b' * 16

    def deck(self, level: str) -> Path:
        root = self.existing_deck('automatic', level, flow='desk', look='default')
        self.on_desk(root)
        return root

    def seen(self, root: Path) -> int:
        return self.desk_view(root)['seen']

    def outline_slide(self, root: Path, number: int) -> dict:
        return json.loads((root / 'outline.json').read_text())['slides'][number - 1]

    def refused(self, action, *given) -> str:
        with self.assertRaises(WorkspaceError) as caught:
            action(*given)
        return str(caught.exception)

    def test_brand_only_refuses_a_word_edit(self):
        root = self.deck('brand-only')
        before = (root / 'outline.json').read_bytes()
        for field in ('title', ['points', 0, 'text']):
            self.assertEqual(self.refused(self.engine.desk_words, root, 2, field, 'Run it fast',
                                          self.seen(root), self.SESSION), desk.STRICT_WORDS)
        self.assertEqual(self.refused(self.engine.desk_redraw_words, root, 2, 'title',
                                      'Run it fast', self.desk_view(root)['expected']),
                         desk.STRICT_WORDS)
        self.assertEqual((root / 'outline.json').read_bytes(), before)
        self.assertEqual(self.waiting(root), 'gate:build')

    def test_polish_refuses_a_selection(self):
        root = self.deck('polish')
        self.assertEqual(self.refused(self.engine.desk_selection, root, 2, 'title', 0, 3,
                                      'rephrase', None, self.seen(root)), desk.STRICT_WORDS)
        self.assertEqual(self.workers.of('words'), [])
        self.assertEqual(self.record(root).get('desk_jobs') or [], [])

    def test_brand_only_takes_a_notes_edit_and_a_slide_note(self):
        root = self.deck('brand-only')
        sections = len(self.workers.of('section'))
        self.engine.desk_notes(root, 2, 'Two minutes. Ask who ships weekly.', self.seen(root),
                               self.SESSION)
        self.on_desk(root)
        self.assertEqual(self.outline_slide(root, 2)['notes'],
                         'Two minutes. Ask who ships weekly.')
        self.assertEqual(len(self.workers.of('section')), sections)
        # The scripted composer draws the outline as it is now, notes and all.
        self.workers.outline_said = json.loads((root / 'outline.json').read_text())
        self.engine.desk_note(root, 2, 'Give the words more room.',
                              self.desk_view(root)['expected'])
        self.on_desk(root)
        again = self.workers.of('section')[sections:]
        self.assertEqual(len(again), 1)
        self.assertIn('Give the words more room.', again[0].task)

    def test_redesign_still_takes_a_word_edit(self):
        root = self.deck('redesign')
        self.engine.desk_words(root, 2, 'title', 'Run it fast', self.seen(root), self.SESSION)
        self.assertEqual(self.outline_slide(root, 2)['title'], 'Run it fast')


if __name__ == '__main__':
    unittest.main()
