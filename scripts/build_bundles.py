#!/usr/bin/env python3
"""Build self-contained Marketing Studio and individual studio installers."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core.bundles import build
from studio_core.bundles import materialize
from studio_core.distribution import PLATFORMS, prepare

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--platform', choices=PLATFORMS, help='Bundle private runtimes and production dependencies for this platform.')
    parser.add_argument('--cache', type=Path, default=ROOT / 'build/download-cache')
    parser.add_argument('--studios', nargs='+', choices=('blog', 'presentation', 'training'))
    args = parser.parse_args()
    if args.platform:
        with tempfile.TemporaryDirectory(prefix='marketing-release-') as temporary:
            staged = Path(temporary) / 'source'
            selected = args.studios or ['blog', 'presentation', 'training']
            materialize(ROOT, staged, selected)
            prepare(ROOT, staged, args.platform, args.cache.resolve(), selected)
            result = build(staged, args.output, selection=args.studios)
    else:
        result = build(ROOT, args.output, selection=args.studios)
    print(json.dumps(result, indent=2))
