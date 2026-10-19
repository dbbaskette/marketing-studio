#!/bin/bash
set -euo pipefail
bundle_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/sh "$bundle_dir/install.sh" "$@"
