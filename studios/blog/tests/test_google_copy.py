"""View-only intake and durable copy recovery, with no real Google accounts."""

import isolation  # noqa: F401
import copy
import json
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import test_google_intake as intake_fixture
from test_google_suggestions import ReviewProvider
import google_copy
import google_drive as drive
import management
import studio


SOURCE = 'https://docs.google.com/document/d/fixture-doc/edit'
ACCOUNT = 'author@example.invalid'
CLIENT_TYPE = drive.Client


class CopyProvider(ReviewProvider):
    def __init__(self):
        super().__init__()
        self.can_copy = True
        self.can_comment = False
        self.copies = []
        self.reads = []
        self.failure = None
        self.visible = True
        self.details = None
        self.original = copy.deepcopy(self.doc)

    def authorize(self):
        return None

    def drive(self, path, **query):
        if path == 'about':
            return {'user': {'emailAddress': ACCOUNT}}
        if path == 'files/root':
            return {'id': 'personal-root'}
        raise AssertionError(path)

    def metadata(self, file_id):
        return {
            'id': file_id,
            'version': self.version,
            'name': 'Synthetic draft',
            'mimeType': drive.DOC_MIME,
            'capabilities': {
                'canEdit': file_id == 'review-copy',
                'canCopy': self.can_copy,
                'canComment': self.can_comment,
            },
        }

    def native_read(self, file_id, **options):
        self.reads.append((file_id, options))
        if file_id == 'fixture-doc':
            assert not options.get('inline'), 'Never request editor-only views of the original'
            return copy.deepcopy(self.original)
        assert file_id == 'review-copy'
        return super().native_read(file_id, **options)

    def export(self, file_id, format):
        assert file_id == 'review-copy', 'Only capture the confirmed review copy'
        return super().export(file_id, format)

    def copy_document(self, file_id, title, parent, operation):
        assert file_id == 'fixture-doc'
        self.copies.append((file_id, title, parent, operation))
        if self.failure and self.failure.definite:
            raise self.failure
        self.doc = copy.deepcopy(self.original)
        self.doc['documentId'] = 'review-copy'
        for index, tab in enumerate(self.doc['tabs']):
            tab['tabProperties']['tabId'] = 'copied-' + str(index)
        self.details = {
            'id': 'review-copy',
            'mimeType': drive.DOC_MIME,
            'parents': [parent],
            'appProperties': {'blogStudioOperation': operation},
            'capabilities': {'canEdit': True},
        }
        if self.failure:
            raise self.failure
        return {'id': 'review-copy', 'mimeType': drive.DOC_MIME}

    def locate(self, operation):
        return {'matches': [self.details] if self.visible and self.details else []}

    def copy_details(self, file_id):
        assert file_id == 'review-copy'
        return copy.deepcopy(self.details)


