"""Checked Training Studio conversation journeys; disposable state and fake companions."""
import io
import json
import zipfile
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401
import workspace
from runner_support import FORM, BLUEPRINT
from runner import desk_chat, studio
from test_runner_deck import DeckCase
from workspace import WorkspaceError


class ConversationTests(DeckCase):
    def create(self, **values):
        return Path(desk_chat.create(self.engine, {**FORM, 'materials': [],
                         'scope': ['outline', 'part'], **values})['path'])

    def submit(self, root, target, kind, payload):
        context = desk_chat.context(self.engine, root, target)
        return desk_chat.submit(self.engine, root, dict(kind=kind, target=target,
                    expected_basis=context['expected_basis'], payload=payload))

    def test_row_186_outline_only_no_worker_or_readiness(self):
        with mock.patch.object(self.engine, 'ready', side_effect=AssertionError('readiness')), \
                mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            root = self.create(levels=['101', '301'], scope=['outline'])
        record = self.record(root)
        self.assertEqual(record['execution'], 'conversation')
        self.assertEqual(record['conversation_scope'], ['outline'])
        session = workspace.load(root)
        self.assertTrue(session['practice_inputs'])
        self.assertEqual(session['settings']['stages'], [])
        self.assertFalse(record.get('research_contract'))
        self.assertEqual(self.workers.jobs, [])
        self.assertFalse((root / 'README.md').exists())

    def test_row_187_checked_absent_plan_then_part_history(self):
        root = self.create()
        before = desk_chat.context(self.engine, root, 'blueprint')
        self.assertFalse(before['inputs']['material'])
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        card = self.engine.draft_card(root, 'blueprint')
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['blueprint'], 'draft')
        target = 'blueprint/' + card['sections'][0]['id']
        self.submit(root, target, 'part', {'text': card['sections'][0]['text'] + '\nA clearer goal.'})
        self.assertTrue(self.engine.draft_versions(root, 'blueprint', card['sections'][0]['id'])['versions'])
        self.assertFalse(self.record(root)['drafts']['jobs'])

    def test_row_188_changed_inputs_and_worker_refuse_without_writes(self):
        root = self.create()
        context = desk_chat.context(self.engine, root, 'blueprint')
        (root / 'intake.md').write_text('Changed person input')
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.submit(self.engine, root, dict(kind='outline', target='blueprint',
                    expected_basis=context['expected_basis'], payload={'text': BLUEPRINT}))
        self.assertEqual(desk_chat._files(root), before)
        (root / self.engines.IN_HAND).write_text('blueprint')
        with self.assertRaises(WorkspaceError):
            desk_chat.context(self.engine, root, 'blueprint')
        self.assertEqual((root / self.engines.IN_HAND).read_text(), 'blueprint')

    def test_recovery_and_page_wake_leave_conversation_alone(self):
        root = self.create()
        (root / self.engines.IN_HAND).write_text('blueprint')
        before = desk_chat._files(root)
        with mock.patch.object(self.engine, '_work', side_effect=AssertionError('worker')):
            self.engine.wake(root)
            self.assertNotIn(root, self.engine._tidy())
        self.assertEqual(desk_chat._files(root), before)

    def test_scope_and_take_preserve_materials_and_ready_facts(self):
        root = self.create()
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        before = (root / 'blueprint.md').read_bytes(), workspace.load(root)
        context = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, context['expected_basis'], ['outline', 'part'])
        self.assertEqual(((root / 'blueprint.md').read_bytes(), workspace.load(root)), before)
        record = self.record(root)
        record['execution'] = 'runner'
        self.engine._store(root, record)
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], context['scope'])
        self.assertEqual(((root / 'blueprint.md').read_bytes(), workspace.load(root)), before)

    def test_cli_json_stdin_and_existing_helper_desk(self):
        from training import parser as helper_parser
        self.assertIsNotNone(helper_parser().parse_args(['desk']).handler)
        data = {**FORM, 'materials': [], 'scope': ['outline']}
        output = io.StringIO()
        args = studio.parser().parse_args(['desk', 'create', '--input', '-'])
        with mock.patch('sys.stdin', io.StringIO(json.dumps(data))):
            self.assertEqual(studio.desk_command(args, make=lambda: self.engine, out=output), 0)
        self.assertEqual(json.loads(output.getvalue())['execution'], 'conversation')

    def researched(self, **values):
        root = self.create(**{'materials': ['document', 'brief'], 'scope': list(desk_chat.KINDS), **values})
        return self.supply_research(root)

    def supply_research(self, root):
        from runner_support import PLAN
        from synthesis_fixture import published_bundle, dossier
        from studio_core import research_contract
        spec = desk_chat.context(self.engine, root, 'research-plan')['requirements']['spec']
        self.submit(root, 'research-plan', 'text', {'plan': {**PLAN, 'scope': spec['scope'],
                                                          'purpose': 'planning', 'sources': []}})
        case = self.base / ('checked-case-' + root.name)
        findings = dossier('synthetic')['findings']
        findings += [{**findings[0], 'id': ident} for ident in ('availability', 'zero-downtime')]
        published_bundle(case / 'research', findings=findings)
        (case / '.harness-research').mkdir()
        (case / '.harness-research/synthesis.json').write_text(json.dumps({
            'owner': research_contract.OWNER, 'digest': 'synthetic-digest'}))
        self.submit(root, 'research', 'research', {'case': str(case)})
        return root

    def test_absent_materials_to_usable_guide_and_held_downstream(self):
        from runner_support import DOCUMENT, BRIEF
        root = self.researched()
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        self.submit(root, 'document', 'text', {'text': DOCUMENT})
        self.submit(root, 'brief', 'text', {'text': BRIEF})
        status = workspace.person_statuses(root, workspace.load(root))
        self.assertEqual([status[name] for name in ('blueprint', 'document', 'brief')], ['draft'] * 3)
        shown = desk_chat.show(self.engine, root)
        self.assertIn('document', shown['cards'])
        card = shown['cards']['blueprint']
        self.submit(root, 'blueprint/' + card['sections'][0]['id'], 'part',
                    {'text': card['sections'][0]['text'] + '\nAn explicit refinement.'})
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['document'], 'stale')
        self.assertEqual(self.workers.jobs, [])
        self.assertFalse((root / 'document.docx').exists())
        self.assertFalse((root / 'README.md').exists())

    def test_outline_look_and_checked_native_drawing_same_conversation(self):
        from runner_support import OUTLINE, CHOSEN, drawn
        root = self.researched(deck_target='pptx', brand=CHOSEN, materials=[])
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        self.submit(root, 'deck-outline', 'outline', {'outline': OUTLINE})
        self.brand.offers_looks = True
        context = desk_chat.context(self.engine, root, 'look')
        desk_chat.answer(self.engine, root, {'target': 'look', 'expected_basis': context['expected_basis'],
            'answer': {'questionId': context['requirements']['questionId'], 'choice': 'default', 'response': 'Use the displayed default.'}})
        context = desk_chat.context(self.engine, root, 'deck')
        sections = {ident: drawn(spec['artifacts']['section']) for ident, spec in context['requirements']['sections'].items()}
        desk_chat.submit(self.engine, root, {'kind': 'drawing', 'target': 'deck',
            'expected_basis': context['expected_basis'], 'payload': {'sections': sections}})
        self.assertTrue((root / 'deck.pptx').read_bytes().startswith(b'PK\x03\x04'))
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')
        self.assertEqual(self.workers.jobs, [])
        self.assertFalse(self.slides.imported)


