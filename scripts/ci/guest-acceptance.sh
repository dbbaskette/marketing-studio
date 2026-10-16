#!/bin/bash
# Focused clean-machine acceptance after the unchanged native suites have passed.
set -euo pipefail
exec bash "$(dirname "$0")/guest-test.sh" acceptance
