"""Sources added on the Training Studio desk use disposable research and documents."""
import json
from unittest import mock

import helpers  # noqa: F401
import workspace
from runner_support import QUOTE
from studio_core import research_view
from test_runner_deck import DeckCase
from workspace import WorkspaceError

from runner import draft_jobs, drafts


class SourceTests(DeckCase):
    def finished(self, **changes):
        root = self.start(flow='desk', materials=['document', 'brief'], **changes)
        self.to_end(root)
        return root

    def test_row_150_a_source_added_after_research_updates_it(self):
        root = self.finished(levels=['101', '201'])
        before = len(self.workers.of('question'))
        session = workspace.load(root)
        plan_file = root / workspace.artifact(root, session, 'research-plan')['file']
        plan_before = plan_file.read_bytes()
        files = {name: (root / workspace.artifact(root, session, name)['file']).read_bytes()
                 for name in session['artifacts'] if workspace.split(name)[0]
                 in ('blueprint', 'document', 'brief')}
        self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(len(self.workers.of('question')), before + 4)
        self.assertTrue(all(not entry['failed'] for name, entry in self.record(root)['steps'].items()
                            if name.startswith('research:')))
        self.assertEqual(len(self.workers.of('blueprint')), 2)
        self.assertEqual(len(self.workers.of('document')), 2)
        self.assertEqual(len(self.workers.of('brief')), 2)
        self.assertEqual(plan_file.read_bytes(), plan_before)
        self.assertEqual({name: (root / workspace.artifact(root, session, name)['file']).read_bytes()
                          for name in files}, files)
        held = drafts.held(root, workspace.load(root), self.record(root))
        self.assertTrue({'blueprint@101', 'blueprint@201', 'brief@101', 'brief@201'} <= held)
        self.assertTrue(any(source['title'] == 'capacity'
                            for source in self.engine._sources(root, self.record(root))[0]))
        self.assertTrue(any(line.endswith('add 1 source(s) and update the research') for line in self.log()))

    def test_a_public_web_training_reads_documents_too(self):
        root = self.finished()
        price = drafts.source_price(root, self.record(root))
        self.assertEqual(price['widened'], drafts.WIDENED)
        self.assertEqual(price['afterwards'], drafts.AFTERWARDS)
        self.assertEqual(price['words'], research_view.price({}, redone=())['words'])
        self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        record = self.record(root)
        self.assertEqual(record['documents']['scope'], 'both')
        self.assertTrue(record['research_from']['documents'])
        self.assertTrue(record['research_from']['widened_at'])
        self.assertTrue((root / 'sources/.all-added').is_file())
        self.assertIsNone(drafts.source_price(root, record)['widened'])

    def test_findings_are_marked_new_or_changed(self):
        root = self.finished()
        old = {'schema': 2, 'findings': [{'id': 'same', 'summary': {'text': 'Same'}},
                                       {'id': 'change', 'summary': {'text': 'Before'}}]}
        with mock.patch.object(workspace, 'research_record', return_value=old):
            with mock.patch.object(self.engine, 'carry_on'):
                self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        new = {'schema': 2, 'findings': [old['findings'][0],
            {'id': 'change', 'summary': {'text': 'After'}}, {'id': 'new', 'summary': {'text': 'New'}}]}
        with mock.patch.object(workspace, 'research_record', return_value=new):
            self.assertEqual(drafts.marked(root, self.record(root)), {'change': 'changed', 'new': 'new'})

    def test_nothing_is_added_while_a_change_is_made(self):
        root = self.finished()
        record = self.record(root)
        record['drafts']['jobs'] = [{'id': 'queued', 'status': 'queued'}]
        self.engine._store(root, record)
        before = self.engine.documents.listed(root)
        with self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.assertEqual(self.engine.documents.listed(root), before)

    def test_row_179_a_paused_deck_change_refuses_a_source_until_finished(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.record(root)['deck']['']['saved']['sha256']
        original = self.engine._section
        def pause_after_first(*args, **kwargs):
            result = original(*args, **kwargs)
            self.engine.act(root, 'pause')
            return result
        with mock.patch.object(self.engine, '_section', side_effect=pause_after_first):
            self.engine.deck_note(root, None, 'Make it simpler.', seen)
        notes = self.record(root)['deck']['']['notes']
        self.assertIn('done', [note['status'] for note in notes])
        self.assertIn('waiting', [note['status'] for note in notes])
        self.assertEqual(self.view(root)['state'], 'paused')
        before, session = self.record(root), workspace.load(root)
        documents, jobs, commits = self.engine.documents.listed(root), len(self.workers.jobs), self.log()
        with self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.assertEqual(self.record(root), before)
        self.assertEqual(workspace.load(root), session)
        self.assertEqual(self.engine.documents.listed(root), documents)
        self.assertEqual((len(self.workers.jobs), self.log()), (jobs, commits))
        self.engine.act(root, 'resume')
        self.to_end(root)
        self.assertTrue(all(note['status'] == 'done' for note in self.record(root)['deck']['']['notes']))
        self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])

    def test_row_179_queued_deck_changes_refuse_before_worker_registration(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.record(root)['deck']['']['saved']['sha256']
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.deck_note(root, None, 'Make it simpler.', seen)
        self.assertTrue(all(note['status'] == 'waiting' for note in self.record(root)['deck']['']['notes']))
        before, documents = self.record(root), self.engine.documents.listed(root)
        with self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.assertEqual(self.record(root), before)
        self.assertEqual(self.engine.documents.listed(root), documents)
        self.engine.deck_note_stop(root, None)
        self.to_end(root)
        self.assertEqual(self.record(root)['deck']['']['note_chain']['status'], 'stopped')
        self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])

    def test_a_queued_redraw_without_notes_refuses_a_source(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.record(root)['deck']['']['saved']['sha256']
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.draw_here(root, None, seen)
        self.assertTrue(self.record(root)['deck']['']['redrawing'])
        self.assertFalse(self.record(root)['deck'][''].get('notes'))
        before = self.record(root)
        with self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.assertEqual(self.record(root), before)
        self.assertEqual(self.engine.documents.listed(root), [])
        self.engine.carry_on(root)
        self.to_end(root)
        self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])

    def test_row_180_pending_source_refresh_refuses_deck_changes_before_writes(self):
        from runner import pipeline

        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.record(root)['deck']['']['saved']['sha256']
        outline = json.loads((root / pipeline.OUTLINE).read_text())
        slide = outline['slides'][0]
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.assertTrue(any(request.get('artifact') == 'research' and request.get('refresh')
                            for request in workspace.load(root)['requests']))
        before, session = self.record(root), workspace.load(root)
        jobs, commits = len(self.workers.jobs), self.log()
        files = {p.relative_to(root): p.read_bytes() for p in root.rglob('*')
                 if p.is_file() and '.git' not in p.relative_to(root).parts}
        actions = [
            lambda: self.engine.deck_note(root, None, 'Simplify.', seen),
            lambda: self.engine.slide_note(root, None, slide['id'], 'Simplify.', seen),
            lambda: self.engine.draw_here(root, None, seen),
            lambda: self.engine.look_apply(root, None, 'any', seen),
            lambda: self.engine.look_samples(root, None),
            lambda: self.engine.deck_outline(root, None, outline['slides'], seen),
            lambda: self.engine.slide_restore(root, None, slide['id'], 'missing', seen, redraw=True),
            lambda: self.engine.slide_words_decide(root, 'missing', 'approve', seen),
            lambda: self.engine.deck_finding(root, None, seen, 'missing', 'apply', []),
            lambda: self.engine.slide_words(root, None, slide['id'], 'title', 'New title', seen),
            lambda: self.engine.slide_words(root, None, slide['id'], 'title', 'New title', seen, _redraw=True),
        ]
        for action in actions:
            with self.subTest(action=action), self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
                action()
        self.assertEqual(self.record(root), before)
        self.assertEqual(workspace.load(root), session)
        self.assertEqual((len(self.workers.jobs), self.log()), (jobs, commits))
        self.assertEqual({p.relative_to(root): p.read_bytes() for p in root.rglob('*')
                          if p.is_file() and '.git' not in p.relative_to(root).parts}, files)
        self.engine.carry_on(root)
        self.to_end(root)
        self.assertFalse(any(request.get('artifact') == 'research'
                             for request in workspace.load(root)['requests']))
        with self.engine.files:
            self.engine._on_desk(root, deck_change=True)  # Ordinary held-material rules remain.

    def test_row_181_research_refresh_blocks_deck_and_bulk_updates_until_retry(self):
        from runner_support import fails

        root = self.begin(flow='desk', levels=['101'])
        self.to_end(root)
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        card = self.engine.draft_card(root, 'document@101')
        section = next(part for part in card['sections'] if part['heading'] == 'Summary')
        self.engine.draft_save(root, 'document@101', section['id'], card['revision'],
                               'Pending learner guide edit.', 'ab12')
        self.assertIn(root, self.engine.pending_commit)

        def refuse():
            before, session, commits, jobs = self.record(root), workspace.load(root), self.log(), len(self.workers.jobs)
            for action in (lambda: self.engine.update(root, 'deck@101'),
                           lambda: self.engine.update_all(root),
                           lambda: self.engine.update_all(root, '101')):
                with self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
                    action()
            self.assertEqual((self.record(root), workspace.load(root), self.log(), len(self.workers.jobs)),
                             (before, session, commits, jobs))
            self.assertIn(root, self.engine.pending_commit)
        refuse()
        self.workers.then('question:instance-min', fails('Not signed in.', 'unavailable'))
        self.engine.carry_on(root)
        self.assertIsNotNone(self.record(root)['problem'])
        self.assertTrue(any(item.get('artifact') == 'research' and item.get('refresh')
                            for item in workspace.load(root)['requests']))
        card = self.engine.draft_card(root, 'document@101')
        section = next(part for part in card['sections'] if part['heading'] == 'Summary')
        self.engine.draft_save(root, 'document@101', section['id'], card['revision'],
                               'Another pending guide edit.', 'ab12')
        refuse()
        self.engine.act(root, 'retry')
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])
        self.assertFalse(any(item.get('artifact') == 'research' for item in workspace.load(root)['requests']))
        with self.assertRaises(WorkspaceError) as held:
            self.engine.update(root, 'deck@101')
        self.assertNotEqual(str(held.exception), draft_jobs.BUSY)
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.update_all(root)
        self.assertTrue(drafts.updates(self.record(root)))
        chain = self.record(root)['drafts']['update_chain']['id']
        self.engine.stop_updates(root, chain)
        self.assertFalse(drafts.updates(self.record(root)))

    def saved_with_later_document(self):
        root = self.begin(source_scope='supplied-only')
        self.send(root, 'first.txt')
        self.engine.supply(root, 'done')
        self.send(root, 'later.txt')
        self.to_end(root)
        self.engine.outline(root, None, 'approve')
        self.to_end(root)
        self.assertEqual(self.state(root), 'done', self.view(root))
        return root

    def test_row_182_opened_saved_training_blocks_research_during_deck_notes(self):
        root = self.saved_with_later_document()
        self.engine.open_on_desk(root)
        seen = self.record(root)['deck']['']['saved']['sha256']
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.deck_note(root, None, 'Simplify.', seen)
        self.assertTrue(any(note['status'] == 'waiting' for note in self.record(root)['deck']['']['notes']))
        record, session, jobs, commits = self.record(root), workspace.load(root), len(self.workers.jobs), self.log()
        with self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
            self.engine.update_research(root)
        self.assertEqual((self.record(root), workspace.load(root), len(self.workers.jobs), self.log()),
                         (record, session, jobs, commits))
        self.engine.carry_on(root)
        self.to_end(root)
        self.assertTrue(all(note['status'] == 'done' for note in self.record(root)['deck']['']['notes']))
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.update_research(root)
        self.assertTrue(any(request.get('artifact') == 'research' and request.get('refresh')
                            for request in workspace.load(root)['requests']))

    def test_row_182_saved_research_update_keeps_its_original_admission(self):
        root = self.saved_with_later_document()
        self.assertFalse(drafts.on_desk(self.record(root)))
        with mock.patch.object(self.engine, 'carry_on'):
            self.engine.update_research(root)
        self.assertTrue(any(request.get('artifact') == 'research' and request.get('refresh')
                            for request in workspace.load(root)['requests']))
        self.assertEqual(self.record(root)['documents']['later'], [])

    def test_legacy_findings_ignore_recording_timestamps(self):
        root = self.finished()
        old = {'schema': 1, 'results': {'same': {'summary': 'A', 'checked_at': 'before'},
                                      'change': {'summary': 'B'}}}
        with mock.patch.object(workspace, 'research_record', return_value=old), \
                mock.patch.object(self.engine, 'carry_on'):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        old['results']['same']['checked_at'] = 'after'
        old['results']['change']['summary'] = 'C'
        old['results']['new'] = {'summary': 'D'}
        with mock.patch.object(workspace, 'research_record', return_value=old):
            self.assertEqual(drafts.marked(root, self.record(root)), {'change': 'changed', 'new': 'new'})

    def test_a_deck_without_a_guide_is_held_without_being_drawn(self):
        root = self.begin(flow='desk', materials=['brief'], levels=['101'])
        self.to_end(root)
        before = len(self.workers.of('section'))
        self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(len(self.workers.of('section')), before)
        self.assertIn('deck@101', drafts.held(root, workspace.load(root), self.record(root)))

    def test_a_refused_batch_preserves_existing_documents_and_findings(self):
        root = self.finished()
        self.engine.add_source(root, [{'name': 'existing.txt', 'data': QUOTE.encode()}])
        before, record = self.engine.documents.listed(root), self.record(root)
        with self.assertRaises(WorkspaceError):
            self.engine.add_source(root, [{'name': 'first.txt', 'data': QUOTE.encode()},
                                          {'name': 'existing.txt', 'data': QUOTE.encode()}])
        self.assertEqual(self.engine.documents.listed(root), before)
        self.assertEqual(self.record(root), record)

    def test_a_worker_in_flight_refuses_a_source_before_writing(self):
        root = self.finished()
        run = self.engine._run(root)
        with mock.patch.object(run, 'busy', True), self.assertRaisesRegex(WorkspaceError, draft_jobs.BUSY):
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.assertEqual(self.engine.documents.listed(root), [])

    def test_synthesis_receives_the_sources_once_and_marks_its_published_findings(self):
        from studio_core import research_contract
        from synthesis_fixture import published_bundle

        calls = []

        def native(engine, root, run, task, sources, product):
            calls.append((task, sources))
            findings = [{'id': ident, 'title': ident,
                         'summary': {'text': 'Updated' if len(calls) > 1 and index == 0 else 'Original'}}
                        for index, ident in enumerate(('instance-min', 'availability', 'health-checks', 'zero-downtime'))]
            if len(calls) > 1:
                findings.append({'id': 'new', 'title': 'Added finding', 'summary': {'text': 'Added'}})
            published_bundle(root / research_contract.CASE / 'research', findings=findings,
                             sources=[{'id': source.get('supplied'), 'title': source['title'],
                                       'permission': 'selected'} for source in sources])

        tool = mock.Mock()
        tool._json.return_value = {'status': 'complete'}
        contract = {'schema': 2, 'version': '1.0.0', 'digest': 'synthetic'}
        with mock.patch.object(research_contract, 'snapshot', return_value=contract), \
                mock.patch.object(research_contract, 'native', side_effect=native), \
                mock.patch.object(research_contract, 'matching', return_value=tool):
            root = self.finished(levels=['101'])
            self.assertIsNone(self.record(root)['problem'])
            self.assertEqual(len(calls), 1)
            before = len(self.workers.jobs)
            self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
            self.assertIsNone(self.record(root)['problem'])
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(self.workers.jobs), before)
            task, sources = calls[-1]
            self.assertEqual(task['source_mode'], 'mixed')
            self.assertTrue(task['refresh'])
            self.assertEqual(sources[0]['text'].strip(), QUOTE)
            self.assertEqual(drafts.marked(root, self.record(root)),
                             {'instance-min': 'changed', 'new': 'new'})
            self.assertTrue({'blueprint@101', 'brief@101'} <= drafts.held(
                root, workspace.load(root), self.record(root)))

    def unreadable_batch(self, mixed):
        from runner import documents
        from test_runner_documents import paragraph, word

        root = self.finished()
        with mock.patch.object(self.engine, 'documents', documents):
            if mixed:
                documents.add(root, 'existing.txt', QUOTE.encode())
            before = documents.listed(root)
            originals = {entry['original']: (root / entry['original']).read_bytes() for entry in before}
            record, session = self.record(root), workspace.load(root)
            jobs, commits = len(self.workers.jobs), self.log()
            files = ([{'name': 'readable.txt', 'data': QUOTE.encode()}] if mixed else [])
            files.append({'name': 'broken.docx', 'data': b'not a Word archive'})
            with self.assertRaises(WorkspaceError) as refused:
                self.engine.add_source(root, files)
            self.assertEqual(str(refused.exception), 'broken.docx: ' + documents.NOT_WORD)
            self.assertEqual(documents.listed(root), before)
            self.assertEqual({file: (root / file).read_bytes() for file in originals}, originals)
            self.assertEqual(self.record(root), record)
            self.assertEqual(workspace.load(root), session)
            self.assertEqual(len(self.workers.jobs), jobs, 'a refused source starts no research')
            self.assertEqual(self.log(), commits)
            self.assertFalse((root / 'sources/.all-added').exists())
            # The same names may be retried after fixing the Word document, without Remove.
            files[-1]['data'] = word(paragraph(QUOTE))
            self.engine.add_source(root, files)
            self.assertIsNone(self.record(root)['problem'])
            self.assertEqual({entry['name'] for entry in documents.listed(root)},
                             {entry['name'] for entry in before} | {file['name'] for file in files})
            self.assertTrue(all(entry['readable'] for entry in documents.listed(root)))

    def test_an_unreadable_source_is_refused_without_starting_research_and_can_be_retried(self):
        self.unreadable_batch(mixed=False)

    def test_a_mixed_readable_and_unreadable_batch_rolls_back_only_its_own_documents(self):
        self.unreadable_batch(mixed=True)


