#!/usr/bin/env python3
"""Refresh exact companion locks to the newest stable tags allowed by their >= requirements.

Only downloads source metadata and Git revisions; never installs tools or runs providers.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core.companions import read_pins, resolve_companion


def refresh(path, check=False):
    path = Path(path)
    before = path.read_bytes()
    document = json.loads(before)
    pins = read_pins(path)
    resolved = {name: resolve_companion(name, pin) for name, pin in pins.items()}
    changed = [name for name in pins if pins[name] != resolved[name]]
    if changed and not check:
        document['companions'] = resolved
        pending = path.with_name('.' + path.name + '.pending-' + secrets.token_hex(6))
        try:
            with pending.open('x') as stream:
                stream.write(json.dumps(document, indent=2) + '\n')
            if path.read_bytes() != before:
                raise ValueError('Companion locks changed during refresh. Retry against the new file.')
            os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)
    return {'changed': changed, 'written': bool(changed and not check),
            'companions': {name: {'requirement': pin.get('requirement', pin['version']),
                                 'version': pin['version'], 'commit': pin['commit'],
                                 'sha256': pin['sha256']} for name, pin in resolved.items()}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', type=Path, default=ROOT / 'pins/companions.json')
    parser.add_argument('--check', action='store_true', help='Report allowed upgrades without changing the lock file.')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(refresh(args.pins, args.check), indent=2))
        return 0
    except (OSError, ValueError) as failure:
        print('Companion refresh failed: ' + str(failure), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
