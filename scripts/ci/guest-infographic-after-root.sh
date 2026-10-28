#!/bin/bash
# Continue the unchanged full-suite pass after its upstream formatting repair.
set -euo pipefail
exec bash "/Volumes/My Shared Files/source/scripts/ci/guest-test.sh" infographic-after-root
