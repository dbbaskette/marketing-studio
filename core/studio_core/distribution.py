"""Build release downloads with verified private runtimes and prepared companions.

Network and npm are used only by an explicitly invoked release build. Installation
copies these files and switches the companions' usual pointers without running npm.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

from .companions import fetch_companion, read_pins

PLATFORMS = ('macos-arm64', 'macos-x64', 'linux-arm64', 'linux-x64')


def host_platform():
    system = {'Darwin': 'macos', 'Linux': 'linux'}.get(platform.system())
    machine = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}.get(platform.machine())
    return f'{system}-{machine}'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(pin, cache):
    """Accept only the exact pinned bytes, including when reusing a local cache."""
    if not re.fullmatch('[0-9a-f]{64}', pin['sha256']) or not pin['url'].startswith('https://'):
        raise ValueError('Runtime downloads require an HTTPS URL and SHA-256 pin.')
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / pin['sha256']
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
            pending = Path(stream.name)
            try:
                with urllib.request.urlopen(pin['url'], timeout=60) as response:
                    shutil.copyfileobj(response, stream)
                stream.flush()
                if digest(pending) != pin['sha256']:
                    raise ValueError('Runtime download failed its checksum: ' + pin['url'])
                pending.replace(target)
            finally:
                pending.unlink(missing_ok=True)
    if digest(target) != pin['sha256']:
        raise ValueError('Cached runtime failed its checksum: ' + str(target))
    return target


def unpack(archive, destination, node=False):
    """Flatten only internal tar links into regular files; never extract paths verbatim."""
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, 'r:gz') as tar:
        members = {}
        for member in tar.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not name.parts:
                raise ValueError('Unsafe runtime archive path.')
            if member.name in members:
                raise ValueError('Duplicate runtime archive path.')
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise ValueError('Runtime archives may not contain special files.')
            members[member.name] = member
        prefixes = {PurePosixPath(name).parts[0] for name in members}
        if len(prefixes) != 1:
            raise ValueError('Expected one runtime archive root.')
        for member in members.values():
            if member.isdir():
                continue
            relative = PurePosixPath(member.name).parts[1:]
            # Browser-based studios never use a private terminal database. Linux's
            # terminfo filenames differ only by case and cannot be staged on the
            # usual case-insensitive macOS filesystem. System curses keeps using
            # the operating system's own terminal database.
            if relative[:2] == ('share', 'terminfo'):
                continue
            if not relative or node and relative not in (('bin', 'node'), ('LICENSE',)):
                continue
            original = member
            seen = set()
            while member.issym() or member.islnk():
                if member.name in seen:
                    raise ValueError('Cyclic runtime archive link.')
                seen.add(member.name)
                link = PurePosixPath(member.linkname)
                if link.is_absolute():
                    raise ValueError('Absolute runtime archive link.')
                path = PurePosixPath(member.name).parent / link if member.issym() else link
                parts = []
                for part in path.parts:
                    if part == '..':
                        if len(parts) <= 1:
                            raise ValueError('Escaping runtime archive link.')
                        parts.pop()
                    elif part != '.':
                        parts.append(part)
                member = members.get('/'.join(parts))
                if member is None:
                    raise ValueError('Broken runtime archive link.')
            if not member.isfile():
                raise ValueError('Runtime link must point to a regular file.')
            output = destination.joinpath(*relative)
            output.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, output.open('xb') as target:
                shutil.copyfileobj(source, target)
            output.chmod(0o755 if member.mode & 0o111 or original.mode & 0o111 else 0o644)


def copy_regular(source, destination):
    """Dependencies can have bin links; resolve only links inside their own package tree."""
    source = Path(source).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    for directory, dirs, names in os.walk(source, followlinks=False):
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError('Dependency directory links are not supported.')
        for name in names:
            path = Path(directory) / name
            resolved = path.resolve()
            if not resolved.is_relative_to(source) or not resolved.is_file():
                raise ValueError('Dependency links must stay inside their package tree.')
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, target)


def python_notices(pin, cache, destination):
    """The install-only Python archive omits its dependency license directory."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(download(pin, cache / 'downloads'), 'r:gz') as source:
        count = 0
        for member in source.getmembers():
            path = PurePosixPath(member.name)
            if len(path.parts) == 2 and re.fullmatch(r'LICENSE\.[\w.-]+\.txt', path.name) and member.isfile():
                (destination / path.name).write_bytes(source.extractfile(member).read())
                count += 1
        if not count:
            raise ValueError('The Python build source did not contain its dependency notices.')


def prepare(root, destination, target, cache, studios):
    """A developer build; never uses installed skills, credentials, or a real HOME."""
    root, destination, cache = Path(root).resolve(), Path(destination).resolve(), Path(cache).resolve()
    pins = json.loads((root / 'pins/runtimes.json').read_text())
    selected = pins['platforms'][target]
    runtime = destination / 'runtime'
    runtime.mkdir()
    for name in ('python', 'node'):
        unpack(download(selected[name], cache / 'downloads'), runtime / name, node=name == 'node')
    python_notices(pins['python_notices'], cache, runtime / 'python/licenses')
    (runtime / 'platform').write_text(target + '\n')
    companions = read_pins(root / 'pins/companions.json')
    if studios == ['blog']:
        companions = {name: pin for name, pin in companions.items() if name == 'harness-research'}
    record = {'schema': 1, 'platform': target,
              'python_notices': pins['python_notices'],
              'runtimes': {name: selected[name] for name in ('python', 'node')}, 'companions': {}}
    with tempfile.TemporaryDirectory(prefix='marketing-release-build-') as temporary:
        work = Path(temporary)
        home = work / 'home'
        home.mkdir()
        (home / 'npm-user.conf').write_text('')
        (home / 'npm-global.conf').write_text('')
        env = {key: value for key, value in os.environ.items()
               if key in ('PATH', 'TMPDIR', 'SYSTEMROOT', 'SSL_CERT_FILE', 'SSL_CERT_DIR')}
        env.update(HOME=str(home), USERPROFILE=str(home), NPM_CONFIG_USERCONFIG=str(home / 'npm-user.conf'),
                   NPM_CONFIG_CACHE=str(cache / 'npm'), NPM_CONFIG_GLOBALCONFIG=str(home / 'npm-global.conf'),
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        for name, pin in companions.items():
            checkout = fetch_companion(name, pin, cache)
            shared = work / name
            command = ['node', str(checkout / pin['installer']), '--home', str(home), '--shared', str(shared)]
            if name == 'harness-slides':
                command.append('--skip-dependencies')
            done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=300, check=True)
            prepared = Path(json.loads(done.stdout)['runtime'])
            if name == 'harness-slides':
                subprocess.run(['npm', 'ci', '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund'],
                               cwd=prepared, env=env, check=True, timeout=900)
                native = list((prepared / 'node_modules').rglob('*.node'))
                if native:
                    raise ValueError('Cross-platform bundles require pure JavaScript slide dependencies.')
            output = destination / 'companions' / name
            copy_regular(prepared, output)
            record['companions'][name] = {'version': pin['version'], 'id': prepared.name,
                                         'commit': pin['commit'], 'source_sha256': pin['sha256']}
    (destination / 'distribution.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
