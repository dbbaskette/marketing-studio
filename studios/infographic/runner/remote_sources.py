"""Explicit remote previews using the shared read-only Google capture boundary."""
from __future__ import annotations
import json
from studio_core import public_fetch, google_reference as shared_google
from studio_core.google_api import Client, DOC_MIME, SLIDES_MIME, GoogleError
from . import documents, intake
from .contracts import Invalid, digest


def google_reference(value):
    try: return shared_google.google_reference(value)
    except ValueError as error: raise Invalid(str(error)) from None


def doc_id(value):
    try: return shared_google.doc_id(value)
    except ValueError as error: raise Invalid(str(error)) from None


def extract_document(document, selected_tabs=None):
    try: return shared_google.extract_document(document, selected_tabs)
    except ValueError as error: raise Invalid(str(error)) from None


def extract_presentation(document, selected=None):
    try: return shared_google.extract_presentation(document, selected)
    except ValueError as error: raise Invalid(str(error)) from None


def google(url, *, account=None, tabs=None, client=None):
    try:
        captured = shared_google.capture(url, account=account, selected=tabs, client=client or Client(account))
        saved = json.loads(captured['raw'])
        ident_key = 'document_id' if captured['kind'] == 'google-doc' else 'presentation_id'
        ident = saved.get(ident_key) or saved['document_id']
        return intake.prepare(captured['raw'], kind=captured['kind'], name=captured['name'],
            extracted=captured['extracted'], provenance={'url':captured['origin'], ident_key:ident,
                'version':saved['version'], 'modified':saved['modified'], 'tabs':captured['selected_tabs'],
                'snapshot_sha256':digest(saved)})
    except (ValueError, OSError) as error:
        raise Invalid(str(error)) from None


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
