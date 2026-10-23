"""Building a deck: its brand, its sections and their composers, the whole deck and its
review, the sections a review sends back, the render and what gate:build shows. The slides
tool and the brand skill are the stand-ins; the workers are played through their tools."""
import copy
import json
import struct
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

import runner_support
from stand_ins import brand as brand_stand_in
from runner_support import LONG_OUTLINE, OUTLINE
from workspace import WorkspaceError

from runner import decks, worker_tools
from runner.steps import build, existing
from studio_core import critic, deck_direction
from runner import brand as brand_skill
from stand_ins.slides import sketch

BY_ID = {slide['id']: slide for slide in OUTLINE['slides']}
PNG_ONE = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
           b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf'
           b'\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`'
           b'\x82')


def drawn(spec: dict, extra=None) -> str:
    """A section as a composer might hand it in: each slide sketched plainly, with every
    approved word, and `extra` nodes added below each slide's drawing."""
    slides = []
    for wanted in spec['slides']:
        if wanted.get('layout'):   # set by the runner: copied as it is given
            slides.append({key: wanted[key] for key in ('id', 'title', 'sources', 'layout',
                                                        'picture', 'notes')
                           if wanted.get(key)})
            continue
        if wanted.get('bare'):   # drawn as before: a shape, any picture given, no words
            shape = {'type': 'box', 'id': f"{spec['prefix']}shape"}
            slides.append({'id': wanted['id'], 'title': wanted['title'],
                           'sources': wanted['sources'], 'notes': wanted['notes'],
                           'canvas': {'type': 'stack', 'direction': 'column',
                                      'children': [wanted['image'], shape]}
                           if wanted.get('image') else shape})
            continue
        slide = sketch(BY_ID[wanted['id']], spec['prefix'])
        if wanted.get('image'):   # a picture the person gave, placed as it is given
            slide['canvas'] = {'type': 'stack', 'direction': 'column',
                               'children': [slide['canvas'], wanted['image']]}
        # The approved notes and provenance are copied as the brief gives them.
        if wanted.get('notes') is not None:
            slide['notes'] = wanted['notes']
        if wanted.get('provenance'):
            slide['provenance'] = wanted['provenance']
        if extra:
            slide['canvas'] = {'type': 'stack', 'direction': 'column',
                               'children': [slide['canvas'], *extra]}
        slides.append(slide)
    return json.dumps({'version': 1, 'title': spec['title'], 'direction': spec['direction'],
                       'slides': slides})


class Deck(unittest.TestCase):
    """A deck folder with the stand-in tools, its brand exported and its outline approved."""
    route, level = 'scratch', None

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name).resolve()
        self.root = self.base / 'presentations' / 'restarts'
        self.root.mkdir(parents=True)
        form = {'route': self.route, 'title': 'Rolling restarts', 'brand': 'example',
                'variant': 'light', 'output': 'google',
                **({'level': self.level} if self.level else {})}
        self.run_ = {'schema': 1, 'id': 'restarts', 'title': 'Rolling restarts',
                     'route': self.route, 'form': form, 'gates': {}, 'steps': {},
                     'revisions': [], 'halted': None}
        decks.write_run(self.root, self.run_)
        self.slides = runner_support.stand_in_slides()
        self.brand = runner_support.stand_in_brand()
        (self.root / 'outline.json').write_text(json.dumps(OUTLINE), encoding='utf-8')
        self.contract = build.export_brand(self.root, self.run_, self.brand)
        self.jobs = 0

    def job(self, work) -> worker_tools.WorkerTools:
        self.jobs += 1
        folder = self.base / 'jobs' / str(self.jobs)
        worker_tools.prepare(folder, **work.prepared)
        return worker_tools.WorkerTools(folder, slides=self.slides, brand=self.brand)

    def draw(self, section: str) -> None:
        """Play one section's composer: preview a plain drawing of it and hand it in."""
        work = build.section_work(self.root, self.run_, section, None, None)
        tools = self.job(work)
        section_drawn = drawn(work.prepared['artifacts']['section'])
        outcome = tools.preview_section(section_drawn)
        self.assertTrue(outcome[0], outcome[1])
        self.assertTrue(tools.submit_section(section_drawn, changed='Nothing.')[0])
        build.keep_section(self.root, self.run_, section,
                           worker_tools.collect(tools.folder))

    def built(self) -> dict:
        build.start(self.root, self.run_, self.slides, self.contract)
        for section in build.to_draw(self.root):
            self.draw(section)
        return build.whole(self.root, self.run_, self.slides, 'local')

    def review(self, findings) -> list:
        """Play the reviewer: look at every slide, then hand in `findings(slides)`."""
        work = build.review_work(self.root, self.run_)
        tools = self.job(work)
        listed = work.prepared['review']['slides']
        if work.prepared['review'].get('sheet'):
            self.assertTrue(tools.look_at_deck()[0])
        for slide in listed:
            self.assertTrue(tools.look_at_slide(slide['number'])[0])
        outcome = tools.submit_assessment(json.dumps(findings(listed)), '[]')
        self.assertTrue(outcome[0], outcome[1])
        return build.keep_review(self.root, self.run_, worker_tools.collect(tools.folder))


def grave(slides):
    """A major finding about how the second slide is drawn."""
    return [{'slide': slides[1]['id'], 'question': 6, 'severity': 'major',
             'about': 'drawing', 'note': 'The two boxes crowd the left half of the slide.'}]


class BrandTests(Deck):
    def test_the_brand_is_exported_once_and_reused(self):
        for name in ('brand-contract.json', 'DESIGN.md', 'VOICE.md', 'version.txt'):
            self.assertTrue((self.root / 'brand' / name).is_file(), name)
        revision = json.loads(self.contract.read_text())['revision']
        self.assertEqual((self.root / build.VERSION).read_text().strip(), revision)
        again = build.export_brand(self.root, self.run_, self.brand)
        self.assertEqual(again, self.contract)
        self.assertEqual(sum(call[:2] == ['contract', 'export']
                             for call in self.brand.run.calls), 1)
        self.assertIn(['contract', 'check'], [call[:2] for call in self.brand.run.calls])
        self.assertIsNone(decks.read_run(self.root)['halted'])

    def test_a_brand_that_changed_stops_the_deck(self):
        rules = self.brand.run.home / 'references' / 'brand-rules.md'
        rules.write_text(rules.read_text() + 'Round corners now.\n')
        with self.assertRaises(build.BrandChanged) as caught:
            build.export_brand(self.root, self.run_, self.brand)
        self.assertIn('The brand changed since this deck began', str(caught.exception))
        halted = decks.read_run(self.root)['halted']
        self.assertTrue(halted['why'].startswith('The brand changed since this deck began'))


class DeliveryTests(Deck):
    """Talk or handout is decided once, on the form, and build.delivery is where the brand
    export, the look samples and the outline read it."""

    def test_the_forms_answer_reaches_the_export_the_looks_and_the_outline(self):
        import shutil
        from runner.steps import look, outline as outlines
        self.run_['form']['delivery'] = 'live'
        self.assertEqual(build.delivery(self.run_), 'live')
        shutil.rmtree(self.root / build.BRAND)
        self.brand.run.offers_looks = True
        contract = build.export_brand(self.root, self.run_, self.brand)
        exported = [call for call in self.brand.run.calls if call[:2] == ['contract', 'export']]
        self.assertEqual(exported[-1][exported[-1].index('--delivery') + 1], 'live')
        look.draw_looks(self.root, self.run_, self.brand, 'local')
        sampled = [call for call in self.brand.run.calls if call[:2] == ['look', 'samples']]
        self.assertEqual(sampled[-1][sampled[-1].index('--delivery') + 1], 'live')
        # The outline is held to it, whatever its writer put, and the build starts from it.
        work = outlines.outline_work(self.root, self.run_, None, None, contract, self.slides)
        spec = work.prepared['artifacts']['outline']
        self.assertEqual(spec['delivery'], 'live')
        scratch = self.base / 'scratch'
        scratch.mkdir()
        written = {**OUTLINE, 'delivery': 'reading'}
        _, _, _, kept = worker_tools.check_outline(json.dumps(written), spec, self.slides, scratch)
        self.assertEqual(json.loads(kept)['delivery'], 'live')
        build.start(self.root, self.run_, self.slides, contract)
        told = json.loads((self.root / build.START / build.TOOL_OUTLINE).read_text())
        self.assertEqual(told['delivery'], 'live')

    def test_a_deck_from_before_the_question_is_a_handout(self):
        self.run_['form'].pop('delivery', None)
        self.assertEqual(build.delivery(self.run_), 'reading')


