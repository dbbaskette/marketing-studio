#!/usr/bin/env python3
"""Install a small managed Blog Studio runtime for local Codex/Claude Code."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import uuid

SOURCE_ROOT = Path(__file__).resolve().parents[1] / 'bootstrap/blog-studio'
TRUSTED_SOURCE = 'https://github.com/dbbaskette/blog-studio.git'


class InstallError(Exception):
    pass


def atomic_json(path, data):
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def replace_link(path, target):
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        temp.symlink_to(target, target_is_directory=True)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def same_link(path, target):
    return path.is_symlink() and Path(os.path.abspath(path.parent / os.readlink(path))) == target


def targets(home, agents, claude_config=None):
    home = Path(home).expanduser().resolve()
    claude = Path(claude_config).expanduser().resolve() if claude_config else home / '.claude'
    mapping = {'codex': home / '.agents/skills/blog-studio', 'claude': claude / 'skills/blog-studio'}
    selected = {name: mapping[name] for name in agents}
    if len(set(selected.values())) != len(selected):
        raise InstallError('Choose separate discovery folders for Codex and Claude Code.')
    return selected


def verify_package(source):
    source = Path(source).resolve()
    try:
        if (source / 'install-manifest.json').is_symlink():
            raise InstallError('The installer manifest must be a regular file.')
        manifest = json.loads((source / 'install-manifest.json').read_text())
        if manifest['schema'] != 1 or manifest['version'] not in ('1.0.0', '1.1.0', '1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.6.1', '1.7.0', '1.8.0'):
            raise InstallError('Unsupported installer package.')
        actual = {p.relative_to(source).as_posix() for p in source.rglob('*')
                  if p.is_file() and p.name not in ('install-manifest.json', 'config.json')
                  and '__pycache__' not in p.parts and p.suffix != '.pyc'}
        if actual != set(manifest['files']):
            raise InstallError('The installer package inventory is incomplete or changed.')
        for name, expected in manifest['files'].items():
            path = source / name
            if any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(source)):
                raise InstallError('Installer package folders must be regular directories.')
            if not path.resolve().is_relative_to(source) or path.is_symlink():
                raise InstallError('Installer package paths must be regular files.')
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise InstallError('Installer package verification failed. Download an intact bundle.')
        required = {'SKILL.md', 'scripts/sync_guidance.py', 'scripts/studio.py',
                    'scripts/text_checks.py', 'scripts/linkedin_import.py'}
        if manifest['version'] in ('1.1.0', '1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.6.1', '1.7.0', '1.8.0'):
            required.update({'scripts/hub.py', 'scripts/hub_store.py', 'scripts/hub_workspace.py'})
        if manifest['version'] in ('1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.6.1', '1.7.0', '1.8.0'):
            required.update({'scripts/experience.py', 'scripts/hub_browse.py'})
        if manifest['version'] in ('1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.6.1', '1.7.0', '1.8.0'):
            required.add('scripts/google_workflow.py')
        if manifest['version'] in ('1.4.0', '1.5.0', '1.6.0', '1.6.1', '1.7.0', '1.8.0'):
            required.add('scripts/google_drive.py')
        if manifest['version'] in ('1.5.0', '1.6.0', '1.6.1', '1.7.0', '1.8.0'):
            required.add('scripts/google_roundtrip.py')
        if manifest['version'] in ('1.7.0', '1.8.0'):
            required.update({'scripts/author_workflow.py', 'scripts/writing_defaults.py'})
        if manifest['version'] == '1.8.0':
            required.update({'scripts/performance.py', 'scripts/local_cache.py', 'scripts/local_reads.py'})
        if not required.issubset(actual):
            raise InstallError('Required runtime files are missing.')
        return manifest
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallError('The installer manifest could not be read.') from exc


def package_key(manifest):
    return manifest['version'] + '-' + hashlib.sha256(
        json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest()[:12]


def read_state(root):
    path = root / 'installation.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise InstallError('The installation record must not be a symlink.')
    try:
        if (root / 'versions').is_symlink():
            raise ValueError()
        state = json.loads(path.read_text())
        if not isinstance(state, dict) or state.get('schema') != 1 or not isinstance(state.get('targets'), dict):
            raise ValueError()
        for name in [state['version'], *state.get('history', [])]:
            version = Path(name)
            if (not version.is_absolute() or version.parent != root / 'versions'
                    or version.is_symlink()):
                raise ValueError()
        if any(not Path(name).is_absolute() for name in state['targets'].values()):
            raise ValueError()
        return state
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise InstallError('The installation record is invalid. Keep it for diagnosis.') from exc


def safe_destination(path, root):
    # A selected discovery parent may be absent; existing symlink parents are rejected.
    for parent in path.parents:
        if parent.is_symlink():
            raise InstallError('A discovery parent is a symlink. Choose an explicit real location.')
    if path == root or root.is_relative_to(path) or path.is_relative_to(root):
        raise InstallError('Managed runtime and discovery folders must be separate.')


@contextmanager
def installation_lock(root):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / '.install.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise InstallError('Another installer is running. Retry after it finishes.') from exc
    try:
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def verify_configuration(version, interpreter=None):
    try:
        path = version / 'config.json'
        if path.is_symlink():
            raise ValueError()
        config = json.loads(path.read_text())
        if (config['trusted_source'] != TRUSTED_SOURCE or config['runtime_version'] != verify_package(version)['version']
                or not Path(config['python']).is_absolute()
                or (interpreter is not None and config['python'] != str(interpreter))):
            raise ValueError()
        return config
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallError('Runtime configuration is invalid. Run repair with an intact installer bundle.') from exc


def smoke_runtime(version, interpreter):
    try:
        with tempfile.TemporaryDirectory(prefix='blog-studio-setup-') as temporary:
            workspace = Path(temporary) / 'disposable-workspace'
            calls = [('studio.py', '--root', str(workspace), 'init'),
                     ('text_checks.py', '--help'), ('linkedin_import.py', '--help')]
            if (version / 'scripts/hub.py').exists():
                calls.append(('hub.py', '--help'))
            for name, *arguments in calls:
                result = subprocess.run([str(interpreter), str(version / 'scripts' / name), *arguments],
                    capture_output=True, timeout=30)
                if result.returncode:
                    raise InstallError('The staged runtime did not pass its local helper check.')
            if not workspace.is_dir():
                raise InstallError('The staged runtime could not create a disposable workspace.')
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError('The selected Python could not run the local helpers. Choose a supported interpreter.') from exc


def stage_version(source, root, manifest, interpreter, repair=False):
    key = package_key(manifest)
    versions = root / 'versions'
    if versions.is_symlink():
        raise InstallError('Managed version storage must not be a symlink.')
    versions.mkdir(exist_ok=True)
    destination = versions / key
    if destination.exists() or destination.is_symlink():
        try:
            if destination.is_symlink():
                raise InstallError('A managed runtime was replaced by a symlink.')
            verify_package(destination)
            configuration = verify_configuration(destination)
            if configuration['python'] == str(interpreter):
                return destination
            key += '-' + hashlib.sha256(str(interpreter).encode()).hexdigest()[:8]
            destination = versions / key
            if destination.exists() or destination.is_symlink():
                if destination.is_symlink():
                    raise InstallError('A managed runtime was replaced by a symlink.')
                verify_package(destination)
                verify_configuration(destination, interpreter)
                return destination
        except InstallError:
            if not repair:
                raise
            # Repair stages a new intact runtime, preserving the damaged version for diagnosis.
            destination = versions / (key + '-repair-' + uuid.uuid4().hex[:8])
    stage = versions / ('.' + uuid.uuid4().hex)
    try:
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'config.json'))
        verify_package(stage)
        atomic_json(stage / 'config.json', {'python': str(interpreter), 'runtime_version': manifest['version'],
                   'trusted_source': TRUSTED_SOURCE})
        for name in manifest['files']:
            if name.endswith('.py'):
                compile((stage / name).read_text(), name, 'exec')
        smoke_runtime(stage, interpreter)
        os.replace(stage, destination)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def install(source, root, selected, interpreter=sys.executable, replace=False, activate=replace_link, repair=False):
    source = Path(source).resolve()
    root = Path(root).expanduser().absolute()
    if root.is_symlink():
        raise InstallError('The managed installation root must not be a symlink.')
    root = root.resolve()
    manifest = verify_package(source)
    for path in selected.values():
        safe_destination(path, root)
    with installation_lock(root):
        state = read_state(root)
        current = root / 'current'
        if current.exists() and not current.is_symlink():
            raise InstallError('The managed current path is not a link. No changes were made.')
        if current.is_symlink() and state is None:
            raise InstallError('An existing runtime has no ownership record. No changes were made.')
        previous = Path(os.readlink(current)) if current.is_symlink() else None
        if previous and not previous.is_absolute():
            previous = current.parent / previous
        if previous and (not previous.is_relative_to(root / 'versions') or previous.is_symlink()):
            raise InstallError('The current runtime is outside managed version storage.')
        if previous and state is None:
            raise InstallError('An existing runtime has no ownership record. No changes were made.')
        if previous and state and not same_link(current, Path(state['version'])):
            raise InstallError('The active runtime no longer matches its ownership record.')
        all_targets = dict(selected)
        if state:
            for agent, name in state['targets'].items():
                path = Path(name)
                if same_link(path, current):
                    all_targets.setdefault(agent, path)
        replacements = []
        for path in all_targets.values():
            safe_destination(path, root)
            if path.exists() or path.is_symlink():
                if not same_link(path, current):
                    if not replace:
                        raise InstallError('An existing skill needs a backup before replacement. Review it and select --replace.')
                    replacements.append(path)
        version = stage_version(source, root, manifest, Path(interpreter).resolve(), repair=repair)
        changed = previous != version or any(not same_link(p, current) for p in all_targets.values())
        if not changed:
            return {'status': 'already-installed', 'version': version.name, 'targets': {k: str(v) for k, v in all_targets.items()}}
        backups = []
        linked = []
        try:
            for path in replacements:
                backup = path.with_name(path.name + '.before-blog-studio-' + uuid.uuid4().hex[:8])
                os.replace(path, backup)
                backups.append((path, backup))
            activate(current, version)
            for path in all_targets.values():
                if not same_link(path, current):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    linked.append(path)
                    activate(path, current)
            for path in all_targets.values():
                if not same_link(path, current) or not (path / 'SKILL.md').is_file():
                    raise InstallError('A harness discovery link could not be verified.')
            history = list((state or {}).get('history', []))
            if previous and previous != version:
                history.append(str(previous))
            saved = {'schema': 1, 'version': str(version), 'history': history,
                     'targets': {k: str(v) for k, v in all_targets.items()},
                     'backups': list((state or {}).get('backups', [])) +
                     [{'original': str(p), 'backup': str(b)} for p, b in backups]}
            atomic_json(root / 'installation.json', saved)
        except Exception:
            for path in reversed(linked):
                if same_link(path, current):
                    path.unlink()
            for path, backup in reversed(backups):
                if path.is_symlink():
                    path.unlink()
                os.replace(backup, path)
            if previous:
                replace_link(current, previous)
            elif current.is_symlink():
                current.unlink()
            raise
        return {'status': 'installed', 'version': version.name, 'targets': saved['targets'],
                'backups': saved['backups'], 'live_harness_discovery': 'not-yet-verified'}


def rollback(root):
    root = Path(root).resolve()
    with installation_lock(root):
        state = read_state(root)
        if not state or not state['history']:
            raise InstallError('There is no previous managed version to restore.')
        current = root / 'current'
        version = Path(state['history'][-1])
        if not version.is_relative_to(root / 'versions') or version.is_symlink():
            raise InstallError('The previous runtime is outside managed storage.')
        verify_package(version)
        verify_configuration(version)
        if not same_link(current, Path(state['version'])):
            raise InstallError('The active runtime no longer matches its ownership record.')
        previous = Path(state['version'])
        replace_link(current, version)
        try:
            state['history'] = state['history'][:-1] + [str(previous)]
            state['version'] = str(version)
            atomic_json(root / 'installation.json', state)
        except Exception:
            replace_link(current, previous)
            raise
        return {'status': 'rolled-back', 'version': version.name}


def uninstall(root, agents):
    root = Path(root).resolve()
    with installation_lock(root):
        state = read_state(root)
        if not state:
            return {'status': 'not-installed'}
        current = root / 'current'
        removed = []
        for agent in agents:
            if agent in state['targets']:
                path = Path(state['targets'][agent])
                if not same_link(path, current):
                    raise InstallError('A discovery link was changed outside the installer; it was preserved.')
        try:
            for agent in agents:
                if agent in state['targets']:
                    path = Path(state['targets'][agent])
                    path.unlink()
                    removed.append((agent, path))
            new_state = dict(state)
            new_state['targets'] = {k: v for k, v in state['targets'].items() if k not in agents}
            atomic_json(root / 'installation.json', new_state)
        except Exception:
            for _, path in removed:
                replace_link(path, current)
            raise
        return {'status': 'uninstalled', 'removed': [k for k, _ in removed],
                'retained': 'Author work, backups, runtime versions, caches, and shared tools.'}


def tool_status(check_remote=False):
    status = {'python': sys.version.split()[0], 'python_supported': sys.version_info >= (3, 11),
              'git': False, 'github_cli': bool(shutil.which('gh')), 'repository_access': 'not-checked'}
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    environment['GIT_TERMINAL_PROMPT'] = '0'
    try:
        status['git'] = subprocess.run(['git', '--version'], capture_output=True, timeout=10).returncode == 0
        if check_remote and status['git']:
            probe = subprocess.run(['git', 'ls-remote', TRUSTED_SOURCE, 'refs/heads/main'],
                capture_output=True, timeout=45, env=environment)
            status['repository_access'] = 'ready' if probe.returncode == 0 and probe.stdout.strip() else 'unavailable'
    except (OSError, subprocess.TimeoutExpired):
        if check_remote:
            status['repository_access'] = 'unavailable'
    status['codex_available'] = bool(shutil.which('codex')) or any(
        Path(p).exists() for p in ('/Applications/Codex.app', '/Applications/ChatGPT.app'))
    status['claude_code_available'] = bool(shutil.which('claude'))
    status['harness_note'] = 'Desktop Claude Code availability may need a manual check; Cowork is not this installation target.'
    return status


def ensure_repository_access(interactive=False):
    tools = tool_status(True)
    if tools['repository_access'] == 'ready':
        return tools
    if not interactive:
        return tools
    print('GitHub access to the private Blog Studio repository is not ready.')
    print('You need access to dbbaskette/blog-studio from your own GitHub account.')
    print('1. Use GitHub CLI browser sign-in and configure Git for github.com')
    print('2. Cancel and use an existing Git sign-in method')
    if input('Choose 1 or 2 [2]: ').strip() != '1':
        return tools
    if not shutil.which('gh'):
        if shutil.which('brew') and input('Install GitHub CLI with your existing Homebrew? [y/N]: ').strip().lower() in ('y', 'yes'):
            if subprocess.run(['brew', 'install', 'gh']).returncode:
                raise InstallError('GitHub CLI installation did not finish. Reopen setup when it is ready.')
        else:
            raise InstallError('Install GitHub CLI from https://cli.github.com/ and reopen setup, or configure Git with your existing credentials.')
    if subprocess.run(['gh', 'auth', 'login', '--hostname', 'github.com', '--git-protocol', 'https', '--web']).returncode:
        raise InstallError('GitHub sign-in did not finish. No skill installation was changed.')
    if subprocess.run(['gh', 'auth', 'setup-git', '--hostname', 'github.com']).returncode:
        raise InstallError('GitHub Git authentication setup did not finish.')
    return tool_status(True)


def inspect(root, selected, online=False):
    root = Path(root).resolve()
    state = read_state(root)
    result = {'tools': tool_status(online), 'targets': {k: {'path': str(p),
        'managed_link': same_link(p, root / 'current'), 'skill_present': (p / 'SKILL.md').is_file()}
        for k, p in selected.items()}, 'installation': 'absent' if not state else 'recorded',
        'live_harness_discovery': 'Verify inside a new local harness session.'}
    if state:
        try:
            if not same_link(root / 'current', Path(state['version'])):
                raise InstallError('Current runtime link does not match its installation record.')
            verify_package(Path(state['version']))
            verify_configuration(Path(state['version']))
            result['runtime_integrity'] = 'verified'
        except (InstallError, OSError) as exc:
            result['runtime_integrity'] = str(exc)
    return result


def setup_summary(result):
    """Human setup status; placement and executable detection are not discovery."""
    tools = result['tools']
    lines = ['Blog Studio setup check']
    lines.append('Python: ' + tools['python'] + (' (supported)' if tools['python_supported'] else ' — install Python 3.11+ from https://www.python.org/downloads/macos/'))
    lines.append('Git: ' + ('available' if tools['git'] else 'install from https://git-scm.com/install/mac'))
    access = tools['repository_access']
    lines.append('Private repository: ' + {'ready': 'accessible with existing sign-in',
        'not-checked': 'not checked offline; network access is needed for new guidance'}.get(access,
        'access unavailable; confirm membership and GitHub sign-in, then retry setup'))
    verified = result.get('runtime_integrity') == 'verified'
    lines.append('Local runtime: ' + ('verified' if verified else result.get('runtime_integrity', 'not installed')))
    for agent, target in result['targets'].items():
        label = 'Codex' if agent == 'codex' else 'Claude Code'
        detected = tools['codex_available' if agent == 'codex' else 'claude_code_available']
        placed = target['managed_link'] and target['skill_present'] and verified
        lines.append(label + ': ' + ('managed files verified' if placed else 'setup or repair needed') + ' at ' + target['path'])
        if not detected:
            lines.append('  Install/open ' + label + ' before writing; automatic detection did not find it.')
        elif placed:
            invocation = '$blog-studio' if agent == 'codex' else '/blog-studio'
            lines.append('  Open a new local session and use ' + invocation + ' to verify discovery.')
    if result.get('planned_changes'):
        lines.append('Preview only: no installation changed. Run setup to install at the locations above.')
    elif not verified:
        lines.append('Next: reopen the trusted installer; use repair if an installation is damaged.')
    else:
        lines.append('Try: Help me build an outline from my notes. Stop at the outline.')
    lines.append('Drafts and voices stay in the author workspace. These checks do not prove live skill discovery.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('install', 'check', 'repair', 'rollback', 'uninstall'), default='install')
    parser.add_argument('--target', choices=('codex', 'claude', 'both'))
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--root', type=Path)
    parser.add_argument('--source', type=Path, default=SOURCE_ROOT)
    parser.add_argument('--google-docs', choices=('skip', 'connector', 'gcloud', 'gcloud-check'), default='skip', help='Optional Google setup; gcloud opens user sign-in, gcloud-check only reads Drive.')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--offline', action='store_true', help='Skip repository-access check; installation still needs Git/Python.')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        if not args.target and args.action == 'install' and not args.yes and not args.dry_run:
            print('Blog Studio setup\nWhere would you like to use it?\n1. Codex\n2. Claude Code\n3. Both')
            answer = input('Choose 1, 2, or 3 [3]: ').strip()
            if answer not in ('', '1', '2', '3'):
                raise InstallError('Choose 1, 2, or 3 and run setup again.')
            args.target = {'1': 'codex', '2': 'claude'}.get(answer, 'both')
        agents = ('codex', 'claude') if (args.target or 'both') == 'both' else (args.target,)
        root = (args.root or args.home / '.local/share/blog-studio').expanduser().absolute()
        selected = targets(args.home, agents, os.environ.get('CLAUDE_CONFIG_DIR') if args.home == Path.home() else None)
        if args.action == 'check' or args.dry_run:
            result = inspect(root, selected, online=not args.offline)
            if args.dry_run:
                result['planned_changes'] = {k: str(v) for k, v in selected.items()}
                result['package_verified'] = verify_package(args.source)['version']
            print(json.dumps(result, indent=2) if args.json else setup_summary(result))
            return 0
        if not args.yes:
            if args.action in ('install', 'repair'):
                readiness = tool_status(False)
                print('Python: ' + readiness['python'] + (' (supported)' if readiness['python_supported'] else ' (upgrade needed)'))
                print('Git: ' + ('available' if readiness['git'] else 'installation needed'))
                for agent in agents:
                    key = 'codex_available' if agent == 'codex' else 'claude_code_available'
                    print(agent + ': ' + ('detected' if readiness[key] else 'not detected; install/open your local harness before writing'))
                print('Private repository access will be verified before installation.')
            print('Selected skill locations:')
            for agent, path in selected.items():
                print(f'  {agent}: {path}')
            print('Existing shared links use one runtime. Author work stays in its workspace.')
            if input(f'Proceed with {args.action}? [y/N]: ').strip().lower() not in ('y', 'yes'):
                print('Setup cancelled. No installation was changed.')
                return 0
        if args.action in ('install', 'repair'):
            if 'codex' in agents:
                legacy = args.home / '.codex/skills/blog-studio'
                if legacy.exists() or legacy.is_symlink():
                    raise InstallError('Another Blog Studio skill exists in ~/.codex/skills. Move that folder to a backup outside the skill roots before installing, to avoid duplicate discovery.')
            tools = tool_status(False) if args.offline else ensure_repository_access(interactive=not args.yes)
            if not tools['python_supported']:
                raise InstallError('Python 3.11 or later is required. Install it from python.org and reopen setup.')
            if not tools['git']:
                raise InstallError('Git is required. Install it from git-scm.com and reopen setup.')
            if not args.offline and tools['repository_access'] != 'ready':
                raise InstallError('Private repository access is not ready. See docs/installation.md for sign-in help.')
            result = install(args.source, root, selected, replace=args.replace, repair=args.action == 'repair')
        elif args.action == 'rollback':
            result = rollback(root)
        else:
            result = uninstall(root, agents)
        if args.action in ('install', 'repair') and args.google_docs != 'skip':
            if args.offline:
                result['google'] = {'status': 'skipped-offline', 'next_step': 'Run installer/google-setup.sh --check when online.'}
            elif args.google_docs == 'connector':
                result['google'] = {'status': 'connector-selected', 'verified': False}
            else:
                helper = root / 'current/scripts/google_drive.py'
                action = 'check' if args.google_docs == 'gcloud-check' else 'login'
                if action == 'login' and (args.json or not sys.stdin.isatty()):
                    result['google'] = {'status': 'needs-interactive-login', 'next_step': 'Run installer/google-setup.sh --login in the VM shell.'}
                else:
                    if action == 'login':
                        print('Google user sign-in requests Drive access and changes the active gcloud account. No Cloud project or OAuth client is created.')
                    check = subprocess.run([sys.executable, str(helper), action], capture_output=action == 'check', text=True)
                    result['google'] = {'status': 'drive-read' if check.returncode == 0 else 'needs-setup',
                        'next_step': 'Use installer/google-setup.sh --install-cli, then --login. Drive read does not verify Docs writes.'}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print('Blog Studio: ' + result['status'].replace('-', ' ') + '.')
            if 'targets' in result:
                print('Skill files and runtime verified. Open a new local harness session to verify discovery.')
                for agent in result['targets']:
                    print('Codex: $blog-studio' if agent == 'codex' else 'Claude Code: /blog-studio')
                print('Try: Help me build an outline from my notes. Stop at the outline.')
                check_command = [sys.executable, str(Path(__file__).resolve()), 'check', '--target', args.target or 'both']
                if args.home != Path.home():
                    check_command += ['--home', str(args.home.absolute())]
                if args.root:
                    check_command += ['--root', str(args.root.absolute())]
                print('To check setup: ' + shlex.join(check_command))
            if result.get('google'):
                print('Google: ' + result['google']['status'])
                if result['google'].get('next_step'):
                    print(result['google']['next_step'])
            if result.get('retained'):
                print(result['retained'])
        return 0
    except (InstallError, OSError, ValueError, EOFError, KeyboardInterrupt) as exc:
        message = str(exc) if isinstance(exc, InstallError) else 'Setup could not finish. Check paths/permissions or reopen the launcher.'
        print('Blog Studio setup: ' + message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
