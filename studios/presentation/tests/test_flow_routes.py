"""Every route, end to end, through the runner's page: a deck from scratch (with research and
without), from a document (a finished script, and raw material the studio first took for a
script), and an existing deck at each level. Each is started, decided gate by gate and
delivered over the page's own addresses, with the engine behind it running over the
stand-ins and scripted workers of runner_support.

Each route is walked at every review level (route_stops.LEVELS): the gates it stopped at
are route_stops.STOPS for its case and level, the gates `stages.steps` gives its record
that the review policy did not continue, and every other gate carries the policy's
receipt. It is delivered as Google Slides through the stand-in Drive, with a link; its contact
sheet is committed; nothing under sources/ or work/ is tracked; and every decision is a
commit of its own. Nothing starts an agent, renders or leaves this computer.
"""
import json
import re
import unittest
from pathlib import Path

import route_stops
from test_runner_page import PageCase

from runner import decks, stages
from runner.steps import build, outline as outlines

DECK = b'PK\x03\x04' + b'stand-in deck'
SCRIPT = ('# Rolling restarts\n\n## A rolling restart replaces instances in batches\n\n'
          '- One batch at a time\n- The app keeps serving\n')


def gates_of(record: dict) -> list[str]:
    """The gates a deck with this record puts to the person, in order."""
    return [step.name for step in stages.steps(record)
            if step.kind == 'gate' and step.name != 'rehearse']


def read_in(inventory: dict) -> dict:
    """The outline an extract worker reads from the stand-in's deck: every slide kept, in
    order, every word the deck's own."""
    slides = []
    for slide in inventory['slides']:
        number, title = slide['number'], slide['title']
        texts = [' '.join(' '.join(item.get('runs') or ()).split())
                 for item in slide['objects']]
        texts = [text for text in texts if text and text != title]
        ident = f'slide-{number:02d}-read'
        if number == 1:
            slides.append({'id': ident, 'kind': 'cover', 'title': title,
                           **({'subtitle': texts[0]} if texts else {})})
        else:
            slides.append({'id': ident, 'kind': 'content', 'title': title,
                           'understand': f'What slide {number} of the deck says.',
                           'relation': 'none', 'points': [{'text': text} for text in texts],
                           'sources': [f'slide-{number}']})
    return {'version': 1, 'title': inventory['slides'][0]['title'], 'slides': slides}


