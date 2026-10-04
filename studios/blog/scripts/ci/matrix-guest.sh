#!/usr/bin/env bash
# Disposable, unsigned-in guest only; no host credentials or model calls.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
case "$(uname -s)" in
  Darwin) shared='/Volumes/My Shared Files' ;;
  Linux)
    sudo -n mkdir -p /mnt/shared
    mountpoint -q /mnt/shared || sudo -n mount -t virtiofs com.apple.virtio-fs.automount /mnt/shared
    shared=/mnt/shared
    ;;
  *) exit 2 ;;
esac
source_dir="$shared/source"
results="$shared/results"
work=$(mktemp -d "${TMPDIR:-/tmp}/blog-studio-matrix.XXXXXX")
cp -R "$source_dir/repo" "$work/repo"
cd "$work/repo"
cp "$source_dir/commit.txt" "$results/commit.txt"
if [[ "$(uname -s)" == Linux ]]; then
  bash scripts/ci/rosetta-linux.sh > "$results/rosetta-setup.log" 2>&1
fi
# Provision interpreters only in this disposable clone. Bases stay unchanged.
if ! command -v uv >/dev/null; then
  if [[ "$(uname -s)" == Darwin ]]; then
    HOMEBREW_NO_AUTO_UPDATE=1 brew install uv > "$results/provision.log" 2>&1
  else
    # shellcheck disable=SC2024 # Result mounts are writable by the guest user.
    sudo -n env DEBIAN_FRONTEND=noninteractive apt-get update > "$results/provision.log" 2>&1
    # shellcheck disable=SC2024
    sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv >> "$results/provision.log" 2>&1
    python3 -m venv "$work/tools"
    "$work/tools/bin/pip" install uv==0.11.19 >> "$results/provision.log" 2>&1
    export PATH="$work/tools/bin:$PATH"
  fi
fi
export UV_PYTHON_INSTALL_DIR="$work/python"
targets=(3.11 3.13)
if [[ "$(uname -s)" == Linux ]]; then
  targets=(cpython-3.11-linux-x86_64-gnu cpython-3.13-linux-x86_64-gnu)
fi
uv python install "${targets[@]}" >> "$results/provision.log" 2>&1
{ uname -a; uv --version; node --version; git --version; } > "$results/environment.txt"
failed=0
for version in 3.11 3.13; do
  cell="$results/python-$version"
  mkdir "$cell"
  if [[ "$(uname -s)" == Linux ]]; then
    # uv's discovery filters foreign architectures; use the explicit installed
    # x86 target instead of accidentally selecting the native ARM interpreter.
    python_bin="$UV_PYTHON_INSTALL_DIR/cpython-$version-linux-x86_64-gnu/bin/python3"
  else
    python_bin=$(uv python find --managed-python "$version")
  fi
  [[ -x "$python_bin" ]] || exit 1
  "$python_bin" -c 'import sys; assert "%s.%s" % sys.version_info[:2] == sys.argv[1]' "$version"
  "$python_bin" -c 'import sysconfig; print(sysconfig.get_platform()); print(sysconfig.get_config_var("MULTIARCH"))' > "$cell/platform.txt"
  if [[ "$(uname -s)" == Linux ]]; then
    "$python_bin" -c 'import sysconfig; assert sysconfig.get_platform() == "linux-x86_64"'
    file -L "$python_bin" >> "$cell/platform.txt"
  fi
  if bash scripts/ci/check.sh "$python_bin" "$cell" > "$cell/console.log" 2>&1; then
    printf '%s PASS\n' "$version" >> "$results/matrix.txt"
  else
    failed=1
    printf '%s FAIL\n' "$version" >> "$results/matrix.txt"
  fi
done
((failed == 0)) || exit 1
# Real install/check/uninstall supplements the unit upgrade/repair/bundle tests.
python_dir=$(dirname "$python_bin")
export PATH="$python_dir:$PATH"
for target in codex claude both; do
  pilot_home="$work/pilot-$target"
  sh installer/install.sh install --home "$pilot_home" --target "$target" --yes --offline > "$results/install-$target.txt"
  sh installer/install.sh check --home "$pilot_home" --target "$target" --offline --json > "$results/check-$target.json"
  sh installer/install.sh uninstall --home "$pilot_home" --target "$target" --yes >> "$results/install-$target.txt"
done
if [[ "$(uname -s)" == Darwin ]]; then
  # Minimal GUI PATH must locate an organization-installed Python independently.
  # Managed test interpreters are intentionally outside those locations.
  HOMEBREW_NO_AUTO_UPDATE=1 brew install python@3.13 >> "$results/provision.log" 2>&1
  printf '\n' | env PATH=/usr/bin:/bin:/usr/sbin:/sbin bash 'installer/Install Blog Studio.command' --dry-run --offline > "$results/launcher-gui-path.txt"
  env PATH=/usr/bin:/bin:/usr/sbin:/sbin sh installer/install.sh --dry-run --offline --json > "$results/shell-minimal-path.json"
  cp 'installer/Install Blog Studio.command' "$work/Quarantined Installer.command"
  xattr -w com.apple.quarantine '0083;00000000;BlogStudioPilot;' "$work/Quarantined Installer.command"
  if spctl --assess --type execute "$work/Quarantined Installer.command" > "$results/quarantine-assessment.txt" 2>&1; then
    echo 'assessment accepted; actual GUI launch requires observation' >> "$results/quarantine-assessment.txt"
  else
    echo 'assessment rejected; no protections bypassed; actual GUI launch requires observation' >> "$results/quarantine-assessment.txt"
  fi
fi
printf 'PASS\n' > "$results/result.txt"
