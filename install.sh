#!/bin/sh
# Run Marketing Studio setup from Terminal or an unpacked installer.
set -eu
setup_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/bash "$setup_dir/installer/install.sh" "$@"
