#!/bin/bash
# A local guided launcher. No public download-and-execute bootstrap.
installer_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
printf '\nWelcome to Blog Studio setup.\n\n'
installer_python=""
for installer_candidate in python3 python3.14 python3.13 python3.12 python3.11 /opt/homebrew/bin/python3{,.14,.13,.12,.11} /usr/local/bin/python3{,.14,.13,.12,.11} /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if command -v "$installer_candidate" >/dev/null 2>&1 && "$installer_candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
    installer_python="$(command -v "$installer_candidate")"
    break
  fi
done
if [ -z "$installer_python" ]; then
  printf 'Python 3.11 or later is needed for the local writing helpers.\n'
  printf 'Install Python from https://www.python.org/downloads/macos/\nThen open this installer again.\n'
  read -r -p 'Press Return to close. ' installer_close
  exit 1
fi
if ! git --version >/dev/null 2>&1; then
  printf 'Git is needed to keep your writing guidance current.\n'
  printf 'Install it using https://git-scm.com/install/mac\nThen open this installer again.\n'
  read -r -p 'Press Return to close. ' installer_close
  exit 1
fi
"$installer_python" "$installer_dir/install.py" "$@"
installer_exit=$?
printf '\n'
read -r -p 'Press Return to close. ' installer_close
exit "$installer_exit"
