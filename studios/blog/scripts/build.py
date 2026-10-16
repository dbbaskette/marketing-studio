#!/usr/bin/env python3
"""Build the release archives into an ignored directory. Nothing in the source tree changes.

    python3 scripts/build.py              # writes build/*.zip and build/*.zip.sha256
    python3 scripts/build.py --check      # builds twice in a temp dir and verifies the result

Archives are reproducible: entries are sorted and carry a fixed timestamp and
mode, so the same tree always produces the same bytes and checksums.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / 'skills/blog-studio'
TOOLKIT = REPO / 'skills/blog-writing-toolkit'
TIMESTAMP = (1980, 1, 1, 0, 0, 0)
INSTALLER_FILES = (
    'installer/Install Blog Studio.command',
    'installer/google-setup.sh',
    'installer/install.py',
    'installer/install.sh',
)
EXECUTABLE = {
    'installer/Install Blog Studio.command',
    'installer/google-setup.sh',
    'installer/install.sh',
}
BUNDLED_DOCS = ('docs/installation.md', 'docs/troubleshooting.md')
ARCHIVES = ('blog-studio-installer.zip', 'blog-studio.zip', 'blog-writing-toolkit.zip')


def load_installer():
    """The installer owns the inventory and manifest rules; the build reuses them."""
    spec = importlib.util.spec_from_file_location(
        'blog_studio_installer', REPO / 'installer/install.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contents():
    """The one include list: archive name -> {path inside archive: bytes}."""
    installer = load_installer()
    manifest = installer.package_manifest(SKILL)
    skill = {name: (SKILL / name).read_bytes() for name in manifest['files']}
    skill[installer.MANIFEST] = (json.dumps(manifest, indent=2) + '\n').encode()
    setup = {name: (REPO / name).read_bytes() for name in INSTALLER_FILES + BUNDLED_DOCS}
    setup.update({'skills/blog-studio/' + name: data for name, data in skill.items()})
    toolkit = {name: (TOOLKIT / name).read_bytes() for name in installer.inventory(TOOLKIT)}
    return manifest['version'], {
        'blog-studio-installer.zip': {
            'blog-studio-setup/' + name: data for name, data in setup.items()
        },
        'blog-studio.zip': {'blog-studio/' + name: data for name, data in skill.items()},
        'blog-writing-toolkit.zip': {
            'blog-writing-toolkit/' + name: data for name, data in toolkit.items()
        },
    }


def write_archive(path, entries):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            executable = name.split('/', 1)[1] in EXECUTABLE
            info.external_attr = (0o100755 if executable else 0o100644) << 16
            archive.writestr(info, entries[name])


def validate_sources():
    for script in (SKILL / 'scripts/validate_package.py', TOOLKIT / 'scripts/validate_package.py'):
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(result.stderr.strip() or 'Source validation failed: ' + str(script))
    for name in BUNDLED_DOCS:
        # Bundled guides travel without the repository, so their relative links must stay inside the bundle.
        source = REPO / name
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (source.parent / unquote(url.path)).resolve()
            if target.relative_to(REPO).as_posix() not in BUNDLED_DOCS:
                raise SystemExit(f'{name} links to {link}, which is not in the installer bundle.')


def build(output):
    """Write all archives and checksums into `output`; return {archive name: sha256}."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    version, archives = contents()
    digests = {}
    for name in ARCHIVES:
        target = output / name
        checksum = output / (name + '.sha256')
        for stale in (target, checksum):
            stale.unlink(missing_ok=True)
        write_archive(target, archives[name])
        digests[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        checksum.write_text(digests[name] + '  ' + name + '\n', encoding='utf-8')
    return version, digests


def check():
    """Prove the tree builds, the build is reproducible, and the archives hold what the source holds."""
    installer = load_installer()
    with tempfile.TemporaryDirectory(prefix='blog-studio-build-') as temporary:
        first = build(Path(temporary) / 'first')
        second = build(Path(temporary) / 'second')
        if first != second:
            raise SystemExit('Two builds of the same tree differ.')
        version, digests = first
        with zipfile.ZipFile(Path(temporary) / 'first/blog-studio-installer.zip') as archive:
            names = archive.namelist()
            if names != sorted(names) or any(
                item.date_time != TIMESTAMP for item in archive.infolist()
            ):
                raise SystemExit('Archive entries are not sorted with fixed timestamps.')
            archive.extractall(Path(temporary) / 'expanded')
        manifest = installer.verify_package(
            Path(temporary) / 'expanded/blog-studio-setup/skills/blog-studio'
        )
        if manifest['version'] != version or manifest != installer.package_manifest(SKILL):
            raise SystemExit('The bundled skill does not match the source tree.')
    return version, digests


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=REPO / 'build',
        help='Directory for archives (default: build/, ignored by Git)',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Verify a reproducible build in a temp dir; write nothing to --output',
    )
    args = parser.parse_args()
    validate_sources()
    version, digests = check() if args.check else build(args.output)
    print(
        json.dumps(
            {
                'version': version,
                'checked': args.check,
                'output': None if args.check else str(args.output),
                'sha256': digests,
            },
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
