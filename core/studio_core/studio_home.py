"""The parts of a studio's `home` module that the studios that build slides share: where a
studio keeps what belongs to this computer rather than to one piece of work.

Each studio's scripts/home.py keeps its own module and binds `NAMES` into it with
`studio_core.modules.bind`, so these functions read that module's names and every patch on
it. The studio module gives them:

    NAME            its folder name under ~/.local/share
    DATA_VARIABLE   the environment variable that overrides the data folder
    ITEMS           the registry's key for the work it remembers
    read_json       its own reader, which takes the value to give for a missing file
    datetime, timezone, Path
                    imported, as the functions here read them

and keeps what differs between studios: what a registry entry holds and how a remembered
folder is known to still hold work.
"""
from __future__ import annotations

import json
import os
import secrets


def data_root() -> Path:
    """The per-user data folder. The studio's DATA_VARIABLE overrides it, for tests and odd
    setups."""
    override = os.environ.get(DATA_VARIABLE)
    if override:
        return Path(override).expanduser()
    return Path.home() / '.local' / 'share' / NAME


def now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def alive(pid: int) -> bool:
    """True while a process with this number exists on this computer."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:  # it exists, and belongs to someone else
        return True
    return True


def write_json(path: Path, value) -> None:
    """Write JSON so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f'.{path.name}.pending-{secrets.token_hex(4)}')
    try:
        pending.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def registry_path() -> Path:
    return data_root() / 'registry.json'


def forget(root: Path) -> None:
    """Stop remembering the work at `root`. Never fails the command that calls it."""
    try:
        registry = read_json(registry_path(), {})
        kept = registry.get(ITEMS) if isinstance(registry, dict) else None
        if isinstance(kept, dict) and kept.pop(str(root), None) is not None:
            write_json(registry_path(), {'schema': 1, ITEMS: kept})
    except OSError:
        pass


NAMES = ('data_root', 'now', 'alive', 'write_json', 'registry_path', 'forget')
