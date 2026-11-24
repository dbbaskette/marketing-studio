"""Bounded local document text and locations. Never OCR, fetch or install a reader.

A studio with its own size limit or error type passes `limit` and `error`
(Infographic Studio reads up to 16 MB and raises its own Invalid); the
defaults are the shared 8 MB and ValueError.
"""
from __future__ import annotations

from html.parser import HTMLParser
import io
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

MAX_SOURCE_BYTES = 8_000_000
def require(value, message, error=ValueError):
    if not value:
        raise error(message)


def megabytes(limit):
    return str(limit // 1_000_000) + ' MB'

KINDS = {'.pdf': 'pdf', '.docx': 'docx', '.html': 'html', '.htm': 'html'}
XML_LIMIT = 24_000_000
WORD = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
STRICT_WORD = 'http://purl.oclc.org/ooxml/wordprocessingml/main'


def result(parts, extractor, warnings=(), *, limit=MAX_SOURCE_BYTES, error=ValueError):
    """Offsets refer to the normalized text, independently of bytes/XML/PDF indexes."""
    lines, locations, at = [], [], 0
    for label, value in parts:
        value = value.replace('\r\n', '\n').replace('\r', '\n').strip()
        if not value:
            continue
        require('\x00' not in value, 'Extracted document text contains binary data.', error)
        lines.append(value + '\n')
        locations.append({'label': label, 'start': at, 'end': at + len(value)})
        at += len(value) + 1
        require(at <= limit and len(locations) <= 20_000,
                'Select a smaller document; extracted text or location coverage exceeds its limit.', error)
    value = ''.join(lines)
    require(len(value.encode('utf-8')) <= limit, 'Extracted document text exceeds ' + megabytes(limit) + '.', error)
    return {'text': value, 'extractor': extractor, 'locations': locations,
            'warnings': list(dict.fromkeys(warnings)), 'readable': bool(value.strip())}


def xml(raw, error=ValueError):
    require(len(raw) <= XML_LIMIT and b'\x00' not in raw
            and not re.search(br'<!\s*(?:DOCTYPE|ENTITY)', raw, re.I),
            'Document XML cannot contain entities, UTF-16/32 data or exceed the extraction limit. Save a fresh UTF-8 Word document.', error)
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        require(False, 'The document XML is malformed. Save a fresh Word document or supply text.', error)


def word(raw, *, limit=MAX_SOURCE_BYTES, error=ValueError):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) <= 512 and len({e.filename for e in entries}) == len(entries),
                    'The Word archive has excessive or duplicate entries.', error)
            total = 0
            for entry in entries:
                path = PurePosixPath(entry.filename)
                require(not path.is_absolute() and '..' not in path.parts and '\\' not in entry.filename
                        and not stat.S_ISLNK(entry.external_attr >> 16) and not entry.flag_bits & 1,
                        'The Word archive contains unsafe paths, links or encrypted entries.', error)
                total += entry.file_size
                require(total <= 64_000_000 and entry.file_size <= XML_LIMIT,
                        'The Word archive exceeds its bounded extraction size.', error)
            require('word/document.xml' in archive.namelist(), 'Supply a Word .docx document.', error)
            entry = archive.getinfo('word/document.xml')
            with archive.open(entry) as stream:
                body = stream.read(XML_LIMIT + 1)
            document = xml(body, error)
            require(document.tag in ('{' + WORD + '}document', '{' + STRICT_WORD + '}document'),
                    'The Word document uses an unsupported XML namespace.', error)
            namespace = document.tag.split('}')[0] + '}'
            parts = []
            warnings = []
            for element in document.iter():
                if element.tag == namespace + 'p':
                    words = []
                    for node in element.iter():
                        if node.tag == namespace + 't': words.append(node.text or '')
                        elif node.tag == namespace + 'tab': words.append('\t')
                        elif node.tag == namespace + 'br': words.append('\n')
                    parts.append(('Paragraph ' + str(len(parts) + 1), ''.join(words)))
                if element.tag in (namespace + 'drawing', namespace + 'pict', namespace + 'object'):
                    warnings.append('Images, charts and embedded objects were not read. Review them separately.')
                if element.tag in (namespace + 'ins', namespace + 'del', namespace + 'moveFrom', namespace + 'moveTo'):
                    warnings.append('Tracked changes are present. Confirm the extracted wording before using it.')
            if any(re.match(r'word/(?:header|footer|footnotes|endnotes|comments)', e.filename) for e in entries):
                warnings.append('Headers, footers, footnotes and comments were not included in the body extraction.')
            return result(parts, 'stdlib-docx-body-v1', warnings, limit=limit, error=error)
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError) as failure:
        raise ValueError('The Word document could not be read. Save it as .docx or supply its text.') from failure


