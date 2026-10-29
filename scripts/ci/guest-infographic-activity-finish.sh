#!/bin/bash
set -euo pipefail
exec bash "$(dirname "$0")/guest-infographic-activity.sh" infographic-activity-finish
