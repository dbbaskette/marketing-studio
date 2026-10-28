#!/usr/bin/env python3
"""Produce shareable synthetic graphics outside the source repository. No AI calls."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

if sys.version_info < (3, 11):
    raise SystemExit('Infographic Studio graphics tests require Python 3.11 or newer.')
NATIVE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NATIVE))
sys.path.insert(0, str(NATIVE / 'tests'))
from runner import render
from graphics_fixtures import scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix='infographic-studio-graphics-'))
    output = output.expanduser().absolute()
    repository = NATIVE.parents[1]
    if output.resolve().is_relative_to(repository):
        parser.error('Graphics test outputs must stay outside the application repository.')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error('Choose an empty graphics-test output folder.')
    results = []
    for kind, preset in [('comparison', 'a4'), ('process', 'letter'), ('concept', 'digital')]:
        folder = output / (kind + '-' + preset)
        result = render.render(scene(kind, preset), preset=preset, fonts=['Arial'],
                               executable=args.renderer, destination=folder)
        results.append({'kind': kind, 'folder': str(folder), **result})
        print(json.dumps(results[-1]), flush=True)
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
