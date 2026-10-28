"""Provider-neutral image contract, with no networking or provider implementation."""
from typing import Protocol


class ImageAdapter(Protocol):
    """Results satisfy runner.validation.validate_image_result.

    File references are owned staged assets, not arbitrary model-selected paths.
    A cancel response can remain unknown when remote cancellation is unavailable.
    """

    def readiness(self) -> dict: ...

    def generate(self, *, attempt_id: str, brief: dict) -> dict: ...

    def edit(self, *, attempt_id: str, brief: dict, reference_assets: list[dict]) -> dict: ...

    def status(self, *, attempt_id: str) -> dict: ...

    def cancel(self, *, attempt_id: str) -> dict: ...


def result(provider, operation, attempt_id, *, state='unverified', reason=None,
           assets=None, request_id=None, usage=None, inspection='unknown'):
    from ..validation import validate_image_result
    value = {'schema': 1, 'provider': provider, 'operation': operation, 'attempt_id': attempt_id,
             'state': state, 'reason': reason, 'request_id': request_id,
             'assets': assets or [], 'inspection': inspection,
             'usage': usage or {'cost': None, 'currency': None, 'input_tokens': None, 'output_tokens': None}}
    return validate_image_result(value)


def save_asset(folder, raw, mime):
    import hashlib
    import os
    from pathlib import Path
    from ..validation import image_size, require
    folder = Path(folder)
    require(folder.is_dir() and not any(p.is_symlink() for p in (folder, *folder.parents)),
            'Returned images need an owned regular attempt folder.')
    width, height = image_size(raw, mime)
    validate_png(raw, mime)
    fingerprint = hashlib.sha256(raw).hexdigest()
    name = fingerprint + ('.png' if mime == 'image/png' else '.jpg')
    file = folder / name
    try:
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except FileExistsError:
        require(file.is_file() and not file.is_symlink() and file.read_bytes() == raw,
                'The returned asset conflicts with an existing file.')
    else:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return {'id': 'a_' + fingerprint[:24], 'file': name, 'sha256': fingerprint,
            'mime': mime, 'bytes': len(raw), 'width': width, 'height': height}


def validate_png(raw, mime):
    """Fully check the bounded 8-bit RGB/RGBA PNG returned by supported providers."""
    import struct
    import zlib
    from ..validation import image_size, require
    require(mime == 'image/png', 'The image provider must return PNG artwork.')
    width, height = image_size(raw, mime)
    offset, chunks, compressed, channels, ended = 8, 0, [], None, False
    while offset + 12 <= len(raw):
        size = int.from_bytes(raw[offset:offset + 4], 'big')
        kind = raw[offset + 4:offset + 8]
        require(offset + size + 12 <= len(raw), 'The PNG has an incomplete chunk.')
        data = raw[offset + 8:offset + 8 + size]
        crc = int.from_bytes(raw[offset + 8 + size:offset + 12 + size], 'big')
        require(zlib.crc32(kind + data) == crc, 'The returned PNG checksum is invalid.')
        if chunks == 0:
            require(kind == b'IHDR' and size == 13, 'The PNG header is invalid.')
            _, _, bits, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', data)
            require(bits == 8 and color in (2, 6) and (compression, filtering, interlace) == (0, 0, 0),
                    'Return a non-interlaced 8-bit RGB/RGBA PNG from the image provider.')
            channels = 3 if color == 2 else 4
        elif kind == b'IHDR':
            raise ValueError('A PNG cannot repeat its header.')
        if kind == b'IDAT':
            compressed.append(data)
        offset += size + 12
        chunks += 1
        if kind == b'IEND':
            require(size == 0 and offset == len(raw), 'The PNG has invalid trailing data.')
            ended = True
            break
    require(ended and channels is not None and bool(compressed), 'The returned PNG is incomplete.')
    expected = height * (1 + width * channels)
    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(b''.join(compressed), expected + 1)
    except zlib.error as failure:
        raise ValueError('The returned PNG pixel data is invalid.') from failure
    require(len(pixels) == expected and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            'The returned PNG pixel data is invalid or exceeds its dimensions.')
    stride = 1 + width * channels
    require(all(pixels[row * stride] <= 4 for row in range(height)), 'The PNG uses an invalid pixel filter.')
