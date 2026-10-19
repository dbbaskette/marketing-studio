#!/bin/sh
# Run Blog Studio setup from Terminal or an unpacked installer.
set -eu
setup_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/sh "$setup_dir/installer/install.sh" "$@"