class GuidanceTests(Deck):
    """The brand as the entry to slide building: the deck's slide task is started through
    it, and its guidance, not only the slides tool's own, is what the workers are handed."""

    def entered(self, guides=True):
        import shutil
        self.brand.run.guides = guides
        shutil.rmtree(self.root / build.BRAND)
        return build.export_brand(self.root, self.run_, self.brand)

    def test_an_older_brand_is_noted_and_the_tools_own_guidance_is_used(self):
        kept = build.guided(self.root)
        self.assertEqual(kept['problem'], build.NO_ENTRY)
        self.assertEqual(build.guided_reading(self.root), {})
        self.assertEqual(set(build.brand_for_workers(self.root, self.contract)), {'brand design'})

    def test_the_deck_task_is_started_through_the_brand_and_kept_out_of_the_share(self):
        self.entered()
        kept = build.guided(self.root)
        self.assertEqual((kept['brand'], kept['variant'], kept['worker']),
                         ('example', 'light', True))
        self.assertIn('task', kept)
        self.assertNotIn('problem', kept)
        start = [call for call in self.brand.run.calls if call[:2] == ['guidance', 'start']]
        self.assertEqual(start[-1][start[-1].index('--project') + 1], str(self.root / 'work'))
        self.assertTrue(str(build.ENTRY).startswith('work/'), 'never shared: it names a runtime')
        self.assertEqual(build.guided_reading(self.root)['drafting guidance'],
                         'Choose the look from real slides.\n')
        self.assertEqual(build.brand_for_workers(self.root, self.contract),
                         {'brand worker guidance': brand_stand_in.WORKER})
        # Exported again for the same brand, the task is resumed, not started again.
        task = kept['task']
        self.entered()
        self.assertEqual(build.guided(self.root)['task'], task)
        self.assertEqual(self.brand.run.calls[-1][:2], ['guidance', 'resume'])

    def test_every_composer_and_the_outline_writer_get_the_brands_worker_guidance(self):
        from runner.steps import outline as outlines
        self.entered()
        build.start(self.root, self.run_, self.slides, self.contract)
        work = build.section_work(self.root, self.run_, 'section-1', None, None)
        inputs = work.prepared['inputs']
        self.assertEqual(inputs['brand worker guidance'], brand_stand_in.WORKER)
        self.assertEqual(inputs['composition guidance'], 'Compose from containers.\n')
        written = outlines.outline_work(self.root, self.run_, None, None, self.contract,
                                        self.slides)
        self.assertEqual(written.prepared['inputs']['brand worker guidance'],
                         brand_stand_in.WORKER)
        self.assertIn('drafting guidance', written.prepared['inputs'])

    def test_reviewer_reads_the_review_guidance(self):
        self.entered()
        self.built()
        inputs = build.review_work(self.root, self.run_).prepared['inputs']
        self.assertEqual(list(inputs), ['the review', 'review guidance',
                                        'brand review checklist'])
        self.assertEqual(inputs['review guidance'], 'Review every slide.\n')
        self.assertIn('Use the Brand checklist.', inputs['brand review checklist'])

    def test_without_them_the_reviewer_has_only_the_review(self):
        self.built()
        inputs = build.review_work(self.root, self.run_).prepared['inputs']
        self.assertEqual(list(inputs), ['the review'])

    def test_a_brand_whose_entry_fails_is_noted_and_the_deck_carries_on(self):
        self.brand.run.guides = True
        original = self.brand.guidance

        def refused(*given, **named):
            raise brand_skill.Refused(['Guidance fetch failed: offline.'])
        self.brand.guidance = refused
        kept = build.guide(self.root, self.run_, self.brand)
        self.brand.guidance = original
        self.assertIn('could not be started', kept['problem'])
        self.assertIn('offline', kept['problem'])


class StartTests(Deck):
    route = 'existing'

    def started(self, level):
        self.run_['form']['level'] = level
        build.start(self.root, self.run_, self.slides, self.contract)
        given = self.root / build.START / 'given'
        return json.loads((given / 'outline.json').read_text()), \
            (given / 'section-1.md').read_text()

    def test_each_level_adds_its_own_house_line(self):
        for level in ('brand-only', 'polish', 'redesign'):
            whole, brief = self.started(level)
            self.assertEqual(whole['house'][-1], build.FREEDOM[level], level)
            self.assertIn(build.FREEDOM[level], brief, level)
            others = [line for name, line in build.FREEDOM.items() if name != level]
            self.assertFalse(any(line in whole['house'] for line in others), level)
        whole, brief = self.started('rework')
        self.assertEqual(whole['house'], list(build.HOUSE))
        self.assertIn('Add no icons', build.FREEDOM['brand-only'])

    def test_the_house_rules_are_about_what_a_slide_says_never_how_it_looks(self):
        rules = ' '.join(build.HOUSE).lower()
        for visual in ('peers', 'square corners', 'icon', 'colour', 'sentence case'):
            self.assertNotIn(visual, rules)

    def test_start_uses_the_direction_the_brand_gives(self):
        own = {'focal': 'accentAqua', 'neutral': 'canvasSecondary',
               'meanings': {'headingPrimary': 'Our product'}}
        (Path(self.contract).parent / deck_direction.FILE).write_text(json.dumps(own))
        whole, brief = self.started('rework')
        self.assertEqual(whole['direction'], own)
        self.assertIn('- `headingPrimary`: Our product', brief)

    def test_start_adds_the_direction_layouts_and_approval(self):
        whole, brief = self.started('rework')
        self.assertEqual(whole['direction'], build.DIRECTION, 'the brand gives none')
        self.assertIsNone(deck_direction.of_file(self.contract))
        self.assertIn('## Colour', brief)
        self.assertEqual(set(whole['layouts']), {'cover', 'closing'})
        self.assertTrue(whole['approval'])
        self.assertIn('submit_section', brief)
        self.assertNotIn(str(self.root), brief)
        state = build.read_state(self.root)
        self.assertEqual(build.to_draw(self.root),
                         [entry['id'] for entry in state['start']['sections']])


class LoopTests(Deck):
    def test_local_repair_freezes_other_slides_and_tracks_persistent_findings(self):
        self.built()
        first = self.review(grave)
        state = build.read_state(self.root)
        section = state['repair'][0]
        work = build.section_work(self.root, self.run_, section, None, None)
        spec = work.prepared['artifacts']['section']
        self.assertTrue(spec['unchanged_slides'])
        earlier = json.loads(work.prepared['inputs']['your earlier section'])
        changed = copy.deepcopy(earlier)
        frozen = next(iter(spec['unchanged_slides']))
        next(slide for slide in changed['slides'] if slide['id'] == frozen)['notes'] = 'Changed without permission'
        self.assertTrue(any('no requested repair' in error for error in build.kept(changed, spec)))
        for part in build.to_draw(self.root): self.draw(part)
        build.whole(self.root, self.run_, self.slides, 'local')
        again = self.review(grave)
        self.assertEqual(first[0]['id'], again[0]['id'])
        self.assertTrue(again[0]['persistent'])
        repair = build.section_work(self.root, self.run_, section, None, None)
        self.assertEqual(repair.purpose, 'repair-escalated')
        self.assertIn(first[0]['id'], repair.prepared['artifacts']['section']['escalation_reason'])

    def test_sections_are_drawn_put_together_and_pictured(self):
        made = self.built()
        self.assertEqual(build.to_draw(self.root), [])
        shots = json.loads((build.shots(self.root) / 'shots.json').read_text())
        self.assertEqual([one['number'] for one in shots['slides']],
                         [slide['number'] for slide in made['slides']])
        self.assertEqual(len(made['slides']), len(OUTLINE['slides']))
        self.assertEqual((self.root / 'contact-sheet.png').read_bytes()[:8], build.PNG)
        self.assertEqual(made['changed'], [])

    def test_review_sends_sections_back_at_most_twice(self):
        self.built()
        rounds = []
        for _ in range(3):
            found = self.review(grave)
            back = build.repair_sections(found)
            self.assertTrue(back)
            rounds.append(build.to_draw(self.root))
            for section in build.to_draw(self.root):
                work = build.section_work(self.root, self.run_, section, None, None)
                self.assertIn('what the review found', work.prepared['inputs'])
                self.assertTrue(work.prepared['look'])
                self.draw(section)
            if build.to_draw(self.root) == [] and rounds[-1]:
                build.whole(self.root, self.run_, self.slides, 'local')
        self.assertTrue(rounds[0] and rounds[1])
        self.assertEqual(rounds[2], [])
        for number in (1, 2, 3):
            self.assertTrue((self.root / 'reviews' / f'build-{number}.md').is_file())
        last = (self.root / 'reviews' / 'build-3.md').read_text()
        self.assertIn('What is left is yours to decide', last)
        self.assertIn('major', (self.root / 'reviews' / 'build-1.md').read_text())

    def test_a_clear_review_sends_nothing_back(self):
        self.built()
        self.assertEqual(self.review(lambda slides: []), [])
        self.assertEqual(build.to_draw(self.root), [])
        self.assertIn('nothing major', (self.root / 'reviews' / 'build-1.md').read_text())

    def test_render_and_gate_view(self):
        self.built()
        self.review(grave)
        deck = build.render(self.root, self.run_, self.slides, brand=self.brand)
        self.assertEqual(deck, self.root / build.DECK)
        last = build.read_state(self.root)['rounds'][-1]
        # The deck delivered is the one previewed and reviewed, not a fresh render.
        self.assertEqual(deck.read_bytes(), (self.root / last['file']).read_bytes())
        self.assertEqual(build._digest(deck), last['deck'])
        self.assertNotIn(['compose', 'render'], [call[:2] for call in self.slides.run.calls])
        self.assertEqual(build.delivered_deck(self.root, self.run_), deck)
        shown = build.gate_view(self.root, self.run_)
        self.assertEqual(shown['round'], 1)
        self.assertEqual(shown['pairs'], [])
        self.assertEqual(shown['contactSheet'], str(self.root / 'contact-sheet.png'))
        second = shown['slides'][1]
        self.assertEqual(second['findings'][0]['severity'], 'major')
        self.assertTrue(Path(second['image']).is_file())
        self.assertIsInstance(shown['audit']['warnings'], int)
        self.assertIn('status', shown['audit'])
        self.assertEqual(decks.read_run(self.root)['gates']['gate:build']['state'], 'waiting')

    def test_without_the_brand_skill_the_audit_says_why(self):
        self.built()
        build.render(self.root, self.run_, self.slides)
        shown = build.gate_view(self.root, self.run_)
        self.assertIsNone(shown['audit'])
        self.assertTrue(shown['auditNote'])

    def test_a_section_drawn_again_marks_its_slides_changed(self):
        self.built()
        self.review(grave)
        for section in build.to_draw(self.root):
            work = build.section_work(self.root, self.run_, section, None, None)
            tools = self.job(work)
            spec = work.prepared['artifacts']['section']
            again = json.loads(drawn(spec, extra=[{'type': 'rule'}]))
            again['slides'] = [spec.get('unchanged_slides', {}).get(slide['id'], slide) for slide in again['slides']]
            outcome = tools.preview_section(again)
            self.assertTrue(outcome[0], outcome[1])
            self.assertTrue(tools.submit_section(again)[0])
            build.keep_section(self.root, self.run_, section,
                               worker_tools.collect(tools.folder))
        made = build.whole(self.root, self.run_, self.slides, 'local')
        self.assertTrue(made['changed'])
        self.assertEqual(build.gate_view(self.root, self.run_)['changed'], made['changed'])


