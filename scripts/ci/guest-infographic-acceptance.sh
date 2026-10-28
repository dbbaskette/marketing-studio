#!/bin/bash
# Finish changed takeover/return cases and platform journeys; reuse unchanged suites.
set -euo pipefail
exec bash "/Volumes/My Shared Files/source/scripts/ci/guest-test.sh" infographic-acceptance
