"""Scan, outline, then fill in (#297): scripted workers and disposable workspaces only."""
import copy
import json
from pathlib import Path

from runner_support import SCAN, URL, StudioCase
from runner import outline_first, pipeline, settings_change, training_plan
from studio_core import research_session
from workspace import WorkspaceError
import workspace


def edited(plan):
    """The outline as the page sends it back, unchanged."""
    return {'sections': copy.deepcopy(plan['sections']), 'separate': copy.deepcopy(plan['separate'])}


class OutlineFirstTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.engine.plan_first = self.engine.outline_first = True

    def begin(self, **changes):
        root = self.start(source_scope='supplied-only', **changes)
        self.send(root, 'handbook.md')
        self.engine.supply(root, 'done')
        return root

    def spent(self, root):
        return [(name, attempt.get('dollars')) for name, entry in self.engine._load(root)['steps'].items()
                for attempt in entry['attempts'] if attempt.get('dollars') is not None]

    def test_a_supplied_only_start_scans_once_and_waits_at_the_outline(self):
        self.workers.cost = 0.12
        root = self.begin()
        record = self.engine._load(root)
        self.assertEqual(record['schema'], outline_first.RECORD_SCHEMA)
        self.assertTrue(training_plan.outlined(record))
        view = self.view(root)
        self.assertEqual(view['state'], 'waiting')
        self.assertTrue(view['outline_first'])
        plan = view['training_plan']
        self.assertEqual(plan['mode'], 'outline')
        self.assertGreaterEqual(len(plan['sections']), 2)
        self.assertTrue(all(1 <= len(section['questions']) <= 3 for section in plan['sections']))
        self.assertIn('not research', plan['scan']['note'])
        # The scan ran once, and nothing else: no research plan, no research, no blueprint.
        self.assertEqual([kind for kind, _, _ in self.workers.jobs], ['training-scan'])
        self.assertFalse((root / pipeline.PLAN).exists())
        scan = self.workers.of('training-scan')[0]
        self.assertEqual(scan.profile, 'write', 'supplied-only never searches the web')
        self.assertLessEqual(scan.limits.seconds, outline_first.SCAN_SECONDS)
        self.assertLessEqual(scan.limits.dollars, outline_first.SCAN_DOLLARS)
        # The spend before the outline is shown is the scan alone.
        self.assertEqual(self.spent(root), [('scan', 0.12)])
        kept = json.loads((root / outline_first.SCAN).read_text())
        self.assertIs(kept['evidence'], False)
        self.assertEqual(kept['documents'][0]['source'], 's1')

    def capture(self):
        """Keep what each research job is given, then do what a scripted researcher does."""
        seen = []

        def act(tools, job):
            seen.append(json.loads(tools.read_input('research-task')[1]))
            return self.workers.research_result(tools, job)
        self.workers.then('research-result', *([act] * 8))
        return seen

    def test_the_person_edits_and_approves_then_each_section_is_researched(self):
        seen = self.capture()
        root = self.begin()
        plan = self.view(root)['training_plan']
        sent = edited(plan)
        sent['sections'].pop()                                           # remove one
        sent['sections'][0]['title'] = 'How batches replace instances'   # rename one
        sent['sections'][1]['questions'].pop()                           # remove a question
        sent['sections'].append({'title': 'Rolling back', 'objectives': ['Undo a bad restart'],
                                 'questions': [{'text': 'How is a rolling restart rolled back?'}]})
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, 'old', 'approve', outline=sent)
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, plan['expected'], 'changes', 'More depth.')
        self.assertEqual(seen, [], 'nothing is researched before the outline is approved')
        result = training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=sent)
        self.assertFalse(result['problem'], result['problem'])
        self.assertFalse(result['training_plan_pending'])
        saved = outline_first.read(root)
        self.assertEqual([s['title'] for s in saved['sections']],
                         ['How batches replace instances', 'Keeping capacity during a restart', 'Rolling back'])
        self.assertEqual(saved['sections'][2]['questions'][0]['from'], 'you')
        items = json.loads((root / pipeline.PLAN).read_text())['items']
        self.assertEqual([item['section'] for item in items], ['section-1', 'section-2', 'section-3'])
        self.assertEqual(items[2]['section_title'], 'Rolling back')
        # Research is given the approved sections, and told to organize the report by them.
        self.assertTrue(seen)
        task = seen[0]['task']
        self.assertIn('Approved training outline', task['scope'])
        self.assertIn('3. Rolling back', task['scope'])
        self.assertEqual([q['section'] for q in task['planning_questions']],
                         ['section-1', 'section-2', 'section-3'])
        self.assertEqual(task['source_mode'], 'selected', 'supplied-only stays supplied-only')
        # The materials are built from the approved outline and the research.
        blueprint = self.workers.of('blueprint')[0]
        self.assertIn('"training outline"', blueprint.task)
        self.assertEqual(self.engine._load(root)['research']['plan_from'], 'outline')
        steps = {step['id']: step for step in self.view(root)['steps']}
        self.assertEqual(steps['research-plan']['label'], outline_first.FROM_OUTLINE)
        self.assertEqual(steps['scan']['status'], 'done')
        self.assertEqual(steps[training_plan.STEP]['status'], 'done')
        self.assertEqual(len(self.workers.of('training-scan')), 1, 'the scan ran once')


class StreamsTests(StudioCase):
    def items(self, *sections):
        return [{'id': f's{n}-q{m}', 'question': f'Question {m} of {n}?', 'section': f'section-{n}',
                 'section_title': f'Section {n}'}
                for n, count in enumerate(sections, start=1) for m in range(1, count + 1)]

    def test_one_area_for_each_section_up_to_three(self):
        areas = research_session.streams({'planning_questions': self.items(1, 2), 'scope': ''})
        self.assertEqual([a['sections'] for a in areas], [['section-1'], ['section-2']])
        self.assertEqual([len(a['questions']) for a in areas], [1, 2])
        self.assertEqual(areas[1]['title'], 'Section 2')
        areas = research_session.streams({'planning_questions': self.items(1, 1, 1, 1, 1), 'scope': ''})
        self.assertEqual([a['sections'] for a in areas],
                         [['section-1', 'section-2'], ['section-3', 'section-4'], ['section-5']])
        self.assertEqual(areas[0]['title'], 'Section 1; Section 2')
        self.assertEqual(len(research_session.streams({'planning_questions': self.items(2, 2, 2), 'scope': ''}, 1)), 1)

    def test_plans_without_sections_keep_their_areas(self):
        plain = [{'id': f'q{n}', 'question': f'Q{n}?'} for n in range(1, 5)]
        areas = research_session.streams({'planning_questions': plain, 'scope': ''})
        self.assertEqual([[q['id'] for q in a['questions']] for a in areas], [['q1', 'q4'], ['q2'], ['q3']])
        self.assertNotIn('title', areas[0])
