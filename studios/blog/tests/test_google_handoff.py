"""The page's first Google Doc handoff, with a stateful native Docs stand-in."""

import isolation  # noqa: F401
from pathlib import Path
from unittest.mock import patch

from test_blog_runner import RunnerCase
from test_google_roundtrip import Provider
import editorial
import google_drive as gd
import google_handoff as handoff
from google_suggestions import accepted_markdown
import studio


class Drive(Provider):
    def __init__(self):
        super().__init__()
        self.imports = []
        self.uncertain = False
        self.matches = []

    def import_new(self, path, title, state_path, folder_id=None, audience_sha256=None):
        self.imports.append((Path(path).read_bytes(), folder_id))
        receipt = {
            'schema': 1,
            'operation': 'a' * 32,
            'status': 'submitting',
            'content_sha256': studio.digest(Path(path).read_bytes()),
            'folder_id': None,
        }
        gd.write_new(Path(state_path), gd.encoded(receipt))
        if self.uncertain:
            raise gd.GoogleError('Upload outcome needs reconciliation.')
        receipt.update(
            status='created-unverified',
            document_id='fixture-doc',
            url='https://docs.google.com/document/d/fixture-doc/edit',
        )
        studio.write_json(Path(state_path), receipt)
        return receipt

    def locate(self, operation):
        return {'matches': self.matches}


class HandoffTests(RunnerCase):
    def setUp(self):
        super().setUp()
        self.drive = Drive()
        signed_in = patch.object(gd, 'active_account', return_value='test@example.invalid')
        signed_in.start()
        self.addCleanup(signed_in.stop)

    def finished(self):
        found = self.create(page=True)
        for stage in ('outline', 'draft', 'review', 'package'):
            found = self.submit(
                found,
                accepted_markdown(self.drive.doc).decode('utf-8') if stage == 'draft' else None,
                page=True,
            )
            found = self.approve(found, page=True)
        self.assertTrue(found['complete'])
        return found['id']

    def test_a_finished_blog_becomes_its_linked_doc_once(self):
        ident = self.finished()
        result = handoff.open_as_doc(self.root, ident, self.drive)
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        directory, record = studio.item(self.root, 'articles', ident)
        self.assertEqual(editorial.doc_link(record)['url'], result['url'])
        self.assertEqual(record['google']['transfers'][result['transfer']]['status'], 'confirmed')
        self.assertEqual(self.drive.imports, [((directory / 'DRAFT.md').read_bytes(), None)])
        self.assertEqual(handoff.open_as_doc(self.root, ident, self.drive)['url'], result['url'])
        self.assertEqual(len(self.drive.imports), 1)

    def test_refusals_and_uncertain_upload_never_import_twice(self):
        unfinished = self.create(page=True)['id']
        with self.assertRaisesRegex(ValueError, 'Finish the blog first'):
            handoff.open_as_doc(self.root, unfinished, self.drive)
        ident = self.finished()
        with patch.object(gd, 'active_account', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Google is not signed in'):
                handoff.open_as_doc(self.root, ident, self.drive)
        self.drive.uncertain = True
        with self.assertRaises(gd.GoogleError):
            handoff.open_as_doc(self.root, ident, self.drive)
        with self.assertRaisesRegex(ValueError, 'last upload is being checked'):
            handoff.open_as_doc(self.root, ident, self.drive)
        self.assertEqual(len(self.drive.imports), 1)
        self.drive.matches = [{'id': 'fixture-doc', 'mimeType': gd.DOC_MIME}]
        result = handoff.open_as_doc(self.root, ident, self.drive)
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        self.assertEqual(len(self.drive.imports), 1)

    def test_failed_readback_keeps_the_created_doc_for_retry(self):
        ident = self.finished()
        with patch.object(self.drive, 'native_read', side_effect=gd.GoogleError('Offline')):
            with self.assertRaises(gd.GoogleError):
                handoff.open_as_doc(self.root, ident, self.drive)
        handoff.open_as_doc(self.root, ident, self.drive)
        self.assertEqual(len(self.drive.imports), 1)

    def test_dispatch_requires_confirmation_and_the_shown_version(self):
        import blog_runner
        import management

        ident = self.finished()
        expected = blog_runner.survey(self.root, ident)['expected']
        with patch.object(gd, 'Client', return_value=self.drive):
            with self.assertRaisesRegex(ValueError, 'Confirm'):
                management.dispatch(self.root, 'google-open', {'id': ident, 'expected': expected})
            with self.assertRaisesRegex(ValueError, 'changed'):
                management.dispatch(
                    self.root, 'google-open', {'id': ident, 'expected': 'old', 'confirmed': True}
                )
            result = management.dispatch(
                self.root, 'google-open', {'id': ident, 'expected': expected, 'confirmed': True}
            )
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        self.assertEqual(len(self.drive.imports), 1)
        self.assertEqual(management.failure(handoff.Conflict('Not ready'), writing=True)[0], 409)

    def test_mismatched_readback_is_not_linked_or_uploaded_again(self):
        import google_roundtrip

        ident = self.finished()

        def different(client, document, tab, snapshot):
            client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0][
                'textRun'
            ]['content'] = 'Different heading.\n'
            return google_roundtrip.capture(client, document, tab, snapshot)

        with self.assertRaisesRegex(ValueError, 'readback does not match'):
            handoff.open_as_doc(self.root, ident, self.drive, different)
        _, record = studio.item(self.root, 'articles', ident)
        self.assertIsNone(editorial.doc_link(record))
        with self.assertRaisesRegex(ValueError, 'readback does not match'):
            handoff.open_as_doc(self.root, ident, self.drive)
        self.assertEqual(len(self.drive.imports), 1)

    def test_changed_local_draft_is_never_sent_or_confirmed(self):
        ident = self.finished()
        directory, _ = studio.item(self.root, 'articles', ident)
        (directory / 'DRAFT.md').write_text('Unapproved replacement.')
        with self.assertRaisesRegex(ValueError, 'Finish the blog first'):
            handoff.open_as_doc(self.root, ident, self.drive)
        self.assertEqual(self.drive.imports, [])
