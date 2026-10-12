#!/usr/bin/env bash
# The one list of project checks. CI, the release workflow and local runs all call this:
#   bash scripts/ci/check.sh /path/to/python3 /path/to/new-results-directory
# Cheap checks run first. The test suite runs last and prints the end of its log on failure.
set -euo pipefail
python_bin=${1:?Pass the Python interpreter}
results=${2:?Pass a new results directory}
mkdir -p "$results"
python_dir=$(dirname "$python_bin")
export PATH="$python_dir:$PATH"
"$python_bin" --version > "$results/python.txt"
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
