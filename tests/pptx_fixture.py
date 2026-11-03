"""Small synthetic .pptx exports, built with zipfile, as Google Drive would send a deck.

Slide files are deliberately numbered against the presentation order, so a reader that
followed file names instead of `ppt/presentation.xml` would read them in the wrong order.
"""
import io
from xml.sax.saxutils import escape
import zipfile

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
RELS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'


def body(lines):
    return '<p:txBody><a:bodyPr/>' + ''.join(
        '<a:p>' + ''.join('<a:r><a:t>' + escape(part) + '</a:t></a:r>' if i == 0 else
                          '<a:br/><a:r><a:t>' + escape(part) + '</a:t></a:r>'
                          for i, part in enumerate(line.split('\n'))) + '</a:p>'
        for line in lines) + '</p:txBody>'


def shape(ident, lines, placeholder=None):
    ph = '<p:nvPr><p:ph type="' + placeholder + '"/></p:nvPr>' if placeholder else '<p:nvPr/>'
    return ('<p:sp><p:nvSpPr><p:cNvPr id="' + str(ident) + '" name="Google Shape;' + str(ident)
            + ';p"/><p:cNvSpPr/>' + ph + '</p:nvSpPr><p:spPr/>' + body(lines) + '</p:sp>')


def table(ident, rows):
    return ('<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="' + str(ident) + '" name="Table"/>'
            '<p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm/><a:graphic>'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl>'
            + ''.join('<a:tr>' + ''.join('<a:tc>' + body([cell]).replace('p:txBody', 'a:txBody')
                                          + '</a:tc>' for cell in row) + '</a:tr>' for row in rows)
            + '</a:tbl></a:graphicData></a:graphic></p:graphicFrame>')


def group(ident, inner):
    return ('<p:grpSp><p:nvGrpSpPr><p:cNvPr id="' + str(ident) + '" name="Group"/><p:cNvGrpSpPr/>'
            '<p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>' + inner + '</p:grpSp>')


PICTURE = ('<p:pic><p:nvPicPr><p:cNvPr id="90" name="Picture"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>'
           '<p:blipFill><a:blip r:embed="rIdImage"/></p:blipFill><p:spPr/></p:pic>')


def slide_xml(slide):
    parts = []
    if slide.get('title'):
        parts.append(shape(2, [slide['title']], 'title'))
    if slide.get('body'):
        parts.append(shape(3, slide['body']))
    if slide.get('table'):
        parts.append(table(4, slide['table']))
    if slide.get('group'):
        parts.append(group(5, ''.join(shape(10 + i, [line]) for i, line in enumerate(slide['group']))))
    if slide.get('picture'):
        parts.append(PICTURE)
    parts.extend(slide.get('raw', ()))
    tree = ('<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr/>' + ''.join(parts))
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld ' + NS + '><p:cSld><p:spTree>' + tree + '</p:spTree></p:cSld></p:sld>'


def notes_xml(text):
    tree = ('<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
            + shape(2, ['Slide image placeholder text'], 'sldImg') + shape(3, [text], 'body'))
    return '<?xml version="1.0" encoding="UTF-8"?><p:notes ' + NS + '><p:cSld><p:spTree>' + tree + '</p:spTree></p:cSld></p:notes>'


