"""Sources added on the Training Studio desk use disposable research and documents."""
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
