#!/bin/bash
# Focused setup verification through the existing disposable macOS runner.
set -euo pipefail
exec bash "$(dirname "$0")/guest-test.sh" shared-setup
