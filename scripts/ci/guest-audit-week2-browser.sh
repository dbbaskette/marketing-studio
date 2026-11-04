#!/bin/bash
set -euo pipefail
exec bash "$(dirname "$0")/guest-test.sh" audit-week2-browser
