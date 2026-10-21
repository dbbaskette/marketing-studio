"""Page-based Google manuscript intake, using synthetic documents and no accounts."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import copy
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import studio
import management
import google_drive as drive
import google_suggestions as suggestions
import blog_runner
import team_workspace as teams
from studio_sync import gitstate, support
from test_google_suggestions import ReviewProvider


class GoogleIntakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='blog-google-intake-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        environment = patch.dict(
            os.environ,
            {
                'HOME': str(self.base),
                'STUDIOS_CONFIG': str(self.base / 'settings.json'),
                'BLOG_STUDIO_DATA': str(self.base / 'data'),
                'BRAND_SKILL_RUNTIME': str(self.base / 'no-brand'),
                'GIT_CONFIG_GLOBAL': os.devnull,
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_AUTHOR_NAME': 'Synthetic Author',
                'GIT_AUTHOR_EMAIL': 'author@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic Author',
                'GIT_COMMITTER_EMAIL': 'author@example.invalid',
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.root = self.base / 'workspace'
        studio.initialize(self.root)
        self.client = ReviewProvider()
        client = patch.object(drive, 'Client', return_value=self.client)
        self.factory = client.start()
        self.addCleanup(client.stop)
        no_jobs = patch.object(
            blog_runner.Engine, 'start', side_effect=AssertionError('No assistant jobs')
        )
        no_jobs.start()
        self.addCleanup(no_jobs.stop)
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def preview(self):
        return management.dispatch(
            self.root,
            'google-preview',
            {'url': 'https://docs.google.com/document/d/fixture-doc/edit'},
        )

    def start(self, capture, **extra):
        return management.dispatch(
            self.root,
            'google-start',
            {
                'preview': capture['preview'],
                'expected': capture['expected'],
                'title': capture['title'],
                'confirmed': True,
                **extra,
            },
        )

    def snapshot(self, preview):
        return drive.staging_root(self.root) / ('desk-' + preview['preview']) / 'snapshot'

    def shared_launch(self, legacy=False):
        found = gitstate.local(self.base / 'managed-workspace', folder='blogs', branch='main')
        self.root = found.root
        if legacy:
            with patch.object(teams, 'keep_setup'):
                studio.initialize(self.root)
        else:
            studio.initialize(self.root)
        return found

    def test_shared_launch_records_setup_and_import_continues_without_an_assistant(self):
        found = self.shared_launch()
        self.assertEqual(gitstate.changed(found), [])
        result = self.start(self.preview())
        folder, _ = studio.item(self.root, 'articles', result['id'])
        self.assertTrue((folder / 'ORIGINAL.md').is_file())
        self.assertEqual(gitstate.changed(found), [])
        self.assertEqual(self.client.writes, 0)

    def test_import_recovers_old_generated_setup_files_but_refuses_author_edits(self):
        found = self.shared_launch(legacy=True)
        self.assertEqual(gitstate.changed(found), ['blogs/.shared/README.md', 'blogs/studio.json'])
        before = support.git(found.repo, 'rev-parse', 'HEAD')
        preview = self.preview()
        self.assertEqual(support.git(found.repo, 'rev-parse', 'HEAD'), before)
        unrelated = found.repo / 'unrelated.txt'
        unrelated.write_text('Synthetic unrelated staged edit.\n')
        support.git(found.repo, 'add', 'unrelated.txt')
        changed = self.root / 'notes.md'
        changed.write_text('Keep this unrecorded writing.\n')
        with self.assertRaisesRegex(ValueError, 'blogs/notes.md'):
            self.start(preview)
        self.assertEqual(changed.read_text(), 'Keep this unrecorded writing.\n')
        self.assertEqual(
            support.git(found.repo, 'diff', '--cached', '--name-only').strip(), 'unrelated.txt'
        )
        self.assertEqual(list(studio.inside(self.root, 'articles').glob('*/session.json')), [])
        changed.unlink()  # Only this synthetic fixture's unrecorded note.
        result = self.start(preview)
        self.assertTrue(studio.item(self.root, 'articles', result['id'])[0].is_dir())
        self.assertEqual(gitstate.changed(found), [])
        self.assertEqual(
            support.git(found.repo, 'diff', '--cached', '--name-only').strip(), 'unrelated.txt'
        )

    def test_modified_setup_metadata_is_never_adopted_as_generated(self):
        found = self.shared_launch(legacy=True)
        studio.write_json(
            self.root / 'studio.json',
            {
                'schema_version': 1,
                'created_at': studio.now(),
                'author_note': 'Keep this synthetic note.',
            },
        )
        (self.root / '.shared/README.md').write_text('Custom synthetic workspace instructions.\n')
        before = {
            name: (self.root / name).read_bytes() for name in ('studio.json', '.shared/README.md')
        }
        with self.assertRaisesRegex(ValueError, 'Local files changed outside'):
            self.start(self.preview())
        self.assertEqual(gitstate.changed(found), ['blogs/.shared/README.md', 'blogs/studio.json'])
        for name, content in before.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_image_payloads_are_hidden_in_preview_but_preserved_in_import_and_downloads(self):
        body = (
            '# Synthetic manuscript\n\nKeep the readable paragraph.\n\n![Synthetic chart][image1]\n\n[image1]: <data:image/png;base64,'
            + 'A' * 250_000
            + '>\n'
        )
        original_export = self.client.export
        with (
            patch(
                'google_suggestions.accepted_markdown',
                side_effect=drive.GoogleError('Synthetic image structure'),
            ),
            patch.object(
                self.client,
                'export',
                side_effect=lambda file_id, kind: (
                    body.encode() if kind == 'md' else original_export(file_id, kind)
                ),
            ),
        ):
            preview = self.preview()
        self.assertTrue(preview['images_omitted'])
        self.assertIn('Keep the readable paragraph.', preview['content'])
        self.assertNotIn('data:image', preview['content'])
        self.assertNotIn('image1', preview['content'])
        self.assertLess(len(preview['content']), 100)
        result = self.start(preview)
        folder, record = studio.item(self.root, 'articles', result['id'])
        self.assertEqual((folder / 'ORIGINAL.md').read_text(), body)
        self.assertEqual((folder / 'DRAFT.md').read_text(), body)
        self.assertEqual(self.client.writes, 0)
        # A small supplied draft exercises the same preview on the review screen.
        small = body.replace('A' * 250_000, 'AAAA')
        studio.save_artifact(folder, 'draft', small, record)
        studio.persist(folder, 'articles', record)
        blog_runner.create(
            self.root,
            {
                'id': result['id'],
                'mode': 'revise',
                'goal': 'Clarify this synthetic draft',
                'audience': 'Authors',
                'research': 'none',
                'stop': 'draft',
            },
        )
        shown = blog_runner.document(self.root, result['id'], 'draft')
        self.assertEqual(shown['content'], small)  # Download remains complete.
        self.assertTrue(shown['images_omitted'])
        self.assertNotIn('data:image', shown['preview_content'])

    def test_preview_is_private_and_confirmation_imports_the_original_link_and_formatting(self):
        drive.remember_account(self.root, 'author@example.invalid')
        preview = self.preview()
        self.factory.assert_called_once_with('author@example.invalid')
        self.assertEqual(preview['status'], 'preview')
        self.assertEqual(preview['title'], self.client.doc['title'])
        self.assertIn('delay', preview['content'])
        self.assertEqual(list(studio.inside(self.root, 'articles').iterdir()), [])
        self.assertFalse(
            studio.read_json(self.snapshot(preview) / 'observation.json')['structure_verified']
        )
        self.assertNotIn('native.json', json.dumps(preview))
        self.assertNotIn(str(self.base), json.dumps(preview))
        result = self.start(preview, title='Synthetic imported manuscript')
        folder, record = studio.item(self.root, 'articles', result['id'])
        self.assertEqual((folder / 'ORIGINAL.md').read_text(), preview['content'])
        self.assertEqual((folder / 'DRAFT.md').read_text(), preview['content'])
        baseline = record['google']['baselines']['draft']
        self.assertEqual(baseline['document']['document_id'], 'fixture-doc')
        self.assertEqual(record['voice']['mode'], 'preserve')
        self.assertFalse(self.snapshot(preview).exists())
        self.assertEqual(self.client.writes, 0)
        self.assertFalse((folder / blog_runner.STATE).exists())
        self.assertEqual(self.start(preview), result)  # A lost response can be retried.
        with studio.locked(self.root):
            run = blog_runner.create(
                self.root,
                {
                    'id': result['id'],
                    'mode': 'review',
                    'goal': 'Proofread this draft',
                    'audience': 'Authors',
                    'research': 'none',
                    'stop': 'review',
                },
            )
        self.assertEqual(run['google']['url'], result['linked_document'])

    def test_reopening_a_linked_doc_preserves_local_edits_and_baseline_without_reading_google(self):
        result = self.start(self.preview())
        folder, record = studio.item(self.root, 'articles', result['id'])
        before = copy.deepcopy(record['google'])
        studio.save_artifact(folder, 'draft', 'Unsent local edits.', record)
        studio.persist(folder, 'articles', record)
        with patch.object(
            self.client, 'native_read', side_effect=AssertionError('Unexpected Google read')
        ):
            repeated = self.preview()
        self.assertEqual(repeated['status'], 'already-linked')
        self.assertEqual(repeated['id'], result['id'])
        self.assertEqual((folder / 'DRAFT.md').read_text(), 'Unsent local edits.')
        self.assertEqual(studio.item(self.root, 'articles', result['id'])[1]['google'], before)

    def test_two_previews_import_only_one_blog_and_ignore_private_workspace_folders(self):
        (studio.inside(self.root, 'articles') / '.private-team-state').mkdir()
        first, second = self.preview(), self.preview()
        result = self.start(first)
        folder, record = studio.item(self.root, 'articles', result['id'])
        baseline = copy.deepcopy(record['google'])
        studio.save_artifact(folder, 'draft', 'Keep these local edits.', record)
        studio.persist(folder, 'articles', record)
        again = self.start(second)
        self.assertEqual(again['status'], 'already-linked')
        self.assertEqual(again['id'], result['id'])
        self.assertFalse(self.snapshot(second).exists())
        self.assertEqual((folder / 'DRAFT.md').read_text(), 'Keep these local edits.')
        self.assertEqual(studio.item(self.root, 'articles', result['id'])[1]['google'], baseline)

    def test_pending_suggestions_are_excluded_and_never_applied(self):
        edits = [
            {
                'id': 'pending',
                'kind': 'edit',
                'tab_id': 't.0',
                'start_index': 5,
                'before': 'delay',
                'after': 'wait',
                'reason': 'Synthetic suggestion.',
            }
        ]
        built = suggestions.build(
            self.client.native_read('fixture-doc', inline=True, comments=True), edits, ['t.0']
        )
        self.client.native_review_update('fixture-doc', 'r1', built['requests'])
        writes = self.client.writes
        preview = self.preview()
        self.assertGreater(preview['summary']['pending_suggestions'], 0)
        result = self.start(preview)
        folder, _ = studio.item(self.root, 'articles', result['id'])
        self.assertIn('delay', (folder / 'DRAFT.md').read_text())
        self.assertNotIn('wait', (folder / 'DRAFT.md').read_text())
        self.assertEqual(self.client.writes, writes)

    def test_validation_missing_confirmation_and_changed_preview_cannot_create_a_blog(self):
        for link in (
            'http://docs.google.com/document/d/id/edit',
            'https://example.invalid/document/d/id/edit',
            'https://docs.google.com.evil.invalid/document/d/id/edit',
            'https://user:secret@docs.google.com/document/d/id/edit',
            '../capture',
        ):
            with self.subTest(link=link), self.assertRaises((ValueError, drive.GoogleError)):
                management.dispatch(self.root, 'google-preview', {'url': link})
        self.factory.assert_not_called()
        preview = self.preview()
        for changes in ({'confirmed': False}, {'expected': 'old-view'}, {'preview': '../outside'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.start(preview, **changes)
        observation = self.snapshot(preview) / 'observation.json'
        value = studio.read_json(observation)
        value['revision_id'] = 'different'
        studio.write_json(observation, value)
        with self.assertRaisesRegex(ValueError, 'capture changed'):
            self.start(preview)
        self.assertEqual(list(studio.inside(self.root, 'articles').iterdir()), [])
        self.assertEqual(self.client.writes, 0)

    def test_tampered_manuscript_is_rejected_and_confirmation_is_reset_for_retry(self):
        preview = self.preview()
        (self.snapshot(preview) / 'document.md').write_text('Tampered')
        with self.assertRaises(ValueError):
            self.start(preview)
        self.assertFalse(
            studio.read_json(self.snapshot(preview) / 'observation.json')['structure_verified']
        )
        self.assertEqual(list(studio.inside(self.root, 'articles').iterdir()), [])

    def test_unavailable_or_multitab_doc_cleans_staging_and_keeps_existing_blogs(self):
        for failure in ('permission', 'tabs'):
            with self.subTest(failure=failure):
                if failure == 'permission':
                    provider = patch.object(
                        self.client,
                        'metadata',
                        side_effect=drive.GoogleError('Google access denied.'),
                    )
                else:
                    self.client.doc['tabs'].append(copy.deepcopy(self.client.doc['tabs'][0]))
                    provider = patch.object(self.client, 'metadata', wraps=self.client.metadata)
                with provider, self.assertRaises(drive.GoogleError):
                    self.preview()
                self.assertEqual(list(drive.staging_root(self.root).iterdir()), [])
                self.assertEqual(list(studio.inside(self.root, 'articles').iterdir()), [])

    def test_authenticated_http_routes_report_google_access_errors_and_refuse_unsigned_requests(
        self,
    ):
        server, url = management.server(self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def post(authenticated):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Content-Type': 'application/json'}
            if authenticated:
                headers['X-Blog-Studio-Token'] = url.split('#')[1]
            connection.request(
                'POST', '/api/google-preview', json.dumps({'url': 'fixture-doc'}), headers
            )
            response = connection.getresponse()
            result = response.status, json.loads(response.read())
            connection.close()
            return result

        status, _ = post(False)
        self.assertEqual(status, 400)
        self.factory.assert_not_called()
        with patch.object(
            self.client, 'metadata', side_effect=drive.GoogleError('Google sign-in is unavailable.')
        ):
            status, response = post(True)
        self.assertEqual(status, 400)
        self.assertIn('Google sign-in', response['error'])

    def compare(self, ident):
        import manuscript_editor

        return management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'google-compare',
                'id': ident,
                'expected': manuscript_editor.read(self.root, ident)['expected'],
            },
        )

    def accept(self, found, **extra):
        return management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'google-accept',
                'id': found['id'],
                'expected': found['expected'],
                'preview': found['preview'],
                'comparison': found['comparison'],
                'confirmed': True,
                **extra,
            },
        )

    def test_compared_accepted_text_keeps_pending_suggestions_and_never_writes_google(self):
        from test_google_suggestions import add_teammate_suggestion

        add_teammate_suggestion(self.client)
        writes = self.client.writes
        imported = self.start(self.preview())
        found = self.compare(imported['id'])
        self.assertEqual(found['status'], 'unchanged')
        self.assertGreater(found['summary']['pending_suggestions'], 0)
        result = self.accept(found)
        self.assertEqual(result['status'], 'accepted')
        self.assertFalse(result['google_written'])
        self.assertEqual(self.client.writes, writes)

    def test_changed_remote_or_local_text_blocks_old_preview_and_keeps_both(self):
        import manuscript_editor

        imported = self.start(self.preview())
        found = self.compare(imported['id'])
        self.client.doc['revisionId'] = 'later-revision'
        with self.assertRaisesRegex(ValueError, 'Google changed'):
            self.accept(found)
        found = self.compare(imported['id'])
        current = manuscript_editor.read(self.root, imported['id'])
        manuscript_editor.dispatch(
            self.root,
            'save',
            {
                'id': imported['id'],
                'expected': current['expected'],
                'content': current['content'] + '\n\nA local correction.',
            },
        )
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.accept(found)
        self.assertEqual(self.client.writes, 0)

    def test_comparison_previews_omit_images_without_changing_the_saved_text(self):
        import manuscript_editor

        imported = self.start(self.preview())
        current = manuscript_editor.read(self.root, imported['id'])
        content = (
            current['content']
            + '\n\n![Diagram][image1]\n\n[image1]: <data:image/png;base64,SYNTHETIC>\n'
        )
        manuscript_editor.dispatch(
            self.root,
            'save',
            {'id': imported['id'], 'expected': current['expected'], 'content': content},
        )
        found = self.compare(imported['id'])
        self.assertEqual(found['local'], content)
        self.assertNotIn('data:image', found['local_preview'])
        self.assertNotIn('![Diagram]', found['local_preview'])
        self.assertEqual(manuscript_editor.read(self.root, imported['id'])['content'], content)
        self.assertEqual(self.client.writes, 0)

    def test_pending_local_proposals_are_kept_and_prevent_baseline_replacement(self):
        import manuscript_editor

        imported = self.start(self.preview())
        current = manuscript_editor.read(self.root, imported['id'])
        body = current['content']
        manuscript_editor.dispatch(
            self.root,
            'proposals',
            {
                'id': imported['id'],
                'expected': current['expected'],
                'proposals': [
                    {
                        'kind': 'comment',
                        'before': body.splitlines()[0],
                        'reason': 'Synthetic review question',
                    }
                ],
            },
        )
        found = self.compare(imported['id'])
        self.assertTrue(found['has_proposals'])
        with self.assertRaisesRegex(ValueError, 'saved wording suggestions'):
            self.accept(found)
        self.assertEqual(len(manuscript_editor.read(self.root, imported['id'])['proposals']), 1)
        self.assertEqual(self.client.writes, 0)

    def test_one_shot_pull_command_keeps_read_compare_and_explicit_local_accept_distinct(self):
        import google_workflow

        imported = self.start(self.preview())
        args = studio.parser().parse_args(
            ['--root', str(self.root), 'google', 'pull', '--id', imported['id']]
        )
        found = google_workflow.command(self.root, args)
        self.assertEqual(found['status'], 'unchanged')
        self.assertFalse(found['google_written'])
        accept = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'google',
                'pull',
                '--id',
                imported['id'],
                '--accept',
                found['preview'],
                '--expected',
                found['expected'],
                '--comparison',
                found['comparison'],
                '--confirmed',
            ]
        )
        result = google_workflow.command(self.root, accept)
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(self.client.writes, 0)


if __name__ == '__main__':
    unittest.main()
