"""The page's first Google Doc handoff, with a stateful native Docs stand-in."""

import isolation  # noqa: F401
from pathlib import Path
import re
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

    def finished(self, spelling=None):
        # A run the manuscript editor's revision made, its review approved.
        found = self.editor_run('revise')
        found = self.submit(found, spelling or accepted_markdown(self.drive.doc).decode('utf-8'))
        found = self.approve(self.submit(found))
        self.assertTrue(found['complete'])
        return found['id']

    def on_desk(self, spelling=None):
        """A blog on the writing desk whose draft is the one the stand-in Doc reads back,
        or the given spelling of it. A desk draft starts with its title, so the Doc does too."""
        return self.desk(spelling or self.desk_text(), title='Desk title')['id']

    def desk_text(self):
        """The Markdown the stand-in Doc reads back, with the title a desk draft starts with."""
        if not getattr(self, 'titled', False):
            titled(self.drive.doc, 'Desk title')
            self.titled = True
        return accepted_markdown(self.drive.doc).decode('utf-8')

    def open(self, ident, *args):
        return handoff.open_as_doc(self.root, ident, self.drive, *args, desk=True)

    def test_equivalent_link_and_heading_spellings_confirm_one_native_doc(self):
        native = self.desk_text()
        ordinary = native.replace('](<https://example.invalid>)', '](https://example.invalid)')
        ordinary = ordinary.replace(
            '## The delay is in handoffs.', 'The delay is in handoffs.\n-------------------------'
        )
        ident = self.on_desk(ordinary)
        result = self.open(ident)
        self.assertTrue(result['url'])
        self.assertEqual(len(self.drive.imports), 1)
        self.assertEqual(self.open(ident), result)

    def test_handoff_rejects_changed_urls_structure_formatting_and_code(self):
        native = self.desk_text()
        link = '[Keep this link.](<https://example.invalid>)'
        for changed in (
            native.replace('https://example.invalid', 'https://different.invalid'),
            native.replace('## ', '# ', 1),
            native.replace('Keep this link.', '**Keep this link.**'),
            native.replace(link, '`[Keep this link.](https://example.invalid)`'),
            native.replace(link, '```\n[Keep this link.](https://example.invalid)\n```'),
            native.replace(link, r'\[Keep this link.](https://example.invalid)'),
        ):
            with self.subTest(changed=changed):
                ident = self.on_desk(changed)
                with self.assertRaisesRegex(handoff.Conflict, 'readback does not match'):
                    self.open(ident)

    def test_a_finished_blog_becomes_its_linked_doc_once(self):
        ident = self.on_desk()
        result = self.open(ident)
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        directory, record = studio.item(self.root, 'articles', ident)
        self.assertEqual(editorial.doc_link(record)['url'], result['url'])
        self.assertEqual(record['google']['transfers'][result['transfer']]['status'], 'confirmed')
        self.assertEqual(self.drive.imports, [((directory / 'DRAFT.md').read_bytes(), None)])
        self.assertEqual(self.open(ident)['url'], result['url'])
        self.assertEqual(len(self.drive.imports), 1)

    def taken_to_the_desk(self, state, move):
        """A saved blog whose DRAFT.md was edited by hand (to the stand-in Doc's text) before
        it was taken to the desk by `move`: that text is what the desk last wrote."""
        import saved_fixtures

        ident = saved_fixtures.load(self.root, state)
        draft = studio.inside(self.root, 'articles', ident) / 'DRAFT.md'
        draft.write_text(self.desk_text())
        move(ident)
        return ident, draft

    def migrated(self, ident):
        import desk_chat

        shown = desk_chat.migration_preview(self.root, ident)
        self.assertTrue(shown['eligible'], shown['blockers'])
        desk_chat.migrate(self.root, ident, shown['expected'])

    def opened(self, ident):
        import management

        management.dispatch(self.root, 'desk-open', {'id': ident})

    def test_a_hand_edited_draft_taken_to_the_desk_goes_and_a_later_edit_does_not(self):
        for state, move in (('draft-gate', self.migrated), ('finished-page', self.opened)):
            with self.subTest(state=state):
                ident, draft = self.taken_to_the_desk(state, move)
                result = self.open(ident)
                self.assertEqual(
                    result['url'], 'https://docs.google.com/document/d/fixture-doc/edit'
                )
                self.assertEqual(self.drive.imports[-1], (draft.read_bytes(), None))
        for state, move in (
            ('draft-gate-chat', self.migrated),
            ('finished-page-warm', self.opened),
        ):
            with self.subTest(state=state, edited='after'):
                ident, draft = self.taken_to_the_desk(state, move)
                draft.write_text(draft.read_text() + '\nChanged by hand after.\n')
                count = len(self.drive.imports)
                with self.assertRaisesRegex(handoff.Conflict, 'changed outside the desk'):
                    self.open(ident)
                self.assertEqual(len(self.drive.imports), count)

    def test_refusals_and_uncertain_upload_never_import_twice(self):
        unfinished = self.on_desk()
        (studio.inside(self.root, 'articles', unfinished) / 'DRAFT.md').write_text('')
        with self.assertRaisesRegex(ValueError, 'no draft yet'):
            self.open(unfinished)
        ident = self.on_desk()
        with patch.object(gd, 'active_account', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Google is not signed in'):
                self.open(ident)
        self.drive.uncertain = True
        with self.assertRaises(gd.GoogleError):
            self.open(ident)
        with self.assertRaisesRegex(ValueError, 'last upload is being checked'):
            self.open(ident)
        self.assertEqual(len(self.drive.imports), 1)
        self.drive.matches = [{'id': 'fixture-doc', 'mimeType': gd.DOC_MIME}]
        result = self.open(ident)
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        self.assertEqual(len(self.drive.imports), 1)

    def test_failed_readback_keeps_the_created_doc_for_retry(self):
        ident = self.on_desk()
        with patch.object(self.drive, 'native_read', side_effect=gd.GoogleError('Offline')):
            with self.assertRaises(gd.GoogleError):
                self.open(ident)
        self.open(ident)
        self.assertEqual(len(self.drive.imports), 1)

    def test_dispatch_requires_confirmation_and_the_shown_version(self):
        import management

        ident = self.on_desk()
        expected = management.view(self.root, 'desk', {'id': [ident]})['expected']
        route = 'desk-google-open'
        with patch.object(gd, 'Client', return_value=self.drive):
            with self.assertRaisesRegex(ValueError, 'Confirm'):
                management.dispatch(self.root, route, {'id': ident, 'expected': expected})
            with self.assertRaisesRegex(ValueError, 'changed'):
                management.dispatch(
                    self.root, route, {'id': ident, 'expected': 'old', 'confirmed': True}
                )
            result = management.dispatch(
                self.root, route, {'id': ident, 'expected': expected, 'confirmed': True}
            )
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        self.assertEqual(len(self.drive.imports), 1)
        self.assertEqual(management.failure(handoff.Conflict('Not ready'), writing=True)[0], 409)

    def test_mismatched_readback_is_not_linked_or_uploaded_again(self):
        import google_roundtrip

        ident = self.on_desk()

        def different(client, document, tab, snapshot):
            client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0][
                'textRun'
            ]['content'] = 'Different heading.\n'
            return google_roundtrip.capture(client, document, tab, snapshot)

        with self.assertRaisesRegex(ValueError, 'readback does not match'):
            self.open(ident, different)
        _, record = studio.item(self.root, 'articles', ident)
        self.assertIsNone(editorial.doc_link(record))
        pending = handoff.pending_link(record)
        self.assertEqual(pending['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        with self.assertRaisesRegex(ValueError, 'readback does not match'):
            self.open(ident)
        self.assertEqual(len(self.drive.imports), 1)

    def test_changed_local_draft_is_never_sent_or_confirmed(self):
        ident = self.finished()
        directory, _ = studio.item(self.root, 'articles', ident)
        (directory / 'DRAFT.md').write_text('Unapproved replacement.')
        with self.assertRaisesRegex(ValueError, 'Finish the blog first'):
            handoff.open_as_doc(self.root, ident, self.drive)
        self.assertEqual(self.drive.imports, [])


def titled(doc, title):
    """The stand-in Doc with the draft's title as its first heading, as a desk draft has."""
    from google_roundtrip import utf16

    blocks = doc['tabs'][0]['documentTab']['body']['content']
    heading = {'namedStyleType': 'HEADING_1'}
    line = {'textRun': {'content': title + '\n', 'textStyle': {}}}
    blocks.insert(1, {'paragraph': {'paragraphStyle': heading, 'elements': [line]}})
    start = 1
    for block in blocks:
        if 'paragraph' not in block:
            continue
        block['startIndex'] = start
        for element in block['paragraph']['elements']:
            element['startIndex'] = start
            start += utf16(element['textRun']['content'])
            element['endIndex'] = start
        block['endIndex'] = start
    return doc


class DeskHandoffTests(RunnerCase):
    """A blog on the writing desk gets its private Google Doc without a step-by-step run."""

    def setUp(self):
        super().setUp()
        self.drive = Drive()
        titled(self.drive.doc, 'Desk title')
        signed_in = patch.object(gd, 'active_account', return_value='test@example.invalid')
        signed_in.start()
        self.addCleanup(signed_in.stop)
        import management

        self.made = management.dispatch(
            self.root,
            'desk-create',
            {
                'operation': 'e' * 32,
                'title': 'Desk title',
                'manuscript': accepted_markdown(self.drive.doc).decode('utf-8'),
            },
        )
        self.ident = self.made['id']

    def open(self, **data):
        import management

        with patch.object(gd, 'Client', return_value=self.drive):
            return management.dispatch(self.root, 'desk-google-open', {'id': self.ident, **data})

    def test_a_desk_blog_becomes_its_linked_doc_once(self):
        result = handoff.open_as_doc(self.root, self.ident, self.drive, desk=True)
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        directory, record = studio.item(self.root, 'articles', self.ident)
        self.assertEqual(editorial.doc_link(record)['url'], result['url'])
        self.assertEqual(record['google']['transfers'][result['transfer']]['status'], 'confirmed')
        self.assertEqual(self.drive.imports, [((directory / 'DRAFT.md').read_bytes(), None)])
        again = handoff.open_as_doc(self.root, self.ident, self.drive, desk=True)
        self.assertEqual(again['url'], result['url'])
        self.assertEqual(len(self.drive.imports), 1)
        import management

        shown = management.view(self.root, 'desk', {'id': [self.ident]})
        self.assertEqual(shown['google']['url'], result['url'])
        self.assertTrue(shown['google_suggestions'], 'later desk changes go to it as suggestions')

    def test_a_desk_doc_refuses_a_changed_desk_view(self):
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.open(expected=self.made['expected'])
        with self.assertRaisesRegex(handoff.Conflict, 'This blog changed. Reload'):
            self.open(expected='old', confirmed=True)
        self.assertEqual(self.drive.imports, [])
        result = self.open(expected=self.made['expected'], confirmed=True)
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')
        self.assertEqual(result['id'], self.ident)
        self.assertEqual(len(self.drive.imports), 1)

    def test_a_desk_doc_needs_google_signed_in(self):
        with patch.object(gd, 'active_account', return_value=None):
            with self.assertRaisesRegex(handoff.Conflict, '^' + handoff.NOT_SIGNED_IN + '$'):
                self.open(expected=self.made['expected'], confirmed=True)
        self.assertEqual(self.drive.imports, [])

    def test_a_desk_doc_refuses_a_draft_changed_outside_the_desk(self):
        directory, _ = studio.item(self.root, 'articles', self.ident)
        draft = directory / 'DRAFT.md'
        draft.write_text(draft.read_text() + '\nAdded in another editor.\n')
        with self.assertRaisesRegex(handoff.Conflict, '^' + re.escape(handoff.CHANGED_HERE) + '$'):
            self.open(expected=self.made['expected'], confirmed=True)
        self.assertEqual(self.drive.imports, [])
        self.assertNotIn('google', studio.item(self.root, 'articles', self.ident)[1])

    def test_a_desk_record_with_no_written_digest_is_not_refused_for_it(self):
        directory, record = studio.item(self.root, 'articles', self.ident)
        record['artifact_hashes'].pop('draft')
        studio.persist(directory, 'articles', record)
        import desk_jobs

        result = self.open(expected=desk_jobs.expected(self.root, self.ident), confirmed=True)
        self.assertEqual(result['url'], 'https://docs.google.com/document/d/fixture-doc/edit')

    def test_a_desk_doc_needs_a_draft(self):
        directory, _ = studio.item(self.root, 'articles', self.ident)
        (directory / 'DRAFT.md').unlink()
        with self.assertRaisesRegex(handoff.Conflict, 'no draft'):
            handoff.open_as_doc(self.root, self.ident, self.drive, desk=True)
        self.assertEqual(self.drive.imports, [])
