#!/usr/bin/env python3
"""Install any selection of studios, keep native launchers, and manage the umbrella UI."""
import argparse
import base64
from contextlib import contextmanager, nullcontext
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core.runtime import ensure_python

ensure_python(ROOT)

from studio_core.bundles import content_key, inventory, materialize
from studio_core import offline_install
from studio_core.runtime import assistant_target, shell_path

STUDIOS = ('blog', 'presentation', 'training')


class InstallError(ValueError):
    pass


def atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '-' + secrets.token_hex(5))
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def link(path, target):
    temporary = path.with_name('.' + path.name + '-' + secrets.token_hex(5))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.symlink_to(target)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_state(data):
    path = data / 'installation.json'
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or value.get('schema') != 1:
            raise ValueError()
        return value
    except (ValueError, OSError) as exc:
        raise InstallError('Keep the existing Marketing Studio installation record and correct it before installing.') from exc


@contextmanager
def locked(data):
    data.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(data / 'install.lock', os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise InstallError('Another Marketing Studio installation is in progress.') from exc
        yield
    finally:
        os.close(descriptor)


def not_running(home, studios, data):
    # Query only recorded process IDs. Never stop active studios to install software.
    for product in ('marketing', *studios):
        base = data if product == 'marketing' else home / '.local/share' / (product + '-studio')
        pid = base / 'runner.pid'
        if pid.is_file():
            value = pid.read_text().strip()
            if value.isdigit():
                try:
                    os.kill(int(value), 0)
                except ProcessLookupError:
                    pass
                else:
                    raise InstallError(product.title() + ' Studio is open. Close it before installing.')
        lockfile = base / ('home.lock' if product == 'marketing' else '.studio-running.lock')
        if lockfile.is_file():
            with lockfile.open('a') as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise InstallError(product.title() + ' Studio is open. Close it before installing.') from exc


def managed_paths(home, studios, data):
    result = [data / 'current', data / 'installation.json', data / 'marketing-studio',
              home / 'Applications/Open Marketing Studio.command', home / '.local/bin/marketing-studio']
    for identifier in studios:
        slug = identifier + '-studio'
        base = home / '.local/share' / slug
        result += [base / name for name in ('current', 'installation.json', 'studio', identifier)]
        result += [home / folder / 'skills' / slug for folder in ('.claude', '.agents')]
        result += [home / 'Applications' / ('Open ' + identifier.title() + ' Studio.command')]
    return result


def snapshot(paths):
    saved = {}
    for path in paths:
        if path.is_symlink():
            saved[str(path)] = {'link': os.readlink(path)}
        elif path.is_file():
            saved[str(path)] = {'bytes': base64.b64encode(path.read_bytes()).decode(),
                                'mode': path.stat().st_mode & 0o777}
        elif path.exists():
            raise InstallError('An unmanaged folder blocks installation: ' + str(path))
        else:
            saved[str(path)] = None
    return saved


def restore(saved, allowed):
    # A damaged or edited metadata file must never turn rollback into arbitrary writes.
    if set(saved) - {str(path) for path in allowed}:
        raise InstallError('The rollback record names an unmanaged path. No files were restored.')
    for name, entry in saved.items():
        path = Path(name)
        if entry is None:
            if path.is_dir() and not path.is_symlink():
                raise InstallError('A folder blocks restoration: ' + name)
            path.unlink(missing_ok=True)
        elif 'link' in entry:
            link(path, entry['link'])
        else:
            atomic(path, base64.b64decode(entry['bytes'], validate=True), entry['mode'])


def verify_bundle(source):
    manifest = source / 'bundle-manifest.json'
    if not manifest.exists():
        return
    try:
        value = json.loads(manifest.read_text())
        studios = value['studios']
        if not isinstance(studios, list) or not studios or set(studios) - set(STUDIOS):
            raise ValueError()
        actual = inventory(source, studios)
        if set(actual) != set(value['files']):
            raise ValueError()
        for name, path in actual.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != value['files'][name]:
                raise ValueError()
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise InstallError('The installer bundle changed or is incomplete. Download a fresh release.') from exc


def run_native(source, identifier, home, action, target, companions='skip'):
    python = source / 'runtime/python/bin/python3'
    command = [str(python) if python.is_file() else sys.executable, str(source / 'studios' / identifier / 'installer/install.py'),
               action, '--home', str(home), '--yes', '--json']
    if action == 'install':
        command += ['--target', target]
        if identifier != 'blog':
            command += ['--companions', 'skip', '--pins', str(source / 'pins/companions.json')]
        else:
            command += ['--offline']
    env = {**os.environ, 'HOME': str(home)}
    if python.is_file():
        env['PATH'] = str(source / 'runtime/python/bin') + ':' + str(source / 'runtime/node/bin') + ':' + env.get('PATH', '')
    done = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=300)
    if done.returncode:
        raise InstallError(identifier.title() + ' Studio: ' + (done.stderr or done.stdout).strip()[-2000:])
    try:
        return json.loads(done.stdout)
    except ValueError as exc:
        raise InstallError(identifier.title() + ' Studio did not return an installation result.') from exc


