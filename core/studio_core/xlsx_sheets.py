"""Read every worksheet of a spreadsheet workbook (.xlsx), with the standard library.

Google Sheets files are exported through Google Drive as .xlsx, and a person may add an
.xlsx file of their own. `extract(data)` gives the shape `source_documents.extract` gives:
text with one section a sheet, headed by the sheet's name, its rows as CSV lines, with
locations and warnings.

- Shared strings, inline strings, numbers, booleans, errors and the kept results of
  formulas are read. A number shown as a date or time is written as an ISO date or time.
- Charts, pictures, comments and formatting are not read. A chart sheet has no cells and
  is named in a warning.
- A sheet is cut at MOST_ROWS rows and MOST_COLUMNS columns, and a workbook at
  MOST_SHEETS sheets; each cut is said in a warning that names the sheet.
- The workbook is untrusted bytes: it is opened with `pptx_slides.Package`, so every part
  is size-capped while it is decompressed, only the parts the workbook names are read,
  and XML with a DTD or entity declaration is refused.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
import io
import re

from studio_core import pptx_slides
from studio_core.source_documents import result

MOST_SHEETS = 50      # Worksheets read from one workbook.
MOST_ROWS = 5000      # Rows with something in them, read from one sheet.
MOST_COLUMNS = 200    # Columns read from one row.

UNREADABLE = ('This spreadsheet could not be read safely. It may be damaged, protected or too '
              'large. Save the sheets you need as CSV or PDF and add those instead.')
# Number formats Excel and Google Sheets build in for dates and times.
DATE_FORMATS = frozenset((14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47))
CELL = re.compile(r'([A-Za-z]{1,3})[0-9]*')


def refuse():
    raise ValueError(UNREADABLE)


def space(tree):
    """The namespace a part's root is in, as `{uri}`, so strict workbooks read the same."""
    return tree.tag[:tree.tag.index('}') + 1] if tree.tag.startswith('{') else ''


def identity(element):
    """A relationship ID, in whichever relationships namespace the workbook uses."""
    return next((value for key, value in element.attrib.items() if key.endswith('}id')), None)


def words(item, ns):
    """The text of a string item: its own text and its runs, never its phonetic guide."""
    parts = []
    for child in item:
        if child.tag == ns + 't':
            parts.append(child.text or '')
        elif child.tag == ns + 'r':
            parts.extend(t.text or '' for t in child.findall(ns + 't'))
    return ''.join(parts)


def dated(code):
    """True for a custom number format that shows a date or a time."""
    plain = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.|_.|\*.', '', code or '')
    return bool(re.search(r'[dmyhs]', plain, re.I)) and 'general' not in plain.lower()


def date_styles(package, part):
    """Which cell styles show their number as a date or time, by style index."""
    if not part:
        return set()
    tree = package.xml(part)
    ns = space(tree)
    custom = {fmt.get('numFmtId'): fmt.get('formatCode') for fmt in tree.iter(ns + 'numFmt')}
    styles = tree.find(ns + 'cellXfs')
    found = set()
    for index, style in enumerate(styles.findall(ns + 'xf') if styles is not None else ()):
        ident = style.get('numFmtId') or '0'
        if (ident.isdigit() and int(ident) in DATE_FORMATS) or dated(custom.get(ident)):
            found.add(index)
    return found


def number(value, as_date, base):
    try:
        amount = float(value)
    except ValueError:
        return value
    if as_date and 0 <= amount < 2_958_466:   # the last day a spreadsheet date can name
        moment = base + timedelta(seconds=round(amount * 86_400))
        if amount < 1:
            return moment.strftime('%H:%M:%S')
        return moment.strftime('%Y-%m-%d' if amount == int(amount) else '%Y-%m-%d %H:%M:%S')
    return format(amount, '.15g')


