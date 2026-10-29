#!/bin/bash
set -euo pipefail
export INFOGRAPHIC_STUDIO_TEST_VISUAL_PAGES=1
export MARKETING_STUDIO_TEST_LIQUID_PILOT=1
exec bash "$(dirname "$0")/guest-infographic-contracts.sh" infographic-activity
