"""Google Slides links are read through a fake Google Drive's PowerPoint export.

No real Google request is made: a fake transport serves a deck built with zipfile and
synthetic Google error bodies, and records every destination it was asked for.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

import re
import threading
from urllib.parse import parse_qs, urlsplit

import marketing_studio  # noqa: F401
from studio_core import google_api, google_reference, pptx_slides, research_sources, source_folders
from studio_core.google_api import Client, GoogleError, Response, SLIDES_MIME
from studio_core.research_sources import Sources
import pptx_fixture
import xlsx_fixture

URL = 'https://docs.google.com/presentation/d/synthetic_deck/edit'
TOKEN = 'synthetic-memory-only-token'


class FakeDrive:
    """Drive metadata and export for one synthetic deck; anything else is refused."""

    def __init__(self, deck, *, version='7'):
        self.deck, self.versions, self.urls = deck, [version], []

    def __call__(self, method, url, headers, payload):
        self.urls.append(url)
        assert method == 'GET' and headers['Authorization'] == 'Bearer ' + TOKEN
        if url.startswith('https://www.googleapis.com/drive/v3/files/synthetic_deck/export?'):
            assert 'mimeType=' + google_api.PPTX_MIME.replace('/', '%2F') in url
            return Response(200, {}, self.deck)
        if url.startswith('https://www.googleapis.com/drive/v3/files/synthetic_deck?'):
            version = self.versions.pop(0) if len(self.versions) > 1 else self.versions[0]
            return Response(200, {}, json.dumps({
                'id': 'synthetic_deck', 'name': 'Synthetic deck', 'mimeType': SLIDES_MIME,
                'version': version, 'modifiedTime': '2026-11-01T00:00:00Z', 'trashed': False,
                'capabilities': {'canDownload': True}}).encode())
        return Response(404, {}, b'{}')

    def client(self):
        return Client('editor@example.invalid', token_provider=lambda _: TOKEN, transport=self)


def capture(drive, **options):
    return google_reference.capture(URL, client=drive.client(), **options)


class DriveExportTests(unittest.TestCase):
    def test_self_paced_review_reads_order_and_alt_text_without_the_notes(self):
        pictured = pptx_fixture.PICTURE.replace('name="Picture"', 'name="Picture" descr="Revision B: 4 errors"')
        hidden = pptx_fixture.shape(40, ['hidden answer']).replace('id="40"', 'id="40" hidden="1"')
        deck = pptx_fixture.deck([{'title': 'Choose a revision', 'raw': [pictured, hidden],
                                   'notes': 'private solution'}, {'title': 'Feedback: choose B'}])
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / 'review.pptx'
            export.write_bytes(deck)
            view = pptx_slides.reader_review(export)
            self.assertLess(view.index('Choose a revision'), view.index('Revision B: 4 errors'))
            self.assertLess(view.index('Revision B: 4 errors'), view.index('Feedback: choose B'))
            self.assertNotIn('private solution', view)
            self.assertNotIn('hidden answer', view)
            export.write_bytes(b'unreadable')
            self.assertIn('unavailable', pptx_slides.reader_review(export))

    def test_slides_link_reads_through_drive_in_presentation_order(self):
        drive = FakeDrive(pptx_fixture.deck(pptx_fixture.SAMPLE))
        found = capture(drive)
        self.assertFalse([u for u in drive.urls if 'slides.googleapis.com' in u])
        self.assertEqual(len(drive.urls), 3)
        self.assertIn('/export?', drive.urls[1])
        text = found['extracted']['text']
        self.assertEqual(text, 'Synthetic opening\nFirst point.\nSecond\npoint.\nOpening speaker context.\n'
                         'Synthetic numbers\nMetric\nCount 12\nOther\nCount 7\n'
                         'Synthetic grouped\nGrouped material.\nMore grouped.\nClosing speaker context.\n')
        self.assertNotIn('Slide image placeholder', text)
        self.assertEqual(found['kind'], 'google-slides')
        self.assertEqual([t['title'] for t in found['tabs']], ['Slide 1', 'Slide 2', 'Slide 3'])
        self.assertEqual(found['selected_tabs'], [t['id'] for t in found['tabs']])
        self.assertEqual(found['extracted']['warnings'], [
            'Images, charts, video and WordArt are not interpreted. Supply their meaningful text or data separately.'])
        labels = [l['label'] for l in found['extracted']['locations']]
        self.assertIn('Slide 1 speaker notes / shape 3', labels)
        self.assertIn('Slide 2 / table 4', labels)
        for location in found['extracted']['locations']:
            self.assertTrue(text[location['start']:location['end']].strip())
        saved = json.loads(found['raw'])
        self.assertEqual(set(saved), {'presentation_id', 'version', 'modified', 'revision', 'tabs'})
        self.assertEqual([s['number'] for s in saved['tabs']], [1, 2, 3])
        self.assertEqual(set(saved['tabs'][0]), {'id', 'number', 'text'})
        self.assertEqual(found['sha256'], hashlib.sha256(found['raw']).hexdigest())

    def test_a_google_shaped_slide_reads_its_runs_and_fallback_only(self):
        found = capture(FakeDrive(pptx_fixture.deck([pptx_fixture.SAMPLE[0], pptx_fixture.GOOGLE])))
        saved = json.loads(found['raw'])['tabs'][1]
        self.assertEqual(saved['text'], 'Google shaped title\nFallback text\nGoogle speaker context.\n')
        self.assertEqual(saved['number'], 2)
        labels = [l['label'] for l in found['extracted']['locations'] if l['label'].startswith('Slide 2')]
        self.assertEqual(labels, ['Slide 2 / shape 54', 'Slide 2 / shape 57', 'Slide 2 speaker notes / shape 3'])
        self.assertNotIn('Choice text', found['extracted']['text'])

    def test_too_many_zip_entries_are_refused_before_listing(self):
        deck = pptx_fixture.deck(pptx_fixture.SAMPLE[:1], extra={'ppt/media/' + str(i): b'' for i in range(30)})
        with mock.patch.object(pptx_slides, 'MOST_ENTRIES', 20), mock.patch.object(zipfile, 'ZipFile') as opened:
            with self.assertRaisesRegex(ValueError, 'could not be read safely'):
                capture(FakeDrive(deck))
        opened.assert_not_called()

    def test_identities_are_stable_and_choices_keep_only_the_chosen_slides(self):
        deck = pptx_fixture.deck(pptx_fixture.SAMPLE)
        first, second = capture(FakeDrive(deck)), capture(FakeDrive(deck))
        self.assertEqual(first['tabs'], second['tabs'])
        chosen = capture(FakeDrive(deck), selected=[first['tabs'][2]['id']])
        self.assertEqual(chosen['selected_tabs'], [first['tabs'][2]['id']])
        self.assertIn('Grouped material.', chosen['extracted']['text'])
        self.assertNotIn(b'Synthetic opening', chosen['raw'])
        self.assertNotIn('Count 12', chosen['extracted']['text'])
        by_number = capture(FakeDrive(deck), selected=['slide-2'])
        self.assertEqual(by_number['selected_tabs'], [first['tabs'][1]['id']])
        with self.assertRaisesRegex(ValueError, 'has 3 slides'):
            capture(FakeDrive(deck), selected=['slide-4'])

    def test_a_moved_or_edited_slide_is_refused_never_swapped(self):
        before = capture(FakeDrive(pptx_fixture.deck(pptx_fixture.SAMPLE)))
        wanted = before['tabs'][0]['id']
        moved = pptx_fixture.deck([pptx_fixture.SAMPLE[1], pptx_fixture.SAMPLE[0], pptx_fixture.SAMPLE[2]])
        edited = pptx_fixture.deck([{**pptx_fixture.SAMPLE[0], 'title': 'Changed opening'}, *pptx_fixture.SAMPLE[1:]])
        for deck in (moved, edited):
            with self.assertRaisesRegex(ValueError, 'changed or moved'):
                capture(FakeDrive(deck), selected=[wanted])

    def test_deck_changed_while_being_read_is_refused(self):
        drive = FakeDrive(pptx_fixture.deck(pptx_fixture.SAMPLE))
        drive.versions = ['7', '8']
        with self.assertRaisesRegex(ValueError, 'changed while being read'):
            capture(drive)
        self.assertIn('/export?', drive.urls[1])

    def test_old_slides_api_identities_map_only_on_the_same_unchanged_deck(self):
        deck = pptx_fixture.deck(pptx_fixture.SAMPLE)
        previous = {'version': '7', 'slides': ['p', 'g2abc_0_5', 'g2abc_0_9']}
        mapped = capture(FakeDrive(deck), selected=['g2abc_0_9', 'p'], previous=previous)
        self.assertEqual([s['number'] for s in json.loads(mapped['raw'])['tabs']], [1, 3])
        self.assertNotIn('Count 12', mapped['extracted']['text'])
        for changed in ({**previous, 'version': '6'}, {**previous, 'slides': previous['slides'][:2] + ['x', 'y']},
                        None):
            with self.assertRaisesRegex(ValueError, "earlier slide identities"):
                capture(FakeDrive(deck), selected=['g2abc_0_9'], previous=changed)

    def test_no_slides_too_many_slides_and_unsafe_exports_are_refused(self):
        with self.assertRaisesRegex(ValueError, '1–200'):
            capture(FakeDrive(pptx_fixture.deck([])))
        with self.assertRaisesRegex(ValueError, '1–200'):
            capture(FakeDrive(pptx_fixture.deck([{'title': 'x'}] * 201)))
        dtd = ('<?xml version="1.0"?><!DOCTYPE p [<!ENTITY big "aaaaaaaa">]><p:sld '
               + pptx_fixture.NS + '><p:cSld><p:spTree/></p:cSld></p:sld>')
        entity = ('<?xml version="1.0"?><!DOCTYPE p SYSTEM "file:///etc/passwd"><p:sld '
                  + pptx_fixture.NS + '/>')
        escaping = pptx_fixture.deck(pptx_fixture.SAMPLE[:1], replace={
            'ppt/_rels/presentation.xml.rels': '<?xml version="1.0"?><Relationships ' + pptx_fixture.RELS
            + '><Relationship Id="rIdS1" Type="' + pptx_fixture.REL + 'slide" Target="../../slide1.xml"/></Relationships>'},
            extra={'slide1.xml': pptx_fixture.slide_xml(pptx_fixture.SAMPLE[0])})
        unsafe = [b'not a zip', b'PK\x03\x04' + b'\0' * 40,
                  pptx_fixture.deck(pptx_fixture.SAMPLE, missing=['ppt/slides/slide2.xml']),
                  pptx_fixture.deck(pptx_fixture.SAMPLE, missing=['ppt/presentation.xml']),
                  pptx_fixture.deck(pptx_fixture.SAMPLE[:1], replace={'ppt/slides/slide1.xml': dtd}),
                  pptx_fixture.deck(pptx_fixture.SAMPLE[:1], replace={'ppt/slides/slide1.xml': entity}),
                  pptx_fixture.deck(pptx_fixture.SAMPLE[:1], replace={'ppt/slides/slide1.xml': '<p:sld'}), escaping]
        for data in unsafe:
            with self.subTest(data=data[:20]), self.assertRaisesRegex(ValueError, 'could not be read safely'):
                capture(FakeDrive(data))

    def test_parts_are_size_capped_while_decompressed(self):
        bomb = pptx_fixture.deck(pptx_fixture.SAMPLE[:1], replace={
            'ppt/slides/slide1.xml': '<p:sld ' + pptx_fixture.NS + '>' + ' ' * 50_000 + '</p:sld>'})
        with mock.patch.object(pptx_slides, 'PART_LIMIT', 10_000):
            with self.assertRaisesRegex(ValueError, 'could not be read safely'):
                capture(FakeDrive(bomb))
        with mock.patch.object(google_api, 'LIMIT', 1_000):
            with self.assertRaisesRegex(GoogleError, 'transfer limit'):
                capture(FakeDrive(pptx_fixture.deck(pptx_fixture.SAMPLE)))

    def test_slides_api_is_not_an_allowed_destination(self):
        token = mock.Mock(return_value=TOKEN)
        client = Client('editor@example.invalid', token_provider=token, transport=mock.Mock())
        with self.assertRaises(GoogleError):
            client.request('https://slides.googleapis.com/v1/presentations/synthetic_deck')
        token.assert_not_called()


def error(status=None, reason=None, detail=None, service=None, message='synthetic'):
    value = {'code': 403, 'message': message}
    if status: value['status'] = status
    if reason: value['errors'] = [{'reason': reason, 'domain': 'global', 'message': TOKEN}]
    if detail:
        value['details'] = [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': detail,
                             **({'metadata': {'service': service, 'consumer': 'projects/123'}} if service else {})}]
    return json.dumps({'error': value}).encode()


class RefusalTests(unittest.TestCase):
    CASES = {
        'disabled': (error('PERMISSION_DENIED', detail='SERVICE_DISABLED', service='slides.googleapis.com'),
                     "Google has not enabled the Google Slides API for the sign-in's project, so it refused this request. "
                     'Reads through Google Drive are unaffected. Upload a copy instead.'),
        'quota': (error('PERMISSION_DENIED', message='The docs.googleapis.com API requires a quota project, which is not set by default.'),
                  "Google has not enabled this Google service for the sign-in's project, so it refused this request. "
                  'Reads through Google Drive are unaffected. Upload a copy instead.'),
        'scope': (error('PERMISSION_DENIED', detail='ACCESS_TOKEN_SCOPE_INSUFFICIENT'),
                  'This Google sign-in was not given the access this needs. Sign in again with Drive access by running '
                  '`gcloud auth login editor@example.invalid --enable-gdrive-access --force --no-activate` in a terminal, then try again.'),
        'insufficient': (error(reason='insufficientPermissions'), None),
        'forbidden': (error(reason='forbidden'),
                      'This Google account cannot open this file. Ask its owner to share it with this account, or upload a copy instead.'),
        'denied': (error('PERMISSION_DENIED'), None),
        'export size': (error(reason='exportSizeLimitExceeded'),
                        'This file is larger than Google Drive can export (10 MB). Download it as a PDF and upload that copy instead.'),
        'unknown': (error(reason='somethingNew'),
                    'The selected Google account lacks access, download permission or the required API scope.'),
        'unknown denied': (error('PERMISSION_DENIED', reason='somethingNew'),
                           'The selected Google account lacks access, download permission or the required API scope.'),
        'domain policy': (error('PERMISSION_DENIED', reason='domainPolicy'),
                          'The selected Google account lacks access, download permission or the required API scope.'),
        'user project': (error('PERMISSION_DENIED', detail='USER_PROJECT_DENIED'),
                         'The selected Google account lacks access, download permission or the required API scope.'),
        'unreadable': (b'<html>' + TOKEN.encode() + b'</html>',
                       'The selected Google account lacks access, download permission or the required API scope.'),
    }

    def refused(self, body, *, through_http_error=False, method='GET'):
        if through_http_error:
            client = Client('editor@example.invalid', token_provider=lambda _: TOKEN)
            failure = urllib.error.HTTPError('https://www.googleapis.com/drive/v3/files/x', 403, 'Forbidden', {}, io.BytesIO(body))
            client.opener = mock.Mock(open=mock.Mock(side_effect=failure))
        else:
            client = Client('editor@example.invalid', token_provider=lambda _: TOKEN,
                            transport=lambda *args: Response(403, {}, body))
        with self.assertRaises(GoogleError) as caught:
            client.request('https://www.googleapis.com/drive/v3/files/x', method=method, body={} if method != 'GET' else None)
        return caught.exception

    def test_each_reason_has_its_own_sentence_without_token_or_raw_body(self):
        expected = dict(self.CASES)
        expected['insufficient'] = (expected['insufficient'][0], expected['scope'][1])
        expected['denied'] = (expected['denied'][0], expected['forbidden'][1])
        for name, (body, message) in expected.items():
            for through in (False, True):
                with self.subTest(name=name, through_http_error=through):
                    failure = self.refused(body, through_http_error=through)
                    self.assertEqual(str(failure), message)
                    self.assertEqual(failure.status, 403)
                    self.assertFalse(failure.uncertain)
                    self.assertNotIn(TOKEN, str(failure))
                    self.assertNotIn('synthetic', str(failure))

    def test_named_drive_service_does_not_claim_drive_reads_are_unaffected(self):
        failure = self.refused(error(detail='SERVICE_DISABLED', service='drive.googleapis.com'))
        self.assertEqual(str(failure), "Google has not enabled the Google Drive API for the sign-in's project, so it refused this request.")

    def test_a_refused_write_is_not_uncertain_and_other_statuses_keep_their_sentences(self):
        self.assertFalse(self.refused(error(reason='forbidden'), method='POST').uncertain)
        client = Client('editor@example.invalid', token_provider=lambda _: TOKEN,
                        transport=lambda *args: Response(503, {}, error(reason='forbidden')))
        with self.assertRaises(GoogleError) as caught:
            client.request('https://www.googleapis.com/drive/v3/files', method='POST', body={})
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(str(caught.exception), 'Google refused this transfer. Existing local work and deliveries are kept.')


def old_source(sources, value, *, version='7'):
    """A deck source saved before decks were read through Google Drive."""
    snapshot = {'presentation_id': 'synthetic_deck', 'version': version, 'modified': '2026-10-29T00:00:00Z',
                'revision': 'synthetic-revision', 'tabs': [
                    {'id': 'p', 'number': 1, 'text': 'Synthetic opening\n'},
                    {'id': 'g2abc_0_9', 'number': 3, 'text': 'Synthetic grouped\n'}]}
    raw = json.dumps(snapshot, sort_keys=True).encode()
    text = 'Synthetic opening\nSynthetic grouped\n'
    folder = sources.folder(value['id'])
    raw_name = 'captures/' + hashlib.sha256(raw).hexdigest() + '.raw'
    text_name = 'captures/' + hashlib.sha256(text.encode()).hexdigest() + '.txt'
    (folder / 'captures').mkdir(exist_ok=True)
    (folder / raw_name).write_bytes(raw)
    (folder / text_name).write_text(text)
    draft = sources.load(value['id'])
    draft['sources'].append({
        'id': 'a' * 32, 'name': 'Synthetic deck', 'kind': 'google-slides', 'origin': URL, 'requested_url': URL,
        'status': 'ready', 'warnings': [], 'problem': None, 'captured_at': '2026-10-29T00:00:00+00:00',
        'tabs': [{'id': 'p', 'title': 'Slide 1'}, {'id': 'g2abc_0_5', 'title': 'Slide 2'}, {'id': 'g2abc_0_9', 'title': 'Slide 3'}],
        'selected_tabs': ['p', 'g2abc_0_9'], 'original': raw_name, 'file': text_name,
        'original_sha256': hashlib.sha256(raw).hexdigest(), 'sha256': hashlib.sha256(text.encode()).hexdigest()})
    sources.save(draft)
    return sources.read(value['id'])


class SavedSourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.drive = FakeDrive(pptx_fixture.deck(pptx_fixture.SAMPLE))
        self.sources = Sources(Path(temp.name), google=lambda url, **options: google_reference.capture(
            url, client=self.drive.client(), **options))
        self.value = old_source(self.sources, self.sources.create())

    def act(self, operation, **data):
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], operation, **data)
        return self.value

    def test_a_source_saved_in_the_old_format_still_opens_without_a_read(self):
        shown = self.value['sources'][0]
        self.assertEqual(shown['selected_tabs'], ['p', 'g2abc_0_9'])
        preview = self.sources.preview(self.value['id'], shown['id'])
        self.assertEqual(preview['text'], 'Synthetic opening\nSynthetic grouped\n')
        prepared = self.sources.prepared(self.value['id'], self.value['revision'])
        self.assertEqual(prepared['sources'][0]['text'], 'Synthetic opening\nSynthetic grouped\n')
        self.assertEqual(self.drive.urls, [])

    def test_an_old_choice_on_the_unchanged_deck_maps_by_position(self):
        self.act('tabs', source='a' * 32, selected=['p', 'g2abc_0_5', 'g2abc_0_9'])
        source = self.value['sources'][0]
        self.assertEqual(source['selected_tabs'], [t['id'] for t in source['tabs']])
        self.assertTrue(all(t['id'].startswith('slide-') for t in source['tabs']))
        self.act('tabs', source='a' * 32, selected=[source['tabs'][1]['id']])
        self.assertEqual(self.sources.preview(self.value['id'], 'a' * 32)['text'],
                         'Synthetic numbers\nMetric\nCount 12\nOther\nCount 7\n')
        self.assertFalse([u for u in self.drive.urls if 'slides.googleapis.com' in u])

    def test_an_old_choice_on_a_changed_deck_is_refused_and_the_old_capture_kept(self):
        self.drive.versions = ['9']
        revision = self.value['revision']
        with self.assertRaisesRegex(ValueError, "earlier slide identities.*Remove this source and add its link again.*earlier capture is kept"):
            self.act('tabs', source='a' * 32, selected=['p'])
        kept = self.sources.read(self.value['id'])
        self.assertEqual(kept['revision'], revision)
        self.assertEqual(kept['sources'][0]['status'], 'ready')
        self.assertEqual(self.sources.preview(kept['id'], 'a' * 32)['text'], 'Synthetic opening\nSynthetic grouped\n')

    def test_reading_again_reads_all_slides_with_new_identities(self):
        self.act('capture', kind='url', url=URL)
        added = self.value['sources'][-1]
        self.assertEqual(added['kind'], 'google-slides')
        self.assertEqual(len(added['selected_tabs']), 3)


if __name__ == '__main__':
    unittest.main()


ROOT = 'synthetic_root_folder_0001'
FOLDER, SHORTCUT = google_api.FOLDER_MIME, google_api.SHORTCUT_MIME


def child(ident, name, mime, **more):
    return {'id': ident, 'name': name, 'mimeType': mime, **more}


def shortcut(ident, name, target, mime):
    return child(ident, name, SHORTCUT, shortcutDetails={'targetId': target, 'targetMimeType': mime})


class FakeFolderDrive:
    """A synthetic Google Drive tree behind the real client: listing pages, metadata, the
    Google Docs API, exports and downloads. Every destination asked for is recorded."""

    def __init__(self, tree, *, page=3):
        self.tree, self.page, self.urls, self.denied = tree, page, [], set()
        self.docs, self.decks, self.sheets, self.media, self.links = {}, {}, {}, {}, {}
        # How many documents are being read at once: `together` readers are held until that
        # many are in a request at the same moment, and `slow` holds one file's bytes back
        # until another's were asked for. Events, never timing.
        self.watch, self.active, self.peak, self.together = threading.Lock(), 0, 0, 0
        self.met, self.slow, self.seen, self.tokens = threading.Event(), {}, {}, 0
        self.names = {item['id']: item for items in tree.values() for item in items}

    def meta(self, ident):
        if ident in self.tree:
            return {'id': ident, 'name': 'Field kit', 'mimeType': FOLDER, 'trashed': False}
        if ident in self.links:
            return {'id': ident, 'name': 'Shortcut to the kit', 'mimeType': SHORTCUT, 'trashed': False,
                    'shortcutDetails': {'targetId': self.links[ident][0], 'targetMimeType': self.links[ident][1]}}
        mime = (google_api.DOC_MIME if ident in self.docs else SLIDES_MIME if ident in self.decks
                else google_api.SHEET_MIME if ident in self.sheets else 'text/plain')
        return {'id': ident, 'name': 'Its own name', 'mimeType': mime, 'version': '3',
                'modifiedTime': '2026-11-01T00:00:00Z', 'trashed': False,
                'capabilities': {'canDownload': True}, 'size': str(len(self.media.get(ident, b'')))}

    def __call__(self, method, url, headers, payload):
        parts = urlsplit(url)
        ident = re.sub(r'/export$', '', parts.path).rsplit('/', 1)[-1]
        reading = parts.path != '/drive/v3/files' and ident not in self.tree and ident not in self.links
        if not reading:
            return self.answer(method, url, headers, payload)
        with self.watch:
            self.active += 1
            self.peak = max(self.peak, self.active)
            if self.active >= self.together:
                self.met.set()
            self.seen.setdefault(ident, threading.Event()).set()
            held = self.seen.setdefault(self.slow[ident], threading.Event()) if ident in self.slow else None
        try:
            assert self.met.wait(5), 'documents were not read at the same time'
            assert held is None or held.wait(5), 'a later document was not read while this one was slow'
            return self.answer(method, url, headers, payload)
        finally:
            with self.watch:
                self.active -= 1

    def answer(self, method, url, headers, payload):
        self.urls.append(url)
        assert method == 'GET' and payload is None and headers['Authorization'] == 'Bearer ' + TOKEN
        parts = urlsplit(url)
        asked = parse_qs(parts.query)
        if parts.netloc == 'docs.googleapis.com':
            ident = parts.path.rsplit('/', 1)[-1]
            return Response(200, {}, json.dumps({'documentId': ident, 'body': {'content': [
                {'paragraph': {'elements': [{'textRun': {'content': self.docs[ident]}}]}}]}}).encode())
        assert parts.netloc == 'www.googleapis.com'
        if parts.path == '/drive/v3/files':
            folder = re.fullmatch(r"'([A-Za-z0-9_-]+)' in parents and trashed = false", asked['q'][0]).group(1)
            assert asked['supportsAllDrives'] == ['true'] and asked['includeItemsFromAllDrives'] == ['true']
            assert 'shortcutDetails(targetId,targetMimeType)' in asked['fields'][0]
            if folder in self.denied:
                return Response(403, {}, json.dumps({'error': {'status': 'PERMISSION_DENIED'}}).encode())
            start = int(asked.get('pageToken', ['0'])[0])
            items = self.tree[folder]
            body = {'files': items[start:start + self.page]}
            if start + self.page < len(items):
                body['nextPageToken'] = str(start + self.page)
            return Response(200, {}, json.dumps(body).encode())
        ident, export = re.fullmatch(r'/drive/v3/files/([A-Za-z0-9_-]+)(/export)?', parts.path).groups()
        if ident in self.denied:
            return Response(404, {}, b'{}')
        if export:
            assert asked['mimeType'] in ([google_api.XLSX_MIME], [google_api.PPTX_MIME])
            return Response(200, {}, self.sheets[ident] if asked['mimeType'] == [google_api.XLSX_MIME] else self.decks[ident])
        if asked.get('alt') == ['media']:
            return Response(200, {}, self.media[ident])
        return Response(200, {}, json.dumps(self.meta(ident)).encode())

    def token(self, account):
        with self.watch:
            self.tokens += 1
        return TOKEN

    def client(self):
        return Client('editor@example.invalid', token_provider=self.token, transport=self)

    def asked(self, part):
        return [url for url in self.urls if part in url]


def field_kit():
    """Nested folders, more than one page, shortcuts to a file and to a folder, a loop, a
    sheet, unsupported types, an oversized file, a repeat, a locked folder and a locked file."""
    drive = FakeFolderDrive({
        ROOT: [child('doc_plan', 'Plan', google_api.DOC_MIME), child('deck_main', 'Deck', SLIDES_MIME),
               child('sheet_one', 'Numbers', google_api.SHEET_MIME), child('file_notes', 'notes.md', 'text/markdown', size='22'),
               child('file_deck', 'slides.pptx', google_api.PPTX_MIME, size='2000'),
               child('file_photo', 'photo.png', 'image/png', size='10'),
               child('form_one', 'Survey', 'application/vnd.google-apps.form'),
               child('file_huge', 'huge.txt', 'text/plain', size=str(research_sources.LIMIT + 1)),
               child('doc_private', 'Private doc', google_api.DOC_MIME),
               child('folder_compete', 'Compete', FOLDER), child('folder_locked', 'Locked', FOLDER)],
        'folder_compete': [child('folder_cards', 'Battlecards', FOLDER),
                           shortcut('short_plan', 'Plan again', 'doc_plan', google_api.DOC_MIME),
                           shortcut('short_note', 'Linked notes', 'file_linked', 'text/plain'),
                           shortcut('short_shared', 'Shared', 'folder_shared', FOLDER),
                           shortcut('short_broken', 'Gone', None, None)],
        'folder_cards': [child('doc_card', 'EDB battle/card', google_api.DOC_MIME),
                         shortcut('short_top', 'Back to top', ROOT, FOLDER)],
        'folder_shared': [child('file_inside', 'Inside shared.md', 'text/markdown', size='20')],
        'folder_locked': [child('doc_never', 'Never listed', google_api.DOC_MIME)],
    })
    drive.docs = {'doc_plan': 'Synthetic plan text.', 'doc_card': 'Synthetic battlecard text.',
                  'doc_private': 'PRIVATE', 'doc_never': 'NEVER'}
    drive.decks = {'deck_main': pptx_fixture.deck(pptx_fixture.SAMPLE)}
    drive.sheets = {'sheet_one': xlsx_fixture.workbook(xlsx_fixture.SAMPLE)}
    drive.media = {'file_notes': b'Synthetic notes file.', 'file_linked': b'Synthetic linked notes.',
                   'file_inside': b'Synthetic shared notes.', 'file_huge': b'NEVER DOWNLOADED',
                   'file_deck': pptx_fixture.deck(pptx_fixture.SAMPLE[:1])}
    drive.denied = {'folder_locked', 'doc_private'}
    return drive


class DriveFolderTests(unittest.TestCase):
    """Add a folder, for a Google Drive folder, through a fake transport only."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.drive = field_kit()
        self.accounts = []
        # Every Google read, a single link's included, goes to the fake transport.
        self.sources = Sources(Path(temp.name).resolve() / 'store', account=lambda: 'editor@example.invalid',
                               drive=lambda account: self.accounts.append(account) or self.drive.client(),
                               google=lambda url, **options: google_reference.capture(
                                   url, **{**options, 'client': options.get('client') or self.drive.client()}))
        self.value = self.sources.create()

    def add(self, location='https://drive.google.com/drive/u/0/folders/' + ROOT + '?lfhs=2'):
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], 'folder', location=location)
        return self.value.pop('folder')

    def test_a_drive_folder_is_listed_through_and_each_document_is_an_ordinary_source(self):
        report = self.add()
        self.assertEqual(self.accounts, ['editor@example.invalid'])
        added = {s['name']: s for s in self.value['sources']}
        self.assertEqual({name: s['kind'] for name, s in added.items()}, {
            'Deck': 'google-slides', 'notes.md': 'file', 'Numbers.xlsx': 'file', 'Plan': 'google-doc', 'slides.pptx': 'file',
            'Compete/Linked notes.txt': 'file', 'Compete/Battlecards/EDB battle-card': 'google-doc',
            'Compete/Shared/Inside shared.md': 'file'})
        self.assertTrue(all(s['status'] == 'ready' and re.fullmatch('[a-f0-9]{32}', s['id']) for s in added.values()))
        # Each keeps its Google identity where every source keeps its origin.
        self.assertEqual(added['Plan']['origin'], 'https://docs.google.com/document/d/doc_plan/edit')
        self.assertEqual(added['Deck']['origin'], 'https://docs.google.com/presentation/d/deck_main/edit')
        self.assertEqual(added['Numbers.xlsx']['origin'], 'https://docs.google.com/spreadsheets/d/sheet_one/edit')
        self.assertEqual(added['Compete/Linked notes.txt']['origin'], 'https://drive.google.com/file/d/file_linked/view')
        self.assertEqual(added['Numbers.xlsx']['warnings'], [], 'every sheet was read, so nothing is said to be missing')
        text = lambda name: self.sources.preview(self.value['id'], added[name]['id'])['text']
        self.assertEqual(text('Plan'), 'Synthetic plan text.\n')
        self.assertEqual(text('Numbers.xlsx'), xlsx_fixture.SAMPLE_TEXT)
        self.assertTrue(self.drive.asked('/files/sheet_one/export?mimeType=application%2Fvnd.openxmlformats-officedocument.spreadsheetml.sheet'))
        self.assertIn('Closing speaker context.', text('Deck'))
        self.assertIn('Opening speaker context.', text('slides.pptx'))
        self.assertEqual(text('Compete/Shared/Inside shared.md'), 'Synthetic shared notes.\n')
        self.assertEqual(len(added['Deck']['tabs']), 3)
        self.assertEqual((report['where'], report['title'], report['added'], report['found']), ('drive', 'Field kit', 8, 9))
        self.assertEqual({row['name']: row['code'] for row in report['skipped']}, {
            'huge.txt': 'too-large', 'photo.png': 'unsupported', 'Survey': 'unsupported', 'Private doc': 'no-permission',
            'Compete/Gone': 'unreadable', 'Compete/Plan again': 'repeat', 'Compete/Battlecards/Back to top/': 'repeat',
            'Locked/': 'no-permission'})
        said = {row['name']: row['reason'] for row in report['skipped']}
        self.assertEqual(said['huge.txt'], 'Larger than 8 MB.')
        self.assertEqual(said['Survey'], 'Not a type that can be read. Among Google files, only Google Docs, Google Slides and Google Sheets are read.')
        self.assertEqual(said['Compete/Battlecards/Back to top/'], 'Appears more than once in this folder. It leads back to a folder already scanned.')
        self.assertTrue(said['Locked/'].startswith('No permission to read it. This Google account cannot open this file.'))
        self.assertTrue(said['Private doc'].startswith('No permission to read it. '))
        everything = json.dumps([self.value, report]) + ''.join(text(name) for name in added)
        self.assertNotIn('PRIVATE', everything)
        self.assertNotIn('NEVER', everything)
        # Listing followed every page, and nothing oversized, unsupported or locked was downloaded.
        self.assertTrue(self.drive.asked('pageToken=3'))
        self.assertEqual(len([u for u in self.drive.asked('/drive/v3/files?') if 'synthetic_root_folder_0001' in u]), 4)
        for never in ('file_huge', 'file_photo', 'form_one', 'doc_never'):
            self.assertFalse(self.drive.asked('/' + never), never)
        self.assertEqual(len(self.drive.asked('/documents/doc_plan')), 1, 'a shortcut to a file already found reads nothing twice')
        self.assertEqual(len(self.drive.asked('/files/file_linked?')), 2, 'a shortcut target is sized, then downloaded')
        for url in self.drive.urls:
            google_api.fixed_url(url)
            self.assertIn(urlsplit(url).netloc, ('www.googleapis.com', 'docs.googleapis.com'))
            self.assertFalse('slides.googleapis.com' in url or 'sheets.googleapis.com' in url)

    def test_what_is_already_here_is_not_added_or_read_again(self):
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], 'capture', kind='url',
                                         url='https://docs.google.com/document/d/doc_plan/edit')
        self.assertEqual(self.value['sources'][0]['name'], 'Its own name')
        self.drive.urls.clear()
        first = self.add()
        self.assertEqual(first['added'], 7)
        self.assertIn({'name': 'Plan', 'code': 'duplicate', 'reason': 'Already a source here.'}, first['skipped'])
        self.assertFalse(self.drive.asked('/documents/doc_plan'))
        self.drive.urls.clear()
        again = self.add(ROOT)        # the bare folder identity is the same folder
        self.assertEqual(again['added'], 0)
        self.assertEqual(again['reasons']['duplicate'], 8)
        self.assertEqual(len(self.value['sources']), 8)
        self.assertFalse(self.drive.asked('/documents/') or self.drive.asked('/export') or self.drive.asked('alt=media'),
                         'a document known by its Google identity is skipped before anything is fetched')

    def test_the_same_bytes_under_another_identity_are_a_duplicate(self):
        self.drive.media['file_inside'] = self.drive.media['file_notes']
        report = self.add()
        self.assertIn({'name': 'Compete/Shared/Inside shared.md', 'code': 'duplicate',
                       'reason': 'Already a source here. It has the same content as “notes.md”.'}, report['skipped'])
        self.assertEqual(report['added'], 7)

    def test_one_add_takes_its_limit_and_names_the_rest(self):
        with mock.patch.object(source_folders, 'FOLDER_MOST', 3):
            first = self.add()
            self.assertEqual(first['added'], 3)
            self.assertEqual([s['name'] for s in self.value['sources']], ['Deck', 'notes.md', 'Numbers.xlsx'])
            self.assertEqual((first['again'], first['next']), (True, 'Add the same folder again to read the next ones.'))
            over = [row['name'] for row in first['skipped'] if row['code'] == 'over-limit']
            self.assertEqual(over, ['Plan', 'Private doc', 'slides.pptx', 'Compete/Linked notes.txt',
                                    'Compete/Battlecards/EDB battle-card', 'Compete/Shared/Inside shared.md'])
            second = self.add()
            self.assertEqual(second['added'], 3)
        self.assertEqual(len(self.value['sources']), 6)

    def test_looking_stops_at_its_limit_and_depth_is_bounded(self):
        scan = source_folders.drive(self.drive.client(), ROOT, research_sources.TYPES, research_sources.LIMIT, looked=4)
        self.assertTrue(scan['stopped'])
        self.assertEqual(scan['looked'], 4)
        self.assertEqual(len(self.drive.asked('/drive/v3/files?')), 2, 'listing stops once the limit is in sight')
        shallow = source_folders.drive(self.drive.client(), ROOT, research_sources.TYPES, research_sources.LIMIT, depth=1)
        self.assertIn({'name': 'Compete/Battlecards/', 'code': 'too-deep', 'reason': 'More than 6 folders deep.'}, shallow['skipped'])
        self.assertIn({'name': 'Compete/Shared/', 'code': 'too-deep', 'reason': 'More than 6 folders deep.'}, shallow['skipped'])
        self.assertNotIn('Compete/Battlecards/EDB battle-card', [item['name'] for item in shallow['found']])

    def test_a_link_that_is_not_an_open_folder_is_refused_whole(self):
        before = self.value['revision']
        self.drive.denied.add(ROOT)
        with self.assertRaisesRegex(ValueError, 'No Google Drive folder with this link or identity is open to this account'):
            self.add()
        with self.assertRaisesRegex(ValueError, 'This is not a Google Drive folder this account can open'):
            self.add('https://drive.google.com/drive/folders/doc_plan_0001')
        self.drive.denied = {'folder_compete'}
        self.drive.tree[ROOT] = [child('folder_compete', 'Compete', FOLDER)]
        report = self.add()
        self.assertEqual((report['added'], [row['code'] for row in report['skipped']]), (0, ['no-permission']))
        self.assertEqual(self.sources.read(self.value['id'])['revision'], before)

    def test_documents_are_read_several_at_a_time_and_no_more_than_the_limit(self):
        self.assertEqual((source_folders.FOLDER_WORKERS, source_folders.FOLDER_AHEAD), (8, 16))
        self.drive.together = 3      # readers are held until three are reading at once
        with mock.patch.object(source_folders, 'FOLDER_WORKERS', 3):
            report = self.add()
        self.assertEqual(report['added'], 8)
        self.assertEqual(self.drive.peak, 3, 'three at once, and never a fourth')
        self.assertEqual(self.drive.tokens, 1, 'one sign-in token is shared by every reader')
        again = field_kit()
        again.together = 2
        self.drive = again
        self.value = self.sources.create()
        self.add()
        self.assertGreater(again.peak, 1)
        self.assertLessEqual(again.peak, source_folders.FOLDER_WORKERS)

    def one_at_a_time(self):
        """What reading the same folder one document after another adds and skips."""
        drive = field_kit()
        drive.media['file_inside'] = drive.media['file_notes']
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        alone = Sources(Path(temp.name).resolve() / 'store', account=lambda: 'editor@example.invalid',
                        drive=lambda account: drive.client(),
                        google=lambda url, **options: google_reference.capture(url, **{**options, 'client': options.get('client') or drive.client()}))
        value = alone.create()
        with mock.patch.object(source_folders, 'FOLDER_WORKERS', 1):
            value = alone.mutate(value['id'], value['revision'], 'folder', location=ROOT)
        self.assertEqual(drive.peak, 1)
        return [(s['name'], s['kind'], s['sha256']) for s in value['sources']], value['folder']

    def test_order_and_the_kept_one_of_two_alike_are_what_reading_in_turn_gives(self):
        expected, said = self.one_at_a_time()
        # The first document in order and the first of two alike are the slowest: each is
        # answered only after the last document in order was asked for.
        self.drive.media['file_inside'] = self.drive.media['file_notes']
        self.drive.slow = {'deck_main': 'file_inside', 'file_notes': 'file_inside'}
        self.drive.together = 2
        report = self.add()
        self.assertGreater(self.drive.peak, 1)
        self.assertEqual([(s['name'], s['kind'], s['sha256']) for s in self.value['sources']], expected)
        self.assertEqual([s['name'] for s in self.value['sources']][:3], ['Deck', 'notes.md', 'Numbers.xlsx'])
        self.assertEqual(report, said)
        self.assertIn({'name': 'Compete/Shared/Inside shared.md', 'code': 'duplicate',
                       'reason': 'Already a source here. It has the same content as “notes.md”.'}, report['skipped'])
        self.assertEqual((report['again'], report['next']), (False, None))

    def test_documents_not_started_in_time_are_named_and_never_fetched(self):
        calls = []
        self.sources.clock = lambda: calls.append(1) or (0 if len(calls) <= 3 else 10_000)
        self.drive.together = 2
        report = self.add()
        self.assertEqual([s['name'] for s in self.value['sources']], ['Deck', 'notes.md'])
        late = [row['name'] for row in report['skipped'] if row['code'] == 'out-of-time']
        self.assertEqual(late, ['Numbers.xlsx', 'Plan', 'Private doc', 'slides.pptx', 'Compete/Linked notes.txt',
                                'Compete/Battlecards/EDB battle-card', 'Compete/Shared/Inside shared.md'])
        self.assertEqual(report['skipped'][-1]['reason'], 'Not read in time. Add the folder again to read the rest.')
        self.assertEqual((report['again'], report['next']), (True, 'Add the same folder again to read the next ones.'))
        for never in ('doc_plan', 'sheet_one', 'file_deck', 'doc_card', 'file_inside', 'doc_private'):
            self.assertFalse(self.drive.asked('/' + never), never)
        self.sources.clock = lambda: 0
        rest = self.add()
        self.assertEqual((rest['added'], rest['again'], len(self.value['sources'])), (6, False, 8))

    def test_a_link_to_a_shortcut_scans_the_folder_it_points_to(self):
        self.drive.links = {'shortcut_to_root_0001': (ROOT, FOLDER), 'shortcut_to_doc_00001': ('doc_plan', google_api.DOC_MIME),
                            'shortcut_to_gone_0001': ('folder_gone', FOLDER)}
        report = self.add('https://drive.google.com/drive/folders/shortcut_to_root_0001')
        self.assertEqual((report['title'], report['added']), ('Field kit', 8))
        self.assertTrue(self.drive.asked('q=%27' + ROOT + '%27'), 'the folder pointed to is the one listed')
        self.assertFalse(self.drive.asked('q=%27shortcut_to_root_0001%27'))
        with self.assertRaisesRegex(ValueError, 'This is not a Google Drive folder this account can open'):
            self.add('https://drive.google.com/drive/folders/shortcut_to_doc_00001')
        self.drive.denied.add('folder_gone')
        with self.assertRaisesRegex(ValueError, 'No Google Drive folder with this link or identity is open'):
            self.add('https://drive.google.com/drive/folders/shortcut_to_gone_0001')

    def test_a_caller_with_less_room_says_so_in_its_own_words(self):
        draft = self.sources.create()
        answer = self.sources.add_folder(draft['id'], draft['revision'], {'location': ROOT}, most=2,
                                         full='A training takes 2 documents here.')
        self.assertEqual(answer['folder']['added'], 2)
        over = [row for row in answer['folder']['skipped'] if row['code'] == 'over-limit']
        self.assertEqual(len(over), 7)
        self.assertEqual(over[0]['reason'], 'Over the limit. A training takes 2 documents here.')

    def test_choosing_tabs_keeps_the_name_that_says_where_a_document_was_found(self):
        self.add()
        card = next(s for s in self.value['sources'] if s['name'] == 'Compete/Battlecards/EDB battle-card')
        self.value = self.sources.mutate(self.value['id'], self.value['revision'], 'tabs', source=card['id'], selected=['body'])
        kept = next(s for s in self.value['sources'] if s['id'] == card['id'])
        self.assertEqual(kept['name'], 'Compete/Battlecards/EDB battle-card')
        self.assertEqual(kept['origin'], 'https://docs.google.com/document/d/doc_card/edit?tab=body')

    def test_the_folder_listing_asks_only_for_the_folder_named(self):
        self.drive.client().children(ROOT)
        asked = parse_qs(urlsplit(self.drive.urls[-1]).query)
        self.assertEqual(asked['q'], ["'" + ROOT + "' in parents and trashed = false"])
        for unsafe in ("x' or name contains '", '../x', ''):
            with self.assertRaises(GoogleError):
                self.drive.client().children(unsafe)
        with self.assertRaises(GoogleError):
            self.drive.client().children(ROOT, page_token='')
