#!/usr/bin/env bash
# Project checks in an isolated Mac environment. No sign-in or model calls.
set -euo pipefail
source_dir='/Volumes/My Shared Files/source'
results_dir='/Volumes/My Shared Files/results'
[[ -d "$source_dir" && -d "$results_dir" ]] || { echo 'Provide isolated source and results mounts.' >&2; exit 1; }
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
python_bin=''
for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
  if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3,11))' 2>/dev/null; then
    python_bin="$(command -v "$candidate")"; break
  fi
done
[[ -n "$python_bin" ]] || { echo 'Install Python 3.11+ in the disposable guest, then rerun. No base VM is modified.' >&2; exit 1; }
# Run in a copied tree; tests/builds cannot modify the host's read-only mount.
run_dir="$(mktemp -d /private/tmp/blog-studio-ci.XXXXXX)"
(cd "$source_dir" && tar --exclude=.git --exclude=__pycache__ -cf - .) | (cd "$run_dir" && tar -xf -)
cd "$run_dir"
{ sw_vers; "$python_bin" --version; git --version; command -v codex || true; command -v claude || true; } > "$results_dir/environment.txt"
"$python_bin" -m unittest discover -s tests -v > "$results_dir/tests.log" 2>&1
"$python_bin" scripts/measure_guidance.py --check > "$results_dir/guidance.json"
"$python_bin" skills/blog-studio/scripts/validate_package.py > "$results_dir/package.txt"
"$python_bin" skills/blog-writing-toolkit/scripts/validate_package.py >> "$results_dir/package.txt"
sh -n installer/install.sh
bash -n 'installer/Install Blog Studio.command'
node scripts/ci/check-newcomer.cjs > "$results_dir/newcomer-prompts.json"
# Exercise the real CLI and shell launcher, separately from unit fixtures.
for target in codex claude both; do
  pilot_home="$run_dir/pilot-$target"
  /bin/sh installer/install.sh install --home "$pilot_home" --target "$target" --yes --offline > "$results_dir/install-$target.txt"
  /bin/sh installer/install.sh check --home "$pilot_home" --target "$target" --offline --json > "$results_dir/check-$target.json"
  /bin/sh installer/install.sh uninstall --home "$pilot_home" --target "$target" --yes >> "$results_dir/install-$target.txt"
done
printf '\n' | env PATH=/usr/bin:/bin:/usr/sbin:/sbin /bin/bash 'installer/Install Blog Studio.command' --dry-run --offline > "$results_dir/launcher-gui-path.txt"
env PATH=/usr/bin:/bin:/usr/sbin:/sbin /bin/sh installer/install.sh --dry-run --offline --json > "$results_dir/shell-minimal-path.json"
# Assessment is observational, never a bypass or a claim of GUI consent.
cp 'installer/Install Blog Studio.command' "$run_dir/Quarantined Installer.command"
xattr -w com.apple.quarantine '0083;00000000;BlogStudioPilot;' "$run_dir/Quarantined Installer.command"
if spctl --assess --type execute "$run_dir/Quarantined Installer.command" > "$results_dir/quarantine-assessment.txt" 2>&1; then
  echo 'assessment accepted; actual GUI launch still requires observation' >> "$results_dir/quarantine-assessment.txt"
else
  echo 'assessment rejected; no protections bypassed; actual GUI launch requires observation' >> "$results_dir/quarantine-assessment.txt"
fi
printf 'PASS\n' > "$results_dir/result.txt"
