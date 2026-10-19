#!/usr/bin/env python3
"""Regenerate the local Apple Silicon Presentation Studio bundle (Python 3.11+)."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core import bundles, distribution

TEMPLATES = ROOT / 'scripts/local_bundle'
ARCHIVES = {'libreoffice', 'micromamba', 'google_cloud_cli', 'codex', 'codex_native'}


def safe_name(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        raise ValueError('Unsafe bundle path: ' + name)
    return path


def load_lock(path):
    lock = json.loads(Path(path).read_text())
    if lock.get('schema') != 1 or lock.get('platform') != 'macos-arm64':
        raise ValueError('Expected an Apple Silicon Presentation Studio tools lock (schema 1).')
    if set(lock['archives']) != ARCHIVES or not lock['packages']:
        raise ValueError('Incomplete Presentation Studio tools lock.')
    if not isinstance(lock['minimum_macos'], int) or lock['minimum_macos'] < 13:
        raise ValueError('The minimum macOS version must be 13 or newer.')
    filenames = set()
    for pin in [*lock['archives'].values(), *lock['packages']]:
        if not re.fullmatch('[0-9a-f]{64}', pin['sha256']) or not pin['url'].startswith('https://'):
            raise ValueError('Every dependency requires an HTTPS URL and SHA-256 pin.')
        for name in pin.get('exclude', []):
            safe_name(name)
    for pin in lock['packages']:
        if '/' in pin['filename'] or '\\' in pin['filename']:
            raise ValueError('Package filenames must be basenames.')
        safe_name(pin['filename'])
        if pin['filename'] in filenames:
            raise ValueError('Duplicate package filename.')
        filenames.add(pin['filename'])
        if not any('/' + arch + '/' in pin['url'] for arch in ('osx-arm64', 'noarch')):
            raise ValueError('Preview packages must target Apple Silicon or be platform independent.')
    return lock


def build_path(path, root=ROOT):
    """Generated files belong outside Git, or under the existing ignored build/dist roots."""
    path = Path(path).expanduser().resolve()
    root = Path(root).resolve()
    if path.is_relative_to(root) and (path == root or path.relative_to(root).parts[0] not in ('build', 'dist')):
        raise ValueError('Keep generated bundles and caches outside the repository, or under build/ or dist/.')
    return path


def clean_environment(home, cache):
    home.mkdir(parents=True, exist_ok=True)
    for name in ('npm-user.conf', 'npm-global.conf'):
        (home / name).write_text('')
    env = {key: value for key, value in os.environ.items()
           if key in ('PATH', 'TMPDIR', 'SYSTEMROOT', 'SSL_CERT_FILE', 'SSL_CERT_DIR')}
    env.update(HOME=str(home), USERPROFILE=str(home), GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_NOSYSTEM='1', NPM_CONFIG_USERCONFIG=str(home / 'npm-user.conf'),
               NPM_CONFIG_GLOBALCONFIG=str(home / 'npm-global.conf'), NPM_CONFIG_CACHE=str(cache / 'npm'))
    return env


def run(command, env, cwd=None):
    result = subprocess.run(list(map(str, command)), env=env, cwd=cwd, text=True,
                            capture_output=True, timeout=900)
    if result.returncode:
        raise ValueError('Build command failed: ' + str(command[0]) + '\n' + result.stdout[-3000:] + result.stderr[-3000:])
    return result.stdout


def unpack_tar(archive, destination, exclude=()):
    """Strip the single archive root using the release builder's validated link handling."""
    # distribution.unpack handles gzip; micromamba's bzip2 archive is handled separately.
    distribution.unpack(archive, destination, exclude=exclude)


def unpack_zip(archive, destination):
    with zipfile.ZipFile(archive) as source:
        seen = set()
        for item in source.infolist():
            relative = safe_name(item.filename.rstrip('/'))
            if str(relative) in seen:
                raise ValueError('Duplicate ZIP member.')
            seen.add(str(relative))
            if item.is_dir():
                continue
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('ZIP links are not allowed.')
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(item) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
            target.chmod(0o755 if item.external_attr >> 16 & 0o111 else 0o644)


