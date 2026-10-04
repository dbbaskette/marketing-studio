#!/usr/bin/env bash
# Manually verify an exact committed revision on Linux/macOS x Python 3.11/3.13.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd -P)
platform=all
ref=HEAD
dry_run=0
while (($#)); do
  case "$1" in
    --platform) platform=${2:?Missing platform}; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --keep) shift ;; # Clones and logs are always retained by this runner.
    --help|-h) echo 'Usage: bash scripts/ci/tart-matrix.sh [--platform all|macos|linux] [--dry-run] [REF]'; exit 0 ;;
    --*) echo "Unknown option: $1" >&2; exit 2 ;;
    *) ref=$1; shift ;;
  esac
done
case "$platform" in all) platforms='macos linux' ;; macos|linux) platforms=$platform ;; *) exit 2 ;; esac
commit=$(git -C "$repo" rev-parse --verify "$ref^{commit}")
runs=${BLOG_STUDIO_TART_RUNS_DIR:-/tmp/blog-studio-matrix-runs}
[[ "$runs" == /* && "$runs" != *:* ]] || exit 2
command -v tart >/dev/null
command -v python3 >/dev/null
failed=0
for lane in $platforms; do
  if [[ "$lane" == macos ]]; then base=${TART_BASE:-tanzu-brand-golden-gate-base}
  else base=${BLOG_STUDIO_LINUX_BASE:-saypipe-ubuntu-24.04-base}; fi
  [[ "$base" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || exit 2
  if ((dry_run)); then
    printf '%s: %s; commit %s; Python 3.11 + 3.13; results %s\n' "$lane" "$base" "$commit" "$runs"
    continue
  fi
  # Inspect only this base; an unrelated busy VM must not break discovery.
  state=$(tart get "$base" --format json | python3 -c 'import json,sys
v=json.load(sys.stdin)
expected="darwin" if sys.argv[1]=="macos" else "linux"
if v["OS"] != expected: sys.exit("Base OS does not match requested lane")
print("running" if v["Running"] else "stopped")' "$lane")
  [[ "$state" == stopped ]] || { echo "Base $base must be stopped" >&2; exit 1; }
  vm="blog-studio-$lane-matrix-$(date -u +%Y%m%d%H%M%S)-$$"
  run="$runs/$vm"
  umask 077
  mkdir -p "$run/source/repo" "$run/results"
  git -C "$repo" archive "$commit" | tar -xf - -C "$run/source/repo"
  printf '%s\n' "$commit" > "$run/source/commit.txt"
  printf 'Commit: %s\nBase: %s\nVM: %s\nPlatform: %s\n' "$commit" "$base" "$vm" "$lane" > "$run/run.txt"
  tart --version >> "$run/run.txt"
  # Keep the subshell outside an if/&&/|| condition: Bash otherwise disables
  # errexit inside it, allowing a failed guest operation to look successful.
  set +e
  (
    set -e
    pid=0
    # shellcheck disable=SC2329 # Invoked by traps.
    cleanup() {
      result=$?
      trap - EXIT INT TERM
      if ((pid)); then tart stop "$vm" >/dev/null 2>&1 || true; wait "$pid" 2>/dev/null || true; fi
      printf 'Retained clone: %s\nResults: %s\n' "$vm" "$run"
      exit "$result"
    }
    trap cleanup EXIT
    trap 'exit 130' INT TERM
    tart clone "$base" "$vm"
    extra_args=(--no-clipboard --no-audio)
    if [[ "$lane" == linux ]]; then extra_args+=(--rosetta=rosetta); fi
    tart run --no-graphics "${extra_args[@]}" --dir="source:$run/source:ro" --dir="results:$run/results" "$vm" > "$run/tart.log" 2>&1 &
    pid=$!
    ready=0
    for ((attempt=0; attempt<120; attempt++)); do
      if tart exec "$vm" /usr/bin/true >/dev/null 2>&1; then ready=1; break; fi
      kill -0 "$pid" 2>/dev/null || exit 1
      sleep 2
    done
    ((ready)) || { echo 'Guest readiness timed out' >&2; exit 1; }
    # Bound provisioning and validation; credentials stay on the host.
    python3 - "$vm" "$run" "$lane" <<'PY'
import pathlib, subprocess, sys
vm, run, lane = sys.argv[1:]
if lane == 'macos':
    command = ['/bin/bash', '/Volumes/My Shared Files/source/repo/scripts/ci/matrix-guest.sh']
else:
    command = ['/bin/bash', '-c', 'set -e; sudo -n mkdir -p /mnt/shared; mountpoint -q /mnt/shared || sudo -n mount -t virtiofs com.apple.virtio-fs.automount /mnt/shared; exec /bin/bash /mnt/shared/source/repo/scripts/ci/matrix-guest.sh']
with open(pathlib.Path(run)/'console.log', 'wb') as log:
    result = subprocess.run(['tart', 'exec', vm, *command], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
    sys.exit(result.returncode)
PY
    # Bash 3.2 does not reliably apply errexit to failed [[ ]] commands.
    [[ -f "$run/results/result.txt" && "$(cat "$run/results/result.txt")" == PASS ]] || exit 1
    [[ "$(cat "$run/results/commit.txt")" == "$commit" ]] || exit 1
  )
  lane_result=$?
  set -e
  if ((lane_result == 0)); then
    printf '%s PASS: %s\n' "$lane" "$commit"
  else
    failed=1
    printf '%s FAIL: %s\n' "$lane" "$commit" >&2
  fi
done
exit "$failed"
