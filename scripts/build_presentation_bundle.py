#!/usr/bin/env python3
"""Build local Apple Silicon studio bundles with private runtimes, skills and brand."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core import bundles, distribution, bundle_sources

TEMPLATES = ROOT / 'scripts/local_bundle'
sys.path.insert(0, str(TEMPLATES))
from tool_payload import prepare_tools, require_arm64

ARCHIVES = {'libreoffice', 'micromamba', 'google_cloud_cli'}
DEFAULT_CONFIG = ROOT / 'presentation-studio-package.local.json'
SHARED_CONFIG = ROOT / 'studio-package.local.json'
PRODUCTS = {'marketing': ['blog', 'presentation', 'training'],
            'blog': ['blog'], 'presentation': ['presentation'], 'training': ['training']}


def install_cli(home=None, command='presentation-studio-package'):
    """Link this checkout's CLI into local bin without replacing another command."""
    source = ROOT / command
    if not source.is_file():
        raise ValueError('The Presentation Studio packaging command is missing from this checkout.')
    target = (Path.home() if home is None else Path(home)) / '.local/bin' / source.name
    if target.is_symlink() and target.resolve() == source.resolve():
        return target
    if target.exists() or target.is_symlink():
        raise ValueError('An unrelated command already exists at ' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)
    return target


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


