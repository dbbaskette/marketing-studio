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

import marketing_studio  # noqa: F401
from studio_core import google_api, google_reference, pptx_slides
from studio_core.google_api import Client, GoogleError, Response, SLIDES_MIME
from studio_core.research_sources import Sources
import pptx_fixture

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
                     'Reads through Google Drive are unaffected.'),
        'quota': (error('PERMISSION_DENIED', message='The docs.googleapis.com API requires a quota project, which is not set by default.'),
                  "Google has not enabled this Google service for the sign-in's project, so it refused this request. "
                  'Reads through Google Drive are unaffected.'),
        'scope': (error('PERMISSION_DENIED', detail='ACCESS_TOKEN_SCOPE_INSUFFICIENT'),
                  'This Google sign-in was not given the access this needs. Sign in again with Drive access by running '
                  '`gcloud auth login editor@example.invalid --enable-gdrive-access --force --no-activate` in a terminal, then try again.'),
        'insufficient': (error(reason='insufficientPermissions'), None),
        'forbidden': (error(reason='forbidden'),
                      'This Google account cannot open this file. Ask its owner to share it with this account, or upload a copy instead.'),
        'denied': (error('PERMISSION_DENIED'), None),
        'export size': (error(reason='exportSizeLimitExceeded'),
                        'This file is larger than Google Drive can export (10 MB). Download it as a PowerPoint or PDF file and upload that copy instead.'),
        'unknown': (error(reason='somethingNew'),
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
        with self.assertRaisesRegex(ValueError, "earlier slide identities.*Read the link again.*earlier capture is kept"):
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