class ConversationDesignTests(DeckCase):
    WALKTHROUGH = True

    def setUp(self):
        super().setUp()
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True

    def taken(self):
        root = self.begin(flow='desk')
        self.to_end(root)
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['drawing', 'part'])
        return root

    def proposed(self, root):
        target = 'deck/check-yourself/title'
        context = desk_chat.context(self.engine, root, target)
        shown = desk_chat.submit(self.engine, root, {'kind': 'part', 'target': target,
            'expected_basis': context['expected_basis'], 'payload': {'text': 'A shorter check'}})
        return shown['approval']

    def reply(self, context):
        return {'target': 'design', 'expected_basis': context['expected_basis'], 'answer': {
            'questionId': context['requirements']['question']['id'],
            'planRevision': context['requirements']['revision'], 'decision': 'approve',
            'feedback': 'Use the shorter checked words.'}}

    def test_row_189_actual_design_answer_and_no_worker_or_ready(self):
        from runner import pipeline
        root = self.taken()
        count = len(self.workers.jobs)
        previous = workspace.load(root)
        self.proposed(root)
        context = desk_chat.context(self.engine, root, 'design')
        before = desk_chat._files(root)
        wrong = self.reply(context)
        wrong['answer']['questionId'] = 'a-different-question'
        with self.assertRaises(WorkspaceError):
            desk_chat.answer(self.engine, root, wrong)
        self.assertEqual(desk_chat._files(root), before)
        desk_chat.answer(self.engine, root, self.reply(context))
        outline = json.loads((root / pipeline.OUTLINE).read_bytes())
        self.assertEqual(outline['slides'][4]['title'], 'A shorter check')
        self.assertEqual(len(self.workers.jobs), count)
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')
        self.assertEqual(workspace.load(root)['practice_inputs'], previous['practice_inputs'])
        self.assertTrue(self.engine.slide_versions(root, None, 'check-yourself')['versions'])

    def test_concurrent_external_proposal_change_refuses_publication_and_cleans_stage(self):
        from runner import deck_edit
        root = self.taken()
        proposed = self.proposed(root)
        context = desk_chat.context(self.engine, root, 'design')
        proposal = deck_edit.proposal_folder(root, proposed['token']) / 'request.json'
        before = {key: value for key, value in desk_chat._files(root).items() if not key.startswith('@proposals/')}
        real = self.slides.design_respond
        def changing(project, reply):
            result = real(project, reply)
            proposal.write_bytes(proposal.read_bytes() + b'\n')
            return result
        with mock.patch.object(self.slides, 'design_respond', side_effect=changing):
            with self.assertRaises(WorkspaceError):
                desk_chat.answer(self.engine, root, self.reply(context))
        self.assertEqual({key: value for key, value in desk_chat._files(root).items() if not key.startswith('@proposals/')}, before)
        remaining = list((self.base / 'data/slide-edits').glob('*/proposals/*/request.json'))
        self.assertEqual(remaining, [proposal])


