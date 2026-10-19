#!/bin/sh
# Install the local Presentation Studio bundle using its private Python.
set -eu
if [ "$(uname -m)" != "arm64" ]; then
  echo "This bundle requires an Apple Silicon Mac. Open Terminal without Rosetta." >&2
  exit 1
fi
bundle_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$bundle_dir/studio/runtime/python/bin/python3" "$bundle_dir/install-local.py" "$@"