def extract_micromamba(archive, payload):
    with tarfile.open(archive, 'r:bz2') as source:
        binary = source.getmember('bin/micromamba')
        if not binary.isfile():
            raise ValueError('Micromamba executable must be a regular file.')
        with source.extractfile(binary) as src, (payload / 'micromamba').open('xb') as dst:
            shutil.copyfileobj(src, dst)
        (payload / 'micromamba').chmod(0o755)
        notices = [item for item in source.getmembers()
                   if item.name.startswith('info/licenses/') and item.isfile()]
        if not notices:
            raise ValueError('Micromamba dependency notices are missing.')
        for item in notices:
            relative = safe_name(item.name)
            path = payload / 'micromamba-licenses' / Path(*relative.parts[2:])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.extractfile(item).read())


def require_arm64(path):
    with Path(path).open('rb') as stream:
        header = stream.read(8)
    if len(header) != 8 or header[:4] != b'\xcf\xfa\xed\xfe' or struct.unpack('<I', header[4:])[0] != 0x0100000c:
        raise ValueError('Expected a native ARM64 Mach-O executable: ' + str(path))


def prepare_tools(lock, cache, payload):
    downloads = cache / 'downloads'
    pins = [*lock['archives'].values(), *lock['packages']]
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Waiting on every future propagates a failed checksum before anything is packaged.
        paths = list(executor.map(lambda pin: distribution.download(pin, downloads), pins))
    archives = dict(zip(lock['archives'], paths[:len(ARCHIVES)]))
    payload.mkdir()
    shutil.copy2(archives['libreoffice'], payload / 'LibreOffice.dmg')
    extract_micromamba(archives['micromamba'], payload)
    unpack_tar(archives['google_cloud_cli'], payload / 'google-cloud-sdk',
               exclude=lock['archives']['google_cloud_cli'].get('exclude', ()))
    modules = payload / 'assistant/node_modules/@openai'
    modules.mkdir(parents=True)
    unpack_tar(archives['codex'], modules / 'codex')
    unpack_tar(archives['codex_native'], modules / 'codex-darwin-arm64')
    for item in ('codex', 'codex_native'):
        folder = 'codex' if item == 'codex' else 'codex-darwin-arm64'
        version = json.loads((modules / folder / 'package.json').read_text())['version']
        if version != lock['archives'][item]['version']:
            raise ValueError('Codex version differs from its lock.')
    if (payload / 'google-cloud-sdk/VERSION').read_text().strip() != lock['archives']['google_cloud_cli']['version']:
        raise ValueError('Google Cloud CLI version differs from its lock.')
    packages = payload / 'packages'
    packages.mkdir()
    for pin, source in zip(lock['packages'], paths[len(ARCHIVES):]):
        shutil.copy2(source, packages / pin['filename'])
    (payload / 'packages.json').write_text(json.dumps(lock['packages'], indent=2) + '\n')
    require_arm64(payload / 'micromamba')
    require_arm64(modules / 'codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex')


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Bundle files must be regular: ' + str(path))
        if path.is_file() and path != root / 'local-manifest.json':
            result[path.relative_to(root).as_posix()] = distribution.digest(path)
    return result


