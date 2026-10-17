"""Install prepared companions at their upstream locations, preserving unrelated skills."""
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager

from .distribution import digest, host_platform
from .companions import tree_digest


def record(source):
    path = source / 'distribution.json'
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get('schema') != 1 or not isinstance(value.get('companions'), dict):
        raise ValueError('The bundle distribution record is incomplete.')
    if value.get('platform') != host_platform():
        raise ValueError('This download is for another platform. Download the matching macOS or Linux bundle.')
    for relative in ('runtime/python/bin/python3', 'runtime/node/bin/node', 'runtime/platform'):
        if not (source / relative).is_file():
            raise ValueError('The private runtime is incomplete. Download a fresh release.')
    if (source / 'runtime/platform').read_text().strip() != value['platform']:
        raise ValueError('The private runtime platform does not match the bundle.')
    return value


def names(studios):
    return ['harness-research'] if studios == ['blog'] else ['harness-research', 'harness-slides']


def shared_root(home, name):
    return home / 'Library/Application Support' / ('Harness Research' if name == 'harness-research' else 'Harness Slides') \
        if sys.platform == 'darwin' else home / '.local/share' / name


def managed_paths(home, studios, target):
    harnesses = ['codex', 'claude'] if target == 'both' else [target]
    return [path for name in names(studios)
            for path in [shared_root(home, name) / 'current',
                         *(home / ('.agents' if harness == 'codex' else '.claude') / 'skills' / name
                           for harness in harnesses)]]


@contextmanager
def locked(home, studios):
    """Use the upstream installers' adjacent exclusive locks for the whole change."""
    acquired = []
    try:
        for name in sorted(names(studios)):
            root = shared_root(home, name)
            root.mkdir(parents=True, exist_ok=True)
            stat = root.stat()
            if root.is_symlink() or stat.st_uid != os.getuid() or stat.st_mode & 0o022:
                raise ValueError('Preserve the unsafe companion installation folder: ' + str(root))
            versions = root / 'versions'
            if versions.is_symlink():
                raise ValueError('Preserve the unrecognized companion versions folder: ' + str(versions))
            path = root / '.install-lock'
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError as exc:
                raise ValueError('Another companion installation is in progress: ' + name) from exc
            os.close(descriptor)
            acquired.append(path)
        yield
    finally:
        for path in reversed(acquired):
            path.unlink()


def plan(source, home, studios, target):
    """Validate all destinations before changing any companion pointer."""
    distribution = record(source)
    if not distribution:
        return []
    result = []
    for name in names(studios):
        item = distribution['companions'].get(name)
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not isinstance(item.get('version'), str) \
                or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{20}', item['id']) \
                or not item['id'].startswith(item['version'] + '-'):
            raise ValueError('Invalid prepared companion version.')
        package = source / 'companions' / name
        if not (package / 'package.json').is_file() or not (package / 'SKILL.md').is_file():
            raise ValueError('The prepared companion is incomplete: ' + name)
        if json.loads((package / 'package.json').read_text())['version'] != item['version']:
            raise ValueError('The prepared companion version does not match its record.')
        root = shared_root(home, name)
        current = root / 'current'
        if current.exists() or current.is_symlink():
            if not current.is_symlink() or not re.fullmatch(r'versions/[\w.-]+', os.readlink(current)):
                raise ValueError('Preserve the unrecognized companion installation: ' + str(current))
        links = managed_paths(home, [studios[0]] if studios == ['blog'] else ['presentation'], target)
        links = [path for path in links if path.name == name and path != current]
        for path in links:
            if (path.exists() or path.is_symlink()) and (not path.is_symlink() or os.readlink(path) != str(current)):
                raise ValueError('Preserve the unrelated skill at ' + str(path))
        # Keep an independently updated companion when it is newer than this bundle.
        previous = current / 'package.json'
        if previous.is_file():
            version = json.loads(previous.read_text()).get('version', '')
            if re.fullmatch(r'\d+\.\d+\.\d+', version) and tuple(map(int, version.split('.'))) > tuple(map(int, item['version'].split('.'))):
                result.append({'name': name, 'keep': True, 'current': current, 'links': links})
                continue
        # An upstream install at the same source revision can have no npm packages
        # yet, or a different npm-generated lock. Keep it intact and give the
        # prepared production tree its own immutable version directory.
        bundled_id = item['id'] + '-bundle-' + tree_digest(package)[:12]
        result.append({'name': name, 'package': package, 'destination': root / 'versions' / bundled_id,
                       'current': current, 'links': links, 'keep': False})
    return result


def install(planned, link):
    results = {}
    for item in planned:
        if not item['keep']:
            package, destination = item['package'], item['destination']
            if destination.is_symlink():
                raise ValueError('Preserve the unrecognized companion version link: ' + str(destination))
            if destination.exists():
                expected = {p.relative_to(package): digest(p) for p in package.rglob('*') if p.is_file()}
                actual = {p.relative_to(destination): digest(p) for p in destination.rglob('*') if p.is_file()}
                if any(p.is_symlink() for p in destination.rglob('*')) or actual != expected:
                    raise ValueError('The retained companion version changed. Preserve it: ' + str(destination))
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='.bundle-', dir=destination.parent) as temporary:
                    stage = Path(temporary) / 'runtime'
                    shutil.copytree(package, stage)
                    stage.rename(destination)
            link(item['current'], 'versions/' + destination.name)
        for path in item['links']:
            link(path, item['current'])
        results[item['name']] = {'state': 'left alone' if item['keep'] else 'installed', 'source': 'bundled'}
    return results
