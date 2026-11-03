"""Read a PowerPoint export's slides, in presentation order, with the standard library.

Google Slides decks are exported through Google Drive as .pptx. This turns the export
into the slide model `google_reference.extract_presentation` reads (shapes, tables,
groups and speaker notes), so captures keep the same text, locations, warnings and
snapshot shape they had when decks were read through the Google Slides API.

The export is untrusted bytes: every part is size-capped while it is decompressed,
only the parts the slide list names are read, and XML with a DTD or entity
declaration is refused.
"""
from __future__ import annotations

import hashlib
import io
import posixpath
import re
import struct
import zipfile
from xml.etree.ElementTree import TreeBuilder
import xml.parsers.expat

LIMIT = 40_000_000  # The whole export, as Google Drive transfers are capped.
PART_LIMIT = 10_000_000  # One XML part, decompressed.
TOTAL_LIMIT = 80_000_000  # Every XML part read, decompressed.
MOST_ENTRIES = 10_000
MOST_SLIDES = 200
DEPTH = 20  # Group nesting, as the Google Slides API reading allowed.
XML_DEPTH = 256

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
TABLE = "http://schemas.openxmlformats.org/drawingml/2006/table"

UNREADABLE = ("Google's PowerPoint export of this deck could not be read safely. "
              "Download it as a PDF and upload that copy instead.")
COUNT = "Choose a presentation with 1–200 readable slides."
NESTED = "Slide groups are nested too deeply."
IDENTITY = re.compile(r"slide-([1-9][0-9]{0,2})-([0-9a-f]{12})")
POSITION = re.compile(r"slide-([1-9][0-9]{0,2})")


class Unreadable(ValueError):
    pass


def refuse(message=UNREADABLE):
    raise Unreadable(message)


def identity(number, text):
    """Stable for an unchanged deck: the slide's position and a digest of its text."""
    return "slide-" + str(number) + "-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def parse(data):
    """An ElementTree root, refusing DTDs, entities and absurd nesting."""
    builder = TreeBuilder()
    parser = xml.parsers.expat.ParserCreate(namespace_separator="}")
    depth = 0

    def name(value):
        return "{" + value if "}" in value else value

    def start(tag, attributes):
        nonlocal depth
        depth += 1
        if depth > XML_DEPTH:
            refuse()
        builder.start(name(tag), {name(k): v for k, v in attributes.items()})

    def end(tag):
        nonlocal depth
        depth -= 1
        builder.end(name(tag))

    def declared(*_):
        refuse()

    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler = builder.data
    parser.StartDoctypeDeclHandler = declared
    parser.EntityDeclHandler = declared
    parser.UnparsedEntityDeclHandler = declared
    parser.ExternalEntityRefHandler = lambda *_: refuse()
    parser.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(data, True)
        return builder.close()
    except Unreadable:
        raise
    except (xml.parsers.expat.ExpatError, ValueError, AssertionError, IndexError):
        refuse()


class Package:
    def __init__(self, data):
        if not isinstance(data, (bytes, bytearray)) or not 0 < len(data) <= LIMIT:
            refuse()
        # Count entries from the end-of-central-directory record before zipfile lists them.
        end = bytes(data[-65_557:]).rfind(b"PK\x05\x06")
        if end < 0 or len(data[-65_557:]) - end < 22:
            refuse()
        if struct.unpack_from("<H", data[-65_557:], end + 10)[0] > MOST_ENTRIES:
            refuse()
        try:
            self.zip = zipfile.ZipFile(io.BytesIO(bytes(data)))
            entries = self.zip.infolist()
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError):
            refuse()
        names = [entry.filename for entry in entries]
        if len(entries) > MOST_ENTRIES or len(set(names)) != len(names):
            refuse()
        self.entries = {entry.filename: entry for entry in entries}
        self.read_total = 0

    def xml(self, name):
        entry = self.entries.get(name)
        if entry is None or entry.flag_bits & 0x1 or entry.file_size > PART_LIMIT:
            refuse()
        try:
            with self.zip.open(entry) as handle:
                data = handle.read(PART_LIMIT + 1)
        except (zipfile.BadZipFile, OSError, ValueError, EOFError, NotImplementedError, RuntimeError):
            refuse()
        self.read_total += len(data)
        if len(data) > PART_LIMIT or self.read_total > TOTAL_LIMIT:
            refuse()
        return parse(data)

    def relationships(self, part):
        """Relationship ID to (type, resolved part) for one part, internal targets only."""
        folder, file = posixpath.split(part)
        rels = posixpath.join(folder, "_rels", file + ".rels")
        if rels not in self.entries:
            return {}
        found = {}
        for item in self.xml(rels).iter(PR + "Relationship"):
            ident, kind, target = item.get("Id"), item.get("Type") or "", item.get("Target")
            if not ident or not target or item.get("TargetMode") == "External":
                continue
            resolved = posixpath.normpath(target[1:] if target.startswith("/")
                                          else posixpath.join(folder, target))
            if resolved.startswith("../") or resolved.startswith("/") or resolved == "..":
                continue  # Never followed; a slide or notes part it would name still refuses later.
            found[ident] = (kind, resolved)
        return found


