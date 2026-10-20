#!/bin/sh
# Find a Python new enough to run the installer, and run it.
installer_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1
# A packaged studio belongs to the enclosing installer, which owns its runtimes.
suite_dir="$installer_dir/../../.."
if [ -f "$suite_dir/distribution.json" ] && [ -f "$suite_dir/installer/install.sh" ]; then
  exec /bin/bash "$suite_dir/installer/install.sh" "$@" --studios training
fi
if [ -z "${STUDIO_INSTALL_LOG:-}" ] && [ -z "${STUDIO_INSTALL_LOG_WRAPPED:-}" ]; then
  exec /bin/bash "$installer_dir/../skills/training-studio/scripts/studio_core/install-log.sh" "$0" "$@"
fi
for candidate in python3 python3.14 python3.13 python3.12 python3.11 \
  /opt/homebrew/bin/python3 /usr/local/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
    exec "$candidate" "$installer_dir/install.py" "$@"
  fi
done
printf '%s\n' 'Training Studio setup needs Python 3.11 or newer.' \
  'Install it from https://www.python.org/downloads/ and run setup again.' >&2
exit 1
