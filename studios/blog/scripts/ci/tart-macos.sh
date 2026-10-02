#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
suite_runner="${MACOS_TEST_SUITE:-$HOME/Projects/macos-test-suite}/scripts/tart-test-vm.sh"
[[ -f "$suite_runner" ]] || { echo 'Set MACOS_TEST_SUITE to the reusable macos-test-suite checkout.' >&2; exit 1; }
exec bash "$suite_runner" --project "$project_root" --name blog-studio \
  --guest scripts/ci/macos-guest.sh --base "${TART_BASE:-tanzu-brand-golden-gate-base}" --auto --keep "$@"
