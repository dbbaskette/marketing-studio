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
if [[ "${1:-full}" == infographic-planning || "${1:-full}" == infographic-activity || "${1:-full}" == infographic-activity-finish || "${1:-full}" == infographic-google-finish || "${1:-full}" == infographic-followups-final || "${1:-full}" == infographic-followups || "${1:-full}" == infographic || "${1:-full}" == infographic-finish || "${1:-full}" == infographic-after-root || "${1:-full}" == infographic-acceptance ]]; then
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
  if [[ "${1:-full}" == infographic-planning || "${1:-full}" == infographic-activity || "${1:-full}" == infographic-activity-finish ]]; then
    {
      node --check studios/infographic/runner/web/app.js
      if [[ "${1:-full}" == infographic-planning || "${1:-full}" == infographic-activity-finish ]]; then
        # Retain the passing full shared suite for unchanged core/home code.
        # Cover affected UI gates; planning also repeats the full native suite.
        PYTHONPATH=tests "$python" -m unittest test_ui_consistency test_layout_pass -v
        if [[ -n "${MARKETING_STUDIO_TEST_SHARED_INTEGRATION:-}" ]]; then
          PYTHONPATH=tests "$python" -m unittest test_bridge_connect test_sync_guard test_companion_versions test_shared_runner test_network -v
        fi
        if [[ "${1:-full}" == infographic-planning ]]; then
          "$python" -m unittest discover -s studios/infographic/tests -v
        fi
      else
        "$python" -m unittest discover -s tests -v
        "$python" -m unittest discover -s studios/infographic/tests -v
      fi
    } 2>&1 | tee "$results_dir/activity-tests.log"
    node studios/infographic/tests/ui/activity.cjs 2>&1 | tee "$results_dir/activity-browser.log"
    if [[ -n "${MARKETING_STUDIO_TEST_LIQUID_PILOT:-}" ]]; then
      node studios/infographic/tests/ui/liquid-pilot.cjs 2>&1 | tee "$results_dir/liquid-pilot-browser.log"
    fi
    if [[ -n "${INFOGRAPHIC_STUDIO_TEST_VISUAL_PAGES:-}" ]]; then
      node studios/infographic/tests/ui/image-recovery.cjs 2>&1 | tee "$results_dir/image-recovery-browser.log"
      "$python" studios/infographic/tests/visual_gallery.py --renderer "$INFOGRAPHIC_STUDIO_TEST_RENDERER" \
        --output "$results_dir/visual-gallery" 2>&1 | tee "$results_dir/visual-gallery.log"
    fi
    if [[ -n "${INFOGRAPHIC_STUDIO_TEST_CONTRACTS:-}" ]]; then
      node studios/infographic/tests/ui/workflow-matrix.cjs 2>&1 | tee "$results_dir/workflow-contracts-browser.log"
    fi
    INFOGRAPHIC_STUDIO_TEST_REMOTE=1 node studios/infographic/tests/ui/journey.cjs 2>&1 | tee "$results_dir/infographic-google-browser.log"
    if [[ -n "${INFOGRAPHIC_STUDIO_TEST_VISUAL:-}" ]]; then
      INFOGRAPHIC_STUDIO_TEST_VISUAL=parts INFOGRAPHIC_STUDIO_TEST_REMOTE=1 node studios/infographic/tests/ui/journey.cjs 2>&1 | tee "$results_dir/infographic-components-browser.log"
    fi
  elif [[ "${1:-full}" == infographic-followups-final ]]; then
    {
      PYTHONPATH=tests "$python" -m unittest test_infographic_network -v
      PYTHONPATH=studios/infographic/tests "$python" -m unittest test_handoffs test_google_delivery -v
      node studios/infographic/tests/ui/intake.cjs
      INFOGRAPHIC_STUDIO_TEST_REMOTE=1 node studios/infographic/tests/ui/journey.cjs
    } 2>&1 | tee "$results_dir/final-bridge-delivery-tests.log"
  elif [[ "${1:-full}" == infographic-followups || "${1:-full}" == infographic-google-finish ]]; then
    # New core modules are additive; unchanged studio suites retain their earlier evidence.
    {
      if [[ "${1:-full}" == infographic-google-finish ]]; then
        # The broad root run completed; correct the two retired running-light
        # expectations and the upstream product-name comment, then reuse other cases.
        PYTHONPATH=tests "$python" -m unittest test_layout_pass test_shared_runner test_home -v
        (cd studios/presentation && PYTHONPATH=tests "$python" -m unittest test_sync -v)
      else
        "$python" -m unittest discover -s tests -v
      fi
      "$python" -m unittest discover -s studios/infographic/tests -v
      bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
    } 2>&1 | tee "$results_dir/tests.log"
    node studios/infographic/tests/ui/home-readiness.cjs 2>&1 | tee "$results_dir/home-readiness-browser.log"
    INFOGRAPHIC_STUDIO_TEST_REMOTE=1 INFOGRAPHIC_STUDIO_TEST_SLIDES=1 node studios/infographic/tests/ui/journey.cjs 2>&1 | tee "$results_dir/infographic-slides-browser.log"
    node studios/infographic/tests/ui/intake.cjs 2>&1 | tee "$results_dir/infographic-intake-browser.log"
    INFOGRAPHIC_STUDIO_TEST_REMOTE=1 node studios/infographic/tests/ui/journey.cjs 2>&1 | tee "$results_dir/infographic-google-browser.log"
  elif [[ "${1:-full}" == infographic-acceptance ]]; then
    # All application suites passed except the now-corrected takeover fixture.
    # Reuse unchanged evidence; repeat the changed group in the same guest OS.
    {
      (cd studios/training && PYTHONPATH=tests "$python" -m unittest test_runner_page.DeskTeamTests -v)
      PYTHONPATH=tests "$python" -m unittest test_suite_link -v
      bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
    } 2>&1 | tee "$results_dir/tests.log"
  elif [[ "${1:-full}" == infographic-after-root ]]; then
    # Root and Infographic Studio already passed on this unchanged application tree.
    # Continue after repairing formatting in the newly integrated upstream tests.
    {
      (cd studios/blog && BLOG_STUDIO_REQUIRE_LINT=1 BLOG_STUDIO_TEST_JOBS=4 bash scripts/ci/check.sh "$python" "$results_dir/blog-studio")
      (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
      (cd studios/training && bash scripts/ci/check.sh "$python")
      bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
    } 2>&1 | tee "$results_dir/tests.log"
  elif [[ "${1:-full}" == infographic-finish ]]; then
    # Reuse passing Blog Studio evidence. Verify shared folder concurrency and
    # return navigation against root/native and both affected deck studios.
    {
      "$python" -m compileall -q studios/infographic/runner
      node --check studios/infographic/runner/web/app.js
      "$python" -m unittest discover -s studios/infographic/tests -v
      "$python" -m unittest discover -s tests -v
      (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
      (cd studios/training && bash scripts/ci/check.sh "$python")
    } 2>&1 | tee "$results_dir/tests.log"
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee -a "$results_dir/tests.log"
  else
    bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
  fi
  node studios/infographic/tests/ui/journey.cjs 2>&1 | tee "$results_dir/infographic-browser.log"
  node studios/infographic/tests/ui/suite-return.cjs 2>&1 | tee "$results_dir/suite-return-browser.log"
  pattern='infographic-first-release-*-macos-arm64.zip'
  if [[ "${1:-full}" == infographic-planning || "${1:-full}" == infographic-activity || "${1:-full}" == infographic-activity-finish || "${1:-full}" == infographic-followups || "${1:-full}" == infographic-followups-final || "${1:-full}" == infographic-google-finish ]]; then pattern='infographic-followups-*-macos-arm64.zip'; fi
  if [[ -n "${INFOGRAPHIC_STUDIO_TEST_VISUAL:-}" ]]; then pattern="infographic-followups-$(cat VERSION)-macos-arm64.zip"; fi
  bundle="$(find dist -maxdepth 1 -name "$pattern" -print -quit)"
  [[ -n "$bundle" ]] || { echo 'A prepared Infographic Studio-only Apple Silicon package is required.' >&2; exit 1; }
  "$python" scripts/ci/infographic_bundle_acceptance.py "$bundle" 2>&1 | tee "$results_dir/infographic-bundle.log"
elif [[ "${1:-full}" == training-settings ]]; then
  (cd studios/training && "$python" scripts/ci/run_tests.py test_desk test_settings_change test_layout && "$python" skills/training-studio/scripts/validate_package.py) > "$results_dir/training-tests.log" 2>&1
  PYTHONPATH=tests "$python" -m unittest test_ui_consistency test_layout_pass -v > "$results_dir/layout-tests.log" 2>&1
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/settings-graphics" --cache "$work/settings-cache")"
  mkdir -p "$work/settings-browser"
  cp studios/infographic/tests/ui/package*.json "$work/settings-browser/"
  touch "$work/settings-npm-user.conf" "$work/settings-npm-global.conf"
  env HOME="$work/settings-home" NPM_CONFIG_USERCONFIG="$work/settings-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/settings-npm-global.conf" \
    npm ci --prefix "$work/settings-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/settings-browser-tools.log" 2>&1
  export NODE_PATH="$work/settings-browser/node_modules" PYTHON="$python" TRAINING_SETTINGS_UI_RESULTS="$results_dir/settings-ui"
  node studios/training/tests/ui/settings_sheet.cjs 2>&1 | tee "$results_dir/settings-browser.log"
elif [[ "${1:-full}" == training-first-output || "${1:-full}" == training-first-output-finish ]]; then
  if [[ "${1:-full}" == training-first-output-finish ]]; then
    # Finish the completed full runs: recheck the repaired brand race and final
    # assembly assertions, then run the remaining package and presentation checks.
    PYTHONPATH=core:tests "$python" -m unittest test_brands -v > "$results_dir/brand-recheck.log" 2>&1
    (cd studios/training && "$python" scripts/ci/run_tests.py test_section_research && "$python" skills/training-studio/scripts/validate_package.py) > "$results_dir/training-tests.log" 2>&1
  else
    PYTHONPATH=core:tests "$python" -m unittest discover -s tests -v > "$results_dir/shared-tests.log" 2>&1
    (cd studios/training && bash scripts/ci/check.sh "$python") > "$results_dir/training-tests.log" 2>&1
  fi
  (cd studios/presentation && "$python" scripts/ci/run_tests.py test_parallel_research) > "$results_dir/presentation-tests.log" 2>&1
elif [[ "${1:-full}" == training-flow || "${1:-full}" == training-cult-ui || "${1:-full}" == training-cult-ui-browser ]]; then
  if [[ "${1:-full}" != training-cult-ui-browser ]]; then
    (cd studios/training && bash scripts/ci/check.sh "$python") > "$results_dir/training-tests.log" 2>&1
  fi
  if [[ "${1:-full}" != training-flow ]]; then
    PYTHONPATH=core:tests "$python" -m unittest test_intake_page test_ui_consistency -v > "$results_dir/shared-ui-tests.log" 2>&1
    export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/ui-graphics" --cache "$work/ui-graphics-cache")"
    mkdir -p "$work/ui-browser"
    cp studios/infographic/tests/ui/package*.json "$work/ui-browser/"
    touch "$work/ui-npm-user.conf" "$work/ui-npm-global.conf"
    env HOME="$work/ui-browser-home" NPM_CONFIG_USERCONFIG="$work/ui-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/ui-npm-global.conf" \
      npm ci --prefix "$work/ui-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/ui-browser-tools.log" 2>&1
    export NODE_PATH="$work/ui-browser/node_modules" PYTHON="$python"
    STUDIO_AUDIT_PRODUCT=training node tests/studio_intake_browser.cjs > "$results_dir/intake-browser.log" 2>&1
    node tests/training_progress_browser.cjs > "$results_dir/progress-browser.log" 2>&1
    node tests/rendered_slide_browser.cjs > "$results_dir/slides-browser.log" 2>&1
  fi
elif [[ "${1:-full}" == training-creator-review-finish ]]; then
  # Reuse the completed full shared run; verify its updated handoff expectation
  # and the subsequent recovery cases, then run the full native suite.
  PYTHONPATH=core:tests "$python" -m unittest test_research_contract test_research_decisions test_research_session test_research_sections test_research_view test_research_page -v > "$results_dir/shared-recheck.log" 2>&1
  (cd studios/training && bash scripts/ci/check.sh "$python") > "$results_dir/training-tests.log" 2>&1
  (cd studios/presentation && "$python" scripts/ci/run_tests.py test_parallel_research) > "$results_dir/presentation-tests.log" 2>&1
elif [[ "${1:-full}" == research-final-brief ]]; then
  PYTHONPATH=core:tests "$python" -m unittest discover -s tests -v > "$results_dir/shared-tests.log" 2>&1
  (cd studios/training && "$python" scripts/ci/run_tests.py test_parallel_research test_settings_change.StopTests) > "$results_dir/training-tests.log" 2>&1
  (cd studios/presentation && "$python" scripts/ci/run_tests.py test_parallel_research) > "$results_dir/presentation-tests.log" 2>&1
elif [[ "${1:-full}" == brand-job-race ]]; then
  PYTHONPATH=core:tests "$python" -m unittest test_brands -v > "$results_dir/brand-tests.log" 2>&1
elif [[ "${1:-full}" == early-evidence ]]; then
  PYTHONPATH=core:tests "$python" -m unittest discover -s tests -v > "$results_dir/shared-tests.log" 2>&1
elif [[ "${1:-full}" == native-polling-finish ]]; then
  PYTHONPATH=core:tests "$python" -m unittest test_polling -v > "$results_dir/final-polling.log" 2>&1
  (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 test_desk.ScreenTests test_desk_page.DeskFollowThroughTests test_desk_page.FinishingPageTests test_desk_page.SecondReviewTests test_desk_page.SlideTextStopTests test_engine_process_lock.EngineProcessLockTests && "$python" skills/presentation-studio/scripts/validate_package.py) > "$results_dir/presentation-tests.log" 2>&1
  (cd studios/training && bash scripts/ci/check.sh "$python") > "$results_dir/training-tests.log" 2>&1
elif [[ "${1:-full}" == native-polling ]]; then
  PYTHONPATH=core:tests "$python" -m unittest discover -s tests -v > "$results_dir/shared-tests.log" 2>&1
  (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py) > "$results_dir/presentation-tests.log" 2>&1
  (cd studios/training && bash scripts/ci/check.sh "$python") > "$results_dir/training-tests.log" 2>&1
elif [[ "${1:-full}" == blog-intake ]]; then
  (cd studios/blog && BLOG_STUDIO_REQUIRE_LINT=1 BLOG_STUDIO_TEST_JOBS=4 bash scripts/ci/check.sh "$python" "$results_dir/blog-studio" && node scripts/ci/check-management.cjs > "$results_dir/blog-management.json") 2>&1 | tee "$results_dir/blog-checks.log"
elif [[ "${1:-full}" == blog-google-tabs ]]; then
  # Full Blog Studio verification plus package boundaries and disposable CLI journeys.
  (
    cd studios/blog
    BLOG_STUDIO_REQUIRE_LINT=1 BLOG_STUDIO_TEST_JOBS=4 bash scripts/ci/check.sh "$python" "$results_dir/blog-studio"
    node scripts/ci/check-management.cjs > "$results_dir/blog-management.json"
  ) 2>&1 | tee "$results_dir/blog-checks.log"
  PYTHONPATH=tests "$python" -m unittest test_suite -v 2>&1 | tee "$results_dir/package-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/acceptance.log"
elif [[ "${1:-full}" == backlog-launchers-finish ]]; then
  # Full shared gate completed; only the former never-reuse mock needed updating.
  PYTHONPATH=tests "$python" -m unittest test_network test_cli -v 2>&1 | tee "$results_dir/affected-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/acceptance.log"
elif [[ "${1:-full}" == backlog-launchers ]]; then
  "$python" -m unittest discover -s tests -v 2>&1 | tee "$results_dir/shared-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/acceptance.log"
elif [[ "${1:-full}" == network ]]; then
  # The LAN bridge is shared by all studios. Exercise the complete home/core/
  # installer suite without starting any provider jobs or using signed-in state.
  "$python" -m unittest discover -s tests -v 2>&1 | tee "$results_dir/network-suite.log"
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
elif [[ "${1:-full}" == marketing-home ]]; then
  # Shared launcher changes need the complete shared suite and real browser
  # states, without repeating unchanged native content pipelines.
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/home-graphics" --cache "$work/home-graphics-cache")"
  mkdir -p "$work/home-browser"
  cp studios/infographic/tests/ui/package*.json "$work/home-browser/"
  touch "$work/home-npm-user.conf" "$work/home-npm-global.conf"
  env HOME="$work/home-browser-home" NPM_CONFIG_USERCONFIG="$work/home-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/home-npm-global.conf" \
    npm ci --prefix "$work/home-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/home-browser-tools.log" 2>&1
  export NODE_PATH="$work/home-browser/node_modules" PYTHON="$python" HOME_LAUNCHPAD_RESULTS="$results_dir/home-ui"
  node tests/home_launchpad.cjs 2>&1 | tee "$results_dir/home-browser.log"
  node studios/infographic/tests/ui/home-readiness.cjs 2>&1 | tee "$results_dir/home-readiness-browser.log"
  "$python" -m unittest discover -s tests -v 2>&1 | tee "$results_dir/home-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/home-acceptance.log"
elif [[ "${1:-full}" == audit-week3 || "${1:-full}" == audit-week4 ]]; then
  # Complete outline-first gates. Week 4 adds Presentation Studio and both native
  # suites for the shared scanner; unchanged Blog/Infographic Studio retain evidence.
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/outline-graphics" --cache "$work/outline-graphics-cache")"
  mkdir -p "$work/outline-browser"
  cp studios/infographic/tests/ui/package*.json "$work/outline-browser/"
  touch "$work/outline-npm-user.conf" "$work/outline-npm-global.conf"
  env HOME="$work/outline-browser-home" NPM_CONFIG_USERCONFIG="$work/outline-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/outline-npm-global.conf" \
    npm ci --prefix "$work/outline-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/outline-browser-tools.log" 2>&1
  export NODE_PATH="$work/outline-browser/node_modules" PYTHON="$python" TRAINING_OUTLINE_RESULTS="$results_dir/outline-ui"
  node studios/training/tests/ui/outline.cjs 2>&1 | tee "$results_dir/outline-browser.log"
  if [[ "${1:-full}" == audit-week4 ]]; then
    export PRESENTATION_STORY_RESULTS="$results_dir/story-ui"
    node studios/presentation/tests/ui/story.cjs 2>&1 | tee "$results_dir/story-browser.log"
  fi
  {
    "$python" scripts/workflow_diagrams.py --check
    "$python" -m unittest discover -s tests -v
    if [[ "${1:-full}" == audit-week4 ]]; then
      (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    fi
    (cd studios/training && bash scripts/ci/check.sh "$python")
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week6-final ]]; then
  # Shared/real-helper/browser and all 2,181 Presentation Studio tests passed.
  # Training Studio completed all 3,175 tests; only these classes observed the
  # optional response key, absent-node handling or updated release label. Rerun
  # each affected complete class, then package and every installer/CLI gate.
  {
    (cd studios/training && "$python" scripts/ci/run_tests.py test_desk.LibraryScreenTests test_desk.RunnerScreenTests test_runner_page.LaterTests test_runner_page.PullCopyTests test_runner_page.RunTests test_runner_page.WireTests test_runner_slides.CurrentTests test_runner_slides.FindingTheRuntimeTests && "$python" skills/training-studio/scripts/validate_package.py)
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week6-finish ]]; then
  # Root 968 checks and both browser journeys completed on the unchanged runtime;
  # only the stale pin-version assertion required correction. Finish its targeted
  # contract and every full affected native suite, package and CLI gate.
  {
    PYTHONPATH=tests "$python" -m unittest test_companion_versions.PinnedFloorTests test_research_impact -v
    "$python" scripts/workflow_diagrams.py --check
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week7-finish ]]; then
  # Shared, Infographic Studio and both browser gates passed. Continue after
  # formatting the Blog Studio save hook; application behavior is unchanged.
  {
    (cd studios/blog && BLOG_STUDIO_REQUIRE_LINT=1 BLOG_STUDIO_TEST_JOBS=4 bash scripts/ci/check.sh "$python" "$results_dir/blog-studio")
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week8 ]]; then
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/recovery-graphics" --cache "$work/recovery-cache")"
  mkdir -p "$work/recovery-browser"
  cp studios/infographic/tests/ui/package*.json "$work/recovery-browser/"
  touch "$work/recovery-user.conf" "$work/recovery-global.conf"
  env HOME="$work/recovery-home" NPM_CONFIG_USERCONFIG="$work/recovery-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/recovery-global.conf" npm ci --prefix "$work/recovery-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/browser-tools.log" 2>&1
  export NODE_PATH="$work/recovery-browser/node_modules" PYTHON="$python" INFOGRAPHIC_UI_RESULTS="$results_dir/recovery-ui" HOME_LAUNCHPAD_RESULTS="$results_dir/home-ui"
  node tests/home_launchpad.cjs 2>&1 | tee "$results_dir/home-browser.log"
  node studios/infographic/tests/ui/build-recovery.cjs 2>&1 | tee "$results_dir/recovery-browser.log"
  export TRAINING_OUTLINE_RESULTS="$results_dir/outline-ui" PRESENTATION_STORY_RESULTS="$results_dir/story-ui"
  node studios/training/tests/ui/outline.cjs 2>&1 | tee "$results_dir/outline-browser.log"
  node studios/presentation/tests/ui/story.cjs 2>&1 | tee "$results_dir/story-browser.log"
  "$python" scripts/workflow_diagrams.py --check
  (cd studios/presentation && "$python" skills/presentation-studio/scripts/validate_package.py)
  (cd studios/training && "$python" skills/training-studio/scripts/validate_package.py)
  PYTHONPATH=tests "$python" -m unittest test_suite test_work_overview -v 2>&1 | tee "$results_dir/package-tests.log"
