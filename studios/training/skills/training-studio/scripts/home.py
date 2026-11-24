"""Where Training Studio keeps what belongs to this computer rather than to one training.

The data folder, the time stamp, the process test, the safe JSON writer and forgetting a
training are shared with Presentation Studio (`studio_core.studio_home`) and bound into this
module; what a remembered training holds and how a training directory is known stay here.
"""
from __future__ import annotations

# ruff: noqa: F821  names bound from studio_core.studio_home are unseen by a linter;
# the root test_studio_scripts checks the bound parts, and the suites call the rest.

import json
from datetime import datetime, timezone  # noqa: F401  read by the shared parts
from pathlib import Path

from studio_core import modules
from studio_core import studio_home as _shared

NAME = 'training-studio'
DATA_VARIABLE = 'TRAINING_STUDIO_DATA'   # the data folder, for tests and odd setups
ITEMS = 'trainings'                      # the registry's key
modules.bind(globals(), _shared, _shared.NAMES)


def read_json(path: Path, default):
    """A JSON file's content, or `default` if it is missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


# --- the registry of trainings on this computer ---------------------------------

def remember(root: Path, title: str, levels: list[str]) -> None:
    """Note that a training lives at `root`. Never fails the command that calls it."""
    try:
        registry = read_json(registry_path(), {})
        trainings = registry.get('trainings') if isinstance(registry, dict) else None
        trainings = trainings if isinstance(trainings, dict) else {}
        trainings[str(root)] = {'title': title, 'levels': levels, 'seen_at': now()}
        write_json(registry_path(), {'schema': 1, 'trainings': trainings})
    except OSError:
        pass


def trainings() -> list[dict]:
    """Every remembered training whose directory still holds one, newest first."""
    registry = read_json(registry_path(), {})
    found = registry.get('trainings') if isinstance(registry, dict) else None
    listed = []
    for path, entry in (found or {}).items():
        if (Path(path) / f'.{NAME}' / 'session.json').is_file():
            listed.append({'path': path, **entry})
    return sorted(listed, key=lambda item: item.get('seen_at', ''), reverse=True)
