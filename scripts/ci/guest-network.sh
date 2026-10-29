#!/bin/bash
# Freeze the mounted script before running the shared bridge verification suite.
set -euo pipefail
program="$(mktemp "${TMPDIR:-/tmp}/network-guest.XXXXXX")"
trap 'rm -f "$program"' EXIT
cp "$(dirname "$0")/guest-test.sh" "$program"
bash "$program" network