class ToolOutlineTests(Deck):
    """What a newer slides tool knows of the outline: a point's `parts`, and a slide's
    `provenance`; and the approved outline every compile of the build names."""

    def outlined(self):
        made = json.loads(json.dumps(OUTLINE))
        made['slides'][1]['points'][0]['parts'] = ['Drain', 'Restart', 'Rejoin']
        made['slides'][1]['provenance'] = 'Findings g1, g7'
        (self.root / 'outline.json').write_text(json.dumps(made), encoding='utf-8')
        return made

    def test_a_newer_tool_is_given_parts_provenance_and_the_approved_outline(self):
        self.slides.run.extra = {'compose-split-point', 'compose-provenance'}
        self.assertEqual(self.slides.knows(), frozenset({'parts', 'provenance'}))
        made = self.outlined()
        build.start(self.root, self.run_, self.slides, self.contract)
        start = self.root / build.START
        told = json.loads((start / build.TOOL_OUTLINE).read_text())
        self.assertEqual(told['slides'][1]['points'][0]['parts'], ['Drain', 'Restart', 'Rejoin'])
        self.assertEqual(told['slides'][1]['provenance'], 'Findings g1, g7')
        self.assertNotIn('Provenance:', told['slides'][1].get('notes') or '')
        work = build.section_work(self.root, self.run_, 'section-1', None, None)
        spec = work.prepared['artifacts']['section']
        self.assertEqual(Path(spec['outline']).name, build.TOOL_OUTLINE)
        wanted = next(slide for slide in spec['slides'] if slide['id'] == made['slides'][1]['id'])
        self.assertEqual(wanted['provenance'], 'Findings g1, g7')
        self.assertEqual(wanted['points'][0]['parts'], ['Drain', 'Restart', 'Rejoin'])
        # A composer that leaves the provenance out is refused; one that copies it is not.
        section = json.loads(drawn(spec))
        self.assertEqual(build.kept(section, spec), [])
        dropped = json.loads(json.dumps(section))
        next(one for one in dropped['slides'] if one['id'] == wanted['id']).pop('provenance')
        self.assertIn('`provenance` stays exactly as it was approved: "Findings g1, g7"',
                      ' '.join(build.kept(dropped, spec)))
        for section_id in build.to_draw(self.root):
            self.draw(section_id)
        build.whole(self.root, self.run_, self.slides, 'local')
        # Every compile of the build, each section's previews and the whole deck, named it.
        self.assertTrue(self.slides.run.outlined)
        self.assertEqual(set(self.slides.run.outlined), {build.TOOL_OUTLINE})
        compiles = [call for call in self.slides.run.calls if call[:2] == ['compose', 'compile']
                    and '--output' in call]
        self.assertTrue(all('--outline' in call for call in compiles), compiles)

    def test_the_outline_check_hands_the_tool_only_what_it_knows(self):
        made = self.outlined()
        scratch = self.base / 'scratch'
        scratch.mkdir()
        spec = {'kind': 'outline', 'brand': str(self.contract), 'rules': []}
        problems, outcomes, _, kept = worker_tools.check_outline(
            json.dumps(made), spec, self.slides, scratch)
        self.assertEqual(problems, [], outcomes)
        self.assertEqual(json.loads(kept), made, 'the outline itself is kept whole')
        checked = [call for call in self.slides.run.calls if call[:2] == ['outline', 'check']]
        sent = json.loads(Path(checked[-1][checked[-1].index('--file') + 1]).read_text())
        self.assertNotIn('provenance', sent['slides'][1])
        self.assertNotIn('parts', sent['slides'][1]['points'][0])
        self.slides.run.extra = {'compose-split-point', 'compose-provenance'}
        self.slides._asked_capabilities = False
        worker_tools.check_outline(json.dumps(made), spec, self.slides, scratch)
        checked = [call for call in self.slides.run.calls if call[:2] == ['outline', 'check']]
        sent = json.loads(Path(checked[-1][checked[-1].index('--file') + 1]).read_text())
        self.assertEqual(sent['slides'][1]['provenance'], 'Findings g1, g7')

    def test_an_older_tool_has_provenance_in_the_notes_and_never_sees_parts(self):
        made = self.outlined()
        self.assertEqual(self.slides.knows(), frozenset())
        build.start(self.root, self.run_, self.slides, self.contract)
        told = json.loads((self.root / build.START / build.TOOL_OUTLINE).read_text())
        slide = told['slides'][1]
        self.assertNotIn('provenance', slide)
        self.assertNotIn('parts', slide['points'][0])
        self.assertTrue(slide['notes'].endswith('Provenance: Findings g1, g7'))
        self.assertTrue(slide['notes'].startswith(made['slides'][1]['notes']))
        for section_id in build.to_draw(self.root):
            self.draw(section_id)
        build.whole(self.root, self.run_, self.slides, 'local')
        self.assertEqual(self.slides.run.outlined, [], 'an older tool is never given --outline')


