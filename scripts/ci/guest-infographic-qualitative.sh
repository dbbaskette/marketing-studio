#!/bin/bash
set -euo pipefail
export INFOGRAPHIC_STUDIO_TEST_VISUAL=comparison
exec bash "$(dirname "$0")/guest-infographic-activity.sh" "${1:-infographic-planning}"