def deck(slides, *, extra=None, missing=None, replace=None):
    """A .pptx with these slides in presentation order; files are numbered in reverse."""
    count = len(slides)
    files = {
        '[Content_Types].xml': '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        '_rels/.rels': '<?xml version="1.0"?><Relationships ' + RELS + '><Relationship Id="rId1" Type="'
                       + REL + 'officeDocument" Target="ppt/presentation.xml"/></Relationships>',
    }
    ids, rels = [], []
    for position, slide in enumerate(slides, 1):
        number = count - position + 1
        ids.append('<p:sldId id="' + str(255 + position) + '" r:id="rIdS' + str(number) + '"/>')
        rels.append('<Relationship Id="rIdS' + str(number) + '" Type="' + REL + 'slide" Target="slides/slide'
                    + str(number) + '.xml"/>')
        files['ppt/slides/slide' + str(number) + '.xml'] = slide_xml(slide)
        slide_rels = ['<Relationship Id="rIdImage" Type="' + REL + 'image" Target="../media/image1.png"/>']
        slide_rels.extend(slide.get('rels', ()))
        if slide.get('notes'):
            files['ppt/notesSlides/notesSlide' + str(number) + '.xml'] = notes_xml(slide['notes'])
            slide_rels.append('<Relationship Id="rIdN" Type="' + REL + 'notesSlide" Target="../notesSlides/notesSlide'
                              + str(number) + '.xml"/>')
        files['ppt/slides/_rels/slide' + str(number) + '.xml.rels'] = (
            '<?xml version="1.0"?><Relationships ' + RELS + '>' + ''.join(slide_rels) + '</Relationships>')
    files['ppt/presentation.xml'] = ('<?xml version="1.0"?><p:presentation ' + NS + '><p:sldIdLst>'
                                     + ''.join(ids) + '</p:sldIdLst></p:presentation>')
    files['ppt/_rels/presentation.xml.rels'] = ('<?xml version="1.0"?><Relationships ' + RELS + '>'
                                                + ''.join(rels) + '</Relationships>')
    files.update(replace or {})
    for name in missing or ():
        files.pop(name)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in {**files, **(extra or {})}.items():
            archive.writestr(name, value if isinstance(value, bytes) else value.encode())
    return buffer.getvalue()


def google_shape(ident, paragraphs, placeholder=None):
    """A shape as Google Drive exports it: named for its Google Slides object and page."""
    ph = '<p:nvPr><p:ph type="' + placeholder + '"/></p:nvPr>' if placeholder else '<p:nvPr/>'
    return ('<p:sp><p:nvSpPr><p:cNvPr id="' + str(ident) + '" name="Google Shape;' + str(ident) + ';p13"/>'
            '<p:cNvSpPr txBox="1"/>' + ph + '</p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>'
            + ''.join(paragraphs) + '</p:txBody></p:sp>')


MC = ('xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
      'xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main"')
GOOGLE = {
    'raw': [
        google_shape(54, ['<a:p><a:pPr marL="0" lvl="0"><a:buNone/></a:pPr><a:r><a:rPr lang="en" b="1"/>'
                          '<a:t>Google </a:t></a:r><a:r><a:rPr lang="en"><a:hlinkClick r:id="rIdLink"/></a:rPr>'
                          '<a:t>shaped title</a:t></a:r><a:endParaRPr lang="en"/></a:p>'], 'title'),
        google_shape(55, ['<a:p><a:pPr algn="r"/><a:fld id="{00000000-1234-1234-1234-123412341234}" type="slidenum">'
                          '<a:rPr lang="en"/><a:t>4</a:t></a:fld><a:endParaRPr lang="en"/></a:p>'], 'sldNum'),
        '<mc:AlternateContent ' + MC + '><mc:Choice Requires="p14">'
        + google_shape(56, ['<a:p><a:r><a:rPr lang="en"/><a:t>Choice text</a:t></a:r></a:p>'])
        + '</mc:Choice><mc:Fallback>'
        + google_shape(57, ['<a:p><a:r><a:rPr lang="en"/><a:t>Fallback text</a:t></a:r><a:endParaRPr/></a:p>'])
        + '</mc:Fallback></mc:AlternateContent>',
    ],
    'rels': ['<Relationship Id="rIdLink" Type="' + REL + 'hyperlink" Target="https://example.invalid/page" TargetMode="External"/>',
             '<Relationship Id="rIdOdd" Type="' + REL + 'hyperlink" Target="../../../outside.html"/>'],
    'notes': 'Google speaker context.',
}

SAMPLE = [
    {'title': 'Synthetic opening', 'body': ['First point.', 'Second\npoint.'], 'notes': 'Opening speaker context.'},
    {'title': 'Synthetic numbers', 'table': [['Metric', 'Count 12'], ['Other', 'Count 7']], 'picture': True},
    {'title': 'Synthetic grouped', 'group': ['Grouped material.', 'More grouped.'], 'notes': 'Closing speaker context.'},
]
