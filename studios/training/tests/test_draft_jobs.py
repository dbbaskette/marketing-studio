"""Desk changes use scripted workers and disposable trainings; no provider is started."""
import importlib.util
import json
from unittest import mock

import helpers  # noqa: F401
import home
import workspace
from test_runner_deck import DeckCase
from workspace import WorkspaceError

from runner import drafts, page, worker_tools


class DraftJobTests(DeckCase):
    NAME = 'document@101'

    def desk(self, **changes):
        self.assertIsNotNone(importlib.util.find_spec('runner.draft_jobs'),
                             'Training Studio needs its desk job queue')
        from runner import draft_jobs
        self.jobs = draft_jobs
        root = self.begin(flow='desk', levels=['101'], **changes)
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])
        return root

    def saved_queue_desk(self, ident):
        # Exercise a finished, explicitly saved queue-format training on the desk.
        from stand_ins.research import saved_queue
        from runner import draft_jobs
        self.research = saved_queue()
        self.jobs = draft_jobs
        self.workers.plan = {**self.workers.plan, 'items': [
            *self.workers.plan['items'], {'id': ident, 'question': 'Extra finding'}]}
        root = self.saved_begin(levels=['101'])
        self.to_end(root)
        self.engine.outline(root, '101', 'approve')
        self.to_end(root)
        self.assertEqual(self.state(root), 'done', self.view(root))
        self.engine.open_on_desk(root)
        self.assertNotIn('research_contract', workspace.load(root))
        return root

    def add_queue_finding(self, root, ident):
        record = workspace.research_record(root)
        source = root / 'extra-source.txt'
        source.write_text('A supported fact.', encoding='utf-8')
        self.research.record(root, record['run'], ident, {
            'status': 'supported', 'summary': 'A supported fact.', 'limits': 'Synthetic example.',
            'evidence': [{'file': 'extra-source.txt', 'title': 'Extra source',
                          'origin': 'https://example.invalid/extra', 'date': '2026-01-01',
                          'locator': 'Full text',
                          'quote': 'A supported fact.', 'start': 0}]})

    def card(self, root, name=NAME):
        return self.engine.draft_card(root, name)

    def ask(self, root, route='note', **sent):
        response = page.RunnerPage(8765, self.engine).write('/api/drafts/' + route,
            {'path': str(root), 'name': self.NAME, **sent})
        return json.loads(response[2])

    def queue(self, root, **changes):
        card = self.card(root)
        return self.ask(root, part=card['sections'][0]['id'], seen=card['revision'],
                        note='Shorter.', **changes)

    def last(self, root):
        return self.record(root)['drafts']['jobs'][-1]

    def saves(self, root):
        return [e for e in workspace.load(root)['events'] if e['event'] == 'save'
                and e['artifact'] == self.NAME]

    def test_row_142_a_section_note_changes_only_its_section(self):
        root = self.desk()
        before = self.card(root)
        self.queue(root)
        after = self.card(root)
        self.assertEqual(after['sections'][0]['text'], before['sections'][0]['text'] + ' Revised.')
        self.assertEqual(after['sections'][1:], before['sections'][1:])
        self.assertEqual(self.saves(root)[-1]['via'], 'rewrite')
        history = self.engine.draft_versions(root, self.NAME, before['sections'][0]['id'])
        self.assertEqual(history['versions'][0]['text'], before['sections'][0]['text'])
        self.assertTrue(self.last(root).get('applied'), (self.last(root), self.record(root)['problem']))

    def test_opening_result_is_saved_as_validated_for_guide_and_brief(self):
        root = self.desk()
        for name in (self.NAME, 'brief@101'):
            with self.subTest(name=name):
                before = self.card(root, name)
                original = before['opening']
                self.assertTrue(original.startswith('# '))
                self.workers.then('part', lambda tools, job: tools.submit_part(
                    tools.job['artifacts']['part']['before']))
                self.ask(root, name=name, part='opening', seen=before['revision'])
                self.assertTrue(self.last(root)['applied'], self.last(root))
                self.assertEqual(self.card(root, name)['opening'], original)

    def test_row_163_stop_after_queue_selection_prevents_worker_start(self):
        root = self.desk()
        with mock.patch.object(self.engine, 'wake'):
            self.queue(root)
        original = self.engine._draft_job
        def stop_before_lock(root, run, job):
            self.engine.stop_draft(root, job['id'])
            return original(root, run, job)
        with mock.patch.object(self.engine, '_draft_job', side_effect=stop_before_lock):
            self.engine.wake(root)
        self.assertEqual(self.last(root)['status'], 'stopped')
        self.assertEqual(self.workers.of('part'), [])
        self.assertFalse(any(e.get('via') == 'rewrite' for e in self.saves(root)))

    def test_a_result_for_a_changed_part_is_set_aside(self):
        root = self.desk()
        def typing(tools, job):
            card = self.card(root)
            self.engine.draft_save(root, self.NAME, card['sections'][0]['id'],
                                   card['revision'], 'Person typed these words.', 'cd12')
            return self.workers.part(tools, job)
        self.workers.then('part', typing)
        self.queue(root)
        self.assertEqual(self.card(root)['sections'][0]['text'], 'Person typed these words.')
        self.assertEqual(self.last(root)['problem'],
                         'The draft changed while this was being written. Run it again.')
        self.assertFalse(any(e.get('via') == 'rewrite' for e in self.saves(root)))
        self.assertNotIn(root, self.engine.pending_commit)
        self.assertIn('Person typed these words.', self.git('show', 'HEAD:' + str(
            (root / '101/document.md').relative_to(self.space.repo))))

    def test_one_desk_job_at_a_time_and_retry_route(self):
        root = self.desk()
        with mock.patch.object(self.engine, 'wake'):
            self.queue(root)
            with self.assertRaisesRegex(WorkspaceError, 'A change is already being made'):
                self.queue(root)
            job = self.last(root)
            self.ask(root, 'stop', job=job['id'])
            self.assertEqual(self.last(root)['status'], 'stopped')
            self.ask(root, 'retry', job=job['id'])
            self.assertEqual(self.last(root)['status'], 'queued')
        self.engine.wake(root)
        self.assertTrue(self.last(root).get('applied'), (self.last(root), self.record(root)['problem']))

    def test_row_165_write_whole_guide_uses_one_document_job(self):
        root = self.desk()
        before = self.card(root)
        count = len(self.workers.of('document'))
        self.ask(root, 'write-whole', seen=before['revision'])
        self.assertEqual(len(self.workers.of('document')), count + 1)
        self.assertEqual(self.last(root)['part'], 'whole')
        self.assertTrue(self.last(root)['applied'])
        self.assertEqual(self.saves(root)[-1]['via'], 'rewrite')
        self.assertNotIn('sections', self.last(root))

    def test_the_whole_guide_note_goes_in_order_and_stops(self):
        root = self.desk()
        before = self.card(root)
        def stopping(tools, job):
            answer = self.workers.part(tools, job)
            self.engine.stop_draft(root, self.last(root)['id'])
            return answer
        self.workers.then('part', stopping)
        self.ask(root, 'revise', note='Tighten.', seen=before['revision'])
        after = self.card(root)
        self.assertEqual(after['sections'][0]['text'], before['sections'][0]['text'] + ' Revised.')
        self.assertEqual(after['sections'][1:], before['sections'][1:])
        self.assertEqual(self.last(root)['status'], 'stopped')
        self.assertEqual(self.saves(root)[-1]['via'], 'revise-all')
        self.assertEqual(len(self.last(root)['done']), 1)

    def test_a_selection_replaces_only_the_passage(self):
        root = self.desk()
        card = self.card(root)
        part = card['sections'][0]['id']
        self.engine.draft_save(root, self.NAME, part, card['revision'], 'one phrase; one phrase.')
        self.workers.then('part', lambda tools, job: tools.submit_part('short'))
        card = self.card(root)
        self.ask(root, 'selection', part=part, seen=card['revision'], action='shorten',
                 passage='one phrase', start=12)
        self.assertEqual(self.card(root)['sections'][0]['text'], 'one phrase; short.')
        self.assertEqual(self.saves(root)[-1]['via'], 'selection')

    def test_browser_selection_after_non_bmp_replaces_the_chosen_repeat(self):
        root = self.desk()
        card = self.card(root)
        part = card['sections'][0]['id']
        self.engine.draft_save(root, self.NAME, part, card['revision'],
                               '😀 one phrase; one phrase [1].')
        self.workers.then('part', lambda tools, job: tools.submit_part('short'))
        card = self.card(root)
        self.ask(root, 'selection', part=part, seen=card['revision'], action='shorten',
                 passage='one phrase', start=15)
        self.assertEqual(self.card(root)['sections'][0]['text'], '😀 one phrase; short [1].')
        self.assertEqual(self.last(root)['start'], 14)

    def test_browser_selection_rejects_offsets_inside_or_past_non_bmp(self):
        root = self.desk()
        card = self.card(root)
        part = card['sections'][0]['id']
        self.engine.draft_save(root, self.NAME, part, card['revision'], '😀 phrase [1].')
        card = self.card(root)
        for start in (1, 2, 99):
            with self.subTest(start=start), self.assertRaisesRegex(
                    WorkspaceError, 'Select the passage again'):
                self.ask(root, 'selection', part=part, seen=card['revision'], action='shorten',
                         passage='phrase', start=start)
        self.assertEqual(self.record(root)['drafts']['jobs'], [])

    def test_selection_does_not_follow_a_passage_in_a_changed_part(self):
        root = self.desk()
        card = self.card(root)
        part = card['sections'][0]['id']
        def typing(tools, job):
            current = self.card(root)
            self.engine.draft_save(root, self.NAME, part, current['revision'],
                                   current['sections'][0]['text'] + ' typed')
            return tools.submit_part('short')
        self.workers.then('part', typing)
        self.ask(root, 'selection', part=part, seen=card['revision'], action='shorten',
                 passage=card['sections'][0]['text'], start=0)
        self.assertTrue(self.card(root)['sections'][0]['text'].endswith(' typed'))
        self.assertFalse(self.last(root)['applied'])

    def test_sources_are_never_queued_and_old_forms_are_refused(self):
        root = self.desk()
        card = self.card(root)
        source = next(s for s in card['sections'] if s.get('locked'))
        with self.assertRaisesRegex(WorkspaceError, 'Sources'):
            self.ask(root, part=source['id'], seen=card['revision'])
        with self.assertRaisesRegex(WorkspaceError, 'changed since you opened'):
            self.ask(root, part=card['sections'][0]['id'], seen=-1)
        self.assertEqual(self.record(root)['drafts']['jobs'], [])

    def test_submit_part_keeps_sources_and_headings(self):
        root = self.desk()
        card = self.card(root, 'brief@101')
        def tries(tools, job):
            spec = tools.job['artifacts']['part']
            bad = tools.submit_part('## 8. Sources\n\n1. invented')
            self.assertFalse(bad[0])
            self.assertIn('Leave Sources as it is', bad[1])
            bad = tools.submit_part('## 1. Different\n\nwords')
            self.assertFalse(bad[0])
            self.assertIn("Keep this section's heading exactly", bad[1])
            self.assertEqual(home.read_json(tools.folder / 'state.json', {})['submissions']['part'], 2)
            return tools.submit_part(spec['before'])
        self.workers.then('part', tries)
        self.ask(root, name='brief@101', part=card['sections'][0]['id'], seen=card['revision'])
        self.assertTrue(self.last(root).get('applied'), (self.last(root), self.record(root)['problem']))

    def test_a_dropped_reference_is_named(self):
        root = self.desk()
        card = self.card(root)
        self.workers.then('part', lambda tools, job: tools.submit_part(
            tools.job['artifacts']['part']['before'].replace('[2]', '')))
        self.ask(root, part=card['sections'][2]['id'], seen=card['revision'])
        self.assertEqual(self.last(root)['dropped'], [2])
        self.assertIn('This change dropped reference [2].', self.last(root)['says'])
        self.assertIn('This change dropped reference [2].', self.card(root)['says'])
        import checks
        self.assertIn('Sources entry 2 is not cited.', checks.citations(
            (root / '101/document.md').read_text(), 'document')['problems'])

    def test_unlocked_text_identical_to_sources_can_be_rewritten(self):
        root = self.desk()
        card = self.card(root)
        source = next(s for s in card['sections'] if s.get('locked'))
        self.engine.draft_save(root, self.NAME, card['sections'][0]['id'], card['revision'], source['text'])
        self.workers.then('part', lambda tools, job: tools.submit_part(
            tools.job['artifacts']['part']['before'] + ' Revised [1].'))
        self.queue(root)
        self.assertTrue(self.last(root).get('applied'), (self.last(root), self.record(root)['problem']))

    def test_added_claim_checks_use_intake_names_and_allow_ordinary_capitals(self):
        self.assertTrue(hasattr(worker_tools, 'check_part'), 'Part submissions need full checks')
        from runner import draft_jobs
        root = self.desk()
        card = self.card(root)
        with self.engine.files:
            job = {'name': self.NAME, 'part': card['sections'][0]['id'], 'kind': 'section',
                   'note': '', 'basis': ''}
            work = draft_jobs.work_for(root, self.engine._survey(root, self.record(root)), job)
        spec = {**work.prepared['artifacts']['part'], 'names': ['Widget Suite']}
        problems, outcomes, warnings, kept = worker_tools.check_part('Use the Next button.', spec)
        self.assertFalse(any('claim with no reference' in p for p in problems), problems)
        problems, *_ = worker_tools.check_part('Widget Suite improves capacity.', spec)
        self.assertTrue(any('claim with no reference' in p for p in problems), problems)

    def test_a_desk_job_waits_for_the_starts_step(self):
        self.assertIsNotNone(importlib.util.find_spec('runner.draft_jobs'))
        from runner import draft_jobs
        def during_brief(tools, job):
            self.queue(root_box[0])
            queued = self.card(root_box[0])
            self.assertEqual(queued['working']['says'],
                'Next, after writing the level 101 brief.')
            self.assertEqual(queued['jobs'][-1]['status'], 'queued')
            with self.assertRaisesRegex(WorkspaceError, 'Being used to write the level 101 brief'):
                self.engine.draft_save(root_box[0], 'blueprint@101', 'opening', 1, 'overwrite')
            return self.workers.brief(tools, job)
        with mock.patch.object(self.engine, 'wake'):
            root = self.begin(flow='desk', levels=['101'])
        root_box = [root]
        self.workers.then('brief', during_brief)
        self.engine.wake(root)
        self.assertTrue(self.record(root)['drafts']['jobs'][-1].get('applied'), self.record(root)['problem'])
        self.assertEqual(len(self.workers.of('part')), 1)
        self.assertEqual(draft_jobs.NEXT, 'Next, after {doing}.')

    def test_a_cited_finding_joins_sources(self):
        root = self.saved_queue_desk('added')
        self.add_queue_finding(root, 'added')
        card = self.card(root)
        # The covers objective's module names this supported finding.
        blueprint = root / '101/blueprint.md'
        blueprint.write_text(blueprint.read_text().replace('[R:availability]', '[R:availability] [R:added]'))
        def cite(tools, job):
            findings = tools.job['artifacts']['part']['findings']
            self.assertEqual(next(f['number'] for f in findings if f['id'] == 'added'), 4)
            bad = tools.submit_part('Extra fact [99].')
            self.assertFalse(bad[0])
            self.assertIn('Cite only the references you were given: [99] is not one of them.', bad[1])
            return tools.submit_part(tools.job['artifacts']['part']['before'] + ' Extra fact [4].')
        self.workers.then('part', cite)
        self.ask(root, part=card['sections'][1]['id'], seen=card['revision'])
        self.assertTrue(self.last(root).get('applied'), (self.last(root), self.record(root)['problem']))
        text = (root / '101/document.md').read_text()
        self.assertIn('4. Extra finding,', text)
        self.assertIn('https://example.invalid/extra', text)
        import checks
        self.assertEqual(checks.citations(text, 'document')['status'], 'passed')
        # A later section job must reuse the number the runner just added.
        reused = []
        def reuse(tools, job):
            reused.extend(tools.job['artifacts']['part']['findings'])
            return tools.submit_part(tools.job['artifacts']['part']['before'] + ' Another fact [4].')
        self.workers.then('part', reuse)
        card = self.card(root)
        self.ask(root, part=card['sections'][1]['id'], seen=card['revision'])
        self.assertTrue(any(f['id'] == 'added' for f in reused), (reused, self.last(root)))
        self.assertEqual(next(f['number'] for f in reused if f['id'] == 'added'), 4)
        self.assertTrue(self.last(root)['applied'], self.last(root))
        source = next(s for s in self.card(root)['sections'] if s.get('locked'))
        self.assertEqual(source['text'].count('Extra finding,'), 1)

    def test_notes_after_the_first_line_are_hidden_and_preserved(self):
        text = '# Guide\n\n## First\n\nA paragraph.\n\n<!-- covers: O1 K1.1 -->\n\nAnother paragraph.\n\n## Sources\n\n1. A source\n'
        codec = drafts.GuideCodec()
        draft = codec.split(text)
        self.assertEqual(draft['sections'][0]['covers'], ['O1', 'K1.1'])
        self.assertNotIn('<!-- covers', draft['sections'][0]['text'])
        self.assertEqual(codec.join(draft), text)
        brief_text = (helpers.EXAMPLES / 'product-brief.md').read_text()
        brief_text = brief_text.replace('<!-- findings: availability -->', 'Extra paragraph.\n\n<!-- findings: availability -->')
        codec = drafts.BriefCodec()
        draft = codec.split(brief_text)
        self.assertIn('availability', draft['sections'][1]['findings'])
        self.assertEqual(codec.join(draft), brief_text)

    def test_a_file_with_an_unclosed_fence_cannot_hide_sources_from_a_worker(self):
        root = self.desk()
        file = root / '101/document.md'
        file.write_text(file.read_text().replace('## Why this matters', '```\n\n## Why this matters'))
        with self.assertRaisesRegex(WorkspaceError, 'Close the code block'):
            card = self.card(root)
            self.ask(root, part='opening', seen=card['revision'])
        self.assertEqual(self.workers.of('part'), [])

    def test_whole_plan_and_practice_notes_use_their_existing_checks(self):
        root = self.desk(yoodli=True)
        for name in ('blueprint@101', 'scenario:objection@101', 'yoodli:objection@101'):
            # Use the plan's real scenario ID, rather than guessing the fixture's ID.
            if name.startswith('scenario:'):
                name = next(n for n in workspace.artifact_names(root, workspace.load(root)) if n.startswith('scenario:'))
            elif name.startswith('yoodli:'):
                name = next(n for n in workspace.artifact_names(root, workspace.load(root)) if n.startswith('yoodli:'))
            with self.subTest(name=name):
                file = root / workspace.artifact(root, workspace.load(root), name)['file']
                self.ask(root, 'note', name=name, note='Keep the shape.', seen=workspace.sha256_file(file))
                self.assertTrue(self.last(root).get('applied'), (self.last(root), self.record(root)['problem']))
                event = [e for e in workspace.load(root)['events'] if e['event'] == 'save' and e['artifact'] == name][-1]
                self.assertEqual(event['via'], 'rewrite')

    def test_reviewed_synthesis_findings_keep_their_context_and_source(self):
        from synthesis_fixture import published_bundle
        root = self.desk()
        session = workspace.load(root)
        session['research_contract'] = {'schema': 2}
        workspace.store(root, session)
        published_bundle(root / 'research', findings=[{
            'id': 'new-source', 'title': 'Synthetic finding',
            'summary': {'text': 'A supported condition.', 'refs': ['fact-new']},
            'support': ['fact-new'], 'conditions': [{'text': 'Within the example.'}],
            'counter': [], 'gaps': [{'text': 'Unmeasured elsewhere.'}]}],
            evidence=[{'id': 'fact-new', 'citations': [{'source': 'source-new'}]}],
            sources=[{'id': 'source-new', 'origin': 'https://example.invalid/source',
                      'title': 'Synthetic source', 'date': '2026-01-01'}],
            review={'accepted': True, 'digest': 'synthetic-digest',
                    'findings': [{'id': 'new-source', 'verdict': 'supported'}]})
        codec = drafts.GuideCodec()
        draft = codec.split((root / '101/document.md').read_text())
        section = draft['sections'][1]
        blueprint = (root / '101/blueprint.md').read_text().replace(
            '[R:availability]', '[R:availability] [R:new-source]')
        findings, modules = self.jobs.references(root, session, draft, section, blueprint)
        handed = next((f for f in findings if f['id'] == 'new-source'), None)
        self.assertIsNotNone(handed, 'A reviewed finding must be handed to the part worker')
        self.assertEqual(handed['summary'], 'A supported condition.')
        self.assertEqual(handed['origin'], 'https://example.invalid/source')
        self.assertEqual(handed['conditions'], [{'text': 'Within the example.'}])
        self.assertEqual(handed['gaps'], [{'text': 'Unmeasured elsewhere.'}])

    def test_a_stopped_single_section_finishes_then_settles(self):
        root = self.desk()
        def stopping(tools, job):
            self.engine.stop_draft(root, self.last(root)['id'])
            return self.workers.part(tools, job)
        self.workers.then('part', stopping)
        self.queue(root)
        self.assertTrue(self.last(root)['applied'])
        self.assertEqual(self.last(root)['status'], 'stopped')

    def test_whole_file_cards_save_history_and_restore(self):
        root = self.desk(yoodli=True)
        for name in ('scenario:main@101', 'yoodli:main@101'):
            with self.subTest(name=name):
                card = self.card(root, name)
                original = card['opening']
                self.assertTrue(card['whole'])
                unchanged = self.engine.draft_save(root, name, 'opening', card['revision'],
                                                   original, 'same-text')
                self.assertEqual(unchanged['revision'], card['revision'])
                saved = self.engine.draft_save(root, name, 'opening', card['revision'],
                                               original + '\n\nA note.', 'whole-session')
                self.assertIn('A note.', saved['opening'])
                versions = self.engine.draft_versions(root, name, 'opening')['versions']
                self.assertEqual(versions[0]['text'].strip(), original.strip())
                restored = self.engine.draft_restore(root, name, 'opening', saved['revision'], 0)
                self.assertEqual(restored['opening'], original)
                if name.startswith('yoodli'):
                    self.assertTrue(restored['fields'])
                    context = next(f for f in restored['fields'] if f['heading'] == ['Context'])
                    self.assertEqual(context['limit'], 10000)

    def test_row_164_own_scenario_layout_uses_existing_words_path(self):
        root = self.desk()
        name = 'scenario:main@101'
        with self.engine.files:
            run = self.record(root)
            run['drafted'].remove(name)
            self.engine._store(root, run)
            self.engine._commit(root, 'keep the person written scenario')
        card = self.card(root, name)
        self.assertTrue(card['own'])
        with mock.patch.object(self.engine, 'wake'):
            self.ask(root, route='layout', name=name, note='Keep every word.', seen=card['seen'])
        work = self.jobs.work_for(root, self.engine._survey(root, self.record(root)), self.last(root))
        self.assertIn('Keep their wording', work.task)
        self.assertIn('Keep every word.', work.task)
        self.assertIn(card['opening'].strip(), work.task)

    def test_person_written_scenarios_are_never_rewritten(self):
        root = self.desk()
        name = next(n for n in workspace.artifact_names(root, workspace.load(root)) if n.startswith('scenario:'))
        with self.engine.files:
            run = self.record(root)
            run['drafted'].remove(name)
            self.engine._store(root, run)
            self.engine._commit(root, 'keep the person written scenario')
        file = root / workspace.artifact(root, workspace.load(root), name)['file']
        before = file.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, 'This scenario is your own'):
            self.ask(root, name=name, note='Rewrite it.', seen=workspace.sha256_file(file))
        self.assertEqual(file.read_bytes(), before)
        self.assertEqual(self.record(root)['drafts']['jobs'], [])

    def test_editing_shorter_text_keeps_an_embedded_covers_note(self):
        codec = drafts.GuideCodec()
        draft = codec.split('# Guide\n\n## First\n\nBefore.\n\n<!-- covers: O1 -->\n\nAfter.\n')
        codec.set_text(draft, draft['sections'][0]['id'], 'Shorter.')
        again = codec.split(codec.join(draft))
        self.assertEqual(again['sections'][0]['covers'], ['O1'])
        self.assertEqual(again['sections'][0]['text'], 'Shorter.')

    def test_a_worker_exception_leaves_a_retryable_job(self):
        root = self.desk()
        def broken(tools, job):
            raise RuntimeError('Synthetic worker failure')
        self.workers.then('part', broken)
        self.queue(root)
        self.assertEqual(self.last(root)['status'], 'failed')
        self.assertIn('Synthetic worker failure', self.last(root)['problem'])
        self.assertIsNone(self.record(root)['problem'], 'a desk failure does not stop the start')
        self.ask(root, 'retry', job=self.last(root)['id'])
        self.assertTrue(self.last(root)['applied'])

    def test_restart_settles_a_desk_job_that_cannot_still_be_running(self):
        root = self.desk()
        with mock.patch.object(self.engine, 'wake'):
            self.queue(root)
        with self.engine.files:
            record = self.record(root)
            record['drafts']['jobs'][-1]['status'] = 'working'
            self.engine._store(root, record)
            self.engine._commit(root, 'synthetic interrupted change')
        self.engine._tidy()
        self.assertEqual(self.last(root)['status'], 'stopped')
        self.ask(root, 'retry', job=self.last(root)['id'])
        self.assertTrue(self.last(root)['applied'])

    def test_job_estimates_use_recent_times_and_record_success(self):
        root = self.desk()
        with mock.patch.object(self.engine, 'wake'):
            self.queue(root)
            self.assertEqual(self.last(root)['minutes'], 1)
            self.ask(root, 'stop', job=self.last(root)['id'])
            home.write_json(drafts.times(), {'draft:section': [180, 240, 300]})
            self.queue(root)
            self.assertEqual(self.last(root)['minutes'], 4)
        self.engine.wake(root)
        self.assertEqual(len(home.read_json(drafts.times(), {})['draft:section']), 4)

    def test_part_jobs_validate_names_from_the_actual_intake(self):
        root = self.desk()
        file = root / 'intake.md'
        file.write_text(file.read_text() + '\n## Products\n\nWidget Suite\n')
        def claim(tools, job):
            self.assertIn('Widget Suite', tools.job['artifacts']['part']['names'])
            self.assertEqual({entry['name'] for entry in tools.offered()},
                             {'list_inputs', 'read_input', 'submit_part'})
            bad = tools.submit_part('Widget Suite improves capacity.')
            self.assertFalse(bad[0])
            self.assertIn('A claim with no reference', bad[1])
            return tools.submit_part('Widget Suite improves capacity [1].')
        self.workers.then('part', claim)
        self.queue(root)
        self.assertTrue(self.last(root)['applied'])
        self.assertEqual(self.card(root)['sections'][0]['text'],
                         'Widget Suite improves capacity [1].')

    def test_a_fact_guard_is_kept_with_the_landed_change(self):
        root = self.desk()
        self.workers.then('part', lambda tools, job: tools.submit_part('Wait 40 seconds [1].'))
        self.queue(root)
        self.assertTrue(self.last(root)['applied'])
        self.assertIn('changes a number', self.last(root)['checks'])

    def change_plan(self, root):
        file = root / '101/blueprint.md'
        text = file.read_text()
        line = next(line for line in text.splitlines() if line.startswith('### O2 '))
        file.write_text(text.replace(line, line.replace(' [', ' updated [')))
        workspace.save(root, 'blueprint@101', edit=True, via='save')
        workspace.accept_desk(root, 'blueprint@101')

    def test_an_update_from_the_plan_keeps_the_person_s_edits(self):
        root = self.desk()
        card = self.card(root)
        part = card['sections'][0]
        self.engine.draft_save(root, self.NAME, part['id'], card['revision'], 'Person typed this [1].')
        self.change_plan(root)
        def update(tools, job):
            self.assertIn('plan change', [item['name'] for item in tools.job['inputs']])
            spec = tools.job['artifacts']['document']
            self.assertEqual(spec['untouched'][part['heading']], 'Person typed this [1].')
            result = tools.submit_artifact('document', (root / '101/document.md').read_text())
            self.assertTrue(result[0], result[1])
            tools.submit_review('The guide keeps the sections that still fit.')
        self.workers.then('document', update)
        self.engine.update(root, self.NAME)
        self.assertIsNone(self.record(root)['problem'], self.record(root)['problem'])
        self.assertEqual(self.card(root)['sections'][0]['text'], 'Person typed this [1].')
        self.assertEqual(self.saves(root)[-1]['via'], 'update')

    def test_an_untouched_section_that_changed_is_handed_back(self):
        text = (helpers.EXAMPLES / 'document.md').read_text()
        section = drafts.GuideCodec().split(text)['sections'][0]
        problems, *_ = worker_tools.check_document(text, {'untouched': {section['heading']: 'Different'}})
        self.assertIn(f'Section "{section["heading"]}" is not touched by the plan change. Copy it exactly.', problems)
        brief = (helpers.EXAMPLES / 'product-brief.md').read_text()
        brief_section = drafts.BriefCodec().split(brief)['sections'][0]
        problems, *_ = worker_tools.check_brief(brief, {'untouched': {brief_section['heading']: 'Different'}})
        self.assertIn(f'Section "{brief_section["heading"]}" is not touched by the plan change. Copy it exactly.', problems)

    def test_touched_recognizes_objectives_and_their_key_points(self):
        draft = {'sections': [{'id': 'one', 'covers': ['K2.1']},
                              {'id': 'two', 'covers': ['O2']},
                              {'id': 'three', 'covers': ['K1.2']}]}
        self.assertEqual(drafts.touched(draft, ['O2']), ['one', 'two'])


    def test_the_update_preview_names_the_sections_and_the_price(self):
        root = self.desk()
        self.change_plan(root)
        preview = drafts.update_preview(root, self.NAME)
        self.assertIn('When capacity holds', preview['parts'])
        response = page.RunnerPage(8765, self.engine).read(
            '/api/drafts/update-preview', lambda key: {'path': str(root), 'name': self.NAME}[key])
        self.assertEqual(json.loads(response[2]), preview)
        self.assertTrue(preview['price'].startswith('Drawn again:'))
        run = self.record(root)
        run['steps'].pop(self.NAME, None)
        home.write_json(root / drafts.RECORD, run)
        self.assertEqual(drafts.update_preview(root, self.NAME)['price'],
                         'This computer has no record yet of what it costs.')

    def test_update_hands_back_unknown_references_in_changed_sections(self):
        root = self.desk()
        self.change_plan(root)
        before = (root / '101/document.md').read_text()
        def worker(tools, job):
            bad = before.replace('## When capacity holds', '## When capacity holds')
            bad = bad.replace('<!-- covers: O2 K1.2 -->', '<!-- covers: O2 K1.2 -->\n\nInvented fact [999].')
            bad += '\n999. Invented source\n'
            result = tools.submit_artifact('document', bad)
            self.assertFalse(result[0], result)
            self.assertIn('[999] is not one of them', result[1])
            unsupported = before.replace('<!-- covers: O2 K1.2 -->',
                '<!-- covers: O2 K1.2 -->\n\nCapacity improves by 40 percent.')
            result = tools.submit_artifact('document', unsupported)
            self.assertFalse(result[0], result)
            self.assertIn('A claim with no reference', result[1])
            result = tools.submit_artifact('document', before.replace(
                '## When capacity holds', '## A different heading'))
            self.assertFalse(result[0], result)
            self.assertIn('Keep the section headings', result[1])
            altered_cover = before.replace('<!-- covers: O3 -->', '<!-- covers: O1 -->')
            result = tools.submit_artifact('document', altered_cover)
            self.assertFalse(result[0], result)
            self.assertIn('Section "Why this matters" is not touched', result[1])
            result = tools.submit_artifact('document', before)
            self.assertTrue(result[0], result)
            tools.submit_review('Kept the guide.')
        self.workers.then('document', worker)
        self.engine.update(root, self.NAME)
        self.assertIsNone(self.record(root)['problem'], self.record(root)['problem'])
        self.assertNotIn('[999]', (root / '101/document.md').read_text())

    def test_update_adds_only_supplied_references_to_sources(self):
        text = (helpers.EXAMPLES / 'document.md').read_text()
        item = {'number': 4, 'id': 'new', 'title': 'Supported finding',
                'date': '2026-01-01', 'origin': 'https://example.invalid/source'}
        spec = {'update_check': {'material': text, 'references': [item], 'names': []}}
        added = text.replace('<!-- covers: O2 K1.2 -->',
            '<!-- covers: O2 K1.2 -->\n\nNew supported fact [4].')
        problems, _, kept = worker_tools._check_update(added, spec, drafts.GuideCodec(), 'document')
        self.assertEqual(problems, [])
        self.assertIn('4. Supported finding, 2026-01-01, https://example.invalid/source', kept)
        forged = added.replace('1. Finding', '1. Forged Finding')
        problems, _, _ = worker_tools._check_update(forged, spec, drafts.GuideCodec(), 'document')
        self.assertIn('Leave Sources as it is: the studio adds the references you use.', problems)

    def test_research_only_update_describes_its_changed_input(self):
        from runner import pipeline
        root = self.saved_queue_desk('extra')
        found = self.engine._survey(root, self.record(root))
        step = next(s for s in found.steps if s.artifact == 'brief@101')
        self.add_queue_finding(root, 'extra')
        self.assertEqual(drafts.input_of(root, found.session, 'brief@101'), ['research'])
        work = pipeline.brief_work(root, found, step, None, None, [], update=True)
        self.assertNotIn(drafts.UPDATE_RULE, work.task)
        self.assertIn('research', work.task.lower())
        self.assertNotIn('plan change', work.prepared['inputs'])
        self.assertIn('extra', [item['id'] for item in json.loads(work.prepared['inputs']['supplied references'])])

    def test_missing_coverage_makes_update_conservatively_whole(self):
        root = self.desk()
        file = root / '101/document.md'
        file.write_text(file.read_text().replace('<!-- covers: O2 K1.2 -->', ''))
        workspace.save(root, self.NAME, edit=True, via='save')
        self.change_plan(root)
        card = self.card(root)
        preview = drafts.update_preview(root, self.NAME)
        self.assertEqual(preview['parts'], [s['heading'] for s in card['sections'] if not s.get('locked')])
        def worker(tools, job):
            self.assertFalse(tools.job['artifacts']['document']['untouched'])
            result = tools.submit_artifact('document', file.read_text().replace(
                '## When capacity holds', '## When capacity holds\n\n<!-- covers: O2 K1.2 -->'))
            self.assertTrue(result[0], result)
            tools.submit_review('Restored the coverage.')
        self.workers.then('document', worker)
        self.engine.update(root, self.NAME)
        self.assertIsNone(self.record(root)['problem'], self.record(root)['problem'])

    def test_saved_runs_do_not_recover_or_run_desk_job_metadata(self):
        root = self.saved_begin()
        with self.engine.files:
            record = self.record(root)
            record['drafts'] = {'jobs': [{'id': 'synthetic', 'status': 'working'}]}
            self.engine._store(root, record)
            self.engine._commit(root, 'synthetic saved run metadata')
        file = root / drafts.RECORD
        before = file.read_bytes()
        self.engine._tidy()
        self.assertEqual(file.read_bytes(), before)
        self.assertEqual(self.workers.of('part'), [])
