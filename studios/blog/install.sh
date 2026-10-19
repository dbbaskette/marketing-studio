#!/bin/sh
# Install this product from its root folder.
set -eu
setup_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/bash "$setup_dir/installer/install.sh" "$@"
