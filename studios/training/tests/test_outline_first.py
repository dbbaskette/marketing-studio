"""Scan, outline, then fill in (#297): scripted workers and disposable workspaces only.

The tests named row_209 to row_213 cover those rows of the state-transition matrix in
docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md.
"""
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

    def test_row_209_a_supplied_only_start_scans_once_and_waits_at_the_outline(self):
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

    def test_row_210_the_person_edits_and_approves_then_each_section_is_researched(self):
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

    def test_row_209_questions_typed_on_the_form_are_kept_and_attached(self):
        seen = self.capture()
        asked = ['How many instances keep capacity while batches restart?',
                 'Which licence covers the support contract?']
        root = self.begin(research_questions=asked)
        scan = self.workers.of('training-scan')[0]
        self.assertIn(asked[0], scan.task, 'the scan is told of them, to give them a home')
        plan = self.view(root)['training_plan']
        capacity = plan['sections'][1]
        self.assertIn({'text': asked[0], 'from': 'form'}, capacity['questions'])
        self.assertEqual(plan['separate'], [{'text': asked[1], 'from': 'form'}])
        result = training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=edited(plan))
        self.assertFalse(result['problem'], result['problem'])
        items = json.loads((root / pipeline.PLAN).read_text())['items']
        self.assertEqual([item['question'] for item in items if item['section'] == 'other'], [asked[1]])
        self.assertIn(asked[0], [item['question'] for item in items if item['section'] == 'section-2'])
        self.assertIn(outline_first.OTHER[1], seen[0]['task']['scope'])

    def test_a_scan_question_the_person_also_typed_is_not_asked_twice(self):
        outline = outline_first.outline_from(SCAN, ['what starts the next batch of a rolling restart'])
        questions = [q for section in outline['sections'] for q in section['questions']]
        self.assertEqual(sum('next batch' in q['text'] for q in questions), 1)
        self.assertEqual(outline['sections'][1]['questions'][1]['from'], 'form')
        self.assertEqual(outline['separate'], [])

    def test_row_209_with_web_search_the_scan_saves_at_most_its_cap_and_research_may_search(self):
        seen = self.capture()
        pages = [f'https://docs.example.com/page-{n}' for n in range(1, 8)]
        for page in pages:
            self.web.page(page, '<html><title>Page</title><body><p>Rolling restarts.</p></body></html>')
        tried = []

        def scan(tools, job):
            for page in pages:
                tried.append(tools.save_source(page))
            accepted = tools.submit_artifact('training-scan', json.dumps(SCAN))
            self.assertTrue(accepted[0], accepted[1])
        self.workers.then('training-scan', scan)
        root = self.start()      # the public web
        job = self.workers.of('training-scan')[0]
        self.assertEqual(job.profile, 'research')
        self.assertIn(f'at most {outline_first.SCAN_PAGES} web searches', job.task)
        self.assertEqual(sum(ok for ok, _ in tried), outline_first.SCAN_PAGES)
        self.assertIn('at most 5 pages', tried[-1][1])
        kept = json.loads((root / outline_first.SCAN).read_text())
        self.assertEqual(len(kept['pages']), outline_first.SCAN_PAGES)
        plan = self.view(root)['training_plan']
        training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=edited(plan))
        self.assertEqual(seen[0]['task']['source_mode'], 'public')
        self.assertTrue(any(kind == 'research-result' and spec['fetch'] for kind, _, spec in self.workers.jobs))

    def test_row_211_stopping_during_the_scan_keeps_nothing_of_it_and_resume_scans_once(self):
        root = self.start(source_scope='supplied-only')
        self.send(root, 'handbook.md')

        def stop(tools, job):
            self.engine.act(root, 'stop')
        self.workers.then('training-scan', stop)
        self.engine.supply(root, 'done')
        view = self.view(root)
        self.assertEqual(view['state'], 'stopped')
        self.assertFalse(outline_first.scanned(root))
        self.assertEqual(pipeline.tries(self.engine._load(root), 'scan')['attempts'][-1]['outcome'], 'stopped')
        self.engine.act(root, 'resume')
        self.assertEqual(len(self.workers.of('training-scan')), 2)
        self.assertEqual(self.view(root)['training_plan']['mode'], 'outline')

    def test_row_211_stopping_at_the_outline_keeps_it_and_its_version(self):
        root = self.begin()
        before = self.view(root)['training_plan']
        self.engine.act(root, 'stop')
        self.assertEqual(self.view(root)['state'], 'stopped')
        with self.assertRaises(WorkspaceError):
            training_plan.decide(self.engine, root, before['expected'], 'approve', outline=edited(before))
        self.engine.act(root, 'resume')
        after = self.view(root)['training_plan']
        self.assertEqual(after['expected'], before['expected'])
        self.assertEqual(len(self.workers.of('training-scan')), 1, 'the scan is not run again')

    def test_row_211_stopping_during_research_keeps_the_scan_and_the_approved_outline(self):
        root = self.begin()
        plan = self.view(root)['training_plan']

        def stop(tools, job):
            self.engine.act(root, 'stop')
        self.workers.then('research-result', stop)
        training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=edited(plan))
        self.assertEqual(self.view(root)['state'], 'stopped')
        self.assertFalse(self.view(root)['training_plan_pending'])
        self.engine.act(root, 'resume')
        self.assertEqual(len(self.workers.of('training-scan')), 1)
        self.assertTrue(self.workers.of('blueprint'))

    def test_row_211_a_scan_that_does_not_finish_stops_once_with_try_again(self):
        from runner_support import fails
        self.workers.then('training-scan', fails('It stopped without finishing.'))
        root = self.begin()
        view = self.view(root)
        self.assertEqual(view['state'], 'failed')
        self.assertEqual(view['problem']['action'], 'retry')
        self.assertIn('quick scan did not finish', view['problem']['what'])
        self.assertIn('no research has started', view['problem']['kept'])
        self.assertEqual(len(self.workers.of('training-scan')), 1, 'never retried by itself')
        self.engine.act(root, 'retry')
        self.assertEqual(len(self.workers.of('training-scan')), 2)
        self.assertEqual(self.view(root)['training_plan']['mode'], 'outline')


