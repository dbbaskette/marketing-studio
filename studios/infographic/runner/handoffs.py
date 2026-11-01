"""Selected materials from a studio-owned folder; never bulk import a workspace."""

from pathlib import Path
import hashlib
import json
import os
from . import documents, intake, sources
from .validation import require, relative_path
from .workspace import _read

PRODUCTS = {
    "blog": ("Blog Studio", "blogs", "blog-studio"),
    "presentation": ("Presentation Studio", "presentations", "presentation-studio"),
    "training": ("Training Studio", "trainings", "training-studio"),
}


def folder(root, studio):
    require(
        studio in PRODUCTS,
        "Choose Blog Studio, Presentation Studio or Training Studio.",
    )
    product, name, tool = PRODUCTS[studio]
    require(isinstance(root, (str, os.PathLike)) and str(root).strip(),
            f"Give the folder that holds {product}'s materials.")
    root = Path(root).expanduser()
    require(root.is_absolute(), f"Give the full path of {product}'s materials folder, starting with / or ~.")
    require(
        not any(p.is_symlink() for p in (root, *root.parents)),
        f"{root} reaches {product}'s materials through a link. Choose the folder itself.",
    )
    # Say which folder and studio, and where to look, rather than a missing internal file.
    require(root.is_dir(), f"No {product} materials folder was found at {root}. "
                           f"Check {product}'s workspace in shared settings.")
    require((root / "hub.json").is_file(), f"{root} is not a {product} materials folder: it has no "
                                           f"hub.json. Check {product}'s workspace in shared settings.")
    marker = json.loads(_read(root, "hub.json", 10_000))
    require(
        marker.get("tool") == tool
        and marker.get("schema") == 1
        and marker.get("folder") == root.name,
        "This folder is not a supported studio-owned materials folder (hub.json).",
    )
    return root


def inventory(root, studio):
    root = folder(root, studio)
    found = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and not (base / d).is_symlink()
            and d not in ("sources", "work", "node_modules")
        ]
        for name in sorted(files):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if (
                path.suffix.lower() not in sources.KINDS
                or any(p.startswith(".") for p in path.relative_to(root).parts)
                or len(path.relative_to(root).parts) < 2
            ):
                continue
            try:
                raw = _read(root, relative, 16_000_000)
            except ValueError:
                continue
            found.append(
                {
                    "file": relative,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
            require(
                len(found) <= 1000,
                "This workspace has too many candidate files. Select a smaller owned folder.",
            )
    return {"studio": studio, "root": str(root), "files": found}


def prepare(root, studio, file, expected_sha256):
    root = folder(root, studio)
    require(
        relative_path(file)
        and len(Path(file).parts) >= 2
        and not any(
            p.startswith(".") or p in ("sources", "work", "node_modules")
            for p in Path(file).parts
        ),
        "Choose one visible material from the selected studio inventory.",
    )
    suffix = Path(file).suffix.lower()
    require(suffix in sources.KINDS, "Choose a readable supported studio material.")
    raw = _read(root, file, 16_000_000)
    require(
        hashlib.sha256(raw).hexdigest() == expected_sha256,
        "The originating studio material changed. Review its fresh inventory before import.",
    )
    kind = sources.KINDS[suffix]
    require(
        kind != "csv",
        "Import CSV with explicit row/column selection through file upload.",
    )
    extracted = (
        documents.extract(raw, kind)
        if kind in ("pdf", "docx", "html")
        else {
            "text": sources.decoded(raw),
            "extractor": "selected-studio-text-v1",
            "locations": [],
            "warnings": [],
            "readable": True,
        }
    )
    return intake.prepare(
        raw,
        kind="handoff",
        name=Path(file).name,
        extracted=extracted,
        provenance={
            "studio": PRODUCTS[studio][0],
            "item": Path(file).parts[0],
            "file": file,
            "origin_sha256": expected_sha256,
        },
    )
