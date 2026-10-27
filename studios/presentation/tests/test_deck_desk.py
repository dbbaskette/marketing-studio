"""The deck desk: a deck started from the desk's start runs the same pipeline as any other,
with its stops met on the desk, and rests at gate:build, which is the desk itself.

Every test runs the engine over the stand-ins, with scripted workers, a disposable data
folder, workspace and git identity. Nothing real is started.
"""
import json
import unittest
from pathlib import Path
from unittest import mock

import runner_support
from runner_support import LONG_OUTLINE, DeskCase
from stand_ins import brand as brand_stand_in
from workspace import WorkspaceError

from runner import desk
from runner.steps import look as looks


class DeskGateTests(DeskCase):
    """The stops a desk deck passes on its way to the desk, each with a desk receipt."""

    def test_a_desk_deck_from_an_idea_reaches_the_desk_after_one_look_pick(self):
        root = self.start_desk(look='pick')
        self.assertEqual(self.waiting(root), 'gate:look')
        record = self.record(root)
        # Nothing waited before the look.
        self.assertEqual([name for name, gate in record['gates'].items()
                          if gate.get('state') == 'waiting'], ['gate:look'])
        self.pick_look(root)
        self.assertEqual(self.waiting(root), 'gate:build')
        record = self.record(root)
        self.assertEqual(record['gates']['gate:outline']['by'], 'desk')
        events = [event for event in record['review_events'] if event['gate'] == 'gate:outline']
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]['by'], events[0]['decision']),
                         ('desk', 'continued-on-the-desk'))
        person = self.gitstate.identity(self.space.repo)
        self.assertFalse([event for event in record['review_events']
                          if event.get('by') == person])
        self.on_desk(root)

    def test_the_default_look_is_chosen_with_the_start_s_words(self):
        root = self.start_desk(look='default')
        self.assertEqual(self.waiting(root), 'gate:build')
        name = next(look['name'] for look in brand_stand_in.DIRECTIONS
                    if look['id'] == brand_stand_in.DEFAULT_LOOK)
        self.assertEqual(looks.chosen(root)['words'],
                         f"You chose the brand's default look at the start: {name}.")
        record = self.record(root)
        self.assertEqual(record['gates']['gate:look']['by'], 'desk')
        approval = json.loads((root / 'outline.json').read_text())['approval']
        self.assertTrue(approval[0].startswith('Continued on the desk, '), approval)
        self.on_desk(root)

    def test_a_desk_deck_keeps_no_review_level(self):
        import studios_config
        before = studios_config.read() if hasattr(studios_config, 'read') else None
        root = self.start_desk(look='default', review_level='automatic', review_default=True)
        record = self.record(root)
        self.assertNotIn('review_policy', record)
        self.assertEqual(record['schema'], 1)
        after = studios_config.read() if hasattr(studios_config, 'read') else None
        self.assertEqual(before, after)

    def test_a_document_read_at_the_start_runs_no_classify_job(self):
        root = self.start_desk(look='default', route='document', reading='material',
                               source={'kind': 'paste', 'text': 'Notes on rolling restarts.'})
        self.assertEqual(self.workers.of('classification'), [])
        record = self.record(root)
        self.assertEqual(record['classified'], 'material')
        self.assertIn('You said at the start it is material to build from.',
                      (root / 'classify.md').read_text())
        self.assertEqual(record['gates']['gate:classify']['by'], 'desk')
        self.on_desk(root)

    def test_a_document_left_unread_is_classified_by_its_job(self):
        root = self.start_desk(look='default', route='document',
                               source={'kind': 'paste', 'text': 'Notes on rolling restarts.'})
        self.assertEqual(len(self.workers.of('classification')), 1)
        self.assertEqual(self.record(root)['gates']['gate:classify']['by'], 'desk')
        self.on_desk(root)

    def test_research_on_a_desk_deck_plans_from_the_form(self):
        from studio_core import research_contract

        from runner import research_steps
        contract = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        with mock.patch.object(self.engines.research_contract, 'snapshot',
                               return_value=contract), \
                mock.patch.object(research_steps.research_contract, 'native',
                                  side_effect=WorkspaceError('Stopped here for the test.')):
            root = self.start_desk(look='default', research=True,
                                   research_questions=['What starts the next batch?'])
        self.assertEqual(self.workers.of('research-plan'), [])
        record = self.record(root)
        self.assertEqual(record['research']['plan_from'], 'form')
        plan = json.loads((root / 'research/plan.json').read_text())
        self.assertEqual([item['question'] for item in plan['items']],
                         ['What starts the next batch?'])
        # Where its research may look is the form's: the public web, for an idea.
        self.assertEqual(plan['scope'], 'public-web')
        self.assertTrue(research_contract)

    def test_a_gated_deck_still_stops_at_every_gate(self):
        root = self.start()
        self.assertEqual(self.waiting(root), 'gate:outline')
        self.assertNotIn('flow', self.record(root))


class DeskRefusalTests(DeskCase):
    """A desk deck is changed only on the desk, and a gated deck only on its own screen."""

    # Each desk route, with what it is sent, by name.
    ROUTES = (('desk_note', (3, 'Shorter.', 'x')), ('desk_deck_note', ('Shorter.', 'x')),
              ('desk_stop', ()), ('desk_deliver', ('x',)), ('desk_outline', ([], 'x')),
              ('desk_outline_price', (None,)), ('desk_reread', ('spec',)),
              ('desk_look', ('example-clear',)), ('desk_look_again', ()),
              ('desk_draw_here', ()))

    def test_a_desk_deck_refuses_a_gate_decision(self):
        root = self.start_desk(look='default')
        self.on_desk(root)
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.decide(root, 'gate:build', 'changes', 'Shorter.')
        self.assertEqual(str(caught.exception), desk.ON_DESK)
        expected = self.view(root)['gate']['expected_deck']
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.review_draft(root, expected)
        self.assertEqual(str(caught.exception), desk.ON_DESK)
        self.assertEqual(self.waiting(root), 'gate:build')

    def test_build_feedback_still_works_while_a_desk_deck_is_drawn(self):
        taken = []

        def noting(tools, job):
            root = next(self.space.repo.rglob('run.json')).parent
            taken.append(self.engine.build_feedback(root, 'a' * 32, 'Name the batch size.',
                                                    number=3))
            return self.workers.section(tools, job)

        self.workers.then('section', noting)
        root = self.start_desk(look='default')
        self.assertEqual(len(taken), 1)
        self.on_desk(root)
        # The note came after its section was drawn: on the desk it is drawn, once.
        record = self.record(root)
        self.assertEqual([(item['number'], item['note'], item['status'])
                          for item in record['desk_notes']],
                         [(3, 'Name the batch size.', 'done')])
        told = [job.task for job in self.workers.of('section')
                if 'Slide 3: Name the batch size.' in job.task]
        self.assertEqual(len(told), 1)

    def test_a_gated_deck_refuses_every_desk_route(self):
        root = self.gated()
        for name, given in self.ROUTES:
            with self.subTest(route=name):
                with self.assertRaises(WorkspaceError) as caught:
                    getattr(self.engine, name)(root, *given)
                self.assertEqual(str(caught.exception), desk.NOT_ON_DESK)
        self.assertEqual(self.waiting(root), 'gate:build')