elif [[ "${1:-full}" == backlog-spending-acceptance ]]; then
  # Full Training Studio completed on unchanged application code; old hard-stop
  # fixture assumptions and the exhaustive route request bodies are corrected.
  {
    (cd studios/training && "$python" scripts/ci/run_tests.py --jobs 4 test_desk.RunnerScreenTests test_settings_change.StopTests test_parallel_research.ParallelNativeTests test_runner_page.RuleTests)
    (cd studios/presentation && PYTHONPATH=tests "$python" -m unittest test_runner_page.CapabilityTests test_runner_page.RuleTests -v)
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == followup-home-recovery ]]; then
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/graphics" --cache "$work/graphics-cache")"
  mkdir -p "$work/browser"
  cp studios/infographic/tests/ui/package*.json "$work/browser/"
  touch "$work/npm-user.conf" "$work/npm-global.conf"
  env HOME="$work/browser-home" NPM_CONFIG_USERCONFIG="$work/npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/npm-global.conf" npm ci --prefix "$work/browser" --ignore-scripts --no-audit --no-fund > "$results_dir/browser-tools.log" 2>&1
  export NODE_PATH="$work/browser/node_modules" PYTHON="$python" HOME_LAUNCHPAD_RESULTS="$results_dir/home-ui" INFOGRAPHIC_UI_RESULTS="$results_dir/recovery-ui"
  node tests/home_launchpad.cjs 2>&1 | tee "$results_dir/home-browser.log"
  node studios/infographic/tests/ui/build-recovery.cjs 2>&1 | tee "$results_dir/recovery-browser.log"
  # Focused UI/metadata/renderer changes: reuse the unchanged native pipeline,
  # installer and launch evidence; cover only affected module suites and pages.
  {
    PYTHONPATH=tests "$python" -m unittest test_work_overview test_layout_pass test_ui_consistency -v
    PYTHONPATH=studios/infographic/tests "$python" -m unittest test_build_recovery test_delivery_flow test_render test_workbench -v
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == backlog-brands ]]; then
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/graphics" --cache "$work/graphics-cache")"
  mkdir -p "$work/browser"
  cp studios/infographic/tests/ui/package*.json "$work/browser/"
  touch "$work/npm-user.conf" "$work/npm-global.conf"
  env HOME="$work/browser-home" NPM_CONFIG_USERCONFIG="$work/npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/npm-global.conf" npm ci --prefix "$work/browser" --ignore-scripts --no-audit --no-fund > "$results_dir/browser-tools.log" 2>&1
  export NODE_PATH="$work/browser/node_modules" PYTHON="$python" BRANDS_UI_RESULTS="$results_dir/brands-ui" HOME_LAUNCHPAD_RESULTS="$results_dir/home-ui" SPENDING_UI_RESULTS="$results_dir/spending-ui"
  node tests/brands_browser.cjs 2>&1 | tee "$results_dir/brands-browser.log"
  node tests/home_launchpad.cjs 2>&1 | tee "$results_dir/home-browser.log"
  node tests/spending_browser.cjs 2>&1 | tee "$results_dir/spending-browser.log"
  bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == backlog-spending-final ]]; then
  # The complete shared, Infographic, Blog and Presentation suites completed.
  # Only the exhaustive API route lists changed; cover page auth/methods again,
  # then finish Training Studio and installer/CLI acceptance.
  {
    (cd studios/presentation && PYTHONPATH=tests "$python" -m unittest test_runner_page -v)
    (cd studios/training && bash scripts/ci/check.sh "$python")
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == backlog-spending-finish ]]; then
  # Shared 984 cases and all browser journeys completed; only the old section-list
  # expectation changed. Recheck that group, then complete every native suite.
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/graphics" --cache "$work/graphics-cache")"
  {
    PYTHONPATH=tests "$python" -m unittest test_layout_pass -v
    "$python" -m unittest discover -s studios/infographic/tests -v
    (cd studios/blog && BLOG_STUDIO_REQUIRE_LINT=1 BLOG_STUDIO_TEST_JOBS=4 bash scripts/ci/check.sh "$python" "$results_dir/blog-studio")
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == backlog-spending ]]; then
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/recovery-graphics" --cache "$work/recovery-cache")"
  mkdir -p "$work/recovery-browser"
  cp studios/infographic/tests/ui/package*.json "$work/recovery-browser/"
  touch "$work/recovery-user.conf" "$work/recovery-global.conf"
  env HOME="$work/recovery-home" NPM_CONFIG_USERCONFIG="$work/recovery-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/recovery-global.conf" npm ci --prefix "$work/recovery-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/browser-tools.log" 2>&1
  export NODE_PATH="$work/recovery-browser/node_modules" PYTHON="$python" INFOGRAPHIC_UI_RESULTS="$results_dir/recovery-ui" HOME_LAUNCHPAD_RESULTS="$results_dir/home-ui"
  node tests/home_launchpad.cjs 2>&1 | tee "$results_dir/home-browser.log"
  node studios/infographic/tests/ui/build-recovery.cjs 2>&1 | tee "$results_dir/recovery-browser.log"
  export SPENDING_UI_RESULTS="$results_dir/spending-ui" TRAINING_OUTLINE_RESULTS="$results_dir/outline-ui" PRESENTATION_STORY_RESULTS="$results_dir/story-ui"
  node tests/spending_browser.cjs 2>&1 | tee "$results_dir/spending-browser.log"
  node studios/training/tests/ui/outline.cjs 2>&1 | tee "$results_dir/outline-browser.log"
  node studios/presentation/tests/ui/story.cjs 2>&1 | tee "$results_dir/story-browser.log"
  "$python" scripts/workflow_diagrams.py --check
  bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week7-browser || "${1:-full}" == audit-week7-full ]]; then
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/recovery-graphics" --cache "$work/recovery-cache")"
  mkdir -p "$work/recovery-browser"
  cp studios/infographic/tests/ui/package*.json "$work/recovery-browser/"
  touch "$work/recovery-user.conf" "$work/recovery-global.conf"
  env HOME="$work/recovery-home" NPM_CONFIG_USERCONFIG="$work/recovery-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/recovery-global.conf" npm ci --prefix "$work/recovery-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/browser-tools.log" 2>&1
  export NODE_PATH="$work/recovery-browser/node_modules" PYTHON="$python" INFOGRAPHIC_UI_RESULTS="$results_dir/recovery-ui" HOME_LAUNCHPAD_RESULTS="$results_dir/home-ui"
  node tests/home_launchpad.cjs 2>&1 | tee "$results_dir/home-browser.log"
  node studios/infographic/tests/ui/build-recovery.cjs 2>&1 | tee "$results_dir/recovery-browser.log"
  if [[ "${1:-full}" == audit-week7-full ]]; then
    "$python" scripts/workflow_diagrams.py --check
    bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
  fi
