"""The brand a deck is made in, shown as its cover before any slide is designed, and another
brand chosen in its place. The slides tool and the brand skill are the stand-ins."""
import json
import tempfile
import unittest
from pathlib import Path

import runner_support
from stand_ins import brand as brand_stand_in
from runner_support import OUTLINE
from workspace import WorkspaceError

from runner import decks
from runner.steps import build, look

BRANDS = [{'brand': 'example', 'name': 'Example Co', 'variants': ['light', 'dark']}]


class Case(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name).resolve() / 'deck'
        self.root.mkdir()
        form = {'route': 'scratch', 'title': 'Rolling restarts', 'brand': 'example',
                'variant': 'light', 'audience': 'Ops', 'goal': '', 'minutes': None,
                'output': 'google', 'research': False}
        self.run_ = {'schema': 1, 'id': 'd', 'title': 'Rolling restarts', 'route': 'scratch',
                     'form': form,
                     'gates': {'gate:outline': {'state': 'approved', 'note': 'Keep it short.'}},
                     'steps': {}, 'look': None}
        decks.write_run(self.root, self.run_)
        (self.root / 'intake.md').write_text(decks.intake(form), encoding='utf-8')
        (self.root / 'outline.json').write_text(json.dumps(OUTLINE), encoding='utf-8')
        self.slides = runner_support.stand_in_slides()
        self.brand = runner_support.stand_in_brand()   # its folder lasts as long as it does
        self.contract = build.export_brand(self.root, self.run_, self.brand)


class SampleTests(Case):
    def test_the_cover_is_drawn_alone_in_the_brand_s_own_colours(self):
        listed = self.slides.layouts(self.contract).get('layouts')
        made = look.composition(OUTLINE, 'Rolling restarts', listed)
        cover = OUTLINE['slides'][0]
        self.assertEqual(made['direction'], build.DIRECTION)
        (slide,) = made['slides']
        self.assertEqual((slide['id'], slide['title'], slide['subtitle']),
                         (cover['id'], cover['title'], cover['subtitle']))
        self.assertEqual(slide['layout'], build.layouts(listed, [cover])['cover'])

    def test_an_outline_with_no_cover_is_shown_the_deck_s_title_on_one(self):
        listed = self.slides.layouts(self.contract).get('layouts')
        bare = {**OUTLINE, 'slides': [one for one in OUTLINE['slides']
                                      if one.get('kind') != 'cover']}
        (slide,) = look.composition(bare, 'Rolling restarts', listed)['slides']
        self.assertEqual((slide['id'], slide['title']), ('cover', OUTLINE['title']))
        self.assertNotIn('subtitle', slide)

    def test_the_sample_is_pictured_and_the_gate_waits(self):
        drawn = look.preview_sample(self.root, self.run_, self.slides, 'local')
        self.assertEqual(drawn, self.root / look.SAMPLE)
        self.assertEqual(drawn.read_bytes()[:8], build.PNG)
        said = (self.root / 'look.md').read_text()
        self.assertIn('This deck is made in example (light).', said)
        self.assertIn(look.OLDER, said)
        gate = decks.read_run(self.root)['gates']['gate:look']
        self.assertEqual((gate['state'], gate['round']), ('waiting', 1))

    def test_a_sample_that_will_not_draw_says_so_and_leaves_nothing(self):
        (self.root / build.CONTRACT).unlink()
        with self.assertRaises(WorkspaceError) as caught:
            look.draw_sample(self.root, self.run_, self.slides, 'local')
        self.assertIn('Your cover could not be drawn in the brand.', str(caught.exception))
        self.assertFalse((self.root / look.FOLDER).exists())


class RebrandTests(Case):
    def test_another_variant_is_named_and_the_old_contract_removed(self):
        form = look.rebrand(self.root, self.run_, 'example', 'dark', BRANDS)
        self.assertEqual((form['brand'], form['variant']), ('example', 'dark'))
        self.assertEqual(self.run_['form']['variant'], 'dark')
        self.assertIn('example (dark)', (self.root / 'intake.md').read_text())
        self.assertFalse((self.root / build.BRAND).exists())

    def test_a_brand_with_no_variant_named_takes_its_first(self):
        self.run_['form']['brand'] = 'other'
        form = look.rebrand(self.root, self.run_, 'example', None, BRANDS)
        self.assertEqual(form['variant'], 'light')

    def test_what_is_not_offered_and_what_it_is_already_are_refused(self):
        for brand, variant, said in (('', None, 'Choose the brand'),
                                     ('nobody', None, 'nobody'),
                                     ('example', 'neon', 'neon'),
                                     ('example', 'light', 'already')):
            with self.subTest(brand=brand, variant=variant):
                with self.assertRaises(WorkspaceError) as caught:
                    look.rebrand(self.root, self.run_, brand, variant, BRANDS)
                self.assertIn(said, str(caught.exception))
                self.assertEqual(self.run_['form']['variant'], 'light')
                self.assertTrue((self.root / build.CONTRACT).is_file())


