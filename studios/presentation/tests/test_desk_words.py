"""Words on the desk: a slide's words patched into its drawn section when they still fit,
typed and selection edits, speaker notes as their own edit, and History per slide.

Every test runs the engine over the stand-ins, with scripted workers, a disposable data
folder, workspace and git identity. Nothing real is started.
"""
import json
import unittest
from pathlib import Path

from runner_support import LONG_OUTLINE, DeskCase
from workspace import WorkspaceError

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


if __name__ == '__main__':
    unittest.main()
