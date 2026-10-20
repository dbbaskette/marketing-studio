"""An offline inventory. No provider sign-in or paid job is started by a check."""
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from studio_core import runtime

from . import shared


def git_value(field):
    try:
        done = subprocess.run(['git', 'config', '--get', field], capture_output=True, text=True, timeout=5)
        return done.stdout.strip() if done.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def assistant():
    """Either assistant may be missing, but not both, nor the one setup uses."""
    values, problem = shared.read()
    chosen = None if problem else (values.get('assistant') or {}).get('agent')
    if chosen and chosen not in runtime.ASSISTANTS:
        return {'name': 'Assistant', 'ready': False, 'optional': False,
                'detail': 'Shared settings name an assistant these studios cannot use. Choose Claude Code or Codex in setup.'}
    agent = chosen or runtime.assistant_default()
    name = runtime.ASSISTANTS[agent]
    other = runtime.ASSISTANTS['claude' if agent == 'codex' else 'codex']
    if runtime.assistant_command(agent):
        detail = name + (' is chosen in shared settings.' if chosen else ' is used unless setup chooses another.')
    elif not any(runtime.assistant_command(found) for found in runtime.ASSISTANTS):
        detail = 'Neither assistant was found. Install Claude Code or Codex, then sign in.'
    elif chosen:
        detail = f'{name} is chosen in shared settings but was not found. Install it, or choose {other} in setup.'
    else:
        detail = f'{name}, which Marketing Studio was installed for, was not found. Install it, or choose {other} in setup.'
    return {'name': 'Assistant', 'ready': bool(runtime.assistant_command(agent)),
            'detail': detail, 'optional': False}


def check(google=False):
    items = [{'name': 'Python', 'ready': sys.version_info >= (3, 11),
              'detail': platform.python_version(), 'optional': False}]
    for binary, name, optional in [('git', 'Git', False), ('node', 'Node.js', False),
                                  ('claude', 'Claude Code', True), ('codex', 'Codex', True),
                                  ('gcloud', 'Google Cloud CLI', not google)]:
        found = runtime.assistant_command(binary) if binary in runtime.ASSISTANTS else shutil.which(binary)
        items.append({'name': name, 'ready': bool(found), 'detail': found or 'Not found', 'optional': optional})
    items.append(assistant())
    identity = bool(git_value('user.name') and git_value('user.email'))
    items.append({'name': 'Git identity', 'ready': identity, 'optional': False,
                  'detail': 'Configured' if identity else 'Set git config --global user.name and user.email.'})
    return {'checked_at': datetime.now(timezone.utc).isoformat(),
            'ready': all(item['ready'] or item['optional'] for item in items), 'items': items}
