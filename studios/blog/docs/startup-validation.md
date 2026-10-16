# Startup and computer checks

The startup experience follows Training Studio’s permanent shell command, Mac
launcher, supported-Python search, and computer report. Blog Studio checks its
own requirements: local writing does not need Git, GitHub CLI, Node, a brand
skill, or slide/research companions. Team Hub tools are reported separately.

## What is covered

- Setup writes `studio` and `blog` beside the managed `current` link, and
  `Open Blog Studio.command` in the chosen home’s Applications folder on macOS.
- Both shell commands follow `current`, quote paths with spaces, try the setup
  interpreter before other supported Pythons, and explain how to repair a missing
  runtime. An older runtime can still open through its original helper.
- The page remembers an explicitly selected workspace and starts without opting
  into source analysis. No session key or provider output is stored in that
  preference or the running-process receipts.
- Setup, installed `studio check`, and the UI Status screen use the same bounded,
  read-only computer report. Codex sign-in is reported from its status command;
  Claude sign-in remains a manual check until a job runs. Reports contain no raw
  provider output or account identity.
- A shared process lease blocks install, repair, rollback and uninstall while a
  page is serving. It releases on normal stop, Ctrl-C, SIGTERM or window hangup.
  File and computer checks remain available while serving.
- Updates preserve foreign or edited launchers. Final-target uninstall removes
  only unchanged launchers recorded by setup, retaining writing and versions.

## Commands and outcomes

All new fixtures use disposable homes, synthetic documents and stand-in CLIs.
No credentials or private team content were copied into them.

- `python -m unittest discover -s tests -p test_installation.py`: 38 passed,
  including launchers, fallback Python, ownership, update/rollback/removal and
  running-page protection.
- `python -m unittest discover -s tests -p test_startup.py`: 7 passed, including
  the real start process, graceful SIGTERM, remembered workspace, missing tools,
  sign-in limits, a usable login command for bundled Codex, and Apple’s
  unconfigured Git placeholder.
- `node scripts/ci/check-management.cjs`: passed, including rendered computer
  checks and next-step instructions. The existing page-opening test also passed
  with a disposable application-data folder.
- The real installer/startup walkthrough passed 10 recorded commands and 12
  checks: install, helper init, computer check, running-page update refusal,
  reopening the remembered workspace, stop, update, rollback, file check and
  removal. Custom launcher edits and synthetic writing survived. Report:
  `/tmp/blog-startup-acceptance.json`.
- `python scripts/acceptance/hub-journey.py --local-fixture --run-directory
  /tmp/blog-studio-startup-parity-hub-20261014`: PASS, all 41 real CLI steps.
  Covers create/join, source and voice intake, saves, reviews, cross-clone
  resume/edit, offline queue/retry, status, readable folders and overwrite guards.
- The full local command is `BLOG_STUDIO_TEST_JOBS=8 bash scripts/ci/check.sh
  "$PWD/.venv/bin/python" /tmp/blog-studio-startup-parity-check-final-20261014`.
  Its detailed results are retained there and summarized on the pull request.
  The existing Tart workflow provides the full platform matrix; no workflow
  files changed.

The collaborative browser rendered the shipped page and successfully requested
and refreshed `/api/computer` from the installed server, with its authenticated
HTTP transport forwarded by the test harness because direct browser loopback
was unavailable. Desktop and 390-pixel mobile layouts were inspected; mobile
had no horizontal overflow. This is bridged browser/server evidence. The new
shell commands and server also ran as real local processes.

No live model jobs, provider sign-ins, multi-account GitHub permissions, Google
transfers, or Finder GUI launch were exercised. The Mac launcher’s generated
shell and file lifecycle were tested in a disposable home. Two local clones of
one fixture account do not establish multi-account permissions.
