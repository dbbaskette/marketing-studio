"""Explicit, independently reviewed schema-2 research handoff; never starts research."""

from __future__ import annotations
from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from studio_core import research_contract as contract
from . import intake
from .contracts import Invalid, digest
from .validation import require, relative_path
from .workspace import _atomic, _read

TOTAL = 16_000_000


def task(project, source_mode="selected"):
    require(
        source_mode in ("selected", "mixed", "public"),
        "Choose supplied-only, mixed or public research explicitly.",
    )
    brief = project["brief"]
    return {
        "topic": brief["title"],
        "audience": brief["audience"]
        or "General readers; explain unfamiliar terminology.",
        "purpose": contract.purpose(
            "an infographic",
            brief["purpose"],
            "One clear takeaway; retain units, periods, qualifications, counterfacts and evidence gaps.",
        ),
        "scope": "\n".join([r["text"] for r in brief["must_show"]])
        or "Explain the selected topic within one readable page.",
        "source_mode": source_mode,
    }


def _unpack(raw, destination):
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        require(
            len(archive.infolist()) <= 1000
            and sum(x.file_size for x in archive.infolist()) <= TOTAL,
            "Choose a research bundle within 16 MB of extracted files.",
        )
        names = set()
        for info in archive.infolist():
            require(
                relative_path(info.filename)
                and info.filename not in names
                and not info.is_dir()
                and (info.external_attr >> 16) & 0o170000 != 0o120000
                and not info.flag_bits & 1,
                "Research bundles need unique ordinary relative files, without links or encryption.",
            )
            names.add(info.filename)
            _atomic(destination / info.filename, archive.read(info))


def _verify(root, *, runtime=None, verifier=None):
    facts, manifest = contract.read_bundle(contract.output_root(root))
    state = json.loads(_read(root, ".harness-research/synthesis.json", 2_000_000))
    require(
        state.get("owner") == contract.OWNER
        and state.get("digest") == manifest["digest"],
        "The research run and reviewed output do not describe the same revision.",
    )
    for source in facts.get("sources", []):
        for key, hash_key in (("file", "sha256"), ("original_file", "original_sha256")):
            if source.get(key):
                require(
                    hashlib.sha256(_read(root, source[key], TOTAL)).hexdigest()
                    == source.get(hash_key),
                    "A pinned research capture is missing or changed. Re-review it before importing.",
                )
    if verifier:
        verified = verifier(root)
    else:
        verified = contract.Workflow(runtime).command(root, "verify")
    require(
        isinstance(verified, dict)
        and verified.get("status") == "complete"
        and verified.get("digest") == manifest["digest"],
        "Harness Research did not verify this exact complete independently reviewed bundle.",
    )
    return facts, manifest


def prepare(case, *, expected_task, runtime=None, verifier=None):
    require(
        isinstance(expected_task, dict)
        and set(expected_task) == set(contract.TASK_FIELDS),
        "Keep the explicit infographic research task and source mode.",
    )
    root = Path(case).expanduser()
    require(
        root.is_absolute() and not any(p.is_symlink() for p in (root, *root.parents)),
        "Choose the owned research case without linked folders.",
    )
    # Read only the declared helper state, manifest and exact selected captures; no directory upload.
    output = contract.output_root(root)
    prefix = '' if output == root else 'research/'
    manifest = json.loads(_read(root, prefix + 'output.json', 2_000_000))
    facts = json.loads(_read(root, prefix + 'facts.json', 2_000_000))
    entries = manifest.get("artifacts")
    require(
        isinstance(entries, list) and len(entries) <= 1000,
        "Choose a bounded research artifact manifest.",
    )
    allowed = set(contract.ARTIFACTS)
    for source in facts.get("sources", []):
        for key in ("snapshot", "original_snapshot"):
            if source.get(key):
                allowed.add(contract.snapshot_name(source[key], manifest))
    require(
        {e.get("file") for e in entries} == allowed,
        "The research bundle contains unrelated or missing files.",
    )
    helper = contract.capability(Path(runtime) if runtime else contract.find_runtime())
    require(helper is not None, "Use an installed schema-2 Harness Research helper.")
    _, files = contract.case_files(root)
    require(sum(len(raw) for raw in files.values()) <= TOTAL, "Choose a research handoff within 16 MB.")
    with tempfile.TemporaryDirectory(prefix="infographic-research-") as temporary:
        copied = Path(temporary)
        for name, raw in files.items():
            _atomic(copied / name, raw)
        facts, manifest = _verify(copied, runtime=runtime, verifier=verifier)
    require(
        all(facts.get(k) == expected_task[k] for k in contract.TASK_FIELDS),
        "Research purpose, audience, scope or source mode differs from this infographic task. Revise and independently review research for this task.",
    )
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    # Brief first, then all qualified evidence, gaps and counterfacts. No automatic factual endorsement.
    text = "\n\n".join(
        files[prefix + n].decode("utf-8")
        for n in ("brief.md", "evidence.md", "report.md")
    )
    extracted = {
        "text": text,
        "extractor": "reviewed-harness-research-schema2",
        "locations": [],
        "warnings": [],
        "readable": True,
    }
    return intake.prepare(
        out.getvalue(),
        kind="research",
        name="Reviewed research",
        extracted=extracted,
        provenance={
            "task": expected_task,
            "helper": helper,
            "review_digest": digest(facts["review"]),
            "research_digest": manifest["digest"],
            "verified_archive_sha256": hashlib.sha256(out.getvalue()).hexdigest(),
        },
    )