elif [[ "${1:-full}" == audit-week3-final ]]; then
  # The complete shared suite and final outline browser passed on unchanged
  # application flow. Repeat all native tests after the copy assertion and JSON
  # example loading-budget accounting repairs, then run every CLI acceptance gate.
  (cd studios/training && bash scripts/ci/check.sh "$python") 2>&1 | tee "$results_dir/training-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week2-training-final ]]; then
  # Every other complete suite and both native browser journeys passed. Only old
  # Training Studio layout/body-cap assertions changed; repeat its whole suite
  # before all disposable package/CLI acceptance on the final candidate.
  (cd studios/training && bash scripts/ci/check.sh "$python") 2>&1 | tee "$results_dir/training-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week2-final ]]; then
  # The shared (958), Infographic Studio (250), Blog Studio (1876) and browser
  # gates passed on the unchanged application tree. Only old Presentation Studio
  # screen assertions changed after that run. Finish both complete native suites
  # and every disposable installer/CLI journey on the final candidate.
  {
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks"
  } 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == audit-week2 || "${1:-full}" == audit-week2-browser ]]; then
  # The Document Library's screen, Add existing work and the Add from library sheet in a
  # real browser at phone width, light/dark and reduced effects, over synthetic data only.
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/library-graphics" --cache "$work/library-graphics-cache")"
  mkdir -p "$work/library-browser"
  cp studios/infographic/tests/ui/package*.json "$work/library-browser/"
  touch "$work/library-npm-user.conf" "$work/library-npm-global.conf"
  env HOME="$work/library-browser-home" NPM_CONFIG_USERCONFIG="$work/library-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/library-npm-global.conf" \
    npm ci --prefix "$work/library-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/library-browser-tools.log" 2>&1
  export NODE_PATH="$work/library-browser/node_modules" PYTHON="$python" LIBRARY_VISUAL_RESULTS="$results_dir/library-ui"
  node tests/library_visual.cjs 2>&1 | tee "$results_dir/library-browser.log"
  export STUDIO_INTAKE_RESULTS="$results_dir/intake-ui"
  node tests/studio_intake_browser.cjs 2>&1 | tee "$results_dir/intake-browser.log"
  if [[ "${1:-full}" == audit-week2 ]]; then
    bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
  fi
