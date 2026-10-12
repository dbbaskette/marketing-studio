#!/usr/bin/env python3
"""Install the complete Blog Studio skill for local Codex and Claude Code.

The skill folder beside this installer is copied into a verified, versioned
directory. Harness skill folders are links to it, so an update or rollback is
one atomic link switch. Nothing is downloaded and no account is needed.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid

try:
    import fcntl
except ImportError:  # Windows is not a supported installation target.
    fcntl = None

SOURCE_ROOT = Path(__file__).resolve().parents[1] / 'skills/blog-studio'
MANIFEST = 'install-manifest.json'
GENERATED = (MANIFEST, 'config.json')
REQUIRED = {'SKILL.md', 'scripts/studio.py'}
VERSION_RE = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+')
MINIMUM_PYTHON = (3, 11)
PYTHON_PROBE = 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'
LABELS = {'codex': 'Codex', 'claude': 'Claude Code'}


class InstallError(Exception):
    pass


class ReplaceRequired(InstallError):
    """Existing unmanaged folders need the user's consent before they are moved."""

    def __init__(self, paths):
        self.paths = list(paths)
        super().__init__(
            'An existing skill folder needs a backup before replacement. Review it and select --replace.'
        )


class Interrupted(BaseException):
    """A termination signal; lets the installer undo a half-finished switch."""


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


def link_target(path):
    """Where a link points, as an absolute path, without following further links."""
    return Path(os.path.abspath(path.parent / os.readlink(path)))


def same_link(path, target):
    return path.is_symlink() and link_target(path) == target


def targets(home, agents, claude_config=None):
    home = Path(home).expanduser().resolve()
    claude = Path(claude_config).expanduser().resolve() if claude_config else home / '.claude'
    mapping = {
        'codex': home / '.agents/skills/blog-studio',
        'claude': claude / 'skills/blog-studio',
    }
    selected = {name: mapping[name] for name in agents}
    if len(set(selected.values())) != len(selected):
        raise InstallError('Choose separate discovery folders for Codex and Claude Code.')
    return selected


def packaged(relative):
    """One inventory rule for build, install and checks.

    Dotfiles (Finder's .DS_Store), bytecode and the two files setup writes are
    local state, not package content.
    """
    return (
        not any(part.startswith('.') or part == '__pycache__' for part in relative.parts)
        and relative.suffix != '.pyc'
        and relative.name not in GENERATED
    )


def ignore_local(directory, names):
    return [name for name in names if not packaged(Path(name))]


def inventory(root):
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob('*')
        if p.is_file() and packaged(p.relative_to(root))
    )


def reject_links(root):
    for path in root.rglob('*'):
        if path.is_symlink() and packaged(path.relative_to(root)):
            raise InstallError('Package files and folders must be regular, not links.')


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_version(source):
    try:
        value = (source / 'VERSION').read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise InstallError('The skill folder has no VERSION file.') from exc
    if not VERSION_RE.fullmatch(value):
        raise InstallError('The skill VERSION is not a release number.')
    return value


def package_manifest(source):
    """Describe a skill folder. Released ZIPs carry this file; a checkout computes it."""
    source = Path(source).resolve()
    reject_links(source)
    return {
        'schema': 1,
        'version': read_version(source),
        'files': {name: file_hash(source / name) for name in inventory(source)},
    }


