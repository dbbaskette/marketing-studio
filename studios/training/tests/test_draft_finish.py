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


class FinishingJobTests(DeckCase):
    NAME = FinishingTests.NAME
    desk, card, ask = FinishingTests.desk, FinishingTests.card, FinishingTests.ask
    # Reuse fixture helpers without rerunning the in-process cases in this subclass.
    def proposal(self, root, kind, *, verdict=None, replacement=None):
        card = self.card(root)
        part = card['sections'][0]
        row = {'part': part['id'], 'quote': part['text'],
               'replacement': replacement if replacement is not None else part['text'] + ' Consider this.',
               'reason': 'Read the supplied finding.'}
        if verdict:
            row.update(verdict=verdict, finding='zero-downtime')
        def answer(tools, job):
            accepted = tools.submit_artifact(kind, json.dumps([row]))
            self.assertTrue(accepted[0], accepted[1])
        self.workers.then(kind, answer)
        return part

    def test_check_against_sources_marks_each_claim(self):
        root = self.desk()
        before = (root / '101/document.md').read_bytes()
        self.proposal(root, 'finish-sources', verdict='contradicted')
        research = len(self.workers.of('question'))
        from runner import drafts
        read_card = drafts.card
        def locked_card(*args, **kwargs):
            self.assertTrue(self.engine.files._is_owned(), 'Finishing returns one locked card snapshot.')
            return read_card(*args, **kwargs)
        with mock.patch.object(drafts, 'card', side_effect=locked_card):
            result = self.ask(root, 'finish', tool='sources', seen=self.card(root)['revision'])
        item = result['finishing']['sources']['items'][0]
        self.assertEqual(item['verdict'], 'contradicted')
        self.assertEqual(item['finding'], 'zero-downtime')
        self.assertIn('downtime', item['source'].lower())
        self.assertEqual((root / '101/document.md').read_bytes(), before)
        self.assertEqual(len(self.workers.of('question')), research)

    def test_humanize_keeps_references(self):
        root = self.desk()
        card = self.card(root)
        self.engine.draft_save(root, self.NAME, card['sections'][0]['id'], card['revision'],
                               'Keep the reference [1].')
        self.proposal(root, 'finish-humanize', replacement='Keep the reference.')
        result = self.ask(root, 'finish', tool='humanize', level='strong', seen=self.card(root)['revision'])
        item = result['finishing']['humanize']['items'][0]
        self.assertEqual(item['dropped'], [1])
        self.assertIn('Check the facts:', item['flag'])
        self.assertTrue(item['present'])
        self.assertEqual(item['state'], 'open')
        result = self.ask(root, 'apply', job=result['finishing']['humanize']['job'],
                          items=[{'id': item['id']}], seen=result['revision'])
        self.assertEqual(result['sections'][0]['text'], 'Keep the reference.')
        self.assertEqual([e for e in workspace.load(root)['events'] if e['event'] == 'save'][-1]['via'], 'finishing')

    def test_a_finishing_job_is_one_desk_job(self):
        root = self.desk()
        card = self.card(root)
        from runner import draft_jobs
        with mock.patch.object(self.engine, 'wake'):
            draft_jobs.begin(self.engine, root, 'section', self.NAME,
                part=card['sections'][0]['id'], seen=card['revision'], note='Clarify.')
        with self.assertRaisesRegex(page.desk.Refusal, draft_jobs.BUSY):
            self.ask(root, 'finish', tool='time', seen=card['revision'])


    def test_row_185_fit_time_offers_deck_words_and_apply_keeps_slide_history(self):
        root = self.desk()
        name = 'deck@101'
        card = self.engine.draft_card(root, name)
        part = next(p for p in card['sections'] if p['slide'] == 'check-yourself' and p['field'] == 'title')
        def answer(tools, job):
            self.assertIn('learner time', [i['name'] for i in tools.job['inputs']])
            accepted = tools.submit_artifact('finish-time', json.dumps([{
                'part': part['id'], 'quote': part['text'], 'replacement': 'A shorter check',
                'reason': 'Keep the practice within the intake time.'}]))
            self.assertTrue(accepted[0], accepted[1])
        self.workers.then('finish-time', answer)
        result = self.finish.finish(self.engine, root, name, 'time', card['revision'])
        item = result['finishing']['time']['items'][0]
        result = self.finish.apply(self.engine, root, name, result['finishing']['time']['job'],
                                  [{'id': item['id']}], result['revision'])
        self.assertTrue(result['slide_result']['fits'])
        self.assertEqual(result['finishing']['time']['items'][0]['state'], 'applied')
        versions = self.engine.slide_versions(root, '101', 'check-yourself')['versions']
        self.assertEqual(versions[0]['source'], 'finishing')

    def test_prices_and_each_worker_context_are_available_before_running(self):
        root = self.desk()
        card = self.card(root)
        self.assertEqual(set(card['finish_prices']), {'sources', 'time', 'answers', 'humanize', 'level'})
        self.assertTrue(all(p['minutes'] == 2 for p in card['finish_prices'].values()))
        for tool in ('time', 'answers', 'level', 'humanize'):
            with self.subTest(tool=tool):
                result = self.ask(root, 'finish', tool=tool, level='light', seen=self.card(root)['revision'])
                self.assertEqual(len(result['finishing'][tool]['items']), 1)
                self.assertEqual(self.record(root)['drafts']['jobs'][-1]['status'], 'done')
        self.assertTrue(home.read_json(__import__('runner.drafts', fromlist=['times']).times(), {}))

    def test_typing_during_a_finishing_job_keeps_the_proposal_on_its_basis(self):
        root = self.desk()
        card = self.card(root)
        part = card['sections'][0]
        def answer(tools, job):
            self.engine.draft_save(root, self.NAME, part['id'], card['revision'], 'My pending words.')
            accepted = tools.submit_artifact('finish-humanize', json.dumps([{
                'part': part['id'], 'quote': part['text'], 'replacement': 'Worker words.',
                'reason': 'A clearer sentence.'}]))
            self.assertTrue(accepted[0], accepted[1])
        self.workers.then('finish-humanize', answer)
        result = self.ask(root, 'finish', tool='humanize', seen=card['revision'])
        item = result['finishing']['humanize']['items'][0]
        self.assertFalse(item['present'])
        self.assertEqual(result['sections'][0]['text'], 'My pending words.')
        with self.assertRaisesRegex(page.desk.Refusal, GONE):
            self.ask(root, 'apply', job=result['finishing']['humanize']['job'],
                     items=[{'id': item['id']}], seen=result['revision'])


    def test_deck_proposal_waits_for_design_approval(self):
        from stand_ins import slides as slides_stand_in
        self.slides.design, self.slides.judges, self.slides.keeps = True, True, True
        self.slides.have['local'] = True
        self.slides.listed = set(slides_stand_in.CURRENT)
        root = self.desk(walkthrough=True)
        name = 'deck@101'
        card = self.engine.draft_card(root, name)
        part = next(p for p in card['sections'] if p['slide'] == 'check-yourself' and p['field'] == 'title')
        def answer(tools, job):
            self.assertTrue(tools.submit_artifact('finish-time', json.dumps([{
                'part': part['id'], 'quote': part['text'], 'replacement': 'A short check',
                'reason': 'Fits the intake time.'}]))[0])
        self.workers.then('finish-time', answer)
        result = self.finish.finish(self.engine, root, name, 'time', card['revision'])
        found = result['finishing']['time']
        before, answers = (root / '101/deck/outline.json').read_bytes(), len(self.slides.replies)
        result = self.finish.apply(self.engine, root, name, found['job'],
                                  [{'id': found['items'][0]['id']}], result['revision'])
        approval = result['slide_result']['approval']
        self.assertEqual(result['finishing']['time']['items'][0]['state'], 'open')
        self.assertEqual((root / '101/deck/outline.json').read_bytes(), before)
        self.assertEqual(len(self.slides.replies), answers)
        self.engine.slide_words_decide(root, approval['token'], 'cancel', None)
        self.assertEqual(self.engine.draft_card(root, name)['finishing']['time']['items'][0]['state'], 'open')
        result = self.finish.apply(self.engine, root, name, found['job'],
                                  [{'id': found['items'][0]['id']}], result['revision'])
        approval = result['slide_result']['approval']
        applied = self.engine.slide_words_decide(root, approval['token'], 'approve', card['seen'],
            question=approval['question']['id'], revision=approval['revision'], response='Use these shorter words.')
        self.assertTrue(applied['fits'])
        self.assertEqual(self.engine.draft_card(root, name)['finishing']['time']['items'][0]['state'], 'applied')

    def test_results_refuse_sources_and_malformed_proposals(self):
        root = self.desk()
        card = self.card(root)
        source = next(p for p in card['sections'] if p.get('locked'))
        before = (root / '101/document.md').read_bytes()
        for value in ('not json', '{}', '[{}]', json.dumps([{
                'part': source['id'], 'quote': source['text'], 'replacement': 'Replace sources.', 'reason': 'No.'}])):
            def answer(tools, job, value=value):
                ok, said = tools.submit_artifact('finish-humanize', value)
                self.assertFalse(ok, said)
            self.workers.then('finish-humanize', answer)
            result = self.ask(root, 'finish', tool='humanize', seen=self.card(root)['revision'])
            self.assertEqual(self.record(root)['drafts']['jobs'][-1]['status'], 'failed')
            self.assertNotIn('humanize', result['finishing'])
        self.assertEqual((root / '101/document.md').read_bytes(), before)

    def test_queued_finishing_can_stop_and_retry_with_the_chosen_level(self):
        root = self.desk()
        with mock.patch.object(self.engine, 'wake'):
            self.ask(root, 'finish', tool='humanize', level='strong', seen=self.card(root)['revision'])
        job = self.record(root)['drafts']['jobs'][-1]
        self.engine.stop_draft(root, job['id'])
        self.assertEqual(len(self.workers.of('finish-humanize')), 0)
        self.engine.retry_draft(root, job['id'])
        self.assertEqual(self.record(root)['drafts']['jobs'][-1]['level'], 'strong')
        self.assertEqual(len(self.workers.of('finish-humanize')), 1)


    def test_level_check_reads_the_earlier_objectives_and_never_researches(self):
        self.finish = importlib.import_module('runner.draft_finish')
        root = self.begin(flow='desk', levels=['101', '201'], materials=['document', 'brief'])
        self.to_end(root)
        name = 'document@201'
        card = self.engine.draft_card(root, name)
        research = len(self.workers.of('question'))
        def answer(tools, job):
            ok, earlier = tools.read_input('earlier levels')
            self.assertTrue(ok)
            self.assertIn('Level 101', earlier)
            self.assertIn('Assume the reader can already:', earlier)
            self.assertNotIn('Level 201', earlier)
            self.assertNotIn('save_source', [entry['name'] for entry in tools.offered()])
            self.workers.finish_level(tools, job)
        self.workers.then('finish-level', answer)
        result = self.finish.finish(self.engine, root, name, 'level', card['revision'])
        self.assertEqual(len(result['finishing']['level']['items']), 1)
        self.assertEqual(len(self.workers.of('question')), research)


