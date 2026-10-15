"""Read-only computer checks shared by setup, the start command and the page."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

BUNDLED_CODEX = Path(
    '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'
)


def cli_path(name):
    return shutil.which(name) or (
        str(BUNDLED_CODEX) if name == 'codex' and BUNDLED_CODEX.is_file() else None
    )


def probe(command, cwd=None):
    try:
        done = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=4,
            cwd=cwd,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
        )
        return done.returncode, (done.stdout or done.stderr).strip()
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None


def git_path():
    path = shutil.which('git')
    if path == '/usr/bin/git' and sys.platform == 'darwin':
        found = probe(['xcode-select', '-p'])
        if not found or found[0] != 0:
            return None  # Do not open Apple's developer-tools installation dialog.
    return path


def report(home=None, sign_in=True):
    home = Path(home or Path.home())
    codex, claude, git, gh = cli_path('codex'), cli_path('claude'), git_path(), shutil.which('gh')
    commands = {'python3': ['python3', '--version']}
    if codex and sign_in:
        commands['codex-login'] = [codex, 'login', 'status']
    if git:
        commands.update({key: [git, 'config', '--get', 'user.' + key] for key in ('name', 'email')})
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = dict(
            zip(
                commands,
                pool.map(
                    lambda command: probe(command, home if home.is_dir() else None),
                    commands.values(),
                ),
                strict=True,
            )
        )
    signed = values.get('codex-login')
    codex_signed = (
        bool(signed and signed[0] == 0 and 'not logged in' not in signed[1].lower())
        if codex and sign_in
        else None
    )
    checks = []

    def add(key, label, status, detail, next_step='', optional=False):
        checks.append(
            dict(
                key=key,
                label=label,
                status=status,
                detail=detail,
                next_step=next_step,
                optional=optional,
            )
        )

    add('python', 'Python', 'ready', 'Using Python ' + sys.version.split()[0] + '.')
    if not codex and not claude:
        add(
            'assistant',
            'Writing assistant',
            'action',
            'No writing CLI was found.',
            'Install Codex or Claude Code, open it and sign in, then check again.',
        )
    if codex:
        login = 'codex' if shutil.which('codex') else shlex.quote(codex)
        add(
            'codex',
            'Codex',
            'ready' if codex_signed else 'manual' if codex_signed is None else 'action',
            'CLI found; signed in.'
            if codex_signed
            else 'CLI found; sign-in was not checked.'
            if codex_signed is None
            else 'CLI found; sign-in could not be confirmed.',
            ''
            if codex_signed
            else 'Run ' + login + ' login, then check again.'
            if codex_signed is False
            else 'Open Codex and sign in before starting a blog.',
        )
    if claude:
        add(
            'claude',
            'Claude Code',
            'manual',
            'CLI found. Its sign-in is checked when a writing step runs.',
            'Run claude once and sign in if asked.',
        )
    if not git or not gh:
        add(
            'hub',
            'Team Hub (optional)',
            'optional',
            'Git '
            + ('found' if git else 'not found')
            + '; GitHub CLI '
            + ('found.' if gh else 'not found.'),
            'To share with a Hub, install Git and GitHub CLI, then run gh auth login. Local writing needs neither.',
            True,
        )
    else:
        known = all(
            values.get(key) and values[key][0] == 0 and values[key][1] for key in ('name', 'email')
        )
        add(
            'hub',
            'Team Hub (optional)',
            'ready' if known else 'optional',
            'Git and GitHub CLI found. Git identity '
            + ('is configured.' if known else 'is incomplete.'),
            'Run gh auth status to check Hub access.'
            if known
            else 'Blog Studio records Hub saves with your Hub identity. Git name and email are only needed for commits you make yourself. Run gh auth status to check Hub access.',
            True,
        )
    known_identity = bool(git) and all(
        values.get(key) and values[key][0] == 0 and values[key][1] for key in ('name', 'email')
    )
    add(
        'team',
        'Studios repository (optional)',
        'ready' if known_identity else 'optional',
        'Git and a commit identity are ready.'
        if known_identity
        else 'Team sharing needs Git with your name and email configured.',
        ''
        if known_identity
        else 'Install Git if needed, then set user.name and user.email in your terminal. Repository access uses your existing Git credentials.',
        True,
    )
    # Setup loads this module by path before the skill scripts are on sys.path.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        'blog_computer_studios_config', Path(__file__).with_name('studios_config.py')
    )
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    shared, problem = config.read()
    add(
        'studios-config',
        'Shared studios defaults',
        'manual' if problem else 'ready',
        problem
        or (
            'Shared defaults loaded.'
            if shared
            else 'No shared defaults file; using this studio’s settings.'
        ),
    )
    path_python = values.get('python3')
    version = re.search(r'Python (\d+)\.(\d+)', path_python[1]) if path_python else None
    if version and tuple(map(int, version.groups())) < (3, 11):
        add(
            'python-path',
            'Python on your PATH',
            'manual',
            'The python3 command is older than 3.11.',
            'Nothing needs changing: the installed studio and blog commands find a supported Python themselves.',
        )
    return {
        'python': sys.version.split()[0],
        'agents': {
            'codex': {'installed': bool(codex), 'signed_in': codex_signed},
            'claude': {'installed': bool(claude), 'signed_in': None},
        },
        'checks': checks,
        'notes': [row['next_step'] for row in checks if row['next_step']],
    }


def describe(found):
    lines = ['Blog Studio · This computer']
    for row in found['checks']:
        lines.append(row['label'] + ': ' + row['detail'])
        if row['next_step']:
            lines.append('  ' + row['next_step'])
    return '\n'.join(lines)
