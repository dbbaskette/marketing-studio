#!/usr/bin/env bash
# The one list of project checks. CI, the release workflow and local runs all call this:
#   bash scripts/ci/check.sh /path/to/python3 /path/to/new-results-directory
# Cheap checks run first. The test suite runs last and prints the end of its log on failure.
#
# Lint uses the ruff version pinned in requirements-dev.txt: the one on PATH, or one that uv
# fetches when uv is installed. With neither, lint is skipped with a notice. The workflows set
# BLOG_STUDIO_REQUIRE_LINT=1, which turns a missing linter into a failure.
set -euo pipefail
python_bin=${1:?Pass the Python interpreter}
results=${2:?Pass a new results directory}
mkdir -p "$results"
python_dir=$(dirname "$python_bin")
export PATH="$python_dir:$PATH"
"$python_bin" --version > "$results/python.txt"

ruff_version=$(sed -n 's/^ruff==//p' requirements-dev.txt)
ruff=()
if command -v ruff >/dev/null && [[ "$(ruff --version)" == "ruff $ruff_version" ]]; then
  ruff=(ruff)
elif command -v uv >/dev/null && uv tool run --quiet "ruff@$ruff_version" --version >/dev/null 2>&1; then
  ruff=(uv tool run --quiet "ruff@$ruff_version")
fi
lint() {
  local status=0
  "${ruff[@]}" check --no-cache || status=1
  "${ruff[@]}" format --check --no-cache || status=1
  return "$status"
}
if (( ${#ruff[@]} )); then
  if ! lint > "$results/lint.txt" 2>&1; then
    cat "$results/lint.txt" >&2
    exit 1
  fi
  echo "Lint and format check passed (ruff $ruff_version)."
elif [[ "${BLOG_STUDIO_REQUIRE_LINT:-}" == 1 ]]; then
  echo "Lint needs ruff $ruff_version. Install it: python3 -m pip install -r requirements-dev.txt" >&2
  exit 1
else
  echo "SKIPPED lint and format check: ruff $ruff_version is not installed (python3 -m pip install -r requirements-dev.txt)." \
    | tee "$results/lint.txt"
fi

sh -n installer/install.sh
sh -n installer/google-setup.sh
bash -n 'installer/Install Blog Studio.command'
"$python_bin" skills/blog-studio/scripts/validate_package.py > "$results/package.txt"
"$python_bin" skills/blog-writing-toolkit/scripts/validate_package.py >> "$results/package.txt"
"$python_bin" scripts/build.py --check > "$results/build.json"
node scripts/ci/check-newcomer.cjs > "$results/newcomer-prompts.json"
"$python_bin" scripts/measure_guidance.py --check > "$results/guidance.json"
if ! "$python_bin" -m unittest discover -s tests -v > "$results/tests.log" 2>&1; then
  tail -n 80 "$results/tests.log" >&2
  exit 1
fi
printf 'PASS\n' > "$results/result.txt"