class FinishingRemovalTests(DeckCase):
    NAME = FinishingTests.NAME
    desk, card, ask = FinishingTests.desk, FinishingTests.card, FinishingTests.ask

    def cut(self, root, text, quote, tool='sources', start=None):
        card = self.card(root)
        part = card['sections'][0]['id']
        self.engine.draft_save(root, self.NAME, part, card['revision'], text)
        card = self.card(root)
        row = {'part': part, 'quote': quote, 'replacement': '', 'reason': 'Cut this passage.'}
        if tool == 'sources':
            row.update(verdict='contradicted', finding='zero-downtime')
        if start is not None:
            row['start'] = start
        def answer(tools, job):
            ok, said = tools.submit_artifact('finish-' + tool, json.dumps([row]))
            self.assertTrue(ok, said)
        self.workers.then('finish-' + tool, answer)
        checked = self.ask(root, 'finish', tool=tool, seen=card['revision'])
        return card, checked['finishing'][tool]

    def test_source_removal_applies_only_the_claim_and_keeps_history(self):
        root = self.desk()
        text = 'Keep this introduction. The claim is contradicted [1]. Keep the explanation [2].'
        before, found = self.cut(root, text, 'The claim is contradicted [1]. ')
        workers = len(self.workers.jobs)
        original = (root / '101/document.md').read_text()
        result = self.ask(root, 'apply', job=found['job'], items=[{'id': 'p1'}], seen=before['revision'])
        self.assertEqual((root / '101/document.md').read_text(),
                         original.replace('The claim is contradicted [1]. ', '', 1))
        self.assertEqual(result['sections'][0]['text'], 'Keep this introduction. Keep the explanation [2].')
        self.assertEqual(result['sections'][1:], before['sections'][1:])
        self.assertEqual(result['finishing']['sources']['items'][0]['state'], 'applied')
        self.assertEqual(found['items'][0]['dropped'], [1])
        history = self.engine.draft_versions(root, self.NAME, before['sections'][0]['id'])
        self.assertEqual(history['versions'][0]['text'], text)
        self.assertEqual([e for e in workspace.load(root)['events'] if e['event'] == 'save'][-1]['via'], 'finishing')
        self.assertEqual(len(self.workers.jobs), workers)

    def test_repeated_cut_uses_the_recorded_character_position(self):
        root = self.desk()
        text = '🙂 Keep this. Repeat this. Middle stays. Repeat this. End stays.'
        quote = 'Repeat this. '
        before, found = self.cut(root, text, quote, 'level', text.rindex(quote))
        result = self.ask(root, 'apply', job=found['job'], items=[{'id': 'p1'}], seen=before['revision'])
        self.assertEqual(result['sections'][0]['text'], '🙂 Keep this. Repeat this. Middle stays. End stays.')

    def test_removal_refuses_a_changed_part(self):
        root = self.desk()
        before, found = self.cut(root, 'Keep this. Remove this.', 'Remove this.', 'time')
        self.engine.draft_save(root, self.NAME, before['sections'][0]['id'], before['revision'],
                               'Keep my typing. Remove this.')
        snapshot = (root / '101/document.md').read_bytes()
        events = workspace.load(root)['events']
        with self.assertRaisesRegex(page.desk.Refusal, GONE):
            self.ask(root, 'apply', job=found['job'], items=[{'id': 'p1'}], seen=self.card(root)['revision'])
        self.assertEqual((root / '101/document.md').read_bytes(), snapshot)
        self.assertEqual(workspace.load(root)['events'], events)
        self.assertEqual(self.card(root)['finishing']['time']['items'][0]['state'], 'open')

    def test_cut_cannot_break_a_fence_or_create_an_unknown_reference(self):
        root = self.desk()
        for text, quote, reason in [('Keep this.\n\n```text\ncode\n```', '```text\n', 'code block'),
                                    ('Keep this [1][2].', '][', '12')]:
            with self.subTest(text=text):
                before, found = self.cut(root, text, quote, 'time')
                snapshot = (root / '101/document.md').read_bytes()
                with self.assertRaisesRegex(page.desk.Refusal, reason):
                    self.ask(root, 'apply', job=found['job'], items=[{'id': 'p1'}], seen=before['revision'])
                self.assertEqual((root / '101/document.md').read_bytes(), snapshot)

    def test_deck_cut_keeps_the_remaining_words_and_slide_history(self):
        root = self.desk()
        name = 'deck@101'
        card = self.engine.draft_card(root, name)
        part = next(p for p in card['sections'] if p['slide'] == 'check-yourself' and p['field'] == 'title')
        quote = part['text'].split()[0] + ' '
        def answer(tools, job):
            self.assertTrue(tools.submit_artifact('finish-time', json.dumps([{
                'part': part['id'], 'quote': quote, 'replacement': '', 'reason': 'Shorter title.'}]))[0])
        self.workers.then('finish-time', answer)
        result = self.finish.finish(self.engine, root, name, 'time', card['revision'])
        found = result['finishing']['time']
        result = self.finish.apply(self.engine, root, name, found['job'], [{'id': 'p1'}], result['revision'])
        self.assertTrue(result['slide_result']['fits'])
        self.assertEqual(next(p for p in result['sections'] if p['id'] == part['id'])['text'], part['text'][len(quote):])
        self.assertEqual(result['finishing']['time']['items'][0]['state'], 'applied')
        self.assertEqual(self.engine.slide_versions(root, '101', 'check-yourself')['versions'][0]['source'], 'finishing')

    def test_ambiguous_or_invalid_cut_positions_are_not_guessed(self):
        from runner import draft_finish
        text = 'Repeat this. Repeat this.'
        spec = {'parts': [{'part': 'one', 'text': text}], 'findings': [], 'finish_kind': 'finish-time'}
        base = {'part': 'one', 'quote': 'Repeat this.', 'replacement': '', 'reason': 'Cut.'}
        for extra in ({}, {'start': None}, {'start': -1}, {'start': True}, {'start': 2}, {'start': len(text)}):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'character position'):
                draft_finish.result(json.dumps([{**base, **extra}]), spec)

    def test_removal_cannot_target_locked_sources(self):
        root = self.desk()
        card = self.card(root)
        source = next(p for p in card['sections'] if p.get('locked'))
        with self.engine.files:
            sets = self.finish.proposals(self.engine, root, self.NAME)
            found = sets.keep(self.NAME, 'c' * 32, 'finish-sources', [{
                'part': source['id'], 'before': source['text'], 'after': '', 'start': 0,
                'basis': basis.fingerprint(source['text']), 'note': 'Invalid Sources cut.'}])
        before = (root / '101/document.md').read_bytes()
        events = workspace.load(root)['events']
        with self.assertRaisesRegex(page.desk.Refusal, GONE):
            self.ask(root, 'apply', job=found['job'], items=[{'id': 'p1'}], seen=card['revision'])
        self.assertEqual((root / '101/document.md').read_bytes(), before)
        self.assertEqual(workspace.load(root)['events'], events)
