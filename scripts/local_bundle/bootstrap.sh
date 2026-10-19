#!/bin/sh
# Private bundle bootstrap; use install.sh in the outermost folder.
set -eu
bundle_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ "$(uname -m)" != "arm64" ]; then
  echo "This bundle requires an Apple Silicon Mac. Open Terminal without Rosetta." >&2
  exit 1
fi
# Keep the verified bundle immutable, including during Python startup and child processes.
export PYTHONDONTWRITEBYTECODE=1
exec "$bundle_dir/studio/runtime/python/bin/python3" "$bundle_dir/install-local.py" "$@"
