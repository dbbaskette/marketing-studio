#!/usr/bin/env python3
"""Atomic native Infographic Studio installation; no workspace or account changes."""
import sys
if sys.version_info < (3, 11):
    raise SystemExit('Infographic Studio setup needs Python 3.11 or newer.')
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import shlex
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runner'))
from studio_core.packaging import files
from studio_core.runtime import shell_path
sys.path.insert(0, str(ROOT))
from runner.workspace import _atomic, _directory, file_lock

NAME = 'infographic-studio'
MARK = '# Written by the Infographic Studio installer.'


def paths(home, target='both'):
    data = home / '.local/share' / NAME
    return [data / n for n in ('current', 'installation.json', 'studio', 'infographic')] + [
        home / folder / 'skills' / NAME for harness, folder in (('codex', '.agents'), ('claude', '.claude'))
        if target in ('both', harness)] + [home / 'Applications/Open Infographic Studio.command']


def snapshot(items):
    result = {}
    for path in items:
        if path.is_symlink(): result[str(path)] = {'link': os.readlink(path)}
        elif path.is_file(): result[str(path)] = {'bytes': base64.b64encode(path.read_bytes()).decode(), 'mode': path.stat().st_mode & 0o777}
        elif path.exists(): raise ValueError('Keep the existing unmanaged folder: ' + str(path))
        else: result[str(path)] = None
    return result


def link(path, target):
    _directory(path.parent)
    temporary = path.with_name('.install-' + secrets.token_hex(8))
    try:
        temporary.symlink_to(target)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def restore(saved, allowed):
    if not isinstance(saved, dict) or set(saved) - {str(p) for p in allowed}:
        raise ValueError('The retained rollback record names unmanaged paths.')
    for name, item in saved.items():
        path = Path(name)
        if item is None:
            if path.is_dir() and not path.is_symlink(): raise ValueError('A folder blocks restoration: ' + name)
            path.unlink(missing_ok=True)
        elif 'link' in item: link(path, item['link'])
        else: _atomic(path, base64.b64decode(item['bytes'], validate=True), mode=item['mode'])


def payload():
    skill = ROOT / 'skills/infographic-studio/SKILL.md'
    result = {Path('SKILL.md'): skill if skill.is_file() else ROOT / 'SKILL.md', Path('VERSION'): ROOT / 'VERSION'}
    for directory in ('runner', 'docs', 'installer'):
        for source in files(ROOT / directory):
            if source.is_file() and source.suffix not in ('.pyc', '.pyo'):
                result[source.relative_to(ROOT)] = source
    renderer = ROOT / 'renderer' if (ROOT / 'renderer').is_dir() else ROOT.parents[1] / 'runtime/renderer'
    if renderer.is_dir():
        for source in files(renderer):
            if source.is_file(): result[Path('renderer') / source.relative_to(renderer)] = source
    return result


