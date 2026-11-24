"""Bounded local document text and locations. Never OCR, fetch or install a reader.

A studio with its own size limit or error type passes `limit` and `error`
(Infographic Studio reads up to 16 MB and raises its own Invalid); the
defaults are the shared 8 MB and ValueError.

Every studio reads Word, PDF and HTML text with the readers here, and keeps its own
limits, return shapes and sentences around them:
- `word_xml(xml, style=...)` reads a Word document's XML: 'paragraphs' (each
  paragraph's own text, as `word` and Blog Studio keep it) or 'lines' (paragraphs,
  list items and table rows as lines, as the deck studios keep a supplied document).
- `pdftotext(path, program=..., timeout=...)` is pdftotext's layout text of a PDF
  file; `pdf_text` is the bounded reader for research sources.
- `PageText` reads an HTML page: its blocks (`blocks()`, as `extract` keeps them) or
  its text with a line break at each block (`joined()`, as a fetched page is kept).
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
from xml.parsers import expat
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


DECLARED = 'Document XML cannot contain entities, UTF-16/32 data or exceed the extraction limit. Save a fresh UTF-8 Word document.'
MALFORMED = 'The document XML is malformed. Save a fresh Word document or supply text.'


def _plain_xml(raw, error=ValueError):
    require(len(raw) <= XML_LIMIT and b'\x00' not in raw
            and not re.search(br'<!\s*(?:DOCTYPE|ENTITY)', raw, re.I), DECLARED, error)


def xml(raw, error=ValueError):
    _plain_xml(raw, error)
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        require(False, MALFORMED, error)


# --- Word -----------------------------------------------------------------------------

WORD_SPACES = (WORD, STRICT_WORD)
MARKUP = 'http://schemas.openxmlformats.org/markup-compatibility/2006'


class WordUnreadable(ValueError):
    """A Word document's XML that cannot be read. `why` is 'malformed', 'declared'
    (it declares a DOCTYPE or an entity, which is never read) or 'long' (more text than
    the reader was allowed)."""

    def __init__(self, why):
        super().__init__(why)
        self.why = why


class _WordParagraphs:
    """Each paragraph's own text, in the order paragraphs start: its text runs, tabs and
    line breaks, a paragraph inside it included. The namespace is the root document's
    when it is one of `spaces`, else the first of them (and `root_ok` is False). Also
    notes what was not read, as `warnings`."""

    def __init__(self, spaces, most=None):
        self.spaces, self.most = spaces, most
        self.space, self.root_ok = None, False
        self.paragraphs, self.warnings = [], []
        self.open, self.text = [], []     # paragraphs not ended; text runs, innermost last

    def start(self, name, attributes):
        space, _, tag = name.rpartition(' ')
        if self.space is None:
            self.root_ok = space in self.spaces and tag == 'document'
            self.space = space if self.root_ok else self.spaces[0]
        if self.text:
            self.text[-1] = False         # a run's text is only what comes before an element in it
        if space != self.space:
            return
        if tag == 'p':
            self.open.append(len(self.paragraphs))
            self.paragraphs.append([])
        elif tag == 't':
            self.text.append(True)
        elif tag == 'tab':
            self._add('\t')
        elif tag == 'br':
            self._add('\n')
        if tag in ('drawing', 'pict', 'object'):
            self.warnings.append('Images, charts and embedded objects were not read. Review them separately.')
        if tag in ('ins', 'del', 'moveFrom', 'moveTo'):
            self.warnings.append('Tracked changes are present. Confirm the extracted wording before using it.')

    def end(self, name):
        space, _, tag = name.rpartition(' ')
        if space != self.space:
            return
        if tag == 'p':
            self.open.pop()
        elif tag == 't':
            self.text.pop()

    def data(self, text):
        if self.text and self.text[-1]:
            self._add(text)

    def _add(self, text):
        for index in self.open:
            self.paragraphs[index].append(text)

    def result(self):
        return [''.join(parts) for parts in self.paragraphs]


class _WordLines:
    """The plain text of a Word document's XML, in the order it is written: a paragraph or
    a heading is a line, a list item a line that starts with a dash, and a table row a line
    with its cells set apart. A text box written twice, once for older programs, and a
    passage still written where it was moved from, are each read once, where shown."""

    def __init__(self, spaces, most=None):
        self.spaces, self.most = spaces, most
        self.lines: list[str] = []
        self.open: list[list] = []          # paragraphs not yet ended: [its text, a list item]
        self.cells: list[list[str]] = []    # table cells not yet ended, innermost last
        self.rows: list[list[str]] = []     # table rows not yet ended, innermost last
        self.in_text, self.skipping, self.chars = False, 0, 0

    def start(self, name: str, attributes: dict) -> None:
        space, _, tag = name.rpartition(' ')
        if self.skipping or (space, tag) == (MARKUP, 'Fallback') or (space in self.spaces and tag == 'moveFrom'):
            self.skipping += 1
        elif space not in self.spaces:
            return
        elif tag == 'p':
            self.open.append([[], False])
        elif tag == 't':
            self.in_text = True
        elif tag in ('tab', 'ptab'):
            self._add('\t')
        elif tag in ('br', 'cr'):
            self._add('\n')
        elif tag == 'noBreakHyphen':
            self._add('-')
        elif tag in ('numPr', 'numId') and self.open:
            # Numbering 0 is how a paragraph says it is not in the list its style puts it in.
            self.open[-1][1] = tag == 'numPr' or attributes.get(f'{space} val') != '0'
        elif tag == 'tc':
            self.cells.append([])
        elif tag == 'tr':
            self.rows.append([])
        elif tag == 'tbl' and not self.cells:
            self.lines.append('')

    def end(self, name: str) -> None:
        if self.skipping:
            self.skipping -= 1
            return
        space, _, tag = name.rpartition(' ')
        if space not in self.spaces:
            return
        if tag == 't':
            self.in_text = False
        elif tag == 'p':
            self._paragraph()
        elif tag == 'tc':
            cell = ' '.join(part for part in self.cells.pop() if part)
            (self.rows[-1] if self.rows else self.lines).append(cell)
        elif tag == 'tr':
            cells = self.rows.pop()
            row = ' | '.join(cells) if any(cells) else ''
            (self.cells[-1] if self.cells else self.lines).append(row)
        elif tag == 'tbl' and not self.cells:
            self.lines.append('')

    def data(self, text: str) -> None:
        if self.in_text and not self.skipping:
            self._add(text)

    def _add(self, text: str) -> None:
        if not self.open:
            return
        self.chars += len(text)
        if self.most is not None and self.chars > self.most:
            raise WordUnreadable('long')
        self.open[-1][0].append(text)

    def _paragraph(self) -> None:
        parts, item = self.open.pop()
        text, self.in_text = ''.join(parts), False
        if self.cells:
            self.cells[-1].append(' '.join(text.split()))
        elif item and text.strip():
            self.lines.append('- ' + ' '.join(text.split()))
        else:
            self.lines += ['', *text.split('\n'), '']

    def result(self):
        return '\n'.join(self.lines)


def word_xml(raw, *, style='paragraphs', spaces=WORD_SPACES, most=None):
    """Read a Word document's XML (bytes) with one parser that never reads a declaration.

    'paragraphs' gives the reader: `.result()` is each paragraph's text, `.root_ok` says
    the root was a document in one of `spaces`, `.warnings` what was not read. 'lines'
    gives the reader whose `.result()` is the text as lines, and refuses more than `most`
    characters. Raises WordUnreadable.
    """
    reader = (_WordLines if style == 'lines' else _WordParagraphs)(spaces, most)
    parser = expat.ParserCreate(namespace_separator=' ')
    parser.buffer_text = True
    parser.StartElementHandler = reader.start
    parser.EndElementHandler = reader.end
    parser.CharacterDataHandler = reader.data

    def declared(*args):
        raise WordUnreadable('declared')

    # A Word document declares nothing. One that does is refused before anything it
    # declares is read, so no entity is ever expanded or fetched.
    parser.StartDoctypeDeclHandler = declared
    parser.EntityDeclHandler = declared
    parser.ExternalEntityRefHandler = declared
    try:
        parser.Parse(raw, True)
    except expat.ExpatError:
        raise WordUnreadable('malformed') from None
    return reader


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
            _plain_xml(body, error)
            try:
                read = word_xml(body, style='paragraphs', spaces=WORD_SPACES)
            except WordUnreadable as failure:
                require(False, DECLARED if failure.why == 'declared' else MALFORMED, error)
            require(read.root_ok, 'The Word document uses an unsupported XML namespace.', error)
            parts = [('Paragraph ' + str(n), text) for n, text in enumerate(read.result(), 1)]
            warnings = list(read.warnings)
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


class PageText(HTMLParser):
    """The readable text of an HTML page, and its title. Text inside a HIDDEN element is
    left out; a block starts at an OPENS tag and ends at a CLOSES tag. A studio sets the
    three for its pages. `blocks()` gives the text as blocks, `joined()` as one text with
    a line break at each block's start and end."""

    HIDDEN = ('script', 'style', 'iframe')
    OPENS = ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'tr', 'br')
    CLOSES = ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'tr')

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pieces, self.hidden, self.warnings = [], 0, []   # text, and None between blocks
        self.title, self.in_title = '', False

    def handle_starttag(self, tag, attrs):
        if tag in self.HIDDEN: self.hidden += 1
        if tag == 'title': self.in_title = True
        if tag in self.OPENS: self.pieces.append(None)
        if tag in ('img', 'object', 'video', 'svg'):
            self.warnings.append('HTML images and embedded media were not read; no linked resources were fetched.')

    def handle_endtag(self, tag):
        if tag in self.HIDDEN and self.hidden: self.hidden -= 1
        if tag == 'title': self.in_title = False
        if tag in self.CLOSES: self.pieces.append(None)

    def handle_data(self, data):
        if self.in_title: self.title += data
        if not self.hidden: self.pieces.append(data)

    def blocks(self):
        """[('Block <n>', its text)], one for each run of text between block boundaries."""
        found, words = [], []
        for piece in [*self.pieces, None]:
            if piece is not None:
                words.append(piece)
            elif words:
                found.append(('Block ' + str(len(found) + 1), ''.join(words)))
                words = []
        return found

    def joined(self):
        return ''.join('\n' if piece is None else piece for piece in self.pieces)


class HTMLText(PageText):
    """A document's HTML as `extract` reads it: `parts` holds its blocks once `flush()`
    is called."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def flush(self):
        self.parts = self.blocks()


def pdftotext(path, *, program, timeout):
    """pdftotext's layout text of the PDF file at `path`, as the bytes it wrote. Raises
    OSError or subprocess.TimeoutExpired when the reader could not run or finish, and
    subprocess.CalledProcessError when it could not read the file. No limit is put on
    the text: `pdf_text` is the bounded reader."""
    done = subprocess.run([program, '-layout', str(path), '-'], capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=timeout)
    if done.returncode != 0:
        raise subprocess.CalledProcessError(done.returncode, program)
    return done.stdout


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
