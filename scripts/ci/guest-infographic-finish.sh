#!/bin/bash
# Final native repair verification, reusing the recorded unchanged full-suite pass.
set -euo pipefail
exec bash "/Volumes/My Shared Files/source/scripts/ci/guest-test.sh" infographic-finish