class PreviewRepairTests(Deck):
    """The screen of the whole deck's preview sends slides back before any review."""

    def test_clusters_are_found_from_the_tools_repair_or_from_each_slides_findings(self):
        slides = [{'id': 'a', 'number': 1, 'findings': [
                       {'severity': 'error', 'code': 'text-overflow'}]},
                  {'id': 'b', 'number': 2, 'findings': [
                       {'severity': 'warn', 'code': 'SPLIT_POINT'}]},
                  {'id': 'c', 'number': 3, 'findings': [
                       {'severity': 'warn', 'code': 'text-overlap'}] * 3},
                  {'id': 'd', 'number': 4, 'findings': [
                       {'severity': 'warn', 'code': 'text-overlap'}] * 2}]
        back = build.preview_repairs({}, slides)
        self.assertEqual([entry['slide'] for entry in back], ['a', 'b', 'c'])
        self.assertIn('error', back[0]['why'])
        self.assertIn('split across shapes', back[1]['why'])
        self.assertIn('3 pieces of text overlap', back[2]['why'])
        # A tool with preview-repair-clusters names them itself, and is believed.
        named = {'repair': {'blocking': ['d'], 'slides': [
            {'slide': 'c', 'number': 3, 'blocking': False, 'codes': ['split-point'],
             'objects': []}]}}
        self.assertEqual([entry['slide'] for entry in
                          build.preview_repairs(named, slides, clustered=True)], ['c', 'd'])
        self.assertEqual([entry['slide'] for entry in build.preview_repairs(named, slides)],
                         ['a', 'b', 'c'], 'an older tool: from each slide\'s findings')

    def overlapping(self):
        second = OUTLINE['slides'][1]['id']
        self.slides.run.screens = {second: [
            {'severity': 'warn', 'code': 'text-overlap', 'detail': 'Text runs into text.'}] * 3}
        return second

    def test_a_slide_the_preview_flags_is_drawn_again_before_any_review(self):
        second = self.overlapping()
        made = self.built()
        self.assertEqual([entry['slide'] for entry in made['preview_repair']], [second])
        state = build.read_state(self.root)
        self.assertEqual((state['repair'], state['repaired']), (['section-1'], 1))
        self.assertEqual(build.to_draw(self.root), ['section-1'])
        work = build.section_work(self.root, self.run_, 'section-1', None, None)
        self.assertIn('3 pieces of text overlap', work.prepared['inputs']['what the preview found'])
        self.assertIn('what the preview found', work.task)
        # Bounded: after REPAIRS rounds the slide is left for the review and the person.
        for _ in range(build.REPAIRS + 1):
            for section_id in build.to_draw(self.root):
                self.draw(section_id)
            build.whole(self.root, self.run_, self.slides, 'local')
        state = build.read_state(self.root)
        self.assertEqual(state['repaired'], build.REPAIRS)
        self.assertEqual(build.to_draw(self.root), [])

    def test_a_tool_that_names_its_clusters_is_followed(self):
        self.slides.run.extra = {'preview-repair-clusters'}
        second = self.overlapping()
        made = self.built()
        self.assertEqual([entry['slide'] for entry in made['preview_repair']], [second])


class DeliveredDeckTests(Deck):
    def test_a_previewed_deck_that_changed_is_not_delivered(self):
        self.built()
        last = build.read_state(self.root)['rounds'][-1]
        (self.root / last['file']).write_bytes(b'PK\x03\x04 something else')
        with self.assertRaises(WorkspaceError) as caught:
            build.render(self.root, self.run_, self.slides)
        self.assertIn('not here as it was', str(caught.exception))
        self.assertFalse((self.root / build.DECK).exists())

    def test_a_new_round_takes_the_earlier_deck_away(self):
        self.built()
        build.render(self.root, self.run_, self.slides)
        build.whole(self.root, self.run_, self.slides, 'local')
        self.assertFalse((self.root / build.DECK).exists())
        with self.assertRaises(WorkspaceError):
            build.delivered_deck(self.root, self.run_)

    def test_a_deck_left_on_disk_is_not_delivered_unrecorded(self):
        (self.root / build.DECK).parent.mkdir(parents=True, exist_ok=True)
        (self.root / build.DECK).write_bytes(b'PK\x03\x04 left behind')
        with self.assertRaises(WorkspaceError):
            build.delivered_deck(self.root, self.run_)


class PairsTests(Deck):
    route = 'existing'

    def originals(self):
        folder = self.root / existing.ORIGINAL_SHOTS
        folder.mkdir(parents=True)
        listed = []
        for number in range(1, len(OUTLINE['slides']) + 1):
            (folder / f'{number}.png').write_bytes(runner_support.png(number))
            listed.append({'number': number, 'image': f'{number}.png'})
        (folder / 'shots.json').write_text(json.dumps({'slides': listed}))

    def test_polish_shows_before_and_after(self):
        self.run_['form']['level'] = 'polish'
        self.originals()
        self.built()
        pairs = build.gate_view(self.root, self.run_)['pairs']
        self.assertEqual(len(pairs), len(OUTLINE['slides']))
        self.assertTrue(all(Path(pair['after']).is_file() for pair in pairs))

    def test_rework_shows_none(self):
        self.run_['form']['level'] = 'rework'
        self.originals()
        self.built()
        self.assertEqual(build.gate_view(self.root, self.run_)['pairs'], [])


