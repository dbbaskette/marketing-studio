#!/bin/bash
# Final shared/native/deck verification, reusing the unchanged Blog Studio pass.
set -euo pipefail
exec bash "/Volumes/My Shared Files/source/scripts/ci/guest-test.sh" infographic-finish
