"""Google transport invariants with disposable files and mocked network/auth."""

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
import urllib.error
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'
sys.path.insert(0, str(SCRIPTS))
import google_drive as gd


class GoogleDriveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client = gd.Client()
        self.client.request = Mock()
        # No test may reach the real gcloud CLI: sign-in is always a fixture.
        self.token = patch.object(gd, 'token', return_value='fixture-token').start()
        self.addCleanup(patch.stopall)

    def test_check_reports_only_drive_read_not_write_or_native_access(self):
        self.client.request.return_value = {'importFormats': {'text/html': [gd.DOC_MIME]}}
        result = self.client.check()
        self.assertTrue(result['html_import_advertised'])
        self.assertEqual(result['write'], 'unverified')
        self.assertEqual(result['native_docs'], 'unverified')

    def test_token_is_not_in_errors_and_account_does_not_switch_config(self):
        patch.stopall()  # This test exercises the real token lookup against a fixture gcloud.
        with (
            patch.object(gd, 'gcloud', return_value='gcloud'),
            patch.object(gd.subprocess, 'run') as run,
        ):
            run.return_value = subprocess.CompletedProcess(
                [], 1, 'secret-token', 'secret-diagnostic'
            )
            with self.assertRaises(gd.GoogleError) as error:
                gd.token('writer@example.invalid')
            self.assertNotIn('secret', str(error.exception))
            self.assertIn('--account', run.call_args.args[0])
            run.side_effect = subprocess.TimeoutExpired('gcloud', 30, output='secret-token')
            with self.assertRaises(gd.GoogleError) as error:
                gd.token()
            self.assertNotIn('secret', str(error.exception))

    def test_no_token_to_external_destinations_or_redirects(self):
        client = gd.Client()
        with patch.object(gd, 'token') as token:
            for url in (
                'http://www.googleapis.com/drive',
                'https://evil.invalid/',
                'https://www.googleapis.com@evil.invalid/',
            ):
                with self.assertRaises(gd.GoogleError):
                    client.request(url)
            token.assert_not_called()
        self.assertIsNone(
            gd.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.invalid')
        )

    def test_http_error_is_redacted_and_writes_are_not_retried(self):
        client = gd.Client()
        client.opener.open = Mock(
            side_effect=urllib.error.HTTPError(
                gd.DRIVE, 403, 'secret', {}, io.BytesIO(b'secret-token')
            )
        )
        with patch.object(gd, 'token', return_value='secret-token'):
            with self.assertRaises(gd.GoogleError) as error:
                client.request(gd.DRIVE + 'files', method='POST', body={'name': 'draft'})
        self.assertNotIn('secret', str(error.exception))
        self.assertEqual(client.opener.open.call_count, 1)

    def test_all_permission_pages_contribute_to_audience_and_shared_drive_is_supported(self):
        self.client.metadata = Mock(
            return_value={
                'mimeType': 'application/vnd.google-apps.folder',
                'capabilities': {'canAddChildren': True},
            }
        )
        self.client.request.side_effect = [
            {
                'permissions': [{'id': 'a', 'type': 'user', 'role': 'owner'}],
                'nextPageToken': 'next',
            },
            {'permissions': [{'id': 'b', 'type': 'anyone', 'role': 'reader'}]},
        ]
        result = self.client.audience('folder')
        self.assertEqual(len(result['permissions']), 2)
        self.assertIn('pageToken=next', self.client.request.call_args.args[0])
        self.assertIn('supportsAllDrives=true', self.client.request.call_args.args[0])
        self.assertEqual(
            result['audience_sha256'],
            gd.digest(gd.encoded({'folder_id': 'folder', 'permissions': result['permissions']})),
        )

    def test_folder_access_change_blocks_upload(self):
        source = self.root / 'draft.txt'
        source.write_text('Selected draft')
        self.client.audience = Mock(
            return_value={'audience_sha256': 'changed', 'can_add_children': True}
        )
        with self.assertRaises(gd.GoogleError):
            self.client.import_new(
                source, 'Title', self.root / 'receipt.json', 'folder', 'previous'
            )
        self.client.request.assert_not_called()
        self.assertFalse((self.root / 'receipt.json').exists())

    def test_import_is_native_multipart_and_never_claims_verified(self):
        source = self.root / 'draft.html'
        source.write_text('<h1>Selected draft</h1>')
        receipt = self.root / 'receipt.json'
        self.client.request.return_value = {'id': 'doc_123', 'mimeType': gd.DOC_MIME}
        result = self.client.import_new(source, 'Title', receipt)
        call = self.client.request.call_args
        self.assertIn('multipart/related', call.kwargs['mime'])
        self.assertIn(b'blogStudioOperation', call.kwargs['body'])
        self.assertNotIn(b'parents', call.kwargs['body'])
        self.assertEqual(result['status'], 'created-unverified')
        self.assertEqual(json.loads(receipt.read_text())['document_id'], 'doc_123')
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.client.import_new(source, 'Title', receipt)
        self.assertEqual(self.client.request.call_count, 1)

    def test_uncertain_upload_keeps_operation_and_reconcile_is_read_only(self):
        source = self.root / 'draft.txt'
        source.write_text('Selected')
        receipt = self.root / 'receipt.json'
        self.client.request.side_effect = gd.GoogleError('network timeout')
        with self.assertRaises(gd.GoogleError):
            self.client.import_new(source, 'Title', receipt)
        operation = json.loads(receipt.read_text())['operation']
        self.assertEqual(json.loads(receipt.read_text())['status'], 'submitting')
        self.client.request.reset_mock(side_effect=True)
        self.client.request.return_value = {'files': []}
        result = self.client.locate(operation)
        self.assertEqual(result['matches'], [])
        self.assertNotIn('method', self.client.request.call_args.kwargs)
        with self.assertRaises(FileExistsError):
            self.client.import_new(source, 'Title', receipt)
        self.assertEqual(self.client.request.call_count, 1)

    def test_native_read_excludes_suggestions_and_includes_all_tabs(self):
        self.client.native_read('doc')
        url = self.client.request.call_args.args[0]
        self.assertIn('includeTabsContent=true', url)
        self.assertIn('PREVIEW_WITHOUT_SUGGESTIONS', url)
        with self.assertRaises(gd.GoogleError):
            self.client.native_update('doc', '', [{'insertText': {}}])
        self.client.request.return_value = {'writeControl': {'requiredRevisionId': 'new'}}
        result = self.client.native_update(
            'doc',
            'fresh',
            [{'insertText': {'text': 'Hi', 'endOfSegmentLocation': {'tabId': 'tab1'}}}],
        )
        self.assertEqual(
            self.client.request.call_args.kwargs['body']['writeControl'],
            {'requiredRevisionId': 'fresh'},
        )
        self.assertEqual(result['status'], 'written-unverified')

    def test_markdown_export_uses_google_native_mime_and_validates_utf8(self):
        self.client.metadata = Mock(return_value={'mimeType': gd.DOC_MIME})
        self.client.request.return_value = b'# Heading\n\n**Emphasis**'
        self.assertEqual(self.client.export('doc', 'md'), b'# Heading\n\n**Emphasis**')
        self.assertIn('text%2Fmarkdown', self.client.request.call_args.args[0])
        self.client.request.return_value = b'\xff'
        with self.assertRaises(gd.GoogleError):
            self.client.export('doc', 'md')

    def test_export_validates_file_and_refuses_overwrite(self):
        self.client.metadata = Mock(return_value={'mimeType': gd.DOC_MIME})
        self.client.request.return_value = b'<html>error</html>'
        for format in ('pdf', 'docx'):
            with self.assertRaises(gd.GoogleError):
                self.client.export('doc', format)
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('[Content_Types].xml', 'x')
            archive.writestr('word/document.xml', 'x')
        self.client.request.return_value = data.getvalue()
        self.assertEqual(self.client.export('doc', 'docx'), data.getvalue())
        output = self.root / 'export.docx'
        gd.write_new(output, data.getvalue())
        with self.assertRaises(FileExistsError):
            gd.write_new(output, b'changed')
        self.assertEqual(output.read_bytes(), data.getvalue())
        link = self.root / 'link'
        link.symlink_to(output)
        with self.assertRaises(FileExistsError):
            gd.write_new(link, b'changed')

    def http_error(self, status, payload=None):
        body = io.BytesIO(json.dumps(payload or {}).encode())
        return urllib.error.HTTPError(gd.DRIVE, status, 'error', {}, body)

    def answer(self, value):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(value).encode()
        return response

    def test_sign_in_failure_before_upload_keeps_its_own_message_and_reserves_nothing(self):
        source = self.root / 'draft.html'
        source.write_text('<h1>Selected draft</h1>')
        self.token.side_effect = gd.GoogleError(
            'Google authentication is unavailable. ' + gd.SIGN_IN
        )
        with self.assertRaisesRegex(gd.GoogleError, 'authentication is unavailable') as caught:
            self.client.import_new(source, 'Title', self.root / 'receipt.json')
        self.assertNotIn('reconciliation', str(caught.exception))
        self.assertFalse((self.root / 'receipt.json').exists())
        self.client.request.assert_not_called()

    def test_refused_upload_releases_the_receipt_but_an_unanswered_one_keeps_it(self):
        source = self.root / 'draft.txt'
        source.write_text('Selected')
        self.client.request.side_effect = gd.GoogleError(
            'Google denied this operation.', status=403
        )
        with self.assertRaisesRegex(gd.GoogleError, 'no document was created') as caught:
            self.client.import_new(source, 'Title', self.root / 'receipt.json')
        self.assertEqual(caught.exception.status, 403)
        self.assertFalse((self.root / 'receipt.json').exists())
        # A server error may still have created the Doc, so the receipt stays for reconciliation.
        self.client.request.side_effect = gd.GoogleError(
            'Google request failed (HTTP 503).', status=503
        )
        with self.assertRaisesRegex(gd.GoogleError, 'needs reconciliation'):
            self.client.import_new(source, 'Title', self.root / 'receipt.json')
        self.assertEqual(
            json.loads((self.root / 'receipt.json').read_text())['status'], 'submitting'
        )

    def test_reads_are_retried_with_backoff_and_writes_are_sent_once(self):
        client = gd.Client()
        waits = []
        client.sleep = waits.append
        client.opener.open = Mock(
            side_effect=[
                self.http_error(503),
                urllib.error.URLError('timed out'),
                self.answer({'id': 'doc'}),
            ]
        )
        self.assertEqual(client.metadata('doc'), {'id': 'doc'})
        self.assertEqual(waits, list(gd.READ_RETRY_DELAYS))
        self.assertEqual(client.opener.open.call_count, 3)
        # One token lookup serves every request this process makes.
        self.assertEqual(self.token.call_count, 1)
        client.opener.open = Mock(side_effect=self.http_error(503))
        with self.assertRaisesRegex(gd.GoogleError, 'HTTP 503'):
            client.metadata('doc')
        self.assertEqual(client.opener.open.call_count, 3)
        for failure in (
            self.http_error(503),
            self.http_error(429),
            urllib.error.URLError('timed out'),
        ):
            client.opener.open = Mock(side_effect=failure)
            with self.assertRaises(gd.GoogleError) as caught:
                client.request(gd.DOCS + 'doc:batchUpdate', method='POST', body={})
            self.assertEqual(client.opener.open.call_count, 1)
            self.assertTrue(caught.exception.transient)
        self.assertIn('write may have completed', str(caught.exception))
        # A request Google refuses for a reason of its own is not repeated either.
        client.opener.open = Mock(side_effect=self.http_error(403))
        with self.assertRaises(gd.GoogleError):
            client.metadata('doc')
        self.assertEqual(client.opener.open.call_count, 1)

    def test_errors_say_what_happened_and_whether_anything_was_written(self):
        client = gd.Client('writer@example.invalid')
        client.sleep = lambda seconds: None
        client.opener.open = Mock(
            side_effect=self.http_error(
                404, {'error': {'status': 'NOT_FOUND', 'message': 'secret'}}
            )
        )
        with self.assertRaises(gd.GoogleError) as caught:
            client.metadata('doc')
        text = str(caught.exception)
        self.assertIn('not shared with writer@example.invalid', text)
        self.assertIn('nothing was written', text)
        self.assertNotIn('secret', text)
        self.assertTrue(caught.exception.definite)
        client.opener.open = Mock(side_effect=urllib.error.URLError('timed out'))
        with self.assertRaises(gd.GoogleError) as caught:
            client.metadata('doc')
        self.assertIn('safe to repeat', str(caught.exception))
        self.assertNotIn('write may have', str(caught.exception))
        self.assertFalse(caught.exception.definite)
        for status, definite, limited in (
            (400, True, False),
            (429, True, True),
            (500, False, False),
        ):
            error = gd.GoogleError('x', status=status)
            self.assertEqual((error.definite, error.rate_limited), (definite, limited))
        self.assertTrue(
            gd.GoogleError('x', status=403, labels={'userRateLimitExceeded'}).rate_limited
        )
        # An expired sign-in drops the cached token so the next call looks it up again.
        client.opener.open = Mock(side_effect=self.http_error(401))
        with self.assertRaisesRegex(gd.GoogleError, 'sign-in expired'):
            client.request(gd.DOCS + 'doc', method='POST', body={})
        before = self.token.call_count
        client.opener.open = Mock(return_value=self.answer({'id': 'doc'}))
        client.metadata('doc')
        self.assertEqual(self.token.call_count, before + 1)

    def workspace(self):
        import studio

        work = self.root / 'work'
        studio.initialize(work)
        return work

    def test_staging_stays_inside_the_workspace_and_only_staged_files_are_removed(self):
        work = self.workspace()
        capture = gd.staging_path(work, 'capture')
        capture.mkdir()
        (capture / 'document.md').write_text('Private text')
        plan = gd.staging_path(work, 'review-plan', '.json')
        plan.write_text('{}')
        self.assertTrue(gd.staged(work, capture))
        self.assertTrue(gd.staged(work, plan))
        self.assertEqual(gd.staging_root(work).stat().st_mode & 0o777, 0o700)
        outside = self.root / 'kept.md'
        outside.write_text('Author file')
        self.assertFalse(gd.staged(work, outside))
        self.assertFalse(gd.discard(work, outside))
        self.assertFalse(gd.discard(work, gd.staging_root(work)))
        self.assertFalse(gd.discard(work, None))
        self.assertTrue(outside.exists())
        self.assertTrue(gd.discard(work, capture))
        self.assertFalse(capture.exists())
        # Old leftovers are swept; recent files stay until cleared on request.
        self.assertEqual(gd.purge_staging(work, older_than=gd.STAGING_MAX_AGE), 0)
        self.assertTrue(plan.exists())
        self.assertEqual(gd.purge_staging(work), 1)
        self.assertFalse(plan.exists())
        with self.assertRaisesRegex(gd.GoogleError, 'initialized writing workspace'):
            gd.staging_path(self.root / 'elsewhere', 'x')

    def run_cli(self, *words):
        stdout = io.StringIO()
        stderr = io.StringIO()
        import contextlib

        with (
            patch.object(sys, 'argv', ['google_drive.py', *[str(word) for word in words]]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = gd.main()
        return code, json.loads(stdout.getvalue() if code == 0 else stderr.getvalue())

    def test_account_is_remembered_per_workspace_and_passed_automatically(self):
        work = self.workspace()
        self.assertIsNone(gd.saved_account(work))
        self.assertIsNone(gd.account_for(work))
        with self.assertRaises(gd.GoogleError):
            gd.remember_account(work, 'not an email')
        code, result = self.run_cli('--root', work, 'account', '--set', 'writer@example.invalid')
        self.assertEqual((code, result['account']), (0, 'writer@example.invalid'))
        saved = work / '.google-account.json'
        self.assertEqual(
            json.loads(saved.read_text()), {'account': 'writer@example.invalid', 'schema': 1}
        )
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertEqual(gd.account_for(work), 'writer@example.invalid')
        self.assertEqual(gd.account_for(work, 'other@example.invalid'), 'other@example.invalid')
        # Helpers started with --root use the remembered account without being told.
        with patch.object(gd, 'Client') as client:
            client.return_value.check.return_value = {'status': 'drive-read'}
            code, result = self.run_cli('--root', work, 'check')
        client.assert_called_once_with('writer@example.invalid')
        self.assertEqual(result['account'], 'writer@example.invalid')
        code, result = self.run_cli('--root', work, 'account', '--clear')
        self.assertTrue(result['removed'])
        self.assertIsNone(gd.saved_account(work))

    def test_login_adds_a_named_account_without_switching_gcloud(self):
        work = self.workspace()
        with (
            patch.object(gd, 'gcloud', return_value='gcloud'),
            patch.object(gd.subprocess, 'run') as run,
            patch.object(gd.Client, 'check', return_value={'status': 'drive-read'}),
        ):
            run.return_value = subprocess.CompletedProcess([], 0, 'someone@example.invalid\n', '')
            code, result = self.run_cli(
                '--root', work, '--account', 'writer@example.invalid', 'login'
            )
            self.assertEqual(code, 0)
            self.assertEqual(
                run.call_args.args[0],
                [
                    'gcloud',
                    'auth',
                    'login',
                    'writer@example.invalid',
                    '--enable-gdrive-access',
                    '--force',
                    '--no-activate',
                ],
            )
            self.assertEqual(result['remembered_account'], 'writer@example.invalid')
            self.assertEqual(gd.saved_account(work), 'writer@example.invalid')
            # Without a named account, an existing gcloud sign-in is never replaced silently.
            run.reset_mock()
            code, error = self.run_cli('login')
            self.assertEqual(code, 1)
            self.assertIn('already signed in as someone@example.invalid', error['error'])
            self.assertEqual(
                [call.args[0][1:4] for call in run.call_args_list],
                [['config', 'get-value', 'account']],
            )
            # Switching is possible, but only when asked for.
            code, _ = self.run_cli('--account', 'writer@example.invalid', 'login', '--activate')
            self.assertNotIn('--no-activate', run.call_args.args[0])
            # With no gcloud account at all there is nothing to switch, so a plain login proceeds.
            run.return_value = subprocess.CompletedProcess([], 0, '(unset)\n', '')
            code, _ = self.run_cli('login')
            self.assertEqual(code, 0)
            self.assertEqual(
                run.call_args.args[0],
                ['gcloud', 'auth', 'login', '--enable-gdrive-access', '--force'],
            )

    def test_raw_updates_reach_only_docs_linked_in_the_workspace(self):
        work = self.workspace()
        requests = self.root / 'requests.json'
        requests.write_text(json.dumps([{'insertText': {'text': 'Hi'}}]))
        with patch.object(
            gd.Client, 'native_update', return_value={'status': 'written-unverified'}
        ) as update:
            code, error = self.run_cli(
                'update',
                '--file-id',
                'someone-elses-doc',
                '--revision',
                'r1',
                '--requests',
                requests,
            )
            self.assertEqual(code, 1)
            self.assertIn('limited to Google Docs linked', error['error'])
            code, error = self.run_cli(
                '--root',
                work,
                'update',
                '--file-id',
                'someone-elses-doc',
                '--revision',
                'r1',
                '--requests',
                requests,
            )
            self.assertEqual(code, 1)
            self.assertIn('not linked to a blog', error['error'])
            update.assert_not_called()
            with patch.object(gd, 'linked_documents', return_value={'linked-doc'}):
                code, _ = self.run_cli(
                    '--root',
                    work,
                    'update',
                    '--file-id',
                    'linked-doc',
                    '--revision',
                    'r1',
                    '--requests',
                    requests,
                )
            self.assertEqual(code, 0)
            self.assertEqual(update.call_count, 1)
            code, _ = self.run_cli(
                '--root',
                work,
                'update',
                '--file-id',
                'new-copy',
                '--revision',
                'r1',
                '--requests',
                requests,
                '--first-handoff',
            )
            self.assertEqual(code, 0)
            self.assertEqual(update.call_count, 2)

    def test_staged_import_receipt_stops_a_repeat_of_the_same_upload(self):
        work = self.workspace()
        source = self.root / 'draft.html'
        source.write_text('<h1>Selected draft</h1>')
        created = {'id': 'doc_123', 'mimeType': gd.DOC_MIME}
        with patch.object(gd.Client, 'request', return_value=created) as request:
            code, result = self.run_cli(
                '--root', work, 'import', '--file', source, '--title', 'Title'
            )
            self.assertEqual((code, result['status']), (0, 'created-unverified'))
            code, error = self.run_cli(
                '--root', work, 'import', '--file', source, '--title', 'Title'
            )
            self.assertEqual(code, 1)
            self.assertIn('already attempted', error['error'])
            self.assertEqual(request.call_count, 1)
            code, error = self.run_cli('import', '--file', source, '--title', 'Title')
            self.assertEqual(code, 1)
            self.assertIn('--root', error['error'])
        self.assertEqual(len(list((work / '.google-staging').glob('import-receipt-*.json'))), 1)

    def test_setup_script_passes_the_email_and_does_not_switch_accounts_by_default(self):
        installer = Path(__file__).resolve().parents[1] / 'installer'
        fake = self.root / 'bin'
        fake.mkdir()
        python = fake / 'python3'
        # A stand-in interpreter that reports the helper arguments instead of running anything.
        python.write_text(
            '#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\nshift\nprintf "ARG:%s\\n" "$@"\n'
        )
        python.chmod(0o755)

        def setup(*words):
            env = {'PATH': str(fake) + ':/usr/bin:/bin', 'HOME': str(self.root)}
            done = subprocess.run(
                ['/bin/sh', str(installer / 'google-setup.sh'), *words],
                capture_output=True,
                text=True,
                env=env,
            )
            return (
                done.returncode,
                [line[4:] for line in done.stdout.split('\n') if line.startswith('ARG:')],
                done.stderr,
            )

        code, passed, _ = setup('--login', 'writer@example.invalid')
        self.assertEqual(code, 0)
        self.assertEqual(passed, ['--account', 'writer@example.invalid', 'login'])
        self.assertEqual(
            setup('--login', 'writer@example.invalid', '--activate')[1],
            ['--account', 'writer@example.invalid', 'login', '--activate'],
        )
        self.assertEqual(setup('--login')[1], ['login'])
        self.assertEqual(setup('--login', '--activate')[1], ['login', '--activate'])
        self.assertEqual(
            setup('--check', 'writer@example.invalid')[1],
            ['--account', 'writer@example.invalid', 'check'],
        )
        self.assertEqual(setup()[1], ['check'])
        for words in (
            ('--login', 'not-an-email'),
            ('--bogus',),
            ('--check', 'a@b.example', 'extra'),
            ('--login', 'a@b.example', '--activate', 'extra'),
        ):
            code, passed, error = setup(*words)
            self.assertEqual((code, passed), (2, []), words)
            self.assertTrue(error.strip())


if __name__ == '__main__':
    unittest.main()