class ConversationGuardTests(DeckCase):
    create = ConversationTests.create
    submit = ConversationTests.submit
    def test_scope_target_and_payload_validation_do_not_widen_work(self):
        root = self.create(scope=['outline'])
        before = desk_chat._files(root)
        for target in ('document', 'blueprint@999', '../secret', 'look'):
            with self.subTest(target=target), self.assertRaises(WorkspaceError):
                desk_chat.context(self.engine, root, target)
        with self.assertRaises(WorkspaceError):
            desk_chat.scope_of(['outline', 'deliver'])
        with self.assertRaises(WorkspaceError):
            self.submit(root, 'blueprint', 'outline', {'text': 'Invalid plan'})
        self.assertEqual(desk_chat._files(root), before)

    def test_helper_page_and_worker_acquisition_cannot_write_conversation(self):
        import training
        root = self.create()
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        card = self.engine.draft_card(root, 'blueprint')
        before = desk_chat._files(root)
        args = training.parser().parse_args(['save', 'blueprint', '--built'])
        with self.assertRaises(WorkspaceError):
            training.dispatch(args, root)
        with self.assertRaises(WorkspaceError):
            self.engine.draft_save(root, 'blueprint', 'opening', card['revision'], 'An edit')
        with self.assertRaises(WorkspaceError):
            self.engine._step_marker(root, 'blueprint')
        self.assertFalse(self.engine._may_go(root))
        self.assertEqual(desk_chat._files(root), before)

    def test_explicit_handoff_checks_effective_scope_before_readiness(self):
        root = self.create()
        record = self.record(root)
        record['research_contract'] = {'schema': 2, 'digest': 'synthetic', 'version': '1.0.0'}
        self.engine._store(root, record)
        context = desk_chat.context(self.engine, root, 'handoff')
        before = desk_chat._files(root)
        with mock.patch.object(self.engine, 'ready', side_effect=AssertionError('readiness')):
            with self.assertRaisesRegex(WorkspaceError, 'scope'):
                desk_chat.handoff(self.engine, root, context['expected_basis'], context['scope'])
        self.assertEqual(desk_chat._files(root), before)
        context = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, context['expected_basis'], list(desk_chat.KINDS))
        context = desk_chat.context(self.engine, root, 'handoff')
        with mock.patch.object(self.engine, 'wake') as wake:
            desk_chat.handoff(self.engine, root, context['expected_basis'], context['scope'])
        self.assertEqual(wake.call_count, 1)
        self.assertEqual(self.record(root)['execution'], 'runner')

    def test_real_two_process_writes_and_recovery_preserve_chat_ownership(self):
        import os
        import subprocess
        import sys
        import time
        root = self.create()
        context = desk_chat.context(self.engine, root, 'scope')
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(helpers.REPO), str(helpers.SCRIPTS))))
        marker = root / self.engines.IN_HAND
        marker.write_text('conversation-owned saved marker')
        result = subprocess.run([sys.executable, '-c', 'from runner.engine import Engine; import sys; e=Engine(background=False); e._tidy(); e.wake(sys.argv[1])', str(root)], env=env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(marker.read_text(), 'conversation-owned saved marker')
        marker.unlink()
        start = self.base / 'compete'
        code = '''import json, sys, time
from pathlib import Path
from runner import desk_chat
from runner.engine import Engine
root, basis, start, ready, kind = sys.argv[1:]
Path(ready).touch()
end = time.monotonic() + 10
while not Path(start).exists() and time.monotonic() < end:
    time.sleep(.01)
try:
    desk_chat.set_scope(Engine(background=False), root, basis, ['outline', kind])
    print(json.dumps({'saved': True}))
except Exception as error:
    print(json.dumps({'refused': str(error)}))
'''
        children = []
        try:
            for kind in ('text', 'part'):
                children.append(subprocess.Popen([sys.executable, '-c', code, str(root), context['expected_basis'], str(start), str(self.base / ('ready-' + kind)), kind], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            deadline = time.monotonic() + 10
            while not all((self.base / ('ready-' + kind)).exists() for kind in ('text', 'part')):
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.01)
            start.touch()
            results = []
            for child in children:
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, out + err)
                self.assertEqual(err, '')
                results.append(json.loads(out))
            self.assertEqual(sum(result.get('saved', False) for result in results), 1, results)
            self.assertIn('changed', next(result['refused'] for result in results if 'refused' in result))
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate()


from runner_support import TeamCase  # noqa: E402


class ConversationTeamTests(TeamCase):
    def test_another_driver_refuses_checked_take_and_submission(self):
        with self.be(self.alex):
            root = Path(desk_chat.create(self.alex.engine, {**FORM, 'materials': [], 'scope': ['outline']})['path'])
            self.alex.engine.share()
        with self.be(self.blake):
            self.blake.engine.fetch()
            theirs = self.theirs(self.blake, root)
            before = desk_chat._files(theirs)
            context = desk_chat.context(self.blake.engine, theirs, 'ownership')
            with self.assertRaises(WorkspaceError):
                desk_chat.take(self.blake.engine, theirs, context['expected_basis'], ['outline'])
            self.assertEqual(desk_chat._files(theirs), before)

    def test_person_ready_and_both_helper_routes_refuse_another_driver(self):
        import desk
        with self.be(self.alex):
            root = Path(desk_chat.create(self.alex.engine, {**FORM, 'materials': [], 'scope': ['outline']})['path'])
            self.alex.engine.share()
        with self.be(self.blake):
            self.blake.engine.fetch()
            theirs = self.theirs(self.blake, root)
            before = desk_chat._files(theirs)
            with self.assertRaises(WorkspaceError):
                self.blake.engine.mark_ready(theirs, 'blueprint', 'unseen')
            for route, payload in [('/api/decide', {'artifact': 'blueprint', 'decision': 'approve', 'seen': 'unseen'}),
                                   ('/api/approval', {'mode': 'chat'})]:
                with self.subTest(route=route), self.assertRaises(WorkspaceError):
                    desk.Page(0).write(route, {'path': str(theirs), **payload})
            self.assertEqual(desk_chat._files(theirs), before)


class ConversationGoogleDraftTests(ConversationDesignTests):
    # Reuse setup/helpers without repeating inherited tests below.
    test_row_189_actual_design_answer_and_no_worker_or_ready = None
    test_concurrent_external_proposal_change_refuses_publication_and_cleans_stage = None

    def google_desk(self):
        root = self.begin(flow='desk', deck_target='google')
        self.to_end(root)
        name = 'deck'
        link = root / workspace.artifact(root, workspace.load(root), name)['file']
        self.engine.mark_ready(root, name, workspace.sha256_file(link))
        baseline = root / workspace.STATE_DIR / 'google-baseline.json'
        baseline.write_text('{"revision":"synthetic-existing-google-revision"}\n')
        original = link.read_bytes(), baseline.read_bytes(), workspace.load(root)['artifacts'][name]['approved']
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['drawing', 'part'])
        return root, link, baseline, original

    def test_google_word_answer_keeps_link_baseline_and_original_approval(self):
        from runner import drafts
        root, link, baseline, original = self.google_desk()
        count = len(self.workers.jobs)
        earlier = self.record(root)['deck']['']['approved']
        self.proposed(root)
        context = desk_chat.context(self.engine, root, 'design')
        with mock.patch.object(self.slides, 'drive_import', side_effect=AssertionError('delivery')):
            desk_chat.answer(self.engine, root, self.reply(context))
        session = workspace.load(root)
        marker = workspace.pending_local_deck(root, session, 'deck')
        self.assertEqual((link.read_bytes(), baseline.read_bytes()), original[:2])
        self.assertEqual(marker['delivered_approval'], original[2])
        previous = self.record(root)['conversation_answers'][-1]['previous_decisions']
        self.assertEqual(previous['materials']['deck']['approved'], original[2])
        self.assertEqual(previous['decks']['']['approved'], earlier)
        self.assertEqual(session['settings']['deck_target'], 'google')
        file = root / workspace.artifact(root, session, 'deck')['file']
        self.assertEqual(file.relative_to(root).as_posix(), 'deck/local-draft.pptx')
        self.assertTrue(file.read_bytes().startswith(b'PK\x03\x04'))
        self.assertEqual(workspace.person_statuses(root, session)['deck'], 'draft')
        self.assertEqual(self.record(root)['deck']['']['saved']['sha256'], workspace.sha256_file(file))
        self.assertEqual(len(self.workers.jobs), count)
        self.assertTrue(drafts.needs_you(root, self.engine._survey(root, self.record(root)), 'deck'))
        with self.assertRaisesRegex(WorkspaceError, 'undelivered local draft'):
            workspace.approve(root, 'deck', by='page')
        # Existing native page/domain edits retain local-only behavior even without
        # the adapter flag: a note edit must not deliver the new local drawing.
        record = self.record(root)
        record['execution'] = 'runner'
        self.engine._store(root, record)
        with mock.patch.object(self.slides, 'drive_import', side_effect=AssertionError('delivery')):
            seen = self.record(root)['deck']['']['saved']['sha256']
            self.assertTrue(self.engine.slide_words(root, None, 'check-yourself', 'notes', 'An explicit local note.', seen)['fits'])
        self.assertEqual((link.read_bytes(), baseline.read_bytes()), original[:2])
        with self.assertRaisesRegex(WorkspaceError, 'needs you'):
            self.engine.mark_ready(root, 'deck', self.record(root)['deck']['']['saved']['sha256'])

    def test_malformed_or_missing_local_draft_never_falls_back_to_delivered_link(self):
        root, link, baseline, original = self.google_desk()
        self.proposed(root)
        context = desk_chat.context(self.engine, root, 'design')
        desk_chat.answer(self.engine, root, self.reply(context))
        session = workspace.load(root)
        file = root / workspace.artifact(root, session, 'deck')['file']
        file.unlink()
        with self.assertRaisesRegex(WorkspaceError, 'missing or changed'):
            workspace.person_statuses(root, workspace.load(root))
        self.assertEqual(link.read_bytes(), original[0])
        session['pending_local_decks']['deck'] = {'file': '../../elsewhere'}
        workspace.store(root, session)
        with self.assertRaises(WorkspaceError):
            workspace.artifact(root, workspace.load(root), 'deck')

    def test_hypothetical_delivered_link_reconciliation_is_atomic(self):
        from runner import pipeline
        root, link, baseline, original = self.google_desk()
        self.proposed(root)
        context = desk_chat.context(self.engine, root, 'design')
        desk_chat.answer(self.engine, root, self.reply(context))
        before = desk_chat._files(root)
        found = self.engine._survey(root, self.record(root))
        mine = found.decks[None]
        shows = json.loads((root / pipeline.SHOWS).read_bytes())
        # Internal domain reconciliation only: no page/CLI delivery action exists.
        explicit_link = '# Hypothetical synthetic delivered link\n\nhttps://docs.example.invalid/new\n'
        with mock.patch.object(workspace, 'save', side_effect=WorkspaceError('save failed')):
            with self.assertRaisesRegex(WorkspaceError, 'save failed'):
                pipeline.keep_deck(root, found, mine, None, explicit_link, shows)
        self.assertEqual(desk_chat._files(root), before)
        with self.engine.files:
            pipeline.keep_deck(root, found, mine, None, explicit_link, shows)
        session = workspace.load(root)
        self.assertNotIn('deck', session['pending_local_decks'])
        self.assertEqual(link.read_text(), explicit_link)
        self.assertEqual(baseline.read_bytes(), original[1])
        self.assertEqual(session['local_deck_history'][-1]['delivered_approval'], original[2])
        self.assertEqual(workspace.artifact(root, session, 'deck')['file'], 'deck-link.md')


