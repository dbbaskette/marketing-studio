#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
for python in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$python" >/dev/null && "$python" -c 'import sys; sys.exit(sys.version_info < (3,11))'; then
    exec "$python" -m marketing_studio --open
  fi
done
echo 'Install Python 3.11 or newer, then open Marketing Studio again.'
exit 1
