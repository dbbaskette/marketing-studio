"""Conversation uses checked Presentation Studio materials without another assistant."""
import copy
import json
from pathlib import Path
from unittest import mock

import runner_support
from runner import decks, desk_chat
from runner.steps import build
from workspace import WorkspaceError


class ConversationTests(runner_support.DeskCase):
    def create(self, scope=None, **changes):
        form = {**runner_support.FORM, 'flow': 'desk', 'scope': scope or ['outline'], **changes}
        return Path(desk_chat.create(self.engine, form)['path'])

    def submit(self, root, target, kind, payload):
        context = desk_chat.context(self.engine, root, target)
        return desk_chat.submit(self.engine, root, {
            'kind': kind, 'target': target, 'expected_basis': context['expected_basis'],
            'payload': payload})

    def test_create_requires_explicit_bounded_scope_without_readiness_or_wake(self):
        with mock.patch.object(self.engine, 'ready', side_effect=AssertionError('assistant readiness')), \
                mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            root = self.create(['outline', 'outline'])
        record = self.record(root)
        self.assertEqual(record['flow'], 'desk')
        self.assertEqual(record['execution'], 'conversation')
        self.assertEqual(record['conversation_scope'], ['outline'])
        self.assertFalse(record['steps'])
        self.assertFalse(record['gates'])
        with self.assertRaisesRegex(WorkspaceError, 'scope'):
            desk_chat.create(self.engine, runner_support.FORM)
        with self.assertRaisesRegex(WorkspaceError, 'scope'):
            self.create(['publish'])

    def test_absent_outline_context_checked_submission_and_changed_input_refusal(self):
        root = self.create()
        context = desk_chat.context(self.engine, root, 'outline')
        self.assertIsNone(context['inputs']['outline'])
        request = {'kind': 'outline', 'target': 'outline',
                   'expected_basis': context['expected_basis'],
                   'payload': {'outline': runner_support.LONG_OUTLINE}}
        record = self.record(root)
        record['form']['goal'] = 'A changed request'
        decks.write_run(root, record)
        with self.assertRaisesRegex(WorkspaceError, 'changed'):
            desk_chat.submit(self.engine, root, request)
        self.assertFalse((root / 'outline.json').exists())
        self.submit(root, 'outline', 'outline', {'outline': runner_support.LONG_OUTLINE})
        self.assertTrue((root / 'outline.json').is_file())
        self.assertFalse(any(g.get('state') == 'approved' for g in self.record(root)['gates'].values()))
        self.assertIsNone(decks.delivered(root))

    def test_outline_only_never_permits_other_materials_or_kind_mismatch(self):
        root = self.create()
        for target in ('research', 'drawing', 'brief'):
            with self.assertRaisesRegex(WorkspaceError, 'scope'):
                desk_chat.context(self.engine, root, target)
        context = desk_chat.context(self.engine, root, 'outline')
        with self.assertRaisesRegex(WorkspaceError, 'kind'):
            desk_chat.submit(self.engine, root, {'kind': 'text', 'target': 'outline',
                'expected_basis': context['expected_basis'], 'payload': {'text': 'invented'}})

    def test_scope_change_preserves_materials_approvals_and_execution(self):
        root = self.create()
        context = desk_chat.context(self.engine, root, 'scope')
        before = self.record(root)
        desk_chat.set_scope(self.engine, root, context['expected_basis'], ['outline', 'part'])
        after = self.record(root)
        self.assertEqual(after['conversation_scope'], ['outline', 'part'])
        for key in ('steps', 'gates', 'execution'):
            self.assertEqual(after[key], before[key])
        with self.assertRaisesRegex(WorkspaceError, 'changed'):
            desk_chat.set_scope(self.engine, root, context['expected_basis'], ['text'])

    def test_recovery_and_wake_leave_conversation_and_marker_untouched(self):
        root = self.create()
        marker = root / 'work/step.lock'
        marker.parent.mkdir(exist_ok=True)
        marker.write_text('conversation-owned input')
        before = (root / 'run.json').read_bytes()
        with mock.patch('runner.engine.research_cli.unlock', side_effect=AssertionError('unlock')), \
                mock.patch.object(self.engine, '_original', side_effect=AssertionError('recover')):
            self.engine.resume()
            self.engine.wake(root)
            self.engine._work(root, self.engine._run(root))
        self.assertEqual(marker.read_text(), 'conversation-owned input')
        self.assertEqual((root / 'run.json').read_bytes(), before)
        with self.assertRaisesRegex(WorkspaceError, 'progress|worker'):
            desk_chat.set_scope(self.engine, root,
                               desk_chat.context(self.engine, root, 'scope')['expected_basis'], ['text'])

    def test_narrow_handoff_refuses_without_transferring_execution(self):
        root = self.create()
        context = desk_chat.context(self.engine, root, 'handoff')
        with self.assertRaisesRegex(WorkspaceError, 'scope'):
            desk_chat.handoff(self.engine, root, context['expected_basis'], ['outline'])
        self.assertEqual(self.record(root)['execution'], 'conversation')

    def test_show_is_read_only_and_local_upload_preserves_original(self):
        original = b'Synthetic source document\n'
        form = {**runner_support.FORM, 'route': 'document', 'scope': ['outline'],
                'reading': 'material', 'source': {'kind': 'upload', 'name': 'source.txt'}}
        root = Path(desk_chat.create(self.engine, form, {'source.txt': original})['path'])
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        shown = desk_chat.show(self.engine, root)
        self.assertEqual(shown['execution'], 'conversation')
        self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes()
                                 for p in root.rglob('*') if p.is_file()})
        self.submit(root, 'outline', 'outline', {'outline': runner_support.LONG_OUTLINE})
        self.assertIn(original, [p.read_bytes() for p in (root / 'sources').rglob('*') if p.is_file()])

    def test_synthetic_conversation_reaches_checked_drawing_then_notes_history(self):
        from stand_ins.slides import sketch
        root = self.create(['outline', 'drawing', 'part'], look='default')
        self.submit(root, 'outline', 'outline', {'outline': runner_support.LONG_OUTLINE})
        context = desk_chat.context(self.engine, root, 'drawing')
        compositions = {}
        by_id = {slide['id']: slide for slide in runner_support.LONG_OUTLINE['slides']}
        for ident, spec in context['requirements']['sections'].items():
            compositions[ident] = {'version': 1, 'title': spec['title'],
                'direction': spec['direction'],
                'slides': [sketch(by_id[slide['id']], spec['prefix']) for slide in spec['slides']]}
        desk_chat.submit(self.engine, root, {'kind': 'drawing', 'target': 'drawing',
            'expected_basis': context['expected_basis'], 'payload': {'sections': compositions}})
        self.assertTrue((root / build.DECK).is_file())
        self.assertTrue(build.read_state(root)['audit'])
        self.assertIsNone(decks.delivered(root))
        ident = runner_support.LONG_OUTLINE['slides'][1]['id']
        target = ident + '/notes'
        context = desk_chat.context(self.engine, root, target)
        desk_chat.save(self.engine, root, {'kind': 'part', 'target': target,
            'expected_basis': context['expected_basis'], 'payload': {'text': 'New speaker notes'}})
        shown = desk_chat.show(self.engine, root)
        self.assertTrue(shown['history'][ident])
        self.assertEqual(next(s for s in shown['outline']['slides'] if s['id'] == ident)['notes'],
                         'New speaker notes')

    def test_drawing_checker_refuses_missing_fixed_words_without_publication(self):
        root = self.create(['outline', 'drawing'], look='default')
        self.submit(root, 'outline', 'outline', {'outline': runner_support.LONG_OUTLINE})
        before = (root / 'outline.json').read_bytes()
        with self.assertRaises(WorkspaceError):
            self.submit(root, 'drawing', 'drawing', {'sections': {}})
        self.assertEqual((root / 'outline.json').read_bytes(), before)
        self.assertFalse((root / build.DECK).exists())

    def test_failed_outline_check_keeps_original_bytes(self):
        root = self.create()
        bad = copy.deepcopy(runner_support.LONG_OUTLINE)
        bad['slides'][1]['notes'] = ''
        with self.assertRaises(WorkspaceError):
            self.submit(root, 'outline', 'outline', {'outline': bad})
        self.assertFalse((root / 'outline.json').exists())

    def test_cli_has_json_commands_without_serving(self):
        from runner import studio
        for command in ('create', 'show', 'save', 'context', 'submit', 'scope', 'handoff'):
            args = ['desk', command]
            if command != 'create':
                args += ['--folder', '/synthetic/deck']
            if command not in ('show', 'context'):
                args += ['--input', '-']
            if command == 'context':
                args += ['--target', 'outline']
            parsed = studio.parser().parse_args(args)
            self.assertEqual(parsed.command, 'desk')

    def test_existing_deck_creation_keeps_original_and_never_imports_google(self):
        from test_flow_routes import DECK
        form = {**runner_support.FORM, 'route': 'existing', 'scope': ['part'],
                'level': 'selected', 'selected': 'Slide 2.',
                'source': {'kind': 'upload', 'name': 'old.pptx'}}
        root = Path(desk_chat.create(self.engine, form, {'old.pptx': DECK})['path'])
        self.assertEqual((root / 'sources/incoming/upload').read_bytes(), DECK)
        self.assertEqual(self.record(root)['form']['selected'], 'Slide 2.')
        google = self.create(['outline'], route='document',
                             source={'kind': 'google', 'link': 'https://docs.example.invalid/document/d/test'})
        with mock.patch.object(self.engine, '_google_ready', side_effect=AssertionError('Google check')):
            with self.assertRaisesRegex(WorkspaceError, 'never fetches'):
                desk_chat.context(self.engine, google, 'outline')
        self.assertFalse((google / 'outline.json').exists())

    def test_idle_page_desk_take_preserves_materials_then_checked_edit(self):
        root = self.start_desk(look='default')
        before = desk_chat._files(root)
        context = desk_chat.context(self.engine, root, 'ownership')
        self.assertIsNone(context['scope'])
        with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            desk_chat.take(self.engine, root, context['expected_basis'], ['part'])
        after = desk_chat._files(root)
        self.assertEqual({k: v for k, v in before.items() if k != 'run.json'},
                         {k: v for k, v in after.items() if k != 'run.json'})
        self.assertEqual(self.record(root)['gates'], json.loads(before['run.json'])['gates'])
        ident = runner_support.LONG_OUTLINE['slides'][1]['id']
        self.submit(root, ident + '/notes', 'part', {'text': 'Notes supplied in chat'})
        self.assertEqual(desk_chat.show(self.engine, root)['outline']['slides'][1]['notes'],
                         'Notes supplied in chat')
        with self.assertRaisesRegex(WorkspaceError, 'changed'):
            desk_chat.take(self.engine, root, context['expected_basis'], ['part'])

    def test_take_refuses_gated_work_and_running_or_queued_work(self):
        root = self.start_desk(look='default')
        context = desk_chat.context(self.engine, root, 'ownership')
        marker = root / 'work/step.lock'
        marker.write_text('canonical active worker')
        before = (root / 'run.json').read_bytes()
        with self.assertRaisesRegex(WorkspaceError, 'progress'):
            desk_chat.take(self.engine, root, context['expected_basis'], ['part'])
        self.assertEqual((root / 'run.json').read_bytes(), before)
        marker.unlink()
        record = self.record(root)
        record['desk_jobs'] = [{'kind': 'words'}]
        decks.write_run(root, record)
        with self.assertRaisesRegex(WorkspaceError, 'progress'):
            desk_chat.take(self.engine, root,
                          desk_chat.context(self.engine, root, 'ownership')['expected_basis'], ['part'])
        record['desk_jobs'] = []
        record['review_requested'] = {'at': 'synthetic pending review'}
        decks.write_run(root, record)
        with self.assertRaisesRegex(WorkspaceError, 'progress'):
            desk_chat.take(self.engine, root,
                          desk_chat.context(self.engine, root, 'ownership')['expected_basis'], ['part'])
        record.pop('review_requested')
        record.pop('flow')
        decks.write_run(root, record)
        with self.assertRaisesRegex(WorkspaceError, 'migration'):
            desk_chat.take(self.engine, root, context['expected_basis'], ['part'])

    def test_scope_only_write_preserves_every_material_byte(self):
        root = self.start_desk(look='default')
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['part'])
        before = desk_chat._files(root)
        context = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, context['expected_basis'], ['part', 'outline'])
        after = desk_chat._files(root)
        self.assertEqual({k: v for k, v in before.items() if k != 'run.json'},
                         {k: v for k, v in after.items() if k != 'run.json'})

    def test_staged_checker_holds_no_process_lock_and_refuses_new_worker(self):
        root = self.create()
        context = desk_chat.context(self.engine, root, 'outline')
        check = self.slides.outline_check
        marker = root / 'work/step.lock'

        def while_checking(*args, **kwargs):
            self.assertFalse(self.engine.files._is_owned())
            with self.engine.files:
                marker.parent.mkdir(exist_ok=True)
                marker.write_text('another process owns canonical output')
            return check(*args, **kwargs)

        with mock.patch.object(self.slides, 'outline_check', side_effect=while_checking):
            with self.assertRaisesRegex(WorkspaceError, 'progress'):
                desk_chat.submit(self.engine, root, {'kind': 'outline', 'target': 'outline',
                    'expected_basis': context['expected_basis'],
                    'payload': {'outline': runner_support.LONG_OUTLINE}})
        self.assertFalse((root / 'outline.json').exists())
        self.assertTrue(marker.is_file())

    def test_look_choice_is_not_inferred_and_design_refusal_is_not_answered(self):
        root = self.create(['outline', 'drawing'])
        self.submit(root, 'outline', 'outline', {'outline': runner_support.LONG_OUTLINE})
        with self.assertRaisesRegex(WorkspaceError, 'explicit choice'):
            desk_chat.context(self.engine, root, 'drawing')
        root = self.create(['outline', 'drawing'], look='default')
        self.submit(root, 'outline', 'outline', {'outline': runner_support.LONG_OUTLINE})
        with mock.patch.object(self.slides, 'outline_start',
                               side_effect=WorkspaceError('Harness Slides needs your design answers')):
            with self.assertRaisesRegex(WorkspaceError, 'design answers'):
                desk_chat.context(self.engine, root, 'drawing')
        self.assertFalse((root / build.DECK).exists())

    def test_text_classification_and_reviewed_research_use_domain_checkers(self):
        from synthesis_fixture import published_bundle
        root = self.create(['text', 'research'], route='document', research=True,
                           source={'kind': 'paste', 'text': 'Synthetic supplied source.'})
        context = desk_chat.context(self.engine, root, 'classification')
        self.assertIn('Synthetic supplied source.', str(context['requirements']['inputs']))
        self.submit(root, 'classification', 'text', {'classification': {
            'kind': 'material', 'reason': 'Synthetic prose, not a slide script.', 'slides': None}})
        self.assertEqual(self.record(root)['classified'], 'material')
        context = desk_chat.context(self.engine, root, 'research')
        self.assertIn('Synthetic supplied source.',
                      str(context['requirements']['inputs']['supplied_sources']))
        with self.assertRaisesRegex(WorkspaceError, 'scope'):
            self.submit(root, 'research-plan', 'text', {'plan': {'purpose': 'planning',
                'scope': 'public-web', 'topic': 'Synthetic', 'items': [{'id': 'q', 'question': 'Why?'}]}})
        case = self.base / 'checked-case'
        facts, manifest = published_bundle(case / 'research')
        (case / '.harness-research').mkdir()
        (case / '.harness-research/synthesis.json').write_text(json.dumps({
            'owner': facts['owner'], 'digest': manifest['digest']}))
        self.submit(root, 'research', 'research', {'case': str(case)})
        self.assertEqual(desk_chat.show(self.engine, root)['research']['digest'], manifest['digest'])
        self.assertFalse(any(g.get('state') == 'approved' for g in self.record(root)['gates'].values()))

    def test_real_processes_compete_on_one_basis_and_recovery_respects_ownership(self):
        import os
        import subprocess
        import sys
        import time
        import helpers
        root = self.create(['text'])
        context = desk_chat.context(self.engine, root, 'scope')
        marker = root / 'work/step.lock'
        marker.parent.mkdir(exist_ok=True)
        marker.write_text('conversation-owned marker')
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(helpers.REPO), str(helpers.SCRIPTS))))
        recovery = subprocess.run([sys.executable, '-c',
            'from runner.engine import Engine; import sys; e=Engine(background=False); e._tidy(); e.wake(sys.argv[1])',
            str(root)], env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(recovery.returncode, 0, recovery.stderr)
        self.assertEqual(marker.read_text(), 'conversation-owned marker')
        marker.unlink()
        # The deleted marker was not an input to this basis.
        self.assertEqual(desk_chat.context(self.engine, root, 'scope')['expected_basis'], context['expected_basis'])
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
    desk_chat.set_scope(Engine(background=False), root, basis, ['text', kind])
    print(json.dumps({'saved': True}))
except Exception as error:
    print(json.dumps({'refused': str(error)}))
'''
        children = []
        try:
            for kind in ('outline', 'part'):
                ready = self.base / ('ready-' + kind)
                child = subprocess.Popen([sys.executable, '-c', code, str(root), context['expected_basis'],
                    str(start), str(ready), kind], env=env, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True)
                children.append(child)
            deadline = time.monotonic() + 10
            while not all((self.base / ('ready-' + kind)).exists() for kind in ('outline', 'part')):
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.01)
            start.touch()
            results = []
            for child in children:
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, out + err)
                self.assertEqual(err, '')
                results.append(json.loads(out))
            self.assertEqual(sum(r.get('saved', False) for r in results), 1, results)
            self.assertIn('changed', next(r['refused'] for r in results if 'refused' in r))
            self.assertEqual(len(self.record(root)['conversation_scope_changes']), 1)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate()


    def test_outline_and_word_edits_preserve_unchanged_sections_and_readiness(self):
        root = self.start_desk(look='default')
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['outline', 'part', 'drawing'])
        state = build.read_state(root)
        sections = list(state['sections'])
        unchanged = root / state['sections'][sections[-1]]['file']
        original = unchanged.read_bytes()
        outline = copy.deepcopy(desk_chat.show(self.engine, root)['outline'])
        outline['slides'][1]['notes'] = 'An explicit outline edit'
        self.submit(root, 'outline', 'outline', {'outline': outline})
        kept = build.read_state(root)['sections'][sections[-1]]
        self.assertTrue(kept['kept'])
        self.assertEqual((root / kept['file']).read_bytes(), original)
        context = desk_chat.context(self.engine, root, 'drawing')
        self.assertNotIn(sections[-1], context['requirements']['sections'])
        self.assertNotEqual(self.record(root)['gates']['gate:build']['state'], 'approved')
        # A direct word edit on an already drawn desk uses fit checks, not a composer.
        root = self.start_desk(look='default', title='Other synthetic deck')
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['part'])
        before_jobs = len(self.workers.of('section'))
        outline = desk_chat.show(self.engine, root)['outline']
        slide = outline['slides'][1]
        self.submit(root, slide['id'] + '/title', 'part', {'text': 'Capacity stays available'})
        self.assertEqual(len(self.workers.of('section')), before_jobs)
        context = desk_chat.context(self.engine, root, slide['id'] + '/points:0:text')
        before = (root / 'outline.json').read_bytes()
        with self.assertRaises(WorkspaceError):
            desk_chat.submit(self.engine, root, {'kind': 'part', 'target': context['target'],
                'expected_basis': context['expected_basis'], 'payload': {'text': 'Too many words ' * 200}})
        self.assertEqual((root / 'outline.json').read_bytes(), before)

    def test_delivered_desk_take_preserves_google_history_then_edit_is_draft(self):
        root = self.start_desk(look='default')
        self.engine.desk_deliver(root, self.engine.view(root)['desk']['expected'])
        delivery = (root / 'deliver.json').read_bytes()
        decisions = copy.deepcopy(self.record(root)['gates'])
        revisions = copy.deepcopy(self.record(root)['revisions'])
        context = desk_chat.context(self.engine, root, 'ownership')
        desk_chat.take(self.engine, root, context['expected_basis'], ['part'])
        self.assertEqual((root / 'deliver.json').read_bytes(), delivery)
        self.assertEqual(self.engine.view(root)['state'], 'finished')
        self.assertEqual(self.record(root)['revisions'], revisions)
        self.assertEqual(self.record(root)['gates'], decisions)
        ident = runner_support.LONG_OUTLINE['slides'][1]['id']
        with mock.patch.object(self.slides, 'drive_import', side_effect=AssertionError('Google write')):
            self.submit(root, ident + '/notes', 'part', {'text': 'A next revision note'})
        record = self.record(root)
        self.assertIsNone(decks.delivered(root))
        self.assertEqual(record['revisions'], revisions)
        self.assertEqual(record['conversation_submissions'][-1]['previous_decisions'], decisions)
        self.assertNotEqual(record['gates']['gate:build']['state'], 'approved')
        self.assertEqual(json.loads(delivery)['url'], revisions[-1]['url'])

    def test_compatible_handoff_uses_current_scope_and_never_invents_approvals(self):
        root = self.create(['text', 'outline', 'drawing'], look='default')
        context = desk_chat.context(self.engine, root, 'handoff')
        with mock.patch.object(self.engine, 'wake') as wake:
            desk_chat.handoff(self.engine, root, context['expected_basis'], context['scope'])
        wake.assert_called_once_with(root)
        record = self.record(root)
        self.assertEqual(record['execution'], 'runner')
        self.assertEqual(record['gates'], {})
        self.assertEqual(record['conversation_handoff']['scope'], context['scope'])

    def test_cli_stdin_json_create_context_and_errors_without_browser(self):
        import io
        from runner import studio
        out = io.StringIO()
        form = {**runner_support.FORM, 'scope': ['text']}
        args = studio.parser().parse_args(['desk', 'create', '--input', '-'])
        with mock.patch('sys.stdin', io.StringIO(json.dumps(form))):
            self.assertEqual(studio.desk_command(args, make=lambda: self.engine, out=out), 0)
        made = json.loads(out.getvalue())
        args = studio.parser().parse_args(['desk', 'context', '--folder', made['path'], '--target', 'brief'])
        out = io.StringIO()
        studio.desk_command(args, make=lambda: self.engine, out=out)
        self.assertEqual(json.loads(out.getvalue())['requirements']['kind'], 'text')
        args = studio.parser().parse_args(['desk', 'create', '--input', '-'])
        with mock.patch('sys.stdin', io.StringIO('{bad')):
            with self.assertRaisesRegex(WorkspaceError, 'valid JSON'):
                studio.desk_command(args, make=lambda: self.engine)


    def test_absent_target_basis_pins_exported_brand_contract_bytes(self):
        root = self.create()
        context = desk_chat.context(self.engine, root, 'outline')
        self.assertFalse((root / build.CONTRACT).exists())
        before = desk_chat._files(root)
        export = self.brand.export

        def changed_contract(folder, *args, **kwargs):
            result = export(folder, *args, **kwargs)
            contract = Path(folder) / 'brand-contract.json'
            # Still a valid contract with unchanged worker reading, but a different
            # byte revision from the one this conversation read before first save.
            contract.write_bytes(contract.read_bytes() + b'\n')
            return result

        with mock.patch.object(self.brand, 'export', side_effect=changed_contract):
            with self.assertRaisesRegex(WorkspaceError, 'changed'):
                desk_chat.submit(self.engine, root, {'kind': 'outline', 'target': 'outline',
                    'expected_basis': context['expected_basis'],
                    'payload': {'outline': runner_support.LONG_OUTLINE}})
        self.assertEqual(desk_chat._files(root), before)


class ConversationTeamTests(runner_support.TeamCase):
    def test_other_driver_cannot_take_or_submit_conversation_work(self):
        root = Path(desk_chat.create(self.engine, {**runner_support.FORM, 'scope': ['text']})['path'])
        self.engine.share()
        with self.be(self.blake):
            self.blake.engine.fetch()
            other = self.theirs(self.blake, root)
            context = desk_chat.context(self.blake.engine, other, 'ownership')
            with self.assertRaisesRegex(WorkspaceError, 'Alex|another|driv'):
                desk_chat.take(self.blake.engine, other, context['expected_basis'], ['text'])
            context = desk_chat.context(self.blake.engine, other, 'brief')
            with self.assertRaisesRegex(WorkspaceError, 'Alex|another|driv'):
                desk_chat.submit(self.blake.engine, other, {'kind': 'text', 'target': 'brief',
                    'expected_basis': context['expected_basis'], 'payload': {'text': 'Wrong driver'}})


class ConversationAnswerTests(runner_support.DeskCase):
    def create(self, scope):
        return Path(desk_chat.create(self.engine, {**runner_support.FORM, 'scope': scope})['path'])

    def outline(self, root):
        context = desk_chat.context(self.engine, root, 'outline')
        desk_chat.submit(self.engine, root, {'kind': 'outline', 'target': 'outline',
            'expected_basis': context['expected_basis'],
            'payload': {'outline': runner_support.LONG_OUTLINE}})

    def answer(self, root, context, answer):
        return desk_chat.answer(self.engine, root, {'target': context['target'],
            'expected_basis': context['expected_basis'], 'answer': answer})

    def drawing_scope(self, root):
        context = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, context['expected_basis'], ['outline', 'drawing'])

    def test_outline_only_later_explicit_default_answer_reaches_usable_drawing(self):
        from stand_ins.slides import sketch
        root = self.create(['outline'])
        self.outline(root)
        with self.assertRaisesRegex(WorkspaceError, 'scope'):
            desk_chat.context(self.engine, root, 'look')
        self.drawing_scope(root)
        before = desk_chat._files(root)
        context = desk_chat.context(self.engine, root, 'look')
        self.assertEqual(desk_chat._files(root), before, 'context never publishes samples')
        self.assertTrue(context['requirements']['offered'])
        self.assertTrue(context['requirements']['previews'])
        with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            self.answer(root, context, {'questionId': context['requirements']['questionId'],
                'choice': 'default', 'response': 'Use the brand default for this drawing.'})
        record = self.record(root)
        self.assertEqual(record['form']['look'], 'default')
        self.assertFalse(any(g.get('state') == 'approved' for g in record['gates'].values()))
        context = desk_chat.context(self.engine, root, 'drawing')
        slides = {s['id']: s for s in runner_support.LONG_OUTLINE['slides']}
        sections = {ident: {'version': 1, 'title': spec['title'], 'direction': spec['direction'],
            'slides': [sketch(slides[slide['id']], spec['prefix']) for slide in spec['slides']]}
            for ident, spec in context['requirements']['sections'].items()}
        desk_chat.submit(self.engine, root, {'kind': 'drawing', 'target': 'drawing',
            'expected_basis': context['expected_basis'], 'payload': {'sections': sections}})
        self.assertTrue((root / build.DECK).is_file())
        self.assertTrue(build.read_state(root)['audit'])
        self.assertIsNone(decks.delivered(root))

    def test_named_look_answer_keeps_words_history_and_real_decisions(self):
        from runner.steps import look
        root = self.create(['outline', 'drawing'])
        self.outline(root)
        before = desk_chat.show(self.engine, root)
        gates = copy.deepcopy(self.record(root)['gates'])
        context = desk_chat.context(self.engine, root, 'look')
        choice = context['requirements']['offered'][-1]['id']
        self.answer(root, context, {'questionId': context['requirements']['questionId'],
                                  'choice': choice, 'response': 'Use this offered look.'})
        after = desk_chat.show(self.engine, root)
        self.assertEqual(look.chosen(root)['choice'], choice)
        self.assertEqual(after['outline']['slides'], before['outline']['slides'])
        self.assertEqual(after['history'], before['history'])
        self.assertEqual(self.record(root)['gates'], gates)
        self.assertEqual(self.record(root)['execution'], 'conversation')

    def test_stale_look_basis_question_and_changed_samples_refuse_without_writes(self):
        root = self.create(['outline', 'drawing'])
        self.outline(root)
        context = desk_chat.context(self.engine, root, 'look')
        answer = {'questionId': context['requirements']['questionId'], 'choice': 'default',
                  'response': 'Use the default look.'}
        before = desk_chat._files(root)
        with self.assertRaisesRegex(WorkspaceError, 'question'):
            self.answer(root, context, {**answer, 'questionId': 'wrong'})
        self.assertEqual(desk_chat._files(root), before)
        record = self.record(root)
        record['form']['goal'] = 'Different current input'
        decks.write_run(root, record)
        before = desk_chat._files(root)
        with self.assertRaisesRegex(WorkspaceError, 'changed'):
            self.answer(root, context, answer)
        self.assertEqual(desk_chat._files(root), before)

    def sample_rewriter(self, rewrite):
        samples = self.brand.look_samples

        def changed(outline, output, *args, **kwargs):
            result = samples(outline, output, *args, **kwargs)
            manifest = json.loads((Path(output) / 'looks.json').read_text())
            for sample in manifest['samples']:
                if sample.get('image'):
                    picture = Path(sample['image'])
                    picture.write_bytes(rewrite(picture.read_bytes()))
            return result
        return changed

    def test_same_visual_preview_different_text_time_metadata_has_stable_basis(self):
        import zlib
        root = self.create(['outline', 'drawing'])
        self.outline(root)
        original = desk_chat.context(self.engine, root, 'look')
        count = 0

        def metadata(data):
            nonlocal count
            count += 1
            def chunk(kind, body):
                return len(body).to_bytes(4, 'big') + kind + body \
                    + zlib.crc32(kind + body).to_bytes(4, 'big')
            # Both timestamp and arbitrary writer text change at each rendering.
            incidental = chunk(b'tEXt', b'Writer\x00render-' + str(count).encode()) \
                + chunk(b'tIME', bytes([7, 234, 10, 28, 12, 0, count % 60]))
            return data[:-12] + incidental + data[-12:]

        before = desk_chat._files(root)
        with mock.patch.object(self.brand, 'look_samples', side_effect=self.sample_rewriter(metadata)):
            current = desk_chat.context(self.engine, root, 'look')
            self.assertEqual(current['expected_basis'], original['expected_basis'])
            self.assertEqual(current['requirements'], original['requirements'])
            self.assertEqual(desk_chat._files(root), before)
            self.answer(root, original, {'questionId': original['requirements']['questionId'],
                'choice': 'default', 'response': 'Use the shown brand default.'})

    def test_changed_visual_preview_refuses_answer_without_material_or_history_changes(self):
        from stand_ins import assets
        root = self.create(['outline', 'drawing'])
        self.outline(root)
        context = desk_chat.context(self.engine, root, 'look')
        before = desk_chat._files(root)
        with mock.patch.object(self.brand, 'look_samples',
                side_effect=self.sample_rewriter(lambda data: assets.png(shade=235))):
            with self.assertRaisesRegex(WorkspaceError, 'changed'):
                self.answer(root, context, {'questionId': context['requirements']['questionId'],
                    'choice': 'default', 'response': 'Use the displayed default.'})
        self.assertEqual(desk_chat._files(root), before)

    def test_truncated_or_bad_checksum_preview_is_refused_without_context_publication(self):
        root = self.create(['outline', 'drawing'])
        self.outline(root)
        before = desk_chat._files(root)
        for rewrite in (lambda data: data[:-1],
                        lambda data: data[:-5] + bytes([data[-5] ^ 1]) + data[-4:]):
            with self.subTest(rewrite=rewrite), mock.patch.object(self.brand, 'look_samples',
                    side_effect=self.sample_rewriter(rewrite)):
                with self.assertRaisesRegex(WorkspaceError, 'PNG'):
                    desk_chat.context(self.engine, root, 'look')
                self.assertEqual(desk_chat._files(root), before)

    def design_question(self, root):
        from stand_ins import slides
        command = slides.StandIn()
        command.design = True
        self.slides = self.real[0](runtime=Path('stand-in'), run=command, read=command.read)
        project = root / 'work'
        project.mkdir(exist_ok=True)
        fixture = Path(__file__).parent / 'fixtures/visual-contract/proposal.json'
        return self.slides.design_propose(project, fixture)

    def test_actual_companion_question_revision_response_contract_is_preserved(self):
        root = self.create(['drawing'])
        status = self.design_question(root)
        context = desk_chat.context(self.engine, root, 'design')
        self.assertEqual(context['requirements']['question']['id'], status['question']['id'])
        before = desk_chat._files(root)
        reply = {'questionId': status['question']['id'], 'planRevision': status['revision'],
                 'decision': 'approve', 'feedback': 'I approve the displayed whole design plan.'}
        with mock.patch.object(self.engine, 'wake', side_effect=AssertionError('wake')):
            self.answer(root, context, reply)
        self.assertTrue(self.slides.design_check(root / 'work')['buildAllowed'])
        self.assertTrue(any(call[:2] == ['design', 'respond'] for call in self.slides.run.calls))
        self.assertEqual(self.record(root)['gates'], {})
        self.assertEqual(self.record(root)['conversation_answers'][-1]['answer'], reply)
        after = desk_chat._files(root)
        untouched = {name: data for name, data in before.items()
                     if name != 'run.json' and not name.startswith('work/.harness-slides/design/')}
        self.assertEqual(untouched, {name: after[name] for name in untouched})
        with self.assertRaisesRegex(WorkspaceError, 'question|changed'):
            self.answer(root, context, reply)

    def test_actual_companion_stale_revision_and_closed_question_refuse(self):
        root = self.create(['drawing'])
        status = self.design_question(root)
        context = desk_chat.context(self.engine, root, 'design')
        reply = {'questionId': status['question']['id'], 'planRevision': 'old-revision',
                 'decision': 'approve', 'feedback': 'I approve the displayed plan.'}
        before = desk_chat._files(root)
        with self.assertRaisesRegex(WorkspaceError, 'revision|question'):
            self.answer(root, context, reply)
        self.assertEqual(desk_chat._files(root), before)
        self.slides.design_respond(root / 'work', {**reply, 'planRevision': status['revision']})
        before = desk_chat._files(root)
        with self.assertRaisesRegex(WorkspaceError, 'question|changed'):
            self.answer(root, context, {**reply, 'planRevision': status['revision']})
        self.assertEqual(desk_chat._files(root), before)

    def test_answer_cannot_publish_after_canonical_worker_acquires_output(self):
        root = self.create(['drawing'])
        status = self.design_question(root)
        context = desk_chat.context(self.engine, root, 'design')
        respond = self.slides.design_respond
        marker = root / 'work/step.lock'
        original = desk_chat._files(root)

        def concurrently(*args, **kwargs):
            self.assertFalse(self.engine.files._is_owned())
            answered = respond(*args, **kwargs)
            with self.engine.files:
                marker.write_text('canonical worker acquired')
            return answered

        with mock.patch.object(self.slides, 'design_respond', side_effect=concurrently):
            with self.assertRaisesRegex(WorkspaceError, 'progress'):
                self.answer(root, context, {'questionId': status['question']['id'],
                    'planRevision': status['revision'], 'decision': 'approve',
                    'feedback': 'I approve this displayed plan.'})
        after = desk_chat._files(root)
        after.pop('work/step.lock')
        self.assertEqual(after, original)
        self.assertFalse(self.slides.design_status(root / 'work')['buildAllowed'])

    def test_answer_cli_is_explicit_and_no_submission_kind_is_added(self):
        from runner import studio
        args = studio.parser().parse_args(['desk', 'answer', '--folder', '/synthetic/deck', '--input', '-'])
        self.assertEqual(args.desk_action, 'answer')
        self.assertEqual(desk_chat.KINDS, ('text', 'outline', 'research', 'drawing', 'part'))