def verify_archive(path):
    """Cross-platform verification: reject unexpected entries, unsafe names, and changed bytes."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries.')
        for name in names:
            safe_name(name)
        manifests = [name for name in names if name.count('/') == 1 and name.endswith('/local-manifest.json')]
        if len(manifests) != 1:
            raise ValueError('Expected one top-level local bundle manifest.')
        prefix = manifests[0].rsplit('/', 1)[0] + '/'
        manifest = json.loads(archive.read(manifests[0]))
        expected = {prefix + str(safe_name(name)) for name in manifest['files']} | set(manifests)
        if set(names) != expected:
            raise ValueError('Unexpected or missing archive files.')
        for name, checksum in manifest['files'].items():
            item = archive.getinfo(prefix + name)
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive links are not allowed.')
            with archive.open(item) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != checksum:
                    raise ValueError('Bundle checksum failed: ' + name)
    return manifest


def write_archive(root, output, manifest):
    """Fixed timestamps, sorted entries, and atomic publication preserve previous good builds."""
    output.mkdir(parents=True, exist_ok=True)
    target = output / (root.name + '-' + manifest['id'].rsplit('-', 1)[-1] + '.zip')
    with tempfile.NamedTemporaryFile(prefix='.presentation-bundle-', suffix='.zip', dir=output, delete=False) as stream:
        pending = Path(stream.name)
    try:
        with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
            for path in sorted(root.rglob('*')):
                if not path.is_file():
                    continue
                info = zipfile.ZipInfo(root.name + '/' + path.relative_to(root).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100755 if path.stat().st_mode & 0o111 else 0o100644) << 16
                with path.open('rb') as src, archive.open(info, 'w', force_zip64=True) as dst:
                    shutil.copyfileobj(src, dst)
        print('Verifying the completed archive…', flush=True)
        verify_archive(pending)
        checksum = distribution.digest(pending)
        if target.exists():
            if distribution.digest(target) != checksum:
                raise ValueError('Refusing to replace a different existing bundle: ' + str(target))
        else:
            # Exclusive creation also protects against a concurrent build publishing this name.
            os.link(pending, target)
        sidecar = target.with_suffix('.zip.sha256')
        text = checksum + '  ' + target.name + '\n'
        if sidecar.exists() and sidecar.read_text() != text:
            raise ValueError('Existing SHA-256 sidecar differs: ' + str(sidecar))
        if not sidecar.exists():
            with sidecar.open('x') as stream:
                stream.write(text)
        return target, checksum
    finally:
        pending.unlink(missing_ok=True)


def build(brand, output, cache, lock):
    if not (brand / 'scripts/pack-skill.mjs').is_file():
        raise ValueError('--brand must point to the Tanzu Brand source project.')
    output, cache = build_path(output), build_path(cache)
    if output.is_relative_to(brand) or cache.is_relative_to(brand):
        raise ValueError('Build output and cache must be outside the brand source.')
    for command in ('node', 'npm', 'git'):
        if not shutil.which(command):
            raise ValueError('Install the build prerequisite: ' + command)
    version = (ROOT / 'VERSION').read_text().strip()
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='presentation-build-', dir=cache) as temporary:
        work = Path(temporary)
        env = clean_environment(work / 'home', cache)
        print('Packing the current Tanzu Brand source…', flush=True)
        brand_zip = work / 'brand.zip'
        brand_record = json.loads(run(['node', brand / 'scripts/pack-skill.mjs', '--output', brand_zip], env))
        brand_version = brand_record['version']
        if not all(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[\w.-]+)?', v) for v in (version, brand_version)):
            raise ValueError('Expected safe semantic studio and brand versions.')
        stage = work / f'Presentation-Studio-{version}-Tanzu-{brand_version}-macos-arm64'
        stage.mkdir()
        unpack_zip(brand_zip, stage / 'brand')
        print('Preparing Presentation Studio and its pinned runtimes/companions…', flush=True)
        studio = stage / 'studio'
        bundles.materialize(ROOT, studio, ['presentation'])
        record = distribution.prepare(ROOT, studio, 'macos-arm64', cache, ['presentation'])
        entries = bundles.inventory(studio, ['presentation'])
        (studio / 'bundle-manifest.json').write_text(json.dumps({
            'schema': 1, 'studios': ['presentation'],
            'files': {name: distribution.digest(path) for name, path in sorted(entries.items())}}, indent=2) + '\n')
        print('Preparing locked offline tools…', flush=True)
        prepare_tools(lock, cache, stage / 'payload')
        for name in ('install-local.py', 'install-brand.mjs', 'verify-installed.py', 'Install Presentation Studio.command'):
            shutil.copy2(TEMPLATES / name, stage / name)
        for name in ('install-local.py', 'verify-installed.py'):
            ast.parse((stage / name).read_text())
        (stage / 'Install Presentation Studio.command').chmod(0o755)
        values = {'STUDIO_VERSION': version, 'BRAND_VERSION': brand_version,
                  'MINIMUM_MACOS': str(lock['minimum_macos']),
                  'PYTHON_VERSION': record['runtimes']['python']['version'],
                  'NODE_VERSION': record['runtimes']['node']['version'],
                  'SLIDES_VERSION': record['companions']['harness-slides']['version'],
                  'RESEARCH_VERSION': record['companions']['harness-research']['version'],
                  **{name.upper() + '_VERSION': pin['version'] for name, pin in lock['archives'].items()}}
        instructions = (TEMPLATES / 'START HERE.txt').read_text()
        for name, value in values.items():
            instructions = instructions.replace('@' + name + '@', value)
        (stage / 'START HERE.txt').write_text(instructions)
        for path in (studio / 'runtime/python/bin/python3', studio / 'runtime/node/bin/node'):
            require_arm64(path)
        files = inventory(stage)
        # Include permissions in the identity; the ZIP preserves executable bits too.
        modes = {name: bool((stage / name).stat().st_mode & 0o111) for name in files}
        manifest = {'schema': 1, 'platform': 'macos-arm64', 'minimum_macos': lock['minimum_macos'],
                    'files': files, 'source_commit': run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], env).strip(),
                    'source_modified': bool(run(['git', '-C', ROOT, 'status', '--porcelain', '--untracked-files=normal'], env).strip()),
                    'brand_commit': brand_record['sourceCommit'], 'brand_version': brand_version,
                    'tools': lock, 'distribution': record,
                    'validation': {'native_arm_execution': False, 'live_provider_calls': False}}
        content = hashlib.sha256(json.dumps([manifest, modes], sort_keys=True).encode()).hexdigest()[:12]
        manifest['id'] = f'{version}-tanzu-{brand_version}-macos-arm64-{content}'
        (stage / 'local-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(f'Packaging {len(files):,} verified files…', flush=True)
        return write_archive(stage, output, manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brand', type=Path, default=ROOT.parent / 'tanzu-brand', help='Tanzu Brand source checkout (default: sibling tanzu-brand).')
    parser.add_argument('--output', type=Path, default=Path.home() / 'LocalBundles/presentation-studio')
    parser.add_argument('--cache', type=Path, help='Verified downloads; defaults to OUTPUT/cache.')
    parser.add_argument('--tools-lock', type=Path, default=ROOT / 'pins/presentation-bundle.json')
    parser.add_argument('--plan', action='store_true', help='Show component versions and paths without downloads or writes.')
    parser.add_argument('--verify', type=Path, metavar='ZIP', help='Verify an existing bundle; works on Intel too.')
    args = parser.parse_args(argv)
    try:
        if args.verify:
            manifest = verify_archive(args.verify)
            print('PASS: ' + manifest['id'])
            return 0
        lock = load_lock(args.tools_lock)
        output = build_path(args.output)
        cache = build_path(args.cache or output / 'cache')
        brand = args.brand.expanduser().resolve()
        if args.plan:
            print(json.dumps({'platform': lock['platform'], 'brand_source': str(brand),
                              'brand_version': json.loads((brand / 'package.json').read_text())['version'],
                              'studio_version': (ROOT / 'VERSION').read_text().strip(),
                              'companions': json.loads((ROOT / 'pins/companions.json').read_text())['companions'],
                              'tools': {name: pin['version'] for name, pin in lock['archives'].items()},
                              'output': str(output), 'cache': str(cache)}, indent=2))
            return 0
        target, checksum = build(brand, output, cache, lock)
        print(json.dumps({'bundle': str(target), 'sha256': checksum}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError, zipfile.BadZipFile) as error:
        print('Presentation Studio packaging failed: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
