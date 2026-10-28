#!/bin/bash
# Dedicated first-release verification through the existing disposable Tart runner.
set -euo pipefail
exec bash "/Volumes/My Shared Files/source/scripts/ci/guest-test.sh" infographic
