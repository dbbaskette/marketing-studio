"""Explicit remote reads become immutable previews; importing never fetches again."""

from __future__ import annotations
import re
from urllib.parse import urlsplit
from studio_core.google_api import Client, DOC_MIME, SLIDES_MIME, GoogleError
from studio_core import public_fetch
from . import documents, intake
from .contracts import Invalid, canonical, digest
from .validation import require


def google_reference(value):
    require(
        isinstance(value, str) and len(value) < 2000, "Give a Google document link."
    )
    try:
        parts = urlsplit(value)
    except ValueError:
        raise Invalid("Give a canonical Google document link.") from None
    match = re.fullmatch(
        r"/(document|presentation)/(?:u/[0-9]+/)?d/([A-Za-z0-9_-]{1,200})(?:/(?:edit|preview|view|present))?/?",
        parts.path,
    )
    require(
        parts.scheme == "https"
        and parts.netloc == "docs.google.com"
        and match is not None,
        "Paste a Google Docs or Google Slides link copied from its Share menu.",
    )
    # Google share links may carry ordinary tab/share parameters; they never choose the API destination.
    return match.group(1), match.group(2)


def doc_id(value):
    kind, ident = google_reference(value)
    require(kind == "document", "Use a Google Docs link for a document.")
    return ident


