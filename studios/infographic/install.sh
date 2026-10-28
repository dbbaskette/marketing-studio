#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -eq 0 ]; then set -- install; fi
for python in python3.14 python3.13 python3.12 python3.11 python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if "$python" -c 'import sys; raise SystemExit(sys.version_info < (3,11))' 2>/dev/null; then
    exec "$python" "$root/installer/install.py" "$@"
  fi
done
printf '%s\n' 'Infographic Studio needs Python 3.11+. Use a matching prepared Marketing Studio download.' >&2
exit 2