def verify_package(source):
    """Check a package, or an installed version of any release, against its own manifest.

    Completeness comes from the inventory and hashes, not from a list of known
    releases, so every intact version this installer ever placed stays usable.
    """
    source = Path(source).resolve()
    try:
        path = source / MANIFEST
        if path.is_symlink():
            raise InstallError('The package manifest must be a regular file.')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if (
            not isinstance(manifest, dict)
            or manifest.get('schema') != 1
            or not isinstance(manifest.get('files'), dict)
            or not isinstance(manifest.get('version'), str)
            or not VERSION_RE.fullmatch(manifest['version'])
        ):
            raise InstallError('The package manifest is not supported.')
        reject_links(source)
        if set(inventory(source)) != set(manifest['files']):
            raise InstallError('The package inventory is incomplete or changed.')
        for name, expected in manifest['files'].items():
            if file_hash(source / name) != expected:
                raise InstallError('A package file does not match its recorded hash.')
        if not REQUIRED.issubset(manifest['files']):
            raise InstallError('Required skill files are missing.')
        if 'VERSION' in manifest['files'] and read_version(source) != manifest['version']:
            raise InstallError('The package version does not match its manifest.')
        return manifest
    except (OSError, ValueError, TypeError) as exc:
        raise InstallError('The package manifest could not be read.') from exc


def source_manifest(source):
    source = Path(source).resolve()
    if not (source / 'SKILL.md').is_file():
        raise InstallError(
            'The skill folder is missing. Keep the expanded download together and run setup from it.'
        )
    if (source / MANIFEST).exists() or (source / MANIFEST).is_symlink():
        return verify_package(source)
    manifest = package_manifest(source)
    if not REQUIRED.issubset(manifest['files']):
        raise InstallError('Required skill files are missing.')
    return manifest


