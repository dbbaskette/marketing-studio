"""Private release runtimes, without changing the person's shell configuration."""
from pathlib import Path
import json
import os
import shlex
import shutil
import subprocess
import sys


MINIMUM_PYTHON = (3, 11)
PYTHON_PROBE = 'import sys, tomllib; raise SystemExit(sys.version_info < (3, 11))'
PYTHONS = ('python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3',
           '/opt/homebrew/bin/python3', '/usr/local/bin/python3',
           '/Library/Frameworks/Python.framework/Versions/Current/bin/python3')


def supported_python(root):
    """Find an existing interpreter; never download, install or change shell settings."""
    def usable(path):
        try:
            result = subprocess.run([str(path), '-c', PYTHON_PROBE],
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=5)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    private = Path(root) / 'runtime/python/bin/python3'
    if private.is_file():
        return str(private) if usable(private) else None
    tried = set()
    for candidate in PYTHONS:
        path = shutil.which(candidate)
        if path and path not in tried:
            tried.add(path)
            if usable(path):
                return path
    uv = shutil.which('uv')
    if uv:
        try:
            result = subprocess.run([uv, 'python', 'find', '--offline',
                                     '--no-python-downloads', '--no-project', '--no-config',
                                     '>=3.11'], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=5)
            path = result.stdout.strip()
            if result.returncode == 0 and Path(path).is_absolute() and usable(path):
                return path
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            pass
    return None


def ensure_python(root, module=None):
    """Bootstrap before application imports, including under macOS's older Python."""
    if sys.version_info >= MINIMUM_PYTHON:
        return
    python = supported_python(root)
    if python is None:
        print('Marketing Studio requires Python 3.11 or newer. Open it with a supported '
              'Python interpreter, or use the matching Marketing Studio download with '
              'its private runtime.', file=sys.stderr)
        raise SystemExit(2)
    entry = ['-m', module] if module else [str(Path(sys.argv[0]).absolute())]
    os.execv(python, [python, *entry, *sys.argv[1:]])


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


# In the installer's order of preference.
ASSISTANTS = {'codex': 'Codex', 'claude': 'Claude Code'}
BUNDLED_CODEX = Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')


def assistant_command(agent):
    """Where an assistant's command is, or None. The ChatGPT app can carry Codex."""
    found = shutil.which(agent)
    if not found and agent == 'codex' and BUNDLED_CODEX.is_file():
        return str(BUNDLED_CODEX)
    return found


def assistant_default(data=None):
    """The assistant used when none is saved: the one Marketing Studio was installed for,
    else an installed assistant, else Claude Code. Nothing is installed or started."""
    data = Path(data or os.environ.get('MARKETING_STUDIO_DATA') or '~/.local/share/marketing-studio')
    try:
        target = json.loads((data.expanduser() / 'installation.json').read_text()).get('target')
    except (OSError, ValueError, AttributeError):
        target = None
    if target in ASSISTANTS:
        return target
    return next((agent for agent in ASSISTANTS if assistant_command(agent)), 'claude')


def shell_path():
    executable = Path(sys.executable).absolute()
    # Installed versions retain their own runtimes, including after rollback.
    if executable.parent.name == 'bin' and executable.parent.parent.name == 'python':
        root = executable.parent.parent.parent
        if (root / 'platform').is_file() and (root / 'node/bin/node').is_file():
            paths = str(root / 'python/bin') + ':' + str(root / 'node/bin')
            return 'export PATH=' + shlex.quote(paths) + ':"$PATH"\n'
    return ''
