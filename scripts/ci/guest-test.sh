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
"$python" - "$work/repo" "$results_dir/source-files.sha256" <<'PYHASH'
import hashlib, os, pathlib, sys
root = pathlib.Path(sys.argv[1])
rows = []
for folder, dirs, files in os.walk(root):
    dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__', '.venv', '.claude', 'dist', 'build'))
    for name in sorted(files):
        path = pathlib.Path(folder) / name
        if path.is_file():
            rows.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + str(path.relative_to(root)) + '\n')
pathlib.Path(sys.argv[2]).write_text(''.join(rows))
PYHASH
"$python" -m venv "$work/tools"
"$work/tools/bin/pip" install -r studios/blog/requirements-dev.txt > "$results_dir/provisioning.log" 2>&1
export PATH="$work/tools/bin:$PATH"
# Real helper contract checks use source only, never an installed skill or provider.
export STUDIO_TEST_RESEARCH_RUNTIME="$work/research-runtime"
"$python" scripts/ci/research-runtime.py "$STUDIO_TEST_RESEARCH_RUNTIME" > "$results_dir/research-runtime.log" 2>&1
if [[ "${1:-full}" == infographic || "${1:-full}" == infographic-finish ]]; then
  # These are explicit CI preparation steps in the disposable clone, not tests
  # downloading software or touching a signed-in machine.
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/graphics" --cache "$work/graphics-cache")"
  mkdir -p "$work/browser"
  cp studios/infographic/tests/ui/package*.json "$work/browser/"
  touch "$work/npm-user.conf" "$work/npm-global.conf"
  env HOME="$work/home" NPM_CONFIG_USERCONFIG="$work/npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/npm-global.conf" \
    npm ci --prefix "$work/browser" --ignore-scripts --no-audit --no-fund > "$results_dir/browser-tools.log" 2>&1
  export NODE_PATH="$work/browser/node_modules"
  export PYTHON="$python"
  export INFOGRAPHIC_UI_RESULTS="$results_dir/infographic-ui"
  if [[ "${1:-full}" == infographic-finish ]]; then
    # Reuse passing full suite evidence for unchanged shared/other-studio code.
    # Verify the final review/approval repair with the full native suite and the
    # same browser + source-independent prepared package journeys.
    {
      "$python" -m compileall -q studios/infographic/runner
      node --check studios/infographic/runner/web/app.js
      "$python" -m unittest discover -s studios/infographic/tests -v
      PYTHONPATH=tests "$python" -m unittest test_infographic_release test_start_stop.ParserTests -v
    } 2>&1 | tee "$results_dir/tests.log"
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee -a "$results_dir/tests.log"
  else
    bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
  fi
  node studios/infographic/tests/ui/journey.cjs 2>&1 | tee "$results_dir/infographic-browser.log"
  bundle="$(find dist -maxdepth 1 -name 'infographic-first-release-*-macos-arm64.zip' -print -quit)"
  [[ -n "$bundle" ]] || { echo 'A prepared Infographic Studio-only Apple Silicon package is required.' >&2; exit 1; }
  "$python" scripts/ci/infographic_bundle_acceptance.py "$bundle" 2>&1 | tee "$results_dir/infographic-bundle.log"
elif [[ "${1:-full}" == presentation-progress ]]; then
  (
    cd studios/presentation
    "$python" scripts/ci/run_tests.py --jobs 4
    "$python" skills/presentation-studio/scripts/validate_package.py
  ) 2>&1 | tee "$results_dir/presentation-tests.log"
  PYTHONPATH=tests "$python" -m unittest test_suite -v 2>&1 | tee "$results_dir/package-tests.log"
  bundle="$(find dist -maxdepth 1 -name 'marketing-studio-*-macos-arm64.zip' -print -quit)"
  [[ -n "$bundle" ]] || exit 1
  "$python" scripts/ci/bundle_acceptance.py "$bundle" 2>&1 | tee "$results_dir/bundle-acceptance.log"
elif [[ "${1:-full}" == bundles ]]; then
  bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
  bundle="$(find dist -maxdepth 1 -name 'marketing-studio-*-macos-arm64.zip' -print -quit)"
  [[ -n "$bundle" ]] || { echo 'A real Apple Silicon platform bundle is required.' >&2; exit 1; }
  "$python" scripts/ci/bundle_acceptance.py "$bundle" 2>&1 | tee "$results_dir/bundle-acceptance.log"
elif [[ "${1:-full}" == research-finish ]]; then
  # Reuse the passing full root, Blog Studio and Presentation Studio evidence.
  # Repeat Training Studio after its contract expectation repair; verify Stop
  # through both native transports and retain all CLI acceptance journeys.
  {
    PYTHONPATH=tests "$python" -m unittest test_research_contract -v
    (cd studios/blog && PYTHONPATH=tests:skills/blog-studio/scripts "$python" -m unittest test_synthesis_integration -v)
    (cd studios/presentation && PYTHONPATH=tests "$python" -m unittest test_synthesis_integration -v)
    (cd studios/training && bash scripts/ci/check.sh "$python")
  } 2>&1 | tee "$results_dir/research-finish-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == research ]]; then
  # Root installation/settings evidence is unchanged; cover the final research
  # contract, all affected studio suites, and the complete synthetic CLI journeys.
  {
    PYTHONPATH=tests "$python" -m unittest test_research_contract test_companion_versions -v
    (cd studios/blog && BLOG_STUDIO_REQUIRE_LINT=1 BLOG_STUDIO_TEST_JOBS=4 bash scripts/ci/check.sh "$python" "$results_dir/blog-studio")
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
  } 2>&1 | tee "$results_dir/research-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == review-levels ]]; then
  # Reuse the unchanged full Marketing Studio and Blog Studio suite evidence;
  # verify final review fixes, every affected native suite, and all CLI journeys.
  {
    PYTHONPATH=tests "$python" -m unittest test_review_policy -v
    (cd studios/blog && node scripts/ci/check-management.cjs)
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
  } 2>&1 | tee "$results_dir/review-levels-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == shared-setup ]]; then
  # Reuse the full-suite evidence for untouched pipelines; check late setup repairs
  # and the real native journeys against the final source in a fresh guest.
  {
    PYTHONPATH=tests "$python" -m unittest test_shared_setup test_suite.CoreTests test_suite.SuiteTests.test_each_subset_installs_and_runs_without_the_source_checkout -v
    (cd studios/blog && PYTHONPATH=tests:skills/blog-studio/scripts "$python" -m unittest test_shared_studios.ConfigTests -v)
    (cd studios/presentation && PYTHONPATH=tests "$python" -m unittest test_runner_setup test_page_app.LinkTests -v)
    (cd studios/training && PYTHONPATH=tests "$python" -m unittest test_desk.RunnerScreenTests test_runner_page.SetUpTests -v)
    (cd studios/training && "$python" skills/training-studio/scripts/validate_package.py)
    (cd studios/presentation && "$python" skills/presentation-studio/scripts/validate_package.py)
  } 2>&1 | tee "$results_dir/shared-setup-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == acceptance ]]; then
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
else
  bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
fi
printf 'PASS\n' > "$results_dir/result.txt"