class SelectedTests(unittest.TestCase):
    def selected(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        root = Path(holder.name) / 'deck'
        root.mkdir()
        run = {'schema': 1, 'id': 'd', 'title': 'Old', 'route': 'existing',
               'form': {'route': 'existing', 'level': 'selected', 'selected': 'slide 2'},
               'gates': {}, 'steps': {}}
        decks.write_run(root, run)
        slides = runner_support.stand_in_slides()
        existing.fetch(root, {'kind': 'upload', 'name': 'old.pptx',
                              'data': b'PK\x03\x04stand-in'}, slides, False)
        existing.inventory(root, run, slides, 'local')
        found = json.loads((root / 'classify.json').read_text())
        item = found['slides'][1]['objects'][0]
        existing.keep_patch(root, json.dumps({'sourceSha256': found['sha256'], 'operations': [
            {'slide': 2, 'object': item['id'], 'expectedHash': item['contentHash'],
             'text': 'Run Acme faster'}]}))
        return root, run, slides, found

    def test_selected_renders_the_patched_deck_with_its_pictures(self):
        root, run, slides, found = self.selected()
        deck = build.render(root, run, slides)
        self.assertEqual(deck, root / existing.PATCHED)
        self.assertEqual(build.delivered_deck(root, run), deck)
        shown = build.gate_view(root, run)
        self.assertEqual([slide['number'] for slide in shown['slides']],
                         [slide['number'] for slide in found['slides']])
        self.assertTrue(all(pair['after'] for pair in shown['pairs']))


    def test_its_pictures_reuse_the_one_preview_file_in_drive(self):
        root, run, slides, _ = self.selected()
        build.render(root, run, slides, renderer='drive')
        kept = json.loads((root / 'work' / 'build' / 'drive-preview.json').read_text())
        build.render(root, run, slides, renderer='drive')
        previews = [ident for ident in slides.run.files if ident.startswith('stand-in-preview')]
        self.assertEqual(previews, [kept['id']])
        self.assertEqual(slides.run.files[kept['id']]['uploads'], 2)
        asked = [call for call in slides.run.calls if call[:1] == ['review']]
        self.assertIn(kept['id'], asked[-1])

    def test_a_picture_that_fails_leaves_no_patched_deck(self):
        root, run, slides, _ = self.selected()
        slides.run.fails['review'] = 'The renderer stopped.'
        with self.assertRaises(WorkspaceError):
            build.render(root, run, slides)
        self.assertFalse((root / existing.PATCHED).exists())
        with self.assertRaises(WorkspaceError):
            build.delivered_deck(root, run)


class RefusalTests(Deck):
    def test_steps_out_of_order_are_refused(self):
        with self.assertRaises(WorkspaceError):
            build.section_work(self.root, self.run_, 'section-1', None, None)
        with self.assertRaises(WorkspaceError):
            build.review_work(self.root, self.run_)
        build.start(self.root, self.run_, self.slides, self.contract)
        with self.assertRaises(WorkspaceError) as caught:
            build.whole(self.root, self.run_, self.slides, 'local')
        self.assertIn('not drawn yet', str(caught.exception))
        with self.assertRaises(WorkspaceError):
            build.section_work(self.root, self.run_, 'section-9', None, None)

    def test_brand_only_and_polish_composers_draw_only_the_approved_words(self):
        build.start(self.root, self.run_, self.slides, self.contract)
        for route, level, strict in (('existing', 'brand-only', True),
                                     ('existing', 'polish', True),
                                     ('existing', 'redesign', False), ('scratch', None, False)):
            run = copy.deepcopy(self.run_)
            run['route'], run['form']['level'] = route, level
            work = build.section_work(self.root, run, 'section-1', None, None)
            self.assertIs(work.prepared['artifacts']['section']['strict'], strict, level)

    def test_a_slide_whose_original_shows_no_words_is_bare_at_brand_only(self):
        build.start(self.root, self.run_, self.slides, self.contract)
        given = json.loads((self.root / build.START / 'given' / 'outline.json').read_text())
        first = next(slide for slide in given['slides'] if slide.get('kind') == 'content')
        number = given['slides'].index(first) + 1
        slides = [{'number': n, 'title': 'Words', 'objects': [
            {'id': '2', 'type': 'sp', 'text': 'Words', 'runs': ['Words']}]}
            for n in range(1, len(given['slides']) + 1)]
        slides[number - 1] = {'number': number, 'title': '', 'objects': []}
        (self.root / 'classify.json').write_text(json.dumps({'slides': slides}))
        for level, bare in (('brand-only', True), ('polish', True), ('redesign', False)):
            run = copy.deepcopy(self.run_)
            run['route'], run['form']['level'] = 'existing', level
            spec = build.section_work(self.root, run, 'section-1', None, None) \
                .prepared['artifacts']['section']
            marked = {slide['id']: slide['bare'] for slide in spec['slides']}
            self.assertIs(marked.get(first['id'], False), bare, level)

    def test_a_gate_note_reaches_the_composer(self):
        self.built()
        run = copy.deepcopy(self.run_)
        run['gates']['gate:build'] = {'state': 'changes', 'note': 'Make the cover calmer.'}
        work = build.section_work(self.root, run, 'section-1', None, None)
        self.assertIn('Make the cover calmer.', work.task)



# --- a slide that had no words -------------------------------------------------------------

def png(wide: int = 16, high: int = 9) -> bytes:
    """A grey picture of `wide` by `high` pixels."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data \
            + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\x00' + b'\x80' * wide for _ in range(high))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', wide, high, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
SHAPE = ('<p:sp><p:nvSpPr><p:cNvPr id="5" name="Arrow"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
         '<p:spPr/></p:sp>')
EMPTY_TITLE = ('<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:cNvSpPr/><p:nvPr>'
               '<p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:p/></p:txBody>'
               '</p:sp>')
HIDDEN = ('<p:sp><p:nvSpPr><p:cNvPr id="6" name="Note" hidden="1"/><p:cNvSpPr/><p:nvPr/>'
          '</p:nvSpPr><p:spPr/></p:sp>')


def picture_xml(ident: int, rel: str, crop: str = '', video: bool = False) -> str:
    media = (f'<a:videoFile r:link="rId9"/>' if video else '')
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{ident}" name="Picture {ident}" descr="Racks"/>'
            f'<p:cNvPicPr/><p:nvPr>{media}</p:nvPr></p:nvPicPr><p:blipFill>'
            f'<a:blip r:embed="{rel}"/>{crop}</p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/>'
            '<a:ext cx="9144000" cy="5143500"/></a:xfrm></p:spPr></p:pic>')


def original(path: Path, count: int, pictured: int | None, media: str = 'image1.png',
             data: bytes | None = None, shapes: str | None = None, target: str | None = None,
             corrupt: bool = False) -> None:
    """A deck of `count` slides as PowerPoint writes one. Slide `pictured` shows `shapes`,
    by default one picture, kept as ppt/media/`media` (`data`, a 16 by 9 PNG unless said)
    and named by `target`; every other slide shows a word. `corrupt` spoils the picture's
    compressed bytes in the file."""
    ids = ''.join(f'<p:sldId id="{255 + n}" r:id="rId{n}"/>' for n in range(1, count + 1))
    rels = ''.join(f'<Relationship Id="rId{n}" Type="{R}/slide" Target="slides/slide{n}.xml"/>'
                   for n in range(1, count + 1))
    data = png() if data is None else data
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as deck:
        deck.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{P}" xmlns:r="{R}">'
                      f'<p:sldIdLst>{ids}</p:sldIdLst></p:presentation>')
        deck.writestr('ppt/_rels/presentation.xml.rels',
                      f'<Relationships xmlns="{REL}">{rels}</Relationships>')
        for n in range(1, count + 1):
            shown = (picture_xml(4, 'rId2') if shapes is None else shapes) if n == pictured \
                else ('<p:sp><p:nvSpPr><p:cNvPr id="2" name="Text"/><p:cNvSpPr/><p:nvPr/>'
                      '</p:nvSpPr><p:txBody><a:p><a:r><a:t>Words</a:t></a:r></a:p>'
                      '</p:txBody></p:sp>')
            deck.writestr(f'ppt/slides/slide{n}.xml',
                          f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld>'
                          f'<p:spTree>{shown}</p:spTree></p:cSld></p:sld>')
            if n == pictured:
                deck.writestr(f'ppt/slides/_rels/slide{n}.xml.rels',
                              f'<Relationships xmlns="{REL}"><Relationship Id="rId2" '
                              f'Type="{R}/image" Target="{target or "../media/" + media}"/>'
                              '</Relationships>')
        deck.writestr(f'ppt/media/{media}', data)
    if corrupt:
        with zipfile.ZipFile(path) as deck:
            info = deck.getinfo(f'ppt/media/{media}')
        raw = bytearray(path.read_bytes())
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        raw[start:start + 8] = b'\xff' * 8
        path.write_bytes(bytes(raw))


class WordlessTests(Deck):
    """At brand only and polish, a slide whose original shows no words is set on a template
    layout that shows no title when its one picture can be carried there; otherwise it is
    drawn as before, under its title, with a note at the gate."""
    route = 'existing'
    BARE = 'when-capacity-holds'   # the third slide
    PICTURE = {'id': '4', 'type': 'pic', 'text': '', 'runs': [], 'alt': 'Racks of servers'}

    def setUp(self):
        super().setUp()
        self.outline = copy.deepcopy(OUTLINE)
        self.outline['slides'][2] = {
            'id': self.BARE, 'kind': 'content', 'relation': 'none', 'points': [],
            'title': BY_ID[self.BARE]['title'], 'understand': 'A picture of the racks.',
            'notes': BY_ID[self.BARE]['notes'], 'sources': BY_ID[self.BARE]['sources']}
        self.count = len(self.outline['slides'])
        self.objects([self.PICTURE])
        (self.root / 'sources').mkdir()
        original(self.root / existing.SOURCE, self.count, 3)

    def objects(self, found: list[dict], number: int = 3) -> None:
        """The inventory, with `found` the objects of slide `number`."""
        slides = [{'number': n, 'id': str(255 + n), 'title': 'Words', 'objects': [
            {'id': '2', 'type': 'sp', 'text': 'Words', 'runs': ['Words']}]}
            for n in range(1, self.count + 1)]
        slides[number - 1] = {'number': number, 'id': str(255 + number), 'title': '',
                              'objects': found}
        (self.root / 'classify.json').write_text(json.dumps({'slides': slides}))

    def at(self, level, outline=None):
        self.run_['form']['level'] = level
        (self.root / 'outline.json').write_text(json.dumps(outline or self.outline))

    def began(self) -> dict:
        return build.read_state(self.root)['start']

    def delivered_words(self) -> list[str]:
        """The words written on each slide of the delivered deck."""
        build.render(self.root, self.run_, self.slides)
        with zipfile.ZipFile(build.delivered_deck(self.root, self.run_)) as deck:
            return [deck.read(f'ppt/slides/slide{n}.xml').decode()
                    for n in range(1, self.count + 1)]

    def carried(self) -> None:
        """Build at brand only; slide 3 is set on the layout with its picture, wordless."""
        self.at('brand-only')
        self.built()
        placed = self.began()['wordless']
        self.assertEqual(placed, {self.BARE: {'layout': 'Quote', 'picture': {
            'src': 'pictures/slide-3.png', 'alt': 'Racks of servers'}}})
        self.assertEqual(self.began()['titled'], {})
        words = self.delivered_words()
        self.assertNotIn('<a:t>', words[2], 'no words at all on that slide')
        self.assertIn(BY_ID['what-it-does']['title'], words[1])

    def falls_back(self, note=build.TITLED, image=True) -> None:
        """Build at brand only; slide 3 is drawn as before, under its title, with its
        picture as a fixed image where `image`, and the gate says so on that slide."""
        self.at('brand-only')
        self.built()
        began = self.began()
        self.assertEqual(began['wordless'], {})
        self.assertEqual(list(began['titled']), [self.BARE])
        self.assertEqual(began['titled'][self.BARE]['note'], note)
        self.assertIs('image' in began['titled'][self.BARE], image)
        compiled = self.root / build.read_state(self.root)['rounds'][-1]['compiled']
        scene = json.loads((compiled / 'scene.json').read_text())
        elements = [element for slide in scene['slides'] if slide['id'] == self.BARE
                    for element in slide['elements']]
        self.assertTrue(any(element['id'].endswith('shape') for element in elements))
        self.assertIs(any(element.get('type') == 'image' for element in elements), image)
        notes = {slide['number']: slide.get('note')
                 for slide in build.gate_view(self.root, self.run_)['slides']}
        self.assertEqual({number: said for number, said in notes.items() if said}, {3: note})
        self.assertIn(BY_ID[self.BARE]['title'], self.delivered_words()[2])

    # --- carried onto a layout without a title

    def test_brand_only_and_polish_set_it_on_a_layout_without_a_title(self):
        self.carried()
        self.assertEqual((self.root / build.START / 'pictures' / 'slide-3.png').read_bytes(),
                         png())
        self.at('polish')
        self.built()
        self.assertIn(self.BARE, self.began()['wordless'])
        self.assertNotIn('<a:t>', self.delivered_words()[2])

    def test_a_picture_cropped_to_the_slot_s_shape_is_carried(self):
        crop = '<a:srcRect t="21875" b="21875"/>'   # a square cut to 16 by 9
        original(self.root / existing.SOURCE, self.count, 3, data=png(16, 16),
                 shapes=picture_xml(4, 'rId2', crop))
        self.carried()

    def test_a_target_named_from_the_package_root_is_carried(self):
        original(self.root / existing.SOURCE, self.count, 3, target='/ppt/media/image1.png')
        self.carried()

    def test_a_picture_under_an_empty_title_placeholder_is_carried(self):
        self.objects([{'id': '2', 'type': 'sp', 'text': '', 'runs': []}, self.PICTURE])
        original(self.root / existing.SOURCE, self.count, 3,
                 shapes=EMPTY_TITLE + picture_xml(4, 'rId2'))
        self.carried()

    def test_a_picture_beside_a_hidden_shape_is_carried(self):
        self.objects([self.PICTURE, {'id': '6', 'type': 'sp', 'text': '', 'runs': []}])
        original(self.root / existing.SOURCE, self.count, 3,
                 shapes=picture_xml(4, 'rId2') + HIDDEN)
        self.carried()

    def test_the_composer_is_told_the_layout_and_may_not_change_it(self):
        self.at('brand-only')
        build.start(self.root, self.run_, self.slides, self.contract)
        section = next(entry['id'] for entry in self.began()['sections']
                       if self.BARE in entry['slides'])
        work = build.section_work(self.root, self.run_, section, None, None)
        spec = work.prepared['artifacts']['section']
        mine = next(slide for slide in spec['slides'] if slide['id'] == self.BARE)
        self.assertEqual(mine['layout'], 'Quote')
        self.assertIn('Quote', work.task)
        self.assertNotIn(str(self.root), work.task)
        self.assertIn('copy it exactly as given',
                      (self.root / build.START / 'given' / f'{section}.md').read_text())
        handed = json.loads(drawn(spec))
        self.assertEqual(build.kept(handed, spec), [])
        at = [slide['id'] for slide in handed['slides']].index(self.BARE)
        for change in ({'layout': 'Blank'}, {'picture': None},
                       {'canvas': {'type': 'text', 'id': f"{spec['prefix']}x",
                                   'text': BY_ID[self.BARE]['title']}},
                       {'subtitle': 'Racks of servers'}):
            wrong = copy.deepcopy(handed)
            wrong['slides'][at].update(change)
            wrong['slides'][at] = {key: value for key, value in wrong['slides'][at].items()
                                   if value is not None}
            self.assertTrue(build.kept(wrong, spec), change)
        others = copy.deepcopy(handed)
        other = next(slide for slide in others['slides'] if slide['id'] != self.BARE)
        other['layout'] = 'Quote'
        self.assertTrue(build.kept(others, spec), 'a slide the runner did not set')

    # --- drawn as before, under its title

    def test_a_picture_of_another_shape_than_the_slot_keeps_it_under_its_title(self):
        original(self.root / existing.SOURCE, self.count, 3, data=png(9, 16))
        self.falls_back()

    def test_the_composer_must_place_the_fixed_picture(self):
        original(self.root / existing.SOURCE, self.count, 3, data=png(9, 16))
        self.at('brand-only')
        build.start(self.root, self.run_, self.slides, self.contract)
        section = next(entry['id'] for entry in self.began()['sections']
                       if self.BARE in entry['slides'])
        work = build.section_work(self.root, self.run_, section, None, None)
        spec = work.prepared['artifacts']['section']
        mine = next(slide for slide in spec['slides'] if slide['id'] == self.BARE)
        self.assertEqual(mine['image'], {'type': 'image', 'id': mine['image']['id'],
                                         'src': 'pictures/slide-3.png',
                                         'alt': 'Racks of servers', 'fit': 'contain'})
        self.assertIn(json.dumps(mine['image']), work.task)
        handed = json.loads(drawn(spec))
        self.assertEqual(build.kept(handed, spec), [])
        at = [slide['id'] for slide in handed['slides']].index(self.BARE)
        for canvas in ({'type': 'box', 'id': f"{spec['prefix']}shape"},
                       {'type': 'stack', 'direction': 'column', 'children': [
                           {**mine['image'], 'fit': 'cover'}]}):
            wrong = copy.deepcopy(handed)
            wrong['slides'][at]['canvas'] = canvas
            self.assertTrue(build.kept(wrong, spec), canvas)

    def test_a_picture_under_an_empty_title_without_a_fitting_slot_keeps_it(self):
        self.objects([{'id': '2', 'type': 'sp', 'text': '', 'runs': []}, self.PICTURE])
        original(self.root / existing.SOURCE, self.count, 3, data=png(9, 16),
                 shapes=EMPTY_TITLE + picture_xml(4, 'rId2'))
        self.falls_back()

    def test_without_image_nodes_the_note_says_it_is_drawn_afresh(self):
        original(self.root / existing.SOURCE, self.count, 3, data=png(9, 16))
        real = self.slides.compose_contract
        with mock.patch.object(self.slides, 'compose_contract',
                               lambda brand: real(brand).replace('image', 'picture')):
            self.falls_back(build.REDRAWN, image=False)

    def test_two_pictures_are_drawn_as_before(self):
        self.objects([self.PICTURE, {**self.PICTURE, 'id': '5'}])
        original(self.root / existing.SOURCE, self.count, 3,
                 shapes=picture_xml(4, 'rId2') + picture_xml(5, 'rId2'))
        self.falls_back(build.REDRAWN, image=False)

    def test_a_picture_with_a_shape_is_drawn_as_before(self):
        self.objects([self.PICTURE, {'id': '5', 'type': 'sp', 'text': '', 'runs': []}])
        original(self.root / existing.SOURCE, self.count, 3,
                 shapes=picture_xml(4, 'rId2') + SHAPE)
        self.falls_back(build.REDRAWN, image=False)

    def test_a_video_s_poster_frame_is_drawn_as_before(self):
        original(self.root / existing.SOURCE, self.count, 3,
                 shapes=picture_xml(4, 'rId2', video=True))
        self.falls_back(build.REDRAWN, image=False)

    def test_a_slide_of_shapes_alone_keeps_its_drawing_under_its_title(self):
        self.objects([{'id': '5', 'type': 'sp', 'text': '', 'runs': []}])
        original(self.root / existing.SOURCE, self.count, 3, shapes=SHAPE)
        self.falls_back(build.REDRAWN, image=False)

    def test_a_picture_the_slides_tool_cannot_place_is_drawn_as_before(self):
        original(self.root / existing.SOURCE, self.count, 3, media='image1.emf',
                 data=b'\x01\x00\x00\x00 an enhanced metafile')
        self.falls_back(build.REDRAWN, image=False)

    def test_a_damaged_picture_is_drawn_as_before_and_the_build_goes_on(self):
        original(self.root / existing.SOURCE, self.count, 3, corrupt=True)
        self.assertIsNone(existing.original_picture(self.root, 3, self.base / 'out'))
        self.falls_back(build.REDRAWN, image=False)

    def test_a_template_without_a_title_less_layout_with_a_picture_slot(self):
        self.slides.run.layouts = tuple(layout for layout in self.slides.run.layouts
                                        if layout[1] or not layout[3])
        self.falls_back()

    def test_a_template_with_no_layout_without_a_title_goes_on(self):
        self.slides.run.layouts = tuple(layout for layout in self.slides.run.layouts
                                        if layout[1])
        self.falls_back()
        self.assertIsNone(decks.read_run(self.root).get('halted'))

    def test_a_slot_whose_size_cannot_be_read(self):
        with mock.patch.object(existing, 'template_slot', lambda *given: None):
            self.falls_back()

    def test_a_lead_slide_with_no_words_is_left_to_its_layout(self):
        self.objects([self.PICTURE], number=1)
        original(self.root / existing.SOURCE, self.count, 1)
        self.at('brand-only')
        build.start(self.root, self.run_, self.slides, self.contract)
        self.assertEqual((self.began()['wordless'], self.began()['titled']), ({}, {}))

    def test_redesign_draws_its_title_as_before(self):
        self.at('redesign', OUTLINE)
        self.built()
        self.assertEqual((self.began()['wordless'], self.began()['titled']), ({}, {}))
        self.assertIn(BY_ID[self.BARE]['title'], self.delivered_words()[2])
        self.assertFalse(any(slide.get('note') for slide in
                             build.gate_view(self.root, self.run_)['slides']))


if __name__ == '__main__':
    unittest.main()


class CriticQuestionsTests(Deck):
    """The reviewer is asked the slides tool's own questions, as its preview wrote them."""
    THREE = ('Is the point plain at a glance?', 'Is the space balanced?',
             'Does every icon explain something?')

    def built_with(self, questions):
        from stand_ins import slides as slides_stand_in
        with mock.patch.object(slides_stand_in, 'QUESTIONS', questions):
            return self.built()

    def test_reviewer_is_asked_the_rounds_questions(self):
        made = self.built_with(self.THREE)
        self.assertEqual(made['questions'], list(self.THREE))
        work = build.review_work(self.root, self.run_)
        asked = work.prepared['inputs']['the review']
        self.assertIn('1. Is the point plain at a glance?\n2. Is the space balanced?\n'
                      '3. Does every icon explain something?\n', asked)
        self.assertNotIn('\n4. ', asked.split('## How grave')[0])
        self.assertEqual(work.prepared['review']['questions'], list(self.THREE))
        slides = work.prepared['review']['slides']
        found, why = build.checked({'slide': slides[1]['id'], 'question': 4,
                                    'severity': 'major', 'note': 'The boxes crowd the left.'},
                                   slides, self.THREE)
        self.assertIsNone(found)
        self.assertEqual(why, f"{slides[1]['id']}: `question` is a number from 1 to 3.")
        tools = self.job(work)
        if work.prepared['review'].get('sheet'):
            tools.look_at_deck()
        for slide in slides:
            tools.look_at_slide(slide['number'])
        said = tools.submit_assessment(json.dumps([{
            'slide': slides[1]['id'], 'question': 4, 'severity': 'major',
            'note': 'The boxes crowd the left.'}]), '[]')
        self.assertFalse(said[0])
        self.assertIn('`question` is a number from 1 to 3', said[1])

    def test_a_preview_without_the_tools_questions_is_refused_and_kept_nowhere(self):
        build.start(self.root, self.run_, self.slides, self.contract)
        for section in build.to_draw(self.root):
            self.draw(section)
        from stand_ins import slides as slides_stand_in
        with mock.patch.object(slides_stand_in, 'QUESTIONS', ()), \
                self.assertRaises(WorkspaceError) as refused:
            build.whole(self.root, self.run_, self.slides, 'local')
        self.assertIn(critic.MISSING, str(refused.exception))
        self.assertEqual(build.read_state(self.root)['rounds'], [])
        self.assertEqual(list((self.root / build.BUILD).glob('whole-*')), [])

    def test_a_round_saved_before_questions_were_kept_reads_the_legacy_ones(self):
        self.built()
        state = build.read_state(self.root)
        state['rounds'][-1].pop('questions')
        build.write_state(self.root, state)
        self.assertEqual(build.round_questions(state['rounds'][-1]), critic.LEGACY)
        found = self.review(grave)
        self.assertEqual(found[0]['verification'], critic.LEGACY[5])
        self.assertIn(f'6. {critic.LEGACY[5]}', build.asked(
            build.read_state(self.root)['rounds'][-1]['slides'], None, critic.LEGACY))


class BrandAuditTests(Deck):
    """The brand's check runs over each round's previewed deck, before its review."""
    BLOCKED = {'status': 'BLOCKED',
               'blockers': [{'code': 'OFF_PALETTE', 'slide': 3,
                             'says': 'A colour outside the palette.'}],
               'warnings': []}
    WARNED = {'status': 'WARN', 'blockers': [],
              'warnings': [{'code': 'SMALL_TEXT', 'slide': 2, 'says': 'Text under 18 points.'},
                           {'code': 'HIGH_TEXT_DENSITY', 'slide': 4,
                            'says': 'Many words for one slide.'}]}

    def audited(self, report=None, refusal=None) -> dict:
        self.built()
        answer = mock.patch.object(self.brand, 'audit', side_effect=refusal) if refusal \
            else mock.patch.object(self.brand, 'audit', return_value=report)
        with answer as audit:
            build.audit_round(self.root, self.run_, self.brand)
        self.assertEqual(audit.call_args[0][0],
                         self.root / build.read_state(self.root)['rounds'][-1]['file'])
        return build.read_state(self.root)

    def test_a_brand_blocker_sends_its_section_back(self):
        state = self.audited(self.BLOCKED)
        last = state['rounds'][-1]
        third = last['slides'][2]['id']
        finding = last['audit_findings'][0]
        self.assertEqual((finding['slide'], finding['severity'], finding['about'],
                          finding['question'], finding['source']),
                         (third, 'critical', 'drawing', None, 'brand'))
        self.assertEqual(finding['note'], "The brand's check: A colour outside the palette.")
        section = next(entry['id'] for entry in state['start']['sections']
                       if third in entry['slides'])
        self.assertEqual(build.to_draw(self.root), [section])
        self.assertEqual(state['repaired'], 1, 'a brand repair counts against REPAIRS')
        work = build.section_work(self.root, self.run_, section, None, None)
        told = work.prepared['inputs']['what the review found']
        self.assertIn("- **critical**, The brand's check: A colour outside the palette.", told)

    def test_brand_warnings_reach_the_reviewer(self):
        self.audited(self.WARNED)
        self.assertEqual(build.to_draw(self.root), [])
        asked = build.review_work(self.root, self.run_).prepared['inputs']['the review']
        self.assertIn("## What the brand's check noticed", asked)
        self.assertIn('- Slide 2: Text under 18 points.', asked)
        self.assertIn('- Slide 4: Many words for one slide.', asked)

    def test_an_audit_that_cannot_run_changes_nothing(self):
        state = self.audited(refusal=WorkspaceError('The deck could not be opened.'))
        last = state['rounds'][-1]
        self.assertEqual(build.to_draw(self.root), [])
        self.assertEqual(last['auditNote'], "The brand's check of this deck could not be run. "
                                            'The deck could not be opened.')
        self.assertEqual(last.get('audit_findings') or [], [])
        asked = build.review_work(self.root, self.run_).prepared['inputs']['the review']
        self.assertNotIn("brand's check noticed", asked)

    def test_audit_refusal_spends_no_repair_round(self):
        state = self.audited(refusal=WorkspaceError('The deck could not be opened.'))
        self.assertEqual(state.get('repaired', 0), 0)
        self.assertEqual(state.get('repair'), [])

    def test_render_still_audits_the_delivered_deck(self):
        self.audited(self.WARNED)
        self.review(lambda slides: [])
        with mock.patch.object(self.brand, 'audit', return_value=self.BLOCKED) as audit:
            deck = build.render(self.root, self.run_, self.slides, brand=self.brand)
        self.assertEqual(audit.call_args[0][0], deck)
        self.assertEqual(build.read_state(self.root)['audit']['errors'], 1)


class CodeSpanWordTests(unittest.TestCase):
    """A name set as a code span is kept and counted as the same words without backticks."""

    def test_code_spans_are_kept_and_counted_as_words(self):
        spanned = 'High availability (`highAvailability`) is off'
        bare = 'High availability (highAvailability) is off'
        self.assertEqual(len(build.WORD.findall(spanned)), len(build.WORD.findall(bare)))
        self.assertEqual(build.plain(spanned), build.plain(bare))


class SuppliedPictureBuildTests(Deck):
    """A picture the person gave a slide is drawn by its asset, from the deck's asset
    project, and the project is checked before the deck stop."""

    def setUp(self):
        super().setUp()
        from stand_ins import slides as slides_stand_in
        self.slides = slides_stand_in.stand_in(assets=True)
        self.content = next(slide['id'] for slide in OUTLINE['slides']
                            if slide['kind'] == 'content')

    def picture(self, slide):
        file = self.base / 'rack.png'
        file.write_bytes(PNG_ONE)
        kind = next((one['kind'] for one in OUTLINE['slides'] if one['id'] == slide), None)
        return build.record_picture(self.root, self.slides, slide, file,
                                    'A rack of servers in our lab.', 'Our own photograph.',
                                    kind=kind)

    def compiles(self):
        return [call for call in self.slides.run.calls if call[:2] == ['compose', 'compile']]

    def test_compile_uses_the_asset_project(self):
        made = self.picture(self.content)
        self.assertEqual(made['asset'], f'pic-{self.content}')
        self.built()
        project = str(self.root / build.ASSETS)
        whole = [call for call in self.compiles() if '--output' in call][-1]
        self.assertEqual(whole[whole.index('--asset-project') + 1], project)
        section = build.section_work(self.root, self.run_, build.to_draw(self.root)[0]
                                     if build.to_draw(self.root) else 'section-1', None, None)
        spec = section.prepared['artifacts']['section']
        self.assertEqual(spec['asset_project'], project)
        image = next(slide['image'] for slide in spec['slides'] if slide['id'] == self.content)
        self.assertEqual((image['type'], image['asset']), ('image', f'pic-{self.content}'))
        self.assertIn('picture', ' '.join(section.prepared['inputs']).lower()
                      + section.task.lower())

    def test_a_picture_whose_slide_is_gone_or_changed_kind_is_left_out(self):
        self.picture('no-such-slide')
        closing = next(slide['id'] for slide in OUTLINE['slides'] if slide['kind'] == 'closing')
        self.picture(closing)
        self.assertEqual(build.pictures(self.root)[closing]['kind'], 'closing')
        self.built()
        self.assertEqual(build.read_state(self.root)['start']['pictures'], {})
        self.assertFalse(any('--asset-project' in call for call in self.compiles()))

    def test_a_deck_without_a_picture_never_names_the_project(self):
        self.built()
        self.assertFalse(any('--asset-project' in call for call in self.compiles()))

    def test_asset_check_problems_stop_before_the_deck(self):
        self.picture(self.content)
        self.built()
        self.review(lambda slides: [])
        self.slides.run.fails = {'assets check': 'pic-x: the recorded file changed.'}
        with self.assertRaises(WorkspaceError) as refused:
            build.render(self.root, self.run_, self.slides, brand=self.brand)
        self.assertIn('pic-x: the recorded file changed.', str(refused.exception))
        self.assertFalse((self.root / build.DECK).exists())


class ReviewReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'sheet.png').write_bytes(b'synthetic contact sheet')
        slides = [{'id': 'slide-' + str(i), 'number': i, 'sha256': 'c' * 64} for i in range(1, 7)]
        evidence = [{'id': s['id'], 'number': s['number'], 'imageSha256': s['sha256'], 'fingerprint': str(s['number']) * 64} for s in slides]
        coverage = {'questions': list(critic.LEGACY), 'slides': [{'id': s['id'], 'image_sha256': s['sha256'], 'answers': [True] * 8} for s in slides]}
        self.state = {'rounds': [{'deck': 'a' * 64, 'render_evidence': {'schema': 1, 'shared': 'd' * 64, 'deckSha256': 'a' * 64, 'slides': evidence}, 'review': {'findings': [], 'coverage': coverage}},
            {'deck': 'b' * 64, 'render_evidence': {'schema': 1, 'shared': 'd' * 64, 'deckSha256': 'b' * 64, 'slides': copy.deepcopy(evidence)}, 'slides': slides, 'sheet': 'sheet.png'}]}

    def test_one_changed_slide_inspects_it_and_neighbors_and_retains_verified_clear_coverage(self):
        self.state['rounds'][-1]['render_evidence']['slides'][2]['fingerprint'] = 'e' * 64
        reused = build.reusable_review(self.root, self.state)
        self.assertEqual(set(reused), {'slide-1', 'slide-5', 'slide-6'})
        self.assertEqual(reused['slide-1']['from_deck'], 'a' * 64)
        self.assertNotIn('approved', reused['slide-1'])

    def test_shared_dependency_order_image_and_unresolved_findings_invalidate_coverage(self):
        for mutate in (
            lambda state: state['rounds'][-1]['render_evidence'].update(shared='e' * 64),
            lambda state: state['rounds'][-1]['render_evidence'].update(deckSha256='f' * 64),
            lambda state: state['rounds'][-2]['review']['coverage'].update(questions=['changed']),
            lambda state: state['rounds'][-1]['slides'].reverse(),
        ):
            state = copy.deepcopy(self.state)
            mutate(state)
            self.assertEqual(build.reusable_review(self.root, state), {})
        self.state['rounds'][-2]['review']['findings'] = [{'slide': 'slide-3'}]
        self.assertEqual(set(build.reusable_review(self.root, self.state)), {'slide-1', 'slide-5', 'slide-6'})
        self.state['rounds'][-1]['render_evidence']['slides'][5]['imageSha256'] = 'f' * 64
        self.assertNotIn('slide-6', build.reusable_review(self.root, self.state))

    def test_reuse_needs_the_same_questions(self):
        self.state['rounds'][-1]['render_evidence']['slides'][2]['fingerprint'] = 'e' * 64
        self.assertTrue(build.reusable_review(self.root, self.state))
        self.state['rounds'][-1]['questions'] = ['A?', 'B?']
        self.assertEqual(build.reusable_review(self.root, self.state), {})


