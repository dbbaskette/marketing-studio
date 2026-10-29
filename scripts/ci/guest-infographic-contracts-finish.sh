#!/bin/bash
set -euo pipefail
# Reuse completed full-suite evidence for unchanged application sources.
exec bash "$(dirname "$0")/guest-infographic-contracts.sh" infographic-activity-finish
