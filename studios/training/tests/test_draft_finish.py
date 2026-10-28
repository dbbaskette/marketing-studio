"""Finishing uses disposable trainings and scripted workers, never providers."""
import importlib
import json
from unittest import mock

import helpers  # noqa: F401
import checks
import workspace
import home
from test_runner_deck import DeckCase
from runner import page
from studio_core.drafting.proposals import GONE
from studio_core.drafting import basis


class FinishingTests(DeckCase):
    NAME = 'document@101'

    def desk(self, **changes):
        self.finish = importlib.import_module('runner.draft_finish')
        root = self.begin(flow='desk', levels=['101'], **changes)
        self.to_end(root)
        self.assertIsNone(self.record(root)['problem'])
        return root

    def card(self, root):
        return self.engine.draft_card(root, self.NAME)

    def ask(self, root, route, **sent):
        reply = page.RunnerPage(8765, self.engine).write('/api/drafts/' + route,
            {'path': str(root), 'name': self.NAME, **sent})
        return json.loads(reply[2])

    def proof(self, root):
        card = self.card(root)
        part = card['sections'][0]['id']
        self.engine.draft_save(root, self.NAME, part, card['revision'],
                               'Try this -- then pause. Keep this -- too.')
        result = self.ask(root, 'finish', tool='proofread')
        return result['finishing']['proofread'], part

    def test_coverage_names_an_objective_no_section_teaches(self):
        root = self.desk()
        path = root / '101/document.md'
        path.write_text(path.read_text().replace('O2', ''), encoding='utf-8')
        jobs = len(self.workers.jobs)
        result = self.ask(root, 'finish', tool='coverage')
        items = result['finishing']['coverage']['items']
        self.assertIn('O2 is not taught by any section.', [p['note'] for p in items])
        self.assertEqual(len(self.workers.jobs), jobs)
        proposal = next(p for p in items if p['note'].startswith('O2 '))
        response = self.ask(root, 'apply', job=result['finishing']['coverage']['job'],
                            items=[{'id': proposal['id']}], seen=result['revision'])
        self.assertEqual(response['note']['text'], 'Teach O2 here.')
        self.assertEqual(len(self.workers.jobs), jobs)

    def test_row_184_applying_a_proposal_keeps_a_version(self):
        root = self.desk()
        found, part = self.proof(root)
        before = self.card(root)
        self.workers.then('part', lambda tools, job: tools.submit_part('Try this, then pause.'))
        self.ask(root, 'skip', job=found['job'], ids=[found['items'][1]['id']])
        result = self.ask(root, 'apply', job=found['job'], items=[{'id': found['items'][0]['id']}],
                          seen=before['revision'])
        self.assertEqual(result['sections'][0]['text'], 'Try this, then pause. Keep this -- too.')
        events = workspace.load(root)['events']
        self.assertEqual([e for e in events if e['event'] == 'save'][-1]['via'], 'finishing')
        history = self.engine.draft_versions(root, self.NAME, part)
        self.assertEqual(history['versions'][0]['text'], before['sections'][0]['text'])
        self.assertEqual([p['state'] for p in result['finishing']['proofread']['items'][:2]],
                         ['applied', 'skipped'])

    def test_a_proposal_for_a_changed_part_is_refused(self):
        root = self.desk()
        found, part = self.proof(root)
        card = self.card(root)
        self.engine.draft_save(root, self.NAME, part, card['revision'],
                               card['sections'][0]['text'] + ' Person typed here.')
        before, jobs = (root / '101/document.md').read_bytes(), len(self.workers.jobs)
        with self.assertRaisesRegex(page.desk.Refusal, GONE):
            self.ask(root, 'apply', job=found['job'], items=[{'id': found['items'][0]['id']}],
                     seen=self.card(root)['revision'])
        self.assertEqual((root / '101/document.md').read_bytes(), before)
        self.assertEqual(len(self.workers.jobs), jobs)

    def test_pending_fix_marks_applied_only_after_a_successful_landing(self):
        root = self.desk()
        found, part = self.proof(root)
        with mock.patch.object(self.engine, 'wake'):
            result = self.ask(root, 'apply', job=found['job'],
                              items=[{'id': found['items'][0]['id']}], seen=self.card(root)['revision'])
        self.assertEqual(result['finishing']['proofread']['items'][0]['state'], 'open')
        self.assertEqual(self.record(root)['drafts']['jobs'][-1]['action'], 'fix')
        self.engine.draft_save(root, self.NAME, part, self.card(root)['revision'], 'Person typed.')
        self.engine.wake(root)
        result = self.card(root)
        self.assertEqual(result['sections'][0]['text'], 'Person typed.')
        self.assertEqual(result['finishing']['proofread']['items'][0]['state'], 'open')

    def test_claims_and_scenario_checks_return_notes_without_a_job(self):
        root = self.desk()
        card = self.card(root)
        self.engine.draft_save(root, self.NAME, card['sections'][0]['id'], card['revision'],
                               'It takes 35 seconds.')
        count = len(self.workers.jobs)
        result = self.ask(root, 'finish', tool='claims')
        self.assertTrue(any('35 seconds' in p['before'] for p in result['finishing']['claims']['items']))
        names = workspace.artifact_names(root, workspace.load(root))
        name = next(n for n in names if n.startswith('scenario:'))
        result = self.ask(root, 'finish', name=name, tool='practice')
        self.assertIn('practice', result['finishing'])
        self.assertEqual(len(self.workers.jobs), count)

    def test_proofread_get_does_not_write_materials_or_start_jobs(self):
        root = self.desk()
        self.proof(root)
        before = (root / '101/document.md').read_bytes()
        jobs = len(self.workers.jobs)
        result = self.finish.proofread(self.engine, root, self.NAME)
        self.assertEqual(result['findings'][0]['rule'], 'double-hyphen')
        self.assertEqual((root / '101/document.md').read_bytes(), before)
        self.assertEqual(len(self.workers.jobs), jobs)

    def test_yoodli_limits_name_the_field_limit_without_starting_a_job(self):
        root = self.desk(yoodli=True)
        names = workspace.artifact_names(root, workspace.load(root))
        name = next(n for n in names if n.startswith('yoodli:'))
        path = root / workspace.artifact(root, workspace.load(root), name)['file']
        limit = home.read_json(workspace.profile_for(root), {})['limits']['context_chars']['value']
        text = path.read_text()
        fields, _ = checks.fenced_fields(text)
        self.assertTrue(fields[('Context',)])
        path.write_text(text.replace(fields[('Context',)], 'a' * (limit + 1)), encoding='utf-8')
        before, jobs = path.read_bytes(), len(self.workers.jobs)
        result = self.ask(root, 'finish', name=name, tool='yoodli')
        found = result['finishing']['yoodli']
        item = next(p for p in found['items'] if p['instruction'].startswith('Bring this field'))
        result = self.ask(root, 'apply', name=name, job=found['job'],
                          items=[{'id': item['id']}], seen=result['revision'])
        self.assertEqual(result['note']['text'], f'Bring this field under {limit} characters.')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.workers.jobs), jobs)

    def test_editing_a_proofread_proposal_keeps_finishing_history(self):
        root = self.desk()
        found, part = self.proof(root)
        result = self.ask(root, 'apply', job=found['job'], seen=self.card(root)['revision'],
                          items=[{'id': found['items'][0]['id'], 'after': 'Try this, then wait.'}])
        self.assertEqual(result['sections'][0]['text'], 'Try this, then wait. Keep this -- too.')
        self.assertEqual([e for e in workspace.load(root)['events']
                          if e['event'] == 'save'][-1]['via'], 'finishing')
        self.assertTrue(self.engine.draft_versions(root, self.NAME, part)['versions'])

    def test_editing_each_repeated_sentence_uses_its_recorded_location(self):
        root = self.desk()
        part = self.card(root)['sections'][0]['id']
        text = '😀 Pause. Try this -- then pause. Try this -- then pause.'
        replacement = 'Try this, then wait.'
        for occurrence in (0, 1):
            with self.subTest(occurrence=occurrence):
                self.engine.draft_save(root, self.NAME, part, self.card(root)['revision'], text)
                checked = self.ask(root, 'finish', tool='proofread')
                found = checked['finishing']['proofread']
                items = [item for item in found['items'] if item['part'] == part
                         and item['before'] == 'Try this -- then pause.']
                chosen = items[occurrence]
                self.assertEqual(text[chosen['start']:chosen['start'] + len(chosen['before'])],
                                 chosen['before'])
                workers = len(self.workers.jobs)
                result = self.ask(root, 'apply', job=found['job'], seen=checked['revision'],
                                  items=[{'id': chosen['id'], 'after': replacement}])
                expected = text[:chosen['start']] + replacement + text[
                    chosen['start'] + len(chosen['before']):]
                self.assertEqual(result['sections'][0]['text'], expected)
                self.assertEqual(expected.count('Try this -- then pause.'), 1)
                self.assertEqual(len(self.workers.jobs), workers)
                self.assertEqual([e for e in workspace.load(root)['events']
                                  if e['event'] == 'save'][-1]['via'], 'finishing')
                history = self.engine.draft_versions(root, self.NAME, part)
                self.assertEqual(history['versions'][0]['text'], text)

    def test_edited_repeated_sentence_refuses_a_changed_part(self):
        root = self.desk()
        part = self.card(root)['sections'][0]['id']
        text = 'Try this -- then pause. Try this -- then pause.'
        self.engine.draft_save(root, self.NAME, part, self.card(root)['revision'], text)
        checked = self.ask(root, 'finish', tool='proofread')
        found = checked['finishing']['proofread']
        chosen = next(item for item in found['items'] if item['part'] == part)
        self.engine.draft_save(root, self.NAME, part, checked['revision'], text + ' Person typed.')
        before = (root / '101/document.md').read_bytes()
        events = workspace.load(root)['events']
        with self.assertRaisesRegex(page.desk.Refusal, GONE):
            self.ask(root, 'apply', job=found['job'], seen=self.card(root)['revision'],
                     items=[{'id': chosen['id'], 'after': 'Try this, then wait.'}])
        self.assertEqual((root / '101/document.md').read_bytes(), before)
        self.assertEqual(workspace.load(root)['events'], events)

    def test_edited_proposal_commits_only_validated_materials(self):
        root = self.desk()
        found, _ = self.proof(root)
        self.engine.draft_share(root)
        brief = root / workspace.artifact(root, workspace.load(root), 'brief@101')['file']
        original = brief.read_text()
        brief.write_text('Unfinished worker output.', encoding='utf-8')
        self.ask(root, 'apply', job=found['job'], seen=self.card(root)['revision'],
                 items=[{'id': found['items'][0]['id'], 'after': 'Try this, then wait.'}])
        committed = self.git('show', 'HEAD:' + str(brief.relative_to(self.space.repo)))
        self.assertEqual(committed.strip(), original.strip())
        self.assertEqual(brief.read_text(), 'Unfinished worker output.')

    def test_an_edited_proposal_locks_sources_by_identity(self):
        root = self.desk()
        card = self.card(root)
        part = card['sections'][0]['id']
        source = next(s for s in card['sections'] if s.get('locked'))
        self.engine.draft_save(root, self.NAME, part, card['revision'], source['text'])
        with self.engine.files:
            sets = self.finish.proposals(self.engine, root, self.NAME)
            found = sets.keep(self.NAME, 'b' * 32, 'finish-proofread', [
                {'part': part, 'before': source['text'], 'basis': basis.fingerprint(source['text'])},
                {'part': source['id'], 'before': source['text'], 'basis': basis.fingerprint(source['text'])}])
        result = self.ask(root, 'apply', job=found['job'], seen=self.card(root)['revision'],
                          items=[{'id': 'p1', 'after': 'Person edited these words.'}])
        self.assertEqual(result['sections'][0]['text'], 'Person edited these words.')
        self.assertEqual(next(s for s in result['sections'] if s.get('locked'))['text'], source['text'])
        with self.assertRaisesRegex(page.desk.Refusal, GONE):
            self.ask(root, 'apply', job=found['job'], seen=result['revision'],
                     items=[{'id': 'p2', 'after': 'Do not write this.'}])

    def test_skip_waits_for_a_requested_sentence_fix_to_stop(self):
        root = self.desk()
        found, part = self.proof(root)
        item = found['items'][0]['id']
        with mock.patch.object(self.engine, 'wake'):
            self.ask(root, 'apply', job=found['job'], seen=self.card(root)['revision'],
                     items=[{'id': item}])
        before = (root / '101/document.md').read_bytes()
        with self.assertRaisesRegex(page.desk.Refusal, 'desk job is working'):
            self.ask(root, 'skip', job=found['job'], ids=[item])
        pending = self.record(root)['drafts']['jobs'][-1]
        self.engine.stop_draft(root, pending['id'])
        result = self.ask(root, 'skip', job=found['job'], ids=[item])
        self.assertEqual(result['finishing']['proofread']['items'][0]['state'], 'skipped')
        self.assertEqual((root / '101/document.md').read_bytes(), before)
