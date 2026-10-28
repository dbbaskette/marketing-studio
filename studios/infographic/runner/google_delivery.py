"""New Google Doc delivery from exact approved local bytes; no source-document mutation."""

from __future__ import annotations
from io import BytesIO
import hashlib
from xml.sax.saxutils import escape
import zipfile
from studio_core.google_api import (
    Client,
    DOC_MIME,
    GoogleError,
    account as valid_account,
    identifier as google_id,
)
from . import exports, visual_review
from .contracts import canonical, digest
from .validation import identifier, require, sha
from .workspace import _atomic, _json, _read, file_lock


def docx(project, png, text):
    """OOXML embeds private page bytes; Google conversion never needs a public image URL."""
    require(
        not any(
            ord(c) < 32 and c not in "\n\r\t" for c in project["brief"]["title"] + text
        ),
        "Remove unsupported control characters before Google document delivery.",
    )
    width, height = project["scene"]["width"], project["scene"]["height"]
    from .render import dimensions

    page = dimensions(project["brief"]["preset"])
    page_w, page_h = page["width_pt"], page["height_pt"]
    fit = min(page_w - 72, (page_h - 112) * width / height)
    cx, cy = round(fit * 12700), round(fit * height / width * 12700)
    page_twips = (round(page_w * 20), round(page_h * 20))
    title = escape(project["brief"]["title"], {'"': "&quot;"})
    paragraphs = "".join(
        '<w:p><w:r><w:t xml:space="preserve">' + escape(line) + "</w:t></w:r></w:p>"
        for line in text.splitlines()
    )
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body><w:p><w:r><w:t>{title}</w:t></w:r></w:p><w:p><w:r><w:drawing><wp:inline><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="1" name="Approved infographic" descr="{title}; editable text and source notes follow."/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="page.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="page"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p><w:p><w:r><w:br w:type="page"/></w:r></w:p>{paragraphs}<w:sectPr><w:pgSz w:w="{page_twips[0]}" w:h="{page_twips[1]}"/><w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/></w:sectPr></w:body></w:document>'''
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="main" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/_rels/document.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="page" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/page.png"/></Relationships>',
        "word/document.xml": content,
        "word/media/page.png": png,
    }
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return out.getvalue()


def approved(store, ident, export_id, revision):
    from .engine import Engine

    project = store.read(ident)
    store.expect(project, revision)
    delivery = next(
        (d for d in Engine(store).deliveries(ident) if d["id"] == export_id), None
    )
    require(
        delivery and delivery["approved_current"],
        "Export the exact approved, visually checked revision before Google delivery.",
    )
    return project, delivery


