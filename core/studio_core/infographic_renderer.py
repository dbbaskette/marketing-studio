"""Pinned Infographic Studio renderer preparation, only during an explicit package build."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

from .distribution import download, digest


def prepare(root, runtime, target, cache):
    pins = json.loads((Path(root) / 'pins/infographic-renderer.json').read_text())
    pin = pins['platforms'].get(target)
    if pin is None:
        raise ValueError('Infographic Studio has no pinned renderer for ' + target + '. Select a supported platform or a subset without Infographic Studio.')
    archive = download(pin, Path(cache) / 'downloads')
    destination = Path(runtime) / 'renderer'
    destination.mkdir()
    total, seen = 0, set()
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename or item.filename in seen or stat.S_ISLNK(mode):
                raise ValueError('The renderer archive contains an unsafe path or link.')
            seen.add(item.filename)
            if item.is_dir(): continue
            if mode & 0o170000 not in (0, stat.S_IFREG): raise ValueError('The renderer archive contains a special file.')
            total += item.file_size
            if len(seen) > 2000 or total > 800_000_000: raise ValueError('The renderer archive exceeds its limits.')
            output = destination / item.filename
            output.parent.mkdir(parents=True, exist_ok=True)
            raw = zipped.read(item)
            output.write_bytes(raw)
            output.chmod(0o755 if mode & 0o111 or item.filename == pin['executable'] else 0o644)
    executable = destination / pin['executable']
    if digest(executable) != pin['executable_sha256']: raise ValueError('The renderer executable failed its checksum.')
    record = {'schema': 1, 'platform': target, 'version': pins['version'],
              'executable': pin['executable'], 'sha256': pin['executable_sha256'], 'archive_sha256': pin['sha256']}
    (destination / 'renderer.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