class RouteCase(PageCase):
    review_level = 'step_by_step'

    def existing(self, level: str, **more) -> str:
        """An existing deck at `level`. The stand-in reads any deck it did not write as the
        same three slides, the last hidden; the scripted extract worker reads them word for
        word."""
        def extract(tools, job):
            # Under Balanced and Automatic draft the deck is read before the page has its
            # path back, so the inventory is read when the worker runs.
            if tools.job['artifacts']['outline'].get('rules'):
                kept = next(Path(self.space.repo).rglob(outlines.INVENTORY))
                said = read_in(json.loads(kept.read_text(encoding='utf-8')))
                self.workers.outline_said = said
                self.workers._ok(tools.submit_outline(json.dumps(said)))
            else:
                self.workers.outline(tools, job)
        self.workers.queued['outline'] = [extract] * 4
        path = self.started(route='existing', level=level, title='Old deck',
                            source={'kind': 'upload', 'name': 'old.pptx'},
                            uploads={'old.pptx': DECK}, **more)
        inventory = outlines.inventory_of(path)
        self.assertEqual([slide['number'] for slide in inventory['slides']], [1, 2, 3])
        return path

    def stops(self, case: str) -> list[str]:
        return route_stops.STOPS[case][self.review_level]

    def walk(self, path: str, title: str, decide=None) -> list[str]:
        """Decide every gate the deck puts to the person until it is finished: approve,
        unless `decide` gives what to send at a gate. Each decision is checked to be one
        commit of its own. Returns the gates, in the order they came up."""
        decide, seen = decide or {}, []
        said = re.compile(rf'^{re.escape(title)}: (approve|ask for changes to) the ')
        for _ in range(20):
            view = self.run_of(path)
            gate = view['gate']
            if gate is None:
                self.assertEqual(view['state'], 'finished', view['sentence'])
                return seen
            seen.append(gate['name'])
            head = self.git('rev-parse', 'HEAD')
            # A review that shows a version is decided on the version shown.
            shown = {'expected': gate['expected']} if gate.get('expected') else {}
            self.decided(path, gate['name'], **{**shown, **decide.get(gate['name'], {})})
            made = self.git('log', '--format=%s', f'{head}..HEAD').splitlines()
            self.assertEqual(len([line for line in made if said.match(line)]), 1,
                             (gate['name'], made))
        self.fail('The deck never stopped asking')

    def delivered(self, path: str, seen: list[str], sheet: bool = True) -> dict:
        """What every route ends with, whatever it is. `sheet` is False for a deck pictured
        by the slides tool's review of a whole file (the selected level), which makes its
        contact sheet as a web page rather than a picture: the page shows each slide's
        picture instead."""
        root = Path(path)
        record = self.record(root)
        by = {name: ((record.get('gates') or {}).get(name) or {}).get('by')
              for name in gates_of(record)}
        self.assertEqual(seen, [name for name in gates_of(record)
                                if by[name] != 'review-policy'], by)
        self.assertEqual({name for name in by if name not in seen},
                         {name for name in by if by[name] == 'review-policy'}, by)
        delivered = json.loads((root / decks.DELIVER).read_text())
        self.assertEqual(delivered['output'], 'google')
        self.assertTrue(delivered['url'].startswith('https://'), delivered)
        relative = root.relative_to(self.space.repo).as_posix()
        tracked = self.git('ls-files', relative).splitlines()
        if sheet:
            self.assertIn(f'{relative}/{build.SHEET}', tracked)
            self.assertTrue(self.engine.picture(root, 'build', 'contact-sheet')
                            .startswith(b'\x89PNG'))
        else:
            self.assertNotIn(f'{relative}/{build.SHEET}', tracked)
            self.assertTrue(self.engine.picture(root, 'build', 2).startswith(b'\x89PNG'))
        self.assertIn(f'{relative}/{decks.DELIVER}', tracked)
        self.assertEqual([name for name in tracked
                          if name.startswith((f'{relative}/sources/', f'{relative}/work/'))],
                         [])
        self.assertEqual(self.git('status', '--porcelain'), '')
        decisions = [line for line in self.log()
                     if line.startswith(f"{record['title']}: approve the ")]
        self.assertEqual(len(decisions), len(seen), decisions)
        return record


class ScratchRouteTests(RouteCase):
    def test_from_scratch_without_research(self):
        path = self.started()
        seen = self.walk(path, 'Rolling restarts')
        self.delivered(path, seen)
        self.assertEqual(seen, self.stops('scratch'))

    def test_from_scratch_with_research(self):
        path = self.started(research=True)
        seen = self.walk(path, 'Rolling restarts')
        self.delivered(path, seen)
        self.assertEqual(seen, self.stops('scratch-research'))
        self.assertTrue((Path(path) / 'research' / 'report.md').is_file())


class DocumentRouteTests(RouteCase):
    def test_a_finished_script(self):
        self.workers.classified = {'kind': 'spec', 'reason': 'Already a slide script.',
                                   'slides': 2}
        path = self.started(route='document', research=True,
                            source={'kind': 'upload', 'name': 'script.md'},
                            uploads={'script.md': SCRIPT.encode()})
        seen = self.walk(path, 'Rolling restarts')
        record = self.delivered(path, seen)
        self.assertEqual(record['classified'], 'spec')
        self.assertEqual(seen, self.stops('document-script'))
        self.assertEqual(self.workers.of('research-plan'), [])

class _MaterialRoute:
    """A document read as material to build from, researched first, at the case's level."""

    def test_material_to_build_from(self):
        path = self.started(route='document', research=True, research_sources='both',
                            source={'kind': 'paste', 'text': 'Notes: capacity holds with two.'})
        seen = self.walk(path, 'Rolling restarts')
        record = self.delivered(path, seen)
        self.assertEqual(record['classified'], 'material')
        self.assertEqual(seen, self.stops('document-material'))


DocumentRouteTests.test_material_to_build_from = _MaterialRoute.test_material_to_build_from