def main(argv=None):
    top = argparse.ArgumentParser(description=__doc__)
    top.add_argument('action', choices=('install', 'status', 'rollback', 'uninstall', 'plan'))
    top.add_argument('--home', type=Path, default=Path.home())
    top.add_argument('--target', choices=('codex', 'claude', 'both'), default='both')
    top.add_argument('--companions', choices=('skip', 'ask', 'install'), default='skip')
    top.add_argument('--pins', type=Path)
    top.add_argument('--yes', action='store_true')
    top.add_argument('--json', action='store_true')
    args = top.parse_args(argv)
    home = args.home.expanduser().absolute()
    managed = paths(home, args.target); allowed = paths(home); data = managed[0].parent
    if args.action == 'plan': return {'action': 'plan', 'product': 'Infographic Studio', 'home': str(home), 'companions': []}
    if args.action == 'status': return {'installed': managed[0].is_dir(), 'product': 'Infographic Studio'}
    if any(parent.is_symlink() for path in managed for parent in path.parents):
        raise ValueError('Installation directories cannot traverse links; existing files were kept.')
    # Read-only status and plan never create data. Mutation holds the same native
    # running lease as the independent CLI and Marketing Studio bridge.
    with file_lock(data / 'install.lock'), file_lock(data / '.studio-running.lock'):
        statefile = data / 'installation.json'
        if statefile.is_symlink(): raise ValueError('Preserve the unexpected installation record link.')
        if statefile.exists() and statefile.stat().st_size > 2_000_000:
            raise ValueError('The native installation record exceeds its limit. Preserve it and restore valid metadata.')
        previous = json.loads(statefile.read_text()) if statefile.exists() else None
        if previous and (previous.get('schema') != 1 or previous.get('product') != 'Infographic Studio'):
            raise ValueError('Restore a valid native installation record before changing this installation.')
        if args.action in ('rollback', 'uninstall'):
            if not previous: return {'action': args.action, 'changed': False}
            key = 'previous' if args.action == 'rollback' else 'original'
            restore(previous[key], allowed)
            return {'action': args.action, 'changed': True, 'workspace': 'kept', 'versions': 'kept'}
        before = snapshot(managed)
        if not previous:
            for path in managed:
                if before[str(path)] is not None:
                    raise ValueError('Keep the existing unrelated installation or skill at ' + str(path))
        else:
            # An install record never grants ownership of a user-replaced pointer.
            for path in managed:
                if path == statefile: continue
                if path.is_symlink():
                    target = str(path.resolve())
                    if not target.startswith(str(data / 'versions') + os.sep):
                        raise ValueError('Keep the changed unrelated link: ' + str(path))
                elif path.exists() and (not path.is_file() or not path.read_text().startswith('#!/bin/sh\n' + MARK)):
                    raise ValueError('Keep the changed unrelated file: ' + str(path))
        content = payload()
        hasher = hashlib.sha256()
        for name, source in sorted(content.items()): hasher.update(str(name).encode() + b'\0' + source.read_bytes() + b'\0')
        version = (ROOT / 'VERSION').read_text().strip()
        if not re.fullmatch(r'\d{1,6}\.\d{1,6}\.\d{1,6}', version): raise ValueError('Use a supported numeric Infographic Studio version.')
        key = version + '-' + hasher.hexdigest()[:16]
        versions = data / 'versions'; _directory(versions)
        destination = versions / key
        if destination.is_symlink(): raise ValueError('Preserve the unexpected version link.')
        if not destination.exists():
            with tempfile.TemporaryDirectory(prefix='.install-', dir=versions) as temp:
                stage = Path(temp) / 'native'; stage.mkdir()
                for name, source in content.items():
                    out = stage / name; out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(source.read_bytes()); out.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
                stage.rename(destination)
        else:
            actual = {p.relative_to(destination): hashlib.sha256(p.read_bytes()).hexdigest() for p in files(destination) if p.is_file()}
            expected = {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in content.items()}
            if actual != expected: raise ValueError('The retained immutable native version changed. Preserve it.')
        try:
            link(managed[0], 'versions/' + key)
            for harness, folder in (('codex', '.agents'), ('claude', '.claude')):
                if args.target in ('both', harness): link(home / folder / 'skills' / NAME, data / 'current')
            # A prepared suite retains its immutable runtime even after Marketing
            # Studio is uninstalled; source installs use the explicitly running Python.
            command = shlex.quote(sys.executable) + ' ' + shlex.quote(str(data / 'current/runner/studio.py'))
            environment = shell_path()
            helper = '#!/bin/sh\n' + MARK + '\n' + environment + 'exec ' + command + ' "$@"\n'
            launcher = '#!/bin/sh\n' + MARK + '\n' + environment + 'exec ' + command + ' serve --open\n'
            _atomic(data / 'infographic', helper.encode(), mode=0o755)
            _atomic(data / 'studio', launcher.encode(), mode=0o755)
            _atomic(managed[-1], launcher.encode(), mode=0o755)
            same = previous and previous['version'] == key and set(previous['original']) == set(before)
            state = {'schema': 1, 'product': 'Infographic Studio', 'version': key,
                     'original': {**before, **previous['original']} if previous else before,
                     'previous': previous['previous'] if same else before}
            _atomic(statefile, (json.dumps(state) + '\n').encode())
        except BaseException:
            restore(before, managed)
            raise
        return {'action': 'install', 'product': 'Infographic Studio', 'version': key, 'path': str(data / 'current'), 'companions': []}


if __name__ == '__main__':
    try:
        print(json.dumps(main()))
    except (ValueError, OSError) as failure:
        print(json.dumps({'error': str(failure)}), file=sys.stderr)
        raise SystemExit(2)
