"""Private release runtimes, without changing the person's shell configuration."""
from pathlib import Path
import json
import os
import shlex
import shutil
import sys


def assistant_target(home):
    """Honor a saved assistant first; otherwise reuse one CLI without provisioning it."""
    path = Path(os.environ.get('STUDIOS_CONFIG') or Path(home) / '.config/studios-config.json')
    try:
        value = json.loads(path.read_text())
        if isinstance(value, dict) and value.get('schema', 1) == 1:
            chosen = (value.get('assistant') or {}).get('agent')
            if chosen in ('codex', 'claude'):
                return chosen
    except (OSError, ValueError, AttributeError):
        pass
    return 'codex' if shutil.which('codex') or not shutil.which('claude') else 'claude'


def shell_path():
    executable = Path(sys.executable).absolute()
    # Installed versions retain their own runtimes, including after rollback.
    if executable.parent.name == 'bin' and executable.parent.parent.name == 'python':
        root = executable.parent.parent.parent
        if (root / 'platform').is_file() and (root / 'node/bin/node').is_file():
            paths = str(root / 'python/bin') + ':' + str(root / 'node/bin')
            return 'export PATH=' + shlex.quote(paths) + ':"$PATH"\n'
    return ''