BLOCKED = {'status': 'BLOCKED', 'warnings': [],
           'blockers': [{'slide': 3, 'says': 'Text runs off the slide.', 'code': 'OUT_OF_BOUNDS'}]}


class DeskViewTests(DeskCase):
    """The desk shows a card per slide, under the sections the deck was split into."""

    def test_every_slide_has_a_card_in_its_section_in_deck_order(self):
        root = self.start_desk(look='default')
        shown = self.on_desk(root)['desk']
        self.assertTrue(shown['drawn_here'])
        self.assertTrue(shown['arrived'])
        cards = [card for part in shown['sections'] for card in part['slides']]
        self.assertEqual([card['number'] for card in cards], list(range(1, 9)))
        self.assertEqual([(part['lead'], part['number'], [card['number'] for card in part['slides']])
                          for part in shown['sections']],
                         [(True, None, [1]), (False, 1, [2, 3, 4]), (False, 2, [5, 6, 7]),
                          (True, None, [8])])
        for card in cards:
            self.assertEqual(card['image'], {'kind': 'build', 'ref': card['number']})
        lead = cards[0]
        self.assertTrue(lead['lead'])
        self.assertEqual((lead['price'], lead['section']), ('', None))
        self.assertEqual(cards[2]['section'], 'section-1')
        last = self.engine._load(root)
        from runner.steps import build
        self.assertEqual(shown['expected'], build.read_state(root)['rounds'][-1]['deck'])
        self.assertTrue(last)

    def test_a_card_shows_its_words_and_notes_from_the_outline(self):
        root = self.start_desk(look='default')
        card = self.on_desk(root)['desk']['sections'][1]['slides'][0]
        slide = LONG_OUTLINE['slides'][1]
        self.assertEqual((card['number'], card['id']), (2, slide['id']))
        self.assertEqual(card['words']['title'], slide['title'])
        self.assertEqual(card['words']['points'], slide['points'])
        self.assertEqual(card['words']['source'], slide['source'])
        self.assertEqual(card['notes'], slide['notes'])

    def test_a_blocker_shows_on_its_slide(self):
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            root = self.start_desk(look='default')
        shown = self.on_desk(root)['desk']
        card = shown['sections'][1]['slides'][1]
        self.assertEqual(card['number'], 3)
        self.assertIn({'says': 'Text runs off the slide.', 'kind': 'error'}, card['audit'])
        self.assertEqual(shown['blockers'], [{'number': 3, 'says': 'Text runs off the slide.'}])
        self.assertEqual(shown['sections'][1]['slides'][0]['audit'], [])

    def test_progress_says_how_long_from_what_the_steps_took_here(self):
        seen = []

        def looking(tools, job):
            root = next(path for path in self.engine.every()
                        if not self.record(path).get('desk'))
            seen.append(self.view(root)['desk']['progress'])
            return self.workers.outline(tools, job)

        self.workers.then('outline', looking, looking)
        first = self.start_desk(look='default')
        self.on_desk(first)
        self.assertIsNone(self.desk_view(first)['progress'])
        self.start_desk(look='default', title='Health checks')
        self.assertIsNone(seen[0]['minutes_left'], 'nothing was recorded here yet')
        self.assertGreaterEqual(seen[1]['minutes_left'], 1)
        self.assertTrue(seen[1]['started_at'])

    def test_a_gated_deck_has_no_desk_view(self):
        root = self.start()
        self.assertIsNone(self.view(root)['desk'])

    def test_notes_sent_while_drawing_are_not_sent_again_after_arrival(self):
        sent = []

        def noting(tools, job):
            self.workers.section(tools, job)
            root = self.engine.every()[0]
            slide = self.engine.view(root)['build_progress']['slides'][0]
            sent.append(slide)
            self.engine.build_feedback(root, slide['ref'], 'Move the label beside its line.')
            # The worker that was told to draw it before the note hands in nothing more.
            import home
            home.write_json(tools.folder / 'accepted/artifacts.json', {})

        self.workers.then('section', noting)
        root = self.start_desk(look='default')
        self.on_desk(root)
        record = self.record(root)
        self.assertEqual(record['build_feedback'], [])
        self.assertEqual([item['note'] for item in record['build_feedback_done']],
                         ['Move the label beside its line.'])
        self.assertFalse(record.get('desk_notes'))
        told = [job for job in self.workers.of('section') if 'Move the label' in job.task]
        self.assertEqual(len(told), 1)


def digests(root: Path) -> dict:
    """Every drawn section file and every slide picture of this computer's last round, by
    name, as SHA-256."""
    import hashlib

    from runner.steps import build
    state = build.read_state(root)
    found = {f"file:{ident}": hashlib.sha256((root / entry['file']).read_bytes()).hexdigest()
             for ident, entry in state['sections'].items()}
    found.update({f'path:{ident}': entry['file'] for ident, entry in state['sections'].items()})
    for slide in state['rounds'][-1]['slides']:
        found[f"slide:{slide['number']}"] = slide['sha256']
    return found