class StartAgainTests(Deck):
    """A deck started again from an outline that changed in places: the sections whose
    slides did not change are kept as they were drawn."""

    def setUp(self):
        super().setUp()
        # Two sections: slides 2 to 4 and 5 to 7.
        BY_ID.update({slide['id']: slide for slide in LONG_OUTLINE['slides']})
        (self.root / 'outline.json').write_text(json.dumps(LONG_OUTLINE), encoding='utf-8')

    def test_a_second_start_keeps_the_sections_whose_slides_did_not_change(self):
        self.built()
        drawn = dict(build.read_state(self.root)['sections'])
        self.assertEqual(sorted(drawn), ['section-1', 'section-2'])
        first = (self.root / drawn['section-1']['file']).read_text(encoding='utf-8')
        outline = json.loads((self.root / 'outline.json').read_text(encoding='utf-8'))
        outline['slides'][6]['title'] = 'A failed batch goes back, never on'
        (self.root / 'outline.json').write_text(json.dumps(outline), encoding='utf-8')
        BY_ID['rolling-back'] = outline['slides'][6]   # the composer draws the new title
        build.start(self.root, self.run_, self.slides, self.contract)
        self.assertEqual(build.to_draw(self.root), ['section-2'])
        state = build.read_state(self.root)
        kept = state['sections']['section-1']
        # Kept as it was drawn, under a name of this start's own.
        self.assertNotEqual(kept['file'], drawn['section-1']['file'])
        self.assertIn('-kept-', kept['file'])
        self.assertTrue(kept['kept'])
        self.assertEqual((self.root / kept['file']).read_text(encoding='utf-8'), first)
        # What the earlier start drew is gone, kept copy aside.
        self.assertFalse((self.root / drawn['section-1']['file']).is_file())
        self.assertFalse((self.root / drawn['section-2']['file']).is_file())
        self.assertEqual(state['rounds'], [])
        self.draw('section-2')
        made = build.whole(self.root, self.run_, self.slides, 'local')
        self.assertEqual(len(made['slides']), len(LONG_OUTLINE['slides']))

    def test_a_kept_section_repaired_again_reaches_the_deck(self):
        self.built()
        state = build.read_state(self.root)
        state['repair'] = ['section-1']        # the first build's review sends it back
        build.write_state(self.root, state)
        self.draw('section-1')
        build.whole(self.root, self.run_, self.slides, 'local')
        outline = json.loads((self.root / 'outline.json').read_text(encoding='utf-8'))
        outline['slides'][6]['title'] = 'A failed batch goes back, never on'
        (self.root / 'outline.json').write_text(json.dumps(outline), encoding='utf-8')
        BY_ID['rolling-back'] = outline['slides'][6]
        build.start(self.root, self.run_, self.slides, self.contract)
        self.assertEqual(build.to_draw(self.root), ['section-2'])
        kept = build.read_state(self.root)['sections']['section-1']['file']
        self.assertTrue((self.root / kept).is_file())
        self.draw('section-2')
        build.whole(self.root, self.run_, self.slides, 'local')
        state = build.read_state(self.root)
        self.assertEqual(state['rounds'][-1]['made_from']['section-1'], kept)
        state['repair'] = ['section-1']        # the second build's review sends it back too
        build.write_state(self.root, state)
        self.assertEqual(build.to_draw(self.root), ['section-1'])
        self.draw('section-1')
        state = build.read_state(self.root)
        repaired = state['sections']['section-1']['file']
        # Drawn again, it is a new file, so the deck has to be put together again.
        self.assertNotEqual(repaired, kept)
        self.assertNotEqual(state['rounds'][-1]['made_from']['section-1'], repaired)
        self.assertTrue((self.root / kept).is_file())

    def test_nothing_is_kept_from_a_build_in_another_brand(self):
        self.built()
        self.assertTrue(build._earlier(self.root, self.contract)['drawn'])
        contract = json.loads(self.contract.read_text(encoding='utf-8'))
        contract['revision'] = 'another'
        self.contract.write_text(json.dumps(contract), encoding='utf-8')
        self.assertEqual(build._earlier(self.root, self.contract), {})

    def test_slide_notes_at_the_gate_reach_the_section_s_composer(self):
        self.built()
        run = copy.deepcopy(self.run_)
        run['gates']['gate:build'] = {'state': 'changes', 'note': 'Calmer.', 'slides': [2],
                                      'slide_notes': {'2': 'Give the batch more room.',
                                                      '6': 'Shorter claim.'}}
        work = build.section_work(self.root, run, 'section-1', None, None)
        self.assertIn('Slide 2: Give the batch more room.', work.task)
        self.assertNotIn('Shorter claim.', work.task)
        spec = work.prepared['artifacts']['section']
        self.assertEqual(sorted(spec['unchanged_slides']),
                         ['the-objection', 'when-capacity-holds'])



class DeliveryTests(unittest.TestCase):
    def test_one_delivery_for_the_export_the_looks_and_the_outline(self):
        self.assertEqual(build.delivery({'form': {'delivery': 'live'}}), 'live')
        self.assertEqual(build.delivery({'form': {'delivery': 'odd'}}), build.DELIVERY)
        self.assertEqual(build.delivery({}), build.DELIVERY)