def execute(
    store,
    ident,
    *,
    expected_revision,
    export_id,
    request_id,
    account,
    folder="",
    reconcile=False,
    client=None,
):
    require(
        identifier(request_id) and identifier(export_id),
        "Choose saved delivery and request identities.",
    )
    try:
        valid_account(account)
        if folder:
            google_id(folder)
    except GoogleError as failure:
        raise ValueError(str(failure)) from None
    require(
        type(reconcile) is bool,
        "Choose an explicit delivery or read-only reconciliation.",
    )
    root = store._project(ident) / "jobs" / ("google_" + request_id)
    with file_lock(root / "operation.lock"):
        intent_path = root / "delivery-intent.json"
        if intent_path.exists():
            intent = _json(root, "delivery-intent.json")
            require(
                intent["request_id"] == request_id
                and intent["account"] == account
                and intent["folder"] == folder
                and intent["export_id"] == export_id
                and intent["revision"] == expected_revision,
                "This Google delivery request belongs to different content or a different destination. Reconcile the saved request.",
            )
            if (root / "result.json").exists():
                return checked_result(_json(root, "result.json"), intent)
            if not reconcile:
                return {
                    "state": "unknown",
                    "request_id": request_id,
                    "message": "A saved intent exists. Reconcile read-only before starting another delivery.",
                }
        else:
            require(not reconcile, "There is no saved Google delivery to reconcile.")
            project, delivery = approved(store, ident, export_id, expected_revision)
            png = exports.read(store, ident, export_id, "png")[1]
            text = exports.read(store, ident, export_id, "text")[1].decode()
            text += "\n\nCaptured sources\n" + "\n".join(
                s["name"]
                + " — "
                + s["sha256"]
                + (
                    "\n" + s.get("provenance", {}).get("url", "")
                    if s.get("provenance", {}).get("url")
                    else ""
                )
                for s in project["sources"]
            )
            payload = docx(project, png, text)
            intent = {
                "schema": 1,
                "request_id": request_id,
                "account": account,
                "folder": folder,
                "project": ident,
                "revision": expected_revision,
                "export_id": export_id,
                "delivery_digest": digest(delivery),
                "review_digest": digest(visual_review.latest(store, project)),
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "title": project["brief"]["title"][:200],
                "source_documents": [
                    s.get("provenance", {}).get("document_id")
                    for s in project["sources"]
                ],
            }
            _atomic(root / "payload.docx", payload)
            _atomic(
                intent_path, canonical(intent)
            )  # Before credential lookup or any Google request.
        client = client or Client(account)
        try:
            if reconcile:
                matches = client.find_delivery(request_id)
                require(
                    len(matches) <= 1,
                    "Multiple Google documents match this request. Inspect them manually; no new write was sent.",
                )
                if not matches:
                    return {
                        "state": "unknown",
                        "request_id": request_id,
                        "message": "No completed Google document is visible yet. Nothing was resent. Keep the PDF and reconcile later.",
                    }
                found = matches[0]
            else:
                # Recheck after intent creation; a changed page must not be labelled current.
                project, delivery = approved(store, ident, export_id, expected_revision)
                require(
                    digest(delivery) == intent["delivery_digest"]
                    and digest(visual_review.latest(store, project))
                    == intent["review_digest"],
                    "The approved delivery changed before upload. Keep this intent for read-only reconciliation.",
                )
                raw = _read(root, "payload.docx", 40_000_000)
                require(
                    hashlib.sha256(raw).hexdigest() == intent["payload_sha256"],
                    "The saved Google delivery payload changed.",
                )
                found = client.create_document(
                    raw,
                    title=intent["title"],
                    request_key=request_id,
                    payload_hash=intent["payload_sha256"],
                    folder=folder or None,
                )
            google_id(found.get("id"))
            require(
                found.get("mimeType") == DOC_MIME
                and found["id"] not in intent["source_documents"]
                and found.get("appProperties", {}).get("infographic_request")
                == request_id
                and found.get("appProperties", {}).get("infographic_payload")
                == intent["payload_sha256"],
                "Google returned a different delivery identity. Reconcile this saved request; no source was overwritten.",
            )
            result = {
                "state": "delivered",
                "request_id": request_id,
                "revision": intent["revision"],
                "export_id": export_id,
                "document_id": found["id"],
                "url": "https://docs.google.com/document/d/" + found["id"] + "/edit",
            }
            _atomic(root / "result.json", canonical(result))
            return result
        except GoogleError as failure:
            problem = {
                "state": "unknown" if failure.uncertain else "failed",
                "request_id": request_id,
                "message": str(failure),
            }
            _atomic(root / "problem.json", canonical(problem))
            return problem


def checked_result(result, intent):
    require(
        isinstance(result, dict)
        and result.get("state") == "delivered"
        and result.get("request_id") == intent["request_id"]
        and result.get("export_id") == intent["export_id"]
        and result.get("revision") == intent["revision"],
        "The saved Google delivery identity changed.",
    )
    try:
        google_id(result.get("document_id"))
    except GoogleError:
        require(False, "The saved Google document identity is invalid.")
    return {
        **result,
        "url": "https://docs.google.com/document/d/" + result["document_id"] + "/edit",
    }


def listing(store, ident):
    store.read(ident)
    jobs = store._project(ident) / "jobs"
    require(not jobs.is_symlink(), "Google delivery jobs cannot be links.")
    found = []
    for path in jobs.glob("google_*"):
        try:
            intent = _json(path, "delivery-intent.json")
            require(
                intent.get("schema") == 1
                and intent.get("project") == ident
                and identifier(intent.get("request_id"))
                and sha(intent.get("payload_sha256")),
                "The saved Google intent is invalid.",
            )
            result = (
                checked_result(_json(path, "result.json"), intent)
                if (path / "result.json").exists()
                else {"state": "unknown"}
            )
            found.append({**intent, **result})
        except (ValueError, OSError):
            continue
    return found
