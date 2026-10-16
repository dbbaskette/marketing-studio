"""Reproducible suite/subset archives that resolve shared checkout links."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

from .packaging import files

ROOT_FILES = ('VERSION', 'LICENSE', 'README.md', 'SUITE.json', 'marketing-studio',
              'Open Marketing Studio.command')
NATIVE_DIRS = {'skills', 'runner', 'installer', 'bootstrap', 'guidance'}
NATIVE_FILES = {'README.md', 'LICENSE', 'VERSION'}
SKIP = {'__pycache__', '.git', '.DS_Store', '.pytest_cache'}


def inventory(root, studios):
    root = Path(root)
    paths = [root / name for name in ROOT_FILES if (root / name).is_file()]
    for folder in ('core', 'ui-kit', 'pins', 'installer', 'marketing_studio', 'docs/assets'):
        paths += files(root / folder)
    for studio in studios:
        base = root / 'studios' / studio
        if not (base / 'installer/install.py').is_file():
            raise ValueError('This package does not contain ' + studio + '-studio.')
        paths += [base / name for name in NATIVE_FILES if (base / name).is_file()]
        for folder in NATIVE_DIRS:
            if (base / folder).is_dir():
                paths += files(base / folder)
    return {path.relative_to(root).as_posix(): path for path in paths
            if path.is_file() and not any(part in SKIP or part.startswith('.') for part in path.relative_to(root).parts)
            and path.suffix not in ('.pyc', '.pyo')}


def content_key(root, studios):
    digest = hashlib.sha256()
    for name, path in sorted(inventory(root, studios).items()):
        digest.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    return (Path(root) / 'VERSION').read_text().strip() + '-' + digest.hexdigest()[:12]


def materialize(root, destination, studios):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, source in inventory(root, studios).items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        target.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)


def build(root, output, selection=None):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    available = [name for name in ('blog', 'presentation', 'training')
                 if (root / 'studios' / name / 'installer/install.py').is_file()]
    groups = {'marketing-studio': selection or available}
    if selection is None:
        groups.update({name + '-studio': [name] for name in available})
    result = {}
    for product, studios in groups.items():
        target = output / (product + '-installer.zip')
        prefix = product + '-setup/'
        entries = inventory(root, studios)
        payload = {name: (source.read_bytes(), source.stat().st_mode) for name, source in entries.items()}
        manifest = {'schema': 1, 'studios': studios,
                    'files': {name: hashlib.sha256(data).hexdigest() for name, (data, _) in sorted(payload.items())}}
        payload['bundle-manifest.json'] = ((json.dumps(manifest, indent=2) + '\n').encode(), 0o644)
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, (data, mode) in sorted(payload.items()):
                info = zipfile.ZipInfo(prefix + name, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100755 if mode & 0o111 else 0o100644) << 16
                archive.writestr(info, data)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        (output / (target.name + '.sha256')).write_text(digest + '  ' + target.name + '\n')
        result[target.name] = digest
    return result
