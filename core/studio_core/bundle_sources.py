"""Resolve explicitly configured packaging sources without modifying their repositories."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

from .companions import VERSION, as_tuple, minimum_version

NAMES = {'harness-slides', 'harness-research', 'brand'}


def source_spec(value, base):
    if isinstance(value, str):
        value = {'git': value} if value.startswith(('https://', 'ssh://', 'git@', 'file://')) else {'path': value}
    if not isinstance(value, dict) or set(value) - {'git', 'path', 'ref'} or ('git' in value) == ('path' in value):
        raise ValueError('Each source needs either path or git, with an optional Git ref.')
    if 'path' in value:
        if 'ref' in value or not isinstance(value['path'], str) or not value['path'].strip():
            raise ValueError('Local sources need a nonempty path; ref applies to Git sources.')
        path = Path(value['path']).expanduser()
        return {'path': str((base / path).resolve())}
    url = value['git']
    if not isinstance(url, str) or not url or any(character.isspace() for character in url):
        raise ValueError('Git sources need an HTTPS, SSH or file URL.')
    if not re.fullmatch(r'git@[\w.-]+:[\w./-]+', url):
        parsed = urlsplit(url)
        if parsed.scheme not in ('https', 'ssh', 'file') or not parsed.path \
                or parsed.password is not None or parsed.scheme == 'https' and parsed.username is not None \
                or parsed.scheme != 'file' and not parsed.hostname:
            raise ValueError('Use an HTTPS, SSH or file Git URL without embedded credentials.')
    ref = value.get('ref', 'HEAD')
    if not isinstance(ref, str) or not re.fullmatch(r'[\w][\w./-]*', ref) or '..' in ref:
        raise ValueError('Git ref must be a branch, tag, HEAD or commit ID.')
    return {'git': url, 'ref': ref}


def load_config(path):
    path = Path(path).expanduser().resolve()
    document = json.loads(path.read_text())
    if not isinstance(document, dict) or document.get('schema') != 1 \
            or set(document) - {'schema', 'sources'} or not isinstance(document.get('sources'), dict) \
            or set(document['sources']) - NAMES:
        raise ValueError('Source config needs schema 1 and sources: harness-slides, harness-research and/or brand.')
    return {name: source_spec(value, path.parent) for name, value in document['sources'].items()}


def init_config(path, example):
    path = Path(path).expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves an existing config or symlink, even if it is broken.
    with path.open('x') as stream:
        stream.write(Path(example).read_text())
    return path


def git(arguments, cwd, env):
    result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'init.templateDir=',
                             '-c', 'core.autocrlf=false', *map(str, arguments)],
                            cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise ValueError('Packaging source Git operation failed: ' + result.stderr.strip()[-2000:])
    return result.stdout.strip()


def digest_source(root):
    """Match companion tree digests while omitting the temporary checkout's Git data."""
    lines = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if '.git' in relative.parts:
            continue
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('Packaging sources may not contain links or special files: ' + str(relative))
        if path.is_file():
            with path.open('rb') as stream:
                checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
            lines.append(checksum + '  ' + relative.as_posix() + '\n')
    return hashlib.sha256(''.join(lines).encode()).hexdigest()


def snapshot(spec, destination, env):
    """Snapshot a Git ref, or tracked working files including local edits; never copy credentials."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    local = Path(spec['path']) if 'path' in spec else None
    if local:
        top = Path(git(['rev-parse', '--show-toplevel'], local, env)).resolve()
        if top != local:
            raise ValueError('A local packaging source must point to the Git checkout root.')
        revision = git(['rev-parse', 'HEAD'], local, env)
        repository = local.as_uri()
    else:
        revision, repository = spec['ref'], spec['git']
    git(['init', '-q'], destination, env)
    git(['remote', 'add', 'origin', repository], destination, env)
    # Account configuration may be used to fetch an explicitly selected remote, but
    # it never reaches npm, source snapshots, installed skills or the final archive.
    fetch_env = dict(env) if local or repository.startswith('file://') else {
        key: value for key, value in os.environ.items()
        if key in ('HOME', 'PATH', 'SSH_AUTH_SOCK', 'GIT_SSH_COMMAND', 'TMPDIR',
                   'SYSTEMROOT', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM')}
    fetch_env['GIT_TERMINAL_PROMPT'] = '0'
    git(['-c', 'protocol.file.allow=always', 'fetch', '-q', '--depth', '1', '--no-tags', 'origin', revision],
        destination, fetch_env)
    git(['checkout', '-q', '--detach', 'FETCH_HEAD'], destination, env)
    commit = git(['rev-parse', 'HEAD'], destination, env)
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('The packaging source did not resolve to a full Git commit.')
    modified = False
    if local:
        for path in destination.iterdir():
            if path.name != '.git':
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        # Index inventory includes staged additions, excludes untracked/private files,
        # and reads current working bytes rather than silently discarding local edits.
        result = subprocess.run(['git', '-C', str(local), 'ls-files', '--stage', '-z'], env=env,
                                capture_output=True, check=True, timeout=30)
        for entry in result.stdout.split(b'\0'):
            if not entry:
                continue
            header, raw_name = entry.split(b'\t', 1)
            mode, _, stage = header.decode().split()
            name = os.fsdecode(raw_name)
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
                raise ValueError('Unsafe tracked packaging source path.')
            if stage != '0' or mode not in ('100644', '100755'):
                raise ValueError('Resolve conflicts, links or submodules before packaging: ' + name)
            source = local / relative
            if not source.exists() and not source.is_symlink():
                continue
            if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(local):
                raise ValueError('Tracked packaging source must be a regular file: ' + name)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
        modified = bool(git(['status', '--porcelain', '--untracked-files=no'], local, env))
        if git(['rev-parse', 'HEAD'], local, env) != commit:
            raise ValueError('The source checkout changed revisions during packaging; retry.')
    metadata = {'kind': 'path' if local else 'git', 'commit': commit,
                'sha256': digest_source(destination), 'modified': modified}
    return destination, metadata


def companion_pin(name, source, metadata, original):
    package = json.loads((source / 'package.json').read_text())
    version = package.get('version', '')
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError('The configured companion needs a semantic package version: ' + name)
    if as_tuple(version) < as_tuple(minimum_version(original)):
        raise ValueError('The configured companion is older than Marketing Studio supports: ' + name)
    if not (source / original['installer']).is_file() or not (source / original['stub']).is_file():
        raise ValueError('The configured companion is missing its installer or skill entry: ' + name)
    entry = re.search(r'^name: *(\S+) *$', (source / original['stub']).read_text(), re.MULTILINE)
    if not entry or entry.group(1) != name:
        raise ValueError('The configured repository contains a different skill: ' + name)
    # This source is already bundled, not a release to discover or fetch at install time.
    return {key: value for key, value in original.items() if key not in ('requirement', 'note')} | {
        'repository': 'local:' + name, 'version': version, 'commit': metadata['commit'],
        'sha256': metadata['sha256'], 'source': metadata}