class ConversationInputTests(ConversationTests):
    # Only new journeys here; shared helpers retain the original focused cases.
    test_row_186_outline_only_no_worker_or_readiness = None
    test_row_187_checked_absent_plan_then_part_history = None
    test_row_188_changed_inputs_and_worker_refuse_without_writes = None
    test_recovery_and_page_wake_leave_conversation_alone = None
    test_scope_and_take_preserve_materials_and_ready_facts = None
    test_cli_json_stdin_and_existing_helper_desk = None
    test_absent_materials_to_usable_guide_and_held_downstream = None
    test_outline_look_and_checked_native_drawing_same_conversation = None

    def test_local_upload_is_explicit_pinned_and_has_no_worker(self):
        from runner import documents
        self.engine.documents = documents
        values = {**FORM, 'materials': [], 'scope': ['text'], 'source_scope': 'supplied-only'}
        root = Path(desk_chat.create(self.engine, values, {'source.md': b'A synthetic selected source.'})['path'])
        context = desk_chat.context(self.engine, root, 'research-plan')
        self.assertIn('A synthetic selected source.', str(context['inputs']['sources']))
        before = desk_chat._files(root)
        source = documents.listed(root)[0]
        (root / source['file']).write_text('A changed source.')
        with self.assertRaises(WorkspaceError):
            desk_chat.submit(self.engine, root, {'kind': 'text', 'target': 'research-plan',
                'expected_basis': context['expected_basis'], 'payload': {'plan': {}}})
        self.assertEqual(self.workers.jobs, [])
        self.assertEqual((root / source['original']).read_bytes(), before[source['original']])

    def test_initial_companion_question_uses_actual_revision_and_response(self):
        from runner_support import CHOSEN, OUTLINE, designed
        from runner import pipeline
        self.slides.design = True
        root = self.researched(materials=[], deck_target='pptx', brand=CHOSEN, walkthrough=True)
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        self.submit(root, 'deck-outline', 'outline', {'outline': {'outline': OUTLINE, 'design': designed(OUTLINE)}})
        context = desk_chat.context(self.engine, root, 'design')
        self.assertIsNone(context['requirements']['token'])
        desk_chat.answer(self.engine, root, {'target': 'design', 'expected_basis': context['expected_basis'],
            'answer': {'questionId': context['requirements']['question']['id'],
                       'planRevision': context['requirements']['revision'], 'decision': 'approve',
                       'feedback': 'Use this proposed teaching design.'}})
        self.assertTrue(self.slides.design_status(pipeline.design_project(root, None))['buildAllowed'])
        self.assertEqual(self.workers.jobs, [])

    def test_outline_update_keeps_unchanged_section_and_saved_look_history(self):
        from runner_support import drawn
        from runner import pipeline
        self.brand.offers_looks = True
        root = self.begin(flow='desk', materials=['document', 'brief'])
        self.to_end(root)
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['outline', 'drawing', 'part'])
        built = pipeline.read_built(root, None)
        ident = sorted(built['sections'])[0]
        original = (root / pipeline.WORK / built['sections'][ident]['file']).read_bytes()
        outline = json.loads((root / pipeline.OUTLINE).read_bytes())
        outline['slides'][4]['notes'] += '\nAn explicit clarification.'
        self.submit(root, 'deck-outline', 'outline', {'outline': outline})
        context = desk_chat.context(self.engine, root, 'look')
        desk_chat.answer(self.engine, root, {'target': 'look', 'expected_basis': context['expected_basis'],
            'answer': {'questionId': context['requirements']['questionId'], 'choice': 'default', 'response': 'Keep this displayed look.'}})
        context = desk_chat.context(self.engine, root, 'deck')
        self.assertNotIn(ident, context['requirements']['sections'])
        payload = {key: drawn(spec['artifacts']['section']) for key, spec in context['requirements']['sections'].items()}
        desk_chat.submit(self.engine, root, {'kind': 'drawing', 'target': 'deck', 'expected_basis': context['expected_basis'],
                                           'payload': {'sections': payload}})
        after = pipeline.read_built(root, None)
        self.assertEqual((root / pipeline.WORK / after['sections'][ident]['file']).read_bytes(), original)
        self.assertTrue(self.record(root)['deck']['']['look_history'])


