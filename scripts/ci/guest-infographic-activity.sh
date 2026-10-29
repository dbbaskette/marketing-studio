#!/bin/bash
# Freeze the mounted program before checking activity and the native workflows.
set -euo pipefail
program="$(mktemp "${TMPDIR:-/tmp}/infographic-activity-guest.XXXXXX")"
trap 'rm -f "$program"' EXIT
cp "$(dirname "$0")/guest-test.sh" "$program"
bash "$program" "${1:-infographic-activity}"
