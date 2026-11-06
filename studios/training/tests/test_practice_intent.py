"""Short descriptions reach planning, practice and Yoodli without provider jobs."""
from runner_support import StudioCase, FORM, BLUEPRINT, SCENARIO
from runner import pipeline, practice_intent, worker_tools, drafts
import workspace
from workspace import WorkspaceError


PLAN = {'mode': 'custom', 'scenarios': [
    {'id': 'custom-one', 'description': 'Explain restart capacity to a skeptical platform lead.'},
    {'id': 'custom-two', 'description': 'Choose a safe next step after a failed health check.'}]}


class PracticeIntentTests(StudioCase):
    def test_description_edit_invalidates_its_scenario_even_when_the_plan_is_unchanged(self):
        import copy
        root = pipeline.create(self.space, pipeline.check_form({**FORM, 'scenario_plan': PLAN, 'yoodli': True}))
        (root/'scenarios').mkdir()
        for row in PLAN['scenarios']:
            path = root/'scenarios'/(row['id'] + '.md')
            path.write_text(SCENARIO)
            workspace.save(root, 'scenario:' + row['id'], built=True)
        session = workspace.load(root)
        before = workspace.inputs(root, session, 'yoodli:custom-one')
        session['settings']['scenario_plan'] = copy.deepcopy(PLAN)
        session['settings']['scenario_plan']['scenarios'][0]['description'] = 'Explain restart capacity to a new operator.'
        workspace.store(root, session)
        self.assertEqual(workspace.statuses(root, session)['scenario:custom-one'], 'stale')
        self.assertNotEqual(workspace.statuses(root, session)['scenario:custom-two'], 'stale')
        self.assertEqual(drafts.input_of(root, session, 'scenario:custom-one'), ['scenario-intent'])
        self.assertNotEqual(workspace.inputs(root, session, 'yoodli:custom-one'), before)
        self.assertEqual((root/'scenarios/custom-one.md').read_text(), SCENARIO)

    def test_default_and_invalid_short_descriptions(self):
        self.assertEqual(practice_intent.check(), {'mode': 'ai', 'scenarios': []})
        for value in [[], {'mode': 'other'}, {'mode': 'custom', 'scenarios': []},
                      {'mode': 'custom', 'scenarios': [{'id': '../x', 'description': 'No'}]},
                      {'mode': 'custom', 'scenarios': [{'id': 'one', 'description': ' '}]},
                      {'mode': 'custom', 'scenarios': [{'id': 'one', 'description': 'x' * 301}]},
                      {'mode': 'custom', 'scenarios': [PLAN['scenarios'][0]] * 2}]:
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                pipeline.check_form({**FORM, 'scenario_plan': value})
        self.assertEqual(practice_intent.check({'mode': 'ai', 'scenarios': PLAN['scenarios']}),
                         {'mode': 'ai', 'scenarios': []})

    def test_descriptions_persist_and_reach_each_author_at_each_selected_level(self):
        root = pipeline.create(self.space, pipeline.check_form({**FORM, 'levels': ['101', '201'],
            'yoodli': True, 'scenario_plan': PLAN}))
        self.assertEqual(practice_intent.of(workspace.load(root)), PLAN)
        for level in ('101', '201'):
            found = pipeline.survey(root)
            step = next(s for s in found.steps if s.id == 'blueprint@' + level)
            work = pipeline.blueprint_work(root, found, step, None, None, [])
            spec = work.prepared['artifacts']['blueprint']
            self.assertEqual(spec['scenario_ids'], ['custom-one', 'custom-two'])
            for row in PLAN['scenarios']:
                self.assertIn(row['description'], work.prepared['inputs']['creator scenario descriptions'])
            text = BLUEPRINT.replace('Time: 25 min', 'Time: 25 min\nLevel: ' + level)
            self.assertTrue(any('exactly the requested' in message
                                for message in worker_tools.check_blueprint(text, spec)[0]))
            text = text.replace('- main: roleplay.', '- custom-one: roleplay.').replace(
                '## Open gaps', '- custom-two: roleplay. Objectives: O3. A platform lead checking the next step.\n\n## Open gaps')
            self.assertFalse(any('exactly the requested' in message
                                 for message in worker_tools.check_blueprint(text, spec)[0]))
            (root/level).mkdir(exist_ok=True)
            (root/level/'blueprint.md').write_text(text)
            found = pipeline.survey(root)
            for row in PLAN['scenarios']:
                step = next(s for s in found.steps if s.id == 'scenario:' + row['id'] + '@' + level)
                work = pipeline.scenario_work(root, found, step, None, None, [])
                self.assertIn(row['description'], work.prepared['inputs']['creator scenario description'])
                folder = root/level/'scenarios'; folder.mkdir(exist_ok=True)
                (folder/(row['id'] + '.md')).write_text(SCENARIO)
                step = next(s for s in found.steps if s.id == 'yoodli:' + row['id'] + '@' + level)
                work = pipeline.yoodli_work(root, found, step, None, None, [])
                self.assertIn(row['description'], work.prepared['inputs']['creator scenario description'])
                self.assertEqual(work.prepared['inputs']['scenario'], SCENARIO)
        self.assertEqual(self.workers.jobs, [])

    def test_custom_planning_preserves_existing_scenarios_and_own_wording(self):
        root = pipeline.create(self.space, pipeline.check_form({**FORM, 'levels': [], 'scenario_plan': PLAN}))
        (root/'scenarios').mkdir()
        (root/'scenarios/own.md').write_text(SCENARIO)
        found = pipeline.survey(root)
        step = next(s for s in found.steps if s.id == 'blueprint')
        work = pipeline.blueprint_work(root, found, step, None, None, [])
        self.assertEqual(work.prepared['artifacts']['blueprint']['scenario_ids'], ['custom-one', 'custom-two', 'own'])
        step = next(s for s in found.steps if s.id == 'scenario:own')
        work = pipeline.scenario_work(root, found, step, None, None, [])
        self.assertIn('Keep their wording', work.task)
        self.assertNotIn('creator scenario description', work.prepared['inputs'])
        self.assertEqual((root/'scenarios/own.md').read_text(), SCENARIO)