class ConversationSelectionTests(DeckCase):
    create = ConversationTests.create
    submit = ConversationTests.submit
    supply_research = ConversationTests.supply_research

    def select(self, root, scope, **selection):
        context = desk_chat.context(self.engine, root, 'scope')
        return desk_chat.set_scope(self.engine, root, context['expected_basis'], scope, **selection)

    def test_outline_only_then_explicit_guide_selection_on_same_desk(self):
        from runner_support import DOCUMENT
        root = self.create(scope=['outline'])
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        original = (root / 'blueprint.md').read_bytes()
        self.select(root, ['outline', 'text', 'part'], materials=['document'])
        self.submit(root, 'document', 'text', {'text': DOCUMENT})
        self.assertEqual((root / 'blueprint.md').read_bytes(), original)
        self.assertTrue((root / 'document.md').is_file())
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['document'], 'draft')
        session = workspace.session_path(root).read_bytes()
        self.select(root, ['text', 'part'])
        self.assertEqual(workspace.session_path(root).read_bytes(), session)
        self.select(root, ['text', 'part'], materials=[])
        self.assertTrue((root / 'document.md').is_file())
        self.assertEqual(self.workers.jobs, [])

    def test_outline_only_then_explicit_local_deck_selection_on_same_desk(self):
        from runner_support import CHOSEN, OUTLINE, drawn
        root = self.create(scope=['outline'])
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        self.select(root, list(desk_chat.KINDS), materials=[], deck_target='pptx', brand=CHOSEN)
        self.supply_research(root)
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        self.submit(root, 'deck-outline', 'outline', {'outline': OUTLINE})
        self.brand.offers_looks = True
        context = desk_chat.context(self.engine, root, 'look')
        desk_chat.answer(self.engine, root, {'target': 'look', 'expected_basis': context['expected_basis'],
            'answer': {'questionId': context['requirements']['questionId'], 'choice': 'default', 'response': 'Use this displayed default.'}})
        context = desk_chat.context(self.engine, root, 'deck')
        sections = {key: drawn(spec['artifacts']['section']) for key, spec in context['requirements']['sections'].items()}
        desk_chat.submit(self.engine, root, {'kind': 'drawing', 'target': 'deck', 'expected_basis': context['expected_basis'], 'payload': {'sections': sections}})
        self.assertTrue((root / 'deck.pptx').read_bytes().startswith(b'PK\x03\x04'))
        before = desk_chat._files(root)
        with self.assertRaisesRegex(WorkspaceError, 'saved work'):
            self.select(root, list(desk_chat.KINDS), deck_target='google')
        self.assertEqual(desk_chat._files(root), before)
        self.assertEqual(self.workers.jobs, [])

    def test_invalid_explicit_selection_refuses_without_mutation(self):
        root = self.create()
        before = desk_chat._files(root)
        for selection in ({'materials': ['unknown']}, {'materials': 'document'}, {'materials': None},
                          {'deck_target': 'unknown'}, {'brand': {'brand': '../bad'}},
                          {'yoodli': True}, {'unrecognized': True}):
            with self.subTest(selection=selection), self.assertRaises(WorkspaceError):
                self.select(root, list(desk_chat.KINDS), **selection)
            self.assertEqual(desk_chat._files(root), before)

    def test_scope_cli_accepts_only_explicit_native_selection_fields(self):
        root = self.create()
        context = desk_chat.context(self.engine, root, 'scope')
        payload = {'expected_basis': context['expected_basis'], 'scope': ['outline', 'text'], 'materials': ['document']}
        args = studio.parser().parse_args(['desk', 'scope', '--folder', str(root), '--input', '-'])
        output = io.StringIO()
        with mock.patch('sys.stdin', io.StringIO(json.dumps(payload))):
            self.assertEqual(studio.desk_command(args, make=lambda: self.engine, out=output), 0)
        self.assertEqual(json.loads(output.getvalue())['session']['settings']['stages'], ['document'])
        self.assertEqual(self.workers.jobs, [])


