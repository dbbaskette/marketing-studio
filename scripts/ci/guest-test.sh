#!/bin/bash
set -euo pipefail
source_dir='/Volumes/My Shared Files/source'
results_dir='/Volumes/My Shared Files/results'
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
work="$(mktemp -d "${TMPDIR:-/tmp}/marketing-studio-guest.XXXXXX")"
trap 'rm -rf "$work"' EXIT
rm -f "$results_dir/result.txt"
python=''
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3,11))'; then
    python="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$python" ]]; then
  HOMEBREW_NO_AUTO_UPDATE=1 brew install python@3.13 > "$results_dir/provisioning.log" 2>&1
  python="$(command -v python3.13)"
fi
# Native package tests inspect tracked files. Keep a disposable Git clone, then
# overlay the mounted working tree so recorded uncommitted changes are tested too.
git -c safe.directory="$source_dir" -c safe.directory="$source_dir/.git" \
  clone --quiet --no-hardlinks "$source_dir" "$work/repo"
rsync -a --exclude=.git --exclude=.claude --exclude=__pycache__ "$source_dir/" "$work/repo/"
cd "$work/repo"
{ sw_vers; "$python" --version; node --version; git --version; } > "$results_dir/environment.txt"
"$python" -m venv "$work/tools"
"$work/tools/bin/pip" install -r studios/blog/requirements-dev.txt > "$results_dir/provisioning.log" 2>&1
export PATH="$work/tools/bin:$PATH"
if [[ "${1:-full}" == acceptance ]]; then
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
else
  bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
fi
printf 'PASS\n' > "$results_dir/result.txt"
