#!/usr/bin/env bash
# Trusted read-only bootstrap, executed before any PR job or runner credential.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ "$(uname -s)" == Linux ]]; then
  shared=/mnt/shared/bootstrap
  bash "$shared/rosetta-linux.sh"
  sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y libicu74 libkrb5-3 libssl3t64 zlib1g
  python3 -m venv /tmp/blog-studio-runner-tools
  /tmp/blog-studio-runner-tools/bin/pip install uv==0.11.19
  export PATH="/tmp/blog-studio-runner-tools/bin:$PATH"
  targets=(cpython-3.11-linux-x86_64-gnu cpython-3.13-linux-x86_64-gnu)
else
  shared='/Volumes/My Shared Files/bootstrap'
  HOMEBREW_NO_AUTO_UPDATE=1 brew install uv python@3.13
  targets=(3.11 3.13)
fi
export UV_PYTHON_INSTALL_DIR=/tmp/blog-studio-runner-python
uv python install "${targets[@]}"
runner=/tmp/blog-studio-actions-runner
[[ ! -e "$runner" ]] || { echo 'Base contains a prior runner; refusing reuse.' >&2; exit 1; }
mkdir -m 700 "$runner"
tar -xzf "$shared/runner.tar.gz" -C "$runner"
"$runner/bin/Runner.Listener" --version
"$runner/config.sh" --help
printf 'Bootstrap complete; credentials have not been requested.\n'
