"""Every route, end to end, through the runner's page: a deck started from the desk's start
(DeskRouteTests, DeskExistingRouteTests) is walked to its first delivery, over the page's own
addresses, with the engine behind it running over the stand-ins and scripted workers of
runner_support. It reads no review level, and its only decisions that are the person's are
the look, where its start chose to pick it, and Deliver. Nothing starts an agent, renders or
leaves this computer. (The earlier step-by-step flow's walks, gate by gate at each review
level, went with that flow: GitHub issue #542.)
"""
import json
import re
import unittest
from pathlib import Path

from test_runner_page import PageCase

from runner import decks, stages
from runner.steps import build, outline as outlines

DECK = b'PK\x03\x04' + b'stand-in deck'
SCRIPT = ('# Rolling restarts\n\n## A rolling restart replaces instances in batches\n\n'
          '- One batch at a time\n- The app keeps serving\n')


def gates_of(record: dict) -> list[str]:
    """The gates a deck with this record puts to the person, in order."""
    return [step.name for step in stages.steps(record)
            if step.kind == 'gate']


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




class DeskRouteTests(RouteCase):
    """Every route a desk deck takes from the desk's start to its first delivery, through the
    page's own addresses. The only decisions that are the person's are the look, where the
    start chose to pick it, and Deliver; every other stop is continued with the desk's
    receipt, at whatever level the shared settings hold."""

    review_level = 'automatic'   # a desk deck never reads it

    def setUp(self):
        super().setUp()
        self.brand.run.offers_looks = True
        self.brand.run.guides = True

    def desk(self, **changes) -> str:
        return self.started(flow='desk', **changes)

    def to_delivery(self, path: str) -> list[str]:
        """Pick the look when the deck pauses for it, then Deliver the deck on screen.
        Returns what the person did, in order."""
        did = []
        for _ in range(6):
            view = self.run_of(path)
            gate = view['gate']
            if gate is None:
                self.assertEqual(view['state'], 'finished', view['sentence'])
                return did
            if gate['name'] == 'gate:look':
                did.append('look')
                self.post('desk-look', {'path': path,
                                        'look': gate['offered']['looks'][0]['id']})
            else:
                self.assertEqual(gate['name'], 'gate:build', view['sentence'])
                shown = self.at_desk = view['desk']
                did.append('deliver')
                self.post('desk-deliver', {'path': path, 'expected': shown['expected'],
                                           **({'blockers_seen': shown['blockers_seen']}
                                              if shown['blockers'] else {})})
        self.fail('The deck never finished')

    def finished(self, path: str, did: list[str], sheet: bool = True) -> dict:
        """`sheet` is False for a deck pictured by the slides tool's review of a whole file
        (Selected changes), as RouteCase.delivered says."""
        root = Path(path)
        record = self.record(root)
        person = self.gitstate.identity(self.space.repo)
        by = {name: ((record.get('gates') or {}).get(name) or {}).get('by')
              for name in gates_of(record)}
        theirs = ['gate:look'] if 'look' in did else []
        self.assertEqual([name for name in by if by[name] == person], [*theirs, 'gate:build'],
                         by)
        self.assertEqual({by[name] for name in by if name not in (*theirs, 'gate:build')},
                         {'desk'} if len(by) > len(theirs) + 1 else set(), by)
        self.assertEqual({event['by'] for event in record.get('review_events') or ()},
                         {'desk'} if record.get('review_events') else set())
        self.assertNotIn('review_policy', record)
        delivered = json.loads((root / decks.DELIVER).read_text())
        # A deck drawn here is reviewed by itself before it reaches the desk; your own deck at
        # Selected changes is not drawn here, and is not reviewed.
        reviewed = 'build-review' in {step.name for step in stages.steps(record)}
        self.assertEqual((delivered['revision'], delivered['review_status']),
                         (1, 'reviewed' if reviewed else 'unreviewed'))
        self.assertTrue(delivered['url'].startswith('https://'), delivered)
        relative = root.relative_to(self.space.repo).as_posix()
        tracked = self.git('ls-files', relative).splitlines()
        if sheet:
            self.assertIn(f'{relative}/{build.SHEET}', tracked)
        self.assertEqual([name for name in tracked
                          if name.startswith((f'{relative}/sources/', f'{relative}/work/'))], [])
        self.assertEqual(self.git('status', '--porcelain'), '')
        return record

    def test_an_idea_without_research(self):
        path = self.desk(look='pick')
        did = self.to_delivery(path)
        self.assertEqual(did, ['look', 'deliver'])
        self.finished(path, did)

    def test_an_idea_with_research_from_the_web(self):
        path = self.desk(look='pick', research=True)
        did = self.to_delivery(path)
        record = self.finished(path, did)
        self.assertEqual(did, ['look', 'deliver'])
        self.assertTrue((Path(path) / 'research' / 'report.md').is_file())
        self.assertEqual((record['gates']['gate:research-plan']['by'],
                          record['gates']['gate:research']['by']), ('desk', 'desk'))

    def test_a_document_read_as_a_script(self):
        path = self.desk(look='pick', route='document', reading='spec',
                         source={'kind': 'upload', 'name': 'script.md'},
                         uploads={'script.md': SCRIPT.encode()})
        did = self.to_delivery(path)
        record = self.finished(path, did)
        self.assertEqual(record['classified'], 'spec')
        self.assertEqual(self.workers.of('classification'), [])

    def test_a_document_left_to_its_classify_job(self):
        # The scripted research worker saves a page from the public web.
        path = self.desk(look='pick', route='document', research=True,
                         research_from={'documents': True, 'sites': [], 'web': True},
                         source={'kind': 'paste', 'text': 'Notes: capacity holds with two.'})
        did = self.to_delivery(path)
        record = self.finished(path, did)
        self.assertEqual(record['classified'], 'material')
        self.assertEqual(len(self.workers.of('classification')), 1)
        self.assertEqual(record['gates']['gate:classify']['by'], 'desk')

    def test_the_default_look_with_no_pause(self):
        path = self.desk(look='default')
        did = self.to_delivery(path)
        self.assertEqual(did, ['deliver'])
        record = self.finished(path, did)
        self.assertEqual(record['gates']['gate:look']['by'], 'desk')


