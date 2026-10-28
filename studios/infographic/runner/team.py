"""Explicit selected-file sharing in a separate owned clone. Never force or replay a push."""

from __future__ import annotations
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import secrets
import subprocess
from studio_core import studios_config
from . import exports
from .contracts import canonical, digest
from .validation import identifier, relative_path, require, validate_project
from .workspace import _atomic, _json, _read, data_root, file_lock

LIMIT = 128_000_000


def configuration():
    settings, problem = studios_config.read()
    require(
        not problem,
        "Restore valid shared settings before connecting a team repository.",
    )
    team = settings.get("team") or {}
    repository = team.get("repository")
    branch = team.get("branch") or "main"
    from studio_core.preferences import (
        repository as valid_repository,
        branch as valid_branch,
    )

    try:
        valid_repository(repository)
        valid_branch(branch)
    except ValueError as failure:
        require(False, str(failure))
    require(
        isinstance(repository, str)
        and len(repository) < 2000
        and not any(c.isspace() for c in repository)
        and (
            repository.startswith("https://")
            or re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+", repository)
            or Path(repository).is_absolute()
            and Path(repository).is_dir()
        ),
        "Configure a shared HTTPS/SSH repository first.",
    )
    require(
        isinstance(branch, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]{0,100}", branch)
        and ".." not in branch,
        "Choose a simple team branch.",
    )
    return repository, branch, settings


def root():
    repository, branch, _ = configuration()
    return (
        data_root() / "team" / digest({"repository": repository, "branch": branch})[:24]
    )


