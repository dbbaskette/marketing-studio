#!/bin/bash
set -euo pipefail
export MARKETING_STUDIO_TEST_LIQUID_PILOT=1
# Full shared/native suites plus synthetic planning, rendering, delivery and packaging.
exec bash "$(dirname "$0")/guest-infographic-contracts.sh" infographic-activity