class DeskExistingRouteTests(RouteCase):
    """An existing deck started from the desk's start, at each of its five levels, through
    the page's own addresses to its first delivery. The only decisions that are the person's
    are the look, at Redesign and Full rework where the start chose to pick it, and Deliver.
    Each card shows the slide as it was in the deck given, at every level whose slides are the
    deck's own (existing.PAIRED), and the original is never changed."""

    review_level = 'automatic'   # a desk deck never reads it

    def setUp(self):
        super().setUp()
        self.brand.run.offers_looks = True
        self.brand.run.guides = True

    def through(self, level: str, look: str = 'pick', **more) -> dict:
        from runner.steps import existing
        path = self.existing(level, flow='desk', look=look, **more)
        did = DeskRouteTests.to_delivery(self, path)
        picks = level in ('redesign', 'rework') and look == 'pick'
        self.assertEqual(did, ['look', 'deliver'] if picks else ['deliver'])
        record = DeskRouteTests.finished(self, path, did, sheet=level != 'selected')
        self.assertEqual(record['gates']['gate:classify']['by'], 'desk')
        cards = [card for part in self.at_desk['sections'] for card in part['slides']]
        self.assertTrue(cards)
        for card in cards:
            if level in existing.PAIRED:
                self.assertEqual(card['before'], {'kind': 'original', 'ref': card['number']},
                                 card)
                self.assertTrue(self.engine.picture(path, 'original', card['number'])
                                .startswith(b'\x89PNG'))
            else:
                self.assertIsNone(card['before'], card)
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
        # The brand's default look, chosen at the start: no pause at all.
        record = self.through('rework', look='default')
        self.assertEqual(record['gates']['gate:look']['by'], 'desk')
        self.assertEqual(record['gates']['gate:outline']['by'], 'desk')

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
        record = self.through('selected', selected='Shorten the words on slide 2')
        self.assertEqual(len(self.workers.of('patch')), 1)
        self.assertNotIn('initial_review', record['form'])


if __name__ == '__main__':
    unittest.main()
