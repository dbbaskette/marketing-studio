"""Conversation work uses the desk without starting another assistant."""

import isolation  # noqa: F401
import json
import subprocess
import sys
from unittest.mock import patch

import blog_runner
import desk
import desk_jobs
import desk_chat
import studio
from test_desk import DeskCase, DRAFT


class ConversationTests(DeskCase):
    def create(self, **data):
        return desk_chat.create(self.root, {'title': 'Synthetic', 'manuscript': DRAFT, **data})

    def test_creation_pins_conversation_and_never_queues(self):
        with patch('desk_jobs.begin', side_effect=AssertionError('nested job')):
            made = self.create()
        self.assertEqual(made['execution'], 'conversation')
        self.assertEqual(desk_jobs.jobs(self.root, made['id']), [])
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['flow'], 'desk')
        self.assertEqual(record['execution'], 'conversation')

    def test_focused_outline_stays_focused_and_cannot_auto_begin_or_retry(self):
        made = desk_chat.create(
            self.root,
            {
                'title': 'Synthetic',
                'way': 'topic',
                'point': 'Retries save work.',
                'scope': 'outline',
            },
        )
        ident = made['id']
        self.assertEqual(desk.read_start(self.root, ident)['steps'], ['outline'])
        with patch('desk_jobs._queue_step', side_effect=AssertionError('nested job')):
            self.assertIsNone(desk_jobs.begin(self.root, ident))
            with self.assertRaisesRegex(ValueError, 'conversation'):
                desk_jobs.retry(self.root, ident)
        context = desk_chat.context(self.root, ident, 'outline')
        result = desk_chat.submit(
            self.root,
            ident,
            {
                'kind': 'outline',
                'target': 'outline',
                'expected_basis': context['expected_basis'],
                'payload': {
                    'title': 'Synthetic',
                    'opening_brief': 'Why retries help.',
                    'sections': [{'heading': 'Retry', 'brief': 'Keep checkpoints.'}],
                },
            },
        )
        self.assertEqual(len(result['draft']['sections']), 1)
        self.assertFalse(
            (self.folder(ident) / 'DRAFT.md').read_text().strip().endswith('Keep checkpoints.')
        )
        with self.assertRaisesRegex(ValueError, 'scope'):
            desk_chat.context(self.root, ident, 'draft')

    def test_part_saves_keep_history_and_refuse_same_part_conflict(self):
        made = self.create()
        ident = made['id']
        old = made['draft']['revision']
        desk_chat.save(self.root, ident, old, 'opening', 'Changed in conversation.')
        self.assertEqual(
            desk.versions(self.root, ident, 'opening')[0]['text'], 'An opening paragraph.'
        )
        with self.assertRaises(ValueError):
            desk_chat.save(self.root, ident, old, 'opening', 'Overwrites work.')
        part = made['draft']['sections'][0]['id']
        result = desk_chat.save(self.root, ident, old, part, 'A different section.')
        self.assertEqual(result['draft']['opening'], 'Changed in conversation.')

    def test_context_binds_initial_draft_to_upstream_changes(self):
        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retries save work.'}
        )
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'draft')
        desk.save(self.root, ident, made['draft']['revision'], 'title', 'Changed title')
        with self.assertRaisesRegex(ValueError, 'changed'):
            desk_chat.submit(
                self.root,
                ident,
                {
                    'kind': 'text',
                    'target': 'draft',
                    'expected_basis': context['expected_basis'],
                    'payload': {'content': DRAFT},
                },
            )
        context = desk_chat.context(self.root, ident, 'draft')
        result = desk_chat.submit(
            self.root,
            ident,
            {
                'kind': 'text',
                'target': 'draft',
                'expected_basis': context['expected_basis'],
                'payload': {'content': DRAFT},
            },
        )
        self.assertTrue(result['markdown'].strip())
        self.assertEqual(result['execution'], 'conversation')

    def test_mismatched_kind_and_unknown_target_refuse_without_changes(self):
        made = self.create()
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'opening')
        with self.assertRaisesRegex(ValueError, 'kind'):
            desk_chat.submit(
                self.root,
                ident,
                {
                    'kind': 'research',
                    'target': 'opening',
                    'expected_basis': context['expected_basis'],
                    'payload': {'content': 'Fabricated'},
                },
            )
        with self.assertRaises(ValueError):
            desk_chat.context(self.root, ident, '../../outside')
        self.assertEqual(desk_chat.read(self.root, ident)['draft'], made['draft'])

    def test_team_and_worker_refuse_checked_submission(self):
        made = self.create()
        ident = made['id']
        with patch('team_workspace.guard', side_effect=ValueError('Other driver')):
            with self.assertRaisesRegex(ValueError, 'Other driver'):
                desk_chat.save(self.root, ident, 1, 'opening', 'No.')
        with patch('desk_jobs._busy', side_effect=ValueError('A worker is active')):
            with self.assertRaisesRegex(ValueError, 'worker'):
                desk_chat.save(self.root, ident, 1, 'opening', 'No.')

    def test_defaults_are_pinned_but_voice_remains_tone_only(self):
        with (
            patch(
                'blog_runner.settings', return_value={'defaults': {'author': 'Synthetic Author'}}
            ),
            patch('brand_skill.defaults', return_value={'brand': 'demo', 'variant': 'blog'}),
            patch(
                'brand_skill.snapshot',
                return_value={
                    'brand': 'demo',
                    'variant': 'blog',
                    'documents': {'guide': 'Synthetic rules'},
                },
            ),
        ):
            made = self.create(tone='Direct')
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['author'], 'Synthetic Author')
        self.assertEqual(record['voice'], {'mode': 'tone', 'tone': 'Direct'})
        context = desk_chat.context(self.root, made['id'], 'opening')
        self.assertEqual(context['inputs']['author'], 'Synthetic Author')
        self.assertEqual(context['inputs']['brand']['brand'], 'demo')

    def test_handoff_requires_current_basis_and_explicit_valid_scope(self):
        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retry.'}
        )
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'outline')
        with patch('desk_jobs.begin') as begin:
            with self.assertRaises(ValueError):
                desk_chat.handoff(self.root, ident, context['expected_basis'], ['publish'])
            self.assertFalse(begin.called)
            handed = desk_chat.handoff(self.root, ident, context['expected_basis'], ['outline'])
            self.assertEqual(handed['execution'], 'runner')
            begin.assert_called_once_with(self.root, ident)
        self.assertEqual(desk.read_start(self.root, ident)['steps'], ['outline'])

    def test_cli_stdin_create_context_submit(self):
        script = isolation.SCRIPTS / 'studio.py'

        def run(*args, data=None):
            result = subprocess.run(
                [sys.executable, str(script), '--root', str(self.root), 'desk', *args],
                input=json.dumps(data) if data is not None else None,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

        made = run('create', '--input', '-', data={'title': 'Synthetic', 'manuscript': DRAFT})
        scope_context = run('context', '--article', made['id'], '--target', 'draft')
        scoped = run(
            'scope',
            '--article',
            made['id'],
            '--input',
            '-',
            data={'expected_basis': scope_context['expected_basis'], 'scope': 'part'},
        )
        self.assertEqual(scoped['scope'], 'part')
        context = run('context', '--article', made['id'], '--target', 'opening')
        saved = run(
            'submit',
            '--article',
            made['id'],
            '--input',
            '-',
            data={
                'kind': 'part',
                'target': 'opening',
                'expected_basis': context['expected_basis'],
                'payload': {'text': 'Checked from stdin.'},
            },
        )
        self.assertEqual(saved['draft']['opening'], 'Checked from stdin.')

    def test_current_gated_cli_create_refuses_with_desk_guidance(self):
        args = blog_runner.add_parser
        self.assertIsNotNone(args)
        result = subprocess.run(
            [
                sys.executable,
                str(isolation.SCRIPTS / 'studio.py'),
                '--root',
                str(self.root),
                'run',
                'create',
                '--title',
                'Synthetic',
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('desk create --input', result.stderr)

    def test_two_cli_processes_cannot_overwrite_the_same_basis(self):
        made = self.create()
        context = desk_chat.context(self.root, made['id'], 'opening')
        command = [
            sys.executable,
            str(isolation.SCRIPTS / 'studio.py'),
            '--root',
            str(self.root),
            'desk',
            'submit',
            '--article',
            made['id'],
            '--input',
            '-',
        ]
        processes = [
            subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        for number, process in enumerate(processes):
            process.stdin.write(
                json.dumps(
                    {
                        'kind': 'part',
                        'target': 'opening',
                        'expected_basis': context['expected_basis'],
                        'payload': {'text': f'Writer {number}.'},
                    }
                )
            )
            process.stdin.close()
            process.stdin = None
        results = [process.communicate(timeout=30) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1])
        rejected = [
            error
            for process, (_, error) in zip(processes, results, strict=True)
            if process.returncode
        ]
        self.assertIn('changed', rejected[0])
        self.assertEqual(len(desk.versions(self.root, made['id'], 'opening')), 1)

    def test_explicit_blank_defaults_and_existing_pins_are_preserved(self):
        with patch('brand_skill.defaults', side_effect=AssertionError('explicit choice')):
            made = self.create(author='', brand='', tone='Warm')
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['author'], '')
        self.assertNotIn('brand', record)
        self.assertEqual(record['voice'], {'mode': 'tone', 'tone': 'Warm'})

    def test_recovery_and_page_inspection_leave_conversation_start_jobs_alone(self):
        import tool_jobs

        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retry.'}
        )
        ident = made['id']
        job_id = 'a' * 32
        folder = self.root / '.blog-runs' / 'tools'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (job_id + '.json')
        value = {
            'schema': 1,
            'id': job_id,
            'kind': 'desk-outline',
            'status': 'working',
            'metadata': {'article': ident, 'desk': {'start': True}},
        }
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        tool_jobs.recover(self.root)
        self.assertEqual(path.read_bytes(), before)
        value['status'] = 'queued'
        path.write_text(json.dumps(value))
        queued = path.read_bytes()
        worker = patch('desk_jobs._queue_step', side_effect=AssertionError('nested job'))
        with worker:
            tool_jobs.once(
                blog_runner.Engine(self.root, worker=lambda *a, **k: self.fail('duplicate worker'))
            )
        self.assertEqual(path.read_bytes(), queued)
        page = desk_jobs.view(self.root, ident)
        self.assertIsNone(page['start'])
        self.assertEqual(page['execution'], 'conversation')
        desk_chat.read(self.root, ident)
        self.assertEqual(
            studio.read_json(self.folder(ident) / 'session.json')['execution'], 'conversation'
        )

    def test_research_refuses_raw_report_and_accepts_checked_companion_bundle(self):
        import hashlib
        from studio_core import research_contract

        made = desk_chat.create(
            self.root,
            {
                'title': 'Synthetic',
                'way': 'topic',
                'point': 'Research retry behavior.',
                'scope': 'research',
            },
        )
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'research')
        request = {
            'kind': 'research',
            'target': 'research',
            'expected_basis': context['expected_basis'],
            'payload': {'content': 'An unreviewed claim.'},
        }
        with self.assertRaises(ValueError):
            desk_chat.submit(self.root, ident, request)
        case = self.base / 'synthetic-case'
        bundle = case / 'research'
        bundle.mkdir(parents=True)
        facts = {
            'owner': research_contract.OWNER,
            'schema': 2,
            'digest': 'synthetic',
            'status': 'complete',
            'review': {'digest': 'synthetic', 'accepted': True},
            'sources': [],
            'facts': [],
            'findings': [],
        }
        files = {
            'facts.json': json.dumps(facts),
            'report.md': 'Synthetic reviewed report.',
            'brief.md': 'Synthetic brief.',
            'evidence.md': 'Synthetic evidence.',
        }
        for name, text in files.items():
            (bundle / name).write_text(text)
        manifest = {key: facts[key] for key in ('owner', 'schema', 'digest', 'status')}
        manifest['artifacts'] = [
            {'file': name, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            for name, text in files.items()
        ]
        (bundle / 'output.json').write_text(json.dumps(manifest))
        request['payload'] = {'case': str(case)}
        desk_chat.submit(self.root, ident, request)
        self.assertEqual(
            (self.folder(ident) / 'research' / 'report.md').read_text(), files['report.md']
        )
        self.assertIsNone(desk.read_start(self.root, ident)['step'])
        old_manifest = (self.folder(ident) / 'research' / 'output.json').read_bytes()
        context = desk_chat.context(self.root, ident, 'research')
        request['expected_basis'] = context['expected_basis']
        desk_chat.submit(self.root, ident, request)
        archive = self.folder(ident) / 'history' / 'research' / studio.digest(old_manifest)
        self.assertEqual((archive / 'output.json').read_bytes(), old_manifest)
        self.assertEqual((archive / 'report.md').read_text(), files['report.md'])

    def test_checked_research_respects_pinned_sources_and_captures(self):
        import hashlib
        from studio_core import research_contract
        from synthesis_fixture import dossier, published_bundle

        selected = self.source('Selected synthetic evidence.')
        unselected = self.source('Unselected synthetic evidence.')
        for scenario in (
            'outside',
            'unknown',
            'unselected',
            'mismatch',
            'original_mismatch',
            'no_selection',
            'public_local',
            'allowed',
            'web',
            'selected',
        ):
            with (
                self.subTest(scenario=scenario),
                patch(
                    'studio_core.research_contract.snapshot', return_value={'version': 'synthetic'}
                ),
            ):
                chosen = (
                    None
                    if scenario == 'no_selection'
                    else {
                        'sites': ['https://allowed.example'],
                        'web': scenario in ('web', 'public_local'),
                    }
                )
                made = desk_chat.create(
                    self.root,
                    {
                        'title': 'Synthetic ' + scenario,
                        'way': 'topic',
                        'point': 'Pinned research.',
                        'scope': 'research',
                        'sources': [selected],
                        'research_from': chosen,
                    },
                )
                ident = made['id']
                draft = desk.read(self.root, ident)
                _, record = studio.item(self.root, 'articles', ident)
                run = {'brief': {'goal': draft['brief']['point'], 'audience': 'Blog readers'}}
                offered = blog_runner.inputs(self.root, record, run)['sources'][0]
                source = dossier('independent-author')['sources'][0]
                source.update(permission='public', origin='https://allowed.example/page')
                if scenario == 'outside' or scenario == 'web':
                    source['origin'] = 'https://outside.example/page'
                if scenario == 'public_local':
                    source['origin'] = offered['origin']
                if scenario == 'unknown':
                    source['permission'] = 'unknown'
                capture = 'Public synthetic evidence.'
                if scenario in (
                    'unselected',
                    'mismatch',
                    'original_mismatch',
                    'no_selection',
                    'selected',
                ):
                    source.update(
                        permission='selected',
                        file='sources/' + offered['id'] + '.txt',
                        origin=offered['origin'],
                    )
                    capture = (
                        offered['text']
                        if scenario in ('selected', 'original_mismatch', 'no_selection')
                        else 'Unselected synthetic evidence.'
                    )
                    if scenario == 'unselected':
                        _, other = studio.item(self.root, 'sources', unselected)
                        other_record = dict(
                            record,
                            sources=[
                                {
                                    'source_id': unselected,
                                    'revision': other['revision'],
                                    'purposes': ['reference'],
                                }
                            ],
                        )
                        other_input = blog_runner.inputs(self.root, other_record, run)['sources'][0]
                        source.update(
                            file='sources/' + other_input['id'] + '.txt',
                            origin=other_input['origin'],
                        )
                        capture = other_input['text']
                case = self.base / ('case-' + scenario)
                bundle = case / 'research'
                value = dossier('independent-author')
                source['snapshot'] = 'research/captures/source.txt'
                if scenario == 'original_mismatch':
                    source['original_snapshot'] = 'research/captures/original.txt'
                facts, manifest = published_bundle(
                    bundle,
                    sources=[source],
                    findings=value['findings'],
                    evidence=value['facts'],
                    review={
                        'accepted': True,
                        'digest': 'synthetic-digest',
                        'reviewer': 'independent-reviewer',
                    },
                )
                snapshot = bundle / 'captures/source.txt'
                snapshot.parent.mkdir()
                snapshot.write_text(capture)
                manifest['artifacts'].append(
                    {
                        'file': 'captures/source.txt',
                        'sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                    }
                )
                if scenario == 'original_mismatch':
                    original = bundle / 'captures/original.txt'
                    original.write_text('Different original document.')
                    manifest['artifacts'].append(
                        {
                            'file': 'captures/original.txt',
                            'sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                        }
                    )
                (bundle / 'output.json').write_text(json.dumps(manifest))
                # A rejected replacement must preserve existing research and History too.
                published_bundle(self.folder(ident) / 'research')
                history = self.folder(ident) / 'history' / 'research' / 'existing' / 'note.txt'
                history.parent.mkdir(parents=True)
                history.write_text('Earlier synthetic history.')
                context = desk_chat.context(self.root, ident, 'research')
                request = {
                    'kind': 'research',
                    'target': 'research',
                    'expected_basis': context['expected_basis'],
                    'payload': {'case': str(case)},
                }

                def snapshot_root():
                    return {
                        str(p.relative_to(self.root)): p.read_bytes()
                        for p in self.root.rglob('*')
                        if p.is_file()
                    }

                before = snapshot_root()
                with patch('desk_jobs.begin', side_effect=AssertionError('nested job')):
                    if scenario in (
                        'outside',
                        'unknown',
                        'unselected',
                        'mismatch',
                        'original_mismatch',
                        'no_selection',
                        'public_local',
                    ):
                        with self.assertRaises(ValueError):
                            desk_chat.submit(self.root, ident, request)
                        self.assertEqual(snapshot_root(), before)
                        self.assertEqual(desk.read_start(self.root, ident)['step'], 'research')
                    else:
                        desk_chat.submit(self.root, ident, request)
                        self.assertIsNone(desk.read_start(self.root, ident)['step'])
                        saved, _ = research_contract.read_bundle(self.folder(ident) / 'research')
                        self.assertEqual(saved['sources'], [source])
                        self.assertEqual(saved['facts'][0]['author'], 'independent-author')
                        self.assertEqual(saved['review']['reviewer'], 'independent-reviewer')

    def test_large_context_capture_is_accepted_and_stale_basis_is_refused(self):
        import hashlib
        from studio_core import research_contract
        from synthesis_fixture import dossier, published_bundle

        text = ('Ordinary synthetic paragraph. ' * 90 + '\n\n') * 120
        text += ('Needle goal relevant synthetic paragraph. ' * 90 + '\n\n') * 10
        self.assertGreater(len(text), 240_000)
        selected = self.source(text)
        with patch('studio_core.research_contract.snapshot', return_value={'version': 'synthetic'}):
            made = desk_chat.create(
                self.root,
                {
                    'title': 'Synthetic large document',
                    'way': 'topic',
                    'point': 'Needle goal relevant',
                    'scope': 'research',
                    'sources': [selected],
                    'research_from': {'sites': ['https://allowed.example'], 'web': False},
                },
            )
            ident = made['id']
            context = desk_chat.context(self.root, ident, 'research')
            offered = context['inputs']['sources'][0]
            _, record = studio.item(self.root, 'articles', ident)
            worker = blog_runner.inputs(
                self.root,
                record,
                {'brief': {'goal': 'Needle goal relevant', 'audience': 'Blog readers'}},
            )['sources'][0]
            self.assertNotEqual(offered['text'], worker['text'])
            source = dossier('independent-author')['sources'][0]
            source.update(
                permission='selected',
                file='sources/' + offered['id'] + '.txt',
                origin=offered['origin'],
                snapshot='research/captures/source.txt',
            )
            bundle = self.base / 'large-case' / 'research'
            value = dossier('independent-author')
            _, manifest = published_bundle(
                bundle,
                sources=[source],
                findings=value['findings'],
                evidence=value['facts'],
                review={
                    'accepted': True,
                    'digest': 'synthetic-digest',
                    'reviewer': 'independent-reviewer',
                },
            )
            capture = bundle / 'captures/source.txt'
            capture.parent.mkdir()
            capture.write_text(offered['text'])
            manifest['artifacts'].append(
                {
                    'file': 'captures/source.txt',
                    'sha256': hashlib.sha256(capture.read_bytes()).hexdigest(),
                }
            )
            (bundle / 'output.json').write_text(json.dumps(manifest))
            request = {
                'kind': 'research',
                'target': 'research',
                'expected_basis': context['expected_basis'],
                'payload': {'case': str(bundle.parent)},
            }
            source_folder, _ = studio.item(self.root, 'sources', selected)
            changed = source_folder / 'content.md'
            original = changed.read_bytes()
            changed.write_bytes(original + b'\nChanged synthetic pinned bytes.')
            before = {
                str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*')
                if p.is_file()
            }
            with patch('desk_jobs.begin', side_effect=AssertionError('nested job')):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    desk_chat.submit(self.root, ident, request)
                self.assertEqual(
                    before,
                    {
                        str(p.relative_to(self.root)): p.read_bytes()
                        for p in self.root.rglob('*')
                        if p.is_file()
                    },
                )
                self.assertEqual(desk.read_start(self.root, ident)['step'], 'research')
                request['expected_basis'] = desk_chat.context(self.root, ident, 'research')[
                    'expected_basis'
                ]
                with self.assertRaisesRegex(ValueError, 'capture outside'):
                    desk_chat.submit(self.root, ident, request)
                self.assertEqual(
                    before,
                    {
                        str(p.relative_to(self.root)): p.read_bytes()
                        for p in self.root.rglob('*')
                        if p.is_file()
                    },
                )
                changed.write_bytes(original)
                request['expected_basis'] = context['expected_basis']
                self.assertEqual(
                    desk_chat.context(self.root, ident, 'research')['expected_basis'],
                    request['expected_basis'],
                )
                desk_chat.submit(self.root, ident, request)
            self.assertIsNone(desk.read_start(self.root, ident)['step'])
            saved, _ = research_contract.read_bundle(self.folder(ident) / 'research')
            self.assertEqual(saved['sources'], [source])
            self.assertEqual(saved['facts'][0]['author'], 'independent-author')
            self.assertEqual(saved['review']['reviewer'], 'independent-reviewer')

    def test_author_change_invalidates_handoff_context(self):
        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retry.'}
        )
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'outline')
        directory, record = studio.item(self.root, 'articles', ident)
        record['author'] = 'Another author'
        studio.persist(directory, 'articles', record)
        with self.assertRaisesRegex(ValueError, 'changed'):
            desk_chat.handoff(self.root, ident, context['expected_basis'], ['outline'])
        self.assertEqual(studio.read_json(directory / 'session.json')['execution'], 'conversation')

    def test_submission_provenance_and_editorial_notes_stay_outside_writing(self):
        made = self.create()
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'draft')
        result = desk_chat.submit(
            self.root,
            ident,
            {
                'kind': 'text',
                'target': 'draft',
                'expected_basis': context['expected_basis'],
                'payload': {
                    'content': DRAFT,
                    'notes': 'Synthetic editorial note.',
                    'gaps': ['Confirm the date.'],
                },
            },
        )
        self.assertNotIn('Synthetic editorial note.', result['markdown'])
        self.assertEqual(result['editorial_notes']['notes'], 'Synthetic editorial note.')
        context = desk_chat.context(self.root, ident, 'draft')
        result = desk_chat.submit(
            self.root,
            ident,
            {
                'kind': 'text',
                'target': 'draft',
                'expected_basis': context['expected_basis'],
                'payload': {'content': DRAFT},
            },
        )
        self.assertEqual(result['editorial_notes']['notes'], 'Synthetic editorial note.')
        receipts = studio.read_json(self.folder(ident) / 'desk' / 'conversation-submissions.json')
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[-1]['expected_basis'], context['expected_basis'])
        self.assertNotIn('approval', receipts[-1])

    def test_variant_without_explicit_brand_refuses_before_creation(self):
        before = list((self.root / 'articles').iterdir())
        with self.assertRaisesRegex(ValueError, 'brand'):
            self.create(variant='blog')
        self.assertEqual(list((self.root / 'articles').iterdir()), before)

    def test_explicit_checked_scope_change_allows_later_draft_without_jobs(self):
        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retry.', 'scope': 'outline'}
        )
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'outline')
        desk_chat.submit(
            self.root,
            ident,
            {
                'kind': 'outline',
                'target': 'outline',
                'expected_basis': context['expected_basis'],
                'payload': {'sections': [{'heading': 'Retry', 'brief': 'Keep work.'}]},
            },
        )
        with self.assertRaisesRegex(ValueError, 'scope'):
            desk_chat.context(self.root, ident, 'draft')
        context = desk_chat.context(self.root, ident, 'outline')
        original = (self.folder(ident) / 'DRAFT.md').read_bytes()
        with patch('desk_jobs.begin', side_effect=AssertionError('nested job')):
            changed = desk_chat.set_scope(self.root, ident, context['expected_basis'], 'draft')
        self.assertEqual(changed['scope'], 'draft')
        self.assertEqual((self.folder(ident) / 'DRAFT.md').read_bytes(), original)
        context = desk_chat.context(self.root, ident, 'draft')
        with self.assertRaisesRegex(ValueError, 'remaining runner plan'):
            desk_chat.handoff(self.root, ident, context['expected_basis'], ['draft'])
        result = desk_chat.submit(
            self.root,
            ident,
            {
                'kind': 'text',
                'target': 'draft',
                'expected_basis': context['expected_basis'],
                'payload': {'content': DRAFT},
            },
        )
        self.assertTrue(result['draft']['opening'])
        self.assertEqual(result['execution'], 'conversation')
        self.assertEqual(desk_jobs.jobs(self.root, ident), [])

    def test_scope_changes_refuse_outdated_basis_and_active_worker_without_mutation(self):
        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retry.', 'scope': 'outline'}
        )
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'outline')
        desk_chat.set_scope(self.root, ident, context['expected_basis'], 'draft')
        record = (self.folder(ident) / 'session.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed'):
            desk_chat.set_scope(self.root, ident, context['expected_basis'], 'research')
        self.assertEqual((self.folder(ident) / 'session.json').read_bytes(), record)
        context = desk_chat.context(self.root, ident, 'draft')
        with patch('desk_jobs._busy', side_effect=ValueError('A worker is active')):
            with self.assertRaisesRegex(ValueError, 'worker'):
                desk_chat.set_scope(self.root, ident, context['expected_basis'], 'outline')
        self.assertEqual((self.folder(ident) / 'session.json').read_bytes(), record)

    def test_handoff_after_narrowed_scope_cannot_execute_old_broader_plan(self):
        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retry.'}
        )
        ident = made['id']
        current = desk_chat.context(self.root, ident, 'draft')
        desk_chat.set_scope(self.root, ident, current['expected_basis'], 'outline')
        current = desk_chat.context(self.root, ident, 'outline')
        with patch('desk_jobs.begin') as begin:
            with self.assertRaisesRegex(ValueError, 'scope'):
                desk_chat.handoff(self.root, ident, current['expected_basis'], ['outline', 'draft'])
            begin.assert_not_called()
            self.assertEqual(desk.read_start(self.root, ident)['steps'], ['outline', 'draft'])
            result = desk_chat.handoff(self.root, ident, current['expected_basis'], ['outline'])
            begin.assert_called_once_with(self.root, ident)
        self.assertEqual(result['execution'], 'runner')
        self.assertEqual(desk.read_start(self.root, ident)['steps'], ['outline'])

    def test_outline_submission_cannot_hide_history_after_supplied_prose_is_cleared(self):
        made = self.create()
        ident = made['id']
        parts = ['opening'] + [section['id'] for section in made['draft']['sections']]
        for part in parts:
            current = desk_chat.read(self.root, ident)
            desk_chat.save(self.root, ident, current['draft']['revision'], part, '')
        before = desk_chat.read(self.root, ident)
        self.assertTrue(all(before['history'][part] for part in parts))
        files = {
            str(path.relative_to(self.folder(ident))): path.read_bytes()
            for path in self.folder(ident).rglob('*')
            if path.is_file()
        }
        context = desk_chat.context(self.root, ident, 'outline')
        with self.assertRaisesRegex(ValueError, 'initial outline'):
            desk_chat.submit(
                self.root,
                ident,
                {
                    'kind': 'outline',
                    'target': 'outline',
                    'expected_basis': context['expected_basis'],
                    'payload': {'sections': [{'heading': 'Replacement', 'brief': 'A new plan.'}]},
                },
            )
        self.assertEqual(desk_chat.read(self.root, ident), before)
        self.assertEqual(
            {
                str(path.relative_to(self.folder(ident))): path.read_bytes()
                for path in self.folder(ident).rglob('*')
                if path.is_file()
            },
            files,
        )
        self.assertEqual(desk.removed(self.root, ident), [])

    def test_cleared_topic_prose_does_not_reset_initial_outline_eligibility(self):
        made = desk_chat.create(
            self.root, {'title': 'Synthetic', 'way': 'topic', 'point': 'Retry.'}
        )
        ident = made['id']
        for text in ('A saved opening.', ''):
            current = desk_chat.read(self.root, ident)
            desk_chat.save(self.root, ident, current['draft']['revision'], 'opening', text)
        current = desk_chat.read(self.root, ident)
        context = desk_chat.context(self.root, ident, 'outline')
        with self.assertRaisesRegex(ValueError, 'initial outline'):
            desk_chat.submit(
                self.root,
                ident,
                {
                    'kind': 'outline',
                    'target': 'outline',
                    'expected_basis': context['expected_basis'],
                    'payload': {'sections': [{'heading': 'Replacement', 'brief': 'A new plan.'}]},
                },
            )
        self.assertEqual(desk_chat.read(self.root, ident), current)

    def test_checked_outline_edits_keep_text_ids_history_and_recoverable_removals(self):
        made = self.create()
        ident = made['id']
        first, second = made['draft']['sections']
        desk_chat.save(self.root, ident, 1, first['id'], 'An edited first passage.')
        history = desk.versions(self.root, ident, first['id'])
        context = desk_chat.context(self.root, ident, 'outline')
        rows = [
            {'id': second['id'], 'heading': 'Second retitled', 'brief': 'Second brief.'},
            {'id': first['id'], 'heading': 'First retitled', 'brief': 'First brief.'},
            {'heading': 'New section', 'brief': 'New brief.'},
        ]
        with patch('desk_jobs.begin', side_effect=AssertionError('nested job')):
            saved = desk_chat.outline_save(
                self.root, ident, {'expected_basis': context['expected_basis'], 'rows': rows}
            )
        self.assertEqual(
            [row['id'] for row in saved['draft']['sections'][:2]], [second['id'], first['id']]
        )
        self.assertEqual(
            [row['text'] for row in saved['draft']['sections']],
            [second['text'], 'An edited first passage.', ''],
        )
        self.assertEqual(saved['draft']['sections'][1]['brief'], 'First brief.')
        self.assertEqual(saved['history'][first['id']], history)
        self.assertEqual(saved['execution'], 'conversation')
        context = desk_chat.context(self.root, ident, 'outline')
        kept = [
            {'id': row['id'], 'heading': row['heading'], 'brief': row.get('brief', '')}
            for row in saved['draft']['sections']
            if row['id'] != first['id']
        ]
        removed = desk_chat.outline_save(
            self.root, ident, {'expected_basis': context['expected_basis'], 'rows': kept}
        )
        self.assertEqual(removed['removed'][0]['id'], first['id'])
        self.assertEqual(removed['removed'][0]['text'], 'An edited first passage.')
        self.assertEqual(removed['history'][first['id']], history)
        restored = desk.unremove(self.root, ident, removed['draft']['revision'], 0)
        self.assertIn(first['id'], [row['id'] for row in restored['sections']])
        self.assertEqual(desk.versions(self.root, ident, first['id']), history)
        self.assertEqual(desk_jobs.jobs(self.root, ident), [])

    def test_checked_outline_refuses_changed_basis_worker_and_team_without_mutation(self):
        made = self.create()
        ident = made['id']
        context = desk_chat.context(self.root, ident, 'outline')
        rows = [
            {'id': row['id'], 'heading': row['heading'], 'brief': ''}
            for row in made['draft']['sections']
        ]
        desk_chat.save(self.root, ident, 1, 'opening', 'A newer opening.')
        before = desk_chat.read(self.root, ident)
        with self.assertRaisesRegex(ValueError, 'changed'):
            desk_chat.outline_save(
                self.root, ident, {'expected_basis': context['expected_basis'], 'rows': rows}
            )
        self.assertEqual(desk_chat.read(self.root, ident), before)
        context = desk_chat.context(self.root, ident, 'outline')
        for target, message in (
            ('desk_jobs._busy', 'A worker is active'),
            ('team_workspace.guard', 'Other driver'),
        ):
            with patch(target, side_effect=ValueError(message)):
                with self.assertRaisesRegex(ValueError, message):
                    desk_chat.outline_save(
                        self.root,
                        ident,
                        {'expected_basis': context['expected_basis'], 'rows': rows},
                    )
            self.assertEqual(desk_chat.read(self.root, ident), before)

    def test_outline_save_cli_accepts_stdin_and_json_file(self):
        made = self.create()
        ident = made['id']
        script = isolation.SCRIPTS / 'studio.py'
        rows = [
            {'id': row['id'], 'heading': row['heading'], 'brief': ''}
            for row in made['draft']['sections']
        ]
        for input_file in ('-', str(self.base / 'outline-edit.json')):
            context = desk_chat.context(self.root, ident, 'outline')
            rows[0]['brief'] = input_file == '-' and 'From stdin.' or 'From a file.'
            request = json.dumps({'expected_basis': context['expected_basis'], 'rows': rows})
            if input_file != '-':
                (self.base / 'outline-edit.json').write_text(request)
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    '--root',
                    str(self.root),
                    'desk',
                    'outline-save',
                    '--article',
                    ident,
                    '--input',
                    input_file,
                ],
                input=request if input_file == '-' else None,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)['draft']['sections'][0]['brief'], rows[0]['brief']
            )

    def test_research_start_narrowed_to_outline_hands_off_with_accessible_current_basis(self):
        made = desk_chat.create(
            self.root,
            {
                'title': 'Synthetic',
                'way': 'topic',
                'point': 'Retry.',
                'research_from': {'sites': [], 'web': True},
            },
        )
        ident = made['id']
        self.assertEqual(made['start']['steps'], ['research', 'outline', 'draft'])
        research = desk_chat.context(self.root, ident, 'research')
        draft = desk_chat.context(self.root, ident, 'draft')
        with patch('desk_jobs.begin') as begin:
            with self.assertRaisesRegex(ValueError, 'order'):
                desk_chat.handoff(
                    self.root, ident, research['expected_basis'], ['draft', 'outline']
                )
            begin.assert_not_called()
            desk_chat.set_scope(self.root, ident, draft['expected_basis'], 'outline')
            current = desk_chat.context(self.root, ident, 'outline')
            before = desk_chat.read(self.root, ident)
            with self.assertRaisesRegex(ValueError, 'changed'):
                desk_chat.handoff(self.root, ident, draft['expected_basis'], ['outline'])
            self.assertEqual(desk_chat.read(self.root, ident), before)
            with self.assertRaisesRegex(ValueError, 'scope'):
                desk_chat.handoff(self.root, ident, current['expected_basis'], ['outline', 'draft'])
            self.assertEqual(desk_chat.read(self.root, ident), before)
            begin.assert_not_called()
            handed = desk_chat.handoff(self.root, ident, current['expected_basis'], ['outline'])
            begin.assert_called_once_with(self.root, ident)
        self.assertEqual(handed['execution'], 'runner')
        self.assertEqual(handed['start']['steps'], ['outline'])
        self.assertEqual(handed['start']['step'], 'outline')
        self.assertEqual(desk_jobs.jobs(self.root, ident), [])

    def test_explicit_outline_narrowing_allows_only_unwritten_initial_submission(self):
        for with_history in (False, True):
            with self.subTest(with_history=with_history):
                made = desk_chat.create(
                    self.root,
                    {
                        'title': 'Synthetic',
                        'way': 'topic',
                        'point': 'Retry.',
                        'research_from': {'sites': [], 'web': True},
                    },
                )
                ident = made['id']
                if with_history:
                    for text in ('A prior opening.', ''):
                        current = desk_chat.read(self.root, ident)
                        desk_chat.save(
                            self.root, ident, current['draft']['revision'], 'opening', text
                        )
                outline = desk_chat.context(self.root, ident, 'outline')
                payload = {'sections': [{'heading': 'A focused outline', 'brief': 'Keep work.'}]}
                # An unchanged draft request still cannot skip pending research.
                with self.assertRaisesRegex(ValueError, 'initial outline'):
                    desk_chat.submit(
                        self.root,
                        ident,
                        {
                            'kind': 'outline',
                            'target': 'outline',
                            'expected_basis': outline['expected_basis'],
                            'payload': payload,
                        },
                    )
                draft = desk_chat.context(self.root, ident, 'draft')
                desk_chat.set_scope(self.root, ident, draft['expected_basis'], 'outline')
                outline = desk_chat.context(self.root, ident, 'outline')
                before = desk_chat.read(self.root, ident)
                request = {
                    'kind': 'outline',
                    'target': 'outline',
                    'expected_basis': outline['expected_basis'],
                    'payload': payload,
                }
                if with_history:
                    with self.assertRaisesRegex(ValueError, 'initial outline'):
                        desk_chat.submit(self.root, ident, request)
                    self.assertEqual(desk_chat.read(self.root, ident), before)
                else:
                    result = desk_chat.submit(self.root, ident, request)
                    self.assertEqual(result['draft']['sections'][0]['heading'], 'A focused outline')
                    self.assertEqual(result['scope'], 'outline')
                    self.assertEqual(result['execution'], 'conversation')
                self.assertEqual(desk_jobs.jobs(self.root, ident), [])
