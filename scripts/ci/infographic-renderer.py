#!/usr/bin/env python3
"""Explicit CI-only provisioning of the checksum-pinned renderer, never a test side effect."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core.distribution import host_platform
from studio_core.infographic_renderer import prepare

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cache', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    record = prepare(ROOT, output, host_platform(), args.cache.resolve())
    print(output / 'renderer' / record['executable'])
