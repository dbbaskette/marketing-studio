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
    use_cache = cache.is_dir() and companions.tree_digest(cache) == pin['sha256']
    if use_cache:
        shutil.copytree(cache, target)
    else:
        target.mkdir(parents=True)
        companions.fetch_revision(pin['repository'], pin['commit'], target)
    if companions.tree_digest(target) != pin['sha256']:
        raise ValueError('The prepared research test source differs from its lock.')
    print(json.dumps({'version': pin['version'], 'commit': pin['commit'], 'sha256': pin['sha256'], 'cache_used': use_cache}))


if __name__ == '__main__':
    main()
