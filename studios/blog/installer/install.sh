#!/bin/sh
# Run the bundled installer from an existing shell, without opening Terminal.
installer_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1
for installer_candidate in python3 python3.14 python3.13 python3.12 python3.11 \
  /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 \
  /usr/local/bin/python3 /usr/local/bin/python3.14 /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11 \
  /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if command -v "$installer_candidate" >/dev/null 2>&1 && "$installer_candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
    exec "$installer_candidate" "$installer_dir/install.py" "$@"
  fi
done
printf '%s\n' 'Blog Studio setup requires Python 3.11 or later.' \
  'Install an organization-approved Python from https://www.python.org/downloads/ and run setup again.' >&2
exit 1
