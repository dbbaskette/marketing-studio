#!/usr/bin/env python3
"""Local Presentation Studio bundle installer; no provider jobs or sign-in."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def run(command, env, timeout=600):
    result = subprocess.run([str(x) for x in command], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stdout[-8000:])
    return result.stdout


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic(path, text, mode=0o755):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '-',
                                     mode='w', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def existing_assistant(current, target, env):
    saved = (current.get('assistant') or {}).get('agent')
    candidates = (saved,) if saved in ('codex', 'claude') else \
        (target,) if target != 'both' else ('codex', 'claude')
    for agent in candidates:
        if shutil.which(agent, path=env.get('PATH')):
            return agent
    raise RuntimeError('An existing Codex or Claude Code installation is required. '
                       'Make the selected assistant available on PATH, then rerun setup.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--target', choices=('codex', 'claude', 'both'), default='both')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'local-manifest.json').read_text())
    print('Checking bundle integrity…', flush=True)
    for name, expected in manifest['files'].items():
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise RuntimeError('Bundle integrity check failed: ' + name)
    if args.verify_only:
        print('PASS: all bundled files match their checksums.')
        return
    minimum = manifest['minimum_macos']
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('This local bundle requires an Apple Silicon Mac.')
    if int(platform.mac_ver()[0].split('.')[0]) < minimum:
        raise RuntimeError(f'macOS {minimum} or newer is required.')
    home = args.home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    config = str(home / '.config/studios-config.json')
    if home == Path.home().resolve():
        config = os.environ.get('STUDIOS_CONFIG', config)
    env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home),
           'STUDIOS_CONFIG': config, 'CODEX_HOME': str(home / '.codex'),
           'CLAUDE_CONFIG_DIR': str(home / '.claude'),
           'MARKETING_STUDIO_DATA': str(home / '.local/share/marketing-studio'),
           'PRESENTATION_STUDIO_DATA': str(home / '.local/share/presentation-studio')}
    env['PATH'] = ':'.join([str(home / '.local/bin'), '/opt/homebrew/bin', '/usr/local/bin',
                            env.get('PATH', '/usr/bin:/bin')])
    os.environ.update(env)
    sys.path.insert(0, str(ROOT / 'studio/core'))
    from studio_core import studios_config
    existing, problem = studios_config.read()
    if problem:
        raise RuntimeError(problem)
    agent = existing_assistant(existing, args.target, env)
    base = home / '.local/share/presentation-studio-local-bundle'
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        install(home, base, env, args.target, manifest, studios_config, agent)


def install_tools(payload, version, env):
    print('Installing private Git and preview dependencies…', flush=True)
    packages = json.loads((payload / 'packages.json').read_text())
    with tempfile.TemporaryDirectory(prefix='presentation-offline-') as scratch:
        scratch = Path(scratch)
        spec = scratch / 'packages.txt'
        spec.write_text('@EXPLICIT\n' + '\n'.join(
            (payload / 'packages' / item['filename']).as_uri() + '#' + item['sha256']
            for item in packages) + '\n')
        run([payload / 'micromamba', '--no-rc', '-r', scratch / 'cache',
             'create', '-y', '--offline', '--always-copy', '-p', version / 'tools', '-f', spec], env)
    print('Installing the private LibreOffice application…', flush=True)
    with tempfile.TemporaryDirectory(prefix='presentation-office-') as scratch:
        mount = Path(scratch) / 'volume'
        run(['/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', mount,
             payload / 'LibreOffice.dmg'], env)
        try:
            run(['/usr/bin/ditto', mount / 'LibreOffice.app', version / 'LibreOffice.app'], env)
        finally:
            run(['/usr/bin/hdiutil', 'detach', mount], env)
    shutil.copytree(payload / 'google-cloud-sdk', version / 'google-cloud-sdk')


def install(home, base, env, target, manifest, config, agent):
    node = ROOT / 'studio/runtime/node/bin/node'
    python = ROOT / 'studio/runtime/python/bin/python3'
    brand_script = ROOT / 'install-brand.mjs'
    # Plan before any suite pointers change. Existing unrelated brand folders are preserved.
    run([node, brand_script, ROOT / 'brand', home, target, 'check'], env)
    version = base / 'versions' / manifest['id']
    ready = version / 'ready.json'
    if not ready.is_file():
        if version.exists():
            raise RuntimeError('An incomplete local tools installation remains at ' + str(version)
                               + '. Preserve it for diagnosis before retrying.')
        version.mkdir(parents=True)
        try:
            sys.path.insert(0, str(ROOT))
            from tool_payload import installer_payload
            with installer_payload(ROOT, manifest, base / 'cache') as payload:
                install_tools(payload, version, env)
            ready.write_text(json.dumps({'id': manifest['id']}))
        except BaseException:
            # Only this attempt's new private tools folder is removed; existing versions stay.
            shutil.rmtree(version)
            raise
    binaries = version / 'bin'
    binaries.mkdir(exist_ok=True)
    atomic(binaries / 'soffice', '#!/bin/sh\nexec ' + shlex.quote(str(version / 'LibreOffice.app/Contents/MacOS/soffice')) + ' "$@"\n')
    # The native installer embeds the private Python/Node paths into its launchers.
    env['PATH'] = ':'.join(map(str, [binaries, version / 'tools/bin', python.parent, node.parent])) + ':' + env.get('PATH', '/usr/bin:/bin')
    print('Installing Presentation Studio and its bundled skills…', flush=True)
    print(run([python, ROOT / 'studio/installer/install.py', 'install', '--source', ROOT / 'studio',
               '--home', home, '--studios', 'presentation', '--target', target,
               '--companions', 'install', '--yes'], env), flush=True)
    suite = (home / '.local/share/marketing-studio/current').resolve()
    installed_node = suite / 'runtime/node/bin/node'
    atomic(binaries / 'gcloud', '#!/bin/sh\nexport CLOUDSDK_PYTHON=' + shlex.quote(str(suite / 'runtime/python/bin/python3')) + '\nexec ' + shlex.quote(str(version / 'google-cloud-sdk/bin/gcloud')) + ' "$@"\n')
    brand = json.loads(run([installed_node, brand_script, ROOT / 'brand', home, target, 'install'], env))
    paths = [binaries, version / 'tools/bin', suite / 'runtime/python/bin', installed_node.parent]
    environment = 'export PATH=' + shlex.quote(':'.join(map(str, paths))) + ':"$PATH"\n'
    environment += 'export HARNESS_SOFFICE=' + shlex.quote(str(binaries / 'soffice')) + '\n'
    environment += 'export HARNESS_PDFTOPPM=' + shlex.quote(str(version / 'tools/bin/pdftoppm')) + '\n'
    environment += 'export HARNESS_PDFINFO=' + shlex.quote(str(version / 'tools/bin/pdfinfo')) + '\n'
    atomic(version / 'environment.sh', environment, 0o644)
    for path in (home / '.local/share/presentation-studio/studio',
                 home / '.local/share/presentation-studio/presentation',
                 home / '.local/share/marketing-studio/marketing-studio',
                 home / 'Applications/Open Presentation Studio.command',
                 home / 'Applications/Open Marketing Studio.command'):
        if path.is_file():
            text = path.read_text()
            marker = '. ' + shlex.quote(str(version / 'environment.sh')) + '\n'
            if marker not in text:
                first, rest = text.split('\n', 1)
                atomic(path, first + '\n' + marker + rest)
    def defaults(current):
        changes = {}
        if not (current.get('brand') or {}).get('skill') and not (current.get('brand') or {}).get('repository'):
            changes['brand'] = {'skill': brand['current']}
        if not (current.get('assistant') or {}).get('agent'):
            changes['assistant'] = {'agent': agent}
        if not current.get('output'):
            changes['output'] = 'pptx'
        return changes
    config.update(defaults)
    record = {'bundle': manifest['id'], 'tools': str(version), 'suite': str(suite),
              'brand': brand['current'], 'environment': str(version / 'environment.sh'), 'assistant': agent}
    atomic(base / 'installation.json', json.dumps(record, indent=2) + '\n', 0o600)
    shutil.copy2(ROOT / 'verify-installed.py', version / 'verify-installed.py')
    verify_command = '#!/bin/bash\nset -euo pipefail\nexec ' + shlex.quote(str(suite / 'runtime/python/bin/python3')) + ' ' + shlex.quote(str(version / 'verify-installed.py')) + '\n'
    for suffix in ('sh', 'command'):
        atomic(home / ('Applications/Verify Presentation Studio.' + suffix), verify_command)
    shell_rc = '. ' + shlex.quote(str(version / 'environment.sh')) + '\n'
    shell_rc += 'echo "Use your existing assistant. Google sign-in: gcloud auth login --enable-gdrive-access --force"\n'
    atomic(version / 'tools-shell.sh', shell_rc, 0o644)
    tools_command = '#!/bin/bash\nexec /bin/bash --rcfile ' + shlex.quote(str(version / 'tools-shell.sh')) + ' -i\n'
    for suffix in ('sh', 'command'):
        atomic(home / ('Applications/Open Presentation Studio Tools.' + suffix), tools_command)
    print('Installed. Open Presentation Studio from Terminal:')
    print('  bash ' + shlex.quote(str(home / '.local/share/presentation-studio/studio')))
    print('Complete assistant sign-in in your own terminal before starting a job.')
    print('Assistant: ' + ('Claude Code' if agent == 'claude' else 'Codex') + ' (existing installation)')
    print('Existing workspaces and saved choices were preserved. Setup remains explicit.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Installation stopped: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