class SlideNoteTests(DeskCase):
    """A note on a slide redraws only that slide's section, and is sent to its composer
    once."""

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def expected(self, root: Path) -> str:
        return self.desk_view(root)['expected']

    def drawn(self) -> int:
        return len(self.workers.of('section'))

    def test_a_slide_note_redraws_its_section_and_keeps_the_rest_byte_for_byte(self):
        root = self.deck()
        before, jobs = digests(root), len(self.workers.jobs)
        self.engine.desk_note(root, 3, 'Make the diagram a sequence.', self.expected(root))
        again = self.workers.jobs[jobs:]
        self.assertEqual([kind for kind, _, _ in again], ['section'])
        _, job, spec = again[0]
        self.assertIn('Draw section 1 of', job.task)
        self.assertIn('Slide 3: Make the diagram a sequence.', job.task)
        unchanged = spec['artifacts']['section']['unchanged_slides']
        self.assertEqual(sorted(unchanged), sorted([LONG_OUTLINE['slides'][1]['id'],
                                                    LONG_OUTLINE['slides'][3]['id']]))
        after = digests(root)
        self.assertEqual(after['file:section-2'], before['file:section-2'])
        self.assertEqual(after['path:section-2'], before['path:section-2'])
        self.assertNotEqual(after['path:section-1'], before['path:section-1'])
        for number in (1, 5, 6, 7, 8):
            self.assertEqual(after[f'slide:{number}'], before[f'slide:{number}'])
        self.on_desk(root)
        notes = self.record(root)['desk_notes']
        self.assertEqual([(item['number'], item['section'], item['status']) for item in notes],
                         [(3, 'section-1', 'done')])

    def test_a_later_redraw_does_not_send_an_old_note_again(self):
        root = self.deck()
        self.engine.desk_note(root, 3, 'Make the diagram a sequence.', self.expected(root))
        jobs = self.drawn()
        self.engine.desk_note(root, 6, 'Give the rollback its own row.', self.expected(root))
        (job,) = self.workers.of('section')[jobs:]
        self.assertIn('Draw section 2 of', job.task)
        self.assertIn('Slide 6: Give the rollback its own row.', job.task)
        self.assertNotIn('Slide 3:', job.task)

    def test_notes_on_two_sections_are_drawn_in_one_chain(self):
        root = self.deck()
        said = []

        def noting(tools, job):
            said.append(self.engine.desk_note(root, 6, 'Give the rollback its own row.',
                                              self.expected(root)))
            return self.workers.section(tools, job)

        self.workers.then('section', noting)
        jobs = self.drawn()
        put = self.log().count('Rolling restarts: the deck is put together')
        self.engine.desk_note(root, 3, 'Make the diagram a sequence.', self.expected(root))
        tasks = [job.task for job in self.workers.of('section')[jobs:]]
        self.assertEqual(len(tasks), 2)
        self.assertIn('Slide 3: Make the diagram a sequence.', tasks[0])
        self.assertIn('Slide 6: Give the rollback its own row.', tasks[1])
        self.assertEqual(self.log().count('Rolling restarts: the deck is put together'), put + 1)
        self.on_desk(root)
        self.assertEqual({item['status'] for item in self.record(root)['desk_notes']}, {'done'})

    def test_a_note_on_a_slide_being_redrawn_is_refused(self):
        root = self.deck()
        refused = []

        def noting(tools, job):
            with self.assertRaises(WorkspaceError) as caught:
                self.engine.desk_note(root, 4, 'Shorter.', self.expected(root))
            refused.append(str(caught.exception))
            return self.workers.section(tools, job)

        self.workers.then('section', noting)
        self.engine.desk_note(root, 3, 'Make the diagram a sequence.', self.expected(root))
        self.assertEqual(refused, [desk.BUSY.format(number=4)])

    def test_a_note_on_a_lead_slide_is_refused(self):
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_note(root, 1, 'Bigger title.', self.expected(root))
        self.assertEqual(str(caught.exception), desk.LEAD)
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_note(root, 99, 'Nowhere.', self.expected(root))
        self.assertEqual(str(caught.exception), 'The deck has no slide 99.')

    def test_a_note_against_an_old_deck_is_refused(self):
        root = self.deck()
        jobs = self.drawn()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_note(root, 3, 'Make the diagram a sequence.', '0' * 64)
        self.assertEqual(str(caught.exception), desk.CHANGED)
        self.assertEqual(self.drawn(), jobs)
        self.assertFalse(self.record(root).get('desk_notes'))


class PriceTests(DeskCase):
    """Every redraw on the desk says first what it last took on this computer."""

    def card(self, root: Path, number: int) -> dict:
        return next(card for part in self.desk_view(root)['sections'] for card in part['slides']
                    if card['number'] == number)

    def test_the_slides_of_a_section_are_said_as_a_person_says_them(self):
        self.assertEqual(desk.slides_words([4]), 'slide 4')
        self.assertEqual(desk.slides_words([4, 5]), 'slides 4 and 5')
        self.assertEqual(desk.slides_words([4, 5, 6]), 'slides 4 to 6')
        self.assertEqual(desk.slides_words([2, 4, 6]), 'slides 2, 4 and 6')

    def test_a_slide_note_is_priced_from_its_section_s_last_try(self):
        self.workers.cost = 0.31
        root = self.start_desk(look='default')
        price = self.card(root, 3)['price']
        self.assertTrue(price.startswith('Redraws section 1 (slides 2 to 4); the other slides '
                                         'stay exactly as they are.'), price)
        self.assertIn('Last time this took', price)
        self.assertIn('about $0.31', price)
        self.assertEqual(self.card(root, 1)['price'], '')

    def test_a_cost_nobody_reported_is_never_zero_dollars(self):
        root = self.start_desk(look='default')
        price = self.card(root, 3)['price']
        self.assertIn('the assistant reported no cost', price)
        self.assertNotIn('$0.00', price)

    def test_a_section_never_drawn_here_says_there_is_no_record(self):
        root = self.start_desk(look='default')
        record = self.engine._load(root)
        record['steps'].pop('build-sections:section-1')
        self.engine._store(root, record)
        self.assertTrue(self.card(root, 3)['price'].endswith('Expect minutes, not seconds.'))

    def test_a_kept_slide_note_says_how_long_it_usually_takes_here(self):
        root = self.start_desk(look='default')
        self.assertNotIn('Usually about', self.card(root, 3)['price'])
        self.engine.desk_note(root, 3, 'Make the diagram a sequence.',
                              self.desk_view(root)['expected'])
        self.assertIn(' Usually about 1 minute here.', self.card(root, 3)['price'])

    def test_the_whole_deck_price_counts_every_section(self):
        from studio_core import stops
        root = self.start_desk(look='default')
        said = self.desk_view(root)['deck_price']
        last = self.engine._last_build(self.record(root))
        self.assertTrue(said.startswith('Redraws every section.'), said)
        self.assertIn(stops.lasted(last['seconds']), said)


