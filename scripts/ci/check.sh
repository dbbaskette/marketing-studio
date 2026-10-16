#!/bin/bash
# One verification entry point for the home UI, shared core, installers, and native studios.
set -euo pipefail
cd "$(dirname "$0")/../.."
python="${1:-python3}"
results="${2:-$(mktemp -d "${TMPDIR:-/tmp}/marketing-studio-checks.XXXXXX")}"
mkdir -p "$results"
"$python" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'
"$python" -m compileall -q marketing_studio core installer
node --check marketing_studio/web/app.js
run() {
  local name="$1"
  shift
  if "$@" > "$results/$name.log" 2>&1; then
    echo "PASS: $name"
    tail -n 5 "$results/$name.log"
  else
    tail -n 100 "$results/$name.log" >&2
    echo "FAIL: $name; full log: $results/$name.log" >&2
    return 1
  fi
}
run home-and-suite "$python" -m unittest discover -s tests -v
run blog-studio bash -c 'cd studios/blog && BLOG_STUDIO_REQUIRE_LINT=1 BLOG_STUDIO_TEST_JOBS=4 bash scripts/ci/check.sh "$1" "$2"' _ "$python" "$results/blog-studio"
run presentation-studio bash -c 'cd studios/presentation && "$1" scripts/ci/run_tests.py --jobs 4 && "$1" skills/presentation-studio/scripts/validate_package.py' _ "$python"
run training-studio bash -c 'cd studios/training && bash scripts/ci/check.sh "$1"' _ "$python"
bash scripts/ci/acceptance.sh "$python" "$results"
printf 'PASS\n' > "$results/result.txt"
echo "All suite checks passed. Logs: $results"