def git(folder, *args, check=True):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("GIT_")
        and k not in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    }
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1")
    options = [
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "protocol.ext.allow=never",
        "-c",
        "core.attributesFile=/dev/null",
    ]
    try:
        # Preserve existing Git credential helpers for an explicitly connected private repository.
        # Disable named content filters before any checkout/add; remote attributes cannot execute them.
        filters = subprocess.run(
            [
                "git",
                "-C",
                str(folder),
                "config",
                "--name-only",
                "--get-regexp",
                r"^filter\..*\.(clean|smudge|process|required)$",
            ],
            capture_output=True,
            timeout=10,
            env=env,
        )
        names = filters.stdout.decode().splitlines()
        require(
            len(names) <= 128
            and all(
                re.fullmatch(
                    r"filter\.[A-Za-z0-9._-]+\.(clean|smudge|process|required)", key
                )
                for key in names
            ),
            "Unsupported Git content filter configuration. No checkout or content filter was run.",
        )
        for key in names:
            options += ["-c", key + ("=false" if key.endswith(".required") else "=")]
        done = subprocess.run(
            ["git", *options, "-C", str(folder), *args],
            capture_output=True,
            timeout=60,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        raise ValueError(
            "Team Git could not finish. Local work and any unshared commit are kept."
        ) from None
    require(
        not check or done.returncode == 0,
        "Team Git could not finish. Check access, then sync explicitly; no forced push or reset was used.",
    )
    return done.stdout.decode("utf-8", "strict").strip()


def safe(folder, relative):
    require(relative_path(relative), "Use a safe shared inventory path.")
    path = folder
    for part in relative.split("/"):
        path = path / part
        require(not path.is_symlink(), "Shared paths cannot traverse links.")
    return path


def clean(folder):
    require(
        not git(folder, "status", "--porcelain", "--untracked-files=all"),
        "The private team clone has unfinished changes. Preserve and resolve them before another team action.",
    )


def connect(*, sync=False):
    folder = root()
    repository, branch, _ = configuration()
    with file_lock(data_root() / ".team.lock"):
        if not folder.exists():
            folder.mkdir(parents=True, mode=0o700)
            git(folder, "init", "--quiet", "--initial-branch=" + branch)
            git(folder, "remote", "add", "origin", repository)
        require(
            not folder.is_symlink()
            and git(folder, "remote", "get-url", "origin") == repository,
            "The team clone destination changed; preserve it and reconnect explicitly.",
        )
        clean(folder)
        git(folder, "fetch", "--no-tags", "origin", branch)
        remote = git(folder, "rev-parse", "FETCH_HEAD")
        head = git(folder, "rev-parse", "--verify", "HEAD", check=False)
        if not head:
            git(folder, "checkout", "--quiet", "-B", branch, remote)
        elif head != remote:
            # Never discard a failed push or merge another person's changes into an unseen inventory.
            ancestor = subprocess.run(
                ["git", "-C", str(folder), "merge-base", "--is-ancestor", head, remote],
                capture_output=True,
            )
            if ancestor.returncode == 0:
                git(folder, "merge", "--ff-only", "--no-edit", remote)
            else:
                raise ValueError(
                    "This clone has an unshared commit or a remote conflict. Its commit is kept; retry the pending share or resolve it explicitly."
                )
        return status()


def head(folder):
    return git(folder, "rev-parse", "HEAD")


def status():
    folder = root()
    if not folder.exists():
        return {"connected": False, "items": []}
    require(not folder.is_symlink(), "The private team clone cannot be a link.")
    found = []
    safe(folder, "infographics")
    for path in (folder / "infographics").glob("*/share.json"):
        try:
            safe(folder, path.relative_to(folder).as_posix())
            entry = _json(path.parent, "share.json", 2_000_000)
            require(
                isinstance(entry, dict)
                and identifier(entry.get("id"))
                and path.parent.name == entry["id"]
                and isinstance(entry.get("title"), str)
                and type(entry.get("editable")) is bool
                and isinstance(entry.get("files"), list)
                and len(entry["files"]) <= 2000,
                "Invalid shared item.",
            )
            claim = _json(path.parent, "claim.json", 10_000)
            require(
                isinstance(claim, dict)
                and claim.get("schema") == 1
                and identifier(claim.get("owner"))
                and identifier(claim.get("generation")),
                "Invalid shared driver claim.",
            )
            missing = []
            for item in entry["files"]:
                require(
                    isinstance(item, dict)
                    and relative_path(item.get("file"))
                    and isinstance(item.get("sha256"), str),
                    "Invalid shared file inventory.",
                )
                try:
                    require(
                        hashlib.sha256(
                            _read(path.parent, item["file"], LIMIT)
                        ).hexdigest()
                        == item["sha256"],
                        "Changed shared asset.",
                    )
                except ValueError:
                    missing.append(item["file"])
            unshared_sources = []
            unshared_assets = []
            if entry.get("editable"):
                project = _json(path.parent, "project.json")
                unshared_sources = [
                    s["id"]
                    for s in project["sources"]
                    if s["id"] not in entry.get("source_ids", [])
                ]
                unshared_assets = [
                    a["id"]
                    for a in project["assets"]
                    if a["id"] not in entry.get("asset_ids", [])
                ]
            found.append(
                {
                    **entry,
                    "claim": claim,
                    "missing": missing,
                    "unshared_sources": unshared_sources,
                    "unshared_assets": unshared_assets,
                }
            )
        except (ValueError, OSError, KeyError, TypeError):
            continue
    return {"connected": True, "head": head(folder), "items": found}


def inventory(
    store,
    ident,
    *,
    expected_revision,
    export_id,
    include_editable=False,
    source_ids=None,
    asset_ids=None,
):
    from .engine import Engine

    p = store.read(ident)
    store.expect(p, expected_revision)
    require(
        type(include_editable) is bool
        and isinstance(source_ids or [], list)
        and isinstance(asset_ids or [], list),
        "Choose an explicit sharing inventory.",
    )
    source_ids, asset_ids = source_ids or [], asset_ids or []
    require(
        set(source_ids) <= {s["id"] for s in p["sources"]}
        and set(asset_ids) <= {a["id"] for a in p["assets"]},
        "Share only named sources and artwork from this infographic.",
    )
    require(
        include_editable or not (source_ids or asset_ids),
        "Select editable project sharing before including private sources or artwork.",
    )
    delivery = next(
        (
            d
            for d in Engine(store).deliveries(ident)
            if d["id"] == export_id and d["approved_current"]
        ),
        None,
    )
    require(
        delivery,
        "Share only a delivery from the current approved and visually checked revision.",
    )
    files = {}
    for item in delivery["files"]:
        files["delivery/" + Path(item["file"]).name] = exports.read(
            store, ident, export_id, item["format"]
        )[1]
    files["README.md"] = (
        p["brief"]["title"]
        + "\n\nApproved local revision "
        + str(p["revision"])
        + ".\n"
    ).encode()
    if include_editable:
        draft = deepcopy(p)
        draft.update(approval=None, checks=[], attempts=[], image_briefs=[], exports=[])
        files["project.json"] = canonical(draft)
        for source in p["sources"]:
            if source["id"] not in source_ids:
                continue
            from .sources import read

            read(store, p, source)
            for key in ("file", "normalized_file"):
                if source.get(key):
                    files["editable/" + source[key]] = _read(
                        store._project(ident), source[key], 16_000_000
                    )
        for asset in p["assets"]:
            if asset["id"] in asset_ids:
                files["editable/" + asset["file"]] = store.read_asset(
                    ident, asset["id"]
                )[1]
    require(
        sum(len(b) for b in files.values()) <= LIMIT,
        "The selected sharing inventory exceeds 128 MB.",
    )
    items = [
        {"file": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for name, raw in sorted(files.items())
    ]
    public = {
        "id": ident,
        "title": p["brief"]["title"],
        "revision": p["revision"],
        "editable": include_editable,
        "files": items,
        "source_ids": source_ids,
        "asset_ids": asset_ids,
    }
    return public, files


def preview(store, ident, **selection):
    public, _ = inventory(store, ident, **selection)
    state = status()
    require(
        state["connected"],
        "Connect the configured team repository before previewing a share.",
    )
    return {
        **public,
        "inventory_digest": digest(public),
        "expected_head": state["head"],
        "expected_connection": digest(configuration()[:2]),
        "expected_claim": next(
            (i["claim"] for i in state["items"] if i["id"] == ident), None
        ),
    }


def identity(folder):
    _, _, settings = configuration()
    person = settings.get("person") or {}
    name = person.get("name")
    from .settings import native

    email = native().get("team_email") or git(
        folder, "config", "--get", "user.email", check=False
    )
    require(
        isinstance(name, str)
        and name.strip()
        and isinstance(email, str)
        and "@" in email
        and "\n" not in name + email,
        "Set your name in shared settings and your team Git email in Infographic Studio defaults before sharing.",
    )
    return name, email


def commit_push(folder, message, files, branch):
    name, email = identity(folder)
    git(folder, "add", "--", *files)
    if git(folder, "diff", "--cached", "--name-only"):
        git(
            folder,
            "-c",
            "user.name=" + name,
            "-c",
            "user.email=" + email,
            "commit",
            "--quiet",
            "-m",
            message,
        )
    git(folder, "push", "origin", "HEAD:refs/heads/" + branch)
    return head(folder)


def share(
    store,
    ident,
    *,
    expected_revision,
    export_id,
    include_editable=False,
    source_ids=None,
    asset_ids=None,
    inventory_digest,
    expected_head,
    expected_claim,
    expected_connection,
    confirm_private=False,
):
    require(
        type(confirm_private) is bool
        and (not (include_editable or source_ids or asset_ids) or confirm_private),
        "Confirm the exact private project/source/art inventory before sharing it.",
    )
    require(
        expected_connection == digest(configuration()[:2]),
        "The configured team destination changed. Preview this inventory again.",
    )
    public, files = inventory(
        store,
        ident,
        expected_revision=expected_revision,
        export_id=export_id,
        include_editable=include_editable,
        source_ids=source_ids,
        asset_ids=asset_ids,
    )
    require(
        digest(public) == inventory_digest,
        "The selected sharing inventory changed. Preview it again before sharing.",
    )
    folder = root()
    _, branch, _ = configuration()
    with file_lock(data_root() / ".team.lock"):
        clean(folder)
        identity(folder)
        require(
            head(folder) == expected_head,
            "The team clone changed. Preview a fresh sharing inventory.",
        )
        git(folder, "fetch", "--no-tags", "origin", branch)
        require(
            git(folder, "rev-parse", "FETCH_HEAD") == expected_head,
            "The team repository changed. Sync and review the current claim before sharing.",
        )
        path = safe(folder, "infographics/" + ident)
        current = (
            _json(path, "claim.json", 10_000)
            if (path / "claim.json").exists()
            else None
        )
        require(
            current == expected_claim
            and (current is None or current["owner"] == store.owner),
            "Someone else drives this shared infographic. Take over explicitly before sharing.",
        )
        claim = current or {
            "schema": 1,
            "owner": store.owner,
            "generation": secrets.token_hex(16),
        }
        # Replace only the previous declared inventory. Unrelated files are kept.
        old = _json(path, "share.json") if (path / "share.json").exists() else None
        if old:
            for item in old["files"]:
                require(
                    relative_path(item["file"]), "The old shared inventory is unsafe."
                )
                if item["file"] not in files:
                    old_path = safe(path, item["file"])
                    require(not old_path.is_symlink(), "Shared files cannot be links.")
                    old_path.unlink(missing_ok=True)
        for name, raw in files.items():
            _atomic(safe(path, name), raw)
        _atomic(path / "share.json", canonical(public))
        _atomic(path / "claim.json", canonical(claim))
        commit_push(
            folder,
            "Share approved Infographic Studio revision",
            [f"infographics/{ident}"],
            branch,
        )
    return {"shared": True, "id": ident, "revision": expected_revision}


def claim(store, ident, *, expected_head, expected_claim, new_owner=None):
    require(
        identifier(ident) and (new_owner is None or identifier(new_owner)),
        "Choose a supported shared infographic and owner identity.",
    )
    folder = root()
    _, branch, _ = configuration()
    with file_lock(data_root() / ".team.lock"):
        clean(folder)
        identity(folder)
        require(
            head(folder) == expected_head,
            "The team state changed. Sync before taking over.",
        )
        git(folder, "fetch", "--no-tags", "origin", branch)
        require(
            git(folder, "rev-parse", "FETCH_HEAD") == expected_head,
            "The remote claim changed. Sync before taking over.",
        )
        current = _json(folder / f"infographics/{ident}", "claim.json", 10_000)
        require(
            current == expected_claim,
            "The shared driver changed. Review their current claim.",
        )
        require(
            new_owner is None or current["owner"] == store.owner,
            "Only the current driver may hand over to a named owner. Take over explicitly first.",
        )
        changed = {
            "schema": 1,
            "owner": new_owner or store.owner,
            "generation": secrets.token_hex(16),
        }
        _atomic(safe(folder, f"infographics/{ident}/claim.json"), canonical(changed))
        commit_push(
            folder,
            "Change Infographic Studio shared driver",
            [f"infographics/{ident}/claim.json"],
            branch,
        )
    return changed


def take(store, ident, *, expected_head, expected_claim):
    folder = root()
    state = status()
    require(
        state["head"] == expected_head,
        "The shared copy changed. Review it before importing.",
    )
    shared = next((x for x in state["items"] if x["id"] == ident), None)
    require(
        shared
        and shared["editable"]
        and shared["claim"] == expected_claim
        and expected_claim["owner"] == store.owner,
        "Take over the shared driver explicitly before importing an editable copy.",
    )
    require(
        not shared["missing"],
        "The shared inventory has missing or changed files. Keep its existing delivery and request the complete copy.",
    )
    source = safe(folder, "infographics/" + ident)
    original = _json(source, "project.json")
    validate_project(original)
    p = deepcopy(original)
    p.update(
        id=ident,
        owner=store.owner,
        revision=0,
        approval=None,
        checks=[],
        attempts=[],
        image_briefs=[],
        exports=[],
    )
    # Missing unselected source/art bytes remain honest, and checks will refuse them.
    with store.locked():
        require(
            not store._project(ident).exists(),
            "A local copy already exists. Keep its work; importing does not overwrite it.",
        )
        for item in shared["files"]:
            if item["file"].startswith("editable/"):
                name = item["file"].removeprefix("editable/")
                require(
                    name.startswith(("sources/", "assets/")),
                    "Editable shared files must be selected sources or artwork.",
                )
                store.write_blob(p["id"], name, _read(source, item["file"], LIMIT))
        store._publish(p)
    return {
        "project": p,
        "shared_origin": ident,
        "missing_sources": [
            s["id"]
            for s in p["sources"]
            if not (store._project(p["id"]) / s["file"]).exists()
        ],
        "missing_assets": [
            a["id"]
            for a in p["assets"]
            if not (store._project(p["id"]) / a["file"]).exists()
        ],
    }


def retry_pending(*, expected_commit):
    folder = root()
    _, branch, _ = configuration()
    with file_lock(data_root() / ".team.lock"):
        clean(folder)
        require(
            head(folder) == expected_commit,
            "The pending shared commit changed. Review it before retrying.",
        )
        git(folder, "push", "origin", "HEAD:refs/heads/" + branch)
    return status()


def download(ident, kind):
    require(
        identifier(ident) and kind in exports.FORMATS,
        "Choose one shared delivery format.",
    )
    state = status()
    entry = next((i for i in state["items"] if i["id"] == ident), None)
    require(entry is not None, "Choose an available shared infographic.")
    name = "delivery/" + exports.FORMATS[kind][0]
    item = next((f for f in entry["files"] if f["file"] == name), None)
    require(item is not None, "That format is not in the declared shared inventory.")
    raw = _read(safe(root(), "infographics/" + ident), name, LIMIT)
    require(
        hashlib.sha256(raw).hexdigest() == item["sha256"],
        "The shared delivery changed. Sync a complete copy before downloading.",
    )
    return exports.FORMATS[kind][1], raw