def section_of_job(tools) -> int:
    return int(tools.job['artifacts']['section']['prefix'].strip('s_'))


class DeckNoteTests(DeskCase):
    """One note for the whole deck redraws every section, three at a time, with Stop."""

    NOTE = 'Use fewer words on every slide.'

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def kept_now(self, root: Path, section: str) -> bool:
        from runner.steps import build
        state = build.read_state(root)
        entry = state['sections'].get(section) or {}
        return entry.get('round', -1) >= len(state['rounds'])

    def wait_for(self, check, seconds: float = 20) -> None:
        import time
        deadline = time.monotonic() + seconds
        while not check():
            if time.monotonic() > deadline:
                self.fail('It never happened.')
            time.sleep(0.02)

    def test_a_whole_deck_note_redraws_every_section_and_says_how_far_it_is(self):
        root = self.deck()
        seen = []

        def second(tools, job):
            if section_of_job(tools) == 2:
                self.wait_for(lambda: self.kept_now(root, 'section-1'))
                seen.append(self.desk_view(root)['working'])
            return self.workers.section(tools, job)

        self.workers.then('section', second, second)
        jobs = len(self.workers.of('section'))
        self.engine.desk_deck_note(root, self.NOTE, self.desk_view(root)['expected'])
        self.assertEqual(seen, [{'what': 'Redrawing: 1 of 2 sections', 'done': 1, 'total': 2}])
        tasks = [job.task for job in self.workers.of('section')[jobs:]]
        self.assertEqual(len(tasks), 2)
        for task in tasks:
            self.assertIn(self.NOTE, task)
            self.assertNotIn('Copy all other slides', task)
        shown = self.on_desk(root)['desk']
        self.assertIsNone(shown['working'])
        self.assertEqual({item['status'] for item in self.record(root)['desk_notes']}, {'done'})

    def test_one_section_redrawn_says_which(self):
        root = self.deck()
        seen = []

        def looking(tools, job):
            seen.append(self.desk_view(root)['working'])
            return self.workers.section(tools, job)

        self.workers.then('section', looking)
        self.engine.desk_note(root, 6, 'Give the rollback its own row.',
                              self.desk_view(root)['expected'])
        self.assertEqual(seen, [{'what': 'Redrawing section 2 (slides 5 to 7)', 'done': 0,
                                 'total': 1}])

    def test_stop_keeps_what_was_redrawn_and_sets_the_rest_aside(self):
        import threading
        root = self.deck()
        before = digests(root)
        stopped = []

        def second(tools, job):
            if section_of_job(tools) == 2:
                self.wait_for(lambda: self.kept_now(root, 'section-1'))
                stopping = threading.Thread(target=lambda: stopped.append(
                    self.engine.desk_stop(root)))
                stopping.start()
                self.wait_for(lambda: (self.engine._load(root).get('halted') or {}).get(
                    'state') == 'stopped')
                stopped.append(stopping)
                return None
            return self.workers.section(tools, job)

        self.workers.then('section', second, second)
        self.engine.desk_deck_note(root, self.NOTE, self.desk_view(root)['expected'])
        stopped[0].join(30)
        self.on_desk(root)
        after = digests(root)
        self.assertNotEqual(after['path:section-1'], before['path:section-1'])
        self.assertEqual((after['path:section-2'], after['file:section-2']),
                         (before['path:section-2'], before['file:section-2']))
        shown = self.desk_view(root)
        cards = {card['number']: card for part in shown['sections'] for card in part['slides']}
        for number in (5, 6, 7):
            self.assertEqual(cards[number]['note']['status'], 'set aside')
            self.assertEqual(cards[number]['note']['says'], desk.SET_ASIDE)
        self.assertEqual(cards[3]['note']['status'], 'done')
        self.assertIsNone(self.record(root)['halted'])
        self.assertIn('Rolling restarts: stop the whole-deck note', self.log())

    def test_a_section_that_fails_leaves_the_others_done(self):
        root = self.deck()

        def failing(tools, job):
            if section_of_job(tools) == 2:
                return runner_support.fails()(tools, job)
            return self.workers.section(tools, job)

        self.workers.then('section', *[failing] * 8)
        self.engine.desk_deck_note(root, self.NOTE, self.desk_view(root)['expected'])
        shown = self.view(root)
        self.assertIn('Draw section 2', shown['problem']['why'])
        self.assertTrue(self.kept_now(root, 'section-1'))
        notes = {item['section']: item['status'] for item in self.record(root)['desk_notes']}
        self.assertEqual(notes, {'section-1': 'done', 'section-2': 'drawing'})


