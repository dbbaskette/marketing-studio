"""Google transport invariants with disposable files and mocked network/auth."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
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

    def test_check_reports_only_drive_read_not_write_or_native_access(self):
        self.client.request.return_value = {'importFormats': {'text/html': [gd.DOC_MIME]}}
        result = self.client.check()
        self.assertTrue(result['html_import_advertised'])
        self.assertEqual(result['write'], 'unverified')
        self.assertEqual(result['native_docs'], 'unverified')

    def test_token_is_not_in_errors_and_account_does_not_switch_config(self):
        with patch.object(gd, 'gcloud', return_value='gcloud'), patch.object(gd.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 1, 'secret-token', 'secret-diagnostic')
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
            for url in ('http://www.googleapis.com/drive', 'https://evil.invalid/', 'https://www.googleapis.com@evil.invalid/'):
                with self.assertRaises(gd.GoogleError):
                    client.request(url)
            token.assert_not_called()
        self.assertIsNone(gd.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.invalid'))

    def test_http_error_is_redacted_and_writes_are_not_retried(self):
        client = gd.Client()
        client.opener.open = Mock(side_effect=urllib.error.HTTPError(gd.DRIVE, 403, 'secret', {}, io.BytesIO(b'secret-token')))
        with patch.object(gd, 'token', return_value='secret-token'):
            with self.assertRaises(gd.GoogleError) as error:
                client.request(gd.DRIVE + 'files', method='POST', body={'name':'draft'})
        self.assertNotIn('secret', str(error.exception))
        self.assertEqual(client.opener.open.call_count, 1)

    def test_all_permission_pages_contribute_to_audience_and_shared_drive_is_supported(self):
        self.client.metadata = Mock(return_value={'mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True}})
        self.client.request.side_effect = [
            {'permissions':[{'id':'a','type':'user','role':'owner'}], 'nextPageToken':'next'},
            {'permissions':[{'id':'b','type':'anyone','role':'reader'}]}]
        result = self.client.audience('folder')
        self.assertEqual(len(result['permissions']), 2)
        self.assertIn('pageToken=next', self.client.request.call_args.args[0])
        self.assertIn('supportsAllDrives=true', self.client.request.call_args.args[0])
        self.assertEqual(result['audience_sha256'], gd.digest(gd.encoded({'folder_id':'folder','permissions':result['permissions']})))

    def test_folder_access_change_blocks_upload(self):
        source = self.root / 'draft.txt';source.write_text('Selected draft')
        self.client.audience = Mock(return_value={'audience_sha256':'changed','can_add_children':True})
        with self.assertRaises(gd.GoogleError):
            self.client.import_new(source,'Title',self.root/'receipt.json','folder','previous')
        self.client.request.assert_not_called()
        self.assertFalse((self.root/'receipt.json').exists())

    def test_import_is_native_multipart_and_never_claims_verified(self):
        source = self.root/'draft.html';source.write_text('<h1>Selected draft</h1>')
        receipt = self.root/'receipt.json'
        self.client.request.return_value = {'id':'doc_123','mimeType':gd.DOC_MIME}
        result = self.client.import_new(source,'Title',receipt)
        call = self.client.request.call_args
        self.assertIn('multipart/related',call.kwargs['mime'])
        self.assertIn(b'blogStudioOperation',call.kwargs['body'])
        self.assertNotIn(b'parents',call.kwargs['body'])
        self.assertEqual(result['status'],'created-unverified')
        self.assertEqual(json.loads(receipt.read_text())['document_id'],'doc_123')
        self.assertEqual(receipt.stat().st_mode & 0o777,0o600)
        with self.assertRaises(FileExistsError):
            self.client.import_new(source,'Title',receipt)
        self.assertEqual(self.client.request.call_count,1)

    def test_uncertain_upload_keeps_operation_and_reconcile_is_read_only(self):
        source = self.root/'draft.txt';source.write_text('Selected')
        receipt = self.root/'receipt.json'
        self.client.request.side_effect = gd.GoogleError('network timeout')
        with self.assertRaises(gd.GoogleError):
            self.client.import_new(source,'Title',receipt)
        operation = json.loads(receipt.read_text())['operation']
        self.assertEqual(json.loads(receipt.read_text())['status'],'submitting')
        self.client.request.reset_mock(side_effect=True)
        self.client.request.return_value = {'files':[]}
        result = self.client.locate(operation)
        self.assertEqual(result['matches'],[])
        self.assertNotIn('method',self.client.request.call_args.kwargs)
        with self.assertRaises(FileExistsError):
            self.client.import_new(source,'Title',receipt)
        self.assertEqual(self.client.request.call_count,1)

    def test_native_read_excludes_suggestions_and_includes_all_tabs(self):
        self.client.native_read('doc')
        url = self.client.request.call_args.args[0]
        self.assertIn('includeTabsContent=true',url)
        self.assertIn('PREVIEW_WITHOUT_SUGGESTIONS',url)
        with self.assertRaises(gd.GoogleError):
            self.client.native_update('doc','', [{'insertText':{}}])
        self.client.request.return_value = {'writeControl':{'requiredRevisionId':'new'}}
        result = self.client.native_update('doc','fresh', [{'insertText':{'text':'Hi','endOfSegmentLocation':{'tabId':'tab1'}}}])
        self.assertEqual(self.client.request.call_args.kwargs['body']['writeControl'],{'requiredRevisionId':'fresh'})
        self.assertEqual(result['status'],'written-unverified')

    def test_markdown_export_uses_google_native_mime_and_validates_utf8(self):
        self.client.metadata = Mock(return_value={'mimeType': gd.DOC_MIME})
        self.client.request.return_value = b'# Heading\n\n**Emphasis**'
        self.assertEqual(self.client.export('doc','md'), b'# Heading\n\n**Emphasis**')
        self.assertIn('text%2Fmarkdown',self.client.request.call_args.args[0])
        self.client.request.return_value = b'\xff'
        with self.assertRaises(gd.GoogleError):self.client.export('doc','md')

    def test_export_validates_file_and_refuses_overwrite(self):
        self.client.metadata = Mock(return_value={'mimeType':gd.DOC_MIME})
        self.client.request.return_value = b'<html>error</html>'
        for format in ('pdf','docx'):
            with self.assertRaises(gd.GoogleError):self.client.export('doc',format)
        data = io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('[Content_Types].xml','x');archive.writestr('word/document.xml','x')
        self.client.request.return_value=data.getvalue()
        self.assertEqual(self.client.export('doc','docx'),data.getvalue())
        output=self.root/'export.docx';gd.write_new(output,data.getvalue())
        with self.assertRaises(FileExistsError):gd.write_new(output,b'changed')
        self.assertEqual(output.read_bytes(),data.getvalue())
        link=self.root/'link';link.symlink_to(output)
        with self.assertRaises(FileExistsError):gd.write_new(link,b'changed')


if __name__ == '__main__':
    unittest.main()