def paragraphs(body):
    """Text as the Google Slides API gave it: runs and line breaks, each paragraph ending a line."""
    lines = []
    for paragraph in body.iter(A + "p"):
        line = []
        for child in paragraph:
            if child.tag == A + "r":
                line.extend(t.text or "" for t in child.iter(A + "t"))
            elif child.tag == A + "br":
                line.append("\n")
        lines.append("".join(line) + "\n")
    return {"textElements": [{"textRun": {"content": "".join(lines)}}]}


def shape_id(element):
    for properties in element.iter(P + "cNvPr"):
        return properties.get("id") or "text"
    return "text"


def elements(tree, depth=0):
    """The slide model's page elements, in the slide's drawing order."""
    if depth > DEPTH:
        refuse(NESTED)
    found = []
    for item in tree:
        tag = item.tag
        if tag == MC + "AlternateContent":
            chosen = item.find(MC + "Fallback")
            if chosen is None:
                chosen = item.find(MC + "Choice")
            if chosen is not None:
                found.extend(elements(chosen, depth))
        elif tag == P + "sp":
            body = item.find(P + "txBody")
            found.append({"objectId": "shape " + shape_id(item),
                          "shape": {"text": paragraphs(body) if body is not None else {}}})
        elif tag == P + "grpSp":
            found.append({"objectId": "group " + shape_id(item),
                          "elementGroup": {"children": elements(item, depth + 1)}})
        elif tag == P + "graphicFrame":
            data = item.find(A + "graphic/" + A + "graphicData")
            table = data.find(A + "tbl") if data is not None else None
            if data is not None and data.get("uri") == TABLE and table is not None:
                rows = [{"tableCells": [{"text": paragraphs(cell.find(A + "txBody"))
                                         if cell.find(A + "txBody") is not None else {}}
                                        for cell in row.findall(A + "tc")]}
                        for row in table.findall(A + "tr")]
                found.append({"objectId": "table " + shape_id(item), "table": {"tableRows": rows}})
            else:
                found.append({"objectId": "object " + shape_id(item), "sheetsChart": {}})
        elif tag == P + "pic":
            media = any(child.tag in (A + "videoFile", A + "audioFile", A + "quickTimeFile")
                        for child in item.iter())
            found.append({"objectId": "picture " + shape_id(item), ("video" if media else "image"): {}})
        elif tag == P + "contentPart":
            found.append({"objectId": "object", "image": {}})
    return found


def notes(package, slide_part):
    for kind, part in package.relationships(slide_part).values():
        if kind.endswith("/notesSlide"):
            tree = package.xml(part).find(P + "cSld/" + P + "spTree")
            if tree is None:
                return None
            body = [element for element in tree.iter(P + "sp")
                    if any(ph.get("type") == "body" for ph in element.iter(P + "ph"))]
            if not body:
                return None
            model = elements(body)
            return {"notesProperties": {"speakerNotesObjectId": model[0]["objectId"]},
                    "pageElements": model}
    return None


def slides(data):
    """Each slide, in the order `ppt/presentation.xml` lists them, as the slide model.

    A slide's `objectId` is `slide-<position>-<12 hex digits of its text's SHA-256>`.
    """
    from studio_core.google_reference import extract_presentation  # The one text reading.

    package = Package(data)
    main = next((part for kind, part in package.relationships("").values()
                 if kind.endswith("/officeDocument")), "ppt/presentation.xml")
    order = package.xml(main).find(P + "sldIdLst")
    listed = [] if order is None else order.findall(P + "sldId")
    if not 0 < len(listed) <= MOST_SLIDES:
        refuse(COUNT)
    targets = package.relationships(main)
    result = []
    for number, entry in enumerate(listed, 1):
        kind, part = targets.get(entry.get(R + "id"), ("", ""))
        if not kind.endswith("/slide"):
            refuse()
        tree = package.xml(part).find(P + "cSld/" + P + "spTree")
        if tree is None:
            refuse()
        slide = {"objectId": "slide", "pageElements": elements(tree)}
        speaker = notes(package, part)
        if speaker:
            slide["slideProperties"] = {"notesPage": speaker}
        _, snapshot = extract_presentation({"slides": [slide]})
        slide["objectId"] = identity(number, snapshot[0]["text"])
        result.append(slide)
    return {"slides": result}
