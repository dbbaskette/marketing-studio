"""Team writing handoff using disposable homes and Git repositories."""

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from hub_fixtures import FakeProvider
from hub import Registry
from hub_store import HubError
from hub_workspace import Workspace
import hub_workspace as adapter_module
import hub_store as store_module
import studio


class HubWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        provider = FakeProvider(self.base / 'remotes')
        self.ra = Registry(self.base / 'a-hubs', provider)
        self.rb = Registry(self.base / 'b-hubs', provider)
        self.id = self.ra.create('fixture/writing', 'Writing')['hub']
        self.rb.join('fixture/writing')
        self.ha = self.ra.hub(self.id)
        self.hb = self.rb.hub(self.id)
        self.a = self.base / 'author-a'
        self.b = self.base / 'author-b'
        studio.initialize(self.a)
        studio.initialize(self.b)
        self.wa = Workspace(self.a, self.ha)
        self.wb = Workspace(self.b, self.hb)
        self.number = 0

    def file(self, text, suffix='.md'):
        self.number += 1
        p = self.base / ('input' + str(self.number) + suffix)
        p.write_text(text)
        return str(p)

    def command(self, root, *words):
        args = studio.parser().parse_args(['--root', str(root), *words])
        with studio.locked(root):
            return getattr(studio, args.group + '_command')(root, args)

    def article(self, root=None, mode='first-draft', profile=None):
        words = ['article', 'create', '--title', 'Writing handoffs', '--mode', mode]
        if profile:
            words += ['--profile', profile]
        return self.command(root or self.a, *words)['id']

    def save(self, root, aid, kind, body):
        return self.command(
            root, 'article', 'save', '--id', aid, '--kind', kind, '--file', self.file(body)
        )

    def export(self, aid):
        result = self.wa.publish_selected({'articles': [aid]})
        self.assertEqual(result['status'], 'shared')
        return result['items'][0]

    def checkout(self, reference, workspace=None):
        return (workspace or self.wb).checkout_selected({'articles': [reference['item']]})['items'][
            0
        ]['local_id']

    def test_hub_saved_timestamp_requires_remote_confirmation_and_does_not_drift(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'First version.')
        self.assertEqual(
            self.wa.publish_selected({'articles': [aid]}, offline=True)['status'], 'queued-offline'
        )
        key = 'articles/' + aid
        self.assertNotIn('last_saved_to_hub', self.wa.state['items'][key])
        ref = self.export(aid)
        first = dict(self.wa.state['items'][key])
        self.assertTrue(first['last_saved_to_hub'])
        self.assertEqual(first['last_saved_revision'], ref['revision'])
        self.assertEqual(self.wa.publish_selected({'articles': [aid]})['status'], 'synchronized')
        self.assertEqual(first, self.wa.state['items'][key])
        bid = self.checkout(ref)
        self.assertTrue(self.wb.state['items']['articles/' + bid]['last_saved_to_hub'])
        self.save(self.a, aid, 'draft', 'Second version.')
        self.wa.publish_selected({'articles': [aid]}, offline=True)
        pending = self.wa.state['items'][key]
        self.assertEqual(pending['last_saved_revision'], first['revision'])
        self.assertEqual(pending['last_saved_to_hub'], first['last_saved_to_hub'])
        self.assertNotEqual(pending['revision'], first['revision'])
        self.export(aid)
        self.assertNotEqual(self.wa.state['items'][key]['last_saved_revision'], first['revision'])
        confirmed = dict(self.wa.state['items'][key])
        self.ha.registry.provider.review = True
        self.save(self.a, aid, 'draft', 'Review-required version.')
        self.assertEqual(self.wa.publish_selected({'articles': [aid]})['status'], 'pending-review')
        self.assertEqual(
            self.wa.state['items'][key]['last_saved_to_hub'], confirmed['last_saved_to_hub']
        )
        import experience

        status = experience.context(self.a, aid)['google_sync']
        self.assertEqual(status['last_saved_to_hub'], confirmed['last_saved_to_hub'])
        self.assertEqual(status['hub_saved_revision'], confirmed['last_saved_revision'])

    def test_original_author_resumes_other_member_edit_without_duplicate_blog(self):
        aid = self.article()
        self.save(self.a, aid, 'original', 'Original manuscript.')
        self.save(self.a, aid, 'draft', 'Shared draft.')
        ref = self.export(aid)
        bid = self.checkout(ref)
        self.save(self.b, bid, 'draft', 'Other member edit.')
        self.wb.publish_selected({'articles': [bid]})
        resumed = self.wa.checkout_selected({'articles': [ref['item']]})['items'][0]
        self.assertEqual(resumed['local_id'], aid)
        self.assertEqual((self.a / 'articles' / aid / 'DRAFT.md').read_text(), 'Other member edit.')
        self.assertEqual(
            (self.a / 'articles' / aid / 'ORIGINAL.md').read_text(), 'Original manuscript.'
        )
        self.assertEqual(len(list((self.a / 'articles').iterdir())), 1)
        # A changed shared head cannot erase an unshared local edit.
        (self.a / 'articles' / aid / 'DRAFT.md').write_text('Unsaved local edit.')
        self.save(self.b, bid, 'draft', 'New shared edit.')
        self.wb.publish_selected({'articles': [bid]})
        with self.assertRaisesRegex(HubError, 'unshared local edits'):
            self.wa.checkout_selected({'articles': [ref['item']]})
        self.assertEqual(
            (self.a / 'articles' / aid / 'DRAFT.md').read_text(), 'Unsaved local edit.'
        )

    def test_cross_machine_dependencies_original_review_checkpoint_and_portable_guidance(self):
        source = self.command(
            self.a,
            'source',
            'add',
            '--name',
            'Evidence',
            '--file',
            self.file('Observed facts.'),
            '--purpose',
            'reference',
            '--purpose',
            'voice-sample',
        )['id']
        profile = self.command(
            self.a,
            'profile',
            'create',
            '--name',
            'Author',
            '--guide-file',
            self.file('Write plainly.'),
            '--sample',
            source,
        )['id']
        aid = self.article(mode='existing', profile=profile)
        self.command(self.a, 'article', 'attach', '--id', aid, '--source', source)
        self.save(self.a, aid, 'original', 'Original manuscript.')
        self.save(self.a, aid, 'draft', 'Edited manuscript.')
        self.command(
            self.a,
            'article',
            'note',
            '--id',
            aid,
            '--kind',
            'interview',
            '--text',
            'An actual example.',
        )
        self.command(
            self.a,
            'article',
            'derive',
            '--id',
            aid,
            '--name',
            'newsletter',
            '--file',
            self.file('Newsletter copy.'),
        )
        installed = self.command(self.a, 'article', 'show', '--id', aid)['guidance']
        self.assertEqual(
            installed,
            {
                'revision': adapter_module.studio.installed_guidance()['revision'],
                'source': 'installed',
            },
        )
        for check in ('proofread', 'factual-support'):
            self.command(
                self.a,
                'article',
                'review',
                '--id',
                aid,
                '--check',
                check,
                '--status',
                'current',
                '--file',
                self.file('{"findings":[]}', '.json'),
            )
        ref = self.export(aid)
        bid = self.checkout(ref)
        shown = self.command(self.b, 'article', 'show', '--id', bid)
        self.assertEqual(shown['stop_point'], 'review')
        self.assertEqual(shown['reviews']['proofread']['status'], 'current')
        self.assertEqual(shown['reviews']['factual-support']['status'], 'current')
        self.assertEqual(shown['guidance'], {'revision': installed['revision'], 'source': 'shared'})
        folder = self.b / 'articles' / bid
        self.assertEqual((folder / 'ORIGINAL.md').read_text(), 'Original manuscript.')
        self.assertEqual((folder / 'derived/newsletter.md').read_text(), 'Newsletter copy.')
        self.assertIn('actual example', (folder / 'INTERVIEW.md').read_text())
        global_record = self.ha.read(ref['item'])['record']
        text = json.dumps(global_record)
        self.assertNotIn(str(self.a), text)
        self.assertNotIn('runtime', text)
        self.assertNotIn(source, text)
        self.assertEqual(
            global_record['data']['studio']['guidance'],
            {'repository': adapter_module.GUIDANCE_REPOSITORY, 'revision': installed['revision']},
        )
        before = len(self.hb.graph()['revisions'])
        self.wb.publish_selected({'articles': [bid]})
        self.assertEqual(len(self.hb.graph()['revisions']), before)
        # Same installed version on the second machine: nothing to adopt and reviews stay current.
        self.command(self.b, 'article', 'guidance', '--id', bid)
        self.assertEqual(
            self.command(self.b, 'article', 'show', '--id', bid)['reviews']['proofread']['status'],
            'current',
        )

    def test_article_pinned_by_an_earlier_release_publishes_checks_out_and_adopts_on_request(self):
        aid = self.article(mode='existing')
        self.save(self.a, aid, 'original', 'Original manuscript.')
        self.save(self.a, aid, 'draft', 'Edited manuscript.')
        path = self.a / 'articles' / aid / 'session.json'
        record = json.loads(path.read_text())
        # A 1.x pin: guidance commit, task ID and a helper path that no longer exists on this machine.
        record['guidance'] = {
            'task': 'a' * 32,
            'revision': 'a' * 40,
            'runtime': str(self.base / 'removed/versions/1.15.0-abc/scripts'),
            'freshness': 'pinned',
        }
        record['guidance_history'] = [
            {
                'task': 'c' * 32,
                'revision': 'c' * 40,
                'runtime': str(self.base / 'removed'),
                'freshness': 'pinned',
            }
        ]
        path.write_text(json.dumps(record))
        self.command(
            self.a,
            'article',
            'review',
            '--id',
            aid,
            '--check',
            'proofread',
            '--status',
            'current',
            '--file',
            self.file('{"findings":[]}', '.json'),
        )
        ref = self.export(aid)
        shared = self.ha.read(ref['item'])['record']['data']['studio']
        self.assertEqual(
            shared['guidance'],
            {
                'repository': adapter_module.GUIDANCE_REPOSITORY,
                'revision': 'a' * 40,
                'freshness': 'pinned',
            },
        )
        self.assertEqual(
            shared['guidance_history'],
            [{'repository': adapter_module.GUIDANCE_REPOSITORY, 'revision': 'c' * 40}],
        )
        self.assertEqual(self.wa.publish_selected({'articles': [aid]})['status'], 'synchronized')
        bid = self.checkout(ref)
        shown = self.command(self.b, 'article', 'show', '--id', bid)
        self.assertEqual(
            shown['guidance'],
            {'revision': 'a' * 40, 'source': 'shared', 'shared_freshness': 'pinned'},
        )
        self.assertEqual(shown['guidance_history'], [{'revision': 'c' * 40, 'source': 'shared'}])
        self.assertEqual(shown['reviews']['proofread']['status'], 'current')
        self.assertNotIn('removed', json.dumps(shown['guidance']))
        before = len(self.hb.graph()['revisions'])
        self.wb.publish_selected({'articles': [bid]})
        self.assertEqual(len(self.hb.graph()['revisions']), before)
        with self.assertRaisesRegex(ValueError, '--adopt'):
            self.command(self.b, 'article', 'guidance', '--id', bid)
        adopted = self.command(self.b, 'article', 'guidance', '--id', bid, '--adopt')
        self.assertEqual(adopted['guidance']['source'], 'installed')
        self.assertEqual([g['revision'] for g in adopted['guidance_history']], ['c' * 40, 'a' * 40])
        self.assertEqual(adopted['reviews']['proofread']['status'], 'stale')
        self.assertEqual((self.b / 'articles' / bid / 'DRAFT.md').read_text(), 'Edited manuscript.')

    def test_article_memory_round_trip_and_retirement_keep_history(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'A preserved draft.')
        self.command(
            self.a,
            'article',
            'remember',
            '--id',
            aid,
            '--key',
            'headings',
            '--file',
            self.file('Use short headings.'),
        )
        ref = self.export(aid)
        bid = self.checkout(ref)
        shown = self.command(self.b, 'article', 'show', '--id', bid)
        self.assertEqual(shown['memory']['headings']['text'], 'Use short headings.')
        self.command(
            self.b,
            'article',
            'remember',
            '--id',
            bid,
            '--key',
            'headings',
            '--file',
            self.file('Use descriptive headings.'),
        )
        self.command(self.b, 'article', 'forget', '--id', bid, '--key', 'headings')
        self.wb.publish_selected({'articles': [bid]})
        self.ha.refresh()
        shared = self.ha.read(ref['item'])['record']['data']['studio']
        self.assertEqual(shared['memory']['headings']['status'], 'forgotten')
        self.assertEqual(shared['memory']['headings']['history'][0]['text'], 'Use short headings.')
        self.assertEqual((self.b / 'articles' / bid / 'DRAFT.md').read_text(), 'A preserved draft.')

    def test_clean_projection_resumes_new_shared_head_and_keeps_prior_folder(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Initial draft.')
        ref = self.export(aid)
        bid = self.checkout(ref)
        c = self.base / 'author-c'
        studio.initialize(c)
        wc = Workspace(c, self.hb)
        cid = self.checkout(ref, wc)
        self.save(self.b, bid, 'draft', 'Updated draft.')
        self.wb.publish_selected({'articles': [bid]})
        self.checkout(ref, wc)
        self.assertEqual((c / 'articles' / cid / 'DRAFT.md').read_text(), 'Updated draft.')
        self.assertEqual(
            (c / '.hub-history' / cid / ref['revision'] / 'DRAFT.md').read_text(), 'Initial draft.'
        )

    def test_dirty_projection_is_preserved_when_shared_head_changes(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Initial draft.')
        ref = self.export(aid)
        bid = self.checkout(ref)
        self.save(self.b, bid, 'draft', 'Unshared local edits.')
        self.save(self.a, aid, 'draft', 'Other author changes.')
        self.export(aid)
        with self.assertRaisesRegex(HubError, 'unshared local edits'):
            self.checkout(ref)
        self.assertEqual(
            (self.b / 'articles' / bid / 'DRAFT.md').read_text(), 'Unshared local edits.'
        )

    def test_same_baseline_writers_create_visible_conflict(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Initial draft.')
        ref = self.export(aid)
        bid = self.checkout(ref)
        self.save(self.a, aid, 'draft', 'A changes.')
        self.export(aid)
        self.save(self.b, bid, 'draft', 'B changes.')
        # Without the explicit choice the stale save waits; nothing competing is pushed.
        waiting = self.wb.publish_selected({'articles': [bid]})
        self.assertEqual(waiting['status'], 'newer-hub-revision')
        self.assertEqual(self.hb.status()['conflicts'], 0)
        forked = self.wb.publish_selected({'articles': [bid]}, fork=True)
        self.assertEqual(forked['status'], 'shared')
        self.assertEqual(self.hb.status()['conflicts'], 1)
        self.assertEqual(len(self.hb.graph()['heads'][ref['item']]), 2)

    def test_all_six_entry_paths_keep_checkpoints_and_stops(self):
        for mode, stop in [
            ('existing', 'review'),
            ('first-draft', 'draft'),
            ('outline-only', 'outline'),
            ('from-outline', 'draft'),
            ('interview', 'outline'),
            ('discover', 'brief'),
        ]:
            aid = self.article(mode=mode)
            self.command(
                self.a,
                'article',
                'progress',
                '--id',
                aid,
                '--stage',
                'intake',
                '--next-step',
                'Continue intake',
                '--pending-question',
                'Who is the reader?',
            )
            ref = self.export(aid)
            bid = self.checkout(ref)
            record = self.command(self.b, 'article', 'show', '--id', bid)
            self.assertEqual(record['stop_point'], stop)
            self.assertEqual(record['pending_question'], 'Who is the reader?')
            if mode == 'outline-only':
                with self.assertRaisesRegex(ValueError, 'stops before drafting'):
                    self.save(self.b, bid, 'draft', 'A draft.')

    def test_migration_only_shares_selected_item_and_dependencies(self):
        selected = self.article()
        other = self.article()
        (self.a / 'articles' / selected / 'credentials.json').write_text('DO NOT SHARE CREDENTIALS')
        (self.a / 'articles' / selected / '.cache').mkdir()
        (self.a / 'articles' / selected / '.cache/private.md').write_text('DO NOT SHARE CACHE')
        self.save(self.a, selected, 'draft', 'Selected.')
        self.save(self.a, other, 'draft', 'Private unrelated draft.')
        self.export(selected)
        self.assertEqual(self.ha.find(kind='article')['total'], 1)
        shared = b''.join(self.ha.files().values())
        self.assertNotIn(b'Private unrelated draft.', shared)
        self.assertNotIn(b'DO NOT SHARE', shared)

    def test_old_voice_revision_remains_pinned_across_handoff(self):
        profile = self.command(
            self.a,
            'profile',
            'create',
            '--name',
            'Author',
            '--guide-file',
            self.file('Original voice.'),
        )['id']
        aid = self.article(profile=profile)
        self.command(
            self.a, 'profile', 'save', '--id', profile, '--guide-file', self.file('Newer voice.')
        )
        ref = self.export(aid)
        bid = self.checkout(ref)
        record = self.command(self.b, 'article', 'show', '--id', bid)
        guide = self.command(
            self.b, 'profile', 'show', '--id', record['voice']['profile_id'], '--revision', '1'
        )['guide']
        self.assertEqual(Path(guide).read_text(), 'Original voice.')

    def test_context_adoption_stales_reviews_without_unrelated_hub_churn(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'An article.')
        self.command(
            self.a,
            'article',
            'review',
            '--id',
            aid,
            '--check',
            'proofread',
            '--status',
            'current',
            '--file',
            self.file('{"findings":[]}', '.json'),
        )
        rule = self.ha.save('rule', 'Style', 'Use sentence case.', data={'key': 'headings'})
        context = self.ha.context()
        self.ra.select(self.id, self.a)
        with patch.object(adapter_module, 'active', return_value=self.wa):
            self.command(
                self.a,
                'article',
                'context',
                '--id',
                aid,
                '--file',
                self.file(json.dumps(context), '.json'),
            )
        self.assertEqual(
            self.command(self.a, 'article', 'show', '--id', aid)['reviews']['proofread']['status'],
            'stale',
        )
        self.command(
            self.a,
            'article',
            'review',
            '--id',
            aid,
            '--check',
            'proofread',
            '--status',
            'current',
            '--file',
            self.file('{"findings":[]}', '.json'),
        )
        self.ha.save('note', 'Unrelated', 'A note.')
        self.assertEqual(
            self.command(self.a, 'article', 'show', '--id', aid)['reviews']['proofread']['status'],
            'current',
        )
        ref = self.export(aid)
        bid = self.checkout(ref)
        self.assertEqual(
            self.command(self.b, 'article', 'show', '--id', bid)['hub_context']['selected'][0][
                'revision'
            ],
            rule['revision'],
        )

    def test_auto_save_reports_offline_queue_and_configuration_errors_preserve_local(self):
        aid = self.article()
        self.ra.provider.unavailable = True
        output = io.StringIO()
        args = [
            'studio',
            '--root',
            str(self.a),
            'article',
            'save',
            '--id',
            aid,
            '--kind',
            'draft',
            '--file',
            self.file('Offline draft.'),
        ]
        with (
            patch.object(sys, 'argv', args),
            patch.object(adapter_module, 'active', return_value=self.wa),
            redirect_stdout(output),
        ):
            self.assertEqual(studio.main(), 0)
        self.assertEqual(json.loads(output.getvalue())['hub_sync']['status'], 'queued-unavailable')
        self.assertEqual(self.ha.status()['queued'], 1)
        output = io.StringIO()
        with (
            patch.object(sys, 'argv', args),
            patch.object(adapter_module, 'active', side_effect=HubError('Invalid hub selection')),
            redirect_stdout(output),
        ):
            self.assertEqual(studio.main(), 0)
        self.assertEqual(
            json.loads(output.getvalue())['hub_sync']['status'], 'local-saved-not-shared'
        )
        self.assertEqual((self.a / 'articles' / aid / 'DRAFT.md').read_text(), 'Offline draft.')

    def test_enqueue_crash_before_mapping_recovers_same_operation(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Durable content.')
        with patch.object(self.wa, 'persist', side_effect=OSError('Fixture crash')):
            with self.assertRaises(OSError):
                self.wa.publish_selected({'articles': [aid]}, offline=True)
        recovered = Workspace(self.a, self.ha)
        recovered.publish_selected({'articles': [aid]}, offline=True)
        self.assertEqual(len(self.ha.graph()['revisions']), 1)

    def test_failed_projection_does_not_leave_partial_article_and_can_retry(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Shared draft.')
        ref = self.export(aid)
        real = adapter_module.atomic

        def fail(path, data):
            if path.name == 'DRAFT.md':
                raise OSError('Fixture write failure')
            return real(path, data)

        with patch.object(adapter_module, 'atomic', side_effect=fail):
            with self.assertRaises(OSError):
                self.checkout(ref)
        self.assertEqual(list((self.b / 'articles').iterdir()), [])
        self.assertFalse(list(self.b.glob('.hub-projection-*')))
        bid = self.checkout(ref)
        self.assertEqual((self.b / 'articles' / bid / 'DRAFT.md').read_text(), 'Shared draft.')

    def test_inconsistent_portable_draft_is_rejected_without_projection(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Original shared draft.')
        ref = self.export(aid)
        read = self.ha.read(ref['item'])
        record = read['record']
        artifacts = {
            name[10:]: (Path(path).read_bytes(), record['files'][name]['media'])
            for name, path in read['paths'].items()
            if name.startswith('artifacts/')
        }
        bad = self.ha.save(
            'article',
            record['title'],
            'Different canonical body.',
            item=ref['item'],
            data=record['data'],
            dependencies=record['dependencies'],
            artifacts=artifacts,
        )
        with self.assertRaisesRegex(HubError, 'body and draft disagree'):
            self.checkout(bad)
        self.assertEqual(list((self.b / 'articles').iterdir()), [])

    def test_projection_mapping_crash_preserves_later_unshared_edits(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Shared draft.')
        ref = self.export(aid)
        with patch.object(self.wb, 'persist', side_effect=OSError('Mapping interrupted')):
            with self.assertRaises(OSError):
                self.checkout(ref)
        bid = 'hub-' + ref['item']
        (self.b / 'articles' / bid / 'DRAFT.md').write_text('Edits after interruption.')
        self.wb = Workspace(self.b, self.hb)
        self.checkout(ref)
        self.save(self.a, aid, 'draft', 'Another shared revision.')
        self.export(aid)
        with self.assertRaisesRegex(HubError, 'unshared local edits'):
            self.checkout(ref)
        self.assertEqual(
            (self.b / 'articles' / bid / 'DRAFT.md').read_text(), 'Edits after interruption.'
        )

    def test_complete_article_conflict_resolution_retains_original_and_resumes(self):
        aid = self.article(mode='existing')
        self.save(self.a, aid, 'original', 'Original.')
        self.save(self.a, aid, 'draft', 'Initial.')
        ref = self.export(aid)
        bid = self.checkout(ref)
        self.save(self.a, aid, 'draft', 'A edit.')
        a = self.export(aid)
        self.save(self.b, bid, 'draft', 'B edit.')
        self.wb.publish_selected({'articles': [bid]}, fork=True)
        self.ha.refresh()
        graph = self.ha.graph()
        heads = graph['heads'][ref['item']]
        self.assertEqual(len(heads), 2)
        chosen = self.ha.read(ref['item'], a['revision'])
        record = chosen['record']
        artifacts = {
            name[10:]: (Path(path).read_bytes(), record['files'][name]['media'])
            for name, path in chosen['paths'].items()
            if name.startswith('artifacts/')
        }
        artifacts['DRAFT.md'] = (b'Merged author choice.', 'text')
        data = record['data']
        data['studio']['reviews'] = {}
        resolved = self.ha.save(
            'article',
            record['title'],
            'Merged author choice.',
            item=ref['item'],
            parents=heads,
            data=data,
            dependencies=record['dependencies'],
            artifacts=artifacts,
        )
        root = self.base / 'resolved'
        studio.initialize(root)
        wc = Workspace(root, self.hb)
        cid = self.checkout(resolved, wc)
        self.assertEqual((root / 'articles' / cid / 'ORIGINAL.md').read_text(), 'Original.')
        self.assertEqual(
            (root / 'articles' / cid / 'DRAFT.md').read_text(), 'Merged author choice.'
        )
        self.assertEqual(self.ha.status()['conflicts'], 0)
        self.assertEqual(set(self.ha.read(ref['item'])['record']['parents']), set(heads))

    def test_unavailable_and_inspiration_sources_do_not_become_evidence(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'A claim.')
        source = self.command(
            self.a,
            'source',
            'add',
            '--name',
            'Inspiration',
            '--file',
            self.file('Inspiration only.'),
            '--purpose',
            'inspiration',
        )['id']
        self.command(self.a, 'article', 'attach', '--id', aid, '--source', source)
        self.command(
            self.a,
            'article',
            'review',
            '--id',
            aid,
            '--check',
            'factual-support',
            '--status',
            'current',
            '--file',
            self.file('{"findings":[]}', '.json'),
        )
        ref = self.export(aid)
        bid = self.checkout(ref)
        self.assertEqual(
            self.command(self.b, 'article', 'show', '--id', bid)['reviews']['factual-support'][
                'status'
            ],
            'unavailable',
        )

    # ---- history is shared once; growth is linear -------------------------------

    def article_revisions(self, hub, item):
        graph = hub.graph(include_local=False)
        return sorted(
            (r for r in graph['revisions'].values() if r['item'] == item),
            key=lambda r: r['created_at'],
        )

    def history_files(self, record):
        return sorted(name for name in record['files'] if name.startswith('artifacts/history/'))

    def test_history_is_shared_once_and_hub_growth_is_linear(self):
        draft = ('A paragraph of synthetic manuscript text for growth checks. ' * 12 + '\n\n') * 6
        aid = self.article()
        sizes = []
        for number in range(1, 9):
            self.save(self.a, aid, 'draft', draft + 'Saved version ' + str(number) + '.\n')
            ref = self.export(aid)
            files = self.ha.files(include_local=False)
            sizes.append((len(files), sum(len(body) for body in files.values())))
        # Each revision carries only the history created since its parent.
        revisions = self.article_revisions(self.ha, ref['item'])
        self.assertEqual([len(self.history_files(r)) for r in revisions], [0, 1, 1, 1, 1, 1, 1, 1])
        shared_history = [name for r in revisions for name in self.history_files(r)]
        self.assertEqual(len(shared_history), len(set(shared_history)))
        # Paths grow by the same amount per save, and bytes by about one save's worth.
        path_steps = [later[0] - earlier[0] for earlier, later in zip(sizes, sizes[1:])]
        byte_steps = [later[1] - earlier[1] for earlier, later in zip(sizes, sizes[1:])]
        self.assertEqual(len(set(path_steps[1:])), 1, path_steps)
        self.assertLess(byte_steps[-1] - byte_steps[1], len(draft), byte_steps)
        # Another clone still gets every earlier draft, under the same names.
        bid = self.checkout(ref)
        local = {p.name: p.read_text() for p in (self.a / 'articles' / aid / 'history').iterdir()}
        resumed = {p.name: p.read_text() for p in (self.b / 'articles' / bid / 'history').iterdir()}
        self.assertEqual(len(local), 7)
        self.assertEqual(resumed, local)
        # Publishing the unchanged resumed copy adds nothing.
        before = len(self.hb.graph()['revisions'])
        self.assertEqual(self.wb.publish_selected({'articles': [bid]})['status'], 'synchronized')
        self.assertEqual(len(self.hb.graph()['revisions']), before)
        # "Undo" on the second clone can reach the very first draft.
        first = sorted(resumed)[0]
        preview = self.command(self.b, 'article', 'restore', '--id', bid, '--revision', first)
        self.assertEqual(preview['status'], 'preview')
        self.command(
            self.b,
            'article',
            'restore',
            '--id',
            bid,
            '--revision',
            first,
            '--expected',
            preview['expected'],
            '--apply',
        )
        self.assertEqual(
            (self.b / 'articles' / bid / 'DRAFT.md').read_text(), draft + 'Saved version 1.\n'
        )
        # The restore is one more save: one new history file travels, not the folder.
        back = self.wb.publish_selected({'articles': [bid]})
        self.assertEqual(back['status'], 'shared')
        newest = self.article_revisions(self.hb, ref['item'])[-1]
        self.assertEqual(len(self.history_files(newest)), 1)
        # The first author resumes that revision and keeps the whole trail.
        self.wa.checkout_selected({'articles': [ref['item']]})
        self.assertEqual(len(list((self.a / 'articles' / aid / 'history').iterdir())), 8)

    def test_hub_written_by_an_earlier_runtime_still_resumes_and_then_grows_linearly(self):
        aid = self.article()
        # An earlier runtime repeated the whole history folder in every revision.
        with patch.object(adapter_module, 'inherited_history', lambda name: False):
            for number in range(1, 5):
                self.save(self.a, aid, 'draft', 'Earlier runtime draft ' + str(number) + '.')
                ref = self.export(aid)
        revisions = self.article_revisions(self.ha, ref['item'])
        self.assertEqual([len(self.history_files(r)) for r in revisions], [0, 1, 2, 3])
        bid = self.checkout(ref)
        history = self.b / 'articles' / bid / 'history'
        self.assertEqual(
            sorted(p.read_text() for p in history.iterdir()),
            ['Earlier runtime draft 1.', 'Earlier runtime draft 2.', 'Earlier runtime draft 3.'],
        )
        # New saves on top stop repeating what those revisions already hold.
        self.save(self.b, bid, 'draft', 'Current runtime draft 5.')
        self.assertEqual(self.wb.publish_selected({'articles': [bid]})['status'], 'shared')
        newest = self.article_revisions(self.hb, ref['item'])[-1]
        self.assertEqual(len(self.history_files(newest)), 1)
        self.wa.checkout_selected({'articles': [ref['item']]})
        self.assertEqual(len(list((self.a / 'articles' / aid / 'history').iterdir())), 4)

    # ---- no silent forks ---------------------------------------------------------

    def mutate(self, root, workspace, *words):
        """A studio mutation followed by the same publish step studio.main runs."""
        args = studio.parser().parse_args(['--root', str(root), *words])
        with studio.locked(root):
            record = studio.article_command(root, args)
            return workspace.publish_mutation('article', record)

    def stale_second_clone(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'Version one.')
        ref = self.export(aid)
        bid = self.checkout(ref)
        self.save(self.a, aid, 'draft', 'Version two by the first author.')
        self.export(aid)
        return aid, bid, ref

    def test_stale_clone_keeps_its_save_local_instead_of_forking(self):
        aid, bid, ref = self.stale_second_clone()
        # The second clone is one revision behind and changes only a next-step note.
        outcome = self.mutate(
            self.b,
            self.wb,
            'article',
            'progress',
            '--id',
            bid,
            '--stage',
            'draft',
            '--next-step',
            'A small note from the stale clone',
        )
        self.assertEqual(outcome['status'], 'newer-hub-revision')
        self.assertEqual(outcome['sync_status'], 'synchronized')
        self.assertIn('--fork', outcome['next_step'])
        self.assertIn('--set-aside-local', outcome['next_step'])
        self.assertEqual(outcome['newer_revision'][0]['local_id'], bid)
        # Nothing competing reached the hub and neither clone sees a conflict.
        self.ha.refresh()
        self.assertEqual(len(self.ha.graph()['heads'][ref['item']]), 1)
        self.assertEqual((self.ha.status()['conflicts'], self.hb.status()['conflicts']), (0, 0))
        self.assertEqual(self.hb.status()['held'], 1)
        # More local changes do not pile further saves onto the waiting one.
        again = self.mutate(
            self.b,
            self.wb,
            'article',
            'progress',
            '--id',
            bid,
            '--stage',
            'draft',
            '--next-step',
            'Another note',
        )
        self.assertEqual(again['status'], 'newer-hub-revision')
        self.assertEqual(self.hb.status()['held'], 1)
        # The first author keeps saving normally.
        self.save(self.a, aid, 'draft', 'Version three by the first author.')
        self.assertEqual(self.export(aid)['kind'], 'article')
        self.assertEqual(self.ha.status()['conflicts'], 0)
        # Resuming the shared version never silently discards the unshared work.
        with self.assertRaisesRegex(HubError, 'unshared local edits'):
            self.wb.checkout_selected({'articles': [ref['item']]})
        self.assertEqual(
            self.command(self.b, 'article', 'show', '--id', bid)['next_step'], 'Another note'
        )
        # The explicit choice to continue from the shared version keeps a backup.
        held_revision = self.wb.state['items']['articles/' + bid]['revision']
        self.wb.checkout_selected({'articles': [ref['item']]}, set_aside=True)
        self.assertEqual(
            (self.b / 'articles' / bid / 'DRAFT.md').read_text(),
            'Version three by the first author.',
        )
        backup = self.b / '.hub-history' / bid / held_revision
        self.assertEqual(
            json.loads((backup / 'session.json').read_text())['next_step'], 'Another note'
        )
        self.assertEqual(self.hb.status()['held'], 0)
        self.assertTrue((self.hb.root / 'withdrawn' / held_revision / 'intent.json').is_file())
        # From there the second clone shares normally again.
        self.save(self.b, bid, 'draft', 'Version four by the second author.')
        self.assertEqual(self.wb.publish_selected({'articles': [bid]})['status'], 'shared')
        self.assertEqual(self.hb.status()['conflicts'], 0)

    def test_offline_save_from_a_stale_clone_waits_and_can_be_forked_explicitly(self):
        aid, bid, ref = self.stale_second_clone()
        self.save(self.b, bid, 'draft', 'Offline edit by the second author.')
        queued = self.wb.publish_selected({'articles': [bid]}, offline=True)
        self.assertEqual(queued['status'], 'queued-offline')
        # Back online, the queued save is found to be stale and is not pushed.
        waiting = self.hb.sync()
        self.assertEqual(waiting['status'], 'newer-hub-revision')
        self.ha.refresh()
        self.assertEqual(len(self.ha.graph()['heads'][ref['item']]), 1)
        # The explicit option shares it as a competing version for a real merge.
        forked = self.wb.publish_selected({'articles': [bid]}, fork=True)
        self.assertEqual(forked['status'], 'shared')
        self.assertEqual((forked['held'], forked['conflicts']), (0, 1))
        self.ha.refresh()
        self.assertEqual(len(self.ha.graph()['heads'][ref['item']]), 2)

    def test_blog_pinning_a_stale_source_waits_with_it(self):
        source = self.command(
            self.a,
            'source',
            'add',
            '--name',
            'Figures',
            '--file',
            self.file('First figures.'),
            '--purpose',
            'reference',
        )['id']
        self.assertEqual(self.wa.publish_selected({'sources': [source]})['status'], 'shared')
        item = self.wa.state['items']['sources/' + source]['item']
        copy = self.wb.checkout_selected({'sources': [item]})['items'][0]['local_id']
        # The first author revises the shared source; the second edits an old copy.
        self.command(
            self.a,
            'source',
            'update',
            '--id',
            source,
            '--text-file',
            self.file('Corrected figures.'),
        )
        self.assertEqual(self.wa.publish_selected({'sources': [source]})['status'], 'shared')
        self.command(
            self.b,
            'source',
            'update',
            '--id',
            copy,
            '--text-file',
            self.file('Second author figures.'),
        )
        blog = self.article(self.b)
        self.command(self.b, 'article', 'attach', '--id', blog, '--source', copy)
        self.save(self.b, blog, 'draft', 'A draft citing the figures.')
        waiting = self.wb.publish_selected({'articles': [blog]})
        self.assertEqual(waiting['status'], 'newer-hub-revision')
        self.assertEqual(self.hb.status()['held'], 2)  # the source and the blog that pins it
        self.ha.refresh()
        self.assertEqual(len(self.ha.graph()['heads'][item]), 1)
        self.assertEqual(self.ha.find(kind='article')['total'], 0)
        # Further saves are refused with the source named, not with a validation error.
        self.save(self.b, blog, 'draft', 'A second draft citing the figures.')
        again = self.wb.publish_selected({'articles': [blog]})
        self.assertEqual(again['status'], 'newer-hub-revision')
        self.assertIn(copy, again['next_step'])
        self.assertIn('--source', again['next_step'])
        self.assertEqual(self.hb.status()['held'], 2)
        # The explicit choice shares both, as competing source versions.
        forked = self.wb.publish_selected({'articles': [blog]}, fork=True)
        self.assertEqual((forked['status'], forked['held']), ('shared', 0))
        self.ha.refresh()
        self.assertEqual(len(self.ha.graph()['heads'][item]), 2)
        self.assertEqual(self.ha.find(kind='article')['total'], 1)

    # ---- multi-hop history -------------------------------------------------------

    def third_clone(self):
        registry = Registry(self.base / 'c-hubs', self.ra.provider)
        registry.join('fixture/writing')
        root = self.base / 'author-c'
        studio.initialize(root)
        return root, Workspace(root, registry.hub(self.id))

    def source_texts(self, root, local_id):
        folder = root / 'sources' / local_id
        return sorted(path.read_text() for path in folder.rglob('content.md'))

    def test_source_history_survives_two_handoffs(self):
        source = self.command(
            self.a,
            'source',
            'add',
            '--name',
            'Spec',
            '--file',
            self.file('First author, revision one.'),
            '--purpose',
            'reference',
        )['id']
        self.command(
            self.a,
            'source',
            'update',
            '--id',
            source,
            '--text-file',
            self.file('First author, revision two.'),
        )
        self.assertEqual(self.wa.publish_selected({'sources': [source]})['status'], 'shared')
        item = self.wa.state['items']['sources/' + source]['item']
        second = self.wb.checkout_selected({'sources': [item]})['items'][0]['local_id']
        self.command(
            self.b,
            'source',
            'update',
            '--id',
            second,
            '--text-file',
            self.file('Second author, revision three.'),
        )
        self.assertEqual(self.wb.publish_selected({'sources': [second]})['status'], 'shared')
        root, third_workspace = self.third_clone()
        third = third_workspace.checkout_selected({'sources': [item]})['items'][0]['local_id']
        everything = [
            'First author, revision one.',
            'First author, revision two.',
            'Second author, revision three.',
        ]
        self.assertEqual(self.source_texts(root, third), everything)
        # A third handoff keeps them all as well.
        self.command(
            root,
            'source',
            'update',
            '--id',
            third,
            '--text-file',
            self.file('Third author, revision four.'),
        )
        self.assertEqual(third_workspace.publish_selected({'sources': [third]})['status'], 'shared')
        fourth = self.wa.checkout_selected({'sources': [item]})['items'][0]['local_id']
        self.assertEqual(
            self.source_texts(self.a, fourth), everything + ['Third author, revision four.']
        )

    def test_projected_files_never_overwrite_each_other(self):
        target = self.b / 'existing.md'
        target.write_text('Already projected')
        with self.assertRaisesRegex(HubError, 'same local file'):
            self.wb._place(target, b'Second file for the same path')
        self.assertEqual(target.read_text(), 'Already projected')

    # ---- size limits -------------------------------------------------------------

    def test_oversized_source_text_is_refused_at_intake_when_the_workspace_is_shared(self):
        self.ra.select(self.id, self.a)
        with patch.object(adapter_module, 'active', return_value=self.wa):
            with patch.object(store_module, 'MAX_TEXT', 4096):
                with self.assertRaises(ValueError) as refused:
                    self.command(
                        self.a,
                        'source',
                        'add',
                        '--name',
                        'Huge report',
                        '--file',
                        self.file('word ' * 2000),
                        '--purpose',
                        'reference',
                    )
                message = str(refused.exception)
                self.assertIn('Huge report', message)
                self.assertIn('content.md', message)
                self.assertIn('limited to 4,096 bytes', message)
                self.assertEqual(list((self.a / 'sources').iterdir()), [])
                small = self.command(
                    self.a,
                    'source',
                    'add',
                    '--name',
                    'Small',
                    '--file',
                    self.file('Fits.'),
                    '--purpose',
                    'reference',
                )['id']
                with self.assertRaisesRegex(ValueError, 'Nothing was changed'):
                    self.command(
                        self.a,
                        'source',
                        'update',
                        '--id',
                        small,
                        '--text-file',
                        self.file('word ' * 2000),
                    )
        self.assertEqual((self.a / 'sources' / small / 'content.md').read_text(), 'Fits.')

    def test_existing_oversized_source_fails_clearly_and_recovers(self):
        # Saved before a hub was selected, so intake accepted it.
        source = self.command(
            self.a,
            'source',
            'add',
            '--name',
            'Long transcript',
            '--file',
            self.file('word ' * 2000),
            '--purpose',
            'reference',
        )['id']
        aid = self.article()
        self.command(self.a, 'article', 'attach', '--id', aid, '--source', source)
        self.save(self.a, aid, 'draft', 'A draft that cites the transcript.')
        with patch.object(store_module, 'MAX_TEXT', 4096):
            for attempt in range(2):
                with self.assertRaises(HubError) as failure:
                    self.wa.publish_selected({'articles': [aid]})
                message = str(failure.exception)
                self.assertIn('Long transcript', message)
                self.assertIn(source, message)
                self.assertIn('content.md', message)
                self.assertIn('limited to 4,096 bytes', message)
                self.assertIn('source update', message)
            self.assertEqual(self.ha.status()['queued'], 0)
            # Following the named remedy makes the blog shareable again. The earlier,
            # larger text remains in this computer's history and is reported, not shared.
            self.command(
                self.a,
                'source',
                'update',
                '--id',
                source,
                '--text-file',
                self.file('A short excerpt.'),
            )
            # The blog still pins the long revision; the message says how to move on.
            with self.assertRaisesRegex(
                HubError, 'revision 1, which this blog pins.*article attach --id ' + aid
            ):
                self.wa.publish_selected({'articles': [aid]})
            self.command(self.a, 'article', 'attach', '--id', aid, '--source', source)
            shared = self.wa.publish_selected({'articles': [aid]})
            self.assertEqual(shared['status'], 'shared')
            reasons = ' '.join(shared['kept_on_this_computer'][0]['kept_on_this_computer'])
            self.assertIn('revisions/1/content.md', reasons)
            self.assertIn('original.md', reasons)
            self.assertEqual(
                (self.a / 'sources' / source / 'revisions/1/content.md').read_text(), 'word ' * 2000
            )
            item = self.wa.state['items']['sources/' + source]['item']
            record = self.ha.read(item)['record']
            self.assertEqual(
                sorted(record['files']),
                ['BODY.md', 'artifacts/content.md', 'artifacts/revisions/1/record.json'],
            )
            self.assertEqual(
                {entry['file'] for entry in record['data']['studio']['files_kept_local']},
                {'original.md', 'revisions/1/content.md'},
            )

    def test_oversized_original_stays_local_while_its_text_is_shared(self):
        path = self.base / 'scan.pdf'
        path.write_bytes(b'%PDF' + b'\x00\xff' * 4000)
        with patch.object(store_module, 'MAX_BINARY', 4096):
            added = self.command(
                self.a,
                'source',
                'add',
                '--name',
                'Scanned report',
                '--file',
                str(path),
                '--text-file',
                self.file('Extracted findings.'),
                '--purpose',
                'reference',
            )
            self.assertIn('original file scan.pdf', added['sharing_limits'][0])
            result = self.wa.publish_selected({'sources': [added['id']]})
            self.assertEqual(result['status'], 'shared')
            self.assertIn(
                'original.pdf', result['kept_on_this_computer'][0]['kept_on_this_computer'][0]
            )
            item = self.wa.state['items']['sources/' + added['id']]['item']
            shared = self.ha.read(item)['record']
            self.assertEqual(sorted(shared['files']), ['BODY.md', 'artifacts/content.md'])
            self.assertIsNone(shared['data']['studio']['original_path'])
            self.assertEqual(
                shared['data']['studio']['files_kept_local'][0]['file'], 'original.pdf'
            )
            # Unchanged, it is not published again.
            before = len(self.ha.graph()['revisions'])
            self.assertEqual(
                self.wa.publish_selected({'sources': [added['id']]})['status'], 'synchronized'
            )
            self.assertEqual(len(self.ha.graph()['revisions']), before)
        second = self.wb.checkout_selected({'sources': [item]})['items'][0]['local_id']
        self.assertEqual(
            (self.b / 'sources' / second / 'content.md').read_text(), 'Extracted findings.'
        )
        self.assertTrue((self.a / 'sources' / added['id'] / 'original.pdf').is_file())

    # ---- binding map is read under the lock --------------------------------------

    def test_binding_saved_by_another_command_is_not_overwritten(self):
        aid = self.article()
        self.save(self.a, aid, 'draft', 'First.')
        early = Workspace(self.a, self.ha)  # built before another command publishes
        ref = self.export(aid)
        self.save(self.a, aid, 'draft', 'Second.')
        latest = self.export(aid)
        # The early adapter must build on the newest binding, not the one it loaded.
        self.save(self.a, aid, 'draft', 'Third.')
        self.assertEqual(early.publish_selected({'articles': [aid]})['status'], 'shared')
        heads = self.ha.graph()['heads'][ref['item']]
        self.assertEqual(len(heads), 1)
        self.assertEqual(self.ha.graph()['revisions'][heads[0]]['parents'], [latest['revision']])


if __name__ == '__main__':
    unittest.main()
