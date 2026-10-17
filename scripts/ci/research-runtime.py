#!/usr/bin/env python3
"""Prepare the exactly locked research source for disposable contract tests only."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core import companions


def main():
    target = Path(sys.argv[1])
    pin = companions.read_pins(ROOT / 'pins/companions.json')['harness-research']
    cache = ROOT / 'build/research-contract-runtime'
    if cache.is_dir():
        if companions.tree_digest(cache) != pin['sha256']:
            raise ValueError('The local research test source differs from its lock.')
        shutil.copytree(cache, target)
    else:
        target.mkdir(parents=True)
        companions.fetch_revision(pin['repository'], pin['commit'], target)
        if companions.tree_digest(target) != pin['sha256']:
            raise ValueError('The downloaded research test source differs from its lock.')
    print(json.dumps({'version': pin['version'], 'commit': pin['commit'], 'sha256': pin['sha256']}))


if __name__ == '__main__':
    main()