elif [[ "${1:-full}" == library-visual ]]; then
  # The Document Library's screen, Add existing work and the Add from library sheet in a
  # real browser at phone width, light/dark and reduced effects, over synthetic data only.
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/library-graphics" --cache "$work/library-graphics-cache")"
  mkdir -p "$work/library-browser"
  cp studios/infographic/tests/ui/package*.json "$work/library-browser/"
  touch "$work/library-npm-user.conf" "$work/library-npm-global.conf"
  env HOME="$work/library-browser-home" NPM_CONFIG_USERCONFIG="$work/library-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/library-npm-global.conf" \
    npm ci --prefix "$work/library-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/library-browser-tools.log" 2>&1
  export NODE_PATH="$work/library-browser/node_modules" PYTHON="$python" LIBRARY_VISUAL_RESULTS="$results_dir/library-ui"
  node tests/library_visual.cjs 2>&1 | tee "$results_dir/library-browser.log"
  PYTHONPATH=tests "$python" -m unittest test_document_library test_library_page test_library_adopt test_home test_layout_pass -v 2>&1 | tee "$results_dir/library-tests.log"
elif [[ "${1:-full}" == yoodli-pdf ]]; then
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/source-picker-graphics" --cache "$work/source-picker-cache")"
  mkdir -p "$work/source-picker-browser"
  cp studios/infographic/tests/ui/package*.json "$work/source-picker-browser/"
  touch "$work/source-picker-npm-user.conf" "$work/source-picker-npm-global.conf"
  env HOME="$work/source-picker-browser-home" NPM_CONFIG_USERCONFIG="$work/source-picker-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/source-picker-npm-global.conf" \
    npm ci --prefix "$work/source-picker-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/source-picker-tools.log" 2>&1
  export NODE_PATH="$work/source-picker-browser/node_modules" PYTHON="$python" TRAINING_PLAN_UI_RESULTS="$results_dir/source-picker-ui"
  if command -v pdftotext >/dev/null; then export STUDIO_TEST_REAL_PDF=1; fi
  node studios/training/tests/ui/yoodli_pdf.cjs 2>&1 | tee "$results_dir/source-picker-browser.log"
  bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == research-packet-preflight ]]; then
  # This change is confined to shared evidence validation and its transport
  # instructions. Reuse unchanged UI/material-generation acceptance evidence.
  {
    "$python" -m unittest discover -s tests -v
    (cd studios/training && "$python" scripts/ci/run_tests.py --jobs 4 test_parallel_research test_synthesis_integration test_runner_worker_tools.ResearchCitationTests test_source_start && "$python" skills/training-studio/scripts/validate_package.py)
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 test_parallel_research test_synthesis_integration test_runner_worker_tools.ResearchCitationTests && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/blog && PYTHONPATH=tests "$python" -m unittest test_synthesis_integration -v)
    PYTHONPATH=studios/infographic/tests "$python" -m unittest test_research_jobs test_research -v
  } 2>&1 | tee "$results_dir/research-packet-tests.log"
