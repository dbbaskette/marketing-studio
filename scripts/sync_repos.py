#!/usr/bin/env python3
"""Update Marketing Studio and sibling component checkouts without discarding work."""
import argparse
import configparser
from dataclasses import dataclass
import os
import math
import re
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core.bundle_sources import load_config, source_spec
from studio_core.install_log import redact

DEFAULTS = {
    'harness-research': ('harness-research-skill', 'https://github.com/dbbaskette/harness-research-skill.git'),
    'harness-slides': ('harness-slides-skill', 'https://github.com/dbbaskette/harness-slides-skill.git'),
    'brand': ('tanzu-brand', 'https://github.com/dbbaskette/tanzu-brand.git'),
}
INHERITED = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY',
             'GIT_COMMON_DIR', 'GIT_PREFIX')


@dataclass
class Repository:
    name: str
    path: Path
    url: str | None = None


def config_file(root, requested=None):
    if requested is not None:
        return Path(requested).expanduser().resolve()
    for name in ('sync.cfg', 'studio-package.local.json', 'presentation-studio-package.local.json'):
        candidate = root / name
        if candidate.exists() or candidate.is_symlink():
            return candidate
    return None


def discover_harness(result, directory):
    seen = {repository.path.resolve() for repository in result}
    for path in sorted(directory.glob('harness-*')):
        if path.is_dir() and (path / '.git').exists() and path.resolve() not in seen:
            seen.add(path.resolve())
            result.append(Repository(path.name, path))
    return result


def configured_repositories(path):
    parser = configparser.ConfigParser(interpolation=None, empty_lines_in_values=False)
    parser.optionxform = str
    try:
        with path.open(encoding='utf-8') as stream:
            parser.read_file(stream)
        if parser.defaults() or set(parser.sections()) != {'sync', 'repositories'}:
            raise ValueError('Sync config needs [sync] and [repositories] sections only.')
        options = parser['sync']
        if set(options) - {'directory', 'discover_harness'} or not options.get('directory', '').strip():
            raise ValueError('[sync] needs directory, with optional discover_harness = true or false.')
        directory = Path(options['directory']).expanduser()
        directory = (path.parent / directory).resolve()
        discover = options.getboolean('discover_harness', fallback=False)
        entries = parser['repositories']
        if not entries:
            raise ValueError('List at least one repository in [repositories].')
        labels = {'marketing-studio': 'Marketing Studio', 'harness-research-skill': 'Harness Research',
                  'harness-slides-skill': 'Harness Slides', 'tanzu-brand': 'Tanzu Brand'}
        result, seen = [], set()
        for folder, url in entries.items():
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', folder):
                raise ValueError('Repository keys must be folder names, without paths or spaces.')
            if folder.casefold() in seen:
                raise ValueError('Repository folder names must be unique, ignoring case.')
            seen.add(folder.casefold())
            validated = source_spec({'git': url}, path.parent)
            result.append(Repository(labels.get(folder, folder), directory / folder, validated['git']))
        return discover_harness(result, directory) if discover else result
    except configparser.Error as error:
        raise ValueError('Invalid sync config: ' + str(error)) from error


def repositories(root, config=None):
    """Use explicit sync destinations, falling back to the original sibling discovery."""
    root = Path(root).resolve()
    config = config_file(root, config)
    if config is not None and config.suffix != '.json':
        return configured_repositories(config)
    sources = load_config(config) if config else {}
    result = [Repository('Marketing Studio', root)]
    seen = {root}
    for key, (default_name, default_url) in DEFAULTS.items():
        spec = sources.get(key, {})
        url = spec.get('git')
        name = default_name
        if spec.get('path'):
            name = Path(spec['path']).name
            # A custom local checkout needs its own remote; never guess which
            # repository to clone into a missing custom folder.
            url = default_url if name == default_name else None
        elif url:
            name = urlsplit(url).path.rsplit('/', 1)[-1].removesuffix('.git')
            if url.startswith('git@'):
                name = url.rsplit('/', 1)[-1].rsplit(':', 1)[-1].removesuffix('.git')
        else:
            url = default_url
        if not name or name in ('.', '..') or '/' in name or '\\' in name:
            raise ValueError('Component repository needs a normal folder name.')
        path = root.parent / name
        if path.resolve() in seen:
            continue
        seen.add(path.resolve())
        result.append(Repository('Tanzu Brand' if key == 'brand' else key.replace('-', ' ').title(), path, url))
    return discover_harness(result, root.parent)


