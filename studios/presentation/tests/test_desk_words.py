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


if __name__ == '__main__':
    unittest.main()
