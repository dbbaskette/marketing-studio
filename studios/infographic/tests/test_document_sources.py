"""Synthetic local extraction, original/text provenance and explicit coverage gaps."""
import hashlib
import io
import os
from pathlib import Path
import unittest
from unittest import mock
import zipfile

from helpers import Isolated
from runner import documents, intake, sources
from runner.contracts import Invalid
from runner.workspace import Store

PDF_READER = os.environ.get('INFOGRAPHIC_STUDIO_TEST_PDF_READER')

def docx(body='Synthetic document.', extra=''):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="' + documents.WORD
                         + '"><w:body><w:p><w:r><w:t>' + body + '</w:t></w:r></w:p>'
                         + extra + '</w:body></w:document>')
    return output.getvalue()


def simple_pdf():
    commands = b'BT /F1 12 Tf 72 720 Td (Synthetic PDF text.) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
               b'<< /Length ' + str(len(commands)).encode() + b' >>\nstream\n' + commands + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    raw, offsets = b'%PDF-1.4\n', [0]
    for n, value in enumerate(objects, 1):
        offsets.append(len(raw)); raw += str(n).encode() + b' 0 obj\n' + value + b'\nendobj\n'
    start = len(raw)
    raw += b'xref\n0 6\n0000000000 65535 f \n'
    raw += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return raw + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(start).encode() + b'\n%%EOF\n'


class DocumentSourceTests(Isolated):
    def setUp(self):
        super().setUp()
        self.store = Store.setup(self.workspace, data=self.data)
        self.project = self.store.create('Synthetic document review')

    def test_word_capture_preserves_original_and_locates_paragraphs_and_tables(self):
        raw = docx('First paragraph.', '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table value 12.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
        p = sources.capture(self.store, self.project['id'], raw, kind='docx', name='supplied.docx', expected_revision=0)
        source = p['sources'][0]
        value = sources.read(self.store, p, source)
        self.assertEqual(value, 'First paragraph.\nTable value 12.\n')
        self.assertEqual(source['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual((self.workspace / 'projects' / p['id'] / source['file']).read_bytes(), raw)
        self.assertEqual([value[loc['start']:loc['end']] for loc in source['coverage']['locations']],
                         ['First paragraph.', 'Table value 12.'])

    def test_unreadable_elements_require_explicit_readable_only_acknowledgment(self):
        raw = docx(extra='<w:p><w:r><w:drawing/></w:r></w:p>')
        preview = documents.extract(raw, 'docx')
        self.assertTrue(preview['warnings'])
        with self.assertRaisesRegex(Invalid, 'extraction gaps'):
            sources.capture(self.store, self.project['id'], raw, kind='docx', expected_revision=0)
        self.assertEqual(self.store.read(self.project['id'])['revision'], 0)
        p = sources.capture(self.store, self.project['id'], raw, kind='docx', expected_revision=0, acknowledge_warnings=True)
        self.assertTrue(p['sources'][0]['coverage']['acknowledged'])

    def test_word_rejects_archive_escape_entities_and_oversized_expansion(self):
        for name, body in [('../word/document.xml', b'<x/>'),
                           ('word/document.xml', b'<!DOCTYPE x [<!ENTITY a "private">]><x>&a;</x>'),
                           ('word/document.xml', '<!DOCTYPE x [<!ENTITY a "private">]><x>&a;</x>'.encode('utf-16')),
                           ('word/document.xml', b'x' * (documents.XML_LIMIT + 1))]:
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive: archive.writestr(name, body)
            with self.subTest(name=name), self.assertRaises(ValueError): documents.extract(output.getvalue(), 'docx')

    def test_pdf_pages_keep_locations_and_name_scanned_gaps_without_ocr(self):
        with mock.patch.object(documents, 'pdf_text', return_value='Readable first page.\f\fReadable third page.\f'):
            value = documents.extract(b'%PDF-synthetic', 'pdf')
        self.assertEqual([p['label'] for p in value['locations']], ['Page 1', 'Page 3'])
        self.assertIn('Page 2', value['warnings'][0])
        with mock.patch.object(documents, 'pdf_text', return_value='\f'):
            self.assertFalse(documents.extract(b'%PDF-synthetic', 'pdf')['readable'])

    def test_missing_pdf_reader_never_installs_or_starts_a_provider(self):
        with mock.patch.object(documents.shutil, 'which', return_value=None), \
                mock.patch.object(documents.subprocess, 'Popen', side_effect=AssertionError('No execution')):
            with self.assertRaisesRegex(Invalid, 'installed pdftotext'): documents.extract(b'%PDF-synthetic', 'pdf')

    def test_pdf_timeout_stops_its_owned_reader_process(self):
        reader = self.temp / 'synthetic-reader'
        reader.write_text('#!/bin/sh\nsleep 60\n')
        reader.chmod(0o700)
        actual = documents.subprocess.Popen
        with mock.patch.object(documents.subprocess, 'Popen', wraps=actual) as spawned:
            with self.assertRaisesRegex(Invalid, 'timed out'):
                documents.pdf_text(b'%PDF-synthetic', executable=reader, timeout=.1)
        self.assertEqual(spawned.call_count, 1)
        self.assertEqual(spawned.call_args.kwargs['env']['PATH'], os.defpath)

    def test_html_never_executes_scripts_or_fetches_linked_resources(self):
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('No fetch')):
            value = documents.extract(b'<p>Supplied &amp; readable.</p><script>private()</script><img src="http://127.0.0.1/secret">', 'html')
        self.assertEqual(value['text'], 'Supplied & readable.\n')
        self.assertTrue(value['warnings'])

    def test_preview_import_uses_one_immutable_capture_and_refuses_tampering(self):
        raw = docx('Preview exactly this revision.')
        preview = intake.prepare(raw, kind='docx', name='synthetic.docx')
        self.assertEqual(self.store.read(self.project['id'])['revision'], 0)
        with mock.patch.object(documents, 'extract', side_effect=AssertionError('Do not extract or fetch again')):
            p = intake.adopt(self.store, self.project['id'], preview['id'], expected_revision=0)
        self.assertEqual(sources.read(self.store, p, p['sources'][0]), 'Preview exactly this revision.\n')
        changed = self.data / 'jobs' / ('intake_' + preview['id']) / 'original.raw'
        changed.write_bytes(b'changed')
        with self.assertRaisesRegex(Invalid, 'preview changed'):
            intake.adopt(self.store, self.project['id'], preview['id'], expected_revision=p['revision'])
        self.assertEqual(self.store.read(self.project['id']), p)

    def test_preview_with_gaps_requires_acknowledgment_again_at_import(self):
        preview = intake.prepare(docx(extra='<w:p><w:r><w:drawing/></w:r></w:p>'), kind='docx', name='synthetic.docx')
        with self.assertRaisesRegex(Invalid, 'extraction gaps'):
            intake.adopt(self.store, self.project['id'], preview['id'], expected_revision=0)
        p = intake.adopt(self.store, self.project['id'], preview['id'], expected_revision=0, acknowledge_warnings=True)
        self.assertTrue(p['sources'][0]['coverage']['acknowledged'])

    @unittest.skipUnless(PDF_READER, 'explicit installed PDF reader acceptance only')
    def test_actual_installed_reader_extracts_a_synthetic_pdf(self):
        reader = Path(PDF_READER)
        self.assertTrue(reader.is_file())
        value = documents.pdf_text(simple_pdf(), executable=reader)
        self.assertIn('Synthetic PDF text.', value)