elif [[ "${1:-full}" == training-plan || "${1:-full}" == training-sources-progress ]]; then
  # Exercise the real page/engine before the complete native suite, so a browser
  # regression does not waste a full-suite run. All authors and settings are fixtures.
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/training-graphics" --cache "$work/training-graphics-cache")"
  mkdir -p "$work/training-browser"
  cp studios/infographic/tests/ui/package*.json "$work/training-browser/"
  touch "$work/training-npm-user.conf" "$work/training-npm-global.conf"
  env HOME="$work/training-browser-home" NPM_CONFIG_USERCONFIG="$work/training-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/training-npm-global.conf" \
    npm ci --prefix "$work/training-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/training-browser-tools.log" 2>&1
  export NODE_PATH="$work/training-browser/node_modules" PYTHON="$python" TRAINING_PLAN_UI_RESULTS="$results_dir/training-plan-ui"
  if [[ "${1:-full}" == training-sources-progress ]]; then
    export TRAINING_PROGRESS_RESULTS="$results_dir/training-progress-ui"
    node studios/training/tests/ui/sources_progress.cjs 2>&1 | tee "$results_dir/training-sources-browser.log"
    node studios/infographic/tests/ui/research.cjs 2>&1 | tee "$results_dir/shared-research-browser.log"
  fi
  node studios/training/tests/ui/training_plan.cjs 2>&1 | tee "$results_dir/training-plan-browser.log"
  if [[ "${1:-full}" == training-sources-progress ]]; then
    bash scripts/ci/check.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
  else
    {
      PYTHONPATH=tests "$python" -m unittest test_ui_consistency test_network_static test_suite.CoreTests -v
      (cd studios/training && bash scripts/ci/check.sh "$python")
    } 2>&1 | tee "$results_dir/training-plan-tests.log"
    bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
  fi
