"""An offline inventory. No provider sign-in or paid job is started by a check."""
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def git_value(field):
    try:
        done = subprocess.run(['git', 'config', '--get', field], capture_output=True, text=True, timeout=5)
        return done.stdout.strip() if done.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def check(google=False):
    items = [{'name': 'Python', 'ready': sys.version_info >= (3, 11),
              'detail': platform.python_version(), 'optional': False}]
    for binary, name, optional in [('git', 'Git', False), ('node', 'Node.js', False),
                                  ('claude', 'Claude Code', True), ('codex', 'Codex', True),
                                  ('gcloud', 'Google Cloud CLI', not google)]:
        found = shutil.which(binary)
        items.append({'name': name, 'ready': bool(found), 'detail': found or 'Not found', 'optional': optional})
    identity = bool(git_value('user.name') and git_value('user.email'))
    items.append({'name': 'Git identity', 'ready': identity, 'optional': False,
                  'detail': 'Configured' if identity else 'Set git config --global user.name and user.email.'})
    return {'checked_at': datetime.now(timezone.utc).isoformat(),
            'ready': all(item['ready'] or item['optional'] for item in items), 'items': items}