class OutlineSettingsTests(StudioCase):
    """Change settings (#296) on a training scanned and outlined before research."""

    def setUp(self):
        super().setUp()
        self.engine.plan_first = self.engine.outline_first = True

    def change(self, root, **values):
        shown = self.engine.settings_form(root)
        self.assertTrue(shown['may'], shown)
        return self.engine.change_settings(root, {**shown['values'], **values,
                                                  'expected': shown['revision'], 'confirmed': True})

    def test_row_212_new_typed_questions_redraft_the_outline_from_the_saved_scan(self):
        from runner_support import fails
        root = self.start()
        plan = self.view(root)['training_plan']
        self.workers.then('research-result', fails(cost=0.5))
        training_plan.decide(self.engine, root, plan['expected'], 'approve', outline=edited(plan))
        self.assertEqual(self.view(root)['state'], 'failed', 'research stopped after one try')
        saved = self.change(root, research_questions=['Which health check starts the next batch?'])
        self.assertEqual(saved['changed_settings']['research'], 'replanned')
        self.assertIn('saved quick scan', ' '.join(saved['changed_settings']['words']))
        self.engine.act(root, 'retry')
        view = self.view(root)
        self.assertTrue(view['training_plan_pending'])
        self.assertEqual(view['training_plan']['mode'], 'outline')
        self.assertEqual(len(self.workers.of('training-scan')), 1, 'no new scan for new questions')
        listed = [q['text'] for s in view['training_plan']['sections'] for q in s['questions']] \
            + [q['text'] for q in view['training_plan']['separate']]
        self.assertIn('Which health check starts the next batch?', listed)

    def test_row_212_a_new_topic_scans_again_before_research(self):
        root = self.start()      # waiting at the outline: Change settings is open there
        saved = self.change(root, topic='Rolling restarts and blue-green deployments')
        self.assertEqual(saved['changed_settings']['research'], 'replanned')
        self.assertIn('new quick scan', ' '.join(saved['changed_settings']['words']))
        self.assertFalse(outline_first.scanned(root))
        self.engine.act(root, 'retry')
        self.assertEqual(len(self.workers.of('training-scan')), 2)
        self.assertEqual(self.view(root)['training_plan']['mode'], 'outline')

    def test_row_212_a_change_research_does_not_read_keeps_the_approved_outline(self):
        root = self.start()
        plan = self.view(root)['training_plan']
        before = self.view(root)['training_plan_pending']
        saved = self.change(root, time_limit='40 minutes')
        self.assertIn(saved['changed_settings']['research'], ('continues', 'restarted'))
        self.assertTrue(outline_first.scanned(root))
        self.assertEqual(self.view(root)['training_plan_pending'], before)
        self.assertEqual(plan['expected'], training_plan.signature(root, workspace.load(root), self.engine._load(root)))


