#!/bin/bash
set -euo pipefail
export MARKETING_STUDIO_TEST_SHARED_INTEGRATION=1
exec bash "$(dirname "$0")/guest-infographic-qualitative.sh" infographic-activity-finish
