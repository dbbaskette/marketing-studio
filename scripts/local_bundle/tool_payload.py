"""Pinned private tools shared by the Presentation Studio builder and installer."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import tarfile
import tempfile
import time

from studio_core import distribution


def require_arm64(path):
    with Path(path).open('rb') as stream:
        header = stream.read(8)
    if len(header) != 8 or header[:4] != b'\xcf\xfa\xed\xfe' or struct.unpack('<I', header[4:])[0] != 0x0100000c:
        raise ValueError('Expected a native ARM64 Mach-O executable: ' + str(path))


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
            relative = PurePosixPath(item.name)
            if '..' in relative.parts or '\\' in item.name:
                raise ValueError('Unsafe Micromamba license path.')
            path = payload / 'micromamba-licenses' / Path(*relative.parts[2:])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.extractfile(item).read())


def download(pin, cache):
    # Checksum failures stop immediately. Interrupted network requests can retry;
    # distribution.download publishes only complete, verified files to the cache.
    for attempt in range(3):
        try:
            return distribution.download(pin, cache)
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def prepare_tools(lock, cache, payload):
    downloads = cache / 'downloads'
    pins = [*lock['archives'].values(), *lock['packages']]
    print('Checking/downloading pinned LibreOffice, Google Cloud CLI, Git and preview tools…', flush=True)
    with ThreadPoolExecutor(max_workers=6) as executor:
        paths = list(executor.map(lambda pin: download(pin, downloads), pins))
    count = len(lock['archives'])
    archives = dict(zip(lock['archives'], paths[:count]))
    # No downloaded archive is extracted until every checksum has passed.
    payload.mkdir()
    shutil.copy2(archives['libreoffice'], payload / 'LibreOffice.dmg')
    extract_micromamba(archives['micromamba'], payload)
    distribution.unpack(archives['google_cloud_cli'], payload / 'google-cloud-sdk',
                        exclude=lock['archives']['google_cloud_cli'].get('exclude', ()))
    if (payload / 'google-cloud-sdk/VERSION').read_text().strip() != lock['archives']['google_cloud_cli']['version']:
        raise ValueError('Google Cloud CLI version differs from its lock.')
    packages = payload / 'packages'
    packages.mkdir()
    for pin, source in zip(lock['packages'], paths[count:]):
        shutil.copy2(source, packages / pin['filename'])
    (payload / 'packages.json').write_text(json.dumps(lock['packages'], indent=2) + '\n')
    require_arm64(payload / 'micromamba')


@contextmanager
def installer_payload(root, manifest, cache):
    mode = manifest.get('mode', 'offline')
    if mode == 'offline':
        yield root / 'payload'
    elif mode == 'online':
        cache.mkdir(parents=True, exist_ok=True)
        print('Online setup needs internet access to download pinned tools. '
              'Completed downloads are cached for retries.', flush=True)
        with tempfile.TemporaryDirectory(prefix='presentation-tools-', dir=cache) as scratch:
            payload = Path(scratch) / 'payload'
            prepare_tools(manifest['tools'], cache, payload)
            yield payload
    else:
        raise ValueError('Unknown Presentation Studio bundle mode: ' + str(mode))
