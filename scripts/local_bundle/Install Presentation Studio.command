#!/bin/bash
set -euo pipefail
if [ "$(uname -m)" != "arm64" ]; then echo "This bundle requires an Apple Silicon Mac. Open Terminal without Rosetta."; exit 1; fi
bundle_dir="$(cd "$(dirname "$0")" && pwd)"
exec "$bundle_dir/studio/runtime/python/bin/python3" "$bundle_dir/install-local.py" "$@"
