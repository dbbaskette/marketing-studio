#!/usr/bin/env python3
"""Report what each companion's `main` holds now, against the floor this version needs.

Companions are installed and updated from their repository's `main`; nothing here is
locked or written. For each companion this reads the commit `main` is at, fetches it into a
temporary folder, checks it file for file as an install would (no links, its entry and
installer, a version at or above the pin's floor) and reports its version. Only Git
revisions are downloaded; no tool is installed and no provider runs. A `main` older than
the floor is reported and the command fails, so the floor can be raised only once `main`
meets it.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core.companions import InstallError, fetch_main, minimum_version, read_pins


def report(path):
    pins = read_pins(Path(path))
    found, short = {}, []
    with tempfile.TemporaryDirectory(prefix='studio-companion-main-') as temporary:
        for name, pin in pins.items():
            entry = {'repository': pin['repository'], 'branch': pin['branch'],
                     'floor': minimum_version(pin)}
            try:
                _, fetched = fetch_main(name, pin, Path(temporary))
                entry.update(version=fetched['version'], commit=fetched['commit'],
                             sha256=fetched['sha256'])
            except InstallError as refusal:
                entry['problem'] = str(refusal)
                short.append(name)
            found[name] = entry
    return {'companions': found, 'short': short}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', type=Path, default=ROOT / 'pins/companions.json')
    parser.add_argument('--check', action='store_true',
                        help='Accepted for older callers; nothing is ever written.')
    args = parser.parse_args(argv)
    try:
        result = report(args.pins)
    except (OSError, ValueError) as failure:
        print('Companion check failed: ' + str(failure), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 1 if result['short'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
