#!/bin/bash
# Real native CLIs against disposable local fixtures; copy records after Git is finished.
set -euo pipefail
cd "$(dirname "$0")/../.."
python="${1:-python3}"
results="${2:?Pass a results directory}"
mkdir -p "$results"
fixtures="$(mktemp -d "${TMPDIR:-/tmp}/marketing-acceptance.XXXXXX")"
retain() {
  local code=$?
  trap - EXIT
  mkdir -p "$results/fixtures"
  cp -R "$fixtures/." "$results/fixtures/" || code=1
  rm -rf "$fixtures"
  exit "$code"
}
trap retain EXIT
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
run native-setup "$python" scripts/ci/native_acceptance.py
run native-launch "$python" scripts/ci/native_launch_acceptance.py
run blog-hub-journey "$python" studios/blog/scripts/acceptance/hub-journey.py --local-fixture --run-directory "$fixtures/hub-fixture"
run shared-studios-journey "$python" studios/blog/scripts/acceptance/studios-journey.py --run-directory "$fixtures/studios-journey" --training-checkout "$PWD/studios/training"