def from_library(document, revision, *, expected_task):
    """Import one research item kept in the Document Library, chosen explicitly by the person.

    The kept bundle is written out and checked (studio_core research_bundle: every file against
    its manifest hash and its review), then captured as this infographic's research source. It
    may have been made for another purpose, audience or scope: its own task is recorded as the
    source's task, and the preview says so (`made_for`, `different`). Every other path still
    takes only research made for this infographic's task, character for character (prepare)."""
    from studio_core.document_library.research import research_bundle
    from studio_core.document_library.store import LibraryError
    require(
        isinstance(expected_task, dict) and set(expected_task) == set(contract.TASK_FIELDS),
        "Keep the explicit infographic research task and source mode.",
    )
    with tempfile.TemporaryDirectory(prefix="infographic-library-research-") as temporary:
        folder = Path(temporary) / "bundle"
        try:
            found = research_bundle(None, document, revision, folder)
            facts, manifest = contract.read_bundle(folder)
        except (LibraryError, ValueError, KeyError, OSError) as failure:
            raise Invalid(str(failure) or "The research in the Document Library could not be read.") from None
        files = {}
        for path in sorted(folder.rglob("*")):
            if path.is_file() and not path.is_symlink():
                files[path.relative_to(folder).as_posix()] = path.read_bytes()
    require(sum(len(raw) for raw in files.values()) <= TOTAL, "Choose research within 16 MB.")
    require(all(name in files for name in ("brief.md", "evidence.md", "report.md")),
            "The research in the Document Library has no report to use.")
    made_for = {key: facts.get(key) for key in contract.TASK_FIELDS}
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    text = "\n\n".join(files[n].decode("utf-8") for n in ("brief.md", "evidence.md", "report.md"))
    title = str(found.get("title") or "Research from the Document Library")[:150]
    prepared = intake.prepare(
        out.getvalue(),
        kind="research",
        name=title.replace("/", " ").replace("\\", " ").strip() or "Research from the Document Library",
        extracted={"text": text, "extractor": "document-library-research-schema2",
                   "locations": [], "warnings": [], "readable": True},
        provenance={
            "task": made_for,
            "review_digest": digest(facts["review"]),
            "research_digest": manifest["digest"],
            "verified_archive_sha256": hashlib.sha256(out.getvalue()).hexdigest(),
            "library": {"id": document, "revision": revision},
        },
    )
    return {**prepared, "made_for": made_for,
            "different": made_for != {key: expected_task[key] for key in contract.TASK_FIELDS}}


def validate_capture(raw, provenance):
    require(
        hashlib.sha256(raw).hexdigest() == provenance.get("verified_archive_sha256"),
        "The reviewed research handoff changed.",
    )
    with tempfile.TemporaryDirectory(prefix="infographic-research-read-") as temporary:
        root = Path(temporary)
        _unpack(raw, root)
        if provenance.get("library"):
            # Imported from the Document Library: the bundle itself, every file checked against
            # its manifest hash and review, with the task it was made for.
            facts, manifest = contract.read_bundle(root)
            require(
                manifest["digest"] == provenance.get("research_digest")
                and digest(facts["review"]) == provenance.get("review_digest")
                and all(facts.get(k) == v for k, v in provenance.get("task", {}).items()),
                "Reviewed research metadata changed.",
            )
            return
        facts, manifest = contract.read_bundle(contract.output_root(root))
        require(
            manifest["digest"] == provenance.get("research_digest")
            and digest(facts["review"]) == provenance.get("review_digest")
            and all(facts.get(k) == v for k, v in provenance.get("task", {}).items()),
            "Reviewed research metadata changed.",
        )
        for source in facts.get("sources", []):
            for key, hash_key in (
                ("file", "sha256"),
                ("original_file", "original_sha256"),
            ):
                if source.get(key):
                    require(
                        hashlib.sha256(_read(root, source[key], TOTAL)).hexdigest()
                        == source.get(hash_key),
                        "A reviewed research source capture changed.",
                    )