class OlderTrainingTests(StudioCase):
    """Trainings saved before this flow keep theirs; one stopped before its research was
    accepted moves only by the person's explicit choice."""

    def setUp(self):
        super().setUp()
        self.engine.plan_first = True

    def test_row_213_a_training_past_research_keeps_its_saved_flow(self):
        root = self.start()                      # the topics review after the blueprints
        self.engine.outline_first = True         # a newer runtime picks it up
        self.engine.wake(root)
        view = self.view(root)
        self.assertEqual(self.engine._load(root)['schema'], training_plan.RECORD_SCHEMA)
        self.assertNotIn('mode', view['training_plan'])
        self.assertNotIn('scan', [step['id'] for step in view['steps']])
        self.assertIsNone(view['outline_offer'], 'research is accepted: no move is offered')
        self.assertFalse(self.workers.of('training-scan'))

    def stopped_before_research(self):
        from runner_support import fails
        self.workers.then('research-result', fails(cost=1.25))
        root = self.start()
        self.assertEqual(self.view(root)['state'], 'failed')
        self.engine.outline_first = True
        return root

    def test_row_213_one_stopped_before_research_moves_only_when_chosen(self):
        root = self.stopped_before_research()
        self.engine.wake(root)
        self.assertEqual(self.view(root)['state'], 'failed', 'nothing moves by itself')
        offer = self.view(root)['outline_offer']
        self.assertIn('quick scan', offer['words'])
        self.assertIn('discards the research plan', offer['confirm'])
        self.assertIn('$1.25', offer['confirm'])
        with self.assertRaises(WorkspaceError):
            outline_first.switch(self.engine, root, offer['expected'], False)
        with self.assertRaises(WorkspaceError):
            outline_first.switch(self.engine, root, 'old', True)
        self.assertEqual(self.engine._load(root)['schema'], training_plan.RECORD_SCHEMA)
        view = outline_first.switch(self.engine, root, offer['expected'], True)
        self.assertEqual(view['problem']['label'], 'Continue')
        record = self.engine._load(root)
        self.assertEqual(record['schema'], outline_first.RECORD_SCHEMA)
        self.assertFalse((root / pipeline.PLAN).exists())
        self.assertFalse(self.workers.of('training-scan'), 'nothing starts until Continue')
        self.assertIn('use the outline-first flow', self.log()[-1])
        self.engine.act(root, 'retry')
        view = self.view(root)
        self.assertEqual(view['training_plan']['mode'], 'outline')
        self.assertEqual(len(self.workers.of('training-scan')), 1)
        self.assertIsNone(view['outline_offer'])


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