class OutlineTabTests(DeskCase):
    """The Outline tab: the outline saved, the document read the other way, the look."""

    def deck(self, **changes) -> Path:
        root = self.start_desk(**{'look': 'default', **changes})
        self.on_desk(root)
        return root

    def edited(self, root: Path, number: int, **words) -> list:
        slides = json.loads(json.dumps(self.desk_view(root)['outline']['slides']))
        slides[number - 1].update(words)
        return slides

    def test_editing_one_slide_s_words_redraws_only_its_section(self):
        root = self.deck()
        slides = self.edited(root, 3, title='Capacity holds with two or more instances')
        self.workers.outline_said = {**LONG_OUTLINE, 'slides': slides}
        jobs = len(self.workers.of('section'))
        self.engine.desk_outline(root, slides, self.desk_view(root)['outline']['expected'])
        again = self.workers.of('section')[jobs:]
        self.assertEqual(len(again), 1)
        self.assertIn('Draw section 1 of', again[0].task)
        from runner.steps import build
        self.assertIn('-kept-', build.read_state(root)['sections']['section-2']['file'])
        self.on_desk(root)
        outline = json.loads((root / 'outline.json').read_text())
        self.assertEqual(outline['slides'][2]['title'], 'Capacity holds with two or more instances')
        self.assertEqual(self.record(root)['gates']['gate:outline']['by'], 'desk')

    def test_the_outline_price_counts_the_sections_that_change(self):
        root = self.deck()
        slides = self.desk_view(root)['outline']['slides']
        moved = [slides[0], slides[1], slides[4], slides[2], slides[3], *slides[5:]]
        said = self.engine.desk_outline_price(root, moved)['says']
        self.assertTrue(said.startswith('2 sections change and are redrawn; the rest stay as '
                                        'drawn.'), said)
        one = self.edited(root, 3, title='Capacity holds with two or more instances')
        said = self.engine.desk_outline_price(root, one)['says']
        self.assertTrue(said.startswith('1 section changes and is redrawn; the rest stay as '
                                        'drawn.'), said)
        self.assertIn('Last time', said)

    def test_a_refused_outline_saves_nothing(self):
        root = self.deck()
        before = (root / 'outline.json').read_bytes()
        slides = self.edited(root, 3, title='Capacity holds with two or more instances')
        refused = {'status': 'findings', 'slides': 8, 'words': {},
                   'findings': [{'slide': 's3', 'code': 'title-too-long'}]}
        with mock.patch.object(self.slides, 'outline_check', return_value=refused), \
                self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_outline(root, slides, self.desk_view(root)['outline']['expected'])
        self.assertTrue(str(caught.exception).startswith('The outline cannot be saved.'))
        self.assertEqual((root / 'outline.json').read_bytes(), before)
        self.assertEqual(self.waiting(root), 'gate:build')

    def test_an_outline_read_before_it_changed_is_refused(self):
        root = self.deck()
        slides = self.edited(root, 3, title='Capacity holds with two or more instances')
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_outline(root, slides, '0' * 64)
        self.assertEqual(str(caught.exception), desk.OUTLINE_CHANGED)

    def test_reading_the_document_the_other_way_writes_the_outline_again(self):
        root = self.deck(route='document',
                         source={'kind': 'paste', 'text': 'Notes on rolling restarts.'})
        self.assertEqual(self.desk_view(root)['outline']['reading']['kind'], 'material')
        self.assertTrue(self.desk_view(root)['outline']['reading']['price'])
        outlines = len(self.workers.of('outline'))
        self.engine.desk_reread(root, 'spec')
        self.assertEqual(self.record(root)['classified'], 'spec')
        self.assertEqual(len(self.workers.of('outline')), outlines + 1)
        self.on_desk(root)

    def test_only_a_document_is_read_the_other_way(self):
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_reread(root, 'spec')
        self.assertEqual(str(caught.exception), 'Only a document is read as a script for '
                                                'the slides or as material.')

    def test_the_look_pick_is_the_person_s(self):
        root = self.start_desk(look='pick')
        self.pick_look(root)
        record = self.record(root)
        self.assertEqual(record['gates']['gate:look']['by'],
                         self.gitstate.identity(self.space.repo))
        self.assertFalse([event for event in record.get('review_events') or ()
                          if event['gate'] == 'gate:look'])

    def test_change_the_look_draws_it_again_and_every_section_after_the_pick(self):
        root = self.deck()
        self.assertTrue(self.desk_view(root)['outline']['look']['price'].startswith(
            'Redraws every section.'))
        jobs = len(self.workers.of('section'))
        self.engine.desk_look_again(root)
        self.assertEqual(self.waiting(root), 'gate:look')
        self.pick_look(root, 'example-bold')
        self.assertEqual(len(self.workers.of('section')) - jobs, 2)
        self.assertEqual(looks.chosen(root)['choice'], 'example-bold')
        self.on_desk(root)


class DeliverTests(DeskCase):
    """Deliver sends the deck on screen, with the brand check the person saw, and is theirs."""

    def deck(self) -> Path:
        root = self.start_desk(look='default')
        self.on_desk(root)
        return root

    def deliver(self, root: Path, **named) -> dict:
        return self.engine.desk_deliver(root, self.desk_view(root)['expected'], **named)

    def names(self) -> list[str]:
        return [entry['name'] for entry in self.slides.run.files.values()]

    def test_deliver_sends_the_deck_on_screen(self):
        root = self.deck()
        self.deliver(root)
        said = json.loads((root / 'deliver.json').read_text())
        self.assertEqual((said['revision'], said['review_status']), (1, 'unreviewed'))
        self.assertEqual(self.names(), ['Rolling restarts'])
        record = self.record(root)
        self.assertEqual(record['gates']['gate:build']['by'],
                         self.gitstate.identity(self.space.repo))
        self.assertEqual(record['gates']['gate:build']['note'], 'Delivered from the desk.')
        shown = self.desk_view(root)
        self.assertEqual(shown['delivered']['revision'], 1)
        name, _ = self.engine.download(root)
        self.assertEqual(name, f'{root.name}.pptx')

    def test_deliver_against_another_deck_is_refused(self):
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_deliver(root, '0' * 64)
        self.assertEqual(str(caught.exception), desk.CHANGED)
        self.assertFalse((root / 'deliver.json').exists())

    def test_deliver_while_a_redraw_runs_is_refused(self):
        root = self.deck()
        refused = []

        def delivering(tools, job):
            with self.assertRaises(WorkspaceError) as caught:
                self.deliver(root)
            refused.append(str(caught.exception))
            return self.workers.section(tools, job)

        self.workers.then('section', delivering)
        self.engine.desk_note(root, 3, 'Make the diagram a sequence.',
                              self.desk_view(root)['expected'])
        self.assertEqual(refused, [desk.STILL])
        self.assertFalse((root / 'deliver.json').exists())

    def test_deliver_over_blockers_needs_the_list_the_person_saw(self):
        with mock.patch.object(self.brand, 'audit', return_value=BLOCKED):
            root = self.deck()
        shown = self.desk_view(root)
        with self.assertRaises(WorkspaceError) as caught:
            self.deliver(root)
        self.assertEqual(str(caught.exception), desk.BLOCKERS_CHANGED)
        # The brand check changed after the page read it: refused again.
        from runner.steps import build
        state = build.read_state(root)
        state['audit']['messages'].append('Slide 5: Text overlaps the picture. (error)')
        build.write_state(root, state)
        with self.assertRaises(WorkspaceError) as caught:
            self.deliver(root, blockers_seen=shown['blockers_seen'])
        self.assertEqual(str(caught.exception), desk.BLOCKERS_CHANGED)
        self.deliver(root, blockers_seen=self.desk_view(root)['blockers_seen'])
        self.assertTrue((root / 'deliver.json').exists())

    def test_a_change_after_delivery_makes_the_next_revision(self):
        root = self.deck()
        self.deliver(root)
        jobs = len(self.workers.of('section'))
        self.engine.desk_note(root, 3, 'Make the diagram a sequence.',
                              self.desk_view(root)['expected'])
        from runner import decks
        self.assertIsNone(decks.delivered(root))
        self.assertEqual([one['revision'] for one in self.record(root)['revisions']], [1])
        again = self.workers.of('section')[jobs:]
        self.assertEqual(len(again), 1)
        self.assertIn('Draw section 1 of', again[0].task)
        shown = self.desk_view(root)
        self.assertIsNone(shown['delivered'])
        self.assertEqual(shown['revision'], desk.DELIVERED_AGAIN.format(revision=1, next=2))
        self.deliver(root)
        self.assertEqual([one['revision'] for one in self.record(root)['revisions']], [1, 2])
        self.assertEqual(self.names(), ['Rolling restarts', 'Rolling restarts (revision 2)'])

    def test_a_gated_deck_still_delivers_with_its_first_draft_title(self):
        root = self.gated(initial_review='user-first')
        self.decide(root, 'gate:build')
        self.assertEqual(self.names(), ['Rolling restarts — first draft, not checked'])
        name, _ = self.engine.download(root)
        self.assertEqual(name, f'{root.name}-unreviewed-first-draft.pptx')