def column(reference, following):
    """A cell's column, counted from 0, from its reference (`C5`), else the next one."""
    found = CELL.fullmatch(reference or '')
    if not found:
        return following
    index = 0
    for letter in found.group(1).upper():
        index = index * 26 + ord(letter) - 64
    return index - 1


def rows(tree, shared, dates, base):
    """A worksheet's rows that hold something, and whether rows or columns were cut."""
    ns = space(tree)
    kept, cut_rows, cut_columns = [], False, False
    data = tree.find(ns + 'sheetData')
    for row in data.findall(ns + 'row') if data is not None else ():
        cells, following = {}, 0
        for cell in row.findall(ns + 'c'):
            at = column(cell.get('r'), following)
            following = at + 1
            kind, held = cell.get('t') or 'n', cell.find(ns + 'v')
            value = held.text or '' if held is not None else ''
            if kind == 's':
                value = shared[int(value)] if value.isdigit() and int(value) < len(shared) else ''
            elif kind == 'inlineStr':
                inline = cell.find(ns + 'is')
                value = words(inline, ns) if inline is not None else ''
            elif kind == 'b':
                value = 'TRUE' if value == '1' else 'FALSE'
            elif kind == 'n' and value:
                style = cell.get('s') or ''
                value = number(value, style.isdigit() and int(style) in dates, base)
            if not value.strip():
                continue
            if at >= MOST_COLUMNS:
                cut_columns = True
                continue
            cells[at] = value
        if not cells:
            continue
        if len(kept) >= MOST_ROWS:
            cut_rows = True
            break
        kept.append([cells.get(index, '') for index in range(max(cells) + 1)])
    return kept, cut_rows, cut_columns


def extract(data):
    """Every worksheet's cells as text, one section a sheet, with locations and warnings."""
    try:
        package = pptx_slides.Package(data)
        main = next((part for kind, part in package.relationships('').values()
                     if kind.endswith('/officeDocument')), 'xl/workbook.xml')
        book = package.xml(main)
        ns = space(book)
        parts = package.relationships(main)
        listed = book.find(ns + 'sheets')
        sheets = listed.findall(ns + 'sheet') if listed is not None else []
        if not sheets:
            refuse()
        settings = book.find(ns + 'workbookPr')
        early = settings is not None and settings.get('date1904') in ('1', 'true')
        base = datetime(1904, 1, 1) if early else datetime(1899, 12, 30)
        strings = next((part for kind, part in parts.values() if kind.endswith('/sharedStrings')), None)
        shared = []
        if strings:
            tree = package.xml(strings)
            shared = [words(item, space(tree)) for item in tree.findall(space(tree) + 'si')]
        dates = date_styles(package, next((part for kind, part in parts.values()
                                           if kind.endswith('/styles')), None))
        sections, warnings = [], []
        if len(sheets) > MOST_SHEETS:
            warnings.append(f'Only the first {MOST_SHEETS} of {len(sheets)} sheets were read.')
        for position, sheet in enumerate(sheets[:MOST_SHEETS], 1):
            name = ' '.join((sheet.get('name') or 'Sheet ' + str(position)).split())[:200]
            kind, part = parts.get(identity(sheet), ('', ''))
            if not kind.endswith('/worksheet'):
                warnings.append(f'Sheet “{name}” holds a chart or a macro, not cells, and was not read.')
                continue
            found, cut_rows, cut_columns = rows(package.xml(part), shared, dates, base)
            if cut_rows:
                warnings.append(f'Sheet “{name}” was cut after its first {MOST_ROWS:,} rows.')
            if cut_columns:
                warnings.append(f'Sheet “{name}” was cut after its first {MOST_COLUMNS} columns.')
            if found:
                written = io.StringIO()
                csv.writer(written, lineterminator='\n').writerows(found)
                sections.append(('Sheet ' + str(position) + ': ' + name, '# ' + name + '\n' + written.getvalue()))
    except pptx_slides.Unreadable:
        refuse()
    return result(sections, 'xlsx-sheets-v1', warnings)