class UpdateChainTests(DeckCase):
    finished = SourceTests.finished

    def changed_research(self):
        root = self.finished(levels=['101', '201'])
        self.engine.add_source(root, [{'name': 'capacity.txt', 'data': QUOTE.encode()}])
        self.workers.blueprint_text += '\nA revised lesson.\n'
        return root

    def test_row_177_update_every_level_runs_level_by_level(self):
        root = self.changed_research()
        before = len(self.workers.jobs)
        made, job = [], self.engine._job

        def record_job(path, run, step, work):
            made.append(step.artifact)
            return job(path, run, step, work)

        with mock.patch.object(self.engine, '_job', side_effect=record_job):
            self.engine.update_all(root)
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(made, [f'{kind}@{level}' for level in ('101', '201')
                          for kind in ('blueprint', 'document', 'brief')])
        self.assertEqual(len(self.workers.jobs), before + 6)
        self.assertFalse(drafts.held(root, workspace.load(root), self.record(root)))
        self.assertFalse(drafts.updates(self.record(root)))

    def test_row_178_stop_leaves_the_rest_held(self):
        root = self.changed_research()
        before = len(self.workers.jobs)
        landed = self.engine._updates_made

        def stop_after_plan(path):
            landed(path)
            record = self.record(path)
            if len(self.workers.of('blueprint')) == 3 and drafts.updates(record):
                chain = next(iter(drafts.updates(record).values()))['chain']
                self.engine.stop_updates(path, chain)

        with mock.patch.object(self.engine, '_updates_made', side_effect=stop_after_plan):
            self.engine.update_all(root)
        self.assertEqual(len(self.workers.jobs), before + 1)
        self.assertFalse(drafts.updates(self.record(root)))
        self.assertIsNone(self.record(root)['problem'])
        self.assertTrue({'document@101', 'brief@101', 'blueprint@201', 'brief@201'}
                        <= drafts.held(root, workspace.load(root), self.record(root)))
        self.engine.wake(root)
        self.assertEqual(len(self.workers.jobs), before + 1)

    def test_stop_finishes_the_worker_under_way(self):
        root = self.changed_research()
        before = len(self.workers.jobs)

        def stop_during_plan(tools, job):
            asked = drafts.updates(self.record(root))
            self.assertEqual(len({entry['chain'] for entry in asked.values()}), 1)
            self.engine.stop_updates(root, asked['blueprint@101']['chain'])
            self.assertEqual(set(drafts.updates(self.record(root))), {'blueprint@101'})
            self.workers.blueprint(tools, job)

        self.workers.then('blueprint', stop_during_plan)
        self.engine.update_all(root)
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(len(self.workers.jobs), before + 1)
        self.assertFalse(drafts.updates(self.record(root)))
        self.assertNotIn('blueprint@101', drafts.held(root, workspace.load(root), self.record(root)))

    def test_one_level_leaves_the_other_level_held(self):
        root = self.changed_research()
        self.engine.update_all(root, '101')
        holding = drafts.held(root, workspace.load(root), self.record(root))
        self.assertTrue({'blueprint@201', 'brief@201'} <= holding)
        self.assertFalse(any(name.endswith('@101') for name in holding))

    def test_chain_price_sums_last_tries_only(self):
        from studio_core import stops

        root = self.finished(levels=['101'])
        record = self.record(root)
        for name, dollars in [('document@101', 2), ('brief@101', 3)]:
            record['steps'][name]['attempts'] = [
                {'seconds': 999, 'dollars': 999}, {'seconds': 30, 'dollars': dollars}]
        self.assertEqual(drafts.chain_price(root, record, ['document@101', 'brief@101']),
                         stops.cost(60, 5))

    def test_stop_before_worker_admission_starts_nothing(self):
        root = self.changed_research()
        before = len(self.workers.jobs)
        noted = self.engine._noted

        def stop_before_registration(path, step, work):
            chain = self.record(path)['drafts']['update_chain']['id']
            self.engine.stop_updates(path, chain)
            return noted(path, step, work)

        with mock.patch.object(self.engine, '_noted', side_effect=stop_before_registration):
            self.engine.update_all(root)
        self.assertEqual(len(self.workers.jobs), before)
        self.assertFalse(drafts.updates(self.record(root)))
        self.assertIsNone(self.record(root)['problem'])

    def test_failed_update_retries_in_order_without_losing_the_chain(self):
        from runner_support import fails

        root = self.changed_research()
        self.workers.then('document', fails(), fails(), fails())
        self.engine.update_all(root)
        self.assertIsNotNone(self.record(root)['problem'])
        self.assertEqual(len(self.workers.of('blueprint')), 3)
        chain = self.record(root)['drafts']['update_chain']['id']
        self.engine.act(root, 'retry')
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(self.record(root)['drafts']['update_chain']['id'], chain)
        self.assertFalse(drafts.held(root, workspace.load(root), self.record(root)))

    def test_bulk_deck_update_uses_the_existing_slide_scope(self):
        import json
        from runner import pipeline
        from test_drafts import edit

        root = self.begin(flow='desk')
        self.to_end(root)
        before = json.loads((root / pipeline.OUTLINE).read_text())
        edit(self, root, 'document', lambda text: text.replace(
            '## Why this matters', '## Why this matters\nChanged detail.'))
        self.workers.outline_said = json.loads(json.dumps(before))
        self.workers.outline_said['slides'][3]['notes'] += ' Changed.'
        count = len(self.workers.of('section'))
        self.engine.update_all(root)
        self.assertIsNone(self.record(root)['problem'])
        job = next(spec for kind, _, spec in reversed(self.workers.jobs) if kind == 'outline')
        self.assertIn('slides to word again', [entry['name'] for entry in job['inputs']])
        self.assertEqual(len(self.workers.of('section')), count + 1)
        self.assertFalse(drafts.held(root, workspace.load(root), self.record(root)))

    def test_a_bulk_deck_update_with_no_served_slide_stays_held(self):
        from test_drafts import edit

        root = self.begin(flow='desk')
        self.to_end(root)
        edit(self, root, 'document', lambda text: text.replace('## Glossary', '## Glossary\nChanged.'))
        before = len(self.workers.jobs)
        self.engine.update_all(root)
        self.assertEqual(len(self.workers.jobs), before)
        self.assertIsNone(self.record(root)['problem'])
        self.assertEqual(drafts.held(root, workspace.load(root), self.record(root)), {'deck'})
        self.assertFalse(drafts.updates(self.record(root)))

    def test_price_includes_materials_that_the_updated_plan_can_hold(self):
        root = self.changed_research()
        before = self.record(root)
        preview = drafts.update_view(root, before)
        self.assertIn('the level 101 learner guide', preview['all']['names'])
        self.assertIn('the level 201 learner guide', preview['all']['names'])
        self.assertEqual(self.record(root), before, 'a price read never starts or records updates')

    def test_bulk_update_leaves_a_persons_held_scenario_and_its_layout_alone(self):
        from runner_support import fails
        from test_drafts import edit

        root = self.start(flow='desk', levels=['101'], yoodli=True)
        self.to_end(root)
        record = self.record(root)
        record['drafted'].remove('scenario:main@101')
        self.engine._store(root, record)
        plan = (root / '101/blueprint.md').read_text()
        line = next(line for line in plan.splitlines() if line.startswith('- main:'))
        edit(self, root, 'blueprint@101', lambda text: text.replace(line, line + ' Discuss cost.'))
        before = len(self.workers.of('yoodli')), len(self.workers.of('scenario'))
        # Bound a broken implementation: it must never try to rebuild from this held input.
        self.workers.then('yoodli', fails(), fails(), fails())
        self.engine.update_all(root, '101')
        self.assertEqual((len(self.workers.of('yoodli')), len(self.workers.of('scenario'))), before)
        self.assertTrue({'scenario:main@101', 'yoodli:main@101'} <= drafts.held(
            root, workspace.load(root), self.record(root)))
