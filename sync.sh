#!/bin/bash
# Update Marketing Studio and sibling component repositories; never installs software.
set -eu
sync_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
for sync_python in "$sync_root/runtime/python/bin/python3" \
  "$HOME/.local/share/marketing-studio/current/runtime/python/bin/python3" \
  python3 python3.14 python3.13 python3.12 python3.11 \
  /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$sync_python" >/dev/null 2>&1 && \
      "$sync_python" -c 'import sys; sys.exit(sys.version_info < (3,11))' >/dev/null 2>&1; then
    exec "$sync_python" "$sync_root/scripts/sync_repos.py" "$@"
  fi
done
if command -v uv >/dev/null 2>&1; then
  sync_python="$(uv python find --offline --no-python-downloads --no-project --no-config '>=3.11')" || exit 1
  exec "$sync_python" "$sync_root/scripts/sync_repos.py" "$@"
fi
echo 'Repository sync needs Git and an existing Python 3.11 or newer. No software was installed.' >&2
exit 1
