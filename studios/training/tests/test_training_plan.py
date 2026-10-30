"""One checked topics review, then automatic generation; synthetic authors only."""
from test_runner_deck import DeckCase, PageCase
from runner import training_plan
from workspace import WorkspaceError
import workspace

class PlanTests(DeckCase):
    def start_plan(self, **changes):
        self.engine.plan_first = True
        self.engine.content_first = True
        return self.begin(flow='desk', **changes)

    def test_topics_review_precedes_every_material_and_one_approval_builds_the_deck(self):
        root = self.start_plan()
        view = self.view(root)
        self.assertEqual(view['state'], 'waiting')
        plan = view['training_plan']
        self.assertTrue(plan['levels'][0]['modules'])
        self.assertTrue(plan['levels'][0]['modules'][0]['items'])
        self.assertTrue(plan['levels'][0]['modules'][0]['example'])
        self.assertFalse(self.workers.of('document'))
        self.assertFalse(self.workers.of('section'))
        self.assertFalse(any(call[0] in ('preview', 'render') for call in self.slides.calls))
        self.assertEqual(self.engine._load(root)['schema'], 6)
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, 'old-version', 'approve')
        result = training_plan.decide(self.engine, root, plan['expected'], 'approve')
        self.assertIsNone(result['training_plan'])
        self.assertFalse(result['problem'])
        self.assertTrue(self.workers.of('document'))
        self.assertTrue(self.workers.of('section'))
        self.assertFalse((result.get('outline') or {}).get('waiting'))
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, plan['expected'], 'approve')
        self.assertFalse(workspace.person_statuses(root, workspace.load(root))['deck'] == 'approved')

    def test_changes_revise_the_topics_without_repeating_research_or_writing_materials(self):
        root = self.start_plan()
        before = self.view(root)['training_plan']
        research = list(self.workers.of('question'))
        self.assertRaises(WorkspaceError, training_plan.decide, self.engine, root, before['expected'], 'changes', '')
        result = training_plan.decide(self.engine, root, before['expected'], 'changes', 'Go deeper on the mechanism and include practical work.')
        self.assertTrue(result['training_plan'])
        self.assertIn('Go deeper on the mechanism', self.workers.of('blueprint')[-1].task)
        self.assertNotEqual(before['expected'], result['training_plan']['expected'])
        self.assertEqual(research, self.workers.of('question'))
        self.assertFalse(self.workers.of('document'))
        self.assertFalse(self.workers.of('section'))
        self.assertRaises(WorkspaceError, training_plan.decide, self.engine, root, before['expected'], 'changes', 'Duplicate request')
        self.assertFalse(any('sample' in key for key in self.engine._load(root)['steps']))

    def test_every_level_is_presented_together_before_writing_any_guide(self):
        root = self.start_plan(levels=['101', '201'])
        plan = self.view(root)['training_plan']
        self.assertEqual([level['level'] for level in plan['levels']], ['101', '201'])
        self.assertFalse(self.workers.of('document'))
        result = training_plan.decide(self.engine, root, plan['expected'], 'approve')
        self.assertFalse(result['problem'])
        self.assertFalse(result['training_plan_pending'])

    def test_active_work_and_paused_state_cannot_be_approved(self):
        root = self.start_plan()
        expected = self.view(root)['training_plan']['expected']
        run = self.engine._run(root)
        run.workers['fixture-active'] = {}
        try:
            self.assertRaises(WorkspaceError, training_plan.decide, self.engine, root, expected, 'approve')
        finally:
            run.workers.pop('fixture-active')
        record = self.engine._load(root)
        record['halt'] = 'paused'
        self.engine._store(root, record)
        self.assertRaises(WorkspaceError, training_plan.decide, self.engine, root, expected, 'approve')
        self.assertFalse(self.workers.of('document'))

    def test_a_plan_file_cannot_read_outside_the_training(self):
        root = self.start_plan()
        session = workspace.load(root)
        file = root / workspace.artifact(root, session, 'blueprint')['file']
        text = file.read_bytes()
        outside = self.base / 'outside-blueprint.md'
        outside.write_text('Synthetic outside content')
        file.unlink(); file.symlink_to(outside)
        try:
            self.assertRaises(WorkspaceError, training_plan.signature, root, session, self.engine._load(root))
        finally:
            file.unlink(); file.write_bytes(text)

    def test_restart_preserves_waiting_decision_and_unsupported_record_cannot_be_driven(self):
        root = self.start_plan()
        before = self.view(root)['training_plan']['expected']
        self.engine.wake(root)
        self.assertEqual(before, self.view(root)['training_plan']['expected'])
        record = self.engine._load(root)
        record['research_execution'] = {'protocol': 'unsupported'}
        self.engine._store(root, record)
        self.assertRaises(WorkspaceError, self.engine._load, root)
        record.pop('research_execution')
        record.pop('training_plan')
        with self.engine.files:
            self.engine._store(root, record)
        self.assertRaises(WorkspaceError, self.engine._load, root)

class PlanPageTests(PageCase):
    def test_the_private_page_requires_authentication_and_the_exact_topics_revision(self):
        self.engine.plan_first = True
        root = self.begin(flow='desk')
        plan = self.view(root)['training_plan']
        body = {'path': str(root), 'expected': plan['expected'], 'decision': 'approve'}
        self.assertEqual(self.ask('POST', '/api/training-plan', body, token=False)[0], 403)
        self.post('training-plan', {**body, 'expected': 'old'}, expect=409)
        self.assertFalse(self.workers.of('document'))
        result = self.post('training-plan', body)
        self.assertFalse(result['problem'])
        self.assertTrue(self.workers.of('document'))
        self.post('training-plan', body, expect=409)
