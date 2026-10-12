#!/usr/bin/env python3
"""Run the test files side by side, each in its own process.

    python3 scripts/ci/run_tests.py --jobs 8

`python3 -m unittest discover -s tests` runs every file in one process, one
after another; that stays the default in scripts/ci/check.sh and is what the
workflows use. This runs the same files with the same command, one interpreter
per file, so the slow Team Hub files overlap. No test is skipped or changed.

Each file's output is printed whole, files that failed last so the end of the
log shows them. The exit status is 1 if any file fails.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]


def run_file(name):
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', name, '-v'],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return name, result.returncode, result.stdout, time.monotonic() - started


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--jobs',
        type=int,
        default=os.cpu_count() or 1,
        help='Test files to run at once (default: the number of processors)',
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be 1 or more')
    files = sorted(path.name for path in (REPO / 'tests').glob('test*.py'))
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run_file, files))
    tests = 0
    failed = [name for name, code, _output, _seconds in results if code]
    for name, _code, output, seconds in sorted(results, key=lambda r: (r[0] in failed, r[0])):
        print(f'===== {name} ({seconds:.1f}s)')
        print(output.rstrip())
        ran = re.search(r'^Ran (\d+) tests? in', output, re.MULTILINE)
        tests += int(ran.group(1)) if ran else 0
    elapsed = time.monotonic() - started
    print(
        f'===== Ran {tests} tests from {len(files)} files in {elapsed:.1f}s, {args.jobs} at a time'
    )
    if failed:
        print('FAILED: ' + ', '.join(failed))
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
