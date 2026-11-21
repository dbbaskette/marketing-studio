"""Small synthetic .xlsx workbooks, built with zipfile, as Google Drive would export a sheet.

A cell is a str (a shared string), an int or float (a number), a bool, None (no cell), or a
tuple: ('inline', text), ('formula', kept result), ('date', serial number) or
('error', code). Sheet files are numbered against the workbook's order, so a reader that
followed file names would read them in the wrong order.
"""
import io
from xml.sax.saxutils import escape, quoteattr
import zipfile

MAIN = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
RELS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
STYLES = ('<styleSheet ' + MAIN + '><numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd\\ hh:mm"/>'
          '</numFmts><cellXfs count="3"><xf numFmtId="0"/><xf numFmtId="14"/><xf numFmtId="164"/></cellXfs></styleSheet>')


def letters(index):
    name = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def sheet_xml(rows, strings):
    lines = []
    for number, row in enumerate(rows, 1):
        cells = []
        for at, value in enumerate(row or ()):
            where = ' r="' + letters(at) + str(number) + '"'
            if value is None:
                continue
            if isinstance(value, bool):
                cells.append('<c' + where + ' t="b"><v>' + str(int(value)) + '</v></c>')
            elif isinstance(value, (int, float)):
                cells.append('<c' + where + '><v>' + repr(value) + '</v></c>')
            elif isinstance(value, str):
                if value not in strings:
                    strings.append(value)
                cells.append('<c' + where + ' t="s"><v>' + str(strings.index(value)) + '</v></c>')
            elif value[0] == 'inline':
                cells.append('<c' + where + ' t="inlineStr"><is><t>' + escape(value[1]) + '</t></is></c>')
            elif value[0] == 'formula':
                cells.append('<c' + where + ' t="str"><f>A1&amp;B1</f><v>' + escape(value[1]) + '</v></c>')
            elif value[0] == 'date':
                style = '2' if value[1] != int(value[1]) else '1'
                cells.append('<c' + where + ' s="' + style + '"><v>' + repr(value[1]) + '</v></c>')
            elif value[0] == 'error':
                cells.append('<c' + where + ' t="e"><v>' + escape(value[1]) + '</v></c>')
        lines.append('<row r="' + str(number) + '">' + ''.join(cells) + '</row>')
    return '<?xml version="1.0"?><worksheet ' + MAIN + '><sheetData>' + ''.join(lines) + '</sheetData></worksheet>'


def workbook(sheets, *, charts=(), replace=None, extra=None):
    """An .xlsx holding `sheets`, each (name, rows), in this order. A name in `charts` is a
    chart sheet with no cells."""
    count, strings = len(sheets), []
    files = {
        '[Content_Types].xml': '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        '_rels/.rels': '<?xml version="1.0"?><Relationships ' + RELS + '><Relationship Id="rId1" Type="'
                       + REL + '/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/styles.xml': '<?xml version="1.0"?>' + STYLES,
    }
    listed, rels = [], []
    for position, (name, rows) in enumerate(sheets, 1):
        number = count - position + 1
        chart = name in charts
        target = ('chartsheets/sheet' if chart else 'worksheets/sheet') + str(number) + '.xml'
        listed.append('<sheet name=' + quoteattr(name) + ' sheetId="' + str(position) + '" r:id="rId' + str(number) + '"/>')
        rels.append('<Relationship Id="rId' + str(number) + '" Type="' + REL + ('/chartsheet' if chart else '/worksheet')
                    + '" Target="' + target + '"/>')
        files['xl/' + target] = '<chartsheet ' + MAIN + '/>' if chart else sheet_xml(rows, strings)
    rels.append('<Relationship Id="rIdStrings" Type="' + REL + '/sharedStrings" Target="sharedStrings.xml"/>')
    rels.append('<Relationship Id="rIdStyles" Type="' + REL + '/styles" Target="styles.xml"/>')
    files['xl/workbook.xml'] = ('<?xml version="1.0"?><workbook ' + MAIN + ' xmlns:r="' + REL + '"><sheets>'
                                + ''.join(listed) + '</sheets></workbook>')
    files['xl/_rels/workbook.xml.rels'] = '<?xml version="1.0"?><Relationships ' + RELS + '>' + ''.join(rels) + '</Relationships>'
    files['xl/sharedStrings.xml'] = ('<?xml version="1.0"?><sst ' + MAIN + '>' + ''.join(
        '<si><r><t>' + escape(text[:3]) + '</t></r><r><t>' + escape(text[3:]) + '</t></r><rPh><t>PHONETIC</t></rPh></si>'
        if len(text) > 6 else '<si><t>' + escape(text) + '</t></si>' for text in strings) + '</sst>')
    files.update(replace or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in {**files, **(extra or {})}.items():
            archive.writestr(name, value if isinstance(value, bytes) else value.encode())
    return buffer.getvalue()


SAMPLE = [
    ('Pipeline', [['Account', 'Stage', 'Value'], ['Synthetic Co', 'Proposal', 12500], ['Other, Inc', ('inline', 'Closed "won"'), 0.1 + 0.2]]),
    ('Dates & notes', [['When', ('date', 46000), ('date', 46000.75), ('date', 0.5)],
                       [('formula', 'Joined text'), True, ('error', '#N/A'), None, 'Far cell']]),
    ('Empty', []),
]

# What `xlsx_sheets.extract` reads from SAMPLE: a section a sheet, the empty one left out.
SAMPLE_TEXT = ('# Pipeline\nAccount,Stage,Value\nSynthetic Co,Proposal,12500\n'
               + '"Other, Inc","Closed ' + '""won""' + '",0.3\n'
               + '# Dates & notes\nWhen,2025-12-09,2025-12-09 18:00:00,12:00:00\n'
               + 'Joined text,TRUE,#N/A,,Far cell\n')
