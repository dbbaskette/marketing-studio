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
from .contracts import digest
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
    facts, manifest = contract.read_bundle(root / "research")
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
    manifest = json.loads(_read(root, "research/output.json", 2_000_000))
    facts = json.loads(_read(root, "research/facts.json", 2_000_000))
    entries = manifest.get("artifacts")
    require(
        isinstance(entries, list) and len(entries) <= 1000,
        "Choose a bounded research artifact manifest.",
    )
    allowed = set(contract.ARTIFACTS)
    for source in facts.get("sources", []):
        for key in ("snapshot", "original_snapshot"):
            if source.get(key):
                require(
                    source[key].startswith("research/"),
                    "Research captures must belong to the declared bundle.",
                )
                allowed.add(source[key].removeprefix("research/"))
    require(
        {e.get("file") for e in entries} == allowed,
        "The research bundle contains unrelated or missing files.",
    )
    helper = contract.capability(Path(runtime) if runtime else contract.find_runtime())
    require(helper is not None, "Use an installed schema-2 Harness Research helper.")
    names = {".harness-research/synthesis.json", "research/output.json"}
    names.update("research/" + e["file"] for e in manifest["artifacts"])
    for source in facts.get("sources", []):
        names.update(source[k] for k in ("file", "original_file") if source.get(k))
    require(len(names) <= 1000, "This research handoff has too many files.")
    files = {}
    total = 0
    for name in sorted(names):
        raw = _read(root, name, TOTAL)
        total += len(raw)
        require(total <= TOTAL, "Choose a research handoff within 16 MB.")
        files[name] = raw
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
        files["research/" + n].decode("utf-8")
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


def validate_capture(raw, provenance):
    require(
        hashlib.sha256(raw).hexdigest() == provenance.get("verified_archive_sha256"),
        "The reviewed research handoff changed.",
    )
    with tempfile.TemporaryDirectory(prefix="infographic-research-read-") as temporary:
        root = Path(temporary)
        _unpack(raw, root)
        facts, manifest = contract.read_bundle(root / "research")
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