def extract_presentation(presentation, selected=None):
    slides = presentation.get("slides", [])
    require(
        isinstance(slides, list) and 0 < len(slides) <= 200,
        "Choose a presentation with 1–200 readable slides.",
    )
    require(
        selected is None
        or isinstance(selected, list)
        and selected
        and len(set(selected)) == len(selected)
        and all(isinstance(i, str) for i in selected),
        "Choose distinct slide identities or include all slides.",
    )
    if selected is not None:
        require(
            set(selected) <= {s.get("objectId") for s in slides},
            "A selected slide is unavailable. Read a fresh preview.",
        )
    chunks, locations, warnings, snapshot = [], [], set(), []
    cursor = 0

    def elements(items, label, depth=0):
        nonlocal cursor
        require(depth < 20, "Slide groups are nested too deeply.")
        for item in items:
            if "elementGroup" in item:
                elements(item["elementGroup"].get("children", []), label, depth + 1)
            values = []
            if "shape" in item:
                values.append(item["shape"].get("text", {}))
            if "table" in item:
                for row in item["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        values.append(cell.get("text", {}))
            for value in values:
                text = "".join(
                    e.get("textRun", {}).get("content", "")
                    for e in value.get("textElements", [])
                ).strip()
                if text:
                    text += "\n"
                    locations.append(
                        {
                            "label": label + " / " + str(item.get("objectId", "text")),
                            "start": cursor,
                            "end": cursor + len(text),
                        }
                    )
                    chunks.append(text)
                    cursor += len(text)
            if any(k in item for k in ("image", "sheetsChart", "video", "wordArt")):
                warnings.add(
                    "Images, charts, video and WordArt are not interpreted. Supply their meaningful text or data separately."
                )

    for number, slide in enumerate(slides, 1):
        if selected is not None and slide.get("objectId") not in selected:
            continue
        start = cursor
        elements(slide.get("pageElements", []), "Slide " + str(number))
        notes = slide.get("slideProperties", {}).get("notesPage", {})
        speaker = notes.get("notesProperties", {}).get("speakerNotesObjectId")
        if speaker:
            elements(
                [
                    e
                    for e in notes.get("pageElements", [])
                    if e.get("objectId") == speaker
                ],
                "Slide " + str(number) + " speaker notes",
            )
        # Preserve selected text/locations, without signed image/content URLs or unselected slides.
        snapshot.append(
            {
                "id": slide.get("objectId"),
                "number": number,
                "text": "".join(chunks)[start:cursor],
            }
        )
    text = "".join(chunks)
    return {
        "text": text,
        "extractor": "google-slides-text-v1",
        "locations": locations,
        "warnings": sorted(warnings),
        "readable": bool(text.strip()),
    }, snapshot


def extract_document(document, selected_tabs=None):
    tabs = []

    def gather(items):
        for tab in items:
            props = tab.get("tabProperties", {})
            tabs.append(
                (
                    props.get("tabId"),
                    props.get("title", "Untitled tab"),
                    tab.get("documentTab", {}),
                )
            )
            gather(tab.get("childTabs", []))

    gather(document.get("tabs", []))
    if not tabs and isinstance(document.get("body"), dict):
        tabs = [("body", "Document", document)]
    require(
        bool(tabs) and len(tabs) <= 100,
        "This Google document has no supported readable tabs or too many tabs.",
    )
    require(
        selected_tabs is None
        or isinstance(selected_tabs, list)
        and 0 < len(selected_tabs) <= 100
        and all(isinstance(t, str) for t in selected_tabs)
        and len(set(selected_tabs)) == len(selected_tabs),
        "Choose distinct document tab identities, or leave empty for all tabs.",
    )
    selected = (
        tabs if selected_tabs is None else [t for t in tabs if t[0] in selected_tabs]
    )
    require(
        selected and (selected_tabs is None or len(selected) == len(selected_tabs)),
        "One of the selected Google tabs is unavailable. Preview the document again.",
    )
    chunks, locations, warnings = [], [], set()
    cursor = 0

    def append(value, label):
        nonlocal cursor
        if not value.strip():
            return
        value = value.rstrip() + "\n"
        chunks.append(value)
        locations.append({"label": label, "start": cursor, "end": cursor + len(value)})
        cursor += len(value)

    def walk(content, label, depth=0):
        require(depth < 20, "This document has too many nested tables.")
        for i, item in enumerate(content):
            here = label + " / block " + str(i + 1)
            if "paragraph" in item:
                elements = item["paragraph"].get("elements", [])
                append(
                    "".join(e.get("textRun", {}).get("content", "") for e in elements),
                    here,
                )
                if any("inlineObjectElement" in e for e in elements):
                    warnings.add(
                        "Images, drawings and embedded objects are not read; supply their meaningful text separately."
                    )
                if any(any(k.startswith("suggested") for k in e) for e in elements):
                    warnings.add(
                        "Google suggestions are not accepted or rejected here; this capture follows the returned text view."
                    )
            elif "table" in item:
                for r, row in enumerate(item["table"].get("tableRows", [])):
                    for c, cell in enumerate(row.get("tableCells", [])):
                        walk(
                            cell.get("content", []),
                            here + f" / row {r + 1} cell {c + 1}",
                            depth + 1,
                        )
            elif "sectionBreak" not in item:
                warnings.add(
                    "Unsupported document structures were omitted from the readable text."
                )

    snapshot = []
    for tab_id, title, tab in selected:
        walk(tab.get("body", {}).get("content", []), title)
        if any(
            tab.get(k)
            for k in (
                "headers",
                "footers",
                "footnotes",
                "positionedObjects",
                "inlineObjects",
            )
        ):
            warnings.add(
                "Headers, footers, notes and object content are omitted. Review readable-only coverage."
            )
        snapshot.append({"id": tab_id, "title": title, "body": tab.get("body", {})})
    return {
        "text": "".join(chunks),
        "extractor": "google-docs-tabs-v1",
        "locations": locations,
        "warnings": sorted(warnings),
        "readable": bool(chunks),
    }, snapshot


def google(url, *, account=None, tabs=None, client=None):
    kind, ident = google_reference(url)
    is_doc = kind == "document"
    try:
        client = client or Client(account)
        before = client.file(ident)
        require(
            before.get("id") == ident
            and before.get("mimeType") == (DOC_MIME if is_doc else SLIDES_MIME)
            and not before.get("trashed")
            and before.get("capabilities", {}).get("canDownload") is True,
            "This account cannot capture this Google document. Check read/download permissions or upload an allowed text copy.",
        )
        document = client.document(ident) if is_doc else client.presentation(ident)
        require(
            document.get("documentId" if is_doc else "presentationId") == ident,
            "Google returned a different document identity.",
        )
        extracted, snapshot = (extract_document if is_doc else extract_presentation)(
            document, tabs
        )
        after = client.file(ident)
        require(
            before.get("version")
            and before.get("modifiedTime")
            and all(
                before.get(k) == after.get(k)
                for k in (
                    "id",
                    "version",
                    "modifiedTime",
                    "mimeType",
                    "trashed",
                    "capabilities",
                )
            ),
            "The Google document changed while being read. Preview a fresh revision; existing local work is kept.",
        )
        saved = {
            "document_id" if is_doc else "presentation_id": ident,
            "version": before["version"],
            "modified": before["modifiedTime"],
            "revision": document.get("revisionId"),
            "tabs": snapshot,
        }
        return intake.prepare(
            canonical(saved),
            kind="google-doc" if is_doc else "google-slides",
            name=str(before.get("name") or "Google document")[:200]
            .replace("/", "-")
            .replace("\\", "-"),
            extracted=extracted,
            provenance={
                "url": "https://docs.google.com/" + kind + "/d/" + ident + "/edit",
                "document_id" if is_doc else "presentation_id": ident,
                "version": before["version"],
                "modified": before["modifiedTime"],
                "tabs": [t["id"] for t in snapshot],
                "snapshot_sha256": digest(saved),
            },
        )
    except GoogleError as failure:
        raise Invalid(str(failure)) from None


def public(url, *, fetcher=public_fetch.fetch):
    try:
        found = fetcher(url)
    except (ValueError, OSError):
        raise Invalid(
            "This public page could not be captured safely. Use a public HTTPS page or upload a permitted copy."
        ) from None
    kind = {"text/html": "html", "text/plain": "text", "application/pdf": "pdf"}[
        found["mime"]
    ]
    extracted = (
        documents.extract(found["raw"], kind)
        if kind != "text"
        else {
            "text": found["raw"].decode("utf-8-sig"),
            "extractor": "public-utf8-v1",
            "locations": [],
            "warnings": [],
            "readable": True,
        }
    )
    return intake.prepare(
        found["raw"],
        kind="url",
        name="Public page",
        extracted=extracted,
        provenance={"url": found["url"], "mime": found["mime"]},
    )