def package_key(manifest):
    return (
        manifest['version']
        + '-'
        + hashlib.sha256(json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest()[:12]
    )


def read_state(root):
    path = root / 'installation.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise InstallError('The installation record must not be a symlink.')
    try:
        if (root / 'versions').is_symlink():
            raise ValueError()
        state = json.loads(path.read_text(encoding='utf-8'))
        if (
            not isinstance(state, dict)
            or state.get('schema') != 1
            or not isinstance(state.get('targets'), dict)
        ):
            raise ValueError()
        for name in [state['version'], *state.get('history', [])]:
            version = Path(name)
            if (
                not version.is_absolute()
                or version.parent != root / 'versions'
                or version.is_symlink()
            ):
                raise ValueError()
        if any(not Path(name).is_absolute() for name in state['targets'].values()):
            raise ValueError()
        return state
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise InstallError('The installation record is invalid. Keep it for diagnosis.') from exc


def recorded_targets(root):
    """Targets chosen at the last install; None when there is no usable record."""
    try:
        state = read_state(Path(root).expanduser().absolute())
    except InstallError:
        return None
    if not state or not state['targets']:
        return None
    return {
        agent: Path(path) for agent, path in state['targets'].items() if agent in LABELS
    } or None


def safe_destination(path, root):
    # A selected discovery parent may be absent; existing symlink parents are rejected.
    for parent in path.parents:
        if parent.is_symlink():
            raise InstallError('A discovery parent is a symlink. Choose an explicit real location.')
    if path == root or root.is_relative_to(path) or path.is_relative_to(root):
        raise InstallError('Managed runtime and discovery folders must be separate.')


@contextmanager
def installation_lock(root):
    """Hold an OS lock that ends with the process, so a crash can never block the next run."""
    if fcntl is None:
        raise InstallError('This installer supports macOS and Linux.')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(
            root / '.install.lock', os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600
        )
    except OSError as exc:
        raise InstallError(
            'The installation lock could not be opened. Check folder permissions.'
        ) from exc
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise InstallError('Another installer is running. Retry after it finishes.') from exc
        yield
    finally:
        os.close(fd)


def stable_interpreter(path):
    """A path that survives patch upgrades: never resolved into a versioned Homebrew Cellar."""
    path = Path(os.path.abspath(os.fspath(path)))
    parts = path.parts
    if 'Cellar' in parts and len(parts) > parts.index('Cellar') + 2:
        index = parts.index('Cellar')
        alias = Path(*parts[:index], 'opt', parts[index + 1], 'bin', path.name)
        if alias.exists():
            return alias
    return path


def interpreter_works(path):
    try:
        path = Path(path)
        if not path.is_absolute() or not path.is_file():
            return False
        return (
            subprocess.run(
                [str(path), '-c', PYTHON_PROBE], capture_output=True, timeout=30
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def verify_configuration(version, manifest=None):
    try:
        path = version / 'config.json'
        if path.is_symlink():
            raise ValueError()
        config = json.loads(path.read_text(encoding='utf-8'))
        manifest = manifest or verify_package(version)
        if (
            not isinstance(config, dict)
            or config['runtime_version'] != manifest['version']
            or not isinstance(config['python'], str)
            or not Path(config['python']).is_absolute()
        ):
            raise ValueError()
        return config
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallError(
            'Runtime configuration is invalid. Run repair from the installer.'
        ) from exc


def configure(version, manifest, interpreter, explicit=False):
    """Record the helper interpreter. Keep a working one; replace a missing or broken one."""
    kept = {}
    try:
        kept = verify_configuration(version, manifest)
        if kept['python'] == str(interpreter) or (
            not explicit and interpreter_works(kept['python'])
        ):
            return False
    except InstallError:
        kept = {}
    if not interpreter_works(interpreter):
        raise InstallError(
            'The selected Python could not run the local helpers. Use Python 3.11 or later.'
        )
    atomic_json(
        version / 'config.json',
        {**kept, 'python': str(interpreter), 'runtime_version': manifest['version']},
    )
    return True


def smoke_runtime(version, interpreter):
    try:
        with tempfile.TemporaryDirectory(prefix='blog-studio-setup-') as temporary:
            workspace = Path(temporary) / 'disposable-workspace'
            calls = [
                ('studio.py', '--root', str(workspace), 'init'),
                ('text_checks.py', '--help'),
                ('linkedin_import.py', '--help'),
                ('hub.py', '--help'),
            ]
            for name, *arguments in calls:
                if not (version / 'scripts' / name).exists():
                    continue
                result = subprocess.run(
                    [str(interpreter), str(version / 'scripts' / name), *arguments],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode:
                    raise InstallError('The staged runtime did not pass its local helper check.')
            if not workspace.is_dir():
                raise InstallError('The staged runtime could not create a disposable workspace.')
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(
            'The selected Python could not run the local helpers. Use Python 3.11 or later.'
        ) from exc


def intact(version, manifest=None):
    """True for a real managed directory whose files match its (or the given) manifest."""
    try:
        if version is None or version.is_symlink() or not version.is_dir():
            return False
        found = verify_package(version)
        return manifest is None or (found['version'], found['files']) == (
            manifest['version'],
            manifest['files'],
        )
    except InstallError:
        return False


def stage_version(source, root, manifest, interpreter, active=None):
    """Return an intact copy of this package in managed storage, staging one if needed."""
    versions = root / 'versions'
    if versions.is_symlink():
        raise InstallError('Managed version storage must not be a symlink.')
    versions.mkdir(exist_ok=True)
    key = package_key(manifest)
    destination = versions / key
    for candidate in (destination, active):
        if intact(candidate, manifest):
            return candidate, False
    if destination.exists() or destination.is_symlink():
        # A damaged copy stays for diagnosis; a clean one is staged beside it.
        destination = versions / (key + '-repair-' + uuid.uuid4().hex[:8])
    stage = versions / ('.' + uuid.uuid4().hex)
    try:
        shutil.copytree(source, stage, ignore=ignore_local)
        atomic_json(stage / MANIFEST, manifest)
        verify_package(stage)
        atomic_json(
            stage / 'config.json',
            {'python': str(interpreter), 'runtime_version': manifest['version']},
        )
        for name in manifest['files']:
            if name.endswith('.py'):
                compile((stage / name).read_text(encoding='utf-8'), name, 'exec')
        smoke_runtime(stage, interpreter)
        os.replace(stage, destination)
        return destination, True
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def backup_path(root, path):
    """Backups live with the managed runtime, never inside a harness skill folder."""
    label = '-'.join(part.lstrip('.') for part in path.parts[-3:])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return root / 'backups' / (stamp + '-' + label + '-' + uuid.uuid4().hex[:8])


def install(
    source,
    root,
    selected,
    interpreter=None,
    replace=False,
    activate=replace_link,
    repair=False,
    legacy=(),
):
    """Install or update; `repair` is the same operation and is kept as a familiar verb."""
    source = Path(source).resolve()
    root = Path(root).expanduser().absolute()
    if root.is_symlink():
        raise InstallError('The managed installation root must not be a symlink.')
    root = root.resolve()
    manifest = source_manifest(source)
    explicit = interpreter is not None
    interpreter = stable_interpreter(interpreter or sys.executable)
    for path in selected.values():
        safe_destination(path, root)
    with installation_lock(root):
        state = read_state(root)
        current = root / 'current'
        if current.exists() and not current.is_symlink():
            raise InstallError('The managed current path is not a link. No changes were made.')
        original = link_target(current) if current.is_symlink() else None
        if original is not None and original.parent != root / 'versions':
            raise InstallError(
                'The current runtime is outside managed version storage. No changes were made.'
            )
        recorded = Path(state['version']) if state else None
        # An interrupted earlier run can leave `current` ahead of the record.
        # A verified managed version is ours, so adopt it instead of refusing.
        active = original if intact(original) else None
        recovered = active is not None and active != recorded
        all_targets = dict(selected)
        if state:
            for agent, name in state['targets'].items():
                if same_link(Path(name), current):
                    all_targets.setdefault(agent, Path(name))
        blocked = [
            path
            for path in all_targets.values()
            if (path.exists() or path.is_symlink()) and not same_link(path, current)
        ]
        for path in all_targets.values():
            safe_destination(path, root)
        blocked += [Path(path) for path in legacy if Path(path).exists() or Path(path).is_symlink()]
        if blocked and not replace:
            raise ReplaceRequired(blocked)
        version, staged = stage_version(source, root, manifest, interpreter, active)
        configured = False if staged else configure(version, manifest, interpreter, explicit)
        wanted = {agent: str(path) for agent, path in all_targets.items()}
        if (
            original == version
            and recorded == version
            and not blocked
            and state['targets'] == wanted
            and all(same_link(path, current) for path in all_targets.values())
        ):
            return {
                'status': 'repaired' if configured else 'already-installed',
                'version': version.name,
                'targets': wanted,
            }
        history = list((state or {}).get('history', []))
        for earlier in (recorded, active):
            if (
                earlier is not None
                and earlier != version
                and intact(earlier)
                and (not history or Path(history[-1]) != earlier)
            ):
                history.append(str(earlier))
        saved = {
            'schema': 1,
            'version': str(version),
            'history': history,
            'targets': wanted,
            'backups': list((state or {}).get('backups', [])),
        }
        moved = []
        linked = []
        try:
            for path in blocked:
                backup = backup_path(root, path)
                backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.move(str(path), str(backup))
                moved.append((path, backup))
            if original != version:
                activate(current, version)
            for path in all_targets.values():
                if not same_link(path, current):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    linked.append(path)
                    activate(path, current)
            for path in all_targets.values():
                if not same_link(path, current) or not (path / 'SKILL.md').is_file():
                    raise InstallError('A harness discovery link could not be verified.')
            saved['backups'] += [{'original': str(p), 'backup': str(b)} for p, b in moved]
            atomic_json(root / 'installation.json', saved)
        except BaseException:
            # Also runs for Ctrl-C and termination signals: leave what was there before.
            for path in reversed(linked):
                if same_link(path, current):
                    path.unlink()
            for path, backup in reversed(moved):
                if path.is_symlink():
                    path.unlink()
                if (backup.exists() or backup.is_symlink()) and not path.exists():
                    shutil.move(str(backup), str(path))
            if original is not None:
                if not same_link(current, original):
                    replace_link(current, original)
            elif current.is_symlink():
                current.unlink()
            raise
        result = {
            'status': 'installed',
            'version': version.name,
            'targets': saved['targets'],
            'backups': saved['backups'],
            'moved_to_backup': [str(b) for _, b in moved],
            'live_harness_discovery': 'not-yet-verified',
        }
        if recovered:
            result['recovered'] = 'An interrupted earlier setup was completed.'
        return result


def rollback(root):
    root = Path(root).resolve()
    with installation_lock(root):
        state = read_state(root)
        if not state or not state.get('history'):
            raise InstallError('There is no previous managed version to restore.')
        current = root / 'current'
        if current.exists() and not current.is_symlink():
            raise InstallError('The managed current path is not a link. No changes were made.')
        target = Path(state['history'][-1])
        if target.parent != root / 'versions' or target.is_symlink():
            raise InstallError('The previous runtime is outside managed storage.')
        manifest = verify_package(target)
        original = link_target(current) if current.is_symlink() else None
        leaving = (
            original
            if original is not None and original.parent == root / 'versions'
            else Path(state['version'])
        )
        # The old version's recorded interpreter may be gone; record one that runs.
        configure(target, manifest, stable_interpreter(sys.executable))
        replace_link(current, target)
        try:
            state['history'] = state['history'][:-1] + ([str(leaving)] if leaving != target else [])
            state['version'] = str(target)
            atomic_json(root / 'installation.json', state)
        except BaseException:
            if original is not None:
                replace_link(current, original)
            raise
        return {'status': 'rolled-back', 'version': target.name}


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
                if (path.exists() or path.is_symlink()) and not same_link(path, current):
                    raise InstallError(
                        'A discovery link was changed outside the installer; it was preserved.'
                    )
        try:
            for agent in agents:
                if agent in state['targets']:
                    path = Path(state['targets'][agent])
                    if path.is_symlink():
                        path.unlink()
                    removed.append((agent, path))
            new_state = dict(state)
            new_state['targets'] = {k: v for k, v in state['targets'].items() if k not in agents}
            atomic_json(root / 'installation.json', new_state)
        except BaseException:
            for _, path in removed:
                if not path.is_symlink():
                    replace_link(path, current)
            raise
        return {
            'status': 'uninstalled',
            'removed': [k for k, _ in removed],
            'retained': 'Your writing, Team Hubs, backups and installed versions were kept. To delete the installed versions, remove '
            + str(root / 'versions')
            + '.',
        }


def tool_status():
    git = shutil.which('git')
    if git == '/usr/bin/git' and sys.platform == 'darwin':
        # Apple's placeholder exists without the developer tools; do not launch it.
        try:
            git = (
                git
                if subprocess.run(
                    ['xcode-select', '-p'], capture_output=True, timeout=10
                ).returncode
                == 0
                else None
            )
        except (OSError, subprocess.TimeoutExpired):
            git = None
    return {
        'python': sys.version.split()[0],
        'python_supported': sys.version_info >= MINIMUM_PYTHON,
        'git': bool(git),
        'github_cli': bool(shutil.which('gh')),
        'codex_available': bool(shutil.which('codex'))
        or any(Path(p).exists() for p in ('/Applications/Codex.app', '/Applications/ChatGPT.app')),
        'claude_code_available': bool(shutil.which('claude')),
        'team_hub_note': 'Git and GitHub CLI are used only for Team Hub. Installing and local writing need neither.',
        'harness_note': 'Desktop Claude Code availability may need a manual check; Cowork is not this installation target.',
    }


def inspect(root, selected):
    """Read-only status. File placement is reported separately from harness discovery."""
    root = Path(root).resolve()
    state = read_state(root)
    current = root / 'current'
    result = {
        'tools': tool_status(),
        'targets': {
            k: {
                'path': str(p),
                'managed_link': same_link(p, current),
                'skill_present': (p / 'SKILL.md').is_file(),
            }
            for k, p in selected.items()
        },
        'installation': 'recorded' if state else 'absent',
        'live_harness_discovery': 'Verify inside a new local harness session.',
    }
    if state or current.is_symlink():
        try:
            active = link_target(current) if current.is_symlink() else None
            if active is None or active.parent != root / 'versions':
                raise InstallError(
                    'The active runtime link is missing. Run repair from the installer.'
                )
            manifest = verify_package(active)
            config = verify_configuration(active, manifest)
            result['version'] = manifest['version']
            result['interpreter'] = {
                'path': config['python'],
                'status': 'ready' if interpreter_works(config['python']) else 'missing',
            }
            if not state or Path(state['version']) != active:
                raise InstallError(
                    'An earlier setup was interrupted. Run repair from the installer.'
                )
            result['runtime_integrity'] = 'verified'
        except (InstallError, OSError) as exc:
            result['runtime_integrity'] = str(exc)
    return result


def setup_summary(result):
    """Human setup status; placement and executable detection are not discovery."""
    tools = result['tools']
    lines = ['Blog Studio setup check']
    lines.append(
        'Python: '
        + tools['python']
        + (
            ' (supported)'
            if tools['python_supported']
            else ' — install Python 3.11+ from https://www.python.org/downloads/macos/'
        )
    )
    files_ok = result.get('runtime_integrity') == 'verified'
    interpreter = result.get('interpreter', {})
    verified = files_ok and interpreter.get('status') == 'ready'
    lines.append(
        'Installed skill: '
        + (
            ('version ' + result['version'] + ', files verified')
            if files_ok
            else result.get('runtime_integrity', 'not installed')
        )
    )
    if files_ok and not verified:
        lines.append(
            'Helper Python: '
            + interpreter.get('path', 'unknown')
            + ' is missing or too old. Run repair from the installer to record a working one.'
        )
    for agent, target in result['targets'].items():
        label = LABELS[agent]
        detected = tools['codex_available' if agent == 'codex' else 'claude_code_available']
        placed = target['managed_link'] and target['skill_present'] and verified
        lines.append(
            label
            + ': '
            + ('managed files verified' if placed else 'setup or repair needed')
            + ' at '
            + target['path']
        )
        if not detected:
            lines.append(
                '  Install/open ' + label + ' before writing; automatic detection did not find it.'
            )
        elif placed:
            invocation = '$blog-studio' if agent == 'codex' else '/blog-studio'
            lines.append(
                '  Open a new local session and use ' + invocation + ' to verify discovery.'
            )
    lines.append(
        'Team Hub (optional): Git '
        + ('found' if tools['git'] else 'not found')
        + ', GitHub CLI '
        + ('found' if tools['github_cli'] else 'not found')
        + '. Local writing needs neither.'
    )
    if result.get('planned_changes'):
        lines.append(
            'Preview only: no installation changed. Run setup to install at the locations above.'
        )
    elif 'runtime_integrity' not in result:
        lines.append('Next: run sh installer/install.sh from the expanded download to install.')
    elif not verified:
        lines.append(
            'Next: run sh installer/install.sh repair from an intact download; it replaces a damaged or interrupted installation.'
        )
    else:
        lines.append('Try: Help me build an outline from my notes. Stop at the outline.')
    lines.append(
        'Drafts and voices stay in the author workspace. These checks do not prove live skill discovery.'
    )
    return '\n'.join(lines)


def ask(prompt, action):
    try:
        return input(prompt).strip()
    except EOFError as exc:
        raise InstallError(
            'Setup needs an answer but has no interactive terminal. Run: sh installer/install.sh '
            + action
            + ' --target <codex|claude|both> --yes'
        ) from exc


@contextmanager
def interruptible():
    """Turn SIGTERM/SIGHUP (a closed Terminal window) into an exception so undo code runs."""

    def stop(signum, frame):
        raise Interrupted()

    previous = {}
    for name in ('SIGTERM', 'SIGHUP'):
        try:
            previous[name] = signal.signal(getattr(signal, name), stop)
        except (AttributeError, OSError, ValueError):
            pass
    try:
        yield
    finally:
        for name, handler in previous.items():
            signal.signal(getattr(signal, name), signal.SIG_DFL if handler is None else handler)


def main():
    parser = argparse.ArgumentParser(
        description='Install, check, repair, roll back or remove the Blog Studio skill.'
    )
    parser.add_argument(
        'action',
        nargs='?',
        choices=('install', 'check', 'repair', 'rollback', 'uninstall'),
        default='install',
    )
    parser.add_argument(
        '--target',
        choices=('codex', 'claude', 'both'),
        help='Default: the targets of the existing installation, otherwise both.',
    )
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--root', type=Path)
    parser.add_argument('--source', type=Path, default=SOURCE_ROOT)
    parser.add_argument(
        '--google-docs',
        choices=('skip', 'connector', 'gcloud', 'gcloud-check'),
        default='skip',
        help='Optional Google setup; gcloud opens user sign-in, gcloud-check only reads Drive.',
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Do not ask for confirmation. Does not authorize replacing an existing folder.',
    )
    parser.add_argument(
        '--replace',
        action='store_true',
        help='Move an existing unmanaged skill folder to a backup first.',
    )
    parser.add_argument(
        '--offline',
        action='store_true',
        help='Accepted for compatibility. Setup never uses the network; with --google-docs it skips Google sign-in.',
    )
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        with interruptible():
            return run(args)
    except (KeyboardInterrupt, Interrupted):
        print(
            'Blog Studio setup: interrupted. The previous installation, if any, is still active.',
            file=sys.stderr,
        )
        return 130
    except (InstallError, OSError, ValueError) as exc:
        message = (
            str(exc)
            if isinstance(exc, InstallError)
            else 'Setup could not finish. Check folder paths and permissions, then run setup again.'
        )
        print('Blog Studio setup: ' + message, file=sys.stderr)
        return 1


def run(args):
    root = (args.root or args.home / '.local/share/blog-studio').expanduser().absolute()
    existing = None if args.target else recorded_targets(root)
    claude_config = os.environ.get('CLAUDE_CONFIG_DIR') if args.home == Path.home() else None
    if existing:
        # An update, repair or check keeps the harnesses chosen at installation.
        selected = dict(existing)
        if args.action == 'install' and not args.yes and not args.dry_run:
            for agent in (name for name in LABELS if name not in existing):
                question = (
                    'Blog Studio is set up for '
                    + ' and '.join(LABELS[name] for name in existing)
                    + '. Add '
                    + LABELS[agent]
                    + ' too? [y/N]: '
                )
                if ask(question, 'install').lower() in ('y', 'yes'):
                    selected.update(targets(args.home, (agent,), claude_config))
    else:
        if not args.target and args.action == 'install' and not args.yes and not args.dry_run:
            print(
                'Blog Studio setup\nWhere would you like to use it?\n1. Codex\n2. Claude Code\n3. Both'
            )
            answer = ask('Choose 1, 2, or 3 [3]: ', 'install')
            if answer not in ('', '1', '2', '3'):
                raise InstallError('Choose 1, 2, or 3 and run setup again.')
            args.target = {'1': 'codex', '2': 'claude'}.get(answer, 'both')
        agents = ('codex', 'claude') if (args.target or 'both') == 'both' else (args.target,)
        selected = targets(args.home, agents, claude_config)
    agents = tuple(selected)
    if args.action == 'check' or args.dry_run:
        result = inspect(root, selected)
        if args.dry_run:
            result['planned_changes'] = {k: str(v) for k, v in selected.items()}
            result['package_verified'] = source_manifest(args.source)['version']
        print(json.dumps(result, indent=2) if args.json else setup_summary(result))
        return 0
    installing = args.action in ('install', 'repair')
    if installing and sys.version_info < MINIMUM_PYTHON:
        raise InstallError(
            'Python 3.11 or later is required. Install it from python.org and run setup again.'
        )
    if not args.yes:
        if installing:
            readiness = tool_status()
            print('Python: ' + readiness['python'] + ' (supported)')
            for agent in agents:
                key = 'codex_available' if agent == 'codex' else 'claude_code_available'
                print(
                    LABELS[agent]
                    + ': '
                    + (
                        'detected'
                        if readiness[key]
                        else 'not detected; install/open it before writing'
                    )
                )
            print(
                'Version to install: '
                + source_manifest(args.source)['version']
                + (' (updating the existing installation)' if existing else '')
            )
        print('Skill locations:')
        for agent, path in selected.items():
            print(f'  {LABELS[agent]}: {path}')
        print(
            'Each location is a link to one managed copy in '
            + str(root)
            + '. Your writing stays in its own workspace.'
        )
        default_yes = installing
        answer = ask(
            f'Proceed with {args.action}? ' + ('[Y/n]: ' if default_yes else '[y/N]: '), args.action
        ).lower()
        if answer not in (('', 'y', 'yes') if default_yes else ('y', 'yes')):
            print('Setup cancelled. No installation was changed.')
            return 0
    if installing:
        # A second copy in Codex's older skill folder would be discovered twice.
        legacy = [args.home / '.codex/skills/blog-studio'] if 'codex' in agents else []
        try:
            result = install(
                args.source,
                root,
                selected,
                replace=args.replace,
                repair=args.action == 'repair',
                legacy=legacy,
            )
        except ReplaceRequired as needed:
            if args.yes:
                raise
            print('These existing skill folders are not managed by this installer:')
            for path in needed.paths:
                print('  ' + str(path))
            if ask(
                'Move them to ' + str(root / 'backups') + ' and continue? [y/N]: ', args.action
            ).lower() not in ('y', 'yes'):
                print('Setup cancelled. No installation was changed.')
                return 0
            result = install(
                args.source,
                root,
                selected,
                replace=True,
                repair=args.action == 'repair',
                legacy=legacy,
            )
    elif args.action == 'rollback':
        result = rollback(root)
    else:
        result = uninstall(root, agents)
    if installing and args.google_docs != 'skip':
        if args.offline:
            result['google'] = {
                'status': 'skipped-offline',
                'next_step': 'Run sh installer/google-setup.sh --check when online.',
            }
        elif args.google_docs == 'connector':
            result['google'] = {'status': 'connector-selected', 'verified': False}
        else:
            helper = root / 'current/scripts/google_drive.py'
            action = 'check' if args.google_docs == 'gcloud-check' else 'login'
            if action == 'login' and (args.json or not sys.stdin.isatty()):
                result['google'] = {
                    'status': 'needs-interactive-login',
                    'next_step': 'Run sh installer/google-setup.sh --login in a terminal.',
                }
            else:
                command = [sys.executable, str(helper)]
                if action == 'login':
                    print(
                        'Google sign-in asks for the access every gcloud sign-in requests plus full Google Drive access. '
                        'No Cloud project or OAuth client is created, and the account gcloud already uses stays active.'
                    )
                    email = input('Google account email to use for Docs: ').strip()
                    if email:
                        command += ['--account', email]
                check = subprocess.run(
                    command + [action], capture_output=action == 'check', text=True
                )
                result['google'] = {
                    'status': 'drive-read' if check.returncode == 0 else 'needs-setup',
                    'next_step': 'Use sh installer/google-setup.sh --install-cli, then --login you@example.com. Drive read does not verify Docs writes.',
                }
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print('Blog Studio: ' + result['status'].replace('-', ' ') + '.')
    if result.get('recovered'):
        print(result['recovered'])
    for backup in result.get('moved_to_backup', []):
        print('Existing folder moved to: ' + backup)
    if 'targets' in result:
        print('Skill files verified. Open a new local harness session to verify discovery.')
        for agent in result['targets']:
            print('Codex: $blog-studio' if agent == 'codex' else 'Claude Code: /blog-studio')
        print('Try: Help me build an outline from my notes. Stop at the outline.')
        check_command = ['sh', str(Path(__file__).resolve().with_name('install.sh')), 'check']
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


if __name__ == '__main__':
    raise SystemExit(main())
