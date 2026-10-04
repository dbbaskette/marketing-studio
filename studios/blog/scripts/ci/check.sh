#!/usr/bin/env bash
# The hosted workflow's checks, with an explicit matrix interpreter.
set -euo pipefail
python_bin=${1:?Pass the Python interpreter}
results=${2:?Pass a new results directory}
mkdir -p "$results"
python_dir=$(dirname "$python_bin")
export PATH="$python_dir:$PATH"
"$python_bin" --version > "$results/python.txt"
"$python_bin" -m unittest discover -s tests -v > "$results/tests.log" 2>&1
node scripts/ci/check-newcomer.cjs > "$results/newcomer-prompts.json"
"$python_bin" scripts/measure_guidance.py --check > "$results/guidance.json"
"$python_bin" skills/blog-studio/scripts/validate_package.py > "$results/package.txt"
"$python_bin" skills/blog-writing-toolkit/scripts/validate_package.py >> "$results/package.txt"
sh -n installer/install.sh
bash -n 'installer/Install Blog Studio.command'
printf 'PASS\n' > "$results/result.txt"