class GoogleCopyTests(unittest.TestCase):
    def setUp(self):
        intake_fixture.GoogleIntakeTests.setUp(self)
        self.client = CopyProvider()
        self.factory.return_value = self.client
        active = patch.object(drive, 'active_account', return_value=ACCOUNT)
        self.active = active.start()
        self.addCleanup(active.stop)

    def offer(self, url=SOURCE):
        return management.dispatch(self.root, 'google-preview', {'url': url})

    def create(self, offer):
        return management.dispatch(
            self.root, 'google-copy', {'copy': offer['copy'], 'confirmed': True}
        )

    def test_warning_is_read_only_and_names_authenticated_account(self):
        shown = self.offer()
        self.assertEqual(shown['status'], 'view-only')
        self.assertEqual(shown['account'], ACCOUNT)
        self.assertTrue(shown['can_copy'])
        self.assertEqual(self.client.reads, [])
        self.assertEqual(self.client.copies, [])
        self.assertFalse(list(self.root.glob('.google-staging/desk-*')))
        self.client.can_comment = True
        self.assertEqual(self.offer()['access'], 'comment-only')

    def test_confirmed_copy_is_owned_in_my_drive_and_becomes_the_linked_doc(self):
        before = copy.deepcopy(self.client.original)
        offered = self.offer()
        made = self.create(offered)
        self.assertEqual(made['url'], 'https://docs.google.com/document/d/review-copy/edit')
        self.assertEqual(self.client.copies[0][2], 'personal-root')
        self.factory.assert_called_with(ACCOUNT)
        preview = self.offer(made['url'])
        imported = intake_fixture.GoogleIntakeTests.start(self, preview)
        folder, record = studio.item(self.root, 'articles', imported['id'])
        self.assertTrue((folder / 'DRAFT.md').is_file())
        self.assertIn('review-copy', json.dumps(record))
        self.assertEqual(self.client.original, before)
        self.assertEqual(self.client.writes, 0)
        # Reopening the source after a restart reconciles this copy, never posts again.
        again = self.offer()
        self.assertTrue(again['copy_pending'])
        self.assertEqual(self.create(again), made)
        self.assertEqual(len(self.client.copies), 1)

    def test_confirmation_and_current_account_are_required(self):
        offered = self.offer()
        for data in (
            {'copy': offered['copy']},
            {'copy': offered['copy'], 'confirmed': False},
            {'copy': '../outside', 'confirmed': True},
        ):
            with self.assertRaises(ValueError):
                management.dispatch(self.root, 'google-copy', data)
        self.active.return_value = 'other@example.invalid'
        with self.assertRaisesRegex(ValueError, 'account changed'):
            self.create(offered)
        self.assertEqual(self.client.copies, [])

    def test_copy_restriction_is_shown_and_rechecked_at_confirmation(self):
        offered = self.offer()
        self.client.can_copy = False
        blocked = self.offer()
        self.assertFalse(blocked['can_copy'])
        self.assertIsNone(blocked['copy'])
        with self.assertRaisesRegex(drive.GoogleError, 'does not allow'):
            self.create(offered)
        self.assertEqual(self.client.copies, [])

    def test_changed_source_requires_a_new_preview(self):
        offered = self.offer()
        self.client.version = '2'
        with self.assertRaisesRegex(drive.GoogleError, 'source Doc changed'):
            self.create(offered)
        self.assertEqual(self.client.copies, [])
        self.create(self.offer())
        self.assertEqual(len(self.client.copies), 1)

    def test_lost_reply_recovers_created_copy_without_reposting(self):
        offered = self.offer()
        self.client.failure = drive.GoogleError('Synthetic lost response', network=True)
        with self.assertRaisesRegex(drive.GoogleError, 'Check copy'):
            self.create(offered)
        self.client.failure = None
        pending = self.offer()
        self.assertTrue(pending['copy_pending'])
        self.assertIn('review-copy', self.create(pending)['url'])
        self.assertEqual(len(self.client.copies), 1)

    def test_unconfirmed_copy_never_posts_again_even_after_reopening(self):
        offered = self.offer()
        self.client.failure = drive.GoogleError('Synthetic lost response', network=True)
        self.client.visible = False
        with self.assertRaises(drive.GoogleError):
            self.create(offered)
        for _ in range(2):
            with self.assertRaisesRegex(drive.GoogleError, 'not confirmed yet'):
                self.create(self.offer())
        self.assertEqual(len(self.client.copies), 1)

    def test_definite_refusal_allows_an_explicit_retry(self):
        offered = self.offer()
        self.client.failure = drive.GoogleError('Synthetic forbidden', status=403)
        with self.assertRaisesRegex(drive.GoogleError, 'no copy was created'):
            self.create(offered)
        self.client.failure = None
        self.assertIn('review-copy', self.create(offered)['url'])
        self.assertEqual(len(self.client.copies), 2)

    def test_selected_tab_uses_the_new_copy_tab_id(self):
        second = copy.deepcopy(self.client.original['tabs'][0])
        second['tabProperties'] = {'tabId': 't.second', 'title': 'Chosen draft'}
        self.client.original['tabs'].append(second)
        offered = self.offer(SOURCE + '?tab=t.second')
        self.assertTrue(offered['selected_tab'])
        self.assertTrue(self.create(offered)['url'].endswith('?tab=copied-1'))
        self.assertFalse(
            any(
                options.get('inline')
                for ident, options in self.client.reads
                if ident == 'fixture-doc'
            )
        )

    def test_changed_copy_location_or_tabs_do_not_trigger_a_second_copy(self):
        offered = self.offer(SOURCE + '?tab=t.0')
        self.create(offered)
        self.client.doc['tabs'][0]['tabProperties']['title'] = 'Changed'
        with self.assertRaisesRegex(drive.GoogleError, 'tabs changed'):
            self.create(offered)
        self.client.details['parents'] = ['elsewhere']
        with self.assertRaisesRegex(drive.GoogleError, 'My Drive location'):
            self.create(offered)
        self.assertEqual(len(self.client.copies), 1)

    def test_workspace_access_is_checked_before_google_copy(self):
        offered = self.offer()
        with patch.object(management, 'authorize_write', side_effect=ValueError('Read-only Hub')):
            with self.assertRaisesRegex(ValueError, 'Read-only Hub'):
                self.create(offered)
        self.assertEqual(self.client.copies, [])

    def test_receipt_is_private_outside_the_shared_workspace(self):
        offered = self.offer()
        path = google_copy.receipt_path(self.root, offered['copy'])
        self.assertFalse(path.is_relative_to(self.root))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        path.unlink()
        path.symlink_to(self.base / 'outside')
        with self.assertRaisesRegex(ValueError, 'regular local file'):
            self.create(offered)

    def test_native_copy_request_targets_one_parent_and_private_operation(self):
        client = CLIENT_TYPE(ACCOUNT)
        client.request = Mock(return_value={'id': 'review-copy'})
        client.copy_document('fixture-doc', 'Review copy', 'personal-root', 'a' * 32)
        args, kwargs = client.request.call_args
        self.assertEqual(parse_qs(urlparse(args[0]).query)['copyComments'], ['false'])
        self.assertEqual(kwargs['method'], 'POST')
        self.assertEqual(
            kwargs['body'],
            {
                'name': 'Review copy',
                'parents': ['personal-root'],
                'appProperties': {'blogStudioOperation': 'a' * 32},
            },
        )
