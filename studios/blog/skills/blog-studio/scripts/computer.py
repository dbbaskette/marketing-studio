"""Read-only computer checks shared by setup, the start command and the page."""

from concurrent.futures import ThreadPoolExecutor
import json
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


def core(name):
    """A module of the shared studio core, or None where it cannot be loaded."""
    import importlib

    try:
        return importlib.import_module('studio_core.' + name)
    except ImportError:
        # Setup loads this module by path, before the skill scripts are on sys.path.
        here = str(Path(__file__).resolve().parent)
        sys.path.insert(0, here)
        try:
            return importlib.import_module('studio_core.' + name)
        except ImportError:
            return None
        finally:
            sys.path.remove(here)


def harness_research():
    """Whether Harness Research, with its checked research, is installed here. Research
    from your sites needs it: it is what saves pages only from under them."""
    research_contract = core('research_contract')
    return research_contract is not None and research_contract.snapshot() is not None


NETWORK_SECONDS = 4  # How long the look at each assistant's service may take.


def unreachable(hosts):
    """{host: why} for each of `hosts` this network does not let through, looked at side by
    side. Like the shared runner's ready(), it only opens a TLS connection: it sends no
    request and starts no assistant."""
    reachability = core('reachability')
    if reachability is None or not hosts:
        return {}

    def look(host):
        try:
            found = reachability.blocked(host, NETWORK_SECONDS)
        except Exception:  # A look that fails says nothing about the network.
            return None
        return reachability.why(host, found) if found else None

    with ThreadPoolExecutor(max_workers=len(hosts)) as pool:
        return {host: said for host, said in zip(hosts, pool.map(look, hosts), strict=True) if said}


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


def claude_signed_in(binary, seconds=4):
    """Whether Claude Code says it is signed in: True, False, or None when it could not be
    asked. It is asked as a writing step starts it, without another Claude session's
    environment, and it starts no job and sends no request of its own."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(('CLAUDE', 'ANTHROPIC'))}
    try:
        done = subprocess.run(
            [binary, 'auth', 'status', '--json'],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=seconds,
            env=env,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    try:
        found = json.loads(done.stdout).get('loggedIn')
    except (ValueError, AttributeError):
        found = None
    return found if isinstance(found, bool) else done.returncode == 0


def git_path():
    path = shutil.which('git')
    if path == '/usr/bin/git' and sys.platform == 'darwin':
        found = probe(['xcode-select', '-p'])
        if not found or found[0] != 0:
            return None  # Do not open Apple's developer-tools installation dialog.
    return path


def report(home=None, sign_in=True, network=False):
    """The read-only checks of this computer. `network` also looks at whether each
    assistant's service can be reached, a TLS connection that sends no request: the Status
    page and the check command ask for it; setup never does, since setup never uses the
    network."""
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
    claude_signed = claude_signed_in(claude) if claude and sign_in else None
    codex_signed = (
        bool(signed and signed[0] == 0 and 'not logged in' not in signed[1].lower())
        if codex and sign_in
        else None
    )
    # A signed-in assistant can still be out of reach: a network can block or intercept
    # one service and not another. Claude Code's sign-in is not checked here, so its
    # service is looked at whenever it is installed.
    reachability = core('reachability') if sign_in and network else None
    hosts = {}
    if reachability is not None:
        if codex and codex_signed:
            hosts['codex'] = reachability.codex_host(signed[1])
        if claude:
            hosts['claude'] = reachability.HOSTS['claude']
    blocked = unreachable(list(dict.fromkeys(hosts.values())))
    cut_off = {agent: blocked.get(host) for agent, host in hosts.items()}

    def other(agent):
        return 'Claude Code' if agent == 'codex' else 'Codex'

    def network_step(agent):
        return (
            'Try another network, or choose '
            + other(agent)
            + ' for new work under Settings → Writing preferences, then check again.'
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
    if codex and cut_off.get('codex'):
        add(
            'codex',
            'Codex',
            'action',
            'CLI found; signed in, but it cannot be used from this network: '
            + cut_off['codex']
            + '.',
            network_step('codex'),
        )
    elif codex:
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
    if claude and cut_off.get('claude'):
        add(
            'claude',
            'Claude Code',
            'action',
            'CLI found, but it cannot be used from this network: ' + cut_off['claude'] + '.',
            network_step('claude'),
        )
    elif claude:
        add(
            'claude',
            'Claude Code',
            'ready' if claude_signed else 'manual' if claude_signed is None else 'action',
            'CLI found; signed in.'
            if claude_signed
            else 'CLI found; sign-in was not checked.'
            if claude_signed is None
            else 'CLI found, but it is not signed in.',
            ''
            if claude_signed
            else 'Run claude auth login in a terminal, then check again.'
            if claude_signed is False
            else 'Run claude once and sign in if asked.',
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
    researching = harness_research()
    add(
        'research',
        'Harness Research (optional)',
        'ready' if researching else 'optional',
        'Harness Research is installed: research is checked independently and keeps to your sites.'
        if researching
        else 'Harness Research is not installed. Research from your sites needs it; research '
        'from your documents or the public web does not.',
        ''
        if researching
        else 'Install Blog Studio or Marketing Studio again from its download, which includes '
        'Harness Research, then check again.',
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
        'Shared studios settings',
        'manual' if problem else 'ready',
        problem
        or (
            'Shared settings loaded from studios-config.json.'
            if shared
            else 'No shared settings file; using built-in defaults.'
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
            'codex': {
                'installed': bool(codex),
                'signed_in': codex_signed,
                'reachable': None if 'codex' not in hosts else not cut_off['codex'],
            },
            'claude': {
                'installed': bool(claude),
                'signed_in': claude_signed,
                'reachable': None if 'claude' not in hosts else not cut_off['claude'],
            },
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
