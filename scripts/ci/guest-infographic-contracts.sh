#!/bin/bash
set -euo pipefail
export INFOGRAPHIC_STUDIO_TEST_CONTRACTS=1
# Exact-version bundle selection; also cover both qualitative visual forms.
exec bash "$(dirname "$0")/guest-infographic-qualitative.sh" "${1:-infographic-activity}"
