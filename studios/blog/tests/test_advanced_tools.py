"""Contextual tool tasks keep synthetic writing and existing approval boundaries."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from unittest.mock import patch

from test_editorial_tools import Fixture
import advanced_tools
import blog_runner
import manuscript_editor
import prepublish
import studio


class AdvancedToolsTests(Fixture):
    def setUp(self):
        super().setUp()
        self.ident = self.article()
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def test_the_done_card_prepublication_route_returns_the_real_report(self):
        import management

        self.assertEqual(
            management.view(self.root, 'prepublish', {'id': [self.ident]}),
            prepublish.report(self.root, self.ident),
        )

    def save(self, content):
        current = manuscript_editor.read(self.root, self.ident)
        return manuscript_editor.dispatch(
            self.root,
            'save',
            {'id': self.ident, 'expected': current['expected'], 'content': content},
        )

    def test_history_preview_and_restore_use_existing_guards_and_keep_metadata(self):
        self.save('# Earlier wording\n\nKeep the technical qualifier.')
        self.save('# Current wording\n\nKeep the technical qualifier.')
        found = advanced_tools.overview(self.root, self.ident)
        revision = found['history'][0]['revision']
        preview = advanced_tools.history_preview(self.root, self.ident, revision)
        directory, before = studio.item(self.root, 'articles', self.ident)
        source, voice = before['sources'], before['voice']
        result = advanced_tools.dispatch(
            self.root,
            {
                'action': 'restore',
                'id': self.ident,
                'expected': found['expected'],
                'revision': revision,
                'restore_expected': preview['expected'],
                'confirmed': True,
            },
        )
        self.assertEqual(result['status'], 'restored')
        self.assertIn('Earlier wording', (directory / 'DRAFT.md').read_text())
        _, after = studio.item(self.root, 'articles', self.ident)
        self.assertEqual((after['sources'], after['voice']), (source, voice))
        with self.assertRaisesRegex(ValueError, 'changed'):
            advanced_tools.dispatch(
                self.root,
                {
                    'action': 'restore',
                    'id': self.ident,
                    'expected': found['expected'],
                    'revision': revision,
                    'restore_expected': preview['expected'],
                    'confirmed': True,
                },
            )

    def test_report_is_read_only_and_distinguishes_findings_from_remote_coverage(self):
        self.save(
            '# A title\n\n### Skipped heading\n\nTODO citation\n\n![](TBD)\n\n[missing]()\n[source:unknown]\n'
        )
        directory, _ = studio.item(self.root, 'articles', self.ident)
        before = {
            p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()
        }
        result = prepublish.report(self.root, self.ident)
        self.assertEqual(
            {f['code'] for f in result['findings']},
            {
                'heading-order',
                'unfinished-note',
                'image-alt',
                'image-source',
                'link-target',
                'evidence-reference',
            },
        )
        self.assertTrue(result['report_only'])
        self.assertIn('not verified', result['coverage'])
        self.assertEqual(
            before,
            {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()},
        )
        self.save(
            '# A supported title\n\n## Context\n\n[Source](https://docs.example.com/source)\n'
        )
        self.assertEqual(prepublish.report(self.root, self.ident)['status'], 'no-findings')

    def test_geo_uses_only_relevant_guidance_and_stales_on_new_text(self):
        current = manuscript_editor.read(self.root, self.ident)
        with patch.object(blog_runner.Engine, 'control', return_value={'status': 'queued'}):
            manuscript_editor.dispatch(
                self.root,
                'check',
                {
                    'id': self.ident,
                    'expected': current['expected'],
                    'check': 'geo',
                    'request': 'Keep uncertainty',
                    'research': 'none',
                },
            )
        _, payload, guidance = blog_runner.job(self.root, self.ident)
        self.assertEqual(payload['response_kind'], 'editing-review')
        self.assertIn('retrieval', guidance.lower())
        self.assertNotIn('Humanization capability', guidance)
        self.assertIn('Keep uncertainty', payload['changes'])


class ContextJobTests(Fixture):
    def setUp(self):
        super().setUp()
        import article_tools
        import tool_jobs

        self.tools, self.jobs = article_tools, tool_jobs
        self.ident = self.article()
        self.engine = blog_runner.Engine(
            self.root,
            worker=lambda *a, **k: {'content': 'Prepared synthetic text.', 'notes': 'No posting.'},
        )
        blog_runner.ENGINES[str(self.root)] = self.engine
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def create(self, kind='repurpose', **extra):
        return self.tools.request(
            self.root,
            {
                'kind': kind,
                'id': self.ident,
                'operation': 'a' * 32,
                'format': 'summary',
                'words': 150,
                **extra,
            },
        )

    def test_job_is_explicit_idempotent_immutable_and_saves_separate_reviewed_variant(self):
        from pathlib import Path

        before = (Path(self.root) / 'articles' / self.ident / 'DRAFT.md').read_bytes()
        job = self.create()
        self.assertEqual(job['status'], 'queued')
        self.assertIsNone(job['result'])
        self.assertEqual(self.create()['id'], job['id'])
        with self.assertRaisesRegex(ValueError, 'another request'):
            self.create(words=300)
        self.jobs.once(self.engine)
        saved = self.jobs.read(self.root, job['id'])
        self.assertEqual(saved['status'], 'ready')
        self.assertFalse(
            saved['model_selection']['web'] if 'web' in saved['model_selection'] else False
        )
        receipt = self.tools.apply(
            self.root,
            {
                'job': job['id'],
                'name': 'launch-summary',
                'content': 'Human-adjusted synthetic copy.',
            },
        )
        self.assertFalse(receipt['posted'])
        self.assertEqual(self.tools.apply(self.root, {'job': job['id']}), receipt)
        self.assertEqual(
            before, (Path(self.root) / 'articles' / self.ident / 'DRAFT.md').read_bytes()
        )
        self.assertFalse(self.tools.job_view(self.root, job['id'])['source_changed'])
        copy = self.tools.variant(self.root, self.ident, 'launch-summary')
        self.tools.save_variant(
            self.root,
            {
                'id': self.ident,
                'name': 'launch-summary',
                'expected': copy['expected'],
                'content': 'A revised local channel copy.',
            },
        )
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.tools.save_variant(
                self.root,
                {
                    'id': self.ident,
                    'name': 'launch-summary',
                    'expected': copy['expected'],
                    'content': 'Older text',
                },
            )
        self.assertEqual(
            self.tools.variant(self.root, self.ident, 'launch-summary')['content'],
            'A revised local channel copy.',
        )
        self.assertEqual(
            self.tools.job_view(self.root, job['id'])['saved_content'],
            'Human-adjusted synthetic copy.',
        )

    def test_source_change_blocks_apply_and_cancelled_late_output_is_discarded(self):
        job = self.create()

        def cancelling(*args, **kwargs):
            self.jobs.control(self.root, job['id'], 'cancel', self.engine)
            return {'content': 'Late result'}

        self.engine.worker = cancelling
        self.jobs.once(self.engine)
        value = self.jobs.read(self.root, job['id'])
        self.assertEqual(value['status'], 'cancelled')
        self.assertIsNone(value['result'])
        self.jobs.control(self.root, job['id'], 'retry', self.engine)
        self.engine.worker = lambda *a, **k: {'content': 'New copy'}
        self.jobs.once(self.engine)
        self.file.write_text('Changed original manuscript.')
        self.command(
            'article', 'save', '--id', self.ident, '--kind', 'draft', '--file', str(self.file)
        )
        self.assertTrue(self.tools.job_view(self.root, job['id'])['source_changed'])
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.tools.apply(self.root, {'job': job['id'], 'name': 'new-copy'})

    def test_interrupted_and_bad_model_jobs_fail_without_stopping_scheduler(self):
        job = self.create()
        saved = self.jobs.read(self.root, job['id'])
        saved['status'] = 'working'
        self.jobs.write(self.root, saved)
        self.jobs.recover(self.root)
        self.assertEqual(self.jobs.read(self.root, job['id'])['status'], 'failed')
        self.jobs.control(self.root, job['id'], 'retry', self.engine)
        with patch(
            'studio_core.model_profiles.route', side_effect=ValueError('Invalid saved model')
        ):
            self.jobs.once(self.engine)
        self.assertEqual(self.jobs.read(self.root, job['id'])['status'], 'failed')
        self.jobs.control(self.root, job['id'], 'retry', self.engine)
        self.jobs.once(self.engine)
        self.assertEqual(self.jobs.read(self.root, job['id'])['status'], 'ready')

    def test_voice_learning_permission_confirmation_audition_retirement_and_pins(self):
        sample = self.source('Synthetic authored passage with a distinctive short rhythm.')
        folder, record = studio.item(self.root, 'sources', sample['id'])
        record['purposes'] = ['voice-sample']
        studio.persist(folder, 'sources', record)
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.create('voice-learn', name='Synthetic Author', samples=[sample['id']])
        job = self.create(
            'voice-learn', name='Synthetic Author', samples=[sample['id']], confirmed=True
        )
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        profile = self.tools.profile(self.root, receipt['profile'])
        self.assertEqual(profile['status'], 'provisional')
        pin = studio.voice_pin(self.root, profile['id'])
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.tools.save_profile(
                self.root,
                {
                    'profile': profile['id'],
                    'expected': profile['expected'],
                    'guide': 'Reviewed guide',
                    'status': 'confirmed',
                },
            )
        receipt = self.tools.save_profile(
            self.root,
            {
                'profile': profile['id'],
                'expected': profile['expected'],
                'name': 'Reviewed Author',
                'guide': 'Reviewed guide',
                'status': 'confirmed',
                'confirmed': True,
            },
        )
        profile = self.tools.profile(self.root, receipt['profile'])
        self.assertEqual(profile['name'], 'Reviewed Author')
        self.assertEqual(pin['revision'], 1)
        self.create(
            'voice-audition',
            operation='b' * 32,
            profile=profile['id'],
            content='A passage to audition.',
        )
        self.jobs.once(self.engine)
        with self.assertRaisesRegex(ValueError, 'read-only'):
            self.tools.apply(self.root, {'job': 'b' * 32})
        self.tools.retire_profile(
            self.root,
            {'profile': profile['id'], 'expected': profile['expected'], 'confirmed': True},
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            studio.voice_pin(self.root, profile['id'])
        self.assertEqual(studio.voice_pin(self.root, profile['id'], 1), pin)

    def classified(self, text, purpose):
        source = self.source(text)
        folder, record = studio.item(self.root, 'sources', source['id'])
        record['purposes'] = [purpose]
        studio.persist(folder, 'sources', record)
        return source['id']

    def test_style_learning_saves_a_provisional_style_apart_from_any_voice(self):
        import styles

        example = self.classified('What is new, for whom, and where to get it.', 'style-sample')
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.create('style-learn', name='Launch note', samples=[example])
        with self.assertRaisesRegex(ValueError, 'style-sample'):
            self.create(
                'style-learn', name='Launch note', samples=[self.source()['id']], confirmed=True
            )
        job = self.create('style-learn', name='Launch note', samples=[example], confirmed=True)
        saved = self.jobs.read(self.root, job['id'])
        self.assertEqual(saved['payload']['style_name'], 'Launch note')
        self.assertIn('Ignore who wrote them', saved['guidance'])
        self.assertNotIn('article', saved['metadata'])
        self.assertEqual(
            [row['id'] for row in self.jobs.listing(self.root)], [job['id']]
        )  # listed without an article
        self.assertFalse(self.tools.job_view(self.root, job['id'])['source_changed'])
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        found = styles.detail(self.root, receipt['style'])
        self.assertEqual(
            (found['status'], found['kind'], found['sample_ids'], found['guide']),
            ('provisional', 'learned', [example], 'Prepared synthetic text.'),
        )
        self.assertEqual([row['id'] for row in self.tools.voices(self.root)['profiles']], [])
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            styles.save(
                self.root,
                {
                    'style': found['id'],
                    'expected': found['expected'],
                    'guide': 'Reviewed',
                    'status': 'confirmed',
                },
            )
        receipt = styles.save(
            self.root,
            {
                'style': found['id'],
                'expected': found['expected'],
                'guide': 'Reviewed',
                'status': 'confirmed',
                'confirmed': True,
            },
        )
        self.assertEqual((receipt['revision'], receipt['status']), (2, 'confirmed'))
        with self.assertRaisesRegex(ValueError, 'changed'):
            styles.save(
                self.root,
                {
                    'style': found['id'],
                    'expected': found['expected'],
                    'guide': 'Stale',
                    'status': 'provisional',
                },
            )
        current = styles.detail(self.root, found['id'])
        self.assertEqual(
            advanced_tools.dispatch(
                self.root,
                {
                    'action': 'style-retire',
                    'style': found['id'],
                    'expected': current['expected'],
                    'confirmed': True,
                },
            )['status'],
            'retired',
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            studio.style_pin(self.root, found['id'])

    def test_style_learning_revises_an_existing_style_and_goes_stale_when_it_changes(self):
        import styles

        example = self.classified('A short release note.', 'style-sample')
        first = self.create('style-learn', name='Release note', samples=[example], confirmed=True)
        self.jobs.once(self.engine)
        style = self.tools.apply(self.root, {'job': first['id']})['style']
        again = self.create(
            'style-learn',
            operation='e' * 32,
            name='Release note',
            samples=[example],
            style=style,
            confirmed=True,
        )
        shown = styles.detail(self.root, style)
        styles.save(
            self.root,
            {'style': style, 'expected': shown['expected'], 'guide': 'Edited meanwhile'},
        )
        self.assertTrue(self.tools.job_view(self.root, again['id'])['source_changed'])
        self.jobs.once(self.engine)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.tools.apply(self.root, {'job': again['id']})

    def test_learning_into_a_retired_style_is_refused_and_does_not_bring_it_back(self):
        import styles

        example = self.classified('A short release note.', 'style-sample')
        job = self.create('style-learn', name='Release note', samples=[example], confirmed=True)
        self.jobs.once(self.engine)
        style = self.tools.apply(self.root, {'job': job['id']})['style']
        waiting = self.create(
            'style-learn',
            operation='f' * 32,
            name='Release note',
            samples=[example],
            style=style,
            confirmed=True,
        )
        self.jobs.once(self.engine)
        shown = styles.detail(self.root, style)
        styles.retire(self.root, {'style': style, 'expected': shown['expected'], 'confirmed': True})
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.create(
                'style-learn',
                operation='1' * 32,
                name='Release note',
                samples=[example],
                style=style,
                confirmed=True,
            )
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.tools.apply(self.root, {'job': waiting['id']})
        self.assertEqual(styles.detail(self.root, style)['status'], 'retired')

    def test_learning_into_an_uncopied_starter_makes_revision_two_and_pinning_is_not_stale(self):

        example = self.classified('A short how-to.', 'style-sample')
        job = self.create(
            'style-learn',
            name='How-to',
            samples=[example],
            style='how-to',
            confirmed=True,
        )
        self.assertFalse((self.root / 'styles' / 'how-to').exists())
        studio.style_pin(self.root, 'how-to')  # copies the starter between request and apply
        self.assertFalse(self.tools.job_view(self.root, job['id'])['source_changed'])
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        self.assertEqual((receipt['style'], receipt['revision']), ('how-to', 2))
        revisions = sorted(
            p.name for p in (self.root / 'styles' / 'how-to' / 'revisions').iterdir()
        )
        self.assertEqual(revisions, ['1', '2'])

    def test_learning_into_an_uncopied_starter_applies_directly_as_revision_two(self):
        example = self.classified('A short how-to.', 'style-sample')
        job = self.create(
            'style-learn', name='How-to', samples=[example], style='how-to', confirmed=True
        )
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        self.assertEqual((receipt['style'], receipt['revision']), ('how-to', 2))
        revisions = sorted(
            p.name for p in (self.root / 'styles' / 'how-to' / 'revisions').iterdir()
        )
        self.assertEqual(revisions, ['1', '2'])

    def test_advanced_actions_and_views_cover_styles_without_sharing_them(self):
        import management

        saved = management.dispatch(
            self.root,
            'tool-action',
            {'action': 'style-save', 'name': 'Field note', 'guide': 'Short.'},
        )
        self.assertEqual(set(saved) - {'team_sync'}, {'style', 'revision', 'status'})
        listing = management.view(self.root, 'styles', {})
        self.assertIn(saved['style'], [row['id'] for row in listing['styles']])
        self.assertEqual(
            management.view(self.root, 'style', {'style': [saved['style']]})['guide'], 'Short.'
        )

    def test_voice_learning_can_take_an_author_background(self):
        sample = self.classified('Synthetic authored passage with a short rhythm.', 'voice-sample')
        about = self.classified('Platform engineer who writes about rollouts.', 'author-background')
        with self.assertRaisesRegex(ValueError, 'author-background'):
            self.create(
                'voice-learn',
                name='Synthetic Author',
                samples=[sample],
                background=sample,
                confirmed=True,
            )
        job = self.create(
            'voice-learn',
            name='Synthetic Author',
            samples=[sample],
            background=about,
            confirmed=True,
        )
        saved = self.jobs.read(self.root, job['id'])
        self.assertEqual(
            saved['payload']['author_background'], 'Platform engineer who writes about rollouts.'
        )
        self.assertIn('author_background is biography', saved['guidance'])
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        folder, _ = studio.item(self.root, 'profiles', receipt['profile'])
        self.assertEqual(
            (folder / 'BACKGROUND.md').read_text(), 'Platform engineer who writes about rollouts.'
        )

    def test_a_queued_voice_job_from_before_backgrounds_still_applies(self):
        sample = self.classified('Synthetic authored passage with a short rhythm.', 'voice-sample')
        job = self.create('voice-learn', name='Synthetic Author', samples=[sample], confirmed=True)
        saved = self.jobs.read(self.root, job['id'])
        self.assertNotIn('background', saved['metadata'])  # exactly as saved before backgrounds
        self.assertNotIn('author_background', saved['payload'])
        saved['status'] = 'ready'
        saved['result'] = {'content': 'Prepared synthetic text.'}
        self.jobs.write(self.root, saved)
        self.assertFalse(self.tools.job_view(self.root, job['id'])['source_changed'])
        receipt = self.tools.apply(self.root, {'job': job['id']})
        self.assertEqual(receipt['status'], 'provisional')

    def test_interview_persists_resume_revisions_and_outline_without_starting_draft(self):
        data = {
            'title': 'Synthetic interview',
            'audience': 'Developers',
            'goal': 'Explain a gateway',
            'operation': 'c' * 32,
        }
        current = self.tools.start_interview(self.root, data)
        self.assertEqual(self.tools.start_interview(self.root, data)['id'], current['id'])
        self.assertEqual(len(list((self.root / 'articles').iterdir())), 2)
        current = self.tools.answer(
            self.root,
            {
                'id': current['id'],
                'expected': current['expected'],
                'answer': 'I observed the gateway route a request.',
            },
        )
        current = self.tools.answer(
            self.root,
            {
                'id': current['id'],
                'expected': current['expected'],
                'question_id': current['answers'][0]['id'],
                'answer': 'Correction: this is a synthetic example.',
            },
        )
        self.assertEqual(
            current['answers'][0]['answer'], 'Correction: this is a synthetic example.'
        )
        job = self.create('interview-outline', operation='d' * 32, id=current['id'])
        self.jobs.once(self.engine)
        receipt = self.tools.apply(self.root, {'job': job['id']})
        self.assertFalse(receipt['draft_started'])
        self.assertFalse(receipt['approved'])
        current = self.tools.interview(self.root, current['id'])
        self.assertTrue(current['outline'])
        self.assertTrue(current['outline_content'])
        folder, _ = studio.item(self.root, 'articles', current['id'])
        self.assertFalse((folder / 'DRAFT.md').exists())
        run = blog_runner.create(
            self.root,
            {
                'id': current['id'],
                'mode': 'from-outline',
                'outline_text': current['outline_content'],
                'goal': 'Explain the synthetic gateway',
                'audience': 'Developers',
                'stop': 'draft',
                'research': 'none',
            },
        )
        self.assertEqual(run['id'], current['id'])
        self.assertEqual(
            studio.item(self.root, 'articles', current['id'])[1]['stop_point'], 'draft'
        )


class AdvisoryAndOutcomeTests(Fixture):
    def test_topic_advice_and_filters_are_local_bounded_and_non_mutating(self):
        import blog_library
        import planning

        source = self.source('Synthetic gateway performance notes.')
        folder, record = studio.item(self.root, 'sources', source['id'])
        record['library'] = {'collections': ['team-one'], 'curation': 'active'}
        studio.persist(folder, 'sources', record)
        before = (folder / 'record.json').read_bytes()
        self.assertEqual(planning.report(self.root, 'gateway')['items'][0]['id'], source['id'])
        self.assertEqual(
            blog_library.catalog(self.root, collection='team-one', status='needs-analysis')[
                'total'
            ],
            1,
        )
        other = self.base / 'other-team'
        studio.initialize(other)
        self.assertEqual(planning.report(other, 'gateway')['total'], 0)
        self.assertEqual((folder / 'record.json').read_bytes(), before)
        blog_library.curate(self.root, source['id'], {'curation': 'retired'})
        self.assertEqual(planning.report(self.root, 'gateway')['total'], 0)
        self.assertEqual(
            blog_library.catalog(self.root, status='retired', include_retired=True)['total'], 1
        )

    def test_compact_cli_keeps_full_default_and_reports_usage_save_and_failure(self):
        import json
        from pathlib import Path
        import subprocess
        import sys

        script = Path(studio.__file__)
        ident = self.article()
        self.file.write_text('A synthetic saved draft.')
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                '--root',
                str(self.root),
                '--compact',
                'article',
                'save',
                '--id',
                ident,
                '--kind',
                'draft',
                '--file',
                str(self.file),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value['saved'])
        self.assertFalse(value['shared'])
        self.assertNotIn('artifact_events', value)
        usage = subprocess.run(
            [sys.executable, str(script), '--compact', '--root', str(self.root), 'article', 'save'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(usage.returncode, 2)
        self.assertEqual(json.loads(usage.stdout)['status'], 'usage')
        failure = subprocess.run(
            [
                sys.executable,
                str(script),
                '--compact',
                '--root',
                str(self.root),
                'article',
                'show',
                '--id',
                'missing',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(json.loads(failure.stdout)['status'], 'failed')
        self.assertIsNone(json.loads(failure.stdout)['saved'])


class SourcePurposeTests(Fixture):
    """A ready reference becomes a voice or style sample from the page, in a new revision."""

    def mark(self, source, purpose, author=None):
        import management

        data = {'action': 'source-purpose', 'source': source, 'purpose': purpose}
        if author is not None:
            data['author'] = author
        return management.dispatch(self.root, 'tool-action', data)

    def test_a_ready_source_becomes_a_sample_in_a_new_revision(self):
        source = self.source('Short sentences about a fictional gateway.')
        result = self.mark(source['id'], 'voice-sample', 'Avery')
        self.assertEqual(
            {key: result[key] for key in ('source', 'revision', 'purposes')},
            {'source': source['id'], 'revision': 2, 'purposes': ['reference', 'voice-sample']},
        )
        self.assertEqual(result['receipts'][0]['sharing'], 'local-only')
        directory, record = studio.item(self.root, 'sources', source['id'])
        self.assertEqual((record['author'], record['revision']), ('Avery', 2))
        kept = studio.read_json(directory / 'revisions' / '1' / 'record.json')
        self.assertEqual((kept['purposes'], kept['author']), (['reference'], ''))
        self.assertEqual(
            (directory / 'revisions' / '1' / 'content.md').read_text(),
            'Short sentences about a fictional gateway.',
        )
        again = self.mark(source['id'], 'voice-sample', 'Avery')
        self.assertEqual((again['revision'], again['receipts']), (2, []), 'nothing to change')
        styled = self.mark(source['id'], 'style-sample', 'Someone else')
        self.assertEqual(styled['purposes'], ['reference', 'voice-sample', 'style-sample'])
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['author'], 'Avery')
        with self.assertRaisesRegex(ValueError, 'Avery'):
            self.mark(source['id'], 'voice-sample', 'Blake')

    def test_a_style_sample_takes_no_author(self):
        source = self.source('A synthetic announcement.')
        result = self.mark(source['id'], 'style-sample', 'Avery')
        self.assertEqual((result['revision'], result['author']), (2, ''))
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['author'], '')
        again = self.mark(source['id'], 'style-sample', 'Avery')
        self.assertEqual(again['revision'], 2, 'an author alone changes nothing for a style')

    def test_refuses_unknown_purposes_pending_sources_material_and_a_missing_author(self):
        import base64
        import blog_library
        import management

        ready = self.source('A synthetic paragraph.')
        with self.assertRaisesRegex(ValueError, 'voice sample or a style sample'):
            self.mark(ready['id'], 'reference')
        with self.assertRaisesRegex(ValueError, 'whose'):
            self.mark(ready['id'], 'voice-sample')
        pending = self.command(
            'source', 'add', '--name', 'Scan', '--purpose', 'reference', '--status', 'pending'
        )
        with self.assertRaisesRegex(ValueError, 'readable text'):
            self.mark(pending['id'], 'style-sample')
        with patch.object(blog_library.shutil, 'which', return_value=None):
            uploaded = management.dispatch(
                self.root,
                'upload',
                {
                    'operation': 'e' * 32,
                    'purpose': 'material',
                    'analyze': False,
                    'files': [
                        {
                            'filename': 'notes.md',
                            'content': base64.b64encode(b'Material words.').decode(),
                        }
                    ],
                },
            )
        material = uploaded['files'][0]['source']['id']
        with self.assertRaisesRegex(ValueError, 'one blog'):
            self.mark(material, 'voice-sample', 'Avery')
        for ident in (ready['id'], pending['id'], material):
            self.assertEqual(studio.item(self.root, 'sources', ident)[1]['revision'], 1)

    def test_the_voice_and_style_views_list_sources_that_could_become_samples(self):
        import article_tools
        import styles

        ready = self.source('A synthetic paragraph.')
        pending = self.command(
            'source', 'add', '--name', 'Scan', '--purpose', 'reference', '--status', 'pending'
        )
        self.mark(ready['id'], 'voice-sample', 'Avery')
        row = lambda ident: {
            key: studio.item(self.root, 'sources', ident)[1].get(key)
            for key in ('id', 'name', 'author')
        }
        voices = article_tools.voices(self.root)
        self.assertEqual(voices['candidates'], [])
        self.assertEqual(voices['pending'], [row(pending['id'])])
        self.assertEqual([s['id'] for s in voices['samples']], [ready['id']])
        found = styles.catalog(self.root)
        self.assertEqual(found['candidates'], [row(ready['id'])])
        self.assertEqual(found['pending'], [row(pending['id'])])
        blank = self.source('Text that goes away.')
        (studio.item(self.root, 'sources', blank['id'])[0] / 'content.md').write_text('  \n')
        found = styles.catalog(self.root)
        self.assertEqual(found['candidates'], [row(ready['id'])], 'no readable text, no sample')
        self.assertEqual(found['pending'], [row(pending['id']), row(blank['id'])])


class VoiceApplyTests(Fixture):
    """Changing a blog's voice is a recorded decision: confirmed once writing exists."""

    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def voice(self, name):
        self.file.write_text(name + ' writes short direct sentences.')
        return self.command(
            'profile',
            'create',
            '--name',
            name,
            '--guide-file',
            str(self.file),
            '--status',
            'confirmed',
        )

    def apply(self, ident, profile, **extra):
        import management

        current = manuscript_editor.read(self.root, ident)
        return management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'voice-apply',
                'id': ident,
                'profile': profile,
                'expected': current['expected'],
                **extra,
            },
        )

    def test_a_blog_with_a_draft_needs_a_confirmed_switch_that_stales_its_reviews(self):
        ident = self.article()
        blake = self.voice('Blake')
        review = self.base / 'review.json'
        review.write_text('{"findings": []}')
        self.command(
            'article',
            'review',
            '--id',
            ident,
            '--check',
            'proofread',
            '--status',
            'current',
            '--file',
            str(review),
        )
        directory, before = studio.item(self.root, 'articles', ident)
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.apply(ident, blake['id'])
        self.assertEqual(studio.item(self.root, 'articles', ident)[1], before)
        result = self.apply(ident, blake['id'], confirmed=True)
        self.assertEqual(result['status'], 'voice-selected')
        self.assertEqual(
            result['voice'], {'mode': 'profile', 'profile_id': blake['id'], 'revision': 1}
        )
        self.assertNotIn('run', result)
        self.assertEqual(len(result['receipts']), 1)
        _, after = studio.item(self.root, 'articles', ident)
        self.assertEqual(
            studio.freshness(self.root, directory, after)['proofread']['status'], 'stale'
        )

    def test_a_guided_run_records_the_change_and_keeps_its_style_and_tone(self):
        avery, blake = self.voice('Avery'), self.voice('Blake')
        found = blog_runner.create(
            self.root,
            {
                'title': 'Synthetic gateway guide',
                'audience': 'New authors',
                'goal': 'Explain a fictional gateway',
                'research': 'none',
                'profile': avery['id'],
                'tone': 'Warm',
                'style': 'how-to',
            },
            'page',
        )
        ident = found['id']
        empty = self.apply(ident, blake['id'])
        self.assertEqual(empty['run']['voice_name'], 'Blake', 'no writing yet: no confirmation')
        found = blog_runner.submit(
            self.root,
            ident,
            'outline',
            {'content': '# Outline\nSynthetic argument.', 'notes': ''},
            empty['run']['expected'],
            page=True,
        )
        found = blog_runner.decide(self.root, ident, found['expected'], 'approve', page=True)
        self.assertEqual(found['stages'][0]['status'], 'approved')
        same = self.apply(ident, blake['id'])
        self.assertEqual(same['run']['decisions'][-1]['event'], 'approve outline', 'the same pin')
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.apply(ident, avery['id'])
        result = self.apply(ident, avery['id'], confirmed=True)
        self.assertEqual(result['run']['stages'][0]['status'], 'stale')
        self.assertEqual(
            result['voice'],
            {'mode': 'profile', 'profile_id': avery['id'], 'revision': 1, 'tone': 'Warm'},
        )
        self.assertEqual(result['run']['voice_name'], 'Avery')
        self.assertEqual(result['run']['style_name'], 'How-to and tutorial')
        events = [row['event'] for row in result['run']['decisions']]
        self.assertEqual(
            events[-4:],
            [
                'Voice changed to Blake (revision 1)',
                'Submitted outline',
                'approve outline',
                'Voice changed to Avery (revision 1)',
            ],
        )
        _, record = studio.item(self.root, 'articles', ident)
        self.assertEqual(record['style'], {'style_id': 'how-to', 'revision': 1})