def build(brand, output, cache, lock, sources=None, mode='online', product='presentation'):
    if product not in PRODUCTS:
        raise ValueError('Choose Marketing Studio, Blog Studio, Presentation Studio or Training Studio.')
    selected = PRODUCTS[product]
    title = product.title() + ' Studio'
    if mode not in ('online', 'offline'):
        raise ValueError('Unknown Presentation Studio bundle mode: ' + str(mode))
    sources = dict(sources or {})
    if selected == ['blog']:
        sources.pop('harness-slides', None)
    sources.setdefault('brand', {'path': str(brand)})
    output, cache = build_path(output), build_path(cache)
    for spec in sources.values():
        if 'path' in spec and (output.is_relative_to(spec['path']) or cache.is_relative_to(spec['path'])):
            raise ValueError('Build output and cache must be outside component source checkouts.')
    for command in ('node', 'npm', 'git'):
        if not shutil.which(command):
            raise ValueError('Install the build prerequisite: ' + command)
    version = (ROOT / 'VERSION').read_text().strip()
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='presentation-build-', dir=cache) as temporary:
        work = Path(temporary)
        env = clean_environment(work / 'home', cache)
        print('Snapshotting configured component repositories…', flush=True)
        snapshots, provenance = {}, {}
        for name, spec in sources.items():
            snapshots[name], provenance[name] = bundle_sources.snapshot(spec, work / 'sources' / name, env)
        brand = snapshots.pop('brand')
        if not (brand / 'scripts/pack-skill.mjs').is_file():
            raise ValueError('The brand repository must provide the Tanzu Brand release packer.')
        print('Packing the current Tanzu Brand source…', flush=True)
        brand_zip = work / 'brand.zip'
        brand_record = json.loads(run(['node', brand / 'scripts/pack-skill.mjs', '--output', brand_zip], env))
        brand_version = brand_record['version']
        if not all(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[\w.-]+)?', v) for v in (version, brand_version)):
            raise ValueError('Expected safe semantic studio and brand versions.')
        stage = work / f'{title.replace(" ", "-")}-{version}-Tanzu-{brand_version}-macos-arm64-{mode}'
        stage.mkdir()
        unpack_zip(brand_zip, stage / 'brand')
        print('Preparing ' + title + ' and its pinned runtimes/companions…', flush=True)
        studio = stage / 'studio'
        bundles.materialize(ROOT, studio, selected)
        companion_locks = json.loads((studio / 'pins/companions.json').read_text())
        for name, source in snapshots.items():
            companion_locks['companions'][name] = bundle_sources.companion_pin(
                name, source, provenance[name], companion_locks['companions'][name])
            shutil.rmtree(source / '.git')
        for path in studio.rglob('companions.json'):
            path.write_text(json.dumps(companion_locks, indent=2) + '\n')
        record = distribution.prepare(ROOT, studio, 'macos-arm64', cache, selected,
                                      companion_sources=snapshots)
        entries = bundles.inventory(studio, selected)
        (studio / 'bundle-manifest.json').write_text(json.dumps({
            'schema': 1, 'studios': selected,
            'files': {name: distribution.digest(path) for name, path in sorted(entries.items())}}, indent=2) + '\n')
        if mode == 'offline':
            print('Preparing locked offline tools…', flush=True)
            prepare_tools(lock, cache, stage / 'payload')
        else:
            print('Recording pinned tools for download during installation…', flush=True)
        for name in ('install.sh', 'install-local.py', 'install-brand.mjs', 'verify-installed.py', 'tool_payload.py', 'Install Presentation Studio.command'):
            shutil.copy2(TEMPLATES / name, stage / name)
        if product != 'presentation':
            (stage / 'Install Presentation Studio.command').rename(stage / ('Install ' + title + '.command'))
        (stage / 'installer').mkdir()
        shutil.copy2(TEMPLATES / 'bootstrap.sh', stage / 'installer/install.sh')
        (stage / 'installer/install.sh').chmod(0o755)
        for name in ('install-local.py', 'verify-installed.py', 'tool_payload.py'):
            ast.parse((stage / name).read_text())
        (stage / ('Install ' + title + '.command')).chmod(0o755)
        (stage / 'install.sh').chmod(0o755)
        values = {'PRODUCT_NAME': title, 'PRODUCT_SLUG': product + '-studio',
                  'PRODUCT_START': '.local/share/marketing-studio/marketing-studio' if product == 'marketing' else '.local/share/' + product + '-studio/studio',
                  'SELECTED_STUDIOS': ', '.join(name.title() + ' Studio' for name in selected),
                  'SLIDES_CONTENT': ('Harness Slides ' + record['companions']['harness-slides']['version'] + ' with production Node packages and Gemini API image tools;\n' if 'harness-slides' in record['companions'] else ''),
                  'BUNDLE_MODE': mode,
                  'SETUP_DOWNLOADS': ('Setup downloads pinned preview and Google tools.\nAn internet connection is required for the first installation; verified downloads\nare cached for retries.' if mode == 'online' else
                                     'Setup installs tools from this archive without downloading dependencies.'),
                  'TOOLS_DELIVERY': ('DOWNLOADED DURING SETUP' if mode == 'online' else 'ALSO INCLUDED'),
                  'STUDIO_VERSION': version, 'BRAND_VERSION': brand_version,
                  'MINIMUM_MACOS': str(lock['minimum_macos']),
                  'PYTHON_VERSION': record['runtimes']['python']['version'],
                  'NODE_VERSION': record['runtimes']['node']['version'],
                  'SLIDES_VERSION': record['companions'].get('harness-slides', {}).get('version', 'not included'),
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
                    'product': product, 'studios': selected,
                    'mode': mode, 'files': files, 'source_commit': run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], env).strip(),
                    'source_modified': bool(run(['git', '-C', ROOT, 'status', '--porcelain', '--untracked-files=normal'], env).strip()),
                    'brand_commit': brand_record['sourceCommit'], 'brand_version': brand_version,
                    'sources': provenance,
                    'tools': lock, 'distribution': record,
                    'validation': {'native_arm_execution': False, 'live_provider_calls': False}}
        content = hashlib.sha256(json.dumps([manifest, modes], sort_keys=True).encode()).hexdigest()[:12]
        manifest['id'] = f'{version}-tanzu-{brand_version}-macos-arm64-{mode}-{content}'
        (stage / 'local-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(f'Packaging {len(files):,} verified files…', flush=True)
        return write_archive(stage, output, manifest)


def main(argv=None, product='presentation', prog='presentation-studio-package'):
    if product not in PRODUCTS:
        raise ValueError('Unknown studio product.')
    selected = PRODUCTS[product]
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument('--mode', choices=('online', 'offline'), default='online',
                        help='Online (default) includes Python/Node and downloads tools at setup; offline includes all tools.')
    parser.add_argument('--brand', type=Path, help='Override the configured brand with a local checkout.')
    parser.add_argument('--config', type=Path, help='Source config (default: ignored studio-package.local.json, with legacy config fallback).')
    parser.add_argument('--output', type=Path, default=Path.home() / 'LocalBundles' / (product + '-studio'))
    parser.add_argument('--cache', type=Path, help='Verified downloads; defaults to OUTPUT/cache.')
    parser.add_argument('--tools-lock', type=Path, default=ROOT / 'pins/presentation-bundle.json')
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--install-cli', action='store_true', help='Make this checkout’s packaging command available in ~/.local/bin.')
    actions.add_argument('--init-config', action='store_true', help='Create a local source config from the tracked example.')
    actions.add_argument('--plan', action='store_true', help='Show component versions and paths without downloads or writes.')
    actions.add_argument('--verify', type=Path, metavar='ZIP', help='Verify an existing bundle; works on Intel too.')
    args = parser.parse_args(argv)
    try:
        if args.init_config:
            path = bundle_sources.init_config(args.config or SHARED_CONFIG,
                                              ROOT / 'studio-package.example.json')
            print('Created ' + str(path))
            print('Edit sources, then run: ' + prog)
            return 0
        if args.install_cli:
            target = install_cli(command='presentation-studio-package' if prog == 'presentation-studio-package' else 'studio-package')
            print('Installed ' + str(target))
            print('Build a bundle: ' + prog)
            if str(target.parent) not in os.environ.get('PATH', '').split(os.pathsep):
                print('Add ~/.local/bin to your terminal PATH: export PATH="$HOME/.local/bin:$PATH"')
            return 0
        if args.verify:
            manifest = verify_archive(args.verify)
            print('PASS: ' + manifest['id'])
            return 0
        lock = load_lock(args.tools_lock)
        output = build_path(args.output)
        cache = build_path(args.cache or output / 'cache')
        config = args.config.expanduser().resolve() if args.config else SHARED_CONFIG if SHARED_CONFIG.exists() else DEFAULT_CONFIG
        sources = bundle_sources.load_config(config) if args.config or config.exists() else {}
        if selected == ['blog']:
            sources.pop('harness-slides', None)
        if args.brand:
            sources['brand'] = bundle_sources.source_spec({'path': str(args.brand)}, Path.cwd())
        brand = Path(sources.get('brand', {}).get('path', ROOT.parent / 'tanzu-brand'))
        if args.plan:
            brand_spec = sources.get('brand', {'path': str(brand)})
            package = brand / 'package.json'
            companions = json.loads((ROOT / 'pins/companions.json').read_text())['companions']
            if selected == ['blog']:
                companions.pop('harness-slides', None)
            for name, spec in sources.items():
                if name != 'brand':
                    package_path = Path(spec['path']) / 'package.json' if 'path' in spec else None
                    companions[name] = {'source': spec, 'version': json.loads(package_path.read_text()).get('version')
                                        if package_path and package_path.is_file() else None}
            print(json.dumps({'product': product, 'studios': selected,
                              'platform': lock['platform'], 'mode': args.mode, 'brand_source': brand_spec.get('git', str(brand)),
                              'brand_version': json.loads(package.read_text())['version'] if 'path' in brand_spec and package.is_file() else None,
                              'sources': {**sources, 'brand': brand_spec},
                              'studio_version': (ROOT / 'VERSION').read_text().strip(),
                              'companions': companions,
                              'tools': {name: pin['version'] for name, pin in lock['archives'].items()},
                              'output': str(output), 'cache': str(cache)}, indent=2))
            return 0
        target, checksum = build(brand, output, cache, lock, sources, mode=args.mode, product=product)
        print(json.dumps({'bundle': str(target), 'sha256': checksum}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(product.title() + ' Studio packaging failed: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