class ExistingRouteTests(RouteCase):
    """An existing deck at each level. The stand-in reads any deck it did not write as the
    same three slides, the last hidden; the scripted extract worker reads them word for
    word."""

    def through(self, level: str, **more) -> dict:
        path = self.existing(level, **more)
        seen = self.walk(path, 'Old deck')
        record = self.delivered(path, seen, sheet=level != 'selected')
        self.assertEqual(seen, self.stops(level))
        original = Path(path) / 'sources' / 'original.pptx'
        self.assertEqual(original.read_bytes(), DECK)
        return record

    def test_brand_only(self):
        self.through('brand-only')

    def test_polish(self):
        self.through('polish')

    def test_redesign(self):
        self.through('redesign')

    def test_rework(self):
        self.through('rework')

    def test_selected(self):
        def patch(tools, job):
            spec = tools.job['artifacts']['patch']
            key, digest = next((key, digest) for key, digest in spec['objects'].items()
                               if key.startswith('2:') and key != '2:2')
            plan = {'sourceSha256': spec['sha256'], 'operations': [
                {'slide': 2, 'object': key.partition(':')[2], 'expectedHash': digest,
                 'runs': [{'index': 1, 'text': 'in minutes.'}]}]}
            self.workers._ok(tools.submit_artifact('patch', json.dumps(plan)))

        self.workers.then('patch', patch)
        self.through('selected', selected='Shorten the words on slide 2')
        self.assertEqual(len(self.workers.of('patch')), 1)


class StepByStepCorrectionTests(RouteCase):
    """Corrections that decide at gate:classify and gate:build: run once, at Step by step."""

    def test_raw_material_the_studio_took_for_a_script_is_corrected(self):
        self.workers.classified = {'kind': 'spec', 'reason': 'Reads as a slide script.',
                                   'slides': 2}
        path = self.started(route='document', research=True, research_sources='both',
                            source={'kind': 'paste', 'text': 'Notes: capacity holds with two.'})
        self.assertEqual(self.run_of(path)['gate']['verdict'], 'spec')
        seen = self.walk(path, 'Rolling restarts',
                         {'gate:classify': {'extra': {'kind': 'material'}}})
        record = self.delivered(path, seen)
        self.assertEqual(record['classified'], 'material')
        self.assertEqual(seen, ['gate:classify', 'gate:research-plan', 'gate:research',
                                'gate:outline', 'gate:look', 'gate:build'])

    def test_selected_with_a_slide_asked_for_at_the_deck(self):
        def patch(number):
            def act(tools, job):
                spec = tools.job['artifacts']['patch']
                key, digest = next((key, digest) for key, digest in spec['objects'].items()
                                   if key.startswith(f'{number}:') and key != f'{number}:2')
                plan = {'sourceSha256': spec['sha256'], 'operations': [
                    {'slide': number, 'object': key.partition(':')[2], 'expectedHash': digest,
                     'runs': [{'index': 0, 'text': 'Shorter.'}]}]}
                self.workers._ok(tools.submit_artifact('patch', json.dumps(plan)))
            return act

        self.workers.then('patch', patch(2), patch(1))
        path = self.existing('selected', selected='Shorten the words on slide 2')
        self.decided(path, 'gate:classify')
        view = self.run_of(path)
        self.assertEqual((view['gate'] or {}).get('name'), 'gate:build', view['sentence'])
        self.decided(path, 'gate:build', 'changes', note='Shorten slide 1 as well.',
                     extra={'slides': [1]})
        view = self.run_of(path)
        self.assertEqual((view['gate'] or {}).get('name'), 'gate:build', view['sentence'])
        patches = [spec['artifacts']['patch'] for kind, job, spec in self.workers.jobs
                   if kind == 'patch']
        self.assertEqual([spec['named'] for spec in patches], [[2], [2, 1]])
        self.assertEqual(self.walk(path, 'Old deck'), ['gate:build'])
        self.delivered(path, ['gate:classify', 'gate:build'], sheet=False)


class BalancedScratchRouteTests(ScratchRouteTests):
    review_level = 'balanced'


class AutomaticScratchRouteTests(ScratchRouteTests):
    review_level = 'automatic'


class BalancedDocumentRouteTests(DocumentRouteTests):
    review_level = 'balanced'


class AutomaticDocumentRouteTests(DocumentRouteTests):
    review_level = 'automatic'


class BalancedExistingRouteTests(ExistingRouteTests):
    review_level = 'balanced'


class AutomaticExistingRouteTests(ExistingRouteTests):
    review_level = 'automatic'


if __name__ == '__main__':
    unittest.main()