class Sync:
    def __init__(self, *, timeout=180, dry_run=False, clone=True):
        self.timeout, self.dry_run, self.clone = timeout, dry_run, clone
        self.environment = {key: value for key, value in os.environ.items() if key not in INHERITED}
        self.environment.update(GIT_TERMINAL_PROMPT='0', GIT_EDITOR='true')

    def git(self, repo, *args, live=False, env=None):
        command = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                   '-c', 'maintenance.auto=false', '-c', 'gc.auto=0', '-C', str(repo), *args]
        print('  $ ' + redact(shlex.join(command)), flush=True)
        started = time.monotonic()
        process = subprocess.Popen(command, env=env or self.environment, stdin=subprocess.DEVNULL,
                                   stdout=None if live else subprocess.PIPE,
                                   stderr=None if live else subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=3)
            raise ValueError(f'Git timed out after {self.timeout:g}s; other repositories will continue.') from None
        if live or process.returncode:
            print(f'  Exit {process.returncode} ({time.monotonic() - started:.1f}s)', flush=True)
        if process.returncode:
            message = (stderr or stdout or '').strip()
            fallback = (f'Git exited with status {process.returncode}; see the command output above.'
                        if live else f'Git exited with status {process.returncode} without an error message.')
            raise ValueError(redact(message) or fallback)
        return (stdout or '').strip()

    def network_environment(self, repo):
        env = dict(self.environment)
        if not env.get('GIT_SSH_COMMAND') and not env.get('GIT_SSH'):
            try:
                self.git(repo, 'config', '--get', 'core.sshCommand')
            except ValueError:
                env['GIT_SSH_COMMAND'] = 'ssh -o BatchMode=yes -o ConnectTimeout=15'
        return env

    def update(self, repository):
        path = repository.path
        if path.is_symlink():
            return 'SKIPPED', 'Folder is a link; keep sibling checkouts in real directories.'
        if not path.exists():
            if not self.clone or not repository.url:
                return 'MISSING', 'No checkout; enable cloning and provide its Git URL in the config.'
            if self.dry_run:
                return 'PLAN', 'Clone ' + repository.url + ' into ' + str(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.git(path.parent, 'clone', '--progress', '--', repository.url, str(path),
                     live=True, env=self.network_environment(path.parent))
            return 'CLONED', self.git(path, 'rev-parse', '--short', 'HEAD')
        if not path.is_dir() or self.git(path, 'rev-parse', '--show-toplevel') != str(path.resolve()):
            return 'SKIPPED', 'This is not a Git checkout root; nothing was overwritten.'
        changes = self.git(path, 'status', '--porcelain=v1', '--untracked-files=normal')
        if changes:
            return 'SKIPPED', 'Local changes kept. Commit or move them before syncing.\n' + changes
        try:
            branch = self.git(path, 'symbolic-ref', '--quiet', '--short', 'HEAD')
        except ValueError:
            return 'SKIPPED', 'Detached HEAD kept; choose a branch before syncing.'
        # Do not silently invent an upstream or change the checked-out branch.
        try:
            upstream = self.git(path, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
        except ValueError:
            return 'SKIPPED', 'Branch ' + branch + ' has no upstream; configure one before syncing.'
        before = self.git(path, 'rev-parse', 'HEAD')
        print('  Branch: ' + branch + ' → ' + upstream, flush=True)
        if self.dry_run:
            return 'PLAN', 'Pull current branch with --ff-only; no network request made.'
        self.git(path, 'pull', '--ff-only', '--no-rebase', '--no-autostash',
                 '--recurse-submodules=no', '--verbose', '--progress',
                 live=True, env=self.network_environment(path))
        after = self.git(path, 'rev-parse', 'HEAD')
        ahead = int(self.git(path, 'rev-list', '--count', '@{upstream}..HEAD'))
        if ahead:
            return 'AHEAD', f'{ahead} local commit(s) kept on {branch}; HEAD {after[:12]}'
        return ('UPDATED' if before != after else 'CURRENT'), after[:12]


def main(argv=None):
    parser = argparse.ArgumentParser(prog='sync.sh', description=__doc__, epilog=
        'Related checkouts are siblings of Marketing Studio. No reset, stash, rebase, install, or provider jobs.')
    parser.add_argument('--config', type=Path, help='Sync .cfg file or legacy packaging source JSON (default: sync.cfg when present).')
    parser.add_argument('--dry-run', action='store_true', help='Inspect and show the plan; no fetch, clone, or pull.')
    parser.add_argument('--no-clone', action='store_true', help='Update existing checkouts only.')
    parser.add_argument('--timeout', type=float, default=180, help='Seconds allowed per Git command (default: 180).')
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be positive')
    if not shutil.which('git'):
        parser.error('Git is required; no software was installed.')
    try:
        selected_config = config_file(ROOT, args.config)
        selected = repositories(ROOT, selected_config)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    sync = Sync(timeout=args.timeout, dry_run=args.dry_run, clone=not args.no_clone)
    results = []
    print('Marketing Studio repository sync', flush=True)
    print('Config: ' + (str(selected_config) if selected_config else 'default sibling discovery'), flush=True)
    for repository in selected:
        print('\n=== ' + repository.name + ': ' + str(repository.path) + ' ===', flush=True)
        try:
            status, detail = sync.update(repository)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            status, detail = 'FAILED', str(error)
        results.append((repository, status))
        print(status + ': ' + redact(detail), flush=True)
    print('\nSync results:', flush=True)
    for repository, status in results:
        print(f'  {status:8} {repository.name} — {repository.path}', flush=True)
    attention = sum(status in ('SKIPPED', 'MISSING', 'FAILED', 'AHEAD') for _, status in results)
    print(f'{len(results) - attention}/{len(results)} repositories ready; {attention} need attention.', flush=True)
    return 1 if attention else 0


if __name__ == '__main__':
    raise SystemExit(main())
