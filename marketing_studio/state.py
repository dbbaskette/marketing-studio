"""Only launcher preferences live here; shared settings have their own source."""
import json
import os
import secrets
from pathlib import Path

from .errors import WorkspaceError


def data_root():
    return Path(os.environ.get('MARKETING_STUDIO_DATA', '~/.local/share/marketing-studio')).expanduser()


def read():
    target = data_root() / 'home.json'
    try:
        result = json.loads(target.read_text())
        if not isinstance(result, dict) or result.get('schema') != 1:
            raise ValueError()
        if not isinstance(result.get('paths', {}), dict) or type(result.get('done', False)) is not bool:
            raise ValueError()
        return result
    except FileNotFoundError:
        return {'schema': 1, 'done': False, 'paths': {}}
    except (ValueError, OSError) as exc:
        raise WorkspaceError('Marketing Studio preferences could not be read. Keep home.json for diagnosis and restore a valid copy.') from exc


def save(value):
    target = data_root() / 'home.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_name('.home-' + secrets.token_hex(6))
    try:
        with pending.open('x') as stream:
            os.chmod(pending, 0o600)
            json.dump(value, stream, indent=2)
            stream.write('\n')
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)
    return value
