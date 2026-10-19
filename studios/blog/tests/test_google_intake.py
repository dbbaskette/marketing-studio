"""Page-based Google manuscript intake, using synthetic documents and no accounts."""

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


if __name__ == '__main__':
    unittest.main()
