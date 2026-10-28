#!/bin/bash
# Freeze the mounted guest program so host edits cannot change an active shell stream.
set -euo pipefail
program="$(mktemp "${TMPDIR:-/tmp}/infographic-guest.XXXXXX")"
trap 'rm -f "$program"' EXIT
cp "$(dirname "$0")/guest-test.sh" "$program"
bash "$program" infographic-followups-final