def install(source, home, data, studios, target, companions):
    verify_bundle(source)
    distribution = offline_install.record(source)
    with offline_install.locked(home, studios) if distribution and companions != 'skip' else nullcontext():
        return install_locked(source, home, data, studios, target, companions, distribution)


def install_locked(source, home, data, studios, target, companions, distribution):
    old = read_state(data)
    selected = sorted(set(studios) | set((old or {}).get('studios', [])))
    available = [identifier for identifier in selected if (source / 'studios' / identifier / 'installer/install.py').is_file()]
    # A subset package can update its own studios; previous independent studios remain available.
    not_running(home, available, data)
    cli = home / '.local/bin/marketing-studio'
    if (cli.exists() or cli.is_symlink()) and not (cli.is_symlink() and cli.resolve() == (data / 'marketing-studio').resolve()):
        raise InstallError('An existing marketing-studio command is unmanaged. Move it aside before installing.')
    companion_paths = offline_install.managed_paths(home, studios, target) if distribution and companions != 'skip' else []
    saved = snapshot([*managed_paths(home, available, data), *companion_paths])
    key = content_key(source, studios)
    versions = data / 'versions'
    versions.mkdir(parents=True, exist_ok=True)
    destination = versions / key
    pending = versions / ('.pending-' + secrets.token_hex(6))
    try:
        if not destination.exists():
            materialize(source, pending, studios)
            pending.rename(destination)
        if content_key(destination, studios) != key:
            raise InstallError('The saved suite version has changed. Keep it for diagnosis and restore a verified copy.')
        prepared = offline_install.plan(destination, home, studios, target) if distribution and companions != 'skip' else []
        results = {}
        for identifier in studios:
            results[identifier] = run_native(destination, identifier, home, 'install', target)
        # One explicitly agreed companion step uses the canonical pin set once.
        if prepared:
            results['companions'] = offline_install.install(prepared, link)
        elif companions == 'install' and not distribution:
            from studio_core.companions import bring_companions, read_pins
            pins = read_pins(destination / 'pins/companions.json')
            if studios == ['blog']:
                pins = {name: pin for name, pin in pins.items() if name == 'harness-research'}
            harnesses = ['claude', 'codex'] if target == 'both' else [target]
            outcomes = bring_companions(home, data, harnesses, pins,
                                         lambda *args: True, {})
            if any(item.get('state') in ('failed', 'refused') for item in outcomes.values()):
                raise InstallError('A shared companion could not be installed. Existing content was preserved.')
            results['companions'] = outcomes
        python = destination / 'runtime/python/bin/python3'
        environment = ('export PATH=' + shlex.quote(str(destination / 'runtime/python/bin') + ':' + str(destination / 'runtime/node/bin')) + ':"$PATH"\n') if distribution else shell_path()
        opener = '#!/bin/sh\n# Written by the Marketing Studio installer.\nexport PATH="$HOME/.local/bin:$PATH:/opt/homebrew/bin:/usr/local/bin"\n' + environment + 'exec ' + shlex.quote(str(python) if distribution else sys.executable) + ' ' + shlex.quote(str(data / 'current/marketing-studio')) + ' --open "$@"\n'
        atomic(data / 'marketing-studio', opener.replace(' --open', '').encode(), 0o755)
        link(home / '.local/bin/marketing-studio', data / 'marketing-studio')
        atomic(home / 'Applications/Open Marketing Studio.command', opener.encode(), 0o755)
        link(data / 'current', destination)
        # Do not grow rollback records on an identical repeat install.
        same = old and old.get('current') == key and old.get('studios') == selected
        record = {'schema': 1, 'version': (source / 'VERSION').read_text().strip(),
                  'current': key, 'studios': selected, 'target': target,
                  'previous': old.get('previous') if same else {'paths': saved, 'studios': available,
                                                              'companions': [str(p) for p in companion_paths]}}
        atomic(data / 'installation.json', (json.dumps(record, indent=2) + '\n').encode())
        return {'action': 'install', 'version': record['version'], 'studios': selected,
                'launcher': str(data / 'marketing-studio'), 'results': results}
    except BaseException:
        restore(saved, [*managed_paths(home, available, data), *companion_paths])
        raise
    finally:
        shutil.rmtree(pending, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='install', choices=('install', 'check', 'rollback', 'uninstall'))
    parser.add_argument('--studios', nargs='+', choices=STUDIOS)
    parser.add_argument('--target', choices=('auto', 'codex', 'claude', 'both'), default='auto')
    parser.add_argument('--companions', choices=('ask', 'install', 'skip'), default='ask')
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    home, source = args.home.expanduser().resolve(), args.source.expanduser().resolve()
    if args.target == 'auto':
        args.target = assistant_target(home)
    data = home / '.local/share/marketing-studio'
    available = [s for s in STUDIOS if (source / 'studios' / s / 'installer/install.py').is_file()]
    studios = args.studios or available
    try:
        if not studios or set(studios) - set(available):
            raise InstallError('The package does not contain the selected studios.')
        if args.dry_run:
            verify_bundle(source)
            result = {'action': 'plan', 'studios': studios, 'home': str(home), 'companions': args.companions}
        elif args.action == 'check':
            state = read_state(data)
            result = {'installed': bool(state), 'suite': state,
                      'studios': {s: (home / '.local/share' / (s + '-studio') / 'current').is_dir() for s in STUDIOS}}
        else:
            if not args.yes:
                if not sys.stdin.isatty() or input('Proceed with ' + args.action + '? [y/N]: ').lower() not in ('y', 'yes'):
                    raise InstallError('Nothing changed. Add --yes to authorize this operation without a prompt.')
            companions = args.companions
            if companions == 'ask' and (source / 'distribution.json').is_file():
                companions = 'install'
            elif companions == 'ask':
                companions = 'install' if sys.stdin.isatty() and input('Install the shared research and slide tools? [y/N]: ').lower() in ('y', 'yes') else 'skip'
            with locked(data):
                if args.action == 'install':
                    result = install(source, home, data, studios, args.target, companions)
                else:
                    state = read_state(data)
                    not_running(home, (state or {}).get('studios', []), data)
                    if not state:
                        raise InstallError('Marketing Studio is not installed here.')
                    if args.action == 'rollback':
                        previous = state.get('previous')
                        if not previous:
                            raise InstallError('No previous installation is recorded.')
                        permitted = offline_install.managed_paths(home, previous['studios'], 'both')
                        # Older records have no companion entries; derive the allowlist
                        # from fixed installation locations, never from saved path text.
                        has_companions = any(str(path) in previous['paths'] for path in permitted)
                        with offline_install.locked(home, previous['studios']) if has_companions else nullcontext():
                            restore(previous['paths'], [*managed_paths(home, previous['studios'], data), *permitted])
                        result = {'action': 'rollback', 'restored': True}
                    else:
                        # Independent studio installations, work, settings and versions stay available.
                        for path in (data / 'current', data / 'marketing-studio',
                                     home / 'Applications/Open Marketing Studio.command', home / '.local/bin/marketing-studio', data / 'installation.json'):
                            path.unlink(missing_ok=True)
                        result = {'action': 'uninstall', 'studios_kept': state['studios']}
        if args.json:
            print(json.dumps(result, indent=2))
        elif result.get('action') == 'install':
            print('Marketing Studio ' + result['version'] + ' is installed.')
            print('Studios: ' + ', '.join(name.title() + ' Studio' for name in result['studios']))
            print('Open: ' + str(home / 'Applications/Open Marketing Studio.command'))
            print('CLI: ' + str(home / '.local/bin/marketing-studio'))
            print('Next: marketing-studio setup')
        else:
            print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as failure:
        print(json.dumps({'error': str(failure)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
