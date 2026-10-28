"""Shared selections stay authoritative; native page/image defaults are separate leaves."""
from copy import deepcopy
from functools import lru_cache
import json
import os
from pathlib import Path
import re

from studio_core import runtime, studios_config

from .contracts import canonical, digest
from .validation import require, text
from .workspace import _atomic, _json, data_root, file_lock

FIELDS = {'gemini_model', 'renderer', 'google_account', 'google_folder', 'team_email'}


def native():
    root = data_root()
    if not root.exists():
        return {}
    path = root / 'preferences.json'
    if not path.exists() and not path.is_symlink():
        return {}
    saved = _json(root, 'preferences.json', 10_000)
    require(isinstance(saved, dict) and set(saved) <= FIELDS, 'Restore valid Infographic Studio preferences.')
    validate(saved)
    return saved


def validate(changes):
    require(isinstance(changes, dict) and set(changes) <= FIELDS, 'Choose only image-model and renderer defaults.')
    for key, value in changes.items():
        require(text(value, empty=True, limit=2000), 'Use bounded non-secret preference text.')
        if key in ('google_account','team_email') and value:
            from studio_core.google_api import account
            try: account(value)
            except ValueError as failure: require(False, str(failure))
        if key == 'google_folder' and value:
            from studio_core.google_api import identifier
            try: identifier(value)
            except ValueError as failure: require(False, str(failure))
        if key == 'gemini_model' and value:
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}', value) is not None, 'Use an explicit Gemini model ID.')
        if key == 'renderer' and value:
            require(Path(value).expanduser().is_absolute(), 'Name an explicitly installed renderer by absolute path.')


def save(changes, *, expected):
    validate(changes)
    changes = {key: str(Path(value).expanduser()) if key == 'renderer' and value else value for key, value in changes.items()}
    with file_lock(data_root() / 'preferences.lock'):
        current = native()
        require(expected == digest(current), 'Infographic Studio preferences changed. Reload this form before saving.')
        changed = {**current, **changes}
        _atomic(data_root() / 'preferences.json', canonical(changed))
        return snapshot()


def snapshot():
    shared, problem = studios_config.read()
    require(not problem, 'Restore valid shared settings before starting provider work.')
    assistant = shared.get('assistant', {})
    require(isinstance(assistant, dict) and all(isinstance(shared.get(key, {}), dict) for key in ('person', 'brand')),
            'Restore valid shared assistant, person and brand sections before starting provider work.')
    agent = assistant.get('agent') or runtime.assistant_default()
    require(agent in ('codex', 'claude'), 'Choose Codex or Claude Code in shared settings.')
    from studio_core.preferences import EFFORTS
    model, effort = assistant.get('model'), assistant.get('effort')
    require(model is None or text(model, limit=200) and not model.startswith('-') and '\n' not in model,
            'Choose a bounded model ID in shared settings.')
    require(effort is None or effort in EFFORTS[agent], 'Choose an effort supported by the shared assistant.')
    local = native()
    return {'assistant': {'agent': agent, 'model': assistant.get('model'), 'effort': assistant.get('effort')},
            'person': deepcopy(shared.get('person') or {}), 'brand': deepcopy(shared.get('brand') or {}),
            'native': local, 'native_revision': digest(local),
            'delivery_default': 'google' if shared.get('output') == 'google' else 'pdf',
            'google': {'account': local.get('google_account') or None, 'folder': local.get('google_folder') or ''},
            'material_folders': {key: str(Path((shared.get('local') or {}).get('root') or '~/Studios').expanduser() / (key+'-workspace') / folder) for key,folder in (('blog','blogs'),('presentation','presentations'),('training','trainings'))},
            'renderer': os.environ.get('INFOGRAPHIC_STUDIO_RENDERER') or local.get('renderer') or packaged_renderer(),
            'image_provider': 'codex' if agent == 'codex' else 'gemini'}


def packaged_renderer():
    root = Path(__file__).resolve().parents[1] / 'renderer'
    if not root.exists():
        # Source checkout / unpacked prepared bundle, before native install.
        root = Path(__file__).resolve().parents[3] / 'runtime/renderer'
    marker = root / 'renderer.json'
    if not marker.is_file(): return None
    from .workspace import _read
    from .validation import relative_path
    import hashlib
    record = json.loads(_read(root, 'renderer.json', 10_000))
    require(record.get('schema') == 1 and relative_path(record.get('executable')), 'Restore a valid packaged renderer record.')
    executable = root / record['executable']
    st = executable.stat()
    _verified_renderer(str(root), record['executable'], record.get('sha256'), st.st_ino, st.st_size, st.st_mtime_ns)
    return str(executable)


@lru_cache(maxsize=4)
def _verified_renderer(root, relative, expected, inode, size, modified):
    from .workspace import _read
    import hashlib
    raw = _read(Path(root), relative, 300_000_000)
    require(hashlib.sha256(raw).hexdigest() == expected, "The packaged renderer executable changed. Reinstall the exact bundle.")