class ConversationReviewFixTests(DeckCase):
    WALKTHROUGH = True
    create = ConversationTests.create
    submit = ConversationTests.submit
    researched = ConversationTests.researched
    supply_research = ConversationTests.supply_research
    proposed = ConversationDesignTests.proposed
    reply = ConversationDesignTests.reply
    taken = ConversationDesignTests.taken
    google_desk = ConversationGoogleDraftTests.google_desk

    def binary_deck(self, root):
        session = workspace.load(root)
        file = root / workspace.artifact(root, session, 'deck')['file']
        with zipfile.ZipFile(file, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('ppt/media/image1.bin', bytes(range(256)))
        with self.assertRaises(UnicodeDecodeError):
            file.read_bytes().decode('utf-8')
        digest = workspace.sha256_file(file)
        session['artifacts']['deck']['sha256'] = digest
        if session.get('pending_local_decks'):
            session['pending_local_decks']['deck']['sha256'] = digest
        workspace.store(root, session)
        record = self.record(root)
        record['deck']['']['saved']['sha256'] = digest
        self.engine._store(root, record)
        return file

    def check_binary_contexts(self, root):
        from runner import pipeline
        context = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, context['expected_basis'], list(desk_chat.KINDS))
        file = self.binary_deck(root)
        before = desk_chat._files(root)
        for target in ('deck/check-yourself/title', 'deck-outline'):
            with self.subTest(target=target):
                context = desk_chat.context(self.engine, root, target)
                material = context['inputs']['material']
                self.assertEqual(material['file'], file.relative_to(root).as_posix())
                self.assertEqual(material['sha256'], workspace.sha256_file(file))
                self.assertEqual(material['outline'], json.loads((root / pipeline.OUTLINE).read_bytes()))
                if '/' in target:
                    self.assertEqual(material['selected']['text'], material['outline']['slides'][4]['title'])
                self.assertEqual(desk_chat._files(root), before)
        self.submit(root, 'deck/check-yourself/title', 'part', {'text': 'A binary title check'})
        before = desk_chat._files(root)
        context = desk_chat.context(self.engine, root, 'design')
        self.assertEqual(context['inputs']['material']['sha256'], workspace.sha256_file(file))
        self.assertTrue(context['requirements']['question']['id'])
        self.assertEqual(desk_chat._files(root), before)
        desk_chat.answer(self.engine, root, self.reply(context))
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['deck'], 'draft')

    def test_binary_zip_deck_part_outline_and_design_contexts(self):
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True
        self.check_binary_contexts(self.taken())

    def test_binary_zip_pending_local_part_outline_and_design_contexts(self):
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True
        root, link, baseline, original = self.google_desk()
        self.proposed(root)
        context = desk_chat.context(self.engine, root, 'design')
        desk_chat.answer(self.engine, root, self.reply(context))
        with mock.patch.object(self.slides, 'drive_import', side_effect=AssertionError('delivery')):
            self.check_binary_contexts(root)
        self.assertEqual((link.read_bytes(), baseline.read_bytes()), original[:2])

    def test_google_plugin_writers_refuse_chat_ownership_before_transport(self):
        import gdocs
        import training
        root = self.create(materials=['document'])
        (root / 'document.md').write_text('# Synthetic document\n')
        export = self.base / 'synthetic-google-export.md'
        export.write_text('# Synthetic remote edit\n')
        gdocs.write_links(root, {'schema': 1, 'docs': {'document': {
            'file_id': 'synthetic', 'url': 'https://example.invalid/doc', 'anchors': [],
            'local_sha256': workspace.sha256_file(root / 'document.md'),
            'remote_sha256': gdocs.digest('# Previous remote text\n')}}})
        before = desk_chat._files(root)
        commands = [['unlink', 'document'],
                    ['record', 'document', '--file-id', 'synthetic', '--url', 'https://example.invalid/doc', '--export', str(export)],
                    ['pull', 'document', '--from', str(export)],
                    ['push', 'document', '--prepare', str(self.base / 'must-not-exist.md')]]
        with mock.patch.object(gdocs, 'GcloudTransport', side_effect=AssertionError('transport')):
            for command in commands:
                with self.subTest(command=command[0]), self.assertRaisesRegex(WorkspaceError, 'conversation'):
                    training.dispatch(training.parser().parse_args(['google', *command]), root)
                self.assertEqual(desk_chat._files(root), before)
            shown = training.dispatch(training.parser().parse_args(['google', 'status', '--offline']), root)
        self.assertIn('document', shown['docs'])
        self.assertFalse((self.base / 'must-not-exist.md').exists())
        self.assertEqual(desk_chat._files(root), before)

    def drawing_request(self, existing, deck_target='pptx'):
        from runner_support import OUTLINE, CHOSEN, drawn
        from runner import pipeline
        if existing:
            root = self.begin(flow='desk', title='Existing synthetic drawing')
            self.to_end(root)
            context = desk_chat.context(self.engine, root, 'ownership')
            desk_chat.take(self.engine, root, context['expected_basis'], ['drawing'])
            if not pipeline.looked(self.record(root)['deck'][''], workspace.sha256_file(root / pipeline.OUTLINE)):
                context = desk_chat.context(self.engine, root, 'look')
                desk_chat.answer(self.engine, root, {'target': 'look', 'expected_basis': context['expected_basis'],
                    'answer': {'questionId': context['requirements']['questionId'], 'choice': 'default', 'response': 'Use the shown default.'}})
        else:
            root = self.researched(deck_target=deck_target, brand=CHOSEN, materials=[])
            self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
            self.submit(root, 'deck-outline', 'outline', {'outline': OUTLINE})
            context = desk_chat.context(self.engine, root, 'look')
            desk_chat.answer(self.engine, root, {'target': 'look', 'expected_basis': context['expected_basis'],
                'answer': {'questionId': context['requirements']['questionId'], 'choice': 'default', 'response': 'Use the shown default.'}})
        context = desk_chat.context(self.engine, root, 'deck')
        return root, {'kind': 'drawing', 'target': 'deck', 'expected_basis': context['expected_basis'],
                      'payload': {'sections': {ident: drawn(spec['artifacts']['section'])
                          for ident, spec in context['requirements']['sections'].items()}}}

    def check_failed_keep(self, operation):
        from runner import pipeline
        import subprocess
        for existing in (False, True):
            with self.subTest(existing=existing):
                root, request = self.drawing_request(existing)
                before = desk_chat._files(root)
                repo = self.engine.space().repo
                head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo)
                receiver, name = (self.slides, 'cited') if operation == 'citation' else (pipeline, 'keep_deck')
                with mock.patch.object(receiver, name, side_effect=WorkspaceError('synthetic final check failed')):
                    with self.assertRaisesRegex(WorkspaceError, 'synthetic final check failed'):
                        desk_chat.submit(self.engine, root, request)
                self.assertEqual(desk_chat._files(root), before)
                self.assertEqual(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo), head)
                self.assertEqual((root / 'deck.pptx').is_file(), existing)

    def test_initial_and_existing_drawing_citation_failure_preserves_canonical(self):
        self.check_failed_keep('citation')

    def test_initial_and_existing_drawing_save_failure_preserves_canonical(self):
        self.check_failed_keep('save')