class ApproveTests(Case):
    def test_the_approval_is_written_into_the_outline_with_no_direction(self):
        outline = {**OUTLINE, 'direction': {'focal': 'accentAqua', 'neutral': 'canvasPrimary',
                                            'motif': 'Open columns on every slide.'}}
        (self.root / 'outline.json').write_text(json.dumps(outline), encoding='utf-8')
        look.approve(self.root, self.run_, note='Looks right.')
        kept = json.loads((self.root / 'outline.json').read_text())
        self.assertNotIn('direction', kept)
        self.assertIn('in example (light).', kept['approval'][0])
        self.assertEqual(kept['approval'][1:], ['Keep it short.', 'Looks right.'])
        gate = decks.read_run(self.root)['gates']['gate:look']
        self.assertEqual((gate['state'], gate['note']), ('approved', 'Looks right.'))
        self.assertFalse((self.root / 'look.json').exists())

    def test_every_slide_is_designed_in_the_brand_s_own_colours(self):
        look.approve(self.root, self.run_)
        build.start(self.root, self.run_, self.slides, self.contract)
        started = json.loads((self.root / build.START / 'outline.json').read_text())
        self.assertEqual(started['direction'], build.DIRECTION)
        self.assertNotIn('motif', started['direction'])


if __name__ == '__main__':
    unittest.main()


