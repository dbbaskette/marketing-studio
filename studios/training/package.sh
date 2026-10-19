#!/bin/sh
# Package this product from its source checkout; never installs it.
set -eu
package_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -f "$package_dir/studio-package" ]; then
  checkout="$package_dir"
  product=marketing
else
  checkout="$(CDPATH= cd -- "$package_dir/../.." && pwd)"
  product="${package_dir##*/}"
fi
if [ ! -f "$checkout/studio-package" ]; then
  echo "Packaging needs the Marketing Studio source checkout. Install a downloaded bundle with bash install.sh." >&2
  exit 1
fi
for candidate in python3 python3.14 python3.13 python3.12 python3.11 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    exec "$candidate" "$checkout/studio-package" "$product" "$@"
  fi
done
if command -v uv >/dev/null 2>&1; then
  candidate="$(uv python find --offline --no-python-downloads --no-project --no-config '>=3.11')" || exit 1
  exec "$candidate" "$checkout/studio-package" "$product" "$@"
fi
echo "Packaging needs an existing Python 3.11 or newer. No software was installed." >&2
exit 1