elif [[ "${1:-full}" == slide-text-final || "${1:-full}" == training-workspace-final ]]; then
  # All relevant full suites ran; retain passing classes and verify the last
  # saved-run response compatibility repair before browser/CLI acceptance.
  (cd studios/training && PYTHONPATH=tests "$python" -m unittest test_runner_deck.PageTests test_runner_deck.ReviewToolTests test_slide_text_workflow -v && "$python" skills/training-studio/scripts/validate_package.py) 2>&1 | tee "$results_dir/slide-text-final.log"
  if [[ "${1:-full}" == training-workspace-final ]]; then
    (cd studios/training && PYTHONPATH=tests "$python" -m unittest test_desk_migration.MigrationPageTests test_desk.TrainingDeskScreenTests test_training_plan -v) 2>&1 | tee "$results_dir/training-workspace-final.log"
  fi
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/slide-graphics" --cache "$work/slide-graphics-cache")"
  mkdir -p "$work/slide-browser"
  cp studios/infographic/tests/ui/package*.json "$work/slide-browser/"
  touch "$work/slide-npm-user.conf" "$work/slide-npm-global.conf"
  env HOME="$work/slide-browser-home" NPM_CONFIG_USERCONFIG="$work/slide-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/slide-npm-global.conf" \
    npm ci --prefix "$work/slide-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/slide-browser-tools.log" 2>&1
  export NODE_PATH="$work/slide-browser/node_modules" SLIDE_TEXT_UI_RESULTS="$results_dir/slide-text-ui"
  node tests/slide_text_browser.cjs 2>&1 | tee "$results_dir/slide-text-browser.log"
  if [[ "${1:-full}" == training-workspace-final ]]; then
    PYTHON="$python" TRAINING_WORKSPACE_UI_RESULTS="$results_dir/training-workspace-ui" \
      node studios/training/tests/ui/training_workspace.cjs 2>&1 | tee "$results_dir/training-workspace-browser.log"
  fi
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == slide-text-finish ]]; then
  {
    PYTHONPATH=tests "$python" -m unittest test_ui_consistency -v
    (cd studios/presentation && PYTHONPATH=tests "$python" -m unittest test_runner_page.RuleTests test_desk_page.ProgressTests test_deck_desk.DeskViewTests test_slide_text_workflow -v && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
  } 2>&1 | tee "$results_dir/slide-text-finish.log"
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/slide-graphics" --cache "$work/slide-graphics-cache")"
  mkdir -p "$work/slide-browser"
  cp studios/infographic/tests/ui/package*.json "$work/slide-browser/"
  touch "$work/slide-npm-user.conf" "$work/slide-npm-global.conf"
  env HOME="$work/slide-browser-home" NPM_CONFIG_USERCONFIG="$work/slide-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/slide-npm-global.conf" \
    npm ci --prefix "$work/slide-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/slide-browser-tools.log" 2>&1
  export NODE_PATH="$work/slide-browser/node_modules" SLIDE_TEXT_UI_RESULTS="$results_dir/slide-text-ui"
  node tests/slide_text_browser.cjs 2>&1 | tee "$results_dir/slide-text-browser.log"
  PYTHON="$python" TRAINING_WORKSPACE_UI_RESULTS="$results_dir/training-workspace-ui" \
    node studios/training/tests/ui/training_workspace.cjs 2>&1 | tee "$results_dir/training-workspace-browser.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == slide-text-first ]]; then
  {
    "$python" -m unittest discover -s tests -v
    (cd studios/blog && node scripts/ci/check-management.cjs)
    (cd studios/presentation && "$python" scripts/ci/run_tests.py --jobs 4 && "$python" skills/presentation-studio/scripts/validate_package.py)
    (cd studios/training && bash scripts/ci/check.sh "$python")
  } 2>&1 | tee "$results_dir/slide-text-first.log"
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/slide-graphics" --cache "$work/slide-graphics-cache")"
  mkdir -p "$work/slide-browser"
  cp studios/infographic/tests/ui/package*.json "$work/slide-browser/"
  touch "$work/slide-npm-user.conf" "$work/slide-npm-global.conf"
  env HOME="$work/slide-browser-home" NPM_CONFIG_USERCONFIG="$work/slide-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/slide-npm-global.conf" \
    npm ci --prefix "$work/slide-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/slide-browser-tools.log" 2>&1
  export NODE_PATH="$work/slide-browser/node_modules" SLIDE_TEXT_UI_RESULTS="$results_dir/slide-text-ui"
  node tests/slide_text_browser.cjs 2>&1 | tee "$results_dir/slide-text-browser.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == shared-research-finish ]]; then
  # All five complete suites have run. Recheck the repaired Training Studio
  # expectations, then finish the real synthetic browser and CLI acceptance gates.
  {
    (cd studios/training && PYTHONPATH=tests "$python" -m unittest test_runner_page.RuleTests test_runner_page.LaterTests test_desk.RunnerScreenTests.test_a_run_is_watched_from_working_to_a_gate_to_a_failure_to_done -v && "$python" skills/training-studio/scripts/validate_package.py)
  } 2>&1 | tee "$results_dir/shared-research-finish.log"
  export INFOGRAPHIC_STUDIO_TEST_RENDERER="$("$python" scripts/ci/infographic-renderer.py --output "$work/research-graphics" --cache "$work/research-graphics-cache")"
  mkdir -p "$work/research-browser"
  cp studios/infographic/tests/ui/package*.json "$work/research-browser/"
  touch "$work/research-npm-user.conf" "$work/research-npm-global.conf"
  env HOME="$work/research-browser-home" NPM_CONFIG_USERCONFIG="$work/research-npm-user.conf" NPM_CONFIG_GLOBALCONFIG="$work/research-npm-global.conf" \
    npm ci --prefix "$work/research-browser" --ignore-scripts --no-audit --no-fund > "$results_dir/research-browser-tools.log" 2>&1
  export NODE_PATH="$work/research-browser/node_modules" PYTHON="$python" INFOGRAPHIC_UI_RESULTS="$results_dir/research-ui"
  node studios/infographic/tests/ui/research.cjs 2>&1 | tee "$results_dir/research-browser.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
elif [[ "${1:-full}" == research-citation-finish ]]; then
  # The full root, Blog Studio, Presentation Studio and remaining Training Studio
  # classes passed. Finish the CLI class after isolating its HOME snapshot, then
  # run the package check and all disposable CLI acceptance journeys.
  (
    cd studios/training
    "$python" scripts/ci/run_tests.py test_cli.ContractTests
    "$python" skills/training-studio/scripts/validate_package.py
  ) 2>&1 | tee "$results_dir/research-citation-final-tests.log"
  bash scripts/ci/acceptance.sh "$python" "$results_dir/checks" 2>&1 | tee "$results_dir/tests.log"
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
  # The shared research contract reaches every research-capable studio. Cover the
  # full root suite, all affected native suites, and synthetic CLI journeys.
  {
    "$python" -m unittest discover -s tests -v
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