class LooksTests(Case):
    """A brand that offers looks: a slide of the outline in each, on one sheet, and the
    person's pick carried into the outline the deck is built from."""

    def setUp(self):
        super().setUp()
        import shutil
        self.brand.run.offers_looks = True
        shutil.rmtree(self.root / build.BRAND)
        self.contract = build.export_brand(self.root, self.run_, self.brand)

    def test_the_looks_are_drawn_locally_and_shown_on_one_sheet(self):
        from studio_core import deck_flow
        shown = look.draw_looks(self.root, self.run_, self.brand, 'local')
        self.assertEqual([one['id'] for one in shown['looks']],
                         [entry['id'] for entry in brand_stand_in.DIRECTIONS])
        self.assertEqual((shown['default'], shown['route'], shown['says']),
                         (brand_stand_in.DEFAULT_LOOK, 'local',
                          deck_flow.route('local')['says']))
        self.assertEqual((self.root / look.SHEET).read_bytes()[:8], build.PNG)
        for one in shown['looks']:
            self.assertNotIn('image', one, 'a picture is served from work/look/ only')
            self.assertEqual((self.root / look.FOLDER / f"{one['number']}.png")
                             .read_bytes()[:8], build.PNG)
        samples = [call for call in self.brand.run.calls if call[:2] == ['look', 'samples']]
        self.assertEqual(samples[-1][samples[-1].index('--preview') + 1], 'local')
        self.assertTrue(str(look.FOLDER).startswith('work/'), 'never shared')
        look.show_sample(self.root, self.run_)
        said = (self.root / 'look.md').read_text()
        self.assertIn('- Clear (the brand\'s default): Most decks', said)
        self.assertIn('- Bold: Launches and keynotes.', said)
        self.assertNotIn(look.OLDER, said)

    def test_previews_go_through_the_slides_tools_own_route(self):
        from studio_core import deck_flow
        shown = look.draw_looks(self.root, self.run_, self.brand, 'drive')
        self.assertEqual((shown['route'], shown['says']),
                         ('google', deck_flow.route('drive')['says']))
        pooled = look.draw_looks(self.root, self.run_, self.brand, 'drive',
                                 lambda name: name == deck_flow.POOL)
        self.assertEqual(pooled['says'], deck_flow.route('drive', lambda name: True)['says'])

    def test_looks_that_cannot_be_rendered_are_noted_and_never_picked_blind(self):
        self.brand.run.unrenderable = 'LibreOffice (soffice) is not installed.'
        shown = look.draw_looks(self.root, self.run_, self.brand, 'local')
        self.assertIn('LibreOffice', shown['failed'])
        self.assertEqual(look.shown_looks(self.root), shown)
        self.assertNotIn('looks', shown)
        with self.assertRaisesRegex(WorkspaceError, 'Choose one of the looks'):
            look.choose(self.root, self.brand, 'example-clear', 'This one.')
        look.show_sample(self.root, self.run_)
        self.assertIn("The brand's looks could not be rendered here",
                      (self.root / 'look.md').read_text())
        # Carried on in the brand's default, in the words deck_flow gives.
        from studio_core import deck_flow
        made = look.choose(self.root, self.brand, look.DEFAULT,
                           deck_flow.PROCEED_WORDS.format(name=look.DEFAULT_NAME))
        self.assertEqual(made['choice'], brand_stand_in.DEFAULT_LOOK)
        self.assertEqual(made['direction'], brand_stand_in.DIRECTIONS[0]['direction'])

    def test_a_choice_is_made_with_the_approved_outline_and_a_stale_one_is_drawn_again(self):
        look.draw_looks(self.root, self.run_, self.brand, 'local')
        picked = look.choose(self.root, self.brand, 'example-bold', 'Bold.')
        chose = [call for call in self.brand.run.calls if call[:2] == ['look', 'choose']][-1]
        self.assertEqual(chose[chose.index('--outline') + 1], str(self.root / look.OUTLINE))
        self.assertTrue(chose[chose.index('--write') + 1].startswith(
            str(self.root / look.FOLDER)))
        self.assertEqual(picked['house'], list(brand_stand_in.LOOK_HOUSE))
        # The outline changed since the samples: the brand refuses, and they are dropped.
        import shutil
        shutil.rmtree(self.root / look.FOLDER)
        look.draw_looks(self.root, self.run_, self.brand, 'local')
        outline = json.loads((self.root / 'outline.json').read_text())
        outline['title'] = 'Another title'
        (self.root / 'outline.json').write_text(json.dumps(outline))
        self.assertIsNone(look.choose(self.root, self.brand, 'example-bold', 'Bold.'))
        self.assertIsNone(look.shown_looks(self.root))
        self.assertFalse((self.root / look.FOLDER).exists())

    def test_the_persons_pick_in_their_words_becomes_the_decks_look(self):
        look.draw_looks(self.root, self.run_, self.brand, 'local')
        with self.assertRaisesRegex(WorkspaceError, 'Choose one of the looks'):
            look.choose(self.root, self.brand, 'nonsense', 'This one.')
        picked = look.choose(self.root, self.brand, 'example-bold', 'Bold suits a launch.')
        self.assertEqual((picked['choice'], picked['words']),
                         ('example-bold', 'Bold suits a launch.'))
        bold = brand_stand_in.DIRECTIONS[1]
        look.approve(self.root, self.run_, 'Looks right.')
        kept = json.loads((self.root / 'outline.json').read_text())
        self.assertEqual(kept['direction'], bold['direction'])
        self.assertEqual(kept['house'], list(brand_stand_in.LOOK_HOUSE))
        self.assertEqual(kept['layouts'], {key: bold['layouts'][key]
                                           for key in ('cover', 'section', 'closing')})
        self.assertIn('Look chosen: Bold (example-bold). In their words: "Bold suits a '
                      'launch."', kept['approval'][1])
        # The deck is built in it: its direction, the look's house style first, and its
        # title-capable closing layout.
        listed = self.slides.layouts(self.contract).get('layouts')
        whole = build.complete(kept, listed, kept['approval'], build.house(self.run_))
        self.assertEqual(whole['direction'], bold['direction'])
        self.assertEqual(whole['house'], [*brand_stand_in.LOOK_HOUSE, *build.HOUSE])
        self.assertEqual(whole['layouts']['closing'], 'Big Statement')

    def test_automatic_draft_takes_the_brands_default_and_says_why(self):
        look.draw_looks(self.root, self.run_, self.brand, 'local')
        picked = look.choose_default(self.root, self.brand)
        self.assertEqual(picked['choice'], brand_stand_in.DEFAULT_LOOK)
        self.assertEqual(picked['words'],
                         "Automatic draft: the brand's default look, Clear, was used.")
        from studio_core import deck_flow
        self.assertEqual(picked['words'], deck_flow.DEFAULT_WORDS.format(name='Clear'))
        self.assertEqual(look.choose_default(self.root, self.brand), picked, 'chosen once')

    def test_a_brand_without_looks_still_gives_its_default_direction(self):
        # No samples were drawn here, but the brand wrote its deck direction record.
        look.approve(self.root, self.run_)
        kept = json.loads((self.root / 'outline.json').read_text())
        self.assertEqual(kept['direction'], brand_stand_in.DIRECTIONS[0]['direction'])
        self.assertIsNone(look.choose_default(self.root, self.brand))

    def test_a_chosen_layout_the_slide_does_not_fit_is_left_for_one_that_does(self):
        listed = self.slides.layouts(self.contract).get('layouts')
        slides = [{'id': 'end', 'kind': 'closing', 'title': 'Thanks', 'subtitle': 'Questions'}]
        made = build.chosen_layouts(listed, slides, {'closing': 'Big Statement'})
        self.assertNotEqual(made['closing'], 'Big Statement', 'it has no room for a subtitle')
        self.assertEqual(build.chosen_layouts(listed, slides, {'closing': 'Missing'}),
                         build.layouts(listed, slides))
