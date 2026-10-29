#!/bin/bash
set -euo pipefail
program="$(mktemp "${TMPDIR:-/tmp}/blog-tabs-guest.XXXXXX")"
trap 'rm -f "$program"' EXIT
cp "$(dirname "$0")/guest-test.sh" "$program"
bash "$program" blog-google-tabs
