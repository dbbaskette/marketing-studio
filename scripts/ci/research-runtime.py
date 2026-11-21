#!/usr/bin/env python3
"""Prepare Harness Research's `main`, checked as an install checks it, for disposable
contract tests only."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core import companions


def main():
    target = Path(sys.argv[1])
    pin = companions.read_pins(ROOT / 'pins/companions.json')['harness-research']
    with tempfile.TemporaryDirectory(prefix='research-contract-runtime-') as holder:
        checkout, fetched = companions.fetch_main('harness-research', pin, Path(holder))
        shutil.copytree(checkout, target)
    if companions.tree_digest(target) != fetched['sha256']:
        raise ValueError('The prepared research test source differs from what was checked.')
    print(json.dumps({key: fetched[key] for key in ('version', 'commit', 'sha256')}))


if __name__ == '__main__':
    main()
