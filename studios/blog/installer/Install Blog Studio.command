#!/bin/bash
# Finder launcher for the same installer used by existing shell sessions.
installer_dir="$(cd -- "$(dirname -- "$0")" && pwd)" || exit 1
printf '\nWelcome to Blog Studio setup.\n\n'
/bin/sh "$installer_dir/install.sh" "$@"
installer_exit=$?
if [ -t 0 ]; then
  printf '\n'
  read -r -p 'Press Return to close. ' installer_close
fi
exit "$installer_exit"
