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

from runner import desk, stages
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
        from runner import research_steps
        from studio_core import research_contract
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
    ROUTES = {'desk_look': ('example-clear',)}

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
        for name, given in self.ROUTES.items():
            with self.subTest(route=name):
                with self.assertRaises(WorkspaceError) as caught:
                    getattr(self.engine, name)(root, *given)
                self.assertEqual(str(caught.exception), desk.NOT_ON_DESK)
        self.assertEqual(self.waiting(root), 'gate:build')


if __name__ == '__main__':
    unittest.main()