class DeskTeamTests(DeskCase, runner_support.TeamCase):
    """The team claim holds on the desk: only the computer that drives a deck changes it,
    and a computer that took a deck over draws it only when asked."""

    def deck(self) -> Path:
        with self.be(self.alex):
            root = self.start_desk(look='default')
            self.on_desk(root)
            self.engine.share()
        return root

    def as_blake(self, action, *args):
        return self.as_(self.blake, action, *args)

    def test_a_teammate_cannot_note_a_slide_on_a_deck_driven_elsewhere(self):
        from runner import team
        root = self.deck()
        self.as_blake(self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        expected = self.as_blake(self.blake.engine.view, theirs)['desk']['expected']
        with self.be(self.blake):
            with self.assertRaises(self.engines.Elsewhere) as caught:
                self.blake.engine.desk_note(theirs, 3, 'Shorter.', expected)
            said = team.elsewhere(self.blake.space, self.blake.engine._load(theirs))
        self.assertEqual(str(caught.exception), said)

    def test_a_deck_taken_over_does_not_redraw_itself(self):
        root = self.deck()
        self.as_blake(self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        jobs = len(self.workers.of('section'))
        taken = self.as_blake(self.blake.engine.drive, theirs, 'take')
        self.assertTrue(taken['mine'])
        self.assertEqual(len(self.workers.of('section')), jobs)
        shown = taken['desk']
        self.assertFalse(shown['drawn_here'])
        self.assertEqual(shown['no_drawing'], desk.NO_DRAWING)
        self.assertTrue(shown['draw_here_price'].startswith('Redraws every section.'))
        self.assertEqual(taken['gate']['name'], 'gate:build')
        # Its cards are the shared outline's words, with no pictures.
        cards = [card for part in shown['sections'] for card in part['slides']]
        self.assertEqual(len(cards), 8)
        self.assertEqual({card['image'] for card in cards}, {None})
        drawn = self.as_blake(self.blake.engine.desk_draw_here, theirs)
        self.assertEqual(len(self.workers.of('section')), jobs + 2)
        self.assertTrue(drawn['desk']['drawn_here'])
        self.assertEqual(drawn['gate']['name'], 'gate:build')

    def test_desk_work_settles_only_on_the_driving_computer(self):
        root = self.deck()
        theirs = self.theirs(self.blake, root)

        def taken_over(tools, job):
            self.as_blake(self.blake.engine.fetch)
            self.as_blake(self.blake.engine.drive, theirs, 'take')
            with self.be(self.alex):
                self.alex.engine.fetch()
            return self.workers.section(tools, job)

        self.workers.then('section', taken_over)
        kept = self.shared().count('Rolling restarts: keep section 1')
        with self.be(self.alex):
            self.engine.desk_note(root, 3, 'Make the diagram a sequence.',
                                  self.desk_view(root)['expected'])
        mine = self.as_blake(self.blake.engine.view, theirs)
        self.assertTrue(mine['mine'])
        notes = self.as_blake(self.blake.engine._load, theirs)['desk_notes']
        self.assertEqual([(item['number'], item['status']) for item in notes], [(3, 'waiting')])
        self.assertFalse(mine['desk']['drawn_here'])
        with self.be(self.alex):
            self.assertFalse(self.engine.view(root)['mine'])
        # Alex's drawing of it was not kept as the deck's: the shared record never had it.
        self.assertEqual(self.shared().count('Rolling restarts: keep section 1'), kept)


class ReviewFixTests(DeskCase):
    """What the first review of the desk found, each held to here."""

    def deck(self, **changes) -> Path:
        root = self.start_desk(**{'look': 'default', **changes})
        self.on_desk(root)
        return root

    def test_a_refused_reading_leaves_a_delivered_deck_delivered(self):
        from runner import decks
        root = self.deck(route='document',
                         source={'kind': 'paste', 'text': 'Notes on rolling restarts.'})
        self.engine.desk_deliver(root, self.desk_view(root)['expected'])
        before = (root / 'deliver.json').read_bytes()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_reread(root, 'material')
        self.assertIn('read as material already', str(caught.exception))
        self.assertEqual((root / 'deliver.json').read_bytes(), before)
        self.assertIsNotNone(decks.delivered(root))
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_a_change_to_a_delivered_deck_leaves_nothing_uncommitted(self):
        root = self.deck()
        self.engine.desk_deliver(root, self.desk_view(root)['expected'])
        self.engine.desk_look_again(root)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_stop_again_after_it_did_not_end_in_time(self):
        import threading

        from runner import engine as engines
        root = self.deck()
        tried, done = [], []

        def stopping(tools, job):
            if section_of_job(tools) == 2:
                def stop():
                    with mock.patch.object(engines.Engine, '_ended', return_value=False):
                        try:
                            self.engine.desk_stop(root)
                        except WorkspaceError as refusal:
                            tried.append(str(refusal))
                    done.append(True)
                thread = threading.Thread(target=stop)
                thread.start()
                thread.join(30)
                return None
            return self.workers.section(tools, job)

        self.workers.then('section', stopping, stopping)
        self.engine.desk_deck_note(root, 'Fewer words.', self.desk_view(root)['expected'])
        self.assertEqual(tried, [desk.NOT_ENDED])
        self.assertEqual(self.record(root)['halted']['state'], 'stopped')
        self.engine.desk_stop(root)
        self.on_desk(root)
        self.assertIsNone(self.record(root)['halted'])
        self.assertFalse(desk.opened(self.record(root)))

    def test_a_note_before_the_deck_reaches_the_desk_says_so(self):
        said = []

        def noting(tools, job):
            root = self.engine.every()[0]
            with self.assertRaises(WorkspaceError) as caught:
                self.engine.desk_note(root, 3, 'Shorter.', 'x')
            said.append(str(caught.exception))
            return self.workers.outline(tools, job)

        self.workers.then('outline', noting)
        self.deck()
        self.assertEqual(said, [desk.NOT_YET])

    def test_an_existing_deck_is_started_on_the_desk_with_its_level(self):
        from runner import decks
        given = {**runner_support.FORM, 'route': 'existing',
                 'source': {'kind': 'upload', 'name': 'old.pptx'}, 'flow': 'desk'}
        polish = decks.check_form({**given, 'level': 'polish'}, None)
        self.assertEqual((polish['flow'], polish['level'], polish['initial_review']),
                         ('desk', 'polish', 'user-first'))
        # Selected changes builds nothing, so it has no first draft before a deck check.
        selected = decks.check_form({**given, 'level': 'selected', 'selected': 'Slide 2.'},
                                    None)
        self.assertEqual(selected['flow'], 'desk')
        self.assertNotIn('initial_review', selected)
        with self.assertRaises(WorkspaceError):
            decks.check_form({**given, 'level': 'polish', 'research': True}, None)

    def test_a_web_plan_from_the_form_searches_with_its_questions(self):
        from runner import research_steps
        contract = {'schema': 2, 'version': '1.0.0', 'digest': 'abc'}
        with mock.patch.object(self.engines.research_contract, 'snapshot',
                               return_value=contract), \
                mock.patch.object(research_steps.research_contract, 'native',
                                  side_effect=WorkspaceError('Stopped here for the test.')):
            root = self.start_desk(look='default', research=True,
                                   research_questions=['What starts the next batch?'])
        plan = json.loads((root / 'research/plan.json').read_text())
        self.assertEqual(plan['items'][0]['public_query'], 'What starts the next batch?')


class SecondReviewTests(DeskCase):
    """What the second review of the desk found, each held to here."""

    def deck(self, **changes) -> Path:
        root = self.start_desk(**{'look': 'default', **changes})
        self.on_desk(root)
        return root

    def test_the_look_pause_on_the_desk_is_not_desk_work(self):
        root = self.deck()
        self.engine.desk_look_again(root)
        shown = self.view(root)
        self.assertEqual(shown['gate']['name'], 'gate:look')
        self.assertIsNone(shown['desk']['working'])
        self.assertFalse(shown['desk']['deliverable'])

    def test_the_looks_are_drawn_again_at_the_pause(self):
        root = self.start_desk(look='pick')
        self.assertEqual(self.waiting(root), 'gate:look')
        self.engine.desk_look_again(root)
        self.assertEqual(self.waiting(root), 'gate:look')
        self.pick_look(root)
        self.on_desk(root)

    def test_a_brand_with_no_looks_does_not_pause_for_one(self):
        self.brand.run.offers_looks = False
        root = self.start_desk(look='pick')
        self.on_desk(root)
        self.assertEqual(self.record(root)['gates']['gate:look']['by'], 'desk')

    def test_a_redraw_that_fails_can_be_given_up(self):
        root = self.deck()

        def failing(tools, job):
            if section_of_job(tools) == 2:
                return runner_support.fails()(tools, job)
            return self.workers.section(tools, job)

        self.workers.then('section', *[failing] * 8)
        self.engine.desk_deck_note(root, 'Fewer words.', self.desk_view(root)['expected'])
        shown = self.view(root)
        self.assertEqual(shown['problem']['state'], 'failed')
        self.assertTrue(shown['desk']['working']['halted'])
        self.assertFalse(shown['desk']['deliverable'])
        self.engine.desk_stop(root)
        shown = self.on_desk(root)
        self.assertIsNone(self.record(root)['halted'])
        self.assertTrue(shown['desk']['deliverable'])
        notes = {item['section']: item['status'] for item in self.record(root)['desk_notes']}
        self.assertEqual(notes, {'section-1': 'done', 'section-2': 'set aside'})

    def test_a_stopped_redraw_still_offers_stop(self):
        from runner import engine as engines
        root = self.deck()
        tried = []

        def stopping(tools, job):
            if section_of_job(tools) == 2:
                import threading

                def stop():
                    with mock.patch.object(engines.Engine, '_ended', return_value=False):
                        try:
                            self.engine.desk_stop(root)
                        except WorkspaceError as refusal:
                            tried.append(str(refusal))
                thread = threading.Thread(target=stop)
                thread.start()
                thread.join(30)
                return None
            return self.workers.section(tools, job)

        self.workers.then('section', stopping, stopping)
        self.engine.desk_deck_note(root, 'Fewer words.', self.desk_view(root)['expected'])
        shown = self.view(root)['desk']
        self.assertTrue(shown['working']['halted'])
        self.assertFalse(shown['deliverable'])

    def test_the_older_note_for_the_next_step_is_refused_on_the_desk(self):
        root = self.deck()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.note(root, 'Keep it short.')
        self.assertEqual(str(caught.exception), desk.ON_DESK)

    def test_a_whole_deck_note_before_the_desk_says_so(self):
        said = []

        def noting(tools, job):
            root = self.engine.every()[0]
            with self.assertRaises(WorkspaceError) as caught:
                self.engine.desk_deck_note(root, 'Fewer words.', 'x')
            said.append(str(caught.exception))
            return self.workers.outline(tools, job)

        self.workers.then('outline', noting)
        self.deck()
        self.assertEqual(said, [desk.NOT_YET])


class DeskTeamFixTests(DeskCase, runner_support.TeamCase):
    def test_draw_it_here_sends_the_notes_with_the_first_drawing(self):
        with self.be(self.alex):
            root = self.start_desk(look='default')
            self.engine.share()
        theirs = self.theirs(self.blake, root)

        def taken_over(tools, job):
            self.as_(self.blake, self.blake.engine.fetch)
            self.as_(self.blake, self.blake.engine.drive, theirs, 'take')
            with self.be(self.alex):
                self.alex.engine.fetch()
            return self.workers.section(tools, job)

        self.workers.then('section', taken_over)
        with self.be(self.alex):
            self.engine.desk_note(root, 3, 'Make the diagram a sequence.',
                                  self.desk_view(root)['expected'])
        shown = self.as_(self.blake, self.blake.engine.view, theirs)
        self.assertNotEqual(shown['state'], 'working')
        self.assertIsNone(shown['desk']['working'])
        jobs = len(self.workers.of('section'))
        self.as_(self.blake, self.blake.engine.desk_draw_here, theirs)
        again = self.workers.of('section')[jobs:]
        self.assertEqual(len(again), 2)
        self.assertEqual(sum('Slide 3: Make the diagram a sequence.' in job.task
                             for job in again), 1)
        notes = self.as_(self.blake, self.blake.engine._load, theirs)['desk_notes']
        self.assertEqual([item['status'] for item in notes], ['done'])


class SourceTests(DeskCase):
    """Add a source on the desk, and the Research panel: findings, gaps and Leave out, and
    Research again, each priced before it runs."""

    def deck(self, **changes) -> Path:
        root = self.start_desk(look='default', **changes)
        self.on_desk(root)
        return root

    def test_a_source_added_on_the_desk_starts_no_job(self):
        root = self.deck()
        jobs, log = len(self.workers.jobs), self.log()
        shown = self.engine.desk_source(root, 'notes.md', b'# Batches\n\nTwo at a time.\n')
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual([entry['title'] for entry in shown['desk']['sources']], ['notes'])
        self.engine.desk_source(root, None, text='Health checks gate each batch.',
                                title='Pasted notes')
        listed = self.desk_view(root)['sources']
        self.assertEqual([entry['title'] for entry in listed], ['notes', 'Pasted notes'])
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(self.log(), log)
        self.on_desk(root)

    def test_a_source_is_refused_as_documents_refuse_it(self):
        root = self.deck()
        self.engine.desk_source(root, 'notes.md', b'Two at a time.')
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_source(root, 'notes.md', b'Two at a time.')
        self.assertIn('was already added', str(caught.exception))
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_source(root, None, text='   ', title='Empty')
        self.assertIn('holds no text', str(caught.exception))
        self.assertEqual(len(self.desk_view(root)['sources']), 1)

    def test_a_gated_deck_adds_no_source_on_the_desk(self):
        root = self.gated()
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_source(root, 'notes.md', b'Two at a time.')
        self.assertEqual(str(caught.exception), desk.NOT_ON_DESK)

    def test_research_again_is_priced_before_it_runs(self):
        from studio_core import research_view
        root = self.deck(research=True)
        shown = self.desk_view(root)
        said = research_view.price({}, drafted=False)['words']
        self.assertEqual(shown['research_price'].split(':')[0], said.split(':')[0])
        self.assertIn('Then it makes again: the outline, the look samples and the deck.',
                      shown['research_price'])
        self.assertEqual([item['id'] for item in shown['research_items']],
                         list(self.engine._questions(root)))

    def test_research_again_reads_the_sources_again_and_comes_back_to_the_desk(self):
        root = self.deck(research=True)
        asked = len(self.workers.of('question'))
        self.engine.desk_research_again(root, self.desk_view(root)['expected'])
        self.assertGreater(len(self.workers.of('question')), asked)
        record = self.record(root)
        self.assertTrue(record['gates']['gate:research'].get('refresh'))
        self.assertEqual(record['gates']['gate:research']['by'], 'desk')
        self.on_desk(root)

    def test_research_again_against_another_deck_is_refused(self):
        root = self.deck(research=True)
        with self.assertRaises(WorkspaceError) as caught:
            self.engine.desk_research_again(root, 'x')
        self.assertEqual(str(caught.exception), desk.CHANGED)

    def test_leaving_a_finding_out_redraws_the_outline_and_looks_without_research(self):
        root = self.deck(research=True)
        shown = self.desk_view(root)
        # What it redraws on the desk, and what that last took here: the outline, the look
        # samples, the last section drawn, and the deck put together and rendered.
        from studio_core import stops
        record = self.record(root)
        last = [entry['tries'][-1] for name, entry in record['steps'].items()
                if name in ('outline', 'look-preview', 'build-whole', 'build-render')
                and entry.get('tries')]
        sections = sorted((attempt for name, entry in record['steps'].items()
                           if name.startswith('build-sections:')
                           for attempt in entry.get('tries') or ()
                           if attempt.get('outcome') == 'kept'),
                          key=lambda attempt: attempt.get('ended_at') or '')
        last.append(sections[-1])
        seconds = round(sum(float(attempt.get('seconds') or 0) for attempt in last), 1)
        self.assertEqual(shown['leave_out_price'], desk.LEAVE_OUT_SAYS + desk.LEAVE_OUT_TOOK.format(
            cost=stops.cost(seconds, None)))
        self.assertEqual(desk.LEAVE_OUT_SAYS, 'Leaving findings out redraws the outline and the '
                         'look samples without researching again, and then redraws the slides '
                         'whose outline changed.')
        first = shown['research_items'][0]['id']
        jobs = len(self.workers.jobs)
        self.engine.desk_leave_out(root, [first])
        again = [kind for kind, _, _ in self.workers.jobs[jobs:]]
        self.assertNotIn('question', again)
        self.assertNotIn('research-plan', again)
        self.assertEqual(again.count('outline'), 1)
        self.assertEqual(self.record(root)['research']['left_out'], [first])
        self.on_desk(root)

    def test_every_finding_cannot_be_left_out(self):
        root = self.deck(research=True)
        every = [item['id'] for item in self.desk_view(root)['research_items']]
        with self.assertRaises(WorkspaceError):
            self.engine.desk_leave_out(root, every)

    def test_a_words_job_reads_the_added_source(self):
        root = self.deck()
        self.engine.desk_source(root, None, text='Each batch waits for its health checks.',
                                title='Runbook')
        read = []

        def reading(tools, job):
            read.append(tools.read_input('sources')[1])
            return self.workers.words(tools, job)

        self.workers.then('words', reading)
        text = json.loads((root / 'outline.json').read_text())['slides'][2]['points'][0]['text']
        start = text.index('the load')
        self.engine.desk_selection(root, 3, ('points', 0, 'text'), start,
                                   start + len('the load'), 'expand', None,
                                   self.desk_view(root)['seen'])
        self.assertEqual(len(read), 1)
        self.assertIn('Each batch waits for its health checks.', read[0])
        self.assertIn('Runbook', read[0])


if __name__ == '__main__':
    unittest.main()