class ScanCheckTests(StudioCase):
    def check(self, value, documents=('s1',)):
        return outline_first.check_scan(json.dumps(value), {'documents': list(documents)})

    def test_a_good_overview_is_kept_as_it_was_handed_back(self):
        value = {**SCAN, 'documents': [{'source': 's1', 'covers': 'The runbook.'}]}
        problems, ran, _, kept = self.check(value)
        self.assertEqual(problems, [])
        self.assertEqual(json.loads(kept)['sections'][0]['title'], SCAN['sections'][0]['title'])

    def test_what_a_scan_must_say(self):
        one = {**SCAN, 'sections': SCAN['sections'][:1], 'documents': [{'source': 's1', 'covers': 'x'}]}
        self.assertIn('2 to 8 sections', self.check(one)[0][0])
        many = copy.deepcopy(SCAN)
        many['sections'][0]['questions'] = ['Q?'] * 4
        many['documents'] = [{'source': 's1', 'covers': 'x'}]
        self.assertTrue(any('"questions"' in p for p in self.check(many)[0]))
        self.assertTrue(any('s1 is missing' in p for p in self.check(SCAN)[0]))
        stray = {**SCAN, 'documents': [{'source': 's9', 'covers': 'x'}]}
        self.assertTrue(any('supplied source' in p for p in self.check(stray)[0]))
        extra = {**SCAN, 'facts': [], 'documents': []}
        self.assertTrue(any('Leave out facts' in p for p in self.check(extra, ())[0]))
        self.assertIn('not valid JSON', outline_first.check_scan('{', {})[0][0])

    def test_an_edited_outline_is_checked(self):
        good = {'sections': [{'title': 'One', 'objectives': [], 'questions': ['Why?']}]}
        self.assertEqual(outline_first.edited(good)['sections'][0]['questions'], [{'text': 'Why?', 'from': 'you'}])
        for bad in ({'sections': []}, {'sections': [{'title': '', 'questions': ['Why?']}]},
                    {'sections': [{'title': 'One', 'questions': []}]},
                    {'sections': [{'title': 'One', 'questions': ['Q?'] * 6}]},
                    {'sections': [{'title': 'x' * 121, 'questions': ['Why?']}]},
                    {'sections': [{'title': 'One', 'questions': ['Why?']}], 'separate': ['Q?'] * 9}):
            with self.subTest(bad=bad), self.assertRaises(WorkspaceError):
                outline_first.edited(bad)


from test_runner_deck import PageCase  # noqa: E402  the page, asked as the browser asks it


class OutlinePageTests(PageCase):
    def setUp(self):
        super().setUp()
        self.engine.plan_first = self.engine.outline_first = True

    def test_row_210_the_page_approves_the_exact_outline_version_with_its_edits(self):
        root = self.start()
        plan = self.view(root)['training_plan']
        sent = edited(plan)
        sent['sections'][0]['title'] = 'Batches'
        body = {'path': str(root), 'expected': plan['expected'], 'decision': 'approve', 'outline': sent}
        self.assertEqual(self.ask('POST', '/api/training-plan', body, token=False)[0], 403)
        self.post('training-plan', {**body, 'expected': 'old'}, expect=409)
        self.assertFalse(self.workers.of('research-result'))
        result = self.post('training-plan', body)
        self.assertFalse(result['training_plan_pending'])
        self.assertEqual(outline_first.read(root)['sections'][0]['title'], 'Batches')
        self.assertTrue(self.workers.of('research-result'))
        self.post('training-plan', body, expect=409)

    def test_row_213_the_page_switches_an_older_stopped_training_only_when_confirmed(self):
        from runner_support import fails
        self.engine.outline_first = False
        self.workers.then('research-result', fails(cost=0.4))
        root = self.start()
        self.engine.outline_first = True
        offer = self.view(root)['outline_offer']
        body = {'path': str(root), 'expected': offer['expected']}
        self.assertEqual(self.ask('POST', '/api/outline-first', {**body, 'confirmed': True}, token=False)[0], 403)
        self.post('outline-first', body, expect=409)
        result = self.post('outline-first', {**body, 'confirmed': True})
        self.assertEqual(result['problem']['label'], 'Continue')
        self.assertTrue(training_plan.outlined(self.engine._load(root)))