class ConversationCompletionTests(ConversationReviewFixTests):
    test_binary_zip_deck_part_outline_and_design_contexts = None
    test_binary_zip_pending_local_part_outline_and_design_contexts = None
    test_google_plugin_writers_refuse_chat_ownership_before_transport = None
    test_initial_and_existing_drawing_citation_failure_preserves_canonical = None
    test_initial_and_existing_drawing_save_failure_preserves_canonical = None

    def guide(self):
        from runner_support import DOCUMENT
        root = self.researched(materials=['document'], title='Ready guide')
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        self.submit(root, 'document', 'text', {'text': DOCUMENT})
        return root

    def test_main_ready_records_explicit_person_without_runner_jobs(self):
        from runner import page
        root = self.guide()
        count = len(self.workers.jobs)
        seen = workspace.sha256_file(root / 'document.md')
        handler = page.RunnerPage(0, self.engine)
        with mock.patch.object(self.engine, 'carry_on', side_effect=AssertionError('runner')):
            handler.drafted('/api/drafts/ready', {'path': str(root), 'name': 'document', 'seen': seen})
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['document'], 'approved')
        self.assertEqual(self.record(root)['execution'], 'conversation')
        self.assertNotIn('research_contract', self.record(root))
        self.assertEqual(len(self.workers.jobs), count)

    def test_ready_checked_cli_and_incomplete_version_refusals(self):
        root = self.create()
        self.submit(root, 'blueprint', 'outline', {'text': BLUEPRINT})
        context = desk_chat.context(self.engine, root, 'ready/blueprint')
        request = {'target': 'blueprint', 'expected_basis': context['expected_basis'],
                   'seen': context['requirements']['seen'], 'response': 'I read it and mark it ready.'}
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, root, request)
        self.assertEqual(desk_chat._files(root), before)
        other = self.guide()
        context = desk_chat.context(self.engine, other, 'ready/document')
        request.update(target='document', expected_basis=context['expected_basis'], seen='outdated')
        before = desk_chat._files(other)
        with self.assertRaises(WorkspaceError):
            desk_chat.ready(self.engine, other, request)
        self.assertEqual(desk_chat._files(other), before)
        request['seen'] = context['requirements']['seen']
        args = studio.parser().parse_args(['desk', 'ready', '--folder', str(other), '--input', '-'])
        with mock.patch('sys.stdin', io.StringIO(json.dumps(request))):
            studio.desk_command(args, make=lambda: self.engine, out=io.StringIO())
        self.assertEqual(workspace.person_statuses(other, workspace.load(other))['document'], 'approved')

    def test_retained_helper_handlers_refuse_conversation_decisions_and_mode(self):
        import desk
        root = self.guide()
        before = desk_chat._files(root)
        for route, payload in [('/api/decide', {'artifact': 'document', 'decision': 'skip'}),
                               ('/api/decide', {'artifact': 'document', 'decision': 'approve', 'seen': workspace.sha256_file(root / 'document.md')}),
                               ('/api/approval', {'mode': 'chat'})]:
            with self.subTest(route=route, payload=payload), self.assertRaises(WorkspaceError):
                desk.Page(0).write(route, {'path': str(root), **payload})
            self.assertEqual(desk_chat._files(root), before)

    def pending(self):
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True
        root, link, baseline, original = self.google_desk()
        previous = self.record(root)['deck']['']
        original_files = desk_chat._files(root)
        self.proposed(root)
        context = desk_chat.context(self.engine, root, 'design')
        desk_chat.answer(self.engine, root, self.reply(context))
        return root, link, baseline, original, previous, original_files

    def resolution(self, root):
        context = desk_chat.context(self.engine, root, 'return-delivered')
        return context, {'target': 'return-delivered', 'expected_basis': context['expected_basis'],
                         'seen': context['requirements']['seen'], 'response': 'Set aside my local draft and return to the delivered deck.'}

    def test_return_delivered_restores_actual_old_state_and_archives_repeated_local_edits(self):
        root, link, baseline, original, previous, original_files = self.pending()
        first = workspace.load(root)['pending_local_decks']['deck']
        self.submit(root, 'deck/check-yourself/notes', 'part', {'text': 'Another explicit local note.'})
        self.assertEqual(workspace.load(root)['pending_local_decks']['deck']['restore_sha256'], first['restore_sha256'])
        context, request = self.resolution(root)
        self.assertIn('delivered', context['requirements']['summary'].lower())
        local = (root / 'deck/local-draft.pptx').read_bytes()
        with mock.patch.object(self.slides, 'drive_import', side_effect=AssertionError('delivery')):
            desk_chat.return_delivered(self.engine, root, request)
        session = workspace.load(root)
        self.assertFalse(session.get('pending_local_decks'))
        self.assertEqual((link.read_bytes(), baseline.read_bytes()), original[:2])
        self.assertEqual(session['artifacts']['deck'], json.loads(original_files['.training-studio/session.json'])['artifacts']['deck'])
        self.assertEqual(self.record(root)['deck'][''], previous)
        self.assertEqual(workspace.person_statuses(root, session)['deck'], 'approved')
        self.assertTrue(any(path.read_bytes() == local for path in (root / 'history').rglob('*.pptx')))
        for name, data in original_files.items():
            if name.startswith(('deck/', 'work/deck/')):
                self.assertEqual((root / name).read_bytes(), data)

    def test_return_delivered_refuses_changed_basis_dependencies_pending_ready_and_failure(self):
        root, _, _, _, _, _ = self.pending()
        context, request = self.resolution(root)
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            self.engine.mark_ready(root, 'deck', request['seen'])
        self.assertEqual(desk_chat._files(root), before)
        request['seen'] = 'different'
        with self.assertRaises(WorkspaceError):
            desk_chat.return_delivered(self.engine, root, request)
        self.assertEqual(desk_chat._files(root), before)
        request['seen'] = context['requirements']['seen']
        from runner import gitstate
        with mock.patch.object(gitstate, 'commit', side_effect=WorkspaceError('synthetic publication failure')):
            with self.assertRaises(WorkspaceError):
                desk_chat.return_delivered(self.engine, root, request)
        self.assertEqual(desk_chat._files(root), before)
        (root / 'blueprint.md').write_bytes((root / 'blueprint.md').read_bytes() + b'\nChanged upstream.\n')
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.return_delivered(self.engine, root, request)
        self.assertEqual(desk_chat._files(root), before)
        with self.assertRaises(WorkspaceError):
            self.resolution(root)

    def test_initial_google_drawing_can_be_set_aside_then_select_local_deck(self):
        root, request = self.drawing_request(False, deck_target='google')
        desk_chat.submit(self.engine, root, request)
        context, request = self.resolution(root)
        self.assertIn('no delivered', context['requirements']['summary'].lower())
        args = studio.parser().parse_args(['desk', 'return-delivered', '--folder', str(root), '--input', '-'])
        with mock.patch('sys.stdin', io.StringIO(json.dumps(request))):
            studio.desk_command(args, make=lambda: self.engine, out=io.StringIO())
        self.assertNotIn('deck', workspace.load(root)['artifacts'])
        self.assertFalse((root / 'deck-link.md').exists())
        context = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, context['expected_basis'], list(desk_chat.KINDS), deck_target='pptx')
        self.assertEqual(workspace.load(root)['settings']['deck_target'], 'pptx')

    def test_snapshot_is_bound_before_pending_and_never_silently_replaced(self):
        from runner import pipeline
        self.slides.design, self.slides.judges = True, True
        self.slides.have['local'] = True
        root, _, _, _ = self.google_desk()
        path = root / 'deck/delivered-state.json'
        path.write_text('{"unrecognized":"original state"}\n')
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.context(self.engine, root, 'deck/check-yourself/title')
        self.assertEqual(desk_chat._files(root), before)
        path.unlink()
        self.proposed(root)
        self.assertTrue(path.is_file())
        self.assertFalse(workspace.load(root).get('pending_local_decks'))
        context = desk_chat.context(self.engine, root, 'design')
        path.write_bytes(path.read_bytes() + b'\n')
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            desk_chat.answer(self.engine, root, self.reply(context))
        self.assertEqual(desk_chat._files(root), before)
        with self.assertRaises(WorkspaceError):
            desk_chat.context(self.engine, root, 'design')
        self.assertTrue((root / pipeline.OUTLINE).is_file())

    def test_ready_and_return_final_recheck_refuse_a_concurrent_writer(self):
        from runner import gitstate
        from contextlib import contextmanager
        pending, _, _, _, _, _ = self.pending()
        _, returning = self.resolution(pending)
        guide = self.guide()
        context = desk_chat.context(self.engine, guide, 'ready/document')
        approving = {'target': 'document', 'expected_basis': context['expected_basis'],
                     'seen': context['requirements']['seen'], 'response': 'Mark the guide ready.'}
        real = gitstate.workspace_locked
        for root, operation, request in [(pending, desk_chat.return_delivered, returning), (guide, desk_chat.ready, approving)]:
            with self.subTest(operation=operation.__name__):
                calls = 0
                external = root / 'blueprint.md'
                @contextmanager
                def racing(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == 3:
                        external.write_bytes(external.read_bytes() + b'\nConcurrent change.\n')
                    with real(*args, **kwargs):
                        yield
                before = desk_chat._files(root)
                with mock.patch.object(gitstate, 'workspace_locked', racing):
                    with self.assertRaises(WorkspaceError):
                        operation(self.engine, root, request)
                after = desk_chat._files(root)
                self.assertEqual({key: data for key, data in after.items() if key != 'blueprint.md'},
                                 {key: data for key, data in before.items() if key != 'blueprint.md'})

    def test_retained_handlers_preserve_runner_and_standalone_saved_behavior(self):
        import desk
        root = self.guide()
        record = self.record(root)
        record['execution'] = 'runner'
        self.engine._store(root, record)
        result = desk.Page(0).write('/api/decide', {'path': str(root), 'artifact': 'document',
                                  'decision': 'approve', 'seen': workspace.sha256_file(root / 'document.md')})
        self.assertEqual(result[0], 200)
        self.assertEqual(workspace.person_statuses(root, workspace.load(root))['document'], 'approved')
        desk.Page(0).write('/api/approval', {'path': str(root), 'mode': 'chat'})
        self.assertEqual(workspace.load(root)['settings']['approval'], 'chat')
        (root / '.training-studio/run.json').unlink()
        desk.Page(0).write('/api/approval', {'path': str(root), 'mode': 'page'})
        self.assertEqual(workspace.load(root)['settings']['approval'], 'page')

    def test_legacy_helper_can_borrow_only_the_exact_owned_workspace_lock(self):
        import home
        import write_guard
        from studio_core.process_lock import ProcessRLock, workspace_lock_path
        root = self.guide()
        record = self.record(root)
        record['execution'] = 'runner'
        self.engine._store(root, record)
        scope = workspace_lock_path(self.engine.space().repo, home.data_root())
        with self.engine.files:
            with write_guard.admitted(root, held=self.engine.files):
                self.assertTrue(self.engine.files.protects(scope))
            self.assertTrue(self.engine.files.protects(scope), 'Inner helper must not release the runner lock.')
        with self.assertRaises(WorkspaceError):
            with write_guard.admitted(root, held=self.engine.files):
                self.fail('An unheld lock cannot authorize a helper write.')
        wrong = ProcessRLock(lambda: home.data_root() / 'other-workspace.lock')
        with wrong, self.assertRaises(WorkspaceError):
            with write_guard.admitted(root, held=wrong):
                self.fail('A different workspace lock cannot authorize this write.')

    def test_legacy_helper_handlers_wait_for_real_shared_process_lock(self):
        import os
        import subprocess
        import sys
        import threading
        import desk
        from studio_core.process_lock import workspace_lock_path
        import home
        root = self.guide()
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(helpers.REPO), str(helpers.SCRIPTS))))
        code = '''from pathlib import Path
import sys
import workspace
from studio_core.process_lock import ProcessRLock
with ProcessRLock(lambda: Path(sys.argv[1]), refusal=ValueError):
    print('locked', flush=True)
    sys.stdin.read(1)
'''
        for route, sent in [('/api/decide', {'artifact': 'document', 'decision': 'skip'}), ('/api/approval', {'mode': 'chat'})]:
            with self.subTest(route=route):
                child = subprocess.Popen([sys.executable, '-c', code, str(workspace_lock_path(self.engine.space().repo, home.data_root()))], env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                finished, started, errors = threading.Event(), threading.Event(), []
                def call():
                    started.set()
                    try:
                        desk.Page(0).write(route, {'path': str(root), **sent})
                    except WorkspaceError as error:
                        errors.append(str(error))
                    finally:
                        finished.set()
                thread = threading.Thread(target=call)
                try:
                    self.assertEqual(child.stdout.readline().strip(), 'locked')
                    before = desk_chat._files(root)
                    thread.start()
                    self.assertTrue(started.wait(2))
                    self.assertFalse(finished.wait(.15))
                    self.assertEqual(desk_chat._files(root), before)
                    child.communicate('x', timeout=5)
                    thread.join(5)
                    self.assertTrue(finished.is_set())
                    self.assertTrue(errors)
                    self.assertEqual(desk_chat._files(root), before)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate()
                    if thread.ident:
                        thread.join(5)

    def test_completion_and_helper_routes_refuse_worker_and_unknown_saved_jobs(self):
        import desk
        root = self.guide()
        marker = root / self.engines.IN_HAND
        marker.write_text('synthetic saved worker')
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            self.engine.mark_ready(root, 'document', workspace.sha256_file(root / 'document.md'))
        for route, payload in [('/api/decide', {'artifact': 'document', 'decision': 'skip'}), ('/api/approval', {'mode': 'chat'})]:
            with self.subTest(route=route), self.assertRaises(WorkspaceError):
                desk.Page(0).write(route, {'path': str(root), **payload})
        self.assertEqual(desk_chat._files(root), before)
        marker.unlink()
        record = self.record(root)
        record['drafts']['jobs'] = 'unknown'
        self.engine._store(root, record)
        before = desk_chat._files(root)
        with self.assertRaises(WorkspaceError):
            desk.Page(0).write('/api/approval', {'path': str(root), 'mode': 'chat'})
        self.assertEqual(desk_chat._files(root), before)
