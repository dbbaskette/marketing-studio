#!/bin/bash
# Freeze the mounted program and use the shared disposable Tart runner.
set -euo pipefail
program="$(mktemp "${TMPDIR:-/tmp}/infographic-guest.XXXXXX")"
trap 'rm -f "$program"' EXIT
cp "$(dirname "$0")/guest-test.sh" "$program"
bash "$program" infographic-google-finish