def pdf_text(raw, *, executable=None, timeout=20, limit=MAX_SOURCE_BYTES, error=ValueError):
    require(raw.startswith(b'%PDF-'), 'The file is not a readable PDF.', error)
    executable = executable or shutil.which('pdftotext')
    require(executable and Path(executable).is_file() and os.access(executable, os.X_OK),
            'PDF reading needs an explicitly installed pdftotext reader. Supply Word or text, or install an approved reader yourself.', error)
    with tempfile.TemporaryDirectory(prefix='studio-document-pdf-') as temporary:
        folder = Path(temporary)
        source, output, diagnostics = (folder / name for name in ('source.pdf', 'source.txt', 'reader.log'))
        source.write_bytes(raw)
        with diagnostics.open('wb') as errors:
            process = subprocess.Popen([str(executable), '-layout', '-enc', 'UTF-8', str(source), str(output)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, cwd=folder,
                env={'PATH': os.defpath, 'HOME': str(folder), 'TMPDIR': str(folder)}, start_new_session=True)
            deadline = time.monotonic() + timeout
            try:
                while process.poll() is None:
                    require(time.monotonic() < deadline, 'PDF extraction timed out. Supply a smaller document.', error)
                    require(all(not p.exists() or p.stat().st_size <= limit for p in (output, diagnostics)),
                            'PDF extraction exceeded its bounded output limit.', error)
                    time.sleep(.03)
                require(process.returncode == 0 and output.is_file(),
                        'This PDF could not be read. It may be encrypted or damaged; supply an accessible copy.', error)
                with output.open('rb') as stream:
                    value = stream.read(limit + 1)
                require(len(value) <= limit, 'PDF text exceeds the extraction limit.', error)
                return value.decode('utf-8', errors='strict')
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)


def pdf(raw, *, limit=MAX_SOURCE_BYTES, error=ValueError):
    text = pdf_text(raw, limit=limit, error=error)
    pages = text.split('\f')
    if pages and not pages[-1].strip(): pages.pop()
    require(len(pages) <= 200, 'Select at most 200 PDF pages for one source.', error)
    warnings = ['Page ' + str(n) + ' contains no readable text; it may be scanned or blank.'
                for n, page in enumerate(pages, 1) if not page.strip()]
    if not pages: warnings.append('This PDF has no readable text. No OCR or provider upload was attempted.')
    return result([('Page ' + str(n), page) for n, page in enumerate(pages, 1)],
                  'installed-pdftotext-layout-v1', warnings, limit=limit, error=error)


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.words, self.hidden, self.warnings = [], [], 0, []

    def flush(self):
        if self.words:
            self.parts.append(('Block ' + str(len(self.parts) + 1), ''.join(self.words)))
            self.words = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe'): self.hidden += 1
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'tr', 'br'): self.flush()
        if tag in ('img', 'object', 'video', 'svg'):
            self.warnings.append('HTML images and embedded media were not read; no linked resources were fetched.')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'iframe'): self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'tr'): self.flush()

    def handle_data(self, data):
        if not self.hidden: self.words.append(data)


def extract(raw, kind, *, limit=MAX_SOURCE_BYTES, error=ValueError):
    require(type(raw) is bytes and 0 < len(raw) <= limit,
            'Supply a nonempty document no larger than ' + megabytes(limit) + '.', error)
    if kind == 'text':
        try: return result([('Text', raw.decode('utf-8-sig', errors='strict'))], 'utf8-text-v1', limit=limit, error=error)
        except UnicodeError: raise ValueError('Use UTF-8 text or upload Word/PDF.') from None
    if kind == 'docx': return word(raw, limit=limit, error=error)
    if kind == 'pdf': return pdf(raw, limit=limit, error=error)
    require(kind == 'html', 'Choose PDF, Word (.docx) or HTML for document extraction.', error)
    parser = HTMLText()
    try: parser.feed(raw.decode('utf-8-sig', errors='strict'))
    except (UnicodeError, RecursionError, ValueError): require(False, 'Supply a UTF-8 HTML document.', error)
    parser.flush()
    return result(parser.parts, 'stdlib-html-text-v1', parser.warnings, limit=limit, error=error)
