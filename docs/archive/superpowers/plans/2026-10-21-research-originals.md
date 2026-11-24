# Research checks that can read what they must attest to: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** the independent research check can read a supplied document's original, an
original is only claimed when it is distinct, a check that cannot finish for a studio
reason stops at once with the cause, real objections are grouped, and the cost of the
rounds is shown. Spec: `../specs/2026-10-21-research-originals-design.md`.

Tests use disposable settings, workspaces and data roots; never the person's studio state;
no provider jobs. Training tests run from `studios/training/tests`, Presentation tests from
`studios/presentation/tests`, core tests from the repository root with `PYTHONPATH=.:tests`.

## Task 1: Originals readable by the checker's tools

Files: `studios/training/runner/worker_tools.py`, `studios/presentation/runner/worker_tools.py`
(`_source`, `read_source`, `search_source`, `list_inputs`), their tests
(`test_runner_worker_tools.py` or the nearest).

- [ ] Tests: a job with a source whose `original` is `.md` serves it with `original=true`
      as text; a `.pdf` original serves the extracted text with a first line naming the
      format, byte size and sha256; a source without an original refuses with a sentence;
      `search_source(original=true)`; `list_inputs` names the original and the flag;
      paths stay inside the job folder.
- [ ] Implement in both studios (the two files are near-copies; change both the same way).
- [ ] Commit: "Let the research check read a supplied document's original".

## Task 2: An original only when it is distinct

Files: `core/studio_core/research_contract.py` (`native`), `studios/training/runner/documents.py`,
`studios/presentation/runner/documents.py`, tests beside each.

- [ ] Tests: a Google Doc material (`.md` original whose text equals the capture) passes no
      `original`; a `.pdf` or `.docx` does; `native()` offers `original` only when given.
- [ ] Commit: "Claim an original only when it differs from the capture".

## Task 3: Stop at once when the check cannot finish

Files: `core/studio_core/research_contract.py` (`Workflow.run`, a new
`unreadable_originals(review)`), `studios/training/runner/engine.py` and
`studios/presentation/runner/research_steps.py` (the refusal handling added on 2026-10-21),
`tests/test_research_contract.py`, the studios' engine tests.

- [ ] Tests: after a review whose non-supported verdicts all name sources with
      `read_original: false`, `run()` raises `CheckCouldNotFinish` (a `ReviewRefused` with
      `cause`) before another author round; the engines stop with the spec's message,
      naming the source and the access error, and count no correction round; Try again is
      refused with the same message while a dry `read_source(original=true)` fails.
- [ ] Commit: "Stop a research check that cannot finish instead of correcting nothing".

## Task 4: Objections grouped, and the cost of the rounds

Files: `core/studio_core/research_contract.py` (`objections`, `ReviewRefused`), the two
engines (review file, problem text), the desk pages' cost card, tests.

- [ ] Tests: objections are grouped by kind and verdict with a count and the first note;
      the review file lists them under their group; each round's tokens and seconds are
      recorded on the run and the stop message names the total.
- [ ] Commit: "Group research objections by cause and say what the rounds cost".

## Task 5: Docs and the full check

- [ ] Training and Presentation docs where the independent check is described
      (`docs/runner.md`, `docs/how-it-works.md`, references), root `docs/` if the research
      contract is described there.
- [ ] Full check: core `tests/test_research_contract.py`; Training `test_runner_engine.py`,
      `test_runner_worker_tools.py`, `test_synthesis_integration.py`; Presentation
      `test_runner_research.py`, worker tools and research steps tests; root
      `test_ui_consistency`. Compare failures with a clean `origin/main` export.
- [ ] Commit: "Document the research check's originals".
