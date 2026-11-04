"""Approved source-scoped updates through the real pinned collection protocol."""
import copy
import json
import os
import unittest
import marketing_studio
from studio_core import research_impact as impact, research_sections as sections, research_session as session
import test_research_sections as fixtures


@unittest.skipUnless(os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME'), 'Pinned helper required.')
class ScopedWorkflowTests(unittest.TestCase):
    setUp = fixtures.SectionWorkflowTests.setUp
    invoke = fixtures.SectionWorkflowTests.invoke

    def run_scope(self, task, sources, intent=None):
        snap = impact.snapshot(self.root, self.record, sources, task['planning_questions'])
        return self.workflow.run(self.root, task, self.invoke, sources, progress=self.states.append,
            input_snapshot=snap, impact=intent, section_policy=sections.pin(self.workflow.runtime),
            section_context={'scope_identity': snap['global'], 'checking': 'synthetic'})

    def prepare(self):
        self.task['planning_questions'] = self.task['planning_questions'][:2]
        self.record = {'section_synthesis': sections.pin(), 'brief': {'audience': 'Synthetic learners'}}
        initial = []
        if getattr(self, 'selected_sources', False):
            self.task['source_mode'] = 'selected'
            initial = [{'file': 'source-a.txt', 'path': self.capture, 'original_path': self.capture,
                'text': self.capture.read_text(), 'permission': 'selected', 'title': 'Section A source', 'origin': 'source-a.txt'}]
        self.run_scope(self.task, initial)
        path = self.root / 'source-b.txt'; path.write_text(fixtures.cases.TEXT + '\nSynthetic new evidence relevant only to section B.')
        return initial + [{'file': 'source-b.txt', 'path': path, 'text': path.read_text(), 'permission': 'selected' if initial else 'public', **({'original_path': path} if initial else {}),
            'title': 'Section B source', 'origin': 'https://example.invalid/section-b'}]

    def test_added_source_for_b_keeps_a_evidence_and_contribution_then_checks_whole(self):
        sources = self.prepare()
        plan = impact.preview(self.root, self.record, sources, self.task['planning_questions'])
        self.assertEqual([row['kind'] for row in plan['changed_inputs']], ['added'])
        self.assertFalse(plan['broad_required'])
        intent = impact.confirm(self.root, self.record, sources, self.task['planning_questions'],
            {'expected': plan['expected'], 'sections': ['question-1']})
        task = {**copy.deepcopy(self.task), 'requested_changes': {'refresh': True, 'note': 'Approved section B source update'}}
        before = len(self.calls), len(self.section_calls)
        facts, _ = self.run_scope(task, sources, intent)
        self.assertTrue(facts['review']['accepted'])
        self.assertEqual(self.section_calls[before[1]:], ['question-1'])
        self.assertEqual([phase for phase, _ in self.calls[before[0]:]], ['investigate', 'final', 'review'])

    def test_permission_or_audience_change_requires_every_section_and_stale_preview_refuses(self):
        sources = self.prepare()
        plan = impact.preview(self.root, self.record, sources, self.task['planning_questions'])
        self.record['brief']['audience'] = 'A different audience'
        with self.assertRaisesRegex(ValueError, 'current affected-work'):
            impact.confirm(self.root, self.record, sources, self.task['planning_questions'], {'expected': plan['expected'], 'sections': ['question-1']})
        new = impact.preview(self.root, self.record, sources, self.task['planning_questions'])
        self.assertTrue(new['broad_required'])
        with self.assertRaisesRegex(ValueError, 'required section'):
            impact.confirm(self.root, self.record, sources, self.task['planning_questions'], {'expected': new['expected'], 'sections': ['question-1']})

    def test_selected_originals_retain_a_without_collecting_it_again(self):
        self.selected_sources = True
        self.test_added_source_for_b_keeps_a_evidence_and_contribution_then_checks_whole()

    def test_changed_original_metadata_or_permission_requires_broad_scope(self):
        self.selected_sources = True
        sources = self.prepare()
        sources[0]['permission'] = 'public'
        plan = impact.preview(self.root, self.record, sources, self.task['planning_questions'])
        self.assertTrue(plan['broad_required'])
        self.assertEqual(plan['changed_inputs'][0]['kind'], 'changed')

    def test_changed_actual_task_after_preview_starts_no_investigation(self):
        sources = self.prepare()
        plan = impact.preview(self.root, self.record, sources, self.task['planning_questions'])
        intent = impact.confirm(self.root, self.record, sources, self.task['planning_questions'], {'expected': plan['expected'], 'sections': ['question-1']})
        before = len(self.calls)
        pointer = session.case_for(self.root)
        task = {**self.task, 'audience': 'Changed after preview'}
        with self.assertRaisesRegex(ValueError, 'scope or audience changed'):
            self.run_scope(task, sources, intent)
        self.assertEqual(len(self.calls), before)
        self.assertEqual(session.case_for(self.root), pointer)
